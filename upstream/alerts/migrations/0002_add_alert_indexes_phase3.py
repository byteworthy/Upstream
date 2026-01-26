# Generated migration for Phase 3 - Add missing indexes to Alert model
#
# Related: TECHNICAL_DEBT.md - Phase 3: Database Optimization
#
# Adds indexes to Alert (legacy) model for common query patterns:
# - status and severity filtering
# - rule-based filtering
# - resolution tracking

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("alerts", "0001_initial"),
    ]

    operations = [
        # =====================================================================
        # Alert (legacy) indexes
        # =====================================================================
        migrations.AddIndex(
            model_name="alert",
            index=models.Index(
                fields=["status", "severity", "-created_at"],
                name="alert_status_sev_date_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="alert",
            index=models.Index(
                fields=["rule", "status", "-created_at"], name="alert_rule_status_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="alert",
            index=models.Index(
                fields=["severity", "-created_at"], name="alert_severity_date_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="alert",
            index=models.Index(
                fields=["status", "-resolved_at"], name="alert_status_resolved_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="alert",
            index=models.Index(
                fields=["resolved_by", "-resolved_at"], name="alert_resolver_date_idx"
            ),
        ),
        # =====================================================================
        # AlertRule indexes
        # =====================================================================
        migrations.AddIndex(
            model_name="alertrule",
            index=models.Index(
                fields=["customer", "enabled", "severity"],
                name="alertrule_cust_en_sev_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="alertrule",
            index=models.Index(
                fields=["enabled", "-routing_priority"],
                name="alertrule_en_priority_idx",
            ),
        ),
        # =====================================================================
        # NotificationChannel indexes
        # =====================================================================
        migrations.AddIndex(
            model_name="notificationchannel",
            index=models.Index(
                fields=["customer", "enabled", "channel_type"],
                name="notifchan_cust_en_type_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="notificationchannel",
            index=models.Index(
                fields=["channel_type", "enabled"], name="notifchan_type_enabled_idx"
            ),
        ),
    ]
