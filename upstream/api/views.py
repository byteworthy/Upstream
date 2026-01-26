"""
Upstream API Views

RESTful API endpoints for the Upstream platform.
All views enforce multi-tenant access control.
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from django.db.models import Count, Avg, Q
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample
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
    Settings,
    Upload,
    ClaimRecord,
    ReportRun,
    DriftEvent,
    PayerMapping,
    CPTGroupMapping,
)
from upstream.alerts.models import AlertEvent, OperatorJudgment
from upstream.ingestion.models import IngestionToken
from upstream.ingestion import IngestionService
from .serializers import (
    CustomerSerializer,
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
)
from .permissions import IsCustomerMember, get_user_customer
from .filters import ClaimRecordFilter, DriftEventFilter


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
        description="Retrieve a list of customers. Regular users only see their own customer; superusers see all.",
        tags=["Customers"],
    ),
    retrieve=extend_schema(
        summary="Get customer details",
        description="Retrieve detailed information for a specific customer.",
        tags=["Customers"],
    ),
)
class CustomerViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing customer information.
    Users can only see their own customer.
    """

    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated, IsCustomerMember]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Customer.objects.all()

        customer = get_user_customer(user)
        if customer:
            return Customer.objects.filter(id=customer.id)
        return Customer.objects.none()


