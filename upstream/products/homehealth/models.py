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


class CertificationCycle(BaseModel):
    """
    Track 60-day home health certification cycles.

    Medicare requires recertification every 60 days for continued care.
    This model tracks:
    - Cycle timing and deadlines
    - Physician recertification requirements
    - Face-to-face requirements for recertification
    - Alerts for approaching/overdue deadlines
    """

    STATUS_CHOICES = [
        ("ACTIVE", "Active Cycle"),
        ("PENDING_RECERT", "Pending Recertification"),
        ("RECERTIFIED", "Recertified"),
        ("DISCHARGED", "Patient Discharged"),
        ("EXPIRED", "Expired - No Recertification"),
    ]

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="certification_cycles",
    )
    episode = models.ForeignKey(
        HomeHealthEpisode,
        on_delete=models.CASCADE,
        related_name="certification_cycles",
    )

    # Cycle identification
    cycle_number = models.PositiveIntegerField(
        default=1,
        help_text="Certification cycle number (1 = initial, 2+ = recertification)",
    )
    cycle_start = models.DateField(
        db_index=True,
        help_text="Start date of this 60-day certification period",
    )
    cycle_end = models.DateField(
        db_index=True,
        help_text="End date of this certification period (start + 60 days)",
    )

    # Recertification requirements
    physician_recert_signed = models.BooleanField(
        default=False,
        help_text="Whether physician has signed recertification",
    )
    physician_recert_date = models.DateField(
        blank=True,
        null=True,
        help_text="Date physician signed recertification",
    )
    physician_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Name of certifying physician",
    )

    # Face-to-face requirements (for recertification)
    f2f_required = models.BooleanField(
        default=False,
        help_text="Whether F2F encounter required for this recertification",
    )
    f2f_completed = models.BooleanField(
        default=False,
        help_text="Whether required F2F has been completed",
    )
    f2f_date = models.DateField(
        blank=True,
        null=True,
        help_text="Date of F2F encounter for recertification",
    )

    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="ACTIVE",
        db_index=True,
    )

    # Alert tracking
    alert_45_day_sent = models.BooleanField(
        default=False,
        help_text="15-day warning alert has been sent",
    )
    alert_30_day_sent = models.BooleanField(
        default=False,
        help_text="30-day warning alert has been sent",
    )
    alert_21_day_sent = models.BooleanField(
        default=False,
        help_text="21-day urgent alert has been sent",
    )
    alert_14_day_sent = models.BooleanField(
        default=False,
        help_text="14-day critical alert has been sent",
    )

    objects = CustomerScopedManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "upstream_certificationcycle"
        verbose_name = "Certification Cycle"
        verbose_name_plural = "Certification Cycles"
        ordering = ["episode", "cycle_number"]
        indexes = [
            models.Index(
                fields=["customer", "status", "cycle_end"],
                name="cert_status_end_idx",
            ),
            models.Index(
                fields=["customer", "episode"],
                name="cert_customer_episode_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["episode", "cycle_number"],
                name="unique_episode_cycle",
            ),
        ]

    def __str__(self):
        return f"Cycle {self.cycle_number} for Episode {self.episode_id}"

    @property
    def days_remaining(self):
        """Calculate days until cycle end."""
        from datetime import date

        if self.cycle_end:
            return (self.cycle_end - date.today()).days
        return None

    @property
    def is_expiring_soon(self):
        """Check if cycle is expiring within 14 days."""
        remaining = self.days_remaining
        return remaining is not None and 0 < remaining <= 14

    @property
    def is_overdue(self):
        """Check if recertification is overdue."""
        from datetime import date

        if self.status in ("RECERTIFIED", "DISCHARGED"):
            return False
        return self.cycle_end and date.today() > self.cycle_end

    def calculate_cycle_end(self):
        """Calculate and set cycle end date (start + 60 days)."""
        from datetime import timedelta

        if self.cycle_start:
            self.cycle_end = self.cycle_start + timedelta(days=60)
            return self.cycle_end
        return None

    def mark_recertified(self, physician_name=None, recert_date=None):
        """
        Mark this cycle as recertified.

        Args:
            physician_name: Name of certifying physician
            recert_date: Date of recertification (defaults to today)
        """
        from datetime import date

        self.physician_recert_signed = True
        self.physician_recert_date = recert_date or date.today()
        if physician_name:
            self.physician_name = physician_name
        self.status = "RECERTIFIED"
        self.save()

    def create_next_cycle(self):
        """
        Create the next certification cycle.

        Returns:
            CertificationCycle: The newly created cycle
        """
        from datetime import timedelta

        if self.status != "RECERTIFIED":
            raise ValueError(
                "Cannot create next cycle until current cycle is recertified"
            )

        next_start = self.cycle_end + timedelta(days=1)
        next_end = next_start + timedelta(days=60)

        return CertificationCycle.objects.create(
            customer=self.customer,
            episode=self.episode,
            cycle_number=self.cycle_number + 1,
            cycle_start=next_start,
            cycle_end=next_end,
            status="ACTIVE",
        )
