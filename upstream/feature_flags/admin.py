"""
Django admin configuration for feature flags.
"""

from django.contrib import admin
from upstream.feature_flags.models import (
    FeatureFlag,
    FeatureFlagOverride,
    FeatureFlagAuditLog,
)


class FeatureFlagOverrideInline(admin.TabularInline):
    model = FeatureFlagOverride
    extra = 0
    fields = ("customer", "user", "override_value", "reason", "created_at")
    readonly_fields = ("created_at",)


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "enabled",
        "rollout_percentage",
        "enabled_in_production",
        "enabled_in_staging",
        "updated_at",
    )
    list_filter = (
        "enabled",
        "enabled_in_production",
        "enabled_in_staging",
        "enabled_in_development",
    )
    search_fields = ("name", "description")
    readonly_fields = ("created_at", "updated_at", "created_by")
    inlines = [FeatureFlagOverrideInline]

    fieldsets = (
        (None, {"fields": ("name", "description", "enabled")}),
        (
            "Rollout",
            {
                "fields": ("rollout_percentage",),
                "description": "Percentage of users to enable for (0-100)",
            },
        ),
        (
            "Environment Settings",
            {
                "fields": (
                    "enabled_in_development",
                    "enabled_in_staging",
                    "enabled_in_production",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadata",
            {
                "fields": ("created_by", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        if not change:  # Creating new flag
            obj.created_by = request.user

        # Log the change
        if change:
            changes = {}
            for field in form.changed_data:
                changes[field] = {
                    "old": form.initial.get(field),
                    "new": form.cleaned_data.get(field),
                }

            FeatureFlagAuditLog.objects.create(
                feature_flag_name=obj.name,
                action=FeatureFlagAuditLog.ACTION_UPDATED,
                changes=changes,
                performed_by=request.user,
            )
        else:
            FeatureFlagAuditLog.objects.create(
                feature_flag_name=obj.name,
                action=FeatureFlagAuditLog.ACTION_CREATED,
                changes={"initial_state": form.cleaned_data},
                performed_by=request.user,
            )

        super().save_model(request, obj, form, change)


@admin.register(FeatureFlagOverride)
class FeatureFlagOverrideAdmin(admin.ModelAdmin):
    list_display = (
        "feature_flag",
        "get_target",
        "override_value",
        "created_at",
    )
    list_filter = ("override_value", "feature_flag")
    search_fields = (
        "feature_flag__name",
        "customer__name",
        "user__email",
    )
    raw_id_fields = ("customer", "user", "created_by")

    def get_target(self, obj):
        if obj.customer:
            return f"Customer: {obj.customer.name}"
        return f"User: {obj.user.email}"

    get_target.short_description = "Target"


@admin.register(FeatureFlagAuditLog)
class FeatureFlagAuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "feature_flag_name",
        "action",
        "performed_by",
        "performed_at",
    )
    list_filter = ("action", "feature_flag_name")
    search_fields = ("feature_flag_name",)
    readonly_fields = (
        "feature_flag_name",
        "action",
        "changes",
        "performed_by",
        "performed_at",
        "ip_address",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
