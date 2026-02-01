"""
Tests for Home Health specialty module.

Story #21: Write tests for HomeHealthService
- Test PDGM group validation
- Test F2F timing requirements
- Test NOA deadline checking
- Test alert creation for violations
- Test handling of missing OASIS data
"""

from datetime import date, timedelta

from django.test import TestCase

from upstream.products.homehealth.constants import (
    PDGM_GROUPS,
    CLINICAL_GROUPS,
    FUNCTIONAL_LEVELS,
    COMORBIDITY_LEVELS,
    TIMING_CATEGORIES,
    F2F_PRIOR_DAYS,
    F2F_POST_DAYS,
    NOA_DEADLINE_DAYS,
    lookup_pdgm_group,
    is_valid_clinical_group,
    is_valid_functional_level,
    is_valid_comorbidity_level,
)
from upstream.products.homehealth.services import HomeHealthService


class MockClaim:
    """Mock claim object for testing."""

    def __init__(
        self,
        specialty_metadata=None,
        customer=None,
    ):
        self.specialty_metadata = specialty_metadata or {}
        self.customer = customer
        self.id = 1


class MockCustomer:
    """Mock customer object for testing."""

    def __init__(self, customer_id=1):
        self.id = customer_id


class PDGMConstantsTest(TestCase):
    """Tests for PDGM constants."""

    def test_timing_categories_defined(self):
        """Test timing categories are defined."""
        self.assertIn("EARLY", TIMING_CATEGORIES)
        self.assertIn("LATE", TIMING_CATEGORIES)

    def test_clinical_groups_has_12_groups(self):
        """Test clinical groups has all 12 PDGM groups."""
        self.assertEqual(len(CLINICAL_GROUPS), 12)

    def test_clinical_groups_include_common(self):
        """Test common clinical groups are included."""
        common_groups = ["MMTA", "WOUND", "NEURO_REHAB", "MS_REHAB", "CARDIAC"]
        for group in common_groups:
            self.assertIn(group, CLINICAL_GROUPS)

    def test_functional_levels_defined(self):
        """Test functional levels are defined."""
        self.assertIn("LOW", FUNCTIONAL_LEVELS)
        self.assertIn("MEDIUM", FUNCTIONAL_LEVELS)
        self.assertIn("HIGH", FUNCTIONAL_LEVELS)

    def test_comorbidity_levels_defined(self):
        """Test comorbidity levels are defined."""
        self.assertIn("NONE", COMORBIDITY_LEVELS)
        self.assertIn("LOW", COMORBIDITY_LEVELS)
        self.assertIn("HIGH", COMORBIDITY_LEVELS)

    def test_pdgm_groups_has_entries(self):
        """Test PDGM_GROUPS has expected entries."""
        self.assertGreater(len(PDGM_GROUPS), 50)

    def test_pdgm_groups_have_hipps_and_weight(self):
        """Test each PDGM group has hipps code and weight."""
        for key, value in PDGM_GROUPS.items():
            self.assertIn("hipps", value, f"Missing hipps for {key}")
            self.assertIn("weight", value, f"Missing weight for {key}")
            self.assertIsInstance(value["weight"], float)


class PDGMLookupTest(TestCase):
    """Tests for PDGM lookup functions."""

    def test_lookup_pdgm_group_found(self):
        """Test lookup returns group when found."""
        result = lookup_pdgm_group("EARLY", "MMTA", "LOW", "NONE")
        self.assertIsNotNone(result)
        self.assertEqual(result["hipps"], "1AAAA")

    def test_lookup_pdgm_group_not_found(self):
        """Test lookup returns None for unknown combination."""
        result = lookup_pdgm_group("EARLY", "UNKNOWN", "LOW", "NONE")
        self.assertIsNone(result)

    def test_lookup_case_insensitive(self):
        """Test lookup is case insensitive."""
        result = lookup_pdgm_group("early", "mmta", "low", "none")
        self.assertIsNotNone(result)

    def test_is_valid_clinical_group(self):
        """Test clinical group validation."""
        self.assertTrue(is_valid_clinical_group("MMTA"))
        self.assertTrue(is_valid_clinical_group("mmta"))  # Case insensitive
        self.assertFalse(is_valid_clinical_group("INVALID"))

    def test_is_valid_functional_level(self):
        """Test functional level validation."""
        self.assertTrue(is_valid_functional_level("LOW"))
        self.assertTrue(is_valid_functional_level("medium"))
        self.assertFalse(is_valid_functional_level("INVALID"))

    def test_is_valid_comorbidity_level(self):
        """Test comorbidity level validation."""
        self.assertTrue(is_valid_comorbidity_level("NONE"))
        self.assertTrue(is_valid_comorbidity_level("high"))
        self.assertFalse(is_valid_comorbidity_level("INVALID"))


