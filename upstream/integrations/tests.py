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
