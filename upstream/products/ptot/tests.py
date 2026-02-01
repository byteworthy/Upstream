"""
Tests for PT/OT specialty module.

Story #13: Write tests for PTOTService.
- Test 8-minute rule calculations at various minute values
- Test alert creation for over/under billing
- Test KX threshold detection
- Test YTD charge calculation
"""

from decimal import Decimal

from django.test import TestCase

from upstream.products.ptot.constants import (
    TIME_BASED_CPTS,
    calculate_units_from_minutes,
    is_time_based_cpt,
    get_minutes_per_unit,
    EIGHT_MINUTE_RULE_THRESHOLDS,
)
from upstream.products.ptot.services import (
    PTOTService,
    THERAPY_CAP_THRESHOLD,
)


class MockClaim:
    """Mock claim object for testing."""

    def __init__(
        self,
        cpt=None,
        total_minutes=None,
        units=None,
        modifiers="",
        customer=None,
        patient=None,
    ):
        self.cpt = cpt
        self.total_minutes = total_minutes
        self.procedure_count = units
        self.modifiers = modifiers
        self.customer = customer
        self.patient = patient
        self.id = 1


class MockCustomer:
    """Mock customer object for testing."""

    def __init__(self, customer_id=1):
        self.id = customer_id


class MockPatient:
    """Mock patient object for testing."""

    def __init__(self, patient_id=1):
        self.id = patient_id
        self.claims = MockClaimManager()


class MockClaimManager:
    """Mock claims manager for testing."""

    def __init__(self, total_charges=Decimal("0")):
        self.total_charges = total_charges

    def filter(self, **kwargs):
        """Return self for chaining."""
        return self

    def aggregate(self, **kwargs):
        """Return mocked aggregate result."""
        return {"total": self.total_charges}


class TimeBasedCPTsConstantsTest(TestCase):
    """Tests for TIME_BASED_CPTS constants."""

    def test_time_based_cpts_has_30_plus_codes(self):
        """Verify TIME_BASED_CPTS has 30+ CPT codes."""
        self.assertGreaterEqual(len(TIME_BASED_CPTS), 30)

    def test_common_pt_codes_included(self):
        """Verify common PT CPT codes are included."""
        common_codes = ["97110", "97112", "97140", "97530", "97535"]
        for code in common_codes:
            self.assertIn(code, TIME_BASED_CPTS)

    def test_all_codes_have_minute_values(self):
        """Verify all CPT codes have positive minute values."""
        for cpt, minutes in TIME_BASED_CPTS.items():
            self.assertIsInstance(minutes, int)
            self.assertGreater(minutes, 0, f"CPT {cpt} has invalid minutes")


class CalculateUnitsFromMinutesTest(TestCase):
    """Tests for 8-minute rule unit calculation."""

    def test_less_than_8_minutes_is_zero_units(self):
        """Test that < 8 minutes returns 0 units."""
        for minutes in [0, 1, 5, 7]:
            result = calculate_units_from_minutes(minutes)
            self.assertEqual(result, 0, f"{minutes} min should be 0 units")

    def test_8_to_22_minutes_is_one_unit(self):
        """Test that 8-22 minutes returns 1 unit."""
        for minutes in [8, 10, 15, 20, 22]:
            result = calculate_units_from_minutes(minutes)
            self.assertEqual(result, 1, f"{minutes} min should be 1 unit")

    def test_23_to_37_minutes_is_two_units(self):
        """Test that 23-37 minutes returns 2 units."""
        for minutes in [23, 25, 30, 35, 37]:
            result = calculate_units_from_minutes(minutes)
            self.assertEqual(result, 2, f"{minutes} min should be 2 units")

    def test_38_to_52_minutes_is_three_units(self):
        """Test that 38-52 minutes returns 3 units."""
        for minutes in [38, 40, 45, 50, 52]:
            result = calculate_units_from_minutes(minutes)
            self.assertEqual(result, 3, f"{minutes} min should be 3 units")

    def test_boundary_values(self):
        """Test boundary values for unit transitions."""
        test_cases = [
            (7, 0),   # Just below 8
            (8, 1),   # Exactly 8
            (22, 1),  # Top of 1 unit
            (23, 2),  # Start of 2 units
            (37, 2),  # Top of 2 units
            (38, 3),  # Start of 3 units
        ]
        for minutes, expected in test_cases:
            result = calculate_units_from_minutes(minutes)
            self.assertEqual(
                result, expected,
                f"{minutes} min should be {expected} units, got {result}"
            )


