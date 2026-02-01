"""
Locust load testing configuration for Upstream API.

This is the main entry point for running Locust load tests.
Uses base classes from upstream.tests_performance_base for
authentication and response validation.

Usage:
    # Run with web UI
    locust --host=http://localhost:8000

    # Run headless (CI mode)
    locust --headless -u 10 -r 2 -t 60s --host=http://localhost:8000

Then open http://localhost:8089 to configure and start the test.

Environment Variables:
    LOCUST_HOST: Target host URL (default: http://localhost:8000)
    LOCUST_USERNAME: Default test user (default: user_a)
    LOCUST_PASSWORD: Default test password
    P95_LIST_THRESHOLD_MS: P95 threshold for list endpoints (default: 500)
    P95_DETAIL_THRESHOLD_MS: P95 threshold for detail endpoints (default: 200)
    MAX_ERROR_RATE: Maximum acceptable error rate (default: 0.01)
"""

from locust import task, between
import random

from upstream.tests_performance_base import (
    AuthenticatedUser,
    AdminUser,
    UnauthenticatedUser,
)


class UpstreamAPIUser(AuthenticatedUser):
    """
    Simulates an Upstream API user making requests to various endpoints.

    This user represents the most common usage pattern:
    - Browsing lists of resources
    - Viewing details
    - Filtering and searching
    - Accessing dashboard and summaries
    """

    wait_time = between(1, 3)  # Wait 1-3 seconds between requests

    @task(3)
    def get_health(self):
        """Health check endpoint (highest frequency)."""
        # Health endpoint doesn't require auth
        with self.client.get("/api/v1/health/", catch_response=True) as response:
            self.validate_response(response, 200)

    @task(2)
    def get_dashboard(self):
        """Dashboard endpoint."""
        self.get_with_auth("/api/v1/dashboard/")

    @task(2)
    def get_drift_feed(self):
        """Drift feed endpoint with pagination."""
        page = random.randint(1, 5)
        self.get_with_auth(
            f"/api/v1/drift-events/?page={page}",
            name="/api/v1/drift-events/?page=[n]",
        )

    @task(1)
    def get_payer_summary(self):
        """Payer summary endpoint."""
        self.get_with_auth("/api/v1/claims/payer_summary/")

    @task(1)
    def get_claims(self):
        """Claim records endpoint with pagination."""
        page = random.randint(1, 10)
        self.get_with_auth(
            f"/api/v1/claims/?page={page}&page_size=25",
            name="/api/v1/claims/?page=[n]",
        )

    @task(1)
    def get_claim_detail(self):
        """Get specific claim record (allows 404 for missing IDs)."""
        claim_id = random.randint(1, 10)
        self.get_with_auth(
            f"/api/v1/claims/{claim_id}/",
            allow_not_found=True,
            name="/api/v1/claims/[id]/",
        )


class UpstreamAdminUser(AdminUser):
    """
    Simulates an admin user performing administrative tasks.

    Admin users have slower pacing and access additional endpoints.
    """

    wait_time = between(2, 5)

    @task(2)
    def get_customers(self):
        """List customers (admin only)."""
        self.get_with_auth("/api/v1/customers/")

    @task(1)
    def get_reports(self):
        """List report runs."""
        self.get_with_auth("/api/v1/reports/")

    @task(1)
    def get_uploads(self):
        """List file uploads."""
        self.get_with_auth("/api/v1/uploads/")


class UpstreamUnauthenticatedUser(UnauthenticatedUser):
    """
    Simulates unauthenticated users.

    Tests that protected endpoints properly require authentication
    and that public endpoints work without auth.
    """

    wait_time = between(1, 2)

    @task(2)
    def health_check_unauth(self):
        """Health check should work without auth."""
        with self.client.get("/api/v1/health/", catch_response=True) as response:
            self.validate_response(response, 200)

    @task(1)
    def try_dashboard_unauth(self):
        """Try to access dashboard without auth (should fail)."""
        with self.client.get("/api/v1/dashboard/", catch_response=True) as response:
            self.validate_auth_required(response)

    @task(1)
    def try_drift_feed_unauth(self):
        """Try to access drift feed without auth (should fail)."""
        with self.client.get("/api/v1/drift-events/", catch_response=True) as response:
            self.validate_auth_required(response)

    @task(1)
    def try_claims_unauth(self):
        """Try to access claims without auth (should fail)."""
        with self.client.get("/api/v1/claims/", catch_response=True) as response:
            self.validate_auth_required(response)
