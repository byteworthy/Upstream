"""
Feature flag models for gradual rollout management.

Provides database-backed feature flags with:
- Percentage-based rollout
- User/customer targeting
- Environment-specific settings
- Audit logging
"""

from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class FeatureFlag(models.Model):
    """
    A feature flag for controlling feature availability.
    """

    name = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Unique identifier for the feature flag (snake_case)",
    )
    description = models.TextField(
        blank=True,
        help_text="Human-readable description of what this flag controls",
    )

    # Global state
    enabled = models.BooleanField(
        default=False,
        help_text="Master switch - if False, flag is off for everyone",
    )

    # Rollout percentage (0-100)
    rollout_percentage = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Percentage of users to enable for (0-100)",
    )

    # Environment controls
    enabled_in_development = models.BooleanField(
        default=True,
        help_text="Enable in development environment",
    )
    enabled_in_staging = models.BooleanField(
        default=True,
        help_text="Enable in staging environment",
    )
    enabled_in_production = models.BooleanField(
        default=False,
        help_text="Enable in production environment",
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_feature_flags",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Feature Flag"
        verbose_name_plural = "Feature Flags"

    def __str__(self):
        status = "ON" if self.enabled else "OFF"
        return f"{self.name} ({status}, {self.rollout_percentage}%)"


class FeatureFlagOverride(models.Model):
    """
    Override feature flag state for specific customers or users.

    Overrides take precedence over the rollout percentage.
    """

    OVERRIDE_ENABLED = "enabled"
    OVERRIDE_DISABLED = "disabled"
    OVERRIDE_CHOICES = [
        (OVERRIDE_ENABLED, "Enabled"),
        (OVERRIDE_DISABLED, "Disabled"),
    ]

    feature_flag = models.ForeignKey(
        FeatureFlag,
        on_delete=models.CASCADE,
        related_name="overrides",
    )

    # Target (either customer or user, not both)
    customer = models.ForeignKey(
        "upstream.Customer",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="feature_flag_overrides",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="feature_flag_overrides",
    )

    override_value = models.CharField(
        max_length=20,
        choices=OVERRIDE_CHOICES,
        default=OVERRIDE_ENABLED,
    )

    reason = models.TextField(
        blank=True,
        help_text="Reason for this override (for audit purposes)",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_feature_overrides",
    )

    class Meta:
        # Ensure unique override per flag/target combination
        constraints = [
            models.UniqueConstraint(
                fields=["feature_flag", "customer"],
                name="unique_flag_customer",
                condition=models.Q(customer__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["feature_flag", "user"],
                name="unique_flag_user",
                condition=models.Q(user__isnull=False),
            ),
            # Ensure either customer or user is set, not both
            models.CheckConstraint(
                check=(
                    models.Q(customer__isnull=False, user__isnull=True)
                    | models.Q(customer__isnull=True, user__isnull=False)
                ),
                name="customer_or_user_not_both",
            ),
        ]
        verbose_name = "Feature Flag Override"
        verbose_name_plural = "Feature Flag Overrides"

    def __str__(self):
        target = self.customer.name if self.customer else self.user.email
        return f"{self.feature_flag.name}: {self.override_value} for {target}"


class FeatureFlagAuditLog(models.Model):
    """
    Audit log for feature flag changes.
    """

    ACTION_CREATED = "created"
    ACTION_UPDATED = "updated"
    ACTION_DELETED = "deleted"
    ACTION_OVERRIDE_ADDED = "override_added"
    ACTION_OVERRIDE_REMOVED = "override_removed"
    ACTION_CHOICES = [
        (ACTION_CREATED, "Created"),
        (ACTION_UPDATED, "Updated"),
        (ACTION_DELETED, "Deleted"),
        (ACTION_OVERRIDE_ADDED, "Override Added"),
        (ACTION_OVERRIDE_REMOVED, "Override Removed"),
    ]

    feature_flag_name = models.CharField(max_length=100)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    changes = models.JSONField(
        default=dict,
        help_text="JSON object describing what changed",
    )

    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    performed_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-performed_at"]
        verbose_name = "Feature Flag Audit Log"
        verbose_name_plural = "Feature Flag Audit Logs"

    def __str__(self):
        return f"{self.feature_flag_name}: {self.action} at {self.performed_at}"