class IsTimeBasedCPTTest(TestCase):
    """Tests for is_time_based_cpt function."""

    def test_time_based_cpt_returns_true(self):
        """Test that time-based CPTs return True."""
        for cpt in ["97110", "97112", "97140"]:
            self.assertTrue(
                is_time_based_cpt(cpt),
                f"CPT {cpt} should be time-based"
            )

    def test_non_time_based_cpt_returns_false(self):
        """Test that non-time-based CPTs return False."""
        non_time_based = ["99213", "99214", "99215", "XXXXX"]
        for cpt in non_time_based:
            self.assertFalse(
                is_time_based_cpt(cpt),
                f"CPT {cpt} should NOT be time-based"
            )


class GetMinutesPerUnitTest(TestCase):
    """Tests for get_minutes_per_unit function."""

    def test_returns_correct_minutes_for_known_cpt(self):
        """Test correct minutes returned for known CPTs."""
        self.assertEqual(get_minutes_per_unit("97110"), 15)
        self.assertEqual(get_minutes_per_unit("97545"), 120)  # Work hardening

    def test_returns_default_for_unknown_cpt(self):
        """Test default 15 minutes returned for unknown CPTs."""
        self.assertEqual(get_minutes_per_unit("UNKNOWN"), 15)


class PTOTServiceEightMinuteRuleTest(TestCase):
    """Tests for PTOTService 8-minute rule validation."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = PTOTService()

    def test_valid_billing_returns_valid(self):
        """Test valid billing scenarios return is_valid=True."""
        valid_cases = [
            ("97110", 15, 1),   # 15 min = 1 unit
            ("97110", 22, 1),   # 22 min = 1 unit (max for 1)
            ("97110", 23, 2),   # 23 min = 2 units
            ("97110", 45, 3),   # 45 min = 3 units
        ]
        for cpt, minutes, units in valid_cases:
            claim = MockClaim(cpt=cpt, total_minutes=minutes, units=units)
            result = self.service.validate_8_minute_rule(claim)
            self.assertTrue(
                result.is_valid,
                f"{minutes}min/{units}u should be valid: {result.message}"
            )

    def test_overbilling_detected(self):
        """Test overbilling detection."""
        # 15 minutes should be 1 unit, billing 2 is overbilling
        claim = MockClaim(cpt="97110", total_minutes=15, units=2)
        result = self.service.validate_8_minute_rule(claim)

        self.assertFalse(result.is_valid)
        self.assertEqual(result.unit_difference, 1)  # Billed 1 extra
        self.assertIn("OVERBILLED", result.message)

    def test_severe_overbilling_is_critical(self):
        """Test severe overbilling (2+ units) is critical severity."""
        # 15 minutes should be 1 unit, billing 3 is severe overbilling
        claim = MockClaim(cpt="97110", total_minutes=15, units=3)
        result = self.service.validate_8_minute_rule(claim)

        self.assertFalse(result.is_valid)
        self.assertEqual(result.severity, "critical")
        self.assertEqual(result.unit_difference, 2)

    def test_underbilling_detected(self):
        """Test underbilling detection."""
        # 45 minutes should be 3 units, billing 2 is underbilling
        claim = MockClaim(cpt="97110", total_minutes=45, units=2)
        result = self.service.validate_8_minute_rule(claim)

        self.assertFalse(result.is_valid)
        self.assertEqual(result.unit_difference, -1)
        self.assertIn("UNDERBILLED", result.message)
        self.assertEqual(result.severity, "info")  # Less severe

    def test_non_time_based_cpt_is_valid(self):
        """Test non-time-based CPT codes are marked valid (not applicable)."""
        claim = MockClaim(cpt="99213", total_minutes=15, units=1)
        result = self.service.validate_8_minute_rule(claim)

        self.assertTrue(result.is_valid)
        self.assertIn("not time-based", result.message)

    def test_missing_cpt_returns_invalid(self):
        """Test missing CPT code returns invalid."""
        claim = MockClaim(cpt=None, total_minutes=15, units=1)
        result = self.service.validate_8_minute_rule(claim)

        self.assertFalse(result.is_valid)
        self.assertIn("missing CPT", result.message)

    def test_missing_minutes_returns_invalid(self):
        """Test missing treatment time returns invalid."""
        claim = MockClaim(cpt="97110", total_minutes=None, units=1)
        result = self.service.validate_8_minute_rule(claim)

        self.assertFalse(result.is_valid)
        self.assertIn("missing", result.message.lower())

    def test_missing_units_returns_invalid(self):
        """Test missing units returns invalid."""
        claim = MockClaim(cpt="97110", total_minutes=15, units=None)
        result = self.service.validate_8_minute_rule(claim)

        self.assertFalse(result.is_valid)
        self.assertIn("missing", result.message.lower())


class PTOTServiceKXThresholdTest(TestCase):
    """Tests for PTOTService KX threshold monitoring."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = PTOTService()

    def test_below_threshold_is_compliant(self):
        """Test charges below threshold are compliant."""
        patient = MockPatient()
        patient.claims = MockClaimManager(total_charges=Decimal("1500.00"))

        result = self.service.check_kx_threshold(patient)

        self.assertTrue(result.is_compliant)
        self.assertFalse(result.requires_kx)

    def test_above_threshold_without_kx_is_non_compliant(self):
        """Test charges above threshold without KX are non-compliant."""
        patient = MockPatient()
        patient.claims = MockClaimManager(total_charges=Decimal("2500.00"))

        claim = MockClaim(modifiers="GP")  # No KX modifier

        result = self.service.check_kx_threshold(patient, claim)

        self.assertFalse(result.is_compliant)
        self.assertTrue(result.requires_kx)
        self.assertEqual(result.severity, "critical")
        self.assertIn("MISSING KX", result.message)

    def test_above_threshold_with_kx_is_compliant(self):
        """Test charges above threshold with KX modifier are compliant."""
        patient = MockPatient()
        patient.claims = MockClaimManager(total_charges=Decimal("2500.00"))

        claim = MockClaim(modifiers="GP,KX")  # Has KX modifier

        result = self.service.check_kx_threshold(patient, claim)

        self.assertTrue(result.is_compliant)
        self.assertTrue(result.requires_kx)
        self.assertTrue(result.has_kx_modifier)

    def test_approaching_threshold_warning(self):
        """Test warning when approaching 90% of threshold."""
        patient = MockPatient()
        # 90% of $2410 = $2169
        patient.claims = MockClaimManager(total_charges=Decimal("2200.00"))

        result = self.service.check_kx_threshold(patient)

        self.assertTrue(result.is_compliant)  # Still compliant
        self.assertEqual(result.severity, "warning")
        self.assertIn("Approaching", result.message)

    def test_threshold_is_configurable(self):
        """Test therapy cap threshold is configurable."""
        custom_cap = Decimal("3000.00")
        service = PTOTService(therapy_cap=custom_cap)

        patient = MockPatient()
        patient.claims = MockClaimManager(total_charges=Decimal("2500.00"))

        result = service.check_kx_threshold(patient)

        # Below custom cap should be compliant
        self.assertTrue(result.is_compliant)
        self.assertFalse(result.requires_kx)

    def test_amount_over_calculated_correctly(self):
        """Test amount over threshold is calculated correctly."""
        patient = MockPatient()
        patient.claims = MockClaimManager(total_charges=Decimal("2600.00"))

        result = self.service.check_kx_threshold(patient)

        expected_over = Decimal("2600.00") - THERAPY_CAP_THRESHOLD
        self.assertEqual(result.amount_over, expected_over)


