"""
PT/OT 8-Minute Rule Validation Service.

Validates PT/OT claims against the 8-minute rule for time-based billing
and monitors KX modifier threshold compliance.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional
import pytz

from django.db.models import Sum
from django.utils import timezone

from upstream.alerts.models import AlertEvent, AlertRule
from upstream.products.ptot.constants import (
    calculate_units_from_minutes,
    is_time_based_cpt,
    get_time_based_cpts,
)


# 2025 therapy cap threshold (combined PT/OT/SLP)
# Updated annually by CMS
THERAPY_CAP_THRESHOLD = Decimal("2410.00")

# KX modifier indicates exception threshold has been exceeded
KX_MODIFIER = "KX"


@dataclass
class EightMinuteRuleResult:
    """Result of 8-minute rule validation for a claim."""

    is_valid: bool
    total_minutes: int = 0
    expected_units: int = 0
    billed_units: int = 0
    unit_difference: int = 0
    severity: str = "none"
    message: str = ""
    cpt_code: str = ""


@dataclass
class KXThresholdResult:
    """Result of KX threshold check for a patient."""

    requires_kx: bool
    ytd_charges: Decimal = Decimal("0")
    threshold: Decimal = THERAPY_CAP_THRESHOLD
    amount_over: Decimal = Decimal("0")
    has_kx_modifier: bool = False
    is_compliant: bool = True
    severity: str = "none"
    message: str = ""


class PTOTService:
    """
    Service for validating PT/OT claims against billing rules.

    Handles:
    - 8-minute rule validation for time-based CPT codes
    - KX modifier threshold monitoring
    - Alert creation for billing violations
    """

    def __init__(self, therapy_cap: Decimal = THERAPY_CAP_THRESHOLD):
        """
        Initialize the PT/OT validation service.

        Args:
            therapy_cap: Annual therapy cap threshold (default $2,410 for 2025)
        """
        self.therapy_cap = therapy_cap
        self._alert_rule_cache = {}

    def validate_8_minute_rule(self, claim) -> EightMinuteRuleResult:
        """
        Validate a claim against the 8-minute rule.

        The 8-minute rule requires:
        - Less than 8 minutes: 0 units
        - 8-22 minutes: 1 unit
        - 23-37 minutes: 2 units
        - Each additional 15 minutes: +1 unit

        Args:
            claim: ClaimRecord with cpt, total_minutes/treatment_time,
                   and procedure_count/units fields

        Returns:
            EightMinuteRuleResult with validation details
        """
        # Validate claim has required fields
        if not hasattr(claim, "cpt") or not claim.cpt:
            return EightMinuteRuleResult(
                is_valid=False,
                message="Claim missing CPT code",
            )

        cpt_code = claim.cpt

        # Check if this is a time-based CPT
        if not is_time_based_cpt(cpt_code):
            return EightMinuteRuleResult(
                is_valid=True,
                cpt_code=cpt_code,
                message=f"CPT {cpt_code} is not time-based",
            )

        # Get total minutes from claim
        total_minutes = getattr(
            claim, "total_minutes", None
        ) or getattr(claim, "treatment_time", None)

        if total_minutes is None:
            return EightMinuteRuleResult(
                is_valid=False,
                cpt_code=cpt_code,
                message="Claim missing treatment time/total minutes",
            )

        total_minutes = int(total_minutes)

        # Get billed units from claim
        billed_units = getattr(
            claim, "procedure_count", None
        ) or getattr(claim, "units", None)

        if billed_units is None:
            return EightMinuteRuleResult(
                is_valid=False,
                cpt_code=cpt_code,
                total_minutes=total_minutes,
                message="Claim missing billed units",
            )

        billed_units = int(billed_units)

        # Calculate expected units using 8-minute rule
        expected_units = calculate_units_from_minutes(total_minutes)

        # Compare billed vs expected
        unit_difference = billed_units - expected_units

        if unit_difference == 0:
            return EightMinuteRuleResult(
                is_valid=True,
                total_minutes=total_minutes,
                expected_units=expected_units,
                billed_units=billed_units,
                unit_difference=0,
                cpt_code=cpt_code,
                message=f"Valid: {billed_units} units for {total_minutes} min",
            )

        # Determine severity based on unit difference
        if unit_difference > 0:
            # Overbilling
            if unit_difference >= 2:
                severity = "critical"
            else:
                severity = "warning"
            message = (
                f"OVERBILLED: {billed_units} units for {total_minutes} min, "
                f"expected {expected_units}"
            )
        else:
            # Underbilling (less severe, may be intentional)
            severity = "info"
            message = (
                f"UNDERBILLED: {billed_units} units for {total_minutes} min, "
                f"expected {expected_units}"
            )

        return EightMinuteRuleResult(
            is_valid=False,
            total_minutes=total_minutes,
            expected_units=expected_units,
            billed_units=billed_units,
            unit_difference=unit_difference,
            severity=severity,
            cpt_code=cpt_code,
            message=message,
        )

    def check_kx_threshold(
        self,
        patient,
        claim=None,
        year: Optional[int] = None,
    ) -> KXThresholdResult:
        """
        Check if patient has exceeded therapy cap and needs KX modifier.

        Args:
            patient: Patient instance with related claims
            claim: Optional current claim to check for KX modifier
            year: Calendar year to check (defaults to current year)

        Returns:
            KXThresholdResult with threshold status
        """
        if year is None:
            year = timezone.now().year

        # Calculate YTD charges for PT/OT/SLP services
        # Filter claims for this patient and year
        utc = pytz.UTC
        start_of_year = datetime(year, 1, 1, tzinfo=utc)
        end_of_year = datetime(year, 12, 31, 23, 59, 59, tzinfo=utc)

        # Get all time-based CPTs
        time_based_cpts = list(get_time_based_cpts().keys())

        # Sum charges from patient's claims
        ytd_charges = Decimal("0")
        if hasattr(patient, "claims"):
            result = patient.claims.filter(
                service_date__gte=start_of_year,
                service_date__lte=end_of_year,
                cpt__in=time_based_cpts,
            ).aggregate(total=Sum("charge_amount"))
            ytd_charges = result.get("total") or Decimal("0")

        # Check if threshold exceeded
        requires_kx = ytd_charges > self.therapy_cap
        amount_over = max(ytd_charges - self.therapy_cap, Decimal("0"))

        # Check if current claim has KX modifier
        has_kx_modifier = False
        if claim is not None:
            modifiers = getattr(claim, "modifiers", "") or ""
            has_kx_modifier = KX_MODIFIER in modifiers.upper()

        # Determine compliance
        is_compliant = True
        severity = "none"
        message = f"YTD charges: ${ytd_charges:.2f}"

        if requires_kx:
            if has_kx_modifier:
                message = (
                    f"Threshold exceeded (${ytd_charges:.2f}), "
                    f"KX modifier present - compliant"
                )
            else:
                is_compliant = False
                severity = "critical"
                message = (
                    f"MISSING KX: YTD ${ytd_charges:.2f} exceeds "
                    f"${self.therapy_cap:.2f} threshold, "
                    f"KX modifier required but not present"
                )
        elif ytd_charges > self.therapy_cap * Decimal("0.90"):
            # Warning when approaching threshold (90%)
            severity = "warning"
            message = (
                f"Approaching threshold: ${ytd_charges:.2f} "
                f"of ${self.therapy_cap:.2f} (90% threshold)"
            )

        return KXThresholdResult(
            requires_kx=requires_kx,
            ytd_charges=ytd_charges,
            threshold=self.therapy_cap,
            amount_over=amount_over,
            has_kx_modifier=has_kx_modifier,
            is_compliant=is_compliant,
            severity=severity,
            message=message,
        )

    def create_8_minute_alert(
        self,
        claim,
        result: EightMinuteRuleResult,
        alert_rule: Optional[AlertRule] = None,
    ) -> Optional[AlertEvent]:
        """
        Create an AlertEvent for 8-minute rule violation.

        Args:
            claim: ClaimRecord that triggered the violation
            result: Result from validate_8_minute_rule
            alert_rule: AlertRule to use (auto-finds if not provided)

        Returns:
            Created AlertEvent or None if valid
        """
        if result.is_valid or result.severity == "none":
            return None

        if alert_rule is None:
            alert_rule = self._get_or_create_alert_rule(
                claim.customer, "ptot_8_minute"
            )

        payload = {
            "type": "ptot_8_minute_violation",
            "cpt": result.cpt_code,
            "total_minutes": result.total_minutes,
            "expected_units": result.expected_units,
            "billed_units": result.billed_units,
            "unit_difference": result.unit_difference,
            "severity": result.severity,
            "message": result.message,
            "claim_id": claim.id if hasattr(claim, "id") else None,
        }

        alert = AlertEvent.objects.create(
            customer=claim.customer,
            alert_rule=alert_rule,
            triggered_at=timezone.now(),
            status="pending",
            payload=payload,
        )

        return alert

    def create_kx_alert(
        self,
        claim,
        result: KXThresholdResult,
        alert_rule: Optional[AlertRule] = None,
    ) -> Optional[AlertEvent]:
        """
        Create an AlertEvent for missing KX modifier.

        Args:
            claim: ClaimRecord missing KX modifier
            result: Result from check_kx_threshold
            alert_rule: AlertRule to use (auto-finds if not provided)

        Returns:
            Created AlertEvent or None if compliant
        """
        if result.is_compliant:
            return None

        if alert_rule is None:
            alert_rule = self._get_or_create_alert_rule(
                claim.customer, "ptot_kx_threshold"
            )

        payload = {
            "type": "ptot_missing_kx_modifier",
            "ytd_charges": str(result.ytd_charges),
            "threshold": str(result.threshold),
            "amount_over": str(result.amount_over),
            "has_kx_modifier": result.has_kx_modifier,
            "severity": result.severity,
            "message": result.message,
            "claim_id": claim.id if hasattr(claim, "id") else None,
        }

        alert = AlertEvent.objects.create(
            customer=claim.customer,
            alert_rule=alert_rule,
            triggered_at=timezone.now(),
            status="pending",
            payload=payload,
        )

        return alert

    def _get_or_create_alert_rule(self, customer, rule_type: str) -> AlertRule:
        """Get or create alert rule for PT/OT alerts."""
        cache_key = f"{customer.id}_{rule_type}"
        if cache_key in self._alert_rule_cache:
            return self._alert_rule_cache[cache_key]

        rule_configs = {
            "ptot_8_minute": {
                "name": "PT/OT 8-Minute Rule Violation",
                "description": "Alert when billed units violate 8-minute rule",
                "metric": "unit_difference",
            },
            "ptot_kx_threshold": {
                "name": "PT/OT Missing KX Modifier",
                "description": "Alert when therapy cap exceeded without KX",
                "metric": "ytd_charges",
            },
        }

        config = rule_configs.get(rule_type, rule_configs["ptot_8_minute"])

        rule, _ = AlertRule.objects.get_or_create(
            customer=customer,
            name=config["name"],
            defaults={
                "description": config["description"],
                "metric": config["metric"],
                "threshold_type": "gte",
                "threshold_value": 0.0,
                "enabled": True,
                "severity": "warning",
                "scope": {"service_type": "PT/OT"},
            },
        )

        self._alert_rule_cache[cache_key] = rule
        return rule

    def analyze_claims(
        self,
        claims,
        create_alerts: bool = True,
        check_kx: bool = True,
    ) -> dict:
        """
        Analyze multiple PT/OT claims for billing violations.

        Args:
            claims: Iterable of ClaimRecord instances
            create_alerts: Whether to create AlertEvents
            check_kx: Whether to check KX threshold

        Returns:
            dict with analysis summary
        """
        results = {
            "total_claims": 0,
            "valid_claims": 0,
            "overbilled_claims": 0,
            "underbilled_claims": 0,
            "non_time_based": 0,
            "kx_violations": 0,
            "alerts_created": 0,
            "total_unit_difference": 0,
        }

        alert_rule = None
        kx_alert_rule = None
        patient_kx_checked = set()

        for claim in claims:
            results["total_claims"] += 1

            # Validate 8-minute rule
            validation = self.validate_8_minute_rule(claim)

            if "not time-based" in validation.message:
                results["non_time_based"] += 1
                continue

            if validation.is_valid:
                results["valid_claims"] += 1
            else:
                unit_diff = abs(validation.unit_difference)
                results["total_unit_difference"] += unit_diff

                if validation.unit_difference > 0:
                    results["overbilled_claims"] += 1
                else:
                    results["underbilled_claims"] += 1

                should_alert = validation.severity in ("warning", "critical")
                if create_alerts and should_alert:
                    if alert_rule is None:
                        alert_rule = self._get_or_create_alert_rule(
                            claim.customer, "ptot_8_minute"
                        )
                    alert = self.create_8_minute_alert(
                        claim, validation, alert_rule
                    )
                    if alert:
                        results["alerts_created"] += 1

            # Check KX threshold (once per patient)
            if check_kx and hasattr(claim, "patient"):
                pat = claim.patient
                patient_id = pat.id if hasattr(pat, "id") else None
                if patient_id and patient_id not in patient_kx_checked:
                    patient_kx_checked.add(patient_id)
                    kx_result = self.check_kx_threshold(claim.patient, claim)

                    if not kx_result.is_compliant:
                        results["kx_violations"] += 1

                        if create_alerts:
                            if kx_alert_rule is None:
                                kx_alert_rule = self._get_or_create_alert_rule(
                                    claim.customer, "ptot_kx_threshold"
                                )
                            kx_alert = self.create_kx_alert(
                                claim, kx_result, kx_alert_rule
                            )
                            if kx_alert:
                                results["alerts_created"] += 1

        return results
