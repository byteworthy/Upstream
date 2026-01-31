"""
Upstream API Serializers

DRF serializers for all Upstream models with proper field exposure
and security considerations for PHI data.
"""

from rest_framework import serializers
from rest_framework.reverse import reverse
from drf_spectacular.utils import (
    extend_schema_field,
    extend_schema_serializer,
    OpenApiExample,
)
from drf_spectacular.types import OpenApiTypes
from ..models import (
    Customer,
    Settings,
    Upload,
    ClaimRecord,
    ReportRun,
    DriftEvent,
    UserProfile,
    PayerMapping,
    CPTGroupMapping,
)
from upstream.alerts.models import AlertEvent, OperatorJudgment


# =============================================================================
# HATEOAS Mixin for Link Generation
# =============================================================================


class HATEOASMixin(serializers.Serializer):
    """
    Mixin to add HATEOAS links to serialized API responses.

    Provides hypermedia controls for resource navigation following REST
    best practices. Generates absolute URLs for self, collection, related
    resources, and pagination links.

    Usage: Add to any ModelSerializer class definition:
        class MySerializer(HATEOASMixin, serializers.ModelSerializer):
            ...

    Requires:
    - Request object in serializer context (pass via context={'request': request})
    - View name convention: {model_name}-list, {model_name}-detail
    """

    _links = serializers.SerializerMethodField(method_name="get__links")

    @extend_schema_field(
        {
            "type": "object",
            "properties": {
                "self": {
                    "type": "string",
                    "format": "uri",
                    "example": "http://localhost:8000/api/v1/uploads/123/",
                },
                "collection": {
                    "type": "string",
                    "format": "uri",
                    "example": "http://localhost:8000/api/v1/uploads/",
                },
                "next": {
                    "type": "string",
                    "format": "uri",
                    "example": "http://localhost:8000/api/v1/uploads/?page=2",
                },
                "previous": {
                    "type": "string",
                    "format": "uri",
                    "example": "http://localhost:8000/api/v1/uploads/?page=1",
                },
            },
            "description": "HATEOAS links for resource navigation and discoverability",
        }
    )
    def get__links(self, obj):
        """Generate HATEOAS links for the serialized resource."""
        request = self.context.get("request")
        if not request:
            return {}

        links = {}

        # Determine model name and view basename
        model_name = obj.__class__.__name__.lower()

        # Map model names to view basenames (DRF router convention)
        basename_map = {
            "customer": "customer",
            "settings": "settings",
            "upload": "upload",
            "claimrecord": "claim",
            "driftevent": "drift-event",
            "reportrun": "report",
            "alertevent": "alert-event",
            "payermapping": "payer-mapping",
            "cptgroupmapping": "cpt-mapping",
            "operatorjudgment": "operator-judgment",
        }
        basename = basename_map.get(model_name)

        if not basename:
            return {}

        # Generate self link (detail view)
        try:
            detail_url = reverse(
                f"{basename}-detail", kwargs={"pk": obj.pk}, request=request
            )
            links["self"] = request.build_absolute_uri(detail_url)
        except Exception:
            pass

        # Generate collection link (list view)
        try:
            list_url = reverse(f"{basename}-list", request=request)
            links["collection"] = request.build_absolute_uri(list_url)
        except Exception:
            pass

        # Add pagination links if available
        # Check if view has paginator and pagination data
        view = (
            request.parser_context.get("view")
            if hasattr(request, "parser_context")
            else None
        )
        if view and hasattr(view, "paginator"):
            # For list views, pagination links are added at response level
            # For detail views in paginated context, we can add them here
            pass

        # Add related resource links based on model type
        links.update(self._get_related_links(obj, request))

        return links

    def _get_related_links(self, obj, request):
        """Generate related resource links based on model type."""
        links = {}
        model_name = obj.__class__.__name__

        try:
            if model_name == "Upload":
                # Upload -> Claims
                claims_url = (
                    reverse("claim-list", request=request) + f"?upload={obj.pk}"
                )
                links["claims"] = request.build_absolute_uri(claims_url)

            elif model_name == "ClaimRecord":
                # Claim -> Upload
                if obj.upload_id:
                    upload_url = reverse(
                        "upload-detail", kwargs={"pk": obj.upload_id}, request=request
                    )
                    links["upload"] = request.build_absolute_uri(upload_url)

            elif model_name == "DriftEvent":
                # DriftEvent -> Report
                if obj.report_run_id:
                    report_url = reverse(
                        "report-detail",
                        kwargs={"pk": obj.report_run_id},
                        request=request,
                    )
                    links["report"] = request.build_absolute_uri(report_url)

            elif model_name == "ReportRun":
                # Report -> DriftEvents
                drift_url = (
                    reverse("drift-event-list", request=request)
                    + f"?report_run={obj.pk}"
                )
                links["drift-events"] = request.build_absolute_uri(drift_url)

            elif model_name == "AlertEvent":
                # AlertEvent -> DriftEvent
                if obj.drift_event_id:
                    drift_url = reverse(
                        "drift-event-detail",
                        kwargs={"pk": obj.drift_event_id},
                        request=request,
                    )
                    links["drift-event"] = request.build_absolute_uri(drift_url)

        except Exception:
            # If reverse fails (e.g., URL not configured), skip that link
            pass

        return links


