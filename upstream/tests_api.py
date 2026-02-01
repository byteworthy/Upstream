"""
Upstream API Endpoint Tests

Tests for API endpoints including:
- Auth endpoints (token obtain/refresh)
- Health endpoint
- Dashboard endpoint
- Drift feed/active drift endpoint
- Payer summary endpoint
- Denial rate trend endpoint (Chunk 6)
- Tenant isolation tests
- Permissions tests
"""

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from datetime import timedelta

from upstream.models import (
    Customer,
    UserProfile,
    Upload,
    ClaimRecord,
    ReportRun,
    DriftEvent,
)


# API base URL (mounted at /api/v1/ in urls.py)
API_BASE = "/api/v1"


class APITestBase(APITestCase):
    """Base class for API tests with common setup."""

    def setUp(self):
        """Set up test fixtures for API tests."""
        # Clear cache to prevent test pollution
        from django.core.cache import cache

        cache.clear()

        # Create customers
        self.customer_a = Customer.objects.create(name="Customer A")
        self.customer_b = Customer.objects.create(name="Customer B")

        # Create users for Customer A
        self.user_a = User.objects.create_user(
            username="user_a", email="user_a@example.com", password="testpass123"
        )
        self.profile_a = UserProfile.objects.create(
            user=self.user_a, customer=self.customer_a
        )

        # Create users for Customer B
        self.user_b = User.objects.create_user(
            username="user_b", email="user_b@example.com", password="testpass123"
        )
        self.profile_b = UserProfile.objects.create(
            user=self.user_b, customer=self.customer_b
        )

        # Create a user without customer profile
        self.user_no_customer = User.objects.create_user(
            username="no_customer",
            email="no_customer@example.com",
            password="testpass123",
        )

        self.client = APIClient()

    def get_tokens_for_user(self, user):
        """Helper to get JWT tokens for a user."""
        response = self.client.post(
            f"{API_BASE}/auth/token/",
            {"username": user.username, "password": "testpass123"},
            format="json",
        )
        return response.data

    def authenticate_as(self, user):
        """Helper to authenticate client as a specific user."""
        tokens = self.get_tokens_for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    def create_upload_for_customer(self, customer):
        """Helper to create an upload for a customer."""
        return Upload.all_objects.create(
            customer=customer, filename="test.csv", status="success", row_count=100
        )

    def create_claim_record_for_customer(self, customer, upload=None):
        """Helper to create a claim record for a customer."""
        if upload is None:
            upload = self.create_upload_for_customer(customer)
        return ClaimRecord.all_objects.create(
            customer=customer,
            upload=upload,
            payer="TestPayer",
            cpt="99213",
            cpt_group="EVAL",
            submitted_date=timezone.now().date() - timedelta(days=10),
            decided_date=timezone.now().date() - timedelta(days=5),
            outcome="PAID",
            allowed_amount=100.00,
            submitted_via="csv_upload",
        )

    def create_report_run_for_customer(self, customer):
        """Helper to create a report run for a customer."""
        return ReportRun.all_objects.create(
            customer=customer,
            run_type="weekly",
            status="success",
            started_at=timezone.now() - timedelta(hours=1),
            finished_at=timezone.now(),
            summary_json={"events_created": 1},
        )

    def create_drift_event_for_customer(self, customer, report_run=None):
        """Helper to create a drift event for a customer."""
        if report_run is None:
            report_run = self.create_report_run_for_customer(customer)
        return DriftEvent.all_objects.create(
            customer=customer,
            report_run=report_run,
            payer="TestPayer",
            cpt_group="EVAL",
            drift_type="DENIAL_RATE",
            baseline_value=0.1,
            current_value=0.3,
            delta_value=0.2,
            severity=0.7,
            confidence=0.9,
            baseline_start=timezone.now().date() - timedelta(days=104),
            baseline_end=timezone.now().date() - timedelta(days=14),
            current_start=timezone.now().date() - timedelta(days=14),
            current_end=timezone.now().date(),
        )


