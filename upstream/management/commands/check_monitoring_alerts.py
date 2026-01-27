"""
Management command to evaluate monitoring alert rules.

Evaluates platform health metrics (error rates, latency, database pool,
Celery failures) against configured thresholds and sends notifications
when alerts are triggered.

Usage:
    python manage.py check_monitoring_alerts [options]

Options:
    --dry-run: Evaluate rules but don't send notifications
    --rule RULE_NAME: Evaluate only specific rule
    --verbose: Show detailed output

This command should be run periodically (via cron or Celery beat):
    */5 * * * * cd /app && python manage.py check_monitoring_alerts
"""

from django.core.management.base import BaseCommand
from upstream.monitoring.alert_rules import (
    evaluate_alert_rules,
    send_alert_notification,
    ALERT_RULES,
)
import logging

logger = logging.getLogger("upstream.monitoring.alerts")


class Command(BaseCommand):
    help = "Evaluate monitoring alert rules and send notifications"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Evaluate rules without sending notifications",
        )
        parser.add_argument(
            "--rule",
            type=str,
            help="Evaluate specific rule only (by name)",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Enable detailed output",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)
        rule_filter = options.get("rule")
        verbose = options.get("verbose", False)

        # Set up logging level
        if verbose:
            logger.setLevel(logging.DEBUG)

        # Validate rule filter
        if rule_filter:
            rule_names = [r["name"] for r in ALERT_RULES]
            if rule_filter not in rule_names:
                self.stdout.write(
                    self.style.ERROR(
                        f"Unknown rule: {rule_filter}\n"
                        f"Available rules: {', '.join(rule_names)}"
                    )
                )
                return

        # Header
        total_rules = len(ALERT_RULES)
        if rule_filter:
            self.stdout.write(
                f"Evaluating 1 monitoring alert rule "
                f"(filtered to: {rule_filter})..."
            )
        else:
            self.stdout.write(
                f"Evaluating {total_rules} monitoring alert rules..."
            )

        if dry_run:
            self.stdout.write(
                self.style.WARNING("[DRY RUN MODE - No notifications will be sent]")
            )

        # Evaluate alert rules
        try:
            triggered_alerts = evaluate_alert_rules()

            # Filter if specific rule requested
            if rule_filter:
                triggered_alerts = [
                    a for a in triggered_alerts if a["rule_name"] == rule_filter
                ]

            # Display results
            self.stdout.write("")  # Blank line

            # Show all rules status (triggered or OK)
            rules_to_check = ALERT_RULES
            if rule_filter:
                rules_to_check = [
                    r for r in ALERT_RULES if r["name"] == rule_filter
                ]

            for rule in rules_to_check:
                rule_name = rule["name"]
                triggered = any(
                    a["rule_name"] == rule_name for a in triggered_alerts
                )

                if triggered:
                    alert = next(
                        a for a in triggered_alerts
                        if a["rule_name"] == rule_name
                    )
                    status_icon = self.style.ERROR("[TRIGGERED]")
                    msg = f"{status_icon} {rule_name}: {alert['message']}"
                else:
                    status_icon = self.style.SUCCESS("[OK]")
                    msg = f"{status_icon} {rule_name}"

                self.stdout.write(msg)

            # Send notifications
            self.stdout.write("")  # Blank line

            if not triggered_alerts:
                self.stdout.write(
                    self.style.SUCCESS(
                        "All monitoring checks passed - no alerts triggered"
                    )
                )
                return

            if dry_run:
                self.stdout.write(
                    self.style.WARNING(
                        f"Would send {len(triggered_alerts)} notifications "
                        f"(dry run mode)"
                    )
                )
            else:
                # Send notifications
                email_sent = 0
                slack_sent = 0
                errors = []

                for alert in triggered_alerts:
                    try:
                        result = send_alert_notification(alert)
                        if result["email_sent"]:
                            email_sent += 1
                        if result["slack_sent"]:
                            slack_sent += 1
                        if result["errors"]:
                            errors.extend(result["errors"])
                    except Exception as e:
                        error_msg = (
                            f"Failed to send notification for "
                            f"{alert['rule_name']}: {e}"
                        )
                        errors.append(error_msg)
                        logger.error(error_msg, exc_info=True)

                # Summary
                total_notifications = email_sent + slack_sent
                if total_notifications > 0:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Sent {total_notifications} notifications "
                            f"({email_sent} email, {slack_sent} slack)"
                        )
                    )

                if errors:
                    self.stdout.write("")  # Blank line
                    self.stdout.write(
                        self.style.WARNING(
                            f"{len(errors)} notification errors:"
                        )
                    )
                    for error in errors:
                        self.stdout.write(f"  - {error}")

        except Exception as e:
            # Handle errors gracefully - alerting system issues shouldn't
            # break cron jobs
            error_msg = f"Error evaluating alert rules: {e}"
            self.stdout.write(self.style.ERROR(error_msg))
            logger.error(error_msg, exc_info=True)

            # Exit with 0 to prevent cron failure notifications
            # The error is logged for investigation
            return
