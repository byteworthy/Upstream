"""
Management command to initialize data quality features for customers.

Usage:
    python manage.py init_data_quality --customer <customer_name>
    python manage.py init_data_quality --all
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from upstream.models import Customer
from upstream.core.default_validation_rules import create_default_rules_for_customer


class Command(BaseCommand):
    help = 'Initialize data quality features (validation rules) for customers'

    def add_arguments(self, parser):
        parser.add_argument(
            '--customer',
            type=str,
            help='Customer name to initialize'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Initialize for all customers'
        )

    @transaction.atomic
    def handle(self, *args, **options):
        customer_name = options.get('customer')
        all_customers = options.get('all')

        if not customer_name and not all_customers:
            raise CommandError('Must specify either --customer <name> or --all')

        if customer_name and all_customers:
            raise CommandError('Cannot specify both --customer and --all')

        if customer_name:
            # Initialize for specific customer
            try:
                customer = Customer.objects.get(name=customer_name)
            except Customer.DoesNotExist:
                raise CommandError(f'Customer "{customer_name}" not found')

            self.init_customer(customer)
        else:
            # Initialize for all customers
            customers = Customer.objects.all()
            self.stdout.write(f'Found {customers.count()} customers')

            for customer in customers:
                self.init_customer(customer)

        self.stdout.write(self.style.SUCCESS('✓ Data quality initialization complete'))

    def init_customer(self, customer):
        """Initialize data quality features for a customer."""
        self.stdout.write(f'Initializing data quality for: {customer.name}')

        # Create default validation rules
        rules = create_default_rules_for_customer(customer)

        if rules:
            self.stdout.write(
                self.style.SUCCESS(f'  ✓ Created {len(rules)} validation rules')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'  • Validation rules already exist')
            )
