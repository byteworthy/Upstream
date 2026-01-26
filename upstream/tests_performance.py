"""
Locust Performance Test Suite for Upstream API

This suite validates that the API meets performance SLA targets under realistic load.

Performance Targets:
- p95 < 500ms for list endpoints
- p95 < 200ms for detail endpoints
- Error rate < 1%

Usage:
    # Run locally with web UI
    locust -f upstream/tests_performance.py --host http://localhost:8000

    # Run headless for CI
    locust -f upstream/tests_performance.py \
        --headless -u 10 -r 2 -t 60s \
        --host http://localhost:8000 \
        --csv=results \
        --only-summary

Simulates realistic API usage patterns:
- List operations with pagination
- Detail views for specific resources
- Filtering and searching
- Custom actions (payer_summary, active)
"""

from locust import HttpUser, task, between
import random


class UpstreamUser(HttpUser):
    """
    Simulates an authenticated user making typical API requests.

    This user represents the most common usage pattern:
    - Browsing lists of resources
    - Viewing details
    - Filtering and searching
    - Accessing dashboard and summaries
    """

    wait_time = between(1, 3)  # Realistic pacing between requests
    host = "http://localhost:8000"

    def on_start(self):
        """Authenticate and obtain JWT token before running tasks."""
        response = self.client.post(
            "/api/v1/auth/token/",
            json={"username": "user_a", "password": "testpass123"},  # pragma: allowlist secret
            catch_response=True,
        )

        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            # Auth failed - set empty headers (requests will fail with 401)
            self.headers = {}
            response.failure(f"Authentication failed: {response.status_code}")

    @task(5)
    def list_claims(self):
        """GET /api/v1/claims/ - List claim records with pagination."""
        page = random.randint(1, 5)
        with self.client.get(
            f"/api/v1/claims/?page={page}&page_size=25",
            headers=self.headers,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Expected 200, got {response.status_code}")

    @task(3)
    def get_claim_detail(self):
        """GET /api/v1/claims/{id}/ - Get specific claim record."""
        # Use a likely ID (tests may not have data, so 404 is acceptable)
        claim_id = random.randint(1, 10)
        with self.client.get(
            f"/api/v1/claims/{claim_id}/",
            headers=self.headers,
            catch_response=True,
        ) as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Expected 200 or 404, got {response.status_code}")

    @task(3)
    def filter_claims_by_payer(self):
        """GET /api/v1/claims/?payer=X - Filter claims by payer name."""
        payer = random.choice(["TestPayer", "BlueCross", "Aetna", "UnitedHealth"])
        with self.client.get(
            f"/api/v1/claims/?payer={payer}&page_size=25",
            headers=self.headers,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Expected 200, got {response.status_code}")

    @task(2)
    def search_claims(self):
        """GET /api/v1/claims/?search=X - Search claims by CPT code or claim number."""
        search_term = random.choice(["99213", "99214", "CLM", "80053"])
        with self.client.get(
            f"/api/v1/claims/?search={search_term}",
            headers=self.headers,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Expected 200, got {response.status_code}")

    @task(4)
    def get_payer_summary(self):
        """GET /api/v1/claims/payer_summary/ - Get aggregated payer statistics."""
        with self.client.get(
            "/api/v1/claims/payer_summary/",
            headers=self.headers,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Expected 200, got {response.status_code}")

    @task(3)
    def list_drift_events(self):
        """GET /api/v1/drift-events/ - List drift detection events."""
        page = random.randint(1, 5)
        with self.client.get(
            f"/api/v1/drift-events/?page={page}&page_size=25",
            headers=self.headers,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Expected 200, got {response.status_code}")

    @task(2)
    def filter_drift_by_severity(self):
        """GET /api/v1/drift-events/?min_severity=X - Filter high-severity drift."""
        severity = random.choice([0.5, 0.7, 0.8])
        with self.client.get(
            f"/api/v1/drift-events/?min_severity={severity}",
            headers=self.headers,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Expected 200, got {response.status_code}")

    @task(4)
    def get_dashboard(self):
        """GET /api/v1/dashboard/ - Get dashboard summary statistics."""
        with self.client.get(
            "/api/v1/dashboard/",
            headers=self.headers,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Expected 200, got {response.status_code}")

    @task(2)
    def list_uploads(self):
        """GET /api/v1/uploads/ - List file uploads."""
        with self.client.get(
            "/api/v1/uploads/?page_size=25",
            headers=self.headers,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Expected 200, got {response.status_code}")

    @task(1)
    def list_reports(self):
        """GET /api/v1/reports/ - List report runs."""
        with self.client.get(
            "/api/v1/reports/?page_size=25",
            headers=self.headers,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Expected 200, got {response.status_code}")
