"""
EHR Connection Health Monitoring.

Provides health checks for EHR connections with alerting on failures.
Runs hourly to verify token refresh and API connectivity.
"""

import logging
from datetime import timedelta
from typing import Dict, Any, List, Optional
from django.utils import timezone

from upstream.integrations.models import EHRConnection

logger = logging.getLogger(__name__)


class HealthCheckResult:
    """Result of a health check."""

    def __init__(
        self,
        connection_id: int,
        connection_name: str,
        ehr_type: str,
        healthy: bool,
        token_check: bool,
        api_check: bool,
        error: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.connection_id = connection_id
        self.connection_name = connection_name
        self.ehr_type = ehr_type
        self.healthy = healthy
        self.token_check = token_check
        self.api_check = api_check
        self.error = error
        self.details = details or {}
        self.checked_at = timezone.now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "connection_id": self.connection_id,
            "connection_name": self.connection_name,
            "ehr_type": self.ehr_type,
            "healthy": self.healthy,
            "token_check": self.token_check,
            "api_check": self.api_check,
            "error": self.error,
            "details": self.details,
            "checked_at": self.checked_at.isoformat(),
        }


def check_connection_health(connection: EHRConnection) -> HealthCheckResult:
    """
    Check health of a single EHR connection.

    Tests:
    1. Token refresh works
    2. Basic API connectivity (metadata endpoint)

    Args:
        connection: EHRConnection to check

    Returns:
        HealthCheckResult with check results
    """
    result_kwargs = {
        "connection_id": connection.id,
        "connection_name": connection.name,
        "ehr_type": connection.ehr_type,
        "healthy": False,
        "token_check": False,
        "api_check": False,
    }

    try:
        # Get appropriate client
        client = _get_client_for_connection(connection)
        if not client:
            result_kwargs["error"] = f"No client for EHR type: {connection.ehr_type}"
            return HealthCheckResult(**result_kwargs)

        # Test connection
        test_result = client.test_connection()

        result_kwargs["token_check"] = test_result.get("token_status") == "success"
        result_kwargs["api_check"] = test_result.get("api_status") == "success"
        result_kwargs["healthy"] = (
            result_kwargs["token_check"] and result_kwargs["api_check"]
        )
        result_kwargs["details"] = test_result

        if not result_kwargs["healthy"]:
            result_kwargs["error"] = test_result.get("error", "Health check failed")

    except Exception as e:
        result_kwargs["error"] = str(e)
        logger.exception(f"Health check failed for connection {connection.name}")

    return HealthCheckResult(**result_kwargs)


def _get_client_for_connection(connection: EHRConnection):
    """Get the appropriate client class for the connection type."""
    if connection.ehr_type == "epic":
        from upstream.integrations.epic import EpicFHIRClient

        return EpicFHIRClient(connection)
    elif connection.ehr_type == "cerner":
        from upstream.integrations.cerner import CernerFHIRClient

        return CernerFHIRClient(connection)
    elif connection.ehr_type == "athena":
        from upstream.integrations.athena import AthenaHealthClient

        return AthenaHealthClient(connection)
    return None


def check_all_connections() -> List[HealthCheckResult]:
    """
    Check health of all enabled EHR connections.

    Returns:
        List of HealthCheckResult for each connection
    """
    connections = EHRConnection.objects.filter(enabled=True)
    results = []

    for connection in connections:
        logger.info(f"Checking health of connection: {connection.name}")
        result = check_connection_health(connection)
        results.append(result)

        # Update connection health status
        _update_connection_status(connection, result)

    return results


def _update_connection_status(connection: EHRConnection, result: HealthCheckResult):
    """Update connection's health status based on check result."""
    if result.healthy:
        connection.health_status = "healthy"
        connection.last_error = None
    else:
        # Check if this is a degraded state (partial success)
        if result.token_check or result.api_check:
            connection.health_status = "degraded"
        else:
            connection.health_status = "unhealthy"
        connection.last_error = result.error

    connection.health_checked_at = result.checked_at
    connection.save(update_fields=["health_status", "health_checked_at", "last_error"])


