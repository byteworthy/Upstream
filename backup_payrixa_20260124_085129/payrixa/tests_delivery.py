"""
Tests for alert and webhook delivery completion.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.core import mail
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch, Mock
import json

from upstream.models import Customer, DriftEvent, ReportRun
from upstream.alerts.models import AlertRule, AlertEvent, NotificationChannel
from upstream.alerts.services import evaluate_drift_event, send_alert_notification, process_pending_alerts
from upstream.integrations.models import WebhookEndpoint, WebhookDelivery
from upstream.integrations.services import generate_signature, deliver_webhook, process_pending_deliveries
from upstream.core.models import DomainAuditEvent


class AlertDeliveryTests(TestCase):
    """Tests for alert evaluation and delivery."""
    
    def setUp(self):
        self.customer = Customer.objects.create(name='Test Customer')
        self.user = User.objects.create_user(username='testuser', password='testpass')
        
        # Create a report run with summary_json
        self.report_run = ReportRun.objects.create(
            customer=self.customer,
            run_type='weekly',
            status='success',
            summary_json={
                'baseline_start': '2025-10-01',
                'baseline_end': '2025-12-30',
                'current_start': '2025-12-31',
                'current_end': '2026-01-14'
            }
        )
        
        # Create a drift event
        self.drift_event = DriftEvent.objects.create(
            customer=self.customer,
            report_run=self.report_run,
            payer='UnitedHealthcare',
            cpt_group='EVAL',
            drift_type='DENIAL_RATE',
            baseline_value=0.2,
            current_value=0.6,
            delta_value=0.4,
            severity=0.8,
            confidence=0.9,
            baseline_start=timezone.now().date() - timedelta(days=104),
            baseline_end=timezone.now().date() - timedelta(days=14),
            current_start=timezone.now().date() - timedelta(days=14),
            current_end=timezone.now().date()
        )
        
        # Create an alert rule that will trigger
        self.alert_rule = AlertRule.objects.create(
            customer=self.customer,
            name='High Denial Rate Alert',
            metric='severity',
            threshold_type='gte',
            threshold_value=0.7,
            enabled=True,
            severity='critical'
        )
    
    def test_drift_event_creates_alert_event(self):
        """Test that DriftEvent above threshold creates AlertEvent."""
        alert_events = evaluate_drift_event(self.drift_event)
        
        # Should create one alert event
        self.assertEqual(len(alert_events), 1)
        self.assertEqual(AlertEvent.objects.count(), 1)
        
        alert_event = alert_events[0]
        self.assertEqual(alert_event.customer, self.customer)
        self.assertEqual(alert_event.alert_rule, self.alert_rule)
        self.assertEqual(alert_event.drift_event, self.drift_event)
        self.assertEqual(alert_event.status, 'pending')
        self.assertEqual(alert_event.payload['payer'], 'UnitedHealthcare')
    
    def test_duplicate_alert_event_prevention(self):
        """Test that duplicate AlertEvents are not created for same drift event and rule."""
        # Create first alert event
        alert_events_1 = evaluate_drift_event(self.drift_event)
        self.assertEqual(len(alert_events_1), 1)
        
        # Try to create again - should return existing, not create new
        alert_events_2 = evaluate_drift_event(self.drift_event)
        self.assertEqual(len(alert_events_2), 1)
        self.assertEqual(AlertEvent.objects.count(), 1)  # Still only 1
        self.assertEqual(alert_events_1[0].id, alert_events_2[0].id)  # Same ID
    
    def test_alert_sent_via_console_backend(self):
        """Test that AlertEvent is sent using console backend with HTML and PDF."""
        # Create alert event
        alert_event = AlertEvent.objects.create(
            customer=self.customer,
            alert_rule=self.alert_rule,
            drift_event=self.drift_event,
            report_run=self.report_run,
            status='pending',
            payload={'payer': 'UnitedHealthcare', 'severity': 0.8}
        )
        
        # Send the alert
        success = send_alert_notification(alert_event)
        
        # Check success
        self.assertTrue(success)
        
        # Reload from DB
        alert_event.refresh_from_db()
        self.assertEqual(alert_event.status, 'sent')
        self.assertIsNotNone(alert_event.notification_sent_at)
        self.assertIsNone(alert_event.error_message)
        
        # Check email was sent (console backend)
        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        
        # Check subject contains customer name and product (Hub v1 format)
        self.assertIn(self.customer.name, sent_email.subject)
        self.assertIn('Alert', sent_email.subject)
        
        # Check HTML alternative exists
        self.assertEqual(len(sent_email.alternatives), 1)
        html_content, content_type = sent_email.alternatives[0]
        self.assertEqual(content_type, 'text/html')
        self.assertIn('Alert', html_content)
        self.assertIn(self.customer.name, html_content)
        
        # Check PDF attachment (may be absent if WeasyPrint fails, which is gracefully handled)
        # Our code logs the error and continues without attachment
        if len(sent_email.attachments) > 0:
            filename, content, mimetype = sent_email.attachments[0]
            self.assertTrue(filename.endswith('.pdf'))
            self.assertEqual(mimetype, 'application/pdf')
            self.assertGreater(len(content), 0)  # PDF has content
    
    def test_failed_send_updates_status(self):
        """Test that failed sends update status correctly."""
        alert_event = AlertEvent.objects.create(
            customer=self.customer,
            alert_rule=self.alert_rule,
            drift_event=self.drift_event,
            report_run=self.report_run,
            status='pending',
            payload={'payer': 'UnitedHealthcare'}
        )
        
        # Mock EmailMultiAlternatives.send to raise exception
        with patch('upstream.alerts.services.EmailMultiAlternatives.send', side_effect=Exception('SMTP Error')):
            success = send_alert_notification(alert_event)
            
            # Check failure
            self.assertFalse(success)
            
            # Reload from DB
            alert_event.refresh_from_db()
            self.assertEqual(alert_event.status, 'failed')
            self.assertIn('SMTP Error', alert_event.error_message)
            self.assertIsNone(alert_event.notification_sent_at)
    
    def test_resend_skips_sent_alerts(self):
        """Test that re-running sender does not resend sent alerts (idempotency)."""
        alert_event = AlertEvent.objects.create(
            customer=self.customer,
            alert_rule=self.alert_rule,
            drift_event=self.drift_event,
            report_run=self.report_run,
            status='pending',
            payload={'payer': 'UnitedHealthcare'}
        )
        
        # Send first time
        send_alert_notification(alert_event)
        alert_event.refresh_from_db()
        first_sent_at = alert_event.notification_sent_at
        
        # Clear mail outbox
        mail.outbox = []
        
        # Try to send again - should skip
        success = send_alert_notification(alert_event)
        self.assertTrue(success)  # Returns true but doesn't actually send
        
        # No new email sent
        self.assertEqual(len(mail.outbox), 0)
        
        # Timestamp unchanged
        alert_event.refresh_from_db()
        self.assertEqual(alert_event.notification_sent_at, first_sent_at)
    
    def test_process_pending_alerts(self):
        """Test process_pending_alerts command."""
        # Create multiple pending alerts
        for i in range(3):
            AlertEvent.objects.create(
                customer=self.customer,
                alert_rule=self.alert_rule,
                drift_event=self.drift_event,
                report_run=self.report_run,
                status='pending',
                payload={'payer': f'Payer{i}'}
            )
        
        # Process all
        results = process_pending_alerts()
        
        self.assertEqual(results['total'], 3)
        self.assertEqual(results['sent'], 3)
        self.assertEqual(results['failed'], 0)
        
        # All should be marked sent
        self.assertEqual(AlertEvent.objects.filter(status='sent').count(), 3)
    
    def test_audit_event_on_alert_creation(self):
        """Test that DomainAuditEvent is created when AlertEvent is created."""
        # Clear any existing audit events
        DomainAuditEvent.objects.all().delete()
        
        # Create alert event
        alert_events = evaluate_drift_event(self.drift_event)
        
        # Check audit event created
        audit_events = DomainAuditEvent.objects.filter(action='alert_event_created')
        self.assertEqual(audit_events.count(), 1)
        
        audit_event = audit_events.first()
        self.assertEqual(audit_event.entity_type, 'AlertEvent')
        self.assertEqual(audit_event.entity_id, str(alert_events[0].id))
        self.assertEqual(audit_event.customer, self.customer)
    
    def test_audit_event_on_alert_send(self):
        """Test that DomainAuditEvent is created when AlertEvent is sent."""
        alert_event = AlertEvent.objects.create(
            customer=self.customer,
            alert_rule=self.alert_rule,
            drift_event=self.drift_event,
            report_run=self.report_run,
            status='pending',
            payload={'payer': 'UnitedHealthcare'}
        )
        
        # Clear audit events
        DomainAuditEvent.objects.all().delete()
        
        # Send alert
        send_alert_notification(alert_event)
        
        # Check audit event created for send
        audit_events = DomainAuditEvent.objects.filter(action='alert_event_sent')
        self.assertEqual(audit_events.count(), 1)
    
    def test_suppression_window_prevents_duplicate_sends(self):
        """
        Test that second send within 4-hour suppression window is suppressed.
        
        Gate D proof: Creates drift event, evaluates it to AlertEvent, sends first,
        then a second send within window marks as suppressed not resent.
        """
        from django.utils import timezone
        from datetime import timedelta
        
        # Create alert event with same product_name, signal_type, entity_label
        alert_event1 = AlertEvent.objects.create(
            customer=self.customer,
            alert_rule=self.alert_rule,
            drift_event=self.drift_event,
            report_run=self.report_run,
            status='pending',
            payload={
                'product_name': 'DriftWatch',
                'signal_type': 'DENIAL_RATE',
                'entity_label': 'UnitedHealthcare',
                'payer': 'UnitedHealthcare',
                'severity': 0.8,
            }
        )
        
        # Send first alert
        success1 = send_alert_notification(alert_event1)
        self.assertTrue(success1)
        alert_event1.refresh_from_db()
        self.assertEqual(alert_event1.status, 'sent')
        self.assertIsNone(alert_event1.error_message)
        self.assertEqual(len(mail.outbox), 1)
        
        # Create second alert event with same payload fingerprint (same product, signal, entity)
        second_drift = DriftEvent.objects.create(
            customer=self.customer,
            report_run=self.report_run,
            payer='UnitedHealthcare',  # Same payer = same entity_label
            cpt_group='EVAL',
            drift_type='DENIAL_RATE',  # Same signal_type
            baseline_value=0.25,
            current_value=0.65,
            delta_value=0.4,
            severity=0.75,
            confidence=0.9,
            baseline_start=timezone.now().date() - timedelta(days=104),
            baseline_end=timezone.now().date() - timedelta(days=14),
            current_start=timezone.now().date() - timedelta(days=14),
            current_end=timezone.now().date()
        )
        
        alert_event2 = AlertEvent.objects.create(
            customer=self.customer,
            alert_rule=self.alert_rule,
            drift_event=second_drift,
            report_run=self.report_run,
            status='pending',
            payload={
                'product_name': 'DriftWatch',  # Same
                'signal_type': 'DENIAL_RATE',  # Same
                'entity_label': 'UnitedHealthcare',  # Same
                'payer': 'UnitedHealthcare',
                'severity': 0.75,
            }
        )
        
        # Clear mail outbox
        mail.outbox = []
        
        # Send second alert (should be suppressed)
        success2 = send_alert_notification(alert_event2)
        self.assertTrue(success2)  # Returns True but was suppressed
        
        alert_event2.refresh_from_db()
        self.assertEqual(alert_event2.status, 'sent')  # Marked as sent
        self.assertEqual(alert_event2.error_message, 'suppressed')  # Suppression marker
        
        # No new email sent (suppressed)
        self.assertEqual(len(mail.outbox), 0)
    
    def test_pdf_artifact_not_duplicated_on_resend(self):
        """Test that PDF artifacts are not duplicated when reprocessing alerts."""
        from upstream.reporting.models import ReportArtifact
        
        # Create alert event
        alert_event = AlertEvent.objects.create(
            customer=self.customer,
            alert_rule=self.alert_rule,
            drift_event=self.drift_event,
            report_run=self.report_run,
            status='pending',
            payload={'payer': 'UnitedHealthcare'}
        )
        
        # Send first time (will attempt to generate artifact, may fail due to WeasyPrint issue)
        send_alert_notification(alert_event)
        
        # Check if artifact was created (depends on WeasyPrint working)
        artifacts = ReportArtifact.objects.filter(
            customer=self.customer,
            report_run=self.report_run,
            kind='weekly_drift_summary'
        )
        
        # If PDF generation worked, verify idempotency
        if artifacts.count() > 0:
            first_artifact = artifacts.first()
            
            # Mark as pending again to simulate reprocessing
            alert_event.status = 'pending'
            alert_event.save()
            
            # Clear mail outbox
            mail.outbox = []
            
            # Send again
            send_alert_notification(alert_event)
            
            # Artifact should not be duplicated (still only 1)
            artifacts = ReportArtifact.objects.filter(
                customer=self.customer,
                report_run=self.report_run,
                kind='weekly_drift_summary'
            )
            self.assertEqual(artifacts.count(), 1)
            
            # Same artifact should be used
            self.assertEqual(artifacts.first().id, first_artifact.id)
            
            # Email should still have been sent
            self.assertEqual(len(mail.outbox), 1)
        else:
            # WeasyPrint failed, but email should still have been sent
            self.assertEqual(len(mail.outbox), 1)


class WebhookDeliveryTests(TestCase):
    """Tests for webhook delivery and retry logic."""
    
    def setUp(self):
        self.customer = Customer.objects.create(name='Test Customer')
        
        self.endpoint = WebhookEndpoint.objects.create(
            customer=self.customer,
            name='Test Webhook',
            url='https://example.com/webhook',
            secret='test_secret_key',
            active=True,
            event_types=['drift_detected', 'report_completed']
        )
    
    def test_signature_generation(self):
        """Test that HMAC-SHA256 signature is generated correctly."""
        payload = {'event': 'test', 'data': {'value': 123}}
        secret = 'test_secret'
        
        signature = generate_signature(payload, secret)
        
        # Verify it's a hex string of correct length (SHA256 = 64 hex chars)
        self.assertEqual(len(signature), 64)
        self.assertTrue(all(c in '0123456789abcdef' for c in signature))
        
        # Verify consistency
        signature2 = generate_signature(payload, secret)
        self.assertEqual(signature, signature2)
    
    def test_signature_consistency_with_different_key_order(self):
        """Test that signature is consistent regardless of dict key order."""
        payload1 = {'a': 1, 'b': 2, 'c': 3}
        payload2 = {'c': 3, 'a': 1, 'b': 2}
        secret = 'test_secret'
        
        sig1 = generate_signature(payload1, secret)
        sig2 = generate_signature(payload2, secret)
        
        # Should be identical because we sort_keys
        self.assertEqual(sig1, sig2)
    
    @patch('upstream.integrations.services.requests.post')
    def test_successful_delivery_marks_sent(self, mock_post):
        """Test that successful delivery marks WebhookDelivery as success."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = 'OK'
        mock_post.return_value = mock_response
        
        # Create delivery
        delivery = WebhookDelivery.objects.create(
            endpoint=self.endpoint,
            event_type='drift_detected',
            payload={'event': 'test'},
            status='pending'
        )
        
        # Deliver
        success = deliver_webhook(delivery)
        
        # Check success
        self.assertTrue(success)
        
        # Reload from DB
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, 'success')
        self.assertEqual(delivery.attempts, 1)
        self.assertEqual(delivery.response_code, 200)
        self.assertIsNotNone(delivery.last_attempt_at)
    
    @patch('upstream.integrations.services.requests.post')
    def test_failed_delivery_increments_attempts(self, mock_post):
        """Test that failed delivery increments attempts and schedules retry."""
        # Mock failed response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = 'Internal Server Error'
        mock_post.return_value = mock_response
        
        # Create delivery
        delivery = WebhookDelivery.objects.create(
            endpoint=self.endpoint,
            event_type='drift_detected',
            payload={'event': 'test'},
            status='pending',
            max_attempts=5
        )
        
        # Deliver (will fail)
        success = deliver_webhook(delivery)
        
        # Check failure
        self.assertFalse(success)
        
        # Reload from DB
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, 'retrying')
        self.assertEqual(delivery.attempts, 1)
        self.assertEqual(delivery.response_code, 500)
        self.assertIsNotNone(delivery.next_attempt_at)
        self.assertIn('HTTP 500', delivery.last_error)
    
    @patch('upstream.integrations.services.requests.post')
    def test_max_attempts_terminal_failure(self, mock_post):
        """Test that delivery stops after max_attempts and marks as failed."""
        # Mock failed response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = 'Error'
        mock_post.return_value = mock_response
        
        # Create delivery with max_attempts=2
        delivery = WebhookDelivery.objects.create(
            endpoint=self.endpoint,
            event_type='drift_detected',
            payload={'event': 'test'},
            status='pending',
            max_attempts=2
        )
        
        # First attempt
        deliver_webhook(delivery)
        delivery.refresh_from_db()
        self.assertEqual(delivery.attempts, 1)
        self.assertEqual(delivery.status, 'retrying')
        
        # Second attempt (should reach max)
        delivery.status = 'retrying'
        delivery.save()
        deliver_webhook(delivery)
        delivery.refresh_from_db()
        self.assertEqual(delivery.attempts, 2)
        self.assertEqual(delivery.status, 'failed')  # Terminal state
    
    @patch('upstream.integrations.services.requests.post')
    def test_request_id_in_payload(self, mock_post):
        """Test that request_id is added to webhook payload metadata."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = 'OK'
        mock_post.return_value = mock_response
        
        # Create delivery without request_id
        delivery = WebhookDelivery.objects.create(
            endpoint=self.endpoint,
            event_type='drift_detected',
            payload={'event': 'test'},
            status='pending'
        )
        
        # Deliver
        deliver_webhook(delivery)
        
        # Check that request_id was added
        delivery.refresh_from_db()
        self.assertIn('metadata', delivery.payload)
        self.assertIn('request_id', delivery.payload['metadata'])
        self.assertIsNotNone(delivery.payload['metadata']['request_id'])
    
    @patch('upstream.integrations.services.requests.post')
    def test_webhook_delivery_audit_event(self, mock_post):
        """Test that DomainAuditEvent is created for webhook delivery."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = 'OK'
        mock_post.return_value = mock_response
        
        # Clear audit events
        DomainAuditEvent.objects.all().delete()
        
        # Create and deliver
        delivery = WebhookDelivery.objects.create(
            endpoint=self.endpoint,
            event_type='drift_detected',
            payload={'event': 'test'},
            status='pending'
        )
        
        deliver_webhook(delivery)
        
        # Check audit event created
        audit_events = DomainAuditEvent.objects.filter(action='webhook_delivery_sent')
        self.assertEqual(audit_events.count(), 1)
        
        audit_event = audit_events.first()
        self.assertEqual(audit_event.entity_type, 'WebhookDelivery')
        self.assertEqual(audit_event.customer, self.customer)
        self.assertIsNotNone(audit_event.request_id)
    
    @patch('upstream.integrations.services.requests.post')
    def test_process_pending_deliveries(self, mock_post):
        """Test process_pending_deliveries processes all pending webhooks."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = 'OK'
        mock_post.return_value = mock_response
        
        # Create multiple pending deliveries
        for i in range(3):
            WebhookDelivery.objects.create(
                endpoint=self.endpoint,
                event_type='drift_detected',
                payload={'index': i},
                status='pending'
            )
        
        # Process all
        results = process_pending_deliveries()
        
        self.assertEqual(results['total'], 3)
        self.assertEqual(results['success'], 3)
        self.assertEqual(results['failed'], 0)
        
        # All should be marked success
        self.assertEqual(WebhookDelivery.objects.filter(status='success').count(), 3)
