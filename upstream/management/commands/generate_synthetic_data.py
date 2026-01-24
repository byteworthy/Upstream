"""
Management command to generate synthetic claim data for performance testing.

Usage:
    python manage.py generate_synthetic_data --records 100000 --customer 1
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from upstream.models import Customer, ClaimRecord
from datetime import datetime, timedelta
import random


class Command(BaseCommand):
    help = 'Generate synthetic claim data for performance testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--records',
            type=int,
            default=10000,
            help='Number of claim records to generate (default: 10000)'
        )
        parser.add_argument(
            '--customer',
            type=int,
            required=True,
            help='Customer ID to generate data for'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Batch size for bulk creation (default: 1000)'
        )

    def handle(self, *args, **options):
        records_count = options['records']
        customer_id = options['customer']
        batch_size = options['batch_size']

        try:
            customer = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Customer {customer_id} does not exist'))
            return

        self.stdout.write(f'Generating {records_count} synthetic claim records for {customer.name}...')

        # Sample data for generation
        payers = ['Aetna', 'UnitedHealthcare', 'Cigna', 'Blue Cross', 'Humana', 'Medicare', 'Medicaid']
        cpt_codes = ['99213', '99214', '99215', '99232', '99233', '80053', '85025', '36415']
        locations = ['Clinic A', 'Clinic B', 'Hospital C', 'Urgent Care D']
        
        batch = []
        created = 0
        
        start_date = datetime.now() - timedelta(days=365)
        
        for i in range(records_count):
            # Generate realistic claim data
            service_date = start_date + timedelta(days=random.randint(0, 365))
            
            claim = ClaimRecord(
                customer=customer,
                claim_id=f'CLM-{customer_id}-{i+1:08d}',
                payer_name=random.choice(payers),
                service_date=service_date.date(),
                cpt_code=random.choice(cpt_codes),
                charged_amount=random.uniform(50, 500),
                allowed_amount=random.uniform(40, 450),
                paid_amount=random.uniform(30, 400),
                location=random.choice(locations),
                status=random.choice(['paid', 'denied', 'pending', 'adjusted']),
            )
            
            batch.append(claim)
            
            # Bulk create in batches
            if len(batch) >= batch_size:
                ClaimRecord.objects.bulk_create(batch, batch_size=batch_size)
                created += len(batch)
                self.stdout.write(f'  Created {created}/{records_count} records...', ending='\r')
                batch = []
        
        # Create remaining records
        if batch:
            ClaimRecord.objects.bulk_create(batch, batch_size=batch_size)
            created += len(batch)
        
        self.stdout.write(self.style.SUCCESS(f'\n✓ Successfully created {created} synthetic claim records'))
        self.stdout.write(f'  Customer: {customer.name}')
        self.stdout.write(f'  Date range: {start_date.date()} to {datetime.now().date()}')
