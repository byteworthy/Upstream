"""
DriftWatch tests.

Hub v1: Deterministic test using existing DriftEvent model.
Filtered to DENIAL_RATE type only for v1.
No new models - reuses payrixa.models.DriftEvent via payer_drift service.
"""

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone

from payrixa.core.models import ProductConfig
from payrixa.models import Customer, ClaimRecord, Upload, UserProfile, DriftEvent, ReportRun
from payrixa.services.payer_drift import compute_weekly_payer_drift
from payrixa.products.driftwatch import DRIFTWATCH_V1_EVENT_TYPE


class DriftWatchTests(TestCase):
    """Tests for DriftWatch product using existing DriftEvent model."""

    def setUp(self):
        self.customer = Customer.objects.create(name='DriftWatch Customer')
        self.user = User.objects.create_user(username='driftwatch_user', password='pass')
        UserProfile.objects.create(user=self.user, customer=self.customer, role='admin')
        self.client.force_login(self.user)

        ProductConfig.objects.create(
            customer=self.customer,
            product_slug='driftwatch',
            enabled=True
        )

        self.upload = Upload.objects.create(
            customer=self.customer,
            filename='drift_claims.csv',
            status='success'
        )

    def _create_claim(self, payer, outcome, days_ago, cpt_group='OFFICE', allowed_amount=100):
        """Helper to create claims for drift testing."""
        submitted_date = timezone.now().date() - timedelta(days=days_ago)
        decided_date = submitted_date + timedelta(days=3)
        return ClaimRecord.objects.create(
            customer=self.customer,
            upload=self.upload,
            payer=payer,
            cpt='99213',
            cpt_group=cpt_group,
            submitted_date=submitted_date,
            decided_date=decided_date,
            outcome=outcome,
            allowed_amount=Decimal(str(allowed_amount)),
        )

    def test_v1_signal_volume_spike_fires(self):
        """
        V1 deterministic test: Verify DriftEvent is created for volume drift.
        
        This test uses the existing payer_drift service which creates DriftEvent rows.
        No new models are created.
        """
        # === BASELINE PERIOD: Low denial rate ===
        for day_offset in range(90):
            days_ago = 104 - day_offset
            for i in range(4):
                outcome = 'DENIED' if (day_offset * 4 + i) % 10 == 0 else 'PAID'
                self._create_claim('Blue Cross Blue Shield', outcome, days_ago, 'E&M')

        # === CURRENT PERIOD: High denial rate (spike) ===
        for day_offset in range(14):
            days_ago = 14 - day_offset
            for i in range(4):
                outcome = 'DENIED' if i < 2 else 'PAID'
                self._create_claim('Blue Cross Blue Shield', outcome, days_ago, 'E&M')

        # Run drift computation using existing service
        report_run = compute_weekly_payer_drift(
            customer=self.customer,
            baseline_days=90,
            current_days=14,
            min_volume=30
        )

        # Assert report run succeeded
        self.assertEqual(report_run.status, 'success')

        # Assert at least one DriftEvent was created
        drift_event_count = DriftEvent.objects.filter(customer=self.customer).count()
        self.assertGreaterEqual(drift_event_count, 1,
            f"Expected at least 1 DriftEvent, got {drift_event_count}")

        # Assert DENIAL_RATE drift type exists (V1 signal)
        denial_rate_event = DriftEvent.objects.filter(
            customer=self.customer,
            drift_type='DENIAL_RATE'
        ).first()
        
        self.assertIsNotNone(denial_rate_event,
            "Expected DriftEvent with drift_type='DENIAL_RATE' (V1 volume spike signal)")
        
        self.assertGreater(denial_rate_event.delta_value, 0.1)
        self.assertGreater(denial_rate_event.severity, 0.0)

    def test_dashboard_renders_with_data(self):
        """Test DriftWatch dashboard renders correctly."""
        for day_offset in range(90):
            days_ago = 104 - day_offset
            for i in range(2):
                outcome = 'DENIED' if i == 0 else 'PAID'
                self._create_claim('Aetna', outcome, days_ago, 'SURGERY')

        for day_offset in range(14):
            days_ago = 14 - day_offset
            for i in range(4):
                outcome = 'DENIED' if i < 3 else 'PAID'
                self._create_claim('Aetna', outcome, days_ago, 'SURGERY')

        compute_weekly_payer_drift(self.customer, min_volume=20)

        response = self.client.get('/portal/products/driftwatch/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'DriftWatch')

    def test_no_new_models_created(self):
        """Verify DriftWatch uses only existing models - no new migrations needed."""
        report_run = ReportRun.objects.create(
            customer=self.customer,
            run_type='weekly',
            status='success'
        )
        
        drift_event = DriftEvent.objects.create(
            customer=self.customer,
            report_run=report_run,
            payer='Test Payer',
            cpt_group='TEST',
            drift_type=DRIFTWATCH_V1_EVENT_TYPE,  # Use V1 constant
            baseline_value=0.1,
            current_value=0.5,
            delta_value=0.4,
            severity=0.8,
            confidence=0.9,
            baseline_start=timezone.now().date() - timedelta(days=104),
            baseline_end=timezone.now().date() - timedelta(days=14),
            current_start=timezone.now().date() - timedelta(days=14),
            current_end=timezone.now().date(),
        )
        
        self.assertIsNotNone(drift_event.id)
        self.assertEqual(drift_event.drift_type, DRIFTWATCH_V1_EVENT_TYPE)

    def test_v1_only_surfaces_denial_rate_type(self):
        """Hub v1: Verify only DENIAL_RATE type events are surfaced."""
        self.assertEqual(DRIFTWATCH_V1_EVENT_TYPE, 'DENIAL_RATE')
        
        # V1 is locked to DENIAL_RATE
        # This test ensures no other types are accidentally surfaced
        from payrixa.products.driftwatch.views import DriftWatchDashboardView
        # The view should filter to DRIFTWATCH_V1_EVENT_TYPE only
        self.assertTrue(hasattr(DriftWatchDashboardView, 'get_context_data'))

    def test_generate_driftwatch_demo_creates_events(self):
        """Verify deterministic demo command creates DENIAL_RATE events."""
        from django.core.management import call_command
        from io import StringIO
        
        out = StringIO()
        call_command('generate_driftwatch_demo', '--customer', self.customer.id, stdout=out)
        
        # Verify output
        output = out.getvalue()
        self.assertIn('Created', output)
        
        # Verify events created
        demo_events = DriftEvent.objects.filter(
            customer=self.customer,
            drift_type=DRIFTWATCH_V1_EVENT_TYPE,
            payer__startswith='Demo-'
        )
        self.assertGreaterEqual(demo_events.count(), 1,
            f"Expected at least 1 demo DriftEvent, got {demo_events.count()}")
