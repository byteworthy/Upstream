"""Admin configuration for Dialysis models."""

from django.contrib import admin
from upstream.products.dialysis.models import DialysisMABaseline


@admin.register(DialysisMABaseline)
class DialysisMABaselineAdmin(admin.ModelAdmin):
    """Admin interface for DialysisMABaseline model."""

    list_display = (
        "cpt",
        "average_payment",
        "sample_size",
        "last_updated",
        "created_at",
    )
    list_filter = ("last_updated",)
    search_fields = ("cpt",)
    ordering = ("cpt",)
    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")

    fieldsets = (
        (
            "Baseline Information",
            {
                "fields": ("cpt", "average_payment", "sample_size", "last_updated"),
            },
        ),
        (
            "Audit Information",
            {
                "fields": ("created_at", "updated_at", "created_by", "updated_by"),
                "classes": ("collapse",),
            },
        ),
    )
