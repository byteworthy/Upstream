"""
Comprehensive tests for DataQualityService.

Tests cover HIPAA-critical PHI detection, validation rules,
anomaly detection, quality metrics, and atomic rollback.
"""

from django.test import TestCase
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from upstream.models import Customer, Upload, ClaimRecord
from upstream.core.data_quality_service import DataQualityService
from upstream.core.validation_models import ValidationRule, ValidationResult
from upstream.core.tenant import customer_context


class PHIDetectionTests(TestCase):
    """
    Test HIPAA-critical PHI detection functionality.

    NOTE: This test class intentionally contains fake PHI patterns
    (SSN, MRN, phone numbers) as test fixtures to validate detection logic.
    These are NOT real patient data.
    """

    def setUp(self):
        self.customer = Customer.objects.create(name="Test Hospital")
        self.service = DataQualityService(self.customer)

        # Create PHI detection rule
        with customer_context(self.customer):
            self.phi_rule = ValidationRule.objects.create(
                customer=self.customer,
                name="PHI Detection",
                code="PHI_001",
                rule_type="phi_detection",
                field_name="notes",
                severity="error",
                enabled=True,
                error_message_template="Potential {phi_type} detected in {field}",
                execution_order=1,
            )

    def test_ssn_detection_positive(self):
        """Test SSN pattern is correctly detected."""
        with customer_context(self.customer):
            # Test fixture: Fake SSN for PHI detection validation
            row_data = {"notes": "Patient SSN is 123-45-6789"}  # nosec
            result = self.service._validate_phi(self.phi_rule, row_data, "notes")

            self.assertFalse(result["passed"])
            self.assertIn("SSN", result["error_message"])
            self.assertEqual(result["field_value"], "[REDACTED]")

    def test_ssn_detection_negative(self):
        """Test normal text doesn't trigger false SSN detection."""
        with customer_context(self.customer):
            row_data = {"notes": "Claim 123-456-789 processed"}
            result = self.service._validate_phi(self.phi_rule, row_data, "notes")

            self.assertTrue(result["passed"])

    def test_mrn_detection_positive(self):
        """Test medical record number pattern is detected."""
        with customer_context(self.customer):
            row_data = {"notes": "MRN: AB123456"}
            result = self.service._validate_phi(self.phi_rule, row_data, "notes")

            self.assertFalse(result["passed"])
            self.assertIn("MRN", result["error_message"])

    def test_phone_detection_positive(self):
        """Test phone number pattern is detected."""
        with customer_context(self.customer):
            row_data = {"notes": "Contact: 555-123-4567"}
            result = self.service._validate_phi(self.phi_rule, row_data, "notes")

            self.assertFalse(result["passed"])
            self.assertIn("Phone", result["error_message"])

    def test_phi_empty_field(self):
        """Test empty field passes PHI check."""
        with customer_context(self.customer):
            row_data = {"notes": ""}
            result = self.service._validate_phi(self.phi_rule, row_data, "notes")

            self.assertTrue(result["passed"])

    def test_phi_multiple_patterns(self):
        """Test detection stops at first PHI pattern found."""
        with customer_context(self.customer):
            # Test fixture: Fake PHI patterns for detection validation
            row_data = {"notes": "SSN: 123-45-6789, Phone: 555-123-4567"}  # nosec
            result = self.service._validate_phi(self.phi_rule, row_data, "notes")

            self.assertFalse(result["passed"])
            # Should detect SSN first (earlier in pattern list)
            self.assertIn("SSN", result["error_message"])


