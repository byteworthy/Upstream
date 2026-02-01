"""
Unit tests for RiskScoringService.

Tests comprehensive coverage of the scoring algorithm, tier routing,
red-line detection, and baseline integration.
"""

import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock

from upstream.services.scoring import (
    RiskScoringService,
    ScoringResult,
    CONFIDENCE_WEIGHTS,
    DEFAULT_AUTO_EXECUTE_CONFIDENCE,
    DEFAULT_QUEUE_REVIEW_MIN_CONFIDENCE,
    RED_LINE_CPT_CODES,
)


class TestRiskScoringServiceCalculateScore:
    """Tests for RiskScoringService.calculate_score()."""

    def test_calculate_score_returns_scoring_result(self):
        """calculate_score returns a ScoringResult dataclass."""
        claim_data = {
            "payer": "Blue Cross",
            "cpt": "99213",
            "cpt_group": "Office Visit",
            "allowed_amount": Decimal("150.00"),
        }

        result = RiskScoringService.calculate_score(claim_data)

        assert isinstance(result, ScoringResult)
        assert hasattr(result, "overall_confidence")
        assert hasattr(result, "recommended_action")
        assert hasattr(result, "automation_tier")

    def test_calculate_score_confidence_in_valid_range(self):
        """All confidence scores should be between 0 and 1."""
        claim_data = {
            "payer": "Unknown Payer",
            "cpt": "12345",
            "cpt_group": "Unknown",
            "allowed_amount": Decimal("100.00"),
        }

        result = RiskScoringService.calculate_score(claim_data)

        assert 0.0 <= result.overall_confidence <= 1.0
        assert 0.0 <= result.coding_confidence <= 1.0
        assert 0.0 <= result.eligibility_confidence <= 1.0
        assert 0.0 <= result.medical_necessity_confidence <= 1.0
        assert 0.0 <= result.documentation_completeness <= 1.0
        assert 0.0 <= result.denial_risk_score <= 1.0
        assert 0.0 <= result.fraud_risk_score <= 1.0
        assert 0.0 <= result.compliance_risk_score <= 1.0

    def test_calculate_score_with_baseline_data(self):
        """Baseline data should influence denial_risk_score."""
        claim_data = {
            "payer": "Aetna",
            "cpt": "99214",
            "cpt_group": "Office Visit",
            "allowed_amount": Decimal("200.00"),
        }

        baseline_data = {
            "denial_rate": 0.15,
            "sample_size": 500,
            "confidence_score": 0.95,
        }

        result = RiskScoringService.calculate_score(claim_data, baseline_data)

        # Denial risk should be influenced by baseline
        assert result.denial_risk_score > 0.0
        # With 15% denial rate and high confidence, risk should be moderate
        assert result.denial_risk_score < 0.5

    def test_calculate_score_without_baseline_uses_default(self):
        """Without baseline, should use default moderate risk estimate."""
        claim_data = {
            "payer": "Unknown",
            "cpt": "99215",
            "cpt_group": "Office Visit",
            "allowed_amount": Decimal("300.00"),
        }

        result = RiskScoringService.calculate_score(claim_data, baseline_data=None)

        # Default risk estimate is 0.30
        assert result.denial_risk_score == pytest.approx(0.30, rel=0.1)

    def test_calculate_score_with_high_denial_baseline(self):
        """High denial rate baseline should increase risk score."""
        claim_data = {
            "payer": "Problematic Payer",
            "cpt": "99213",
            "cpt_group": "Office Visit",
            "allowed_amount": Decimal("150.00"),
        }

        baseline_high_denial = {
            "denial_rate": 0.75,
            "sample_size": 1000,
            "confidence_score": 0.99,
        }

        result = RiskScoringService.calculate_score(claim_data, baseline_high_denial)

        # High denial rate should result in higher denial risk
        assert result.denial_risk_score > 0.5

    def test_calculate_score_with_profile_thresholds(self):
        """Custom thresholds from profile should affect tier determination."""
        claim_data = {
            "payer": "Blue Cross",
            "cpt": "99213",
            "cpt_group": "Office Visit",
            "allowed_amount": Decimal("100.00"),
        }

        # Lower auto-execute threshold
        profile_thresholds = {
            "auto_execute_confidence": 0.80,
            "auto_execute_max_amount": Decimal("500.00"),
            "queue_review_min_confidence": 0.60,
        }

        result = RiskScoringService.calculate_score(
            claim_data, profile_thresholds=profile_thresholds
        )

        # With lower threshold, more likely to get tier 1
        assert result.automation_tier in [1, 2]


