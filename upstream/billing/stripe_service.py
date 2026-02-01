"""
Stripe integration service for billing operations.

Handles all Stripe API interactions:
- Customer creation
- Checkout session creation
- Subscription management
"""

import logging
from typing import Optional
from django.conf import settings

logger = logging.getLogger(__name__)

# Stripe price IDs (configured per environment)
STRIPE_PRICE_IDS = {
    "essentials": getattr(settings, "STRIPE_PRICE_ESSENTIALS", "price_essentials"),
    "professional": getattr(
        settings, "STRIPE_PRICE_PROFESSIONAL", "price_professional"
    ),
    "enterprise": getattr(settings, "STRIPE_PRICE_ENTERPRISE", "price_enterprise"),
}

# Trial period in days
TRIAL_PERIOD_DAYS = 30


def get_stripe_client():
    """Get configured Stripe client."""
    try:
        import stripe

        stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", None)
        return stripe
    except ImportError:
        logger.warning("Stripe library not installed")
        return None


def create_stripe_customer(customer) -> Optional[str]:
    """
    Create a Stripe customer for the given Customer model instance.

    Args:
        customer: Customer model instance with name attribute

    Returns:
        Stripe customer ID (cus_xxxxx) or None if creation fails

    Raises:
        No exceptions raised - errors are logged and None returned
    """
    stripe = get_stripe_client()
    if stripe is None or not stripe.api_key:
        logger.info(
            "Stripe not configured, skipping customer creation for %s", customer.name
        )
        return None

    try:
        # Get email from customer settings if available
        email = None
        if hasattr(customer, "settings") and customer.settings:
            email = customer.settings.to_email

        # Create Stripe customer with metadata
        stripe_customer = stripe.Customer.create(
            name=customer.name,
            email=email,
            metadata={
                "upstream_customer_id": str(customer.id),
                "customer_name": customer.name,
            },
        )

        logger.info(
            "Created Stripe customer %s for %s",
            stripe_customer.id,
            customer.name,
        )

        return stripe_customer.id

    except Exception as e:
        logger.error(
            "Failed to create Stripe customer for %s: %s",
            customer.name,
            str(e),
        )
        return None


def update_stripe_customer(customer) -> bool:
    """
    Update Stripe customer with latest Customer model data.

    Args:
        customer: Customer model instance

    Returns:
        True if update succeeded, False otherwise
    """
    stripe = get_stripe_client()
    if stripe is None or not stripe.api_key:
        return False

    if not customer.stripe_customer_id:
        logger.warning("Customer %s has no Stripe customer ID", customer.name)
        return False

    try:
        email = None
        if hasattr(customer, "settings") and customer.settings:
            email = customer.settings.to_email

        stripe.Customer.modify(
            customer.stripe_customer_id,
            name=customer.name,
            email=email,
            metadata={
                "upstream_customer_id": str(customer.id),
                "customer_name": customer.name,
            },
        )

        logger.info(
            "Updated Stripe customer %s for %s",
            customer.stripe_customer_id,
            customer.name,
        )
        return True

    except Exception as e:
        logger.error(
            "Failed to update Stripe customer for %s: %s",
            customer.name,
            str(e),
        )
        return False


def delete_stripe_customer(stripe_customer_id: str) -> bool:
    """
    Delete a Stripe customer.

    Args:
        stripe_customer_id: Stripe customer ID to delete

    Returns:
        True if deletion succeeded, False otherwise
    """
    stripe = get_stripe_client()
    if stripe is None or not stripe.api_key:
        return False

    try:
        stripe.Customer.delete(stripe_customer_id)
        logger.info("Deleted Stripe customer %s", stripe_customer_id)
        return True

    except Exception as e:
        logger.error(
            "Failed to delete Stripe customer %s: %s",
            stripe_customer_id,
            str(e),
        )
        return False


def get_stripe_customer(stripe_customer_id: str) -> Optional[dict]:
    """
    Retrieve Stripe customer details.

    Args:
        stripe_customer_id: Stripe customer ID

    Returns:
        Stripe customer object dict or None
    """
    stripe = get_stripe_client()
    if stripe is None or not stripe.api_key:
        return None

    try:
        return stripe.Customer.retrieve(stripe_customer_id)
    except Exception as e:
        logger.error(
            "Failed to retrieve Stripe customer %s: %s",
            stripe_customer_id,
            str(e),
        )
        return None
