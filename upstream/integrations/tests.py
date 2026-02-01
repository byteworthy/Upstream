"""
Tests for EHR integration models and admin functionality.

Milestone 04: EHR Integrations
"""

from django.test import TestCase
from django.contrib.admin.sites import AdminSite
from django.utils import timezone

from upstream.test_fixtures import TenantTestMixin
from upstream.integrations.models import EHRConnection, EHRSyncLog
from upstream.admin import EHRConnectionAdmin, EHRSyncLogAdmin


class EHRConnectionModelTestCase(TenantTestMixin, TestCase):
    """Tests for EHRConnection model."""

    def setUp(self):
        super().setUp()
        self.customer = self.create_customer("Test Hospital")

    def test_create_epic_connection(self):
        """Test creating an Epic FHIR R4 connection."""
        connection = self.create_ehr_connection(
            customer=self.customer,
            name="Main Hospital Epic",
            ehr_type="epic",
            client_id="epic-client-id",
            client_secret="epic-client-secret",
            oauth_endpoint="https://fhir.epic.com/oauth2/token",
            fhir_endpoint="https://fhir.epic.com/api/FHIR/R4",
        )

        self.assertIsNotNone(connection)
        self.assertEqual(connection.customer, self.customer)
        self.assertEqual(connection.ehr_type, "epic")
        self.assertEqual(connection.name, "Main Hospital Epic")
        self.assertTrue(connection.enabled)

    def test_create_cerner_connection(self):
        """Test creating a Cerner/Oracle Health connection."""
        connection = self.create_ehr_connection(
            customer=self.customer,
            name="Cerner Integration",
            ehr_type="cerner",
            client_id="cerner-client-id",
            client_secret="cerner-client-secret",
            oauth_endpoint="https://fhir.cerner.com/oauth2/token",
            fhir_endpoint="https://fhir.cerner.com/api/FHIR/R4",
        )

        self.assertEqual(connection.ehr_type, "cerner")
        self.assertEqual(connection.get_ehr_type_display(), "Cerner/Oracle Health")

    def test_create_athena_connection(self):
        """Test creating an athenahealth connection."""
        connection = self.create_ehr_connection(
            customer=self.customer,
            name="Athena Integration",
            ehr_type="athena",
            client_id="athena-client-id",
            client_secret="athena-client-secret",
            oauth_endpoint="https://api.athenahealth.com/oauth2/token",
            fhir_endpoint="https://api.athenahealth.com/fhir/r4",
        )

        self.assertEqual(connection.ehr_type, "athena")
        self.assertEqual(connection.get_ehr_type_display(), "athenahealth")

    def test_client_secret_encrypted(self):
        """Test that client_secret is encrypted at rest."""
        connection = self.create_ehr_connection(
            customer=self.customer,
            client_secret="super-secret-value",
        )

        # Re-fetch from database to ensure encryption works
        connection.refresh_from_db()

        # The encrypted field should still return the original value when accessed
        self.assertEqual(connection.client_secret, "super-secret-value")

    def test_masked_client_secret(self):
        """Test masked_client_secret property returns masked value."""
        connection = self.create_ehr_connection(
            customer=self.customer,
            client_secret="super-secret-value",
        )

        # Should return masked format
        masked = connection.masked_client_secret
        self.assertIsNotNone(masked)
        self.assertIn("*", masked)
        self.assertNotIn("super-secret-value", masked)

    def test_unique_together_customer_name(self):
        """Test that customer + name is unique."""
        self.create_ehr_connection(
            customer=self.customer,
            name="Unique Connection",
        )

        # Creating another with same name should fail
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            self.create_ehr_connection(
                customer=self.customer,
                name="Unique Connection",
            )

    def test_health_status_choices(self):
        """Test health status field choices."""
        for status in ["healthy", "degraded", "unhealthy", "unknown"]:
            connection = self.create_ehr_connection(
                customer=self.customer,
                name=f"Connection {status}",
                health_status=status,
            )
            self.assertEqual(connection.health_status, status)

    def test_connection_str_representation(self):
        """Test string representation of EHRConnection."""
        connection = self.create_ehr_connection(
            customer=self.customer,
            name="Test Epic",
            ehr_type="epic",
        )

        str_repr = str(connection)
        self.assertIn("Test Epic", str_repr)
        self.assertIn("Epic FHIR R4", str_repr)
        self.assertIn(self.customer.name, str_repr)


