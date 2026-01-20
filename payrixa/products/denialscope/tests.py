from datetime import timedelta
from django.core.management import call_command
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone

from payrixa.core.models import ProductConfig
from payrixa.ingestion.models import SystemEvent
from payrixa.models import Customer, ClaimRecord, Upload, UserProfile
from payrixa.products.denialscope.models import DenialAggregate, DenialSignal
from payrixa.products.denialscope.services import DenialScopeComputationService


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

        self.upload = Upload.objects.create(
            customer=self.customer,
            filename='claims.csv',
            status='success'
        )

    def _create_claim(self, payer, outcome, days_ago, denial_reason=None, allowed_amount=100):
        submitted_date = timezone.now().date() - timedelta(days=days_ago)
        decided_date = submitted_date + timedelta(days=2)
        return ClaimRecord.objects.create(
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
        service.compute()

        response = self.client.get('/portal/products/denialscope/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Total Denials')
        self.assertContains(response, 'Top denial reasons by payer')
        self.assertContains(response, 'Recent signals')

    def test_management_command_idempotent(self):
        self._create_claim('United', 'DENIED', 5, denial_reason='CO-123')
        self._create_claim('United', 'PAID', 5)

        call_command('compute_denialscope', customer=self.customer.id)
        first_count = DenialAggregate.objects.filter(customer=self.customer).count()

        call_command('compute_denialscope', customer=self.customer.id)
        second_count = DenialAggregate.objects.filter(customer=self.customer).count()

        self.assertEqual(first_count, second_count)

    def test_denialscope_enablement_still_works(self):
        response = self.client.get('/portal/products/denialscope/')
        self.assertEqual(response.status_code, 200)
        
        ProductConfig.objects.filter(customer=self.customer, product_slug='denialscope').update(enabled=False)
        response = self.client.get('/portal/products/denialscope/')
        self.assertEqual(response.status_code, 403)
