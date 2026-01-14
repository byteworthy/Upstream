from django.core.management.base import BaseCommand
from payrixa.models import Customer
from payrixa.services.payer_drift import compute_weekly_payer_drift
from datetime import datetime

class Command(BaseCommand):
    help = 'Run weekly payer drift computation'

    def add_arguments(self, parser):
        parser.add_argument('--customer-id', type=int, required=True, help='Customer ID')
        parser.add_argument('--as-of', type=str, help='As-of date in YYYY-MM-DD format')
        parser.add_argument('--baseline-days', type=int, default=90, help='Baseline days (default: 90)')
        parser.add_argument('--current-days', type=int, default=14, help='Current days (default: 14)')
        parser.add_argument('--min-volume', type=int, default=30, help='Minimum volume threshold (default: 30)')

    def handle(self, *args, **options):
        try:
            # Get customer
            customer_id = options['customer_id']
            customer = Customer.objects.get(id=customer_id)

            # Parse as_of_date if provided
            as_of_date = None
            if options['as_of']:
                as_of_date = datetime.strptime(options['as_of'], '%Y-%m-%d').date()

            # Run computation
            report_run = compute_weekly_payer_drift(
                customer=customer,
                baseline_days=options['baseline_days'],
                current_days=options['current_days'],
                min_volume=options['min_volume'],
                as_of_date=as_of_date
            )

            # Print summary
            self.stdout.write(self.style.SUCCESS(
                f'Report run {report_run.id} completed successfully. '
                f'Events created: {report_run.summary_json.get("events_created", 0)}'
            ))

        except Customer.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Customer with ID {customer_id} not found'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error running payer drift computation: {str(e)}'))
<task_progress>
- [x] Inspect current model fields (no changes yet)
- [x] Create payer_drift.py service module
- [x] Implement compute_weekly_payer_drift function
- [x] Add management command
- [ ] Update reports page
- [ ] Add tests
</task_progress>
</write_to_file>
