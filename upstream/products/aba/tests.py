"""
Tests for ABA Authorization Tracking.

Comprehensive test coverage for ABAAuthorizationTracker model
and ABAAuthorizationService functionality.
"""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

from django.test import TestCase
from django.utils import timezone

from upstream.models import Customer, Authorization
from upstream.products.aba.models import ABAAuthorizationTracker
from upstream.products.aba.services import (
    ABAAuthorizationService,
    UTILIZATION_HIGH_THRESHOLD,
    UTILIZATION_CRITICAL_THRESHOLD,
    REAUTH_30_DAY_ALERT,
    REAUTH_14_DAY_ALERT,
    REAUTH_3_DAY_ALERT,
    CREDENTIAL_60_DAY_ALERT,
    CREDENTIAL_30_DAY_ALERT,
    CREDENTIAL_14_DAY_ALERT,
)


class ABAAuthorizationTrackerModelTest(TestCase):
    """Tests for ABAAuthorizationTracker model."""

    def setUp(self):
        """Set up test fixtures."""
        self.customer = Customer.objects.create(name="Test Customer")
        self.authorization = Authorization.objects.create(
            customer=self.customer,
            auth_number="ABA-TEST-001",
            patient_identifier="PAT001",
            payer="Test Payer",
            service_type="ABA",
            cpt_codes=["97151", "97153"],
            auth_start_date=date.today() - timedelta(days=30),
            auth_end_date=date.today() + timedelta(days=60),
            specialty_metadata={
                "authorized_units": 100,
                "bcba_required": True,
                "credential_expiration": str(date.today() + timedelta(days=45)),
            },
        )

    def test_create_tracker(self):
        """Test basic creation of an ABA tracker."""
        tracker = ABAAuthorizationTracker.objects.create(
            authorization=self.authorization,
            units_authorized=100,
            units_used=0,
        )
        self.assertEqual(tracker.units_authorized, 100)
        self.assertEqual(tracker.units_used, 0)
        self.assertEqual(tracker.units_remaining, 100)

    def test_units_remaining_property(self):
        """Test units_remaining property calculation."""
        tracker = ABAAuthorizationTracker.objects.create(
            authorization=self.authorization,
            units_authorized=100,
            units_used=40,
        )
        self.assertEqual(tracker.units_remaining, 60)

    def test_units_remaining_never_negative(self):
        """Test units_remaining is never negative."""
        tracker = ABAAuthorizationTracker.objects.create(
            authorization=self.authorization,
            units_authorized=100,
            units_used=150,  # Over-usage
        )
        self.assertEqual(tracker.units_remaining, 0)

    def test_utilization_percentage(self):
        """Test utilization percentage calculation."""
        tracker = ABAAuthorizationTracker.objects.create(
            authorization=self.authorization,
            units_authorized=100,
            units_used=75,
        )
        self.assertEqual(tracker.utilization_percentage, Decimal("75"))

    def test_utilization_percentage_zero_authorized(self):
        """Test utilization percentage when zero units authorized."""
        tracker = ABAAuthorizationTracker.objects.create(
            authorization=self.authorization,
            units_authorized=1,  # Minimum allowed
            units_used=0,
        )
        tracker.units_authorized = 0  # Force to zero for property test
        self.assertEqual(tracker.utilization_percentage, Decimal("0"))

    def test_str_representation(self):
        """Test string representation."""
        tracker = ABAAuthorizationTracker.objects.create(
            authorization=self.authorization,
            units_authorized=100,
        )
        self.assertIn("ABA-TEST-001", str(tracker))

    def test_update_usage(self):
        """Test update_usage method."""
        tracker = ABAAuthorizationTracker.objects.create(
            authorization=self.authorization,
            units_authorized=100,
            units_used=0,
        )
        tracker.update_usage(25)
        self.assertEqual(tracker.units_used, 25)
        self.assertIsNotNone(tracker.last_usage_update)

    def test_unique_authorization_constraint(self):
        """Test that only one tracker per authorization."""
        ABAAuthorizationTracker.objects.create(
            authorization=self.authorization,
            units_authorized=100,
        )
        with self.assertRaises(Exception):
            ABAAuthorizationTracker.objects.create(
                authorization=self.authorization,
                units_authorized=50,
            )


