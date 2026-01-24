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

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from datetime import timedelta

from upstream.models import (
    Customer, UserProfile, Upload, ClaimRecord,
    ReportRun, DriftEvent
)


# API base URL (mounted at /api/v1/ in urls.py)
API_BASE = '/api/v1'


class APITestBase(APITestCase):
    """Base class for API tests with common setup."""
    
    def setUp(self):
        """Set up test fixtures for API tests."""
        # Create customers
        self.customer_a = Customer.objects.create(name='Customer A')
        self.customer_b = Customer.objects.create(name='Customer B')
        
        # Create users for Customer A
        self.user_a = User.objects.create_user(
            username='user_a',
            email='user_a@example.com',
            password='testpass123'
        )
        self.profile_a = UserProfile.objects.create(
            user=self.user_a,
            customer=self.customer_a
        )
        
        # Create users for Customer B
        self.user_b = User.objects.create_user(
            username='user_b',
            email='user_b@example.com',
            password='testpass123'
        )
        self.profile_b = UserProfile.objects.create(
            user=self.user_b,
            customer=self.customer_b
        )
        
        # Create a user without customer profile
        self.user_no_customer = User.objects.create_user(
            username='no_customer',
            email='no_customer@example.com',
            password='testpass123'
        )
        
        self.client = APIClient()
    
    def get_tokens_for_user(self, user):
        """Helper to get JWT tokens for a user."""
        response = self.client.post(f'{API_BASE}/auth/token/', {
            'username': user.username,
            'password': 'testpass123'
        })
        return response.data
    
    def authenticate_as(self, user):
        """Helper to authenticate client as a specific user."""
        tokens = self.get_tokens_for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    
    def create_upload_for_customer(self, customer):
        """Helper to create an upload for a customer."""
        return Upload.objects.create(
            customer=customer,
            filename='test.csv',
            status='success',
            row_count=100
        )
    
    def create_claim_record_for_customer(self, customer, upload=None):
        """Helper to create a claim record for a customer."""
        if upload is None:
            upload = self.create_upload_for_customer(customer)
        return ClaimRecord.objects.create(
            customer=customer,
            upload=upload,
            payer='TestPayer',
            cpt='99213',
            cpt_group='EVAL',
            submitted_date=timezone.now().date() - timedelta(days=10),
            decided_date=timezone.now().date() - timedelta(days=5),
            outcome='PAID',
            allowed_amount=100.00
        )
    
    def create_report_run_for_customer(self, customer):
        """Helper to create a report run for a customer."""
        return ReportRun.objects.create(
            customer=customer,
            run_type='weekly',
            status='success',
            started_at=timezone.now() - timedelta(hours=1),
            finished_at=timezone.now(),
            summary_json={'events_created': 1}
        )
    
    def create_drift_event_for_customer(self, customer, report_run=None):
        """Helper to create a drift event for a customer."""
        if report_run is None:
            report_run = self.create_report_run_for_customer(customer)
        return DriftEvent.objects.create(
            customer=customer,
            report_run=report_run,
            payer='TestPayer',
            cpt_group='EVAL',
            drift_type='DENIAL_RATE',
            baseline_value=0.1,
            current_value=0.3,
            delta_value=0.2,
            severity=0.7,
            confidence=0.9,
            baseline_start=timezone.now().date() - timedelta(days=104),
            baseline_end=timezone.now().date() - timedelta(days=14),
            current_start=timezone.now().date() - timedelta(days=14),
            current_end=timezone.now().date()
        )


