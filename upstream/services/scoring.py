"""
Risk Scoring Service

Implements the ML-based confidence scoring algorithm for claim automation.
Combines multiple confidence factors (coding, eligibility, documentation)
with historical denial risk from RiskBaseline to produce ClaimScore.

This service is responsible for:
- Calculating individual confidence metrics
- Looking up historical denial rates from RiskBaseline
- Computing overall confidence as weighted average
- Determining automation tier based on thresholds
- Detecting red-line actions requiring human review
- Integrating specialty-specific risk factors (dialysis, ABA, PT/OT, imaging,
  home health)

All methods accept domain objects (ClaimRecord, Customer) and return
structured results. Stateless and framework-agnostic.
"""

import logging
from typing import Dict, Optional, Any, List
from decimal import Decimal
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Confidence weights for overall score calculation
CONFIDENCE_WEIGHTS = {
    "coding": 0.25,
    "eligibility": 0.20,
    "medical_necessity": 0.30,
    "documentation": 0.25,
}

# Tier thresholds (default values - can be overridden by CustomerAutomationProfile)
DEFAULT_AUTO_EXECUTE_CONFIDENCE = 0.95
DEFAULT_AUTO_EXECUTE_MAX_AMOUNT = Decimal("1000.00")
DEFAULT_QUEUE_REVIEW_MIN_CONFIDENCE = 0.70
DEFAULT_QUEUE_REVIEW_MAX_AMOUNT = Decimal("10000.00")

# Risk score thresholds
HIGH_FRAUD_RISK_THRESHOLD = 0.70
HIGH_COMPLIANCE_RISK_THRESHOLD = 0.70

# Red-line actions requiring human review by regulation
RED_LINE_CPT_CODES = {
    # Medical necessity determinations (CA SB 1120, etc.)
    "99215",  # High-complexity E&M
    "99223",  # High-complexity inpatient
    "99291",  # Critical care
    # Prior authorization required procedures
    "27447",  # Total knee replacement
    "27130",  # Total hip replacement
}


@dataclass
class SpecialtyValidationResult:
    """Result of specialty-specific validation."""

    service_type: str
    is_compliant: bool
    risk_adjustment: float = 0.0
    violations: List[str] = field(default_factory=list)
    requires_review: bool = False
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScoringResult:
    """Result of scoring calculation."""

    overall_confidence: float
    coding_confidence: float
    eligibility_confidence: float
    medical_necessity_confidence: float
    documentation_completeness: float
    denial_risk_score: float
    fraud_risk_score: float
    compliance_risk_score: float
    recommended_action: str
    automation_tier: int
    requires_human_review: bool
    red_line_reason: str
    feature_importance: Dict[str, float]
    prediction_reasoning: str
    specialty_validation: Optional[SpecialtyValidationResult] = None


