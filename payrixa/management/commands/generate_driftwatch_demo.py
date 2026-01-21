"""
DriftWatch deterministic demo data command.

Creates DriftEvent rows for customer 1 matching DRIFTWATCH_V1_EVENT_TYPE (DENIAL_RATE).
Safe to run repeatedly - clears previous demo events before recreating.
"""

from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone

from payrixa.models import Customer, DriftEvent, ReportRun
from payrixa.products.driftwatch import DRIFTWATCH_V1_EVENT_TYPE


class Command(BaseCommand):
    help = 'Generate deterministic DriftWatch demo data for customer 1'

    def add_arguments(self, parser):
        parser.add_argument(
            '--customer',
            type=int,
            default=1,
            help='Customer ID (default: 1)'
        )
        parser.add_argument(
            '--clear-only',
            action='store_true',
            help='Only clear existing demo events, do not recreate'
        )

    def handle(self, *args, **options):
        customer_id = options['customer']

        try:
            customer = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Customer {customer_id} not found'))
            return

        # Clear previously generated demo events (those with demo marker)
        deleted_count, _ = DriftEvent.objects.filter(
            customer=customer,
            drift_type=DRIFTWATCH_V1_EVENT_TYPE,
            payer__startswith='Demo-'
        ).delete()
        self.stdout.write(f'Cleared {deleted_count} previous demo DriftEvent rows')

        if options['clear_only']:
            return

        # Create or reuse a demo report run
        report_run, created = ReportRun.objects.get_or_create(
            customer=customer,
            run_type='driftwatch_demo',
            defaults={
                'started_at': timezone.now(),
                'finished_at': timezone.now(),
                'status': 'success',
                'summary_json': {'source': 'generate_driftwatch_demo'}
            }
        )
        if not created:
            report_run.finished_at = timezone.now()
            report_run.save()

        now = timezone.now().date()
        baseline_start = now - timedelta(days=104)
        baseline_end = now - timedelta(days=14)
        current_start = now - timedelta(days=14)
        current_end = now

        demo_events = [
            {
                'payer': 'Demo-UnitedHealthcare',
                'cpt_group': 'EVAL',
                'baseline_value': 0.15,
                'current_value': 0.42,
                'delta_value': 0.27,
                'severity': 0.85,
                'confidence': 0.92,
            },
            {
                'payer': 'Demo-Aetna',
                'cpt_group': 'IMAGING',
                'baseline_value': 0.08,
                'current_value': 0.25,
                'delta_value': 0.17,
                'severity': 0.65,
                'confidence': 0.88,
            },
            {
                'payer': 'Demo-Cigna',
                'cpt_group': 'PROC',
                'baseline_value': 0.20,
                'current_value': 0.35,
                'delta_value': 0.15,
                'severity': 0.55,
                'confidence': 0.80,
            },
        ]

        created_count = 0
        for data in demo_events:
            DriftEvent.objects.create(
                customer=customer,
                report_run=report_run,
                payer=data['payer'],
                cpt_group=data['cpt_group'],
                drift_type=DRIFTWATCH_V1_EVENT_TYPE,
                baseline_value=data['baseline_value'],
                current_value=data['current_value'],
                delta_value=data['delta_value'],
                severity=data['severity'],
                confidence=data['confidence'],
                baseline_start=baseline_start,
                baseline_end=baseline_end,
                current_start=current_start,
                current_end=current_end,
            )
            created_count += 1
            self.stdout.write(f"  Created: {data['payer']} {DRIFTWATCH_V1_EVENT_TYPE}")

        self.stdout.write(self.style.SUCCESS(
            f'✓ Created {created_count} DriftWatch demo events for customer {customer.name}'
        ))
