from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings
from upstream.core.tenant import CustomerScopedManager


class Customer(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


class Settings(models.Model):
    customer = models.OneToOneField(
        Customer, on_delete=models.CASCADE, related_name="settings"
    )
    to_email = models.EmailField()
    cc_email = models.EmailField(blank=True, null=True)
    attach_pdf = models.BooleanField(default=True)

    # Tenant isolation
    objects = CustomerScopedManager()
    all_objects = models.Manager()  # Unfiltered access for superusers

    def __str__(self):
        return f"Settings for {self.customer.name}"


class Upload(models.Model):
    STATUS_CHOICES = [
        ("processing", "Processing"),
        ("success", "Success"),
        ("failed", "Failed"),
        ("partial", "Partial Success"),
    ]

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="uploads"
    )
    # HIGH-14: Add db_index for query performance on date filtering/ordering
    uploaded_at = models.DateTimeField(auto_now_add=True, db_index=True)
    filename = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="processing"
    )
    error_message = models.TextField(blank=True, null=True)
    row_count = models.IntegerField(blank=True, null=True)
    # HIGH-14: Add db_index for date range queries
    date_min = models.DateField(blank=True, null=True, db_index=True)
    date_max = models.DateField(blank=True, null=True, db_index=True)

    # Processing metadata (additive)
    processing_started_at = models.DateTimeField(blank=True, null=True)
    processing_completed_at = models.DateTimeField(blank=True, null=True)
    processing_duration_seconds = models.IntegerField(
        blank=True, null=True, help_text="Time taken to process upload"
    )

    # Quality tracking (additive)
    accepted_row_count = models.IntegerField(
        default=0, help_text="Number of rows that passed validation"
    )
    rejected_row_count = models.IntegerField(
        default=0, help_text="Number of rows that failed validation"
    )
    warning_row_count = models.IntegerField(
        default=0, help_text="Number of rows with warnings"
    )

    # File metadata
    file_size_bytes = models.BigIntegerField(blank=True, null=True)
    file_hash = models.CharField(
        max_length=64, blank=True, null=True, help_text="SHA-256 hash for deduplication"
    )
    # HIGH-15: Remove null=True - inconsistent with default="utf-8" (always has value)
    file_encoding = models.CharField(max_length=50, blank=True, default="utf-8")

    # Upload context
    uploaded_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploads",
        help_text="User who uploaded this file",
    )
    upload_source = models.CharField(
        max_length=50,
        default="web_ui",
        choices=[("web_ui", "Web UI"), ("api", "API"), ("batch", "Batch Process")],
        help_text="How this file was uploaded",
    )

    # Validation summary
    validation_errors = models.JSONField(
        default=list, blank=True, help_text="Summary of validation errors by type"
    )
    data_quality_issues = models.JSONField(
        default=dict, blank=True, help_text="Summary of data quality issues found"
    )

    # Tenant isolation
    objects = CustomerScopedManager()
    all_objects = models.Manager()  # Unfiltered access for superusers

    class Meta:
        constraints = [
            # HIGH-12: Unique constraint on file_hash for deduplication
            # Prevents duplicate file uploads within a customer's scope
            models.UniqueConstraint(
                fields=["customer", "file_hash"],
                condition=models.Q(file_hash__isnull=False),
                name="upload_unique_file_hash_per_customer",
            ),
            # CHECK constraints for data integrity (Phase 3 Task #3)
            models.CheckConstraint(
                check=models.Q(row_count__gte=0) | models.Q(row_count__isnull=True),
                name="upload_row_count_nonnegative",
            ),
            models.CheckConstraint(
                check=models.Q(accepted_row_count__gte=0),
                name="upload_accepted_count_nonnegative",
            ),
            models.CheckConstraint(
                check=models.Q(rejected_row_count__gte=0),
                name="upload_rejected_count_nonnegative",
            ),
            models.CheckConstraint(
                check=models.Q(warning_row_count__gte=0),
                name="upload_warning_count_nonnegative",
            ),
            models.CheckConstraint(
                check=models.Q(date_min__lte=models.F("date_max"))
                | models.Q(date_min__isnull=True)
                | models.Q(date_max__isnull=True),
                name="upload_date_range_logical",
            ),
            models.CheckConstraint(
                check=models.Q(
                    status__in=["processing", "success", "failed", "partial"]
                ),
                name="upload_status_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["customer", "uploaded_at"], name="upload_cust_date_idx"
            ),
            models.Index(fields=["customer", "status"], name="upload_cust_status_idx"),
            models.Index(fields=["customer", "file_hash"], name="upload_file_hash_idx"),
            # Covering index for customer + uploaded_at + status queries
            models.Index(
                fields=["customer", "-uploaded_at", "status"],
                name="upload_cust_date_status_cov",
            ),
        ]

    @property
    def quality_score(self):
        """Calculate data quality score (0.0 to 1.0)."""
        if not hasattr(self, "quality_report") or not self.quality_report:
            # Fallback to basic calculation
            if self.row_count and self.row_count > 0:
                return self.accepted_row_count / self.row_count
            return None
        report = self.quality_report
        if report.total_rows == 0:
            return 0.0
        return report.accepted_rows / report.total_rows

    @property
    def acceptance_rate(self):
        """Calculate acceptance rate percentage."""
        score = self.quality_score
        if score is not None:
            return score * 100
        return None

    @property
    def has_quality_issues(self):
        """Check if upload has any quality issues."""
        return (
            self.rejected_row_count > 0
            or self.warning_row_count > 0
            or len(self.data_quality_issues or {}) > 0
        )

    @property
    def processing_speed(self):
        """Calculate rows processed per second."""
        if self.processing_duration_seconds and self.row_count:
            return self.row_count / self.processing_duration_seconds
        return None

    def __str__(self):
        return f"{self.filename} ({self.status})"


