# Generated migration for Phase 3 - Add missing indexes to integration models
#
# Related: TECHNICAL_DEBT.md - Phase 3: Database Optimization
#
# Adds indexes to integration models for common query patterns:
# - IntegrationProvider: provider_type and is_active filtering
# - IntegrationConnection: provider, status, and connection_type filtering
# - IntegrationLog: connection and status filtering
# - WebhookEndpoint: customer and active status
# - WebhookDelivery: endpoint, status, and retry scheduling

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "__first__"),
    ]

    operations = [
        # =====================================================================
        # IntegrationProvider indexes
        # =====================================================================
        migrations.AddIndex(
            model_name="integrationprovider",
            index=models.Index(
                fields=["provider_type", "is_active"], name="integ_prov_type_active_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="integrationprovider",
            index=models.Index(
                fields=["is_active", "-created_at"], name="integ_prov_active_date_idx"
            ),
        ),
        # =====================================================================
        # IntegrationConnection indexes
        # =====================================================================
        migrations.AddIndex(
            model_name="integrationconnection",
            index=models.Index(
                fields=["provider", "status"], name="integ_conn_prov_status_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="integrationconnection",
            index=models.Index(
                fields=["connection_type", "status"], name="integ_conn_type_status_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="integrationconnection",
            index=models.Index(
                fields=["status", "-last_successful_sync"],
                name="integ_conn_status_sync_idx",
            ),
        ),
        # =====================================================================
        # IntegrationLog indexes
        # =====================================================================
        migrations.AddIndex(
            model_name="integrationlog",
            index=models.Index(
                fields=["connection", "status", "-start_time"],
                name="integ_log_conn_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="integrationlog",
            index=models.Index(
                fields=["operation_type", "status", "-start_time"],
                name="integ_log_op_status_idx",
            ),
        ),
        # =====================================================================
        # WebhookEndpoint indexes
        # =====================================================================
        migrations.AddIndex(
            model_name="webhookendpoint",
            index=models.Index(
                fields=["customer", "active"], name="webhook_ep_cust_active_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="webhookendpoint",
            index=models.Index(
                fields=["active", "-created_at"], name="webhook_ep_active_date_idx"
            ),
        ),
        # =====================================================================
        # WebhookDelivery indexes
        # =====================================================================
        migrations.AddIndex(
            model_name="webhookdelivery",
            index=models.Index(
                fields=["endpoint", "status", "-created_at"],
                name="webhook_del_ep_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="webhookdelivery",
            index=models.Index(
                fields=["status", "next_attempt_at"], name="webhook_del_retry_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="webhookdelivery",
            index=models.Index(
                fields=["event_type", "status", "-created_at"],
                name="webhook_del_evt_status_idx",
            ),
        ),
    ]
