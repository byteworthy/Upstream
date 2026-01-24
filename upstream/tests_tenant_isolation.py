"""
Tests for tenant isolation (multi-customer data separation).

Verifies that customer A cannot access customer B's data, even if a developer
forgets to add a .filter(customer=...) check in a view.
"""

from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from upstream.models import (
    Customer, Upload, ClaimRecord, DriftEvent, ReportRun,
    PayerMapping, CPTGroupMapping, UserProfile
)
from upstream.alerts.models import AlertRule, AlertEvent, NotificationChannel, OperatorJudgment
from upstream.core.tenant import (
    set_current_customer, get_current_customer, clear_current_customer,
    customer_context, TenantIsolationMiddleware
)


class TenantIsolationTest(TestCase):
    """Test that customer data is properly isolated."""

    def setUp(self):
        """Create two customers with separate data."""
        # Customer A
        self.customer_a = Customer.objects.create(name="Hospital A")
        self.user_a = User.objects.create_user(username="user_a", password="testpass")
        self.profile_a = UserProfile.objects.create(
            user=self.user_a,
            customer=self.customer_a,
            role='admin'
        )

        # Customer B
        self.customer_b = Customer.objects.create(name="Hospital B")
        self.user_b = User.objects.create_user(username="user_b", password="testpass")
        self.profile_b = UserProfile.objects.create(
            user=self.user_b,
            customer=self.customer_b,
            role='admin'
        )

        # Create data for both customers
        self._create_data_for_customer(self.customer_a)
        self._create_data_for_customer(self.customer_b)

    def _create_data_for_customer(self, customer):
        """Create test data for a customer."""
        # Upload
        upload = Upload.all_objects.create(
            customer=customer,
            filename=f"test_{customer.name}.csv",
            status='success'
        )

        # Claim records
        ClaimRecord.all_objects.create(
            customer=customer,
            upload=upload,
            payer="BCBS",
            cpt="99213",
            cpt_group="E&M",
            submitted_date=timezone.now().date(),
            decided_date=timezone.now().date(),
            outcome='PAID'
        )

        # Report run
        report_run = ReportRun.all_objects.create(
            customer=customer,
            run_type='weekly',
            status='success'
        )

        # Drift event
        DriftEvent.all_objects.create(
            customer=customer,
            report_run=report_run,
            payer="BCBS",
            cpt_group="E&M",
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

        # Alert rule
        AlertRule.all_objects.create(
            customer=customer,
            name="Test Rule",
            metric='severity',
            threshold_value=0.7
        )

        # Payer mapping
        PayerMapping.all_objects.create(
            customer=customer,
            raw_name="BLUE CROSS BLUE SHIELD",
            normalized_name="BCBS"
        )

    def tearDown(self):
        """Clean up after each test."""
        clear_current_customer()

    def test_upload_isolation(self):
        """Customer A cannot see Customer B's uploads."""
        # Set context to customer A
        set_current_customer(self.customer_a)

        # Query uploads (should only see customer A's data)
        uploads = Upload.objects.all()

        self.assertEqual(uploads.count(), 1)
        self.assertEqual(uploads.first().customer, self.customer_a)

        # Verify customer B's upload exists but is not visible
        all_uploads = Upload.all_objects.all()
        self.assertEqual(all_uploads.count(), 2)

    def test_claim_record_isolation(self):
        """Customer A cannot see Customer B's claim records."""
        set_current_customer(self.customer_a)

        claims = ClaimRecord.objects.all()

        self.assertEqual(claims.count(), 1)
        self.assertEqual(claims.first().customer, self.customer_a)

        # Verify total count
        all_claims = ClaimRecord.all_objects.all()
        self.assertEqual(all_claims.count(), 2)

    def test_drift_event_isolation(self):
        """Customer A cannot see Customer B's drift events."""
        set_current_customer(self.customer_a)

        drift_events = DriftEvent.objects.all()

        self.assertEqual(drift_events.count(), 1)
        self.assertEqual(drift_events.first().customer, self.customer_a)

        # Verify total count
        all_drift_events = DriftEvent.all_objects.all()
        self.assertEqual(all_drift_events.count(), 2)

    def test_alert_rule_isolation(self):
        """Customer A cannot see Customer B's alert rules."""
        set_current_customer(self.customer_a)

        alert_rules = AlertRule.objects.all()

        self.assertEqual(alert_rules.count(), 1)
        self.assertEqual(alert_rules.first().customer, self.customer_a)

        # Verify total count
        all_rules = AlertRule.all_objects.all()
        self.assertEqual(all_rules.count(), 2)

    def test_payer_mapping_isolation(self):
        """Customer A cannot see Customer B's payer mappings."""
        set_current_customer(self.customer_a)

        mappings = PayerMapping.objects.all()

        self.assertEqual(mappings.count(), 1)
        self.assertEqual(mappings.first().customer, self.customer_a)

        # Verify total count
        all_mappings = PayerMapping.all_objects.all()
        self.assertEqual(all_mappings.count(), 2)

    def test_context_manager(self):
        """Test customer_context() context manager."""
        # Initially no customer set
        self.assertIsNone(get_current_customer())

        # Inside context, customer is set
        with customer_context(self.customer_a):
            self.assertEqual(get_current_customer(), self.customer_a)

            uploads = Upload.objects.all()
            self.assertEqual(uploads.count(), 1)
            self.assertEqual(uploads.first().customer, self.customer_a)

        # After context, customer is cleared
        self.assertIsNone(get_current_customer())

    def test_nested_context_managers(self):
        """Test nested customer contexts."""
        with customer_context(self.customer_a):
            self.assertEqual(get_current_customer(), self.customer_a)

            # Nested context
            with customer_context(self.customer_b):
                self.assertEqual(get_current_customer(), self.customer_b)

                uploads = Upload.objects.all()
                self.assertEqual(uploads.count(), 1)
                self.assertEqual(uploads.first().customer, self.customer_b)

            # Back to customer A
            self.assertEqual(get_current_customer(), self.customer_a)

            uploads = Upload.objects.all()
            self.assertEqual(uploads.count(), 1)
            self.assertEqual(uploads.first().customer, self.customer_a)

    def test_for_customer_method(self):
        """Test explicit .for_customer() method."""
        set_current_customer(self.customer_a)

        # Explicitly query customer B's data (bypasses thread-local)
        customer_b_uploads = Upload.objects.for_customer(self.customer_b)

        self.assertEqual(customer_b_uploads.count(), 1)
        self.assertEqual(customer_b_uploads.first().customer, self.customer_b)

    def test_unscoped_method(self):
        """Test .unscoped() method for superuser access."""
        set_current_customer(self.customer_a)

        # Get all data regardless of customer
        all_uploads = Upload.objects.unscoped()

        self.assertEqual(all_uploads.count(), 2)

    def test_middleware_sets_customer(self):
        """Test that middleware sets customer from user profile."""
        factory = RequestFactory()
        request = factory.get('/')
        request.user = self.user_a

        # Track if customer was set during request processing
        customer_during_request = [None]

        def get_response(req):
            # Check customer is set during request processing
            customer_during_request[0] = get_current_customer()
            return None

        middleware = TenantIsolationMiddleware(get_response)
        middleware(request)

        # Customer should have been set during request processing
        self.assertEqual(customer_during_request[0], self.customer_a)

        # Customer should be cleared after request completes
        self.assertIsNone(get_current_customer())

    def test_middleware_skips_superuser(self):
        """Test that middleware doesn't set customer for superusers."""
        factory = RequestFactory()
        request = factory.get('/')

        superuser = User.objects.create_superuser(
            username="admin",
            password="admin",
            email="admin@test.com"
        )
        request.user = superuser

        middleware = TenantIsolationMiddleware(lambda r: None)
        middleware(request)

        # Customer should NOT be set for superuser
        self.assertIsNone(get_current_customer())

    def test_filter_method_isolation(self):
        """Test that .filter() applies customer filter."""
        set_current_customer(self.customer_a)

        # Filter by payer should still only return customer A's claims
        bcbs_claims = ClaimRecord.objects.filter(payer="BCBS")

        self.assertEqual(bcbs_claims.count(), 1)
        self.assertEqual(bcbs_claims.first().customer, self.customer_a)

    def test_get_method_isolation(self):
        """Test that .get() applies customer filter."""
        set_current_customer(self.customer_a)

        # Get upload by filename (should only find customer A's upload)
        upload = Upload.objects.get(filename=f"test_{self.customer_a.name}.csv")

        self.assertEqual(upload.customer, self.customer_a)

        # Trying to get customer B's upload should fail
        with self.assertRaises(Upload.DoesNotExist):
            Upload.objects.get(filename=f"test_{self.customer_b.name}.csv")

    def test_no_customer_context_returns_empty(self):
        """Test that queries return empty when no customer is set."""
        clear_current_customer()

        # Without customer context, should return empty
        uploads = Upload.objects.all()
        self.assertEqual(uploads.count(), 0)

        claims = ClaimRecord.objects.all()
        self.assertEqual(claims.count(), 0)

    def test_create_inherits_customer(self):
        """Test that creating objects in customer context works."""
        set_current_customer(self.customer_a)

        # Create a new upload
        new_upload = Upload.objects.create(
            customer=self.customer_a,
            filename="new_upload.csv",
            status='processing'
        )

        # Should be visible in customer A's context
        uploads = Upload.objects.all()
        self.assertIn(new_upload, uploads)

        # Switch to customer B
        set_current_customer(self.customer_b)

        # Should NOT be visible in customer B's context
        uploads_b = Upload.objects.all()
        self.assertNotIn(new_upload, uploads_b)

    def test_operator_judgment_isolation(self):
        """Test operator judgment isolation."""
        # Create alert events for both customers
        alert_rule_a = AlertRule.all_objects.filter(customer=self.customer_a).first()
        alert_event_a = AlertEvent.all_objects.create(
            customer=self.customer_a,
            alert_rule=alert_rule_a,
            status='pending'
        )

        OperatorJudgment.all_objects.create(
            customer=self.customer_a,
            alert_event=alert_event_a,
            operator=self.user_a,
            verdict='real',
            notes='Legitimate issue'
        )

        alert_rule_b = AlertRule.all_objects.filter(customer=self.customer_b).first()
        alert_event_b = AlertEvent.all_objects.create(
            customer=self.customer_b,
            alert_rule=alert_rule_b,
            status='pending'
        )

        OperatorJudgment.all_objects.create(
            customer=self.customer_b,
            alert_event=alert_event_b,
            operator=self.user_b,
            verdict='noise',
            notes='False positive'
        )

        # Set context to customer A
        set_current_customer(self.customer_a)

        # Should only see customer A's judgments
        judgments = OperatorJudgment.objects.all()
        self.assertEqual(judgments.count(), 1)
        self.assertEqual(judgments.first().verdict, 'real')

        # Switch to customer B
        set_current_customer(self.customer_b)

        # Should only see customer B's judgments
        judgments_b = OperatorJudgment.objects.all()
        self.assertEqual(judgments_b.count(), 1)
        self.assertEqual(judgments_b.first().verdict, 'noise')


class TenantIsolationAcceptanceTest(TestCase):
    """
    Acceptance criteria from developer requirements:
    'A test that proves customer A cannot query customer B objects
    even if a dev forgets a filter in a view'
    """

    def setUp(self):
        # Create two customers
        self.customer_a = Customer.objects.create(name="Customer A")
        self.customer_b = Customer.objects.create(name="Customer B")

        # Create 2 uploads for each customer
        Upload.all_objects.create(
            customer=self.customer_a,
            filename="upload_a1.csv",
            status='success'
        )
        Upload.all_objects.create(
            customer=self.customer_a,
            filename="upload_a2.csv",
            status='success'
        )

        Upload.all_objects.create(
            customer=self.customer_b,
            filename="upload_b1.csv",
            status='success'
        )
        Upload.all_objects.create(
            customer=self.customer_b,
            filename="upload_b2.csv",
            status='success'
        )

    def tearDown(self):
        clear_current_customer()

    def test_acceptance_customer_a_cannot_see_customer_b_uploads(self):
        """
        ACCEPTANCE CRITERIA:
        Create 2 customers and 2 uploads per customer.
        Prove each customer only sees its own records from identical endpoints.
        """
        # Simulate customer A's request
        set_current_customer(self.customer_a)

        # Developer forgets to add .filter(customer=customer_a) in the view
        # But the manager does it automatically
        uploads_a = Upload.objects.all()

        # Customer A should only see their own 2 uploads
        self.assertEqual(
            uploads_a.count(),
            2,
            "Customer A should only see 2 uploads (their own)"
        )

        for upload in uploads_a:
            self.assertEqual(
                upload.customer,
                self.customer_a,
                f"All uploads should belong to Customer A, but found {upload.customer}"
            )

        # Simulate customer B's request
        clear_current_customer()
        set_current_customer(self.customer_b)

        uploads_b = Upload.objects.all()

        # Customer B should only see their own 2 uploads
        self.assertEqual(
            uploads_b.count(),
            2,
            "Customer B should only see 2 uploads (their own)"
        )

        for upload in uploads_b:
            self.assertEqual(
                upload.customer,
                self.customer_b,
                f"All uploads should belong to Customer B, but found {upload.customer}"
            )

        # Verify total count (sanity check)
        clear_current_customer()
        all_uploads = Upload.all_objects.all()
        self.assertEqual(
            all_uploads.count(),
            4,
            "Total uploads should be 4 (2 per customer)"
        )
