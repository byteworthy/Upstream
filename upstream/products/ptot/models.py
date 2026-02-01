"""
PT/OT Models for G-Code Functional Limitation Tracking.

Medicare requires functional limitation G-codes at:
- Initial evaluation
- Every 10 visits (progress report)
- Discharge
"""

from django.db import models
from upstream.models import Customer
from upstream.core.managers import CustomerScopedManager


class PTOTFunctionalLimitation(models.Model):
    """
    Track G-code functional limitations for Medicare compliance.

    Medicare requires G-codes for 7 functional limitation categories.
    Each category has current status, goal, and (at discharge) discharge G-codes.
    """

    LIMITATION_CATEGORY_CHOICES = [
        ("MOBILITY", "Mobility"),
        ("CHANGING_POSITION", "Changing/Maintaining Position"),
        ("CARRYING", "Carrying/Moving Objects"),
        ("SELF_CARE", "Self Care"),
        ("OTHER_PT", "Other PT/OT Primary"),
        ("OTHER_SLP", "Other SLP Primary"),
        ("SWALLOWING", "Swallowing"),
    ]

    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("DISCHARGED", "Discharged"),
    ]

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="ptot_functional_limitations"
    )
    patient_id = models.CharField(max_length=100, db_index=True)

    # Limitation category
    limitation_category = models.CharField(
        max_length=50, choices=LIMITATION_CATEGORY_CHOICES
    )

    # G-codes (format: G8978-G8999)
    current_gcode = models.CharField(max_length=10)
    goal_gcode = models.CharField(max_length=10)
    discharge_gcode = models.CharField(max_length=10, null=True, blank=True)

    # Severity modifiers (CH through CN)
    current_severity = models.CharField(max_length=2)
    goal_severity = models.CharField(max_length=2)
    discharge_severity = models.CharField(max_length=2, null=True, blank=True)

    # Tracking dates
    evaluation_date = models.DateField()
    last_reported_date = models.DateField()
    visit_count_since_report = models.IntegerField(default=0)
    discharge_date = models.DateField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ACTIVE")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CustomerScopedManager()

    class Meta:
        db_table = "upstream_ptotfunctionallimitation"
        verbose_name = "PT/OT Functional Limitation"
        verbose_name_plural = "PT/OT Functional Limitations"
        indexes = [
            models.Index(
                fields=["customer", "patient_id"], name="ptot_fl_customer_patient_idx"
            ),
            models.Index(
                fields=["customer", "status"], name="ptot_fl_customer_status_idx"
            ),
            models.Index(fields=["limitation_category"], name="ptot_fl_category_idx"),
        ]

    def __str__(self):
        return f"{self.patient_id} - {self.limitation_category} ({self.current_gcode})"


class PTOTProgressReport(models.Model):
    """
    Track G-code reporting at evaluation, progress (every 10 visits), and discharge.
    """

    REPORTING_TYPE_CHOICES = [
        ("EVALUATION", "Evaluation"),
        ("PROGRESS", "Progress Report"),
        ("DISCHARGE", "Discharge"),
    ]

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="ptot_progress_reports"
    )
    functional_limitation = models.ForeignKey(
        PTOTFunctionalLimitation,
        on_delete=models.CASCADE,
        related_name="progress_reports",
    )

    report_date = models.DateField()
    visit_number = models.IntegerField()
    reporting_type = models.CharField(max_length=20, choices=REPORTING_TYPE_CHOICES)

    # G-codes reported in this report
    gcodes_reported = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now_add=True)

    objects = CustomerScopedManager()

    class Meta:
        db_table = "upstream_ptotprogressreport"
        verbose_name = "PT/OT Progress Report"
        verbose_name_plural = "PT/OT Progress Reports"
        indexes = [
            models.Index(
                fields=["customer", "report_date"], name="ptot_pr_customer_date_idx"
            ),
            models.Index(
                fields=["functional_limitation", "report_date"],
                name="ptot_pr_fl_date_idx",
            ),
        ]

    def __str__(self):
        return f"{self.reporting_type} - Visit {self.visit_number} ({self.report_date})"
