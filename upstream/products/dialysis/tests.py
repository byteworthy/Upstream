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
