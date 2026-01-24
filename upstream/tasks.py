"""
Celery tasks for async processing in Upstream.

These tasks allow drift detection, alert sending, webhook delivery,
and report generation to run asynchronously.
"""

from typing import Dict, Any
from celery import shared_task
from decouple import config
import logging

logger = logging.getLogger(__name__)

# Check if Celery is enabled
CELERY_ENABLED = config('CELERY_ENABLED', default=False, cast=bool)


@shared_task(name='upstream.tasks.run_drift_detection')
def run_drift_detection_task(customer_id: int, **kwargs: Any) -> Dict[str, Any]:
    """
    Async task for running payer drift detection.

    Args:
        customer_id: The customer to run drift detection for
        **kwargs: Additional arguments for drift detection

    Returns:
        dict: Summary of drift detection results
    """
    from upstream.services.payer_drift import detect_drift_events
    from upstream.models import Customer
    
    logger.info(f"Starting async drift detection for customer {customer_id}")
    
    try:
        customer = Customer.objects.get(id=customer_id)
        results = detect_drift_events(customer, **kwargs)
        
        logger.info(f"Completed drift detection for customer {customer_id}: {len(results)} events")
        return {
            'customer_id': customer_id,
            'events_detected': len(results),
            'status': 'success'
        }
    except Exception as e:
        logger.error(f"Error in drift detection task for customer {customer_id}: {str(e)}")
        raise


@shared_task(name='upstream.tasks.send_alert')
def send_alert_task(alert_id: int) -> Dict[str, Any]:
    """
    Async task for sending a single alert.

    Args:
        alert_id: The alert to send

    Returns:
        dict: Send result
    """
    from upstream.alerts.services import send_single_alert
    from upstream.alerts.models import Alert
    
    logger.info(f"Starting async alert send for alert {alert_id}")
    
    try:
        alert = Alert.objects.get(id=alert_id)
        result = send_single_alert(alert)
        
        logger.info(f"Completed alert send for alert {alert_id}: {result.get('status')}")
        return result
    except Exception as e:
        logger.error(f"Error sending alert {alert_id}: {str(e)}")
        raise


@shared_task(name='upstream.tasks.send_webhook')
def send_webhook_task(webhook_delivery_id: int) -> Dict[str, Any]:
    """
    Async task for sending a webhook.

    Args:
        webhook_delivery_id: The webhook delivery record to process

    Returns:
        dict: Send result
    """
    from upstream.integrations.services import deliver_webhook
    from upstream.integrations.models import WebhookDelivery
    
    logger.info(f"Starting async webhook delivery for {webhook_delivery_id}")
    
    try:
        delivery = WebhookDelivery.objects.get(id=webhook_delivery_id)
        result = deliver_webhook(delivery)
        
        logger.info(f"Completed webhook delivery {webhook_delivery_id}: {result.get('status')}")
        return result
    except Exception as e:
        logger.error(f"Error delivering webhook {webhook_delivery_id}: {str(e)}")
        raise


@shared_task(name='upstream.tasks.generate_report_artifact')
def generate_report_artifact_task(report_run_id: int, artifact_type: str = 'pdf') -> Dict[str, Any]:
    """
    Async task for generating report artifacts.

    Args:
        report_run_id: The report run to generate artifacts for
        artifact_type: Type of artifact ('pdf', 'csv', 'xlsx')

    Returns:
        dict: Generation result
    """
    from upstream.reporting.services import generate_weekly_drift_pdf, export_drift_events_csv
    from upstream.reporting.models import ReportRun
    
    logger.info(f"Starting async report artifact generation for run {report_run_id}, type {artifact_type}")

    try:
        report_run = ReportRun.all_objects.get(id=report_run_id)

        if artifact_type == 'pdf':
            artifact = generate_weekly_drift_pdf(report_run_id)
        elif artifact_type == 'csv':
            artifact = export_drift_events_csv(report_run.customer, report_run.period_start, report_run.period_end)
        else:
            raise ValueError(f"Unsupported artifact type: {artifact_type}")
        
        logger.info(f"Completed artifact generation for run {report_run_id}")
        return {
            'report_run_id': report_run_id,
            'artifact_type': artifact_type,
            'artifact_id': artifact.id if artifact else None,
            'status': 'success'
        }
    except Exception as e:
        logger.error(f"Error generating artifact for run {report_run_id}: {str(e)}")
        raise


