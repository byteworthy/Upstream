"""Django app configuration for Dialysis specialty module."""

from django.apps import AppConfig


class DialysisConfig(AppConfig):
    """Configuration for the Dialysis specialty module."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "upstream.products.dialysis"
    verbose_name = "Dialysis Specialty Module"