class DataQualityReport(models.Model):
    """
    Data quality report for CSV upload validation.

    Tracks which rows were accepted/rejected and why.
    Enables "Trust before scale" principle by showing operators
    exactly what data passed validation.
    """

    upload = models.OneToOneField(
        Upload, on_delete=models.CASCADE, related_name="quality_report"
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="quality_reports"
    )

    # Summary metrics
    total_rows = models.IntegerField(default=0, help_text="Total rows in CSV file")
    accepted_rows = models.IntegerField(
        default=0, help_text="Rows that passed validation"
    )
    rejected_rows = models.IntegerField(
        default=0, help_text="Rows that failed validation"
    )

    # Detailed rejection tracking
    rejection_details = models.JSONField(
        default=dict,
        help_text="Map of row numbers to rejection reasons: {row_num: reason}",
    )

    # Validation warnings (non-fatal)
    warnings = models.JSONField(
        default=list, help_text="List of warning messages: [{row: int, message: str}]"
    )

    # Quality metrics
    phi_detections = models.IntegerField(
        default=0, help_text="Number of rows rejected for potential PHI"
    )
    missing_fields = models.IntegerField(
        default=0, help_text="Number of rows rejected for missing required fields"
    )
    invalid_dates = models.IntegerField(
        default=0, help_text="Number of rows rejected for invalid date formats"
    )
    invalid_values = models.IntegerField(
        default=0, help_text="Number of rows rejected for invalid field values"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    # Tenant isolation
    objects = CustomerScopedManager()
    all_objects = models.Manager()  # Unfiltered access for superusers

    class Meta:
        constraints = [
            # CHECK constraints for data integrity (Phase 3 Task #3)
            models.CheckConstraint(
                check=models.Q(total_rows__gte=0), name="dqr_total_rows_nonnegative"
            ),
            models.CheckConstraint(
                check=models.Q(accepted_rows__gte=0),
                name="dqr_accepted_rows_nonnegative",
            ),
            models.CheckConstraint(
                check=models.Q(rejected_rows__gte=0),
                name="dqr_rejected_rows_nonnegative",
            ),
            models.CheckConstraint(
                check=models.Q(phi_detections__gte=0),
                name="dqr_phi_detections_nonnegative",
            ),
            models.CheckConstraint(
                check=models.Q(missing_fields__gte=0),
                name="dqr_missing_fields_nonnegative",
            ),
            models.CheckConstraint(
                check=models.Q(invalid_dates__gte=0),
                name="dqr_invalid_dates_nonnegative",
            ),
            models.CheckConstraint(
                check=models.Q(invalid_values__gte=0),
                name="dqr_invalid_values_nonnegative",
            ),
            models.CheckConstraint(
                check=models.Q(accepted_rows__lte=models.F("total_rows")),
                name="dqr_accepted_lte_total",
            ),
            models.CheckConstraint(
                check=models.Q(rejected_rows__lte=models.F("total_rows")),
                name="dqr_rejected_lte_total",
            ),
        ]
        indexes = [
            models.Index(
                fields=["customer", "-created_at"], name="dqr_cust_created_idx"
            ),
            models.Index(fields=["upload"], name="dqr_upload_idx"),
            # Covering index for aggregate queries - uses DataQualityReport.created_at
            models.Index(
                fields=["customer", "-created_at"],
                name="dqr_cust_date_agg_idx",
            ),
        ]

    def __str__(self):
        quality_pct = (
            (self.accepted_rows / self.total_rows * 100) if self.total_rows > 0 else 0
        )
        return f"Quality Report: {self.upload.filename} ({quality_pct:.1f}% accepted)"

    @property
    def quality_score(self):
        """Calculate quality score (0.0 to 1.0)."""
        if self.total_rows == 0:
            return 0.0
        return self.accepted_rows / self.total_rows

    @property
    def has_issues(self):
        """Returns True if there were any rejections or warnings."""
        return self.rejected_rows > 0 or len(self.warnings) > 0

    def get_rejection_summary(self):
        """Get human-readable summary of rejection reasons."""
        summary = {}
        if self.phi_detections > 0:
            summary["PHI detected"] = self.phi_detections
        if self.missing_fields > 0:
            summary["Missing required fields"] = self.missing_fields
        if self.invalid_dates > 0:
            summary["Invalid dates"] = self.invalid_dates
        if self.invalid_values > 0:
            summary["Invalid values"] = self.invalid_values
        return summary


class ClaimRecord(models.Model):
    OUTCOME_CHOICES = [
        ("PAID", "Paid"),
        ("DENIED", "Denied"),
        ("OTHER", "Other"),
    ]

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="claim_records"
    )
    # CRIT-8: Changed from CASCADE to PROTECT to preserve audit trail
    # Prevents deletion of Upload if ClaimRecords exist (HIPAA compliance)
    upload = models.ForeignKey(
        Upload, on_delete=models.PROTECT, related_name="claim_records"
    )
    # CRIT-3: Changed from TextField to CharField with indexes for query performance
    payer = models.CharField(
        max_length=255, db_index=True, help_text="Insurance payer name"
    )
    cpt = models.CharField(max_length=20, db_index=True, help_text="CPT procedure code")
    cpt_group = models.CharField(
        max_length=50,
        db_index=True,
        default="OTHER",
        help_text="CPT code group for analytics",
    )
    # HIGH-14: Add db_index for analytics and date range filtering
    submitted_date = models.DateField(db_index=True)
    decided_date = models.DateField(db_index=True)
    outcome = models.CharField(max_length=20, choices=OUTCOME_CHOICES)
    allowed_amount = models.DecimalField(
        max_digits=12, decimal_places=2, blank=True, null=True
    )

    # DenialScope fields - additive for Sprint 2
    denial_reason_code = models.CharField(
        max_length=50, blank=True, null=True, help_text="Denial reason code from payer"
    )
    denial_reason_text = models.TextField(
        blank=True, null=True, help_text="Denial reason description"
    )

    # Advanced analytics fields (additive)
    billed_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Original billed amount",
    )
    paid_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Amount actually paid (may differ from allowed)",
    )
    # HIGH-14: Add db_index for payment tracking queries
    payment_date = models.DateField(
        blank=True,
        null=True,
        db_index=True,
        help_text="Actual payment date (if different from decided_date)",
    )

    # Authorization tracking
    authorization_required = models.BooleanField(
        default=False, db_index=True, help_text="Whether prior auth was required"
    )
    authorization_number = models.CharField(max_length=100, blank=True, null=True)
    authorization_obtained = models.BooleanField(
        default=False, help_text="Whether auth was obtained before service"
    )

    # Claim complexity indicators
    modifier_codes = models.JSONField(
        default=list, blank=True, help_text="List of modifier codes used"
    )
    diagnosis_codes = models.JSONField(
        default=list, blank=True, help_text="List of diagnosis codes"
    )
    procedure_count = models.IntegerField(
        default=1, help_text="Number of procedures on this claim"
    )

    # Data quality tracking
    data_quality_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        blank=True,
        null=True,
        help_text="Quality score for this claim (0.0 = poor, 1.0 = perfect)",
    )
    data_quality_flags = models.JSONField(
        default=list,
        blank=True,
        help_text="List of quality issues: [{severity, message, field}]",
    )

    # Validation metadata
    validation_passed = models.BooleanField(default=True, db_index=True)
    validation_timestamp = models.DateTimeField(blank=True, null=True)

    # Processing metadata
    # HIGH-15: Remove null=True - inconsistent with auto_now_add (always sets value)
    processed_at = models.DateTimeField(auto_now_add=True, db_index=True)
    # HIGH-15: Remove null=True - inconsistent with auto_now (always sets value)
    updated_at = models.DateTimeField(auto_now=True)

    # Source data tracking (for audit trail)
    source_row_number = models.IntegerField(
        blank=True, null=True, help_text="Row number in source CSV file"
    )
    source_data_hash = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        help_text="SHA-256 hash of source row for deduplication",
    )

    # Multi-channel ingestion tracking
    SUBMITTED_VIA_CHOICES = [
        ("csv_upload", "CSV Upload"),
        ("ehr_webhook", "EHR Webhook"),
        ("api", "API"),
        ("batch_import", "Batch Import"),
    ]
    submitted_via = models.CharField(
        max_length=20,
        choices=SUBMITTED_VIA_CHOICES,
        default="csv_upload",
        db_index=True,
        help_text="Source of claim submission for multi-channel ingestion tracking",
    )

    # Tenant isolation
    objects = CustomerScopedManager()
    all_objects = models.Manager()  # Unfiltered access for superusers

    class Meta:
        constraints = [
            # HIGH-12: Unique constraint on source_data_hash for deduplication
            # Prevents duplicate row processing within an upload
            models.UniqueConstraint(
                fields=["customer", "upload", "source_data_hash"],
                condition=models.Q(source_data_hash__isnull=False),
                name="claim_unique_source_hash_per_upload",
            ),
            # CHECK constraints for data integrity (Phase 3 Task #3)
            models.CheckConstraint(
                check=models.Q(data_quality_score__gte=0.0)
                & models.Q(data_quality_score__lte=1.0)
                | models.Q(data_quality_score__isnull=True),
                name="claim_quality_score_range",
            ),
            models.CheckConstraint(
                check=models.Q(procedure_count__gte=1),
                name="claim_procedure_count_positive",
            ),
            models.CheckConstraint(
                check=models.Q(allowed_amount__gte=0)
                | models.Q(allowed_amount__isnull=True),
                name="claim_allowed_amount_nonnegative",
            ),
            models.CheckConstraint(
                check=models.Q(billed_amount__gte=0)
                | models.Q(billed_amount__isnull=True),
                name="claim_billed_amount_nonnegative",
            ),
            models.CheckConstraint(
                check=models.Q(paid_amount__gte=0) | models.Q(paid_amount__isnull=True),
                name="claim_paid_amount_nonnegative",
            ),
            models.CheckConstraint(
                check=models.Q(submitted_date__lte=models.F("decided_date")),
                name="claim_dates_logical_order",
            ),
        ]
        indexes = [
            models.Index(
                fields=["customer", "submitted_date"], name="claim_cust_subdate_idx"
            ),
            models.Index(
                fields=["customer", "decided_date"], name="claim_cust_decdate_idx"
            ),
            models.Index(
                fields=["customer", "payer", "submitted_date"],
                name="claim_cust_payer_date_idx",
            ),
            models.Index(
                fields=["customer", "outcome", "decided_date"],
                name="claim_cust_outcome_idx",
            ),
            # CRIT-3: Composite index for common filter patterns
            models.Index(
                fields=["customer", "payer", "outcome", "submitted_date"],
                name="claim_payer_outcome_idx",
            ),
            # New indexes for advanced features
            models.Index(
                fields=["customer", "authorization_required", "authorization_obtained"],
                name="claim_auth_idx",
            ),
            # Covering indexes for aggregate queries (Phase 3 Task #2)
            models.Index(
                fields=["customer", "decided_date", "payer", "cpt_group", "outcome"],
                name="claim_analytics_agg_idx",
            ),
            models.Index(
                fields=["customer", "payer", "-decided_date"],
                name="claim_payer_payment_idx",
            ),
            models.Index(
                fields=["customer", "validation_passed", "processed_at"],
                name="claim_validation_idx",
            ),
            models.Index(
                fields=["customer", "payment_date"], name="claim_payment_date_idx"
            ),
            # QW-2: Performance indexes for common query patterns
            models.Index(
                fields=["customer", "payer", "cpt_group"], name="claim_drift_detect_idx"
            ),
            models.Index(
                fields=["customer", "submitted_date", "decided_date"],
                name="claim_lag_analysis_idx",
            ),
            # HIGH-12: Index for source_data_hash lookups
            models.Index(
                fields=["customer", "upload", "source_data_hash"],
                name="claim_source_hash_idx",
            ),
            # Covering index for customer + decided_date + outcome queries
            models.Index(
                fields=["customer", "-decided_date", "outcome"],
                name="claim_cust_date_outcome_cov",
            ),
        ]

    def __str__(self):
        return f"Claim {self.id} - {self.payer} - {self.outcome}"

    @property
    def days_to_decision(self):
        """Calculate days between submission and decision."""
        if self.submitted_date and self.decided_date:
            return (self.decided_date - self.submitted_date).days
        return None

    @property
    def days_to_payment(self):
        """Calculate days between submission and payment."""
        if self.submitted_date and self.payment_date:
            return (self.payment_date - self.submitted_date).days
        return None

    @property
    def payment_variance(self):
        """Calculate variance between allowed and paid amounts."""
        if self.allowed_amount and self.paid_amount:
            return float(self.paid_amount - self.allowed_amount)
        return None

    @property
    def is_underpayment(self):
        """Check if paid amount is less than allowed."""
        if self.allowed_amount and self.paid_amount:
            return self.paid_amount < self.allowed_amount
        return False

    @property
    def complexity_score(self):
        """Calculate claim complexity score (0-10)."""
        score = 0
        # Base complexity from procedure count
        score += min(self.procedure_count, 5)
        # Modifiers add complexity
        score += min(len(self.modifier_codes or []), 3)
        # Diagnoses add complexity
        score += min(len(self.diagnosis_codes or []) / 2, 2)
        return min(int(score), 10)


