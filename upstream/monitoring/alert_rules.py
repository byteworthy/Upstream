"""
Platform Monitoring Alert Rules

Defines alert rules for platform health monitoring and notification delivery.

Alert rule evaluation logic queries Prometheus metrics exposed at /metrics endpoint
and fires alerts when thresholds are exceeded. Notifications are sent via email
and Slack channels configured in Django settings.

This is distinct from business alerts (drift/delay notifications to customers).
Platform alerts notify operators about infrastructure health.

Usage:
    from upstream.monitoring.alert_rules import evaluate_alert_rules, send_alert_notification

    # Evaluate all rules
    triggered = evaluate_alert_rules()

    # Send notifications
    for alert in triggered:
        send_alert_notification(alert)
"""

import logging
import re
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail

logger = logging.getLogger("upstream.monitoring.alerts")

# =============================================================================
# Alert Rule Definitions
# =============================================================================

ALERT_RULES = [
    {
        "name": "high_error_rate",
        "description": "High rate of 5xx errors detected",
        "severity": "critical",
        "metric": "django_http_responses_total_by_status_total",
        "condition": "5xx_rate > threshold",
        "window": "5m",
        "threshold_key": "error_rate",
        "notification_channels": ["email", "slack"],
    },
    {
        "name": "slow_response_time",
        "description": "API response time p95 exceeds threshold",
        "severity": "warning",
        "metric": "django_http_requests_latency_seconds_by_view_method",
        "condition": "p95 > threshold",
        "window": "5m",
        "threshold_key": "response_time_p95",
        "notification_channels": ["email", "slack"],
    },
    {
        "name": "db_pool_exhaustion",
        "description": "Database connection pool nearing capacity",
        "severity": "critical",
        "metric": "django_db_connections_total",
        "condition": "utilization > threshold",
        "window": "1m",
        "threshold_key": "db_pool_utilization",
        "notification_channels": ["email", "slack"],
    },
    {
        "name": "celery_task_failures",
        "description": "High rate of Celery task failures",
        "severity": "warning",
        "metric": "upstream_background_job_failed_total",
        "condition": "failure_rate > threshold",
        "window": "15m",
        "threshold_key": "celery_failure_rate",
        "notification_channels": ["email", "slack"],
    },
]


# =============================================================================
# Alert Evaluation
# =============================================================================


def evaluate_alert_rules() -> List[Dict[str, Any]]:
    """
    Evaluate all alert rules against current Prometheus metrics.

    Queries the /metrics endpoint, parses prometheus_client text format,
    and compares current values against configured thresholds.

    Returns:
        list[dict]: List of triggered alerts with keys:
            - rule_name: str - Name of triggered rule
            - severity: str - Alert severity (critical/warning)
            - description: str - Alert description
            - current_value: float - Current metric value
            - threshold: float - Configured threshold
            - metric: str - Prometheus metric name
            - timestamp: str - ISO format timestamp
            - message: str - Human-readable alert message

    Example:
        >>> triggered = evaluate_alert_rules()
        >>> for alert in triggered:
        ...     print(f"{alert['rule_name']}: {alert['message']}")
    """
    triggered_alerts = []

    # Check if monitoring alerts are enabled
    monitoring_config = getattr(settings, "MONITORING_ALERTS", {})
    if not monitoring_config.get("enabled", True):
        logger.debug("Monitoring alerts disabled in settings")
        return triggered_alerts

    thresholds = monitoring_config.get("thresholds", {})

    for rule in ALERT_RULES:
        try:
            # Get threshold from settings
            threshold_key = rule["threshold_key"]
            threshold = thresholds.get(threshold_key)

            if threshold is None:
                logger.warning(
                    f"No threshold configured for {threshold_key}, skipping rule {rule['name']}"
                )
                continue

            # Evaluate rule based on metric type
            current_value = None
            rule_name = rule["name"]

            if rule_name == "high_error_rate":
                current_value = _evaluate_error_rate()
            elif rule_name == "slow_response_time":
                current_value = _evaluate_response_time()
            elif rule_name == "db_pool_exhaustion":
                current_value = _evaluate_db_pool_utilization()
            elif rule_name == "celery_task_failures":
                current_value = _evaluate_celery_failure_rate()

            # Check if threshold exceeded
            if current_value is not None and current_value > threshold:
                # Check suppression before adding to triggered list
                if not should_suppress_alert(rule_name):
                    alert = {
                        "rule_name": rule_name,
                        "severity": rule["severity"],
                        "description": rule["description"],
                        "current_value": current_value,
                        "threshold": threshold,
                        "metric": rule["metric"],
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "message": _format_alert_message(
                            rule, current_value, threshold
                        ),
                    }
                    triggered_alerts.append(alert)
                    logger.info(f"Alert triggered: {rule_name} - {alert['message']}")
                else:
                    logger.debug(f"Alert suppressed (cooldown): {rule_name}")

        except Exception as e:
            logger.error(f"Error evaluating rule {rule['name']}: {e}", exc_info=True)
            continue

    return triggered_alerts