class RequiredFieldValidationTests(TestCase):
    """Test required field validation."""

    def setUp(self):
        self.customer = Customer.objects.create(name="Test Clinic")
        self.service = DataQualityService(self.customer)

        with customer_context(self.customer):
            self.rule = ValidationRule.objects.create(
                customer=self.customer,
                name="Payer Required",
                code="REQ_001",
                rule_type="required_field",
                field_name="payer",
                severity="error",
                enabled=True,
                error_message_template="{field} is required",
                execution_order=1,
            )

    def test_required_field_present(self):
        """Test required field with valid value passes."""
        with customer_context(self.customer):
            row_data = {"payer": "UnitedHealthcare"}
            result = self.service._validate_required_field(self.rule, row_data, "payer")

            self.assertTrue(result["passed"])

    def test_required_field_missing(self):
        """Test missing required field fails."""
        with customer_context(self.customer):
            row_data = {}
            result = self.service._validate_required_field(self.rule, row_data, "payer")

            self.assertFalse(result["passed"])
            self.assertIn("payer is required", result["error_message"])

    def test_required_field_none(self):
        """Test None value fails required field check."""
        with customer_context(self.customer):
            row_data = {"payer": None}
            result = self.service._validate_required_field(self.rule, row_data, "payer")

            self.assertFalse(result["passed"])

    def test_required_field_empty_string(self):
        """Test empty string fails required field check."""
        with customer_context(self.customer):
            row_data = {"payer": "   "}
            result = self.service._validate_required_field(self.rule, row_data, "payer")

            self.assertFalse(result["passed"])


class FormatValidationTests(TestCase):
    """Test format validation with regex patterns."""

    def setUp(self):
        self.customer = Customer.objects.create(name="Test Practice")
        self.service = DataQualityService(self.customer)

        with customer_context(self.customer):
            self.rule = ValidationRule.objects.create(
                customer=self.customer,
                name="CPT Format",
                code="FMT_001",
                rule_type="format_check",
                field_name="cpt",
                severity="error",
                enabled=True,
                error_message_template=(
                    "{field} value '{value}' doesn't match pattern {pattern}"
                ),
                validation_logic={"pattern": r"^\d{5}$"},
                execution_order=1,
            )

    def test_format_valid_pattern(self):
        """Test value matching regex pattern passes."""
        with customer_context(self.customer):
            row_data = {"cpt": "99213"}
            result = self.service._validate_format(
                self.rule, row_data, "cpt", {"pattern": r"^\d{5}$"}
            )

            self.assertTrue(result["passed"])

    def test_format_invalid_pattern(self):
        """Test value not matching regex pattern fails."""
        with customer_context(self.customer):
            row_data = {"cpt": "ABC123"}
            result = self.service._validate_format(
                self.rule, row_data, "cpt", {"pattern": r"^\d{5}$"}
            )

            self.assertFalse(result["passed"])
            self.assertIn("doesn't match pattern", result["error_message"])

    def test_format_empty_optional(self):
        """Test empty value passes for optional fields."""
        with customer_context(self.customer):
            row_data = {"cpt": ""}
            result = self.service._validate_format(
                self.rule, row_data, "cpt", {"pattern": r"^\d{5}$"}
            )

            self.assertTrue(result["passed"])


class RangeValidationTests(TestCase):
    """Test numeric range validation."""

    def setUp(self):
        self.customer = Customer.objects.create(name="Test Group")
        self.service = DataQualityService(self.customer)

        with customer_context(self.customer):
            self.rule = ValidationRule.objects.create(
                customer=self.customer,
                name="Amount Range",
                code="RNG_001",
                rule_type="range_check",
                field_name="allowed_amount",
                severity="error",
                enabled=True,
                error_message_template="{field} out of range",
                validation_logic={"min": 0, "max": 100000},
                execution_order=1,
            )

    def test_range_within_bounds(self):
        """Test value within range passes."""
        with customer_context(self.customer):
            row_data = {"allowed_amount": "500.00"}
            result = self.service._validate_range(
                self.rule,
                row_data,
                "allowed_amount",
                {"min": 0, "max": 100000},
            )

            self.assertTrue(result["passed"])

    def test_range_below_minimum(self):
        """Test value below minimum fails."""
        with customer_context(self.customer):
            row_data = {"allowed_amount": "-50.00"}
            result = self.service._validate_range(
                self.rule,
                row_data,
                "allowed_amount",
                {"min": 0, "max": 100000},
            )

            self.assertFalse(result["passed"])
            self.assertIn("below minimum", result["error_message"])

    def test_range_above_maximum(self):
        """Test value above maximum fails."""
        with customer_context(self.customer):
            row_data = {"allowed_amount": "150000.00"}
            result = self.service._validate_range(
                self.rule,
                row_data,
                "allowed_amount",
                {"min": 0, "max": 100000},
            )

            self.assertFalse(result["passed"])
            self.assertIn("exceeds maximum", result["error_message"])

    def test_range_non_numeric(self):
        """Test non-numeric value fails."""
        with customer_context(self.customer):
            row_data = {"allowed_amount": "INVALID"}
            result = self.service._validate_range(
                self.rule,
                row_data,
                "allowed_amount",
                {"min": 0, "max": 100000},
            )

            self.assertFalse(result["passed"])
            self.assertIn("must be a number", result["error_message"])

    def test_range_empty_optional(self):
        """Test empty value passes for optional fields."""
        with customer_context(self.customer):
            row_data = {"allowed_amount": ""}
            result = self.service._validate_range(
                self.rule,
                row_data,
                "allowed_amount",
                {"min": 0, "max": 100000},
            )

            self.assertTrue(result["passed"])


