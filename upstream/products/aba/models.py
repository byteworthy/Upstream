"""
ABA Authorization Tracking Models.

Models for tracking ABA authorization unit consumption
and projecting authorization exhaustion dates.
"""

from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone

from upstream.core.models import BaseModel
from upstream.models import Authorization


class ABAAuthorizationTracker(BaseModel):
    """
    Tracks ABA authorization unit consumption and exhaustion projections.

    Monitors units used vs units authorized and calculates projected
    exhaustion dates based on historical usage patterns.
    """

    authorization = models.OneToOneField(
        Authorization,
        on_delete=models.CASCADE,
        related_name="aba_tracker",
        help_text="Associated ABA authorization",
    )
    units_authorized = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Total units authorized for this period",
    )
    units_used = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Units consumed so far",
    )
    weekly_usage_rate = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Average weekly unit consumption rate",
    )
    projected_exhaustion_date = models.DateField(
        null=True,
        blank=True,
        help_text="Projected date when units will be exhausted",
    )
    last_usage_update = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When units_used was last updated",
    )
    last_alert_date = models.DateField(
        null=True,
        blank=True,
        help_text="Last date an exhaustion alert was sent",
    )
    last_alert_type = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text="Type of last alert sent (e.g., '90_percent', 'exhausted')",
    )

    class Meta:
        db_table = "upstream_aba_authorization_tracker"
        verbose_name = "ABA Authorization Tracker"
        verbose_name_plural = "ABA Authorization Trackers"
        indexes = [
            models.Index(
                fields=["projected_exhaustion_date"],
                name="aba_tracker_exhaust_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(units_used__lte=models.F("units_authorized") * 2),
                name="aba_tracker_units_reasonable",
            ),
            models.CheckConstraint(
                check=models.Q(units_authorized__gte=1),
                name="aba_tracker_units_auth_positive",
            ),
        ]

    def __str__(self):
        return f"ABA Tracker: {self.authorization.auth_number}"

    @property
    def units_remaining(self) -> int:
        """Calculate remaining units."""
        return max(0, self.units_authorized - self.units_used)

    @property
    def utilization_percentage(self) -> Decimal:
        """Calculate utilization as a percentage."""
        if self.units_authorized == 0:
            return Decimal("0")
        return Decimal(self.units_used) / Decimal(self.units_authorized) * 100

    def update_usage(self, units: int, update_rate: bool = True):
        """
        Update units used and optionally recalculate weekly rate.

        Args:
            units: Number of units to add to usage
            update_rate: Whether to recalculate weekly usage rate
        """
        self.units_used += units
        self.last_usage_update = timezone.now()

        if update_rate:
            self._recalculate_weekly_rate()
            self._project_exhaustion()

        self.save()

    def _recalculate_weekly_rate(self):
        """Recalculate weekly usage rate based on historical data."""
        if not self.authorization.auth_start_date:
            return

        start = self.authorization.auth_start_date
        today = timezone.now().date()
        days_elapsed = (today - start).days

        if days_elapsed > 0:
            daily_rate = Decimal(self.units_used) / Decimal(days_elapsed)
            self.weekly_usage_rate = daily_rate * 7

    def _project_exhaustion(self):
        """Project exhaustion date based on weekly usage rate."""
        if self.weekly_usage_rate <= 0:
            self.projected_exhaustion_date = None
            return

        remaining = self.units_remaining
        if remaining <= 0:
            self.projected_exhaustion_date = timezone.now().date()
            return

        daily_rate = self.weekly_usage_rate / 7
        if daily_rate > 0:
            days_remaining = int(Decimal(remaining) / daily_rate)
            self.projected_exhaustion_date = (
                timezone.now().date() + timezone.timedelta(days=days_remaining)
            )
