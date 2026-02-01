"""
Tests for Imaging specialty module.

Story #17: Write tests for ImagingPAService
- Test PA requirement lookup
- Test authorization verification
- Test alert creation for missing PA
- Test documentation validation
- Test bulk import functionality
"""

from datetime import date

from django.test import TestCase

from upstream.products.imaging.models import ImagingPARequirement
from upstream.products.imaging.services import ImagingPAService


class MockClaim:
    """Mock claim object for testing."""

    def __init__(
        self,
        cpt=None,
        payer_name=None,
        authorization=None,
        service_date=None,
        specialty_metadata=None,
        customer=None,
    ):
        self.cpt = cpt
        self.payer_name = payer_name
        self.authorization = authorization
        self.service_date = service_date
        self.specialty_metadata = specialty_metadata or {}
        self.customer = customer
        self.id = 1


class MockAuthorization:
    """Mock authorization object for testing."""

    def __init__(
        self,
        status="approved",
        auth_start_date=None,
        auth_expiration_date=None,
    ):
        self.status = status
        self.auth_start_date = auth_start_date
        self.auth_expiration_date = auth_expiration_date
        self.id = 1


class MockCustomer:
    """Mock customer object for testing."""

    def __init__(self, customer_id=1):
        self.id = customer_id


class ImagingPARequirementModelTest(TestCase):
    """Tests for ImagingPARequirement model."""

    def test_create_pa_requirement(self):
        """Test creating PA requirement."""
        req = ImagingPARequirement.objects.create(
            payer="Aetna",
            cpt="72148",
            pa_required=True,
            rbm_provider="EVICORE",
            effective_date=date(2025, 1, 1),
        )
        self.assertEqual(req.payer, "Aetna")
        self.assertEqual(req.cpt, "72148")
        self.assertTrue(req.pa_required)
        self.assertEqual(req.rbm_provider, "EVICORE")

    def test_str_representation(self):
        """Test string representation."""
        req = ImagingPARequirement.objects.create(
            payer="BCBS",
            cpt="72141",
            pa_required=True,
            rbm_provider="AIM",
            effective_date=date(2025, 1, 1),
        )
        self.assertIn("BCBS", str(req))
        self.assertIn("72141", str(req))

    def test_is_active_current_requirement(self):
        """Test is_active for current requirement."""
        req = ImagingPARequirement.objects.create(
            payer="UHC",
            cpt="72148",
            pa_required=True,
            rbm_provider="EVICORE",
            effective_date=date(2020, 1, 1),
        )
        self.assertTrue(req.is_active)

    def test_is_active_future_requirement(self):
        """Test is_active for future requirement."""
        req = ImagingPARequirement.objects.create(
            payer="UHC",
            cpt="72149",
            pa_required=True,
            rbm_provider="EVICORE",
            effective_date=date(2030, 1, 1),
        )
        self.assertFalse(req.is_active)

    def test_is_active_expired_requirement(self):
        """Test is_active for expired requirement."""
        req = ImagingPARequirement.objects.create(
            payer="UHC",
            cpt="72150",
            pa_required=True,
            rbm_provider="EVICORE",
            effective_date=date(2020, 1, 1),
            end_date=date(2021, 12, 31),
        )
        self.assertFalse(req.is_active)

    def test_get_requirement_finds_active(self):
        """Test get_requirement finds active requirement."""
        ImagingPARequirement.objects.create(
            payer="Cigna",
            cpt="72148",
            pa_required=True,
            rbm_provider="CARECORE",
            effective_date=date(2020, 1, 1),
        )
        req = ImagingPARequirement.get_requirement("Cigna", "72148")
        self.assertIsNotNone(req)
        self.assertEqual(req.payer, "Cigna")

    def test_get_requirement_returns_none_for_unknown(self):
        """Test get_requirement returns None for unknown payer/CPT."""
        req = ImagingPARequirement.get_requirement("Unknown", "99999")
        self.assertIsNone(req)