class DateLogicValidationTests(TestCase):
    """Test date logic validation."""

    def setUp(self):
        self.customer = Customer.objects.create(name="Test System")
        self.service = DataQualityService(self.customer)

        with customer_context(self.customer):
            self.rule = ValidationRule.objects.create(
                customer=self.customer,
                name="Decided After Submitted",
                code="DT_001",
                rule_type="date_logic",
                severity="error",
                enabled=True,
                error_message_template="Date logic error",
                validation_logic={
                    "date1_field": "decided_date",
                    "date2_field": "submitted_date",
                    "comparison": "after",
                },
                execution_order=1,
            )

    def test_date_logic_after_valid(self):
        """Test decided_date after submitted_date passes."""
        with customer_context(self.customer):
            row_data = {
                "submitted_date": datetime(2023, 1, 15).date(),
                "decided_date": datetime(2023, 1, 20).date(),
            }
            result = self.service._validate_date_logic(
                self.rule,
                row_data,
                {
                    "date1_field": "decided_date",
                    "date2_field": "submitted_date",
                    "comparison": "after",
                },
            )

            self.assertTrue(result["passed"])

    def test_date_logic_after_invalid(self):
        """Test decided_date before submitted_date fails."""
        with customer_context(self.customer):
            row_data = {
                "submitted_date": datetime(2023, 1, 20).date(),
                "decided_date": datetime(2023, 1, 15).date(),
            }
            result = self.service._validate_date_logic(
                self.rule,
                row_data,
                {
                    "date1_field": "decided_date",
                    "date2_field": "submitted_date",
                    "comparison": "after",
                },
            )

            self.assertFalse(result["passed"])
            self.assertIn("must be after", result["error_message"])

    def test_date_logic_before_valid(self):
        """Test before comparison works correctly."""
        with customer_context(self.customer):
            row_data = {
                "submitted_date": datetime(2023, 1, 15).date(),
                "decided_date": datetime(2023, 1, 20).date(),
            }
            result = self.service._validate_date_logic(
                self.rule,
                row_data,
                {
                    "date1_field": "submitted_date",
                    "date2_field": "decided_date",
                    "comparison": "before",
                },
            )

            self.assertTrue(result["passed"])

    def test_date_logic_missing_dates(self):
        """Test missing dates are skipped."""
        with customer_context(self.customer):
            row_data = {"submitted_date": None, "decided_date": None}
            result = self.service._validate_date_logic(
                self.rule,
                row_data,
                {
                    "date1_field": "decided_date",
                    "date2_field": "submitted_date",
                    "comparison": "after",
                },
            )

            self.assertTrue(result["passed"])