class CustomerSerializer(HATEOASMixin, serializers.ModelSerializer):
    """
    Serializer for Customer model.

    Represents healthcare organization accounts in the platform.

    **Success Response (200 OK):**
    ```json
    {
        "id": 1,
        "name": "Memorial Hospital System",
        "_links": {
            "self": "http://localhost:8000/api/v1/customers/1/",
            "collection": "http://localhost:8000/api/v1/customers/"
        }
    }
    ```
    """

    class Meta:
        model = Customer
        fields = ["id", "name", "_links"]
        read_only_fields = ["id"]


class SettingsSerializer(HATEOASMixin, serializers.ModelSerializer):
    """
    Serializer for Settings model.

    Customer-specific configuration for report delivery and notification preferences.

    **Request Example (Update):**
    ```json
    {
        "to_email": "billing@hospital.com",
        "cc_email": "manager@hospital.com",
        "attach_pdf": true
    }
    ```

    **Success Response (200 OK):**
    ```json
    {
        "id": 5,
        "customer": 1,
        "to_email": "billing@hospital.com",
        "cc_email": "manager@hospital.com",
        "attach_pdf": true,
        "_links": {
            "self": "http://localhost:8000/api/v1/settings/5/",
            "collection": "http://localhost:8000/api/v1/settings/"
        }
    }
    ```
    """

    class Meta:
        model = Settings
        fields = ["id", "customer", "to_email", "cc_email", "attach_pdf", "_links"]
        read_only_fields = ["id", "customer"]


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Successful Upload",
            description="Completed upload with all claims processed",
            value={
                "id": 567,
                "customer": 1,
                "uploaded_at": "2025-01-26T10:45:00Z",
                "filename": "claims_q1_2025.csv",
                "status": "success",
                "error_message": None,
                "row_count": 8543,
                "date_min": "2025-01-01",
                "date_max": "2025-03-31",
            },
        ),
        OpenApiExample(
            "Failed Upload",
            description="Upload that failed validation",
            value={
                "id": 568,
                "customer": 1,
                "uploaded_at": "2025-01-26T11:00:00Z",
                "filename": "claims_invalid.csv",
                "status": "failed",
                "error_message": "Invalid CSV format: Missing required column 'payer'",
                "row_count": 0,
                "date_min": None,
                "date_max": None,
            },
        ),
    ]
)
class UploadSerializer(HATEOASMixin, serializers.ModelSerializer):
    """
    Serializer for Upload model.

    Represents claim data file uploads with processing status, validation results,
    and temporal coverage metadata.

    **Request Example (Create Upload):**
    ```json
    {
        "filename": "claims_q1_2025.csv",
        "date_min": "2025-01-01",
        "date_max": "2025-03-31"
    }
    ```

    **Success Response (201 Created):**
    ```json
    {
        "id": 567,
        "customer": 1,
        "uploaded_at": "2025-01-26T10:45:00Z",
        "filename": "claims_q1_2025.csv",
        "status": "completed",
        "error_message": null,
        "row_count": 8543,
        "date_min": "2025-01-01",
        "date_max": "2025-03-31",
        "_links": {
            "self": "http://localhost:8000/api/v1/uploads/567/",
            "collection": "http://localhost:8000/api/v1/uploads/",
            "claims": "http://localhost:8000/api/v1/claims/?upload=567"
        }
    }
    ```

    **Error Response (400 Bad Request):**
    ```json
    {
        "filename": ["This field is required."],
        "date_max": ["Date cannot be in the future."]
    }
    ```

    **Status Values:**
    - `pending`: Upload queued for processing
    - `processing`: Currently validating and importing claims
    - `completed`: Successfully processed all records
    - `failed`: Processing failed (see error_message)
    """

    class Meta:
        model = Upload
        fields = [
            "id",
            "customer",
            "uploaded_at",
            "filename",
            "status",
            "error_message",
            "row_count",
            "date_min",
            "date_max",
            "_links",
        ]
        read_only_fields = [
            "id",
            "customer",
            "uploaded_at",
            "status",
            "error_message",
            "row_count",
        ]


