from django.db import models
from django.core.validators import MinValueValidator
from upstream.core.tenant import CustomerScopedManager


class DialysisMABaseline(models.Model):
    """
    Traditional Medicare payment baselines for dialysis CPT codes.
    Used to compare MA payer payments and detect variance.
    """

    cpt = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        help_text="CPT procedure code for dialysis service",
    )
    average_payment = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Average traditional Medicare payment for this CPT",
    )
    sample_size = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Number of claims in baseline calculation",
    )
    last_updated = models.DateTimeField(
        auto_now=True,
        db_index=True,
        help_text="Last time this baseline was updated",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "upstream_dialysis_ma_baseline"
        verbose_name = "Dialysis MA Baseline"
        verbose_name_plural = "Dialysis MA Baselines"
        indexes = [
            models.Index(fields=["cpt"], name="dialysis_baseline_cpt_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(average_payment__gte=0),
                name="dialysis_baseline_payment_nonnegative",
            ),
            models.CheckConstraint(
                check=models.Q(sample_size__gte=1),
                name="dialysis_baseline_sample_positive",
            ),
        ]

    def __str__(self):
        return f"Dialysis Baseline {self.cpt}: ${self.average_payment}"
