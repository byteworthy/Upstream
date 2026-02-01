"""
Upstream API Views

RESTful API endpoints for the Upstream platform.
All views enforce multi-tenant access control.

## Authentication

All API endpoints (except /health and /auth/*) require JWT authentication.
Include the access token in the Authorization header:

    Authorization: Bearer <access_token>

### Authentication Flow

1. **Login**: POST to /api/v1/auth/token/ with username/password
   - Returns access token (1 hour expiry) and refresh token (24 hour expiry)
   - Access token is used for all subsequent API requests

2. **API Requests**: Include access token in Authorization header
   - Example: Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGci...

3. **Token Refresh**: POST to /api/v1/auth/token/refresh/ with refresh token
   - Returns new access token when current one expires
   - Avoids requiring user to re-enter credentials

4. **Token Verify**: POST to /api/v1/auth/token/verify/ with token
   - Checks if token is valid and not expired
   - Returns 200 if valid, 401 if invalid

### RBAC Roles and Permissions

The system supports three user roles with different permission levels:

- **Superuser (Django superuser)**: Full access to all resources across all customers
  - Can view and manage data for any customer
  - Bypass tenant isolation filters
  - Access Django admin interface

- **Customer Admin (customer_admin role)**: Full access to their customer's data
  - View, create, update, and delete all resources for their customer
  - Manage uploads, reports, alerts, and configurations
  - Cannot access other customers' data (tenant-isolated)

- **Customer Viewer (customer_viewer role)**: Read-only access to their customer's data
  - View uploads, claims, reports, and alerts for their customer
  - Cannot create, update, or delete resources
  - Cannot access other customers' data (tenant-isolated)

All non-superuser API requests are automatically filtered to the user's customer
via the CustomerFilterMixin. Attempting to access another customer's resources
will return 404 Not Found.
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Avg, Q
from django.db import connection
from django.utils import timezone
from django.utils.cache import patch_cache_control
from django.core.cache import cache
from django.conf import settings
import time
import shutil
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiParameter,
    OpenApiExample,
)
from drf_spectacular.types import OpenApiTypes
from datetime import datetime, timedelta
from django_filters.rest_framework import DjangoFilterBackend

# HIGH-2: JWT auth views with rate limiting
from rest_framework_simplejwt.views import (
    TokenObtainPairView as BaseTokenObtainPairView,
    TokenRefreshView as BaseTokenRefreshView,
    TokenVerifyView as BaseTokenVerifyView,
)

# QW-5: Import custom throttle classes
from .throttling import (
    ReportGenerationThrottle,
    BulkOperationThrottle,
    ReadOnlyThrottle,
    AuthenticationThrottle,
)

from ..models import (
    Customer,
    CustomerSpecialtyModule,
    Settings,
    Upload,
    ClaimRecord,
    ReportRun,
    DriftEvent,
    PayerMapping,
    CPTGroupMapping,
    NetworkAlert,
)
from upstream.alerts.models import AlertEvent, OperatorJudgment
from upstream.automation.models import (
    ClaimScore,
    CustomerAutomationProfile,
    ShadowModeResult,
)
from upstream.ingestion.models import IngestionToken
from upstream.ingestion import IngestionService
from upstream.services.scoring import RiskScoringService
from .serializers import (
    CustomerSerializer,
    CustomerWithSpecialtiesSerializer,
    SetPrimarySpecialtySerializer,
    EnableSpecialtySerializer,
    SettingsSerializer,
    UploadSerializer,
    UploadSummarySerializer,
    ClaimRecordSerializer,
    ClaimRecordSummarySerializer,
    ReportRunSerializer,
    ReportRunSummarySerializer,
    DriftEventSerializer,
    PayerMappingSerializer,
    CPTGroupMappingSerializer,
    PayerSummarySerializer,
    DashboardSerializer,
    AlertEventSerializer,
    OperatorJudgmentSerializer,
    OperatorFeedbackSerializer,
    ErrorResponseSerializer,
    ClaimScoreSerializer,
    CustomerAutomationProfileSerializer,
    ShadowModeResultSerializer,
    NetworkAlertSerializer,
)
from .permissions import IsCustomerMember, get_user_customer
from .filters import ClaimRecordFilter, DriftEventFilter


class ETagMixin:
    """
    Mixin to add ETag support for API ViewSets.

    Configures Cache-Control headers to enable HTTP caching with ETags.
    Django's ConditionalGetMiddleware automatically generates ETag headers
    and handles If-None-Match validation to return 304 Not Modified responses.

    - GET requests: cacheable with max-age=60 and must-revalidate
    - Other methods (POST/PUT/DELETE): no-cache, no-store, must-revalidate
    """

    def finalize_response(self, request, response, *args, **kwargs):
        """Configure Cache-Control headers based on request method."""
        response = super().finalize_response(request, response, *args, **kwargs)

        if request.method == "GET" and response.status_code == 200:
            # GET requests are cacheable: 60 second max age with revalidation
            patch_cache_control(response, max_age=60, must_revalidate=True)
        else:
            # Non-GET requests (POST/PUT/DELETE) should not be cached
            patch_cache_control(
                response, no_cache=True, no_store=True, must_revalidate=True
            )

        return response


class CustomerFilterMixin:
    """
    Mixin to automatically filter querysets to the user's customer.
    """

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        # Superusers see all data
        if user.is_superuser:
            return (
                queryset.model.objects.unscoped()
                if hasattr(queryset.model.objects, "unscoped")
                else queryset
            )

        # Regular users only see their customer's data
        customer = get_user_customer(user)
        if customer is None:
            return queryset.none()

        # Filter by customer field - use for_customer() to avoid
        # double-filtering with tenant isolation
        if hasattr(queryset.model, "customer"):
            # Use for_customer() which bypasses auto-filtering and explicitly filters
            if hasattr(queryset.model.objects, "for_customer"):
                return queryset.model.objects.for_customer(customer)
            else:
                return queryset.filter(customer=customer)

        return queryset


@extend_schema_view(
    list=extend_schema(
        summary="List customers",
        description=(
            "Retrieve a list of customers. Regular users only see their own "
            "customer; superusers see all."
        ),
        tags=["Customers"],
        responses={
            200: CustomerSerializer(many=True),
            401: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
            429: ErrorResponseSerializer,
        },
    ),
    retrieve=extend_schema(
        summary="Get customer details",
        description="Retrieve detailed information for a specific customer.",
        tags=["Customers"],
        responses={
            200: CustomerSerializer,
            401: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
            429: ErrorResponseSerializer,
        },
    ),
)
class CustomerViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing customer information.
    Users can only see their own customer.

    Includes specialty module management:
    - GET /customers/me/ - Get current customer with specialty info
    - POST /customers/set_primary_specialty/ - Set primary specialty (onboarding)
    - POST /customers/enable_specialty/ - Enable add-on module
    - POST /customers/disable_specialty/ - Disable add-on module
    """

    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated, IsCustomerMember]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Customer.objects.prefetch_related("specialty_modules").all()

        customer = get_user_customer(user)
        if customer:
            return Customer.objects.prefetch_related("specialty_modules").filter(
                id=customer.id
            )
        return Customer.objects.none()

    @extend_schema(
        summary="Get current customer with specialties",
        description=(
            "Get the authenticated user's customer profile including "
            "primary specialty, enabled add-on modules, and convenience "
            "list of all enabled specialties."
        ),
        tags=["Customers"],
        responses={
            200: CustomerWithSpecialtiesSerializer,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
    @action(detail=False, methods=["get"])
    def me(self, request):
        """Get current user's customer with specialty information."""
        customer = get_user_customer(request.user)
        if not customer:
            return Response(
                {"error": "No customer found for user"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Prefetch specialty modules for efficiency
        customer = (
            Customer.objects.prefetch_related("specialty_modules")
            .filter(id=customer.id)
            .first()
        )

        serializer = CustomerWithSpecialtiesSerializer(
            customer, context={"request": request}
        )
        return Response(serializer.data)

    @extend_schema(
        summary="Set primary specialty",
        description=(
            "Set the customer's primary specialty. Typically done during "
            "onboarding. Creates a corresponding CustomerSpecialtyModule "
            "entry marked as primary."
        ),
        tags=["Customers"],
        request=SetPrimarySpecialtySerializer,
        responses={
            200: CustomerWithSpecialtiesSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
    @action(detail=False, methods=["post"])
    def set_primary_specialty(self, request):
        """Set primary specialty during onboarding."""
        customer = get_user_customer(request.user)
        if not customer:
            return Response(
                {"error": "No customer found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = SetPrimarySpecialtySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        specialty = serializer.validated_data["specialty_type"]

        # Update customer's primary specialty
        customer.specialty_type = specialty
        customer.save(update_fields=["specialty_type"])

        # Create or update specialty module as primary and enabled
        CustomerSpecialtyModule.objects.update_or_create(
            customer=customer,
            specialty=specialty,
            defaults={"is_primary": True, "enabled": True},
        )

        # Ensure other modules are not marked as primary
        CustomerSpecialtyModule.objects.filter(customer=customer).exclude(
            specialty=specialty
        ).update(is_primary=False)

        # Refresh customer and return
        customer.refresh_from_db()
        return Response(
            CustomerWithSpecialtiesSerializer(
                customer, context={"request": request}
            ).data
        )

    @extend_schema(
        summary="Enable specialty module",
        description=(
            "Enable an additional specialty module for the customer. "
            "This is typically a paid add-on (+$99/mo per module). "
            "Cannot enable a specialty that is already the primary."
        ),
        tags=["Customers"],
        request=EnableSpecialtySerializer,
        responses={
            200: CustomerWithSpecialtiesSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
    @action(detail=False, methods=["post"])
    def enable_specialty(self, request):
        """Enable an additional specialty module."""
        customer = get_user_customer(request.user)
        if not customer:
            return Response(
                {"error": "No customer found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = EnableSpecialtySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        specialty = serializer.validated_data["specialty"]

        # Create or enable module
        module, created = CustomerSpecialtyModule.objects.get_or_create(
            customer=customer,
            specialty=specialty,
            defaults={
                "enabled": True,
                "is_primary": customer.specialty_type == specialty,
            },
        )

        if not created and not module.enabled:
            module.enabled = True
            module.save(update_fields=["enabled"])

        # Refresh and return
        customer.refresh_from_db()
        return Response(
            CustomerWithSpecialtiesSerializer(
                customer, context={"request": request}
            ).data
        )

    @extend_schema(
        summary="Disable specialty module",
        description=(
            "Disable a specialty module. Cannot disable the primary specialty. "
            "The module is not deleted, just marked as disabled."
        ),
        tags=["Customers"],
        request=EnableSpecialtySerializer,
        responses={
            200: CustomerWithSpecialtiesSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
    @action(detail=False, methods=["post"])
    def disable_specialty(self, request):
        """Disable a specialty module."""
        customer = get_user_customer(request.user)
        if not customer:
            return Response(
                {"error": "No customer found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = EnableSpecialtySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        specialty = serializer.validated_data["specialty"]

        # Cannot disable primary specialty
        if customer.specialty_type == specialty:
            return Response(
                {"error": "Cannot disable primary specialty"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Disable module (don't delete, just mark as disabled)
        CustomerSpecialtyModule.objects.filter(
            customer=customer,
            specialty=specialty,
        ).update(enabled=False)

        # Refresh and return
        customer.refresh_from_db()
        return Response(
            CustomerWithSpecialtiesSerializer(
                customer, context={"request": request}
            ).data
        )


@extend_schema_view(
    list=extend_schema(
        summary="List settings",
        description=(
            "Retrieve customer settings. Returns settings for the "
            "authenticated user's customer."
        ),
        tags=["Settings"],
        responses={
            200: SettingsSerializer(many=True),
            401: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
            429: ErrorResponseSerializer,
        },
    ),
    retrieve=extend_schema(
        summary="Get settings",
        description=(
            "Retrieve specific customer settings. Gets or creates settings "
            "for the user's customer."
        ),
        tags=["Settings"],
        responses={
            200: SettingsSerializer,
            401: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
            429: ErrorResponseSerializer,
        },
    ),
    create=extend_schema(
        summary="Create settings",
        description="Create new customer settings with email notification preferences.",
        tags=["Settings"],
        examples=[
            OpenApiExample(
                "Create Settings",
                value={
                    "to_email": "alerts@example.com",
                    "cc_email": "team@example.com",
                    "attach_pdf": True,
                },
                request_only=True,
            ),
        ],
        responses={
            201: SettingsSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
            429: ErrorResponseSerializer,
        },
    ),
    update=extend_schema(
        summary="Update settings",
        description="Update all customer settings fields.",
        tags=["Settings"],
        examples=[
            OpenApiExample(
                "Update Settings",
                value={
                    "to_email": "alerts@example.com",
                    "cc_email": "team@example.com",
                    "attach_pdf": False,
                },
                request_only=True,
            ),
        ],
        responses={
            200: SettingsSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
            429: ErrorResponseSerializer,
        },
    ),
    partial_update=extend_schema(
        summary="Partially update settings",
        description="Update specific customer settings fields.",
        tags=["Settings"],
        examples=[
            OpenApiExample(
                "Partial Update",
                value={"attach_pdf": False},
                request_only=True,
            ),
        ],
        responses={
            200: SettingsSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
            429: ErrorResponseSerializer,
        },
    ),
    destroy=extend_schema(
        summary="Delete settings",
        description="Delete customer settings.",
        tags=["Settings"],
        responses={
            204: None,
            401: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
            429: ErrorResponseSerializer,
        },
    ),
)
class SettingsViewSet(CustomerFilterMixin, viewsets.ModelViewSet):
    """
    API endpoint for managing customer settings.
    """

    queryset = Settings.objects.all()
    serializer_class = SettingsSerializer
    permission_classes = [IsAuthenticated, IsCustomerMember]

    def get_object(self):
        """Get or create settings for the user's customer."""
        customer = get_user_customer(self.request.user)
        if customer:
            settings, _ = Settings.objects.get_or_create(customer=customer)
            return settings
        return super().get_object()


@extend_schema_view(
    list=extend_schema(
        summary="List uploads",
        description=(
            "Retrieve a paginated list of file uploads with filtering and "
            "search. Returns summary data for performance. Supports pagination "
            "with page and page_size query parameters."
        ),
        tags=["Uploads"],
        parameters=[
            OpenApiParameter(
                name="page",
                type=int,
                description="Page number for pagination (default: 1)",
                required=False,
            ),
            OpenApiParameter(
                name="page_size",
                type=int,
                description="Number of results per page (default: 100, max: 1000)",
                required=False,
            ),
            OpenApiParameter(
                name="status",
                type=str,
                description="Filter by upload status (success, failed, processing)",
                required=False,
            ),
            OpenApiParameter(
                name="search",
                type=str,
                description="Search by filename or status",
                required=False,
            ),
            OpenApiParameter(
                name="ordering",
                type=str,
                description=(
                    "Order by: uploaded_at, status, row_count "
                    "(prefix with - for descending)"
                ),
                required=False,
            ),
        ],
        examples=[
            OpenApiExample(
                "Paginated Response",
                value={
                    "count": 150,
                    "next": "https://api.example.com/api/uploads/?page=2&page_size=10",
                    "previous": None,
                    "results": [
                        {
                            "id": 1,
                            "filename": "claims_2024_Q1.csv",
                            "status": "success",
                            "uploaded_at": "2024-01-15T10:30:00Z",
                            "row_count": 5000,
                        },
                        {
                            "id": 2,
                            "filename": "claims_2024_Q2.csv",
                            "status": "processing",
                            "uploaded_at": "2024-04-20T14:22:00Z",
                            "row_count": 0,
                        },
                    ],
                },
                response_only=True,
            ),
            OpenApiExample(
                "Filtered by Status",
                value={
                    "count": 5,
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": 3,
                            "filename": "claims_2024_Q3.csv",
                            "status": "failed",
                            "uploaded_at": "2024-07-10T09:15:00Z",
                            "row_count": 0,
                            "error_message": "Invalid CSV format",
                        },
                    ],
                },
                response_only=True,
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Get upload details",
        description=(
            "Retrieve detailed information for a specific upload including "
            "date range and row count."
        ),
        tags=["Uploads"],
    ),
    create=extend_schema(
        summary="Create upload",
        description=(
            "Create a new file upload record. Requires authentication - "
            "include JWT access token in Authorization header. Rate limited "
            "to 20 uploads/hour. User must have customer_admin role."
        ),
        tags=["Uploads"],
        examples=[
            OpenApiExample(
                "Create Upload",
                value={
                    "filename": "claims_2024_Q1.csv",
                    "date_min": "2024-01-01",
                    "date_max": "2024-03-31",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Create Success",
                value={
                    "id": 42,
                    "filename": "claims_2024_Q1.csv",
                    "status": "processing",
                    "uploaded_at": "2024-01-15T10:30:00Z",
                    "date_min": "2024-01-01",
                    "date_max": "2024-03-31",
                    "row_count": 0,
                },
                response_only=True,
                status_codes=["201"],
            ),
            OpenApiExample(
                "Unauthorized - Missing Token",
                value={"detail": "Authentication credentials were not provided."},
                response_only=True,
                status_codes=["401"],
            ),
            OpenApiExample(
                "Forbidden - Insufficient Permissions",
                value={
                    "detail": (
                        "You do not have permission to perform this action. "
                        "Requires customer_admin role."
                    )
                },
                response_only=True,
                status_codes=["403"],
            ),
        ],
    ),
    update=extend_schema(
        summary="Update upload",
        description="Update upload metadata (filename, date range).",
        tags=["Uploads"],
    ),
    partial_update=extend_schema(
        summary="Partially update upload",
        description="Update specific upload fields.",
        tags=["Uploads"],
    ),
    destroy=extend_schema(
        summary="Delete upload",
        description="Delete an upload record.",
        tags=["Uploads"],
    ),
)
class UploadViewSet(ETagMixin, CustomerFilterMixin, viewsets.ModelViewSet):
    """
    API endpoint for managing file uploads.
    Rate limit: 20 uploads/hour for bulk operations.
    """

    queryset = Upload.objects.all().order_by("-uploaded_at")
    serializer_class = UploadSerializer
    permission_classes = [IsAuthenticated, IsCustomerMember]
    throttle_classes = [BulkOperationThrottle]  # QW-5: Rate limit bulk uploads
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["status"]
    search_fields = ["filename", "status"]
    ordering_fields = ["uploaded_at", "status", "row_count"]

    def get_queryset(self):
        """Optimize queryset with select_related for detail views."""
        queryset = super().get_queryset()
        # HIGH-13: Add select_related to avoid N+1 queries
        # UploadSerializer includes 'customer' field, so prefetch it for detail views
        # PERF-03: Add select_related for list views to optimize N+1 queries
        # Story #3: Upload list view loads customer and uploaded_by for each upload
        if self.action in ("retrieve", "update", "partial_update"):
            queryset = queryset.select_related("customer")
        elif self.action == "list":
            # Optimize list view: load customer and uploaded_by in single query
            queryset = queryset.select_related("customer", "uploaded_by")
        return queryset

    def get_serializer_class(self):
        if self.action == "list":
            return UploadSummarySerializer
        return UploadSerializer

    @extend_schema(
        summary="Get upload statistics",
        description=(
            "Retrieve aggregated upload statistics including total uploads, "
            "success/failed/processing counts, and total claim records across "
            "all uploads. Uses optimized single-query aggregation for performance."
        ),
        tags=["Uploads"],
        responses={200: dict},
        examples=[
            OpenApiExample(
                "Upload Statistics",
                value={
                    "total": 150,
                    "success": 140,
                    "failed": 5,
                    "processing": 5,
                    "total_rows": 125000,
                },
                response_only=True,
            ),
        ],
    )
    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Get upload statistics for the customer."""
        queryset = self.get_queryset()

        # Optimize: Use single aggregate query instead of 4 separate COUNT queries
        # Before: 4 queries (total, success, failed, processing)
        # After: 1 query with conditional aggregation
        aggregates = queryset.aggregate(
            total=Count("id"),
            success=Count("id", filter=Q(status="success")),
            failed=Count("id", filter=Q(status="failed")),
            processing=Count("id", filter=Q(status="processing")),
            total_rows=Count("claim_records"),
        )

        stats = {
            "total": aggregates["total"] or 0,
            "success": aggregates["success"] or 0,
            "failed": aggregates["failed"] or 0,
            "processing": aggregates["processing"] or 0,
            "total_rows": aggregates["total_rows"] or 0,
        }
        return Response(stats)


@extend_schema_view(
    list=extend_schema(
        summary="List claim records",
        description=(
            "Retrieve a paginated list of claim records with filtering, "
            "search, and ordering. Returns summary data for performance. "
            "Rate limited to 2000 requests/hour. Supports pagination with "
            "page and page_size query parameters."
        ),
        tags=["Claims"],
        parameters=[
            OpenApiParameter(
                name="page",
                type=int,
                description="Page number for pagination (default: 1)",
                required=False,
            ),
            OpenApiParameter(
                name="page_size",
                type=int,
                description="Number of results per page (default: 100, max: 1000)",
                required=False,
            ),
            OpenApiParameter(
                name="payer",
                type=str,
                description="Filter by payer name (exact match)",
                required=False,
            ),
            OpenApiParameter(
                name="outcome",
                type=str,
                description="Filter by claim outcome (PAID, DENIED, OTHER)",
                required=False,
            ),
            OpenApiParameter(
                name="submitted_date_after",
                type=OpenApiTypes.DATE,
                description="Filter claims submitted after this date (YYYY-MM-DD)",
                required=False,
            ),
            OpenApiParameter(
                name="submitted_date_before",
                type=OpenApiTypes.DATE,
                description="Filter claims submitted before this date (YYYY-MM-DD)",
                required=False,
            ),
            OpenApiParameter(
                name="decided_date_after",
                type=OpenApiTypes.DATE,
                description="Filter claims decided after this date (YYYY-MM-DD)",
                required=False,
            ),
            OpenApiParameter(
                name="decided_date_before",
                type=OpenApiTypes.DATE,
                description="Filter claims decided before this date (YYYY-MM-DD)",
                required=False,
            ),
            OpenApiParameter(
                name="search",
                type=str,
                description="Search by payer, CPT code, or denial reason code",
                required=False,
            ),
            OpenApiParameter(
                name="ordering",
                type=str,
                description=(
                    "Order by: decided_date, submitted_date, payer, outcome "
                    "(prefix with - for descending)"
                ),
                required=False,
            ),
        ],
        examples=[
            OpenApiExample(
                "Paginated Response",
                value={
                    "count": 125000,
                    "next": "https://api.example.com/api/claims/?page=2&page_size=10",
                    "previous": None,
                    "results": [
                        {
                            "id": 1,
                            "payer": "Blue Cross Blue Shield",
                            "cpt": "99213",
                            "outcome": "PAID",
                            "submitted_date": "2024-01-10",
                            "decided_date": "2024-01-25",
                            "allowed_amount": "150.00",
                        },
                        {
                            "id": 2,
                            "payer": "Aetna",
                            "cpt": "99214",
                            "outcome": "DENIED",
                            "submitted_date": "2024-01-12",
                            "decided_date": "2024-01-28",
                            "allowed_amount": "0.00",
                            "denial_reason_code": "CO-97",
                        },
                    ],
                },
                response_only=True,
            ),
            OpenApiExample(
                "Filtered by Payer and Outcome",
                value={
                    "count": 45,
                    "next": (
                        "https://api.example.com/api/claims/"
                        "?payer=Aetna&outcome=DENIED&page=2"
                    ),
                    "previous": None,
                    "results": [
                        {
                            "id": 5,
                            "payer": "Aetna",
                            "cpt": "99215",
                            "outcome": "DENIED",
                            "submitted_date": "2024-01-20",
                            "decided_date": "2024-02-05",
                            "allowed_amount": "0.00",
                            "denial_reason_code": "CO-16",
                        },
                    ],
                },
                response_only=True,
            ),
            OpenApiExample(
                "Filtered by Date Range",
                value={
                    "count": 350,
                    "next": (
                        "https://api.example.com/api/claims/"
                        "?submitted_date_after=2024-01-01"
                        "&submitted_date_before=2024-01-31&page=2"
                    ),
                    "previous": None,
                    "results": [
                        {
                            "id": 10,
                            "payer": "UnitedHealthcare",
                            "cpt": "99213",
                            "outcome": "PAID",
                            "submitted_date": "2024-01-15",
                            "decided_date": "2024-01-30",
                            "allowed_amount": "145.00",
                        },
                    ],
                },
                response_only=True,
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Get claim record details",
        description="Retrieve detailed information for a specific claim record.",
        tags=["Claims"],
    ),
)
class ClaimRecordViewSet(ETagMixin, CustomerFilterMixin, viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing claim records.
    Supports filtering by payer, outcome, and date range.
    Rate limit: 2000 requests/hour for read operations.
    """

    queryset = ClaimRecord.objects.all().order_by("-decided_date")
    serializer_class = ClaimRecordSerializer
    permission_classes = [IsAuthenticated, IsCustomerMember]
    throttle_classes = [ReadOnlyThrottle]  # QW-5: Liberal rate limit for reads
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = ClaimRecordFilter
    search_fields = ["payer", "cpt", "denial_reason_code"]
    ordering_fields = ["decided_date", "submitted_date", "payer", "outcome"]

    def get_serializer_class(self):
        if self.action == "list":
            return ClaimRecordSummarySerializer
        return ClaimRecordSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        # HIGH-13: Add select_related to avoid N+1 queries
        # ClaimRecordSerializer includes 'customer' and 'upload' fields
        # PERF-04: Story #4 - Optimize list and retrieve views with select_related
        if self.action == "retrieve":
            queryset = queryset.select_related("customer", "upload")
        elif self.action == "list":
            # Optimize list view: load customer and upload in single query
            queryset = queryset.select_related("customer", "upload")

        return queryset

    @extend_schema(
        summary="Get payer summary statistics",
        description=(
            "Retrieve aggregated statistics by payer including total claims, "
            "paid/denied counts, denial rates, and average allowed amounts. "
            "Defaults to last 90 days for performance. Cached for 15 minutes. "
            "Results are paginated."
        ),
        tags=["Claims"],
        responses={200: PayerSummarySerializer(many=True)},
        parameters=[
            OpenApiParameter(
                name="start_date",
                type=OpenApiTypes.DATE,
                description="Start date (YYYY-MM-DD). Defaults to 90 days ago.",
                required=False,
            ),
            OpenApiParameter(
                name="end_date",
                type=OpenApiTypes.DATE,
                description="End date (YYYY-MM-DD). Defaults to today.",
                required=False,
            ),
            OpenApiParameter(
                name="page",
                type=int,
                description="Page number for pagination",
                required=False,
            ),
            OpenApiParameter(
                name="page_size",
                type=int,
                description="Number of results per page",
                required=False,
            ),
        ],
        examples=[
            OpenApiExample(
                "Payer Summary Response",
                value={
                    "count": 15,
                    "next": "https://api.example.com/api/claims/payer_summary/?page=2",
                    "previous": None,
                    "results": [
                        {
                            "payer": "Blue Cross Blue Shield",
                            "total_claims": 5234,
                            "paid_count": 4812,
                            "denied_count": 398,
                            "other_count": 24,
                            "denial_rate": 7.61,
                            "avg_allowed_amount": "187.50",
                        },
                        {
                            "payer": "Aetna",
                            "total_claims": 3156,
                            "paid_count": 2789,
                            "denied_count": 345,
                            "other_count": 22,
                            "denial_rate": 10.93,
                            "avg_allowed_amount": "165.23",
                        },
                        {
                            "payer": "UnitedHealthcare",
                            "total_claims": 2890,
                            "paid_count": 2601,
                            "denied_count": 276,
                            "other_count": 13,
                            "denial_rate": 9.55,
                            "avg_allowed_amount": "192.45",
                        },
                    ],
                },
                response_only=True,
            ),
            OpenApiExample(
                "Custom Date Range",
                value={
                    "count": 12,
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "payer": "Cigna",
                            "total_claims": 1256,
                            "paid_count": 1089,
                            "denied_count": 152,
                            "other_count": 15,
                            "denial_rate": 12.10,
                            "avg_allowed_amount": "175.89",
                        },
                    ],
                },
                response_only=True,
            ),
        ],
    )
    @action(detail=False, methods=["get"])
    def payer_summary(self, request):
        """
        Get aggregated statistics by payer.

        Performance: Defaults to last 90 days to prevent expensive
        full-table aggregation. Override with start_date/end_date params.
        """
        customer = get_user_customer(request.user)
        if not customer:
            return Response(
                {"error": "No customer associated with user"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Parse and validate date range parameters
        # Performance: Default to last 90 days to avoid full-table scan
        try:
            end_date = request.query_params.get("end_date")
            if end_date:
                end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
            else:
                end_date = timezone.now().date()

            start_date = request.query_params.get("start_date")
            if start_date:
                start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            else:
                # Default to 90 days ago
                start_date = end_date - timedelta(days=90)

            if start_date > end_date:
                return Response(
                    {"error": "start_date must be before end_date"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD (e.g., 2024-01-15)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # QW-4: Cache payer summary for 15 minutes (rarely changes, expensive query)
        # Include date range in cache key to avoid stale data
        cache_key = (
            f"payer_summary:customer:{customer.id}:"
            f"{start_date.isoformat()}:{end_date.isoformat()}"
        )
        cache_ttl = settings.CACHE_TTL.get("payer_mappings", 900)  # 15 minutes

        def compute_payer_summary():
            """Expensive aggregation query - cached to reduce DB load."""
            queryset = self.get_queryset()

            # Performance: Filter by date range to prevent full-table aggregation
            queryset = queryset.filter(
                submitted_date__gte=start_date, submitted_date__lte=end_date
            )

            payers = (
                queryset.values("payer")
                .annotate(
                    total_claims=Count("id"),
                    paid_count=Count("id", filter=Q(outcome="PAID")),
                    denied_count=Count("id", filter=Q(outcome="DENIED")),
                    other_count=Count("id", filter=Q(outcome="OTHER")),
                    avg_allowed_amount=Avg("allowed_amount"),
                )
                .order_by("-total_claims")
            )

            # Calculate denial rate
            results = []
            for p in payers:
                denial_rate = 0
                if p["total_claims"] > 0:
                    denial_rate = (p["denied_count"] / p["total_claims"]) * 100

                results.append(
                    {
                        "payer": p["payer"],
                        "total_claims": p["total_claims"],
                        "paid_count": p["paid_count"],
                        "denied_count": p["denied_count"],
                        "other_count": p["other_count"],
                        "denial_rate": round(denial_rate, 2),
                        "avg_allowed_amount": p["avg_allowed_amount"],
                    }
                )

            return results

        # Get from cache or compute and store
        results = cache.get_or_set(cache_key, compute_payer_summary, cache_ttl)

        # Apply pagination to results list
        page = self.paginate_queryset(results)
        if page is not None:
            serializer = PayerSummarySerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = PayerSummarySerializer(results, many=True)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(
        summary="List report runs",
        description=(
            "Retrieve a paginated list of report runs with their status and "
            "drift event counts."
        ),
        tags=["Reports"],
    ),
    retrieve=extend_schema(
        summary="Get report run details",
        description=(
            "Retrieve detailed information for a specific report run "
            "including all drift events."
        ),
        tags=["Reports"],
    ),
)
class ReportRunViewSet(ETagMixin, CustomerFilterMixin, viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing report runs and their results.
    """

    queryset = ReportRun.objects.all().order_by("-started_at")
    serializer_class = ReportRunSerializer
    permission_classes = [IsAuthenticated, IsCustomerMember]

    def get_queryset(self):
        # PERF-20: Annotate drift_event_count to avoid N+1 queries
        queryset = super().get_queryset()
        return queryset.annotate(drift_event_count=Count("drift_events"))

    def get_serializer_class(self):
        if self.action == "list":
            return ReportRunSummarySerializer
        return ReportRunSerializer

    @extend_schema(
        summary="Trigger a new report run",
        description=(
            "Trigger a new payer drift report run. Creates a report run and "
            "queues async processing to detect payer behavior drift. "
            "Rate limited to 10 requests/hour. Returns immediately with "
            "report run ID; processing continues asynchronously."
        ),
        tags=["Reports"],
        request=None,
        responses={
            202: ReportRunSerializer,
            400: OpenApiExample(
                "Error Response",
                value={"error": "No customer associated with user"},
                response_only=True,
            ),
        },
        examples=[
            OpenApiExample(
                "Report Triggered",
                value={
                    "id": 42,
                    "run_type": "weekly",
                    "status": "running",
                    "started_at": "2024-01-25T10:30:00Z",
                    "finished_at": None,
                    "drift_event_count": 0,
                },
                response_only=True,
            ),
        ],
    )
    @action(detail=False, methods=["post"], throttle_classes=[ReportGenerationThrottle])
    def trigger(self, request):
        """Trigger a new payer drift report run (Rate limit: 10/hour)."""
        customer = get_user_customer(request.user)
        if not customer:
            return Response(
                {"error": "No customer associated with user"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create a new report run
        report_run = ReportRun.objects.create(
            customer=customer, run_type="weekly", status="running"
        )

        # QW-4: Invalidate dashboard cache when new report is created
        cache_key = f"dashboard:customer:{customer.id}"
        cache.delete(cache_key)

        # Trigger async task to compute drift
        from upstream.tasks import compute_report_drift_task, enqueue_or_run_sync

        enqueue_or_run_sync(compute_report_drift_task, report_run.id)

        serializer = ReportRunSerializer(report_run)
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)


@extend_schema_view(
    list=extend_schema(
        summary="List drift events",
        description=(
            "Retrieve a paginated list of drift events with filtering, "
            "search, and ordering. Rate limited to 2000 requests/hour. "
            "Supports pagination with page and page_size query parameters."
        ),
        tags=["Drift Detection"],
        parameters=[
            OpenApiParameter(
                name="page",
                type=int,
                description="Page number for pagination (default: 1)",
                required=False,
            ),
            OpenApiParameter(
                name="page_size",
                type=int,
                description="Number of results per page (default: 100, max: 1000)",
                required=False,
            ),
            OpenApiParameter(
                name="payer",
                type=str,
                description="Filter by payer name (exact match)",
                required=False,
            ),
            OpenApiParameter(
                name="cpt_group",
                type=str,
                description="Filter by CPT group (exact match)",
                required=False,
            ),
            OpenApiParameter(
                name="drift_type",
                type=str,
                description=(
                    "Filter by drift type "
                    "(denial_rate, decision_time, allowed_amount)"
                ),
                required=False,
            ),
            OpenApiParameter(
                name="severity_min",
                type=OpenApiTypes.FLOAT,
                description="Filter by minimum severity (0.0-1.0)",
                required=False,
            ),
            OpenApiParameter(
                name="severity_max",
                type=OpenApiTypes.FLOAT,
                description="Filter by maximum severity (0.0-1.0)",
                required=False,
            ),
            OpenApiParameter(
                name="search",
                type=str,
                description="Search by payer, CPT group, or drift type",
                required=False,
            ),
            OpenApiParameter(
                name="ordering",
                type=str,
                description=(
                    "Order by: created_at, severity, payer "
                    "(prefix with - for descending)"
                ),
                required=False,
            ),
        ],
        examples=[
            OpenApiExample(
                "Paginated Response",
                value={
                    "count": 42,
                    "next": (
                        "https://api.example.com/api/drift-events/"
                        "?page=2&page_size=10"
                    ),
                    "previous": None,
                    "results": [
                        {
                            "id": 1,
                            "payer": "Blue Cross Blue Shield",
                            "cpt_group": "Office Visits",
                            "drift_type": "denial_rate",
                            "severity": 0.85,
                            "baseline_value": "5.2",
                            "current_value": "18.7",
                            "delta_value": "13.5",
                            "created_at": "2024-01-15T10:30:00Z",
                        },
                        {
                            "id": 2,
                            "payer": "Aetna",
                            "cpt_group": "Imaging",
                            "drift_type": "decision_time",
                            "severity": 0.72,
                            "baseline_value": "12.3",
                            "current_value": "28.9",
                            "delta_value": "16.6",
                            "created_at": "2024-01-15T10:30:00Z",
                        },
                    ],
                },
                response_only=True,
            ),
            OpenApiExample(
                "Filtered by Severity",
                value={
                    "count": 8,
                    "next": None,
                    "previous": None,
                    "results": [
                        {
                            "id": 5,
                            "payer": "UnitedHealthcare",
                            "cpt_group": "Surgery",
                            "drift_type": "allowed_amount",
                            "severity": 0.92,
                            "baseline_value": "1500.00",
                            "current_value": "950.00",
                            "delta_value": "-550.00",
                            "created_at": "2024-01-15T10:30:00Z",
                        },
                    ],
                },
                response_only=True,
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Get drift event details",
        description=(
            "Retrieve detailed information for a specific drift event "
            "including baseline and current values."
        ),
        tags=["Drift Detection"],
    ),
)
class DriftEventViewSet(ETagMixin, CustomerFilterMixin, viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing drift events.
    Rate limit: 2000 requests/hour for read operations.
    """

    queryset = DriftEvent.objects.all().order_by("-created_at")
    serializer_class = DriftEventSerializer
    permission_classes = [IsAuthenticated, IsCustomerMember]
    throttle_classes = [ReadOnlyThrottle]  # QW-5: Liberal rate limit for reads
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = DriftEventFilter
    search_fields = ["payer", "cpt_group", "drift_type"]
    ordering_fields = ["created_at", "severity", "payer"]

    @extend_schema(
        summary="Get active drift events",
        description=(
            "Retrieve drift events from the most recent successful report "
            "run. Returns only drift events that are still active (not resolved). "
            "Results are paginated for performance."
        ),
        tags=["Drift Detection"],
        parameters=[
            OpenApiParameter(
                name="page",
                type=int,
                description="Page number for pagination (default: 1)",
                required=False,
            ),
            OpenApiParameter(
                name="page_size",
                type=int,
                description="Number of results per page (default: 100)",
                required=False,
            ),
        ],
        responses={200: DriftEventSerializer(many=True)},
        examples=[
            OpenApiExample(
                "Active Drift Events",
                value={
                    "count": 15,
                    "next": "https://api.example.com/api/drift-events/active/?page=2",
                    "previous": None,
                    "results": [
                        {
                            "id": 1,
                            "payer": "Blue Cross Blue Shield",
                            "cpt_group": "Office Visits",
                            "drift_type": "denial_rate",
                            "severity": 0.92,
                            "baseline_value": "5.2",
                            "current_value": "18.7",
                            "delta_value": "13.5",
                            "created_at": "2024-01-20T10:30:00Z",
                            "report_run": 42,
                        },
                        {
                            "id": 2,
                            "payer": "Aetna",
                            "cpt_group": "Imaging",
                            "drift_type": "decision_time",
                            "severity": 0.87,
                            "baseline_value": "12.3",
                            "current_value": "28.9",
                            "delta_value": "16.6",
                            "created_at": "2024-01-20T10:30:00Z",
                            "report_run": 42,
                        },
                    ],
                },
                response_only=True,
            ),
        ],
    )
    @action(detail=False, methods=["get"])
    def active(self, request):
        """Get drift events from the most recent report run."""
        queryset = self.get_queryset()

        # Get the most recent report run
        # Use all_objects with explicit customer filter to avoid double-filtering
        latest_report = (
            ReportRun.all_objects.filter(
                customer=get_user_customer(request.user), status="success"
            )
            .order_by("-finished_at")
            .first()
        )

        if latest_report:
            queryset = queryset.filter(report_run=latest_report)
        else:
            queryset = queryset.none()

        # Apply pagination to prevent OOM on large result sets
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = DriftEventSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = DriftEventSerializer(queryset, many=True)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(
        summary="List network alerts",
        description=(
            "Retrieve platform-level alerts showing cross-customer patterns. "
            "NetworkAlerts are created when 3+ customers show the same payer drift."
        ),
        tags=["Network Intelligence"],
    ),
    retrieve=extend_schema(
        summary="Get network alert details",
        description="Retrieve details for a specific network alert.",
        tags=["Network Intelligence"],
    ),
)
class NetworkAlertViewSet(ETagMixin, viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing platform-level network alerts.

    NetworkAlerts show cross-customer intelligence - patterns that affect
    multiple customers. These are platform-level (no customer FK) and
    visible to all authenticated users.
    """

    queryset = NetworkAlert.objects.all().order_by("-created_at")
    serializer_class = NetworkAlertSerializer
    permission_classes = [IsAuthenticated]
    throttle_classes = [ReadOnlyThrottle]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["payer", "drift_type", "severity"]
    search_fields = ["payer", "summary_text"]
    ordering_fields = ["created_at", "severity", "affected_customer_count"]

    @extend_schema(
        summary="Get active network alerts",
        description="Retrieve unresolved network alerts.",
        tags=["Network Intelligence"],
    )
    @action(detail=False, methods=["get"])
    def active(self, request):
        """Get unresolved network alerts."""
        queryset = self.get_queryset().filter(resolved_at__isnull=True)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(
        summary="List payer mappings",
        description=(
            "Retrieve a list of payer name mappings for normalizing payer " "names."
        ),
        tags=["Configuration"],
    ),
    retrieve=extend_schema(
        summary="Get payer mapping details",
        description="Retrieve details for a specific payer mapping.",
        tags=["Configuration"],
    ),
    create=extend_schema(
        summary="Create payer mapping",
        description=(
            "Create a new payer name mapping to normalize raw payer names "
            "to standard names."
        ),
        tags=["Configuration"],
        examples=[
            OpenApiExample(
                "Create Payer Mapping",
                value={
                    "raw_name": "BCBS CA",
                    "normalized_name": "Blue Cross Blue Shield California",
                },
                request_only=True,
            ),
        ],
    ),
    update=extend_schema(
        summary="Update payer mapping",
        description="Update a payer name mapping.",
        tags=["Configuration"],
    ),
    partial_update=extend_schema(
        summary="Partially update payer mapping",
        description="Update specific fields of a payer mapping.",
        tags=["Configuration"],
    ),
    destroy=extend_schema(
        summary="Delete payer mapping",
        description="Delete a payer name mapping.",
        tags=["Configuration"],
    ),
)
class PayerMappingViewSet(ETagMixin, CustomerFilterMixin, viewsets.ModelViewSet):
    """
    API endpoint for managing payer name mappings.
    """

    queryset = PayerMapping.objects.all().order_by("raw_name")
    serializer_class = PayerMappingSerializer
    permission_classes = [IsAuthenticated, IsCustomerMember]

    def perform_create(self, serializer):
        customer = get_user_customer(self.request.user)
        serializer.save(customer=customer)


@extend_schema_view(
    list=extend_schema(
        summary="List CPT group mappings",
        description="Retrieve a list of CPT code to group mappings.",
        tags=["Configuration"],
    ),
    retrieve=extend_schema(
        summary="Get CPT group mapping details",
        description="Retrieve details for a specific CPT group mapping.",
        tags=["Configuration"],
    ),
    create=extend_schema(
        summary="Create CPT group mapping",
        description=(
            "Create a new CPT code to group mapping for categorizing "
            "procedure codes."
        ),
        tags=["Configuration"],
        examples=[
            OpenApiExample(
                "Create CPT Group Mapping",
                value={"cpt_code": "99213", "cpt_group": "Office Visits"},
                request_only=True,
            ),
        ],
    ),
    update=extend_schema(
        summary="Update CPT group mapping",
        description="Update a CPT group mapping.",
        tags=["Configuration"],
    ),
    partial_update=extend_schema(
        summary="Partially update CPT group mapping",
        description="Update specific fields of a CPT group mapping.",
        tags=["Configuration"],
    ),
    destroy=extend_schema(
        summary="Delete CPT group mapping",
        description="Delete a CPT group mapping.",
        tags=["Configuration"],
    ),
)
class CPTGroupMappingViewSet(ETagMixin, CustomerFilterMixin, viewsets.ModelViewSet):
    """
    API endpoint for managing CPT code to group mappings.
    """

    queryset = CPTGroupMapping.objects.all().order_by("cpt_code")
    serializer_class = CPTGroupMappingSerializer
    permission_classes = [IsAuthenticated, IsCustomerMember]

    def perform_create(self, serializer):
        customer = get_user_customer(self.request.user)
        serializer.save(customer=customer)


class DashboardView(APIView):
    """
    API endpoint for dashboard overview data.
    """

    permission_classes = [IsAuthenticated, IsCustomerMember]

    @extend_schema(
        summary="Get dashboard overview",
        description=(
            "Retrieve dashboard overview data including claim statistics, "
            "upload counts, active drift events, denial rate trends (last 6 months), "
            "and top 5 drift payers by severity. Cached for 5 minutes to reduce "
            "database load."
        ),
        tags=["Dashboard"],
        responses={
            200: DashboardSerializer,
            400: OpenApiExample(
                "Error Response",
                value={"error": "No customer associated with user"},
                response_only=True,
            ),
        },
        examples=[
            OpenApiExample(
                "Dashboard Overview",
                value={
                    "total_claims": 125000,
                    "total_uploads": 42,
                    "active_drift_events": 15,
                    "behavioral_prediction_count": 3,
                    "last_report_date": "2024-01-20T10:30:00Z",
                    "denial_rate_trend": [
                        {
                            "month": "2023-08",
                            "denial_rate": 8.5,
                            "total_claims": 18500,
                            "denied_claims": 1573,
                        },
                        {
                            "month": "2023-09",
                            "denial_rate": 9.2,
                            "total_claims": 19200,
                            "denied_claims": 1766,
                        },
                        {
                            "month": "2023-10",
                            "denial_rate": 10.1,
                            "total_claims": 20100,
                            "denied_claims": 2030,
                        },
                        {
                            "month": "2023-11",
                            "denial_rate": 11.5,
                            "total_claims": 21000,
                            "denied_claims": 2415,
                        },
                        {
                            "month": "2023-12",
                            "denial_rate": 12.3,
                            "total_claims": 22500,
                            "denied_claims": 2768,
                        },
                        {
                            "month": "2024-01",
                            "denial_rate": 13.8,
                            "total_claims": 23700,
                            "denied_claims": 3271,
                        },
                    ],
                    "top_drift_payers": [
                        {
                            "payer": "Blue Cross Blue Shield",
                            "severity": 0.92,
                            "delta_value": "15.3",
                        },
                        {
                            "payer": "Aetna",
                            "severity": 0.87,
                            "delta_value": "12.8",
                        },
                        {
                            "payer": "UnitedHealthcare",
                            "severity": 0.79,
                            "delta_value": "9.5",
                        },
                        {
                            "payer": "Cigna",
                            "severity": 0.71,
                            "delta_value": "7.2",
                        },
                        {
                            "payer": "Humana",
                            "severity": 0.68,
                            "delta_value": "6.8",
                        },
                    ],
                },
                response_only=True,
            ),
        ],
    )
    def get(self, request):
        customer = get_user_customer(request.user)
        if not customer:
            return Response(
                {"error": "No customer associated with user"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # QW-4: Cache dashboard data for 5 minutes to reduce DB
        # queries by 40-60%
        cache_key = f"dashboard:customer:{customer.id}"
        cache_ttl = settings.CACHE_TTL.get("drift_events", 300)  # 5 minutes default

        def compute_dashboard_data():
            """Expensive dashboard queries - cached to reduce DB load."""
            # Get counts - use for_customer() to bypass auto-filtering
            # and explicitly filter
            total_claims = ClaimRecord.objects.for_customer(customer).count()
            total_uploads = (
                Upload.objects.for_customer(customer).filter(status="success").count()
            )

            # Get latest report
            latest_report = (
                ReportRun.objects.for_customer(customer)
                .filter(status="success")
                .order_by("-finished_at")
                .first()
            )

            active_drift_events = 0
            if latest_report:
                active_drift_events = latest_report.drift_events.count()

            # Count behavioral prediction events in last 7 days
            from datetime import timedelta as td

            seven_days_ago = timezone.now() - td(days=7)
            behavioral_prediction_count = DriftEvent.objects.filter(
                customer=customer,
                drift_type="BEHAVIORAL_PREDICTION",
                current_start__gte=seven_days_ago.date(),
            ).count()

            # Get top drift payers from latest report
            top_drift_payers = []
            if latest_report:
                top_events = latest_report.drift_events.order_by("-severity")[:5]
                for event in top_events:
                    top_drift_payers.append(
                        {
                            "payer": event.payer,
                            "severity": event.severity,
                            "delta_value": event.delta_value,
                        }
                    )

            # Compute denial rate trend over last 6 months
            from django.db.models.functions import TruncMonth
            from datetime import timedelta

            denial_rate_trend = []
            six_months_ago = timezone.now().date() - timedelta(days=180)

            trend_data = (
                ClaimRecord.objects.for_customer(customer)
                .filter(decided_date__gte=six_months_ago)
                .annotate(month=TruncMonth("decided_date"))
                .values("month")
                .annotate(
                    total=Count("id"), denied=Count("id", filter=Q(outcome="DENIED"))
                )
                .order_by("month")
            )

            for item in trend_data:
                denial_rate = (
                    (item["denied"] / item["total"] * 100) if item["total"] > 0 else 0
                )
                denial_rate_trend.append(
                    {
                        "month": item["month"].strftime("%Y-%m"),
                        "denial_rate": round(denial_rate, 2),
                        "total_claims": item["total"],
                        "denied_claims": item["denied"],
                    }
                )

            return {
                "total_claims": total_claims,
                "total_uploads": total_uploads,
                "active_drift_events": active_drift_events,
                "behavioral_prediction_count": behavioral_prediction_count,
                "last_report_date": (
                    latest_report.finished_at if latest_report else None
                ),
                "denial_rate_trend": denial_rate_trend,
                "top_drift_payers": top_drift_payers,
            }

        # Get from cache or compute and store
        data = cache.get_or_set(cache_key, compute_dashboard_data, cache_ttl)

        serializer = DashboardSerializer(data)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(
        summary="List alert events",
        description=(
            "Retrieve a paginated list of alert events with operator "
            "feedback. Read-only to preserve audit trail. "
            "By default, filters to customer's enabled specialties + CORE alerts."
        ),
        tags=["Alerts"],
        parameters=[
            OpenApiParameter(
                name="status", type=str, description="Filter by alert status"
            ),
            OpenApiParameter(
                name="specialty",
                type=str,
                description=(
                    "Filter by specialty (comma-separated). "
                    "Options: DIALYSIS, ABA, PTOT, IMAGING, HOME_HEALTH, CORE"
                ),
            ),
            OpenApiParameter(
                name="search", type=str, description="Search by payer name"
            ),
            OpenApiParameter(
                name="ordering",
                type=str,
                description=(
                    "Order by: triggered_at, status " "(prefix with - for descending)"
                ),
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Get alert event details",
        description=(
            "Retrieve detailed information for a specific alert event "
            "including operator judgments."
        ),
        tags=["Alerts"],
    ),
)
class AlertEventViewSet(ETagMixin, CustomerFilterMixin, viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for alert events with operator feedback (HIGH-8).
    Read-only to preserve audit trail - alerts cannot be modified or deleted.

    Specialty Filtering:
    - By default, non-superusers only see alerts for their enabled specialties + CORE
    - Use ?specialty=DIALYSIS,ABA to filter to specific specialties
    """

    queryset = (
        AlertEvent.objects.all()
        .select_related("alert_rule", "drift_event")
        .prefetch_related("operator_judgments")
    )
    serializer_class = AlertEventSerializer
    permission_classes = [IsAuthenticated, IsCustomerMember]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["status", "specialty"]
    search_fields = ["drift_event__payer"]
    ordering_fields = ["triggered_at", "status"]
    ordering = ["-triggered_at"]

    def get_queryset(self):
        """
        Override get_queryset to add specialty filtering.

        For non-superusers, automatically filters to:
        - CORE alerts (always shown)
        - Alerts matching customer's enabled specialties

        Explicit specialty filter (?specialty=X) takes precedence.
        """
        queryset = super().get_queryset()

        # Check if explicit specialty filter is provided
        specialty_param = self.request.query_params.get("specialty")
        if specialty_param:
            # User explicitly requested specific specialties
            specialties = [s.strip().upper() for s in specialty_param.split(",")]
            queryset = queryset.filter(specialty__in=specialties)
        else:
            # Auto-filter to customer's enabled specialties + CORE
            user = self.request.user
            if not user.is_superuser:
                customer = get_user_customer(user)
                if customer:
                    # Get enabled specialties
                    enabled = customer.enabled_specialties or []
                    # Always include CORE alerts
                    allowed = ["CORE"] + enabled
                    queryset = queryset.filter(specialty__in=allowed)

        return queryset

    @action(detail=True, methods=["post"], url_path="feedback")
    @extend_schema(
        summary="Submit operator feedback on an alert",
        description=(
            "Submit operator feedback/judgment on an alert event. Creates or "
            "updates an OperatorJudgment record and updates alert status. "
            "Logs action to audit trail."
        ),
        tags=["Alerts"],
        request=OperatorFeedbackSerializer,
        examples=[
            OpenApiExample(
                "Feedback - Real Alert",
                value={
                    "verdict": "real",
                    "reason_codes": ["payer_policy_change"],
                    "recovered_amount": "5000.00",
                    "recovered_date": "2024-03-15",
                    "notes": "Contacted payer and confirmed policy change",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Feedback - Noise",
                value={
                    "verdict": "noise",
                    "reason_codes": ["data_quality_issue"],
                    "notes": "False positive due to incomplete data upload",
                },
                request_only=True,
            ),
        ],
        responses={
            201: OperatorJudgmentSerializer,
            200: OperatorJudgmentSerializer,
            400: OpenApiExample(
                "Validation Error",
                value={"verdict": ["This field is required."]},
                response_only=True,
            ),
        },
    )
    def feedback(self, request, pk=None):
        """
        Submit operator feedback/judgment on an alert event.
        Creates or updates an OperatorJudgment record.
        """
        from upstream.ingestion.models import SystemEvent

        alert_event = self.get_object()
        customer = get_user_customer(request.user)

        if not customer:
            return Response(
                {"error": "No customer associated with user"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate input
        feedback_serializer = OperatorFeedbackSerializer(data=request.data)
        if not feedback_serializer.is_valid():
            return Response(
                feedback_serializer.errors, status=status.HTTP_400_BAD_REQUEST
            )

        validated_data = feedback_serializer.validated_data

        # Create or update operator judgment
        # Use all_objects to avoid double-filtering issues with update_or_create
        judgment, created = OperatorJudgment.all_objects.update_or_create(
            alert_event=alert_event,
            operator=request.user,
            defaults={
                "customer": customer,
                "verdict": validated_data["verdict"],
                "reason_codes_json": validated_data.get("reason_codes", []),
                "recovered_amount": validated_data.get("recovered_amount"),
                "recovered_date": validated_data.get("recovered_date"),
                "notes": validated_data.get("notes", ""),
            },
        )

        # Update alert event status based on verdict
        old_status = alert_event.status
        if validated_data["verdict"] == "noise":
            alert_event.status = "resolved"
        elif validated_data["verdict"] == "real":
            alert_event.status = "acknowledged"
        elif validated_data["verdict"] == "needs_followup":
            alert_event.status = "pending"

        alert_event.save(update_fields=["status"])

        # Log operator feedback action (audit trail)
        SystemEvent.objects.create(
            customer=customer,
            event_type="operator_feedback_submitted",
            payload={
                "alert_id": alert_event.id,
                "verdict": validated_data["verdict"],
                "previous_status": old_status,
                "new_status": alert_event.status,
                "recovered_amount": (
                    str(validated_data.get("recovered_amount"))
                    if validated_data.get("recovered_amount")
                    else None
                ),
                "action": "created" if created else "updated",
                "drift_event_id": (
                    alert_event.drift_event.id if alert_event.drift_event else None
                ),
                "operator_username": request.user.username,
            },
            related_alert=alert_event,
        )

        serializer = OperatorJudgmentSerializer(judgment)
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class WebhookIngestionView(APIView):
    """
    Webhook ingestion endpoint.

    Accepts JSON payloads authenticated with ingestion tokens.
    Creates durable ingestion records for async processing.
    """

    permission_classes = []  # Uses token auth instead

    @extend_schema(
        summary="Ingest data via webhook",
        description=(
            "Accept webhook payload authenticated with ingestion tokens. "
            "Creates durable ingestion records for async processing. "
            "Include Authorization: Bearer <token> header."
        ),
        tags=["Webhook Ingestion"],
        request={"application/json": dict},
        examples=[
            OpenApiExample(
                "Webhook Payload",
                value={
                    "claims": [
                        {
                            "payer": "BCBS",
                            "cpt": "99213",
                            "submitted_date": "2024-01-15",
                            "decided_date": "2024-02-01",
                            "outcome": "PAID",
                            "allowed_amount": "150.00",
                        }
                    ]
                },
                request_only=True,
            ),
        ],
        responses={
            202: OpenApiExample(
                "Accepted Response",
                value={
                    "status": "accepted",
                    "ingestion_id": 123,
                    "message": "Payload received and queued for processing",
                },
                response_only=True,
            ),
            401: OpenApiExample(
                "Auth Error",
                value={"error": "Missing or invalid authorization header"},
                response_only=True,
            ),
            400: OpenApiExample(
                "Validation Error",
                value={"error": "Empty payload"},
                response_only=True,
            ),
        },
    )
    def post(self, request):
        """Accept webhook payload and create ingestion record."""
        # Extract token from header
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith("Bearer "):
            return Response(
                {"error": "Missing or invalid authorization header"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        token_value = auth_header[7:]  # Remove 'Bearer '

        # Validate token
        try:
            token = IngestionToken.objects.get(token=token_value, is_active=True)

            # Check expiration
            if token.expires_at and token.expires_at < timezone.now():
                return Response(
                    {"error": "Token expired"}, status=status.HTTP_401_UNAUTHORIZED
                )

            # Update last used
            token.last_used_at = timezone.now()
            token.save(update_fields=["last_used_at"])

        except IngestionToken.DoesNotExist:
            return Response(
                {"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED
            )

        # Extract payload
        payload = request.data
        if not payload:
            return Response(
                {"error": "Empty payload"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Extract optional idempotency key
        idempotency_key = request.META.get("HTTP_X_IDEMPOTENCY_KEY")

        # Create ingestion record
        try:
            service = IngestionService(
                customer=token.customer, source_type="webhook", created_by=None
            )

            record = service.create_record(
                payload_metadata={
                    "source": "webhook",
                    "token_name": token.name,
                    "payload_keys": (
                        list(payload.keys()) if isinstance(payload, dict) else []
                    ),
                },
                idempotency_key=idempotency_key,
                record_count=len(payload) if isinstance(payload, list) else 1,
            )

            # Trigger async processing task
            from upstream.tasks import process_ingestion_task, enqueue_or_run_sync

            enqueue_or_run_sync(process_ingestion_task, record.id)

            return Response(
                {
                    "status": "accepted",
                    "ingestion_id": record.id,
                    "message": "Payload received and queued for processing",
                },
                status=status.HTTP_202_ACCEPTED,
            )

        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {"error": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class EpicEHRWebhookView(APIView):
    """
    Epic FHIR R4 webhook endpoint for real-time notifications.

    Story 7: Build webhook receiver for real-time updates
    - Handles Epic FHIR notifications
    - Validates Epic signature header
    - Parses FHIR resource from payload
    - Creates/updates ClaimRecord with idempotency
    """

    permission_classes = []  # Uses Epic signature validation

    @extend_schema(
        summary="Receive Epic EHR webhook notifications",
        description=(
            "POST /api/v1/webhooks/ehr/epic/ handles Epic notifications. "
            "Validates Epic signature header, parses FHIR resource, "
            "and creates/updates ClaimRecords with idempotency using resource ID."
        ),
        tags=["EHR Webhooks"],
        request={"application/fhir+json": dict},
        responses={
            200: OpenApiExample(
                "Success Response",
                value={
                    "status": "processed",
                    "resource_id": "eob-12345",
                    "action": "created",
                },
                response_only=True,
            ),
            401: OpenApiExample(
                "Invalid Signature",
                value={"error": "Invalid Epic signature"},
                response_only=True,
            ),
            400: OpenApiExample(
                "Invalid Payload",
                value={"error": "Invalid FHIR resource"},
                response_only=True,
            ),
        },
    )
    def post(self, request, connection_id=None):
        """
        Handle Epic FHIR webhook notification.

        Args:
            request: HTTP request with FHIR payload
            connection_id: Optional EHRConnection ID to match

        Returns:
            Response with processing status
        """
        import hashlib
        import hmac
        from upstream.integrations.models import EHRConnection, EHRSyncLog
        from upstream.integrations.fhir_parser import FHIRParser, FHIRParseError
        from upstream.models import ClaimRecord, Upload

        # Validate Epic signature header
        epic_signature = request.META.get("HTTP_X_EPIC_SIGNATURE", "")
        epic_timestamp = request.META.get("HTTP_X_EPIC_TIMESTAMP", "")

        # Get connection for signature validation
        connection = None
        if connection_id:
            try:
                connection = EHRConnection.objects.get(
                    id=connection_id, ehr_type="epic", enabled=True
                )
            except EHRConnection.DoesNotExist:
                return Response(
                    {"error": "Invalid connection"}, status=status.HTTP_404_NOT_FOUND
                )

            # Validate signature using connection's client_secret
            if epic_signature:
                payload_bytes = request.body
                expected_signature = hmac.new(
                    connection.client_secret.encode(),
                    f"{epic_timestamp}.{payload_bytes.decode()}".encode(),
                    hashlib.sha256,
                ).hexdigest()

                if not hmac.compare_digest(epic_signature, expected_signature):
                    return Response(
                        {"error": "Invalid Epic signature"},
                        status=status.HTTP_401_UNAUTHORIZED,
                    )

        # Parse FHIR payload
        payload = request.data
        if not payload:
            return Response(
                {"error": "Empty payload"}, status=status.HTTP_400_BAD_REQUEST
            )

        resource_type = payload.get("resourceType")
        resource_id = payload.get("id")

        if not resource_type or not resource_id:
            return Response(
                {"error": "Invalid FHIR resource: missing resourceType or id"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Only process ExplanationOfBenefit resources
        if resource_type != "ExplanationOfBenefit":
            return Response(
                {
                    "status": "skipped",
                    "reason": f"Unsupported resource type: {resource_type}",
                },
                status=status.HTTP_200_OK,
            )

        # Parse the EOB using FHIR parser
        try:
            customer = connection.customer if connection else None
            customer_salt = str(customer.id) if customer else ""
            parser = FHIRParser(customer_salt=customer_salt)
            parsed_data = parser.parse_eob(payload)
        except FHIRParseError as e:
            return Response(
                {"error": f"Failed to parse EOB: {e}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Idempotency check using source_data_hash
        source_hash = parsed_data.get("source_data_hash")
        action = "created"

        if customer:
            existing = ClaimRecord.objects.filter(
                customer=customer, source_data_hash=source_hash
            ).first()

            if existing:
                # Already processed, return success without creating duplicate
                return Response(
                    {
                        "status": "processed",
                        "resource_id": resource_id,
                        "action": "duplicate",
                        "claim_id": existing.id,
                    },
                    status=status.HTTP_200_OK,
                )

            # Create upload record for webhook data
            upload, _ = Upload.objects.get_or_create(
                customer=customer,
                filename=f"epic_webhook_{timezone.now().strftime('%Y%m%d')}",
                defaults={
                    "status": "success",
                    "upload_source": "batch",
                },
            )

            # Create ClaimRecord
            try:
                claim = ClaimRecord.objects.create(
                    customer=customer,
                    upload=upload,
                    payer=parsed_data.get("payer", "Unknown"),
                    cpt=parsed_data.get("cpt", ""),
                    submitted_date=parsed_data.get("submitted_date"),
                    decided_date=parsed_data.get("decided_date"),
                    outcome=parsed_data.get("outcome", "OTHER"),
                    allowed_amount=parsed_data.get("allowed_amount"),
                    billed_amount=parsed_data.get("billed_amount"),
                    paid_amount=parsed_data.get("paid_amount"),
                    payment_date=parsed_data.get("payment_date"),
                    modifier_codes=parsed_data.get("modifier_codes", []),
                    diagnosis_codes=parsed_data.get("diagnosis_codes", []),
                    procedure_count=parsed_data.get("procedure_count", 1),
                    submitted_via="ehr_webhook",
                    source_data_hash=source_hash,
                )
            except Exception as e:
                return Response(
                    {"error": f"Failed to create claim: {e}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            # Log sync activity
            if connection:
                EHRSyncLog.objects.create(
                    connection=connection,
                    status="success",
                    records_fetched=1,
                    records_created=1,
                    completed_at=timezone.now(),
                )

            return Response(
                {
                    "status": "processed",
                    "resource_id": resource_id,
                    "action": action,
                    "claim_id": claim.id,
                },
                status=status.HTTP_200_OK,
            )

        # No connection specified, just acknowledge receipt
        return Response(
            {
                "status": "acknowledged",
                "resource_id": resource_id,
                "message": "Webhook received but no connection configured",
            },
            status=status.HTTP_200_OK,
        )


class HealthCheckView(APIView):
    """
    API health check endpoint (no auth required).
    Returns detailed health status for all critical services.
    """

    permission_classes = []

    def check_database(self):
        """Check database connectivity and measure latency."""
        try:
            start = time.time()
            connection.ensure_connection()
            latency_ms = (time.time() - start) * 1000
            return {"status": "healthy", "latency_ms": round(latency_ms, 1)}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    def check_redis(self):
        """Check Redis availability via cache operations."""
        try:
            start = time.time()
            test_key = "health_check_test"
            test_value = "ok"
            cache.set(test_key, test_value, timeout=10)
            result = cache.get(test_key)
            latency_ms = (time.time() - start) * 1000

            if result != test_value:
                return {"status": "unhealthy", "error": "Cache get/set mismatch"}

            return {"status": "healthy", "latency_ms": round(latency_ms, 1)}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    def check_celery(self):
        """Check Celery worker availability."""
        # Skip check if Celery is disabled (dev environments)
        if not getattr(settings, "CELERY_ENABLED", False):
            return {"status": "disabled"}

        try:
            from upstream.celery import app

            inspect = app.control.inspect()
            active = inspect.active()

            if active is None:
                return {"status": "unhealthy", "error": "No workers responding"}

            worker_count = len(active.keys())
            return {"status": "healthy", "workers": worker_count}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    def check_disk_space(self):
        """Check disk space availability."""
        try:
            disk = shutil.disk_usage("/")
            percent_free = (disk.free / disk.total) * 100
            free_gb = disk.free / (1024**3)

            # Critical threshold: < 10% free
            if percent_free < 10:
                return {
                    "status": "unhealthy",
                    "percent_free": round(percent_free, 1),
                    "free_gb": round(free_gb, 1),
                    "error": "Disk space critically low",
                }
            # Warning threshold: < 20% free
            elif percent_free < 20:
                return {
                    "status": "warning",
                    "percent_free": round(percent_free, 1),
                    "free_gb": round(free_gb, 1),
                }
            else:
                return {
                    "status": "healthy",
                    "percent_free": round(percent_free, 1),
                    "free_gb": round(free_gb, 1),
                }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    @extend_schema(
        summary="API health check",
        description=(
            "Check API health status with detailed checks for database, Redis, "
            "Celery workers, and disk space. Returns 503 if any critical service "
            "is unavailable. No authentication required."
        ),
        tags=["Health"],
        responses={
            200: OpenApiExample(
                "Healthy Response",
                value={
                    "status": "healthy",
                    "version": "1.0.0",
                    "timestamp": "2024-03-15T10:30:00Z",
                    "checks": {
                        "database": {"status": "healthy", "latency_ms": 2.3},
                        "redis": {"status": "healthy", "latency_ms": 1.1},
                        "celery": {"status": "healthy", "workers": 2},
                        "disk": {
                            "status": "healthy",
                            "percent_free": 45.2,
                            "free_gb": 15.8,
                        },
                    },
                },
                response_only=True,
            ),
            503: OpenApiExample(
                "Unhealthy Response",
                value={
                    "status": "unhealthy",
                    "version": "1.0.0",
                    "timestamp": "2024-03-15T10:30:00Z",
                    "checks": {
                        "database": {"status": "healthy", "latency_ms": 2.3},
                        "redis": {"status": "unhealthy", "error": "Connection refused"},
                        "celery": {"status": "healthy", "workers": 2},
                        "disk": {
                            "status": "healthy",
                            "percent_free": 45.2,
                            "free_gb": 15.8,
                        },
                    },
                },
                response_only=True,
            ),
        },
    )
    def get(self, request):
        # Run all health checks
        checks = {
            "database": self.check_database(),
            "redis": self.check_redis(),
            "celery": self.check_celery(),
            "disk": self.check_disk_space(),
        }

        # Determine overall status - only database is critical for 503
        # Redis/Celery/disk are important but not critical for API availability
        critical_checks = ["database"]
        overall_status = "healthy"
        for check_name in critical_checks:
            if checks.get(check_name, {}).get("status") == "unhealthy":
                overall_status = "unhealthy"
                break

        # If any non-critical check is unhealthy, mark as degraded but still 200
        if overall_status == "healthy":
            for check_name, check_result in checks.items():
                if (
                    check_name not in critical_checks
                    and check_result.get("status") == "unhealthy"
                ):
                    overall_status = "degraded"
                    break

        response_data = {
            "status": overall_status,
            "version": "1.0.0",
            "timestamp": timezone.now().isoformat(),
            "checks": checks,
        }

        # Return 503 only if critical checks (database) are unhealthy
        status_code = 503 if overall_status == "unhealthy" else 200

        return Response(response_data, status=status_code)


# HIGH-2: JWT Authentication Views with Rate Limiting
# Prevents brute-force password attacks by limiting login attempts to 5 per 15 minutes


@extend_schema(
    summary="Obtain JWT token pair",
    description=(
        "Obtain access and refresh JWT tokens using username and password. "
        "Rate limited to 5 attempts per 15 minutes to prevent brute-force "
        "attacks. Use the access token in the Authorization header for "
        "subsequent API requests: 'Authorization: Bearer <access_token>'. "
        "Access tokens expire after 1 hour. Use the refresh token to obtain "
        "a new access token without re-authenticating.\n\n"
        "**RBAC Roles:**\n"
        "- **Owner**: Full access - manage users, alerts, webhooks, "
        "upload claims, manage mappings, view reports\n"
        "- **Admin**: Manage users, alerts, webhooks, upload claims, "
        "manage mappings, view reports\n"
        "- **Analyst**: Upload claims, manage mappings, view reports\n"
        "- **Viewer**: View reports only\n\n"
        "**Using the Token:**\n"
        "Include the access token in the Authorization header:\n"
        "```\nAuthorization: Bearer eyJ0eXAiOiJKV1QiLCJ...\n```\n\n"
        "**Logout:**\n"
        "JWTs are stateless. To logout, delete the tokens from the client. "
        "Tokens automatically expire (access: 1 hour, refresh: 24 hours)."
    ),
    tags=["Authentication"],
    examples=[
        OpenApiExample(
            "Login Request",
            value={
                "username": "doctor@healthcorp.com",
                "password": "SecurePassword123!",  # pragma: allowlist secret
            },
            request_only=True,
        ),
        OpenApiExample(
            "Login Success",
            value={
                # pragma: allowlist secret
                "access": (
                    "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9."  # pragma: allowlist secret
                    "eyJ1c2VyX2lkIjoxLCJ1c2VybmFtZSI6ImRvY3Rvckho"  # noqa: E501
                    "ZWFsdGhjb3JwLmNvbSJ9.abc123"
                ),
                "refresh": (
                    "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9."
                    "eyJ1c2VyX2lkIjoxLCJ0eXBlIjoicmVmcmVzaCJ9."
                    "def456"
                ),
            },
            response_only=True,
            status_codes=["200"],
        ),
        OpenApiExample(
            "Login Failed - Invalid Credentials",
            value={"detail": "No active account found with the given credentials"},
            response_only=True,
            status_codes=["401"],
        ),
        OpenApiExample(
            "Login Failed - Rate Limited",
            value={
                "detail": (
                    "Request was throttled. Expected available in " "600 seconds."
                )
            },
            response_only=True,
            status_codes=["429"],
        ),
        OpenApiExample(
            "Using Token - Example API Request",
            description=(
                "After login, include the access token in the "
                "Authorization header for all API requests. "
                "Example: GET /api/uploads/ with Authorization header."
            ),
            value={
                "count": 42,
                "next": "https://api.example.com/api/uploads/?page=2",
                "previous": None,
                "results": [
                    {
                        "id": 123,
                        "filename": "claims_2024_01.csv",
                        "status": "success",
                        "uploaded_at": "2024-01-15T10:30:00Z",
                    }
                ],
            },
            response_only=True,
            status_codes=["200"],
        ),
    ],
)

# =============================================================================
# Automation ViewSets (ClaimScore, CustomerAutomationProfile, ShadowModeResult)
# =============================================================================


@extend_schema_view(
    list=extend_schema(
        summary="List claim scores",
        description=(
            "Retrieve a paginated list of ML-based claim scores for automation "
            "decisions. Each score includes confidence metrics, risk assessments, "
            "and the recommended automation tier. Filtered by customer tenant."
        ),
        tags=["Automation"],
        responses={
            200: ClaimScoreSerializer(many=True),
            401: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
        },
    ),
    retrieve=extend_schema(
        summary="Get claim score details",
        description=(
            "Retrieve detailed scoring information for a specific claim, including "
            "confidence metrics, risk factors, feature importance, and reasoning."
        ),
        tags=["Automation"],
        responses={
            200: ClaimScoreSerializer,
            401: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    ),
    create=extend_schema(
        summary="Create claim score",
        description=(
            "Generate a new ML-based score for a claim. The claim must belong to "
            "the authenticated user's customer. Returns the computed confidence "
            "scores, risk assessments, and recommended automation action."
        ),
        tags=["Automation"],
        responses={
            201: ClaimScoreSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
        },
    ),
)
class ClaimScoreViewSet(ETagMixin, CustomerFilterMixin, viewsets.ModelViewSet):
    """
    API endpoint for ML-based claim scoring.

    Provides confidence metrics for automation decisions:
    - Tier 1 (Auto-Execute): High confidence, low risk
    - Tier 2 (Queue Review): Medium confidence, moderate risk
    - Tier 3 (Escalate): Low confidence, high risk, or red-line actions

    Supports list, retrieve, and create operations with tenant isolation.
    """

    queryset = ClaimScore.objects.all().order_by("-created_at")
    serializer_class = ClaimScoreSerializer
    permission_classes = [IsAuthenticated, IsCustomerMember]
    throttle_classes = [ReadOnlyThrottle]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = [
        "automation_tier",
        "recommended_action",
        "requires_human_review",
    ]
    search_fields = ["claim__payer", "claim__cpt", "prediction_reasoning"]
    ordering_fields = ["created_at", "overall_confidence", "denial_risk_score"]

    def get_queryset(self):
        """Optimize queryset with select_related for claim details."""
        queryset = super().get_queryset()
        if self.action in ("retrieve", "list"):
            queryset = queryset.select_related("customer", "claim")
        return queryset

    def perform_create(self, serializer):
        """Validate claim ownership before creating score."""
        user = self.request.user
        customer = get_user_customer(user)

        # Get claim from request data
        claim_id = self.request.data.get("claim")
        if claim_id:
            try:
                claim = ClaimRecord.objects.get(id=claim_id)
                # Verify claim belongs to user's customer
                if not user.is_superuser and claim.customer != customer:
                    from rest_framework.exceptions import PermissionDenied

                    raise PermissionDenied("Cannot score claims from other customers.")
            except ClaimRecord.DoesNotExist:
                from rest_framework.exceptions import ValidationError

                raise ValidationError({"claim": "Claim not found."})

        serializer.save(customer=customer)

    @extend_schema(
        summary="Score a claim for automation",
        description=(
            "Calculate ML-based risk score for a claim and return automation "
            "recommendation. Creates and persists a ClaimScore record. "
            "Response time target: < 200ms for single claim."
        ),
        tags=["Automation"],
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "claim_id": {
                        "type": "integer",
                        "description": "ID of the claim to score",
                    },
                },
                "required": ["claim_id"],
            }
        },
        responses={
            201: ClaimScoreSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
        examples=[
            OpenApiExample(
                "Score Request",
                value={"claim_id": 12345},
                request_only=True,
            ),
        ],
    )
    @action(detail=False, methods=["post"], throttle_classes=[BulkOperationThrottle])
    def score(self, request):
        """
        Calculate risk score for a claim.

        Accepts claim_id, retrieves claim data, runs scoring algorithm,
        and returns the computed ClaimScore with automation recommendation.
        """
        claim_id = request.data.get("claim_id")
        if not claim_id:
            return Response(
                {"error": {"code": "validation_error", "message": "claim_id required"}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        customer = get_user_customer(user)

        # Fetch and validate claim - use all_objects to bypass tenant filter
        # since we'll verify ownership explicitly
        try:
            claim = ClaimRecord.all_objects.select_related("customer").get(id=claim_id)
        except ClaimRecord.DoesNotExist:
            return Response(
                {"error": {"code": "not_found", "message": "Claim not found"}},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Verify ownership
        if not user.is_superuser and claim.customer != customer:
            return Response(
                {"error": {"code": "forbidden", "message": "Cannot score this claim"}},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check if score already exists
        existing_score = ClaimScore.objects.filter(claim=claim).first()
        if existing_score:
            serializer = ClaimScoreSerializer(
                existing_score, context={"request": request}
            )
            return Response(serializer.data, status=status.HTTP_200_OK)

        # Build claim data dict for scoring service
        claim_data = {
            "payer": claim.payer,
            "cpt": claim.cpt,
            "cpt_group": claim.cpt_group,
            "allowed_amount": claim.allowed_amount,
            "outcome": claim.outcome,
            "has_prior_auth": False,  # Not tracked in current model
            "documentation_count": 0,  # Not tracked in current model
        }

        # Look up baseline and profile
        baseline = RiskScoringService.lookup_baseline(
            customer_id=claim.customer_id,
            payer=claim.payer,
            cpt=claim.cpt,
        )
        profile = RiskScoringService.get_profile_thresholds(claim.customer_id)

        # Calculate score
        result = RiskScoringService.calculate_score(
            claim_data=claim_data,
            baseline_data=baseline,
            profile_thresholds=profile,
        )

        # Create and persist ClaimScore
        claim_score = ClaimScore.objects.create(
            claim=claim,
            customer=claim.customer,
            overall_confidence=result.overall_confidence,
            coding_confidence=result.coding_confidence,
            eligibility_confidence=result.eligibility_confidence,
            medical_necessity_confidence=result.medical_necessity_confidence,
            documentation_completeness=result.documentation_completeness,
            denial_risk_score=result.denial_risk_score,
            fraud_risk_score=result.fraud_risk_score,
            compliance_risk_score=result.compliance_risk_score,
            model_version="rf_v1.0",
            feature_importance=result.feature_importance,
            prediction_reasoning=result.prediction_reasoning,
            recommended_action=result.recommended_action,
            automation_tier=result.automation_tier,
            requires_human_review=result.requires_human_review,
            red_line_reason=result.red_line_reason,
        )

        serializer = ClaimScoreSerializer(claim_score, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    list=extend_schema(
        summary="List automation profiles",
        description=(
            "Retrieve automation profiles with threshold configurations and "
            "trust calibration stages. Each customer has one profile."
        ),
        tags=["Automation"],
        responses={
            200: CustomerAutomationProfileSerializer(many=True),
            401: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
        },
    ),
    retrieve=extend_schema(
        summary="Get automation profile",
        description=(
            "Retrieve detailed automation configuration including tier thresholds, "
            "action toggles, shadow mode settings, and notification preferences."
        ),
        tags=["Automation"],
        responses={
            200: CustomerAutomationProfileSerializer,
            401: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    ),
    update=extend_schema(
        summary="Update automation profile",
        description=(
            "Update automation thresholds and configuration. Changes take effect "
            "immediately for new claim scoring decisions."
        ),
        tags=["Automation"],
        responses={
            200: CustomerAutomationProfileSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
        },
    ),
    partial_update=extend_schema(
        summary="Partially update automation profile",
        description="Update specific automation settings without replacing profile.",
        tags=["Automation"],
        responses={
            200: CustomerAutomationProfileSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
        },
    ),
)
class CustomerAutomationProfileViewSet(
    ETagMixin, CustomerFilterMixin, viewsets.ModelViewSet
):
    """
    API endpoint for customer automation configuration.

    Manages trust calibration stages, tier thresholds, action toggles,
    and shadow mode settings. Each customer has exactly one profile.
    """

    queryset = CustomerAutomationProfile.objects.all().order_by("-created_at")
    serializer_class = CustomerAutomationProfileSerializer
    permission_classes = [IsAuthenticated, IsCustomerMember]
    throttle_classes = [ReadOnlyThrottle]
    http_method_names = ["get", "put", "patch", "head", "options"]

    def get_queryset(self):
        """Optimize queryset with select_related."""
        queryset = super().get_queryset()
        if self.action in ("retrieve", "list", "update", "partial_update"):
            queryset = queryset.select_related("customer", "compliance_officer")
        return queryset


@extend_schema_view(
    list=extend_schema(
        summary="List shadow mode results",
        description=(
            "Retrieve shadow mode comparison results showing AI predictions vs. "
            "human decisions. Used to validate AI accuracy before enabling "
            "autonomous execution."
        ),
        tags=["Automation"],
        responses={
            200: ShadowModeResultSerializer(many=True),
            401: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
        },
    ),
    retrieve=extend_schema(
        summary="Get shadow mode result",
        description=(
            "Retrieve detailed comparison between AI recommendation and human "
            "decision, including outcome classification and discrepancy notes."
        ),
        tags=["Automation"],
        responses={
            200: ShadowModeResultSerializer,
            401: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    ),
)
class ShadowModeResultViewSet(
    ETagMixin, CustomerFilterMixin, viewsets.ReadOnlyModelViewSet
):
    """
    API endpoint for shadow mode validation results (read-only).

    Tracks AI predictions vs. human decisions to measure accuracy before
    enabling autonomous execution. Results are created by the scoring
    workflow, not directly via API.
    """

    queryset = ShadowModeResult.objects.all().order_by("-created_at")
    serializer_class = ShadowModeResultSerializer
    permission_classes = [IsAuthenticated, IsCustomerMember]
    throttle_classes = [ReadOnlyThrottle]
    filter_backends = [
        DjangoFilterBackend,
        filters.OrderingFilter,
    ]
    filterset_fields = ["actions_match", "outcome"]
    ordering_fields = ["created_at", "ai_confidence"]

    def get_queryset(self):
        """Optimize queryset with select_related."""
        queryset = super().get_queryset()
        if self.action in ("retrieve", "list"):
            queryset = queryset.select_related(
                "customer", "claim_score", "human_decision_user"
            )
        return queryset


class ThrottledTokenObtainPairView(BaseTokenObtainPairView):
    """
    JWT token obtain view with strict rate limiting (HIGH-2).
    Limits login attempts to 5 per 15 minutes to prevent brute-force attacks.
    """

    throttle_classes = [AuthenticationThrottle]


@extend_schema(
    summary="Refresh JWT token",
    description=(
        "Refresh an access token using a valid refresh token. "
        "Access tokens expire after 1 hour. Use this endpoint to obtain "
        "a new access token without requiring the user to re-authenticate "
        "with username/password. Refresh tokens are valid for 24 hours. "
        "Rate limited to prevent abuse."
    ),
    tags=["Authentication"],
    examples=[
        OpenApiExample(
            "Refresh Request",
            value={
                "refresh": (
                    "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9."
                    "eyJ1c2VyX2lkIjoxLCJ0eXBlIjoicmVmcmVzaCJ9."
                    "def456"
                ),
            },
            request_only=True,
        ),
        OpenApiExample(
            "Refresh Success",
            value={
                # pragma: allowlist secret
                "access": (
                    "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9."
                    "eyJ1c2VyX2lkIjoxLCJ1c2VybmFtZSI6ImRvY3Rvckho"
                    "ZWFsdGhjb3JwLmNvbSJ9.xyz789"
                ),
            },
            response_only=True,
            status_codes=["200"],
        ),
        OpenApiExample(
            "Refresh Failed - Invalid Token",
            value={"detail": "Token is invalid or expired", "code": "token_not_valid"},
            response_only=True,
            status_codes=["401"],
        ),
    ],
)
class ThrottledTokenRefreshView(BaseTokenRefreshView):
    """
    JWT token refresh view with rate limiting (HIGH-2).
    """

    throttle_classes = [AuthenticationThrottle]


@extend_schema(
    summary="Verify JWT token",
    description=(
        "Verify that a JWT token (access or refresh) is valid and not expired. "
        "Returns an empty 200 response if valid, or 401 error if invalid/expired. "
        "Useful for checking token validity before making API requests. "
        "Rate limited to prevent abuse."
    ),
    tags=["Authentication"],
    examples=[
        OpenApiExample(
            "Verify Request",
            value={
                "token": (
                    "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9."
                    "eyJ1c2VyX2lkIjoxLCJ1c2VybmFtZSI6ImRvY3Rvckho"
                    "ZWFsdGhjb3JwLmNvbSJ9.abc123"
                ),
            },
            request_only=True,
        ),
        OpenApiExample(
            "Token Valid",
            value={},
            response_only=True,
            status_codes=["200"],
        ),
        OpenApiExample(
            "Token Invalid",
            value={"detail": "Token is invalid or expired", "code": "token_not_valid"},
            response_only=True,
            status_codes=["401"],
        ),
    ],
)
class ThrottledTokenVerifyView(BaseTokenVerifyView):
    """
    JWT token verify view with rate limiting (HIGH-2).
    """

    throttle_classes = [AuthenticationThrottle]
