"""
Management command to send pending webhook deliveries.

Usage:
    python manage.py send_webhooks
"""
from django.core.management.base import BaseCommand
from upstream.services.webhook_processor import process_pending_deliveries


class Command(BaseCommand):
    help = "Send pending webhook deliveries"

    def handle(self, *args, **options):
        self.stdout.write("Processing pending webhook deliveries...")

        results = process_pending_deliveries()

        self.stdout.write(
            self.style.SUCCESS(
                f"Webhook processing complete:\n"
                f'  Total: {results["total"]}\n'
                f'  Success: {results["success"]}\n'
                f'  Retrying: {results["retrying"]}\n'
                f'  Failed: {results["failed"]}'
            )
        )