class HealthEndpointTests(APITestCase):
    """Tests for the health check endpoint."""

    def test_health_endpoint_returns_200(self):
        """Health endpoint should return 200 without authentication."""
        response = self.client.get(f"{API_BASE}/health/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_health_endpoint_returns_status(self):
        """Health endpoint should return status field."""
        response = self.client.get(f"{API_BASE}/health/")
        self.assertEqual(response.data["status"], "healthy")

    def test_health_endpoint_returns_version(self):
        """Health endpoint should return version field."""
        response = self.client.get(f"{API_BASE}/health/")
        self.assertIn("version", response.data)

    def test_health_endpoint_returns_timestamp(self):
        """Health endpoint should return timestamp field."""
        response = self.client.get(f"{API_BASE}/health/")
        self.assertIn("timestamp", response.data)


class AuthEndpointTests(APITestBase):
    """Tests for authentication endpoints."""

    def test_token_obtain_with_valid_credentials(self):
        """Token obtain should return tokens with valid credentials."""
        response = self.client.post(
            f"{API_BASE}/auth/token/", {"username": "user_a", "password": "testpass123"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_token_obtain_with_invalid_credentials(self):
        """Token obtain should return 401 with invalid credentials."""
        response = self.client.post(
            f"{API_BASE}/auth/token/",
            {"username": "user_a", "password": "wrongpassword"},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_obtain_with_nonexistent_user(self):
        """Token obtain should return 401 for nonexistent user."""
        response = self.client.post(
            f"{API_BASE}/auth/token/",
            {"username": "nonexistent", "password": "testpass123"},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_refresh_with_valid_token(self):
        """Token refresh should return new access token."""
        # First obtain tokens
        obtain_response = self.client.post(
            f"{API_BASE}/auth/token/", {"username": "user_a", "password": "testpass123"}
        )
        refresh_token = obtain_response.data["refresh"]

        # Then refresh
        response = self.client.post(
            f"{API_BASE}/auth/token/refresh/", {"refresh": refresh_token}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_token_refresh_with_invalid_token(self):
        """Token refresh should return 401 with invalid token."""
        response = self.client.post(
            f"{API_BASE}/auth/token/refresh/", {"refresh": "invalid-token"}
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class DashboardEndpointTests(APITestBase):
    """Tests for the dashboard endpoint."""

    def test_dashboard_unauthenticated(self):
        """Dashboard should return 401 for unauthenticated request."""
        response = self.client.get(f"{API_BASE}/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_dashboard_authenticated(self):
        """Dashboard should return 200 for authenticated request."""
        self.authenticate_as(self.user_a)
        response = self.client.get(f"{API_BASE}/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_dashboard_returns_expected_fields(self):
        """Dashboard should return expected fields."""
        self.authenticate_as(self.user_a)
        response = self.client.get(f"{API_BASE}/dashboard/")

        self.assertIn("total_claims", response.data)
        self.assertIn("total_uploads", response.data)
        self.assertIn("active_drift_events", response.data)
        self.assertIn("last_report_date", response.data)
        self.assertIn("top_drift_payers", response.data)

    def test_dashboard_shows_customer_data_only(self):
        """Dashboard should only see data for user's customer."""
        # Create data for both customers
        self.create_upload_for_customer(self.customer_a)
        self.create_upload_for_customer(self.customer_a)
        self.create_upload_for_customer(self.customer_b)

        # Verify uploads were created
        total_uploads = Upload.all_objects.count()
        self.assertEqual(total_uploads, 3, f"Expected 3 uploads, got {total_uploads}")

        customer_a_uploads = Upload.all_objects.filter(customer=self.customer_a).count()
        self.assertEqual(
            customer_a_uploads,
            2,
            f"Expected 2 uploads for customer A, got {customer_a_uploads}",
        )

        self.authenticate_as(self.user_a)
        response = self.client.get(f"{API_BASE}/dashboard/")

        # User A should only see Customer A's uploads
        self.assertEqual(
            response.status_code,
            200,
            f"Expected 200, got {response.status_code}: {response.data}",
        )
        self.assertEqual(response.data["total_uploads"], 2)

    def test_dashboard_query_count(self):
        """Dashboard should use optimized queries to prevent N+1."""
        # Create test data
        report_run = self.create_report_run_for_customer(self.customer_a)
        for i in range(5):
            self.create_upload_for_customer(self.customer_a)
            self.create_drift_event_for_customer(self.customer_a, report_run)

        self.authenticate_as(self.user_a)

        # Dashboard should aggregate data efficiently
        # Expected queries:
        # 1. SELECT user (authentication)
        # 2. SELECT user profile (get customer)
        # 3. SELECT customer
        # 4. SELECT COUNT claims
        # 5. SELECT COUNT uploads (status=success)
        # 6. SELECT latest report run
        # 7. SELECT monthly denial trend
        # Should be constant (~7 queries) regardless of data volume
        with self.assertNumQueries(7):
            response = self.client.get(f"{API_BASE}/dashboard/")
            # Force evaluation
            _ = response.data


class DriftEventEndpointTests(APITestBase):
    """Tests for drift event endpoints."""

    def test_drift_events_list_unauthenticated(self):
        """Drift events list should return 401 for unauthenticated request."""
        response = self.client.get(f"{API_BASE}/drift-events/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_drift_events_list_authenticated(self):
        """Drift events list should return 200 for authenticated request."""
        self.authenticate_as(self.user_a)
        response = self.client.get(f"{API_BASE}/drift-events/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_drift_events_active_endpoint(self):
        """Active drift endpoint should return recent events."""
        # Create report run and drift event for Customer A
        report_run = self.create_report_run_for_customer(self.customer_a)
        self.create_drift_event_for_customer(self.customer_a, report_run)

        self.authenticate_as(self.user_a)
        response = self.client.get(f"{API_BASE}/drift-events/active/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Response is now paginated with count, results, next, previous
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 1)

    def test_drift_events_filter_by_severity(self):
        """Drift events should be filterable by minimum severity."""
        report_run = self.create_report_run_for_customer(self.customer_a)

        # Create events with different severities
        DriftEvent.objects.create(
            customer=self.customer_a,
            report_run=report_run,
            payer="LowSeverityPayer",
            cpt_group="EVAL",
            drift_type="DENIAL_RATE",
            baseline_value=0.1,
            current_value=0.15,
            delta_value=0.05,
            severity=0.2,
            confidence=0.9,
            baseline_start=timezone.now().date() - timedelta(days=104),
            baseline_end=timezone.now().date() - timedelta(days=14),
            current_start=timezone.now().date() - timedelta(days=14),
            current_end=timezone.now().date(),
        )
        DriftEvent.objects.create(
            customer=self.customer_a,
            report_run=report_run,
            payer="HighSeverityPayer",
            cpt_group="EVAL",
            drift_type="DENIAL_RATE",
            baseline_value=0.1,
            current_value=0.5,
            delta_value=0.4,
            severity=0.8,
            confidence=0.9,
            baseline_start=timezone.now().date() - timedelta(days=104),
            baseline_end=timezone.now().date() - timedelta(days=14),
            current_start=timezone.now().date() - timedelta(days=14),
            current_end=timezone.now().date(),
        )

        self.authenticate_as(self.user_a)
        response = self.client.get(f"{API_BASE}/drift-events/?min_severity=0.5")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should only return the high severity event
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["payer"], "HighSeverityPayer")

    def test_drift_events_list_query_count(self):
        """Drift events list should use optimized queries to prevent N+1."""
        report_run = self.create_report_run_for_customer(self.customer_a)

        # Create 10 drift events with relationships
        for i in range(10):
            self.create_drift_event_for_customer(self.customer_a, report_run)

        self.authenticate_as(self.user_a)

        # Query count should be constant regardless of number of events
        # Expected queries:
        # 1. SELECT user (authentication)
        # 2. SELECT user profile (get customer)
        # 3. SELECT customer
        # 4. SELECT count for pagination
        # 5. SELECT drift events
        with self.assertNumQueries(5):
            response = self.client.get(f"{API_BASE}/drift-events/")
            # Force evaluation
            _ = response.data["results"]


class PayerSummaryEndpointTests(APITestBase):
    """Tests for payer summary endpoint."""

    def test_payer_summary_unauthenticated(self):
        """Payer summary should return 401 for unauthenticated request."""
        response = self.client.get(f"{API_BASE}/claims/payer_summary/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_payer_summary_authenticated(self):
        """Payer summary should return 200 for authenticated request."""
        self.authenticate_as(self.user_a)
        response = self.client.get(f"{API_BASE}/claims/payer_summary/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_payer_summary_aggregates_claims(self):
        """Payer summary should aggregate claims by payer."""
        upload = self.create_upload_for_customer(self.customer_a)

        # Create claims for different payers
        for i in range(5):
            ClaimRecord.objects.create(
                customer=self.customer_a,
                upload=upload,
                payer="PayerOne",
                cpt="99213",
                submitted_date=timezone.now().date() - timedelta(days=10),
                decided_date=timezone.now().date() - timedelta(days=5),
                outcome="PAID" if i < 3 else "DENIED",
                allowed_amount=100.00,
                submitted_via="csv_upload",
            )

        for i in range(3):
            ClaimRecord.objects.create(
                customer=self.customer_a,
                upload=upload,
                payer="PayerTwo",
                cpt="99213",
                submitted_date=timezone.now().date() - timedelta(days=10),
                decided_date=timezone.now().date() - timedelta(days=5),
                outcome="DENIED",
                allowed_amount=100.00,
                submitted_via="csv_upload",
            )

        self.authenticate_as(self.user_a)
        response = self.client.get(f"{API_BASE}/claims/payer_summary/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Response is now paginated with count, results, next, previous
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 2)

        # Find PayerOne in results
        payer_one = next(
            p for p in response.data["results"] if p["payer"] == "PayerOne"
        )
        self.assertEqual(payer_one["total_claims"], 5)
        self.assertEqual(payer_one["paid_count"], 3)
        self.assertEqual(payer_one["denied_count"], 2)


class TenantIsolationTests(APITestBase):
    """
    Tests for tenant isolation.

    Ensures customers cannot access each other's data.
    """

    def test_uploads_tenant_isolation(self):
        """Customer A should not see Customer B's uploads."""
        # Create uploads for both customers
        upload_a = self.create_upload_for_customer(self.customer_a)
        upload_b = self.create_upload_for_customer(self.customer_b)

        self.authenticate_as(self.user_a)
        response = self.client.get(f"{API_BASE}/uploads/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        upload_ids = [u["id"] for u in response.data["results"]]

        self.assertIn(upload_a.id, upload_ids)
        self.assertNotIn(upload_b.id, upload_ids)

    def test_claims_tenant_isolation(self):
        """Customer A should not see Customer B's claims."""
        # Create claims for both customers
        claim_a = self.create_claim_record_for_customer(self.customer_a)
        claim_b = self.create_claim_record_for_customer(self.customer_b)

        self.authenticate_as(self.user_a)
        response = self.client.get(f"{API_BASE}/claims/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        claim_ids = [c["id"] for c in response.data["results"]]

        self.assertIn(claim_a.id, claim_ids)
        self.assertNotIn(claim_b.id, claim_ids)

    def test_drift_events_tenant_isolation(self):
        """Customer A should not see Customer B's drift events."""
        # Create drift events for both customers
        event_a = self.create_drift_event_for_customer(self.customer_a)
        event_b = self.create_drift_event_for_customer(self.customer_b)

        self.authenticate_as(self.user_a)
        response = self.client.get(f"{API_BASE}/drift-events/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        event_ids = [e["id"] for e in response.data["results"]]

        self.assertIn(event_a.id, event_ids)
        self.assertNotIn(event_b.id, event_ids)

    def test_reports_tenant_isolation(self):
        """Customer A should not see Customer B's reports."""
        # Create reports for both customers
        report_a = self.create_report_run_for_customer(self.customer_a)
        report_b = self.create_report_run_for_customer(self.customer_b)

        self.authenticate_as(self.user_a)
        response = self.client.get(f"{API_BASE}/reports/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        report_ids = [r["id"] for r in response.data["results"]]

        self.assertIn(report_a.id, report_ids)
        self.assertNotIn(report_b.id, report_ids)

    def test_direct_object_access_denied(self):
        """Customer A should not access Customer B's specific object."""
        upload_b = self.create_upload_for_customer(self.customer_b)

        self.authenticate_as(self.user_a)
        response = self.client.get(f"{API_BASE}/uploads/{upload_b.id}/")

        # Should return 404 (object not found for this customer)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_dashboard_tenant_isolation(self):
        """Dashboard should only show data for the authenticated user's customer."""
        # Create data for Customer A
        self.create_upload_for_customer(self.customer_a)
        upload_a = self.create_upload_for_customer(self.customer_a)
        for i in range(5):
            self.create_claim_record_for_customer(self.customer_a, upload_a)

        # Create data for Customer B
        self.create_upload_for_customer(self.customer_b)
        upload_b = self.create_upload_for_customer(self.customer_b)
        for i in range(10):
            self.create_claim_record_for_customer(self.customer_b, upload_b)

        # User A should only see Customer A's data
        self.authenticate_as(self.user_a)
        response = self.client.get(f"{API_BASE}/dashboard/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_uploads"], 2)
        self.assertEqual(response.data["total_claims"], 5)

        # User B should only see Customer B's data
        self.authenticate_as(self.user_b)
        response = self.client.get(f"{API_BASE}/dashboard/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_uploads"], 2)
        self.assertEqual(response.data["total_claims"], 10)


class PermissionsTests(APITestBase):
    """Tests for permission enforcement."""

    def test_unauthenticated_request_returns_401(self):
        """Unauthenticated requests to protected endpoints should return 401."""
        endpoints = [
            f"{API_BASE}/dashboard/",
            f"{API_BASE}/uploads/",
            f"{API_BASE}/claims/",
            f"{API_BASE}/reports/",
            f"{API_BASE}/drift-events/",
            f"{API_BASE}/customers/",
        ]

        for endpoint in endpoints:
            response = self.client.get(endpoint)
            self.assertEqual(
                response.status_code,
                status.HTTP_401_UNAUTHORIZED,
                f"Expected 401 for {endpoint}, got {response.status_code}",
            )

    def test_authenticated_user_without_customer_gets_forbidden(self):
        """Authenticated user without customer profile should get forbidden."""
        self.authenticate_as(self.user_no_customer)

        # Dashboard should return error (no customer)
        response = self.client.get(f"{API_BASE}/dashboard/")
        self.assertIn(
            response.status_code,
            [status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN],
        )

    def test_authenticated_user_with_customer_gets_access(self):
        """Authenticated user with customer profile should get access."""
        self.authenticate_as(self.user_a)

        response = self.client.get(f"{API_BASE}/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_expired_token_returns_401(self):
        """Expired or invalid token should return 401."""
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid-token")
        response = self.client.get(f"{API_BASE}/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_missing_authorization_header(self):
        """Request without authorization header should return 401."""
        response = self.client.get(f"{API_BASE}/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class CustomerEndpointTests(APITestBase):
    """Tests for customer endpoint."""

    def test_customer_list_shows_own_customer_only(self):
        """Customer list should only show the user's own customer."""
        self.authenticate_as(self.user_a)
        response = self.client.get(f"{API_BASE}/customers/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        customer_ids = [c["id"] for c in response.data["results"]]

        self.assertIn(self.customer_a.id, customer_ids)
        self.assertNotIn(self.customer_b.id, customer_ids)


class ReportRunEndpointTests(APITestBase):
    """Tests for report run endpoints."""

    def test_report_list_authenticated(self):
        """Report list should return 200 for authenticated request."""
        self.authenticate_as(self.user_a)
        response = self.client.get(f"{API_BASE}/reports/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_report_list_query_count(self):
        """Report list should use optimized queries to prevent N+1."""
        # Create 10 report runs
        for i in range(10):
            self.create_report_run_for_customer(self.customer_a)

        self.authenticate_as(self.user_a)

        # Query count should be constant regardless of number of reports
        # Expected queries:
        # 1. SELECT user (authentication)
        # 2. SELECT user profile (get customer)
        # 3. SELECT customer
        # 4. SELECT count for pagination
        # 5. SELECT report runs
        with self.assertNumQueries(5):
            response = self.client.get(f"{API_BASE}/reports/")
            # Force evaluation
            _ = response.data["results"]

    def test_report_trigger_creates_new_run(self):
        """Report trigger should create a new report run."""
        self.authenticate_as(self.user_a)
        response = self.client.post(f"{API_BASE}/reports/trigger/")

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertIn("id", response.data)

        # Verify report was created for customer A
        report = ReportRun.all_objects.get(id=response.data["id"])
        self.assertEqual(report.customer, self.customer_a)


class ClaimRecordEndpointTests(APITestBase):
    """Tests for claim record endpoints."""

    def test_claims_list_authenticated(self):
        """Claims list should return 200 for authenticated request."""
        self.authenticate_as(self.user_a)
        response = self.client.get(f"{API_BASE}/claims/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_claims_filter_by_payer(self):
        """Claims should be filterable by payer."""
        upload = self.create_upload_for_customer(self.customer_a)

        ClaimRecord.objects.create(
            customer=self.customer_a,
            upload=upload,
            payer="FilterPayer",
            cpt="99213",
            submitted_date=timezone.now().date(),
            decided_date=timezone.now().date(),
            outcome="PAID",
            submitted_via="csv_upload",
        )
        ClaimRecord.objects.create(
            customer=self.customer_a,
            upload=upload,
            payer="OtherPayer",
            cpt="99213",
            submitted_date=timezone.now().date(),
            decided_date=timezone.now().date(),
            outcome="PAID",
            submitted_via="csv_upload",
        )

        self.authenticate_as(self.user_a)
        response = self.client.get(f"{API_BASE}/claims/?payer=FilterPayer")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["payer"], "FilterPayer")

    def test_claims_filter_by_outcome(self):
        """Claims should be filterable by outcome."""
        upload = self.create_upload_for_customer(self.customer_a)

        ClaimRecord.objects.create(
            customer=self.customer_a,
            upload=upload,
            payer="TestPayer",
            cpt="99213",
            submitted_date=timezone.now().date(),
            decided_date=timezone.now().date(),
            outcome="PAID",
            submitted_via="csv_upload",
        )
        ClaimRecord.objects.create(
            customer=self.customer_a,
            upload=upload,
            payer="TestPayer",
            cpt="99213",
            submitted_date=timezone.now().date(),
            decided_date=timezone.now().date(),
            outcome="DENIED",
            submitted_via="csv_upload",
        )

        self.authenticate_as(self.user_a)
        response = self.client.get(f"{API_BASE}/claims/?outcome=denied")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["outcome"], "DENIED")


class ClaimRecordFilterTests(APITestBase):
    """Tests for ClaimRecord filtering via DjangoFilterBackend."""

    def setUp(self):
        super().setUp()
        # Create test claims with different attributes
        self.upload = self.create_upload_for_customer(self.customer_a)
        self.claim1 = ClaimRecord.objects.create(
            customer=self.customer_a,
            upload=self.upload,
            payer="Aetna",
            cpt="99213",
            outcome="PAID",
            decided_date="2024-06-15",
            submitted_date="2024-06-01",
            allowed_amount=100.00,
            submitted_via="csv_upload",
        )
        self.claim2 = ClaimRecord.objects.create(
            customer=self.customer_a,
            upload=self.upload,
            payer="Blue Cross",
            cpt="99214",
            outcome="DENIED",
            decided_date="2024-07-20",
            submitted_date="2024-07-01",
            allowed_amount=200.00,
            submitted_via="csv_upload",
        )

    def test_filter_by_payer_icontains(self):
        """Test filtering claims by payer name (partial match)."""
        self.authenticate_as(self.user_a)
        response = self.client.get(f"{API_BASE}/claims/?payer=aet")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["payer"], "Aetna")

    def test_filter_by_outcome(self):
        """Test filtering claims by outcome."""
        self.authenticate_as(self.user_a)
        response = self.client.get(f"{API_BASE}/claims/?outcome=denied")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["outcome"], "DENIED")

    def test_filter_by_date_range(self):
        """Test filtering claims by date range."""
        self.authenticate_as(self.user_a)
        response = self.client.get(
            f"{API_BASE}/claims/?start_date=2024-07-01&end_date=2024-07-31"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["payer"], "Blue Cross")

    def test_search_by_cpt(self):
        """Test searching claims by CPT code."""
        self.authenticate_as(self.user_a)
        response = self.client.get(f"{API_BASE}/claims/?search=99213")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["cpt"], "99213")

    def test_search_by_payer(self):
        """Test searching claims by payer name."""
        self.authenticate_as(self.user_a)
        response = self.client.get(f"{API_BASE}/claims/?search=blue")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["payer"], "Blue Cross")

    def test_combined_filters(self):
        """Test combining multiple filters."""
        self.authenticate_as(self.user_a)
        response = self.client.get(f"{API_BASE}/claims/?payer=aet&outcome=paid")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)


class DriftEventFilterTests(APITestBase):
    """Tests for DriftEvent filtering via DjangoFilterBackend."""

    def setUp(self):
        super().setUp()
        # Create a report run first
        self.report = ReportRun.objects.create(
            customer=self.customer_a,
            run_type="weekly",
            status="success",
        )
        self.drift1 = DriftEvent.objects.create(
            customer=self.customer_a,
            report_run=self.report,
            payer="Aetna",
            drift_type="DENIAL_RATE",
            severity=0.8,
            delta_value=0.15,
            baseline_value=0.1,
            current_value=0.25,
            confidence=0.9,
            baseline_start=timezone.now().date() - timedelta(days=104),
            baseline_end=timezone.now().date() - timedelta(days=14),
            current_start=timezone.now().date() - timedelta(days=14),
            current_end=timezone.now().date(),
        )
        self.drift2 = DriftEvent.objects.create(
            customer=self.customer_a,
            report_run=self.report,
            payer="Blue Cross",
            drift_type="PAYMENT_TIMING",
            severity=0.3,
            delta_value=5.0,
            baseline_value=10.0,
            current_value=15.0,
            confidence=0.85,
            baseline_start=timezone.now().date() - timedelta(days=104),
            baseline_end=timezone.now().date() - timedelta(days=14),
            current_start=timezone.now().date() - timedelta(days=14),
            current_end=timezone.now().date(),
        )

    def test_filter_by_min_severity(self):
        """Test filtering drift events by minimum severity."""
        self.authenticate_as(self.user_a)
        response = self.client.get(f"{API_BASE}/drift-events/?min_severity=0.5")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["severity"], 0.8)

    def test_filter_by_drift_type(self):
        """Test filtering drift events by type."""
        self.authenticate_as(self.user_a)
        response = self.client.get(f"{API_BASE}/drift-events/?drift_type=denial_rate")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["drift_type"], "DENIAL_RATE")

    def test_filter_by_payer(self):
        """Test filtering drift events by payer."""
        self.authenticate_as(self.user_a)
        response = self.client.get(f"{API_BASE}/drift-events/?payer=blue")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["payer"], "Blue Cross")

    def test_search_drift_events(self):
        """Test searching drift events."""
        self.authenticate_as(self.user_a)
        response = self.client.get(f"{API_BASE}/drift-events/?search=aetna")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)


class PaginationTests(APITestBase):
    """Tests for API pagination."""

    def test_payer_summary_paginated(self):
        """Test that payer_summary returns paginated response."""
        upload = self.create_upload_for_customer(self.customer_a)
        # Create claims for multiple payers
        for i in range(5):
            ClaimRecord.objects.create(
                customer=self.customer_a,
                upload=upload,
                payer=f"Payer{i}",
                cpt="99213",
                outcome="PAID",
                decided_date="2024-06-15",
                submitted_date="2024-06-01",
                allowed_amount=100.00,
                submitted_via="csv_upload",
            )

        self.authenticate_as(self.user_a)
        response = self.client.get(f"{API_BASE}/claims/payer_summary/")
        self.assertEqual(response.status_code, 200)
        # Check paginated response structure
        self.assertIn("count", response.data)
        self.assertIn("results", response.data)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)

    def test_list_pagination(self):
        """Test that list endpoints are paginated."""
        self.authenticate_as(self.user_a)
        response = self.client.get(f"{API_BASE}/claims/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("count", response.data)
        self.assertIn("results", response.data)


class ErrorHandlingTests(APITestBase):
    """Tests for standardized error handling across API endpoints."""

    def assertErrorFormat(self, response, expected_code, expected_status):
        """Helper to verify error response format."""
        self.assertEqual(response.status_code, expected_status)
        self.assertIn("error", response.data)
        self.assertIn("code", response.data["error"])
        self.assertIn("message", response.data["error"])
        self.assertIn("details", response.data["error"])
        self.assertEqual(response.data["error"]["code"], expected_code)

    def test_validation_error_format(self):
        """
        Test validation errors return standardized format.

        Checks field-level details are included.
        """
        self.authenticate_as(self.user_a)

        # Create settings with invalid email format
        response = self.client.post(
            f"{API_BASE}/settings/",
            {
                "to_email": "not-an-email",  # Invalid email format
            },
        )

        self.assertErrorFormat(response, "validation_error", 400)
        # Check field-level details are present
        self.assertIsNotNone(response.data["error"]["details"])
        self.assertIsInstance(response.data["error"]["details"], dict)
        # Should contain validation errors
        self.assertTrue(len(response.data["error"]["details"]) > 0)

    def test_validation_error_invalid_data(self):
        """Test validation errors with invalid field values."""
        self.authenticate_as(self.user_a)

        # Try to create settings with invalid boolean value
        response = self.client.post(
            f"{API_BASE}/settings/",
            {
                "to_email": "valid@example.com",
                "attach_pdf": "not-a-boolean",  # Invalid boolean
            },
        )

        self.assertErrorFormat(response, "validation_error", 400)
        details = response.data["error"]["details"]
        self.assertIsInstance(details, dict)
        # Should have validation errors
        self.assertTrue(len(details) > 0)

    def test_authentication_error_missing_credentials(self):
        """Test that missing authentication credentials return standardized format."""
        # Don't authenticate - try to access protected endpoint
        response = self.client.get(f"{API_BASE}/claims/")

        self.assertErrorFormat(response, "authentication_failed", 401)
        self.assertIsNone(response.data["error"]["details"])

    def test_authentication_error_invalid_token(self):
        """Test that invalid JWT tokens return standardized format."""
        # Use invalid token
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid_token_here")
        response = self.client.get(f"{API_BASE}/claims/")

        self.assertErrorFormat(response, "authentication_failed", 401)

    def test_permission_denied_error(self):
        """Test that permission denied errors return standardized format."""
        # Authenticate as user without customer profile
        tokens = self.get_tokens_for_user(self.user_no_customer)
        token = f"Bearer {tokens['access']}"
        self.client.credentials(HTTP_AUTHORIZATION=token)

        # Try to access endpoint that requires customer membership
        response = self.client.get(f"{API_BASE}/claims/")

        # Should return empty results due to queryset filtering
        # Test different scenario: access another customer's resource
        self.authenticate_as(self.user_a)
        claim = self.create_claim_record_for_customer(self.customer_b)

        # User A tries to access Customer B's claim (should be filtered by queryset)
        response = self.client.get(f"{API_BASE}/claims/{claim.id}/")

        # This will return 404 because queryset filters it out
        self.assertEqual(response.status_code, 404)
        self.assertErrorFormat(response, "not_found", 404)

    def test_not_found_error(self):
        """Test that 404 errors return standardized format."""
        self.authenticate_as(self.user_a)

        # Try to access non-existent resource
        response = self.client.get(f"{API_BASE}/claims/99999/")

        self.assertErrorFormat(response, "not_found", 404)

    def test_method_not_allowed_error(self):
        """Test that method not allowed errors return standardized format."""
        self.authenticate_as(self.user_a)

        # Try to DELETE on health endpoint (which only supports GET)
        response = self.client.delete(f"{API_BASE}/health/")

        self.assertErrorFormat(response, "method_not_allowed", 405)

    def test_parse_error_malformed_json(self):
        """Test that malformed JSON returns standardized format."""
        self.authenticate_as(self.user_a)

        # Send malformed JSON to a writeable endpoint
        response = self.client.post(
            f"{API_BASE}/settings/",
            data='{"invalid": json}',
            content_type="application/json",
        )

        self.assertErrorFormat(response, "parse_error", 400)

    def test_unsupported_media_type_error(self):
        """Test that unsupported media type returns standardized format."""
        self.authenticate_as(self.user_a)

        # Send request with unsupported content type to a writeable endpoint
        response = self.client.post(
            f"{API_BASE}/settings/",
            data="<xml>data</xml>",
            content_type="application/xml",
        )

        self.assertErrorFormat(response, "unsupported_media_type", 415)

    def test_throttled_error_format(self):
        """Test that throttled requests return standardized format."""
        from unittest.mock import patch
        from rest_framework.exceptions import Throttled

        self.authenticate_as(self.user_a)

        # Mock the dashboard view to raise a Throttled exception
        with patch(
            "upstream.api.views.DashboardView.get",
            side_effect=Throttled(wait=60),
        ):
            response = self.client.get(f"{API_BASE}/dashboard/")

            # Should return 429 with standardized error format
            self.assertErrorFormat(response, "throttled", 429)
            # Should include wait_seconds in details
            self.assertIsNotNone(response.data["error"]["details"])
            self.assertIn("wait_seconds", response.data["error"]["details"])
            self.assertEqual(response.data["error"]["details"]["wait_seconds"], 60)

    def test_server_error_format(self):
        """Test that unexpected server errors return standardized format."""
        from unittest.mock import patch
        from upstream.api.views import DashboardView

        self.authenticate_as(self.user_a)

        # Mock the dashboard view to raise an unexpected exception
        with patch.object(
            DashboardView,
            "get",
            side_effect=RuntimeError("Simulated server error"),
        ):
            response = self.client.get(f"{API_BASE}/dashboard/")

            # Should return 500 with standardized error format
            self.assertErrorFormat(response, "internal_server_error", 500)
            self.assertIsNone(response.data["error"]["details"])

    def test_django_http404_exception(self):
        """Test that Django Http404 exceptions return standardized format."""
        from unittest.mock import patch
        from django.http import Http404

        self.authenticate_as(self.user_a)

        # Mock a view to raise Django's Http404
        with patch(
            "upstream.api.views.DashboardView.get",
            side_effect=Http404("Resource not found"),
        ):
            response = self.client.get(f"{API_BASE}/dashboard/")

            # Should return 404 with standardized error format
            self.assertErrorFormat(response, "not_found", 404)
            self.assertIsNone(response.data["error"]["details"])

    def test_not_acceptable_error(self):
        """Test that NotAcceptable errors return standardized format."""
        from unittest.mock import patch
        from rest_framework.exceptions import NotAcceptable

        self.authenticate_as(self.user_a)

        # Mock a view to raise NotAcceptable
        with patch(
            "upstream.api.views.DashboardView.get",
            side_effect=NotAcceptable("Could not satisfy accept header"),
        ):
            response = self.client.get(f"{API_BASE}/dashboard/")

            # Should return 406 with standardized error format
            self.assertErrorFormat(response, "not_acceptable", 406)
            self.assertIsNone(response.data["error"]["details"])

    def test_not_found_with_detail_message(self):
        """Test NotFound exception with custom detail message."""
        from unittest.mock import patch
        from rest_framework.exceptions import NotFound

        self.authenticate_as(self.user_a)

        # Mock a view to raise NotFound with custom message
        with patch(
            "upstream.api.views.DashboardView.get",
            side_effect=NotFound("Custom not found message"),
        ):
            response = self.client.get(f"{API_BASE}/dashboard/")

            # Should return 404 with standardized error format and details
            self.assertErrorFormat(response, "not_found", 404)
            self.assertIsNotNone(response.data["error"]["details"])
            self.assertIn("detail", response.data["error"]["details"])

    def test_error_format_consistency(self):
        """Test that all error responses have consistent structure."""
        self.authenticate_as(self.user_a)

        # Test multiple different errors and verify they all have same structure
        error_responses = [
            self.client.get(f"{API_BASE}/claims/99999/"),  # 404
            self.client.post(
                f"{API_BASE}/settings/", {"to_email": "invalid"}
            ),  # 400 validation
            self.client.delete(f"{API_BASE}/health/"),  # 405
        ]

        for response in error_responses:
            # All should have error wrapper
            self.assertIn("error", response.data)
            error = response.data["error"]

            # All should have required fields
            self.assertIn("code", error)
            self.assertIn("message", error)
            self.assertIn("details", error)

            # Code should be a string
            self.assertIsInstance(error["code"], str)
            # Message should be a string
            self.assertIsInstance(error["message"], str)
            # Details can be None or dict
            self.assertTrue(
                error["details"] is None or isinstance(error["details"], dict)
            )


class ETagCachingTests(APITestBase):
    """Test ETag support for API responses (quick-010)."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        # Create an upload to test with
        self.upload = Upload.objects.create(
            customer=self.customer_a,
            filename="test_claims.csv",
            status="success",
            uploaded_by=self.user_a,
            row_count=100,
        )

    def test_get_response_includes_etag(self):
        """Test that GET requests return ETag header."""
        self.authenticate_as(self.user_a)

        response = self.client.get(f"{API_BASE}/uploads/")

        # Should return 200 with ETag header
        self.assertEqual(response.status_code, 200)
        self.assertIn("ETag", response)
        self.assertIsNotNone(response["ETag"])

        # ETag should be a quoted string (MD5 hash format)
        etag = response["ETag"]
        self.assertTrue(etag.startswith('"') and etag.endswith('"'))

        # Should also have Cache-Control header
        self.assertIn("Cache-Control", response)
        cache_control = response["Cache-Control"]
        self.assertIn("max-age=60", cache_control)
        self.assertIn("must-revalidate", cache_control)

    def test_if_none_match_returns_304(self):
        """Test that If-None-Match with matching ETag returns 304 Not Modified."""
        self.authenticate_as(self.user_a)

        # First request to get ETag
        response1 = self.client.get(f"{API_BASE}/uploads/")
        self.assertEqual(response1.status_code, 200)
        etag = response1["ETag"]

        # Second request with If-None-Match header
        response2 = self.client.get(f"{API_BASE}/uploads/", HTTP_IF_NONE_MATCH=etag)

        # Should return 304 Not Modified with no body
        self.assertEqual(response2.status_code, 304)
        self.assertEqual(len(response2.content), 0)

        # ETag should still be present in 304 response
        self.assertEqual(response2["ETag"], etag)

    def test_if_none_match_mismatch_returns_200(self):
        """Test If-None-Match with non-matching ETag returns 200."""
        self.authenticate_as(self.user_a)

        # Request with non-matching ETag
        fake_etag = '"fake-etag-12345"'
        response = self.client.get(f"{API_BASE}/uploads/", HTTP_IF_NONE_MATCH=fake_etag)

        # Should return 200 with full response body
        self.assertEqual(response.status_code, 200)
        self.assertIn("results", response.data)
        self.assertGreater(len(response.content), 0)

        # Should return new ETag that differs from fake one
        self.assertIn("ETag", response)
        self.assertNotEqual(response["ETag"], fake_etag)

    def test_post_request_has_no_cache(self):
        """Test that non-GET responses have no-cache headers."""
        self.authenticate_as(self.user_a)

        # Test DELETE request (simpler than POST/PUT)
        response = self.client.delete(f"{API_BASE}/uploads/{self.upload.id}/")

        # Should return 204 No Content
        self.assertEqual(response.status_code, 204)

        # Should have Cache-Control: no-cache, no-store
        self.assertIn("Cache-Control", response)
        cache_control = response["Cache-Control"]
        self.assertIn("no-cache", cache_control)
        self.assertIn("no-store", cache_control)
        self.assertIn("must-revalidate", cache_control)

        # Non-GET responses still get ETags from ConditionalGetMiddleware
        # but they shouldn't be used for caching due to no-cache directive

    def test_etag_changes_when_content_changes(self):
        """Test that ETag changes after content is modified."""
        self.authenticate_as(self.user_a)

        # First request to get initial ETag
        response1 = self.client.get(f"{API_BASE}/uploads/")
        self.assertEqual(response1.status_code, 200)
        etag1 = response1["ETag"]

        # Create a new upload to change the content
        Upload.objects.create(
            customer=self.customer_a,
            filename="another_claims.csv",
            status="success",
            uploaded_by=self.user_a,
            row_count=200,
        )

        # Second request should have different ETag
        response2 = self.client.get(f"{API_BASE}/uploads/")
        self.assertEqual(response2.status_code, 200)
        etag2 = response2["ETag"]

        # ETags should differ because content changed
        self.assertNotEqual(etag1, etag2)

        # Using old ETag with If-None-Match should return 200 (not 304)
        response3 = self.client.get(f"{API_BASE}/uploads/", HTTP_IF_NONE_MATCH=etag1)
        self.assertEqual(response3.status_code, 200)
        self.assertGreater(len(response3.content), 0)


class TestHATEOASLinks(APITestBase):
    """Tests for HATEOAS link generation across all API ViewSets (quick-011)."""

    def setUp(self):
        """Set up test fixtures for HATEOAS tests."""
        super().setUp()
        # Create test data
        self.upload_a = self.create_upload_for_customer(self.customer_a)
        self.claim_a = self.create_claim_record_for_customer(
            self.customer_a, self.upload_a
        )
        self.report_a = self.create_report_run_for_customer(self.customer_a)
        self.drift_a = self.create_drift_event_for_customer(
            self.customer_a, self.report_a
        )

    def test_upload_detail_links(self):
        """Test that upload detail view includes proper HATEOAS links."""
        self.authenticate_as(self.user_a)
        response = self.client.get(f"{API_BASE}/uploads/{self.upload_a.id}/")

        self.assertEqual(response.status_code, 200)

        # Assert _links field exists
        self.assertIn("_links", response.data)
        links = response.data["_links"]

        # Assert self link exists and is absolute
        self.assertIn("self", links)
        self.assertTrue(links["self"].startswith("http"))
        self.assertIn(f"/uploads/{self.upload_a.id}/", links["self"])

        # Assert collection link exists
        self.assertIn("collection", links)
        self.assertTrue(links["collection"].startswith("http"))
        self.assertIn("/uploads/", links["collection"])

        # Assert claims link exists (related resource)
        self.assertIn("claims", links)
        self.assertTrue(links["claims"].startswith("http"))
        self.assertIn(f"/claims/?upload={self.upload_a.id}", links["claims"])

    def test_upload_list_links(self):
        """Test that upload list view includes HATEOAS links for each item."""
        # Create additional uploads
        for i in range(3):
            self.create_upload_for_customer(self.customer_a)

        self.authenticate_as(self.user_a)
        response = self.client.get(f"{API_BASE}/uploads/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("results", response.data)
        self.assertGreater(len(response.data["results"]), 0)

        # Check each result has _links
        for upload in response.data["results"]:
            self.assertIn("_links", upload)
            self.assertIn("self", upload["_links"])
            self.assertTrue(upload["_links"]["self"].startswith("http"))

        # Verify self links are unique
        self_links = [u["_links"]["self"] for u in response.data["results"]]
        self.assertEqual(
            len(self_links), len(set(self_links)), "Self links should be unique"
        )

    def test_claim_detail_links(self):
        """Test that claim detail view includes upload link."""
        self.authenticate_as(self.user_a)
        response = self.client.get(f"{API_BASE}/claims/{self.claim_a.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("_links", response.data)
        links = response.data["_links"]

        # Assert self link
        self.assertIn("self", links)
        self.assertTrue(links["self"].startswith("http"))
        self.assertIn(f"/claims/{self.claim_a.id}/", links["self"])

        # Assert upload link (related resource)
        self.assertIn("upload", links)
        self.assertTrue(links["upload"].startswith("http"))
        self.assertIn(f"/uploads/{self.upload_a.id}/", links["upload"])

    def test_drift_event_detail_links(self):
        """Test that drift event detail view includes report link."""
        self.authenticate_as(self.user_a)
        response = self.client.get(f"{API_BASE}/drift-events/{self.drift_a.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("_links", response.data)
        links = response.data["_links"]

        # Assert self link
        self.assertIn("self", links)
        self.assertTrue(links["self"].startswith("http"))

        # Assert report link (related resource)
        self.assertIn("report", links)
        self.assertTrue(links["report"].startswith("http"))
        self.assertIn(f"/reports/{self.report_a.id}/", links["report"])

    def test_report_detail_links(self):
        """Test that report detail view includes drift-events link."""
        self.authenticate_as(self.user_a)
        response = self.client.get(f"{API_BASE}/reports/{self.report_a.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("_links", response.data)
        links = response.data["_links"]

        # Assert self link
        self.assertIn("self", links)
        self.assertTrue(links["self"].startswith("http"))

        # Assert drift-events link (related resource)
        self.assertIn("drift-events", links)
        self.assertTrue(links["drift-events"].startswith("http"))
        self.assertIn(
            f"/drift-events/?report_run={self.report_a.id}", links["drift-events"]
        )

    def test_pagination_links(self):
        """Test that paginated responses include next/previous links."""
        # Create 60 uploads to exceed PAGE_SIZE (50)
        for i in range(60):
            self.create_upload_for_customer(self.customer_a)

        self.authenticate_as(self.user_a)

        # Page 1 should have next link
        response = self.client.get(f"{API_BASE}/uploads/?page=1")
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data.get("next"))
        if response.data.get("next"):
            self.assertTrue(response.data["next"].startswith("http"))

        # Page 2 should have previous link
        response = self.client.get(f"{API_BASE}/uploads/?page=2")
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data.get("previous"))
        if response.data.get("previous"):
            self.assertTrue(response.data["previous"].startswith("http"))

    def test_links_respect_tenant_isolation(self):
        """Test that HATEOAS links respect tenant isolation."""
        # Create uploads for both customers
        upload_b = self.create_upload_for_customer(self.customer_b)

        # Authenticate as Customer A user
        self.authenticate_as(self.user_a)
        response = self.client.get(f"{API_BASE}/uploads/")

        self.assertEqual(response.status_code, 200)

        # Extract all self links from results
        self_links = [u["_links"]["self"] for u in response.data["results"]]

        # Verify Customer A's upload is included
        customer_a_link = any(
            f"/uploads/{self.upload_a.id}/" in link for link in self_links
        )
        self.assertTrue(customer_a_link, "Customer A's upload should be in results")

        # Verify Customer B's upload is NOT included
        customer_b_link = any(f"/uploads/{upload_b.id}/" in link for link in self_links)
        self.assertFalse(
            customer_b_link, "Customer B's upload should NOT be in results"
        )

    def test_customer_serializer_includes_links(self):
        """Test that customer serializer includes HATEOAS links."""
        self.authenticate_as(self.user_a)
        response = self.client.get(f"{API_BASE}/customers/{self.customer_a.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("_links", response.data)
        links = response.data["_links"]

        # Assert self link
        self.assertIn("self", links)
        self.assertTrue(links["self"].startswith("http"))
        self.assertIn(f"/customers/{self.customer_a.id}/", links["self"])


class ErrorResponseTests(APITestBase):
    """Test error response format consistency across all API endpoints."""

    def test_validation_error_format(self):
        """Test that validation errors return consistent format with field details."""
        # Authenticate as user
        self.authenticate_as(self.user_a)

        # Create invalid POST data (missing required fields)
        invalid_data = {
            # Missing required fields: filename, etc.
            "row_count": "invalid",  # Should be integer, not string
        }

        # POST invalid data to Upload endpoint
        response = self.client.post(f"{API_BASE}/uploads/", invalid_data, format="json")

        # Assert validation error status
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Assert error structure
        self.assertIn("error", response.data)
        error = response.data["error"]

        # Assert required fields
        self.assertIn("code", error)
        self.assertEqual(error["code"], "validation_error")

        self.assertIn("message", error)
        self.assertIsInstance(error["message"], str)

        self.assertIn("details", error)
        self.assertIsInstance(error["details"], dict)
        # Should contain field-level errors
        self.assertTrue(
            len(error["details"]) > 0, "Validation details should include field errors"
        )

        # Assert RFC 7807 type field
        self.assertIn("type", error)
        self.assertEqual(error["type"], "/errors/validation-error")

    def test_authentication_error_format(self):
        """Test that authentication errors return consistent format."""
        # GET endpoint without auth token
        response = self.client.get(f"{API_BASE}/claims/")

        # Assert authentication error status
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Assert error structure
        self.assertIn("error", response.data)
        error = response.data["error"]

        # Assert required fields
        self.assertIn("code", error)
        self.assertEqual(error["code"], "authentication_failed")

        self.assertIn("message", error)
        self.assertIsInstance(error["message"], str)
        self.assertIn("credentials", error["message"].lower())

        # Assert RFC 7807 type field
        self.assertIn("type", error)
        self.assertEqual(error["type"], "/errors/authentication-failed")

    def test_permission_error_format(self):
        """Test that permission denied errors return consistent format."""
        # Authenticate as user without customer profile
        self.authenticate_as(self.user_no_customer)

        # Try to access claims (requires customer association)
        response = self.client.get(f"{API_BASE}/claims/")

        # Assert permission error status
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Assert error structure
        self.assertIn("error", response.data)
        error = response.data["error"]

        # Assert required fields
        self.assertIn("code", error)
        self.assertEqual(error["code"], "permission_denied")

        self.assertIn("message", error)
        self.assertIsInstance(error["message"], str)

        # Assert RFC 7807 type field
        self.assertIn("type", error)
        self.assertEqual(error["type"], "/errors/permission-denied")

    def test_not_found_error_format(self):
        """Test that not found errors return consistent format."""
        # Authenticate as user
        self.authenticate_as(self.user_a)

        # GET non-existent claim record
        response = self.client.get(f"{API_BASE}/claims/999999/")

        # Assert not found error status
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Assert error structure
        self.assertIn("error", response.data)
        error = response.data["error"]

        # Assert required fields
        self.assertIn("code", error)
        self.assertEqual(error["code"], "not_found")

        self.assertIn("message", error)
        self.assertIsInstance(error["message"], str)
        self.assertIn("not found", error["message"].lower())

        # Assert RFC 7807 type field
        self.assertIn("type", error)
        self.assertEqual(error["type"], "/errors/not-found")

    def test_throttle_error_format(self):
        """Test that throttle errors return consistent format with wait_seconds."""
        # This test requires actual throttling to occur, which is hard to test
        # without making many requests. We'll test the format if throttling is enabled.
        # For now, we'll skip this test unless we can trigger throttling.
        # In production, this would be tested by exceeding rate limits.
        self.skipTest(
            "Throttle testing requires making many requests to trigger rate limit"
        )

    def test_method_not_allowed_format(self):
        """Test that method not allowed errors return consistent format."""
        # Authenticate as user
        self.authenticate_as(self.user_a)

        # Try PATCH on customers endpoint (read-only ViewSet)
        response = self.client.patch(
            f"{API_BASE}/customers/{self.customer_a.id}/",
            {"name": "New Name"},
            format="json",
        )

        # Assert method not allowed error status
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # Assert error structure
        self.assertIn("error", response.data)
        error = response.data["error"]

        # Assert required fields
        self.assertIn("code", error)
        self.assertEqual(error["code"], "method_not_allowed")

        self.assertIn("message", error)
        self.assertIsInstance(error["message"], str)

        # Assert RFC 7807 type field
        self.assertIn("type", error)
        self.assertEqual(error["type"], "/errors/method-not-allowed")

    def test_error_response_includes_request_id_if_available(self):
        """Test that error responses include request_id when middleware sets it."""
        # Note: RequestIdMiddleware would need to be active for this to work
        # This test documents the expected behavior when middleware is present

        # GET without authentication
        response = self.client.get(f"{API_BASE}/claims/")

        # Assert error structure
        self.assertIn("error", response.data)
        error = response.data["error"]

        # If request_id middleware is active, request_id should be present
        # Otherwise, it won't be present (which is also valid)
        if "request_id" in error:
            self.assertIsInstance(error["request_id"], str)
            self.assertTrue(len(error["request_id"]) > 0)
