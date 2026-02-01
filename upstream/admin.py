from django.contrib import admin
from django.utils.html import format_html
from .models import (
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
from upstream.core.models import ProductConfig
from upstream.automation.models import (
    ClaimScore,
    CustomerAutomationProfile,
    ShadowModeResult,
)
from upstream.integrations.models import EHRConnection, EHRSyncLog


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


@admin.register(Settings)
class SettingsAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "to_email", "attach_pdf")
    search_fields = ("customer__name", "to_email")
    list_filter = ("attach_pdf",)


@admin.register(Upload)
class UploadAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "filename", "status", "uploaded_at", "row_count")
    list_filter = ("status", "customer")
    search_fields = ("filename", "customer__name")
    date_hierarchy = "uploaded_at"


@admin.register(ClaimRecord)
class ClaimRecordAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "customer",
        "upload",
        "payer",
        "cpt",
        "outcome",
        "submitted_date",
        "decided_date",
    )
    list_filter = ("customer", "outcome", "payer", "cpt_group")
    search_fields = ("payer", "cpt", "customer__name")
    date_hierarchy = "submitted_date"


@admin.register(ReportRun)
class ReportRunAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "run_type", "status", "started_at", "finished_at")
    list_filter = ("run_type", "status", "customer")
    search_fields = ("customer__name",)
    date_hierarchy = "started_at"


@admin.register(DriftEvent)
class DriftEventAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "customer",
        "report_run",
        "payer",
        "cpt_group",
        "drift_type",
        "severity",
        "confidence",
        "created_at",
    )
    list_filter = ("drift_type", "customer", "payer", "cpt_group")
    search_fields = ("payer", "cpt_group", "customer__name")
    date_hierarchy = "created_at"


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "customer")
    search_fields = ("user__username", "customer__name")
    list_filter = ("customer",)


@admin.register(PayerMapping)
class PayerMappingAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "raw_name", "normalized_name")
    search_fields = ("customer__name", "raw_name", "normalized_name")
    list_filter = ("customer",)


@admin.register(CPTGroupMapping)
class CPTGroupMappingAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "cpt_code", "cpt_group")
    search_fields = ("customer__name", "cpt_code", "cpt_group")
    list_filter = ("customer", "cpt_group")


