# Generated manually for PT/OT G-Code tracking models

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("upstream", "0034_add_certification_cycle"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PTOTFunctionalLimitation",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "patient_id",
                    models.CharField(
                        max_length=100,
                        db_index=True,
                    ),
                ),
                (
                    "limitation_category",
                    models.CharField(
                        max_length=50,
                        choices=[
                            ("MOBILITY", "Mobility"),
                            ("CHANGING_POSITION", "Changing/Maintaining Position"),
                            ("CARRYING", "Carrying/Moving Objects"),
                            ("SELF_CARE", "Self Care"),
                            ("OTHER_PT", "Other PT/OT Primary"),
                            ("OTHER_SLP", "Other SLP Primary"),
                            ("SWALLOWING", "Swallowing"),
                        ],
                    ),
                ),
                (
                    "current_gcode",
                    models.CharField(max_length=10),
                ),
                (
                    "goal_gcode",
                    models.CharField(max_length=10),
                ),
                (
                    "discharge_gcode",
                    models.CharField(
                        max_length=10,
                        null=True,
                        blank=True,
                    ),
                ),
                (
                    "current_severity",
                    models.CharField(max_length=2),
                ),
                (
                    "goal_severity",
                    models.CharField(max_length=2),
                ),
                (
                    "discharge_severity",
                    models.CharField(
                        max_length=2,
                        null=True,
                        blank=True,
                    ),
                ),
                (
                    "evaluation_date",
                    models.DateField(),
                ),
                (
                    "last_reported_date",
                    models.DateField(),
                ),
                (
                    "visit_count_since_report",
                    models.IntegerField(default=0),
                ),
                (
                    "discharge_date",
                    models.DateField(
                        null=True,
                        blank=True,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        max_length=20,
                        choices=[
                            ("ACTIVE", "Active"),
                            ("DISCHARGED", "Discharged"),
                        ],
                        default="ACTIVE",
                    ),
                ),
                (
                    "customer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ptot_functional_limitations",
                        to="upstream.customer",
                    ),
                ),
            ],
            options={
                "verbose_name": "PT/OT Functional Limitation",
                "verbose_name_plural": "PT/OT Functional Limitations",
                "db_table": "upstream_ptotfunctionallimitation",
            },
        ),
        migrations.CreateModel(
            name="PTOTProgressReport",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "report_date",
                    models.DateField(),
                ),
                (
                    "visit_number",
                    models.IntegerField(),
                ),
                (
                    "reporting_type",
                    models.CharField(
                        max_length=20,
                        choices=[
                            ("EVALUATION", "Evaluation"),
                            ("PROGRESS", "Progress Report"),
                            ("DISCHARGE", "Discharge"),
                        ],
                    ),
                ),
                (
                    "gcodes_reported",
                    models.JSONField(default=dict),
                ),
                (
                    "customer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ptot_progress_reports",
                        to="upstream.customer",
                    ),
                ),
                (
                    "functional_limitation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="progress_reports",
                        to="upstream.ptotfunctionallimitation",
                    ),
                ),
            ],
            options={
                "verbose_name": "PT/OT Progress Report",
                "verbose_name_plural": "PT/OT Progress Reports",
                "db_table": "upstream_ptotprogressreport",
            },
        ),
        migrations.AddIndex(
            model_name="ptotfunctionallimitation",
            index=models.Index(
                fields=["customer", "patient_id"],
                name="ptot_fl_customer_patient_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="ptotfunctionallimitation",
            index=models.Index(
                fields=["customer", "status"],
                name="ptot_fl_customer_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="ptotfunctionallimitation",
            index=models.Index(
                fields=["limitation_category"],
                name="ptot_fl_category_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="ptotprogressreport",
            index=models.Index(
                fields=["customer", "report_date"],
                name="ptot_pr_customer_date_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="ptotprogressreport",
            index=models.Index(
                fields=["functional_limitation", "report_date"],
                name="ptot_pr_fl_date_idx",
            ),
        ),
    ]