class HomeHealthServicePDGMTest(TestCase):
    """Tests for HomeHealthService PDGM validation."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = HomeHealthService()

    def test_valid_pdgm_grouping(self):
        """Test valid PDGM grouping passes validation."""
        claim = MockClaim(
            specialty_metadata={
                "timing": "EARLY",
                "clinical_group": "MMTA",
                "functional_level": "LOW",
                "comorbidity": "NONE",
                "hipps_code": "1AAAA",
            }
        )
        result = self.service.validate_pdgm_grouping(claim)

        self.assertTrue(result.is_valid)
        self.assertEqual(result.timing, "EARLY")
        self.assertEqual(result.clinical_group, "MMTA")

    def test_pdgm_mismatch_detected(self):
        """Test PDGM mismatch is detected."""
        claim = MockClaim(
            specialty_metadata={
                "timing": "EARLY",
                "clinical_group": "MMTA",
                "functional_level": "LOW",
                "comorbidity": "NONE",
                "hipps_code": "WRONG",  # Wrong HIPPS code
            }
        )
        result = self.service.validate_pdgm_grouping(claim)

        self.assertFalse(result.is_valid)
        self.assertEqual(result.severity, "high")
        self.assertIn("MISMATCH", result.message)

    def test_missing_timing_detected(self):
        """Test missing timing field is detected."""
        claim = MockClaim(
            specialty_metadata={
                "clinical_group": "MMTA",
                "functional_level": "LOW",
                "comorbidity": "NONE",
            }
        )
        result = self.service.validate_pdgm_grouping(claim)

        self.assertFalse(result.is_valid)
        self.assertIn("timing", result.missing_fields)

    def test_multiple_missing_fields_is_high_severity(self):
        """Test multiple missing fields results in high severity."""
        claim = MockClaim(specialty_metadata={})
        result = self.service.validate_pdgm_grouping(claim)

        self.assertFalse(result.is_valid)
        self.assertEqual(result.severity, "high")
        self.assertEqual(len(result.missing_fields), 4)

    def test_invalid_clinical_group_detected(self):
        """Test invalid clinical group is detected."""
        claim = MockClaim(
            specialty_metadata={
                "timing": "EARLY",
                "clinical_group": "INVALID",
                "functional_level": "LOW",
                "comorbidity": "NONE",
            }
        )
        result = self.service.validate_pdgm_grouping(claim)

        self.assertFalse(result.is_valid)
        self.assertIn("Invalid clinical group", result.message)

    def test_missing_hipps_code_detected(self):
        """Test missing HIPPS code on claim is detected."""
        claim = MockClaim(
            specialty_metadata={
                "timing": "EARLY",
                "clinical_group": "MMTA",
                "functional_level": "LOW",
                "comorbidity": "NONE",
                # No hipps_code
            }
        )
        result = self.service.validate_pdgm_grouping(claim)

        self.assertFalse(result.is_valid)
        self.assertIn("Missing HIPPS", result.message)

    def test_unmapped_combination_is_valid(self):
        """Test unmapped but valid combination passes."""
        claim = MockClaim(
            specialty_metadata={
                "timing": "EARLY",
                "clinical_group": "BEHAVIORAL",  # Not in sample PDGM_GROUPS
                "functional_level": "LOW",
                "comorbidity": "NONE",
            }
        )
        result = self.service.validate_pdgm_grouping(claim)

        # Valid fields but no mapping - should pass with message
        self.assertTrue(result.is_valid)
        self.assertIn("No PDGM mapping", result.message)


class HomeHealthServiceF2FTest(TestCase):
    """Tests for HomeHealthService F2F timing validation."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = HomeHealthService()

    def test_f2f_before_soc_within_limit_is_valid(self):
        """Test F2F before SOC within 90 days is valid."""
        soc_date = date(2025, 6, 15)
        f2f_date = date(2025, 4, 1)  # 75 days before SOC

        claim = MockClaim(
            specialty_metadata={
                "soc_date": soc_date.isoformat(),
                "f2f_date": f2f_date.isoformat(),
            }
        )
        result = self.service.validate_f2f_timing(claim)

        self.assertTrue(result.is_valid)
        self.assertEqual(result.days_from_soc, -75)

    def test_f2f_after_soc_within_limit_is_valid(self):
        """Test F2F after SOC within 30 days is valid."""
        soc_date = date(2025, 6, 1)
        f2f_date = date(2025, 6, 20)  # 19 days after SOC

        claim = MockClaim(
            specialty_metadata={
                "soc_date": soc_date.isoformat(),
                "f2f_date": f2f_date.isoformat(),
            }
        )
        result = self.service.validate_f2f_timing(claim)

        self.assertTrue(result.is_valid)
        self.assertEqual(result.days_from_soc, 19)

    def test_f2f_too_early_is_invalid(self):
        """Test F2F more than 90 days before SOC is invalid."""
        soc_date = date(2025, 6, 15)
        f2f_date = date(2025, 3, 1)  # 106 days before SOC

        claim = MockClaim(
            specialty_metadata={
                "soc_date": soc_date.isoformat(),
                "f2f_date": f2f_date.isoformat(),
            }
        )
        result = self.service.validate_f2f_timing(claim)

        self.assertFalse(result.is_valid)
        self.assertEqual(result.severity, "critical")
        self.assertIn("too early", result.message)

    def test_f2f_too_late_is_invalid(self):
        """Test F2F more than 30 days after SOC is invalid."""
        soc_date = date(2025, 6, 1)
        f2f_date = date(2025, 7, 15)  # 44 days after SOC

        claim = MockClaim(
            specialty_metadata={
                "soc_date": soc_date.isoformat(),
                "f2f_date": f2f_date.isoformat(),
            }
        )
        result = self.service.validate_f2f_timing(claim)

        self.assertFalse(result.is_valid)
        self.assertEqual(result.severity, "critical")
        self.assertIn("too late", result.message)

    def test_missing_f2f_date_is_invalid(self):
        """Test missing F2F date is detected."""
        claim = MockClaim(
            specialty_metadata={
                "soc_date": "2025-06-01",
            }
        )
        result = self.service.validate_f2f_timing(claim)

        self.assertFalse(result.is_valid)
        self.assertEqual(result.severity, "high")
        self.assertIn("Missing F2F", result.message)

    def test_missing_soc_date_is_invalid(self):
        """Test missing SOC date is detected."""
        claim = MockClaim(
            specialty_metadata={
                "f2f_date": "2025-06-01",
            }
        )
        result = self.service.validate_f2f_timing(claim)

        self.assertFalse(result.is_valid)
        self.assertIn("Missing SOC", result.message)

    def test_f2f_boundary_90_days_before(self):
        """Test F2F exactly 90 days before SOC is valid."""
        soc_date = date(2025, 6, 15)
        f2f_date = soc_date - timedelta(days=F2F_PRIOR_DAYS)

        claim = MockClaim(
            specialty_metadata={
                "soc_date": soc_date.isoformat(),
                "f2f_date": f2f_date.isoformat(),
            }
        )
        result = self.service.validate_f2f_timing(claim)

        self.assertTrue(result.is_valid)

    def test_f2f_boundary_30_days_after(self):
        """Test F2F exactly 30 days after SOC is valid."""
        soc_date = date(2025, 6, 1)
        f2f_date = soc_date + timedelta(days=F2F_POST_DAYS)

        claim = MockClaim(
            specialty_metadata={
                "soc_date": soc_date.isoformat(),
                "f2f_date": f2f_date.isoformat(),
            }
        )
        result = self.service.validate_f2f_timing(claim)

        self.assertTrue(result.is_valid)


