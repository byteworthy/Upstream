"""
Management command to run DenialScope computation.

Usage:
    python manage.py compute_denialscope --customer 1 --start-date 2026-01-01 --end-date 2026-02-01
    python manage.py compute_denialscope --customer 1  # defaults to last 30 days
"""

from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from payrixa.models import Customer
from payrixa.products.denialscope.services import DenialScopeComputationService


class Command(BaseCommand):
    help = 'Compute DenialScope aggregates and signals for a customer'

    def add_arguments(self, parser):
        parser.add_argument(
            '--customer',
            type=int,
            required=True,
            help='Customer ID to compute DenialScope for'
        )
        parser.add_argument(
            '--start-date',
            type=str,
            help='Start date (YYYY-MM-DD). Defaults to 30 days ago.'
        )
        parser.add_argument(
            '--end-date',
            type=str,
            help='End date (YYYY-MM-DD). Defaults to today.'
        )
        parser.add_argument(
            '--min-volume',
            type=int,
            default=10,
            help='Minimum volume threshold for signal creation (default: 10)'
        )

    def handle(self, *args, **options):
        customer_id = options['customer']
        start_date = options.get('start_date')
        end_date = options.get('end_date')
        min_volume = options['min_volume']

        try:
            customer = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Customer {customer_id} does not exist'))
            return

        if end_date:
            end_date = self._parse_date(end_date, 'end-date')
        else:
            end_date = timezone.now().date()

        if start_date:
            start_date = self._parse_date(start_date, 'start-date')
        else:
            start_date = end_date - timedelta(days=30)

        if start_date >= end_date:
            self.stdout.write(self.style.ERROR('start-date must be before end-date'))
            return

        self.stdout.write(
            f'Computing DenialScope for {customer.name} from {start_date} to {end_date}...'
        )

        service = DenialScopeComputationService(customer)
        result = service.compute(start_date=start_date, end_date=end_date, min_volume=min_volume)

        self.stdout.write(self.style.SUCCESS('✓ DenialScope computation complete'))
        self.stdout.write(f"  Aggregates created: {result['aggregates_created']}")
        self.stdout.write(f"  Signals created: {result['signals_created']}")
        self.stdout.write(f"  Date range: {result['start_date']} to {result['end_date']}")

    def _parse_date(self, date_str, field_name):
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            raise ValueError(f"Invalid {field_name} format. Use YYYY-MM-DD")
