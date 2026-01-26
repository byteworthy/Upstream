"""
Tests for UserProfile indexes (Phase 6, Story #1)
"""
from django.test import TestCase
from django.db import connection


class UserProfileIndexesTestCase(TestCase):
    """Test that UserProfile has proper indexes on user and customer fields."""

    def test_userprofile_indexes_exist(self):
        """Verify that indexes exist on user_id and customer_id fields."""
        with connection.cursor() as cursor:
            # Get all indexes for upstream_userprofile table
            cursor.execute(
                """
                SELECT name, sql
                FROM sqlite_master
                WHERE type='index'
                AND tbl_name='upstream_userprofile'
            """
            )
            indexes = cursor.fetchall()

        # Check customer_id has an index
        customer_index_exists = any(
            "customer_id" in (sql or "") for name, sql in indexes
        )
        self.assertTrue(customer_index_exists, "Index on customer_id should exist")

        # Check user_id has UNIQUE constraint (which creates an index)
        # Get table schema to check for UNIQUE constraint
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT sql
                FROM sqlite_master
                WHERE type='table'
                AND name='upstream_userprofile'
            """
            )
            schema = cursor.fetchone()[0]

        self.assertIn(
            "UNIQUE",
            schema,
            "user_id should have UNIQUE constraint (which creates an index)",
        )
        self.assertIn("user_id", schema, "user_id field should exist in schema")

    def test_userprofile_model_has_db_index(self):
        """Verify that the model definition includes db_index=True."""
        from upstream.models import UserProfile

        # Check that user field has db_index set
        user_field = UserProfile._meta.get_field("user")
        # OneToOneField with unique=True automatically creates index
        self.assertTrue(
            user_field.unique, "user field should have unique=True (OneToOneField)"
        )

        # Check that customer field has db_index set
        customer_field = UserProfile._meta.get_field("customer")
        self.assertTrue(
            customer_field.db_index, "customer field should have db_index=True"
        )