@shared_task(name='upstream.tasks.send_scheduled_report')
def send_scheduled_report_task(customer_id: int, report_type: str = 'weekly_drift') -> Dict[str, Any]:
    """
    Async task for generating and sending scheduled reports.

    Args:
        customer_id: The customer to generate report for
        report_type: Type of report to generate

    Returns:
        dict: Send result
    """
    from upstream.reporting.services import generate_and_send_weekly_report
    from upstream.models import Customer

    logger.info(f"Starting scheduled report generation for customer {customer_id}, type {report_type}")

    try:
        customer = Customer.objects.get(id=customer_id)
        result = generate_and_send_weekly_report(customer)

        logger.info(f"Completed scheduled report for customer {customer_id}")
        return result
    except Exception as e:
        logger.error(f"Error in scheduled report for customer {customer_id}: {str(e)}")
        raise


@shared_task(name='upstream.tasks.compute_report_drift')
def compute_report_drift_task(report_run_id: int) -> Dict[str, Any]:
    """
    Async task for computing drift for a specific report run.

    Args:
        report_run_id: The report run to compute drift for

    Returns:
        dict: Drift computation result
    """
    from upstream.models import ReportRun
    from upstream.services.payer_drift import compute_weekly_payer_drift

    logger.info(f"Starting drift computation for report run {report_run_id}")

    try:
        report_run = ReportRun.all_objects.get(id=report_run_id)

        # Compute drift for this report run
        report_run = compute_weekly_payer_drift(report_run.customer, report_run=report_run)

        # Update report run status
        report_run.status = 'completed'
        report_run.save()

        # Count drift events for this report
        drift_event_count = report_run.drift_events.count()
        logger.info(f"Completed drift computation for report run {report_run_id}: {drift_event_count} events")
        return {
            'report_run_id': report_run_id,
            'events_detected': drift_event_count,
            'status': 'success'
        }
    except Exception as e:
        logger.error(f"Error computing drift for report run {report_run_id}: {str(e)}")
        # Mark report as failed
        try:
            report_run = ReportRun.all_objects.get(id=report_run_id)
            report_run.status = 'failed'
            report_run.save()
        except Exception:
            pass
        raise


@shared_task(name='upstream.tasks.process_ingestion')
def process_ingestion_task(ingestion_id: int) -> Dict[str, Any]:
    """
    Async task for processing an ingestion record.

    Args:
        ingestion_id: The ingestion record to process

    Returns:
        dict: Processing result
    """
    from upstream.ingestion.models import Ingestion
    from upstream.ingestion.services import process_ingestion_record

    logger.info(f"Starting ingestion processing for record {ingestion_id}")

    try:
        ingestion = Ingestion.objects.get(id=ingestion_id)

        # Process the ingestion
        result = process_ingestion_record(ingestion)

        logger.info(f"Completed ingestion processing for record {ingestion_id}")
        return {
            'ingestion_id': ingestion_id,
            'status': 'success',
            'result': result
        }
    except Exception as e:
        logger.error(f"Error processing ingestion {ingestion_id}: {str(e)}")
        # Mark ingestion as failed
        try:
            ingestion = Ingestion.objects.get(id=ingestion_id)
            ingestion.status = 'failed'
            ingestion.error_message = str(e)
            ingestion.save()
        except Exception:
            pass
        raise


# Helper function to enqueue tasks conditionally
def enqueue_or_run_sync(task: Any, *args: Any, **kwargs: Any) -> Any:
    """
    Either enqueue a task to Celery or run it synchronously.

    This allows the system to work with or without Celery running.
    """
    if CELERY_ENABLED:
        return task.delay(*args, **kwargs)
    else:
        # Run synchronously
        return task(*args, **kwargs)