class TestRiskScoringServiceTierRouting:
    """Tests for three-tier routing logic."""

    def test_tier1_auto_execute_high_confidence_low_amount(self):
        """Tier 1: High confidence + low amount = auto-execute."""
        claim_data = {
            "payer": "Blue Cross",
            "cpt": "99213",
            "cpt_group": "Office Visit",
            "allowed_amount": Decimal("100.00"),
            "has_prior_auth": True,
            "documentation_count": 5,
        }

        # Use very high baseline confidence
        baseline_data = {
            "denial_rate": 0.02,
            "sample_size": 1000,
            "confidence_score": 0.99,
        }

        # Set threshold at 0.70 to make auto-execute more likely
        profile = {
            "auto_execute_confidence": 0.70,
            "auto_execute_max_amount": Decimal("500.00"),
            "queue_review_min_confidence": 0.50,
        }

        result = RiskScoringService.calculate_score(claim_data, baseline_data, profile)

        assert result.automation_tier == 1
        assert result.recommended_action == "auto_execute"

    def test_tier2_queue_review_moderate_confidence(self):
        """Tier 2: Moderate confidence = queue for review."""
        claim_data = {
            "payer": "Unknown Payer",
            "cpt": "99213",
            "cpt_group": "Office Visit",
            "allowed_amount": Decimal("5000.00"),
        }

        baseline_data = {
            "denial_rate": 0.30,
            "sample_size": 100,
            "confidence_score": 0.50,
        }

        result = RiskScoringService.calculate_score(claim_data, baseline_data)

        # Should be tier 2 with moderate confidence
        assert result.automation_tier in [2, 3]

    def test_tier3_escalate_low_confidence(self):
        """Tier 3: Low confidence = escalate to human."""
        claim_data = {
            "payer": "Unknown",
            "cpt": "12345",
            "cpt_group": "Unknown",
            "allowed_amount": Decimal("50000.00"),
        }

        baseline_data = {
            "denial_rate": 0.80,
            "sample_size": 50,
            "confidence_score": 0.30,
        }

        result = RiskScoringService.calculate_score(claim_data, baseline_data)

        assert result.automation_tier == 3
        assert result.recommended_action in ["escalate", "block"]

    def test_tier3_high_fraud_risk(self):
        """Tier 3: High fraud risk should trigger escalation."""
        claim_data = {
            "payer": "Blue Cross",
            "cpt": "99213",
            "cpt_group": "Office Visit",
            "allowed_amount": Decimal("100000.00"),  # Very high amount
        }

        result = RiskScoringService.calculate_score(claim_data)

        # High amount should trigger fraud risk and require escalation
        assert result.fraud_risk_score > 0.10
        assert result.automation_tier == 3

    def test_high_amount_exceeds_auto_execute_threshold(self):
        """Amount above auto_execute_max_amount should prevent tier 1."""
        claim_data = {
            "payer": "Blue Cross",
            "cpt": "99213",
            "cpt_group": "Office Visit",
            "allowed_amount": Decimal("5000.00"),  # Above default 1000
            "has_prior_auth": True,
        }

        baseline_data = {
            "denial_rate": 0.01,
            "sample_size": 1000,
            "confidence_score": 0.99,
        }

        result = RiskScoringService.calculate_score(claim_data, baseline_data)

        # Even with high confidence, amount exceeds threshold
        assert result.automation_tier != 1 or result.recommended_action != "auto_execute"


