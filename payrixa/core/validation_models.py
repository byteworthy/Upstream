"""
Comprehensive data validation and quality tracking models.

These models enable deep visibility into data quality, validation rules,
and quality trends over time.
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from payrixa.core.models import BaseModel
from payrixa.core.tenant import CustomerScopedManager


class ValidationRule(BaseModel):
    """
    Configurable validation rules for data quality checks.

    Enables customers to define their own validation logic
    and quality thresholds.
    """

    RULE_TYPES = [
        ('required_field', 'Required Field'),
        ('format_check', 'Format Check'),
        ('range_check', 'Range Check'),
        ('date_logic', 'Date Logic'),
        ('phi_detection', 'PHI Detection'),
        ('reference_check', 'Reference Data Check'),
        ('business_rule', 'Business Rule'),
    ]

    SEVERITY_LEVELS = [
        ('error', 'Error - Reject Row'),
        ('warning', 'Warning - Accept with Flag'),
        ('info', 'Info - Log Only'),
    ]

    customer = models.ForeignKey('payrixa.Customer', on_delete=models.CASCADE,
                                related_name='validation_rules')

    # Rule identification
    name = models.CharField(max_length=200, help_text='Human-readable rule name')
    code = models.CharField(max_length=50, help_text='Unique code for this rule (e.g., "REQ_001")')
    rule_type = models.CharField(max_length=30, choices=RULE_TYPES, db_index=True)

    # Rule configuration
    field_name = models.CharField(max_length=100, blank=True,
                                 help_text='Field this rule applies to (if field-specific)')
    validation_logic = models.JSONField(
        default=dict,
        help_text='Rule-specific validation configuration (regex, min/max, etc.)'
    )

    # Rule behavior
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS, default='error')
    enabled = models.BooleanField(default=True, db_index=True)

    # Error messaging
    error_message_template = models.TextField(
        help_text='Error message template with {field} placeholders'
    )
    remediation_guidance = models.TextField(
        blank=True,
        help_text='How to fix violations of this rule'
    )

    # Metadata
    applies_to_entity = models.CharField(
        max_length=50,
        default='claim_record',
        help_text='Entity type this rule applies to (claim_record, upload, etc.)'
    )
    execution_order = models.IntegerField(
        default=100,
        help_text='Order in which rules are executed (lower = earlier)'
    )

    # Tenant isolation
    objects = CustomerScopedManager()
    all_objects = models.Manager()

    class Meta:
        verbose_name = 'Validation Rule'
        verbose_name_plural = 'Validation Rules'
        ordering = ['execution_order', 'name']
        unique_together = ('customer', 'code')
        indexes = [
            models.Index(fields=['customer', 'enabled', 'execution_order']),
            models.Index(fields=['customer', 'rule_type']),
        ]

    def __str__(self):
        return f"{self.code}: {self.name} ({self.severity})"


class ValidationResult(BaseModel):
    """
    Individual validation failures for detailed tracking.

    Links validation failures to specific rows/records for
    granular quality analysis.
    """

    customer = models.ForeignKey('payrixa.Customer', on_delete=models.CASCADE,
                                related_name='validation_results')

    # Linkage to source data
    upload = models.ForeignKey('payrixa.Upload', on_delete=models.CASCADE,
                              related_name='validation_results', null=True, blank=True)
    claim_record = models.ForeignKey('payrixa.ClaimRecord', on_delete=models.CASCADE,
                                    related_name='validation_results', null=True, blank=True)

    # Validation details
    validation_rule = models.ForeignKey(ValidationRule, on_delete=models.CASCADE,
                                       related_name='validation_results')
    row_number = models.IntegerField(null=True, blank=True,
                                    help_text='Row number in CSV (if applicable)')
    field_name = models.CharField(max_length=100, blank=True)
    field_value = models.TextField(blank=True, help_text='The value that failed validation')

    # Result details
    passed = models.BooleanField(default=False, db_index=True)
    error_message = models.TextField()
    severity = models.CharField(max_length=20,
                               choices=ValidationRule.SEVERITY_LEVELS,
                               default='error', db_index=True)

    # Metadata
    context_data = models.JSONField(
        default=dict,
        blank=True,
        help_text='Additional context about the validation (full row data, etc.)'
    )

    # Tenant isolation
    objects = CustomerScopedManager()
    all_objects = models.Manager()

    class Meta:
        verbose_name = 'Validation Result'
        verbose_name_plural = 'Validation Results'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', 'upload', 'severity']),
            models.Index(fields=['customer', 'validation_rule', '-created_at']),
            models.Index(fields=['customer', 'passed', '-created_at']),
        ]

    def __str__(self):
        status = "✓ Pass" if self.passed else "✗ Fail"
        return f"{status} - {self.validation_rule.code} - Row {self.row_number or 'N/A'}"


class DataQualityMetric(BaseModel):
    """
    Time-series tracking of data quality metrics.

    Enables trending and monitoring of data quality over time
    to identify degradation or improvement.
    """

    METRIC_TYPES = [
        ('completeness', 'Completeness'),
        ('accuracy', 'Accuracy'),
        ('consistency', 'Consistency'),
        ('timeliness', 'Timeliness'),
        ('validity', 'Validity'),
        ('uniqueness', 'Uniqueness'),
    ]

    customer = models.ForeignKey('payrixa.Customer', on_delete=models.CASCADE,
                                related_name='quality_metrics')

    # Metric identification
    metric_type = models.CharField(max_length=30, choices=METRIC_TYPES, db_index=True)
    metric_name = models.CharField(max_length=100, help_text='Specific metric name')

    # Time window
    measurement_date = models.DateField(db_index=True)
    measurement_timestamp = models.DateTimeField(default=timezone.now)

    # Metric value (0.0 to 1.0 score, where 1.0 = perfect quality)
    score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text='Quality score from 0.0 (worst) to 1.0 (perfect)'
    )

    # Supporting data
    sample_size = models.IntegerField(help_text='Number of records measured')
    passed_count = models.IntegerField(help_text='Number of records passing quality check')
    failed_count = models.IntegerField(help_text='Number of records failing quality check')

    # Context
    entity_type = models.CharField(
        max_length=50,
        default='claim_record',
        help_text='Type of entity measured (claim_record, upload, etc.)'
    )
    dimension = models.CharField(
        max_length=100,
        blank=True,
        help_text='Optional dimension (payer, cpt_group, etc.)'
    )
    dimension_value = models.CharField(
        max_length=255,
        blank=True,
        help_text='Value of the dimension (if applicable)'
    )

    # Metadata
    details = models.JSONField(
        default=dict,
        blank=True,
        help_text='Detailed breakdown and supporting metrics'
    )

    # Tenant isolation
    objects = CustomerScopedManager()
    all_objects = models.Manager()

    class Meta:
        verbose_name = 'Data Quality Metric'
        verbose_name_plural = 'Data Quality Metrics'
        ordering = ['-measurement_date', '-measurement_timestamp']
        indexes = [
            models.Index(fields=['customer', 'metric_type', '-measurement_date']),
            models.Index(fields=['customer', 'measurement_date']),
            models.Index(fields=['customer', 'entity_type', 'metric_type', '-measurement_date']),
        ]

    def __str__(self):
        return f"{self.metric_name} - {self.measurement_date} - Score: {self.score:.2f}"

    @property
    def quality_grade(self):
        """Return letter grade for quality score."""
        if self.score >= 0.95:
            return 'A+'
        elif self.score >= 0.90:
            return 'A'
        elif self.score >= 0.85:
            return 'B+'
        elif self.score >= 0.80:
            return 'B'
        elif self.score >= 0.75:
            return 'C+'
        elif self.score >= 0.70:
            return 'C'
        elif self.score >= 0.60:
            return 'D'
        else:
            return 'F'


class ClaimValidationHistory(BaseModel):
    """
    Track validation history at the claim level.

    Enables understanding of which claims have quality issues
    and tracking quality improvements over time.
    """

    customer = models.ForeignKey('payrixa.Customer', on_delete=models.CASCADE,
                                related_name='claim_validations')
    claim_record = models.ForeignKey('payrixa.ClaimRecord', on_delete=models.CASCADE,
                                    related_name='validations')
    upload = models.ForeignKey('payrixa.Upload', on_delete=models.CASCADE,
                              related_name='claim_validations')

    # Validation summary
    validation_passed = models.BooleanField(default=True, db_index=True)
    error_count = models.IntegerField(default=0)
    warning_count = models.IntegerField(default=0)

    # Quality score for this specific claim
    quality_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        null=True,
        blank=True,
        help_text='Overall quality score for this claim'
    )

    # Validation details
    validation_errors = models.JSONField(
        default=list,
        help_text='List of validation errors: [{rule_code, message, field}]'
    )
    validation_warnings = models.JSONField(
        default=list,
        help_text='List of validation warnings'
    )

    # Metadata
    validated_at = models.DateTimeField(default=timezone.now)

    # Tenant isolation
    objects = CustomerScopedManager()
    all_objects = models.Manager()

    class Meta:
        verbose_name = 'Claim Validation History'
        verbose_name_plural = 'Claim Validation Histories'
        ordering = ['-validated_at']
        indexes = [
            models.Index(fields=['customer', 'upload', 'validation_passed']),
            models.Index(fields=['customer', 'claim_record', '-validated_at']),
            models.Index(fields=['customer', 'validation_passed', '-validated_at']),
        ]

    def __str__(self):
        status = "✓ Valid" if self.validation_passed else "✗ Invalid"
        return f"{status} - Claim {self.claim_record.id} - {self.error_count} errors"


class DataAnomalyDetection(BaseModel):
    """
    Track detected data anomalies and outliers.

    Uses statistical methods to identify unusual patterns
    in uploaded data that may indicate quality issues.
    """

    ANOMALY_TYPES = [
        ('statistical_outlier', 'Statistical Outlier'),
        ('pattern_break', 'Pattern Break'),
        ('volume_anomaly', 'Volume Anomaly'),
        ('distribution_shift', 'Distribution Shift'),
        ('missing_data_spike', 'Missing Data Spike'),
        ('duplicate_spike', 'Duplicate Spike'),
    ]

    customer = models.ForeignKey('payrixa.Customer', on_delete=models.CASCADE,
                                related_name='data_anomalies')
    upload = models.ForeignKey('payrixa.Upload', on_delete=models.CASCADE,
                              related_name='anomalies', null=True, blank=True)

    # Anomaly details
    anomaly_type = models.CharField(max_length=50, choices=ANOMALY_TYPES, db_index=True)
    field_name = models.CharField(max_length=100, blank=True)

    # Detection metadata
    detected_at = models.DateTimeField(default=timezone.now, db_index=True)
    severity = models.CharField(
        max_length=20,
        choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical')],
        default='medium',
        db_index=True
    )

    # Anomaly metrics
    anomaly_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text='Anomaly score (higher = more anomalous)'
    )
    confidence = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text='Confidence in anomaly detection'
    )

    # Details
    description = models.TextField(help_text='Human-readable anomaly description')
    statistical_details = models.JSONField(
        default=dict,
        help_text='Statistical details: mean, std, z-score, etc.'
    )

    # Impact assessment
    affected_row_count = models.IntegerField(default=0)
    recommended_action = models.TextField(
        blank=True,
        help_text='Recommended remediation action'
    )

    # Resolution tracking
    acknowledged = models.BooleanField(default=False, db_index=True)
    acknowledged_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='acknowledged_anomalies'
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)

    # Tenant isolation
    objects = CustomerScopedManager()
    all_objects = models.Manager()

    class Meta:
        verbose_name = 'Data Anomaly Detection'
        verbose_name_plural = 'Data Anomaly Detections'
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['customer', 'severity', '-detected_at']),
            models.Index(fields=['customer', 'anomaly_type', '-detected_at']),
            models.Index(fields=['customer', 'acknowledged', '-detected_at']),
        ]

    def __str__(self):
        return f"{self.anomaly_type} - {self.severity} - Score: {self.anomaly_score:.2f}"