class ReferenceCheckValidationTests(TestCase):
    """Test reference data validation."""

    def setUp(self):
        self.customer = Customer.objects.create(name="Test Network")
        self.service = DataQualityService(self.customer)

        with customer_context(self.customer):
            self.rule = ValidationRule.objects.create(
                customer=self.customer,
                name="Valid Outcome",
                code="REF_001",
                rule_type="reference_check",
                field_name="outcome",
                severity="error",
                enabled=True,
                error_message_template="{field} invalid",
                validation_logic={"allowed_values": ["PAID", "DENIED", "PENDING"]},
                execution_order=1,
            )

    def test_reference_valid_value(self):
        """Test value in allowed list passes."""
        with customer_context(self.customer):
            row_data = {"outcome": "PAID"}
            result = self.service._validate_reference(
                self.rule,
                row_data,
                "outcome",
                {"allowed_values": ["PAID", "DENIED", "PENDING"]},
            )

            self.assertTrue(result["passed"])

    def test_reference_invalid_value(self):
        """Test value not in allowed list fails."""
        with customer_context(self.customer):
            row_data = {"outcome": "UNKNOWN"}
            result = self.service._validate_reference(
                self.rule,
                row_data,
                "outcome",
                {"allowed_values": ["PAID", "DENIED", "PENDING"]},
            )

            self.assertFalse(result["passed"])
            self.assertIn("not in allowed list", result["error_message"])

    def test_reference_empty_optional(self):
        """Test empty value passes."""
        with customer_context(self.customer):
            row_data = {"outcome": ""}
            result = self.service._validate_reference(
                self.rule,
                row_data,
                "outcome",
                {"allowed_values": ["PAID", "DENIED", "PENDING"]},
            )

            self.assertTrue(result["passed"])


class BusinessRuleValidationTests(TestCase):
    """Test business rule validation."""

    def setUp(self):
        self.customer = Customer.objects.create(name="Test Entity")
        self.service = DataQualityService(self.customer)

        with customer_context(self.customer):
            self.rule = ValidationRule.objects.create(
                customer=self.customer,
                name="Denial Requires Reason",
                code="BUS_001",
                rule_type="business_rule",
                severity="error",
                enabled=True,
                error_message_template="Business rule violation",
                validation_logic={"rule_name": "denial_requires_reason"},
                execution_order=1,
            )

    def test_business_rule_denial_with_reason(self):
        """Test denied claim with reason passes."""
        with customer_context(self.customer):
            row_data = {
                "outcome": "DENIED",
                "denial_reason_code": "CO-45",
            }
            result = self.service._validate_business_rule(
                self.rule,
                row_data,
                {"rule_name": "denial_requires_reason"},
            )

            self.assertTrue(result["passed"])

    def test_business_rule_denial_without_reason(self):
        """Test denied claim without reason fails."""
        with customer_context(self.customer):
            row_data = {
                "outcome": "DENIED",
                "denial_reason_code": "",
            }
            result = self.service._validate_business_rule(
                self.rule,
                row_data,
                {"rule_name": "denial_requires_reason"},
            )

            self.assertFalse(result["passed"])
            self.assertIn("must have a denial reason", result["error_message"])

    def test_business_rule_paid_no_reason_needed(self):
        """Test paid claim doesn't require denial reason."""
        with customer_context(self.customer):
            row_data = {
                "outcome": "PAID",
                "denial_reason_code": "",
            }
            result = self.service._validate_business_rule(
                self.rule,
                row_data,
                {"rule_name": "denial_requires_reason"},
            )

            self.assertTrue(result["passed"])