class ImagingPARequirementBulkImportTest(TestCase):
    """Tests for bulk CSV import."""

    def test_bulk_import_creates_records(self):
        """Test bulk import creates records."""
        csv_data = [
            {
                "payer": "Aetna",
                "cpt": "72148",
                "pa_required": True,
                "rbm_provider": "EVICORE",
                "effective_date": "2025-01-01",
            },
            {
                "payer": "BCBS",
                "cpt": "72141",
                "pa_required": "yes",  # String boolean
                "rbm_provider": "AIM",
                "effective_date": "2025-01-01",
            },
        ]

        result = ImagingPARequirement.bulk_import_csv(csv_data)

        self.assertEqual(result["created"], 2)
        self.assertEqual(result["errors"], [])
        self.assertEqual(ImagingPARequirement.objects.count(), 2)

    def test_bulk_import_updates_existing(self):
        """Test bulk import updates existing records."""
        # Create initial record
        ImagingPARequirement.objects.create(
            payer="Aetna",
            cpt="72148",
            pa_required=True,
            rbm_provider="EVICORE",
            effective_date=date(2025, 1, 1),
        )

        # Import with same key but different RBM
        csv_data = [
            {
                "payer": "Aetna",
                "cpt": "72148",
                "pa_required": True,
                "rbm_provider": "AIM",
                "effective_date": "2025-01-01",
            },
        ]

        result = ImagingPARequirement.bulk_import_csv(csv_data)

        self.assertEqual(result["updated"], 1)
        self.assertEqual(result["created"], 0)

        req = ImagingPARequirement.objects.get(payer="Aetna", cpt="72148")
        self.assertEqual(req.rbm_provider, "AIM")

    def test_bulk_import_handles_errors(self):
        """Test bulk import handles errors gracefully."""
        csv_data = [
            {
                "payer": "Aetna",
                # Missing required cpt
                "pa_required": True,
                "effective_date": "2025-01-01",
            },
        ]

        result = ImagingPARequirement.bulk_import_csv(csv_data)

        self.assertEqual(result["created"], 0)
        self.assertEqual(len(result["errors"]), 1)