class EHRSyncLogModelTestCase(TenantTestMixin, TestCase):
    """Tests for EHRSyncLog model."""

    def setUp(self):
        super().setUp()
        self.customer = self.create_customer("Test Hospital")
        self.connection = self.create_ehr_connection(
            customer=self.customer,
            name="Test Connection",
        )

    def test_create_sync_log_success(self):
        """Test creating a successful sync log."""
        sync_log = self.create_ehr_sync_log(
            connection=self.connection,
            status="success",
            records_fetched=100,
            records_created=95,
            records_updated=3,
            records_skipped=2,
        )

        self.assertIsNotNone(sync_log)
        self.assertEqual(sync_log.connection, self.connection)
        self.assertEqual(sync_log.status, "success")
        self.assertEqual(sync_log.records_fetched, 100)
        self.assertEqual(sync_log.records_created, 95)

    def test_create_sync_log_error(self):
        """Test creating an error sync log."""
        sync_log = self.create_ehr_sync_log(
            connection=self.connection,
            status="error",
            records_fetched=0,
            records_created=0,
            error_message="Connection timeout",
        )

        self.assertEqual(sync_log.status, "error")
        self.assertEqual(sync_log.error_message, "Connection timeout")

    def test_create_sync_log_partial(self):
        """Test creating a partial success sync log."""
        sync_log = self.create_ehr_sync_log(
            connection=self.connection,
            status="partial",
            records_fetched=50,
            records_created=45,
            error_message="Rate limit reached after 50 records",
        )

        self.assertEqual(sync_log.status, "partial")
        self.assertIsNotNone(sync_log.error_message)

    def test_duration_seconds_property(self):
        """Test duration_seconds property calculation."""
        sync_log = self.create_ehr_sync_log(
            connection=self.connection,
        )

        # Set completed_at to calculate duration
        sync_log.completed_at = sync_log.started_at + timezone.timedelta(seconds=45)
        sync_log.save()

        self.assertAlmostEqual(sync_log.duration_seconds, 45, places=1)

    def test_duration_seconds_none_when_incomplete(self):
        """Test duration_seconds is None when not completed."""
        sync_log = self.create_ehr_sync_log(
            connection=self.connection,
            status="error",
            completed_at=None,
        )

        self.assertIsNone(sync_log.duration_seconds)

    def test_sync_log_ordering(self):
        """Test sync logs are ordered by started_at descending."""
        # Create multiple sync logs
        log1 = self.create_ehr_sync_log(connection=self.connection)
        log2 = self.create_ehr_sync_log(connection=self.connection)
        log3 = self.create_ehr_sync_log(connection=self.connection)

        logs = list(EHRSyncLog.objects.filter(connection=self.connection))

        # Most recent should be first
        self.assertEqual(logs[0].id, log3.id)
        self.assertEqual(logs[2].id, log1.id)

    def test_sync_log_str_representation(self):
        """Test string representation of EHRSyncLog."""
        sync_log = self.create_ehr_sync_log(
            connection=self.connection,
            status="success",
        )

        str_repr = str(sync_log)
        self.assertIn("Sync", str_repr)
        self.assertIn(self.connection.name, str_repr)
        self.assertIn("success", str_repr)


