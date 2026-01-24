"""
Tests for Operator Memory Loop (Phase 1).

Tests operator feedback functionality on alert events.
"""

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from decimal import Decimal

from upstream.models import Customer, DriftEvent, ReportRun
from upstream.alerts.models import AlertRule, AlertEvent, NotificationChannel, OperatorJudgment
from upstream.core.models import ProductConfig


class OperatorJudgmentModelTest(TestCase):
    """Test OperatorJudgment model creation and constraints."""

    def setUp(self):
        self.customer = Customer.objects.create(name="Test Hospital")
        self.user = User.objects.create_user(username="operator", password="testpass")

        # Create report run and drift event
        self.report_run = ReportRun.objects.create(
            customer=self.customer,
            run_type='weekly',
            status='success'
        )

        self.drift_event = DriftEvent.objects.create(
            customer=self.customer,
            report_run=self.report_run,
            payer="Test Payer",
            cpt_group="SURGERY",
            drift_type="DENIAL_RATE",
            baseline_value=0.10,
            current_value=0.25,
            delta_value=0.15,
            severity=0.8,
            confidence=0.9,
            baseline_start=timezone.now().date(),
            baseline_end=timezone.now().date(),
            current_start=timezone.now().date(),
            current_end=timezone.now().date()
        )

        # Create alert rule and event
        self.alert_rule = AlertRule.objects.create(
            customer=self.customer,
            name="High Severity Alert",
            metric="severity",
            threshold_value=0.7,
            severity="critical"
        )

        self.alert_event = AlertEvent.objects.create(
            customer=self.customer,
            alert_rule=self.alert_rule,
            drift_event=self.drift_event,
            report_run=self.report_run,
            status='pending',
            payload={}
        )

    def test_create_operator_judgment(self):
        """Test creating an operator judgment on an alert."""
        judgment = OperatorJudgment.objects.create(
            customer=self.customer,
            alert_event=self.alert_event,
            verdict='noise',
            operator=self.user,
            notes='False positive - data entry error'
        )

        self.assertEqual(judgment.verdict, 'noise')
        self.assertEqual(judgment.operator, self.user)
        self.assertEqual(judgment.alert_event, self.alert_event)

    def test_judgment_with_recovery_amount(self):
        """Test creating a judgment with recovered amount."""
        judgment = OperatorJudgment.objects.create(
            customer=self.customer,
            alert_event=self.alert_event,
            verdict='real',
            operator=self.user,
            recovered_amount=Decimal('50000.00'),
            recovered_date=timezone.now().date(),
            notes='Recovered $50K from payer appeal'
        )

        self.assertEqual(judgment.recovered_amount, Decimal('50000.00'))
        self.assertEqual(judgment.verdict, 'real')

    def test_unique_together_constraint(self):
        """Test that one operator can only judge an alert once."""
        OperatorJudgment.objects.create(
            customer=self.customer,
            alert_event=self.alert_event,
            verdict='noise',
            operator=self.user
        )

        # Attempting to create another judgment for same alert + operator should fail
        # (update_or_create pattern should be used in practice)
        with self.assertRaises(Exception):
            OperatorJudgment.objects.create(
                customer=self.customer,
                alert_event=self.alert_event,
                verdict='real',
                operator=self.user
            )