class TestRiskScoringServiceRedLineDetection:
    """Tests for red-line action detection."""

    @pytest.mark.parametrize("cpt_code", list(RED_LINE_CPT_CODES))
    def test_redline_cpt_requires_human_review(self, cpt_code):
        """Red-line CPT codes should require human review."""
        claim_data = {
            "payer": "Blue Cross",
            "cpt": cpt_code,
            "cpt_group": "Procedure",
            "allowed_amount": Decimal("500.00"),
        }

        result = RiskScoringService.calculate_score(claim_data)

        assert result.requires_human_review is True
        assert result.automation_tier == 3
        assert "requires" in result.red_line_reason.lower()

    def test_high_value_claim_requires_review(self):
        """Claims above $50,000 should require human review."""
        claim_data = {
            "payer": "Blue Cross",
            "cpt": "99213",
            "cpt_group": "Office Visit",
            "allowed_amount": Decimal("75000.00"),
        }

        result = RiskScoringService.calculate_score(claim_data)

        assert result.requires_human_review is True
        assert "high-value" in result.red_line_reason.lower()

    def test_non_redline_cpt_no_review_required(self):
        """Non-red-line CPT codes should not require review by default."""
        claim_data = {
            "payer": "Blue Cross",
            "cpt": "99213",  # Not in RED_LINE_CPT_CODES
            "cpt_group": "Office Visit",
            "allowed_amount": Decimal("150.00"),
        }

        result = RiskScoringService.calculate_score(claim_data)

        # Should not require review unless confidence is low
        assert result.red_line_reason == "" or result.requires_human_review is False


class TestRiskScoringServiceConfidenceCalculations:
    """Tests for individual confidence calculations."""

    def test_coding_confidence_boosted_for_mapped_cpt(self):
        """CPT codes with known groups should have higher coding confidence."""
        claim_mapped = {
            "payer": "Blue Cross",
            "cpt": "99213",
            "cpt_group": "Office Visit",
            "allowed_amount": Decimal("150.00"),
        }

        claim_unmapped = {
            "payer": "Blue Cross",
            "cpt": "99213",
            "cpt_group": "Unknown",
            "allowed_amount": Decimal("150.00"),
        }

        result_mapped = RiskScoringService.calculate_score(claim_mapped)
        result_unmapped = RiskScoringService.calculate_score(claim_unmapped)

        assert result_mapped.coding_confidence > result_unmapped.coding_confidence

    def test_eligibility_confidence_boosted_for_major_payers(self):
        """Major payers should have higher eligibility confidence."""
        claim_major = {
            "payer": "Blue Cross Blue Shield",
            "cpt": "99213",
            "cpt_group": "Office Visit",
            "allowed_amount": Decimal("150.00"),
        }

        claim_minor = {
            "payer": "Small Local Insurer XYZ",
            "cpt": "99213",
            "cpt_group": "Office Visit",
            "allowed_amount": Decimal("150.00"),
        }

        result_major = RiskScoringService.calculate_score(claim_major)
        result_minor = RiskScoringService.calculate_score(claim_minor)

        assert result_major.eligibility_confidence > result_minor.eligibility_confidence

    def test_documentation_completeness_scales_with_doc_count(self):
        """More documentation should increase completeness score."""
        claim_no_docs = {
            "payer": "Blue Cross",
            "cpt": "99213",
            "cpt_group": "Office Visit",
            "allowed_amount": Decimal("150.00"),
            "documentation_count": 0,
        }

        claim_many_docs = {
            "payer": "Blue Cross",
            "cpt": "99213",
            "cpt_group": "Office Visit",
            "allowed_amount": Decimal("150.00"),
            "documentation_count": 5,
        }

        result_no_docs = RiskScoringService.calculate_score(claim_no_docs)
        result_many_docs = RiskScoringService.calculate_score(claim_many_docs)

        assert (
            result_many_docs.documentation_completeness
            > result_no_docs.documentation_completeness
        )


class TestRiskScoringServiceFeatureImportance:
    """Tests for feature importance and explainability."""

    def test_feature_importance_sums_to_approximately_one(self):
        """Feature importance values should sum to approximately 1.0."""
        claim_data = {
            "payer": "Blue Cross",
            "cpt": "99213",
            "cpt_group": "Office Visit",
            "allowed_amount": Decimal("150.00"),
        }

        result = RiskScoringService.calculate_score(claim_data)

        total_importance = sum(result.feature_importance.values())
        assert total_importance == pytest.approx(1.0, abs=0.05)

    def test_feature_importance_has_payer_history(self):
        """Feature importance should include payer_history."""
        claim_data = {
            "payer": "Blue Cross",
            "cpt": "99213",
            "cpt_group": "Office Visit",
            "allowed_amount": Decimal("150.00"),
        }

        baseline_data = {
            "denial_rate": 0.10,
            "sample_size": 500,
            "confidence_score": 0.90,
        }

        result = RiskScoringService.calculate_score(claim_data, baseline_data)

        assert "payer_history" in result.feature_importance

    def test_prediction_reasoning_contains_confidence_level(self):
        """Prediction reasoning should mention confidence level."""
        claim_data = {
            "payer": "Blue Cross",
            "cpt": "99213",
            "cpt_group": "Office Visit",
            "allowed_amount": Decimal("150.00"),
        }

        result = RiskScoringService.calculate_score(claim_data)

        assert "confidence" in result.prediction_reasoning.lower()


