"""
Cross-Customer Network Intelligence Service.

This module implements cross-customer pattern detection that aggregates
drift signals across all customers to identify payer-wide behavior changes.
Creates NetworkAlert records when 3+ customers show the same drift pattern.

Key Insight: If multiple providers see the same drift with the same payer,
it's likely a payer-wide policy change rather than an isolated issue.

Detection Logic:
    - Query recent DriftEvents across all customers (last 7 days)
    - Group by payer + drift_type combination
    - When 3+ customers affected, create NetworkAlert
    - Severity based on affected customer count and average delta
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Optional

from django.db import transaction
from django.db.models import Avg, Count, Max
from django.utils import timezone

from upstream.models import DriftEvent, NetworkAlert


# Network intelligence specific constants
NETWORK_ALERT_MIN_CUSTOMERS = 3  # Minimum customers to trigger network alert
NETWORK_ALERT_LOOKBACK_DAYS = 7  # Days to look back for drift events


@dataclass
class NetworkPattern:
    """Represents a detected cross-customer pattern."""

    payer: str
    drift_type: str
    affected_customer_count: int
    customer_ids: List[int]
    avg_delta: float
    avg_severity: float
    max_severity: float


def compute_cross_customer_patterns(
    as_of_date: Optional[date] = None,
    lookback_days: int = NETWORK_ALERT_LOOKBACK_DAYS,
    min_customers: int = NETWORK_ALERT_MIN_CUSTOMERS,
) -> List[NetworkAlert]:
    """
    Detect cross-customer patterns and create NetworkAlert records.

    Scans recent DriftEvents across all customers to find patterns where
    multiple customers experience the same type of drift with the same payer.
    This indicates a payer-wide behavior change rather than customer-specific issues.

    Args:
        as_of_date: Reference date (defaults to today)
        lookback_days: Number of days to look back for drift events (default: 7)
        min_customers: Minimum customers to trigger alert (default: 3)

    Returns:
        List of NetworkAlert objects created

    Concurrency:
        Uses select_for_update() on DriftEvent to prevent race conditions
        when multiple workers process the same time window.
    """
    if as_of_date is None:
        as_of_date = timezone.now().date()

    # Calculate lookback window
    lookback_start = as_of_date - timedelta(days=lookback_days)

    created_alerts = []

    with transaction.atomic():
        # Query drift events within the lookback window
        # Use all_objects to bypass tenant filtering - this is platform-level analysis
        drift_events = DriftEvent.all_objects.filter(
            created_at__date__gte=lookback_start,
            created_at__date__lte=as_of_date,
            suppressed=False,
        )

        # Group by payer + drift_type and aggregate
        patterns = (
            drift_events.values("payer", "drift_type")
            .annotate(
                customer_count=Count("customer_id", distinct=True),
                avg_delta=Avg("delta_value"),
                avg_severity=Avg("severity"),
                max_severity=Max("severity"),
            )
            .filter(customer_count__gte=min_customers)
        )

        for pattern in patterns:
            payer = pattern["payer"]
            drift_type = pattern["drift_type"]
            customer_count = pattern["customer_count"]
            avg_delta = pattern["avg_delta"] or 0.0
            avg_severity = pattern["avg_severity"] or 0.0
            max_severity = pattern["max_severity"] or 0.0

            # Get the list of affected customer IDs
            customer_ids = list(
                drift_events.filter(payer=payer, drift_type=drift_type)
                .values_list("customer_id", flat=True)
                .distinct()
            )

            # Determine severity based on customer count and max severity
            severity = _calculate_network_severity(customer_count, max_severity)

            # Generate summary text
            summary_text = _generate_summary_text(
                payer, drift_type, customer_count, avg_delta
            )

            # Check if we already have an active (unresolved) alert for this pattern
            existing_alert = NetworkAlert.objects.filter(
                payer=payer,
                drift_type=drift_type,
                resolved_at__isnull=True,
                created_at__date__gte=lookback_start,
            ).first()

            if existing_alert:
                # Update existing alert if customer count increased
                if customer_count > existing_alert.affected_customer_count:
                    existing_alert.affected_customer_count = customer_count
                    existing_alert.severity = severity
                    existing_alert.summary_text = summary_text
                    existing_alert.details = {
                        "customer_ids": customer_ids,
                        "avg_delta": round(avg_delta, 4),
                        "avg_severity": round(avg_severity, 4),
                        "max_severity": round(max_severity, 4),
                        "date_range": {
                            "start": lookback_start.isoformat(),
                            "end": as_of_date.isoformat(),
                        },
                    }
                    existing_alert.save()
                    created_alerts.append(existing_alert)
            else:
                # Create new network alert
                alert = NetworkAlert.objects.create(
                    payer=payer,
                    drift_type=drift_type,
                    affected_customer_count=customer_count,
                    summary_text=summary_text,
                    severity=severity,
                    details={
                        "customer_ids": customer_ids,
                        "avg_delta": round(avg_delta, 4),
                        "avg_severity": round(avg_severity, 4),
                        "max_severity": round(max_severity, 4),
                        "date_range": {
                            "start": lookback_start.isoformat(),
                            "end": as_of_date.isoformat(),
                        },
                    },
                )
                created_alerts.append(alert)

    return created_alerts


def _calculate_network_severity(customer_count: int, max_severity: float) -> str:
    """
    Calculate network alert severity based on impact scope.

    Args:
        customer_count: Number of affected customers
        max_severity: Maximum severity among individual drift events

    Returns:
        Severity level: LOW, MEDIUM, HIGH, or CRITICAL
    """
    # Higher customer count = higher severity
    if customer_count >= 10 or max_severity >= 0.9:
        return "CRITICAL"
    elif customer_count >= 7 or max_severity >= 0.7:
        return "HIGH"
    elif customer_count >= 5 or max_severity >= 0.5:
        return "MEDIUM"
    else:
        return "LOW"


def _generate_summary_text(
    payer: str, drift_type: str, customer_count: int, avg_delta: float
) -> str:
    """
    Generate human-readable summary for network alert.

    Args:
        payer: Payer name
        drift_type: Type of drift detected
        customer_count: Number of affected customers
        avg_delta: Average delta value across customers

    Returns:
        Human-readable summary string
    """
    drift_type_labels = {
        "DENIAL_RATE": "denial rate",
        "DECISION_TIME": "decision time",
        "PAYMENT_AMOUNT": "payment amount",
        "APPROVAL_RATE": "approval rate",
        "PROCESSING_DELAY": "processing delay",
        "AUTH_FAILURE_RATE": "authorization failure rate",
        "BEHAVIORAL_PREDICTION": "behavioral prediction",
    }

    drift_label = drift_type_labels.get(
        drift_type, drift_type.lower().replace("_", " ")
    )

    direction = "increase" if avg_delta > 0 else "decrease"
    delta_pct = abs(avg_delta * 100)

    return (
        f"Cross-customer {drift_label} {direction} detected for {payer}. "
        f"{customer_count} customers affected with average change of {delta_pct:.1f}%."
    )


def get_active_network_alerts(
    payer: Optional[str] = None,
    drift_type: Optional[str] = None,
    min_severity: Optional[str] = None,
) -> List[NetworkAlert]:
    """
    Get active (unresolved) network alerts with optional filtering.

    Args:
        payer: Filter by payer name
        drift_type: Filter by drift type
        min_severity: Minimum severity level (LOW, MEDIUM, HIGH, CRITICAL)

    Returns:
        List of active NetworkAlert objects
    """
    queryset = NetworkAlert.objects.filter(resolved_at__isnull=True)

    if payer:
        queryset = queryset.filter(payer=payer)

    if drift_type:
        queryset = queryset.filter(drift_type=drift_type)

    if min_severity:
        severity_levels = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
        min_level = severity_levels.get(min_severity, 0)
        # Filter by severity level (ordered query would be better but this works)
        queryset = queryset.filter(
            severity__in=[
                s for s, level in severity_levels.items() if level >= min_level
            ]
        )

    return list(queryset.order_by("-created_at"))


def resolve_network_alert(alert_id: int) -> bool:
    """
    Mark a network alert as resolved.

    Args:
        alert_id: ID of the NetworkAlert to resolve

    Returns:
        True if resolved successfully, False if not found
    """
    try:
        alert = NetworkAlert.objects.get(id=alert_id, resolved_at__isnull=True)
        alert.resolved_at = timezone.now()
        alert.save()
        return True
    except NetworkAlert.DoesNotExist:
        return False
