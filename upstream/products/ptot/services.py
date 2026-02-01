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

from django.db.models import Sum, F
from django.utils import timezone

from upstream.alerts.models import AlertEvent, AlertRule
from upstream.products.ptot.constants import (
    calculate_units_from_minutes,
    is_time_based_cpt,
    get_time_based_cpts,
    CPT_CODES_REQUIRING_GCODES,
    PROGRESS_REPORT_VISIT_INTERVAL,
    GCODE_ALERT_THRESHOLDS,
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
        total_minutes = getattr(claim, "total_minutes", None) or getattr(
            claim, "treatment_time", None
        )

        if total_minutes is None:
            return EightMinuteRuleResult(
                is_valid=False,
                cpt_code=cpt_code,
                message="Claim missing treatment time/total minutes",
            )

        total_minutes = int(total_minutes)

        # Get billed units from claim
        billed_units = getattr(claim, "procedure_count", None) or getattr(
            claim, "units", None
        )

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
            alert_rule = self._get_or_create_alert_rule(claim.customer, "ptot_8_minute")

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
                    alert = self.create_8_minute_alert(claim, validation, alert_rule)
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


# =============================================================================
# G-CODE VALIDATION SERVICE
# =============================================================================


@dataclass
class GCodeValidationResult:
    """Result of G-code validation for a claim."""

    is_valid: bool
    requires_gcodes: bool = False
    gcodes_present: bool = False
    missing_gcodes: list = None
    severity: str = "none"
    message: str = ""
    reporting_type: str = ""  # EVALUATION, PROGRESS, DISCHARGE
    visit_number: int = 0

    def __post_init__(self):
        if self.missing_gcodes is None:
            self.missing_gcodes = []


@dataclass
class ProgressReportDueResult:
    """Result of checking if progress report is due."""

    is_due: bool
    patient_id: str = ""
    visits_since_last_report: int = 0
    visits_until_due: int = 0
    last_report_date: datetime = None
    severity: str = "none"
    message: str = ""


class PTOTGCodeService:
    """
    Service for validating G-code functional limitation reporting.

    Medicare requires G-codes for functional limitations at:
    - Initial evaluation (EVALUATION)
    - Every 10th visit (PROGRESS)
    - Discharge (DISCHARGE)

    G-codes track 7 functional limitation categories:
    - Mobility
    - Changing/Maintaining Position
    - Carrying/Moving Objects
    - Self Care
    - Other PT/OT Primary
    - Other SLP Primary
    - Swallowing
    """

    def __init__(self):
        """Initialize the G-code validation service."""
        self._alert_rule_cache = {}

    def validate_gcode_reporting(self, claim) -> GCodeValidationResult:
        """
        Validate if a claim has required G-codes for Medicare compliance.

        G-codes are required when:
        - CPT code is an evaluation (97161-97168, 92521-92524)
        - It's a 10th visit (progress report due)
        - Claim indicates discharge

        Args:
            claim: ClaimRecord with cpt, modifiers, and optionally gcodes field

        Returns:
            GCodeValidationResult with validation details
        """
        # Get CPT code from claim
        cpt_code = getattr(claim, "cpt", None)
        if not cpt_code:
            return GCodeValidationResult(
                is_valid=True,
                requires_gcodes=False,
                message="No CPT code on claim",
            )

        # Check if this is an evaluation CPT that requires G-codes
        is_evaluation = cpt_code in CPT_CODES_REQUIRING_GCODES

        # Check for discharge indicator
        is_discharge = self._check_is_discharge(claim)

        # Check for progress report visit (10th visit)
        visit_number = getattr(claim, "visit_number", 0) or 0
        is_progress_report = (
            visit_number > 0 and visit_number % PROGRESS_REPORT_VISIT_INTERVAL == 0
        )

        # Determine reporting type
        if is_evaluation:
            reporting_type = "EVALUATION"
        elif is_discharge:
            reporting_type = "DISCHARGE"
        elif is_progress_report:
            reporting_type = "PROGRESS"
        else:
            # G-codes not required for this claim
            return GCodeValidationResult(
                is_valid=True,
                requires_gcodes=False,
                visit_number=visit_number,
                message=f"G-codes not required for CPT {cpt_code}",
            )

        # G-codes are required - check if present
        gcodes_on_claim = self._extract_gcodes(claim)
        gcodes_present = len(gcodes_on_claim) > 0

        # Validate G-code completeness
        missing = self._check_gcode_completeness(gcodes_on_claim, reporting_type)

        if not missing:
            return GCodeValidationResult(
                is_valid=True,
                requires_gcodes=True,
                gcodes_present=True,
                reporting_type=reporting_type,
                visit_number=visit_number,
                message=f"G-codes complete for {reporting_type}",
            )

        # Missing G-codes - determine severity
        severity = (
            "critical" if reporting_type in ("EVALUATION", "DISCHARGE") else "high"
        )

        return GCodeValidationResult(
            is_valid=False,
            requires_gcodes=True,
            gcodes_present=gcodes_present,
            missing_gcodes=missing,
            severity=severity,
            reporting_type=reporting_type,
            visit_number=visit_number,
            message=f"Missing G-codes for {reporting_type}: {', '.join(missing)}",
        )

    def check_progress_report_due(
        self, patient_id: str, customer
    ) -> ProgressReportDueResult:
        """
        Check if a patient's 10th visit progress report is due.

        Args:
            patient_id: Patient identifier
            customer: Customer for scoping

        Returns:
            ProgressReportDueResult with due status
        """
        # Import here to avoid circular imports
        from upstream.products.ptot.models import PTOTFunctionalLimitation

        # Get active functional limitations for this patient
        limitations = PTOTFunctionalLimitation.objects.filter(
            customer=customer,
            patient_id=patient_id,
            status="ACTIVE",
        ).order_by("-last_reported_date")

        if not limitations.exists():
            return ProgressReportDueResult(
                is_due=False,
                patient_id=patient_id,
                message="No active functional limitations tracked",
            )

        # Get the most recent limitation record
        limitation = limitations.first()
        visits_since = limitation.visit_count_since_report

        # Calculate visits until due
        visits_until = PROGRESS_REPORT_VISIT_INTERVAL - visits_since
        warning_threshold = GCODE_ALERT_THRESHOLDS["progress_report_warning_visits"]

        # Determine status
        if visits_since >= PROGRESS_REPORT_VISIT_INTERVAL:
            is_due = True
            severity = "critical"
            message = (
                f"Progress report OVERDUE: {visits_since} visits since last report"
            )
        elif visits_since >= warning_threshold:
            is_due = False
            severity = "warning"
            message = f"Progress report due in {visits_until} visits"
        else:
            is_due = False
            severity = "none"
            message = f"Next progress report in {visits_until} visits"

        return ProgressReportDueResult(
            is_due=is_due,
            patient_id=patient_id,
            visits_since_last_report=visits_since,
            visits_until_due=max(0, visits_until),
            last_report_date=limitation.last_reported_date,
            severity=severity,
            message=message,
        )

    def increment_visit_count(self, patient_id: str, customer) -> int:
        """
        Increment visit count for patient's functional limitations.

        Args:
            patient_id: Patient identifier
            customer: Customer for scoping

        Returns:
            New visit count
        """
        from upstream.products.ptot.models import PTOTFunctionalLimitation

        updated = PTOTFunctionalLimitation.objects.filter(
            customer=customer,
            patient_id=patient_id,
            status="ACTIVE",
        ).update(
            visit_count_since_report=F("visit_count_since_report") + 1,
            updated_at=timezone.now(),
        )

        if updated > 0:
            limitation = PTOTFunctionalLimitation.objects.filter(
                customer=customer,
                patient_id=patient_id,
                status="ACTIVE",
            ).first()
            return limitation.visit_count_since_report if limitation else 0

        return 0

    def record_progress_report(
        self, patient_id: str, customer, report_date=None, gcodes_reported: dict = None
    ):
        """
        Record that a progress report was submitted, resetting visit counter.

        Args:
            patient_id: Patient identifier
            customer: Customer for scoping
            report_date: Date of report (defaults to today)
            gcodes_reported: Dict of G-codes reported
        """
        from upstream.products.ptot.models import (
            PTOTFunctionalLimitation,
            PTOTProgressReport,
        )

        if report_date is None:
            report_date = timezone.now().date()

        # Get active limitations
        limitations = PTOTFunctionalLimitation.objects.filter(
            customer=customer,
            patient_id=patient_id,
            status="ACTIVE",
        )

        for limitation in limitations:
            visit_number = limitation.visit_count_since_report

            # Create progress report record
            PTOTProgressReport.objects.create(
                customer=customer,
                functional_limitation=limitation,
                report_date=report_date,
                visit_number=visit_number,
                reporting_type="PROGRESS",
                gcodes_reported=gcodes_reported or {},
            )

            # Reset visit counter
            limitation.visit_count_since_report = 0
            limitation.last_reported_date = report_date
            limitation.save()

    def create_gcode_missing_alert(
        self,
        claim,
        result: GCodeValidationResult,
        alert_rule: Optional[AlertRule] = None,
    ) -> Optional[AlertEvent]:
        """
        Create an AlertEvent for missing G-codes.

        Args:
            claim: ClaimRecord missing G-codes
            result: Result from validate_gcode_reporting
            alert_rule: AlertRule to use (auto-creates if not provided)

        Returns:
            Created AlertEvent or None if valid
        """
        if result.is_valid:
            return None

        if alert_rule is None:
            alert_rule = self._get_or_create_gcode_alert_rule(claim.customer)

        payload = {
            "type": "ptot_gcode_missing",
            "reporting_type": result.reporting_type,
            "visit_number": result.visit_number,
            "missing_gcodes": result.missing_gcodes,
            "severity": result.severity,
            "message": result.message,
            "claim_id": claim.id if hasattr(claim, "id") else None,
            "patient_id": getattr(claim, "patient_id", None),
        }

        alert = AlertEvent.objects.create(
            customer=claim.customer,
            alert_rule=alert_rule,
            triggered_at=timezone.now(),
            status="pending",
            payload=payload,
        )

        return alert

    def create_progress_report_alert(
        self,
        customer,
        result: ProgressReportDueResult,
        alert_rule: Optional[AlertRule] = None,
    ) -> Optional[AlertEvent]:
        """
        Create an AlertEvent for progress report due/overdue.

        Args:
            customer: Customer to create alert for
            result: Result from check_progress_report_due
            alert_rule: AlertRule to use (auto-creates if not provided)

        Returns:
            Created AlertEvent or None if not due
        """
        if result.severity == "none":
            return None

        if alert_rule is None:
            alert_rule = self._get_or_create_progress_alert_rule(customer)

        payload = {
            "type": "ptot_progress_report_due",
            "patient_id": result.patient_id,
            "visits_since_last_report": result.visits_since_last_report,
            "visits_until_due": result.visits_until_due,
            "last_report_date": (
                result.last_report_date.isoformat() if result.last_report_date else None
            ),
            "is_overdue": result.is_due,
            "severity": result.severity,
            "message": result.message,
        }

        alert = AlertEvent.objects.create(
            customer=customer,
            alert_rule=alert_rule,
            triggered_at=timezone.now(),
            status="pending",
            payload=payload,
        )

        return alert

    def _check_is_discharge(self, claim) -> bool:
        """Check if claim indicates discharge."""
        # Check for discharge modifier or indicator
        modifiers = getattr(claim, "modifiers", "") or ""
        if "DC" in modifiers.upper():
            return True

        # Check for explicit discharge flag
        if getattr(claim, "is_discharge", False):
            return True

        # Check for discharge in claim type or status
        claim_type = getattr(claim, "claim_type", "") or ""
        if "discharge" in claim_type.lower():
            return True

        return False

    def _extract_gcodes(self, claim) -> list:
        """Extract G-codes from claim."""
        gcodes = []

        # Check gcodes field
        if hasattr(claim, "gcodes") and claim.gcodes:
            if isinstance(claim.gcodes, list):
                gcodes.extend(claim.gcodes)
            elif isinstance(claim.gcodes, str):
                # Parse comma-separated G-codes
                gcodes.extend([g.strip() for g in claim.gcodes.split(",") if g.strip()])

        # Check modifiers for G-codes (G8978-G8998 range)
        modifiers = getattr(claim, "modifiers", "") or ""
        for part in modifiers.split(","):
            part = part.strip().upper()
            if part.startswith("G89") and len(part) == 5:
                gcodes.append(part)

        # Check additional_codes field
        if hasattr(claim, "additional_codes") and claim.additional_codes:
            codes = claim.additional_codes
            if isinstance(codes, list):
                for code in codes:
                    if isinstance(code, str) and code.upper().startswith("G89"):
                        gcodes.append(code.upper())

        return list(set(gcodes))  # Remove duplicates

    def _check_gcode_completeness(
        self, gcodes_present: list, reporting_type: str
    ) -> list:
        """
        Check if G-code set is complete for reporting type.

        For Medicare compliance, need:
        - Current status G-code (G8978, G8981, G8984, etc.)
        - Goal G-code (G8979, G8982, G8985, etc.)
        - At discharge: Discharge G-code (G8980, G8983, G8986, etc.)

        G-codes are organized by functional limitation category, with each category
        having 3 sequential codes: current, goal, discharge.
        - Mobility: G8978, G8979, G8980
        - Changing Position: G8981, G8982, G8983
        - etc.

        To determine type: (gcode_num - 8978) % 3
        - 0 = current
        - 1 = goal
        - 2 = discharge

        Args:
            gcodes_present: List of G-codes on claim
            reporting_type: EVALUATION, PROGRESS, or DISCHARGE

        Returns:
            List of missing G-code types
        """
        if not gcodes_present:
            if reporting_type == "DISCHARGE":
                return ["current", "goal", "discharge"]
            return ["current", "goal"]

        # Classify each G-code by type
        has_current = False
        has_goal = False
        has_discharge = False

        for gcode in gcodes_present:
            gcode = gcode.upper()
            if not gcode.startswith("G89"):
                continue

            try:
                gcode_num = int(gcode[1:])  # Remove 'G' and parse number
                if gcode_num < 8978 or gcode_num > 8998:
                    continue

                # Type based on position: 0=current, 1=goal, 2=discharge
                gcode_type = (gcode_num - 8978) % 3

                if gcode_type == 0:
                    has_current = True
                elif gcode_type == 1:
                    has_goal = True
                elif gcode_type == 2:
                    has_discharge = True

            except ValueError:
                continue

        missing = []
        if not has_current:
            missing.append("current")
        if not has_goal:
            missing.append("goal")

        # Check for discharge G-code (only at discharge)
        if reporting_type == "DISCHARGE" and not has_discharge:
            missing.append("discharge")

        return missing

    def _get_or_create_gcode_alert_rule(self, customer) -> AlertRule:
        """Get or create alert rule for G-code missing alerts."""
        cache_key = f"{customer.id}_ptot_gcode"
        if cache_key in self._alert_rule_cache:
            return self._alert_rule_cache[cache_key]

        rule, _ = AlertRule.objects.get_or_create(
            customer=customer,
            name="PT/OT Missing G-Codes",
            defaults={
                "description": "Alert when required G-codes missing from claim",
                "metric": "gcode_completeness",
                "threshold_type": "eq",
                "threshold_value": 0.0,
                "enabled": True,
                "severity": "critical",
                "scope": {"service_type": "PT/OT", "alert_type": "gcode_missing"},
            },
        )

        self._alert_rule_cache[cache_key] = rule
        return rule

    def _get_or_create_progress_alert_rule(self, customer) -> AlertRule:
        """Get or create alert rule for progress report alerts."""
        cache_key = f"{customer.id}_ptot_progress"
        if cache_key in self._alert_rule_cache:
            return self._alert_rule_cache[cache_key]

        rule, _ = AlertRule.objects.get_or_create(
            customer=customer,
            name="PT/OT Progress Report Due",
            defaults={
                "description": "Alert when 10th visit progress report approaching",
                "metric": "visits_since_report",
                "threshold_type": "gte",
                "threshold_value": 8.0,
                "enabled": True,
                "severity": "warning",
                "scope": {"service_type": "PT/OT", "alert_type": "progress_report"},
            },
        )

        self._alert_rule_cache[cache_key] = rule
        return rule
