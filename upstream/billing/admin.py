"""
Admin interface for billing models.
"""

from django.contrib import admin
from .models import Subscription


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