class ReportRun(models.Model):
    REPORT_TYPE_CHOICES = [
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
        ("custom", "Custom"),
    ]

    STATUS_CHOICES = [
        ("running", "Running"),
        ("success", "Success"),
        ("failed", "Failed"),
    ]

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="report_runs"
    )
    run_type = models.CharField(
        max_length=20, choices=REPORT_TYPE_CHOICES, default="weekly"
    )
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="running")
    summary_json = models.JSONField(blank=True, null=True)

    # Tenant isolation
    objects = CustomerScopedManager()
    all_objects = models.Manager()  # Unfiltered access for superusers

    class Meta:
        indexes = [
            models.Index(
                fields=["customer", "status", "-started_at"],
                name="reportrun_cust_status_idx",
            ),
            models.Index(
                fields=["customer", "run_type", "-started_at"],
                name="reportrun_cust_type_idx",
            ),
            models.Index(
                fields=["status", "-started_at"], name="reportrun_status_date_idx"
            ),
        ]

    def __str__(self):
        return f"Report {self.id} - {self.run_type} ({self.status})"


class DriftEvent(models.Model):
    DRIFT_TYPE_CHOICES = [
        ("DENIAL_RATE", "Denial Rate"),
        ("DECISION_TIME", "Decision Time"),
        ("PAYMENT_AMOUNT", "Payment Amount"),
        ("APPROVAL_RATE", "Approval Rate"),
        ("PROCESSING_DELAY", "Processing Delay"),
        ("AUTH_FAILURE_RATE", "Authorization Failure Rate"),
    ]

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="drift_events"
    )
    report_run = models.ForeignKey(
        ReportRun, on_delete=models.CASCADE, related_name="drift_events"
    )
    payer = models.TextField()
    cpt_group = models.TextField()
    drift_type = models.CharField(max_length=30, choices=DRIFT_TYPE_CHOICES)
    baseline_value = models.FloatField()
    current_value = models.FloatField()
    delta_value = models.FloatField()
    severity = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    confidence = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    baseline_start = models.DateField()
    baseline_end = models.DateField()
    current_start = models.DateField()
    current_end = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    # Advanced statistical fields (additive)
    baseline_sample_size = models.IntegerField(
        default=0, help_text="Number of claims in baseline period"
    )
    current_sample_size = models.IntegerField(
        default=0, help_text="Number of claims in current period"
    )
    baseline_std_dev = models.FloatField(
        blank=True, null=True, help_text="Standard deviation of baseline"
    )
    statistical_significance = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        blank=True,
        null=True,
        help_text="P-value from statistical test (lower = more significant)",
    )

    # Financial impact tracking
    estimated_revenue_impact = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Estimated monthly revenue impact of this drift",
    )

    # Trend analysis
    trend_direction = models.CharField(
        max_length=20,
        choices=[
            ("improving", "Improving"),
            ("degrading", "Degrading"),
            ("stable", "Stable"),
        ],
        default="stable",
        db_index=True,
    )
    consecutive_periods = models.IntegerField(
        default=1, help_text="Number of consecutive periods this drift has persisted"
    )

    # Root cause hints
    potential_root_causes = models.JSONField(
        default=list,
        blank=True,
        help_text="AI-suggested root causes: [{cause, likelihood}]",
    )

    # Suppression tracking
    suppressed = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether this event was suppressed from alerting",
    )
    suppression_reason = models.TextField(
        blank=True, help_text="Why this event was suppressed"
    )

    # Tenant isolation
    objects = CustomerScopedManager()
    all_objects = models.Manager()  # Unfiltered access for superusers

    class Meta:
        constraints = [
            # CHECK constraints for data integrity (Phase 3 Task #3)
            models.CheckConstraint(
                check=models.Q(severity__gte=0.0) & models.Q(severity__lte=1.0),
                name="drift_severity_range",
            ),
            models.CheckConstraint(
                check=models.Q(confidence__gte=0.0) & models.Q(confidence__lte=1.0),
                name="drift_confidence_range",
            ),
            models.CheckConstraint(
                check=models.Q(statistical_significance__gte=0.0)
                & models.Q(statistical_significance__lte=1.0)
                | models.Q(statistical_significance__isnull=True),
                name="drift_significance_range",
            ),
            # DB-02: Unique constraint prevents duplicate drift signals
            # Each (customer, report_run, payer, cpt_group, drift_type) combination
            # can only have one DriftEvent record
            models.UniqueConstraint(
                fields=["customer", "report_run", "payer", "cpt_group", "drift_type"],
                name="driftevent_unique_signal",
            ),
        ]
        indexes = [
            models.Index(
                fields=["customer", "-created_at"], name="drift_cust_created_idx"
            ),
            models.Index(
                fields=["customer", "payer", "drift_type"],
                name="drift_cust_payer_type_idx",
            ),
            models.Index(
                fields=["customer", "drift_type", "-created_at"],
                name="drift_cust_type_date_idx",
            ),
            # New indexes
            models.Index(
                fields=["customer", "trend_direction", "-severity"],
                name="drift_trend_sev_idx",
            ),
            models.Index(
                fields=["customer", "suppressed", "-created_at"],
                name="drift_suppressed_idx",
            ),
            # QW-2: Performance indexes for dashboard and filtering
            models.Index(
                fields=["customer", "report_run", "-severity"],
                name="drift_report_sev_idx",
            ),
            models.Index(
                fields=["payer", "cpt_group", "-created_at"],
                name="drift_hist_trend_idx",
            ),
            # Covering index for customer + created_at + severity queries
            models.Index(
                fields=["customer", "-created_at", "severity"],
                name="drift_cust_date_sev_cov",
            ),
        ]

    def __str__(self):
        return f"Drift Event {self.id} - {self.drift_type} - {self.payer}"

    @property
    def delta_percentage(self):
        """Calculate percentage change from baseline."""
        if self.baseline_value and self.baseline_value != 0:
            return (self.delta_value / self.baseline_value) * 100
        return 0

    @property
    def is_statistically_significant(self):
        """Check if drift is statistically significant (p < 0.05)."""
        if self.statistical_significance is not None:
            return self.statistical_significance < 0.05
        return False

    @property
    def severity_label(self):
        """Human-readable severity label."""
        if self.severity >= 0.9:
            return "Critical"
        elif self.severity >= 0.7:
            return "High"
        elif self.severity >= 0.4:
            return "Medium"
        else:
            return "Low"

    @property
    def confidence_label(self):
        """Human-readable confidence label."""
        if self.confidence >= 0.9:
            return "Very High"
        elif self.confidence >= 0.75:
            return "High"
        elif self.confidence >= 0.6:
            return "Medium"
        else:
            return "Low"