class HomeHealthServiceNOATest(TestCase):
    """Tests for HomeHealthService NOA deadline checking."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = HomeHealthService()

    def test_noa_submitted_on_time(self):
        """Test NOA submitted within deadline is compliant."""
        soc_date = date(2025, 6, 1)
        noa_date = date(2025, 6, 3)  # 2 days after SOC

        claim = MockClaim(
            specialty_metadata={
                "soc_date": soc_date.isoformat(),
                "noa_submitted_date": noa_date.isoformat(),
            }
        )
        result = self.service.check_noa_deadline(claim)

        self.assertTrue(result.has_noa)
        self.assertFalse(result.is_overdue)
        self.assertIn("on time", result.message)

    def test_noa_submitted_late(self):
        """Test NOA submitted after deadline is flagged."""
        soc_date = date(2025, 6, 1)
        noa_date = date(2025, 6, 10)  # 9 days after SOC (4 days late)

        claim = MockClaim(
            specialty_metadata={
                "soc_date": soc_date.isoformat(),
                "noa_submitted_date": noa_date.isoformat(),
            }
        )
        result = self.service.check_noa_deadline(claim)

        self.assertTrue(result.has_noa)
        self.assertTrue(result.is_overdue)
        self.assertEqual(result.severity, "warning")
        self.assertIn("late", result.message)

    def test_noa_pending_not_urgent(self):
        """Test pending NOA with time remaining is info severity."""
        # SOC today, deadline in 5 days
        soc_date = date.today()

        claim = MockClaim(
            specialty_metadata={
                "soc_date": soc_date.isoformat(),
                # No noa_submitted_date
            }
        )
        result = self.service.check_noa_deadline(claim)

        self.assertFalse(result.has_noa)
        self.assertFalse(result.is_overdue)
        self.assertEqual(result.days_until_deadline, NOA_DEADLINE_DAYS)

    def test_noa_deadline_approaching(self):
        """Test NOA due within 2 days is high severity."""
        # SOC was 4 days ago, deadline tomorrow
        soc_date = date.today() - timedelta(days=4)

        claim = MockClaim(
            specialty_metadata={
                "soc_date": soc_date.isoformat(),
            }
        )
        result = self.service.check_noa_deadline(claim)

        self.assertFalse(result.has_noa)
        self.assertEqual(result.days_until_deadline, 1)
        self.assertEqual(result.severity, "high")
        self.assertIn("due in", result.message)

    def test_noa_overdue(self):
        """Test NOA past deadline is critical severity."""
        # SOC was 10 days ago, 5 days overdue
        soc_date = date.today() - timedelta(days=10)

        claim = MockClaim(
            specialty_metadata={
                "soc_date": soc_date.isoformat(),
            }
        )
        result = self.service.check_noa_deadline(claim)

        self.assertFalse(result.has_noa)
        self.assertTrue(result.is_overdue)
        self.assertEqual(result.severity, "critical")
        self.assertIn("OVERDUE", result.message)

    def test_missing_soc_date(self):
        """Test missing SOC date is handled."""
        claim = MockClaim(specialty_metadata={})
        result = self.service.check_noa_deadline(claim)

        self.assertFalse(result.has_noa)
        self.assertIn("Missing SOC", result.message)


class HomeHealthServiceAnalyzeClaimsTest(TestCase):
    """Tests for HomeHealthService batch analysis."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = HomeHealthService()

    def test_analyze_empty_claims(self):
        """Test analyzing empty claims list."""
        results = self.service.analyze_claims([], create_alerts=False)

        self.assertEqual(results["total_claims"], 0)
        self.assertEqual(results["pdgm_valid"], 0)

    def test_analyze_counts_valid_pdgm(self):
        """Test counting valid PDGM claims."""
        claims = [
            MockClaim(
                specialty_metadata={
                    "timing": "EARLY",
                    "clinical_group": "MMTA",
                    "functional_level": "LOW",
                    "comorbidity": "NONE",
                    "hipps_code": "1AAAA",
                    "soc_date": "2025-06-01",
                    "f2f_date": "2025-05-15",
                }
            ),
        ]

        results = self.service.analyze_claims(
            claims, create_alerts=False, check_noa=False
        )

        self.assertEqual(results["total_claims"], 1)
        self.assertEqual(results["pdgm_valid"], 1)
        self.assertEqual(results["f2f_valid"], 1)

    def test_analyze_counts_invalid_pdgm(self):
        """Test counting invalid PDGM claims."""
        claims = [
            MockClaim(
                specialty_metadata={
                    "timing": "EARLY",
                    "clinical_group": "MMTA",
                    "functional_level": "LOW",
                    "comorbidity": "NONE",
                    "hipps_code": "WRONG",  # Mismatch
                    "soc_date": "2025-06-01",
                    "f2f_date": "2025-05-15",
                }
            ),
        ]

        results = self.service.analyze_claims(
            claims, create_alerts=False, check_noa=False
        )

        self.assertEqual(results["pdgm_invalid"], 1)

    def test_analyze_counts_missing_data(self):
        """Test counting claims with missing PDGM data."""
        claims = [
            MockClaim(
                specialty_metadata={
                    "soc_date": "2025-06-01",
                    "f2f_date": "2025-05-15",
                }
            ),
        ]

        results = self.service.analyze_claims(
            claims, create_alerts=False, check_noa=False
        )

        self.assertEqual(results["pdgm_missing_data"], 1)

    def test_analyze_counts_f2f_violations(self):
        """Test counting F2F timing violations."""
        claims = [
            MockClaim(
                specialty_metadata={
                    "timing": "EARLY",
                    "clinical_group": "BEHAVIORAL",
                    "functional_level": "LOW",
                    "comorbidity": "NONE",
                    "soc_date": "2025-06-01",
                    "f2f_date": "2025-08-01",  # Too late
                }
            ),
        ]

        results = self.service.analyze_claims(
            claims, create_alerts=False, check_noa=False
        )

        self.assertEqual(results["f2f_invalid"], 1)


