"""
Tests for test fixture factories.

These tests verify that the fixture factories in test_fixtures.py work correctly
and can be used to create test data for automation models.
"""

from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from upstream.test_fixtures import TenantTestMixin
from upstream.automation.models import (
    ClaimScore,
    CustomerAutomationProfile,
    ShadowModeResult,
)


class TestClaimScoreFactory(TenantTestMixin, TestCase):
    """Tests for the create_claim_score fixture factory."""

    def setUp(self):
        super().setUp()
        self.customer = self.create_customer("Test Hospital")

    def test_create_claim_score_with_defaults(self):
        """Test creating a ClaimScore with default values."""
        score = self.create_claim_score(customer=self.customer)

        self.assertIsNotNone(score)
        self.assertIsInstance(score, ClaimScore)
        self.assertEqual(score.customer, self.customer)
        self.assertEqual(score.overall_confidence, 0.85)
        self.assertEqual(score.recommended_action, "queue_review")
        self.assertEqual(score.automation_tier, 2)

    def test_create_claim_score_with_custom_values(self):
        """Test creating a ClaimScore with custom confidence values."""
        score = self.create_claim_score(
            customer=self.customer,
            overall_confidence=0.98,
            recommended_action="auto_execute",
            automation_tier=1,
        )

        self.assertEqual(score.overall_confidence, 0.98)
        self.assertEqual(score.recommended_action, "auto_execute")
        self.assertEqual(score.automation_tier, 1)

    def test_create_claim_score_creates_claim_if_not_provided(self):
        """Test that a claim is created automatically if not provided."""
        score = self.create_claim_score(customer=self.customer)

        self.assertIsNotNone(score.claim)
        self.assertEqual(score.claim.customer, self.customer)

    def test_create_claim_score_with_existing_claim(self):
        """Test creating a ClaimScore with an existing claim."""
        # Create an upload first (required for claims)
        upload = self.create_upload(self.customer)
        claims = self.create_claims(self.customer, count=1, upload=upload)
        claim = claims[0]

        score = self.create_claim_score(customer=self.customer, claim=claim)

        self.assertEqual(score.claim, claim)

    def test_create_claim_score_with_risk_scores(self):
        """Test creating a ClaimScore with custom risk scores."""
        score = self.create_claim_score(
            customer=self.customer,
            denial_risk_score=0.80,
            fraud_risk_score=0.75,
            compliance_risk_score=0.50,
        )

        self.assertEqual(score.denial_risk_score, 0.80)
        self.assertEqual(score.fraud_risk_score, 0.75)
        self.assertEqual(score.compliance_risk_score, 0.50)

    def test_create_claim_score_with_human_review_required(self):
        """Test creating a ClaimScore requiring human review."""
        score = self.create_claim_score(
            customer=self.customer,
            requires_human_review=True,
            red_line_reason="Medical necessity determination required",
        )

        self.assertTrue(score.requires_human_review)
        self.assertEqual(
            score.red_line_reason, "Medical necessity determination required"
        )


class TestCustomerAutomationProfileFactory(TenantTestMixin, TestCase):
    """Tests for the create_automation_profile fixture factory."""

    def setUp(self):
        super().setUp()
        self.customer = self.create_customer("Test Hospital")

    def test_create_automation_profile_with_defaults(self):
        """Test creating a CustomerAutomationProfile with default values."""
        profile = self.create_automation_profile(customer=self.customer)

        self.assertIsNotNone(profile)
        self.assertIsInstance(profile, CustomerAutomationProfile)
        self.assertEqual(profile.customer, self.customer)
        self.assertEqual(profile.automation_stage, "observe")
        self.assertEqual(profile.auto_execute_confidence, 0.95)
        self.assertEqual(profile.auto_execute_max_amount, Decimal("1000.00"))
        self.assertTrue(profile.shadow_mode_enabled)

    def test_create_automation_profile_with_custom_stage(self):
        """Test creating a profile with different automation stages."""
        for stage in ["observe", "suggest", "act_notify", "full_autonomy"]:
            # Use a new customer for each iteration to avoid unique constraint
            customer = self.create_customer(f"Hospital {stage}")
            profile = self.create_automation_profile(
                customer=customer, automation_stage=stage
            )
            self.assertEqual(profile.automation_stage, stage)

    def test_create_automation_profile_with_custom_thresholds(self):
        """Test creating a profile with custom confidence thresholds."""
        profile = self.create_automation_profile(
            customer=self.customer,
            auto_execute_confidence=0.99,
            queue_review_min_confidence=0.80,
            auto_execute_max_amount=Decimal("500.00"),
        )

        self.assertEqual(profile.auto_execute_confidence, 0.99)
        self.assertEqual(profile.queue_review_min_confidence, 0.80)
        self.assertEqual(profile.auto_execute_max_amount, Decimal("500.00"))

    def test_create_automation_profile_shadow_mode_disabled(self):
        """Test creating a profile with shadow mode disabled."""
        profile = self.create_automation_profile(
            customer=self.customer, shadow_mode_enabled=False
        )

        self.assertFalse(profile.shadow_mode_enabled)