class EHRConnectionAdminTestCase(TenantTestMixin, TestCase):
    """Tests for EHRConnection admin interface."""

    def setUp(self):
        super().setUp()
        self.site = AdminSite()
        self.admin = EHRConnectionAdmin(EHRConnection, self.site)
        self.customer = self.create_customer("Test Hospital")

    def test_list_display_fields(self):
        """Test that list_display contains expected fields."""
        expected_fields = [
            "id",
            "name",
            "customer",
            "ehr_type",
            "enabled",
            "health_status_display",
            "last_poll",
            "created_at",
        ]
        for field in expected_fields:
            self.assertIn(field, self.admin.list_display)

    def test_masked_secret_display(self):
        """Test masked_secret_display shows masked secret."""
        connection = self.create_ehr_connection(
            customer=self.customer,
            client_secret="my-secret-value",
        )

        masked = self.admin.masked_secret_display(connection)

        self.assertIn("*", masked)
        self.assertIn("Encrypted", masked)
        self.assertNotIn("my-secret-value", masked)

    def test_health_status_display_colors(self):
        """Test health_status_display shows color-coded status."""
        for status in ["healthy", "degraded", "unhealthy", "unknown"]:
            connection = self.create_ehr_connection(
                customer=self.customer,
                name=f"Test {status}",
                health_status=status,
            )

            display = self.admin.health_status_display(connection)

            # Should contain color styling
            self.assertIn("color:", display)

    def test_customer_readonly_on_edit(self):
        """Test customer field is readonly when editing."""
        connection = self.create_ehr_connection(customer=self.customer)

        readonly_fields = self.admin.get_readonly_fields(None, obj=connection)

        self.assertIn("customer", readonly_fields)

    def test_customer_not_readonly_on_create(self):
        """Test customer field is editable when creating."""
        readonly_fields = self.admin.get_readonly_fields(None, obj=None)

        self.assertNotIn("customer", readonly_fields)


class EHRSyncLogAdminTestCase(TenantTestMixin, TestCase):
    """Tests for EHRSyncLog admin interface."""

    def setUp(self):
        super().setUp()
        self.site = AdminSite()
        self.admin = EHRSyncLogAdmin(EHRSyncLog, self.site)
        self.customer = self.create_customer("Test Hospital")
        self.connection = self.create_ehr_connection(customer=self.customer)

    def test_list_display_fields(self):
        """Test that list_display contains expected fields."""
        expected_fields = [
            "id",
            "connection",
            "started_at",
            "completed_at",
            "status",
            "records_fetched",
            "records_created",
            "duration_display",
        ]
        for field in expected_fields:
            self.assertIn(field, self.admin.list_display)

    def test_duration_display(self):
        """Test duration_display method."""
        sync_log = self.create_ehr_sync_log(connection=self.connection)
        sync_log.completed_at = sync_log.started_at + timezone.timedelta(seconds=30)
        sync_log.save()

        duration = self.admin.duration_display(sync_log)

        self.assertIn("s", duration)

    def test_duration_display_none(self):
        """Test duration_display shows dash when not completed."""
        sync_log = self.create_ehr_sync_log(
            connection=self.connection,
            completed_at=None,
        )

        duration = self.admin.duration_display(sync_log)

        self.assertEqual(duration, "-")

    def test_has_add_permission_false(self):
        """Test that add permission is denied for audit logs."""
        self.assertFalse(self.admin.has_add_permission(None))

    def test_has_change_permission_false(self):
        """Test that change permission is denied for audit logs."""
        sync_log = self.create_ehr_sync_log(connection=self.connection)
        self.assertFalse(self.admin.has_change_permission(None, sync_log))


# =============================================================================
# Story 2: EpicFHIRClient Tests
# =============================================================================