class UserProfile(models.Model):
    """User profile linking users to customers with roles."""

    ROLE_CHOICES = [
        ("owner", "Owner"),
        ("admin", "Admin"),
        ("analyst", "Analyst"),
        ("viewer", "Viewer"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
        db_index=True,
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="user_profiles", db_index=True
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="viewer")

    def __str__(self):
        return f"Profile for {self.user.username} ({self.role}) -> {self.customer.name}"

    @property
    def is_owner(self):
        return self.role == "owner"

    @property
    def is_admin(self):
        return self.role in ("owner", "admin")

    @property
    def is_analyst(self):
        return self.role in ("owner", "admin", "analyst")

    @property
    def can_manage_users(self):
        """Check if user can manage team members."""
        return self.role in ("owner", "admin")

    class Meta:
        indexes = [
            models.Index(
                fields=["customer", "role"],
                name="userprofile_customer_role_idx",
            ),
        ]

    @property
    def can_manage_alerts(self):
        """Check if user can manage alert rules and routing."""
        return self.role in ("owner", "admin")

    @property
    def can_manage_webhooks(self):
        """Check if user can manage webhooks."""
        return self.role in ("owner", "admin")

    @property
    def can_upload_claims(self):
        """Check if user can upload claim files."""
        return self.role in ("owner", "admin", "analyst")

    @property
    def can_manage_mappings(self):
        """Check if user can manage payer/CPT mappings."""
        return self.role in ("owner", "admin", "analyst")

    @property
    def can_view_reports(self):
        """Check if user can view reports and drift feed."""
        return True  # All roles can view


class PayerMapping(models.Model):
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="payer_mappings"
    )
    raw_name = models.CharField(max_length=255)
    normalized_name = models.CharField(max_length=255)

    # Tenant isolation
    objects = CustomerScopedManager()
    all_objects = models.Manager()  # Unfiltered access for superusers

    class Meta:
        unique_together = ("customer", "raw_name")

    def __str__(self):
        return f"{self.raw_name} -> {self.normalized_name}"


