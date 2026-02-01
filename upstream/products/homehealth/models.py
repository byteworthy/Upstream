"""
Home Health product line models.

Provides PDGM grouping lookup and episode tracking with F2F/NOA monitoring.
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from upstream.core.models import BaseModel
from upstream.models import Customer
from upstream.core.tenant import CustomerScopedManager


class HomeHealthPDGMGroup(BaseModel):
    """
    PDGM (Patient-Driven Grouping Model) group lookup table.

    Stores the 432+ possible PDGM group combinations with their
    HIPPS codes and payment weights for home health billing validation.
    """

    TIMING_CHOICES = [
        ("EARLY", "Early (within 30 days of discharge)"),
        ("LATE", "Late (31+ days or community admission)"),
    ]

    CLINICAL_GROUP_CHOICES = [
        ("MMTA", "Medication Management, Teaching and Assessment"),
        ("MMTA_SURG", "MMTA - Surgical Aftercare"),
        ("WOUND", "Wound/Ostomy Care"),
        ("NEURO_REHAB", "Neurological/Stroke Rehabilitation"),
        ("COMPLEX_NURS", "Complex Nursing Interventions"),
        ("MS_REHAB", "Musculoskeletal Rehabilitation"),
        ("BEHAVIORAL", "Behavioral Health Care"),
        ("CARDIAC", "Cardiac/Circulatory Care"),
        ("DIABETES", "Endocrine/Diabetes Care"),
        ("RESP", "Respiratory Care"),
        ("GI_GU", "GI/GU Care"),
        ("SKIN", "Skin Care (non-wound)"),
    ]

    FUNCTIONAL_LEVEL_CHOICES = [
        ("LOW", "Low functional impairment"),
        ("MEDIUM", "Medium functional impairment"),
        ("HIGH", "High functional impairment"),
    ]

    COMORBIDITY_CHOICES = [
        ("NONE", "No qualifying comorbidities"),
        ("LOW", "Low comorbidity adjustment"),
        ("HIGH", "High comorbidity adjustment"),
    ]

    timing = models.CharField(
        max_length=10,
        choices=TIMING_CHOICES,
        db_index=True,
        help_text="Admission source/timing category",
    )
    clinical_group = models.CharField(
        max_length=20,
        choices=CLINICAL_GROUP_CHOICES,
        db_index=True,
        help_text="Clinical grouping based on principal diagnosis",
    )
    functional_level = models.CharField(
        max_length=10,
        choices=FUNCTIONAL_LEVEL_CHOICES,
        db_index=True,
        help_text="Functional level based on OASIS scores",
    )
    comorbidity = models.CharField(
        max_length=10,
        choices=COMORBIDITY_CHOICES,
        db_index=True,
        help_text="Comorbidity adjustment level",
    )
    hipps_code = models.CharField(
        max_length=10,
        unique=True,
        help_text="HIPPS code for this PDGM group",
    )
    payment_weight = models.FloatField(
        validators=[MinValueValidator(0.0)],
        help_text="Payment weight multiplier for this group",
    )

    class Meta:
        db_table = "upstream_homehealthpdgmgroup"
        verbose_name = "Home Health PDGM Group"
        verbose_name_plural = "Home Health PDGM Groups"
        ordering = ["timing", "clinical_group", "functional_level", "comorbidity"]
        constraints = [
            models.UniqueConstraint(
                fields=["timing", "clinical_group", "functional_level", "comorbidity"],
                name="hh_pdgm_unique_combo",
            ),
            models.CheckConstraint(
                condition=models.Q(payment_weight__gte=0),
                name="hh_pdgm_weight_positive",
            ),
        ]
        indexes = [
            models.Index(
                fields=["timing", "clinical_group"],
                name="hh_pdgm_timing_grp_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.hipps_code}: {self.timing}/{self.clinical_group}/"
            f"{self.functional_level}/{self.comorbidity}"
        )


class HomeHealthEpisode(BaseModel):
    """
    Home health episode tracking with F2F and NOA compliance monitoring.

    Tracks patient episodes including:
    - Start of Care (SOC) date
    - Face-to-Face (F2F) encounter timing
    - Notice of Admission (NOA) submission status
    - PDGM grouping validation
    """

    STATUS_CHOICES = [
        ("ACTIVE", "Active Episode"),
        ("COMPLETED", "Episode Completed"),
        ("DISCHARGED", "Patient Discharged"),
        ("TRANSFERRED", "Transferred to Another Agency"),
    ]

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="homehealth_episodes",
    )
    patient_identifier = models.CharField(
        max_length=255,
        help_text="Patient ID (should be encrypted in production)",
    )
    payer = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Primary payer for this episode",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="ACTIVE",
        db_index=True,
    )

    # Episode dates
    soc_date = models.DateField(
        db_index=True,
        help_text="Start of Care date",
    )
    episode_end_date = models.DateField(
        blank=True,
        null=True,
        help_text="Episode end date (60-day periods)",
    )

    # Face-to-Face tracking
    f2f_date = models.DateField(
        blank=True,
        null=True,
        help_text="Face-to-Face encounter date",
    )
    f2f_physician = models.CharField(
        max_length=255,
        blank=True,
        help_text="Certifying physician for F2F",
    )
    f2f_is_valid = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether F2F timing is within requirements",
    )

    # NOA tracking
    noa_submitted_date = models.DateField(
        blank=True,
        null=True,
        help_text="Date NOA was submitted to Medicare",
    )
    noa_deadline_date = models.DateField(
        blank=True,
        null=True,
        help_text="NOA submission deadline (SOC + 5 days)",
    )
    noa_is_timely = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether NOA was submitted on time",
    )

    # PDGM grouping
    pdgm_group = models.ForeignKey(
        HomeHealthPDGMGroup,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="episodes",
        help_text="Assigned PDGM group for this episode",
    )
    timing = models.CharField(
        max_length=10,
        blank=True,
        help_text="EARLY or LATE timing classification",
    )
    clinical_group = models.CharField(
        max_length=20,
        blank=True,
        help_text="Clinical group classification",
    )
    functional_level = models.CharField(
        max_length=10,
        blank=True,
        help_text="Functional impairment level",
    )
    comorbidity = models.CharField(
        max_length=10,
        blank=True,
        help_text="Comorbidity adjustment level",
    )

    # OASIS assessment data
    oasis_date = models.DateField(
        blank=True,
        null=True,
        help_text="Date of OASIS assessment",
    )
    oasis_functional_score = models.IntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(0), MaxValueValidator(30)],
        help_text="OASIS functional score (0-30)",
    )

    # Tenant isolation
    objects = CustomerScopedManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "upstream_homehealthepisode"
        verbose_name = "Home Health Episode"
        verbose_name_plural = "Home Health Episodes"
        ordering = ["-soc_date"]
        indexes = [
            models.Index(
                fields=["customer", "status", "soc_date"],
                name="hh_ep_status_idx",
            ),
            models.Index(
                fields=["customer", "payer", "-soc_date"],
                name="hh_ep_payer_idx",
            ),
            models.Index(
                fields=["customer", "f2f_is_valid"],
                name="hh_ep_f2f_idx",
            ),
            models.Index(
                fields=["customer", "noa_is_timely"],
                name="hh_ep_noa_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(oasis_functional_score__gte=0)
                & models.Q(oasis_functional_score__lte=30)
                | models.Q(oasis_functional_score__isnull=True),
                name="hh_ep_oasis_range",
            ),
        ]

    def __str__(self):
        return f"Episode {self.id}: {self.patient_identifier} ({self.status})"

    @property
    def days_to_f2f(self):
        """Calculate days between SOC and F2F."""
        if self.soc_date and self.f2f_date:
            return (self.f2f_date - self.soc_date).days
        return None

    @property
    def noa_days_remaining(self):
        """Calculate days until NOA deadline."""
        from datetime import date

        if self.noa_deadline_date and not self.noa_submitted_date:
            return (self.noa_deadline_date - date.today()).days
        return None

    def validate_f2f_timing(self):
        """
        Validate F2F timing against requirements.
        F2F must occur within 90 days prior to or 30 days after SOC.
        """
        from upstream.products.homehealth.constants import F2F_PRIOR_DAYS, F2F_POST_DAYS

        if not self.f2f_date or not self.soc_date:
            self.f2f_is_valid = False
            return False

        days_from_soc = (self.f2f_date - self.soc_date).days

        # F2F can be up to 90 days before SOC or up to 30 days after
        self.f2f_is_valid = -F2F_PRIOR_DAYS <= days_from_soc <= F2F_POST_DAYS
        return self.f2f_is_valid

    def calculate_noa_deadline(self):
        """Calculate and set NOA deadline based on SOC date."""
        from datetime import timedelta
        from upstream.products.homehealth.constants import NOA_DEADLINE_DAYS

        if self.soc_date:
            self.noa_deadline_date = self.soc_date + timedelta(days=NOA_DEADLINE_DAYS)
            return self.noa_deadline_date
        return None

    def validate_noa_timeliness(self):
        """Validate whether NOA was submitted on time."""
        if not self.noa_deadline_date:
            self.calculate_noa_deadline()

        if self.noa_submitted_date and self.noa_deadline_date:
            self.noa_is_timely = self.noa_submitted_date <= self.noa_deadline_date
        else:
            self.noa_is_timely = False

        return self.noa_is_timely

    def lookup_pdgm_group(self):
        """Look up and assign PDGM group based on episode characteristics."""
        if not all(
            [self.timing, self.clinical_group, self.functional_level, self.comorbidity]
        ):
            return None

        try:
            group = HomeHealthPDGMGroup.objects.get(
                timing=self.timing.upper(),
                clinical_group=self.clinical_group.upper(),
                functional_level=self.functional_level.upper(),
                comorbidity=self.comorbidity.upper(),
            )
            self.pdgm_group = group
            return group
        except HomeHealthPDGMGroup.DoesNotExist:
            return None