class VolumeAnomalyDetectionTests(TestCase):
    """Test volume anomaly detection."""

    def setUp(self):
        self.customer = Customer.objects.create(name="Test Center")
        self.service = DataQualityService(self.customer)

    def test_volume_anomaly_high_z_score(self):
        """Test high z-score triggers volume anomaly."""
        with customer_context(self.customer):
            # Create historical uploads with varying sizes (avg ~1000, std ~50)
            row_counts = [950, 980, 1000, 1020, 1050, 990, 1010, 1030, 970, 1000]
            for i, count in enumerate(row_counts):
                Upload.objects.create(
                    customer=self.customer,
                    filename=f"test{i}.csv",
                    row_count=count,
                    status="success",
                    uploaded_at=timezone.now() - timedelta(days=i + 1),
                )

            # Current upload with 5000 rows (much higher than normal)
            upload = Upload.objects.create(
                customer=self.customer,
                filename="anomaly.csv",
                row_count=5000,
                status="processing",
                uploaded_at=timezone.now(),
            )

            result = self.service._detect_volume_anomaly(upload, 5000)

            self.assertIsNotNone(result)
            self.assertEqual(result["anomaly_type"], "volume_anomaly")
            self.assertGreater(result["statistical_details"]["z_score"], 3)

    def test_volume_anomaly_normal_volume(self):
        """Test normal volume doesn't trigger anomaly."""
        with customer_context(self.customer):
            # Create historical uploads
            for i in range(10):
                Upload.objects.create(
                    customer=self.customer,
                    filename=f"test{i}.csv",
                    row_count=1000,
                    status="success",
                    uploaded_at=timezone.now() - timedelta(days=i + 1),
                )

            upload = Upload.objects.create(
                customer=self.customer,
                filename="normal.csv",
                row_count=1050,
                status="processing",
                uploaded_at=timezone.now(),
            )

            result = self.service._detect_volume_anomaly(upload, 1050)

            self.assertIsNone(result)

    def test_volume_anomaly_no_history(self):
        """Test no anomaly when no historical data."""
        with customer_context(self.customer):
            upload = Upload.objects.create(
                customer=self.customer,
                filename="first.csv",
                row_count=5000,
                status="processing",
                uploaded_at=timezone.now(),
            )

            result = self.service._detect_volume_anomaly(upload, 5000)

            self.assertIsNone(result)


class MissingDataSpikeDetectionTests(TestCase):
    """Test missing data spike detection."""

    def setUp(self):
        self.customer = Customer.objects.create(name="Test Org")
        self.service = DataQualityService(self.customer)

    def test_missing_data_spike_high_rate(self):
        """Test high missing rate triggers spike detection."""
        with customer_context(self.customer):
            # 100 rows with 60% missing payer
            rows_data = []
            for i in range(100):
                rows_data.append(
                    {
                        "payer": "" if i < 60 else "UnitedHealthcare",
                        "cpt": "99213",
                        "outcome": "PAID",
                    }
                )

            result = self.service._detect_missing_data_spike(rows_data)

            self.assertIsNotNone(result)
            self.assertEqual(result["anomaly_type"], "missing_data_spike")
            self.assertEqual(result["field_name"], "payer")
            self.assertGreater(result["anomaly_score"], 0.5)

    def test_missing_data_spike_low_rate(self):
        """Test low missing rate doesn't trigger spike."""
        with customer_context(self.customer):
            # 100 rows with 10% missing
            rows_data = []
            for i in range(100):
                rows_data.append(
                    {
                        "payer": "" if i < 10 else "UnitedHealthcare",
                        "cpt": "99213",
                    }
                )

            result = self.service._detect_missing_data_spike(rows_data)

            self.assertIsNone(result)

    def test_missing_data_spike_empty_dataset(self):
        """Test empty dataset returns None."""
        with customer_context(self.customer):
            result = self.service._detect_missing_data_spike([])
            self.assertIsNone(result)


class DistributionShiftDetectionTests(TestCase):
    """Test distribution shift detection."""

    def setUp(self):
        self.customer = Customer.objects.create(name="Test Provider")
        self.service = DataQualityService(self.customer)

    def test_distribution_shift_high_denial_rate(self):
        """Test unusually high denial rate triggers shift detection."""
        with customer_context(self.customer):
            # 100 rows with 50% denied (expected ~15%)
            rows_data = []
            for i in range(100):
                rows_data.append(
                    {
                        "outcome": "DENIED" if i < 50 else "PAID",
                    }
                )

            results = self.service._detect_distribution_shift(rows_data)

            self.assertGreater(len(results), 0)
            denied_anomaly = next(
                (r for r in results if r["statistical_details"]["outcome"] == "DENIED"),
                None,
            )
            self.assertIsNotNone(denied_anomaly)
            self.assertEqual(denied_anomaly["anomaly_type"], "distribution_shift")

    def test_distribution_shift_normal_distribution(self):
        """Test normal distribution doesn't trigger shift."""
        with customer_context(self.customer):
            # 100 rows with expected distribution
            rows_data = []
            for i in range(100):
                if i < 75:
                    outcome = "PAID"
                elif i < 90:
                    outcome = "DENIED"
                else:
                    outcome = "OTHER"
                rows_data.append({"outcome": outcome})

            results = self.service._detect_distribution_shift(rows_data)

            self.assertEqual(len(results), 0)