class RiskScoringService:
    """
    Stateless service for ML-based claim risk scoring.

    All methods are static - no instance state. This ensures the service
    is framework-agnostic and easily testable in isolation.
    """

    @staticmethod
    def calculate_score(
        claim_data: Dict[str, Any],
        baseline_data: Optional[Dict[str, Any]] = None,
        profile_thresholds: Optional[Dict[str, Any]] = None,
    ) -> ScoringResult:
        """
        Calculate comprehensive risk score for a claim.

        Combines multiple confidence factors with historical denial risk
        to produce an overall score and automation recommendation.

        Args:
            claim_data: Dict with claim fields:
                - payer: str
                - cpt: str
                - cpt_group: str
                - allowed_amount: Decimal
                - outcome: str (if known)
                - has_prior_auth: bool (optional)
                - documentation_count: int (optional)
            baseline_data: Optional dict from RiskBaseline lookup:
                - denial_rate: float
                - sample_size: int
                - confidence_score: float
            profile_thresholds: Optional customer thresholds:
                - auto_execute_confidence: float
                - auto_execute_max_amount: Decimal
                - queue_review_min_confidence: float

        Returns:
            ScoringResult with all confidence metrics and recommendation.
        """
        # Calculate individual confidence scores
        coding_confidence = RiskScoringService._calculate_coding_confidence(claim_data)
        eligibility_confidence = RiskScoringService._calculate_eligibility_confidence(
            claim_data
        )
        medical_necessity = RiskScoringService._calculate_medical_necessity_confidence(
            claim_data
        )
        documentation = RiskScoringService._calculate_documentation_completeness(
            claim_data
        )

        # Calculate risk scores
        denial_risk = RiskScoringService._calculate_denial_risk(
            claim_data, baseline_data
        )
        fraud_risk = RiskScoringService._calculate_fraud_risk(claim_data)
        compliance_risk = RiskScoringService._calculate_compliance_risk(claim_data)

        # Calculate weighted overall confidence
        overall_confidence = (
            coding_confidence * CONFIDENCE_WEIGHTS["coding"]
            + eligibility_confidence * CONFIDENCE_WEIGHTS["eligibility"]
            + medical_necessity * CONFIDENCE_WEIGHTS["medical_necessity"]
            + documentation * CONFIDENCE_WEIGHTS["documentation"]
        )

        # Adjust overall confidence based on risk scores
        risk_penalty = (denial_risk * 0.3 + fraud_risk * 0.2 + compliance_risk * 0.2)
        overall_confidence = max(0.0, overall_confidence - risk_penalty)

        # Check for red-line actions
        requires_review, red_line_reason = RiskScoringService._check_red_line_actions(
            claim_data
        )

        # Determine automation tier and recommended action
        action, tier = RiskScoringService._determine_automation_tier(
            overall_confidence,
            claim_data.get("allowed_amount"),
            fraud_risk,
            compliance_risk,
            requires_review,
            profile_thresholds,
        )

        # Build feature importance for explainability
        feature_importance = RiskScoringService._build_feature_importance(
            claim_data, baseline_data
        )

        # Generate human-readable reasoning
        reasoning = RiskScoringService._generate_reasoning(
            overall_confidence, denial_risk, action, red_line_reason
        )

        return ScoringResult(
            overall_confidence=round(overall_confidence, 4),
            coding_confidence=round(coding_confidence, 4),
            eligibility_confidence=round(eligibility_confidence, 4),
            medical_necessity_confidence=round(medical_necessity, 4),
            documentation_completeness=round(documentation, 4),
            denial_risk_score=round(denial_risk, 4),
            fraud_risk_score=round(fraud_risk, 4),
            compliance_risk_score=round(compliance_risk, 4),
            recommended_action=action,
            automation_tier=tier,
            requires_human_review=requires_review,
            red_line_reason=red_line_reason,
            feature_importance=feature_importance,
            prediction_reasoning=reasoning,
        )

    @staticmethod
    def _calculate_coding_confidence(claim_data: Dict[str, Any]) -> float:
        """
        Calculate confidence in CPT code accuracy.

        Factors considered:
        - Whether CPT code is in a known group (mapped)
        - CPT code format validity
        - Modifier presence/validity
        """
        cpt = claim_data.get("cpt", "")
        cpt_group = claim_data.get("cpt_group", "")

        confidence = 0.7  # Base confidence

        # Boost if CPT is properly mapped to a group
        if cpt_group and cpt_group not in ("Unknown", "Other"):
            confidence += 0.15

        # Boost for standard E&M codes (well-documented)
        if cpt.startswith("99"):
            confidence += 0.10

        # Slight penalty for procedure codes (more variability)
        if cpt.startswith(("2", "3", "4", "5", "6")):
            confidence -= 0.05

        return min(1.0, max(0.0, confidence))

    @staticmethod
    def _calculate_eligibility_confidence(claim_data: Dict[str, Any]) -> float:
        """
        Calculate confidence patient is eligible for service.

        Higher confidence when payer is known and claim has prior auth.
        """
        payer = claim_data.get("payer", "")
        has_prior_auth = claim_data.get("has_prior_auth", False)

        confidence = 0.75  # Base confidence

        # Boost for known major payers
        major_payers = ["Blue Cross", "Aetna", "United", "Cigna", "Medicare"]
        if any(mp.lower() in payer.lower() for mp in major_payers):
            confidence += 0.15

        # Boost if prior authorization obtained
        if has_prior_auth:
            confidence += 0.10

        return min(1.0, max(0.0, confidence))

    @staticmethod
    def _calculate_medical_necessity_confidence(claim_data: Dict[str, Any]) -> float:
        """
        Calculate confidence medical necessity criteria are met.

        This is typically the hardest to assess without clinical data.
        """
        cpt = claim_data.get("cpt", "")
        cpt_group = claim_data.get("cpt_group", "")

        confidence = 0.70  # Base - lower due to uncertainty

        # Standard E&M visits have clearer necessity
        if cpt.startswith("99") and "Office" in str(cpt_group):
            confidence += 0.20

        # Preventive care has clear criteria
        if "Preventive" in str(cpt_group):
            confidence += 0.15

        # Complex procedures need more documentation
        if cpt_group in ("Surgery", "Inpatient"):
            confidence -= 0.10

        return min(1.0, max(0.0, confidence))

    @staticmethod
    def _calculate_documentation_completeness(claim_data: Dict[str, Any]) -> float:
        """
        Calculate documentation completeness score.

        Based on presence of required supporting documents.
        """
        doc_count = claim_data.get("documentation_count", 0)
        has_prior_auth = claim_data.get("has_prior_auth", False)

        confidence = 0.60  # Base for minimal documentation

        # Scale up based on document count (diminishing returns)
        if doc_count >= 1:
            confidence += 0.15
        if doc_count >= 3:
            confidence += 0.10
        if doc_count >= 5:
            confidence += 0.05

        # Prior auth indicates documentation was reviewed
        if has_prior_auth:
            confidence += 0.10

        return min(1.0, max(0.0, confidence))

    @staticmethod
    def _calculate_denial_risk(
        claim_data: Dict[str, Any],
        baseline_data: Optional[Dict[str, Any]],
    ) -> float:
        """
        Calculate denial risk from historical baselines.

        Uses RiskBaseline lookup weighted by statistical confidence.
        """
        if baseline_data is None:
            # No baseline - use moderate risk estimate
            return 0.30

        denial_rate = baseline_data.get("denial_rate", 0.0)
        baseline_confidence = baseline_data.get("confidence_score", 0.5)

        # Weight the denial rate by baseline confidence
        # Low sample size = less confident in rate
        risk = denial_rate * baseline_confidence + 0.25 * (1 - baseline_confidence)

        return min(1.0, max(0.0, risk))

    @staticmethod
    def _calculate_fraud_risk(claim_data: Dict[str, Any]) -> float:
        """
        Calculate fraud risk score.

        Placeholder for NPI pattern analysis, billing anomaly detection.
        Real implementation would integrate with fraud detection models.
        """
        # Basic heuristics - real implementation would be ML-based
        allowed_amount = claim_data.get("allowed_amount")
        risk = 0.05  # Low base risk

        # Higher amounts warrant more scrutiny
        if allowed_amount:
            amount = Decimal(str(allowed_amount))
            if amount > Decimal("5000"):
                risk += 0.10
            if amount > Decimal("10000"):
                risk += 0.15

        return min(1.0, max(0.0, risk))

    @staticmethod
    def _calculate_compliance_risk(claim_data: Dict[str, Any]) -> float:
        """
        Calculate compliance risk (Stark, Anti-Kickback, etc.).

        Placeholder for compliance rule checking.
        Real implementation would check against known compliance patterns.
        """
        # Base low risk - most claims are compliant
        return 0.05

    @staticmethod
    def _check_red_line_actions(
        claim_data: Dict[str, Any],
    ) -> tuple[bool, str]:
        """
        Check if claim requires human review by regulation.

        Returns:
            Tuple of (requires_review: bool, reason: str)
        """
        cpt = claim_data.get("cpt", "")

        if cpt in RED_LINE_CPT_CODES:
            return True, f"CPT {cpt} requires medical necessity determination"

        allowed_amount = claim_data.get("allowed_amount")
        if allowed_amount:
            amount = Decimal(str(allowed_amount))
            if amount > Decimal("50000"):
                return True, "High-value claim requires human review"

        return False, ""

    @staticmethod
    def _determine_automation_tier(
        overall_confidence: float,
        allowed_amount: Optional[Decimal],
        fraud_risk: float,
        compliance_risk: float,
        requires_human_review: bool,
        profile_thresholds: Optional[Dict[str, Any]],
    ) -> tuple[str, int]:
        """
        Determine automation tier and recommended action.

        Returns:
            Tuple of (recommended_action: str, automation_tier: int)
        """
        # Get thresholds from profile or use defaults
        if profile_thresholds:
            auto_conf = profile_thresholds.get(
                "auto_execute_confidence", DEFAULT_AUTO_EXECUTE_CONFIDENCE
            )
            auto_amount = profile_thresholds.get(
                "auto_execute_max_amount", DEFAULT_AUTO_EXECUTE_MAX_AMOUNT
            )
            review_conf = profile_thresholds.get(
                "queue_review_min_confidence", DEFAULT_QUEUE_REVIEW_MIN_CONFIDENCE
            )
        else:
            auto_conf = DEFAULT_AUTO_EXECUTE_CONFIDENCE
            auto_amount = DEFAULT_AUTO_EXECUTE_MAX_AMOUNT
            review_conf = DEFAULT_QUEUE_REVIEW_MIN_CONFIDENCE

        # Check for blocking conditions
        if requires_human_review:
            return "escalate", 3

        if fraud_risk > HIGH_FRAUD_RISK_THRESHOLD:
            return "block", 3

        if compliance_risk > HIGH_COMPLIANCE_RISK_THRESHOLD:
            return "escalate", 3

        # Check amount threshold
        amount = Decimal(str(allowed_amount)) if allowed_amount else Decimal("0")

        # Tier 1: Auto-execute
        if overall_confidence >= auto_conf and amount <= auto_amount:
            return "auto_execute", 1

        # Tier 3: Escalate (below review threshold)
        if overall_confidence < review_conf:
            return "escalate", 3

        # Tier 2: Queue for review (middle ground)
        return "queue_review", 2

    @staticmethod
    def _build_feature_importance(
        claim_data: Dict[str, Any],
        baseline_data: Optional[Dict[str, Any]],
    ) -> Dict[str, float]:
        """
        Build feature importance dict for explainability.

        Shows which factors most influenced the score.
        """
        importance = {}

        # Payer history is often most important
        if baseline_data and baseline_data.get("sample_size", 0) > 10:
            importance["payer_history"] = 0.35
        else:
            importance["payer_history"] = 0.15

        # CPT code characteristics
        cpt_group = claim_data.get("cpt_group", "")
        if cpt_group and cpt_group not in ("Unknown", "Other"):
            importance["cpt_denial_rate"] = 0.25
        else:
            importance["cpt_denial_rate"] = 0.15

        # Documentation
        doc_count = claim_data.get("documentation_count", 0)
        if doc_count > 0:
            importance["documentation"] = 0.20
        else:
            importance["documentation_gaps"] = 0.30

        # Fill remaining importance
        remaining = 1.0 - sum(importance.values())
        importance["other_factors"] = max(0.0, remaining)

        return importance

    @staticmethod
    def _generate_reasoning(
        overall_confidence: float,
        denial_risk: float,
        action: str,
        red_line_reason: str,
    ) -> str:
        """
        Generate human-readable explanation of score.
        """
        parts = []

        if overall_confidence >= 0.95:
            parts.append("High confidence based on strong historical patterns")
        elif overall_confidence >= 0.70:
            parts.append("Moderate confidence - some uncertainty in prediction")
        else:
            parts.append("Low confidence - significant uncertainty")

        if denial_risk > 0.50:
            parts.append(f"Elevated denial risk ({denial_risk:.0%})")

        if red_line_reason:
            parts.append(f"Requires human review: {red_line_reason}")

        if action == "auto_execute":
            parts.append("Recommended for autonomous execution")
        elif action == "queue_review":
            parts.append("Recommended for review queue")
        else:
            parts.append("Requires escalation to human reviewer")

        return ". ".join(parts) + "."

    @staticmethod
    def lookup_baseline(
        customer_id: int,
        payer: str,
        cpt: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Look up RiskBaseline for customer/payer/cpt combination.

        Returns dict with denial_rate, sample_size, confidence_score
        or None if no baseline exists.

        Note: This is the only method that touches Django ORM.
        In production, consider caching baselines for performance.
        """
        from upstream.models import RiskBaseline

        try:
            baseline = RiskBaseline.objects.get(
                customer_id=customer_id,
                payer=payer,
                cpt=cpt,
            )
            return {
                "denial_rate": baseline.denial_rate,
                "sample_size": baseline.sample_size,
                "confidence_score": baseline.confidence_score,
            }
        except RiskBaseline.DoesNotExist:
            return None

    @staticmethod
    def get_profile_thresholds(customer_id: int) -> Optional[Dict[str, Any]]:
        """
        Get automation thresholds from CustomerAutomationProfile.

        Returns dict with threshold values or None if no profile exists.

        Note: This is the only method that touches Django ORM.
        """
        from upstream.automation.models import CustomerAutomationProfile

        try:
            profile = CustomerAutomationProfile.objects.get(customer_id=customer_id)
            return {
                "auto_execute_confidence": profile.auto_execute_confidence,
                "auto_execute_max_amount": profile.auto_execute_max_amount,
                "queue_review_min_confidence": profile.queue_review_min_confidence,
                "queue_review_max_amount": profile.queue_review_max_amount,
                "escalate_min_amount": profile.escalate_min_amount,
                "automation_stage": profile.automation_stage,
                "shadow_mode_enabled": profile.shadow_mode_enabled,
            }
        except CustomerAutomationProfile.DoesNotExist:
            return None

    @staticmethod
    def validate_specialty(
        claim_data: Dict[str, Any],
    ) -> Optional[SpecialtyValidationResult]:
        """
        Run specialty-specific validation based on claim service_type.

        Routes to appropriate specialty service and returns validation results
        that affect overall confidence and human review requirements.

        Args:
            claim_data: Dict with claim fields including:
                - service_type: str (DIALYSIS, ABA, PTOT, IMAGING, HOME_HEALTH)
                - cpt: str
                - payer: str
                - specialty_metadata: dict (specialty-specific data)

        Returns:
            SpecialtyValidationResult or None if no specialty applies
        """
        service_type = claim_data.get("service_type", "").upper()

        if not service_type:
            return None

        try:
            if service_type == "DIALYSIS":
                return RiskScoringService._validate_dialysis(claim_data)
            elif service_type == "ABA":
                return RiskScoringService._validate_aba(claim_data)
            elif service_type in ("PTOT", "PT/OT", "PT", "OT"):
                return RiskScoringService._validate_ptot(claim_data)
            elif service_type == "IMAGING":
                return RiskScoringService._validate_imaging(claim_data)
            elif service_type in ("HOME_HEALTH", "HOMEHEALTH", "HH"):
                return RiskScoringService._validate_home_health(claim_data)
            else:
                return None
        except Exception as e:
            logger.warning(f"Specialty validation failed for {service_type}: {e}")
            return None

    @staticmethod
    def _validate_dialysis(claim_data: Dict[str, Any]) -> SpecialtyValidationResult:
        """Validate dialysis claim for MA variance."""
        from upstream.products.dialysis.services import DialysisMAService

        service = DialysisMAService()
        violations = []
        risk_adjustment = 0.0
        requires_review = False
        details = {}

        # Create mock claim object for service
        class MockClaim:
            def __init__(self, data):
                self.cpt = data.get("cpt", "")
                self.paid_amount = data.get("paid_amount")

        claim = MockClaim(claim_data)
        result = service.detect_variance(claim)

        if result.has_variance:
            violations.append(result.message)
            details["variance_ratio"] = float(result.ratio) if result.ratio else None
            details["variance_amount"] = (
                str(result.variance_amount) if result.variance_amount else None
            )
            details["projected_annual_loss"] = (
                str(result.projected_annual_loss)
                if result.projected_annual_loss else None
            )

            if result.severity == "critical":
                risk_adjustment = 0.25
                requires_review = True
            elif result.severity == "warning":
                risk_adjustment = 0.15

        return SpecialtyValidationResult(
            service_type="DIALYSIS",
            is_compliant=not result.has_variance,
            risk_adjustment=risk_adjustment,
            violations=violations,
            requires_review=requires_review,
            details=details,
        )

    @staticmethod
    def _validate_aba(claim_data: Dict[str, Any]) -> SpecialtyValidationResult:
        """Validate ABA claim for unit tracking compliance."""
        from upstream.products.aba.services import ABAService

        service = ABAService()
        violations = []
        risk_adjustment = 0.0
        requires_review = False
        details = {}

        # Create mock claim object
        class MockClaim:
            def __init__(self, data):
                self.specialty_metadata = data.get("specialty_metadata", {})
                self.service_date = data.get("service_date")
                self.cpt = data.get("cpt", "")
                self.procedure_count = data.get("procedure_count")

        claim = MockClaim(claim_data)
        result = service.check_unit_compliance(claim)

        if not result.is_compliant:
            violations.append(result.message)
            details["units_used"] = result.units_used
            details["units_authorized"] = result.units_authorized
            details["units_remaining"] = result.units_remaining
            details["percent_used"] = result.percent_used

            if result.severity == "critical":
                risk_adjustment = 0.30
                requires_review = True
            elif result.severity in ("high", "warning"):
                risk_adjustment = 0.20

        return SpecialtyValidationResult(
            service_type="ABA",
            is_compliant=result.is_compliant,
            risk_adjustment=risk_adjustment,
            violations=violations,
            requires_review=requires_review,
            details=details,
        )

    @staticmethod
    def _validate_ptot(claim_data: Dict[str, Any]) -> SpecialtyValidationResult:
        """Validate PT/OT claim for 8-minute rule compliance."""
        from upstream.products.ptot.services import PTOTService

        service = PTOTService()
        violations = []
        risk_adjustment = 0.0
        requires_review = False
        details = {}

        # Create mock claim object
        class MockClaim:
            def __init__(self, data):
                self.cpt = data.get("cpt", "")
                self.total_minutes = data.get("total_minutes") or data.get(
                    "specialty_metadata", {}
                ).get("treatment_time")
                self.procedure_count = data.get("procedure_count") or data.get(
                    "specialty_metadata", {}
                ).get("units")
                self.modifiers = data.get("modifiers", "")

        claim = MockClaim(claim_data)
        result = service.validate_8_minute_rule(claim)

        if not result.is_valid and "not time-based" not in result.message:
            violations.append(result.message)
            details["total_minutes"] = result.total_minutes
            details["expected_units"] = result.expected_units
            details["billed_units"] = result.billed_units
            details["unit_difference"] = result.unit_difference

            if result.severity == "critical":
                risk_adjustment = 0.25
                requires_review = True
            elif result.severity == "warning":
                risk_adjustment = 0.15

        return SpecialtyValidationResult(
            service_type="PTOT",
            is_compliant=result.is_valid,
            risk_adjustment=risk_adjustment,
            violations=violations,
            requires_review=requires_review,
            details=details,
        )

    @staticmethod
    def _validate_imaging(claim_data: Dict[str, Any]) -> SpecialtyValidationResult:
        """Validate imaging claim for PA requirements."""
        from upstream.products.imaging.services import ImagingPAService

        service = ImagingPAService()
        violations = []
        risk_adjustment = 0.0
        requires_review = False
        details = {}

        # Create mock claim object
        class MockClaim:
            def __init__(self, data):
                self.cpt = data.get("cpt", "")
                self.payer_name = data.get("payer", "")
                self.authorization = data.get("authorization")
                self.specialty_metadata = data.get("specialty_metadata", {})

        claim = MockClaim(claim_data)
        pa_result = service.check_pa_required(claim)

        if pa_result.pa_required:
            details["pa_required"] = True
            details["rbm_provider"] = pa_result.rbm_provider

            if not pa_result.is_compliant:
                violations.append(pa_result.message)
                risk_adjustment = 0.30
                requires_review = True

        # Also check documentation
        doc_result = service.validate_documentation(claim)
        if not doc_result.is_complete:
            violations.append(
                f"Missing documentation: {', '.join(doc_result.missing_fields)}"
            )
            details["missing_fields"] = doc_result.missing_fields
            if doc_result.severity == "high":
                risk_adjustment = max(risk_adjustment, 0.20)

        return SpecialtyValidationResult(
            service_type="IMAGING",
            is_compliant=pa_result.is_compliant and doc_result.is_complete,
            risk_adjustment=risk_adjustment,
            violations=violations,
            requires_review=requires_review,
            details=details,
        )

    @staticmethod
    def _validate_home_health(
        claim_data: Dict[str, Any],
    ) -> SpecialtyValidationResult:
        """Validate home health claim for PDGM compliance."""
        from upstream.products.homehealth.services import HomeHealthService

        service = HomeHealthService()
        violations = []
        risk_adjustment = 0.0
        requires_review = False
        details = {}

        # Create mock claim object
        class MockClaim:
            def __init__(self, data):
                self.specialty_metadata = data.get("specialty_metadata", {})

        claim = MockClaim(claim_data)

        # Validate PDGM grouping
        pdgm_result = service.validate_pdgm_grouping(claim)
        if not pdgm_result.is_valid:
            violations.append(pdgm_result.message)
            details["pdgm_timing"] = pdgm_result.timing
            details["pdgm_clinical_group"] = pdgm_result.clinical_group
            details["pdgm_missing_fields"] = pdgm_result.missing_fields

            if pdgm_result.severity == "high":
                risk_adjustment = 0.25
                requires_review = True
            elif pdgm_result.severity == "medium":
                risk_adjustment = 0.15

        # Validate F2F timing
        f2f_result = service.validate_f2f_timing(claim)
        if not f2f_result.is_valid:
            violations.append(f2f_result.message)
            details["f2f_days_from_soc"] = f2f_result.days_from_soc

            if f2f_result.severity == "critical":
                risk_adjustment = max(risk_adjustment, 0.30)
                requires_review = True

        # Check NOA deadline
        noa_result = service.check_noa_deadline(claim)
        if noa_result.severity in ("high", "critical"):
            violations.append(noa_result.message)
            details["noa_days_until_deadline"] = noa_result.days_until_deadline
            details["noa_overdue"] = noa_result.is_overdue

            if noa_result.is_overdue:
                risk_adjustment = max(risk_adjustment, 0.25)
                requires_review = True

        is_compliant = (
            pdgm_result.is_valid
            and f2f_result.is_valid
            and not noa_result.is_overdue
        )

        return SpecialtyValidationResult(
            service_type="HOME_HEALTH",
            is_compliant=is_compliant,
            risk_adjustment=risk_adjustment,
            violations=violations,
            requires_review=requires_review,
            details=details,
        )

    @staticmethod
    def calculate_score_with_specialty(
        claim_data: Dict[str, Any],
        baseline_data: Optional[Dict[str, Any]] = None,
        profile_thresholds: Optional[Dict[str, Any]] = None,
    ) -> ScoringResult:
        """
        Calculate risk score including specialty-specific validation.

        This is the enhanced version of calculate_score that integrates
        specialty module validation into the overall risk assessment.

        Args:
            claim_data: Dict with claim fields including service_type
            baseline_data: Optional RiskBaseline lookup result
            profile_thresholds: Optional customer thresholds

        Returns:
            ScoringResult with specialty_validation populated
        """
        # Get base score
        result = RiskScoringService.calculate_score(
            claim_data, baseline_data, profile_thresholds
        )

        # Run specialty validation
        specialty_result = RiskScoringService.validate_specialty(claim_data)

        if specialty_result:
            # Apply specialty risk adjustment to overall confidence
            adjusted_confidence = max(
                0.0,
                result.overall_confidence - specialty_result.risk_adjustment
            )

            # Check if specialty requires human review
            requires_review = (
                result.requires_human_review or specialty_result.requires_review
            )
            red_line_reason = result.red_line_reason
            if specialty_result.requires_review and not red_line_reason:
                red_line_reason = (
                    f"Specialty violation: {specialty_result.violations[0]}"
                    if specialty_result.violations
                    else f"{specialty_result.service_type} compliance issue"
                )

            # Re-determine automation tier with adjusted confidence
            action, tier = RiskScoringService._determine_automation_tier(
                adjusted_confidence,
                claim_data.get("allowed_amount"),
                result.fraud_risk_score,
                result.compliance_risk_score,
                requires_review,
                profile_thresholds,
            )

            # Update reasoning
            reasoning_parts = [result.prediction_reasoning.rstrip(".")]
            if specialty_result.violations:
                reasoning_parts.append(
                    f"Specialty issues: {'; '.join(specialty_result.violations)}"
                )
            reasoning = ". ".join(reasoning_parts) + "."

            # Return updated result
            return ScoringResult(
                overall_confidence=round(adjusted_confidence, 4),
                coding_confidence=result.coding_confidence,
                eligibility_confidence=result.eligibility_confidence,
                medical_necessity_confidence=result.medical_necessity_confidence,
                documentation_completeness=result.documentation_completeness,
                denial_risk_score=result.denial_risk_score,
                fraud_risk_score=result.fraud_risk_score,
                compliance_risk_score=result.compliance_risk_score,
                recommended_action=action,
                automation_tier=tier,
                requires_human_review=requires_review,
                red_line_reason=red_line_reason,
                feature_importance=result.feature_importance,
                prediction_reasoning=reasoning,
                specialty_validation=specialty_result,
            )

        # No specialty validation - return original result
        return result