class EpicFHIRClientTestCase(TenantTestMixin, TestCase):
    """Tests for EpicFHIRClient class (Story 2)."""

    def setUp(self):
        super().setUp()
        self.customer = self.create_customer("Test Hospital")
        self.connection = self.create_ehr_connection(
            customer=self.customer,
            name="Epic Connection",
            ehr_type="epic",
            client_id="test-epic-client",
            client_secret="test-epic-secret",
            oauth_endpoint="https://fhir.epic.com/oauth2/token",
            fhir_endpoint="https://fhir.epic.com/api/FHIR/R4",
        )

    def test_client_initialization(self):
        """Test EpicFHIRClient constructor accepts EHRConnection."""
        from upstream.integrations.epic import EpicFHIRClient

        client = EpicFHIRClient(self.connection)

        self.assertIsNotNone(client)
        self.assertEqual(client.connection, self.connection)
        self.assertEqual(client.fhir_endpoint, "https://fhir.epic.com/api/FHIR/R4")

    def test_client_rejects_non_epic_connection(self):
        """Test EpicFHIRClient rejects non-Epic connections."""
        from upstream.integrations.epic import EpicFHIRClient

        cerner_connection = self.create_ehr_connection(
            customer=self.customer,
            name="Cerner Connection",
            ehr_type="cerner",
        )

        with self.assertRaises(ValueError) as ctx:
            EpicFHIRClient(cerner_connection)

        self.assertIn("epic", str(ctx.exception).lower())

    def test_client_has_get_token_method(self):
        """Test EpicFHIRClient has get_token() method."""
        from upstream.integrations.epic import EpicFHIRClient

        client = EpicFHIRClient(self.connection)

        self.assertTrue(hasattr(client, 'get_token'))
        self.assertTrue(callable(client.get_token))

    def test_client_has_fetch_eobs_method(self):
        """Test EpicFHIRClient has fetch_eobs() method."""
        from upstream.integrations.epic import EpicFHIRClient

        client = EpicFHIRClient(self.connection)

        self.assertTrue(hasattr(client, 'fetch_eobs'))
        self.assertTrue(callable(client.fetch_eobs))

    def test_client_has_test_connection_method(self):
        """Test EpicFHIRClient has test_connection() method."""
        from upstream.integrations.epic import EpicFHIRClient

        client = EpicFHIRClient(self.connection)

        self.assertTrue(hasattr(client, 'test_connection'))
        self.assertTrue(callable(client.test_connection))

    def test_client_has_get_health_status_method(self):
        """Test EpicFHIRClient has get_health_status() method."""
        from upstream.integrations.epic import EpicFHIRClient

        client = EpicFHIRClient(self.connection)

        self.assertTrue(hasattr(client, 'get_health_status'))

        # Test that it returns expected fields
        status = client.get_health_status()
        self.assertIn('connection_id', status)
        self.assertIn('ehr_type', status)
        self.assertEqual(status['ehr_type'], 'epic')


# =============================================================================
# Story 3: Token Manager Tests
# =============================================================================

class TokenManagerTestCase(TenantTestMixin, TestCase):
    """Tests for OAuth 2.0 Token Manager (Story 3)."""

    def setUp(self):
        super().setUp()
        from upstream.integrations.token_manager import TokenManager
        self.token_manager = TokenManager(
            connection_id=999,
            client_id="test-client",
            client_secret="test-secret",
            token_endpoint="https://example.com/oauth/token",
            scope="test_scope",
        )

    def test_token_manager_initialization(self):
        """Test TokenManager initializes correctly."""
        from upstream.integrations.token_manager import TokenManager

        manager = TokenManager(
            connection_id=1,
            client_id="my-client",
            client_secret="my-secret",
            token_endpoint="https://example.com/token",
        )

        self.assertEqual(manager.connection_id, 1)
        self.assertEqual(manager.client_id, "my-client")

    def test_token_manager_has_get_token_method(self):
        """Test TokenManager has get_token() method."""
        self.assertTrue(hasattr(self.token_manager, 'get_token'))
        self.assertTrue(callable(self.token_manager.get_token))

    def test_token_manager_has_invalidate_token_method(self):
        """Test TokenManager has invalidate_token() method."""
        self.assertTrue(hasattr(self.token_manager, 'invalidate_token'))
        self.assertTrue(callable(self.token_manager.invalidate_token))

    def test_token_manager_has_get_token_status_method(self):
        """Test TokenManager has get_token_status() method."""
        self.assertTrue(hasattr(self.token_manager, 'get_token_status'))

        status = self.token_manager.get_token_status()
        self.assertIn('has_token', status)
        self.assertIn('needs_refresh', status)

    def test_token_manager_refresh_buffer(self):
        """Test TokenManager has refresh buffer constant."""
        from upstream.integrations.token_manager import TokenManager

        self.assertTrue(hasattr(TokenManager, 'REFRESH_BUFFER_SECONDS'))
        self.assertEqual(TokenManager.REFRESH_BUFFER_SECONDS, 60)


# =============================================================================
# Story 4: FHIR Parser Tests
# =============================================================================

