"""
Dialysis MA Variance Detection Service

Detects when Medicare Advantage payer payments are significantly below
traditional Medicare baselines, triggering alerts for potential underpayment.
"""

import logging
from decimal import Decimal
from typing import Dict, Optional, Any
from dataclasses import dataclass

from django.utils import timezone

from .models import DialysisMABaseline
from .constants import (
    is_ma_payer,
    get_severity_for_ratio,
    VARIANCE_THRESHOLD,
    ANNUAL_CLAIM_MULTIPLIER,
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
)

logger = logging.getLogger(__name__)


@dataclass
class VarianceResult:
    """Result of variance detection analysis."""

    has_variance: bool
    ratio: Optional[float] = None
    baseline_amount: Optional[Decimal] = None
    paid_amount: Optional[Decimal] = None
    variance_amount: Optional[Decimal] = None
    severity: Optional[str] = None
    projected_annual_loss: Optional[Decimal] = None
    message: str = ""


class DialysisMAService:
    """
    Service for detecting MA payer payment variance against Medicare baselines.

    This service compares actual MA payer payments to traditional Medicare
    baselines for dialysis CPT codes. When payments fall below the threshold
    (default 85%), alerts are created to flag potential underpayment.
    """

    @staticmethod
    def detect_variance(
        claim_data: Dict[str, Any],
        threshold: float = VARIANCE_THRESHOLD,
    ) -> VarianceResult:
        """
        Detect if an MA payer payment is significantly below Medicare baseline.

        Args:
            claim_data: Dict with claim fields:
                - payer: str - Name of the payer
                - cpt: str - CPT code for the service
                - paid_amount: Decimal - Amount paid by the payer
                - procedure_count: int (optional) - Number of procedures (default 1)
            threshold: float - Minimum acceptable ratio (default 0.85)

        Returns:
            VarianceResult with variance detection details
        """
        payer = claim_data.get("payer", "")
        cpt = claim_data.get("cpt", "")
        paid_amount = claim_data.get("paid_amount")
        procedure_count = claim_data.get("procedure_count", 1)

        # Check if this is an MA payer
        if not is_ma_payer(payer):
            return VarianceResult(
                has_variance=False,
                message="Not an MA payer - variance check not applicable"
            )

        # Validate paid amount
        if paid_amount is None:
            return VarianceResult(
                has_variance=False,
                message="No paid amount available for comparison"
            )

        paid_amount = Decimal(str(paid_amount))
        if paid_amount <= 0:
            return VarianceResult(
                has_variance=False,
                message="Paid amount is zero or negative"
            )

        # Look up baseline
        baseline = DialysisMAService._lookup_baseline(cpt)
        if baseline is None:
            return VarianceResult(
                has_variance=False,
                message=f"No Medicare baseline found for CPT {cpt}"
            )

        # Calculate expected payment (baseline * procedure count)
        expected_payment = baseline.average_payment * procedure_count

        # Calculate ratio
        ratio = float(paid_amount / expected_payment)

        # Check if below threshold
        if ratio >= threshold:
            return VarianceResult(
                has_variance=False,
                ratio=ratio,
                baseline_amount=expected_payment,
                paid_amount=paid_amount,
                message=f"Payment ratio {ratio:.2%} is within acceptable range"
            )

        # Calculate variance details
        variance_amount = expected_payment - paid_amount
        severity = get_severity_for_ratio(ratio)
        projected_annual_loss = variance_amount * ANNUAL_CLAIM_MULTIPLIER

        return VarianceResult(
            has_variance=True,
            ratio=ratio,
            baseline_amount=expected_payment,
            paid_amount=paid_amount,
            variance_amount=variance_amount,
            severity=severity,
            projected_annual_loss=projected_annual_loss,
            message=f"MA payment is {ratio:.2%} of Medicare baseline ({severity} severity)"
        )

    @staticmethod
    def create_variance_alert(
        claim,
        variance_result: VarianceResult,
        customer,
    ) -> Optional[Any]:
        """
        Create an AlertEvent for detected variance.

        Args:
            claim: ClaimRecord instance
            variance_result: VarianceResult from detect_variance
            customer: Customer instance

        Returns:
            AlertEvent instance if created, None otherwise
        """
        if not variance_result.has_variance:
            return None

        from upstream.alerts.models import AlertEvent, AlertRule

        # Find or create a default variance alert rule
        alert_rule, _ = AlertRule.objects.get_or_create(
            customer=customer,
            name="Dialysis MA Variance Detection",
            defaults={
                "description": "Alerts when MA payer payments fall below Medicare baselines",
                "metric": "severity",
                "threshold_type": "gte",
                "threshold_value": 0.0,
                "enabled": True,
                "severity": variance_result.severity.lower() if variance_result.severity else "warning",
            }
        )

        # Build alert payload
        payload = {
            "claim_id": claim.id,
            "payer": claim.payer,
            "cpt": claim.cpt,
            "paid_amount": str(variance_result.paid_amount),
            "baseline_amount": str(variance_result.baseline_amount),
            "variance_amount": str(variance_result.variance_amount),
            "ratio": variance_result.ratio,
            "severity": variance_result.severity,
            "projected_annual_loss": str(variance_result.projected_annual_loss),
            "alert_type": "dialysis_ma_variance",
        }

        # Create the alert event
        alert_event = AlertEvent.objects.create(
            customer=customer,
            alert_rule=alert_rule,
            triggered_at=timezone.now(),
            status="pending",
            payload=payload,
        )

        logger.info(
            f"Created MA variance alert for claim {claim.id}: "
            f"ratio={variance_result.ratio:.2%}, severity={variance_result.severity}"
        )

        return alert_event

    @staticmethod
    def calculate_revenue_impact(
        variance_results: list[VarianceResult],
        period_months: int = 12,
    ) -> Dict[str, Decimal]:
        """
        Calculate aggregate revenue impact from variance results.

        Args:
            variance_results: List of VarianceResult objects
            period_months: Number of months to project (default 12)

        Returns:
            Dict with total_variance, projected_loss, claim_count
        """
        total_variance = Decimal("0.00")
        claims_with_variance = 0

        for result in variance_results:
            if result.has_variance and result.variance_amount:
                total_variance += result.variance_amount
                claims_with_variance += 1

        projected_annual_loss = total_variance * (period_months / 12)

        return {
            "total_variance": total_variance,
            "projected_annual_loss": projected_annual_loss,
            "claims_with_variance": claims_with_variance,
            "average_variance": (
                total_variance / claims_with_variance
                if claims_with_variance > 0
                else Decimal("0.00")
            ),
        }

    @staticmethod
    def _lookup_baseline(cpt: str) -> Optional[DialysisMABaseline]:
        """
        Look up Medicare baseline for a CPT code.

        Args:
            cpt: CPT code to look up

        Returns:
            DialysisMABaseline instance or None if not found
        """
        try:
            return DialysisMABaseline.objects.get(cpt=cpt)
        except DialysisMABaseline.DoesNotExist:
            logger.debug(f"No baseline found for CPT {cpt}")
            return None

    @staticmethod
    def analyze_claim(
        claim,
        create_alert: bool = True,
    ) -> VarianceResult:
        """
        Convenience method to analyze a ClaimRecord for MA variance.

        Args:
            claim: ClaimRecord instance
            create_alert: Whether to create an AlertEvent if variance detected

        Returns:
            VarianceResult with analysis details
        """
        claim_data = {
            "payer": claim.payer,
            "cpt": claim.cpt,
            "paid_amount": claim.paid_amount,
            "procedure_count": claim.procedure_count,
        }

        result = DialysisMAService.detect_variance(claim_data)

        if result.has_variance and create_alert:
            DialysisMAService.create_variance_alert(
                claim=claim,
                variance_result=result,
                customer=claim.customer,
            )

        return result

    @staticmethod
    def get_specialty_risk_factor(claim_data: Dict[str, Any]) -> float:
        """
        Calculate specialty-specific risk factor for scoring integration.

        This method is called by RiskScoringService to incorporate
        dialysis-specific risk factors into the overall ClaimScore.

        Args:
            claim_data: Dict with claim fields

        Returns:
            Risk factor between 0.0 (low risk) and 1.0 (high risk)
        """
        result = DialysisMAService.detect_variance(claim_data)

        if not result.has_variance:
            return 0.0

        # Map severity to risk factor
        severity_risk_map = {
            SEVERITY_CRITICAL: 0.9,
            SEVERITY_HIGH: 0.7,
            None: 0.4,  # MEDIUM
        }

        return severity_risk_map.get(result.severity, 0.4)
