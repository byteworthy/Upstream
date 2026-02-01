"""
ABA Authorization Tracking Service.

Service for tracking ABA authorization unit consumption, projecting
exhaustion dates, and generating alerts for re-authorization needs
and credential expirations.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional, List

from django.db import transaction
from django.utils import timezone

from upstream.alerts.models import AlertEvent, AlertRule
from upstream.models import Authorization
from upstream.products.aba.models import ABAAuthorizationTracker


# Alert thresholds
UTILIZATION_WARNING_THRESHOLD = Decimal("75")  # 75% utilization
UTILIZATION_HIGH_THRESHOLD = Decimal("90")  # 90% utilization
UTILIZATION_CRITICAL_THRESHOLD = Decimal("95")  # 95% utilization

# Re-auth alert days before expiration
REAUTH_30_DAY_ALERT = 30
REAUTH_14_DAY_ALERT = 14
REAUTH_3_DAY_ALERT = 3

# Credential expiration alert days
CREDENTIAL_60_DAY_ALERT = 60
CREDENTIAL_30_DAY_ALERT = 30
CREDENTIAL_14_DAY_ALERT = 14


@dataclass
class UnitTrackingResult:
    """Result of tracking units for a claim."""

    success: bool
    tracker: Optional[ABAAuthorizationTracker] = None
    units_added: int = 0
    units_remaining: int = 0
    utilization_percentage: Decimal = Decimal("0")
    alert_created: bool = False
    message: str = ""


@dataclass
class ExhaustionProjection:
    """Result of exhaustion projection."""

    projected_date: Optional[date] = None
    days_until_exhaustion: Optional[int] = None
    weekly_rate: Decimal = Decimal("0")
    is_at_risk: bool = False
    severity: str = "none"


@dataclass
class CredentialCheckResult:
    """Result of credential expiration check."""

    has_credential: bool = False
    credential_expiration: Optional[date] = None
    days_until_expiration: Optional[int] = None
    alert_needed: bool = False
    severity: str = "none"
    message: str = ""


class ABAAuthorizationService:
    """
    Service for tracking ABA authorization units and generating alerts.

    Handles:
    - Unit consumption tracking from claims
    - Authorization exhaustion projection
    - Re-authorization deadline alerts
    - BCBA credential expiration alerts
    """

    def __init__(self):
        """Initialize the ABA authorization service."""
        self._alert_rule_cache = {}

    def get_or_create_tracker(
        self, authorization: Authorization
    ) -> ABAAuthorizationTracker:
        """
        Get existing tracker or create one for an authorization.

        Args:
            authorization: Authorization to track

        Returns:
            ABAAuthorizationTracker instance
        """
        tracker, created = ABAAuthorizationTracker.objects.get_or_create(
            authorization=authorization,
            defaults={
                "units_authorized": self._get_authorized_units(authorization),
                "units_used": 0,
            },
        )
        return tracker

    def _get_authorized_units(self, authorization: Authorization) -> int:
        """Extract authorized units from authorization metadata."""
        metadata = authorization.specialty_metadata or {}
        return metadata.get("authorized_units", 0)

    @transaction.atomic
    def track_units(self, claim) -> UnitTrackingResult:
        """
        Track unit consumption from a claim.

        Args:
            claim: ClaimRecord with authorization and procedure_count

        Returns:
            UnitTrackingResult with tracking details
        """
        # Validate claim has required fields
        if not hasattr(claim, "authorization") or not claim.authorization:
            return UnitTrackingResult(
                success=False,
                message="Claim missing authorization",
            )

        if claim.authorization.service_type != "ABA":
            return UnitTrackingResult(
                success=False,
                message="Authorization is not for ABA services",
            )

        # Get unit count from claim
        units = getattr(claim, "procedure_count", None) or getattr(
            claim, "units", None
        )
        if units is None or units <= 0:
            return UnitTrackingResult(
                success=False,
                message="Claim missing valid unit count",
            )

        # Get or create tracker
        tracker = self.get_or_create_tracker(claim.authorization)

        # Update usage
        tracker.update_usage(units)

        # Check if alert needed
        alert_created = False
        if tracker.utilization_percentage >= UTILIZATION_HIGH_THRESHOLD:
            alert_created = self._create_utilization_alert(
                claim, tracker
            )

        return UnitTrackingResult(
            success=True,
            tracker=tracker,
            units_added=units,
            units_remaining=tracker.units_remaining,
            utilization_percentage=tracker.utilization_percentage,
            alert_created=alert_created,
            message=f"Tracked {units} units. {tracker.units_remaining} remaining.",
        )

    def project_exhaustion(
        self, authorization: Authorization
    ) -> ExhaustionProjection:
        """
        Project authorization exhaustion date.

        Args:
            authorization: Authorization to project

        Returns:
            ExhaustionProjection with projection details
        """
        try:
            tracker = ABAAuthorizationTracker.objects.get(
                authorization=authorization
            )
        except ABAAuthorizationTracker.DoesNotExist:
            return ExhaustionProjection(
                is_at_risk=False,
                severity="none",
            )

        # Recalculate projection
        tracker._recalculate_weekly_rate()
        tracker._project_exhaustion()
        tracker.save()

        # Calculate days until exhaustion
        days_until = None
        if tracker.projected_exhaustion_date:
            delta = tracker.projected_exhaustion_date - timezone.now().date()
            days_until = delta.days

        # Determine severity
        severity = "none"
        is_at_risk = False
        if days_until is not None:
            if days_until <= 7:
                severity = "critical"
                is_at_risk = True
            elif days_until <= 14:
                severity = "high"
                is_at_risk = True
            elif days_until <= 30:
                severity = "medium"
                is_at_risk = True

        return ExhaustionProjection(
            projected_date=tracker.projected_exhaustion_date,
            days_until_exhaustion=days_until,
            weekly_rate=tracker.weekly_usage_rate,
            is_at_risk=is_at_risk,
            severity=severity,
        )

    def check_auth_expiration(
        self,
        authorization: Authorization,
        create_alert: bool = True,
    ) -> Optional[AlertEvent]:
        """
        Check authorization expiration and create alert if needed.

        Args:
            authorization: Authorization to check
            create_alert: Whether to create AlertEvent

        Returns:
            AlertEvent if alert created, None otherwise
        """
        if not authorization.auth_end_date:
            return None

        today = timezone.now().date()
        days_until = (authorization.auth_end_date - today).days

        # Determine severity based on days until expiration
        if days_until <= REAUTH_3_DAY_ALERT:
            severity = "critical"
            alert_type = "reauth_3_day"
        elif days_until <= REAUTH_14_DAY_ALERT:
            severity = "high"
            alert_type = "reauth_14_day"
        elif days_until <= REAUTH_30_DAY_ALERT:
            severity = "medium"
            alert_type = "reauth_30_day"
        else:
            return None  # No alert needed

        if not create_alert:
            return None

        # Check if we already sent this alert
        try:
            tracker = ABAAuthorizationTracker.objects.get(
                authorization=authorization
            )
            if (
                tracker.last_alert_type == alert_type
                and tracker.last_alert_date == today
            ):
                return None  # Already sent today
        except ABAAuthorizationTracker.DoesNotExist:
            tracker = None

        # Create alert
        alert_rule = self._get_or_create_alert_rule(
            authorization.customer, "aba_reauth"
        )

        payload = {
            "type": "aba_reauth_expiration",
            "authorization_id": authorization.id,
            "auth_number": authorization.auth_number,
            "days_until_expiration": days_until,
            "expiration_date": str(authorization.auth_end_date),
            "severity": severity,
        }

        alert = AlertEvent.objects.create(
            customer=authorization.customer,
            alert_rule=alert_rule,
            triggered_at=timezone.now(),
            status="pending",
            payload=payload,
        )

        # Update tracker with alert info
        if tracker:
            tracker.last_alert_date = today
            tracker.last_alert_type = alert_type
            tracker.save()

        return alert

    def check_credential_expiration(
        self,
        authorization: Authorization,
        create_alert: bool = True,
    ) -> CredentialCheckResult:
        """
        Check BCBA credential expiration from specialty_metadata.

        Args:
            authorization: Authorization to check
            create_alert: Whether to create AlertEvent

        Returns:
            CredentialCheckResult with check details
        """
        metadata = authorization.specialty_metadata or {}

        # Check if BCBA credential info exists
        if not metadata.get("bcba_required", False):
            return CredentialCheckResult(
                has_credential=False,
                message="BCBA credential not required for this authorization",
            )

        credential_expiration_str = metadata.get("credential_expiration")
        if not credential_expiration_str:
            return CredentialCheckResult(
                has_credential=True,
                alert_needed=True,
                severity="high",
                message="BCBA credential required but expiration not set",
            )

        # Parse expiration date
        try:
            credential_expiration = date.fromisoformat(
                credential_expiration_str
            )
        except (ValueError, TypeError):
            return CredentialCheckResult(
                has_credential=True,
                alert_needed=True,
                severity="high",
                message="Invalid credential expiration date format",
            )

        # Calculate days until expiration
        today = timezone.now().date()
        days_until = (credential_expiration - today).days

        # Determine severity
        if days_until <= CREDENTIAL_14_DAY_ALERT:
            severity = "critical"
            alert_needed = True
        elif days_until <= CREDENTIAL_30_DAY_ALERT:
            severity = "high"
            alert_needed = True
        elif days_until <= CREDENTIAL_60_DAY_ALERT:
            severity = "medium"
            alert_needed = True
        else:
            severity = "none"
            alert_needed = False

        # Create alert if needed
        if alert_needed and create_alert:
            self._create_credential_alert(
                authorization, days_until, severity
            )

        return CredentialCheckResult(
            has_credential=True,
            credential_expiration=credential_expiration,
            days_until_expiration=days_until,
            alert_needed=alert_needed,
            severity=severity,
            message=f"BCBA credential expires in {days_until} days",
        )

    def _create_utilization_alert(
        self,
        claim,
        tracker: ABAAuthorizationTracker,
    ) -> bool:
        """Create alert for high utilization."""
        # Determine severity
        util = tracker.utilization_percentage
        if util >= UTILIZATION_CRITICAL_THRESHOLD:
            severity = "critical"
        elif util >= UTILIZATION_HIGH_THRESHOLD:
            severity = "high"
        else:
            severity = "medium"

        alert_rule = self._get_or_create_alert_rule(
            claim.customer, "aba_utilization"
        )

        payload = {
            "type": "aba_utilization",
            "authorization_id": tracker.authorization.id,
            "auth_number": tracker.authorization.auth_number,
            "units_used": tracker.units_used,
            "units_authorized": tracker.units_authorized,
            "units_remaining": tracker.units_remaining,
            "utilization_percentage": str(tracker.utilization_percentage),
            "projected_exhaustion_date": str(
                tracker.projected_exhaustion_date
            )
            if tracker.projected_exhaustion_date
            else None,
            "severity": severity,
        }

        AlertEvent.objects.create(
            customer=claim.customer,
            alert_rule=alert_rule,
            triggered_at=timezone.now(),
            status="pending",
            payload=payload,
        )

        return True

    def _create_credential_alert(
        self,
        authorization: Authorization,
        days_until: int,
        severity: str,
    ):
        """Create alert for credential expiration."""
        alert_rule = self._get_or_create_alert_rule(
            authorization.customer, "aba_credential"
        )

        payload = {
            "type": "aba_credential_expiration",
            "authorization_id": authorization.id,
            "auth_number": authorization.auth_number,
            "days_until_expiration": days_until,
            "severity": severity,
        }

        AlertEvent.objects.create(
            customer=authorization.customer,
            alert_rule=alert_rule,
            triggered_at=timezone.now(),
            status="pending",
            payload=payload,
        )

    def _get_or_create_alert_rule(
        self, customer, rule_type: str
    ) -> AlertRule:
        """Get or create alert rule for ABA alerts."""
        cache_key = f"{customer.id}_{rule_type}"
        if cache_key in self._alert_rule_cache:
            return self._alert_rule_cache[cache_key]

        rule_configs = {
            "aba_utilization": {
                "name": "ABA Authorization Utilization Alert",
                "description": "Alert when ABA units reach high utilization",
                "metric": "utilization_percentage",
            },
            "aba_reauth": {
                "name": "ABA Re-Authorization Alert",
                "description": "Alert when ABA authorization nearing expiration",
                "metric": "days_until_expiration",
            },
            "aba_credential": {
                "name": "ABA Credential Expiration Alert",
                "description": "Alert when BCBA credential nearing expiration",
                "metric": "days_until_credential_expiration",
            },
        }

        config = rule_configs.get(rule_type, rule_configs["aba_utilization"])

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
                "scope": {"service_type": "ABA"},
            },
        )

        self._alert_rule_cache[cache_key] = rule
        return rule

    def analyze_authorizations(
        self,
        authorizations,
        check_expiration: bool = True,
        check_credentials: bool = True,
    ) -> dict:
        """
        Analyze multiple ABA authorizations.

        Args:
            authorizations: Iterable of Authorization instances
            check_expiration: Whether to check expiration dates
            check_credentials: Whether to check credentials

        Returns:
            dict with analysis summary
        """
        results = {
            "total": 0,
            "at_risk_utilization": 0,
            "expiring_soon": 0,
            "credential_expiring": 0,
            "alerts_created": 0,
        }

        for auth in authorizations:
            if auth.service_type != "ABA":
                continue

            results["total"] += 1

            # Check utilization
            projection = self.project_exhaustion(auth)
            if projection.is_at_risk:
                results["at_risk_utilization"] += 1

            # Check expiration
            if check_expiration:
                alert = self.check_auth_expiration(auth)
                if alert:
                    results["expiring_soon"] += 1
                    results["alerts_created"] += 1

            # Check credentials
            if check_credentials:
                cred_result = self.check_credential_expiration(auth)
                if cred_result.alert_needed:
                    results["credential_expiring"] += 1
                    results["alerts_created"] += 1

        return results
