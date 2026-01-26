# Generated manually for PERF-19: Missing indexes for recovery stats
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("upstream", "0008_add_not_null_constraints_high15"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="operatorjudgment",
            index=models.Index(
                fields=["customer", "-recovered_date"],
                name="opjudge_recovery_stats_idx",
                condition=models.Q(recovered_amount__isnull=False),
            ),
        ),
    ]
