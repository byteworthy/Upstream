"""
Home Health PDGM Validation Service.

Validates home health claims against Patient-Driven Grouping Model (PDGM)
requirements, including F2F timing and NOA deadlines.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from django.utils import timezone

from upstream.alerts.models import AlertEvent, AlertRule
from upstream.products.homehealth.constants import (
    lookup_pdgm_group,
    is_valid_clinical_group,
    is_valid_functional_level,
    is_valid_comorbidity_level,
    F2F_PRIOR_DAYS,
    F2F_POST_DAYS,
    NOA_DEADLINE_DAYS,
)


@dataclass
class PDGMValidationResult:
    """Result of PDGM group validation for a claim."""

    is_valid: bool
    expected_group: Optional[dict] = None
    billed_group: Optional[dict] = None
    timing: str = ""
    clinical_group: str = ""
    functional_level: str = ""
    comorbidity: str = ""
    severity: str = "none"
    message: str = ""
    missing_fields: list = None

    def __post_init__(self):
        if self.missing_fields is None:
            self.missing_fields = []


@dataclass
class F2FValidationResult:
    """Result of Face-to-Face timing validation."""

    is_valid: bool
    f2f_date: Optional[date] = None
    soc_date: Optional[date] = None
    days_from_soc: Optional[int] = None
    severity: str = "none"
    message: str = ""


@dataclass
class NOACheckResult:
    """Result of NOA deadline check."""

    has_noa: bool
    noa_submitted_date: Optional[date] = None
    soc_date: Optional[date] = None
    deadline_date: Optional[date] = None
    days_until_deadline: Optional[int] = None
    is_overdue: bool = False
    severity: str = "none"
    message: str = ""


class HomeHealthService:
    """
    Service for validating home health claims against PDGM requirements.

    Handles:
    - PDGM group validation (timing, clinical, functional, comorbidity)
    - Face-to-Face (F2F) timing requirements
    - Notice of Admission (NOA) deadline tracking
    - Alert creation for compliance violations
    """

    def __init__(self):
        """Initialize the home health validation service."""
        self._alert_rule_cache = {}

    def validate_pdgm_grouping(self, claim) -> PDGMValidationResult:
        """
        Validate claim against expected PDGM grouping.

        Extracts timing, clinical group, functional level, and comorbidity
        from claim's specialty_metadata and compares against billed group.

        Args:
            claim: ClaimRecord with specialty_metadata containing PDGM fields

        Returns:
            PDGMValidationResult with validation details
        """
        # Get specialty metadata
        metadata = getattr(claim, "specialty_metadata", None) or {}

        # Extract PDGM components
        timing = metadata.get("timing", "").upper()
        clinical_group = metadata.get("clinical_group", "").upper()
        functional_level = metadata.get("functional_level", "").upper()
        comorbidity = metadata.get("comorbidity", "").upper()

        # Check for missing required fields
        missing_fields = []
        if not timing:
            missing_fields.append("timing")
        if not clinical_group:
            missing_fields.append("clinical_group")
        if not functional_level:
            missing_fields.append("functional_level")
        if not comorbidity:
            missing_fields.append("comorbidity")

        if missing_fields:
            severity = "high" if len(missing_fields) >= 2 else "medium"
            return PDGMValidationResult(
                is_valid=False,
                timing=timing,
                clinical_group=clinical_group,
                functional_level=functional_level,
                comorbidity=comorbidity,
                missing_fields=missing_fields,
                severity=severity,
                message=f"Missing PDGM data: {', '.join(missing_fields)}",
            )

        # Validate individual field values
        validation_errors = []

        if timing not in ("EARLY", "LATE"):
            validation_errors.append(f"Invalid timing: {timing}")

        if not is_valid_clinical_group(clinical_group):
            validation_errors.append(f"Invalid clinical group: {clinical_group}")

        if not is_valid_functional_level(functional_level):
            validation_errors.append(f"Invalid functional level: {functional_level}")

        if not is_valid_comorbidity_level(comorbidity):
            validation_errors.append(f"Invalid comorbidity: {comorbidity}")

        if validation_errors:
            return PDGMValidationResult(
                is_valid=False,
                timing=timing,
                clinical_group=clinical_group,
                functional_level=functional_level,
                comorbidity=comorbidity,
                severity="high",
                message="; ".join(validation_errors),
            )

        # Look up expected PDGM group
        expected_group = lookup_pdgm_group(
            timing, clinical_group, functional_level, comorbidity
        )

        # Get billed HIPPS code from claim
        billed_hipps = metadata.get("hipps_code", "")
        billed_group = {"hipps": billed_hipps} if billed_hipps else None

        # If no expected group found, it's a valid but unmapped combination
        if expected_group is None:
            return PDGMValidationResult(
                is_valid=True,
                timing=timing,
                clinical_group=clinical_group,
                functional_level=functional_level,
                comorbidity=comorbidity,
                billed_group=billed_group,
                message=(
                    f"No PDGM mapping for {timing}/{clinical_group}/"
                    f"{functional_level}/{comorbidity}"
                ),
            )

        # Compare billed vs expected
        if not billed_hipps:
            return PDGMValidationResult(
                is_valid=False,
                expected_group=expected_group,
                timing=timing,
                clinical_group=clinical_group,
                functional_level=functional_level,
                comorbidity=comorbidity,
                severity="high",
                message="Missing HIPPS code on claim",
            )

        if billed_hipps != expected_group["hipps"]:
            return PDGMValidationResult(
                is_valid=False,
                expected_group=expected_group,
                billed_group=billed_group,
                timing=timing,
                clinical_group=clinical_group,
                functional_level=functional_level,
                comorbidity=comorbidity,
                severity="high",
                message=(
                    f"PDGM MISMATCH: billed {billed_hipps}, "
                    f"expected {expected_group['hipps']}"
                ),
            )

        return PDGMValidationResult(
            is_valid=True,
            expected_group=expected_group,
            billed_group=billed_group,
            timing=timing,
            clinical_group=clinical_group,
            functional_level=functional_level,
            comorbidity=comorbidity,
            message="PDGM grouping valid",
        )

    def validate_f2f_timing(self, claim) -> F2FValidationResult:
        """
        Validate Face-to-Face encounter timing.

        F2F must occur within 90 days prior to or 30 days after SOC.

        Args:
            claim: ClaimRecord with specialty_metadata containing f2f_date, soc_date

        Returns:
            F2FValidationResult with timing validation details
        """
        metadata = getattr(claim, "specialty_metadata", None) or {}

        # Get F2F and SOC dates
        f2f_date = metadata.get("f2f_date")
        soc_date = metadata.get("soc_date")

        # Parse dates if strings
        if isinstance(f2f_date, str):
            try:
                f2f_date = date.fromisoformat(f2f_date)
            except ValueError:
                f2f_date = None

        if isinstance(soc_date, str):
            try:
                soc_date = date.fromisoformat(soc_date)
            except ValueError:
                soc_date = None

        # Check for missing dates
        if soc_date is None:
            return F2FValidationResult(
                is_valid=False,
                severity="medium",
                message="Missing SOC date for F2F validation",
            )

        if f2f_date is None:
            return F2FValidationResult(
                is_valid=False,
                soc_date=soc_date,
                severity="high",
                message="Missing F2F encounter date",
            )

        # Calculate days from SOC
        days_from_soc = (f2f_date - soc_date).days

        # Check timing requirements
        # F2F can be up to 90 days before SOC or up to 30 days after
        if days_from_soc < -F2F_PRIOR_DAYS:
            return F2FValidationResult(
                is_valid=False,
                f2f_date=f2f_date,
                soc_date=soc_date,
                days_from_soc=days_from_soc,
                severity="critical",
                message=(
                    f"F2F too early: {abs(days_from_soc)} days before SOC "
                    f"(max {F2F_PRIOR_DAYS} days)"
                ),
            )

        if days_from_soc > F2F_POST_DAYS:
            return F2FValidationResult(
                is_valid=False,
                f2f_date=f2f_date,
                soc_date=soc_date,
                days_from_soc=days_from_soc,
                severity="critical",
                message=(
                    f"F2F too late: {days_from_soc} days after SOC "
                    f"(max {F2F_POST_DAYS} days)"
                ),
            )

        return F2FValidationResult(
            is_valid=True,
            f2f_date=f2f_date,
            soc_date=soc_date,
            days_from_soc=days_from_soc,
            message=f"F2F timing valid ({days_from_soc} days from SOC)",
        )

    def check_noa_deadline(self, claim) -> NOACheckResult:
        """
        Check Notice of Admission (NOA) deadline status.

        NOA must be submitted within 5 calendar days of SOC.

        Args:
            claim: ClaimRecord with specialty_metadata containing
                   soc_date and noa_submitted_date

        Returns:
            NOACheckResult with deadline status
        """
        metadata = getattr(claim, "specialty_metadata", None) or {}

        # Get dates
        soc_date = metadata.get("soc_date")
        noa_submitted_date = metadata.get("noa_submitted_date")

        # Parse dates if strings
        if isinstance(soc_date, str):
            try:
                soc_date = date.fromisoformat(soc_date)
            except ValueError:
                soc_date = None

        if isinstance(noa_submitted_date, str):
            try:
                noa_submitted_date = date.fromisoformat(noa_submitted_date)
            except ValueError:
                noa_submitted_date = None

        if soc_date is None:
            return NOACheckResult(
                has_noa=False,
                severity="medium",
                message="Missing SOC date for NOA deadline check",
            )

        # Calculate deadline
        deadline_date = soc_date + timedelta(days=NOA_DEADLINE_DAYS)
        today = date.today()

        if noa_submitted_date:
            # NOA was submitted
            is_overdue = noa_submitted_date > deadline_date
            days_until_deadline = (deadline_date - noa_submitted_date).days

            if is_overdue:
                days_late = (noa_submitted_date - deadline_date).days
                return NOACheckResult(
                    has_noa=True,
                    noa_submitted_date=noa_submitted_date,
                    soc_date=soc_date,
                    deadline_date=deadline_date,
                    days_until_deadline=-days_late,
                    is_overdue=True,
                    severity="warning",
                    message=f"NOA submitted {days_late} days late",
                )

            return NOACheckResult(
                has_noa=True,
                noa_submitted_date=noa_submitted_date,
                soc_date=soc_date,
                deadline_date=deadline_date,
                days_until_deadline=days_until_deadline,
                is_overdue=False,
                message="NOA submitted on time",
            )

        # NOA not yet submitted - check urgency
        days_until_deadline = (deadline_date - today).days
        is_overdue = today > deadline_date

        if is_overdue:
            days_late = (today - deadline_date).days
            return NOACheckResult(
                has_noa=False,
                soc_date=soc_date,
                deadline_date=deadline_date,
                days_until_deadline=-days_late,
                is_overdue=True,
                severity="critical",
                message=f"NOA OVERDUE: {days_late} days past deadline",
            )

        if days_until_deadline <= 2:
            return NOACheckResult(
                has_noa=False,
                soc_date=soc_date,
                deadline_date=deadline_date,
                days_until_deadline=days_until_deadline,
                is_overdue=False,
                severity="high",
                message=f"NOA due in {days_until_deadline} days",
            )

        return NOACheckResult(
            has_noa=False,
            soc_date=soc_date,
            deadline_date=deadline_date,
            days_until_deadline=days_until_deadline,
            is_overdue=False,
            severity="info",
            message=f"NOA deadline in {days_until_deadline} days",
        )

    def create_pdgm_alert(
        self,
        claim,
        result: PDGMValidationResult,
        alert_rule: Optional[AlertRule] = None,
    ) -> Optional[AlertEvent]:
        """
        Create AlertEvent for PDGM validation failure.

        Args:
            claim: ClaimRecord that failed validation
            result: PDGMValidationResult with failure details
            alert_rule: AlertRule to use (auto-creates if not provided)

        Returns:
            Created AlertEvent or None if valid
        """
        if result.is_valid or result.severity == "none":
            return None

        if alert_rule is None:
            alert_rule = self._get_or_create_alert_rule(
                claim.customer, "homehealth_pdgm"
            )

        payload = {
            "type": "homehealth_pdgm_mismatch",
            "timing": result.timing,
            "clinical_group": result.clinical_group,
            "functional_level": result.functional_level,
            "comorbidity": result.comorbidity,
            "expected_group": result.expected_group,
            "billed_group": result.billed_group,
            "missing_fields": result.missing_fields,
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

    def create_f2f_alert(
        self,
        claim,
        result: F2FValidationResult,
        alert_rule: Optional[AlertRule] = None,
    ) -> Optional[AlertEvent]:
        """
        Create AlertEvent for F2F timing violation.

        Args:
            claim: ClaimRecord with F2F timing issue
            result: F2FValidationResult with violation details
            alert_rule: AlertRule to use (auto-creates if not provided)

        Returns:
            Created AlertEvent or None if valid
        """
        if result.is_valid or result.severity == "none":
            return None

        if alert_rule is None:
            alert_rule = self._get_or_create_alert_rule(
                claim.customer, "homehealth_f2f"
            )

        payload = {
            "type": "homehealth_f2f_timing",
            "f2f_date": str(result.f2f_date) if result.f2f_date else None,
            "soc_date": str(result.soc_date) if result.soc_date else None,
            "days_from_soc": result.days_from_soc,
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

    def create_noa_alert(
        self,
        claim,
        result: NOACheckResult,
        alert_rule: Optional[AlertRule] = None,
    ) -> Optional[AlertEvent]:
        """
        Create AlertEvent for NOA deadline issues.

        Args:
            claim: ClaimRecord with NOA deadline issue
            result: NOACheckResult with deadline details
            alert_rule: AlertRule to use (auto-creates if not provided)

        Returns:
            Created AlertEvent or None if not urgent
        """
        # Only create alerts for high/critical severity
        if result.severity not in ("high", "critical"):
            return None

        if alert_rule is None:
            alert_rule = self._get_or_create_alert_rule(
                claim.customer, "homehealth_noa"
            )

        payload = {
            "type": "homehealth_noa_deadline",
            "has_noa": result.has_noa,
            "noa_submitted_date": (
                str(result.noa_submitted_date)
                if result.noa_submitted_date else None
            ),
            "soc_date": str(result.soc_date) if result.soc_date else None,
            "deadline_date": (
                str(result.deadline_date) if result.deadline_date else None
            ),
            "days_until_deadline": result.days_until_deadline,
            "is_overdue": result.is_overdue,
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
        """Get or create alert rule for home health alerts."""
        cache_key = f"{customer.id}_{rule_type}"
        if cache_key in self._alert_rule_cache:
            return self._alert_rule_cache[cache_key]

        rule_configs = {
            "homehealth_pdgm": {
                "name": "Home Health PDGM Mismatch",
                "description": "Alert when PDGM grouping doesn't match claim",
                "metric": "pdgm_match",
            },
            "homehealth_f2f": {
                "name": "Home Health F2F Timing",
                "description": "Alert when F2F encounter outside requirements",
                "metric": "f2f_timing",
            },
            "homehealth_noa": {
                "name": "Home Health NOA Deadline",
                "description": "Alert when NOA deadline approaching or missed",
                "metric": "noa_deadline",
            },
        }

        config = rule_configs.get(rule_type, rule_configs["homehealth_pdgm"])

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
                "scope": {"service_type": "HOME_HEALTH"},
            },
        )

        self._alert_rule_cache[cache_key] = rule
        return rule

    def analyze_claims(
        self,
        claims,
        create_alerts: bool = True,
        check_f2f: bool = True,
        check_noa: bool = True,
    ) -> dict:
        """
        Analyze multiple home health claims for PDGM compliance.

        Args:
            claims: Iterable of ClaimRecord instances
            create_alerts: Whether to create AlertEvents
            check_f2f: Whether to validate F2F timing
            check_noa: Whether to check NOA deadlines

        Returns:
            dict with analysis summary
        """
        results = {
            "total_claims": 0,
            "pdgm_valid": 0,
            "pdgm_invalid": 0,
            "pdgm_missing_data": 0,
            "f2f_valid": 0,
            "f2f_invalid": 0,
            "noa_on_time": 0,
            "noa_overdue": 0,
            "noa_pending": 0,
            "alerts_created": 0,
        }

        pdgm_rule = None
        f2f_rule = None
        noa_rule = None

        for claim in claims:
            results["total_claims"] += 1

            # Validate PDGM grouping
            pdgm_result = self.validate_pdgm_grouping(claim)

            if pdgm_result.is_valid:
                results["pdgm_valid"] += 1
            elif pdgm_result.missing_fields:
                results["pdgm_missing_data"] += 1
            else:
                results["pdgm_invalid"] += 1

            if create_alerts and not pdgm_result.is_valid:
                if pdgm_rule is None:
                    pdgm_rule = self._get_or_create_alert_rule(
                        claim.customer, "homehealth_pdgm"
                    )
                alert = self.create_pdgm_alert(claim, pdgm_result, pdgm_rule)
                if alert:
                    results["alerts_created"] += 1

            # Validate F2F timing
            if check_f2f:
                f2f_result = self.validate_f2f_timing(claim)

                if f2f_result.is_valid:
                    results["f2f_valid"] += 1
                else:
                    results["f2f_invalid"] += 1

                if create_alerts and not f2f_result.is_valid:
                    if f2f_rule is None:
                        f2f_rule = self._get_or_create_alert_rule(
                            claim.customer, "homehealth_f2f"
                        )
                    alert = self.create_f2f_alert(claim, f2f_result, f2f_rule)
                    if alert:
                        results["alerts_created"] += 1

            # Check NOA deadline
            if check_noa:
                noa_result = self.check_noa_deadline(claim)

                if noa_result.has_noa and not noa_result.is_overdue:
                    results["noa_on_time"] += 1
                elif noa_result.is_overdue:
                    results["noa_overdue"] += 1
                else:
                    results["noa_pending"] += 1

                if create_alerts:
                    if noa_rule is None:
                        noa_rule = self._get_or_create_alert_rule(
                            claim.customer, "homehealth_noa"
                        )
                    alert = self.create_noa_alert(claim, noa_result, noa_rule)
                    if alert:
                        results["alerts_created"] += 1

        return results
