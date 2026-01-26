"""
Management command to check Celery worker health and queue status.

Usage:
    python manage.py celery_health

This command:
- Checks if Celery workers are running
- Reports queue depth
- Shows running tasks
- Provides recommendations

Related: Phase 3 - DevOps Monitoring & Metrics (Task #4)
"""

from django.core.management.base import BaseCommand
from upstream.celery_monitoring import (
    get_celery_health_summary,
    get_running_tasks,
    get_scheduled_tasks,
    get_task_stats,
)


class Command(BaseCommand):
    help = "Check Celery worker health and queue status"

    def add_arguments(self, parser):
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Show detailed task information",
        )

    def handle(self, *args, **options):
        verbose = options["verbose"]

        self.stdout.write(self.style.SUCCESS("Celery Health Check"))
        self.stdout.write("=" * 60)

        # Get health summary
        health = get_celery_health_summary()

        # Overall status
        status = health["status"]
        if status == "healthy":
            status_style = self.style.SUCCESS
            status_icon = "✓"
        elif status == "degraded":
            status_style = self.style.WARNING
            status_icon = "⚠"
        else:
            status_style = self.style.ERROR
            status_icon = "✗"

        self.stdout.write(
            f"\nOverall Status: {status_style(status.upper())} {status_icon}"
        )

        # Worker status
        self.stdout.write("\nWorker Status:")
        workers = health["workers"]
        if workers["healthy"]:
            self.stdout.write(
                f"  {self.style.SUCCESS('✓')} Workers: "
                f"{workers['worker_count']} active"
            )
            if verbose:
                for worker in workers["active_workers"]:
                    self.stdout.write(f"    - {worker}")
        else:
            self.stdout.write(
                f"  {self.style.ERROR('✗')} Workers: "
                f"{workers.get('error', 'No workers found')}"
            )

        # Queue status
        self.stdout.write("\nQueue Status:")
        queues = health["queues"]
        for queue_name, queue_depth in queues.items():
            if queue_depth == -1:
                self.stdout.write(
                    f"  {self.style.WARNING('?')} {queue_name}: unavailable"
                )
            elif queue_depth > 100:
                self.stdout.write(
                    f"  {self.style.WARNING('⚠')} {queue_name}: "
                    f"{queue_depth} tasks (high)"
                )
            else:
                self.stdout.write(
                    f"  {self.style.SUCCESS('✓')} {queue_name}: "
                    f"{queue_depth} tasks"
                )

        # Task statistics
        if verbose:
            self.stdout.write("\nTask Statistics:")
            stats = get_task_stats()
            self.stdout.write(f"  Running: {stats['total_running']}")
            self.stdout.write(f"  Scheduled: {stats['total_scheduled']}")

            if stats["by_task_name"]:
                self.stdout.write("\n  By Task Name:")
                for task_name, task_stats in stats["by_task_name"].items():
                    self.stdout.write(
                        f"    {task_name}: "
                        f"running={task_stats['running']}, "
                        f"scheduled={task_stats['scheduled']}"
                    )

        # Recommendations
        if health["recommendations"]:
            self.stdout.write("\nRecommendations:")
            for rec in health["recommendations"]:
                self.stdout.write(f"  • {rec}")

        # Exit with appropriate code
        if status == "unhealthy":
            self.stdout.write(
                self.style.ERROR(
                    "\n✗ Celery is UNHEALTHY - workers not running"
                )
            )
            exit(1)
        elif status == "degraded":
            self.stdout.write(
                self.style.WARNING(
                    "\n⚠ Celery is DEGRADED - performance may be impacted"
                )
            )
            exit(0)  # Still operational
        else:
            self.stdout.write(
                self.style.SUCCESS("\n✓ Celery is HEALTHY")
            )
            exit(0)
