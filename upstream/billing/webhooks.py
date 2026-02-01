"""
Stripe webhook event handlers.

Processes Stripe webhook events for subscription lifecycle management.
"""

import logging
from datetime import datetime
from typing import Optional
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def handle_checkout_session_completed(event: dict) -> bool:
    """
    Handle checkout.session.completed event.

    Creates or updates Subscription when checkout completes successfully.
    """
    from upstream.models import Customer
    from upstream.billing.models import Subscription

    session = event.get("data", {}).get("object", {})
    subscription_id = session.get("subscription")
    customer_id = session.get("customer")
    metadata = session.get("metadata", {})

    upstream_customer_id = metadata.get("upstream_customer_id")
    tier = metadata.get("tier", "essentials")

    if not upstream_customer_id:
        logger.warning("Checkout session missing upstream_customer_id in metadata")
        return False

    try:
        customer = Customer.objects.get(pk=upstream_customer_id)

        # Create or update subscription
        subscription, created = Subscription.objects.update_or_create(
            customer=customer,
            defaults={
                "stripe_subscription_id": subscription_id,
                "tier": tier,
                "status": "active",
            },
        )

        logger.info(
            "Checkout completed: %s subscription for %s (sub: %s)",
            "Created" if created else "Updated",
            customer.name,
            subscription_id,
        )
        return True

    except Customer.DoesNotExist:
        logger.error("Customer %s not found for checkout session", upstream_customer_id)
        return False
    except Exception as e:
        logger.error("Error handling checkout.session.completed: %s", str(e))
        return False


def handle_subscription_updated(event: dict) -> bool:
    """
    Handle customer.subscription.updated event.

    Updates Subscription status and period when subscription changes.
    """
    from upstream.billing.models import Subscription

    subscription_data = event.get("data", {}).get("object", {})
    subscription_id = subscription_data.get("id")
    status = subscription_data.get("status")
    current_period_start = subscription_data.get("current_period_start")
    current_period_end = subscription_data.get("current_period_end")
    trial_end = subscription_data.get("trial_end")
    cancel_at_period_end = subscription_data.get("cancel_at_period_end", False)

    try:
        subscription = Subscription.objects.get(stripe_subscription_id=subscription_id)

        # Update subscription fields
        subscription.status = status
        subscription.cancel_at_period_end = cancel_at_period_end

        if current_period_start:
            subscription.current_period_start = timezone.make_aware(
                datetime.fromtimestamp(current_period_start)
            )
        if current_period_end:
            subscription.current_period_end = timezone.make_aware(
                datetime.fromtimestamp(current_period_end)
            )
        if trial_end:
            subscription.trial_end = timezone.make_aware(
                datetime.fromtimestamp(trial_end)
            )

        subscription.save()

        logger.info(
            "Subscription %s updated: status=%s, cancel_at_period_end=%s",
            subscription_id,
            status,
            cancel_at_period_end,
        )
        return True

    except Subscription.DoesNotExist:
        logger.warning("Subscription %s not found for update", subscription_id)
        return False
    except Exception as e:
        logger.error("Error handling customer.subscription.updated: %s", str(e))
        return False


def handle_subscription_deleted(event: dict) -> bool:
    """
    Handle customer.subscription.deleted event.

    Updates Subscription status to canceled.
    """
    from upstream.billing.models import Subscription

    subscription_data = event.get("data", {}).get("object", {})
    subscription_id = subscription_data.get("id")

    try:
        subscription = Subscription.objects.get(stripe_subscription_id=subscription_id)
        subscription.status = "canceled"
        subscription.canceled_at = timezone.now()
        subscription.save()

        logger.info("Subscription %s canceled", subscription_id)
        return True

    except Subscription.DoesNotExist:
        logger.warning("Subscription %s not found for deletion", subscription_id)
        return False
    except Exception as e:
        logger.error("Error handling customer.subscription.deleted: %s", str(e))
        return False


def handle_invoice_payment_succeeded(event: dict) -> bool:
    """
    Handle invoice.payment_succeeded event.

    Updates subscription and optionally sends notification.
    """
    invoice = event.get("data", {}).get("object", {})
    subscription_id = invoice.get("subscription")
    customer_email = invoice.get("customer_email")
    amount_paid = invoice.get("amount_paid", 0)

    logger.info(
        "Payment succeeded for subscription %s: $%.2f to %s",
        subscription_id,
        amount_paid / 100,
        customer_email,
    )

    # Could send email notification here
    # send_payment_success_email(customer_email, amount_paid)

    return True


def handle_invoice_payment_failed(event: dict) -> bool:
    """
    Handle invoice.payment_failed event.

    Updates subscription status and sends notification.
    """
    from upstream.billing.models import Subscription

    invoice = event.get("data", {}).get("object", {})
    subscription_id = invoice.get("subscription")
    customer_email = invoice.get("customer_email")
    attempt_count = invoice.get("attempt_count", 0)

    logger.warning(
        "Payment failed for subscription %s (attempt %d) - %s",
        subscription_id,
        attempt_count,
        customer_email,
    )

    # Update subscription status if we have it
    if subscription_id:
        try:
            subscription = Subscription.objects.get(
                stripe_subscription_id=subscription_id
            )
            subscription.status = "past_due"
            subscription.save()
        except Subscription.DoesNotExist:
            pass

    # Could send email notification here
    # send_payment_failed_email(customer_email, attempt_count)

    return True


# Event handler mapping
WEBHOOK_HANDLERS = {
    "checkout.session.completed": handle_checkout_session_completed,
    "customer.subscription.updated": handle_subscription_updated,
    "customer.subscription.deleted": handle_subscription_deleted,
    "invoice.payment_succeeded": handle_invoice_payment_succeeded,
    "invoice.payment_failed": handle_invoice_payment_failed,
}


def process_webhook_event(event: dict) -> bool:
    """
    Process a Stripe webhook event.

    Args:
        event: Stripe event dictionary

    Returns:
        True if event was handled successfully, False otherwise
    """
    event_type = event.get("type")
    handler = WEBHOOK_HANDLERS.get(event_type)

    if handler:
        return handler(event)
    else:
        logger.debug("Unhandled webhook event type: %s", event_type)
        return True  # Return True for unhandled events (not an error)


def verify_webhook_signature(payload: bytes, sig_header: str) -> Optional[dict]:
    """
    Verify Stripe webhook signature and construct event.

    Args:
        payload: Raw request body bytes
        sig_header: Stripe-Signature header value

    Returns:
        Stripe event dict if valid, None if verification fails
    """
    try:
        import stripe

        webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", None)
        if not webhook_secret:
            logger.warning("STRIPE_WEBHOOK_SECRET not configured")
            return None

        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        return event

    except ImportError:
        logger.error("Stripe library not installed")
        return None
    except Exception as e:
        logger.error("Webhook signature verification failed: %s", str(e))
        return None