class TestShadowModeResultFactory(TenantTestMixin, TestCase):
    """Tests for the create_shadow_result fixture factory."""

    def setUp(self):
        super().setUp()
        self.customer = self.create_customer("Test Hospital")

    def test_create_shadow_result_with_defaults(self):
        """Test creating a ShadowModeResult with default values."""
        result = self.create_shadow_result(customer=self.customer)

        self.assertIsNotNone(result)
        self.assertIsInstance(result, ShadowModeResult)
        self.assertEqual(result.customer, self.customer)
        self.assertEqual(result.ai_recommended_action, "queue_review")
        self.assertEqual(result.human_action_taken, "queue_review")
        self.assertTrue(result.actions_match)
        self.assertEqual(result.outcome, "true_positive")

    def test_create_shadow_result_with_matching_actions(self):
        """Test creating a ShadowModeResult where AI and human agree."""
        result = self.create_shadow_result(
            customer=self.customer,
            ai_recommended_action="auto_execute",
            human_action_taken="auto_execute",
            actions_match=True,
            outcome="true_positive",
        )

        self.assertTrue(result.actions_match)
        self.assertEqual(result.ai_recommended_action, result.human_action_taken)

    def test_create_shadow_result_with_mismatching_actions(self):
        """Test creating a ShadowModeResult where AI and human disagree."""
        result = self.create_shadow_result(
            customer=self.customer,
            ai_recommended_action="auto_execute",
            human_action_taken="escalate",
            actions_match=False,
            outcome="false_positive",
        )

        self.assertFalse(result.actions_match)
        self.assertNotEqual(result.ai_recommended_action, result.human_action_taken)
        self.assertIn("discrepancy", result.discrepancy_reason.lower())

    def test_create_shadow_result_creates_claim_score_if_not_provided(self):
        """Test that a claim_score is created automatically if not provided."""
        result = self.create_shadow_result(customer=self.customer)

        self.assertIsNotNone(result.claim_score)
        self.assertEqual(result.claim_score.customer, self.customer)

    def test_create_shadow_result_with_existing_claim_score(self):
        """Test creating a ShadowModeResult with an existing ClaimScore."""
        score = self.create_claim_score(
            customer=self.customer,
            overall_confidence=0.92,
            recommended_action="auto_execute",
        )

        result = self.create_shadow_result(
            customer=self.customer,
            claim_score=score,
            ai_recommended_action="auto_execute",
            ai_confidence=0.92,
        )

        self.assertEqual(result.claim_score, score)
        self.assertEqual(result.ai_confidence, 0.92)

    def test_create_shadow_result_creates_human_user_if_not_provided(self):
        """Test that a human decision user is created if not provided."""
        result = self.create_shadow_result(customer=self.customer)

        self.assertIsNotNone(result.human_decision_user)


class TestAutomationFixtureIntegration(TenantTestMixin, TestCase):
    """Integration tests for automation fixtures working together."""

    def setUp(self):
        super().setUp()
        self.customer = self.create_customer("Test Hospital")
        self.user = self.create_user(self.customer, username="reviewer")

    def test_full_automation_workflow(self):
        """Test creating a complete automation workflow with fixtures."""
        # Create automation profile
        profile = self.create_automation_profile(
            customer=self.customer,
            automation_stage="suggest",
            shadow_mode_enabled=True,
        )

        # Create claims and scores (upload required for claims)
        upload = self.create_upload(self.customer)
        claims = self.create_claims(self.customer, count=3, upload=upload)
        scores = []
        for claim in claims:
            score = self.create_claim_score(
                customer=self.customer,
                claim=claim,
                overall_confidence=0.88,
            )
            scores.append(score)

        # Create shadow results
        for score in scores:
            self.create_shadow_result(
                customer=self.customer,
                claim_score=score,
                human_decision_user=self.user,
                ai_recommended_action=score.recommended_action,
                human_action_taken=score.recommended_action,
                actions_match=True,
            )

        # Verify all data was created
        self.assertEqual(
            ClaimScore.objects.filter(customer=self.customer).count(), 3
        )
        self.assertEqual(
            ShadowModeResult.objects.filter(customer=self.customer).count(), 3
        )
        self.assertEqual(
            CustomerAutomationProfile.objects.filter(customer=self.customer).count(),
            1,
        )

    def test_shadow_mode_accuracy_calculation(self):
        """Test fixtures support shadow mode accuracy calculation."""
        # Create profile
        self.create_automation_profile(customer=self.customer)

        # Create 10 shadow results: 8 match, 2 don't
        for i in range(10):
            actions_match = i < 8  # First 8 match
            self.create_shadow_result(
                customer=self.customer,
                human_decision_user=self.user,  # Reuse the same user
                ai_recommended_action="queue_review",
                human_action_taken="queue_review" if actions_match else "escalate",
                actions_match=actions_match,
                outcome="true_positive" if actions_match else "false_negative",
            )

        # Calculate accuracy
        total = ShadowModeResult.objects.filter(customer=self.customer).count()
        matches = ShadowModeResult.objects.filter(
            customer=self.customer, actions_match=True
        ).count()
        accuracy = matches / total

        self.assertEqual(total, 10)
        self.assertEqual(matches, 8)
        self.assertEqual(accuracy, 0.8)

    def test_tier_routing_with_fixtures(self):
        """Test that fixtures can create claims for each tier."""
        # Tier 1: High confidence, auto-execute
        tier1_score = self.create_claim_score(
            customer=self.customer,
            overall_confidence=0.98,
            recommended_action="auto_execute",
            automation_tier=1,
        )
        self.assertEqual(tier1_score.automation_tier, 1)

        # Tier 2: Moderate confidence, queue for review
        tier2_score = self.create_claim_score(
            customer=self.customer,
            overall_confidence=0.80,
            recommended_action="queue_review",
            automation_tier=2,
        )
        self.assertEqual(tier2_score.automation_tier, 2)

        # Tier 3: Low confidence or requires escalation
        tier3_score = self.create_claim_score(
            customer=self.customer,
            overall_confidence=0.50,
            recommended_action="escalate",
            automation_tier=3,
        )
        self.assertEqual(tier3_score.automation_tier, 3)
