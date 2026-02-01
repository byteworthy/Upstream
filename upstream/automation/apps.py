"""
AppConfig for Upstream Automation app.

Handles the RCM automation models including ClaimScore, CustomerAutomationProfile,
and ShadowModeResult for confidence scoring and trust calibration.
"""

from django.apps import AppConfig


class AutomationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "upstream.automation"
    verbose_name = "Upstream Automation"
