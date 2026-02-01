from datetime import timedelta
from io import StringIO
from django.core.management import call_command
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone

from upstream.core.models import ProductConfig
from upstream.core.tenant import customer_context
from upstream.ingestion.models import SystemEvent
from upstream.models import Customer, ClaimRecord, Upload, UserProfile
from upstream.products.denialscope.models import DenialAggregate, DenialSignal
from upstream.products.denialscope.services import DenialScopeComputationService


class DenialScopeTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(name='DenialScope Customer')
        self.user = User.objects.create_user(username='denial_user', password='pass')
        UserProfile.objects.create(user=self.user, customer=self.customer, role='admin')
        self.client.force_login(self.user)

        ProductConfig.objects.create(
            customer=self.customer,
            product_slug='denialscope',
            enabled=True
        )

        self.upload = Upload.all_objects.create(
            customer=self.customer,
            filename='claims.csv',
            status='success'
        )

    def _create_claim(self, payer, outcome, days_ago, denial_reason=None, allowed_amount=100):
        submitted_date = timezone.now().date() - timedelta(days=days_ago)
        decided_date = submitted_date + timedelta(days=2)
        return ClaimRecord.all_objects.create(
            customer=self.customer,
            upload=self.upload,
            payer=payer,
            cpt='99213',
            cpt_group='OFFICE',
            submitted_date=submitted_date,
            decided_date=decided_date,
            outcome=outcome,
            allowed_amount=allowed_amount,
            denial_reason_code=denial_reason,
        )

    def test_compute_creates_aggregates(self):
        self._create_claim('Aetna', 'DENIED', 5, denial_reason='CO-45')
        self._create_claim('Aetna', 'PAID', 5)
        self._create_claim('Aetna', 'DENIED', 6, denial_reason='CO-45')

        service = DenialScopeComputationService(self.customer)
        with customer_context(self.customer):
            result = service.compute()

            self.assertGreater(result['aggregates_created'], 0)
            aggregate = DenialAggregate.objects.filter(customer=self.customer).first()
            self.assertIsNotNone(aggregate)
            self.assertEqual(aggregate.payer, 'Aetna')
            self.assertIn(aggregate.denial_reason, ['CO-45', 'DENIED'])

    def test_signal_creation_publishes_system_event(self):
        # Baseline window: low denial count
        for i in range(12):
            self._create_claim('Cigna', 'DENIED', 20, denial_reason='CO-97')
            self._create_claim('Cigna', 'PAID', 20)

        # Recent window: spike
        for i in range(20):
            self._create_claim('Cigna', 'DENIED', 3, denial_reason='CO-97')
            self._create_claim('Cigna', 'PAID', 3)

        service = DenialScopeComputationService(self.customer)
        with customer_context(self.customer):
            service.compute(min_volume=10)

            self.assertTrue(DenialSignal.objects.filter(customer=self.customer).exists())
            self.assertTrue(SystemEvent.objects.filter(
                customer=self.customer,
            event_type='denialscope_signal_created'
        ).exists())

    def test_dashboard_renders_with_data(self):
        self._create_claim('Aetna', 'DENIED', 5, denial_reason='CO-45')
        self._create_claim('Aetna', 'PAID', 5)

        service = DenialScopeComputationService(self.customer)
        with customer_context(self.customer):
            service.compute()

        response = self.client.get('/portal/products/denialscope/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Total Denials')
        self.assertContains(response, 'Top denial reasons by payer')
        self.assertContains(response, 'Recent signals')

    def test_management_command_idempotent(self):
        self._create_claim('United', 'DENIED', 5, denial_reason='CO-123')
        self._create_claim('United', 'PAID', 5)

        out = StringIO()
        call_command('compute_denialscope', customer=self.customer.id, stdout=out)
        first_count = DenialAggregate.objects.filter(customer=self.customer).count()

        out = StringIO()
        call_command('compute_denialscope', customer=self.customer.id, stdout=out)
        second_count = DenialAggregate.objects.filter(customer=self.customer).count()

        self.assertEqual(first_count, second_count)

    def test_denialscope_enablement_still_works(self):
        response = self.client.get('/portal/products/denialscope/')
        self.assertEqual(response.status_code, 200)
        
        ProductConfig.objects.filter(customer=self.customer, product_slug='denialscope').update(enabled=False)
        response = self.client.get('/portal/products/denialscope/')
        self.assertEqual(response.status_code, 403)

    def test_v1_signal_denial_dollars_spike_fires(self):
        """
        V1 deterministic test: Verify denial_dollars_spike signal fires.

        This test mirrors the generate_denialscope_test_data pattern:
        - Baseline: low denial rate/dollars over 21 days
        - Recent: high denial rate/dollars over 7 days
        - Expected signal: denial_dollars_spike
        """
        from decimal import Decimal

        # Baseline period (21 days): 10% denial rate, ~$1,500 denied
        for day in range(21):
            days_ago = 28 - day  # Days 28-8
            # 10 claims per day: 1 denied, 9 paid
            for i in range(10):
                if i == 0:
                    self._create_claim(
                        'Blue Cross Blue Shield', 'DENIED', days_ago,
                        denial_reason='CO-197', allowed_amount=150
                    )
                else:
                    self._create_claim(
                        'Blue Cross Blue Shield', 'PAID', days_ago,
                        allowed_amount=150
                    )

        # Recent period (7 days): 50% denial rate, ~$5,250 denied
        for day in range(7):
            days_ago = 7 - day  # Days 7-1
            # 10 claims per day: 5 denied, 5 paid
            for i in range(10):
                if i < 5:
                    self._create_claim(
                        'Blue Cross Blue Shield', 'DENIED', days_ago,
                        denial_reason='CO-197', allowed_amount=150
                    )
                else:
                    self._create_claim(
                        'Blue Cross Blue Shield', 'PAID', days_ago,
                        allowed_amount=150
                    )

        # Run computation
        service = DenialScopeComputationService(self.customer)
        with customer_context(self.customer):
            result = service.compute(min_volume=5)

            # Assert at least one signal created
            signal_count = DenialSignal.objects.filter(customer=self.customer).count()
            self.assertGreaterEqual(signal_count, 1,
                f"Expected at least 1 signal, got {signal_count}. Result: {result}")

            # Assert denial_dollars_spike is the signal type (V1 primary signal)
            latest_signal = DenialSignal.objects.filter(
                customer=self.customer
            ).order_by('-created_at').first()

            self.assertIsNotNone(latest_signal)
            self.assertEqual(latest_signal.signal_type, 'denial_dollars_spike',
                f"V1 expects denial_dollars_spike, got {latest_signal.signal_type}")
            self.assertIn(latest_signal.severity, ['critical', 'medium', 'high'],
                f"Expected severity critical/medium/high, got {latest_signal.severity}")
            self.assertGreater(latest_signal.confidence, 0.5)

    def test_dollar_spike_50k_threshold_triggers_signal(self):
        """Test $50K threshold triggers signal."""
        from upstream.constants import DENIAL_DOLLARS_SPIKE_THRESHOLD
        for day in range(21):
            days_ago = 28 - day
            for i in range(5):
                self._create_claim('Humana', 'DENIED', days_ago, denial_reason='CO-50', allowed_amount=1000)
                self._create_claim('Humana', 'PAID', days_ago, allowed_amount=1000)
        for day in range(7):
            days_ago = 7 - day
            for i in range(10):
                self._create_claim('Humana', 'DENIED', days_ago, denial_reason='CO-50', allowed_amount=1000)
            for i in range(5):
                self._create_claim('Humana', 'PAID', days_ago, allowed_amount=1000)
        service = DenialScopeComputationService(self.customer)
        with customer_context(self.customer):
            result = service.compute(min_volume=5)
            signals = DenialSignal.objects.filter(customer=self.customer, signal_type='denial_dollars_spike')
            self.assertTrue(signals.exists(), f"Expected denial_dollars_spike signal. Result: {result}")
            self.assertEqual(DENIAL_DOLLARS_SPIKE_THRESHOLD, 50000)