class FHIRParserTestCase(TenantTestMixin, TestCase):
    """Tests for FHIR EOB Parser (Story 4)."""

    def setUp(self):
        super().setUp()
        from upstream.integrations.fhir_parser import FHIRParser
        self.parser = FHIRParser(customer_salt="test-salt")

    def test_parser_initialization(self):
        """Test FHIRParser initializes with customer salt."""
        from upstream.integrations.fhir_parser import FHIRParser

        parser = FHIRParser(customer_salt="my-customer-salt")
        self.assertEqual(parser.customer_salt, "my-customer-salt")

    def test_parse_eob_extracts_required_fields(self):
        """Test parse_eob extracts all required fields."""
        eob = {
            "resourceType": "ExplanationOfBenefit",
            "id": "eob-12345",
            "patient": {"reference": "Patient/P123"},
            "insurer": {"display": "Blue Cross"},
            "billablePeriod": {
                "start": "2025-01-01",
                "end": "2025-01-15",
            },
            "outcome": "complete",
            "total": [
                {"category": {"coding": [{"code": "submitted"}]}, "amount": {"value": 1500.00}},
                {"category": {"coding": [{"code": "benefit"}]}, "amount": {"value": 1200.00}},
            ],
            "item": [
                {
                    "productOrService": {"coding": [{"code": "99213"}]},
                    "modifier": [{"coding": [{"code": "25"}]}],
                }
            ],
            "diagnosis": [
                {"diagnosisCodeableConcept": {"coding": [{"code": "J06.9"}]}},
            ],
        }

        result = self.parser.parse_eob(eob)

        # Verify extracted fields
        self.assertEqual(result['payer'], "Blue Cross")
        self.assertEqual(result['cpt'], "99213")
        self.assertIn("25", result['modifier_codes'])
        self.assertIn("J06.9", result['diagnosis_codes'])
        self.assertEqual(result['outcome'], "PAID")

    def test_parse_eob_deidentifies_patient_mrn(self):
        """Test parse_eob de-identifies patient MRN using hash."""
        eob = {
            "resourceType": "ExplanationOfBenefit",
            "id": "eob-1",
            "patient": {"reference": "Patient/MRN12345"},
            "insurer": {"display": "Aetna"},
        }

        result = self.parser.parse_eob(eob)

        # MRN should be hashed, not raw
        self.assertNotIn("MRN12345", result.get('patient_mrn_hash', ''))
        self.assertTrue(len(result.get('patient_mrn_hash', '')) == 64)  # SHA-256 hex

    def test_parse_eob_validates_required_fields(self):
        """Test parse_eob validates required fields present."""
        from upstream.integrations.fhir_parser import FHIRParseError

        # Missing patient field
        eob = {
            "resourceType": "ExplanationOfBenefit",
            "id": "eob-1",
            "insurer": {"display": "Payer"},
        }

        with self.assertRaises(FHIRParseError):
            self.parser.parse_eob(eob)

    def test_parse_eob_handles_multiple_diagnoses(self):
        """Test parse_eob handles multiple diagnoses."""
        eob = {
            "resourceType": "ExplanationOfBenefit",
            "id": "eob-1",
            "patient": {"reference": "Patient/1"},
            "insurer": {"display": "Payer"},
            "diagnosis": [
                {"diagnosisCodeableConcept": {"coding": [{"code": "J06.9"}]}},
                {"diagnosisCodeableConcept": {"coding": [{"code": "M54.5"}]}},
                {"diagnosisCodeableConcept": {"coding": [{"code": "E11.9"}]}},
            ],
        }

        result = self.parser.parse_eob(eob)

        self.assertEqual(len(result['diagnosis_codes']), 3)
        self.assertIn("J06.9", result['diagnosis_codes'])
        self.assertIn("M54.5", result['diagnosis_codes'])
        self.assertIn("E11.9", result['diagnosis_codes'])

    def test_parse_eob_computes_source_hash(self):
        """Test parse_eob computes source data hash for deduplication."""
        eob = {
            "resourceType": "ExplanationOfBenefit",
            "id": "eob-1",
            "patient": {"reference": "Patient/1"},
            "insurer": {"display": "Payer"},
        }

        result = self.parser.parse_eob(eob)

        self.assertIn('source_data_hash', result)
        self.assertEqual(len(result['source_data_hash']), 64)  # SHA-256 hex


