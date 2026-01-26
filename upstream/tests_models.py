"""
Tests for model indexes and database schema.

Phase 6: Database Indexes - Verify composite indexes are created.
"""

from django.test import TestCase
from django.db import connection


class AlertRuleIndexTest(TestCase):
    """Test that AlertRule has the correct composite index."""

    def test_alertrule_has_customer_enabled_index(self):
        """Verify that AlertRule has composite index on (customer, enabled)."""
        # Get the table name for AlertRule
        from upstream.alerts.models import AlertRule

        table_name = AlertRule._meta.db_table

        # Query the database for indexes on the AlertRule table
        with connection.cursor() as cursor:
            # SQLite query to get indexes
            cursor.execute(
                "SELECT name, sql FROM sqlite_master "
                "WHERE type='index' AND tbl_name=%s",
                [table_name],
            )
            indexes = cursor.fetchall()

        # Convert to a dict for easier checking
        index_dict = {name: sql for name, sql in indexes if sql is not None}

        # Check that the composite index exists
        index_name = "idx_alertrule_customer_enabled"
        self.assertIn(
            index_name,
            index_dict,
            f"Expected index '{index_name}' not found. "
            f"Available indexes: {list(index_dict.keys())}",
        )

        # Verify the index is on the correct columns
        index_sql = index_dict[index_name]
        self.assertIn(
            "customer_id",
            index_sql.lower(),
            "Index should include customer_id column",
        )
        self.assertIn(
            "enabled", index_sql.lower(), "Index should include enabled column"
        )

    def test_alertrule_index_column_order(self):
        """Verify index has columns in correct order (customer, enabled)."""
        index_name = "idx_alertrule_customer_enabled"

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT sql FROM sqlite_master " "WHERE type='index' AND name=%s",
                [index_name],
            )
            result = cursor.fetchone()

        self.assertIsNotNone(result, f"Index '{index_name}' not found")

        index_sql = result[0]

        # Extract column list: ON table ("col1", "col2")
        import re

        match = re.search(r"ON\s+\S+\s+\((.+?)\)", index_sql)
        self.assertIsNotNone(match, f"Could not parse columns from SQL: {index_sql}")

        columns_str = match.group(1)
        # Remove quotes and split by comma
        columns = [col.strip().strip('"').strip("'") for col in columns_str.split(",")]

        # Verify column order
        self.assertEqual(len(columns), 2, "Index should have exactly 2 columns")
        self.assertEqual(columns[0], "customer_id", "First column is customer_id")
        self.assertEqual(columns[1], "enabled", "Second column is enabled")


class NotificationChannelIndexTest(TestCase):
    """Test that NotificationChannel has the correct composite index."""

    def test_notificationchannel_has_composite_index(self):
        """Verify NotificationChannel has composite index.

        Index: (customer, enabled, channel_type)
        """
        from upstream.alerts.models import NotificationChannel

        table_name = NotificationChannel._meta.db_table

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT name, sql FROM sqlite_master "
                "WHERE type='index' AND tbl_name=%s",
                [table_name],
            )
            indexes = cursor.fetchall()

        index_dict = {name: sql for name, sql in indexes if sql is not None}

        index_name = "idx_notificationchannel_lookup"
        self.assertIn(
            index_name,
            index_dict,
            f"Expected index '{index_name}' not found. "
            f"Available indexes: {list(index_dict.keys())}",
        )

        # Verify the index is on the correct columns
        index_sql = index_dict[index_name]
        self.assertIn(
            "customer_id",
            index_sql.lower(),
            "Index should include customer_id column",
        )
        self.assertIn(
            "enabled", index_sql.lower(), "Index should include enabled column"
        )
        self.assertIn(
            "channel_type",
            index_sql.lower(),
            "Index should include channel_type column",
        )

    def test_notificationchannel_index_column_order(self):
        """Verify index column order.

        Order: (customer, enabled, channel_type)
        """
        index_name = "idx_notificationchannel_lookup"

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT sql FROM sqlite_master " "WHERE type='index' AND name=%s",
                [index_name],
            )
            result = cursor.fetchone()

        self.assertIsNotNone(result, f"Index '{index_name}' not found")

        index_sql = result[0]

        # Extract column list
        import re

        match = re.search(r"ON\s+\S+\s+\((.+?)\)", index_sql)
        self.assertIsNotNone(match, f"Could not parse columns from SQL: {index_sql}")

        columns_str = match.group(1)
        columns = [col.strip().strip('"').strip("'") for col in columns_str.split(",")]

        # Verify column order
        self.assertEqual(len(columns), 3, "Index should have exactly 3 columns")
        self.assertEqual(columns[0], "customer_id", "First column is customer_id")
        self.assertEqual(columns[1], "enabled", "Second column is enabled")
        self.assertEqual(columns[2], "channel_type", "Third column is channel_type")


