"""
Tests for Dialysis specialty module.

Story #1: Create DialysisMABaseline model for Medicare baselines.
Story #4: Write tests for DialysisMAService (to be implemented).
"""
from decimal import Decimal
from datetime import date

from django.test import TestCase
from django.db import IntegrityError, connection

from upstream.products.dialysis.models import DialysisMABaseline


class DialysisMABaselineModelTest(TestCase):
    """Tests for DialysisMABaseline model creation and validation."""

    def test_create_baseline(self):
        """Test basic creation of a dialysis MA baseline."""
        baseline = DialysisMABaseline.objects.create(
            cpt="90935",
            average_payment=Decimal("250.00"),
            sample_size=1000,
            last_updated=date(2025, 1, 15),
        )
        self.assertEqual(baseline.cpt, "90935")
        self.assertEqual(baseline.average_payment, Decimal("250.00"))
        self.assertEqual(baseline.sample_size, 1000)
        self.assertEqual(baseline.last_updated, date(2025, 1, 15))

    def test_str_representation(self):
        """Test string representation of baseline."""
        baseline = DialysisMABaseline.objects.create(
            cpt="90937",
            average_payment=Decimal("450.50"),
            sample_size=500,
            last_updated=date(2025, 1, 15),
        )
        expected = "CPT 90937: $450.50 (n=500)"
        self.assertEqual(str(baseline), expected)

    def test_unique_cpt_constraint(self):
        """Test that CPT codes must be unique."""
        DialysisMABaseline.objects.create(
            cpt="90935",
            average_payment=Decimal("250.00"),
            sample_size=1000,
            last_updated=date(2025, 1, 15),
        )

        with self.assertRaises(IntegrityError):
            DialysisMABaseline.objects.create(
                cpt="90935",
                average_payment=Decimal("275.00"),
                sample_size=500,
                last_updated=date(2025, 2, 1),
            )

    def test_average_payment_positive_constraint(self):
        """Test that average_payment must be non-negative."""
        with self.assertRaises(IntegrityError):
            DialysisMABaseline.objects.create(
                cpt="90935",
                average_payment=Decimal("-10.00"),
                sample_size=100,
                last_updated=date(2025, 1, 15),
            )

    def test_sample_size_positive_constraint(self):
        """Test that sample_size must be at least 1."""
        with self.assertRaises(IntegrityError):
            DialysisMABaseline.objects.create(
                cpt="90935",
                average_payment=Decimal("250.00"),
                sample_size=0,
                last_updated=date(2025, 1, 15),
            )

    def test_auto_timestamps(self):
        """Test that created_at and updated_at are automatically set."""
        baseline = DialysisMABaseline.objects.create(
            cpt="90935",
            average_payment=Decimal("250.00"),
            sample_size=1000,
            last_updated=date(2025, 1, 15),
        )
        self.assertIsNotNone(baseline.created_at)
        self.assertIsNotNone(baseline.updated_at)


class DialysisMABaselineIndexTest(TestCase):
    """Test that DialysisMABaseline has the correct indexes."""

    def test_cpt_index_exists(self):
        """Verify that dialysis_ma_baseline_cpt_idx exists."""
        table_name = DialysisMABaseline._meta.db_table

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT name FROM sqlite_master " "WHERE type='index' AND tbl_name=%s",
                [table_name],
            )
            indexes = [row[0] for row in cursor.fetchall()]

        self.assertIn(
            "dialysis_ma_baseline_cpt_idx",
            indexes,
            f"CPT index not found. Available indexes: {indexes}",
        )

    def test_cpt_field_is_indexed(self):
        """Verify cpt field has db_index=True."""
        cpt_field = DialysisMABaseline._meta.get_field("cpt")
        self.assertTrue(cpt_field.db_index, "CPT field should have db_index=True")


