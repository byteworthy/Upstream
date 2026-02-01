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
