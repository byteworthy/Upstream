"""
Tests for Dialysis MA Variance Detection

Comprehensive tests for DialysisMAService including:
- Variance detection at various payment ratios
- Alert creation with correct severity
- Revenue loss calculation
- Handling of missing baselines
"""

from decimal import Decimal
from django.test import TestCase

from upstream.models import Customer
from .models import DialysisMABaseline
from .services import DialysisMAService, VarianceResult
from .constants import (
    is_ma_payer,
    get_severity_for_ratio,
    VARIANCE_THRESHOLD,
    HIGH_VARIANCE_THRESHOLD,
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    SEVERITY_MEDIUM,
)


class DialysisConstantsTests(TestCase):
    """Tests for dialysis constants and helper functions."""

    def test_is_ma_payer_positive_cases(self):
        """Test MA payer detection with known MA payers."""
        ma_payers = [
            "Humana Medicare Advantage",
            "UnitedHealthcare Medicare",
            "Aetna Medicare HMO",
            "WellCare Health Plans",
            "Centene Medicare",
            "UHC Medicare Complete",
        ]
        for payer in ma_payers:
            with self.subTest(payer=payer):
                self.assertTrue(is_ma_payer(payer), f"{payer} should be detected as MA")

    def test_is_ma_payer_negative_cases(self):
        """Test MA payer detection excludes non-MA payers."""
        non_ma_payers = [
            "Traditional Medicare",
            "Medicare FFS",
            "Blue Cross Commercial",
            "Cigna Commercial",
            "Self Pay",
            "",
            None,
        ]
        for payer in non_ma_payers:
            with self.subTest(payer=payer):
                self.assertFalse(is_ma_payer(payer), f"{payer} should not be detected as MA")

    def test_get_severity_for_ratio_critical(self):
        """Test critical severity for very low ratios."""
        self.assertEqual(get_severity_for_ratio(0.40), SEVERITY_CRITICAL)
        self.assertEqual(get_severity_for_ratio(0.30), SEVERITY_CRITICAL)
        self.assertEqual(get_severity_for_ratio(0.49), SEVERITY_CRITICAL)

    def test_get_severity_for_ratio_high(self):
        """Test high severity for ratios below 70%."""
        self.assertEqual(get_severity_for_ratio(0.50), SEVERITY_HIGH)
        self.assertEqual(get_severity_for_ratio(0.60), SEVERITY_HIGH)
        self.assertEqual(get_severity_for_ratio(0.69), SEVERITY_HIGH)

    def test_get_severity_for_ratio_medium(self):
        """Test medium severity for ratios below 85%."""
        self.assertEqual(get_severity_for_ratio(0.70), SEVERITY_MEDIUM)
        self.assertEqual(get_severity_for_ratio(0.75), SEVERITY_MEDIUM)
        self.assertEqual(get_severity_for_ratio(0.84), SEVERITY_MEDIUM)

    def test_get_severity_for_ratio_no_alert(self):
        """Test no alert for acceptable ratios."""
        self.assertIsNone(get_severity_for_ratio(0.85))
        self.assertIsNone(get_severity_for_ratio(0.90))
        self.assertIsNone(get_severity_for_ratio(1.00))
        self.assertIsNone(get_severity_for_ratio(1.10))


class DialysisMABaselineTests(TestCase):
    """Tests for DialysisMABaseline model."""

    def test_create_baseline(self):
        """Test creating a baseline record."""
        baseline = DialysisMABaseline.objects.create(
            cpt="90935",
            average_payment=Decimal("250.00"),
            sample_size=100,
        )
        self.assertEqual(baseline.cpt, "90935")
        self.assertEqual(baseline.average_payment, Decimal("250.00"))
        self.assertEqual(baseline.sample_size, 100)
        self.assertIsNotNone(baseline.created_at)
        self.assertIsNotNone(baseline.last_updated)

    def test_baseline_unique_cpt(self):
        """Test that CPT codes must be unique."""
        DialysisMABaseline.objects.create(
            cpt="90935",
            average_payment=Decimal("250.00"),
            sample_size=100,
        )
        with self.assertRaises(Exception):  # IntegrityError
            DialysisMABaseline.objects.create(
                cpt="90935",
                average_payment=Decimal("300.00"),
                sample_size=50,
            )

    def test_baseline_str_representation(self):
        """Test string representation of baseline."""
        baseline = DialysisMABaseline.objects.create(
            cpt="90935",
            average_payment=Decimal("250.00"),
            sample_size=100,
        )
        self.assertIn("90935", str(baseline))
        self.assertIn("250", str(baseline))