class UploadSummarySerializer(HATEOASMixin, serializers.ModelSerializer):
    """Lightweight serializer for Upload listings."""

    class Meta:
        model = Upload
        fields = ["id", "filename", "uploaded_at", "status", "row_count", "_links"]


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Paid Claim",
            description="Example of an approved and paid claim record",
            value={
                "id": 12345,
                "customer": 1,
                "upload": 567,
                "payer": "Blue Cross Blue Shield",
                "cpt": "99213",
                "cpt_group": "Office Visits",
                "submitted_date": "2025-01-15",
                "decided_date": "2025-02-01",
                "outcome": "PAID",
                "allowed_amount": "125.50",
            },
        ),
        OpenApiExample(
            "Denied Claim",
            description="Example of a denied claim with reason code",
            value={
                "id": 12346,
                "customer": 1,
                "upload": 567,
                "payer": "Aetna",
                "cpt": "99214",
                "cpt_group": "Office Visits",
                "submitted_date": "2025-01-16",
                "decided_date": "2025-02-02",
                "outcome": "DENIED",
                "allowed_amount": "0.00",
                "denial_reason_code": "CO-97",
            },
        ),
    ]
)
class ClaimRecordSerializer(HATEOASMixin, serializers.ModelSerializer):
    """
    Serializer for ClaimRecord model.

    Represents healthcare claim records with payer information, procedure codes,
    and payment outcomes.

    **Request Example (Create):**
    ```json
    {
        "payer": "Aetna Health Plans",
        "cpt": "99213",
        "cpt_group": "Office Visits",
        "submitted_date": "2025-01-15",
        "decided_date": "2025-02-01",
        "outcome": "paid",
        "allowed_amount": "125.50"
    }
    ```

    **Success Response (200 OK):**
    ```json
    {
        "id": 12345,
        "customer": 1,
        "upload": 567,
        "payer": "Aetna Health Plans",
        "cpt": "99213",
        "cpt_group": "Office Visits",
        "submitted_date": "2025-01-15",
        "decided_date": "2025-02-01",
        "outcome": "paid",
        "allowed_amount": "125.50",
        "_links": {
            "self": "http://localhost:8000/api/v1/claims/12345/",
            "collection": "http://localhost:8000/api/v1/claims/",
            "upload": "http://localhost:8000/api/v1/uploads/567/"
        }
    }
    ```

    **Error Response (400 Bad Request):**
    ```json
    {
        "payer": ["This field is required."],
        "outcome": [
            "'invalid' is not a valid choice. Choose: paid, denied, pending"
        ]
    }
    ```
    """

    class Meta:
        model = ClaimRecord
        fields = [
            "id",
            "customer",
            "upload",
            "payer",
            "cpt",
            "cpt_group",
            "submitted_date",
            "decided_date",
            "outcome",
            "allowed_amount",
            "_links",
        ]
        read_only_fields = ["id", "customer", "upload"]