class HealthEndpointTests(APITestCase):
    """Tests for the health check endpoint."""
    
    def test_health_endpoint_returns_200(self):
        """Health endpoint should return 200 without authentication."""
        response = self.client.get(f'{API_BASE}/health/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_health_endpoint_returns_status(self):
        """Health endpoint should return status field."""
        response = self.client.get(f'{API_BASE}/health/')
        self.assertEqual(response.data['status'], 'healthy')
    
    def test_health_endpoint_returns_version(self):
        """Health endpoint should return version field."""
        response = self.client.get(f'{API_BASE}/health/')
        self.assertIn('version', response.data)
    
    def test_health_endpoint_returns_timestamp(self):
        """Health endpoint should return timestamp field."""
        response = self.client.get(f'{API_BASE}/health/')
        self.assertIn('timestamp', response.data)


class AuthEndpointTests(APITestBase):
    """Tests for authentication endpoints."""
    
    def test_token_obtain_with_valid_credentials(self):
        """Token obtain should return tokens with valid credentials."""
        response = self.client.post(f'{API_BASE}/auth/token/', {
            'username': 'user_a',
            'password': 'testpass123'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
    
    def test_token_obtain_with_invalid_credentials(self):
        """Token obtain should return 401 with invalid credentials."""
        response = self.client.post(f'{API_BASE}/auth/token/', {
            'username': 'user_a',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_token_obtain_with_nonexistent_user(self):
        """Token obtain should return 401 for nonexistent user."""
        response = self.client.post(f'{API_BASE}/auth/token/', {
            'username': 'nonexistent',
            'password': 'testpass123'
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_token_refresh_with_valid_token(self):
        """Token refresh should return new access token."""
        # First obtain tokens
        obtain_response = self.client.post(f'{API_BASE}/auth/token/', {
            'username': 'user_a',
            'password': 'testpass123'
        })
        refresh_token = obtain_response.data['refresh']
        
        # Then refresh
        response = self.client.post(f'{API_BASE}/auth/token/refresh/', {
            'refresh': refresh_token
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
    
    def test_token_refresh_with_invalid_token(self):
        """Token refresh should return 401 with invalid token."""
        response = self.client.post(f'{API_BASE}/auth/token/refresh/', {
            'refresh': 'invalid-token'
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class DashboardEndpointTests(APITestBase):
    """Tests for the dashboard endpoint."""
    
    def test_dashboard_unauthenticated(self):
        """Dashboard should return 401 for unauthenticated request."""
        response = self.client.get(f'{API_BASE}/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_dashboard_authenticated(self):
        """Dashboard should return 200 for authenticated request."""
        self.authenticate_as(self.user_a)
        response = self.client.get(f'{API_BASE}/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_dashboard_returns_expected_fields(self):
        """Dashboard should return expected fields."""
        self.authenticate_as(self.user_a)
        response = self.client.get(f'{API_BASE}/dashboard/')
        
        self.assertIn('total_claims', response.data)
        self.assertIn('total_uploads', response.data)
        self.assertIn('active_drift_events', response.data)
        self.assertIn('last_report_date', response.data)
        self.assertIn('top_drift_payers', response.data)
    
    def test_dashboard_shows_customer_data_only(self):
        """Dashboard should only show data for user's customer."""
        # Create data for both customers
        self.create_upload_for_customer(self.customer_a)
        self.create_upload_for_customer(self.customer_a)
        self.create_upload_for_customer(self.customer_b)
        
        self.authenticate_as(self.user_a)
        response = self.client.get(f'{API_BASE}/dashboard/')
        
        # User A should only see Customer A's uploads
        self.assertEqual(response.data['total_uploads'], 2)


class DriftEventEndpointTests(APITestBase):
    """Tests for drift event endpoints."""
    
    def test_drift_events_list_unauthenticated(self):
        """Drift events list should return 401 for unauthenticated request."""
        response = self.client.get(f'{API_BASE}/drift-events/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_drift_events_list_authenticated(self):
        """Drift events list should return 200 for authenticated request."""
        self.authenticate_as(self.user_a)
        response = self.client.get(f'{API_BASE}/drift-events/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_drift_events_active_endpoint(self):
        """Active drift endpoint should return recent events."""
        # Create report run and drift event for Customer A
        report_run = self.create_report_run_for_customer(self.customer_a)
        self.create_drift_event_for_customer(self.customer_a, report_run)
        
        self.authenticate_as(self.user_a)
        response = self.client.get(f'{API_BASE}/drift-events/active/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
    
    def test_drift_events_filter_by_severity(self):
        """Drift events should be filterable by minimum severity."""
        report_run = self.create_report_run_for_customer(self.customer_a)
        
        # Create events with different severities
        DriftEvent.objects.create(
            customer=self.customer_a,
            report_run=report_run,
            payer='LowSeverityPayer',
            cpt_group='EVAL',
            drift_type='DENIAL_RATE',
            baseline_value=0.1,
            current_value=0.15,
            delta_value=0.05,
            severity=0.2,
            confidence=0.9,
            baseline_start=timezone.now().date() - timedelta(days=104),
            baseline_end=timezone.now().date() - timedelta(days=14),
            current_start=timezone.now().date() - timedelta(days=14),
            current_end=timezone.now().date()
        )
        DriftEvent.objects.create(
            customer=self.customer_a,
            report_run=report_run,
            payer='HighSeverityPayer',
            cpt_group='EVAL',
            drift_type='DENIAL_RATE',
            baseline_value=0.1,
            current_value=0.5,
            delta_value=0.4,
            severity=0.8,
            confidence=0.9,
            baseline_start=timezone.now().date() - timedelta(days=104),
            baseline_end=timezone.now().date() - timedelta(days=14),
            current_start=timezone.now().date() - timedelta(days=14),
            current_end=timezone.now().date()
        )
        
        self.authenticate_as(self.user_a)
        response = self.client.get(f'{API_BASE}/drift-events/?min_severity=0.5')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should only return the high severity event
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['payer'], 'HighSeverityPayer')


class PayerSummaryEndpointTests(APITestBase):
    """Tests for payer summary endpoint."""
    
    def test_payer_summary_unauthenticated(self):
        """Payer summary should return 401 for unauthenticated request."""
        response = self.client.get(f'{API_BASE}/claims/payer_summary/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_payer_summary_authenticated(self):
        """Payer summary should return 200 for authenticated request."""
        self.authenticate_as(self.user_a)
        response = self.client.get(f'{API_BASE}/claims/payer_summary/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_payer_summary_aggregates_claims(self):
        """Payer summary should aggregate claims by payer."""
        upload = self.create_upload_for_customer(self.customer_a)
        
        # Create claims for different payers
        for i in range(5):
            ClaimRecord.objects.create(
                customer=self.customer_a,
                upload=upload,
                payer='PayerOne',
                cpt='99213',
                submitted_date=timezone.now().date() - timedelta(days=10),
                decided_date=timezone.now().date() - timedelta(days=5),
                outcome='PAID' if i < 3 else 'DENIED',
                allowed_amount=100.00
            )
        
        for i in range(3):
            ClaimRecord.objects.create(
                customer=self.customer_a,
                upload=upload,
                payer='PayerTwo',
                cpt='99213',
                submitted_date=timezone.now().date() - timedelta(days=10),
                decided_date=timezone.now().date() - timedelta(days=5),
                outcome='DENIED',
                allowed_amount=100.00
            )
        
        self.authenticate_as(self.user_a)
        response = self.client.get(f'{API_BASE}/claims/payer_summary/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        
        # Find PayerOne in results
        payer_one = next(p for p in response.data if p['payer'] == 'PayerOne')
        self.assertEqual(payer_one['total_claims'], 5)
        self.assertEqual(payer_one['paid_count'], 3)
        self.assertEqual(payer_one['denied_count'], 2)


class TenantIsolationTests(APITestBase):
    """Tests for tenant isolation - ensuring customers cannot access each other's data."""
    
    def test_uploads_tenant_isolation(self):
        """Customer A should not see Customer B's uploads."""
        # Create uploads for both customers
        upload_a = self.create_upload_for_customer(self.customer_a)
        upload_b = self.create_upload_for_customer(self.customer_b)
        
        self.authenticate_as(self.user_a)
        response = self.client.get(f'{API_BASE}/uploads/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        upload_ids = [u['id'] for u in response.data['results']]
        
        self.assertIn(upload_a.id, upload_ids)
        self.assertNotIn(upload_b.id, upload_ids)
    
    def test_claims_tenant_isolation(self):
        """Customer A should not see Customer B's claims."""
        # Create claims for both customers
        claim_a = self.create_claim_record_for_customer(self.customer_a)
        claim_b = self.create_claim_record_for_customer(self.customer_b)
        
        self.authenticate_as(self.user_a)
        response = self.client.get(f'{API_BASE}/claims/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        claim_ids = [c['id'] for c in response.data['results']]
        
        self.assertIn(claim_a.id, claim_ids)
        self.assertNotIn(claim_b.id, claim_ids)
    
    def test_drift_events_tenant_isolation(self):
        """Customer A should not see Customer B's drift events."""
        # Create drift events for both customers
        event_a = self.create_drift_event_for_customer(self.customer_a)
        event_b = self.create_drift_event_for_customer(self.customer_b)
        
        self.authenticate_as(self.user_a)
        response = self.client.get(f'{API_BASE}/drift-events/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        event_ids = [e['id'] for e in response.data['results']]
        
        self.assertIn(event_a.id, event_ids)
        self.assertNotIn(event_b.id, event_ids)
    
    def test_reports_tenant_isolation(self):
        """Customer A should not see Customer B's reports."""
        # Create reports for both customers
        report_a = self.create_report_run_for_customer(self.customer_a)
        report_b = self.create_report_run_for_customer(self.customer_b)
        
        self.authenticate_as(self.user_a)
        response = self.client.get(f'{API_BASE}/reports/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        report_ids = [r['id'] for r in response.data['results']]
        
        self.assertIn(report_a.id, report_ids)
        self.assertNotIn(report_b.id, report_ids)
    
    def test_direct_object_access_denied(self):
        """Customer A should not access Customer B's specific object."""
        upload_b = self.create_upload_for_customer(self.customer_b)
        
        self.authenticate_as(self.user_a)
        response = self.client.get(f'{API_BASE}/uploads/{upload_b.id}/')
        
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
        response = self.client.get(f'{API_BASE}/dashboard/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_uploads'], 2)
        self.assertEqual(response.data['total_claims'], 5)
        
        # User B should only see Customer B's data
        self.authenticate_as(self.user_b)
        response = self.client.get(f'{API_BASE}/dashboard/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_uploads'], 2)
        self.assertEqual(response.data['total_claims'], 10)


class PermissionsTests(APITestBase):
    """Tests for permission enforcement."""
    
    def test_unauthenticated_request_returns_401(self):
        """Unauthenticated requests to protected endpoints should return 401."""
        endpoints = [
            f'{API_BASE}/dashboard/',
            f'{API_BASE}/uploads/',
            f'{API_BASE}/claims/',
            f'{API_BASE}/reports/',
            f'{API_BASE}/drift-events/',
            f'{API_BASE}/customers/',
        ]
        
        for endpoint in endpoints:
            response = self.client.get(endpoint)
            self.assertEqual(
                response.status_code,
                status.HTTP_401_UNAUTHORIZED,
                f"Expected 401 for {endpoint}, got {response.status_code}"
            )
    
    def test_authenticated_user_without_customer_gets_forbidden(self):
        """Authenticated user without customer profile should get forbidden."""
        self.authenticate_as(self.user_no_customer)
        
        # Dashboard should return error (no customer)
        response = self.client.get(f'{API_BASE}/dashboard/')
        self.assertIn(response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN])
    
    def test_authenticated_user_with_customer_gets_access(self):
        """Authenticated user with customer profile should get access."""
        self.authenticate_as(self.user_a)
        
        response = self.client.get(f'{API_BASE}/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_expired_token_returns_401(self):
        """Expired or invalid token should return 401."""
        self.client.credentials(HTTP_AUTHORIZATION='Bearer invalid-token')
        response = self.client.get(f'{API_BASE}/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_missing_authorization_header(self):
        """Request without authorization header should return 401."""
        response = self.client.get(f'{API_BASE}/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class CustomerEndpointTests(APITestBase):
    """Tests for customer endpoint."""
    
    def test_customer_list_shows_own_customer_only(self):
        """Customer list should only show the user's own customer."""
        self.authenticate_as(self.user_a)
        response = self.client.get(f'{API_BASE}/customers/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        customer_ids = [c['id'] for c in response.data['results']]
        
        self.assertIn(self.customer_a.id, customer_ids)
        self.assertNotIn(self.customer_b.id, customer_ids)


class ReportRunEndpointTests(APITestBase):
    """Tests for report run endpoints."""
    
    def test_report_list_authenticated(self):
        """Report list should return 200 for authenticated request."""
        self.authenticate_as(self.user_a)
        response = self.client.get(f'{API_BASE}/reports/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_report_trigger_creates_new_run(self):
        """Report trigger should create a new report run."""
        self.authenticate_as(self.user_a)
        response = self.client.post(f'{API_BASE}/reports/trigger/')
        
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertIn('id', response.data)
        
        # Verify report was created for customer A
        report = ReportRun.objects.get(id=response.data['id'])
        self.assertEqual(report.customer, self.customer_a)


class ClaimRecordEndpointTests(APITestBase):
    """Tests for claim record endpoints."""
    
    def test_claims_list_authenticated(self):
        """Claims list should return 200 for authenticated request."""
        self.authenticate_as(self.user_a)
        response = self.client.get(f'{API_BASE}/claims/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_claims_filter_by_payer(self):
        """Claims should be filterable by payer."""
        upload = self.create_upload_for_customer(self.customer_a)
        
        ClaimRecord.objects.create(
            customer=self.customer_a,
            upload=upload,
            payer='FilterPayer',
            cpt='99213',
            submitted_date=timezone.now().date(),
            decided_date=timezone.now().date(),
            outcome='PAID'
        )
        ClaimRecord.objects.create(
            customer=self.customer_a,
            upload=upload,
            payer='OtherPayer',
            cpt='99213',
            submitted_date=timezone.now().date(),
            decided_date=timezone.now().date(),
            outcome='PAID'
        )
        
        self.authenticate_as(self.user_a)
        response = self.client.get(f'{API_BASE}/claims/?payer=FilterPayer')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['payer'], 'FilterPayer')
    
    def test_claims_filter_by_outcome(self):
        """Claims should be filterable by outcome."""
        upload = self.create_upload_for_customer(self.customer_a)
        
        ClaimRecord.objects.create(
            customer=self.customer_a,
            upload=upload,
            payer='TestPayer',
            cpt='99213',
            submitted_date=timezone.now().date(),
            decided_date=timezone.now().date(),
            outcome='PAID'
        )
        ClaimRecord.objects.create(
            customer=self.customer_a,
            upload=upload,
            payer='TestPayer',
            cpt='99213',
            submitted_date=timezone.now().date(),
            decided_date=timezone.now().date(),
            outcome='DENIED'
        )
        
        self.authenticate_as(self.user_a)
        response = self.client.get(f'{API_BASE}/claims/?outcome=denied')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['outcome'], 'DENIED')
