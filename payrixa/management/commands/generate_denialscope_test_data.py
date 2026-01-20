"""
Generate deterministic test data that guarantees DenialScope signals fire.

This creates a clear denial spike pattern:
- Baseline period (21 days): ~10% denial rate
- Recent period (7 days): ~50% denial rate

This MUST produce at least one denial_rate_spike signal.

Usage:
    python manage.py generate_denialscope_test_data --customer 1
    python manage.py generate_denialscope_test_data --customer 1 --clear
"""

from datetime import timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from payrixa.models import Customer, Upload, ClaimRecord


class Command(BaseCommand):
    help = 'Generate deterministic test data that guarantees DenialScope signals'

    def add_arguments(self, parser):
        parser.add_argument(
            '--customer',
            type=int,
            required=True,
            help='Customer ID to generate data for'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing claim records before generating'
        )

    def handle(self, *args, **options):
        customer_id = options['customer']
        clear = options['clear']

        try:
            customer = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Customer {customer_id} does not exist'))
            return

        if clear:
            deleted_count = ClaimRecord.objects.filter(customer=customer).delete()[0]
            self.stdout.write(f'Cleared {deleted_count} existing claim records')

        # Create upload record
        upload = Upload.objects.create(
            customer=customer,
            filename='denialscope_test_data.csv',
            status='success',
            row_count=0
        )

        today = timezone.now().date()
        claims_created = 0

        # === BASELINE PERIOD (Days -28 to -8): Low denial rate ~10% ===
        # 90 PAID, 10 DENIED = 10% denial rate
        baseline_start = today - timedelta(days=28)
        baseline_end = today - timedelta(days=8)
        
        self.stdout.write(f'Creating baseline period claims ({baseline_start} to {baseline_end})...')
        
        for day_offset in range(21):  # 21 days of baseline
            claim_date = baseline_start + timedelta(days=day_offset)
            
            # Create 5 claims per day: 4-5 PAID, 0-1 DENIED (~10% rate)
            for i in range(5):
                # Every 10th claim is denied (10% rate across all baseline)
                outcome = 'DENIED' if (day_offset * 5 + i) % 10 == 0 else 'PAID'
                
                ClaimRecord.objects.create(
                    customer=customer,
                    upload=upload,
                    payer='Blue Cross Blue Shield',
                    cpt='99213',
                    cpt_group='E&M Office Visit',
                    submitted_date=claim_date,
                    decided_date=claim_date + timedelta(days=3),
                    outcome=outcome,
                    allowed_amount=Decimal('150.00'),
                    denial_reason_code='CO-197' if outcome == 'DENIED' else None,
                    denial_reason_text='Precertification/authorization/notification absent' if outcome == 'DENIED' else None,
                )
                claims_created += 1

        baseline_claims = ClaimRecord.objects.filter(
            customer=customer,
            submitted_date__gte=baseline_start,
            submitted_date__lt=baseline_end
        )
        baseline_total = baseline_claims.count()
        baseline_denied = baseline_claims.filter(outcome='DENIED').count()
        baseline_rate = baseline_denied / baseline_total if baseline_total > 0 else 0
        
        self.stdout.write(f'  Baseline: {baseline_denied}/{baseline_total} denied ({baseline_rate:.1%})')

        # === RECENT PERIOD (Days -7 to 0): High denial rate ~50% ===
        # 25 PAID, 25 DENIED = 50% denial rate
        recent_start = today - timedelta(days=7)
        recent_end = today
        
        self.stdout.write(f'Creating recent period claims ({recent_start} to {recent_end})...')
        
        for day_offset in range(7):  # 7 days of recent
            claim_date = recent_start + timedelta(days=day_offset)
            
            # Create 8 claims per day: 4 PAID, 4 DENIED (50% rate)
            for i in range(8):
                outcome = 'DENIED' if i < 4 else 'PAID'
                
                ClaimRecord.objects.create(
                    customer=customer,
                    upload=upload,
                    payer='Blue Cross Blue Shield',
                    cpt='99213',
                    cpt_group='E&M Office Visit',
                    submitted_date=claim_date,
                    decided_date=claim_date + timedelta(days=3),
                    outcome=outcome,
                    allowed_amount=Decimal('150.00'),
                    denial_reason_code='CO-197' if outcome == 'DENIED' else None,
                    denial_reason_text='Precertification/authorization/notification absent' if outcome == 'DENIED' else None,
                )
                claims_created += 1

        recent_claims = ClaimRecord.objects.filter(
            customer=customer,
            submitted_date__gte=recent_start,
            submitted_date__lte=recent_end
        )
        recent_total = recent_claims.count()
        recent_denied = recent_claims.filter(outcome='DENIED').count()
        recent_rate = recent_denied / recent_total if recent_total > 0 else 0
        
        self.stdout.write(f'  Recent: {recent_denied}/{recent_total} denied ({recent_rate:.1%})')

        # Update upload record
        upload.row_count = claims_created
        upload.date_min = baseline_start
        upload.date_max = today
        upload.save()

        self.stdout.write(self.style.SUCCESS(f'✓ Created {claims_created} claim records'))
        self.stdout.write(f'  Baseline denial rate: {baseline_rate:.1%}')
        self.stdout.write(f'  Recent denial rate: {recent_rate:.1%}')
        self.stdout.write(f'  Expected signal: denial_rate_spike ({baseline_rate:.1%} → {recent_rate:.1%})')
        self.stdout.write('')
        self.stdout.write('Now run: python manage.py compute_denialscope --customer 1')
