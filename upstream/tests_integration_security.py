"""
Cross-Tenant Security Integration Tests.

Comprehensive tests verifying tenant isolation at the API level.
These tests ensure customers cannot access each other's data through any API endpoint.
"""

from django.test import TestCase
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from upstream.models import Customer, UserProfile, Upload, ClaimRecord, ReportRun, DriftEvent
from upstream.alerts.models import AlertRule, AlertEvent, OperatorJudgment, NotificationChannel
from upstream.test_fixtures import TenantTestMixin


class CrossTenantAPISecurityTest(TenantTestMixin, APITestCase):
    """
    Test that API endpoints enforce tenant isolation.

    These tests verify that Customer A cannot access Customer B's data
    through any API endpoint, even with direct ID access.
    """

    def setUp(self):
        """Set up two customers with data."""
        super().setUp()

        # Create Customer A with data
        self.customer_a = self.create_customer('Hospital A')
        self.user_a = self.create_user(self.customer_a, 'user_a')
        self.upload_a = self.create_upload(self.customer_a, 'customer_a.csv')
        self.report_a = self.create_report_run(self.customer_a)
        self.drift_a = self.create_drift_event(self.customer_a, self.report_a)
        self.alert_rule_a = self.create_alert_rule(self.customer_a)

        # Create Customer B with data
        self.customer_b = self.create_customer('Hospital B')
        self.user_b = self.create_user(self.customer_b, 'user_b')
        self.upload_b = self.create_upload(self.customer_b, 'customer_b.csv')
        self.report_b = self.create_report_run(self.customer_b)
        self.drift_b = self.create_drift_event(self.customer_b, self.report_b)
        self.alert_rule_b = self.create_alert_rule(self.customer_b)

        self.client = APIClient()

    def test_upload_list_isolated(self):
        """User A cannot see User B's uploads in list."""
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get('/api/v1/uploads/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Get list of uploads (handle both paginated and non-paginated)
        if isinstance(response.data, dict) and 'results' in response.data:
            uploads = response.data['results']
        else:
            uploads = response.data

        # Check that only customer A's upload is visible
        filenames = [u['filename'] for u in uploads]
        self.assertIn('customer_a.csv', filenames)
        self.assertNotIn('customer_b.csv', filenames)

    def test_upload_detail_isolated(self):
        """User A cannot access User B's upload by ID."""
        self.client.force_authenticate(user=self.user_a)

        # Try to access customer B's upload
        response = self.client.get(f'/api/v1/uploads/{self.upload_b.id}/')

        # Should return 404, not the data
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_report_list_isolated(self):
        """User A cannot see User B's reports in list."""
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get('/api/v1/reports/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Get list of report IDs (handle both paginated and non-paginated)
        if isinstance(response.data, dict) and 'results' in response.data:
            report_ids = [r['id'] for r in response.data['results']]
        else:
            report_ids = [r['id'] for r in response.data]

        # Should only see customer A's report
        self.assertIn(self.report_a.id, report_ids)
        self.assertNotIn(self.report_b.id, report_ids)

    def test_report_detail_isolated(self):
        """User A cannot access User B's report by ID."""
        self.client.force_authenticate(user=self.user_a)

        # Try to access customer B's report
        response = self.client.get(f'/api/v1/reports/{self.report_b.id}/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_drift_event_list_isolated(self):
        """User A cannot see User B's drift events in list."""
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get('/api/v1/drift-events/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Get list of drift IDs (handle both paginated and non-paginated)
        if isinstance(response.data, dict) and 'results' in response.data:
            drift_ids = [d['id'] for d in response.data['results']]
        else:
            drift_ids = [d['id'] for d in response.data]

        # Should only see customer A's drift event
        self.assertIn(self.drift_a.id, drift_ids)
        self.assertNotIn(self.drift_b.id, drift_ids)

    def test_drift_event_detail_isolated(self):
        """User A cannot access User B's drift event by ID."""
        self.client.force_authenticate(user=self.user_a)

        # Try to access customer B's drift event
        response = self.client.get(f'/api/v1/drift-events/{self.drift_b.id}/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # Note: Alert rules are not currently exposed via REST API
    # They are configured through Django admin or database directly
    # If/when alert rules API is added, add tests here

    def test_dashboard_isolated(self):
        """Dashboard only shows customer's own data."""
        # Create uploads for both customers
        Upload.all_objects.create(customer=self.customer_a, filename='a2.csv', status='success')
        Upload.all_objects.create(customer=self.customer_b, filename='b2.csv', status='success')

        self.client.force_authenticate(user=self.user_a)
        response = self.client.get('/api/v1/dashboard/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should only count customer A's uploads
        self.assertEqual(response.data['total_uploads'], 2)  # a.csv + a2.csv

    # Note: Customer is automatically set from authenticated user's profile
    # API does not allow specifying customer_id directly, so this attack vector
    # is not possible. Customer assignment is enforced at the view level.

    def test_cannot_update_other_customer_data(self):
        """User A cannot update Customer B's data."""
        self.client.force_authenticate(user=self.user_a)

        # Try to update customer B's upload
        response = self.client.patch(f'/api/v1/uploads/{self.upload_b.id}/', {
            'filename': 'hacked.csv'
        })

        # Should return 404, not allow update
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Verify data wasn't changed
        self.upload_b.refresh_from_db()
        self.assertEqual(self.upload_b.filename, 'customer_b.csv')

    def test_cannot_delete_other_customer_data(self):
        """User A cannot delete Customer B's data."""
        self.client.force_authenticate(user=self.user_a)

        # Try to delete customer B's upload
        response = self.client.delete(f'/api/v1/uploads/{self.upload_b.id}/')

        # Should return 404, not allow deletion
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Verify data still exists
        self.assertTrue(Upload.all_objects.filter(id=self.upload_b.id).exists())


class CrossTenantAlertSecurityTest(TenantTestMixin, APITestCase):
    """
    Test that alert system enforces tenant isolation.

    Verifies that alerts, judgments, and notifications are properly isolated.
    """

    def setUp(self):
        """Set up two customers with alerts."""
        super().setUp()

        # Customer A setup
        self.customer_a = self.create_customer('Hospital A')
        self.user_a = self.create_user(self.customer_a, 'user_a')
        self.report_a = self.create_report_run(self.customer_a)
        self.drift_a = self.create_drift_event(self.customer_a, self.report_a)
        self.alert_rule_a = self.create_alert_rule(self.customer_a)
        self.alert_a = self.create_alert_event(
            self.customer_a,
            self.alert_rule_a,
            self.drift_a,
            self.report_a
        )

        # Customer B setup
        self.customer_b = self.create_customer('Hospital B')
        self.user_b = self.create_user(self.customer_b, 'user_b')
        self.report_b = self.create_report_run(self.customer_b)
        self.drift_b = self.create_drift_event(self.customer_b, self.report_b)
        self.alert_rule_b = self.create_alert_rule(self.customer_b)
        self.alert_b = self.create_alert_event(
            self.customer_b,
            self.alert_rule_b,
            self.drift_b,
            self.report_b
        )

        self.client = APIClient()

    def test_alert_event_list_isolated(self):
        """User A cannot see User B's alert events."""
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get('/api/v1/alerts/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Get list of alert IDs (handle both paginated and non-paginated)
        if isinstance(response.data, dict) and 'results' in response.data:
            alert_ids = [a['id'] for a in response.data['results']]
        else:
            alert_ids = [a['id'] for a in response.data]

        # Should only see customer A's alert
        self.assertIn(self.alert_a.id, alert_ids)
        self.assertNotIn(self.alert_b.id, alert_ids)

    def test_alert_event_detail_isolated(self):
        """User A cannot access User B's alert event by ID."""
        self.client.force_authenticate(user=self.user_a)

        # Try to access customer B's alert
        response = self.client.get(f'/api/v1/alerts/{self.alert_b.id}/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_operator_judgment_isolated(self):
        """User A's judgments don't affect User B's alerts."""
        # User A marks their alert as noise
        OperatorJudgment.all_objects.create(
            customer=self.customer_a,
            alert_event=self.alert_a,
            operator=self.user_a,
            verdict='noise'
        )

        # Verify judgment exists for customer A
        judgments_a = OperatorJudgment.all_objects.filter(customer=self.customer_a)
        self.assertEqual(judgments_a.count(), 1)

        # Verify judgment doesn't exist for customer B
        judgments_b = OperatorJudgment.all_objects.filter(customer=self.customer_b)
        self.assertEqual(judgments_b.count(), 0)

    def test_cannot_submit_feedback_for_other_customer_alert(self):
        """User A cannot submit feedback on User B's alert."""
        self.client.force_authenticate(user=self.user_a)

        # Try to submit feedback on customer B's alert
        response = self.client.post(f'/api/v1/alerts/{self.alert_b.id}/feedback/', {
            'verdict': 'noise',
            'notes': 'Trying to mark another customer\'s alert'
        })

        # Should return 404
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Verify no judgment was created
        judgments = OperatorJudgment.all_objects.filter(alert_event=self.alert_b)
        self.assertEqual(judgments.count(), 0)

    # Note: Notification channels are not currently exposed via REST API
    # They are configured through Django admin or database directly
    # Isolation is enforced at the ORM level
    def test_notification_channels_isolated_at_orm_level(self):
        """Verify notification channels are isolated at ORM level."""
        # Create channels for both customers
        channel_a = self.create_notification_channel(self.customer_a, 'Channel A')
        channel_b = self.create_notification_channel(self.customer_b, 'Channel B')

        # Verify ORM isolation works
        from upstream.core.tenant import customer_context

        # Customer A can see their channel
        with customer_context(self.customer_a):
            channels_a = NotificationChannel.objects.all()
            channel_ids_a = [c.id for c in channels_a]
            self.assertIn(channel_a.id, channel_ids_a)
            self.assertNotIn(channel_b.id, channel_ids_a)

        # Customer B can see their channel
        with customer_context(self.customer_b):
            channels_b = NotificationChannel.objects.all()
            channel_ids_b = [c.id for c in channels_b]
            self.assertIn(channel_b.id, channel_ids_b)
            self.assertNotIn(channel_a.id, channel_ids_b)


class CrossTenantSuppressionTest(TenantTestMixin, TestCase):
    """
    Test that alert suppression respects tenant boundaries.

    Verifies that noise judgments from one customer don't suppress
    alerts for another customer.
    """

    def setUp(self):
        """Set up two customers with alerts."""
        super().setUp()

        self.customer_a = self.create_customer('Hospital A')
        self.user_a = self.create_user(self.customer_a, 'user_a')

        self.customer_b = self.create_customer('Hospital B')
        self.user_b = self.create_user(self.customer_b, 'user_b')

    def test_noise_judgments_dont_cross_tenants(self):
        """Noise judgments from Customer A don't affect Customer B."""
        from upstream.alerts.services import _is_suppressed
        from upstream.core.tenant import customer_context

        evidence_payload = {
            'product_name': 'DriftWatch',
            'signal_type': 'DENIAL_RATE',
            'entity_label': 'BCBS',
        }

        # Create two noise judgments for customer A
        report_a = self.create_report_run(self.customer_a)
        alert_rule_a = self.create_alert_rule(self.customer_a)

        for days_ago in [10, 20]:
            drift_a = self.create_drift_event(
                self.customer_a,
                report_a,
                payer='BCBS'
            )
            alert_a = self.create_alert_event(
                self.customer_a,
                alert_rule_a,
                drift_a,
                report_a,
                status='sent'
            )
            alert_a.notification_sent_at = timezone.now() - timedelta(days=days_ago)
            alert_a.payload = evidence_payload
            alert_a.save()

            OperatorJudgment.all_objects.create(
                customer=self.customer_a,
                alert_event=alert_a,
                operator=self.user_a,
                verdict='noise'
            )

        # Customer A's alerts should be suppressed
        with customer_context(self.customer_a):
            result_a = _is_suppressed(self.customer_a, evidence_payload)
            self.assertTrue(result_a, "Customer A's alerts should be suppressed")

        # Customer B's alerts should NOT be suppressed
        with customer_context(self.customer_b):
            result_b = _is_suppressed(self.customer_b, evidence_payload)
            self.assertFalse(result_b, "Customer B's alerts should NOT be suppressed")

    def test_time_based_suppression_isolated(self):
        """Time-based suppression is isolated per customer."""
        from upstream.alerts.services import _is_suppressed
        from upstream.core.tenant import customer_context

        evidence_payload = {
            'product_name': 'DriftWatch',
            'signal_type': 'DENIAL_RATE',
            'entity_label': 'Medicare',
        }

        # Create recent alert for customer A (within 4-hour window)
        report_a = self.create_report_run(self.customer_a)
        alert_rule_a = self.create_alert_rule(self.customer_a)
        drift_a = self.create_drift_event(self.customer_a, report_a)
        alert_a = self.create_alert_event(
            self.customer_a,
            alert_rule_a,
            drift_a,
            report_a,
            status='sent'
        )
        alert_a.notification_sent_at = timezone.now() - timedelta(hours=2)
        alert_a.payload = evidence_payload
        alert_a.save()

        # Customer A should be suppressed (recent alert)
        with customer_context(self.customer_a):
            result_a = _is_suppressed(self.customer_a, evidence_payload)
            self.assertTrue(result_a)

        # Customer B should NOT be suppressed (no recent alert)
        with customer_context(self.customer_b):
            result_b = _is_suppressed(self.customer_b, evidence_payload)
            self.assertFalse(result_b)


class UnauthenticatedAccessTest(APITestCase):
    """
    Test that unauthenticated users cannot access any data.

    All API endpoints should require authentication.
    """

    def setUp(self):
        """Set up test data."""
        self.customer = Customer.objects.create(name='Test Hospital')
        self.upload = Upload.all_objects.create(
            customer=self.customer,
            filename='test.csv',
            status='success'
        )

        self.client = APIClient()

    def test_uploads_require_auth(self):
        """Uploads endpoint requires authentication."""
        response = self.client.get('/api/v1/uploads/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_reports_require_auth(self):
        """Reports endpoint requires authentication."""
        response = self.client.get('/api/v1/reports/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_drift_events_require_auth(self):
        """Drift events endpoint requires authentication."""
        response = self.client.get('/api/v1/drift-events/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_alerts_require_auth(self):
        """Alert events endpoint requires authentication."""
        response = self.client.get('/api/v1/alerts/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_dashboard_requires_auth(self):
        """Dashboard endpoint requires authentication."""
        response = self.client.get('/api/v1/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class UserWithoutCustomerTest(TenantTestMixin, APITestCase):
    """
    Test that users without customer assignment cannot access data.

    Users must have a customer assigned via UserProfile.
    """

    def setUp(self):
        """Set up user without customer."""
        super().setUp()

        self.customer = self.create_customer('Test Hospital')

        # Create user WITHOUT customer profile
        self.user_no_customer = User.objects.create_user(
            username='no_customer',
            password='testpass123'
        )

        # Create some data
        self.upload = self.create_upload(self.customer)

        self.client = APIClient()

    def test_user_without_customer_denied_access(self):
        """User without customer is denied access."""
        self.client.force_authenticate(user=self.user_no_customer)

        response = self.client.get('/api/v1/uploads/')

        # Should return 403 Forbidden (user has no customer)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_without_customer_cannot_create_data(self):
        """User without customer cannot create data."""
        self.client.force_authenticate(user=self.user_no_customer)

        response = self.client.post('/api/v1/uploads/', {
            'filename': 'test.csv',
            'status': 'success'
        })

        # Should fail - no customer to assign
        self.assertNotEqual(response.status_code, status.HTTP_201_CREATED)
