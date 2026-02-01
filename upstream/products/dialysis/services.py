"""
Dialysis MA Variance Detection Service.

Detects when Medicare Advantage payer payments fall significantly below
traditional Medicare baselines, indicating potential underpayment.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from django.utils import timezone

from upstream.alerts.models import AlertEvent, AlertRule
from upstream.products.dialysis.models import DialysisMABaseline
from upstream.products.dialysis.constants import (
    VARIANCE_THRESHOLD as DEFAULT_VARIANCE_THRESHOLD,
    HIGH_VARIANCE_THRESHOLD,
    ANNUAL_DIALYSIS_TREATMENTS,
)


@dataclass
class VarianceResult:
    """Result of MA variance detection for a claim."""

    has_variance: bool
    ratio: Optional[Decimal] = None
    baseline_amount: Optional[Decimal] = None
    paid_amount: Optional[Decimal] = None
    variance_amount: Optional[Decimal] = None
    projected_annual_loss: Optional[Decimal] = None
    severity: str = "none"
    message: str = ""


class DialysisMAService:
    """
    Service to detect Medicare Advantage payment variance for dialysis claims.

    Compares actual paid amounts against traditional Medicare baselines
    to identify potential underpayment patterns.
    """

    def __init__(
        self,
        variance_threshold: Decimal = DEFAULT_VARIANCE_THRESHOLD,
        high_variance_threshold: Decimal = HIGH_VARIANCE_THRESHOLD,
    ):
        """
        Initialize the service with configurable thresholds.

        Args:
            variance_threshold: Ratio triggering variance (default 0.85)
            high_variance_threshold: Ratio for critical alerts (default 0.70)
        """
        self.variance_threshold = variance_threshold
        self.high_variance_threshold = high_variance_threshold

    def detect_variance(self, claim) -> VarianceResult:
        """
        Detect MA payment variance for a claim.

        Args:
            claim: ClaimRecord instance with cpt and paid_amount fields

        Returns:
            VarianceResult with variance details
        """
        # Validate claim has required fields
        if not hasattr(claim, "cpt") or not claim.cpt:
            return VarianceResult(
                has_variance=False,
                message="Claim missing CPT code",
            )

        if not hasattr(claim, "paid_amount") or claim.paid_amount is None:
            return VarianceResult(
                has_variance=False,
                message="Claim missing paid amount",
            )

        # Look up baseline for this CPT
        try:
            baseline = DialysisMABaseline.objects.get(cpt=claim.cpt)
        except DialysisMABaseline.DoesNotExist:
            return VarianceResult(
                has_variance=False,
                message=f"No baseline found for CPT {claim.cpt}",
            )

        # Calculate variance ratio
        paid_amount = Decimal(str(claim.paid_amount))
        baseline_amount = baseline.average_payment

        if baseline_amount <= 0:
            return VarianceResult(
                has_variance=False,
                message=f"Invalid baseline amount for CPT {claim.cpt}",
            )

        ratio = paid_amount / baseline_amount
        variance_amount = baseline_amount - paid_amount

        # Determine if variance threshold exceeded
        if ratio >= self.variance_threshold:
            return VarianceResult(
                has_variance=False,
                ratio=ratio,
                baseline_amount=baseline_amount,
                paid_amount=paid_amount,
                variance_amount=variance_amount,
                message="Payment within acceptable range",
            )

        # Calculate severity based on ratio
        if ratio < self.high_variance_threshold:
            severity = "critical"
        else:
            severity = "warning"

        # Calculate projected annual loss
        # Standard dialysis: 3x/week = 156 treatments/year
        projected_annual_loss = variance_amount * ANNUAL_DIALYSIS_TREATMENTS

        return VarianceResult(
            has_variance=True,
            ratio=ratio,
            baseline_amount=baseline_amount,
            paid_amount=paid_amount,
            variance_amount=variance_amount,
            projected_annual_loss=projected_annual_loss,
            severity=severity,
            message=(
                f"Payment {ratio:.1%} of Medicare baseline "
                f"(threshold: {self.variance_threshold:.0%})"
            ),
        )

    def create_alert_event(
        self,
        claim,
        variance_result: VarianceResult,
        alert_rule: Optional[AlertRule] = None,
    ) -> Optional[AlertEvent]:
        """
        Create an AlertEvent for a variance detection.

        Args:
            claim: ClaimRecord that triggered the variance
            variance_result: Result from detect_variance
            alert_rule: AlertRule to use (auto-finds if not provided)

        Returns:
            Created AlertEvent or None if no variance
        """
        if not variance_result.has_variance:
            return None

        # Try to find or use provided AlertRule
        if alert_rule is None:
            alert_rule = self._get_or_create_alert_rule(claim.customer)

        # Build payload with variance details
        payload = {
            "type": "dialysis_ma_variance",
            "cpt": claim.cpt,
            "paid_amount": str(variance_result.paid_amount),
            "baseline_amount": str(variance_result.baseline_amount),
            "variance_amount": str(variance_result.variance_amount),
            "ratio": str(variance_result.ratio),
            "projected_annual_loss": str(variance_result.projected_annual_loss),
            "severity": variance_result.severity,
            "message": variance_result.message,
            "claim_id": claim.id if hasattr(claim, "id") else None,
        }

        # Create the AlertEvent
        alert_event = AlertEvent.objects.create(
            customer=claim.customer,
            alert_rule=alert_rule,
            triggered_at=timezone.now(),
            status="pending",
            payload=payload,
        )

        return alert_event

    def _get_or_create_alert_rule(self, customer) -> AlertRule:
        """Get or create default dialysis MA variance alert rule."""
        rule, _ = AlertRule.objects.get_or_create(
            customer=customer,
            name="Dialysis MA Variance Alert",
            defaults={
                "description": "Alert when MA payments fall below baseline",
                "metric": "severity",
                "threshold_type": "gte",
                "threshold_value": 0.0,
                "enabled": True,
                "severity": "warning",
                "scope": {"service_type": "DIALYSIS"},
            },
        )
        return rule

    def analyze_claims(self, claims, create_alerts: bool = True):
        """
        Analyze multiple claims for MA variance.

        Args:
            claims: Iterable of ClaimRecord instances
            create_alerts: Whether to create AlertEvents for variances

        Returns:
            dict with analysis summary
        """
        results = {
            "total_claims": 0,
            "variance_claims": 0,
            "critical_claims": 0,
            "warning_claims": 0,
            "missing_baseline": 0,
            "total_variance_amount": Decimal("0"),
            "total_projected_annual_loss": Decimal("0"),
            "alerts_created": 0,
        }

        alert_rule = None  # Cache the alert rule

        for claim in claims:
            results["total_claims"] += 1

            variance_result = self.detect_variance(claim)

            if "No baseline found" in variance_result.message:
                results["missing_baseline"] += 1
                continue

            if variance_result.has_variance:
                results["variance_claims"] += 1
                results[
                    "total_variance_amount"
                ] += variance_result.variance_amount or Decimal("0")
                results[
                    "total_projected_annual_loss"
                ] += variance_result.projected_annual_loss or Decimal("0")

                if variance_result.severity == "critical":
                    results["critical_claims"] += 1
                elif variance_result.severity == "warning":
                    results["warning_claims"] += 1

                if create_alerts:
                    if alert_rule is None:
                        alert_rule = self._get_or_create_alert_rule(claim.customer)
                    alert = self.create_alert_event(claim, variance_result, alert_rule)
                    if alert:
                        results["alerts_created"] += 1

        return results
