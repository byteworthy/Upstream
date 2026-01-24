"""
Management command to cleanup old data based on retention policies.

Usage:
    python manage.py cleanup_old_data
    python manage.py cleanup_old_data --dry-run
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from upstream.models import Upload, DriftEvent, ReportRun
from upstream.reporting.models import ReportArtifact
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Cleanup old data based on retention policies'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No data will be deleted'))
        
        # Retention policies (in days)
        RETENTION_POLICIES = {
            'uploads': 90,  # Keep raw uploads for 90 days
            'drift_events': 180,  # Keep drift events for 180 days
            'report_runs': 365,  # Keep report runs for 1 year
            'artifacts_csv': 30,  # Keep CSV artifacts for 30 days
            'artifacts_pdf': 90,  # Keep PDF artifacts for 90 days
        }
        
        total_deleted = 0
        
        # Cleanup old uploads
        cutoff_date = timezone.now() - timedelta(days=RETENTION_POLICIES['uploads'])
        old_uploads = Upload.objects.filter(uploaded_at__lt=cutoff_date)
        count = old_uploads.count()
        
        if count > 0:
            self.stdout.write(f'Found {count} old uploads (older than {RETENTION_POLICIES["uploads"]} days)')
            if not dry_run:
                deleted_count, _ = old_uploads.delete()
                total_deleted += deleted_count
                self.stdout.write(self.style.SUCCESS(f'Deleted {deleted_count} old uploads'))
                logger.info(f'Cleanup: deleted {deleted_count} old uploads')
        
        # Cleanup old drift events (orphaned ones without report runs)
        cutoff_date = timezone.now() - timedelta(days=RETENTION_POLICIES['drift_events'])
        old_drift_events = DriftEvent.objects.filter(
            created_at__lt=cutoff_date,
            report_run__isnull=True
        )
        count = old_drift_events.count()
        
        if count > 0:
            self.stdout.write(f'Found {count} old orphaned drift events')
            if not dry_run:
                deleted_count, _ = old_drift_events.delete()
                total_deleted += deleted_count
                self.stdout.write(self.style.SUCCESS(f'Deleted {deleted_count} old drift events'))
                logger.info(f'Cleanup: deleted {deleted_count} old drift events')
        
        # Cleanup old report runs
        cutoff_date = timezone.now() - timedelta(days=RETENTION_POLICIES['report_runs'])
        old_report_runs = ReportRun.objects.filter(started_at__lt=cutoff_date)
        count = old_report_runs.count()
        
        if count > 0:
            self.stdout.write(f'Found {count} old report runs (older than {RETENTION_POLICIES["report_runs"]} days)')
            if not dry_run:
                # This will cascade delete related drift events and artifacts
                deleted_count, _ = old_report_runs.delete()
                total_deleted += deleted_count
                self.stdout.write(self.style.SUCCESS(f'Deleted {deleted_count} old report runs'))
                logger.info(f'Cleanup: deleted {deleted_count} old report runs')
        
        # Cleanup old CSV artifacts
        cutoff_date = timezone.now() - timedelta(days=RETENTION_POLICIES['artifacts_csv'])
        old_csv_artifacts = ReportArtifact.objects.filter(
            created_at__lt=cutoff_date,
            kind__icontains='csv'
        )
        count = old_csv_artifacts.count()
        
        if count > 0:
            self.stdout.write(f'Found {count} old CSV artifacts')
            if not dry_run:
                deleted_count, _ = old_csv_artifacts.delete()
                total_deleted += deleted_count
                self.stdout.write(self.style.SUCCESS(f'Deleted {deleted_count} old CSV artifacts'))
                logger.info(f'Cleanup: deleted {deleted_count} old CSV artifacts')
        
        # Cleanup old PDF artifacts
        cutoff_date = timezone.now() - timedelta(days=RETENTION_POLICIES['artifacts_pdf'])
        old_pdf_artifacts = ReportArtifact.objects.filter(
            created_at__lt=cutoff_date,
            kind='weekly_drift_summary'
        )
        count = old_pdf_artifacts.count()
        
        if count > 0:
            self.stdout.write(f'Found {count} old PDF artifacts')
            if not dry_run:
                deleted_count, _ = old_pdf_artifacts.delete()
                total_deleted += deleted_count
                self.stdout.write(self.style.SUCCESS(f'Deleted {deleted_count} old PDF artifacts'))
                logger.info(f'Cleanup: deleted {deleted_count} old PDF artifacts')
        
        # Summary
        if dry_run:
            self.stdout.write(self.style.WARNING(f'DRY RUN: Would have deleted {total_deleted} records'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Cleanup complete: Deleted {total_deleted} total records'))