@admin.register(ProductConfig)
class ProductConfigAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "product_slug", "enabled", "created_at")
    list_filter = ("enabled", "product_slug", "customer")
    search_fields = ("customer__name",)
    date_hierarchy = "created_at"
    fieldsets = (
        ("Product", {"fields": ("customer", "product_slug", "enabled")}),
        ("Configuration", {"fields": ("config_json",), "classes": ("collapse",)}),
        (
            "Metadata",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )
    readonly_fields = ("created_at", "updated_at")


@admin.register(ClaimScore)
class ClaimScoreAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "claim",
        "customer",
        "overall_confidence",
        "denial_risk_score",
        "automation_tier",
        "recommended_action",
        "requires_human_review",
        "created_at",
    )
    list_filter = (
        "automation_tier",
        "recommended_action",
        "requires_human_review",
        "customer",
        "model_version",
    )
    search_fields = ("customer__name", "claim__payer", "claim__cpt", "red_line_reason")
    date_hierarchy = "created_at"
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Claim Information", {"fields": ("claim", "customer")}),
        (
            "Confidence Metrics",
            {
                "fields": (
                    "overall_confidence",
                    "coding_confidence",
                    "eligibility_confidence",
                    "medical_necessity_confidence",
                    "documentation_completeness",
                )
            },
        ),
        (
            "Risk Scores",
            {
                "fields": (
                    "denial_risk_score",
                    "fraud_risk_score",
                    "compliance_risk_score",
                )
            },
        ),
        (
            "Automation Decision",
            {
                "fields": (
                    "automation_tier",
                    "recommended_action",
                    "requires_human_review",
                    "red_line_reason",
                )
            },
        ),
        (
            "Model Metadata",
            {
                "fields": (
                    "model_version",
                    "feature_importance",
                    "prediction_reasoning",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(CustomerAutomationProfile)
class CustomerAutomationProfileAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "customer",
        "automation_stage",
        "shadow_mode_enabled",
        "shadow_accuracy_rate",
        "auto_submit_claims",
        "created_at",
    )
    list_filter = (
        "automation_stage",
        "shadow_mode_enabled",
        "auto_submit_claims",
        "auto_check_status",
        "auto_verify_eligibility",
    )
    search_fields = (
        "customer__name",
        "notification_email",
        "compliance_officer__username",
    )
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Customer", {"fields": ("customer", "compliance_officer")}),
        ("Trust Calibration", {"fields": ("automation_stage", "stage_start_date")}),
        (
            "Tier 1: Auto-Execute Thresholds",
            {"fields": ("auto_execute_confidence", "auto_execute_max_amount")},
        ),
        (
            "Tier 2: Queue Review Thresholds",
            {"fields": ("queue_review_min_confidence", "queue_review_max_amount")},
        ),
        ("Tier 3: Escalate Thresholds", {"fields": ("escalate_min_amount",)}),
        (
            "Action Toggles",
            {
                "fields": (
                    "auto_submit_claims",
                    "auto_check_status",
                    "auto_verify_eligibility",
                    "auto_submit_prior_auth",
                    "auto_modify_codes",
                    "auto_submit_appeals",
                )
            },
        ),
        (
            "Shadow Mode",
            {
                "fields": (
                    "shadow_mode_enabled",
                    "shadow_mode_start_date",
                    "shadow_accuracy_rate",
                    "shadow_mode_min_accuracy",
                )
            },
        ),
        (
            "Notifications",
            {
                "fields": (
                    "notify_on_auto_execute",
                    "notify_on_escalation",
                    "notification_email",
                    "undo_window_hours",
                )
            },
        ),
        ("Compliance", {"fields": ("audit_all_actions",)}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(ShadowModeResult)
class ShadowModeResultAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "customer",
        "claim_score",
        "ai_recommended_action",
        "ai_confidence",
        "human_action_taken",
        "actions_match",
        "outcome",
        "created_at",
    )
    list_filter = ("actions_match", "outcome", "customer", "ai_recommended_action")
    search_fields = (
        "customer__name",
        "ai_recommended_action",
        "human_action_taken",
        "discrepancy_reason",
        "human_decision_user__username",
    )
    date_hierarchy = "created_at"
    readonly_fields = ("created_at",)
    fieldsets = (
        ("Reference", {"fields": ("customer", "claim_score")}),
        ("AI Prediction", {"fields": ("ai_recommended_action", "ai_confidence")}),
        (
            "Human Decision",
            {
                "fields": (
                    "human_action_taken",
                    "human_decision_user",
                    "human_decision_timestamp",
                )
            },
        ),
        ("Comparison", {"fields": ("actions_match", "outcome", "discrepancy_reason")}),
        ("Timestamps", {"fields": ("created_at",), "classes": ("collapse",)}),
    )


class EHRSyncLogInline(admin.TabularInline):
    """Inline display of sync history for EHR connections."""

    model = EHRSyncLog
    extra = 0
    readonly_fields = (
        "started_at",
        "completed_at",
        "status",
        "records_fetched",
        "records_created",
        "error_message",
    )
    fields = (
        "started_at",
        "completed_at",
        "status",
        "records_fetched",
        "records_created",
        "error_message",
    )
    ordering = ["-started_at"]
    max_num = 10
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(EHRConnection)
class EHRConnectionAdmin(admin.ModelAdmin):
    """Admin interface for EHR connections with secret masking."""

    list_display = (
        "id",
        "name",
        "customer",
        "ehr_type",
        "enabled",
        "health_status_display",
        "last_poll",
        "created_at",
    )
    list_filter = ("ehr_type", "enabled", "health_status", "customer")
    search_fields = ("name", "customer__name", "client_id")
    date_hierarchy = "created_at"
    readonly_fields = (
        "created_at",
        "updated_at",
        "last_poll",
        "last_error",
        "health_status",
        "health_checked_at",
        "masked_secret_display",
    )
    inlines = [EHRSyncLogInline]

    fieldsets = (
        ("Connection Info", {"fields": ("customer", "name", "ehr_type", "enabled")}),
        (
            "OAuth Credentials",
            {
                "fields": ("client_id", "client_secret", "masked_secret_display"),
                "description": "OAuth 2.0 client credentials. Client secret is encrypted at rest.",
            },
        ),
        ("Endpoints", {"fields": ("oauth_endpoint", "fhir_endpoint")}),
        (
            "Health Status",
            {
                "fields": (
                    "health_status",
                    "health_checked_at",
                    "last_poll",
                    "last_error",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Audit",
            {
                "fields": ("created_at", "updated_at", "created_by", "updated_by"),
                "classes": ("collapse",),
            },
        ),
    )

    def health_status_display(self, obj):
        """Display health status with color coding."""
        colors = {
            "healthy": "green",
            "degraded": "orange",
            "unhealthy": "red",
            "unknown": "gray",
        }
        color = colors.get(obj.health_status, "gray")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_health_status_display(),
        )

    health_status_display.short_description = "Health"

    def masked_secret_display(self, obj):
        """Display masked client secret for verification."""
        if obj.client_secret:
            return format_html(
                '<span style="font-family: monospace;">{}...{}</span> '
                '<span style="color: green;">✓ Encrypted</span>',
                "*" * 8,
                "*" * 4,
            )
        return format_html('<span style="color: red;">Not set</span>')

    masked_secret_display.short_description = "Client Secret (Masked)"

    def get_readonly_fields(self, request, obj=None):
        """Make customer read-only on edit."""
        if obj:  # Editing existing object
            return self.readonly_fields + ("customer",)
        return self.readonly_fields


@admin.register(EHRSyncLog)
class EHRSyncLogAdmin(admin.ModelAdmin):
    """Admin interface for EHR sync audit logs."""

    list_display = (
        "id",
        "connection",
        "started_at",
        "completed_at",
        "status",
        "records_fetched",
        "records_created",
        "duration_display",
    )
    list_filter = ("status", "connection__ehr_type", "connection__customer")
    search_fields = ("connection__name", "connection__customer__name", "error_message")
    date_hierarchy = "started_at"
    readonly_fields = (
        "connection",
        "started_at",
        "completed_at",
        "status",
        "records_fetched",
        "records_created",
        "records_updated",
        "records_skipped",
        "error_message",
        "sync_metadata",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Sync Info",
            {"fields": ("connection", "started_at", "completed_at", "status")},
        ),
        (
            "Results",
            {
                "fields": (
                    "records_fetched",
                    "records_created",
                    "records_updated",
                    "records_skipped",
                )
            },
        ),
        ("Error Details", {"fields": ("error_message",), "classes": ("collapse",)}),
        ("Metadata", {"fields": ("sync_metadata",), "classes": ("collapse",)}),
    )

    def duration_display(self, obj):
        """Display sync duration."""
        duration = obj.duration_seconds
        if duration is not None:
            return f"{duration:.2f}s"
        return "-"

    duration_display.short_description = "Duration"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        # Only superusers can delete audit logs
        return request.user.is_superuser
