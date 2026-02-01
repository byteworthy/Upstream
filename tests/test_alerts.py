"""
Locust Load Tests for Alerts API Endpoints.

Tests the alerts list, detail, and acknowledge endpoints under load.

Target Performance:
- List: <500ms p95 response time
- Detail: <200ms p95 response time
- Acknowledge: <300ms p95 response time
- Error rate: <1%

Usage:
    # Run alerts tests only
    locust -f tests/test_alerts.py --host http://localhost:8000

    # Run headless for CI
    locust -f tests/test_alerts.py --headless -u 50 -r 5 -t 60s \
        --host http://localhost:8000 --csv=alerts_results
"""

import logging
import random
import sys
from pathlib import Path

from locust import between, events, task

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from upstream.tests_performance_base import (  # noqa: E402
    AuthenticatedUser,
    config,
)

logger = logging.getLogger(__name__)


# Alert severity levels
SEVERITY_LEVELS = ["low", "medium", "high", "critical"]

# Alert status values
ALERT_STATUSES = ["open", "acknowledged", "resolved", "dismissed"]


class AlertsListUser(AuthenticatedUser):
    """
    Load test user for alerts list operations.

    Tests paginated list views with various filters.
    """

    wait_time = between(1, 3)

    @task(5)
    def list_alerts_paginated(self):
        """
        GET /api/v1/alerts/ with pagination.

        Tests the paginated alerts list view.
        """
        page = random.randint(1, 5)
        page_size = random.choice([25, 50, 100])

        self.get_with_auth(
            f"/api/v1/alerts/?page={page}&page_size={page_size}",
            name="/api/v1/alerts/?page=[n]&page_size=[n]",
        )

    @task(3)
    def filter_alerts_by_severity(self):
        """
        GET /api/v1/alerts/?severity=X

        Tests filtering by severity level.
        """
        severity = random.choice(SEVERITY_LEVELS)
        self.get_with_auth(
            f"/api/v1/alerts/?severity={severity}",
            name="/api/v1/alerts/?severity=[level]",
        )

    @task(2)
    def filter_alerts_by_status(self):
        """
        GET /api/v1/alerts/?status=X

        Tests filtering by alert status.
        """
        status = random.choice(ALERT_STATUSES)
        self.get_with_auth(
            f"/api/v1/alerts/?status={status}",
            name="/api/v1/alerts/?status=[status]",
        )

    @task(2)
    def filter_open_alerts(self):
        """
        GET /api/v1/alerts/?status=open

        Tests a common pattern: getting all open alerts.
        """
        self.get_with_auth(
            "/api/v1/alerts/?status=open&page_size=50",
            name="/api/v1/alerts/?status=open",
        )

    @task(1)
    def filter_high_severity_open(self):
        """
        GET /api/v1/alerts/ with severity and status filters.

        Tests a common pattern: high-severity open alerts.
        """
        severity = random.choice(["high", "critical"])
        self.get_with_auth(
            f"/api/v1/alerts/?severity={severity}&status=open",
            name="/api/v1/alerts/?severity=[high]&status=open",
        )


class AlertsDetailUser(AuthenticatedUser):
    """
    Load test user for alerts detail operations.

    Tests individual alert retrieval.
    """

    wait_time = between(1, 2)

    @task
    def get_alert_detail(self):
        """
        GET /api/v1/alerts/{id}/

        Tests retrieving individual alert records.
        Accepts 404 for non-existent alerts.
        """
        alert_id = random.randint(1, 50)
        self.get_with_auth(
            f"/api/v1/alerts/{alert_id}/",
            allow_not_found=True,
            name="/api/v1/alerts/[id]/",
        )


class AlertsAcknowledgeUser(AuthenticatedUser):
    """
    Load test user for alert acknowledgment operations.

    Tests the acknowledge action on alerts.
    Note: This modifies data and may affect other test users.
    """

    wait_time = between(2, 5)

    @task
    def acknowledge_alert(self):
        """
        POST /api/v1/alerts/{id}/acknowledge/

        Tests acknowledging an alert.
        This is a write operation that changes alert state.
        """
        alert_id = random.randint(1, 50)

        # Use patch_with_auth for acknowledge action
        with self.client.post(
            f"/api/v1/alerts/{alert_id}/acknowledge/",
            headers=self.headers,
            json={},
            catch_response=True,
            name="/api/v1/alerts/[id]/acknowledge/",
        ) as response:
            # Accept 200 (success), 404 (not found), or 400 (already acknowledged)
            if response.status_code in [200, 404, 400]:
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")


class AlertsHighLoadUser(AuthenticatedUser):
    """
    High-load test user for alerts endpoints.

    Simulates aggressive API usage patterns for stress testing.
    """

    wait_time = between(0.5, 1)  # Faster pacing

    @task(3)
    def rapid_list_requests(self):
        """
        Rapid paginated list requests for stress testing.
        """
        page = random.randint(1, 3)
        self.get_with_auth(
            f"/api/v1/alerts/?page={page}&page_size=100",
            name="/api/v1/alerts/?page=[n] (stress)",
        )

    @task(2)
    def rapid_filter_requests(self):
        """
        Rapid filtered list requests for stress testing.
        """
        status = random.choice(ALERT_STATUSES)
        self.get_with_auth(
            f"/api/v1/alerts/?status={status}&page_size=100",
            name="/api/v1/alerts/?status=[status] (stress)",
        )

    @task(1)
    def rapid_detail_requests(self):
        """
        Rapid detail view requests for stress testing.
        """
        alert_id = random.randint(1, 100)
        self.get_with_auth(
            f"/api/v1/alerts/{alert_id}/",
            allow_not_found=True,
            name="/api/v1/alerts/[id]/ (stress)",
        )


# Event listeners for alerts-specific metrics
@events.test_start.add_listener
def on_alerts_test_start(environment, **kwargs):
    """Log alerts test configuration."""
    logger.info("=" * 60)
    logger.info("Alerts API Load Test Starting")
    logger.info(f"List threshold: {config.p95_list_threshold_ms}ms")
    logger.info(f"Detail threshold: {config.p95_detail_threshold_ms}ms")
    logger.info("=" * 60)


@events.test_stop.add_listener
def on_alerts_test_stop(environment, **kwargs):
    """Log alerts test summary."""
    logger.info("=" * 60)
    logger.info("Alerts API Load Test Completed")

    stats = environment.stats
    endpoints = [
        "/api/v1/alerts/?page=[n]&page_size=[n]",
        "/api/v1/alerts/?severity=[level]",
        "/api/v1/alerts/?status=[status]",
        "/api/v1/alerts/[id]/",
        "/api/v1/alerts/[id]/acknowledge/",
    ]

    for name in endpoints:
        entry = stats.entries.get((name, "GET")) or stats.entries.get((name, "POST"))
        if entry and entry.num_requests > 0:
            p95 = entry.get_response_time_percentile(0.95)
            logger.info(
                f"{name}: {entry.num_requests} requests, "
                f"avg {entry.avg_response_time:.0f}ms, "
                f"p95 {p95:.0f}ms, "
                f"failures {entry.num_failures}"
            )

    logger.info("=" * 60)
