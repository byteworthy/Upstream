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
            json={
                "username": "user_a",
                "password": "testpass123",
            },  # pragma: allowlist secret
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


# Django Query Count Tests for N+1 Optimization (Phase 07)

from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from upstream.models import (
    Customer,
    UserProfile,
    Upload,
    ClaimRecord,
    DriftEvent,
    ReportRun,
)
from upstream.test_fixtures import TenantTestMixin
from datetime import date, timedelta
from django.db import connection
from django.test.utils import override_settings
from decimal import Decimal


class QueryOptimizationTests(TenantTestMixin, TestCase):
    """
    Test suite verifying N+1 query optimizations (Story #5 - Phase 07).

    Performance thresholds:
    - Upload list: 3-4 queries (main + count + JOINs for customer/uploaded_by)
    - ClaimRecord list: <10 queries for 50 claims
    - Drift computation: <15 queries for 100 claims
    """

    def setUp(self):
        """Create test customer and user."""
        super().setUp()
        self.customer = self.create_customer("Test Hospital")
        self.user = self.create_user(self.customer, username="testuser")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_upload_list_query_optimization(self):
        """
        Story #3: Verify Upload list view uses select_related for customer/uploaded_by.

        Expected: ~3-4 queries
        - Main query with JOINs
        - Count query for pagination
        """
        # Create 25 uploads with uploaded_by
        for i in range(25):
            Upload.objects.create(
                customer=self.customer,
                filename=f"upload_{i}.csv",
                status="success",
                row_count=100,
                uploaded_by=self.user,
            )

        # Query uploads through API
        with override_settings(DEBUG=True):
            from django.db import reset_queries

            reset_queries()

            response = self.client.get("/api/v1/uploads/")
            self.assertEqual(response.status_code, 200)

            query_count = len(connection.queries)

            # Should be ~3-4 queries total (main + count + maybe permissions check)
            self.assertLessEqual(
                query_count,
                6,
                f"Upload list used {query_count} queries, expected <=6. "
                f"Queries: {[q['sql'][:100] for q in connection.queries]}",
            )

    def test_claimrecord_list_query_optimization(self):
        """
        Story #4: Verify ClaimRecord list view prefetches drift_events.

        Expected: <10 queries for 50 claims
        """
        upload = self.create_upload(self.customer, uploaded_by=self.user)

        # Create 50 claim records using bulk_create for speed
        claims = []
        for i in range(50):
            claims.append(
                ClaimRecord(
                    customer=self.customer,
                    upload=upload,
                    payer=f"Payer{i % 10}",
                    cpt="99213",
                    cpt_group="OFFICE",
                    outcome="PAID" if i % 2 == 0 else "DENIED",
                    submitted_date=date.today() - timedelta(days=i),
                    decided_date=date.today() - timedelta(days=i - 7),
                    allowed_amount=Decimal("150.00") if i % 2 == 0 else Decimal("0.00"),
                )
            )
        ClaimRecord.objects.bulk_create(claims)

        # Query claims through API
        with override_settings(DEBUG=True):
            from django.db import reset_queries

            reset_queries()

            response = self.client.get("/api/v1/claims/?page_size=50")
            self.assertEqual(response.status_code, 200)

            query_count = len(connection.queries)

            # Should be <10 queries
            self.assertLess(
                query_count,
                10,
                f"ClaimRecord list used {query_count} queries, expected <10",
            )

    def test_drift_computation_query_efficiency(self):
        """
        Story #1: Verify drift computation is efficient with .values() optimization.

        Expected: <15 queries for 100 claims
        """
        from upstream.services.payer_drift import compute_weekly_payer_drift

        upload = self.create_upload(self.customer, uploaded_by=self.user)

        # Create 100 claims spanning baseline and current windows
        claims = []
        today = date.today()
        for i in range(100):
            days_ago = 104 - i
            claims.append(
                ClaimRecord(
                    customer=self.customer,
                    upload=upload,
                    payer=f"Payer{i % 5}",
                    cpt="99213",
                    cpt_group=f"Group{i % 3}",
                    outcome="PAID" if i % 3 == 0 else "DENIED",
                    submitted_date=today - timedelta(days=days_ago),
                    decided_date=today - timedelta(days=days_ago - 5),
                    allowed_amount=Decimal("150.00") if i % 3 == 0 else Decimal("0.00"),
                )
            )
        ClaimRecord.objects.bulk_create(claims)

        # Run drift computation and count queries
        with override_settings(DEBUG=True):
            from django.db import reset_queries

            reset_queries()

            report_run = compute_weekly_payer_drift(
                customer=self.customer, as_of_date=today
            )

            query_count = len(connection.queries)

            # Current .values() implementation is efficient
            self.assertLess(
                query_count,
                15,
                f"Drift computation used {query_count} queries, expected <15",
            )
            self.assertEqual(report_run.status, "success")

    def test_upload_retrieve_with_select_related(self):
        """
        Verify that single upload retrieval also uses select_related.
        """
        upload = Upload.objects.create(
            customer=self.customer,
            filename="test.csv",
            status="success",
            row_count=100,
            uploaded_by=self.user,
        )

        with override_settings(DEBUG=True):
            from django.db import reset_queries

            reset_queries()

            response = self.client.get(f"/api/v1/uploads/{upload.id}/")
            self.assertEqual(response.status_code, 200)

            query_count = len(connection.queries)

            # Should be minimal queries (main query with JOIN + maybe permissions)
            self.assertLessEqual(
                query_count,
                5,
                f"Upload retrieve used {query_count} queries, expected <=5",
            )