class ClaimRecordSummarySerializer(HATEOASMixin, serializers.ModelSerializer):
    """Lightweight serializer for ClaimRecord listings."""

    class Meta:
        model = ClaimRecord
        fields = ["id", "payer", "cpt", "outcome", "decided_date", "_links"]


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "High Severity Drift",
            description="Critical denial rate spike requiring immediate attention",
            value={
                "id": 789,
                "customer": 1,
                "report_run": 456,
                "payer": "Blue Cross Blue Shield",
                "cpt_group": "Cardiology",
                "drift_type": "denial_rate",
                "baseline_value": "15.5",
                "current_value": "32.8",
                "delta_value": "17.3",
                "severity": 0.92,
                "confidence": 0.95,
                "baseline_start": "2024-10-01",
                "baseline_end": "2024-12-31",
                "current_start": "2025-01-01",
                "current_end": "2025-01-25",
                "created_at": "2025-01-26T10:30:00Z",
            },
        ),
        OpenApiExample(
            "Low Severity Drift",
            description="Minor decision time increase within acceptable range",
            value={
                "id": 790,
                "customer": 1,
                "report_run": 456,
                "payer": "Aetna",
                "cpt_group": "Office Visits",
                "drift_type": "decision_time",
                "baseline_value": "18.2",
                "current_value": "21.5",
                "delta_value": "3.3",
                "severity": 0.35,
                "confidence": 0.88,
                "baseline_start": "2024-10-01",
                "baseline_end": "2024-12-31",
                "current_start": "2025-01-01",
                "current_end": "2025-01-25",
                "created_at": "2025-01-26T10:30:00Z",
            },
        ),
    ]
)
class DriftEventSerializer(HATEOASMixin, serializers.ModelSerializer):
    """
    Serializer for DriftEvent model with computed fields.

    Represents detected anomalies in claim patterns with baseline comparison,
    severity scoring, and confidence metrics.

    **Success Response (200 OK):**
    ```json
    {
        "id": 789,
        "customer": 1,
        "report_run": 456,
        "payer": "Blue Cross Blue Shield",
        "cpt_group": "Cardiology",
        "drift_type": "denial_rate",
        "baseline_value": 15.5,
        "current_value": 32.8,
        "delta_value": 17.3,
        "delta_percent": 111.61,
        "severity": 0.85,
        "severity_label": "CRITICAL",
        "confidence": 0.92,
        "baseline_start": "2024-10-01",
        "baseline_end": "2024-12-31",
        "current_start": "2025-01-01",
        "current_end": "2025-01-25",
        "created_at": "2025-01-26T10:30:00Z",
        "_links": {
            "self": "http://localhost:8000/api/v1/drift-events/789/",
            "collection": "http://localhost:8000/api/v1/drift-events/",
            "report": "http://localhost:8000/api/v1/reports/456/"
        }
    }
    ```

    **Error Response (404 Not Found):**
    ```json
    {
        "detail": "Not found."
    }
    ```

    **Computed Fields:**
    - `delta_percent`: Percentage change from baseline (calculated)
    - `severity_label`: Human-readable severity (CRITICAL/HIGH/MEDIUM/LOW)
    """

    delta_percent = serializers.SerializerMethodField()
    severity_label = serializers.SerializerMethodField()

    class Meta:
        model = DriftEvent
        fields = [
            "id",
            "customer",
            "report_run",
            "payer",
            "cpt_group",
            "drift_type",
            "baseline_value",
            "current_value",
            "delta_value",
            "delta_percent",
            "severity",
            "severity_label",
            "confidence",
            "baseline_start",
            "baseline_end",
            "current_start",
            "current_end",
            "created_at",
            "_links",
        ]
        read_only_fields = ["id", "created_at"]

    @extend_schema_field(OpenApiTypes.FLOAT)
    def get_delta_percent(self, obj):
        """Calculate percentage change from baseline."""
        if obj.baseline_value and obj.baseline_value != 0:
            return round((obj.delta_value / obj.baseline_value) * 100, 2)
        return None

    @extend_schema_field(OpenApiTypes.STR)
    def get_severity_label(self, obj):
        """Human-readable severity label."""
        if obj.severity >= 0.8:
            return "CRITICAL"
        elif obj.severity >= 0.6:
            return "HIGH"
        elif obj.severity >= 0.4:
            return "MEDIUM"
        else:
            return "LOW"


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Completed Report",
            description="Successfully completed report with drift events detected",
            value={
                "id": 456,
                "customer": 1,
                "run_type": "weekly",
                "started_at": "2025-01-26T09:00:00Z",
                "finished_at": "2025-01-26T09:15:32Z",
                "status": "success",
                "summary_json": {
                    "total_claims_analyzed": 15420,
                    "drift_events_detected": 12,
                    "high_severity_count": 3,
                },
                "drift_event_count": 12,
            },
        ),
        OpenApiExample(
            "Running Report",
            description="Report currently in progress",
            value={
                "id": 457,
                "customer": 1,
                "run_type": "weekly",
                "started_at": "2025-01-27T10:00:00Z",
                "finished_at": None,
                "status": "running",
                "summary_json": {},
                "drift_event_count": 0,
            },
        ),
    ]
)
class ReportRunSerializer(HATEOASMixin, serializers.ModelSerializer):
    """
    Serializer for ReportRun model with nested drift events.

    Represents analytics report execution with embedded drift event results,
    summary statistics, and execution metadata.

    **Request Example (Trigger Report):**
    ```json
    {
        "run_type": "monthly_analysis"
    }
    ```

    **Success Response (200 OK):**
    ```json
    {
        "id": 456,
        "customer": 1,
        "run_type": "monthly_analysis",
        "started_at": "2025-01-26T09:00:00Z",
        "finished_at": "2025-01-26T09:15:32Z",
        "status": "completed",
        "summary_json": {
            "total_claims_analyzed": 15420,
            "drift_events_detected": 12,
            "high_severity_count": 3
        },
        "drift_events": [
            {
                "id": 789,
                "payer": "Aetna",
                "drift_type": "denial_rate",
                "severity": 0.85,
                "severity_label": "CRITICAL"
            }
        ],
        "drift_event_count": 12,
        "_links": {
            "self": "http://localhost:8000/api/v1/reports/456/",
            "collection": "http://localhost:8000/api/v1/reports/",
            "drift-events": "http://localhost:8000/api/v1/drift-events/?report_run=456"
        }
    }
    ```

    **Error Response (400 Bad Request):**
    ```json
    {
        "run_type": ["'invalid_type' is not a valid choice."]
    }
    ```
    """

    drift_events = DriftEventSerializer(many=True, read_only=True)
    drift_event_count = serializers.SerializerMethodField()

    class Meta:
        model = ReportRun
        fields = [
            "id",
            "customer",
            "run_type",
            "started_at",
            "finished_at",
            "status",
            "summary_json",
            "drift_events",
            "drift_event_count",
            "_links",
        ]
        read_only_fields = ["id", "started_at", "finished_at", "status", "summary_json"]

    @extend_schema_field(OpenApiTypes.INT)
    def get_drift_event_count(self, obj):
        """Count of drift events in this report (PERF-20: uses annotated count)."""
        return getattr(obj, "drift_event_count", obj.drift_events.count())