# ============================================================================
# HomeHealth Model Tests (Story #13)
# ============================================================================


class HomeHealthPDGMGroupModelTest(TestCase):
    """Tests for HomeHealthPDGMGroup model."""

    def test_create_pdgm_group(self):
        """Test creating a PDGM group."""
        from upstream.products.homehealth.models import HomeHealthPDGMGroup

        group = HomeHealthPDGMGroup.objects.create(
            timing="EARLY",
            clinical_group="MMTA",
            functional_level="LOW",
            comorbidity="NONE",
            hipps_code="1AAAA",
            payment_weight=0.8234,
        )

        self.assertEqual(group.timing, "EARLY")
        self.assertEqual(group.clinical_group, "MMTA")
        self.assertEqual(group.functional_level, "LOW")
        self.assertEqual(group.comorbidity, "NONE")
        self.assertEqual(group.hipps_code, "1AAAA")
        self.assertAlmostEqual(group.payment_weight, 0.8234, places=4)

    def test_pdgm_group_str(self):
        """Test string representation of PDGM group."""
        from upstream.products.homehealth.models import HomeHealthPDGMGroup

        group = HomeHealthPDGMGroup.objects.create(
            timing="LATE",
            clinical_group="WOUND",
            functional_level="HIGH",
            comorbidity="LOW",
            hipps_code="2ABCB",
            payment_weight=1.4456,
        )

        expected = "2ABCB: LATE/WOUND/HIGH/LOW"
        self.assertEqual(str(group), expected)

    def test_pdgm_group_unique_hipps_code(self):
        """Test that HIPPS code must be unique."""
        from django.db import IntegrityError
        from upstream.products.homehealth.models import HomeHealthPDGMGroup

        HomeHealthPDGMGroup.objects.create(
            timing="EARLY",
            clinical_group="MMTA",
            functional_level="LOW",
            comorbidity="NONE",
            hipps_code="UNIQUE1",
            payment_weight=1.0,
        )

        with self.assertRaises(IntegrityError):
            HomeHealthPDGMGroup.objects.create(
                timing="LATE",
                clinical_group="WOUND",
                functional_level="HIGH",
                comorbidity="HIGH",
                hipps_code="UNIQUE1",  # Duplicate
                payment_weight=1.5,
            )

    def test_pdgm_group_unique_combination(self):
        """Test timing/clinical/functional/comorbidity combination must be unique."""
        from django.db import IntegrityError
        from upstream.products.homehealth.models import HomeHealthPDGMGroup

        HomeHealthPDGMGroup.objects.create(
            timing="EARLY",
            clinical_group="MMTA",
            functional_level="LOW",
            comorbidity="NONE",
            hipps_code="CODE1",
            payment_weight=1.0,
        )

        with self.assertRaises(IntegrityError):
            HomeHealthPDGMGroup.objects.create(
                timing="EARLY",
                clinical_group="MMTA",
                functional_level="LOW",
                comorbidity="NONE",  # Same combination
                hipps_code="CODE2",
                payment_weight=1.5,
            )

    def test_pdgm_group_payment_weight_nonnegative(self):
        """Test that payment weight must be non-negative."""
        from django.core.exceptions import ValidationError
        from upstream.products.homehealth.models import HomeHealthPDGMGroup

        group = HomeHealthPDGMGroup(
            timing="EARLY",
            clinical_group="MMTA",
            functional_level="LOW",
            comorbidity="NONE",
            hipps_code="NEGATIVE",
            payment_weight=-1.0,
        )

        with self.assertRaises(ValidationError):
            group.full_clean()