class QualityMetricsTests(TestCase):
    """Test quality metric calculation."""

    def setUp(self):
        self.customer = Customer.objects.create(name="Test Facility")
        self.service = DataQualityService(self.customer)

    def test_completeness_metric(self):
        """Test completeness metric calculation."""
        with customer_context(self.customer):
            upload = Upload.objects.create(
                customer=self.customer,
                filename="test.csv",
                status="success",
                uploaded_at=timezone.now(),
            )

            # Create 10 claims - 8 complete, 2 incomplete
            for i in range(8):
                ClaimRecord.objects.create(
                    customer=self.customer,
                    upload=upload,
                    payer="UnitedHealthcare",
                    cpt="99213",
                    allowed_amount=Decimal("100.00"),
                    submitted_date=timezone.now().date(),
                    decided_date=timezone.now().date(),
                    outcome="PAID",
                    processed_at=timezone.now(),
                    submitted_via="csv_upload",
                )

            for i in range(2):
                ClaimRecord.objects.create(
                    customer=self.customer,
                    upload=upload,
                    payer="",  # Incomplete
                    cpt="99213",
                    allowed_amount=Decimal("100.00"),
                    submitted_date=timezone.now().date(),
                    decided_date=timezone.now().date(),
                    outcome="PAID",
                    processed_at=timezone.now(),
                    submitted_via="csv_upload",
                )

            start_date = timezone.now().date()
            end_date = timezone.now().date()

            metrics = self.service.calculate_quality_metrics(start_date, end_date)

            completeness = next(
                (m for m in metrics if m["metric_type"] == "completeness"), None
            )

            self.assertIsNotNone(completeness)
            self.assertEqual(completeness["score"], 0.8)
            self.assertEqual(completeness["sample_size"], 10)
            self.assertEqual(completeness["passed_count"], 8)

    def test_validity_metric(self):
        """Test validity metric calculation."""
        with customer_context(self.customer):
            upload = Upload.objects.create(
                customer=self.customer,
                filename="test.csv",
                status="success",
                uploaded_at=timezone.now(),
            )

            # 7 passed validation, 3 failed
            for i in range(7):
                ClaimRecord.objects.create(
                    customer=self.customer,
                    upload=upload,
                    payer="UnitedHealthcare",
                    cpt="99213",
                    allowed_amount=Decimal("100.00"),
                    submitted_date=timezone.now().date(),
                    decided_date=timezone.now().date(),
                    outcome="PAID",
                    validation_passed=True,
                    processed_at=timezone.now(),
                    submitted_via="csv_upload",
                )

            for i in range(3):
                ClaimRecord.objects.create(
                    customer=self.customer,
                    upload=upload,
                    payer="UnitedHealthcare",
                    cpt="99213",
                    allowed_amount=Decimal("100.00"),
                    submitted_date=timezone.now().date(),
                    decided_date=timezone.now().date(),
                    outcome="DENIED",
                    validation_passed=False,
                    processed_at=timezone.now(),
                    submitted_via="csv_upload",
                )

            start_date = timezone.now().date()
            end_date = timezone.now().date()

            metrics = self.service.calculate_quality_metrics(start_date, end_date)

            validity = next(
                (m for m in metrics if m["metric_type"] == "validity"), None
            )

            self.assertIsNotNone(validity)
            self.assertEqual(validity["score"], 0.7)
            self.assertEqual(validity["sample_size"], 10)

    def test_timeliness_metric(self):
        """Test timeliness metric calculation."""
        with customer_context(self.customer):
            # Upload same day as data (created for metrics query)
            Upload.objects.create(  # noqa: F841
                customer=self.customer,
                filename="fresh.csv",
                status="success",
                date_max=timezone.now().date(),
                uploaded_at=timezone.now(),
            )

            start_date = timezone.now().date()
            end_date = timezone.now().date()

            metrics = self.service.calculate_quality_metrics(start_date, end_date)

            timeliness = next(
                (m for m in metrics if m["metric_type"] == "timeliness"), None
            )

            self.assertIsNotNone(timeliness)
            self.assertEqual(timeliness["score"], 1.0)