class OperatorFeedbackAPITest(TestCase):
    """Test the operator feedback API endpoint."""

    def setUp(self):
        self.customer = Customer.objects.create(name="Test Hospital")
        self.user = User.objects.create_user(username="operator", password="testpass")

        # Link user to customer via UserProfile
        from upstream.models import UserProfile
        UserProfile.objects.create(
            user=self.user,
            customer=self.customer,
            role='admin'
        )

        # Enable products
        ProductConfig.objects.create(
            customer=self.customer,
            product_slug='upstream-core',
            enabled=True
        )
        ProductConfig.objects.create(
            customer=self.customer,
            product_slug='denialscope',
            enabled=True
        )

        # Create test data
        self.report_run = ReportRun.objects.create(
            customer=self.customer,
            run_type='weekly',
            status='success'
        )

        self.drift_event = DriftEvent.objects.create(
            customer=self.customer,
            report_run=self.report_run,
            payer="Test Payer",
            cpt_group="SURGERY",
            drift_type="DENIAL_RATE",
            baseline_value=0.10,
            current_value=0.25,
            delta_value=0.15,
            severity=0.8,
            confidence=0.9,
            baseline_start=timezone.now().date(),
            baseline_end=timezone.now().date(),
            current_start=timezone.now().date(),
            current_end=timezone.now().date()
        )

        self.alert_rule = AlertRule.objects.create(
            customer=self.customer,
            name="High Severity Alert",
            metric="severity",
            threshold_value=0.7,
            severity="critical"
        )

        self.alert_event = AlertEvent.objects.create(
            customer=self.customer,
            alert_rule=self.alert_rule,
            drift_event=self.drift_event,
            report_run=self.report_run,
            status='pending',
            payload={}
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_submit_noise_verdict(self):
        """Test submitting a 'noise' verdict on an alert."""
        url = f'/api/v1/alerts/{self.alert_event.id}/feedback/'
        data = {
            'verdict': 'noise',
            'reason_codes': ['false_positive', 'data_entry_error'],
            'notes': 'This was caused by a data entry mistake'
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify judgment was created
        judgment = OperatorJudgment.objects.get(alert_event=self.alert_event)
        self.assertEqual(judgment.verdict, 'noise')
        self.assertEqual(judgment.operator, self.user)
        self.assertEqual(judgment.reason_codes_json, ['false_positive', 'data_entry_error'])

        # Verify alert status was updated
        self.alert_event.refresh_from_db()
        self.assertEqual(self.alert_event.status, 'resolved')

    def test_submit_real_verdict_with_recovery(self):
        """Test submitting a 'real' verdict with recovery amount."""
        url = f'/api/v1/alerts/{self.alert_event.id}/feedback/'
        data = {
            'verdict': 'real',
            'recovered_amount': '25000.50',
            'recovered_date': '2026-01-20',
            'notes': 'Appealed and recovered funds'
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify judgment
        judgment = OperatorJudgment.objects.get(alert_event=self.alert_event)
        self.assertEqual(judgment.verdict, 'real')
        self.assertEqual(judgment.recovered_amount, Decimal('25000.50'))

        # Verify alert status
        self.alert_event.refresh_from_db()
        self.assertEqual(self.alert_event.status, 'acknowledged')

    def test_submit_needs_followup_verdict(self):
        """Test submitting a 'needs_followup' verdict."""
        url = f'/api/v1/alerts/{self.alert_event.id}/feedback/'
        data = {
            'verdict': 'needs_followup',
            'notes': 'Needs further investigation with billing team'
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        judgment = OperatorJudgment.objects.get(alert_event=self.alert_event)
        self.assertEqual(judgment.verdict, 'needs_followup')

        # Verify alert status remains pending
        self.alert_event.refresh_from_db()
        self.assertEqual(self.alert_event.status, 'pending')

    def test_update_existing_judgment(self):
        """Test that submitting feedback twice updates the existing judgment."""
        url = f'/api/v1/alerts/{self.alert_event.id}/feedback/'

        # First submission
        data1 = {'verdict': 'noise', 'notes': 'Initial assessment'}
        response1 = self.client.post(url, data1, format='json')
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)

        # Second submission (should update, not create new)
        data2 = {'verdict': 'real', 'notes': 'Changed my mind after review'}
        response2 = self.client.post(url, data2, format='json')
        self.assertEqual(response2.status_code, status.HTTP_200_OK)

        # Verify only one judgment exists
        judgments = OperatorJudgment.objects.filter(alert_event=self.alert_event)
        self.assertEqual(judgments.count(), 1)
        self.assertEqual(judgments.first().verdict, 'real')

    def test_list_alert_events_with_judgments(self):
        """Test that alert events API includes judgment information."""
        # Create a judgment
        OperatorJudgment.objects.create(
            customer=self.customer,
            alert_event=self.alert_event,
            verdict='noise',
            operator=self.user
        )

        # Fetch alert event
        url = f'/api/v1/alerts/{self.alert_event.id}/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Verify judgment data is included
        self.assertTrue(data['has_judgment'])
        self.assertEqual(data['latest_judgment_verdict'], 'noise')
        self.assertEqual(len(data['operator_judgments']), 1)
        self.assertEqual(data['operator_judgments'][0]['verdict'], 'noise')