class DialysisMAServiceTests(TestCase):
    """Tests for DialysisMAService variance detection."""

    def setUp(self):
        """Set up test data."""
        self.baseline = DialysisMABaseline.objects.create(
            cpt="90935",
            average_payment=Decimal("250.00"),
            sample_size=100,
        )
        self.customer = Customer.objects.create(name="Test Dialysis Clinic")

    def test_detect_variance_no_variance(self):
        """Test no variance when payment meets threshold."""
        claim_data = {
            "payer": "Humana Medicare Advantage",
            "cpt": "90935",
            "paid_amount": Decimal("250.00"),  # 100% of baseline
        }
        result = DialysisMAService.detect_variance(claim_data)
        self.assertFalse(result.has_variance)
        self.assertEqual(result.ratio, 1.0)

    def test_detect_variance_at_threshold(self):
        """Test no variance at exactly 85% threshold."""
        claim_data = {
            "payer": "Humana Medicare Advantage",
            "cpt": "90935",
            "paid_amount": Decimal("212.50"),  # 85% of baseline
        }
        result = DialysisMAService.detect_variance(claim_data)
        self.assertFalse(result.has_variance)
        self.assertAlmostEqual(result.ratio, 0.85, places=2)

    def test_detect_variance_medium_severity(self):
        """Test medium severity variance detection."""
        claim_data = {
            "payer": "Humana Medicare Advantage",
            "cpt": "90935",
            "paid_amount": Decimal("200.00"),  # 80% of baseline
        }
        result = DialysisMAService.detect_variance(claim_data)
        self.assertTrue(result.has_variance)
        self.assertEqual(result.severity, SEVERITY_MEDIUM)
        self.assertAlmostEqual(result.ratio, 0.80, places=2)
        self.assertEqual(result.variance_amount, Decimal("50.00"))

    def test_detect_variance_high_severity(self):
        """Test high severity variance detection."""
        claim_data = {
            "payer": "UnitedHealthcare Medicare",
            "cpt": "90935",
            "paid_amount": Decimal("150.00"),  # 60% of baseline
        }
        result = DialysisMAService.detect_variance(claim_data)
        self.assertTrue(result.has_variance)
        self.assertEqual(result.severity, SEVERITY_HIGH)
        self.assertAlmostEqual(result.ratio, 0.60, places=2)

    def test_detect_variance_critical_severity(self):
        """Test critical severity variance detection."""
        claim_data = {
            "payer": "Aetna Medicare",
            "cpt": "90935",
            "paid_amount": Decimal("100.00"),  # 40% of baseline
        }
        result = DialysisMAService.detect_variance(claim_data)
        self.assertTrue(result.has_variance)
        self.assertEqual(result.severity, SEVERITY_CRITICAL)
        self.assertAlmostEqual(result.ratio, 0.40, places=2)

    def test_detect_variance_non_ma_payer(self):
        """Test that non-MA payers don't trigger variance check."""
        claim_data = {
            "payer": "Blue Cross Commercial",
            "cpt": "90935",
            "paid_amount": Decimal("100.00"),
        }
        result = DialysisMAService.detect_variance(claim_data)
        self.assertFalse(result.has_variance)
        self.assertIn("Not an MA payer", result.message)

    def test_detect_variance_missing_baseline(self):
        """Test graceful handling of missing baseline."""
        claim_data = {
            "payer": "Humana Medicare Advantage",
            "cpt": "99999",  # Non-existent CPT
            "paid_amount": Decimal("100.00"),
        }
        result = DialysisMAService.detect_variance(claim_data)
        self.assertFalse(result.has_variance)
        self.assertIn("No Medicare baseline", result.message)

    def test_detect_variance_missing_paid_amount(self):
        """Test handling of missing paid amount."""
        claim_data = {
            "payer": "Humana Medicare Advantage",
            "cpt": "90935",
            "paid_amount": None,
        }
        result = DialysisMAService.detect_variance(claim_data)
        self.assertFalse(result.has_variance)
        self.assertIn("No paid amount", result.message)

    def test_detect_variance_zero_paid_amount(self):
        """Test handling of zero paid amount."""
        claim_data = {
            "payer": "Humana Medicare Advantage",
            "cpt": "90935",
            "paid_amount": Decimal("0.00"),
        }
        result = DialysisMAService.detect_variance(claim_data)
        self.assertFalse(result.has_variance)
        self.assertIn("zero or negative", result.message)

    def test_detect_variance_multiple_procedures(self):
        """Test variance detection with multiple procedures."""
        claim_data = {
            "payer": "Humana Medicare Advantage",
            "cpt": "90935",
            "paid_amount": Decimal("400.00"),  # 80% of 500 (250 * 2)
            "procedure_count": 2,
        }
        result = DialysisMAService.detect_variance(claim_data)
        self.assertTrue(result.has_variance)
        self.assertEqual(result.baseline_amount, Decimal("500.00"))
        self.assertAlmostEqual(result.ratio, 0.80, places=2)

    def test_projected_annual_loss_calculation(self):
        """Test that annual loss projection is calculated correctly."""
        claim_data = {
            "payer": "Humana Medicare Advantage",
            "cpt": "90935",
            "paid_amount": Decimal("200.00"),  # $50 variance
        }
        result = DialysisMAService.detect_variance(claim_data)
        self.assertTrue(result.has_variance)
        # $50 variance * 12 months = $600 annual loss
        self.assertEqual(result.projected_annual_loss, Decimal("600.00"))

    def test_calculate_revenue_impact(self):
        """Test aggregate revenue impact calculation."""
        results = [
            VarianceResult(
                has_variance=True,
                variance_amount=Decimal("50.00"),
                ratio=0.80,
            ),
            VarianceResult(
                has_variance=True,
                variance_amount=Decimal("100.00"),
                ratio=0.60,
            ),
            VarianceResult(
                has_variance=False,
                variance_amount=None,
            ),
        ]
        impact = DialysisMAService.calculate_revenue_impact(results)
        self.assertEqual(impact["total_variance"], Decimal("150.00"))
        self.assertEqual(impact["claims_with_variance"], 2)
        self.assertEqual(impact["average_variance"], Decimal("75.00"))

    def test_get_specialty_risk_factor_no_variance(self):
        """Test risk factor is 0 when no variance."""
        claim_data = {
            "payer": "Traditional Medicare",
            "cpt": "90935",
            "paid_amount": Decimal("250.00"),
        }
        risk = DialysisMAService.get_specialty_risk_factor(claim_data)
        self.assertEqual(risk, 0.0)

    def test_get_specialty_risk_factor_critical(self):
        """Test risk factor for critical variance."""
        claim_data = {
            "payer": "Humana Medicare Advantage",
            "cpt": "90935",
            "paid_amount": Decimal("100.00"),  # 40% - CRITICAL
        }
        risk = DialysisMAService.get_specialty_risk_factor(claim_data)
        self.assertEqual(risk, 0.9)

    def test_get_specialty_risk_factor_high(self):
        """Test risk factor for high variance."""
        claim_data = {
            "payer": "Humana Medicare Advantage",
            "cpt": "90935",
            "paid_amount": Decimal("150.00"),  # 60% - HIGH
        }
        risk = DialysisMAService.get_specialty_risk_factor(claim_data)
        self.assertEqual(risk, 0.7)


