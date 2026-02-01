from django.contrib import admin
from .models import Customer, Settings, Upload, ClaimRecord, ReportRun, DriftEvent, UserProfile, PayerMapping, CPTGroupMapping
from upstream.core.models import ProductConfig
from upstream.automation.models import ClaimScore, CustomerAutomationProfile, ShadowModeResult

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)

@admin.register(Settings)
class SettingsAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'to_email', 'attach_pdf')
    search_fields = ('customer__name', 'to_email')
    list_filter = ('attach_pdf',)

@admin.register(Upload)
class UploadAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'filename', 'status', 'uploaded_at', 'row_count')
    list_filter = ('status', 'customer')
    search_fields = ('filename', 'customer__name')
    date_hierarchy = 'uploaded_at'

@admin.register(ClaimRecord)
class ClaimRecordAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'upload', 'payer', 'cpt', 'outcome', 'submitted_date', 'decided_date')
    list_filter = ('customer', 'outcome', 'payer', 'cpt_group')
    search_fields = ('payer', 'cpt', 'customer__name')
    date_hierarchy = 'submitted_date'

@admin.register(ReportRun)
class ReportRunAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'run_type', 'status', 'started_at', 'finished_at')
    list_filter = ('run_type', 'status', 'customer')
    search_fields = ('customer__name',)
    date_hierarchy = 'started_at'

@admin.register(DriftEvent)
class DriftEventAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'report_run', 'payer', 'cpt_group', 'drift_type', 'severity', 'confidence', 'created_at')
    list_filter = ('drift_type', 'customer', 'payer', 'cpt_group')
    search_fields = ('payer', 'cpt_group', 'customer__name')
    date_hierarchy = 'created_at'

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'customer')
    search_fields = ('user__username', 'customer__name')
    list_filter = ('customer',)

@admin.register(PayerMapping)
class PayerMappingAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'raw_name', 'normalized_name')
    search_fields = ('customer__name', 'raw_name', 'normalized_name')
    list_filter = ('customer',)

@admin.register(CPTGroupMapping)
class CPTGroupMappingAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'cpt_code', 'cpt_group')
    search_fields = ('customer__name', 'cpt_code', 'cpt_group')
    list_filter = ('customer', 'cpt_group')

@admin.register(ProductConfig)
class ProductConfigAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'product_slug', 'enabled', 'created_at')
    list_filter = ('enabled', 'product_slug', 'customer')
    search_fields = ('customer__name',)
    date_hierarchy = 'created_at'
    fieldsets = (
        ('Product', {
            'fields': ('customer', 'product_slug', 'enabled')
        }),
        ('Configuration', {
            'fields': ('config_json',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ClaimScore)
class ClaimScoreAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'claim', 'customer', 'overall_confidence', 'denial_risk_score',
        'automation_tier', 'recommended_action', 'requires_human_review', 'created_at'
    )
    list_filter = (
        'automation_tier', 'recommended_action', 'requires_human_review',
        'customer', 'model_version'
    )
    search_fields = ('customer__name', 'claim__payer', 'claim__cpt', 'red_line_reason')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Claim Information', {
            'fields': ('claim', 'customer')
        }),
        ('Confidence Metrics', {
            'fields': (
                'overall_confidence', 'coding_confidence', 'eligibility_confidence',
                'medical_necessity_confidence', 'documentation_completeness'
            )
        }),
        ('Risk Scores', {
            'fields': ('denial_risk_score', 'fraud_risk_score', 'compliance_risk_score')
        }),
        ('Automation Decision', {
            'fields': (
                'automation_tier', 'recommended_action',
                'requires_human_review', 'red_line_reason'
            )
        }),
        ('Model Metadata', {
            'fields': ('model_version', 'feature_importance', 'prediction_reasoning'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(CustomerAutomationProfile)
class CustomerAutomationProfileAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'customer', 'automation_stage', 'shadow_mode_enabled',
        'shadow_accuracy_rate', 'auto_submit_claims', 'created_at'
    )
    list_filter = (
        'automation_stage', 'shadow_mode_enabled', 'auto_submit_claims',
        'auto_check_status', 'auto_verify_eligibility'
    )
    search_fields = ('customer__name', 'notification_email', 'compliance_officer__username')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Customer', {
            'fields': ('customer', 'compliance_officer')
        }),
        ('Trust Calibration', {
            'fields': ('automation_stage', 'stage_start_date')
        }),
        ('Tier 1: Auto-Execute Thresholds', {
            'fields': ('auto_execute_confidence', 'auto_execute_max_amount')
        }),
        ('Tier 2: Queue Review Thresholds', {
            'fields': ('queue_review_min_confidence', 'queue_review_max_amount')
        }),
        ('Tier 3: Escalate Thresholds', {
            'fields': ('escalate_min_amount',)
        }),
        ('Action Toggles', {
            'fields': (
                'auto_submit_claims', 'auto_check_status', 'auto_verify_eligibility',
                'auto_submit_prior_auth', 'auto_modify_codes', 'auto_submit_appeals'
            )
        }),
        ('Shadow Mode', {
            'fields': (
                'shadow_mode_enabled', 'shadow_mode_start_date',
                'shadow_accuracy_rate', 'shadow_mode_min_accuracy'
            )
        }),
        ('Notifications', {
            'fields': (
                'notify_on_auto_execute', 'notify_on_escalation',
                'notification_email', 'undo_window_hours'
            )
        }),
        ('Compliance', {
            'fields': ('audit_all_actions',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ShadowModeResult)
class ShadowModeResultAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'customer', 'claim_score', 'ai_recommended_action', 'ai_confidence',
        'human_action_taken', 'actions_match', 'outcome', 'created_at'
    )
    list_filter = ('actions_match', 'outcome', 'customer', 'ai_recommended_action')
    search_fields = (
        'customer__name', 'ai_recommended_action', 'human_action_taken',
        'discrepancy_reason', 'human_decision_user__username'
    )
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)
    fieldsets = (
        ('Reference', {
            'fields': ('customer', 'claim_score')
        }),
        ('AI Prediction', {
            'fields': ('ai_recommended_action', 'ai_confidence')
        }),
        ('Human Decision', {
            'fields': ('human_action_taken', 'human_decision_user', 'human_decision_timestamp')
        }),
        ('Comparison', {
            'fields': ('actions_match', 'outcome', 'discrepancy_reason')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