class PTOTServiceAnalyzeClaimsTest(TestCase):
    """Tests for PTOTService batch analysis."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = PTOTService()

    def test_analyze_empty_claims(self):
        """Test analyzing empty claims list."""
        results = self.service.analyze_claims([], create_alerts=False)

        self.assertEqual(results["total_claims"], 0)
        self.assertEqual(results["valid_claims"], 0)

    def test_analyze_counts_valid_claims(self):
        """Test counting valid claims."""
        claims = [
            MockClaim(cpt="97110", total_minutes=15, units=1),
            MockClaim(cpt="97110", total_minutes=23, units=2),
            MockClaim(cpt="97110", total_minutes=38, units=3),
        ]

        results = self.service.analyze_claims(claims, create_alerts=False)

        self.assertEqual(results["total_claims"], 3)
        self.assertEqual(results["valid_claims"], 3)
        self.assertEqual(results["overbilled_claims"], 0)
        self.assertEqual(results["underbilled_claims"], 0)

    def test_analyze_counts_overbilled_claims(self):
        """Test counting overbilled claims."""
        claims = [
            MockClaim(cpt="97110", total_minutes=15, units=2),  # Overbilled
            MockClaim(cpt="97110", total_minutes=15, units=1),  # Valid
        ]

        results = self.service.analyze_claims(claims, create_alerts=False)

        self.assertEqual(results["overbilled_claims"], 1)
        self.assertEqual(results["valid_claims"], 1)

    def test_analyze_counts_underbilled_claims(self):
        """Test counting underbilled claims."""
        claims = [
            MockClaim(cpt="97110", total_minutes=45, units=2),  # Underbilled
        ]

        results = self.service.analyze_claims(claims, create_alerts=False)

        self.assertEqual(results["underbilled_claims"], 1)

    def test_analyze_tracks_unit_difference(self):
        """Test total unit difference is tracked."""
        claims = [
            MockClaim(cpt="97110", total_minutes=15, units=3),  # +2 overbill
            MockClaim(cpt="97110", total_minutes=45, units=2),  # -1 underbill
        ]

        results = self.service.analyze_claims(claims, create_alerts=False)

        # Should be sum of absolute differences
        self.assertEqual(results["total_unit_difference"], 3)

    def test_analyze_counts_non_time_based(self):
        """Test non-time-based CPTs are counted separately."""
        claims = [
            MockClaim(cpt="99213", total_minutes=15, units=1),  # Non-time
            MockClaim(cpt="97110", total_minutes=15, units=1),  # Time-based
        ]

        results = self.service.analyze_claims(claims, create_alerts=False)

        self.assertEqual(results["non_time_based"], 1)
        self.assertEqual(results["valid_claims"], 1)


class EightMinuteRuleThresholdsTest(TestCase):
    """Tests for EIGHT_MINUTE_RULE_THRESHOLDS constant."""

    def test_threshold_ranges_are_valid(self):
        """Test threshold ranges are properly defined."""
        for units, (min_val, max_val) in EIGHT_MINUTE_RULE_THRESHOLDS.items():
            self.assertLess(min_val, max_val)
            self.assertGreater(units, 0)

    def test_threshold_ranges_are_contiguous(self):
        """Test threshold ranges don't have gaps."""
        sorted_units = sorted(EIGHT_MINUTE_RULE_THRESHOLDS.keys())

        for i in range(len(sorted_units) - 1):
            current_max = EIGHT_MINUTE_RULE_THRESHOLDS[sorted_units[i]][1]
            next_min = EIGHT_MINUTE_RULE_THRESHOLDS[sorted_units[i + 1]][0]
            self.assertEqual(
                next_min, current_max + 1,
                f"Gap between {sorted_units[i]} and {sorted_units[i+1]}"
            )
