# Generated migration for Phase 3 - Add missing indexes to reporting models
#
# Related: TECHNICAL_DEBT.md - Phase 3: Database Optimization
#
# Adds indexes to reporting models for common query patterns:
# - ReportTemplate: template_type and is_active filtering
# - ScheduledReport: schedule lookup and status filtering
# - ReportArtifact: customer and report_run filtering

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("reporting", "__first__"),
    ]

    operations = [
        # =====================================================================
        # ReportTemplate indexes
        # =====================================================================
        migrations.AddIndex(
            model_name="reporttemplate",
            index=models.Index(
                fields=["template_type", "is_active"], name="rpt_tpl_type_active_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="reporttemplate",
            index=models.Index(
                fields=["is_active", "-created_at"], name="rpt_tpl_active_date_idx"
            ),
        ),
        # =====================================================================
        # ScheduledReport indexes
        # =====================================================================
        migrations.AddIndex(
            model_name="scheduledreport",
            index=models.Index(
                fields=["template", "next_run_date"], name="rpt_sched_tpl_next_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="scheduledreport",
            index=models.Index(
                fields=["schedule_type", "next_run_date"],
                name="rpt_sched_type_next_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="scheduledreport",
            index=models.Index(
                fields=["last_run_status", "-last_run_date"],
                name="rpt_sched_status_date_idx",
            ),
        ),
        # =====================================================================
        # ReportArtifact indexes
        # =====================================================================
        migrations.AddIndex(
            model_name="reportartifact",
            index=models.Index(
                fields=["customer", "-created_at"], name="rpt_art_cust_date_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="reportartifact",
            index=models.Index(
                fields=["report_run", "kind"], name="rpt_art_run_kind_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="reportartifact",
            index=models.Index(
                fields=["customer", "kind", "-created_at"], name="rpt_art_cust_kind_idx"
            ),
        ),
    ]
