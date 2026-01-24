"""
Management command to run DelayGuard computation.

Usage:
    python manage.py compute_delayguard --customer 1
    python manage.py compute_delayguard --customer 1 --end-date 2026-02-01
    python manage.py compute_delayguard --all  # Run for all customers
"""

from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from payrixa.models import Customer
from payrixa.products.delayguard.services import DelayGuardComputationService
from payrixa.products.delayguard import (
    DELAYGUARD_CURRENT_WINDOW_DAYS,
    DELAYGUARD_BASELINE_WINDOW_DAYS,
    DELAYGUARD_MIN_SAMPLE_SIZE,
)


class Command(BaseCommand):
    help = 'Compute DelayGuard aggregates and signals for payment delay drift'

    def add_arguments(self, parser):
        parser.add_argument(
            '--customer',
            type=int,
            help='Customer ID to compute DelayGuard for'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Run for all customers'
        )
        parser.add_argument(
            '--end-date',
            type=str,
            help='End date for current window (YYYY-MM-DD). Defaults to today.'
        )
        parser.add_argument(
            '--current-window-days',
            type=int,
            default=DELAYGUARD_CURRENT_WINDOW_DAYS,
            help=f'Current window size in days (default: {DELAYGUARD_CURRENT_WINDOW_DAYS})'
        )
        parser.add_argument(
            '--baseline-window-days',
            type=int,
            default=DELAYGUARD_BASELINE_WINDOW_DAYS,
            help=f'Baseline window size in days (default: {DELAYGUARD_BASELINE_WINDOW_DAYS})'
        )
        parser.add_argument(
            '--min-sample-size',
            type=int,
            default=DELAYGUARD_MIN_SAMPLE_SIZE,
            help=f'Minimum sample size for signal generation (default: {DELAYGUARD_MIN_SAMPLE_SIZE})'
        )

    def handle(self, *args, **options):
        if not options['all'] and not options['customer']:
            self.stdout.write(self.style.ERROR('Must specify either --customer or --all'))
            return

        # Parse end date
        end_date = None
        if options.get('end_date'):
            try:
                end_date = datetime.strptime(options['end_date'], '%Y-%m-%d').date()
            except ValueError:
                self.stdout.write(self.style.ERROR('Invalid end-date format. Use YYYY-MM-DD'))
                return
        else:
            end_date = timezone.now().date()

        # Get customers to process
        if options['all']:
            customers = Customer.objects.all()
            self.stdout.write(f'Running DelayGuard for {customers.count()} customers...')
        else:
            try:
                customer = Customer.objects.get(id=options['customer'])
                customers = [customer]
            except Customer.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Customer {options['customer']} does not exist"))
                return

        # Process each customer
        total_signals = 0
        total_aggregates = 0

        for customer in customers:
            self.stdout.write(f'\n📊 Processing {customer.name}...')

            try:
                service = DelayGuardComputationService(customer)
                result = service.compute(
                    end_date=end_date,
                    current_window_days=options['current_window_days'],
                    baseline_window_days=options['baseline_window_days'],
                    min_sample_size=options['min_sample_size'],
                )

                total_aggregates += result['aggregates_created']
                total_signals += result['signals_created']

                self.stdout.write(self.style.SUCCESS(f"  ✓ {customer.name} complete"))
                self.stdout.write(f"    Aggregates: {result['aggregates_created']}")
                self.stdout.write(f"    Signals: {result['signals_created']}")

                if result['data_quality_warnings']:
                    self.stdout.write(self.style.WARNING(f"    Warnings: {len(result['data_quality_warnings'])}"))
                    for warning in result['data_quality_warnings'][:3]:  # Show first 3
                        self.stdout.write(f"      - {warning['payer']}: {warning['warning']}")

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ Error processing {customer.name}: {str(e)}"))
                continue

        # Summary
        self.stdout.write(self.style.SUCCESS(f'\n✓ DelayGuard computation complete'))
        self.stdout.write(f"  Total customers: {len(customers)}")
        self.stdout.write(f"  Total aggregates: {total_aggregates}")
        self.stdout.write(f"  Total signals: {total_signals}")
        self.stdout.write(f"  Analysis date: {end_date}")
