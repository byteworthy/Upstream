"""
Tests for RPA (Robotic Process Automation) Module.

Comprehensive test coverage for:
- PayerPortalBase abstract class
- MockPayerPortal implementation
- Data structures (ReauthRequest, AppealRequest, SubmissionResult)
- Portal registry and factory functions
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch
from django.test import TestCase
from django.utils import timezone

from upstream.automation.rpa import (
    PayerPortalBase,
    MockPayerPortal,
    ReauthRequest,
    AppealRequest,
    SubmissionResult,
    StatusResult,
    get_portal_for_payer,
    register_portal,
    get_available_portals,
    PortalAuthenticationError,
    PortalLookupError,
)


class TestReauthRequest(TestCase):
    """Test ReauthRequest dataclass."""

    def test_create_minimal_request(self):
        """Test creating request with required fields only."""
        request = ReauthRequest(
            auth_number="AUTH123",
            patient_id="PAT456",
            payer="Aetna",
            service_type="PT",
            units_requested=12,
        )

        self.assertEqual(request.auth_number, "AUTH123")
        self.assertEqual(request.patient_id, "PAT456")
        self.assertEqual(request.payer, "Aetna")
        self.assertEqual(request.service_type, "PT")
        self.assertEqual(request.units_requested, 12)
        self.assertIsNone(request.utilization_report_url)
        self.assertEqual(request.urgency, "standard")

    def test_create_full_request(self):
        """Test creating request with all fields."""
        start = timezone.now()
        end = start + timedelta(days=90)

        request = ReauthRequest(
            auth_number="AUTH123",
            patient_id="PAT456",
            payer="Aetna",
            service_type="PT",
            units_requested=12,
            utilization_report_url="https://example.com/report.pdf",
            start_date=start,
            end_date=end,
            diagnosis_codes=["M54.5", "M25.561"],
            cpt_codes=["97110", "97140"],
            clinical_notes="Patient requires continued therapy",
            urgency="urgent",
        )

        self.assertEqual(len(request.diagnosis_codes), 2)
        self.assertEqual(len(request.cpt_codes), 2)
        self.assertEqual(request.urgency, "urgent")


class TestAppealRequest(TestCase):
    """Test AppealRequest dataclass."""

    def test_create_minimal_appeal(self):
        """Test creating appeal with required fields only."""
        appeal = AppealRequest(
            claim_id="CLM789",
            payer="UnitedHealthcare",
            denial_reason="Medical necessity not established",
            appeal_letter="We respectfully appeal this denial...",
        )

        self.assertEqual(appeal.claim_id, "CLM789")
        self.assertEqual(appeal.appeal_level, "first")
        self.assertEqual(len(appeal.supporting_docs), 0)

    def test_create_full_appeal(self):
        """Test creating appeal with all fields."""
        appeal = AppealRequest(
            claim_id="CLM789",
            payer="UnitedHealthcare",
            denial_reason="Medical necessity not established",
            appeal_letter="We respectfully appeal this denial...",
            supporting_docs=[
                "https://example.com/clinical_notes.pdf",
                "https://example.com/test_results.pdf",
            ],
            original_dos=timezone.now() - timedelta(days=30),
            billed_amount=1500.00,
            appeal_level="second",
            deadline=timezone.now() + timedelta(days=60),
            contact_info={"phone": "555-1234", "email": "billing@provider.com"},
        )

        self.assertEqual(len(appeal.supporting_docs), 2)
        self.assertEqual(appeal.appeal_level, "second")
        self.assertEqual(appeal.billed_amount, 1500.00)


class TestSubmissionResult(TestCase):
    """Test SubmissionResult dataclass."""

    def test_successful_result(self):
        """Test creating successful submission result."""
        result = SubmissionResult(
            success=True,
            confirmation_number="CONF123",
            submitted_at=timezone.now(),
            payer="Aetna",
        )

        self.assertTrue(result.success)
        self.assertEqual(result.confirmation_number, "CONF123")
        self.assertIsNone(result.error_message)

    def test_failed_result(self):
        """Test creating failed submission result."""
        result = SubmissionResult(
            success=False,
            confirmation_number=None,
            submitted_at=timezone.now(),
            payer="Aetna",
            error_message="Portal unavailable",
            error_code="ERR500",
        )

        self.assertFalse(result.success)
        self.assertIsNone(result.confirmation_number)
        self.assertEqual(result.error_message, "Portal unavailable")

    def test_to_dict(self):
        """Test converting result to dictionary."""
        submitted = timezone.now()
        result = SubmissionResult(
            success=True,
            confirmation_number="CONF123",
            submitted_at=submitted,
            payer="Aetna",
            response_data={"key": "value"},
        )

        data = result.to_dict()

        self.assertTrue(data["success"])
        self.assertEqual(data["confirmation_number"], "CONF123")
        self.assertEqual(data["payer"], "Aetna")
        self.assertEqual(data["response_data"], {"key": "value"})


class TestPayerPortalBase(TestCase):
    """Test PayerPortalBase abstract class."""

    def test_cannot_instantiate_directly(self):
        """Test that PayerPortalBase cannot be instantiated."""
        with self.assertRaises(TypeError) as context:
            PayerPortalBase("Aetna")

        self.assertIn("abstract", str(context.exception).lower())

    def test_subclass_must_implement_methods(self):
        """Test that subclass must implement abstract methods."""

        class IncompletePortal(PayerPortalBase):
            def login(self):
                return True

        # Should fail because not all abstract methods implemented
        with self.assertRaises(TypeError):
            IncompletePortal("Aetna")


class TestMockPayerPortal(TestCase):
    """Test MockPayerPortal implementation."""

    def setUp(self):
        """Set up test fixtures."""
        MockPayerPortal.clear_all_submissions()

    def test_login_success(self):
        """Test successful login."""
        portal = MockPayerPortal("Aetna", delay_seconds=0)
        result = portal.login()

        self.assertTrue(result)
        self.assertTrue(portal.is_authenticated)

    def test_login_with_invalid_credentials(self):
        """Test login with invalid credentials."""
        portal = MockPayerPortal("Aetna", delay_seconds=0)
        portal.set_credentials_valid(False)

        with self.assertRaises(PortalAuthenticationError):
            portal.login()

    def test_logout(self):
        """Test logout."""
        portal = MockPayerPortal("Aetna", delay_seconds=0)
        portal.login()
        result = portal.logout()

        self.assertTrue(result)
        self.assertFalse(portal.is_authenticated)

    def test_submit_reauth_request_success(self):
        """Test successful reauth request submission."""
        portal = MockPayerPortal("Aetna", delay_seconds=0)
        portal.login()

        request = ReauthRequest(
            auth_number="AUTH123",
            patient_id="PAT456",
            payer="Aetna",
            service_type="PT",
            units_requested=12,
        )

        result = portal.submit_reauth_request(request)

        self.assertTrue(result.success)
        self.assertIsNotNone(result.confirmation_number)
        self.assertTrue(result.confirmation_number.startswith("MOCK-REAUTH-"))
        self.assertEqual(result.payer, "Aetna")
        self.assertIsNotNone(result.estimated_response_date)

    def test_submit_appeal_success(self):
        """Test successful appeal submission."""
        portal = MockPayerPortal("Aetna", delay_seconds=0)
        portal.login()

        appeal = AppealRequest(
            claim_id="CLM789",
            payer="Aetna",
            denial_reason="Medical necessity",
            appeal_letter="We appeal this denial...",
            supporting_docs=["doc1.pdf", "doc2.pdf"],
        )

        result = portal.submit_appeal(appeal)

        self.assertTrue(result.success)
        self.assertIsNotNone(result.confirmation_number)
        self.assertTrue(result.confirmation_number.startswith("MOCK-APPEAL-"))
        self.assertEqual(result.response_data["documents_attached"], 2)

    def test_check_status_found(self):
        """Test status check for existing submission."""
        portal = MockPayerPortal("Aetna", delay_seconds=0)
        portal.login()

        request = ReauthRequest(
            auth_number="AUTH123",
            patient_id="PAT456",
            payer="Aetna",
            service_type="PT",
            units_requested=12,
        )

        submit_result = portal.submit_reauth_request(request)
        status_result = portal.check_status(submit_result.confirmation_number)

        self.assertEqual(
            status_result.confirmation_number, submit_result.confirmation_number
        )
        self.assertIn(
            status_result.status, ["pending", "in_review", "approved", "denied"]
        )
        self.assertEqual(status_result.payer, "Aetna")

    def test_check_status_not_found(self):
        """Test status check for non-existent confirmation number."""
        portal = MockPayerPortal("Aetna", delay_seconds=0)

        with self.assertRaises(PortalLookupError):
            portal.check_status("INVALID-CONF-123")

    def test_fail_rate_produces_failures(self):
        """Test that fail_rate parameter produces failures."""
        # Login first with no failures, then set fail_rate for submissions
        portal = MockPayerPortal("Aetna", fail_rate=0.0, delay_seconds=0)
        portal.login()
        # Now set fail_rate to 1.0 for submission failures
        portal.fail_rate = 1.0

        request = ReauthRequest(
            auth_number="AUTH123",
            patient_id="PAT456",
            payer="Aetna",
            service_type="PT",
            units_requested=12,
        )

        result = portal.submit_reauth_request(request)

        self.assertFalse(result.success)
        self.assertIsNone(result.confirmation_number)
        self.assertIsNotNone(result.error_message)

    def test_fail_rate_zero_no_failures(self):
        """Test that fail_rate=0 produces no failures."""
        portal = MockPayerPortal("Aetna", fail_rate=0.0, delay_seconds=0)
        portal.login()

        request = ReauthRequest(
            auth_number="AUTH123",
            patient_id="PAT456",
            payer="Aetna",
            service_type="PT",
            units_requested=12,
        )

        # Submit multiple times, all should succeed
        for _ in range(10):
            result = portal.submit_reauth_request(request)
            self.assertTrue(result.success)

    def test_context_manager(self):
        """Test portal as context manager."""
        with MockPayerPortal("Aetna", delay_seconds=0) as portal:
            self.assertTrue(portal.is_authenticated)

            request = ReauthRequest(
                auth_number="AUTH123",
                patient_id="PAT456",
                payer="Aetna",
                service_type="PT",
                units_requested=12,
            )
            result = portal.submit_reauth_request(request)
            self.assertTrue(result.success)

        # After context, should be logged out
        self.assertFalse(portal.is_authenticated)

    def test_submission_tracking(self):
        """Test that submissions are tracked."""
        portal = MockPayerPortal("Aetna", delay_seconds=0)
        portal.login()

        request = ReauthRequest(
            auth_number="AUTH123",
            patient_id="PAT456",
            payer="Aetna",
            service_type="PT",
            units_requested=12,
        )

        result = portal.submit_reauth_request(request)

        # Check local tracking
        self.assertEqual(len(portal.submissions), 1)
        self.assertEqual(portal.submissions[0]["type"], "reauth")

        # Check global tracking
        submission = MockPayerPortal.get_submission(result.confirmation_number)
        self.assertIsNotNone(submission)
        self.assertEqual(submission["type"], "reauth")

    def test_clear_all_submissions(self):
        """Test clearing all tracked submissions."""
        portal = MockPayerPortal("Aetna", delay_seconds=0)
        portal.login()

        request = ReauthRequest(
            auth_number="AUTH123",
            patient_id="PAT456",
            payer="Aetna",
            service_type="PT",
            units_requested=12,
        )

        result = portal.submit_reauth_request(request)
        self.assertIsNotNone(MockPayerPortal.get_submission(result.confirmation_number))

        MockPayerPortal.clear_all_submissions()
        self.assertIsNone(MockPayerPortal.get_submission(result.confirmation_number))


class TestPortalRegistry(TestCase):
    """Test portal registry and factory functions."""

    def test_get_portal_for_payer_returns_mock(self):
        """Test that get_portal_for_payer returns MockPayerPortal by default."""
        portal = get_portal_for_payer("Aetna")

        self.assertIsInstance(portal, MockPayerPortal)
        self.assertEqual(portal.payer, "Aetna")

    def test_get_portal_with_fail_rate(self):
        """Test getting portal with custom fail rate."""
        portal = get_portal_for_payer("Aetna", fail_rate=0.5)

        self.assertIsInstance(portal, MockPayerPortal)
        self.assertEqual(portal.fail_rate, 0.5)

    def test_get_portal_different_payers(self):
        """Test getting portals for different payers."""
        payers = ["Aetna", "UnitedHealthcare", "Blue Cross Blue Shield", "Humana"]

        for payer in payers:
            portal = get_portal_for_payer(payer)
            self.assertEqual(portal.payer, payer)

    def test_get_available_portals(self):
        """Test getting list of available portals."""
        available = get_available_portals()

        self.assertIn("Aetna", available)
        self.assertIn("UnitedHealthcare", available)
        # All should be False since we only have mock implementations
        self.assertFalse(available["Aetna"])

    def test_register_custom_portal(self):
        """Test registering a custom portal implementation."""

        class CustomPortal(PayerPortalBase):
            def login(self):
                return True

            def logout(self):
                return True

            def submit_reauth_request(self, request):
                return SubmissionResult(
                    success=True,
                    confirmation_number="CUSTOM-123",
                    submitted_at=timezone.now(),
                    payer=self.payer,
                )

            def submit_appeal(self, appeal):
                return SubmissionResult(
                    success=True,
                    confirmation_number="CUSTOM-APPEAL-123",
                    submitted_at=timezone.now(),
                    payer=self.payer,
                )

            def check_status(self, confirmation_number):
                return StatusResult(
                    confirmation_number=confirmation_number,
                    status="pending",
                    status_date=timezone.now(),
                    payer=self.payer,
                )

        register_portal("TestPayer", CustomPortal)

        # Should still return mock when use_mock=True (default)
        portal = get_portal_for_payer("TestPayer")
        self.assertIsInstance(portal, MockPayerPortal)

        # Should return custom when use_mock=False
        portal = get_portal_for_payer("TestPayer", use_mock=False)
        self.assertIsInstance(portal, CustomPortal)