# =============================================================================
# Story 8: CernerFHIRClient Tests
# =============================================================================

class CernerFHIRClientTestCase(TenantTestMixin, TestCase):
    """Tests for CernerFHIRClient class (Story 8)."""

    def setUp(self):
        super().setUp()
        self.customer = self.create_customer("Test Hospital")
        self.connection = self.create_ehr_connection(
            customer=self.customer,
            name="Cerner Connection",
            ehr_type="cerner",
            client_id="test-cerner-client",
            client_secret="test-cerner-secret",
            oauth_endpoint="https://fhir.cerner.com/oauth2/token",
            fhir_endpoint="https://fhir.cerner.com/api/FHIR/R4",
        )

    def test_client_initialization(self):
        """Test CernerFHIRClient constructor accepts EHRConnection."""
        from upstream.integrations.cerner import CernerFHIRClient

        client = CernerFHIRClient(self.connection)

        self.assertIsNotNone(client)
        self.assertEqual(client.connection, self.connection)

    def test_client_rejects_non_cerner_connection(self):
        """Test CernerFHIRClient rejects non-Cerner connections."""
        from upstream.integrations.cerner import CernerFHIRClient

        epic_connection = self.create_ehr_connection(
            customer=self.customer,
            name="Epic Connection",
            ehr_type="epic",
        )

        with self.assertRaises(ValueError):
            CernerFHIRClient(epic_connection)

    def test_client_has_fetch_claims_method(self):
        """Test CernerFHIRClient has fetch_claims() method."""
        from upstream.integrations.cerner import CernerFHIRClient

        client = CernerFHIRClient(self.connection)

        self.assertTrue(hasattr(client, 'fetch_claims'))
        self.assertTrue(callable(client.fetch_claims))

    def test_client_has_rate_limiting(self):
        """Test CernerFHIRClient has rate limiting settings."""
        from upstream.integrations.cerner import CernerFHIRClient

        client = CernerFHIRClient(self.connection)

        self.assertTrue(hasattr(client, 'RATE_LIMIT_DELAY'))
        self.assertTrue(hasattr(client, 'MAX_REQUESTS_PER_MINUTE'))


# =============================================================================
# Story 9: AthenaHealthClient Tests
# =============================================================================

class AthenaHealthClientTestCase(TenantTestMixin, TestCase):
    """Tests for AthenaHealthClient class (Story 9)."""

    def setUp(self):
        super().setUp()
        self.customer = self.create_customer("Test Hospital")
        self.connection = self.create_ehr_connection(
            customer=self.customer,
            name="Athena Connection",
            ehr_type="athena",
            client_id="test-athena-client",
            client_secret="test-athena-secret",
            oauth_endpoint="https://api.athenahealth.com/oauth2/token",
            fhir_endpoint="https://api.athenahealth.com/v1",
        )

    def test_client_initialization(self):
        """Test AthenaHealthClient constructor accepts EHRConnection."""
        from upstream.integrations.athena import AthenaHealthClient

        client = AthenaHealthClient(self.connection)

        self.assertIsNotNone(client)
        self.assertEqual(client.connection, self.connection)

    def test_client_rejects_non_athena_connection(self):
        """Test AthenaHealthClient rejects non-Athena connections."""
        from upstream.integrations.athena import AthenaHealthClient

        epic_connection = self.create_ehr_connection(
            customer=self.customer,
            name="Epic Connection",
            ehr_type="epic",
        )

        with self.assertRaises(ValueError):
            AthenaHealthClient(epic_connection)

    def test_client_has_fetch_claims_method(self):
        """Test AthenaHealthClient has fetch_claims() method."""
        from upstream.integrations.athena import AthenaHealthClient

        client = AthenaHealthClient(self.connection)

        self.assertTrue(hasattr(client, 'fetch_claims'))
        self.assertTrue(callable(client.fetch_claims))


# =============================================================================
# Story 10: Health Monitoring Tests
# =============================================================================