class HomeHealthEpisodeModelTest(TestCase):
    """Tests for HomeHealthEpisode model."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data for all tests."""
        from upstream.models import Customer

        cls.customer = Customer.objects.create(name="Test HomeHealth Provider")

    def test_create_episode(self):
        """Test creating a HomeHealth episode."""
        from upstream.products.homehealth.models import HomeHealthEpisode

        episode = HomeHealthEpisode.objects.create(
            customer=self.customer,
            patient_identifier="PT12345",
            payer="Medicare",
            soc_date=date(2025, 6, 1),
        )

        self.assertEqual(episode.patient_identifier, "PT12345")
        self.assertEqual(episode.payer, "Medicare")
        self.assertEqual(episode.soc_date, date(2025, 6, 1))
        self.assertEqual(episode.status, "ACTIVE")

    def test_episode_str(self):
        """Test string representation of episode."""
        from upstream.products.homehealth.models import HomeHealthEpisode

        episode = HomeHealthEpisode.objects.create(
            customer=self.customer,
            patient_identifier="PT67890",
            payer="Medicare",
            soc_date=date(2025, 6, 15),
        )

        str_repr = str(episode)
        self.assertIn("PT67890", str_repr)
        self.assertIn("ACTIVE", str_repr)

    def test_episode_f2f_validation_valid(self):
        """Test F2F validation when timing is within requirements."""
        from upstream.products.homehealth.models import HomeHealthEpisode

        # F2F 45 days before SOC (within 90 day limit)
        episode = HomeHealthEpisode.objects.create(
            customer=self.customer,
            patient_identifier="PT_F2F_VALID",
            payer="Medicare",
            soc_date=date(2025, 6, 1),
            f2f_date=date(2025, 4, 17),  # 45 days before SOC
        )

        result = episode.validate_f2f_timing()
        self.assertTrue(result)
        self.assertTrue(episode.f2f_is_valid)

    def test_episode_f2f_validation_too_early(self):
        """Test F2F validation when F2F is too early."""
        from upstream.products.homehealth.models import HomeHealthEpisode

        # F2F 120 days before SOC (exceeds 90 day limit)
        episode = HomeHealthEpisode.objects.create(
            customer=self.customer,
            patient_identifier="PT_F2F_EARLY",
            payer="Medicare",
            soc_date=date(2025, 6, 1),
            f2f_date=date(2025, 2, 1),  # ~120 days before SOC
        )

        result = episode.validate_f2f_timing()
        self.assertFalse(result)
        self.assertFalse(episode.f2f_is_valid)

    def test_episode_f2f_validation_too_late(self):
        """Test F2F validation when F2F is too late."""
        from upstream.products.homehealth.models import HomeHealthEpisode

        # F2F 45 days after SOC (exceeds 30 day limit)
        episode = HomeHealthEpisode.objects.create(
            customer=self.customer,
            patient_identifier="PT_F2F_LATE",
            payer="Medicare",
            soc_date=date(2025, 6, 1),
            f2f_date=date(2025, 7, 16),  # 45 days after SOC
        )

        result = episode.validate_f2f_timing()
        self.assertFalse(result)
        self.assertFalse(episode.f2f_is_valid)

    def test_episode_f2f_validation_missing_dates(self):
        """Test F2F validation with missing dates."""
        from upstream.products.homehealth.models import HomeHealthEpisode

        episode = HomeHealthEpisode.objects.create(
            customer=self.customer,
            patient_identifier="PT_F2F_MISSING",
            payer="Medicare",
            soc_date=date(2025, 6, 1),
            # No f2f_date
        )

        result = episode.validate_f2f_timing()
        self.assertFalse(result)
        self.assertFalse(episode.f2f_is_valid)

    def test_episode_days_to_f2f_property(self):
        """Test days_to_f2f property calculation."""
        from upstream.products.homehealth.models import HomeHealthEpisode

        episode = HomeHealthEpisode.objects.create(
            customer=self.customer,
            patient_identifier="PT_DAYS",
            payer="Medicare",
            soc_date=date(2025, 6, 1),
            f2f_date=date(2025, 5, 15),  # 17 days before SOC
        )

        self.assertEqual(episode.days_to_f2f, -17)

    def test_episode_noa_deadline_calculation(self):
        """Test NOA deadline calculation."""
        from upstream.products.homehealth.models import HomeHealthEpisode

        episode = HomeHealthEpisode.objects.create(
            customer=self.customer,
            patient_identifier="PT_NOA_CALC",
            payer="Medicare",
            soc_date=date(2025, 6, 1),
        )

        deadline = episode.calculate_noa_deadline()
        self.assertEqual(deadline, date(2025, 6, 6))  # SOC + 5 days
        self.assertEqual(episode.noa_deadline_date, date(2025, 6, 6))

    def test_episode_noa_validation_on_time(self):
        """Test NOA validation when submitted on time."""
        from upstream.products.homehealth.models import HomeHealthEpisode

        episode = HomeHealthEpisode.objects.create(
            customer=self.customer,
            patient_identifier="PT_NOA_ONTIME",
            payer="Medicare",
            soc_date=date(2025, 6, 1),
            noa_submitted_date=date(2025, 6, 3),  # 2 days after SOC
        )
        episode.calculate_noa_deadline()

        result = episode.validate_noa_timeliness()
        self.assertTrue(result)
        self.assertTrue(episode.noa_is_timely)

    def test_episode_noa_validation_late(self):
        """Test NOA validation when submitted late."""
        from upstream.products.homehealth.models import HomeHealthEpisode

        episode = HomeHealthEpisode.objects.create(
            customer=self.customer,
            patient_identifier="PT_NOA_LATE",
            payer="Medicare",
            soc_date=date(2025, 6, 1),
            noa_submitted_date=date(2025, 6, 10),  # 9 days after SOC
        )
        episode.calculate_noa_deadline()

        result = episode.validate_noa_timeliness()
        self.assertFalse(result)
        self.assertFalse(episode.noa_is_timely)

    def test_episode_pdgm_group_lookup(self):
        """Test PDGM group lookup on episode."""
        from upstream.products.homehealth.models import (
            HomeHealthEpisode,
            HomeHealthPDGMGroup,
        )

        # Create a PDGM group
        pdgm = HomeHealthPDGMGroup.objects.create(
            timing="EARLY",
            clinical_group="MMTA",
            functional_level="LOW",
            comorbidity="NONE",
            hipps_code="LOOKUP1",
            payment_weight=0.8234,
        )

        episode = HomeHealthEpisode.objects.create(
            customer=self.customer,
            patient_identifier="PT_LOOKUP",
            payer="Medicare",
            soc_date=date(2025, 6, 1),
            timing="EARLY",
            clinical_group="MMTA",
            functional_level="LOW",
            comorbidity="NONE",
        )

        result = episode.lookup_pdgm_group()
        self.assertEqual(result, pdgm)
        self.assertEqual(episode.pdgm_group, pdgm)

    def test_episode_pdgm_group_lookup_not_found(self):
        """Test PDGM group lookup when no match."""
        from upstream.products.homehealth.models import HomeHealthEpisode

        episode = HomeHealthEpisode.objects.create(
            customer=self.customer,
            patient_identifier="PT_NO_MATCH",
            payer="Medicare",
            soc_date=date(2025, 6, 1),
            timing="EARLY",
            clinical_group="BEHAVIORAL",  # Not in DB
            functional_level="HIGH",
            comorbidity="HIGH",
        )

        result = episode.lookup_pdgm_group()
        self.assertIsNone(result)

    def test_episode_pdgm_group_lookup_missing_fields(self):
        """Test PDGM group lookup with missing fields returns None."""
        from upstream.products.homehealth.models import HomeHealthEpisode

        episode = HomeHealthEpisode.objects.create(
            customer=self.customer,
            patient_identifier="PT_MISSING_FIELDS",
            payer="Medicare",
            soc_date=date(2025, 6, 1),
            timing="EARLY",
            # Missing other PDGM fields
        )

        result = episode.lookup_pdgm_group()
        self.assertIsNone(result)

    def test_episode_oasis_score_constraint(self):
        """Test OASIS score constraint (0-30)."""
        from django.core.exceptions import ValidationError
        from upstream.products.homehealth.models import HomeHealthEpisode

        # Valid score should work
        episode = HomeHealthEpisode.objects.create(
            customer=self.customer,
            patient_identifier="PT_OASIS_VALID",
            payer="Medicare",
            soc_date=date(2025, 6, 1),
            oasis_functional_score=15,
        )
        self.assertEqual(episode.oasis_functional_score, 15)

        # Out of range score should fail validation
        episode_invalid = HomeHealthEpisode(
            customer=self.customer,
            patient_identifier="PT_OASIS_INVALID",
            payer="Medicare",
            soc_date=date(2025, 6, 1),
            oasis_functional_score=35,  # Invalid - exceeds 30
        )

        with self.assertRaises(ValidationError):
            episode_invalid.full_clean()

    def test_episode_status_choices(self):
        """Test valid status choices."""
        from upstream.products.homehealth.models import HomeHealthEpisode

        valid_statuses = ["ACTIVE", "COMPLETED", "DISCHARGED", "TRANSFERRED"]

        for i, status in enumerate(valid_statuses):
            episode = HomeHealthEpisode.objects.create(
                customer=self.customer,
                patient_identifier=f"PT_STATUS_{i}",
                payer="Medicare",
                soc_date=date(2025, 6, 1),
                status=status,
            )
            self.assertEqual(episode.status, status)

    def test_episode_customer_relationship(self):
        """Test episode belongs to customer."""
        from upstream.products.homehealth.models import HomeHealthEpisode

        episode = HomeHealthEpisode.objects.create(
            customer=self.customer,
            patient_identifier="PT_CUSTOMER",
            payer="Medicare",
            soc_date=date(2025, 6, 1),
        )

        self.assertEqual(episode.customer, self.customer)
        customer_episodes = HomeHealthEpisode.all_objects.filter(customer=self.customer)
        self.assertIn(episode, customer_episodes)