class WebhookDeliveryIndexTest(TestCase):
    """Test that WebhookDelivery has the correct composite index."""

    def test_webhookdelivery_has_retry_index(self):
        """Verify WebhookDelivery has composite index on (status, next_attempt_at)."""
        from upstream.integrations.models import WebhookDelivery

        table_name = WebhookDelivery._meta.db_table

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT name, sql FROM sqlite_master "
                "WHERE type='index' AND tbl_name=%s",
                [table_name],
            )
            indexes = cursor.fetchall()

        index_dict = {name: sql for name, sql in indexes if sql is not None}

        index_name = "idx_webhookdelivery_retry"
        self.assertIn(
            index_name,
            index_dict,
            f"Expected index '{index_name}' not found. "
            f"Available indexes: {list(index_dict.keys())}",
        )

        # Verify the index is on the correct columns
        index_sql = index_dict[index_name]
        self.assertIn(
            "status",
            index_sql.lower(),
            "Index should include status column",
        )
        self.assertIn(
            "next_attempt_at",
            index_sql.lower(),
            "Index should include next_attempt_at column",
        )

    def test_webhookdelivery_index_column_order(self):
        """Verify index has columns in correct order (status, next_attempt_at)."""
        index_name = "idx_webhookdelivery_retry"

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT sql FROM sqlite_master " "WHERE type='index' AND name=%s",
                [index_name],
            )
            result = cursor.fetchone()

        self.assertIsNotNone(result, f"Index '{index_name}' not found")

        index_sql = result[0]

        # Extract column list
        import re

        match = re.search(r"ON\s+\S+\s+\((.+?)\)", index_sql)
        self.assertIsNotNone(match, f"Could not parse columns from SQL: {index_sql}")

        columns_str = match.group(1)
        columns = [col.strip().strip('"').strip("'") for col in columns_str.split(",")]

        # Verify column order
        self.assertEqual(len(columns), 2, "Index should have exactly 2 columns")
        self.assertEqual(columns[0], "status", "First column is status")
        self.assertEqual(
            columns[1], "next_attempt_at", "Second column is next_attempt_at"
        )


class IntegrationLogIndexTest(TestCase):
    """Test that IntegrationLog has the correct composite index with DESC ordering."""

    def test_integrationlog_has_history_index(self):
        """Verify IntegrationLog has composite index on (connection, -start_time)."""
        from upstream.integrations.models import IntegrationLog

        table_name = IntegrationLog._meta.db_table

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT name, sql FROM sqlite_master "
                "WHERE type='index' AND tbl_name=%s",
                [table_name],
            )
            indexes = cursor.fetchall()

        index_dict = {name: sql for name, sql in indexes if sql is not None}

        index_name = "idx_integrationlog_history"
        self.assertIn(
            index_name,
            index_dict,
            f"Expected index '{index_name}' not found. "
            f"Available indexes: {list(index_dict.keys())}",
        )

        # Verify the index is on the correct columns
        index_sql = index_dict[index_name]
        self.assertIn(
            "connection_id",
            index_sql.lower(),
            "Index should include connection_id column",
        )
        self.assertIn(
            "start_time",
            index_sql.lower(),
            "Index should include start_time column",
        )

    def test_integrationlog_index_column_order_and_desc(self):
        """Verify index has columns (connection, start_time DESC)."""
        index_name = "idx_integrationlog_history"

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT sql FROM sqlite_master " "WHERE type='index' AND name=%s",
                [index_name],
            )
            result = cursor.fetchone()

        self.assertIsNotNone(result, f"Index '{index_name}' not found")

        index_sql = result[0]

        # Extract column list - handle DESC keyword
        import re

        match = re.search(r"ON\s+\S+\s+\((.+?)\)", index_sql)
        self.assertIsNotNone(match, f"Could not parse columns from SQL: {index_sql}")

        columns_str = match.group(1)
        # Parse columns including DESC/ASC modifiers
        columns = [col.strip().strip('"').strip("'") for col in columns_str.split(",")]

        # Verify column order
        self.assertEqual(len(columns), 2, "Index should have exactly 2 columns")
        self.assertEqual(columns[0], "connection_id", "First column is connection_id")

        # Verify second column is start_time with DESC modifier
        self.assertTrue(
            "start_time" in columns[1].lower(),
            f"Second column should include start_time, got: {columns[1]}",
        )
        self.assertTrue(
            "desc" in columns[1].lower(),
            f"Second column should have DESC modifier, got: {columns[1]}",
        )