class ABAAuthorizationServiceUnitTrackingTest(TestCase):
    """Tests for unit tracking functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.customer = Customer.objects.create(name="Test Customer")
        self.authorization = Authorization.objects.create(
            customer=self.customer,
            auth_number="ABA-TEST-002",
            patient_identifier="PAT002",
            payer="Test Payer",
            service_type="ABA",
            cpt_codes=["97151"],
            auth_start_date=date.today() - timedelta(days=30),
            auth_end_date=date.today() + timedelta(days=60),
            specialty_metadata={"authorized_units": 100},
        )
        self.service = ABAAuthorizationService()

    def test_track_units_success(self):
        """Test successful unit tracking."""
        claim = Mock()
        claim.authorization = self.authorization
        claim.customer = self.customer
        claim.procedure_count = 5

        result = self.service.track_units(claim)

        self.assertTrue(result.success)
        self.assertEqual(result.units_added, 5)
        self.assertEqual(result.units_remaining, 95)

    def test_track_units_missing_authorization(self):
        """Test handling of claim without authorization."""
        claim = Mock()
        claim.authorization = None

        result = self.service.track_units(claim)

        self.assertFalse(result.success)
        self.assertIn("missing authorization", result.message)

    def test_track_units_non_aba_authorization(self):
        """Test handling of non-ABA authorization."""
        self.authorization.service_type = "PT"
        self.authorization.save()

        claim = Mock()
        claim.authorization = self.authorization
        claim.procedure_count = 5

        result = self.service.track_units(claim)

        self.assertFalse(result.success)
        self.assertIn("not for ABA", result.message)

    def test_track_units_missing_unit_count(self):
        """Test handling of claim without unit count."""
        claim = Mock()
        claim.authorization = self.authorization
        claim.procedure_count = None
        claim.units = None

        result = self.service.track_units(claim)

        self.assertFalse(result.success)
        self.assertIn("missing valid unit count", result.message)

    def test_track_units_creates_alert_at_90_percent(self):
        """Test alert creation when hitting 90% utilization."""
        # First create a tracker with high usage
        tracker = ABAAuthorizationTracker.objects.create(
            authorization=self.authorization,
            units_authorized=100,
            units_used=85,
        )

        claim = Mock()
        claim.authorization = self.authorization
        claim.customer = self.customer
        claim.procedure_count = 10  # This will push to 95%

        result = self.service.track_units(claim)

        self.assertTrue(result.success)
        self.assertTrue(result.alert_created)

    def test_track_units_cumulative(self):
        """Test cumulative unit tracking."""
        claim = Mock()
        claim.authorization = self.authorization
        claim.customer = self.customer
        claim.procedure_count = 10

        # Track first batch
        self.service.track_units(claim)

        # Track second batch
        claim.procedure_count = 15
        result = self.service.track_units(claim)

        self.assertEqual(result.units_remaining, 75)  # 100 - 10 - 15


class ABAAuthorizationServiceProjectionTest(TestCase):
    """Tests for exhaustion projection functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.customer = Customer.objects.create(name="Test Customer")
        self.authorization = Authorization.objects.create(
            customer=self.customer,
            auth_number="ABA-TEST-003",
            patient_identifier="PAT003",
            payer="Test Payer",
            service_type="ABA",
            cpt_codes=["97151"],
            auth_start_date=date.today() - timedelta(days=30),
            auth_end_date=date.today() + timedelta(days=60),
            specialty_metadata={"authorized_units": 100},
        )
        self.service = ABAAuthorizationService()

    def test_project_exhaustion_no_tracker(self):
        """Test projection when no tracker exists."""
        result = self.service.project_exhaustion(self.authorization)

        self.assertFalse(result.is_at_risk)
        self.assertEqual(result.severity, "none")

    def test_project_exhaustion_with_usage(self):
        """Test projection with actual usage data."""
        tracker = ABAAuthorizationTracker.objects.create(
            authorization=self.authorization,
            units_authorized=100,
            units_used=30,
            weekly_usage_rate=Decimal("7"),  # 7 units per week
        )

        result = self.service.project_exhaustion(self.authorization)

        self.assertIsNotNone(result.projected_date)
        self.assertIsNotNone(result.days_until_exhaustion)

    def test_project_exhaustion_critical_severity(self):
        """Test critical severity when exhaustion imminent."""
        tracker = ABAAuthorizationTracker.objects.create(
            authorization=self.authorization,
            units_authorized=100,
            units_used=93,
            weekly_usage_rate=Decimal("14"),  # High usage
        )
        # Manually set projected exhaustion date
        tracker.projected_exhaustion_date = date.today() + timedelta(days=5)
        tracker.save()

        result = self.service.project_exhaustion(self.authorization)

        self.assertTrue(result.is_at_risk)


