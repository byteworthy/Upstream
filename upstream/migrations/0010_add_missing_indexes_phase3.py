# Generated migration for Phase 3 - Add missing database indexes
#
# This migration adds indexes to frequently queried fields that were missing indexes,
# improving query performance across the application.
#
# Related: TECHNICAL_DEBT.md - Phase 3: Database Optimization
#
# Index Strategy:
# - Foreign keys without db_index get individual field indexes
# - Status/enum fields that are frequently filtered get indexes
# - Composite indexes for common query patterns (customer + status, customer + date)
# - Date fields used in ORDER BY get indexes

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("upstream", "0009_add_recovery_stats_index_perf19"),
    ]

    operations = [
        # =====================================================================
        # ReportRun indexes (upstream/models.py:487-517)
        # =====================================================================
        migrations.AddIndex(
            model_name="reportrun",
            index=models.Index(
                fields=["customer", "status", "-started_at"],
                name="reportrun_cust_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="reportrun",
            index=models.Index(
                fields=["customer", "run_type", "-started_at"],
                name="reportrun_cust_type_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="reportrun",
            index=models.Index(
                fields=["status", "-started_at"], name="reportrun_status_date_idx"
            ),
        ),
        # =====================================================================
        # DomainAuditEvent indexes (upstream/core/models.py:23-56)
        # =====================================================================
        migrations.AddIndex(
            model_name="domainauditevent",
            index=models.Index(
                fields=["customer", "action", "-timestamp"],
                name="audit_cust_action_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="domainauditevent",
            index=models.Index(
                fields=["entity_type", "entity_id", "-timestamp"],
                name="audit_entity_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="domainauditevent",
            index=models.Index(
                fields=["user", "-timestamp"], name="audit_user_date_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="domainauditevent",
            index=models.Index(
                fields=["action", "-timestamp"], name="audit_action_date_idx"
            ),
        ),
        # =====================================================================
        # ProductConfig indexes (upstream/core/models.py:59-83)
        # =====================================================================
        migrations.AddIndex(
            model_name="productconfig",
            index=models.Index(
                fields=["customer", "enabled"], name="prodcfg_cust_enabled_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="productconfig",
            index=models.Index(
                fields=["product_slug", "enabled"], name="prodcfg_slug_enabled_idx"
            ),
        ),
    ]
