"""
Imaging Prior Authorization Service.

Service for validating imaging claims have required prior authorization
and proper medical necessity documentation.
"""

from dataclasses import dataclass
from typing import Optional

from django.utils import timezone

from upstream.alerts.models import AlertEvent, AlertRule
from upstream.products.imaging.models import ImagingPARequirement


@dataclass
class PACheckResult:
    """Result of PA requirement check for a claim."""

    pa_required: bool
    has_authorization: bool = False
    is_compliant: bool = True
    rbm_provider: str = ""
    severity: str = "none"
    message: str = ""
    authorization_id: Optional[int] = None


@dataclass
class DocumentationCheckResult:
    """Result of medical necessity documentation check."""

    is_complete: bool = True
    has_medical_necessity_docs: bool = False
    has_clinical_justification: bool = False
    has_icd10_codes: bool = False
    missing_fields: list = None
    severity: str = "none"
    message: str = ""

    def __post_init__(self):
        if self.missing_fields is None:
            self.missing_fields = []


class ImagingPAService:
    """
    Service for validating imaging claims against PA requirements.

    Handles:
    - PA requirement lookup by payer and CPT code
    - Authorization verification for claims
    - Medical necessity documentation validation
    - Alert creation for non-compliance
    """

    def __init__(self):
        """Initialize the imaging PA service."""
        self._alert_rule_cache = {}

    def check_pa_required(self, claim) -> PACheckResult:
        """
        Check if claim requires prior authorization.

        Args:
            claim: ClaimRecord with payer, cpt, and authorization fields

        Returns:
            PACheckResult with PA requirement status
        """
        # Validate claim has required fields
        if not hasattr(claim, "cpt") or not claim.cpt:
            return PACheckResult(
                pa_required=False,
                is_compliant=True,
                message="Claim missing CPT code",
            )

        # Get payer info
        payer = self._get_payer(claim)
        if not payer:
            return PACheckResult(
                pa_required=False,
                is_compliant=True,
                message="Could not determine payer",
            )

        # Look up PA requirement
        requirement = ImagingPARequirement.get_requirement(
            payer=payer,
            cpt=claim.cpt,
        )

        if not requirement or not requirement.pa_required:
            return PACheckResult(
                pa_required=False,
                is_compliant=True,
                message=f"No PA required for {payer}/{claim.cpt}",
            )

        # PA is required - check for active authorization
        has_auth = False
        auth_id = None

        if hasattr(claim, "authorization") and claim.authorization:
            auth = claim.authorization
            has_auth = self._is_authorization_valid(auth, claim)
            auth_id = auth.id if has_auth else None

        # Determine compliance
        if has_auth:
            return PACheckResult(
                pa_required=True,
                has_authorization=True,
                is_compliant=True,
                rbm_provider=requirement.rbm_provider,
                authorization_id=auth_id,
                message="PA required and authorization found",
            )
        else:
            return PACheckResult(
                pa_required=True,
                has_authorization=False,
                is_compliant=False,
                rbm_provider=requirement.rbm_provider,
                severity="critical",
                message=(
                    f"MISSING PA: {payer}/{claim.cpt} requires authorization "
                    f"via {requirement.get_rbm_provider_display()}"
                ),
            )

    def _get_payer(self, claim) -> Optional[str]:
        """Extract payer identifier from claim."""
        # Try various payer fields
        if hasattr(claim, "payer_name") and claim.payer_name:
            return claim.payer_name
        if hasattr(claim, "payer") and claim.payer:
            if hasattr(claim.payer, "name"):
                return claim.payer.name
            return str(claim.payer)
        if hasattr(claim, "insurance_name") and claim.insurance_name:
            return claim.insurance_name
        return None

    def _is_authorization_valid(self, auth, claim) -> bool:
        """Check if authorization is valid for this claim."""
        if not auth:
            return False

        # Check authorization status
        valid_statuses = ("approved", "active")
        if hasattr(auth, "status") and auth.status not in valid_statuses:
            return False

        # Check date validity
        service_date = getattr(claim, "service_date", None)
        if service_date:
            start = getattr(auth, "auth_start_date", None)
            if start and service_date < start:
                return False
            end = getattr(auth, "auth_expiration_date", None)
            if end and service_date > end:
                return False

        return True

    def validate_documentation(self, claim) -> DocumentationCheckResult:
        """
        Validate medical necessity documentation in claim metadata.

        Expected specialty_metadata fields:
        - has_medical_necessity_docs: bool
        - clinical_justification: str
        - icd10_codes: list

        Args:
            claim: ClaimRecord with specialty_metadata

        Returns:
            DocumentationCheckResult with validation details
        """
        metadata = getattr(claim, "specialty_metadata", None) or {}
        missing = []

        # Check required documentation fields
        has_necessity = metadata.get("has_medical_necessity_docs", False)
        has_justification = bool(metadata.get("clinical_justification", ""))
        has_icd10 = bool(metadata.get("icd10_codes", []))

        if not has_necessity:
            missing.append("has_medical_necessity_docs")
        if not has_justification:
            missing.append("clinical_justification")
        if not has_icd10:
            missing.append("icd10_codes")

        is_complete = len(missing) == 0

        if is_complete:
            return DocumentationCheckResult(
                is_complete=True,
                has_medical_necessity_docs=has_necessity,
                has_clinical_justification=has_justification,
                has_icd10_codes=has_icd10,
                message="Documentation complete",
            )
        else:
            severity = "high" if len(missing) >= 2 else "medium"
            return DocumentationCheckResult(
                is_complete=False,
                has_medical_necessity_docs=has_necessity,
                has_clinical_justification=has_justification,
                has_icd10_codes=has_icd10,
                missing_fields=missing,
                severity=severity,
                message=f"Missing documentation: {', '.join(missing)}",
            )

    def create_pa_alert(
        self,
        claim,
        result: PACheckResult,
        alert_rule: Optional[AlertRule] = None,
    ) -> Optional[AlertEvent]:
        """
        Create an AlertEvent for missing PA.

        Args:
            claim: ClaimRecord that triggered the alert
            result: Result from check_pa_required
            alert_rule: AlertRule to use (auto-finds if not provided)

        Returns:
            Created AlertEvent or None if compliant
        """
        if result.is_compliant:
            return None

        if alert_rule is None:
            alert_rule = self._get_or_create_alert_rule(
                claim.customer, "imaging_missing_pa"
            )

        payload = {
            "type": "imaging_missing_pa",
            "cpt": claim.cpt,
            "payer": self._get_payer(claim),
            "rbm_provider": result.rbm_provider,
            "pa_required": result.pa_required,
            "has_authorization": result.has_authorization,
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

    def create_documentation_alert(
        self,
        claim,
        result: DocumentationCheckResult,
        alert_rule: Optional[AlertRule] = None,
    ) -> Optional[AlertEvent]:
        """
        Create an AlertEvent for missing documentation.

        Args:
            claim: ClaimRecord with incomplete documentation
            result: Result from validate_documentation
            alert_rule: AlertRule to use (auto-finds if not provided)

        Returns:
            Created AlertEvent or None if complete
        """
        if result.is_complete:
            return None

        if alert_rule is None:
            alert_rule = self._get_or_create_alert_rule(
                claim.customer, "imaging_documentation"
            )

        payload = {
            "type": "imaging_incomplete_documentation",
            "cpt": claim.cpt if hasattr(claim, "cpt") else None,
            "missing_fields": result.missing_fields,
            "has_medical_necessity_docs": result.has_medical_necessity_docs,
            "has_clinical_justification": result.has_clinical_justification,
            "has_icd10_codes": result.has_icd10_codes,
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
        """Get or create alert rule for imaging alerts."""
        cache_key = f"{customer.id}_{rule_type}"
        if cache_key in self._alert_rule_cache:
            return self._alert_rule_cache[cache_key]

        rule_configs = {
            "imaging_missing_pa": {
                "name": "Imaging Missing Prior Authorization",
                "description": "Alert when PA-required imaging lacks auth",
                "metric": "pa_required",
            },
            "imaging_documentation": {
                "name": "Imaging Incomplete Documentation",
                "description": "Alert when medical necessity docs incomplete",
                "metric": "missing_fields_count",
            },
        }

        default_config = rule_configs["imaging_missing_pa"]
        config = rule_configs.get(rule_type, default_config)

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
                "scope": {"service_type": "IMAGING"},
            },
        )

        self._alert_rule_cache[cache_key] = rule
        return rule

    def analyze_claims(
        self,
        claims,
        create_alerts: bool = True,
        validate_docs: bool = True,
    ) -> dict:
        """
        Analyze multiple imaging claims for PA compliance.

        Args:
            claims: Iterable of ClaimRecord instances
            create_alerts: Whether to create AlertEvents
            validate_docs: Whether to validate documentation

        Returns:
            dict with analysis summary
        """
        results = {
            "total_claims": 0,
            "pa_required_claims": 0,
            "pa_compliant_claims": 0,
            "missing_pa_claims": 0,
            "docs_complete": 0,
            "docs_incomplete": 0,
            "alerts_created": 0,
        }

        pa_alert_rule = None
        doc_alert_rule = None

        for claim in claims:
            results["total_claims"] += 1

            # Check PA requirement
            pa_result = self.check_pa_required(claim)

            if pa_result.pa_required:
                results["pa_required_claims"] += 1
                if pa_result.is_compliant:
                    results["pa_compliant_claims"] += 1
                else:
                    results["missing_pa_claims"] += 1
                    if create_alerts:
                        if pa_alert_rule is None:
                            pa_alert_rule = self._get_or_create_alert_rule(
                                claim.customer, "imaging_missing_pa"
                            )
                        alert = self.create_pa_alert(
                            claim, pa_result, pa_alert_rule
                        )
                        if alert:
                            results["alerts_created"] += 1

            # Validate documentation for PA-required claims
            if validate_docs and pa_result.pa_required:
                doc_result = self.validate_documentation(claim)
                if doc_result.is_complete:
                    results["docs_complete"] += 1
                else:
                    results["docs_incomplete"] += 1
                    if create_alerts:
                        if doc_alert_rule is None:
                            doc_alert_rule = self._get_or_create_alert_rule(
                                claim.customer, "imaging_documentation"
                            )
                        alert = self.create_documentation_alert(
                            claim, doc_result, doc_alert_rule
                        )
                        if alert:
                            results["alerts_created"] += 1

        return results
