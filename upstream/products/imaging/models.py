"""
Imaging product line models.

Stores prior authorization requirements by payer and CPT code
for imaging procedures.
"""

from django.db import models
from upstream.core.models import BaseModel


# RBM Provider choices (Radiology Benefit Management)
RBM_PROVIDER_CHOICES = [
    ("EVICORE", "eviCore"),
    ("AIM", "AIM Specialty Health"),
    ("CARECORE", "CareCore National"),
    ("NIA", "National Imaging Associates"),
    ("MAGELLAN", "Magellan Healthcare"),
    ("OTHER", "Other"),
    ("NONE", "Direct to Payer"),
]


class ImagingPARequirement(BaseModel):
    """
    Prior Authorization requirements for imaging procedures.

    Stores which payer/CPT combinations require PA and which
    RBM (Radiology Benefit Management) provider handles the PA.
    """

    payer = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Payer name or ID requiring PA",
    )
    cpt = models.CharField(
        max_length=20,
        db_index=True,
        help_text="CPT code for imaging procedure",
    )
    pa_required = models.BooleanField(
        default=True,
        help_text="Whether PA is required for this payer/CPT",
    )
    rbm_provider = models.CharField(
        max_length=20,
        choices=RBM_PROVIDER_CHOICES,
        default="NONE",
        help_text="RBM provider handling PA requests",
    )
    effective_date = models.DateField(
        db_index=True,
        help_text="Date this PA requirement became effective",
    )
    end_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date this PA requirement ends (null = active)",
    )
    notes = models.TextField(
        blank=True,
        default="",
        help_text="Additional notes about PA requirements",
    )

    class Meta:
        db_table = "upstream_imagingparequirement"
        verbose_name = "Imaging PA Requirement"
        verbose_name_plural = "Imaging PA Requirements"
        ordering = ["payer", "cpt"]
        indexes = [
            models.Index(
                fields=["payer", "cpt"],
                name="imaging_pa_payer_cpt_idx"
            ),
            models.Index(
                fields=["effective_date"],
                name="imaging_pa_effective_idx"
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["payer", "cpt", "effective_date"],
                name="imaging_pa_unique_payer_cpt_date",
            ),
        ]

    def __str__(self):
        status = "Required" if self.pa_required else "Not Required"
        return f"{self.payer}/{self.cpt}: PA {status} ({self.rbm_provider})"

    @property
    def is_active(self):
        """Check if this PA requirement is currently active."""
        from django.utils import timezone

        today = timezone.now().date()
        if self.end_date and today > self.end_date:
            return False
        return today >= self.effective_date

    @classmethod
    def get_requirement(cls, payer, cpt, as_of_date=None):
        """
        Look up PA requirement for a payer/CPT combination.

        Args:
            payer: Payer name or ID
            cpt: CPT code
            as_of_date: Date to check (defaults to today)

        Returns:
            ImagingPARequirement or None if not found
        """
        from django.utils import timezone

        if as_of_date is None:
            as_of_date = timezone.now().date()

        qs = cls.objects.filter(
            payer=payer,
            cpt=cpt,
            effective_date__lte=as_of_date,
        )
        no_end = models.Q(end_date__isnull=True)
        active = models.Q(end_date__gte=as_of_date)
        qs = qs.filter(no_end | active)
        return qs.first()

    @classmethod
    def bulk_import_csv(cls, csv_data):
        """
        Bulk import PA requirements from CSV data.

        Expected CSV columns:
        payer,cpt,pa_required,rbm_provider,effective_date,end_date,notes

        Args:
            csv_data: List of dicts with CSV row data

        Returns:
            dict with import statistics
        """
        from datetime import datetime

        created = 0
        updated = 0
        errors = []

        for row in csv_data:
            try:
                # Parse dates
                eff_date = row.get("effective_date")
                if isinstance(eff_date, str):
                    eff_date = datetime.strptime(eff_date, "%Y-%m-%d").date()

                end_date = row.get("end_date")
                if end_date and isinstance(end_date, str):
                    end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

                # Parse boolean
                pa_req = row.get("pa_required", True)
                if isinstance(pa_req, str):
                    pa_req = pa_req.lower() in ("true", "yes", "1")

                obj, was_created = cls.objects.update_or_create(
                    payer=row["payer"],
                    cpt=row["cpt"],
                    effective_date=eff_date,
                    defaults={
                        "pa_required": pa_req,
                        "rbm_provider": row.get("rbm_provider", "NONE"),
                        "end_date": end_date,
                        "notes": row.get("notes", ""),
                    },
                )
                if was_created:
                    created += 1
                else:
                    updated += 1
            except Exception as e:
                errors.append({
                    "row": row,
                    "error": str(e),
                })

        return {
            "created": created,
            "updated": updated,
            "errors": errors,
            "total": created + updated,
        }
