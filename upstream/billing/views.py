"""
Billing views for Stripe webhook handling.
"""

import logging
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from upstream.billing.webhooks import verify_webhook_signature, process_webhook_event

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """
    Handle Stripe webhook events.

    POST /webhooks/stripe/

    Validates Stripe signature and processes subscription lifecycle events.
    """
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

    # Verify signature and construct event
    event = verify_webhook_signature(payload, sig_header)
    if event is None:
        logger.warning("Webhook signature verification failed")
        return HttpResponse(status=400)

    # Process the event
    event_type = event.get("type", "unknown")
    logger.info("Received webhook event: %s", event_type)

    success = process_webhook_event(event)

    if success:
        return HttpResponse(status=200)
    else:
        logger.error("Failed to process webhook event: %s", event_type)
        return HttpResponse(status=500)