def _evaluate_error_rate() -> Optional[float]:
    """
    Calculate 5xx error rate from django_http_responses_total_by_status_total metric.

    Returns:
        float: Error rate as decimal (0.05 = 5%) or None if metrics unavailable
    """
    try:
        metrics = _query_prometheus_metrics()

        # Count total requests and 5xx responses
        total_requests = 0
        error_requests = 0

        # Parse prometheus text format
        for line in metrics.split("\n"):
            if line.startswith("django_http_responses_total_by_status_total"):
                # Example: django_http_responses_total_by_status_total{status="200"} 1234
                match = re.search(r'status="(\d+)"\}\s+([\d.]+)', line)
                if match:
                    status_code = match.group(1)
                    count = float(match.group(2))
                    total_requests += count

                    if status_code.startswith("5"):
                        error_requests += count

        if total_requests == 0:
            return 0.0

        error_rate = error_requests / total_requests
        return error_rate

    except Exception as e:
        logger.error(f"Error calculating error rate: {e}")
        return None


def _evaluate_response_time() -> Optional[float]:
    """
    Calculate p95 response time from django_http_requests_latency_seconds_by_view_method.

    Returns:
        float: p95 latency in milliseconds or None if metrics unavailable
    """
    try:
        metrics = _query_prometheus_metrics()

        # Look for latency histogram quantiles (if available)
        # Or approximate from bucket counts
        latencies = []

        for line in metrics.split("\n"):
            if (
                "django_http_requests_latency_seconds_by_view_method" in line
                and "quantile" in line
            ):
                # Example: django_http_requests_latency_seconds_by_view_method{quantile="0.95"} 0.234
                match = re.search(r'quantile="0\.95"\}\s+([\d.]+)', line)
                if match:
                    latency_seconds = float(match.group(1))
                    return latency_seconds * 1000  # Convert to milliseconds

        # If no quantile available, return None (Prometheus needs to be configured for quantiles)
        # For now, return a safe value indicating no data
        return None

    except Exception as e:
        logger.error(f"Error calculating response time: {e}")
        return None


def _evaluate_db_pool_utilization() -> Optional[float]:
    """
    Calculate database connection pool utilization percentage.

    Returns:
        float: Pool utilization as decimal (0.90 = 90%) or None if unavailable
    """
    try:
        metrics = _query_prometheus_metrics()

        # Look for django-prometheus DB connection metrics
        # django_db_connections_total shows active connections
        active_connections = 0
        max_connections = 100  # Default, should be from settings

        for line in metrics.split("\n"):
            if line.startswith("django_db_connections_total"):
                # Example: django_db_connections_total{alias="default"} 15
                match = re.search(r"\}\s+([\d.]+)", line)
                if match:
                    active_connections = float(match.group(1))

        # Get max connections from Django settings
        from django.conf import settings

        db_settings = settings.DATABASES.get("default", {})
        max_conn_setting = db_settings.get("CONN_MAX_AGE")

        # For SQLite or if not set, use a reasonable default
        if max_conn_setting and max_conn_setting > 0:
            max_connections = max_conn_setting
        else:
            max_connections = 100  # PostgreSQL default

        if max_connections == 0:
            return 0.0

        utilization = active_connections / max_connections
        return utilization

    except Exception as e:
        logger.error(f"Error calculating DB pool utilization: {e}")
        return None


