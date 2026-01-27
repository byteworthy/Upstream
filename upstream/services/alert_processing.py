"""
Alert Processing Service

Extracts alert processing business logic from views and tasks into a stateless,
framework-agnostic service layer.

This service is responsible for:
- Evaluating alert rules against drift/delay events
- Processing alert delivery logic
- Computing alert priority scores
- Determining alert suppression based on cooldown and noise patterns

All methods accept domain objects (Alert, AlertRule, DriftEvent) and return
structured results that views/tasks can format into responses or actions.
"""

import logging
from typing import Dict, List, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Default suppression constants (can be overridden by config)
DEFAULT_COOLDOWN_HOURS = 4
DEFAULT_NOISE_WINDOW_DAYS = 7
DEFAULT_NOISE_THRESHOLD = 3


class AlertProcessingService:
    """
    Stateless service for alert processing and evaluation.

    All methods are static methods - no instance state.
    This ensures the service is framework-agnostic and easily testable.
    """

    @staticmethod
    def evaluate_alert_rules(
        drift_events: List[Dict[str, Any]],
        alert_rules: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Evaluate drift events against alert rules.

        Determines which events should trigger alerts based on configured
        rule criteria (severity thresholds, drift types, etc.).

        Args:
            drift_events: List of drift event dicts with keys:
                - id, payer, cpt_group, drift_type, severity, delta_value
            alert_rules: List of alert rule dicts with keys:
                - id, name, enabled, threshold_value, drift_type_filter

        Returns:
            list[dict]: List of triggered alerts with keys:
                - rule_id: int - ID of triggered rule
                - rule_name: str - Name of rule
                - event_id: int - ID of drift event
                - severity: float - Event severity
                - trigger_reason: str - Why the rule triggered
                - payload: dict - Alert payload data

        Example:
            >>> alerts = AlertProcessingService.evaluate_alert_rules(
            ...     drift_events=events,
            ...     alert_rules=rules
            ... )
            >>> print(f"Triggered {len(alerts)} alerts")
        """
        triggered_alerts = []

        for event in drift_events:
            for rule in alert_rules:
                # Skip disabled rules
                if not rule.get("enabled", True):
                    continue

                # Check drift type filter
                drift_type_filter = rule.get("drift_type_filter")
                if drift_type_filter and event.get("drift_type") != drift_type_filter:
                    continue

                # Check severity threshold
                threshold = rule.get("threshold_value", 0.0)
                event_severity = event.get("severity", 0.0)

                if event_severity >= threshold:
                    # Rule triggered!
                    alert = {
                        "rule_id": rule.get("id"),
                        "rule_name": rule.get("name", "Unnamed Rule"),
                        "event_id": event.get("id"),
                        "severity": event_severity,
                        "trigger_reason": (
                            f"Severity {event_severity:.2f} exceeds "
                            f"threshold {threshold:.2f}"
                        ),
                        "payload": {
                            "product_name": "DriftWatch",
                            "signal_type": event.get("drift_type"),
                            "entity_label": event.get("payer"),
                            "payer": event.get("payer"),
                            "cpt_group": event.get("cpt_group"),
                            "drift_type": event.get("drift_type"),
                            "baseline_value": event.get("baseline_value"),
                            "current_value": event.get("current_value"),
                            "delta_value": event.get("delta_value"),
                            "severity": event_severity,
                            "rule_name": rule.get("name"),
                            "rule_threshold": threshold,
                        },
                    }
                    triggered_alerts.append(alert)

        return triggered_alerts

    @staticmethod
    def process_alert_delivery(
        alert: Dict[str, Any],
        channels: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Process alert delivery to configured channels.

        Determines which channels should receive the alert and prepares
        delivery records with formatted content for each channel.

        Args:
            alert: Alert dict with keys:
                - id, severity, payload, customer_id
            channels: List of notification channel dicts with keys:
                - id, type (email/slack), config, enabled

        Returns:
            list[dict]: List of delivery records with keys:
                - channel_id: int - ID of channel
                - channel_type: str - Type (email/slack)
                - status: str - 'pending' or 'skipped'
                - content: dict - Formatted content for delivery
                - skip_reason: str - Why delivery was skipped (if applicable)

        Example:
            >>> deliveries = AlertProcessingService.process_alert_delivery(
            ...     alert=alert_data,
            ...     channels=notification_channels
            ... )
            >>> pending = [d for d in deliveries if d['status'] == 'pending']
            >>> print(f"{len(pending)} deliveries pending")
        """
        deliveries = []

        for channel in channels:
            # Skip disabled channels
            if not channel.get("enabled", True):
                deliveries.append(
                    {
                        "channel_id": channel.get("id"),
                        "channel_type": channel.get("type"),
                        "status": "skipped",
                        "content": {},
                        "skip_reason": "Channel disabled",
                    }
                )
                continue

            # Prepare content based on channel type
            channel_type = channel.get("type", "email")
            content = AlertProcessingService._format_alert_content(alert, channel_type)

            deliveries.append(
                {
                    "channel_id": channel.get("id"),
                    "channel_type": channel_type,
                    "status": "pending",
                    "content": content,
                    "skip_reason": None,
                }
            )

        return deliveries

    @staticmethod
    def compute_alert_priority(alert_data: Dict[str, Any]) -> int:
        """
        Compute alert priority score (0-10).

        Priority is based on:
        - Severity level (0-10 scale)
        - Delta magnitude (percentage change)
        - Historical frequency
        - Business impact indicators

        Args:
            alert_data: Dict with alert information:
                - severity: float - Alert severity (0.0-1.0)
                - delta_value: float - Change magnitude
                - baseline_value: float - Baseline for percentage calc
                - drift_type: str - Type of drift
                - consecutive_periods: int - How many periods this persists

        Returns:
            int: Priority score from 0 (lowest) to 10 (highest)

        Example:
            >>> priority = AlertProcessingService.compute_alert_priority(
            ...     alert_data={
            ...         "severity": 0.85,
            ...         "delta_value": 0.15,
            ...         "baseline_value": 0.50,
            ...         "drift_type": "DENIAL_RATE"
            ...     }
            ... )
            >>> if priority >= 8:
            ...     print("Critical priority - immediate action required")
        """
        # Start with severity (scaled to 0-10)
        severity = alert_data.get("severity", 0.0)
        priority = severity * 10

        # Adjust for delta magnitude
        delta = abs(alert_data.get("delta_value", 0.0))
        baseline = alert_data.get("baseline_value", 1.0)

        if baseline > 0:
            percent_change = (delta / baseline) * 100
            if percent_change > 50:
                priority += 2
            elif percent_change > 25:
                priority += 1

        # Adjust for consecutive periods (persistent issues)
        consecutive = alert_data.get("consecutive_periods", 1)
        if consecutive >= 3:
            priority += 2
        elif consecutive >= 2:
            priority += 1

        # Adjust for critical drift types
        critical_types = ["DENIAL_RATE", "PAYMENT_AMOUNT", "APPROVAL_RATE"]
        if alert_data.get("drift_type") in critical_types:
            priority += 1

        # Cap at 10
        return min(int(priority), 10)

    @staticmethod
    def should_suppress_alert(
        alert: Dict[str, Any],
        alert_history: List[Dict[str, Any]],
        cooldown_hours: int = DEFAULT_COOLDOWN_HOURS,
        noise_window_days: int = DEFAULT_NOISE_WINDOW_DAYS,
        noise_threshold: int = DEFAULT_NOISE_THRESHOLD,
    ) -> Dict[str, Any]:
        """
        Determine if alert should be suppressed.

        Checks two suppression criteria:
        1. Cooldown: Similar alert sent recently (within cooldown window)
        2. Noise pattern: Operators marked similar alerts as noise repeatedly

        Args:
            alert: Alert dict with keys:
                - product_name, signal_type, entity_label
            alert_history: List of recent alert dicts with keys:
                - id, status, notification_sent_at, payload,
                  operator_judgments (list of dicts with verdict, created_at)
            cooldown_hours: Hours for cooldown suppression (default: 4)
            noise_window_days: Days to look back for noise patterns (default: 7)
            noise_threshold: Min noise judgments to suppress (default: 3)

        Returns:
            dict: Suppression decision with keys:
                - suppressed: bool - Whether to suppress
                - reason: str - Suppression reason
                  ('cooldown', 'noise_pattern', or None)
                - details: dict - Additional context

        Example:
            >>> decision = AlertProcessingService.should_suppress_alert(
            ...     alert=alert_data,
            ...     alert_history=recent_alerts
            ... )
            >>> if decision['suppressed']:
            ...     print(f"Suppressed due to: {decision['reason']}")
        """
        result = {
            "suppressed": False,
            "reason": None,
            "details": {},
        }

        # Extract alert identifiers
        product = alert.get("product_name")
        signal_type = alert.get("signal_type")
        entity = alert.get("entity_label")

        # Check 1: Time-based cooldown
        now = datetime.now()
        cooldown_window = now - timedelta(hours=cooldown_hours)

        for hist_alert in alert_history:
            # Check if this is a similar alert sent recently
            hist_payload = hist_alert.get("payload", {})
            if (
                hist_payload.get("product_name") == product
                and hist_payload.get("signal_type") == signal_type
                and hist_payload.get("entity_label") == entity
            ):
                # Check if sent within cooldown window
                sent_at = hist_alert.get("notification_sent_at")
                if sent_at and hist_alert.get("status") == "sent":
                    if isinstance(sent_at, str):
                        sent_at = datetime.fromisoformat(sent_at.replace("Z", "+00:00"))

                    if sent_at >= cooldown_window:
                        result["suppressed"] = True
                        result["reason"] = "cooldown"
                        result["details"] = {
                            "last_sent_at": sent_at.isoformat() if sent_at else None,
                            "cooldown_hours": cooldown_hours,
                        }
                        return result

        # Check 2: Operator noise pattern
        noise_window = now - timedelta(days=noise_window_days)
        noise_count = 0

        for hist_alert in alert_history:
            hist_payload = hist_alert.get("payload", {})
            if (
                hist_payload.get("product_name") == product
                and hist_payload.get("signal_type") == signal_type
                and hist_payload.get("entity_label") == entity
            ):
                # Check operator judgments
                judgments = hist_alert.get("operator_judgments", [])
                for judgment in judgments:
                    if judgment.get("verdict") == "noise":
                        # Check if judgment is within noise window
                        created_at = judgment.get("created_at")
                        if created_at:
                            if isinstance(created_at, str):
                                created_at = datetime.fromisoformat(
                                    created_at.replace("Z", "+00:00")
                                )

                            if created_at >= noise_window:
                                noise_count += 1

        if noise_count >= noise_threshold:
            result["suppressed"] = True
            result["reason"] = "noise_pattern"
            result["details"] = {
                "noise_count": noise_count,
                "noise_threshold": noise_threshold,
                "noise_window_days": noise_window_days,
            }

        return result

    @staticmethod
    def _format_alert_content(
        alert: Dict[str, Any], channel_type: str
    ) -> Dict[str, Any]:
        """
        Format alert content for specific channel type.

        Private helper method for formatting alert data.

        Args:
            alert: Alert dict with payload data
            channel_type: Type of channel ('email' or 'slack')

        Returns:
            dict: Formatted content structure for the channel
        """
        payload = alert.get("payload", {})

        if channel_type == "email":
            return {
                "subject": f"Alert: {payload.get('signal_type', 'Drift Detected')}",
                "payer": payload.get("payer"),
                "drift_type": payload.get("drift_type"),
                "severity": payload.get("severity"),
                "delta_value": payload.get("delta_value"),
            }
        elif channel_type == "slack":
            return {
                "text": (
                    f"*{payload.get('signal_type', 'Alert')}* detected "
                    f"for {payload.get('payer', 'Unknown')}"
                ),
                "severity": payload.get("severity"),
                "fields": [
                    {"title": "Drift Type", "value": payload.get("drift_type")},
                    {"title": "Severity", "value": f"{payload.get('severity', 0):.2f}"},
                ],
            }
        else:
            # Generic format
            return payload