class CPTGroupMapping(models.Model):
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="cpt_group_mappings"
    )
    cpt_code = models.CharField(max_length=10)
    cpt_group = models.CharField(max_length=50)

    # Tenant isolation
    objects = CustomerScopedManager()
    all_objects = models.Manager()  # Unfiltered access for superusers

    class Meta:
        unique_together = ("customer", "cpt_code")

    def __str__(self):
        return f"{self.cpt_code} -> {self.cpt_group}"


class RiskBaseline(models.Model):
    """
    Historical denial rate baselines for risk scoring.
    Stores aggregated historical denial rates for each
    (customer, payer, CPT) combination.
    Updated nightly by build_risk_baselines Celery task.
    """

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="risk_baselines"
    )
    payer = models.CharField(max_length=255, db_index=True)
    cpt = models.CharField(max_length=20, db_index=True)
    denial_rate = models.FloatField(
        help_text="Historical denial rate: denied / total claims",
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )
    sample_size = models.IntegerField(
        help_text="Number of claims in baseline calculation",
        validators=[MinValueValidator(1)],
    )
    confidence_score = models.FloatField(
        help_text="Statistical confidence: min(sample_size / 100, 1.0)",
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )
    last_updated = models.DateTimeField(auto_now=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = CustomerScopedManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "upstream_risk_baseline"
        indexes = [
            models.Index(
                fields=["customer", "payer", "cpt"], name="risk_baseline_lookup_idx"
            ),
            models.Index(fields=["last_updated"], name="risk_baseline_updated_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["customer", "payer", "cpt"], name="unique_risk_baseline"
            ),
            models.CheckConstraint(
                check=models.Q(confidence_score__gte=0.0)
                & models.Q(confidence_score__lte=1.0),
                name="risk_baseline_confidence_range",
            ),
            models.CheckConstraint(
                check=models.Q(denial_rate__gte=0.0) & models.Q(denial_rate__lte=1.0),
                name="risk_baseline_denial_rate_range",
            ),
            models.CheckConstraint(
                check=models.Q(sample_size__gte=1),
                name="risk_baseline_sample_size_positive",
            ),
        ]

    def __str__(self):
        return (
            f"{self.customer.name} - {self.payer} - {self.cpt}: {self.denial_rate:.1%}"
        )


class AutomationRule(models.Model):
    """
    Pre-approved workflow rules for autonomous execution.
    Defines trigger conditions and actions for automated workflows.
    """

    RULE_TYPE_CHOICES = [
        ("reauth", "Reauthorization Request"),
        ("appeal", "Appeal Generation"),
        ("high_risk_hold", "High Risk Hold"),
    ]

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="automation_rules"
    )
    rule_type = models.CharField(max_length=20, choices=RULE_TYPE_CHOICES)
    trigger_conditions = models.JSONField(
        help_text="Conditions that trigger this rule (payer, cpt_code, etc.)"
    )
    actions = models.JSONField(
        help_text="Actions to execute when triggered (action_type, etc.)"
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_executed = models.DateTimeField(null=True, blank=True)

    objects = CustomerScopedManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "upstream_automation_rule"
        indexes = [
            models.Index(
                fields=["customer", "rule_type", "is_active"],
                name="automation_rule_lookup_idx",
            ),
            models.Index(
                fields=["is_active", "rule_type"], name="automation_rule_active_idx"
            ),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(rule_type__in=["reauth", "appeal", "high_risk_hold"]),
                name="automation_rule_type_valid",
            ),
        ]

    def __str__(self):
        return f"{self.customer.name} - {self.get_rule_type_display()}"