def _evaluate_celery_failure_rate() -> Optional[float]:
    """
    Calculate Celery task failure rate from upstream_background_job_failed_total.

    Returns:
        float: Failure rate as decimal (0.10 = 10%) or None if unavailable
    """
    try:
        metrics = _query_prometheus_metrics()

        total_jobs = 0
        failed_jobs = 0

        # Count completed and failed jobs
        for line in metrics.split("\n"):
            if line.startswith("upstream_background_job_completed_total"):
                match = re.search(r"\}\s+([\d.]+)", line)
                if match:
                    total_jobs += float(match.group(1))

            if line.startswith("upstream_background_job_failed_total"):
                match = re.search(r"\}\s+([\d.]+)", line)
                if match:
                    count = float(match.group(1))
                    failed_jobs += count
                    total_jobs += count

        if total_jobs == 0:
            return 0.0

        failure_rate = failed_jobs / total_jobs
        return failure_rate

    except Exception as e:
        logger.error(f"Error calculating Celery failure rate: {e}")
        return None


def _query_prometheus_metrics() -> str:
    """
    Query Prometheus metrics endpoint and return raw text format.

    Returns:
        str: Prometheus text format metrics

    Raises:
        requests.RequestException: If metrics endpoint is unavailable
    """
    # Construct metrics URL (local endpoint)
    metrics_path = getattr(settings, "PROMETHEUS_METRICS_PATH", "/metrics")

    # For local queries, use localhost
    metrics_url = f"http://localhost:8000{metrics_path}"

    try:
        response = requests.get(metrics_url, timeout=5)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        logger.error(f"Failed to query Prometheus metrics at {metrics_url}: {e}")
        raise


# =============================================================================
# Alert Notification
# =============================================================================