class TestRiskScoringServiceLookupMethods:
    """Tests for database lookup methods."""

    @pytest.mark.django_db
    def test_lookup_baseline_returns_none_when_not_found(self):
        """lookup_baseline should return None when no baseline exists."""
        result = RiskScoringService.lookup_baseline(
            customer_id=99999,  # Non-existent
            payer="Unknown Payer",
            cpt="99999",
        )

        assert result is None

    @pytest.mark.django_db
    def test_get_profile_thresholds_returns_none_when_not_found(self):
        """get_profile_thresholds should return None when no profile exists."""
        result = RiskScoringService.get_profile_thresholds(customer_id=99999)

        assert result is None


class TestRiskScoringServiceEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_claim_data(self):
        """Should handle empty claim data gracefully."""
        claim_data = {}

        result = RiskScoringService.calculate_score(claim_data)

        assert isinstance(result, ScoringResult)
        assert 0.0 <= result.overall_confidence <= 1.0

    def test_none_allowed_amount(self):
        """Should handle None allowed_amount."""
        claim_data = {
            "payer": "Blue Cross",
            "cpt": "99213",
            "cpt_group": "Office Visit",
            "allowed_amount": None,
        }

        result = RiskScoringService.calculate_score(claim_data)

        assert isinstance(result, ScoringResult)
        # Should not crash and should give valid output

    def test_string_allowed_amount(self):
        """Should handle string allowed_amount (converted to Decimal)."""
        claim_data = {
            "payer": "Blue Cross",
            "cpt": "99213",
            "cpt_group": "Office Visit",
            "allowed_amount": "150.00",
        }

        result = RiskScoringService.calculate_score(claim_data)

        assert isinstance(result, ScoringResult)

    def test_negative_baseline_values_clamped(self):
        """Negative baseline values should be handled gracefully."""
        claim_data = {
            "payer": "Blue Cross",
            "cpt": "99213",
            "cpt_group": "Office Visit",
            "allowed_amount": Decimal("150.00"),
        }

        # Invalid but shouldn't crash
        baseline_data = {
            "denial_rate": -0.5,
            "sample_size": -10,
            "confidence_score": -0.5,
        }

        result = RiskScoringService.calculate_score(claim_data, baseline_data)

        # Risk should be clamped to valid range
        assert 0.0 <= result.denial_risk_score <= 1.0

    def test_very_high_amount_fraud_risk(self):
        """Very high amounts should increase fraud risk."""
        claim_data = {
            "payer": "Blue Cross",
            "cpt": "99213",
            "cpt_group": "Office Visit",
            "allowed_amount": Decimal("1000000.00"),  # $1M
        }

        result = RiskScoringService.calculate_score(claim_data)

        # Should have elevated fraud risk
        assert result.fraud_risk_score > 0.2

    def test_e_m_codes_boost_confidence(self):
        """E&M codes (99xxx) should get confidence boost."""
        claim_em = {
            "payer": "Blue Cross",
            "cpt": "99214",
            "cpt_group": "Office Visit",
            "allowed_amount": Decimal("150.00"),
        }

        claim_procedure = {
            "payer": "Blue Cross",
            "cpt": "27447",  # Knee replacement
            "cpt_group": "Surgery",
            "allowed_amount": Decimal("150.00"),
        }

        result_em = RiskScoringService.calculate_score(claim_em)
        result_proc = RiskScoringService.calculate_score(claim_procedure)

        # E&M should have higher coding confidence
        assert result_em.coding_confidence >= result_proc.coding_confidence


class TestRiskScoringServiceWeights:
    """Tests for confidence weight configuration."""

    def test_confidence_weights_sum_to_one(self):
        """CONFIDENCE_WEIGHTS should sum to exactly 1.0."""
        total = sum(CONFIDENCE_WEIGHTS.values())
        assert total == pytest.approx(1.0)

    def test_all_weight_categories_present(self):
        """All required weight categories should be present."""
        required = ["coding", "eligibility", "medical_necessity", "documentation"]
        for category in required:
            assert category in CONFIDENCE_WEIGHTS
