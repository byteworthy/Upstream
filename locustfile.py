"""
Locust load testing configuration for Upstream API.

Usage:
    locust --host=http://localhost:8000

Then open http://localhost:8089 to configure and start the test.
"""

from locust import HttpUser, task, between
import random


class UpstreamAPIUser(HttpUser):
    """
    Simulates an Upstream API user making requests to various endpoints.
    """

    wait_time = between(1, 3)  # Wait 1-3 seconds between requests

    def on_start(self):
        """Login and get JWT token before starting tasks."""
        # Attempt to login (adjust credentials as needed)
        response = self.client.post(
            "/api/v1/auth/token/",
            json={"username": "testuser", "password": "testpass123"},
            catch_response=True,
        )

        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            # If login fails, set empty headers (will test auth failures)
            self.headers = {}

    @task(3)
    def get_health(self):
        """Health check endpoint (highest frequency)."""
        self.client.get("/api/v1/health/", headers=self.headers)

    @task(2)
    def get_dashboard(self):
        """Dashboard endpoint."""
        self.client.get("/api/v1/dashboard/", headers=self.headers)

    @task(2)
    def get_drift_feed(self):
        """Drift feed endpoint with pagination."""
        page = random.randint(1, 5)
        self.client.get(f"/api/v1/drift-events/?page={page}", headers=self.headers)

    @task(1)
    def get_payer_summary(self):
        """Payer summary endpoint."""
        self.client.get("/api/v1/payer-summary/", headers=self.headers)

    @task(1)
    def get_denial_trend(self):
        """Denial rate trend endpoint."""
        self.client.get("/api/v1/denial-rate-trend/", headers=self.headers)

    @task(1)
    def get_claims(self):
        """Claim records endpoint with pagination."""
        page = random.randint(1, 10)
        self.client.get(f"/api/v1/claims/?page={page}", headers=self.headers)


class AdminUser(HttpUser):
    """
    Simulates an admin user performing administrative tasks.
    """

    wait_time = between(2, 5)

    def on_start(self):
        """Login as admin."""
        response = self.client.post(
            "/api/v1/auth/token/",
            json={"username": "admin", "password": "admin123"},
            catch_response=True,
        )

        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            self.headers = {}

    @task(2)
    def get_customers(self):
        """List customers."""
        self.client.get("/api/v1/customers/", headers=self.headers)

    @task(1)
    def get_report_runs(self):
        """List report runs."""
        self.client.get("/api/v1/report-runs/", headers=self.headers)


class UnauthenticatedUser(HttpUser):
    """
    Simulates unauthenticated users (should get 401/403 responses).
    """

    wait_time = between(1, 2)

    @task
    def try_dashboard_unauth(self):
        """Try to access dashboard without auth."""
        with self.client.get("/api/v1/dashboard/", catch_response=True) as response:
            if response.status_code in [401, 403]:
                response.success()

    @task
    def try_drift_feed_unauth(self):
        """Try to access drift feed without auth."""
        with self.client.get("/api/v1/drift-events/", catch_response=True) as response:
            if response.status_code in [401, 403]:
                response.success()