class HealthMonitoringTestCase(TenantTestMixin, TestCase):
    """Tests for connection health monitoring (Story 10)."""

    def setUp(self):
        super().setUp()
        self.customer = self.create_customer("Test Hospital")
        self.connection = self.create_ehr_connection(
            customer=self.customer,
            name="Test Connection",
            ehr_type="epic",
        )

    def test_check_connection_health_function_exists(self):
        """Test check_connection_health function exists."""
        from upstream.integrations.health import check_connection_health

        self.assertTrue(callable(check_connection_health))

    def test_health_check_result_structure(self):
        """Test HealthCheckResult has expected structure."""
        from upstream.integrations.health import HealthCheckResult

        result = HealthCheckResult(
            connection_id=1,
            connection_name="Test",
            ehr_type="epic",
            healthy=True,
            token_check=True,
            api_check=True,
        )

        result_dict = result.to_dict()

        self.assertIn('connection_id', result_dict)
        self.assertIn('healthy', result_dict)
        self.assertIn('token_check', result_dict)
        self.assertIn('api_check', result_dict)
        self.assertIn('checked_at', result_dict)

    def test_check_all_connections_function_exists(self):
        """Test check_all_connections function exists."""
        from upstream.integrations.health import check_all_connections

        self.assertTrue(callable(check_all_connections))


# =============================================================================
# Story 13: Resilience Patterns Tests
# =============================================================================

class ResiliencePatternTestCase(TenantTestMixin, TestCase):
    """Tests for retry logic and circuit breakers (Story 13)."""

    def test_circuit_breaker_initialization(self):
        """Test CircuitBreaker initializes correctly."""
        from upstream.integrations.resilience import CircuitBreaker

        cb = CircuitBreaker(
            name="test-breaker",
            failure_threshold=5,
            recovery_timeout=300,
        )

        self.assertEqual(cb.name, "test-breaker")
        self.assertEqual(cb.failure_threshold, 5)
        self.assertEqual(cb.recovery_timeout, 300)
        self.assertEqual(cb.state, CircuitBreaker.CLOSED)

    def test_circuit_breaker_opens_after_failures(self):
        """Test CircuitBreaker opens after 5 consecutive failures."""
        from upstream.integrations.resilience import CircuitBreaker

        cb = CircuitBreaker(
            name="test-open-breaker",
            failure_threshold=5,
            recovery_timeout=300,
        )

        # Record 5 failures
        for i in range(5):
            cb.record_failure(Exception(f"Failure {i+1}"))

        self.assertEqual(cb.state, CircuitBreaker.OPEN)

    def test_circuit_breaker_resets_on_success(self):
        """Test CircuitBreaker resets failure count on success."""
        from upstream.integrations.resilience import CircuitBreaker

        cb = CircuitBreaker(
            name="test-reset-breaker",
            failure_threshold=5,
            recovery_timeout=300,
        )

        # Record some failures
        cb.record_failure(Exception("Failure 1"))
        cb.record_failure(Exception("Failure 2"))

        self.assertEqual(cb.failure_count, 2)

        # Record success
        cb.record_success()

        self.assertEqual(cb.failure_count, 0)
        self.assertEqual(cb.state, CircuitBreaker.CLOSED)

    def test_resilient_client_has_circuit_breaker(self):
        """Test ResilientClient has circuit breaker."""
        from upstream.integrations.resilience import ResilientClient

        client = ResilientClient(
            connection_name="test-client",
            failure_threshold=5,
            recovery_timeout=300,
            max_retries=3,
        )

        self.assertTrue(hasattr(client, 'circuit_breaker'))
        self.assertIsNotNone(client.circuit_breaker)

    def test_retry_decorator_exists(self):
        """Test retry_with_backoff decorator exists."""
        from upstream.integrations.resilience import retry_with_backoff

        self.assertTrue(callable(retry_with_backoff))

    def test_circuit_breaker_decorator_exists(self):
        """Test with_circuit_breaker decorator exists."""
        from upstream.integrations.resilience import with_circuit_breaker

        self.assertTrue(callable(with_circuit_breaker))
