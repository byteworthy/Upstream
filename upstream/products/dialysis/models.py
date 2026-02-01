"""
Dialysis product line models.

Stores Medicare baselines and MA variance tracking data for dialysis claims.
"""

from django.db import models
from django.core.validators import MinValueValidator
from upstream.core.models import BaseModel


class DialysisMABaseline(BaseModel):
    """
    Traditional Medicare payment baselines for dialysis CPT codes.

    Used to compare Medicare Advantage payer payments against traditional
    Medicare rates to detect significant variance.
    """

    cpt = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        help_text="CPT code for dialysis procedure",
    )
    average_payment = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Average traditional Medicare payment amount",
    )
    sample_size = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Number of claims used to calculate average",
    )
    last_updated = models.DateField(
        db_index=True,
        help_text="Date when baseline was last updated from CMS data",
    )

    class Meta:
        # Use the existing table created by upstream migration 0027
        db_table = "upstream_dialysismabaseline"
        verbose_name = "Dialysis MA Baseline"
        verbose_name_plural = "Dialysis MA Baselines"
        ordering = ["cpt"]
        indexes = [
            models.Index(fields=["cpt"], name="dialysis_ma_baseline_cpt_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(average_payment__gte=0),
                name="dialysis_ma_baseline_payment_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(sample_size__gte=1),
                name="dialysis_ma_baseline_sample_positive",
            ),
        ]

    def __str__(self):
        return f"CPT {self.cpt}: ${self.average_payment} (n={self.sample_size})"
