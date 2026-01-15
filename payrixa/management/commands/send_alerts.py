"""
Management command to send pending alert notifications.

Usage:
    python manage.py send_alerts
"""
from django.core.management.base import BaseCommand
from payrixa.alerts.services import process_pending_alerts


class Command(BaseCommand):
    help = 'Send pending alert notifications'

    def handle(self, *args, **options):
        self.stdout.write('Processing pending alert events...')
        
        results = process_pending_alerts()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Alert processing complete:\n'
                f'  Total: {results["total"]}\n'
                f'  Sent: {results["sent"]}\n'
                f'  Failed: {results["failed"]}'
            )
        )
