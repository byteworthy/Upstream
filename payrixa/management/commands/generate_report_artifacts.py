from django.core.management.base import BaseCommand, CommandError
from payrixa.reporting.services import generate_weekly_drift_pdf
from payrixa.models import ReportRun

class Command(BaseCommand):
    help = 'Generate report artifacts (PDF) for a given report run'

    def add_arguments(self, parser):
        parser.add_argument(
            'report_run_id',
            type=int,
            help='ID of the report run to generate artifacts for'
        )

    def handle(self, *args, **options):
        report_run_id = options['report_run_id']

        try:
            # Verify report run exists
            report_run = ReportRun.objects.get(id=report_run_id)
            
            self.stdout.write(
                self.style.WARNING(f'Generating PDF artifact for Report Run {report_run_id}...')
            )

            # Generate PDF artifact
            artifact = generate_weekly_drift_pdf(report_run_id)

            # Print success message
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ Successfully generated PDF artifact (ID: {artifact.id})\n'
                    f'  Customer: {artifact.customer.name}\n'
                    f'  Report Run: {artifact.report_run.id}\n'
                    f'  Kind: {artifact.kind}\n'
                    f'  File: {artifact.file_path}\n'
                    f'  Content Hash: {artifact.content_hash[:16]}...\n'
                    f'  Created: {artifact.created_at}'
                )
            )

        except ReportRun.DoesNotExist:
            raise CommandError(f'Report Run with ID {report_run_id} does not exist')
        except Exception as e:
            raise CommandError(f'Failed to generate artifact: {str(e)}')
