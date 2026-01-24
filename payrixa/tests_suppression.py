"""
Tests for alert suppression based on operator judgments.

Verifies that marking an alert as "noise" suppresses similar future alerts.
"""

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from payrixa.models import Customer, DriftEvent, ReportRun
from payrixa.alerts.models import AlertRule, AlertEvent, OperatorJudgment
from payrixa.alerts.services import _is_suppressed


class AlertSuppressionTest(TestCase):
    """Test alert suppression based on operator judgments."""

    def setUp(self):
        self.customer = Customer.objects.create(name="Test Hospital")
        self.operator = User.objects.create_user(username="operator1", password="testpass")

        self.report_run = ReportRun.objects.create(
            customer=self.customer,
            run_type='weekly',
            status='success'
        )

        self.alert_rule = AlertRule.objects.create(
            customer=self.customer,
            name="High Denial Rate",
            metric='severity',
            threshold_value=0.7
        )

    def test_no_suppression_for_new_alert(self):
        """New alerts with no history should not be suppressed."""
        evidence_payload = {
            'product_name': 'DriftWatch',
            'signal_type': 'DENIAL_RATE',
            'entity_label': 'BCBS',
        }

        result = _is_suppressed(self.customer, evidence_payload)
        self.assertFalse(result)

    def test_time_based_suppression(self):
        """Alerts should be suppressed within 4-hour cooldown window."""
        evidence_payload = {
            'product_name': 'DriftWatch',
            'signal_type': 'DENIAL_RATE',
            'entity_label': 'BCBS',
        }

        # Create a recent alert that was sent
        AlertEvent.objects.create(
            customer=self.customer,
            alert_rule=self.alert_rule,
            status='sent',
            notification_sent_at=timezone.now() - timedelta(hours=2),
            payload=evidence_payload
        )

        result = _is_suppressed(self.customer, evidence_payload)
        self.assertTrue(result, "Alert should be suppressed within 4-hour window")

    def test_time_based_suppression_expired(self):
        """Alerts should NOT be suppressed after 4-hour cooldown expires."""
        evidence_payload = {
            'product_name': 'DriftWatch',
            'signal_type': 'DENIAL_RATE',
            'entity_label': 'BCBS',
        }

        # Create an old alert that was sent 5 hours ago
        AlertEvent.objects.create(
            customer=self.customer,
            alert_rule=self.alert_rule,
            status='sent',
            notification_sent_at=timezone.now() - timedelta(hours=5),
            payload=evidence_payload
        )

        result = _is_suppressed(self.customer, evidence_payload)
        self.assertFalse(result, "Alert should NOT be suppressed after cooldown expires")

    def test_noise_judgment_suppression_single(self):
        """Single noise judgment should not suppress (need 2+)."""
        evidence_payload = {
            'product_name': 'DriftWatch',
            'signal_type': 'DENIAL_RATE',
            'entity_label': 'BCBS',
        }

        # Create an alert from 10 days ago
        alert_event = AlertEvent.objects.create(
            customer=self.customer,
            alert_rule=self.alert_rule,
            status='sent',
            notification_sent_at=timezone.now() - timedelta(days=10),
            created_at=timezone.now() - timedelta(days=10),
            payload=evidence_payload
        )

        # Mark it as noise
        OperatorJudgment.objects.create(
            customer=self.customer,
            alert_event=alert_event,
            operator=self.operator,
            verdict='noise',
            notes='False positive'
        )

        result = _is_suppressed(self.customer, evidence_payload)
        self.assertFalse(result, "Single noise judgment should not suppress")

    def test_noise_judgment_suppression_multiple(self):
        """Multiple noise judgments should suppress similar alerts."""
        evidence_payload = {
            'product_name': 'DriftWatch',
            'signal_type': 'DENIAL_RATE',
            'entity_label': 'BCBS',
        }

        # Create two alerts from different days, both marked as noise
        for days_ago in [10, 20]:
            alert_event = AlertEvent.objects.create(
                customer=self.customer,
                alert_rule=self.alert_rule,
                status='sent',
                notification_sent_at=timezone.now() - timedelta(days=days_ago),
                created_at=timezone.now() - timedelta(days=days_ago),
                payload=evidence_payload
            )

            OperatorJudgment.objects.create(
                customer=self.customer,
                alert_event=alert_event,
                operator=self.operator,
                verdict='noise',
                notes=f'False positive {days_ago} days ago'
            )

        result = _is_suppressed(self.customer, evidence_payload)
        self.assertTrue(result, "2+ noise judgments should suppress similar alerts")

    def test_noise_judgment_expired(self):
        """Noise judgments older than 30 days should not suppress."""
        evidence_payload = {
            'product_name': 'DriftWatch',
            'signal_type': 'DENIAL_RATE',
            'entity_label': 'BCBS',
        }

        # Create two alerts from 35 days ago, both marked as noise
        for days_ago in [35, 40]:
            alert_event = AlertEvent.objects.create(
                customer=self.customer,
                alert_rule=self.alert_rule,
                status='sent',
                notification_sent_at=timezone.now() - timedelta(days=days_ago),
                created_at=timezone.now() - timedelta(days=days_ago),
                payload=evidence_payload
            )

            # Create judgment with old created_at timestamp
            judgment = OperatorJudgment(
                customer=self.customer,
                alert_event=alert_event,
                operator=self.operator,
                verdict='noise',
                notes=f'Old false positive'
            )
            judgment.save()
            # Manually update created_at after save to bypass auto_now_add
            OperatorJudgment.objects.filter(id=judgment.id).update(
                created_at=timezone.now() - timedelta(days=days_ago)
            )

        result = _is_suppressed(self.customer, evidence_payload)
        self.assertFalse(result, "Old noise judgments (30+ days) should not suppress")

    def test_real_judgment_does_not_suppress(self):
        """Alerts marked as 'real' should not suppress future alerts."""
        evidence_payload = {
            'product_name': 'DriftWatch',
            'signal_type': 'DENIAL_RATE',
            'entity_label': 'BCBS',
        }

        # Create two alerts marked as "real"
        for days_ago in [10, 20]:
            alert_event = AlertEvent.objects.create(
                customer=self.customer,
                alert_rule=self.alert_rule,
                status='sent',
                notification_sent_at=timezone.now() - timedelta(days=days_ago),
                created_at=timezone.now() - timedelta(days=days_ago),
                payload=evidence_payload
            )

            OperatorJudgment.objects.create(
                customer=self.customer,
                alert_event=alert_event,
                operator=self.operator,
                verdict='real',
                notes='Legitimate issue'
            )

        result = _is_suppressed(self.customer, evidence_payload)
        self.assertFalse(result, "Alerts marked as 'real' should not suppress future alerts")

    def test_different_payer_not_suppressed(self):
        """Noise judgments for one payer should not suppress another payer."""
        # Mark BCBS alerts as noise
        bcbs_payload = {
            'product_name': 'DriftWatch',
            'signal_type': 'DENIAL_RATE',
            'entity_label': 'BCBS',
        }

        for days_ago in [10, 20]:
            alert_event = AlertEvent.objects.create(
                customer=self.customer,
                alert_rule=self.alert_rule,
                status='sent',
                notification_sent_at=timezone.now() - timedelta(days=days_ago),
                created_at=timezone.now() - timedelta(days=days_ago),
                payload=bcbs_payload
            )

            OperatorJudgment.objects.create(
                customer=self.customer,
                alert_event=alert_event,
                operator=self.operator,
                verdict='noise'
            )

        # Check if Aetna alerts are suppressed (they shouldn't be)
        aetna_payload = {
            'product_name': 'DriftWatch',
            'signal_type': 'DENIAL_RATE',
            'entity_label': 'Aetna',
        }

        result = _is_suppressed(self.customer, aetna_payload)
        self.assertFalse(result, "Different payer should not be suppressed")

    def test_multi_tenant_isolation(self):
        """Noise judgments from one customer should not affect another."""
        customer2 = Customer.objects.create(name="Another Hospital")

        evidence_payload = {
            'product_name': 'DriftWatch',
            'signal_type': 'DENIAL_RATE',
            'entity_label': 'BCBS',
        }

        # Create noise judgments for customer1
        for days_ago in [10, 20]:
            alert_event = AlertEvent.objects.create(
                customer=self.customer,
                alert_rule=self.alert_rule,
                status='sent',
                notification_sent_at=timezone.now() - timedelta(days=days_ago),
                created_at=timezone.now() - timedelta(days=days_ago),
                payload=evidence_payload
            )

            OperatorJudgment.objects.create(
                customer=self.customer,
                alert_event=alert_event,
                operator=self.operator,
                verdict='noise'
            )

        # Check suppression for customer2 (should not be suppressed)
        result = _is_suppressed(customer2, evidence_payload)
        self.assertFalse(result, "Customer2 should not be affected by customer1's judgments")
