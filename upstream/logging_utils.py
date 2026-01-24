"""
Structured logging utilities for Upstream.

Provides context management and structured logging helpers to make
debugging in production easier with rich, contextual log messages.

Usage:
    from upstream.logging_utils import get_logger, add_log_context

    logger = get_logger(__name__)

    # Add context for this request/operation
    with add_log_context(customer_id=customer.id, user_id=user.id):
        logger.info("Processing upload", extra={'upload_id': upload.id})
"""

import logging
import threading
from typing import Any, Dict, Optional
from contextvars import ContextVar
from django.http import HttpRequest


# Thread-local storage for log context
_log_context: ContextVar[Dict[str, Any]] = ContextVar('log_context', default={})


class ContextualLoggerAdapter(logging.LoggerAdapter):
    """
    Logger adapter that automatically includes context in log records.

    This adapter pulls context from thread-local storage and adds it
    to every log message, making it easy to filter and search logs
    by customer, user, request, etc.
    """

    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        """
        Process log message and add context.

        Args:
            msg: Log message
            kwargs: Keyword arguments for logging

        Returns:
            Tuple of (msg, kwargs) with context added
        """
        # Get current context
        context = _log_context.get({})

        # Merge context with extra data
        extra = kwargs.get('extra', {})
        extra.update(context)
        kwargs['extra'] = extra

        return msg, kwargs


def get_logger(name: str) -> ContextualLoggerAdapter:
    """
    Get a logger with automatic context injection.

    Usage:
        logger = get_logger(__name__)
        logger.info("Processing data")  # Automatically includes context

    Args:
        name: Logger name (typically __name__)

    Returns:
        ContextualLoggerAdapter: Logger with context support
    """
    base_logger = logging.getLogger(name)
    return ContextualLoggerAdapter(base_logger, {})


def set_log_context(**kwargs: Any) -> None:
    """
    Set context for all subsequent log messages in this thread/async context.

    Usage:
        set_log_context(customer_id=123, user_id=456, request_id='abc')
        logger.info("Operation complete")  # Includes customer_id, user_id, request_id

    Args:
        **kwargs: Context key-value pairs to add to logs
    """
    current_context = _log_context.get({}).copy()
    current_context.update(kwargs)
    _log_context.set(current_context)


def clear_log_context() -> None:
    """
    Clear all log context for the current thread/async context.

    Usage:
        clear_log_context()  # Remove all context
    """
    _log_context.set({})


def get_log_context() -> Dict[str, Any]:
    """
    Get the current log context.

    Returns:
        Dict[str, Any]: Current context dictionary
    """
    return _log_context.get({}).copy()


