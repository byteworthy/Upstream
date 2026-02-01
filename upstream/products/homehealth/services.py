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
                str(result.noa_submitted_date) if result.noa_submitted_date else None
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

    # =========================================================================
    # Model-based methods for HomeHealthPDGMGroup and HomeHealthEpisode
    # =========================================================================

    def get_pdgm_group_from_db(
        self,
        timing: str,
        clinical_group: str,
        functional_level: str,
        comorbidity: str,
    ):
        """
        Look up PDGM group from database model.

        Falls back to constants if not found in database.

        Args:
            timing: EARLY or LATE
            clinical_group: One of CLINICAL_GROUPS keys
            functional_level: LOW, MEDIUM, or HIGH
            comorbidity: NONE, LOW, or HIGH

        Returns:
            HomeHealthPDGMGroup instance or dict from constants
        """
        from upstream.products.homehealth.models import HomeHealthPDGMGroup

        try:
            return HomeHealthPDGMGroup.objects.get(
                timing=timing.upper(),
                clinical_group=clinical_group.upper(),
                functional_level=functional_level.upper(),
                comorbidity=comorbidity.upper(),
            )
        except HomeHealthPDGMGroup.DoesNotExist:
            return lookup_pdgm_group(
                timing, clinical_group, functional_level, comorbidity
            )

    def sync_pdgm_groups_to_db(self) -> dict:
        """
        Synchronize PDGM groups from constants to database.

        Creates or updates HomeHealthPDGMGroup records for all
        combinations defined in PDGM_GROUPS constant.

        Returns:
            dict with counts: {created: int, updated: int, total: int}
        """
        from upstream.products.homehealth.models import HomeHealthPDGMGroup
        from upstream.products.homehealth.constants import PDGM_GROUPS

        created = 0
        updated = 0

        for key, value in PDGM_GROUPS.items():
            timing, clinical_group, functional_level, comorbidity = key
            hipps_code = value["hipps"]
            payment_weight = value["weight"]

            group, was_created = HomeHealthPDGMGroup.objects.update_or_create(
                timing=timing,
                clinical_group=clinical_group,
                functional_level=functional_level,
                comorbidity=comorbidity,
                defaults={
                    "hipps_code": hipps_code,
                    "payment_weight": payment_weight,
                },
            )

            if was_created:
                created += 1
            else:
                updated += 1

        return {
            "created": created,
            "updated": updated,
            "total": created + updated,
        }

    def create_episode(
        self,
        customer,
        patient_identifier: str,
        payer: str,
        soc_date: date,
        **kwargs,
    ):
        """
        Create a new HomeHealthEpisode with validation.

        Args:
            customer: Customer instance
            patient_identifier: Patient ID
            payer: Payer name
            soc_date: Start of Care date
            **kwargs: Additional episode fields (f2f_date, timing, etc.)

        Returns:
            Created HomeHealthEpisode instance
        """
        from upstream.products.homehealth.models import HomeHealthEpisode

        episode = HomeHealthEpisode(
            customer=customer,
            patient_identifier=patient_identifier,
            payer=payer,
            soc_date=soc_date,
            **kwargs,
        )

        # Calculate NOA deadline
        episode.calculate_noa_deadline()

        # Validate F2F if provided
        if kwargs.get("f2f_date"):
            episode.validate_f2f_timing()

        # Validate NOA if provided
        if kwargs.get("noa_submitted_date"):
            episode.validate_noa_timeliness()

        # Look up PDGM group if classification provided
        if all(
            [
                kwargs.get("timing"),
                kwargs.get("clinical_group"),
                kwargs.get("functional_level"),
                kwargs.get("comorbidity"),
            ]
        ):
            episode.lookup_pdgm_group()

        episode.save()
        return episode

    def get_episodes_with_f2f_issues(self, customer):
        """
        Get episodes with F2F validation issues.

        Returns episodes where f2f_is_valid is False.

        Args:
            customer: Customer instance

        Returns:
            QuerySet of HomeHealthEpisode instances
        """
        from upstream.products.homehealth.models import HomeHealthEpisode

        return HomeHealthEpisode.objects.filter(
            customer=customer,
            f2f_is_valid=False,
            status="ACTIVE",
        ).order_by("-soc_date")

    def get_episodes_with_noa_issues(self, customer):
        """
        Get episodes with NOA deadline issues.

        Returns episodes where noa_is_timely is False and no NOA submitted.

        Args:
            customer: Customer instance

        Returns:
            QuerySet of HomeHealthEpisode instances
        """
        from upstream.products.homehealth.models import HomeHealthEpisode

        return HomeHealthEpisode.objects.filter(
            customer=customer,
            noa_is_timely=False,
            noa_submitted_date__isnull=True,
            status="ACTIVE",
        ).order_by("noa_deadline_date")

    def get_expiring_episodes(self, customer, days_ahead: int = 7):
        """
        Get episodes expiring within specified days.

        Args:
            customer: Customer instance
            days_ahead: Number of days to look ahead

        Returns:
            QuerySet of HomeHealthEpisode instances
        """
        from upstream.products.homehealth.models import HomeHealthEpisode

        cutoff_date = date.today() + timedelta(days=days_ahead)
        return HomeHealthEpisode.objects.filter(
            customer=customer,
            status="ACTIVE",
            episode_end_date__lte=cutoff_date,
            episode_end_date__gte=date.today(),
        ).order_by("episode_end_date")

    def validate_episode(self, episode) -> dict:
        """
        Validate a HomeHealthEpisode for compliance issues.

        Runs F2F timing, NOA deadline, and PDGM validation on the episode.

        Args:
            episode: HomeHealthEpisode instance

        Returns:
            dict with validation results
        """
        results = {
            "episode_id": episode.id,
            "f2f_valid": False,
            "noa_valid": False,
            "pdgm_valid": False,
            "issues": [],
        }

        # Validate F2F timing
        if episode.f2f_date and episode.soc_date:
            episode.validate_f2f_timing()
            results["f2f_valid"] = episode.f2f_is_valid
            if not episode.f2f_is_valid:
                days = episode.days_to_f2f
                results["issues"].append(f"F2F timing invalid: {days} days from SOC")
        else:
            if not episode.f2f_date:
                results["issues"].append("Missing F2F date")

        # Validate NOA deadline
        episode.calculate_noa_deadline()
        episode.validate_noa_timeliness()
        results["noa_valid"] = episode.noa_is_timely
        if not episode.noa_is_timely:
            if episode.noa_submitted_date:
                results["issues"].append("NOA submitted late")
            elif episode.noa_deadline_date:
                days_remaining = episode.noa_days_remaining
                if days_remaining is not None and days_remaining < 0:
                    results["issues"].append(
                        f"NOA overdue by {abs(days_remaining)} days"
                    )
                elif days_remaining is not None and days_remaining <= 2:
                    results["issues"].append(f"NOA due in {days_remaining} days")

        # Validate PDGM grouping
        if all(
            [
                episode.timing,
                episode.clinical_group,
                episode.functional_level,
                episode.comorbidity,
            ]
        ):
            group = episode.lookup_pdgm_group()
            results["pdgm_valid"] = group is not None
            if group is None:
                results["issues"].append(
                    f"No PDGM group found for: {episode.timing}/"
                    f"{episode.clinical_group}/{episode.functional_level}/"
                    f"{episode.comorbidity}"
                )
        else:
            missing = []
            if not episode.timing:
                missing.append("timing")
            if not episode.clinical_group:
                missing.append("clinical_group")
            if not episode.functional_level:
                missing.append("functional_level")
            if not episode.comorbidity:
                missing.append("comorbidity")
            if missing:
                results["issues"].append(f"Missing PDGM fields: {', '.join(missing)}")

        # Save updated validation flags
        episode.save(
            update_fields=[
                "f2f_is_valid",
                "noa_is_timely",
                "noa_deadline_date",
                "pdgm_group",
            ]
        )

        return results

    def get_compliance_summary(self, customer) -> dict:
        """
        Get compliance summary for all active episodes.

        Args:
            customer: Customer instance

        Returns:
            dict with compliance metrics
        """
        from upstream.products.homehealth.models import HomeHealthEpisode

        episodes = HomeHealthEpisode.objects.filter(
            customer=customer,
            status="ACTIVE",
        )

        total = episodes.count()
        f2f_valid = episodes.filter(f2f_is_valid=True).count()
        noa_timely = episodes.filter(noa_is_timely=True).count()
        pdgm_assigned = episodes.filter(pdgm_group__isnull=False).count()

        return {
            "total_active_episodes": total,
            "f2f_compliant": f2f_valid,
            "f2f_compliance_rate": (f2f_valid / total * 100) if total else 0,
            "noa_timely": noa_timely,
            "noa_compliance_rate": (noa_timely / total * 100) if total else 0,
            "pdgm_assigned": pdgm_assigned,
            "pdgm_assignment_rate": (pdgm_assigned / total * 100) if total else 0,
        }

    # =========================================================================
    # CERTIFICATION CYCLE MANAGEMENT
    # =========================================================================

    def create_initial_certification_cycle(self, episode):
        """
        Create the initial certification cycle for a new episode.

        Args:
            episode: HomeHealthEpisode instance

        Returns:
            Created CertificationCycle instance
        """
        from upstream.products.homehealth.models import CertificationCycle

        # Calculate 60-day cycle end from SOC
        cycle_end = episode.soc_date + timedelta(days=60)

        cycle = CertificationCycle.objects.create(
            customer=episode.customer,
            episode=episode,
            cycle_number=1,
            cycle_start=episode.soc_date,
            cycle_end=cycle_end,
            status="ACTIVE",
        )

        return cycle

    def get_active_certification_cycles(self, customer):
        """
        Get all active certification cycles for a customer.

        Args:
            customer: Customer instance

        Returns:
            QuerySet of CertificationCycle instances
        """
        from upstream.products.homehealth.models import CertificationCycle

        return (
            CertificationCycle.all_objects.filter(
                customer=customer,
                status="ACTIVE",
            )
            .select_related("episode")
            .order_by("cycle_end")
        )

    def get_cycles_approaching_deadline(self, customer, days_ahead: int = 14) -> list:
        """
        Get certification cycles with recertification due within specified days.

        Returns cycles organized by urgency level:
        - 45 days: INFO - Recert window opening
        - 30 days: MEDIUM - Recert deadline approaching
        - 21 days: HIGH - Urgent recert needed
        - 14 days: CRITICAL - Imminent expiration

        Args:
            customer: Customer instance
            days_ahead: Maximum days ahead to look (default 14)

        Returns:
            list of dicts with cycle info and urgency level
        """
        from upstream.products.homehealth.models import CertificationCycle

        today = date.today()
        cutoff = today + timedelta(days=days_ahead)

        cycles = (
            CertificationCycle.all_objects.filter(
                customer=customer,
                status="ACTIVE",
                cycle_end__gte=today,
                cycle_end__lte=cutoff,
            )
            .select_related("episode")
            .order_by("cycle_end")
        )

        results = []
        for cycle in cycles:
            days_remaining = (cycle.cycle_end - today).days

            # Determine urgency level
            if days_remaining <= 14:
                severity = "critical"
            elif days_remaining <= 21:
                severity = "high"
            elif days_remaining <= 30:
                severity = "medium"
            else:
                severity = "info"

            results.append(
                {
                    "cycle": cycle,
                    "cycle_id": cycle.id,
                    "episode_id": cycle.episode_id,
                    "patient_identifier": cycle.episode.patient_identifier,
                    "cycle_number": cycle.cycle_number,
                    "cycle_end": cycle.cycle_end,
                    "days_remaining": days_remaining,
                    "severity": severity,
                    "physician_recert_signed": cycle.physician_recert_signed,
                }
            )

        return results

    def check_certification_deadlines(self, customer) -> list:
        """
        Check all certification deadlines and return alerts for action.

        Returns alerts at these thresholds:
        - 45 days before: INFO alert
        - 30 days before: MEDIUM alert
        - 21 days before: HIGH alert
        - 14 days before: CRITICAL alert
        - Past deadline: EXPIRED

        Args:
            customer: Customer instance

        Returns:
            list of CertificationDeadlineResult with alerts
        """
        from upstream.products.homehealth.models import CertificationCycle

        today = date.today()
        results = []

        # Get all active cycles
        cycles = CertificationCycle.all_objects.filter(
            customer=customer,
            status="ACTIVE",
        ).select_related("episode")

        for cycle in cycles:
            days_remaining = (cycle.cycle_end - today).days

            # Skip if plenty of time remaining
            if days_remaining > 45:
                continue

            # Determine severity and message
            if days_remaining < 0:
                severity = "critical"
                message = f"Recertification EXPIRED {abs(days_remaining)} days ago"
                if cycle.status != "EXPIRED":
                    cycle.status = "EXPIRED"
                    cycle.save()
            elif days_remaining <= 14:
                severity = "critical"
                message = f"Recertification CRITICAL: {days_remaining} days remaining"
            elif days_remaining <= 21:
                severity = "high"
                message = f"Recertification URGENT: {days_remaining} days remaining"
            elif days_remaining <= 30:
                severity = "medium"
                message = f"Recertification approaching: {days_remaining} days"
            else:  # 31-45 days
                severity = "info"
                message = f"Recertification window: {days_remaining} days"

            results.append(
                {
                    "cycle_id": cycle.id,
                    "episode_id": cycle.episode_id,
                    "patient_identifier": cycle.episode.patient_identifier,
                    "cycle_number": cycle.cycle_number,
                    "cycle_start": cycle.cycle_start,
                    "cycle_end": cycle.cycle_end,
                    "days_remaining": days_remaining,
                    "severity": severity,
                    "message": message,
                    "physician_recert_signed": cycle.physician_recert_signed,
                    "requires_action": days_remaining <= 30
                    and not cycle.physician_recert_signed,
                }
            )

        # Sort by days remaining (most urgent first)
        results.sort(key=lambda x: x["days_remaining"])
        return results

    def recertify_cycle(
        self,
        cycle,
        physician_name: str = None,
        recert_date: date = None,
        create_next_cycle: bool = True,
    ):
        """
        Process recertification for a cycle.

        Args:
            cycle: CertificationCycle instance
            physician_name: Name of recertifying physician
            recert_date: Date of recertification
            create_next_cycle: Whether to create the next 60-day cycle

        Returns:
            tuple: (current_cycle, next_cycle or None)
        """
        # Mark current cycle as recertified
        cycle.mark_recertified(
            physician_name=physician_name,
            recert_date=recert_date,
        )

        # Create next cycle if requested
        next_cycle = None
        if create_next_cycle:
            next_cycle = cycle.create_next_cycle()

        return cycle, next_cycle

    def create_recertification_alert(
        self,
        customer,
        cycle_result: dict,
        alert_rule: Optional[AlertRule] = None,
    ) -> Optional[AlertEvent]:
        """
        Create an AlertEvent for certification deadline.

        Args:
            customer: Customer instance
            cycle_result: Result from check_certification_deadlines
            alert_rule: AlertRule to use (auto-creates if not provided)

        Returns:
            Created AlertEvent or None if not actionable
        """
        # Only create alerts for medium severity and above
        if cycle_result["severity"] not in ("medium", "high", "critical"):
            return None

        if alert_rule is None:
            alert_rule = self._get_or_create_cert_alert_rule(customer)

        payload = {
            "type": "homehealth_recertification_due",
            "cycle_id": cycle_result["cycle_id"],
            "episode_id": cycle_result["episode_id"],
            "patient_identifier": cycle_result["patient_identifier"],
            "cycle_number": cycle_result["cycle_number"],
            "cycle_start": str(cycle_result["cycle_start"]),
            "cycle_end": str(cycle_result["cycle_end"]),
            "days_remaining": cycle_result["days_remaining"],
            "severity": cycle_result["severity"],
            "message": cycle_result["message"],
            "requires_action": cycle_result["requires_action"],
        }

        alert = AlertEvent.objects.create(
            customer=customer,
            alert_rule=alert_rule,
            triggered_at=timezone.now(),
            status="pending",
            payload=payload,
        )

        return alert

    def _get_or_create_cert_alert_rule(self, customer) -> AlertRule:
        """Get or create alert rule for certification cycle alerts."""
        cache_key = f"{customer.id}_homehealth_cert"
        if cache_key in self._alert_rule_cache:
            return self._alert_rule_cache[cache_key]

        rule, _ = AlertRule.objects.get_or_create(
            customer=customer,
            name="Home Health Recertification Due",
            defaults={
                "description": "Alert when 60-day recertification deadline approaching",
                "metric": "certification_days_remaining",
                "threshold_type": "lte",
                "threshold_value": 30.0,
                "enabled": True,
                "severity": "warning",
                "scope": {
                    "service_type": "HOME_HEALTH",
                    "alert_type": "recertification",
                },
            },
        )

        self._alert_rule_cache[cache_key] = rule
        return rule

    def process_certification_alerts(self, customer) -> dict:
        """
        Process all certification deadline alerts for a customer.

        Checks deadlines and creates alerts as needed.

        Args:
            customer: Customer instance

        Returns:
            dict with processing summary
        """
        deadline_results = self.check_certification_deadlines(customer)

        summary = {
            "total_cycles_checked": len(deadline_results),
            "alerts_created": 0,
            "critical_count": 0,
            "high_count": 0,
            "medium_count": 0,
            "expired_count": 0,
        }

        alert_rule = None

        for result in deadline_results:
            severity = result["severity"]
            if severity == "critical" and result["days_remaining"] < 0:
                summary["expired_count"] += 1
            elif severity == "critical":
                summary["critical_count"] += 1
            elif severity == "high":
                summary["high_count"] += 1
            elif severity == "medium":
                summary["medium_count"] += 1

            # Create alert for actionable items
            if result["requires_action"] or severity == "critical":
                if alert_rule is None:
                    alert_rule = self._get_or_create_cert_alert_rule(customer)
                alert = self.create_recertification_alert(customer, result, alert_rule)
                if alert:
                    summary["alerts_created"] += 1

        return summary