class ImagingPAServicePACheckTest(TestCase):
    """Tests for ImagingPAService PA checking."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = ImagingPAService()
        # Create PA requirement
        ImagingPARequirement.objects.create(
            payer="Aetna",
            cpt="72148",
            pa_required=True,
            rbm_provider="EVICORE",
            effective_date=date(2020, 1, 1),
        )

    def test_no_pa_required_for_unknown_cpt(self):
        """Test no PA required for CPT without requirement."""
        claim = MockClaim(cpt="99213", payer_name="Aetna")
        result = self.service.check_pa_required(claim)

        self.assertFalse(result.pa_required)
        self.assertTrue(result.is_compliant)

    def test_pa_required_without_auth_is_non_compliant(self):
        """Test PA required without authorization is non-compliant."""
        claim = MockClaim(cpt="72148", payer_name="Aetna")
        result = self.service.check_pa_required(claim)

        self.assertTrue(result.pa_required)
        self.assertFalse(result.has_authorization)
        self.assertFalse(result.is_compliant)
        self.assertEqual(result.severity, "critical")
        self.assertIn("MISSING PA", result.message)

    def test_pa_required_with_auth_is_compliant(self):
        """Test PA required with valid authorization is compliant."""
        auth = MockAuthorization(status="approved")
        claim = MockClaim(
            cpt="72148",
            payer_name="Aetna",
            authorization=auth,
        )
        result = self.service.check_pa_required(claim)

        self.assertTrue(result.pa_required)
        self.assertTrue(result.has_authorization)
        self.assertTrue(result.is_compliant)

    def test_pa_required_with_denied_auth_is_non_compliant(self):
        """Test PA required with denied authorization is non-compliant."""
        auth = MockAuthorization(status="denied")
        claim = MockClaim(
            cpt="72148",
            payer_name="Aetna",
            authorization=auth,
        )
        result = self.service.check_pa_required(claim)

        self.assertTrue(result.pa_required)
        self.assertFalse(result.has_authorization)
        self.assertFalse(result.is_compliant)

    def test_rbm_provider_in_result(self):
        """Test RBM provider is included in result."""
        claim = MockClaim(cpt="72148", payer_name="Aetna")
        result = self.service.check_pa_required(claim)

        self.assertEqual(result.rbm_provider, "EVICORE")


class ImagingPAServiceDocumentationTest(TestCase):
    """Tests for ImagingPAService documentation validation."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = ImagingPAService()

    def test_complete_documentation_is_valid(self):
        """Test complete documentation passes validation."""
        claim = MockClaim(
            specialty_metadata={
                "has_medical_necessity_docs": True,
                "clinical_justification": "Patient has chronic back pain",
                "icd10_codes": ["M54.5"],
            }
        )
        result = self.service.validate_documentation(claim)

        self.assertTrue(result.is_complete)
        self.assertEqual(result.missing_fields, [])

    def test_missing_necessity_docs_is_invalid(self):
        """Test missing medical necessity docs is invalid."""
        claim = MockClaim(
            specialty_metadata={
                "clinical_justification": "Back pain",
                "icd10_codes": ["M54.5"],
            }
        )
        result = self.service.validate_documentation(claim)

        self.assertFalse(result.is_complete)
        self.assertIn("has_medical_necessity_docs", result.missing_fields)

    def test_missing_justification_is_invalid(self):
        """Test missing clinical justification is invalid."""
        claim = MockClaim(
            specialty_metadata={
                "has_medical_necessity_docs": True,
                "icd10_codes": ["M54.5"],
            }
        )
        result = self.service.validate_documentation(claim)

        self.assertFalse(result.is_complete)
        self.assertIn("clinical_justification", result.missing_fields)

    def test_missing_icd10_is_invalid(self):
        """Test missing ICD-10 codes is invalid."""
        claim = MockClaim(
            specialty_metadata={
                "has_medical_necessity_docs": True,
                "clinical_justification": "Back pain",
            }
        )
        result = self.service.validate_documentation(claim)

        self.assertFalse(result.is_complete)
        self.assertIn("icd10_codes", result.missing_fields)

    def test_multiple_missing_fields_is_high_severity(self):
        """Test multiple missing fields results in high severity."""
        claim = MockClaim(specialty_metadata={})
        result = self.service.validate_documentation(claim)

        self.assertFalse(result.is_complete)
        self.assertEqual(result.severity, "high")
        self.assertEqual(len(result.missing_fields), 3)

    def test_single_missing_field_is_medium_severity(self):
        """Test single missing field results in medium severity."""
        claim = MockClaim(
            specialty_metadata={
                "has_medical_necessity_docs": True,
                "clinical_justification": "Back pain",
                # Missing icd10_codes
            }
        )
        result = self.service.validate_documentation(claim)

        self.assertEqual(result.severity, "medium")


class ImagingPAServiceAnalyzeClaimsTest(TestCase):
    """Tests for ImagingPAService batch analysis."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = ImagingPAService()
        ImagingPARequirement.objects.create(
            payer="Aetna",
            cpt="72148",
            pa_required=True,
            rbm_provider="EVICORE",
            effective_date=date(2020, 1, 1),
        )

    def test_analyze_empty_claims(self):
        """Test analyzing empty claims list."""
        results = self.service.analyze_claims([], create_alerts=False)

        self.assertEqual(results["total_claims"], 0)
        self.assertEqual(results["pa_required_claims"], 0)

    def test_analyze_counts_pa_required(self):
        """Test counting PA required claims."""
        claims = [
            MockClaim(cpt="72148", payer_name="Aetna"),
            MockClaim(cpt="99213", payer_name="Aetna"),  # No PA required
        ]

        results = self.service.analyze_claims(claims, create_alerts=False)

        self.assertEqual(results["total_claims"], 2)
        self.assertEqual(results["pa_required_claims"], 1)
        self.assertEqual(results["missing_pa_claims"], 1)

    def test_analyze_counts_compliant_claims(self):
        """Test counting compliant claims."""
        auth = MockAuthorization(status="approved")
        claims = [
            MockClaim(cpt="72148", payer_name="Aetna", authorization=auth),
        ]

        results = self.service.analyze_claims(claims, create_alerts=False)

        self.assertEqual(results["pa_compliant_claims"], 1)
        self.assertEqual(results["missing_pa_claims"], 0)