class DialysisMABaselineQueryTest(TestCase):
    """Test querying DialysisMABaseline data."""

    def setUp(self):
        """Set up test baselines."""
        self.baseline1 = DialysisMABaseline.objects.create(
            cpt="90935",
            average_payment=Decimal("250.00"),
            sample_size=1000,
            last_updated=date(2025, 1, 15),
        )
        self.baseline2 = DialysisMABaseline.objects.create(
            cpt="90937",
            average_payment=Decimal("450.50"),
            sample_size=800,
            last_updated=date(2025, 1, 20),
        )
        self.baseline3 = DialysisMABaseline.objects.create(
            cpt="90940",
            average_payment=Decimal("175.25"),
            sample_size=1500,
            last_updated=date(2025, 1, 10),
        )

    def test_lookup_by_cpt(self):
        """Test looking up baseline by CPT code."""
        baseline = DialysisMABaseline.objects.get(cpt="90937")
        self.assertEqual(baseline.average_payment, Decimal("450.50"))

    def test_filter_by_sample_size(self):
        """Test filtering baselines by sample size."""
        large_samples = DialysisMABaseline.objects.filter(sample_size__gte=1000)
        self.assertEqual(large_samples.count(), 2)

    def test_ordering_by_cpt(self):
        """Test default ordering is by CPT code."""
        baselines = list(DialysisMABaseline.objects.all())
        cpts = [b.cpt for b in baselines]
        self.assertEqual(cpts, sorted(cpts))


# =============================================================================
# Story #4: DialysisMAService Tests
# =============================================================================


class MockClaim:
    """Mock claim object for testing DialysisMAService."""

    def __init__(self, cpt, paid_amount, customer=None, id=1):
        self.cpt = cpt
        self.paid_amount = paid_amount
        self.customer = customer
        self.id = id


class DialysisMAServiceVarianceTest(TestCase):
    """Test DialysisMAService variance detection."""

    def setUp(self):
        """Set up test baselines."""
        from upstream.products.dialysis.services import DialysisMAService

        self.baseline = DialysisMABaseline.objects.create(
            cpt="90935",
            average_payment=Decimal("250.00"),
            sample_size=1000,
            last_updated=date(2025, 1, 15),
        )
        self.service = DialysisMAService()

    def test_no_variance_at_full_payment(self):
        """Test no variance when payment equals baseline."""
        claim = MockClaim(cpt="90935", paid_amount=Decimal("250.00"))
        result = self.service.detect_variance(claim)

        self.assertFalse(result.has_variance)
        self.assertEqual(result.ratio, Decimal("1"))
        self.assertEqual(result.severity, "none")

    def test_no_variance_above_threshold(self):
        """Test no variance when payment is above 85% threshold."""
        claim = MockClaim(cpt="90935", paid_amount=Decimal("225.00"))  # 90%
        result = self.service.detect_variance(claim)

        self.assertFalse(result.has_variance)
        self.assertEqual(result.ratio, Decimal("0.9"))

    def test_variance_at_84_percent(self):
        """Test variance detected when payment is at 84%."""
        claim = MockClaim(cpt="90935", paid_amount=Decimal("210.00"))  # 84%
        result = self.service.detect_variance(claim)

        self.assertTrue(result.has_variance)
        self.assertEqual(result.ratio, Decimal("0.84"))
        self.assertEqual(result.severity, "warning")

    def test_critical_variance_at_69_percent(self):
        """Test critical severity when payment is below 70%."""
        claim = MockClaim(cpt="90935", paid_amount=Decimal("172.50"))  # 69%
        result = self.service.detect_variance(claim)

        self.assertTrue(result.has_variance)
        self.assertEqual(result.ratio, Decimal("0.69"))
        self.assertEqual(result.severity, "critical")

    def test_variance_at_exactly_85_percent(self):
        """Test edge case at exactly 85% threshold."""
        claim = MockClaim(cpt="90935", paid_amount=Decimal("212.50"))  # 85%
        result = self.service.detect_variance(claim)

        self.assertFalse(result.has_variance)
        self.assertEqual(result.ratio, Decimal("0.85"))

    def test_variance_just_below_85_percent(self):
        """Test detection just below 85% threshold."""
        claim = MockClaim(cpt="90935", paid_amount=Decimal("212.00"))  # 84.8%
        result = self.service.detect_variance(claim)

        self.assertTrue(result.has_variance)
        self.assertEqual(result.severity, "warning")


