"""
Billing signals for Stripe integration.

Handles automatic Stripe customer creation on Customer model save.
"""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from upstream.models import Customer
from upstream.billing.stripe_service import create_stripe_customer

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Customer)
def create_stripe_customer_on_save(sender, instance, created, **kwargs):
    """
    Create Stripe customer when a new Customer is created.

    Only creates Stripe customer for new Customer records that don't
    already have a stripe_customer_id.
    """
    if created and not instance.stripe_customer_id:
        stripe_customer_id = create_stripe_customer(instance)

        if stripe_customer_id:
            # Update customer with Stripe ID (without triggering signal again)
            Customer.objects.filter(pk=instance.pk).update(
                stripe_customer_id=stripe_customer_id
            )
            # Update the instance in memory too
            instance.stripe_customer_id = stripe_customer_id
            logger.info(
                "Linked Customer %s to Stripe customer %s",
                instance.name,
                stripe_customer_id,
            )
