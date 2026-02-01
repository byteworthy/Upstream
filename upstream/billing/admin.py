"""
Admin interface for billing models.
"""

from django.contrib import admin
from .models import Subscription, UsageRecord


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "customer",
        "tier",
        "status",
        "monthly_price",
        "current_period_end",
        "trial_end",
        "created_at",
    )
    list_filter = ("tier", "status", "cancel_at_period_end")
    search_fields = ("customer__name", "stripe_subscription_id")
    date_hierarchy = "created_at"
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (
            "Customer",
            {
                "fields": ("customer",),
            },
        ),
        (
            "Stripe",
            {
                "fields": ("stripe_subscription_id",),
            },
        ),
        (
            "Subscription Details",
            {
                "fields": ("tier", "status"),
            },
        ),
        (
            "Billing Period",
            {
                "fields": (
                    "current_period_start",
                    "current_period_end",
                    "trial_end",
                ),
            },
        ),
        (
            "Cancellation",
            {
                "fields": ("cancel_at_period_end", "canceled_at"),
                "classes": ("collapse",),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def monthly_price(self, obj):
        return f"${obj.monthly_price}"

    monthly_price.short_description = "Monthly Price"


@admin.register(UsageRecord)
class UsageRecordAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "customer",
        "period_start",
        "period_end",
        "claims_processed",
        "claims_scored",
        "api_calls",
        "storage_display",
    )
    list_filter = ("period_start", "customer")
    search_fields = ("customer__name",)
    date_hierarchy = "period_start"
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (
            "Customer & Period",
            {
                "fields": ("customer", "period_start", "period_end"),
            },
        ),
        (
            "Usage Metrics",
            {
                "fields": (
                    "claims_processed",
                    "claims_scored",
                    "api_calls",
                    "storage_bytes",
                ),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def storage_display(self, obj):
        """Display storage in human-readable format."""
        bytes_val = obj.storage_bytes
        if bytes_val < 1024:
            return f"{bytes_val} B"
        elif bytes_val < 1024 * 1024:
            return f"{bytes_val / 1024:.1f} KB"
        elif bytes_val < 1024 * 1024 * 1024:
            return f"{bytes_val / (1024 * 1024):.1f} MB"
        else:
            return f"{bytes_val / (1024 * 1024 * 1024):.1f} GB"

    storage_display.short_description = "Storage"
