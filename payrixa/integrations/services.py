"""Webhook services for signed delivery and retry logic."""
import hashlib
import hmac
import json
import logging
import requests
from django.utils import timezone
from .models import WebhookEndpoint, WebhookDelivery

logger = logging.getLogger(__name__)

def generate_signature(payload, secret):
    """Generate HMAC-SHA256 signature for webhook payload."""
    if isinstance(payload, dict):
        payload = json.dumps(payload, separators=(',', ':'), sort_keys=True)
    if isinstance(payload, str):
        payload = payload.encode('utf-8')
    if isinstance(secret, str):
        secret = secret.encode('utf-8')
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()

def verify_signature(payload, secret, signature):
    """Verify HMAC-SHA256 signature for webhook payload."""
    expected_signature = generate_signature(payload, secret)
    return hmac.compare_digest(expected_signature, signature)

def create_webhook_delivery(endpoint, event_type, payload):
    """Create a webhook delivery record."""
    if endpoint.event_types and event_type not in endpoint.event_types:
        return None
    if not endpoint.active:
        return None
    return WebhookDelivery.objects.create(endpoint=endpoint, event_type=event_type, payload=payload, status='pending')

def deliver_webhook(delivery):
    """Attempt to deliver a webhook."""
    endpoint = delivery.endpoint
    payload_str = json.dumps(delivery.payload, separators=(',', ':'), sort_keys=True)
    signature = generate_signature(payload_str, endpoint.secret)
    headers = {'Content-Type': 'application/json', 'X-Signature': signature, 'X-Webhook-Event': delivery.event_type, 'X-Webhook-Delivery-ID': str(delivery.id)}
    delivery.attempts += 1
    delivery.last_attempt_at = timezone.now()
    delivery.save()
    try:
        response = requests.post(endpoint.url, data=payload_str, headers=headers, timeout=30)
        delivery.response_code = response.status_code
        delivery.response_body = response.text[:1000]
        if 200 <= response.status_code < 300:
            delivery.status = 'success'
            delivery.save()
            return True
        else:
            delivery.last_error = f"HTTP {response.status_code}: {response.text[:200]}"
            delivery.schedule_next_attempt()
            return False
    except requests.exceptions.Timeout:
        delivery.last_error = "Request timed out"
        delivery.schedule_next_attempt()
        return False
    except Exception as e:
        delivery.last_error = f"Error: {str(e)}"
        delivery.schedule_next_attempt()
        return False

def dispatch_event(customer, event_type, payload):
    """Dispatch an event to all active webhook endpoints for a customer."""
    endpoints = WebhookEndpoint.objects.filter(customer=customer, active=True)
    deliveries = []
    for endpoint in endpoints:
        delivery = create_webhook_delivery(endpoint, event_type, payload)
        if delivery:
            deliveries.append(delivery)
            deliver_webhook(delivery)
    return deliveries

def process_pending_deliveries():
    """Process all pending and retrying webhook deliveries."""
    now = timezone.now()
    pending = WebhookDelivery.objects.filter(status__in=['pending', 'retrying'], next_attempt_at__lte=now) | WebhookDelivery.objects.filter(status='pending', next_attempt_at__isnull=True)
    results = {'total': pending.count(), 'success': 0, 'failed': 0, 'retrying': 0}
    for delivery in pending:
        if deliver_webhook(delivery):
            results['success'] += 1
        elif delivery.status == 'retrying':
            results['retrying'] += 1
        else:
            results['failed'] += 1
    return results
