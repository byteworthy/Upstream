"""
Unit tests for Behavioral Prediction Engine.

Tests the compute_behavioral_prediction function that detects
denial rate changes using day-3 detection (comparing last 3 days
vs previous 14 days per payer).
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from upstream.models import (
    ClaimRecord,
    Customer,
    DriftEvent,
    Upload,
    UserProfile,
)
from upstream.services.behavioral_prediction import (
    BEHAVIORAL_BASELINE_DAYS,
    BEHAVIORAL_CURRENT_DAYS,
    BEHAVIORAL_MIN_VOLUME,
    BEHAVIORAL_RATE_CHANGE_THRESHOLD,
    compute_behavioral_prediction,
)


class BehavioralPredictionDetectionTests(TestCase):
    """Tests for behavioral prediction detection of denial increases."""

    def setUp(self):
        self.customer = Customer.objects.create(name="Behavioral Test Customer")
        self.user = User.objects.create_user(
            username="behavioral_user", password="pass"
        )
        UserProfile.objects.create(user=self.user, customer=self.customer, role="admin")

        self.upload = Upload.all_objects.create(
            customer=self.customer, filename="behavioral_claims.csv", status="success"
        )

        # Pre-calculate date windows that match engine behavior EXACTLY
        # Engine uses: submitted_date >= start AND submitted_date < end
        self.as_of_date = timezone.now().date()
        self.current_days = BEHAVIORAL_CURRENT_DAYS  # 3
        self.baseline_days = BEHAVIORAL_BASELINE_DAYS  # 14

        # Engine's current window calculation:
        # current_start = as_of_date - timedelta(days=current_days)
        # current_end = as_of_date
        # Filter: submitted_date >= current_start AND submitted_date < current_end
        self.current_start = self.as_of_date - timedelta(days=self.current_days)
        self.current_end = self.as_of_date - timedelta(days=1)  # Exclusive upper bound

        # Engine's baseline window calculation:
        # baseline_start = current_start - timedelta(days=baseline_days)
        # baseline_end = current_start
        # Filter: submitted_date >= baseline_start AND submitted_date < baseline_end
        self.baseline_start = self.current_start - timedelta(days=self.baseline_days)
        self.baseline_end = self.current_start - timedelta(
            days=1
        )  # Exclusive upper bound

    def _create_claim_on_date(self, payer, outcome, submitted_date):
        """Helper to create claims for behavioral testing on specific date."""
        decided_date = submitted_date + timedelta(days=1)
        return ClaimRecord.all_objects.create(
            customer=self.customer,
            upload=self.upload,
            payer=payer,
            cpt="99213",
            cpt_group="E&M",
            submitted_date=submitted_date,
            decided_date=decided_date,
            outcome=outcome,
            allowed_amount=Decimal("100.00"),
        )

    def _create_claims_in_window(
        self, payer, start_date, end_date, paid_count, denied_count
    ):
        """Create claims evenly distributed across a date window."""
        days = (end_date - start_date).days + 1
        total = paid_count + denied_count
        claims = []

        for i in range(total):
            day_offset = i % days
            submitted_date = start_date + timedelta(days=day_offset)
            outcome = "DENIED" if i < denied_count else "PAID"
            claims.append(self._create_claim_on_date(payer, outcome, submitted_date))

        return claims

    def test_detects_significant_denial_increase(self):
        """
        Detects when denial rate increases significantly from baseline.

        Baseline: 10% denial rate (14 denied, 126 paid = 140 total)
        Current: 50% denial rate (15 denied, 15 paid = 30 total)
        Rate change: +40% (significantly exceeds 5% threshold)
        """
        payer = "Aetna"

        # Create baseline claims: 10% denial rate
        self._create_claims_in_window(
            payer,
            self.baseline_start,
            self.baseline_end,
            paid_count=126,
            denied_count=14,  # 10% of 140
        )

        # Create current claims: 50% denial rate
        self._create_claims_in_window(
            payer,
            self.current_start,
            self.current_end,
            paid_count=15,
            denied_count=15,  # 50% of 30
        )

        # Run behavioral prediction
        report_run = compute_behavioral_prediction(
            customer=self.customer,
            min_volume=10,
        )

        # Assert report succeeded
        self.assertEqual(report_run.status, "success")

        # Assert DriftEvent was created with BEHAVIORAL_PREDICTION type
        events = DriftEvent.all_objects.filter(
            customer=self.customer,
            drift_type="BEHAVIORAL_PREDICTION",
            payer=payer,
        )
        self.assertEqual(
            events.count(), 1, f"Expected 1 event, summary: {report_run.summary_json}"
        )

        event = events.first()
        # Baseline should be ~10% (0.1)
        self.assertAlmostEqual(event.baseline_value, 0.10, delta=0.05)
        # Current should be ~50% (0.5)
        self.assertAlmostEqual(event.current_value, 0.50, delta=0.05)
        # Delta should be positive (increase)
        self.assertGreater(event.delta_value, 0.35)
        # Trend should be degrading (higher denial rate is worse)
        self.assertEqual(event.trend_direction, "degrading")

    def test_no_false_positive_when_stable(self):
        """
        No alert when denial rates are stable (no significant change).

        Baseline and current both have ~20% denial rate.
        """
        payer = "UnitedHealthcare"

        # Create baseline claims: 20% denial rate
        self._create_claims_in_window(
            payer,
            self.baseline_start,
            self.baseline_end,
            paid_count=80,
            denied_count=20,  # 20% of 100
        )

        # Create current claims: same 20% denial rate
        self._create_claims_in_window(
            payer,
            self.current_start,
            self.current_end,
            paid_count=24,
            denied_count=6,  # 20% of 30
        )

        # Run behavioral prediction
        report_run = compute_behavioral_prediction(
            customer=self.customer,
            min_volume=10,
        )

        # Assert report succeeded
        self.assertEqual(report_run.status, "success")

        # Assert no DriftEvent was created (stable rates)
        events = DriftEvent.all_objects.filter(
            customer=self.customer,
            drift_type="BEHAVIORAL_PREDICTION",
            payer=payer,
        )
        self.assertEqual(events.count(), 0)

    def test_respects_min_volume_threshold(self):
        """
        Skips analysis for payers below minimum volume threshold.
        """
        payer = "Small Payer"

        # Create only 5 claims in baseline (below threshold of 10)
        self._create_claims_in_window(
            payer,
            self.baseline_start,
            self.baseline_end,
            paid_count=5,
            denied_count=0,
        )

        # Create 5 claims in current (below threshold)
        self._create_claims_in_window(
            payer,
            self.current_start,
            self.current_end,
            paid_count=0,
            denied_count=5,
        )

        # Run behavioral prediction with min_volume=10
        report_run = compute_behavioral_prediction(
            customer=self.customer,
            min_volume=10,
        )

        # Assert report succeeded
        self.assertEqual(report_run.status, "success")

        # Assert no DriftEvent created (below volume threshold)
        events = DriftEvent.all_objects.filter(
            customer=self.customer,
            drift_type="BEHAVIORAL_PREDICTION",
        )
        self.assertEqual(events.count(), 0)

        # Summary should show 0 payers analyzed
        self.assertEqual(report_run.summary_json["payers_analyzed"], 0)

    def test_drift_event_fields_populated_correctly(self):
        """
        Verifies all DriftEvent fields are correctly populated.
        """
        payer = "Cigna"

        # Create claims with significant rate change
        # Baseline: 5% denial rate
        self._create_claims_in_window(
            payer,
            self.baseline_start,
            self.baseline_end,
            paid_count=190,
            denied_count=10,  # 5% of 200
        )

        # Current: 30% denial rate
        self._create_claims_in_window(
            payer,
            self.current_start,
            self.current_end,
            paid_count=21,
            denied_count=9,  # 30% of 30
        )

        report_run = compute_behavioral_prediction(
            customer=self.customer,
            min_volume=10,
        )

        events = DriftEvent.all_objects.filter(
            customer=self.customer,
            drift_type="BEHAVIORAL_PREDICTION",
        )
        self.assertEqual(
            events.count(), 1, f"Expected 1 event, summary: {report_run.summary_json}"
        )

        event = events.first()

        # Check required fields
        self.assertEqual(event.payer, payer)
        self.assertEqual(event.cpt_group, "ALL")  # Payer-level analysis
        self.assertEqual(event.drift_type, "BEHAVIORAL_PREDICTION")

        # Severity should be between 0 and 1
        self.assertGreaterEqual(event.severity, 0.0)
        self.assertLessEqual(event.severity, 1.0)

        # Confidence should be between 0 and 1
        self.assertGreaterEqual(event.confidence, 0.0)
        self.assertLessEqual(event.confidence, 1.0)

        # Sample sizes should be populated
        self.assertGreater(event.baseline_sample_size, 0)
        self.assertGreater(event.current_sample_size, 0)

        # Statistical significance should be populated (p-value)
        self.assertIsNotNone(event.statistical_significance)
        self.assertLess(event.statistical_significance, 0.05)

        # Date windows should be set
        self.assertIsNotNone(event.baseline_start)
        self.assertIsNotNone(event.baseline_end)
        self.assertIsNotNone(event.current_start)
        self.assertIsNotNone(event.current_end)

    def test_detects_denial_rate_decrease(self):
        """
        Also detects significant decreases (improving trend).
        """
        payer = "Humana"

        # Baseline: 50% denial rate
        self._create_claims_in_window(
            payer,
            self.baseline_start,
            self.baseline_end,
            paid_count=50,
            denied_count=50,  # 50% of 100
        )

        # Current: 10% denial rate (improvement)
        self._create_claims_in_window(
            payer,
            self.current_start,
            self.current_end,
            paid_count=27,
            denied_count=3,  # 10% of 30
        )

        report_run = compute_behavioral_prediction(
            customer=self.customer,
            min_volume=10,
        )

        events = DriftEvent.all_objects.filter(
            customer=self.customer,
            drift_type="BEHAVIORAL_PREDICTION",
            payer=payer,
        )
        self.assertEqual(
            events.count(), 1, f"Expected 1 event, summary: {report_run.summary_json}"
        )

        event = events.first()
        # Delta should be negative (decrease)
        self.assertLess(event.delta_value, -0.3)
        # Trend should be improving
        self.assertEqual(event.trend_direction, "improving")


class BehavioralPredictionConstantsTests(TestCase):
    """Tests for behavioral prediction constants and configuration."""

    def test_default_constants_are_defined(self):
        """Verify default constants are defined with expected values."""
        self.assertEqual(BEHAVIORAL_BASELINE_DAYS, 14)
        self.assertEqual(BEHAVIORAL_CURRENT_DAYS, 3)
        self.assertEqual(BEHAVIORAL_MIN_VOLUME, 10)
        self.assertEqual(BEHAVIORAL_RATE_CHANGE_THRESHOLD, 0.05)


class BehavioralPredictionReportRunTests(TestCase):
    """Tests for ReportRun creation and summary."""

    def setUp(self):
        self.customer = Customer.objects.create(name="Report Test Customer")

    def test_creates_report_run_with_correct_type(self):
        """Report run is created with custom type (behavioral uses custom)."""
        report_run = compute_behavioral_prediction(customer=self.customer)

        # Behavioral prediction uses 'custom' type since it's not in REPORT_TYPE_CHOICES
        self.assertEqual(report_run.run_type, "custom")
        self.assertEqual(report_run.status, "success")
        self.assertIsNotNone(report_run.finished_at)

    def test_summary_json_contains_parameters(self):
        """Summary JSON contains all parameters used."""
        report_run = compute_behavioral_prediction(
            customer=self.customer,
            baseline_days=7,
            current_days=2,
            min_volume=5,
            rate_change_threshold=0.10,
        )

        summary = report_run.summary_json
        self.assertEqual(summary["parameters"]["baseline_days"], 7)
        self.assertEqual(summary["parameters"]["current_days"], 2)
        self.assertEqual(summary["parameters"]["min_volume"], 5)
        self.assertEqual(summary["parameters"]["rate_change_threshold"], 0.10)

    def test_summary_includes_date_windows(self):
        """Summary includes baseline and current date windows."""
        report_run = compute_behavioral_prediction(customer=self.customer)

        summary = report_run.summary_json
        self.assertIn("baseline_start", summary)
        self.assertIn("baseline_end", summary)
        self.assertIn("current_start", summary)
        self.assertIn("current_end", summary)