class ExecutionLog(models.Model):
    """
    Audit trail for all autonomous action executions.
    HIPAA-compliant logging of automated workflows.
    """

    RESULT_CHOICES = [
        ("SUCCESS", "Success"),
        ("FAILED", "Failed"),
        ("ESCALATED", "Escalated to Alert"),
    ]

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="execution_logs"
    )
    rule = models.ForeignKey(
        AutomationRule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="executions",
        help_text="Rule that triggered this execution (nullable for ad-hoc actions)",
    )
    trigger_event = models.JSONField(
        help_text="Event data that triggered the action: {type, claim_id, ...}"
    )
    action_taken = models.CharField(
        max_length=50,
        help_text="Action executed: submit_reauth, generate_appeal, etc.",
    )
    result = models.CharField(
        max_length=20, choices=RESULT_CHOICES, default="SUCCESS", db_index=True
    )
    details = models.JSONField(
        help_text="Execution details: outcomes, error messages, response data"
    )
    execution_time_ms = models.IntegerField(
        help_text="Execution duration in milliseconds",
        validators=[MinValueValidator(0)],
    )
    executed_at = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = CustomerScopedManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "upstream_execution_log"
        ordering = ["-executed_at"]
        indexes = [
            models.Index(
                fields=["customer", "-executed_at"], name="execution_log_customer_idx"
            ),
            models.Index(fields=["rule", "result"], name="execution_log_rule_idx"),
        ]

    def __str__(self):
        return f"{self.customer.name} - {self.action_taken} - {self.result}"


