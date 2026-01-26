"""
Celery health check endpoints for monitoring and observability.

These endpoints provide:
- Worker health status
- Queue depth metrics
- Running task information
- Task execution statistics

Related: Phase 3 - DevOps Monitoring & Metrics (Task #4)
"""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from upstream.celery_monitoring import (
    get_celery_health_summary,
    get_running_tasks,
    get_scheduled_tasks,
    get_task_stats,
    cache_health_check,
)


@require_http_methods(["GET"])
@csrf_exempt
def celery_health_check(request):
    """
    Health check endpoint for Celery workers and queues.

    GET /api/celery/health/

    Returns:
        200: Celery is healthy
        503: Celery is unhealthy or degraded

    Response:
        {
            "status": "healthy|degraded|unhealthy",
            "workers": {
                "healthy": true,
                "active_workers": ["worker1@hostname"],
                "worker_count": 1
            },
            "queues": {
                "celery": 5
            },
            "recommendations": []
        }
    """
    # Use cached health check (5 min TTL) to avoid overwhelming broker
    health = cache_health_check(ttl=300)

    # Determine HTTP status code
    if health["status"] == "healthy":
        status_code = 200
    elif health["status"] == "degraded":
        status_code = 200  # Degraded but operational
    else:
        status_code = 503  # Unhealthy

    return JsonResponse(health, status=status_code)


@require_http_methods(["GET"])
@csrf_exempt
def celery_tasks(request):
    """
    Get information about running and scheduled tasks.

    GET /api/celery/tasks/

    Returns:
        {
            "running": [
                {
                    "worker": "worker1@hostname",
                    "task_name": "upstream.tasks.run_drift_detection",
                    "task_id": "abc-123",
                    "time_start": 1234567890
                }
            ],
            "scheduled": [
                {
                    "worker": "worker1@hostname",
                    "task_name": "upstream.tasks.send_scheduled_report",
                    "task_id": "def-456",
                    "eta": "2024-01-28T10:30:00"
                }
            ]
        }
    """
    running = get_running_tasks()
    scheduled = get_scheduled_tasks()

    return JsonResponse(
        {"running": running, "scheduled": scheduled, "running_count": len(running)}
    )


@require_http_methods(["GET"])
@csrf_exempt
def celery_stats(request):
    """
    Get statistics about task execution.

    GET /api/celery/stats/

    Returns:
        {
            "total_running": 3,
            "total_scheduled": 1,
            "by_task_name": {
                "upstream.tasks.run_drift_detection": {
                    "running": 2,
                    "scheduled": 0
                },
                "upstream.tasks.send_alert": {
                    "running": 1,
                    "scheduled": 1
                }
            }
        }
    """
    stats = get_task_stats()

    return JsonResponse(stats)