@extend_schema_view(
    list=extend_schema(
        summary="List settings",
        description="Retrieve customer settings. Returns settings for the authenticated user's customer.",
        tags=["Settings"],
    ),
    retrieve=extend_schema(
        summary="Get settings",
        description="Retrieve specific customer settings. Gets or creates settings for the user's customer.",
        tags=["Settings"],
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
                    "attach_pdf": True
                },
                request_only=True,
            ),
        ],
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
                    "attach_pdf": False
                },
                request_only=True,
            ),
        ],
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
    ),
    destroy=extend_schema(
        summary="Delete settings",
        description="Delete customer settings.",
        tags=["Settings"],
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
        description="Retrieve a paginated list of file uploads with filtering and search. Returns summary data for performance.",
        tags=["Uploads"],
        parameters=[
            OpenApiParameter(name="status", type=str, description="Filter by upload status (success, failed, processing)"),
            OpenApiParameter(name="search", type=str, description="Search by filename or status"),
            OpenApiParameter(name="ordering", type=str, description="Order by: uploaded_at, status, row_count (prefix with - for descending)"),
        ],
    ),
    retrieve=extend_schema(
        summary="Get upload details",
        description="Retrieve detailed information for a specific upload including date range and row count.",
        tags=["Uploads"],
    ),
    create=extend_schema(
        summary="Create upload",
        description="Create a new file upload record. Rate limited to 20 uploads/hour.",
        tags=["Uploads"],
        examples=[
            OpenApiExample(
                "Create Upload",
                value={
                    "filename": "claims_2024_Q1.csv",
                    "date_min": "2024-01-01",
                    "date_max": "2024-03-31"
                },
                request_only=True,
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
class UploadViewSet(CustomerFilterMixin, viewsets.ModelViewSet):
    """
    API endpoint for managing file uploads.
    Rate limit: 20 uploads/hour for bulk operations.
    """

    queryset = Upload.objects.all().order_by("-uploaded_at")
    serializer_class = UploadSerializer
    permission_classes = [IsAuthenticated, IsCustomerMember]
    throttle_classes = [BulkOperationThrottle]  # QW-5: Rate limit bulk uploads
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status']
    search_fields = ['filename', 'status']
    ordering_fields = ["uploaded_at", "status", "row_count"]

    def get_queryset(self):
        """Optimize queryset with select_related for detail views."""
        queryset = super().get_queryset()
        # HIGH-13: Add select_related to avoid N+1 queries
        # UploadSerializer includes 'customer' field, so prefetch it for detail views
        if self.action in ("retrieve", "update", "partial_update"):
            queryset = queryset.select_related("customer")
        return queryset

    def get_serializer_class(self):
        if self.action == "list":
            return UploadSummarySerializer
        return UploadSerializer

    @extend_schema(
        summary="Get upload statistics",
        description="Retrieve aggregated upload statistics including total uploads, success/failed counts, and total rows processed.",
        tags=["Uploads"],
        responses={
            200: OpenApiExample(
                "Upload Statistics",
                value={
                    "total": 150,
                    "success": 140,
                    "failed": 5,
                    "processing": 5,
                    "total_rows": 125000
                },
                response_only=True,
            )
        },
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
        description="Retrieve a paginated list of claim records with filtering, search, and ordering. Returns summary data for performance. Rate limited to 2000 requests/hour.",
        tags=["Claims"],
        parameters=[
            OpenApiParameter(name="payer", type=str, description="Filter by payer name"),
            OpenApiParameter(name="outcome", type=str, description="Filter by claim outcome (PAID, DENIED, OTHER)"),
            OpenApiParameter(name="submitted_date_after", type=OpenApiTypes.DATE, description="Filter claims submitted after this date (YYYY-MM-DD)"),
            OpenApiParameter(name="submitted_date_before", type=OpenApiTypes.DATE, description="Filter claims submitted before this date (YYYY-MM-DD)"),
            OpenApiParameter(name="decided_date_after", type=OpenApiTypes.DATE, description="Filter claims decided after this date (YYYY-MM-DD)"),
            OpenApiParameter(name="decided_date_before", type=OpenApiTypes.DATE, description="Filter claims decided before this date (YYYY-MM-DD)"),
            OpenApiParameter(name="search", type=str, description="Search by payer, CPT code, or denial reason code"),
            OpenApiParameter(name="ordering", type=str, description="Order by: decided_date, submitted_date, payer, outcome (prefix with - for descending)"),
        ],
    ),
    retrieve=extend_schema(
        summary="Get claim record details",
        description="Retrieve detailed information for a specific claim record.",
        tags=["Claims"],
    ),
)
class ClaimRecordViewSet(CustomerFilterMixin, viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing claim records.
    Supports filtering by payer, outcome, and date range.
    Rate limit: 2000 requests/hour for read operations.
    """

    queryset = ClaimRecord.objects.all().order_by("-decided_date")
    serializer_class = ClaimRecordSerializer
    permission_classes = [IsAuthenticated, IsCustomerMember]
    throttle_classes = [ReadOnlyThrottle]  # QW-5: Liberal rate limit for reads
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ClaimRecordFilter
    search_fields = ['payer', 'cpt', 'denial_reason_code']
    ordering_fields = ["decided_date", "submitted_date", "payer", "outcome"]

    def get_serializer_class(self):
        if self.action == "list":
            return ClaimRecordSummarySerializer
        return ClaimRecordSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        # HIGH-13: Add select_related to avoid N+1 queries
        # ClaimRecordSerializer includes 'customer' and 'upload' fields
        if self.action == "retrieve":
            queryset = queryset.select_related("customer", "upload")

        return queryset

    @extend_schema(
        summary="Get payer summary statistics",
        responses={200: PayerSummarySerializer(many=True)},
        parameters=[
            {
                "name": "start_date",
                "in": "query",
                "description": "Start date (YYYY-MM-DD). Defaults to 90 days ago.",
                "required": False,
                "schema": {"type": "string", "format": "date"},
            },
            {
                "name": "end_date",
                "in": "query",
                "description": "End date (YYYY-MM-DD). Defaults to today.",
                "required": False,
                "schema": {"type": "string", "format": "date"},
            },
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
        description="Retrieve a paginated list of report runs with their status and drift event counts.",
        tags=["Reports"],
    ),
    retrieve=extend_schema(
        summary="Get report run details",
        description="Retrieve detailed information for a specific report run including all drift events.",
        tags=["Reports"],
    ),
)
class ReportRunViewSet(CustomerFilterMixin, viewsets.ReadOnlyModelViewSet):
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
        description="Trigger a new payer drift report run. Creates a report run and queues async processing to detect payer behavior drift. Rate limited to 10 requests/hour.",
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
        description="Retrieve a paginated list of drift events with filtering, search, and ordering. Rate limited to 2000 requests/hour.",
        tags=["Drift Detection"],
        parameters=[
            OpenApiParameter(name="payer", type=str, description="Filter by payer name"),
            OpenApiParameter(name="cpt_group", type=str, description="Filter by CPT group"),
            OpenApiParameter(name="drift_type", type=str, description="Filter by drift type"),
            OpenApiParameter(name="severity_min", type=OpenApiTypes.FLOAT, description="Filter by minimum severity (0.0-1.0)"),
            OpenApiParameter(name="severity_max", type=OpenApiTypes.FLOAT, description="Filter by maximum severity (0.0-1.0)"),
            OpenApiParameter(name="search", type=str, description="Search by payer, CPT group, or drift type"),
            OpenApiParameter(name="ordering", type=str, description="Order by: created_at, severity, payer (prefix with - for descending)"),
        ],
    ),
    retrieve=extend_schema(
        summary="Get drift event details",
        description="Retrieve detailed information for a specific drift event including baseline and current values.",
        tags=["Drift Detection"],
    ),
)
class DriftEventViewSet(CustomerFilterMixin, viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing drift events.
    Rate limit: 2000 requests/hour for read operations.
    """

    queryset = DriftEvent.objects.all().order_by("-created_at")
    serializer_class = DriftEventSerializer
    permission_classes = [IsAuthenticated, IsCustomerMember]
    throttle_classes = [ReadOnlyThrottle]  # QW-5: Liberal rate limit for reads
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = DriftEventFilter
    search_fields = ['payer', 'cpt_group', 'drift_type']
    ordering_fields = ['created_at', 'severity', 'payer']

    @extend_schema(
        summary="Get active drift events",
        description="Retrieve drift events from the most recent successful report run. Returns paginated results.",
        tags=["Drift Detection"],
        parameters=[
            OpenApiParameter(name="page", type=int, description="Page number for pagination"),
            OpenApiParameter(name="page_size", type=int, description="Number of results per page"),
        ],
        responses={200: DriftEventSerializer(many=True)},
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
        summary="List payer mappings",
        description="Retrieve a list of payer name mappings for normalizing payer names.",
        tags=["Configuration"],
    ),
    retrieve=extend_schema(
        summary="Get payer mapping details",
        description="Retrieve details for a specific payer mapping.",
        tags=["Configuration"],
    ),
    create=extend_schema(
        summary="Create payer mapping",
        description="Create a new payer name mapping to normalize raw payer names to standard names.",
        tags=["Configuration"],
        examples=[
            OpenApiExample(
                "Create Payer Mapping",
                value={
                    "raw_name": "BCBS CA",
                    "normalized_name": "Blue Cross Blue Shield California"
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
class PayerMappingViewSet(CustomerFilterMixin, viewsets.ModelViewSet):
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
        description="Create a new CPT code to group mapping for categorizing procedure codes.",
        tags=["Configuration"],
        examples=[
            OpenApiExample(
                "Create CPT Group Mapping",
                value={
                    "cpt_code": "99213",
                    "cpt_group": "Office Visits"
                },
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
class CPTGroupMappingViewSet(CustomerFilterMixin, viewsets.ModelViewSet):
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
        description="Retrieve dashboard overview data including claim statistics, upload counts, active drift events, denial rate trends, and top drift payers. Cached for 5 minutes.",
        tags=["Dashboard"],
        responses={
            200: DashboardSerializer,
            400: OpenApiExample(
                "Error Response",
                value={"error": "No customer associated with user"},
                response_only=True,
            ),
        },
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
                "last_report_date": latest_report.finished_at
                if latest_report
                else None,
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
        description="Retrieve a paginated list of alert events with operator feedback. Read-only to preserve audit trail.",
        tags=["Alerts"],
        parameters=[
            OpenApiParameter(name="status", type=str, description="Filter by alert status"),
            OpenApiParameter(name="search", type=str, description="Search by payer name"),
            OpenApiParameter(name="ordering", type=str, description="Order by: triggered_at, status (prefix with - for descending)"),
        ],
    ),
    retrieve=extend_schema(
        summary="Get alert event details",
        description="Retrieve detailed information for a specific alert event including operator judgments.",
        tags=["Alerts"],
    ),
)
class AlertEventViewSet(CustomerFilterMixin, viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for alert events with operator feedback (HIGH-8).
    Read-only to preserve audit trail - alerts cannot be modified or deleted.
    """

    queryset = (
        AlertEvent.objects.all()
        .select_related("alert_rule", "drift_event")
        .prefetch_related("operator_judgments")
    )
    serializer_class = AlertEventSerializer
    permission_classes = [IsAuthenticated, IsCustomerMember]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status']
    search_fields = ['drift_event__payer']
    ordering_fields = ['triggered_at', 'status']
    ordering = ["-triggered_at"]

    @action(detail=True, methods=["post"], url_path="feedback")
    @extend_schema(
        summary="Submit operator feedback on an alert",
        description="Submit operator feedback/judgment on an alert event. Creates or updates an OperatorJudgment record and updates alert status. Logs action to audit trail.",
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
                    "notes": "Contacted payer and confirmed policy change"
                },
                request_only=True,
            ),
            OpenApiExample(
                "Feedback - Noise",
                value={
                    "verdict": "noise",
                    "reason_codes": ["data_quality_issue"],
                    "notes": "False positive due to incomplete data upload"
                },
                request_only=True,
            ),
        ],
        responses={
            201: OperatorJudgmentSerializer,
            200: OperatorJudgmentSerializer,
            400: OpenApiExample(
                "Validation Error",
                value={
                    "verdict": ["This field is required."]
                },
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
                "recovered_amount": str(validated_data.get("recovered_amount"))
                if validated_data.get("recovered_amount")
                else None,
                "action": "created" if created else "updated",
                "drift_event_id": alert_event.drift_event.id
                if alert_event.drift_event
                else None,
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
        description="Accept webhook payload authenticated with ingestion tokens. Creates durable ingestion records for async processing. Include Authorization: Bearer <token> header.",
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
                            "allowed_amount": "150.00"
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
                    "message": "Payload received and queued for processing"
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
                    "payload_keys": list(payload.keys())
                    if isinstance(payload, dict)
                    else [],
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


class HealthCheckView(APIView):
    """
    API health check endpoint (no auth required).
    Returns application health status, version, and timestamp.
    """

    permission_classes = []

    @extend_schema(
        summary="API health check",
        description="Check API health status. Returns application version and current timestamp. No authentication required.",
        tags=["Health"],
        responses={
            200: OpenApiExample(
                "Healthy Response",
                value={
                    "status": "healthy",
                    "version": "1.0.0",
                    "timestamp": "2024-03-15T10:30:00Z"
                },
                response_only=True,
            ),
        },
    )
    def get(self, request):
        return Response(
            {
                "status": "healthy",
                "version": "1.0.0",
                "timestamp": timezone.now().isoformat(),
            }
        )


# HIGH-2: JWT Authentication Views with Rate Limiting
# Prevents brute-force password attacks by limiting login attempts to 5 per 15 minutes


@extend_schema(
    summary="Obtain JWT token pair",
    description="Obtain access and refresh JWT tokens using username and password. Rate limited to 5 attempts per 15 minutes to prevent brute-force attacks.",
    tags=["Authentication"],
)
class ThrottledTokenObtainPairView(BaseTokenObtainPairView):
    """
    JWT token obtain view with strict rate limiting (HIGH-2).
    Limits login attempts to 5 per 15 minutes to prevent brute-force attacks.
    """

    throttle_classes = [AuthenticationThrottle]


@extend_schema(
    summary="Refresh JWT token",
    description="Refresh an access token using a valid refresh token. Rate limited to prevent abuse.",
    tags=["Authentication"],
)
class ThrottledTokenRefreshView(BaseTokenRefreshView):
    """
    JWT token refresh view with rate limiting (HIGH-2).
    """

    throttle_classes = [AuthenticationThrottle]


@extend_schema(
    summary="Verify JWT token",
    description="Verify that a JWT token is valid and not expired. Rate limited to prevent abuse.",
    tags=["Authentication"],
)
class ThrottledTokenVerifyView(BaseTokenVerifyView):
    """
    JWT token verify view with rate limiting (HIGH-2).
    """

    throttle_classes = [AuthenticationThrottle]
