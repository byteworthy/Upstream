"""
Phase 1 of 2: Add unique index concurrently for DriftEvent.

This migration creates a unique index using PostgreSQL's CONCURRENTLY option,
which allows the index to be built without blocking reads or writes to the table.

Part of DB-02: Implement unique constraints for data integrity.
"""
from django.db import migrations


class Migration(migrations.Migration):
    """
    Zero-downtime migration: Creates unique index concurrently.

    IMPORTANT: atomic = False is required for CONCURRENTLY operations.
    PostgreSQL cannot run CREATE INDEX CONCURRENTLY inside a transaction.
    """

    atomic = False  # Required for CONCURRENTLY operations

    dependencies = [
        (
            "upstream",
            "0013_claimvalidationhistory_cvh_error_count_nonnegative_and_more",
        ),
    ]

    operations = [
        # Create unique index concurrently (no table lock)
        # Must use RunSQL because models.Index doesn't support unique=True
        migrations.RunSQL(
            sql="""
                CREATE UNIQUE INDEX CONCURRENTLY driftevent_signal_uniq_idx
                ON upstream_driftevent (customer_id, report_run_id, payer, cpt_group, drift_type);
            """,
            reverse_sql="""
                DROP INDEX CONCURRENTLY IF EXISTS driftevent_signal_uniq_idx;
            """,
        ),
    ]