class add_log_context:
    """
    Context manager to temporarily add log context.

    Usage:
        with add_log_context(customer_id=123, operation='upload'):
            logger.info("Processing")  # Includes customer_id and operation
        # Context is restored after the block
    """

    def __init__(self, **kwargs: Any):
        """
        Initialize context manager.

        Args:
            **kwargs: Context key-value pairs to add
        """
        self.new_context = kwargs
        self.previous_context: Optional[Dict[str, Any]] = None

    def __enter__(self):
        """Enter context - save previous context and add new."""
        self.previous_context = get_log_context()
        set_log_context(**self.new_context)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context - restore previous context."""
        if self.previous_context is not None:
            _log_context.set(self.previous_context)
        else:
            clear_log_context()


def extract_request_context(request: HttpRequest) -> Dict[str, Any]:
    """
    Extract logging context from an HTTP request.

    Args:
        request: Django HTTP request

    Returns:
        Dict[str, Any]: Context dictionary with request information
    """
    from upstream.middleware import get_request_id
    from upstream.permissions import get_user_profile

    context = {}

    # Add request ID
    request_id = get_request_id()
    if request_id:
        context['request_id'] = request_id

    # Add user information
    if hasattr(request, 'user') and request.user.is_authenticated:
        context['user_id'] = request.user.id
        context['username'] = request.user.username

        # Add customer information
        profile = get_user_profile(request.user)
        if profile and hasattr(profile, 'customer'):
            context['customer_id'] = profile.customer.id
            context['customer_name'] = profile.customer.name

    # Add request metadata
    context['method'] = request.method
    context['path'] = request.path

    # Add IP address (be careful with privacy)
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        context['ip'] = x_forwarded_for.split(',')[0].strip()
    else:
        context['ip'] = request.META.get('REMOTE_ADDR', 'unknown')

    return context


class StructuredLogFormatter(logging.Formatter):
    """
    Custom log formatter that outputs structured (key=value) logs.

    This formatter makes logs easier to parse by log aggregation tools
    like CloudWatch, Datadog, or ELK stack.

    Example output:
        2024-01-28 10:30:45 INFO customer_id=123 user_id=456 request_id=abc message="Upload complete"
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record with structured data.

        Args:
            record: Log record to format

        Returns:
            str: Formatted log message
        """
        # Start with timestamp and level
        timestamp = self.formatTime(record, self.datefmt)
        level = record.levelname
        parts = [f"{timestamp} {level}"]

        # Add context fields
        context_fields = [
            'customer_id',
            'customer_name',
            'user_id',
            'username',
            'request_id',
            'method',
            'path',
            'ip',
        ]

        for field in context_fields:
            if hasattr(record, field):
                value = getattr(record, field)
                # Quote strings with spaces
                if isinstance(value, str) and ' ' in value:
                    parts.append(f'{field}="{value}"')
                else:
                    parts.append(f'{field}={value}')

        # Add the main message
        msg = record.getMessage()
        if ' ' in msg or '=' in msg:
            parts.append(f'message="{msg}"')
        else:
            parts.append(f'message={msg}')

        # Add exception info if present
        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)

        if record.exc_text:
            parts.append(f'\n{record.exc_text}')

        return ' '.join(parts)


# Pre-configured logger instances for common use cases
def get_service_logger(service_name: str) -> ContextualLoggerAdapter:
    """
    Get a logger for a service with the service name included.

    Usage:
        logger = get_service_logger('payer_drift')
        logger.info("Drift detected")  # Includes service_name=payer_drift

    Args:
        service_name: Name of the service

    Returns:
        ContextualLoggerAdapter: Logger with service context
    """
    logger = get_logger(f"upstream.services.{service_name}")

    # Add service name to all logs from this logger
    class ServiceLoggerAdapter(ContextualLoggerAdapter):
        def process(self, msg, kwargs):
            msg, kwargs = super().process(msg, kwargs)
            kwargs['extra']['service_name'] = service_name
            return msg, kwargs

    return ServiceLoggerAdapter(logger.logger, {})


def get_task_logger(task_name: str) -> ContextualLoggerAdapter:
    """
    Get a logger for a Celery task with the task name included.

    Usage:
        logger = get_task_logger('compute_drift')
        logger.info("Task started")  # Includes task_name=compute_drift

    Args:
        task_name: Name of the Celery task

    Returns:
        ContextualLoggerAdapter: Logger with task context
    """
    logger = get_logger(f"upstream.tasks.{task_name}")

    # Add task name to all logs from this logger
    class TaskLoggerAdapter(ContextualLoggerAdapter):
        def process(self, msg, kwargs):
            msg, kwargs = super().process(msg, kwargs)
            kwargs['extra']['task_name'] = task_name
            return msg, kwargs

    return TaskLoggerAdapter(logger.logger, {})


# Example usage in docstring
"""
Example: Using structured logging in a view

    from upstream.logging_utils import get_logger, add_log_context

    logger = get_logger(__name__)

    def process_upload(request, upload_id):
        upload = Upload.objects.get(id=upload_id)

        # Add context for this operation
        with add_log_context(
            customer_id=upload.customer.id,
            upload_id=upload.id,
            operation='process_upload'
        ):
            logger.info("Starting upload processing")

            try:
                # Process upload
                result = process_file(upload.file_path)
                logger.info("Upload processed successfully",
                           extra={'rows_processed': result.row_count})
                return result

            except Exception as e:
                logger.error("Upload processing failed",
                            extra={'error': str(e)},
                            exc_info=True)
                raise

Example: Using structured logging in a service

    from upstream.logging_utils import get_service_logger, add_log_context

    logger = get_service_logger('payer_drift')

    def compute_weekly_payer_drift(customer):
        with add_log_context(customer_id=customer.id):
            logger.info("Starting drift computation")

            # ... computation logic ...

            logger.info("Drift computation complete",
                       extra={'events_created': events_created})

Example: Using structured logging in a Celery task

    from upstream.logging_utils import get_task_logger, set_log_context

    logger = get_task_logger('compute_report_drift')

    @shared_task
    def compute_report_drift_task(report_run_id):
        report_run = ReportRun.objects.get(id=report_run_id)

        # Set context for entire task
        set_log_context(
            customer_id=report_run.customer.id,
            report_run_id=report_run.id
        )

        logger.info("Task started")
        # All subsequent logs will include customer_id and report_run_id
"""
