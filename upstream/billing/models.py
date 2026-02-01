"""
Billing models for subscription management.

Supports tiered subscription pricing:
- Essentials: $299/month
- Professional: $599/month
- Enterprise: $999/month
"""

from django.db import models
from django.core.validators import MinValueValidator
from upstream.models import Customer
from upstream.core.tenant import CustomerScopedManager


class Subscription(models.Model):
    """
    Customer subscription tracking for Stripe billing.

    Stores subscription state synced from Stripe webhooks.
    """

    TIER_CHOICES = [
        ("essentials", "Essentials"),
        ("professional", "Professional"),
        ("enterprise", "Enterprise"),
    ]

    TIER_PRICING = {
        "essentials": 299,
        "professional": 599,
        "enterprise": 999,
    }

    STATUS_CHOICES = [
        ("trialing", "Trialing"),
        ("active", "Active"),
        ("past_due", "Past Due"),
        ("canceled", "Canceled"),
        ("unpaid", "Unpaid"),
        ("incomplete", "Incomplete"),
        ("incomplete_expired", "Incomplete Expired"),
    ]

    customer = models.OneToOneField(
        Customer,
        on_delete=models.CASCADE,
        related_name="subscription",
        help_text="Customer this subscription belongs to",
    )
    stripe_subscription_id = models.CharField(
        max_length=255,
        unique=True,
        blank=True,
        null=True,
        help_text="Stripe subscription ID (sub_xxxxx)",
    )
    tier = models.CharField(
        max_length=20,
        choices=TIER_CHOICES,
        default="essentials",
        db_index=True,
        help_text="Subscription tier",
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="trialing",
        db_index=True,
        help_text="Subscription status from Stripe",
    )
    current_period_start = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Start of current billing period",
    )
    current_period_end = models.DateTimeField(
        blank=True,
        null=True,
        db_index=True,
        help_text="End of current billing period",
    )
    trial_end = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Trial period end date",
    )
    cancel_at_period_end = models.BooleanField(
        default=False,
        help_text="Whether subscription will cancel at period end",
    )
    canceled_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When subscription was canceled",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CustomerScopedManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "upstream_subscription"
        indexes = [
            models.Index(
                fields=["status", "current_period_end"],
                name="subscription_status_period_idx",
            ),
            models.Index(
                fields=["tier", "status"],
                name="subscription_tier_status_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(tier__in=["essentials", "professional", "enterprise"]),
                name="subscription_tier_valid",
            ),
        ]

    def __str__(self):
        return f"{self.customer.name} - {self.get_tier_display()} ({self.status})"

    @property
    def monthly_price(self):
        """Get the monthly price for this subscription tier."""
        return self.TIER_PRICING.get(self.tier, 0)

    @property
    def is_active(self):
        """Check if subscription is in an active billing state."""
        return self.status in ("trialing", "active")

    @property
    def is_trialing(self):
        """Check if subscription is in trial period."""
        return self.status == "trialing"

    @property
    def needs_payment(self):
        """Check if subscription requires payment attention."""
        return self.status in ("past_due", "unpaid", "incomplete")


class UsageRecord(models.Model):
    """
    Tracks claim processing volume for usage-based billing.

    Records monthly usage per customer for potential overage charges
    or usage-based pricing tiers.
    """

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="usage_records",
        help_text="Customer this usage belongs to",
    )
    period_start = models.DateField(
        db_index=True,
        help_text="Start of usage period (first day of month)",
    )
    period_end = models.DateField(
        db_index=True,
        help_text="End of usage period (last day of month)",
    )
    claims_processed = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Number of claims ingested/processed",
    )
    claims_scored = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Number of claims scored by AI",
    )
    api_calls = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Number of API calls made",
    )
    storage_bytes = models.BigIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Storage used in bytes",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CustomerScopedManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "upstream_usage_record"
        unique_together = [["customer", "period_start"]]
        indexes = [
            models.Index(
                fields=["customer", "period_start"],
                name="usage_customer_period_idx",
            ),
        ]
        ordering = ["-period_start"]

    def __str__(self):
        return f"{self.customer.name} - {self.period_start} to {self.period_end}"

    @property
    def total_claims(self):
        """Total claims (processed + scored)."""
        return self.claims_processed + self.claims_scored
