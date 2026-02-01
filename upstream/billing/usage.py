"""
Usage tracking and reporting for billing.

Provides functions to record and aggregate customer usage
for usage-based billing calculations.
"""

import logging
from datetime import date
from calendar import monthrange
from typing import Optional
from django.db import transaction
from django.db.models import Sum
from upstream.models import Customer
from upstream.billing.models import UsageRecord

logger = logging.getLogger(__name__)


def get_current_period() -> tuple[date, date]:
    """Get the current billing period (month) start and end dates."""
    today = date.today()
    period_start = today.replace(day=1)
    last_day = monthrange(today.year, today.month)[1]
    period_end = today.replace(day=last_day)
    return period_start, period_end


def get_or_create_usage_record(customer: Customer) -> UsageRecord:
    """
    Get or create a UsageRecord for the current period.

    Args:
        customer: Customer model instance

    Returns:
        UsageRecord for current month
    """
    period_start, period_end = get_current_period()

    record, created = UsageRecord.objects.get_or_create(
        customer=customer,
        period_start=period_start,
        defaults={
            "period_end": period_end,
        },
    )

    if created:
        logger.info(
            "Created usage record for %s, period %s to %s",
            customer.name,
            period_start,
            period_end,
        )

    return record


def record_claim_processed(customer: Customer, count: int = 1) -> None:
    """
    Record claims processed for a customer.

    Args:
        customer: Customer model instance
        count: Number of claims processed (default 1)
    """
    with transaction.atomic():
        record = get_or_create_usage_record(customer)
        record.claims_processed += count
        record.save(update_fields=["claims_processed", "updated_at"])

    logger.debug(
        "Recorded %d claims processed for %s (total: %d)",
        count,
        customer.name,
        record.claims_processed,
    )


def record_claim_scored(customer: Customer, count: int = 1) -> None:
    """
    Record claims scored by AI for a customer.

    Args:
        customer: Customer model instance
        count: Number of claims scored (default 1)
    """
    with transaction.atomic():
        record = get_or_create_usage_record(customer)
        record.claims_scored += count
        record.save(update_fields=["claims_scored", "updated_at"])

    logger.debug(
        "Recorded %d claims scored for %s (total: %d)",
        count,
        customer.name,
        record.claims_scored,
    )


def record_api_call(customer: Customer, count: int = 1) -> None:
    """
    Record API calls for a customer.

    Args:
        customer: Customer model instance
        count: Number of API calls (default 1)
    """
    with transaction.atomic():
        record = get_or_create_usage_record(customer)
        record.api_calls += count
        record.save(update_fields=["api_calls", "updated_at"])


def record_storage_usage(customer: Customer, bytes_used: int) -> None:
    """
    Record storage usage for a customer.

    Args:
        customer: Customer model instance
        bytes_used: Total bytes used (replaces previous value)
    """
    with transaction.atomic():
        record = get_or_create_usage_record(customer)
        record.storage_bytes = bytes_used
        record.save(update_fields=["storage_bytes", "updated_at"])


def get_customer_usage(
    customer: Customer,
    period_start: Optional[date] = None,
) -> dict:
    """
    Get usage summary for a customer.

    Args:
        customer: Customer model instance
        period_start: Optional specific period (defaults to current)

    Returns:
        Dictionary with usage metrics
    """
    if period_start is None:
        period_start, _ = get_current_period()

    try:
        record = UsageRecord.objects.get(
            customer=customer,
            period_start=period_start,
        )
        return {
            "period_start": record.period_start.isoformat(),
            "period_end": record.period_end.isoformat(),
            "claims_processed": record.claims_processed,
            "claims_scored": record.claims_scored,
            "api_calls": record.api_calls,
            "storage_bytes": record.storage_bytes,
            "total_claims": record.total_claims,
        }
    except UsageRecord.DoesNotExist:
        # Return zeroes for period with no usage
        period_end = period_start.replace(
            day=monthrange(period_start.year, period_start.month)[1]
        )
        return {
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "claims_processed": 0,
            "claims_scored": 0,
            "api_calls": 0,
            "storage_bytes": 0,
            "total_claims": 0,
        }


def get_usage_history(customer: Customer, months: int = 6) -> list[dict]:
    """
    Get usage history for a customer.

    Args:
        customer: Customer model instance
        months: Number of months of history (default 6)

    Returns:
        List of usage dictionaries ordered by period (newest first)
    """
    records = UsageRecord.objects.filter(customer=customer).order_by("-period_start")[
        :months
    ]

    return [
        {
            "period_start": r.period_start.isoformat(),
            "period_end": r.period_end.isoformat(),
            "claims_processed": r.claims_processed,
            "claims_scored": r.claims_scored,
            "api_calls": r.api_calls,
            "storage_bytes": r.storage_bytes,
            "total_claims": r.total_claims,
        }
        for r in records
    ]


def get_aggregate_usage(
    period_start: Optional[date] = None,
) -> dict:
    """
    Get aggregate usage across all customers for a period.

    Args:
        period_start: Period to aggregate (defaults to current)

    Returns:
        Dictionary with aggregate metrics
    """
    if period_start is None:
        period_start, _ = get_current_period()

    aggregates = UsageRecord.objects.filter(period_start=period_start).aggregate(
        total_claims_processed=Sum("claims_processed"),
        total_claims_scored=Sum("claims_scored"),
        total_api_calls=Sum("api_calls"),
        total_storage_bytes=Sum("storage_bytes"),
    )

    return {
        "period_start": period_start.isoformat(),
        "total_claims_processed": aggregates["total_claims_processed"] or 0,
        "total_claims_scored": aggregates["total_claims_scored"] or 0,
        "total_api_calls": aggregates["total_api_calls"] or 0,
        "total_storage_bytes": aggregates["total_storage_bytes"] or 0,
        "customer_count": UsageRecord.objects.filter(period_start=period_start).count(),
    }
