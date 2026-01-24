"""
Tests for Slack integration and advanced routing functionality.
"""

from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch, MagicMock
from upstream.models import Customer, DriftEvent, ReportRun
from upstream.alerts.models import AlertRule, NotificationChannel, AlertEvent
from upstream.alerts.services import send_slack_notification, send_alert_notification


class SlackNotificationTest(TestCase):
    """Test Slack notification delivery."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.customer = Customer.objects.create(name='Test Hospital')
        
        # Create Slack notification channel
        self.slack_channel = NotificationChannel.objects.create(
            customer=self.customer,
            name='Slack Alerts',
            channel_type='slack',
            config={'webhook_url': 'https://hooks.slack.com/services/TEST/WEBHOOK'},
            enabled=True
        )
        
        # Create alert rule
        self.alert_rule = AlertRule.objects.create(
            customer=self.customer,
            name='High Severity Drift',
            metric='severity',
            threshold_type='gte',
            threshold_value=0.7,
            severity='critical',
            enabled=True
        )
        
        # Create report run and drift event
        self.report_run = ReportRun.objects.create(
            customer=self.customer,
            status='completed'
        )
        
        self.drift_event = DriftEvent.objects.create(
            customer=self.customer,
            report_run=self.report_run,
            payer='Medicare',
            cpt_group='Office Visits',
            drift_type='DENIAL_RATE',
            baseline_value=0.15,
            current_value=0.35,
            delta_value=0.20,
            severity=0.85,
            confidence=0.90,
            baseline_start=timezone.now().date() - timedelta(days=104),
            baseline_end=timezone.now().date() - timedelta(days=14),
            current_start=timezone.now().date() - timedelta(days=14),
            current_end=timezone.now().date()
        )
        
        # Create alert event
        self.alert_event = AlertEvent.objects.create(
            customer=self.customer,
            alert_rule=self.alert_rule,
            drift_event=self.drift_event,
            report_run=self.report_run,
            status='pending',
            payload={
                'payer': 'Medicare',
                'drift_type': 'DENIAL_RATE',
                'delta_value': 0.20,
                'severity': 0.85
            }
        )
    
    @override_settings(SLACK_ENABLED=True)
    @patch('requests.post')
    def test_send_slack_notification_success(self, mock_post):
        """Test successful Slack notification delivery."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        result = send_slack_notification(self.alert_event, self.slack_channel)
        
        self.assertTrue(result)
        self.assertEqual(mock_post.call_count, 1)
        
        # Verify webhook URL was called
        call_args = mock_post.call_args
        self.assertEqual(call_args[0][0], 'https://hooks.slack.com/services/TEST/WEBHOOK')
        
        # Verify payload structure
        import json
        payload = json.loads(call_args[1]['data'])
        self.assertIn('blocks', payload)
        self.assertIn('Medicare', payload['text'])
    
    @override_settings(SLACK_ENABLED=True)
    @patch('requests.post')
    def test_send_slack_notification_failure(self, mock_post):
        """Test failed Slack notification delivery."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = 'Internal Server Error'
        mock_post.return_value = mock_response
        
        result = send_slack_notification(self.alert_event, self.slack_channel)
        
        self.assertFalse(result)
    
    @override_settings(SLACK_ENABLED=True)
    def test_send_slack_notification_missing_webhook(self):
        """Test Slack notification with missing webhook URL."""
        channel_no_webhook = NotificationChannel.objects.create(
            customer=self.customer,
            name='Broken Slack',
            channel_type='slack',
            config={},  # No webhook_url
            enabled=True
        )
        
        result = send_slack_notification(self.alert_event, channel_no_webhook)
        
        self.assertFalse(result)


class AdvancedRoutingTest(TestCase):
    """Test advanced routing rules functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.customer = Customer.objects.create(name='Test Hospital')
        
        # Create multiple notification channels
        self.email_channel = NotificationChannel.objects.create(
            customer=self.customer,
            name='Email Alerts',
            channel_type='email',
            config={'recipients': ['alerts@test.com']},
            enabled=True
        )
        
        self.slack_channel = NotificationChannel.objects.create(
            customer=self.customer,
            name='Slack Alerts',
            channel_type='slack',
            config={'webhook_url': 'https://hooks.slack.com/test'},
            enabled=True
        )
        
        # Create report run
        self.report_run = ReportRun.objects.create(
            customer=self.customer,
            status='completed'
        )
    
    @override_settings(SLACK_ENABLED=True)
    @patch('requests.post')
    @patch('upstream.alerts.services._send_email_with_pdf')
    def test_routing_to_specific_channels(self, mock_email, mock_slack):
        """Test routing alert to specific channels only."""
        mock_email.return_value = True
        mock_slack_response = MagicMock()
        mock_slack_response.status_code = 200
        mock_slack.return_value = mock_slack_response
        
        # Create alert rule with specific channel routing
        alert_rule = AlertRule.objects.create(
            customer=self.customer,
            name='Slack Only Rule',
            metric='severity',
            threshold_type='gte',
            threshold_value=0.7,
            enabled=True
        )
        alert_rule.routing_channels.add(self.slack_channel)
        
        drift_event = DriftEvent.objects.create(
            customer=self.customer,
            report_run=self.report_run,
            payer='Aetna',
            cpt_group='Labs',
            drift_type='DENIAL_RATE',
            baseline_value=0.10,
            current_value=0.30,
            delta_value=0.20,
            severity=0.75,
            confidence=0.88,
            baseline_start=timezone.now().date() - timedelta(days=104),
            baseline_end=timezone.now().date() - timedelta(days=14),
            current_start=timezone.now().date() - timedelta(days=14),
            current_end=timezone.now().date()
        )
        
        alert_event = AlertEvent.objects.create(
            customer=self.customer,
            alert_rule=alert_rule,
            drift_event=drift_event,
            report_run=self.report_run,
            status='pending',
            payload={
                'payer': 'Aetna',
                'drift_type': 'DENIAL_RATE',
                'delta_value': 0.20,
                'severity': 0.75
            }
        )
        
        result = send_alert_notification(alert_event)
        
        self.assertTrue(result)
        # Email should NOT be called (only Slack)
        mock_email.assert_not_called()
        # Slack should be called
        self.assertEqual(mock_slack.call_count, 1)
    
    def test_routing_priority(self):
        """Test alert rule priority ordering."""
        # Create rules with different priorities
        rule_low = AlertRule.objects.create(
            customer=self.customer,
            name='Low Priority',
            routing_priority=0,
            enabled=True
        )
        
        rule_medium = AlertRule.objects.create(
            customer=self.customer,
            name='Medium Priority',
            routing_priority=5,
            enabled=True
        )
        
        rule_high = AlertRule.objects.create(
            customer=self.customer,
            name='High Priority',
            routing_priority=10,
            enabled=True
        )
        
        # Query rules ordered by priority
        rules = AlertRule.objects.filter(customer=self.customer).order_by('-routing_priority')
        
        self.assertEqual(rules[0].name, 'High Priority')
        self.assertEqual(rules[1].name, 'Medium Priority')
        self.assertEqual(rules[2].name, 'Low Priority')
    
    def test_routing_tags(self):
        """Test routing tags for categorization."""
        alert_rule = AlertRule.objects.create(
            customer=self.customer,
            name='Tagged Rule',
            routing_tags=['critical', 'medicare', 'denial'],
            enabled=True
        )
        
        self.assertEqual(len(alert_rule.routing_tags), 3)
        self.assertIn('critical', alert_rule.routing_tags)
        self.assertIn('medicare', alert_rule.routing_tags)
    
    def test_duplicate_alert_prevention(self):
        """Test that duplicate alerts are not created for same drift event and rule."""
        from upstream.alerts.services import evaluate_drift_event
        
        alert_rule = AlertRule.objects.create(
            customer=self.customer,
            name='Test Rule',
            metric='severity',
            threshold_type='gte',
            threshold_value=0.5,
            enabled=True
        )
        
        drift_event = DriftEvent.objects.create(
            customer=self.customer,
            report_run=self.report_run,
            payer='UHC',
            cpt_group='Surgeries',
            drift_type='DENIAL_RATE',
            baseline_value=0.10,
            current_value=0.25,
            delta_value=0.15,
            severity=0.60,
            confidence=0.85,
            baseline_start=timezone.now().date() - timedelta(days=104),
            baseline_end=timezone.now().date() - timedelta(days=14),
            current_start=timezone.now().date() - timedelta(days=14),
            current_end=timezone.now().date()
        )
        
        # First evaluation creates alert
        alert_events_1 = evaluate_drift_event(drift_event)
        self.assertEqual(len(alert_events_1), 1)
        
        # Second evaluation should NOT create duplicate
        alert_events_2 = evaluate_drift_event(drift_event)
        self.assertEqual(len(alert_events_2), 1)
        self.assertEqual(alert_events_1[0].id, alert_events_2[0].id)
        
        # Verify only one alert event exists
        total_alerts = AlertEvent.objects.filter(
            drift_event=drift_event,
            alert_rule=alert_rule
        ).count()
        self.assertEqual(total_alerts, 1)