class ReportRunSummarySerializer(HATEOASMixin, serializers.ModelSerializer):
    """Lightweight serializer for ReportRun listings."""

    drift_event_count = serializers.SerializerMethodField()

    class Meta:
        model = ReportRun
        fields = [
            "id",
            "run_type",
            "started_at",
            "status",
            "drift_event_count",
            "_links",
        ]

    @extend_schema_field(OpenApiTypes.INT)
    def get_drift_event_count(self, obj):
        """PERF-20: Use annotated count to avoid N+1 queries."""
        return getattr(obj, "drift_event_count", obj.drift_events.count())


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for UserProfile model.

    User account with customer association and RBAC role information.

    **Success Response (200 OK):**
    ```json
    {
        "id": 3,
        "username": "jane.analyst",
        "email": "jane@hospital.com",
        "customer": 1,
        "customer_name": "Memorial Hospital System"
    }
    ```
    """

    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.CharField(source="user.email", read_only=True)
    customer_name = serializers.CharField(source="customer.name", read_only=True)

    class Meta:
        model = UserProfile
        fields = ["id", "username", "email", "customer", "customer_name"]
        read_only_fields = ["id", "username", "email"]


class PayerMappingSerializer(HATEOASMixin, serializers.ModelSerializer):
    """
    Serializer for PayerMapping model.

    Maps raw payer names from claim files to standardized normalized names,
    enabling consistent analytics across data sources.

    **Request Example (Create):**
    ```json
    {
        "raw_name": "BCBS of California",
        "normalized_name": "Blue Cross Blue Shield"
    }
    ```

    **Success Response (201 Created):**
    ```json
    {
        "id": 42,
        "customer": 1,
        "raw_name": "BCBS of California",
        "normalized_name": "Blue Cross Blue Shield",
        "_links": {
            "self": "http://localhost:8000/api/v1/payer-mappings/42/",
            "collection": "http://localhost:8000/api/v1/payer-mappings/"
        }
    }
    ```

    **Error Response (400 Bad Request):**
    ```json
    {
        "raw_name": ["This field is required."],
        "normalized_name": ["Ensure this field has no more than 255 characters."]
    }
    ```
    """

    class Meta:
        model = PayerMapping
        fields = ["id", "customer", "raw_name", "normalized_name", "_links"]
        read_only_fields = ["id", "customer"]


class CPTGroupMappingSerializer(HATEOASMixin, serializers.ModelSerializer):
    """
    Serializer for CPTGroupMapping model.

    Maps CPT procedure codes to logical groupings for aggregated analytics.

    **Request Example (Create):**
    ```json
    {
        "cpt_code": "99213",
        "cpt_group": "Office Visits"
    }
    ```

    **Success Response (201 Created):**
    ```json
    {
        "id": 88,
        "customer": 1,
        "cpt_code": "99213",
        "cpt_group": "Office Visits",
        "_links": {
            "self": "http://localhost:8000/api/v1/cpt-group-mappings/88/",
            "collection": "http://localhost:8000/api/v1/cpt-group-mappings/"
        }
    }
    ```
    """

    class Meta:
        model = CPTGroupMapping
        fields = ["id", "customer", "cpt_code", "cpt_group", "_links"]
        read_only_fields = ["id", "customer"]


# =============================================================================
# Analytics Serializers (for dashboard/reporting endpoints)
# =============================================================================


class PayerSummarySerializer(serializers.Serializer):
    """
    Aggregated payer statistics.

    Analytics summary showing claim outcomes and financial metrics by payer.

    **Success Response (200 OK):**
    ```json
    {
        "payer": "Blue Cross Blue Shield",
        "total_claims": 4523,
        "paid_count": 3890,
        "denied_count": 512,
        "other_count": 121,
        "denial_rate": 11.32,
        "avg_allowed_amount": "187.45"
    }
    ```
    """

    payer = serializers.CharField()
    total_claims = serializers.IntegerField()
    paid_count = serializers.IntegerField()
    denied_count = serializers.IntegerField()
    other_count = serializers.IntegerField()
    denial_rate = serializers.FloatField()
    avg_allowed_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, allow_null=True
    )


class DriftInsightSerializer(serializers.Serializer):
    """AI-generated insight for drift events."""

    event_id = serializers.IntegerField()
    payer = serializers.CharField()
    insight_text = serializers.CharField()
    recommendation = serializers.CharField()
    confidence_score = serializers.FloatField()


class DashboardSerializer(serializers.Serializer):
    """
    Dashboard overview data.

    High-level metrics and trends for executive summary view.

    **Success Response (200 OK):**
    ```json
    {
        "total_claims": 45820,
        "total_uploads": 12,
        "active_drift_events": 7,
        "last_report_date": "2025-01-26T09:15:32Z",
        "denial_rate_trend": [
            {"month": "2024-11", "rate": 10.5},
            {"month": "2024-12", "rate": 11.2},
            {"month": "2025-01", "rate": 12.8}
        ],
        "top_drift_payers": [
            {"payer": "Aetna", "severity": 0.85},
            {"payer": "UnitedHealthcare", "severity": 0.72}
        ]
    }
    ```
    """

    total_claims = serializers.IntegerField()
    total_uploads = serializers.IntegerField()
    active_drift_events = serializers.IntegerField()
    last_report_date = serializers.DateTimeField(allow_null=True)
    denial_rate_trend = serializers.ListField(child=serializers.DictField())
    top_drift_payers = serializers.ListField(child=serializers.DictField())


# =============================================================================
# Alert & Operator Judgment Serializers
# =============================================================================


class OperatorJudgmentSerializer(serializers.ModelSerializer):
    """
    Serializer for OperatorJudgment model.

    Captures operator feedback on alert events, including verdict classification,
    reason codes, and recovery tracking for financial impact assessment.

    **Request Example (Create Judgment):**
    ```json
    {
        "alert_event": 234,
        "verdict": "real",
        "reason_codes_json": ["coding_error", "payer_policy_change"],
        "recovered_amount": "2450.00",
        "recovered_date": "2025-02-15",
        "notes": "Identified systematic coding issue affecting Cardiology claims"
    }
    ```

    **Success Response (201 Created):**
    ```json
    {
        "id": 67,
        "customer": 1,
        "alert_event": 234,
        "verdict": "real",
        "reason_codes_json": ["coding_error", "payer_policy_change"],
        "recovered_amount": "2450.00",
        "recovered_date": "2025-02-15",
        "notes": "Identified systematic coding issue affecting Cardiology claims",
        "operator": 3,
        "operator_username": "jane.analyst",
        "created_at": "2025-01-26T14:20:00Z",
        "updated_at": "2025-01-26T14:20:00Z"
    }
    ```

    **Error Response (400 Bad Request):**
    ```json
    {
        "verdict": ["This field is required."],
        "alert_event": ["Invalid pk '999' - object does not exist."]
    }
    ```

    **Verdict Choices:**
    - `noise`: False positive, no action needed
    - `real`: Legitimate issue requiring follow-up
    - `needs_followup`: Uncertain, requires additional investigation
    """

    operator_username = serializers.CharField(
        source="operator.username", read_only=True
    )

    class Meta:
        model = OperatorJudgment
        fields = [
            "id",
            "customer",
            "alert_event",
            "verdict",
            "reason_codes_json",
            "recovered_amount",
            "recovered_date",
            "notes",
            "operator",
            "operator_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "customer",
            "operator",
            "operator_username",
            "created_at",
            "updated_at",
        ]


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Triggered Alert",
            description="Alert event triggered by critical drift detection",
            value={
                "id": 234,
                "customer": 1,
                "alert_rule": 45,
                "drift_event": 789,
                "report_run": 456,
                "triggered_at": "2025-01-26T10:30:15Z",
                "status": "triggered",
                "payload": {
                    "severity": "CRITICAL",
                    "payer": "Blue Cross Blue Shield",
                    "drift_type": "denial_rate",
                    "message": "Denial rate spike detected: 15.5% → 32.8%",
                },
                "notification_sent_at": None,
                "error_message": None,
                "has_judgment": False,
                "latest_judgment_verdict": None,
                "created_at": "2025-01-26T10:30:15Z",
                "updated_at": "2025-01-26T10:30:15Z",
            },
        ),
        OpenApiExample(
            "Resolved Alert",
            description="Alert with operator feedback marking it as resolved",
            value={
                "id": 235,
                "customer": 1,
                "alert_rule": 45,
                "drift_event": 790,
                "report_run": 456,
                "triggered_at": "2025-01-26T10:35:00Z",
                "status": "resolved",
                "payload": {
                    "severity": "HIGH",
                    "payer": "Aetna",
                    "drift_type": "decision_time",
                    "message": "Decision time increased: 18.2 → 28.9 days",
                },
                "notification_sent_at": "2025-01-26T10:35:05Z",
                "error_message": None,
                "has_judgment": True,
                "latest_judgment_verdict": "real",
                "created_at": "2025-01-26T10:35:00Z",
                "updated_at": "2025-01-26T14:20:00Z",
            },
        ),
    ]
)
class AlertEventSerializer(serializers.ModelSerializer):
    """
    Serializer for AlertEvent model with operator judgments.

    Represents alert notifications triggered by drift events, including delivery
    status, operator feedback, and resolution tracking.

    **Success Response (200 OK):**
    ```json
    {
        "id": 234,
        "customer": 1,
        "alert_rule": 45,
        "drift_event": 789,
        "report_run": 456,
        "triggered_at": "2025-01-26T10:30:15Z",
        "status": "delivered",
        "payload": {
            "severity": "CRITICAL",
            "message": "Denial rate spike detected for Aetna"
        },
        "notification_sent_at": "2025-01-26T10:30:18Z",
        "error_message": null,
        "operator_judgments": [
            {
                "id": 67,
                "verdict": "real",
                "notes": "Confirmed pattern change",
                "operator_username": "jane.analyst"
            }
        ],
        "has_judgment": true,
        "latest_judgment_verdict": "real",
        "created_at": "2025-01-26T10:30:15Z",
        "updated_at": "2025-01-26T14:20:00Z"
    }
    ```

    **Error Response (404 Not Found):**
    ```json
    {
        "detail": "Not found."
    }
    ```
    """

    operator_judgments = serializers.SerializerMethodField()
    has_judgment = serializers.SerializerMethodField()
    latest_judgment_verdict = serializers.SerializerMethodField()

    class Meta:
        model = AlertEvent
        fields = [
            "id",
            "customer",
            "alert_rule",
            "drift_event",
            "report_run",
            "triggered_at",
            "status",
            "payload",
            "notification_sent_at",
            "error_message",
            "operator_judgments",
            "has_judgment",
            "latest_judgment_verdict",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "triggered_at"]

    def get_operator_judgments(self, obj):
        """
        Get operator judgments (PERF-20: uses prefetched data).
        """
        # Use prefetched operator_judgments to avoid N+1 queries
        # Prefetch is defined in AlertEventViewSet.queryset
        judgments = obj.operator_judgments.all()
        return OperatorJudgmentSerializer(judgments, many=True).data

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_has_judgment(self, obj):
        """
        Check if alert has operator judgment (PERF-20: uses prefetched).
        """
        # Use prefetched operator_judgments to avoid N+1 queries
        return len(obj.operator_judgments.all()) > 0

    @extend_schema_field(OpenApiTypes.STR)
    def get_latest_judgment_verdict(self, obj):
        """
        Get latest judgment verdict (PERF-20: uses prefetched data).
        """
        # Use prefetched operator_judgments and sort in Python to avoid N+1 queries
        judgments = list(obj.operator_judgments.all())
        if not judgments:
            return None
        latest = max(judgments, key=lambda j: j.created_at)
        return latest.verdict


class OperatorFeedbackSerializer(serializers.Serializer):
    """
    Serializer for operator feedback submission.

    Structured input form for operator judgment creation on alert events.

    **Request Example:**
    ```json
    {
        "verdict": "real",
        "reason_codes": ["coding_error", "payer_policy_change"],
        "recovered_amount": "2450.00",
        "recovered_date": "2025-02-15",
        "notes": "Systematic coding issue identified"
    }
    ```

    **Validation Error (400 Bad Request):**
    ```json
    {
        "verdict": ["This field is required."],
        "recovered_amount": ["Ensure that there are no more than 12 digits in total."]
    }
    ```
    """

    verdict = serializers.ChoiceField(
        choices=[
            ("noise", "Noise"),
            ("real", "Real/Legitimate"),
            ("needs_followup", "Needs Follow-up"),
        ]
    )
    reason_codes = serializers.ListField(
        child=serializers.CharField(), required=False, allow_empty=True
    )
    recovered_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    recovered_date = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class HealthCheckSerializer(serializers.Serializer):
    """Serializer for health check endpoint response."""

    status = serializers.CharField(help_text="Health status: 'healthy' or 'unhealthy'")
    version = serializers.CharField(help_text="Application version")
    timestamp = serializers.DateTimeField(help_text="Current server timestamp")
