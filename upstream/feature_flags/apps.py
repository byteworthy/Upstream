"""
Django app configuration for feature flags.
"""

from django.apps import AppConfig


class FeatureFlagsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "upstream.feature_flags"
    verbose_name = "Feature Flags"