class Authorization(models.Model):
    """
    Multi-vertical authorization tracking with expiration monitoring.

    Supports all four verticals:
    - ABA: Applied Behavior Analysis therapy authorizations
    - PT: Physical Therapy (including Dialysis MA variance)
    - OT: Occupational Therapy
    - IMAGING: Diagnostic Imaging (RBM requirements)
    - HOME_HEALTH: Home Health (PDGM validation)
    - DIALYSIS: Dialysis Services

    Uses specialty_metadata JSON field for vertical-specific requirements.
    """

    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("EXPIRING_SOON", "Expiring Soon"),
        ("EXPIRED", "Expired"),
        ("RENEWED", "Renewed"),
    ]

    SERVICE_TYPE_CHOICES = [
        ("ABA", "ABA Therapy"),
        ("PT", "Physical Therapy"),
        ("OT", "Occupational Therapy"),
        ("IMAGING", "Diagnostic Imaging"),
        ("HOME_HEALTH", "Home Health"),
        ("DIALYSIS", "Dialysis Services"),
    ]

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="authorizations"
    )
    auth_number = models.CharField(
        max_length=100, unique=True, help_text="Unique authorization number from payer"
    )
    patient_identifier = models.CharField(
        max_length=255, help_text="Patient ID (should be encrypted in production)"
    )
    payer = models.CharField(max_length=255, db_index=True)
    service_type = models.CharField(
        max_length=50,
        choices=SERVICE_TYPE_CHOICES,
        db_index=True,
        help_text="Service vertical (ABA, PT, OT, IMAGING, HOME_HEALTH, DIALYSIS)",
    )
    specialty_metadata = models.JSONField(
        default=dict,
        help_text=(
            "Vertical-specific fields. "
            "ABA: {'bcba_required': true, 'credential_expiration': '2025-06-30'}. "
            "Imaging: {'rbm_provider': 'eviCore', 'pa_required': true}. "
            "Home Health: {'f2f_completed': true, 'oasis_date': '2025-01-15'}. "
            "Dialysis: {'ma_plan_type': 'Advantage', 'esrd_pps_bundle': 'CA2F'}"
        ),
    )
    cpt_codes = models.JSONField(
        help_text="List of authorized CPT codes: ['97151', '97153']"
    )
    auth_start_date = models.DateField()
    auth_expiration_date = models.DateField(db_index=True)
    units_authorized = models.IntegerField(validators=[MinValueValidator(1)])
    units_used = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="ACTIVE", db_index=True
    )
    reauth_lead_time_days = models.IntegerField(
        default=21,
        validators=[MinValueValidator(1)],
        help_text="Days before expiration to trigger reauth (default 21)",
    )
    auto_reauth_enabled = models.BooleanField(
        default=False, help_text="Enable autonomous reauthorization submission"
    )
    last_alert_sent = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CustomerScopedManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "upstream_authorization"
        indexes = [
            models.Index(
                fields=["customer", "status", "auth_expiration_date"],
                name="authorization_expiring_idx",
            ),
            models.Index(
                fields=["customer", "payer", "status"], name="authorization_payer_idx"
            ),
            models.Index(
                fields=["customer", "service_type", "status"],
                name="authorization_service_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(units_used__lte=models.F("units_authorized")),
                name="authorization_units_valid",
            ),
        ]

    def __str__(self):
        return f"{self.customer.name} - {self.auth_number} - {self.status}"