class DialysisMAServiceMissingBaselineTest(TestCase):
    """Test DialysisMAService handling of missing baselines."""

    def setUp(self):
        """Set up service."""
        from upstream.products.dialysis.services import DialysisMAService

        self.service = DialysisMAService()

    def test_missing_cpt_baseline(self):
        """Test graceful handling when no baseline exists for CPT."""
        claim = MockClaim(cpt="99999", paid_amount=Decimal("100.00"))
        result = self.service.detect_variance(claim)

        self.assertFalse(result.has_variance)
        self.assertIn("No baseline found", result.message)

    def test_missing_cpt_on_claim(self):
        """Test handling when claim has no CPT."""
        claim = MockClaim(cpt=None, paid_amount=Decimal("100.00"))
        result = self.service.detect_variance(claim)

        self.assertFalse(result.has_variance)
        self.assertIn("missing CPT", result.message)

    def test_missing_paid_amount(self):
        """Test handling when claim has no paid amount."""
        claim = MockClaim(cpt="90935", paid_amount=None)
        result = self.service.detect_variance(claim)

        self.assertFalse(result.has_variance)
        self.assertIn("missing paid amount", result.message)


class DialysisMAServiceRevenueLossTest(TestCase):
    """Test DialysisMAService projected annual revenue loss calculation."""

    def setUp(self):
        """Set up test baselines."""
        from upstream.products.dialysis.services import DialysisMAService

        self.baseline = DialysisMABaseline.objects.create(
            cpt="90935",
            average_payment=Decimal("250.00"),
            sample_size=1000,
            last_updated=date(2025, 1, 15),
        )
        self.service = DialysisMAService()

    def test_revenue_loss_calculation(self):
        """Test projected annual revenue loss calculation."""
        # Claim at 80% = $200, variance = $50
        # Annual: 156 treatments * $50 = $7,800
        claim = MockClaim(cpt="90935", paid_amount=Decimal("200.00"))
        result = self.service.detect_variance(claim)

        self.assertTrue(result.has_variance)
        self.assertEqual(result.variance_amount, Decimal("50.00"))
        self.assertEqual(result.projected_annual_loss, Decimal("7800.00"))

    def test_no_revenue_loss_without_variance(self):
        """Test no revenue loss calculated when no variance."""
        claim = MockClaim(cpt="90935", paid_amount=Decimal("250.00"))
        result = self.service.detect_variance(claim)

        self.assertFalse(result.has_variance)
        self.assertIsNone(result.projected_annual_loss)

    def test_revenue_loss_at_critical_level(self):
        """Test revenue loss at critical variance level."""
        # Claim at 60% = $150, variance = $100
        # Annual: 156 * $100 = $15,600
        claim = MockClaim(cpt="90935", paid_amount=Decimal("150.00"))
        result = self.service.detect_variance(claim)

        self.assertTrue(result.has_variance)
        self.assertEqual(result.severity, "critical")
        self.assertEqual(result.variance_amount, Decimal("100.00"))
        self.assertEqual(result.projected_annual_loss, Decimal("15600.00"))


class DialysisMAServiceCustomThresholdTest(TestCase):
    """Test DialysisMAService with custom thresholds."""

    def setUp(self):
        """Set up test baselines."""
        self.baseline = DialysisMABaseline.objects.create(
            cpt="90935",
            average_payment=Decimal("250.00"),
            sample_size=1000,
            last_updated=date(2025, 1, 15),
        )

    def test_custom_variance_threshold(self):
        """Test using a custom variance threshold."""
        from upstream.products.dialysis.services import DialysisMAService

        # Use 90% threshold instead of 85%
        service = DialysisMAService(variance_threshold=Decimal("0.90"))
        claim = MockClaim(cpt="90935", paid_amount=Decimal("220.00"))  # 88%

        result = service.detect_variance(claim)

        self.assertTrue(result.has_variance)  # 88% < 90%

    def test_custom_high_variance_threshold(self):
        """Test using a custom high variance threshold."""
        from upstream.products.dialysis.services import DialysisMAService

        # Use 75% high threshold instead of 70%
        service = DialysisMAService(high_variance_threshold=Decimal("0.75"))
        claim = MockClaim(cpt="90935", paid_amount=Decimal("180.00"))  # 72%

        result = service.detect_variance(claim)

        self.assertTrue(result.has_variance)
        self.assertEqual(result.severity, "critical")  # 72% < 75%