def send_alert_notification(alert: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send alert notification to configured channels (email and Slack).

    Args:
        alert: Alert dict with keys:
            - rule_name, severity, description, current_value, threshold, message

    Returns:
        dict: Delivery status with keys:
            - email_sent: bool
            - slack_sent: bool
            - errors: list[str]

    Example:
        >>> alert = triggered_alerts[0]
        >>> result = send_alert_notification(alert)
        >>> if result['email_sent']:
        ...     print("Email notification sent successfully")
    """
    result = {
        "email_sent": False,
        "slack_sent": False,
        "errors": [],
    }

    monitoring_config = getattr(settings, "MONITORING_ALERTS", {})

    # Send email notification
    email_config = monitoring_config.get("email", {})
    if email_config.get("enabled", True):
        try:
            _send_email_notification(alert, email_config)
            result["email_sent"] = True
            logger.info(f"Email notification sent for alert: {alert['rule_name']}")
        except Exception as e:
            error_msg = f"Email notification failed: {e}"
            result["errors"].append(error_msg)
            logger.error(error_msg, exc_info=True)

    # Send Slack notification
    slack_config = monitoring_config.get("slack", {})
    if slack_config.get("enabled", False):
        try:
            _send_slack_notification(alert, slack_config)
            result["slack_sent"] = True
            logger.info(f"Slack notification sent for alert: {alert['rule_name']}")
        except Exception as e:
            error_msg = f"Slack notification failed: {e}"
            result["errors"].append(error_msg)
            logger.error(error_msg, exc_info=True)

    # Record alert in suppression cache
    _record_alert_in_cache(alert)

    return result


def _send_email_notification(
    alert: Dict[str, Any], email_config: Dict[str, Any]
) -> None:
    """
    Send email notification for alert.

    Args:
        alert: Alert dict
        email_config: Email configuration from settings

    Raises:
        Exception: If email sending fails
    """
    recipients = email_config.get("recipients", [])
    from_email = email_config.get("from_email", settings.DEFAULT_FROM_EMAIL)

    if not recipients:
        logger.warning("No email recipients configured for monitoring alerts")
        return

    # Format email content
    severity_emoji = "🚨" if alert["severity"] == "critical" else "⚠️"
    subject = f"{severity_emoji} [{alert['severity'].upper()}] {alert['description']}"

    message = f"""
Platform Monitoring Alert

Rule: {alert['rule_name']}
Severity: {alert['severity']}
Time: {alert['timestamp']}

{alert['message']}

Metric: {alert['metric']}
Current Value: {alert['current_value']:.4f}
Threshold: {alert['threshold']:.4f}

---
This is an automated alert from Upstream Healthcare Platform monitoring.
    """.strip()

    send_mail(
        subject=subject,
        message=message,
        from_email=from_email,
        recipient_list=recipients,
        fail_silently=False,
    )


def _send_slack_notification(
    alert: Dict[str, Any], slack_config: Dict[str, Any]
) -> None:
    """
    Send Slack notification for alert.

    Args:
        alert: Alert dict
        slack_config: Slack configuration from settings

    Raises:
        Exception: If Slack webhook fails
    """
    webhook_url = slack_config.get("webhook_url")

    if not webhook_url:
        logger.warning("No Slack webhook URL configured for monitoring alerts")
        return

    # Format Slack message
    severity_emoji = (
        ":rotating_light:" if alert["severity"] == "critical" else ":warning:"
    )
    color = "danger" if alert["severity"] == "critical" else "warning"

    payload = {
        "username": slack_config.get("username", "Upstream Monitoring"),
        "icon_emoji": slack_config.get("icon_emoji", ":rotating_light:"),
        "channel": slack_config.get("channel", "#alerts"),
        "attachments": [
            {
                "color": color,
                "title": f"{severity_emoji} {alert['description']}",
                "text": alert["message"],
                "fields": [
                    {
                        "title": "Rule",
                        "value": alert["rule_name"],
                        "short": True,
                    },
                    {
                        "title": "Severity",
                        "value": alert["severity"].upper(),
                        "short": True,
                    },
                    {
                        "title": "Current Value",
                        "value": f"{alert['current_value']:.4f}",
                        "short": True,
                    },
                    {
                        "title": "Threshold",
                        "value": f"{alert['threshold']:.4f}",
                        "short": True,
                    },
                ],
                "footer": "Upstream Monitoring",
                "ts": int(datetime.utcnow().timestamp()),
            }
        ],
    }

    response = requests.post(webhook_url, json=payload, timeout=10)
    response.raise_for_status()


# =============================================================================
# Alert Suppression
# =============================================================================


def should_suppress_alert(rule_name: str) -> bool:
    """
    Check if alert should be suppressed based on cooldown period.

    Prevents duplicate notifications for the same alert within cooldown window.

    Args:
        rule_name: Name of the alert rule

    Returns:
        bool: True if alert should be suppressed, False otherwise
    """
    monitoring_config = getattr(settings, "MONITORING_ALERTS", {})
    cooldown_seconds = monitoring_config.get(
        "cooldown_period", 300
    )  # 5 minutes default

    # Check cache for recent alert
    cache_key = f"monitoring_alert:{rule_name}"
    last_sent = cache.get(cache_key)

    if last_sent:
        elapsed = (datetime.utcnow() - last_sent).total_seconds()
        if elapsed < cooldown_seconds:
            return True

    return False


def _record_alert_in_cache(alert: Dict[str, Any]) -> None:
    """
    Record alert in cache for suppression tracking.

    Args:
        alert: Alert dict
    """
    monitoring_config = getattr(settings, "MONITORING_ALERTS", {})
    cooldown_seconds = monitoring_config.get("cooldown_period", 300)

    cache_key = f"monitoring_alert:{alert['rule_name']}"
    cache.set(cache_key, datetime.utcnow(), timeout=cooldown_seconds)


# =============================================================================
# Formatting Helpers
# =============================================================================


def _format_alert_message(
    rule: Dict[str, Any], current_value: float, threshold: float
) -> str:
    """
    Format human-readable alert message.

    Args:
        rule: Alert rule dict
        current_value: Current metric value
        threshold: Configured threshold

    Returns:
        str: Formatted message
    """
    rule_name = rule["name"]

    if rule_name == "high_error_rate":
        return (
            f"Error rate is {current_value*100:.2f}% (threshold: {threshold*100:.2f}%)"
        )
    elif rule_name == "slow_response_time":
        return (
            f"p95 response time is {current_value:.0f}ms (threshold: {threshold:.0f}ms)"
        )
    elif rule_name == "db_pool_exhaustion":
        return f"Database pool utilization is {current_value*100:.1f}% (threshold: {threshold*100:.1f}%)"
    elif rule_name == "celery_task_failures":
        return f"Celery task failure rate is {current_value*100:.2f}% (threshold: {threshold*100:.2f}%)"
    else:
        return f"Value {current_value:.4f} exceeds threshold {threshold:.4f}"