# Import models from submodules to ensure Django migrations detect them
# HIGH-4: Replace wildcard imports with explicit imports
from upstream.core.models import (  # noqa: F401, E402
    BaseModel,
    SystemConfiguration,
    DomainAuditEvent,
    ProductConfig,
)
from upstream.core.validation_models import (  # noqa: F401, E402
    ValidationRule,
    ValidationResult,
    DataQualityMetric,
    ClaimValidationHistory,
    DataAnomalyDetection,
)
from upstream.alerts.models import (  # noqa: F401, E402
    AlertRule,
    NotificationChannel,
    AlertEvent,
    Alert,
    OperatorJudgment,
)
from upstream.integrations.models import (  # noqa: F401, E402
    IntegrationProvider,
    IntegrationConnection,
    IntegrationLog,
    WebhookEndpoint,
    WebhookDelivery,
)
from upstream.reporting.models import (  # noqa: F401, E402
    ReportTemplate,
    ScheduledReport,
    ReportArtifact,
)
from upstream.products.denialscope.models import (  # noqa: F401, E402
    DenialAggregate,
    DenialSignal,
)
from upstream.products.delayguard.models import (  # noqa: F401, E402
    PaymentDelayAggregate,
    PaymentDelaySignal,
    PaymentDelayClaimSet,
    PaymentDelayEvidenceArtifact,
)
from upstream.products.dialysis.models import (  # noqa: F401, E402
    DialysisMABaseline,
)
from upstream.models_agents import (  # noqa: F401, E402
    AgentRun,
    Finding,
    CodeQualityMetric,
    DatabaseQueryAnalysis,
    TestCoverageReport,
    MigrationAnalysis,
)
