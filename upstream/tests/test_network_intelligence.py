"""
Unit tests for Cross-Customer Network Intelligence Service.

Tests the compute_cross_customer_patterns function that detects
patterns across multiple customers to identify payer-wide changes.
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
    NetworkAlert,
    ReportRun,
    Upload,
    UserProfile,
)
from upstream.services.network_intelligence import (
    NETWORK_ALERT_LOOKBACK_DAYS,
    NETWORK_ALERT_MIN_CUSTOMERS,
    compute_cross_customer_patterns,
    get_active_network_alerts,
    resolve_network_alert,
)


class NetworkIntelligenceDetectionTests(TestCase):
    """Tests for cross-customer pattern detection."""

    def setUp(self):
        # Create multiple customers to test cross-customer detection
        self.customers = []
        self.report_runs = []
        for i in range(5):
            customer = Customer.objects.create(name=f"Test Customer {i}")
            self.customers.append(customer)
            report_run = ReportRun.objects.create(
                customer=customer,
                run_type="weekly",
                status="success",
            )
            self.report_runs.append(report_run)

    def _create_drift_event(
        self,
        customer,
        report_run,
        payer,
        drift_type,
        delta_value=0.15,
        severity=0.6,
        days_ago=0,
    ):
        """Helper to create drift events for testing."""
        created_at = timezone.now() - timedelta(days=days_ago)
        as_of_date = created_at.date()

        event = DriftEvent.all_objects.create(
            customer=customer,
            report_run=report_run,
            payer=payer,
            cpt_group="ALL",
            drift_type=drift_type,
            baseline_value=0.10,
            current_value=0.25,
            delta_value=delta_value,
            severity=severity,
            confidence=0.85,
            baseline_start=as_of_date - timedelta(days=14),
            baseline_end=as_of_date - timedelta(days=4),
            current_start=as_of_date - timedelta(days=3),
            current_end=as_of_date,
        )
        # Manually update created_at to override auto_now_add
        if days_ago > 0:
            DriftEvent.all_objects.filter(id=event.id).update(created_at=created_at)
            event.refresh_from_db()
        return event

    def test_detects_cross_customer_pattern(self):
        """
        Detects when 3+ customers have the same drift pattern with a payer.
        """
        payer = "Aetna"
        drift_type = "DENIAL_RATE"

        # Create drift events for 4 customers with the same payer/drift_type
        for i in range(4):
            self._create_drift_event(
                customer=self.customers[i],
                report_run=self.report_runs[i],
                payer=payer,
                drift_type=drift_type,
                delta_value=0.15 + (i * 0.01),  # Slight variation
                severity=0.6 + (i * 0.05),
            )

        # Run network intelligence
        alerts = compute_cross_customer_patterns()

        # Should create one NetworkAlert
        self.assertEqual(len(alerts), 1)

        alert = alerts[0]
        self.assertEqual(alert.payer, payer)
        self.assertEqual(alert.drift_type, drift_type)
        self.assertEqual(alert.affected_customer_count, 4)
        self.assertIn("customer_ids", alert.details)
        self.assertEqual(len(alert.details["customer_ids"]), 4)

    def test_no_alert_below_threshold(self):
        """
        No alert created when fewer than 3 customers are affected.
        """
        payer = "Blue Cross"
        drift_type = "DENIAL_RATE"

        # Create drift events for only 2 customers
        for i in range(2):
            self._create_drift_event(
                customer=self.customers[i],
                report_run=self.report_runs[i],
                payer=payer,
                drift_type=drift_type,
            )

        # Run network intelligence
        alerts = compute_cross_customer_patterns()

        # Should not create any alerts
        self.assertEqual(len(alerts), 0)

    def test_separate_alerts_for_different_drift_types(self):
        """
        Creates separate alerts for same payer with different drift types.
        """
        payer = "UnitedHealthcare"

        # Create DENIAL_RATE drift for 3 customers
        for i in range(3):
            self._create_drift_event(
                customer=self.customers[i],
                report_run=self.report_runs[i],
                payer=payer,
                drift_type="DENIAL_RATE",
            )

        # Create DECISION_TIME drift for 3 different customers (overlapping)
        for i in range(3):
            self._create_drift_event(
                customer=self.customers[i + 1],  # Offset by 1
                report_run=self.report_runs[i + 1],
                payer=payer,
                drift_type="DECISION_TIME",
            )

        # Run network intelligence
        alerts = compute_cross_customer_patterns()

        # Should create 2 separate alerts
        self.assertEqual(len(alerts), 2)

        drift_types = {a.drift_type for a in alerts}
        self.assertEqual(drift_types, {"DENIAL_RATE", "DECISION_TIME"})

    def test_separate_alerts_for_different_payers(self):
        """
        Creates separate alerts for different payers with same drift type.
        """
        drift_type = "DENIAL_RATE"

        # Create drift for Aetna across 3 customers
        for i in range(3):
            self._create_drift_event(
                customer=self.customers[i],
                report_run=self.report_runs[i],
                payer="Aetna",
                drift_type=drift_type,
            )

        # Create drift for Cigna across 3 customers
        for i in range(3):
            self._create_drift_event(
                customer=self.customers[i],
                report_run=self.report_runs[i],
                payer="Cigna",
                drift_type=drift_type,
            )

        # Run network intelligence
        alerts = compute_cross_customer_patterns()

        # Should create 2 separate alerts
        self.assertEqual(len(alerts), 2)

        payers = {a.payer for a in alerts}
        self.assertEqual(payers, {"Aetna", "Cigna"})

    def test_ignores_old_drift_events(self):
        """
        Ignores drift events outside the lookback window.
        """
        payer = "Humana"
        drift_type = "DENIAL_RATE"

        # Create drift events that are 10 days old (outside default 7-day window)
        for i in range(4):
            self._create_drift_event(
                customer=self.customers[i],
                report_run=self.report_runs[i],
                payer=payer,
                drift_type=drift_type,
                days_ago=10,
            )

        # Run network intelligence
        alerts = compute_cross_customer_patterns()

        # Should not create any alerts (events too old)
        self.assertEqual(len(alerts), 0)

    def test_includes_events_within_lookback(self):
        """
        Includes drift events within the lookback window.
        """
        payer = "Kaiser"
        drift_type = "DENIAL_RATE"

        # Create drift events 5 days ago (within 7-day window)
        for i in range(3):
            self._create_drift_event(
                customer=self.customers[i],
                report_run=self.report_runs[i],
                payer=payer,
                drift_type=drift_type,
                days_ago=5,
            )

        # Run network intelligence
        alerts = compute_cross_customer_patterns()

        # Should create alert
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].payer, payer)

    def test_ignores_suppressed_drift_events(self):
        """
        Ignores drift events that have been suppressed.
        """
        payer = "Molina"
        drift_type = "DENIAL_RATE"

        # Create drift events and mark them as suppressed
        for i in range(4):
            event = self._create_drift_event(
                customer=self.customers[i],
                report_run=self.report_runs[i],
                payer=payer,
                drift_type=drift_type,
            )
            event.suppressed = True
            event.save()

        # Run network intelligence
        alerts = compute_cross_customer_patterns()

        # Should not create any alerts (all events suppressed)
        self.assertEqual(len(alerts), 0)


class NetworkAlertSeverityTests(TestCase):
    """Tests for network alert severity calculation."""

    def setUp(self):
        self.customers = []
        self.report_runs = []
        for i in range(12):
            customer = Customer.objects.create(name=f"Severity Test Customer {i}")
            self.customers.append(customer)
            report_run = ReportRun.objects.create(
                customer=customer,
                run_type="weekly",
                status="success",
            )
            self.report_runs.append(report_run)

    def _create_drift_event(self, customer, report_run, payer, severity=0.5):
        """Helper to create drift events."""
        as_of_date = timezone.now().date()
        return DriftEvent.all_objects.create(
            customer=customer,
            report_run=report_run,
            payer=payer,
            cpt_group="ALL",
            drift_type="DENIAL_RATE",
            baseline_value=0.10,
            current_value=0.25,
            delta_value=0.15,
            severity=severity,
            confidence=0.85,
            baseline_start=as_of_date - timedelta(days=14),
            baseline_end=as_of_date - timedelta(days=4),
            current_start=as_of_date - timedelta(days=3),
            current_end=as_of_date,
        )

    def test_critical_severity_high_customer_count(self):
        """
        CRITICAL severity when 10+ customers affected.
        """
        payer = "Critical Payer"
        # Create events for 10 customers
        for i in range(10):
            self._create_drift_event(
                customer=self.customers[i],
                report_run=self.report_runs[i],
                payer=payer,
                severity=0.5,  # Medium severity individually
            )

        alerts = compute_cross_customer_patterns()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].severity, "CRITICAL")

    def test_critical_severity_high_individual_severity(self):
        """
        CRITICAL severity when max individual severity >= 0.9.
        """
        payer = "High Sev Payer"
        for i in range(3):
            self._create_drift_event(
                customer=self.customers[i],
                report_run=self.report_runs[i],
                payer=payer,
                severity=0.95,  # Very high individual severity
            )

        alerts = compute_cross_customer_patterns()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].severity, "CRITICAL")

    def test_high_severity(self):
        """
        HIGH severity when 7-9 customers affected.
        """
        payer = "High Payer"
        for i in range(7):
            self._create_drift_event(
                customer=self.customers[i],
                report_run=self.report_runs[i],
                payer=payer,
                severity=0.5,
            )

        alerts = compute_cross_customer_patterns()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].severity, "HIGH")

    def test_medium_severity(self):
        """
        MEDIUM severity when 5-6 customers affected.
        """
        payer = "Medium Payer"
        for i in range(5):
            self._create_drift_event(
                customer=self.customers[i],
                report_run=self.report_runs[i],
                payer=payer,
                severity=0.4,
            )

        alerts = compute_cross_customer_patterns()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].severity, "MEDIUM")

    def test_low_severity(self):
        """
        LOW severity when 3-4 customers affected with low individual severity.
        """
        payer = "Low Payer"
        for i in range(3):
            self._create_drift_event(
                customer=self.customers[i],
                report_run=self.report_runs[i],
                payer=payer,
                severity=0.3,  # Low individual severity
            )

        alerts = compute_cross_customer_patterns()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].severity, "LOW")


class NetworkAlertSummaryTests(TestCase):
    """Tests for network alert summary text generation."""

    def setUp(self):
        self.customers = []
        self.report_runs = []
        for i in range(5):
            customer = Customer.objects.create(name=f"Summary Test Customer {i}")
            self.customers.append(customer)
            report_run = ReportRun.objects.create(
                customer=customer,
                run_type="weekly",
                status="success",
            )
            self.report_runs.append(report_run)

    def _create_drift_event(self, customer, report_run, payer, drift_type, delta_value):
        """Helper to create drift events."""
        as_of_date = timezone.now().date()
        return DriftEvent.all_objects.create(
            customer=customer,
            report_run=report_run,
            payer=payer,
            cpt_group="ALL",
            drift_type=drift_type,
            baseline_value=0.10,
            current_value=0.10 + delta_value,
            delta_value=delta_value,
            severity=0.6,
            confidence=0.85,
            baseline_start=as_of_date - timedelta(days=14),
            baseline_end=as_of_date - timedelta(days=4),
            current_start=as_of_date - timedelta(days=3),
            current_end=as_of_date,
        )

    def test_summary_contains_payer_name(self):
        """Summary text includes the payer name."""
        payer = "Aetna"
        for i in range(3):
            self._create_drift_event(
                customer=self.customers[i],
                report_run=self.report_runs[i],
                payer=payer,
                drift_type="DENIAL_RATE",
                delta_value=0.15,
            )

        alerts = compute_cross_customer_patterns()
        self.assertEqual(len(alerts), 1)
        self.assertIn(payer, alerts[0].summary_text)

    def test_summary_contains_customer_count(self):
        """Summary text includes the affected customer count."""
        for i in range(4):
            self._create_drift_event(
                customer=self.customers[i],
                report_run=self.report_runs[i],
                payer="Test Payer",
                drift_type="DENIAL_RATE",
                delta_value=0.15,
            )

        alerts = compute_cross_customer_patterns()
        self.assertEqual(len(alerts), 1)
        self.assertIn("4 customers", alerts[0].summary_text)

    def test_summary_indicates_increase(self):
        """Summary text indicates increase for positive delta."""
        for i in range(3):
            self._create_drift_event(
                customer=self.customers[i],
                report_run=self.report_runs[i],
                payer="Increase Payer",
                drift_type="DENIAL_RATE",
                delta_value=0.20,  # Positive
            )

        alerts = compute_cross_customer_patterns()
        self.assertEqual(len(alerts), 1)
        self.assertIn("increase", alerts[0].summary_text)

    def test_summary_indicates_decrease(self):
        """Summary text indicates decrease for negative delta."""
        for i in range(3):
            self._create_drift_event(
                customer=self.customers[i],
                report_run=self.report_runs[i],
                payer="Decrease Payer",
                drift_type="DENIAL_RATE",
                delta_value=-0.15,  # Negative
            )

        alerts = compute_cross_customer_patterns()
        self.assertEqual(len(alerts), 1)
        self.assertIn("decrease", alerts[0].summary_text)


class NetworkAlertDetailsTests(TestCase):
    """Tests for network alert details JSON population."""

    def setUp(self):
        self.customers = []
        self.report_runs = []
        for i in range(5):
            customer = Customer.objects.create(name=f"Details Test Customer {i}")
            self.customers.append(customer)
            report_run = ReportRun.objects.create(
                customer=customer,
                run_type="weekly",
                status="success",
            )
            self.report_runs.append(report_run)

    def _create_drift_event(self, customer, report_run):
        """Helper to create drift events."""
        as_of_date = timezone.now().date()
        return DriftEvent.all_objects.create(
            customer=customer,
            report_run=report_run,
            payer="Details Payer",
            cpt_group="ALL",
            drift_type="DENIAL_RATE",
            baseline_value=0.10,
            current_value=0.25,
            delta_value=0.15,
            severity=0.6,
            confidence=0.85,
            baseline_start=as_of_date - timedelta(days=14),
            baseline_end=as_of_date - timedelta(days=4),
            current_start=as_of_date - timedelta(days=3),
            current_end=as_of_date,
        )

    def test_details_contains_customer_ids(self):
        """Details JSON contains list of affected customer IDs."""
        for i in range(3):
            self._create_drift_event(
                customer=self.customers[i],
                report_run=self.report_runs[i],
            )

        alerts = compute_cross_customer_patterns()
        self.assertEqual(len(alerts), 1)

        details = alerts[0].details
        self.assertIn("customer_ids", details)
        self.assertEqual(len(details["customer_ids"]), 3)
        # Verify actual customer IDs are present
        expected_ids = {c.id for c in self.customers[:3]}
        actual_ids = set(details["customer_ids"])
        self.assertEqual(expected_ids, actual_ids)

    def test_details_contains_avg_delta(self):
        """Details JSON contains average delta value."""
        for i in range(3):
            self._create_drift_event(
                customer=self.customers[i],
                report_run=self.report_runs[i],
            )

        alerts = compute_cross_customer_patterns()
        self.assertEqual(len(alerts), 1)

        details = alerts[0].details
        self.assertIn("avg_delta", details)
        self.assertIsInstance(details["avg_delta"], float)

    def test_details_contains_date_range(self):
        """Details JSON contains date range information."""
        for i in range(3):
            self._create_drift_event(
                customer=self.customers[i],
                report_run=self.report_runs[i],
            )

        alerts = compute_cross_customer_patterns()
        self.assertEqual(len(alerts), 1)

        details = alerts[0].details
        self.assertIn("date_range", details)
        self.assertIn("start", details["date_range"])
        self.assertIn("end", details["date_range"])


class NetworkAlertQueryTests(TestCase):
    """Tests for get_active_network_alerts function."""

    def setUp(self):
        # Create some network alerts directly
        self.alert1 = NetworkAlert.objects.create(
            payer="Aetna",
            drift_type="DENIAL_RATE",
            affected_customer_count=5,
            summary_text="Test alert 1",
            severity="HIGH",
            details={"customer_ids": [1, 2, 3, 4, 5]},
        )
        self.alert2 = NetworkAlert.objects.create(
            payer="Cigna",
            drift_type="DECISION_TIME",
            affected_customer_count=3,
            summary_text="Test alert 2",
            severity="LOW",
            details={"customer_ids": [1, 2, 3]},
        )
        self.resolved_alert = NetworkAlert.objects.create(
            payer="UnitedHealthcare",
            drift_type="DENIAL_RATE",
            affected_customer_count=4,
            summary_text="Resolved alert",
            severity="MEDIUM",
            details={"customer_ids": [1, 2, 3, 4]},
            resolved_at=timezone.now(),
        )

    def test_get_all_active_alerts(self):
        """Returns all active (unresolved) alerts."""
        alerts = get_active_network_alerts()
        self.assertEqual(len(alerts), 2)
        # Resolved alert should not be included
        alert_ids = {a.id for a in alerts}
        self.assertNotIn(self.resolved_alert.id, alert_ids)

    def test_filter_by_payer(self):
        """Filters alerts by payer name."""
        alerts = get_active_network_alerts(payer="Aetna")
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].payer, "Aetna")

    def test_filter_by_drift_type(self):
        """Filters alerts by drift type."""
        alerts = get_active_network_alerts(drift_type="DECISION_TIME")
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].drift_type, "DECISION_TIME")

    def test_filter_by_min_severity(self):
        """Filters alerts by minimum severity level."""
        alerts = get_active_network_alerts(min_severity="HIGH")
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].severity, "HIGH")


class NetworkAlertResolutionTests(TestCase):
    """Tests for resolve_network_alert function."""

    def setUp(self):
        self.alert = NetworkAlert.objects.create(
            payer="Test Payer",
            drift_type="DENIAL_RATE",
            affected_customer_count=3,
            summary_text="Test alert",
            severity="MEDIUM",
            details={"customer_ids": [1, 2, 3]},
        )

    def test_resolve_active_alert(self):
        """Successfully resolves an active alert."""
        result = resolve_network_alert(self.alert.id)
        self.assertTrue(result)

        # Verify alert is resolved
        self.alert.refresh_from_db()
        self.assertIsNotNone(self.alert.resolved_at)

    def test_resolve_already_resolved_alert(self):
        """Returns False for already resolved alert."""
        # First resolve it
        self.alert.resolved_at = timezone.now()
        self.alert.save()

        # Try to resolve again
        result = resolve_network_alert(self.alert.id)
        self.assertFalse(result)

    def test_resolve_nonexistent_alert(self):
        """Returns False for non-existent alert ID."""
        result = resolve_network_alert(99999)
        self.assertFalse(result)


class NetworkIntelligenceConstantsTests(TestCase):
    """Tests for network intelligence constants."""

    def test_default_constants_defined(self):
        """Verify default constants are defined with expected values."""
        self.assertEqual(NETWORK_ALERT_MIN_CUSTOMERS, 3)
        self.assertEqual(NETWORK_ALERT_LOOKBACK_DAYS, 7)