class ABAAuthorizationServiceReauthAlertTest(TestCase):
    """Tests for re-authorization alert functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.customer = Customer.objects.create(name="Test Customer")
        self.service = ABAAuthorizationService()

    def test_reauth_alert_30_days(self):
        """Test alert at 30 days before expiration."""
        auth = Authorization.objects.create(
            customer=self.customer,
            auth_number="ABA-TEST-030",
            patient_identifier="PAT030",
            payer="Test Payer",
            service_type="ABA",
            cpt_codes=["97151"],
            auth_start_date=date.today() - timedelta(days=60),
            auth_end_date=date.today() + timedelta(days=25),
            specialty_metadata={},
        )

        alert = self.service.check_auth_expiration(auth)

        self.assertIsNotNone(alert)
        self.assertEqual(alert.payload["severity"], "medium")

    def test_reauth_alert_14_days(self):
        """Test alert at 14 days before expiration."""
        auth = Authorization.objects.create(
            customer=self.customer,
            auth_number="ABA-TEST-014",
            patient_identifier="PAT014",
            payer="Test Payer",
            service_type="ABA",
            cpt_codes=["97151"],
            auth_start_date=date.today() - timedelta(days=60),
            auth_end_date=date.today() + timedelta(days=10),
            specialty_metadata={},
        )

        alert = self.service.check_auth_expiration(auth)

        self.assertIsNotNone(alert)
        self.assertEqual(alert.payload["severity"], "high")

    def test_reauth_alert_3_days(self):
        """Test alert at 3 days before expiration."""
        auth = Authorization.objects.create(
            customer=self.customer,
            auth_number="ABA-TEST-003D",
            patient_identifier="PAT003D",
            payer="Test Payer",
            service_type="ABA",
            cpt_codes=["97151"],
            auth_start_date=date.today() - timedelta(days=60),
            auth_end_date=date.today() + timedelta(days=2),
            specialty_metadata={},
        )

        alert = self.service.check_auth_expiration(auth)

        self.assertIsNotNone(alert)
        self.assertEqual(alert.payload["severity"], "critical")

    def test_no_alert_far_from_expiration(self):
        """Test no alert when far from expiration."""
        auth = Authorization.objects.create(
            customer=self.customer,
            auth_number="ABA-TEST-FAR",
            patient_identifier="PATFAR",
            payer="Test Payer",
            service_type="ABA",
            cpt_codes=["97151"],
            auth_start_date=date.today() - timedelta(days=30),
            auth_end_date=date.today() + timedelta(days=90),
            specialty_metadata={},
        )

        alert = self.service.check_auth_expiration(auth)

        self.assertIsNone(alert)

    def test_duplicate_alert_prevention(self):
        """Test that duplicate alerts are prevented."""
        auth = Authorization.objects.create(
            customer=self.customer,
            auth_number="ABA-TEST-DUP",
            patient_identifier="PATDUP",
            payer="Test Payer",
            service_type="ABA",
            cpt_codes=["97151"],
            auth_start_date=date.today() - timedelta(days=60),
            auth_end_date=date.today() + timedelta(days=25),
            specialty_metadata={},
        )

        # Create tracker and mark alert as sent today
        tracker = ABAAuthorizationTracker.objects.create(
            authorization=auth,
            units_authorized=100,
            last_alert_date=date.today(),
            last_alert_type="reauth_30_day",
        )

        alert = self.service.check_auth_expiration(auth)

        self.assertIsNone(alert)


class ABAAuthorizationServiceCredentialTest(TestCase):
    """Tests for credential expiration checking."""

    def setUp(self):
        """Set up test fixtures."""
        self.customer = Customer.objects.create(name="Test Customer")
        self.service = ABAAuthorizationService()

    def test_credential_not_required(self):
        """Test when BCBA credential is not required."""
        auth = Authorization.objects.create(
            customer=self.customer,
            auth_number="ABA-CRED-001",
            patient_identifier="PATCRED001",
            payer="Test Payer",
            service_type="ABA",
            cpt_codes=["97151"],
            auth_start_date=date.today(),
            auth_end_date=date.today() + timedelta(days=90),
            specialty_metadata={"bcba_required": False},
        )

        result = self.service.check_credential_expiration(auth)

        self.assertFalse(result.has_credential)
        self.assertFalse(result.alert_needed)

    def test_credential_missing_expiration(self):
        """Test when credential required but expiration not set."""
        auth = Authorization.objects.create(
            customer=self.customer,
            auth_number="ABA-CRED-002",
            patient_identifier="PATCRED002",
            payer="Test Payer",
            service_type="ABA",
            cpt_codes=["97151"],
            auth_start_date=date.today(),
            auth_end_date=date.today() + timedelta(days=90),
            specialty_metadata={"bcba_required": True},
        )

        result = self.service.check_credential_expiration(auth)

        self.assertTrue(result.has_credential)
        self.assertTrue(result.alert_needed)
        self.assertEqual(result.severity, "high")

    def test_credential_expiring_60_days(self):
        """Test credential expiring in 60 days."""
        auth = Authorization.objects.create(
            customer=self.customer,
            auth_number="ABA-CRED-060",
            patient_identifier="PATCRED060",
            payer="Test Payer",
            service_type="ABA",
            cpt_codes=["97151"],
            auth_start_date=date.today(),
            auth_end_date=date.today() + timedelta(days=90),
            specialty_metadata={
                "bcba_required": True,
                "credential_expiration": str(date.today() + timedelta(days=50)),
            },
        )

        result = self.service.check_credential_expiration(
            auth, create_alert=False
        )

        self.assertTrue(result.alert_needed)
        self.assertEqual(result.severity, "medium")

    def test_credential_expiring_14_days(self):
        """Test credential expiring in 14 days - critical."""
        auth = Authorization.objects.create(
            customer=self.customer,
            auth_number="ABA-CRED-014",
            patient_identifier="PATCRED014",
            payer="Test Payer",
            service_type="ABA",
            cpt_codes=["97151"],
            auth_start_date=date.today(),
            auth_end_date=date.today() + timedelta(days=90),
            specialty_metadata={
                "bcba_required": True,
                "credential_expiration": str(date.today() + timedelta(days=10)),
            },
        )

        result = self.service.check_credential_expiration(
            auth, create_alert=False
        )

        self.assertTrue(result.alert_needed)
        self.assertEqual(result.severity, "critical")

    def test_credential_far_from_expiration(self):
        """Test credential with far expiration - no alert."""
        auth = Authorization.objects.create(
            customer=self.customer,
            auth_number="ABA-CRED-FAR",
            patient_identifier="PATCREDFAR",
            payer="Test Payer",
            service_type="ABA",
            cpt_codes=["97151"],
            auth_start_date=date.today(),
            auth_end_date=date.today() + timedelta(days=90),
            specialty_metadata={
                "bcba_required": True,
                "credential_expiration": str(date.today() + timedelta(days=120)),
            },
        )

        result = self.service.check_credential_expiration(
            auth, create_alert=False
        )

        self.assertFalse(result.alert_needed)
        self.assertEqual(result.severity, "none")


class ABAAuthorizationServiceAnalyzeTest(TestCase):
    """Tests for bulk authorization analysis."""

    def setUp(self):
        """Set up test fixtures."""
        self.customer = Customer.objects.create(name="Test Customer")
        self.service = ABAAuthorizationService()

    def test_analyze_authorizations(self):
        """Test bulk authorization analysis."""
        # Create authorizations with various states
        auth1 = Authorization.objects.create(
            customer=self.customer,
            auth_number="ABA-ANALYZE-001",
            patient_identifier="PATA001",
            payer="Test Payer",
            service_type="ABA",
            cpt_codes=["97151"],
            auth_start_date=date.today() - timedelta(days=30),
            auth_end_date=date.today() + timedelta(days=10),  # Expiring soon
            specialty_metadata={},
        )

        auth2 = Authorization.objects.create(
            customer=self.customer,
            auth_number="ABA-ANALYZE-002",
            patient_identifier="PATA002",
            payer="Test Payer",
            service_type="ABA",
            cpt_codes=["97151"],
            auth_start_date=date.today() - timedelta(days=30),
            auth_end_date=date.today() + timedelta(days=90),
            specialty_metadata={},
        )

        auths = [auth1, auth2]
        results = self.service.analyze_authorizations(auths)

        self.assertEqual(results["total"], 2)
        self.assertGreaterEqual(results["expiring_soon"], 1)

    def test_analyze_filters_non_aba(self):
        """Test that non-ABA authorizations are filtered."""
        auth = Authorization.objects.create(
            customer=self.customer,
            auth_number="PT-ANALYZE-001",
            patient_identifier="PATP001",
            payer="Test Payer",
            service_type="PT",  # Not ABA
            cpt_codes=["97110"],
            auth_start_date=date.today(),
            auth_end_date=date.today() + timedelta(days=90),
            specialty_metadata={},
        )

        results = self.service.analyze_authorizations([auth])

        self.assertEqual(results["total"], 0)