class UploadValidationIntegrationTests(TestCase):
    """Integration tests for full upload validation."""

    def setUp(self):
        self.customer = Customer.objects.create(name="Integration Test")
        self.service = DataQualityService(self.customer)

        with customer_context(self.customer):
            # Create validation rules
            ValidationRule.objects.create(
                customer=self.customer,
                name="Payer Required",
                code="REQ_001",
                rule_type="required_field",
                field_name="payer",
                severity="error",
                enabled=True,
                error_message_template="{field} is required",
                execution_order=1,
            )

            ValidationRule.objects.create(
                customer=self.customer,
                name="PHI Check",
                code="PHI_001",
                rule_type="phi_detection",
                field_name="notes",
                severity="error",
                enabled=True,
                error_message_template="PHI detected",
                execution_order=2,
            )

    def test_validate_upload_success(self):
        """Test successful upload validation."""
        with customer_context(self.customer):
            upload = Upload.objects.create(
                customer=self.customer,
                filename="valid.csv",
                status="processing",
                uploaded_at=timezone.now(),
            )

            rows_data = [
                {"payer": "UnitedHealthcare", "notes": "Clean notes"},
                {"payer": "Aetna", "notes": "No PHI here"},
            ]

            result = self.service.validate_upload(upload, rows_data)

            self.assertEqual(result["summary"]["total_rows"], 2)
            self.assertEqual(result["summary"]["accepted_rows"], 2)
            self.assertEqual(result["summary"]["rejected_rows"], 0)

            # Check quality report created
            self.assertIsNotNone(result["quality_report"])
            self.assertEqual(result["quality_report"].total_rows, 2)

    def test_validate_upload_with_errors(self):
        """Test upload validation with validation errors."""
        with customer_context(self.customer):
            upload = Upload.objects.create(
                customer=self.customer,
                filename="errors.csv",
                status="processing",
                uploaded_at=timezone.now(),
            )

            # Test fixture: Second row contains fake SSN for PHI validation
            rows_data = [  # nosec
                {"payer": "", "notes": "Missing payer"},
                {"payer": "Aetna", "notes": "SSN: 123-45-6789"},
                {"payer": "Cigna", "notes": "Clean"},
            ]

            result = self.service.validate_upload(upload, rows_data)

            self.assertEqual(result["summary"]["total_rows"], 3)
            self.assertEqual(result["summary"]["accepted_rows"], 1)
            self.assertEqual(result["summary"]["rejected_rows"], 2)

            # Check error tracking
            self.assertIn("required_field", result["summary"]["errors_by_type"])
            self.assertIn("phi_detection", result["summary"]["errors_by_type"])

    def test_validate_upload_atomic_rollback(self):
        """Test transaction rollback on validation error."""
        with customer_context(self.customer):
            upload = Upload.objects.create(
                customer=self.customer,
                filename="rollback.csv",
                status="processing",
                uploaded_at=timezone.now(),
            )

            initial_result_count = ValidationResult.objects.count()

            # Mock an exception during validation
            with patch.object(
                self.service,
                "_detect_upload_anomalies",
                side_effect=Exception("Test error"),
            ):
                with self.assertRaises(Exception):
                    self.service.validate_upload(
                        upload,
                        [{"payer": "Test", "notes": "Test"}],
                    )

            # Ensure no ValidationResults were created (rollback worked)
            final_result_count = ValidationResult.objects.count()
            self.assertEqual(initial_result_count, final_result_count)