# ============================================================================
# Certification Cycle Tests
# ============================================================================


class CertificationCycleModelTest(TestCase):
    """Tests for CertificationCycle model."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data for all tests."""
        from upstream.models import Customer
        from upstream.products.homehealth.models import HomeHealthEpisode

        cls.customer = Customer.objects.create(name="Test HH Provider Cert")
        cls.episode = HomeHealthEpisode.objects.create(
            customer=cls.customer,
            patient_identifier="PT_CERT_TEST",
            payer="Medicare",
            soc_date=date(2025, 6, 1),
        )

    def test_create_certification_cycle(self):
        """Test creating a certification cycle."""
        from upstream.products.homehealth.models import CertificationCycle

        cycle = CertificationCycle.objects.create(
            customer=self.customer,
            episode=self.episode,
            cycle_number=1,
            cycle_start=date(2025, 6, 1),
            cycle_end=date(2025, 7, 31),
        )

        self.assertEqual(cycle.cycle_number, 1)
        self.assertEqual(cycle.cycle_start, date(2025, 6, 1))
        self.assertEqual(cycle.cycle_end, date(2025, 7, 31))
        self.assertEqual(cycle.status, "ACTIVE")

    def test_certification_cycle_str(self):
        """Test string representation."""
        from upstream.products.homehealth.models import CertificationCycle

        cycle = CertificationCycle.objects.create(
            customer=self.customer,
            episode=self.episode,
            cycle_number=2,
            cycle_start=date(2025, 8, 1),
            cycle_end=date(2025, 9, 30),
        )

        self.assertIn("Cycle 2", str(cycle))

    def test_calculate_cycle_end(self):
        """Test automatic cycle end calculation."""
        from upstream.products.homehealth.models import CertificationCycle

        cycle = CertificationCycle(
            customer=self.customer,
            episode=self.episode,
            cycle_number=1,
            cycle_start=date(2025, 6, 1),
        )

        end_date = cycle.calculate_cycle_end()
        self.assertEqual(end_date, date(2025, 7, 31))  # 60 days from start
        self.assertEqual(cycle.cycle_end, date(2025, 7, 31))

    def test_days_remaining_property(self):
        """Test days remaining property."""
        from upstream.products.homehealth.models import CertificationCycle

        # Cycle ending in 10 days
        future_end = date.today() + timedelta(days=10)
        cycle = CertificationCycle.objects.create(
            customer=self.customer,
            episode=self.episode,
            cycle_number=3,
            cycle_start=date.today() - timedelta(days=50),
            cycle_end=future_end,
        )

        self.assertEqual(cycle.days_remaining, 10)

    def test_is_expiring_soon_property(self):
        """Test is_expiring_soon property."""
        from upstream.products.homehealth.models import CertificationCycle

        # Cycle ending in 10 days (within 14 day window)
        soon_cycle = CertificationCycle.objects.create(
            customer=self.customer,
            episode=self.episode,
            cycle_number=4,
            cycle_start=date.today() - timedelta(days=50),
            cycle_end=date.today() + timedelta(days=10),
        )
        self.assertTrue(soon_cycle.is_expiring_soon)

        # Cycle ending in 30 days (outside window)
        later_cycle = CertificationCycle.objects.create(
            customer=self.customer,
            episode=self.episode,
            cycle_number=5,
            cycle_start=date.today() - timedelta(days=30),
            cycle_end=date.today() + timedelta(days=30),
        )
        self.assertFalse(later_cycle.is_expiring_soon)

    def test_is_overdue_property(self):
        """Test is_overdue property."""
        from upstream.products.homehealth.models import CertificationCycle

        # Overdue cycle (ended yesterday)
        overdue_cycle = CertificationCycle.objects.create(
            customer=self.customer,
            episode=self.episode,
            cycle_number=6,
            cycle_start=date.today() - timedelta(days=61),
            cycle_end=date.today() - timedelta(days=1),
        )
        self.assertTrue(overdue_cycle.is_overdue)

        # Active cycle
        active_cycle = CertificationCycle.objects.create(
            customer=self.customer,
            episode=self.episode,
            cycle_number=7,
            cycle_start=date.today() - timedelta(days=30),
            cycle_end=date.today() + timedelta(days=30),
        )
        self.assertFalse(active_cycle.is_overdue)

    def test_mark_recertified(self):
        """Test marking a cycle as recertified."""
        from upstream.products.homehealth.models import CertificationCycle

        cycle = CertificationCycle.objects.create(
            customer=self.customer,
            episode=self.episode,
            cycle_number=8,
            cycle_start=date(2025, 6, 1),
            cycle_end=date(2025, 7, 31),
        )

        cycle.mark_recertified(
            physician_name="Dr. Smith", recert_date=date(2025, 7, 25)
        )

        cycle.refresh_from_db()
        self.assertEqual(cycle.status, "RECERTIFIED")
        self.assertTrue(cycle.physician_recert_signed)
        self.assertEqual(cycle.physician_name, "Dr. Smith")
        self.assertEqual(cycle.physician_recert_date, date(2025, 7, 25))

    def test_create_next_cycle(self):
        """Test creating the next cycle after recertification."""
        from upstream.products.homehealth.models import CertificationCycle

        cycle = CertificationCycle.objects.create(
            customer=self.customer,
            episode=self.episode,
            cycle_number=9,
            cycle_start=date(2025, 6, 1),
            cycle_end=date(2025, 7, 31),
        )

        cycle.mark_recertified()
        next_cycle = cycle.create_next_cycle()

        self.assertEqual(next_cycle.cycle_number, 10)
        self.assertEqual(
            next_cycle.cycle_start, date(2025, 8, 1)
        )  # Day after previous end
        self.assertEqual(next_cycle.cycle_end, date(2025, 9, 30))  # 60 days from start
        self.assertEqual(next_cycle.status, "ACTIVE")

    def test_create_next_cycle_requires_recertified(self):
        """Test that creating next cycle requires recertified status."""
        from upstream.products.homehealth.models import CertificationCycle

        cycle = CertificationCycle.objects.create(
            customer=self.customer,
            episode=self.episode,
            cycle_number=10,
            cycle_start=date(2025, 6, 1),
            cycle_end=date(2025, 7, 31),
            status="ACTIVE",  # Not recertified
        )

        with self.assertRaises(ValueError):
            cycle.create_next_cycle()

    def test_unique_episode_cycle_constraint(self):
        """Test that episode + cycle_number must be unique."""
        from django.db import IntegrityError
        from upstream.products.homehealth.models import CertificationCycle

        CertificationCycle.objects.create(
            customer=self.customer,
            episode=self.episode,
            cycle_number=11,
            cycle_start=date(2025, 6, 1),
            cycle_end=date(2025, 7, 31),
        )

        with self.assertRaises(IntegrityError):
            CertificationCycle.objects.create(
                customer=self.customer,
                episode=self.episode,
                cycle_number=11,  # Duplicate
                cycle_start=date(2025, 8, 1),
                cycle_end=date(2025, 9, 30),
            )


