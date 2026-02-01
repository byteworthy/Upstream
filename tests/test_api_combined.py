"""
Locust Load Tests for Core API Endpoints.

Tests drift events, uploads, reports, and dashboard endpoints under load.

Target Performance:
- List: <500ms p95 response time
- Detail: <200ms p95 response time
- Dashboard: <500ms p95 response time
- Error rate: <1%

Usage:
    # Run API tests only
    locust -f tests/test_api_combined.py --host http://localhost:8000

    # Run headless for CI
    locust -f tests/test_api_combined.py --headless -u 50 -r 5 -t 60s \
        --host http://localhost:8000 --csv=api_results
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


class DriftEventsUser(AuthenticatedUser):
    """
    Load test user for drift events operations.

    Tests the drift events list, filtering, and detail views.
    """

    wait_time = between(1, 3)

    @task(5)
    def list_drift_events(self):
        """
        GET /api/v1/drift-events/ with pagination.

        Tests the paginated drift events list.
        """
        page = random.randint(1, 5)
        page_size = random.choice([25, 50, 100])

        self.get_with_auth(
            f"/api/v1/drift-events/?page={page}&page_size={page_size}",
            name="/api/v1/drift-events/?page=[n]&page_size=[n]",
        )

    @task(3)
    def filter_drift_by_severity(self):
        """
        GET /api/v1/drift-events/?min_severity=X

        Tests filtering by minimum severity score.
        """
        severity = random.choice([0.3, 0.5, 0.7, 0.8])
        self.get_with_auth(
            f"/api/v1/drift-events/?min_severity={severity}",
            name="/api/v1/drift-events/?min_severity=[n]",
        )

    @task(2)
    def get_drift_event_detail(self):
        """
        GET /api/v1/drift-events/{id}/

        Tests retrieving individual drift events.
        """
        event_id = random.randint(1, 50)
        self.get_with_auth(
            f"/api/v1/drift-events/{event_id}/",
            allow_not_found=True,
            name="/api/v1/drift-events/[id]/",
        )


class UploadsUser(AuthenticatedUser):
    """
    Load test user for uploads operations.

    Tests the uploads list and detail views.
    """

    wait_time = between(1, 3)

    @task(4)
    def list_uploads(self):
        """
        GET /api/v1/uploads/ with pagination.

        Tests the paginated uploads list.
        """
        page = random.randint(1, 5)
        page_size = random.choice([25, 50])

        self.get_with_auth(
            f"/api/v1/uploads/?page={page}&page_size={page_size}",
            name="/api/v1/uploads/?page=[n]&page_size=[n]",
        )

    @task(2)
    def filter_uploads_by_status(self):
        """
        GET /api/v1/uploads/?status=X

        Tests filtering by upload status.
        """
        status = random.choice(["pending", "processing", "success", "failed"])
        self.get_with_auth(
            f"/api/v1/uploads/?status={status}",
            name="/api/v1/uploads/?status=[status]",
        )

    @task(1)
    def get_upload_detail(self):
        """
        GET /api/v1/uploads/{id}/

        Tests retrieving individual upload records.
        """
        upload_id = random.randint(1, 50)
        self.get_with_auth(
            f"/api/v1/uploads/{upload_id}/",
            allow_not_found=True,
            name="/api/v1/uploads/[id]/",
        )


class ReportsUser(AuthenticatedUser):
    """
    Load test user for reports operations.

    Tests the reports list and detail views.
    """

    wait_time = between(2, 4)  # Reports are typically accessed less frequently

    @task(3)
    def list_reports(self):
        """
        GET /api/v1/reports/ with pagination.

        Tests the paginated reports list.
        """
        page = random.randint(1, 3)
        page_size = random.choice([25, 50])

        self.get_with_auth(
            f"/api/v1/reports/?page={page}&page_size={page_size}",
            name="/api/v1/reports/?page=[n]&page_size=[n]",
        )

    @task(1)
    def get_report_detail(self):
        """
        GET /api/v1/reports/{id}/

        Tests retrieving individual report records.
        """
        report_id = random.randint(1, 20)
        self.get_with_auth(
            f"/api/v1/reports/{report_id}/",
            allow_not_found=True,
            name="/api/v1/reports/[id]/",
        )


class DashboardUser(AuthenticatedUser):
    """
    Load test user for dashboard operations.

    Tests the dashboard summary endpoint which aggregates data.
    """

    wait_time = between(2, 4)

    @task
    def get_dashboard(self):
        """
        GET /api/v1/dashboard/

        Tests the dashboard summary endpoint.
        This aggregates multiple data sources.
        """
        self.get_with_auth(
            "/api/v1/dashboard/",
            name="/api/v1/dashboard/",
        )


class HealthCheckUser(AuthenticatedUser):
    """
    Load test user for health check operations.

    Tests the health check endpoint (no auth required).
    """

    wait_time = between(1, 2)

    @task
    def health_check(self):
        """
        GET /api/v1/health/

        Tests the health check endpoint.
        """
        with self.client.get(
            "/api/v1/health/",
            catch_response=True,
            name="/api/v1/health/",
        ) as response:
            self.validate_response(response, 200)


class CombinedAPIUser(AuthenticatedUser):
    """
    Combined load test user simulating realistic API usage.

    Tests multiple endpoints in a realistic usage pattern.
    """

    wait_time = between(1, 3)

    @task(4)
    def browse_claims(self):
        """Browse claims list."""
        page = random.randint(1, 5)
        self.get_with_auth(
            f"/api/v1/claims/?page={page}&page_size=50",
            name="/api/v1/claims/?page=[n] (combined)",
        )

    @task(3)
    def browse_alerts(self):
        """Browse alerts list."""
        self.get_with_auth(
            "/api/v1/alerts/?status=open&page_size=50",
            name="/api/v1/alerts/?status=open (combined)",
        )

    @task(2)
    def check_drift(self):
        """Check drift events."""
        self.get_with_auth(
            "/api/v1/drift-events/?min_severity=0.5&page_size=25",
            name="/api/v1/drift-events/?min_severity=0.5 (combined)",
        )

    @task(2)
    def view_dashboard(self):
        """View dashboard summary."""
        self.get_with_auth(
            "/api/v1/dashboard/",
            name="/api/v1/dashboard/ (combined)",
        )

    @task(1)
    def check_uploads(self):
        """Check upload status."""
        self.get_with_auth(
            "/api/v1/uploads/?page_size=25",
            name="/api/v1/uploads/ (combined)",
        )

    @task(1)
    def view_reports(self):
        """View reports."""
        self.get_with_auth(
            "/api/v1/reports/?page_size=25",
            name="/api/v1/reports/ (combined)",
        )


# Event listeners for API-specific metrics
@events.test_start.add_listener
def on_api_test_start(environment, **kwargs):
    """Log API test configuration."""
    logger.info("=" * 60)
    logger.info("Combined API Load Test Starting")
    logger.info(f"List threshold: {config.p95_list_threshold_ms}ms")
    logger.info(f"Detail threshold: {config.p95_detail_threshold_ms}ms")
    logger.info("=" * 60)


@events.test_stop.add_listener
def on_api_test_stop(environment, **kwargs):
    """Log API test summary."""
    logger.info("=" * 60)
    logger.info("Combined API Load Test Completed")

    stats = environment.stats
    endpoints = [
        "/api/v1/drift-events/?page=[n]&page_size=[n]",
        "/api/v1/uploads/?page=[n]&page_size=[n]",
        "/api/v1/reports/?page=[n]&page_size=[n]",
        "/api/v1/dashboard/",
        "/api/v1/health/",
    ]

    for name in endpoints:
        entry = stats.entries.get((name, "GET"))
        if entry and entry.num_requests > 0:
            p95 = entry.get_response_time_percentile(0.95)
            logger.info(
                f"{name}: {entry.num_requests} requests, "
                f"avg {entry.avg_response_time:.0f}ms, "
                f"p95 {p95:.0f}ms, "
                f"failures {entry.num_failures}"
            )

    logger.info("=" * 60)
