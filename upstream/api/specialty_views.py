"""
Specialty Module API Views

API endpoints for specialty-specific data and validation.

Endpoints:
- GET /api/v1/specialty/dialysis/baselines/ - list MA baselines
- GET /api/v1/specialty/aba/authorizations/ - list ABA auth tracking
- GET /api/v1/specialty/imaging/pa-requirements/ - list PA requirements
- POST /api/v1/specialty/validate/ - run specialty validation for claim
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import serializers
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiExample,
    OpenApiParameter,
)

from upstream.api.views import CustomerFilterMixin, IsCustomerMember
from upstream.products.dialysis.models import DialysisMABaseline
from upstream.products.aba.models import ABAAuthorizationTracker
from upstream.products.imaging.models import ImagingPARequirement
from upstream.services.scoring import RiskScoringService


# Serializers


class DialysisMABaselineSerializer(serializers.ModelSerializer):
    """Serializer for DialysisMABaseline model."""

    class Meta:
        model = DialysisMABaseline
        fields = [
            "id",
            "cpt",
            "payer",
            "average_payment",
            "sample_size",
            "effective_date",
            "end_date",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ABAAuthorizationTrackerSerializer(serializers.ModelSerializer):
    """Serializer for ABAAuthorizationTracker model."""

    percent_used = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = ABAAuthorizationTracker
        fields = [
            "id",
            "patient_id",
            "authorization_number",
            "payer",
            "service_type",
            "units_authorized",
            "units_used",
            "percent_used",
            "auth_start_date",
            "auth_end_date",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_percent_used(self, obj):
        """Calculate percentage of units used."""
        if obj.units_authorized > 0:
            return round((obj.units_used / obj.units_authorized) * 100, 1)
        return 0.0

    def get_is_active(self, obj):
        """Check if authorization is currently active."""
        return obj.is_active


class ImagingPARequirementSerializer(serializers.ModelSerializer):
    """Serializer for ImagingPARequirement model."""

    is_active = serializers.SerializerMethodField()

    class Meta:
        model = ImagingPARequirement
        fields = [
            "id",
            "payer",
            "cpt",
            "pa_required",
            "rbm_provider",
            "effective_date",
            "end_date",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_is_active(self, obj):
        """Check if PA requirement is currently active."""
        return obj.is_active


class SpecialtyValidationRequestSerializer(serializers.Serializer):
    """Serializer for specialty validation request."""

    service_type = serializers.ChoiceField(
        choices=[
            ("DIALYSIS", "Dialysis"),
            ("ABA", "ABA Therapy"),
            ("PTOT", "PT/OT"),
            ("IMAGING", "Imaging"),
            ("HOME_HEALTH", "Home Health"),
        ],
        help_text="Service type for specialty validation",
    )
    cpt = serializers.CharField(
        max_length=20,
        required=False,
        help_text="CPT code for the service",
    )
    payer = serializers.CharField(
        max_length=100,
        required=False,
        help_text="Payer name",
    )
    paid_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        help_text="Paid amount (for dialysis MA variance)",
    )
    total_minutes = serializers.IntegerField(
        required=False,
        help_text="Total treatment time in minutes (for PT/OT)",
    )
    procedure_count = serializers.IntegerField(
        required=False,
        help_text="Number of units billed",
    )
    specialty_metadata = serializers.DictField(
        required=False,
        help_text="Additional specialty-specific data",
    )


class SpecialtyValidationResponseSerializer(serializers.Serializer):
    """Serializer for specialty validation response."""

    service_type = serializers.CharField()
    is_compliant = serializers.BooleanField()
    risk_adjustment = serializers.FloatField()
    violations = serializers.ListField(child=serializers.CharField())
    requires_review = serializers.BooleanField()
    details = serializers.DictField()


# ViewSets


@extend_schema_view(
    list=extend_schema(
        summary="List dialysis MA baselines",
        description=(
            "Retrieve a list of Medicare Advantage payment baselines for dialysis "
            "services. Use these baselines to detect payment variance."
        ),
        tags=["Specialty - Dialysis"],
        parameters=[
            OpenApiParameter(
                name="cpt",
                type=str,
                description="Filter by CPT code",
                required=False,
            ),
            OpenApiParameter(
                name="payer",
                type=str,
                description="Filter by payer name",
                required=False,
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Get dialysis MA baseline details",
        description="Retrieve details for a specific MA baseline entry.",
        tags=["Specialty - Dialysis"],
    ),
)
class DialysisMABaselineViewSet(
    CustomerFilterMixin, viewsets.ReadOnlyModelViewSet
):
    """
    API endpoint for viewing dialysis MA baselines.

    These baselines are used to detect Medicare Advantage underpayment.
    """

    queryset = DialysisMABaseline.objects.all().order_by("-created_at")
    serializer_class = DialysisMABaselineSerializer
    permission_classes = [IsAuthenticated, IsCustomerMember]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["cpt", "payer"]


@extend_schema_view(
    list=extend_schema(
        summary="List ABA authorization trackers",
        description=(
            "Retrieve a list of ABA therapy authorization trackers. "
            "Monitor unit usage against authorized limits."
        ),
        tags=["Specialty - ABA"],
        parameters=[
            OpenApiParameter(
                name="patient_id",
                type=str,
                description="Filter by patient ID",
                required=False,
            ),
            OpenApiParameter(
                name="payer",
                type=str,
                description="Filter by payer name",
                required=False,
            ),
            OpenApiParameter(
                name="service_type",
                type=str,
                description="Filter by service type",
                required=False,
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Get ABA authorization details",
        description="Retrieve details for a specific ABA authorization tracker.",
        tags=["Specialty - ABA"],
    ),
)
class ABAAuthorizationTrackerViewSet(
    CustomerFilterMixin, viewsets.ReadOnlyModelViewSet
):
    """
    API endpoint for viewing ABA authorization trackers.

    Track unit usage against authorized limits for ABA therapy.
    """

    queryset = ABAAuthorizationTracker.objects.all().order_by("-created_at")
    serializer_class = ABAAuthorizationTrackerSerializer
    permission_classes = [IsAuthenticated, IsCustomerMember]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["patient_id", "payer", "service_type"]

    @extend_schema(
        summary="Get active authorizations",
        description="Retrieve only active (non-expired) ABA authorizations.",
        tags=["Specialty - ABA"],
    )
    @action(detail=False, methods=["get"])
    def active(self, request):
        """Get only active authorizations."""
        queryset = self.get_queryset()
        # Filter for active authorizations using model property logic
        from django.utils import timezone
        today = timezone.now().date()
        queryset = queryset.filter(
            auth_start_date__lte=today,
            auth_end_date__gte=today,
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Get authorizations approaching limit",
        description="Retrieve authorizations with >80% units used.",
        tags=["Specialty - ABA"],
    )
    @action(detail=False, methods=["get"])
    def approaching_limit(self, request):
        """Get authorizations approaching their unit limit (>80% used)."""
        queryset = self.get_queryset()
        # Filter using raw SQL since we need a calculated field
        from django.db.models import F, ExpressionWrapper, FloatField
        queryset = queryset.annotate(
            percent=ExpressionWrapper(
                F("units_used") * 100.0 / F("units_authorized"),
                output_field=FloatField(),
            )
        ).filter(percent__gte=80, units_authorized__gt=0)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(
        summary="List imaging PA requirements",
        description=(
            "Retrieve a list of prior authorization requirements for imaging "
            "procedures by payer and CPT code."
        ),
        tags=["Specialty - Imaging"],
        parameters=[
            OpenApiParameter(
                name="payer",
                type=str,
                description="Filter by payer name",
                required=False,
            ),
            OpenApiParameter(
                name="cpt",
                type=str,
                description="Filter by CPT code",
                required=False,
            ),
            OpenApiParameter(
                name="rbm_provider",
                type=str,
                description="Filter by RBM provider",
                required=False,
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Get imaging PA requirement details",
        description="Retrieve details for a specific PA requirement.",
        tags=["Specialty - Imaging"],
    ),
)
class ImagingPARequirementViewSet(
    CustomerFilterMixin, viewsets.ReadOnlyModelViewSet
):
    """
    API endpoint for viewing imaging PA requirements.

    Check prior authorization requirements by payer and CPT code.
    """

    queryset = ImagingPARequirement.objects.all().order_by("payer", "cpt")
    serializer_class = ImagingPARequirementSerializer
    permission_classes = [IsAuthenticated, IsCustomerMember]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["payer", "cpt", "rbm_provider", "pa_required"]

    @extend_schema(
        summary="Check PA requirement for payer/CPT",
        description=(
            "Look up the current PA requirement for a specific payer and CPT code."
        ),
        tags=["Specialty - Imaging"],
        parameters=[
            OpenApiParameter(
                name="payer",
                type=str,
                description="Payer name",
                required=True,
            ),
            OpenApiParameter(
                name="cpt",
                type=str,
                description="CPT code",
                required=True,
            ),
        ],
    )
    @action(detail=False, methods=["get"])
    def lookup(self, request):
        """Look up PA requirement for specific payer/CPT."""
        payer = request.query_params.get("payer")
        cpt = request.query_params.get("cpt")

        if not payer or not cpt:
            return Response(
                {"error": "Both payer and cpt parameters are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        requirement = ImagingPARequirement.get_requirement(payer, cpt)
        if requirement:
            serializer = self.get_serializer(requirement)
            return Response(serializer.data)
        return Response(
            {"message": "No PA requirement found for this payer/CPT combination"},
            status=status.HTTP_404_NOT_FOUND,
        )


@extend_schema(
    summary="Run specialty validation",
    description=(
        "Run specialty-specific validation for a claim. "
        "Routes to the appropriate specialty service based on service_type "
        "and returns compliance status, violations, and risk adjustment."
    ),
    tags=["Specialty - Validation"],
    request=SpecialtyValidationRequestSerializer,
    responses={200: SpecialtyValidationResponseSerializer},
    examples=[
        OpenApiExample(
            "Dialysis Validation Request",
            value={
                "service_type": "DIALYSIS",
                "cpt": "90935",
                "payer": "Aetna MA",
                "paid_amount": "180.00",
            },
            request_only=True,
        ),
        OpenApiExample(
            "PT/OT Validation Request",
            value={
                "service_type": "PTOT",
                "cpt": "97110",
                "total_minutes": 15,
                "procedure_count": 2,
            },
            request_only=True,
        ),
        OpenApiExample(
            "Validation Response - Compliant",
            value={
                "service_type": "DIALYSIS",
                "is_compliant": True,
                "risk_adjustment": 0.0,
                "violations": [],
                "requires_review": False,
                "details": {},
            },
            response_only=True,
        ),
        OpenApiExample(
            "Validation Response - Non-Compliant",
            value={
                "service_type": "PTOT",
                "is_compliant": False,
                "risk_adjustment": 0.15,
                "violations": [
                    "OVERBILLED: 2 units for 15 min, expected 1"
                ],
                "requires_review": False,
                "details": {
                    "total_minutes": 15,
                    "expected_units": 1,
                    "billed_units": 2,
                    "unit_difference": 1,
                },
            },
            response_only=True,
        ),
    ],
)
class SpecialtyValidationView(APIView):
    """
    API endpoint for running specialty-specific validation.

    Accepts claim data and returns validation results from the
    appropriate specialty service.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Run specialty validation for a claim."""
        serializer = SpecialtyValidationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Build claim_data dict from validated data
        claim_data = serializer.validated_data.copy()

        # Run specialty validation
        result = RiskScoringService.validate_specialty(claim_data)

        if result is None:
            return Response(
                {"error": "No specialty validation available for this service type"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        response_serializer = SpecialtyValidationResponseSerializer({
            "service_type": result.service_type,
            "is_compliant": result.is_compliant,
            "risk_adjustment": result.risk_adjustment,
            "violations": result.violations,
            "requires_review": result.requires_review,
            "details": result.details,
        })

        return Response(response_serializer.data)