class DialysisMAServiceAlertTests(TestCase):
    """Tests for alert creation functionality."""

    def setUp(self):
        """Set up test data."""
        self.baseline = DialysisMABaseline.objects.create(
            cpt="90935",
            average_payment=Decimal("250.00"),
            sample_size=100,
        )
        self.customer = Customer.objects.create(name="Test Dialysis Clinic")

    def test_create_variance_alert(self):
        """Test alert creation for detected variance."""
        from upstream.models import ClaimRecord, Upload

        # Create minimal upload and claim for testing
        upload = Upload.objects.create(
            customer=self.customer,
            filename="test.csv",
            status="success",
        )
        claim = ClaimRecord.objects.create(
            customer=self.customer,
            upload=upload,
            payer="Humana Medicare Advantage",
            cpt="90935",
            cpt_group="Dialysis",
            submitted_date="2026-01-01",
            decided_date="2026-01-15",
            outcome="PAID",
            paid_amount=Decimal("200.00"),
        )

        # Detect variance and create alert
        variance_result = DialysisMAService.detect_variance({
            "payer": claim.payer,
            "cpt": claim.cpt,
            "paid_amount": claim.paid_amount,
        })

        alert = DialysisMAService.create_variance_alert(
            claim=claim,
            variance_result=variance_result,
            customer=self.customer,
        )

        self.assertIsNotNone(alert)
        self.assertEqual(alert.customer, self.customer)
        self.assertEqual(alert.status, "pending")
        self.assertEqual(alert.payload["claim_id"], claim.id)
        self.assertEqual(alert.payload["alert_type"], "dialysis_ma_variance")

    def test_no_alert_when_no_variance(self):
        """Test no alert is created when there's no variance."""
        variance_result = VarianceResult(
            has_variance=False,
            message="No variance"
        )

        alert = DialysisMAService.create_variance_alert(
            claim=None,
            variance_result=variance_result,
            customer=self.customer,
        )

        self.assertIsNone(alert)
