"""
Celery task monitoring and health checks for Upstream.

This module provides:
- Task execution tracking (success/failure/duration)
- Worker health checks
- Queue depth monitoring
- Integration with Prometheus metrics

Related: Phase 3 - DevOps Monitoring & Metrics (Task #4)
"""

import logging
import time
from functools import wraps
from typing import Any, Callable, Dict, List, Optional
from celery import Task
from celery.app.control import Inspect
from django.core.cache import cache
from upstream.metrics import (
    background_job_started,
    background_job_completed,
    background_job_failed,
    background_job_duration,
)

logger = logging.getLogger(__name__)


# =============================================================================
# TASK MONITORING DECORATOR
# =============================================================================


def monitor_task(task_func: Callable) -> Callable:
    """
    Decorator to automatically monitor Celery task execution.

    Tracks:
    - Task starts (counter)
    - Task completions (counter)
    - Task failures (counter with error type)
    - Task duration (histogram)

    Usage:
        @shared_task
        @monitor_task
        def my_task(arg1, arg2):
            # Task logic here
            pass

    Args:
        task_func: The Celery task function to monitor

    Returns:
        Wrapped task function with monitoring
    """

    @wraps(task_func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Get task name
        task_name = task_func.__name__
        if hasattr(task_func, "name"):
            task_name = task_func.name

        # Get customer_id if available (for label)
        customer_id = "unknown"
        if "customer_id" in kwargs:
            customer_id = str(kwargs["customer_id"])
        elif len(args) > 0 and isinstance(args[0], int):
            # Assume first arg might be customer_id
            customer_id = str(args[0])

        # Track task start
        background_job_started.labels(
            task_name=task_name, customer_id=customer_id
        ).inc()

        start_time = time.time()
        error = None

        try:
            # Execute task
            result = task_func(*args, **kwargs)

            # Track success
            duration = time.time() - start_time
            background_job_completed.labels(
                task_name=task_name, customer_id=customer_id
            ).inc()
            background_job_duration.labels(task_name=task_name).observe(duration)

            logger.info(
                f"Task {task_name} completed successfully in {duration:.2f}s "
                f"(customer={customer_id})"
            )

            return result

        except Exception as e:
            # Track failure
            duration = time.time() - start_time
            error_type = e.__class__.__name__

            background_job_failed.labels(
                task_name=task_name, error_type=error_type, customer_id=customer_id
            ).inc()
            background_job_duration.labels(task_name=task_name).observe(duration)

            logger.error(
                f"Task {task_name} failed after {duration:.2f}s "
                f"with {error_type}: {str(e)} (customer={customer_id})"
            )

            # Re-raise to maintain Celery's error handling
            raise

    return wrapper


class MonitoredTask(Task):
    """
    Base class for Celery tasks with automatic monitoring.

    Usage:
        @shared_task(base=MonitoredTask)
        def my_task(arg1, arg2):
            # Task logic here
            pass

    This class automatically tracks:
    - Task starts
    - Task completions
    - Task failures with error types
    - Task duration
    """

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Execute task with monitoring."""
        task_name = self.name

        # Get customer_id if available
        customer_id = "unknown"
        if "customer_id" in kwargs:
            customer_id = str(kwargs["customer_id"])
        elif len(args) > 0 and isinstance(args[0], int):
            customer_id = str(args[0])

        # Track task start
        background_job_started.labels(
            task_name=task_name, customer_id=customer_id
        ).inc()

        start_time = time.time()

        try:
            # Execute task
            result = super().__call__(*args, **kwargs)

            # Track success
            duration = time.time() - start_time
            background_job_completed.labels(
                task_name=task_name, customer_id=customer_id
            ).inc()
            background_job_duration.labels(task_name=task_name).observe(duration)

            logger.info(
                f"Task {task_name} completed successfully in {duration:.2f}s "
                f"(customer={customer_id})"
            )

            return result

        except Exception as e:
            # Track failure
            duration = time.time() - start_time
            error_type = e.__class__.__name__

            background_job_failed.labels(
                task_name=task_name, error_type=error_type, customer_id=customer_id
            ).inc()
            background_job_duration.labels(task_name=task_name).observe(duration)

            logger.error(
                f"Task {task_name} failed after {duration:.2f}s "
                f"with {error_type}: {str(e)} (customer={customer_id})"
            )

            # Re-raise to maintain Celery's error handling
            raise


# =============================================================================
# WORKER HEALTH CHECKS
# =============================================================================


def get_celery_worker_status() -> Dict[str, Any]:
    """
    Check the health status of Celery workers.

    Returns:
        dict: Worker status information
            - healthy: bool
            - active_workers: list of worker names
            - active_queues: list of queue names
            - error: str (if unhealthy)
    """
    try:
        from upstream.celery import app

        # Create inspector to check workers
        inspector = app.control.inspect()

        # Get active workers
        stats = inspector.stats()

        if stats is None or len(stats) == 0:
            return {
                "healthy": False,
                "active_workers": [],
                "active_queues": [],
                "error": "No active Celery workers found",
            }

        # Extract worker information
        active_workers = list(stats.keys())
        active_queues = set()

        # Get active queues from each worker
        active_tasks = inspector.active()
        if active_tasks:
            for worker_name, tasks in active_tasks.items():
                for task in tasks:
                    if "delivery_info" in task:
                        queue = task["delivery_info"].get("routing_key", "celery")
                        active_queues.add(queue)

        return {
            "healthy": True,
            "active_workers": active_workers,
            "active_queues": list(active_queues),
            "worker_count": len(active_workers),
        }

    except Exception as e:
        logger.error(f"Error checking Celery worker status: {str(e)}")
        return {
            "healthy": False,
            "active_workers": [],
            "active_queues": [],
            "error": str(e),
        }


def get_celery_queue_length(queue_name: str = "celery") -> int:
    """
    Get the number of pending tasks in a Celery queue.

    Args:
        queue_name: Name of the queue to check (default: 'celery')

    Returns:
        int: Number of pending tasks in the queue
    """
    try:
        from upstream.celery import app

        # Try to get queue length from Redis broker
        # This is broker-specific (Redis implementation)
        with app.connection_or_acquire() as conn:
            return conn.default_channel.client.llen(queue_name)

    except Exception as e:
        logger.warning(f"Could not get queue length for {queue_name}: {str(e)}")
        return -1  # Return -1 to indicate unavailable


def get_celery_health_summary() -> Dict[str, Any]:
    """
    Get comprehensive health summary for Celery.

    Returns:
        dict: Complete health information
            - status: 'healthy', 'degraded', or 'unhealthy'
            - workers: worker status dict
            - queues: dict of queue lengths
            - recommendations: list of recommended actions
    """
    worker_status = get_celery_worker_status()
    queue_length = get_celery_queue_length()

    # Determine overall status
    if not worker_status["healthy"]:
        status = "unhealthy"
    elif queue_length > 1000:  # High queue depth
        status = "degraded"
    else:
        status = "healthy"

    recommendations = []

    if not worker_status["healthy"]:
        recommendations.append(
            "Start Celery workers: celery -A upstream worker --loglevel=info"
        )

    if queue_length > 1000:
        recommendations.append(
            f"Queue depth is high ({queue_length} tasks). "
            "Consider adding more workers or investigating slow tasks."
        )

    if status == "healthy" and len(worker_status["active_workers"]) == 1:
        recommendations.append(
            "Running with single worker. "
            "For production, run multiple workers for redundancy."
        )

    return {
        "status": status,
        "workers": worker_status,
        "queues": {"celery": queue_length},
        "recommendations": recommendations,
    }


# =============================================================================
# TASK MONITORING UTILITIES
# =============================================================================


def get_running_tasks() -> List[Dict[str, Any]]:
    """
    Get list of currently running tasks across all workers.

    Returns:
        list: List of running task information dicts
    """
    try:
        from upstream.celery import app

        inspector = app.control.inspect()
        active_tasks = inspector.active()

        if not active_tasks:
            return []

        # Flatten tasks from all workers
        all_tasks = []
        for worker_name, tasks in active_tasks.items():
            for task in tasks:
                task_info = {
                    "worker": worker_name,
                    "task_name": task.get("name", "unknown"),
                    "task_id": task.get("id", "unknown"),
                    "args": task.get("args", []),
                    "kwargs": task.get("kwargs", {}),
                    "time_start": task.get("time_start", None),
                }
                all_tasks.append(task_info)

        return all_tasks

    except Exception as e:
        logger.error(f"Error getting running tasks: {str(e)}")
        return []


def get_scheduled_tasks() -> List[Dict[str, Any]]:
    """
    Get list of scheduled (not yet running) tasks.

    Returns:
        list: List of scheduled task information dicts
    """
    try:
        from upstream.celery import app

        inspector = app.control.inspect()
        scheduled_tasks = inspector.scheduled()

        if not scheduled_tasks:
            return []

        # Flatten tasks from all workers
        all_tasks = []
        for worker_name, tasks in scheduled_tasks.items():
            for task in tasks:
                task_info = {
                    "worker": worker_name,
                    "task_name": task.get("request", {}).get("name", "unknown"),
                    "task_id": task.get("request", {}).get("id", "unknown"),
                    "eta": task.get("eta", None),
                }
                all_tasks.append(task_info)

        return all_tasks

    except Exception as e:
        logger.error(f"Error getting scheduled tasks: {str(e)}")
        return []


def get_task_stats() -> Dict[str, Any]:
    """
    Get statistics about task execution.

    Returns:
        dict: Task execution statistics
            - total_completed: int
            - total_failed: int
            - total_running: int
            - total_scheduled: int
            - by_task_name: dict of task-specific stats
    """
    running_tasks = get_running_tasks()
    scheduled_tasks = get_scheduled_tasks()

    # Count by task name
    by_task_name = {}
    for task in running_tasks:
        task_name = task["task_name"]
        if task_name not in by_task_name:
            by_task_name[task_name] = {"running": 0, "scheduled": 0}
        by_task_name[task_name]["running"] += 1

    for task in scheduled_tasks:
        task_name = task["task_name"]
        if task_name not in by_task_name:
            by_task_name[task_name] = {"running": 0, "scheduled": 0}
        by_task_name[task_name]["scheduled"] += 1

    return {
        "total_running": len(running_tasks),
        "total_scheduled": len(scheduled_tasks),
        "by_task_name": by_task_name,
    }


# =============================================================================
# CACHE-BASED HEALTH CHECK
# =============================================================================


def cache_health_check(ttl: int = 300) -> Dict[str, Any]:
    """
    Cache Celery health check results to avoid overwhelming the broker.

    Args:
        ttl: Cache TTL in seconds (default: 5 minutes)

    Returns:
        dict: Cached health check results
    """
    cache_key = "celery_health_check"

    # Try to get from cache
    cached = cache.get(cache_key)
    if cached:
        cached["cached"] = True
        return cached

    # Compute fresh health check
    health = get_celery_health_summary()
    health["cached"] = False

    # Cache the result
    cache.set(cache_key, health, ttl)

    return health
