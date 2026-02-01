"""
Celery tasks for async processing in Upstream.

These tasks allow drift detection, alert sending, webhook delivery,
and report generation to run asynchronously.

All tasks use MonitoredTask base class for automatic metrics tracking.
"""

from typing import Dict, Any
from celery import shared_task
from decouple import config
import logging
from upstream.celery_monitoring import MonitoredTask

logger = logging.getLogger(__name__)

# Check if Celery is enabled
CELERY_ENABLED = config("CELERY_ENABLED", default=False, cast=bool)


@shared_task(name="upstream.tasks.run_drift_detection", base=MonitoredTask)
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

        logger.info(
            f"Completed drift detection for customer {customer_id}: "
            f"{len(results)} events"
        )
        return {
            "customer_id": customer_id,
            "events_detected": len(results),
            "status": "success",
        }
    except Exception as e:
        logger.error(
            f"Error in drift detection task for customer {customer_id}: {str(e)}"
        )
        raise


@shared_task(name="upstream.tasks.send_alert", base=MonitoredTask)
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

        logger.info(
            f"Completed alert send for alert {alert_id}: {result.get('status')}"
        )
        return result
    except Exception as e:
        logger.error(f"Error sending alert {alert_id}: {str(e)}")
        raise


@shared_task(name="upstream.tasks.send_webhook", base=MonitoredTask)
def send_webhook_task(webhook_delivery_id: int) -> Dict[str, Any]:
    """
    Async task for sending a webhook.

    Args:
        webhook_delivery_id: The webhook delivery record to process

    Returns:
        dict: Send result
    """
    from upstream.services.webhook_processor import deliver_webhook
    from upstream.integrations.models import WebhookDelivery

    logger.info(f"Starting async webhook delivery for {webhook_delivery_id}")

    try:
        delivery = WebhookDelivery.objects.get(id=webhook_delivery_id)
        result = deliver_webhook(delivery)

        logger.info(
            f"Completed webhook delivery {webhook_delivery_id}: "
            f"{result.get('status')}"
        )
        return result
    except Exception as e:
        logger.error(f"Error delivering webhook {webhook_delivery_id}: {str(e)}")
        raise


@shared_task(name="upstream.tasks.generate_report_artifact", base=MonitoredTask)
def generate_report_artifact_task(
    report_run_id: int, artifact_type: str = "pdf"
) -> Dict[str, Any]:
    """
    Async task for generating report artifacts.

    Args:
        report_run_id: The report run to generate artifacts for
        artifact_type: Type of artifact ('pdf', 'csv', 'xlsx')

    Returns:
        dict: Generation result
    """
    from upstream.services.report_scheduler import ReportSchedulerService
    from upstream.models import ReportRun

    logger.info(
        f"Starting async report artifact generation for run {report_run_id}, "
        f"type {artifact_type}"
    )

    try:
        report_run = ReportRun.all_objects.get(id=report_run_id)

        result = ReportSchedulerService.generate_report_artifact(
            report_run, artifact_type
        )

        logger.info(f"Completed artifact generation for run {report_run_id}")
        return {
            "report_run_id": report_run_id,
            "artifact_type": result["artifact_type"],
            "artifact_id": result["artifact_id"],
            "status": result["status"],
        }
    except Exception as e:
        logger.error(f"Error generating artifact for run {report_run_id}: {str(e)}")
        raise


@shared_task(name="upstream.tasks.send_scheduled_report", base=MonitoredTask)
def send_scheduled_report_task(
    customer_id: int, report_type: str = "weekly_drift"
) -> Dict[str, Any]:
    """
    Async task for generating and sending scheduled reports.

    Args:
        customer_id: The customer to generate report for
        report_type: Type of report to generate

    Returns:
        dict: Send result
    """
    from upstream.services.report_scheduler import ReportSchedulerService
    from upstream.models import Customer
    from datetime import datetime, timedelta

    logger.info(
        f"Starting scheduled report generation for customer {customer_id}, "
        f"type {report_type}"
    )

    try:
        customer = Customer.objects.get(id=customer_id)

        # Calculate weekly period
        period_end = datetime.now().date()
        period_start = period_end - timedelta(days=7)

        result = ReportSchedulerService.schedule_weekly_report(
            customer, period_start, period_end
        )

        logger.info(f"Completed scheduled report for customer {customer_id}")
        return result
    except Exception as e:
        logger.error(f"Error in scheduled report for customer {customer_id}: {str(e)}")
        raise


@shared_task(name="upstream.tasks.compute_report_drift", base=MonitoredTask)
def compute_report_drift_task(report_run_id: int) -> Dict[str, Any]:
    """
    Async task for computing drift for a specific report run.

    Args:
        report_run_id: The report run to compute drift for

    Returns:
        dict: Drift computation result
    """
    from upstream.services.report_scheduler import ReportSchedulerService
    from upstream.models import ReportRun

    logger.info(f"Starting drift computation for report run {report_run_id}")

    try:
        report_run = ReportRun.all_objects.get(id=report_run_id)

        result = ReportSchedulerService.compute_report_drift(report_run)

        logger.info(
            f"Completed drift computation for report run {report_run_id}: "
            f"{result['events_detected']} events"
        )
        return result
    except Exception as e:
        logger.error(f"Error computing drift for report run {report_run_id}: {str(e)}")
        raise


@shared_task(name="upstream.tasks.process_ingestion", base=MonitoredTask)
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
        return {"ingestion_id": ingestion_id, "status": "success", "result": result}
    except Exception as e:
        logger.error(f"Error processing ingestion {ingestion_id}: {str(e)}")
        # Mark ingestion as failed
        try:
            ingestion = Ingestion.objects.get(id=ingestion_id)
            ingestion.status = "failed"
            ingestion.error_message = str(e)
            ingestion.save()
        except Exception:
            pass
        raise


