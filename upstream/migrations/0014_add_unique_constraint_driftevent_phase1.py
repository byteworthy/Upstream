"""
Phase 1 of 2: Add unique index concurrently for DriftEvent.

This migration creates a unique index using PostgreSQL's CONCURRENTLY option,
which allows the index to be built without blocking reads or writes to the table.

Part of DB-02: Implement unique constraints for data integrity.
"""
from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Zero-downtime migration: Creates unique index concurrently.

    IMPORTANT: atomic = False is required for CONCURRENTLY operations.
    PostgreSQL cannot run CREATE INDEX CONCURRENTLY inside a transaction.
    """

    atomic = False  # Required for AddIndexConcurrently

    dependencies = [
        ("upstream", "0013_claimvalidationhistory_cvh_error_count_nonnegative_and_more"),
    ]

    operations = [
        # Create unique index concurrently (no table lock)
        # Index name follows pattern: {table}_{columns}_uniq_idx
        AddIndexConcurrently(
            model_name="driftevent",
            index=models.Index(
                fields=["customer", "report_run", "payer", "cpt_group", "drift_type"],
                name="driftevent_signal_uniq_idx",
            ),
        ),
    ]
