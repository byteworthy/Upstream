# Generated manually for CertificationCycle model

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("upstream", "0033_add_homehealth_models"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CertificationCycle",
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
                    "cycle_number",
                    models.PositiveIntegerField(
                        default=1,
                        help_text="Certification cycle (1=initial, 2+=recert)",
                    ),
                ),
                (
                    "cycle_start",
                    models.DateField(
                        db_index=True,
                        help_text="Start date of this 60-day certification period",
                    ),
                ),
                (
                    "cycle_end",
                    models.DateField(
                        db_index=True,
                        help_text="End date of certification period",
                    ),
                ),
                (
                    "physician_recert_signed",
                    models.BooleanField(
                        default=False,
                        help_text="Whether physician has signed recertification",
                    ),
                ),
                (
                    "physician_recert_date",
                    models.DateField(
                        blank=True,
                        null=True,
                        help_text="Date physician signed recertification",
                    ),
                ),
                (
                    "physician_name",
                    models.CharField(
                        blank=True,
                        max_length=255,
                        help_text="Name of certifying physician",
                    ),
                ),
                (
                    "f2f_required",
                    models.BooleanField(
                        default=False,
                        help_text="Whether F2F encounter required",
                    ),
                ),
                (
                    "f2f_completed",
                    models.BooleanField(
                        default=False,
                        help_text="Whether required F2F has been completed",
                    ),
                ),
                (
                    "f2f_date",
                    models.DateField(
                        blank=True,
                        null=True,
                        help_text="Date of F2F encounter for recertification",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("ACTIVE", "Active Cycle"),
                            ("PENDING_RECERT", "Pending Recertification"),
                            ("RECERTIFIED", "Recertified"),
                            ("DISCHARGED", "Patient Discharged"),
                            ("EXPIRED", "Expired - No Recertification"),
                        ],
                        db_index=True,
                        default="ACTIVE",
                        max_length=20,
                    ),
                ),
                (
                    "alert_45_day_sent",
                    models.BooleanField(
                        default=False,
                        help_text="15-day warning alert has been sent",
                    ),
                ),
                (
                    "alert_30_day_sent",
                    models.BooleanField(
                        default=False,
                        help_text="30-day warning alert has been sent",
                    ),
                ),
                (
                    "alert_21_day_sent",
                    models.BooleanField(
                        default=False,
                        help_text="21-day urgent alert has been sent",
                    ),
                ),
                (
                    "alert_14_day_sent",
                    models.BooleanField(
                        default=False,
                        help_text="14-day critical alert has been sent",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_updated",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "customer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="certification_cycles",
                        to="upstream.customer",
                    ),
                ),
                (
                    "episode",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="certification_cycles",
                        to="upstream.homehealthepisode",
                    ),
                ),
            ],
            options={
                "verbose_name": "Certification Cycle",
                "verbose_name_plural": "Certification Cycles",
                "db_table": "upstream_certificationcycle",
                "ordering": ["episode", "cycle_number"],
            },
        ),
        migrations.AddIndex(
            model_name="certificationcycle",
            index=models.Index(
                fields=["customer", "status", "cycle_end"],
                name="cert_status_end_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="certificationcycle",
            index=models.Index(
                fields=["customer", "episode"],
                name="cert_customer_episode_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="certificationcycle",
            constraint=models.UniqueConstraint(
                fields=("episode", "cycle_number"),
                name="unique_episode_cycle",
            ),
        ),
    ]
