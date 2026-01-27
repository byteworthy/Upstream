"""Webhook delivery, retry, and dispatch service."""
from typing import Dict, List, Optional, Any
import json
import logging
import uuid
import requests
from django.utils import timezone
from upstream.integrations.services import generate_signature
from upstream.integrations.models import WebhookEndpoint, WebhookDelivery
from upstream.models import Customer

logger = logging.getLogger(__name__)


def create_webhook_delivery(
    endpoint: WebhookEndpoint, event_type: str, payload: Dict[str, Any]
) -> Optional[WebhookDelivery]:
    """Create a webhook delivery record."""
    if endpoint.event_types and event_type not in endpoint.event_types:
        return None
    if not endpoint.active:
        return None
    return WebhookDelivery.objects.create(
        endpoint=endpoint, event_type=event_type, payload=payload, status="pending"
    )


def deliver_webhook(delivery: WebhookDelivery) -> bool:
    """Attempt to deliver a webhook."""
    from upstream.core.services import create_audit_event
    from upstream.middleware import get_request_id

    endpoint = delivery.endpoint

    # Add request_id to payload metadata if not present
    if "metadata" not in delivery.payload:
        delivery.payload["metadata"] = {}
    if "request_id" not in delivery.payload["metadata"]:
        delivery.payload["metadata"]["request_id"] = get_request_id() or str(
            uuid.uuid4()
        )

    payload_str = json.dumps(delivery.payload, separators=(",", ":"), sort_keys=True)
    signature = generate_signature(payload_str, endpoint.secret)
    headers = {
        "Content-Type": "application/json",
        "X-Signature": signature,
        "X-Webhook-Event": delivery.event_type,
        "X-Webhook-Delivery-ID": str(delivery.id),
    }
    delivery.attempts += 1
    delivery.last_attempt_at = timezone.now()
    delivery.save()

    try:
        response = requests.post(
            endpoint.url, data=payload_str, headers=headers, timeout=30
        )
        delivery.response_code = response.status_code
        delivery.response_body = response.text[:1000]
        if 200 <= response.status_code < 300:
            delivery.status = "success"
            delivery.save()

            # Create audit event for successful delivery
            create_audit_event(
                action="webhook_delivery_sent",
                entity_type="WebhookDelivery",
                entity_id=delivery.id,
                customer=endpoint.customer,
                metadata={
                    "endpoint_name": endpoint.name,
                    "event_type": delivery.event_type,
                    "attempts": delivery.attempts,
                    "response_code": response.status_code,
                },
                request_id=delivery.payload["metadata"]["request_id"],
            )
            logger.info(f"Webhook delivery {delivery.id} sent successfully")
            return True
        else:
            delivery.last_error = f"HTTP {response.status_code}: {response.text[:200]}"
            delivery.schedule_next_attempt()

            # Create audit event for failed delivery if terminal
            if delivery.status == "failed":
                create_audit_event(
                    action="webhook_delivery_failed",
                    entity_type="WebhookDelivery",
                    entity_id=delivery.id,
                    customer=endpoint.customer,
                    metadata={
                        "endpoint_name": endpoint.name,
                        "event_type": delivery.event_type,
                        "attempts": delivery.attempts,
                        "error": delivery.last_error,
                    },
                    request_id=delivery.payload["metadata"]["request_id"],
                )
            return False
    except requests.exceptions.Timeout:
        delivery.last_error = "Request timed out"
        delivery.schedule_next_attempt()

        # Create audit event for failed delivery if terminal
        if delivery.status == "failed":
            create_audit_event(
                action="webhook_delivery_failed",
                entity_type="WebhookDelivery",
                entity_id=delivery.id,
                customer=endpoint.customer,
                metadata={
                    "endpoint_name": endpoint.name,
                    "event_type": delivery.event_type,
                    "attempts": delivery.attempts,
                    "error": delivery.last_error,
                },
                request_id=delivery.payload["metadata"]["request_id"],
            )
        return False
    except Exception as e:
        delivery.last_error = f"Error: {str(e)}"
        delivery.schedule_next_attempt()

        # Create audit event for failed delivery if terminal
        if delivery.status == "failed":
            create_audit_event(
                action="webhook_delivery_failed",
                entity_type="WebhookDelivery",
                entity_id=delivery.id,
                customer=endpoint.customer,
                metadata={
                    "endpoint_name": endpoint.name,
                    "event_type": delivery.event_type,
                    "attempts": delivery.attempts,
                    "error": delivery.last_error,
                },
                request_id=delivery.payload["metadata"]["request_id"],
            )
        return False


def dispatch_event(
    customer: Customer, event_type: str, payload: Dict[str, Any]
) -> List[WebhookDelivery]:
    """Dispatch an event to all active webhook endpoints for a customer."""
    endpoints = WebhookEndpoint.objects.filter(customer=customer, active=True)
    deliveries = []
    for endpoint in endpoints:
        delivery = create_webhook_delivery(endpoint, event_type, payload)
        if delivery:
            deliveries.append(delivery)
            deliver_webhook(delivery)
    return deliveries


def process_pending_deliveries() -> Dict[str, int]:
    """Process all pending and retrying webhook deliveries."""
    now = timezone.now()
    pending = WebhookDelivery.objects.filter(
        status__in=["pending", "retrying"], next_attempt_at__lte=now
    ) | WebhookDelivery.objects.filter(status="pending", next_attempt_at__isnull=True)
    results = {"total": pending.count(), "success": 0, "failed": 0, "retrying": 0}
    for delivery in pending:
        if deliver_webhook(delivery):
            results["success"] += 1
        elif delivery.status == "retrying":
            results["retrying"] += 1
        else:
            results["failed"] += 1
    return results