class CertificationCycleServiceTest(TestCase):
    """Tests for HomeHealthService certification cycle methods."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data."""
        from upstream.models import Customer
        from upstream.products.homehealth.models import HomeHealthEpisode

        cls.customer = Customer.objects.create(name="Test HH Cert Service")
        cls.episode = HomeHealthEpisode.objects.create(
            customer=cls.customer,
            patient_identifier="PT_SVC_TEST",
            payer="Medicare",
            soc_date=date(2025, 6, 1),
        )

    def setUp(self):
        """Set up test fixtures."""
        self.service = HomeHealthService()

    def test_create_initial_certification_cycle(self):
        """Test creating initial certification cycle for episode."""
        from upstream.products.homehealth.models import HomeHealthEpisode

        episode = HomeHealthEpisode.objects.create(
            customer=self.customer,
            patient_identifier="PT_INIT_CYCLE",
            payer="Medicare",
            soc_date=date(2025, 7, 1),
        )

        cycle = self.service.create_initial_certification_cycle(episode)

        self.assertEqual(cycle.cycle_number, 1)
        self.assertEqual(cycle.cycle_start, date(2025, 7, 1))
        self.assertEqual(cycle.cycle_end, date(2025, 8, 30))  # 60 days
        self.assertEqual(cycle.episode, episode)

    def test_get_active_certification_cycles(self):
        """Test getting active cycles for customer."""
        from upstream.products.homehealth.models import (
            CertificationCycle,
            HomeHealthEpisode,
        )

        episode = HomeHealthEpisode.objects.create(
            customer=self.customer,
            patient_identifier="PT_ACTIVE",
            payer="Medicare",
            soc_date=date(2025, 8, 1),
        )

        CertificationCycle.objects.create(
            customer=self.customer,
            episode=episode,
            cycle_number=1,
            cycle_start=date(2025, 8, 1),
            cycle_end=date(2025, 9, 30),
            status="ACTIVE",
        )

        cycles = self.service.get_active_certification_cycles(self.customer)
        self.assertEqual(cycles.count(), 1)

    def test_check_certification_deadlines(self):
        """Test checking certification deadlines."""
        from upstream.products.homehealth.models import (
            CertificationCycle,
            HomeHealthEpisode,
        )

        episode = HomeHealthEpisode.objects.create(
            customer=self.customer,
            patient_identifier="PT_DEADLINE",
            payer="Medicare",
            soc_date=date.today() - timedelta(days=50),
        )

        # Cycle ending in 10 days (critical)
        CertificationCycle.objects.create(
            customer=self.customer,
            episode=episode,
            cycle_number=1,
            cycle_start=date.today() - timedelta(days=50),
            cycle_end=date.today() + timedelta(days=10),
            status="ACTIVE",
        )

        results = self.service.check_certification_deadlines(self.customer)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["days_remaining"], 10)
        self.assertEqual(results[0]["severity"], "critical")

    def test_check_certification_deadlines_severity_levels(self):
        """Test different severity levels for deadlines."""
        from upstream.products.homehealth.models import (
            CertificationCycle,
            HomeHealthEpisode,
        )

        # Create episodes with cycles at different urgency levels
        severities = [
            (10, "critical"),  # 10 days
            (18, "high"),  # 18 days (within 21)
            (25, "medium"),  # 25 days (within 30)
            (40, "info"),  # 40 days (within 45)
        ]

        for i, (days, expected_severity) in enumerate(severities):
            ep = HomeHealthEpisode.objects.create(
                customer=self.customer,
                patient_identifier=f"PT_SEV_{i}",
                payer="Medicare",
                soc_date=date.today() - timedelta(days=60 - days),
            )
            CertificationCycle.objects.create(
                customer=self.customer,
                episode=ep,
                cycle_number=1,
                cycle_start=date.today() - timedelta(days=60 - days),
                cycle_end=date.today() + timedelta(days=days),
                status="ACTIVE",
            )

        results = self.service.check_certification_deadlines(self.customer)

        # Results sorted by days_remaining
        result_severities = {r["days_remaining"]: r["severity"] for r in results}

        for days, expected in severities:
            self.assertEqual(result_severities.get(days), expected)

    def test_recertify_cycle(self):
        """Test recertifying a cycle and creating next."""
        from upstream.products.homehealth.models import (
            CertificationCycle,
            HomeHealthEpisode,
        )

        episode = HomeHealthEpisode.objects.create(
            customer=self.customer,
            patient_identifier="PT_RECERT",
            payer="Medicare",
            soc_date=date(2025, 6, 1),
        )

        cycle = CertificationCycle.objects.create(
            customer=self.customer,
            episode=episode,
            cycle_number=1,
            cycle_start=date(2025, 6, 1),
            cycle_end=date(2025, 7, 31),
            status="ACTIVE",
        )

        recerted_cycle, next_cycle = self.service.recertify_cycle(
            cycle,
            physician_name="Dr. Johnson",
            create_next_cycle=True,
        )

        self.assertEqual(recerted_cycle.status, "RECERTIFIED")
        self.assertTrue(recerted_cycle.physician_recert_signed)
        self.assertIsNotNone(next_cycle)
        self.assertEqual(next_cycle.cycle_number, 2)

    def test_get_cycles_approaching_deadline(self):
        """Test getting cycles approaching deadline within days."""
        from upstream.products.homehealth.models import (
            CertificationCycle,
            HomeHealthEpisode,
        )

        # Create cycle ending in 7 days
        episode = HomeHealthEpisode.objects.create(
            customer=self.customer,
            patient_identifier="PT_APPROACH",
            payer="Medicare",
            soc_date=date.today() - timedelta(days=53),
        )

        CertificationCycle.objects.create(
            customer=self.customer,
            episode=episode,
            cycle_number=1,
            cycle_start=date.today() - timedelta(days=53),
            cycle_end=date.today() + timedelta(days=7),
            status="ACTIVE",
        )

        # Should find it with 14-day lookahead
        results = self.service.get_cycles_approaching_deadline(
            self.customer, days_ahead=14
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["days_remaining"], 7)
        self.assertEqual(results[0]["severity"], "critical")

        # Should not find it with 5-day lookahead
        results = self.service.get_cycles_approaching_deadline(
            self.customer, days_ahead=5
        )
        self.assertEqual(len(results), 0)