@shared_task(name="upstream.tasks.run_daily_behavioral_prediction", base=MonitoredTask)
def run_daily_behavioral_prediction(customer_id: int = None) -> Dict[str, Any]:
    """
    Async task for running daily behavioral prediction across customers.

    Behavioral prediction compares denial rates from the last 3 days against
    the previous 14 days per payer. Creates DriftEvent with drift_type=
    'BEHAVIORAL_PREDICTION' when p-value < 0.05 AND rate change > 5%.

    Args:
        customer_id: Optional specific customer to run for. If None, runs
                     for all active customers.

    Returns:
        dict: Summary of behavioral prediction results across all customers
    """
    from upstream.models import Customer
    from upstream.services.behavioral_prediction import compute_behavioral_prediction

    logger.info(
        f"Starting daily behavioral prediction"
        f"{f' for customer {customer_id}' if customer_id else ' for all customers'}"
    )

    results = []

    try:
        if customer_id:
            customers = Customer.objects.filter(id=customer_id, is_active=True)
        else:
            customers = Customer.objects.filter(is_active=True)

        for customer in customers:
            try:
                report_run = compute_behavioral_prediction(customer)
                summary = report_run.summary_json or {}
                results.append(
                    {
                        "customer_id": customer.id,
                        "customer_name": customer.name,
                        "events_created": summary.get("events_created", 0),
                        "payers_analyzed": summary.get("payers_analyzed", 0),
                        "status": "success",
                    }
                )
                logger.info(
                    f"Completed behavioral prediction for customer {customer.id}: "
                    f"{summary.get('events_created', 0)} events"
                )
            except Exception as e:
                logger.error(
                    f"Error in behavioral prediction for customer {customer.id}: "
                    f"{str(e)}"
                )
                results.append(
                    {
                        "customer_id": customer.id,
                        "customer_name": customer.name,
                        "status": "failed",
                        "error": str(e),
                    }
                )

        total_events = sum(
            r.get("events_created", 0) for r in results if r.get("status") == "success"
        )
        successful = sum(1 for r in results if r.get("status") == "success")

        logger.info(
            f"Completed daily behavioral prediction: "
            f"{successful}/{len(results)} customers, {total_events} total events"
        )

        return {
            "customers_processed": len(results),
            "customers_successful": successful,
            "total_events_created": total_events,
            "results": results,
            "status": "success" if successful == len(results) else "partial",
        }

    except Exception as e:
        logger.error(f"Error in daily behavioral prediction task: {str(e)}")
        raise


@shared_task(name="upstream.tasks.run_network_intelligence", base=MonitoredTask)
def run_network_intelligence() -> Dict[str, Any]:
    """
    Async task for running cross-customer network intelligence analysis.

    Analyzes denial patterns across all customers to detect payer-wide
    behavioral changes. Creates NetworkAlert when 3+ customers are
    affected by the same payer drift.

    Returns:
        dict: Summary of network intelligence results
    """
    from upstream.services.network_intelligence import compute_cross_customer_patterns

    logger.info("Starting network intelligence analysis")

    try:
        alerts_created = compute_cross_customer_patterns()

        logger.info(
            f"Completed network intelligence analysis: {alerts_created} alerts created"
        )

        return {
            "alerts_created": alerts_created,
            "status": "success",
        }

    except Exception as e:
        logger.error(f"Error in network intelligence task: {str(e)}")
        raise


@shared_task(
    bind=True,
    base=MonitoredTask,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
)
def process_claim_with_automation(
    self, customer_id: int, fhir_payload: dict, source: str = "ehr_webhook"
) -> dict:
    """
    Process incoming claim with automation rules evaluation.

    Args:
        customer_id: Customer ID
        fhir_payload: FHIR R4 Claim resource
        source: Source of claim (ehr_webhook, api, etc.)

    Returns:
        dict: Processing result with actions executed
    """
    from upstream.models import Customer
    from upstream.automation.rules_engine import RulesEngine, Event
    from datetime import datetime

    logger.info(
        f"Processing claim with automation for customer {customer_id}, source: {source}"
    )

    try:
        # Load customer
        customer = Customer.objects.get(id=customer_id)

        # Simplified FHIR parsing for Week 1 (full parsing in Week 2)
        claim_id = fhir_payload.get("id", "unknown")
        patient_id = fhir_payload.get("patient", {}).get("reference", "unknown")
        payer = fhir_payload.get("insurer", {}).get("display", "unknown")

        # Create event for rules engine
        event = Event(
            event_type="claim_submitted",
            customer_id=customer_id,
            payload={
                "claim_id": claim_id,
                "patient_id": patient_id,
                "payer": payer,
                "source": source,
                "fhir_data": fhir_payload,
            },
            timestamp=datetime.now(),
        )

        # Evaluate and execute automation rules
        engine = RulesEngine(customer)
        actions = engine.evaluate_event(event)
        results = engine.execute_actions(actions)

        logger.info(
            f"Completed automation processing for claim {claim_id}: "
            f"{len(actions)} actions evaluated, "
            f"{sum(1 for r in results if r.success)} succeeded"
        )

        return {
            "customer_id": customer_id,
            "claim_id": claim_id,
            "source": source,
            "actions_executed": len(actions),
            "status": "success",
        }

    except Customer.DoesNotExist:
        logger.error(f"Customer {customer_id} not found")
        raise
    except Exception as e:
        logger.error(
            f"Error processing claim with automation for customer {customer_id}: {str(e)}"
        )
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