def get_health_summary() -> Dict[str, Any]:
    """
    Get summary of all EHR connection health statuses.

    Returns:
        Dict with health summary for dashboard display
    """
    connections = EHRConnection.objects.filter(enabled=True)

    summary = {
        "total_connections": connections.count(),
        "healthy": 0,
        "degraded": 0,
        "unhealthy": 0,
        "unknown": 0,
        "by_type": {},
        "last_checked": None,
    }

    for connection in connections:
        status = connection.health_status
        if status == "healthy":
            summary["healthy"] += 1
        elif status == "degraded":
            summary["degraded"] += 1
        elif status == "unhealthy":
            summary["unhealthy"] += 1
        else:
            summary["unknown"] += 1

        # Track by EHR type
        ehr_type = connection.ehr_type
        if ehr_type not in summary["by_type"]:
            summary["by_type"][ehr_type] = {
                "total": 0,
                "healthy": 0,
                "unhealthy": 0,
            }
        summary["by_type"][ehr_type]["total"] += 1
        if status == "healthy":
            summary["by_type"][ehr_type]["healthy"] += 1
        elif status in ("unhealthy", "degraded"):
            summary["by_type"][ehr_type]["unhealthy"] += 1

        # Track most recent check
        if connection.health_checked_at:
            if (
                summary["last_checked"] is None
                or connection.health_checked_at > summary["last_checked"]
            ):
                summary["last_checked"] = connection.health_checked_at

    # Calculate overall health percentage
    if summary["total_connections"] > 0:
        summary["health_percentage"] = (
            summary["healthy"] / summary["total_connections"] * 100
        )
    else:
        summary["health_percentage"] = 100.0

    return summary


def get_unhealthy_connections() -> List[EHRConnection]:
    """
    Get list of unhealthy or degraded connections.

    Returns:
        List of EHRConnection instances needing attention
    """
    return list(
        EHRConnection.objects.filter(
            enabled=True,
            health_status__in=["unhealthy", "degraded"],
        )
    )


def create_health_alert(connection: EHRConnection, result: HealthCheckResult):
    """
    Create alert for unhealthy connection.

    Args:
        connection: Unhealthy EHRConnection
        result: HealthCheckResult with failure details
    """
    from upstream.alerts.models import Alert, AlertRule

    try:
        # Find or create alert rule for EHR health
        rule, _ = AlertRule.objects.get_or_create(
            customer=connection.customer,
            name="EHR Connection Health",
            defaults={
                "alert_type": "health_check",
                "severity": "high",
                "conditions": {"type": "ehr_connection_health"},
                "notification_channels": ["email"],
                "enabled": True,
            },
        )

        # Create alert
        Alert.objects.create(
            customer=connection.customer,
            rule=rule,
            severity="high" if not result.healthy else "medium",
            title=f"EHR Connection Unhealthy: {connection.name}",
            message=(
                f"Connection '{connection.name}' ({connection.get_ehr_type_display()}) "
                f"failed health check.\n\n"
                f"Token Check: {'Pass' if result.token_check else 'Fail'}\n"
                f"API Check: {'Pass' if result.api_check else 'Fail'}\n"
                f"Error: {result.error or 'Unknown'}"
            ),
            metadata={
                "connection_id": connection.id,
                "ehr_type": connection.ehr_type,
                "health_result": result.to_dict(),
            },
        )

        logger.info(f"Created health alert for connection {connection.name}")

    except Exception as e:
        logger.error(f"Failed to create health alert: {e}")


def should_alert_for_connection(connection: EHRConnection) -> bool:
    """
    Check if we should create an alert for this connection.

    Prevents alert spam by checking recent alert history.

    Args:
        connection: EHRConnection to check

    Returns:
        True if alert should be created
    """
    from upstream.alerts.models import Alert

    # Check if there's a recent alert (within last hour)
    one_hour_ago = timezone.now() - timedelta(hours=1)

    recent_alerts = Alert.objects.filter(
        customer=connection.customer,
        metadata__connection_id=connection.id,
        created_at__gte=one_hour_ago,
    ).exists()

    return not recent_alerts
