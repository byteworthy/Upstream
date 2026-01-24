"""
Advanced DenialScope Models for ML-powered features.

Implements:
- Denial clustering and pattern recognition
- Cascade detection (related denials)
- Pre-denial warnings (predictive alerts)
- Appeal auto-generation
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from payrixa.core.models import BaseModel
from payrixa.core.tenant import CustomerScopedManager


class DenialCluster(BaseModel):
    """
    Detected clusters of related denials.

    Uses ML clustering to group denials with similar characteristics
    for pattern recognition and bulk resolution.
    """

    customer = models.ForeignKey('payrixa.Customer', on_delete=models.CASCADE,
                                related_name='denial_clusters')

    # Cluster identification
    cluster_id = models.CharField(max_length=50, db_index=True,
                                  help_text='Unique cluster identifier (e.g., CLU-2024-001)')
    cluster_name = models.CharField(max_length=200,
                                   help_text='Human-readable cluster name')

    # Cluster characteristics
    primary_denial_reason = models.CharField(max_length=255)
    secondary_denial_reasons = models.JSONField(
        default=list,
        help_text='Other denial reasons in this cluster'
    )

    # Payer/CPT patterns
    payers = models.JSONField(
        default=list,
        help_text='List of payers in this cluster'
    )
    cpt_codes = models.JSONField(
        default=list,
        help_text='List of CPT codes in this cluster'
    )

    # Cluster metrics
    claim_count = models.IntegerField(default=0)
    total_denied_dollars = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # ML metadata
    cluster_confidence = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text='Confidence score for cluster cohesion (0-1)'
    )
    silhouette_score = models.FloatField(
        blank=True,
        null=True,
        help_text='ML silhouette score for cluster quality'
    )

    # Pattern summary
    pattern_description = models.TextField(
        help_text='AI-generated description of the denial pattern'
    )
    root_cause_hypothesis = models.TextField(
        help_text='AI-generated hypothesis about root cause'
    )

    # Resolution tracking
    resolution_strategy = models.TextField(
        blank=True,
        help_text='Recommended resolution strategy for this cluster'
    )
    resolved = models.BooleanField(default=False, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_denial_clusters'
    )

    # Date range
    first_denial_date = models.DateField()
    last_denial_date = models.DateField()

    # Tenant isolation
    objects = CustomerScopedManager()
    all_objects = models.Manager()

    class Meta:
        verbose_name = 'Denial Cluster'
        verbose_name_plural = 'Denial Clusters'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', 'resolved', '-created_at']),
            models.Index(fields=['customer', 'cluster_id']),
        ]
        unique_together = ('customer', 'cluster_id')

    def __str__(self):
        return f"{self.cluster_id}: {self.cluster_name} ({self.claim_count} claims)"


class DenialCascade(BaseModel):
    """
    Detected denial cascades - related denials across claims.

    Identifies patterns where one denial triggers or is related to others
    (e.g., same patient, related procedures, timing patterns).
    """

    customer = models.ForeignKey('payrixa.Customer', on_delete=models.CASCADE,
                                related_name='denial_cascades')

    # Cascade identification
    cascade_id = models.CharField(max_length=50, db_index=True)
    cascade_type = models.CharField(
        max_length=50,
        choices=[
            ('temporal', 'Temporal - Same timeframe'),
            ('procedural', 'Procedural - Related procedures'),
            ('payer_systemic', 'Payer Systemic - Payer-wide issue'),
            ('documentation', 'Documentation - Same doc issue'),
        ],
        default='temporal'
    )

    # Related claims
    claim_ids = models.JSONField(
        default=list,
        help_text='List of ClaimRecord IDs in this cascade'
    )
    claim_count = models.IntegerField(default=0)

    # Cascade characteristics
    payer = models.CharField(max_length=255)
    denial_reasons = models.JSONField(default=list)

    # Impact
    total_denied_dollars = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Detection metadata
    confidence_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )

    # Pattern analysis
    pattern_summary = models.TextField(
        help_text='Description of the cascade pattern'
    )
    root_cause = models.TextField(
        blank=True,
        help_text='Identified or suspected root cause'
    )

    # Resolution
    resolution_recommended = models.TextField(
        blank=True,
        help_text='Recommended resolution strategy'
    )
    resolved = models.BooleanField(default=False, db_index=True)

    # Date range
    cascade_start_date = models.DateField()
    cascade_end_date = models.DateField()

    # Tenant isolation
    objects = CustomerScopedManager()
    all_objects = models.Manager()

    class Meta:
        verbose_name = 'Denial Cascade'
        verbose_name_plural = 'Denial Cascades'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', 'resolved', '-created_at']),
            models.Index(fields=['customer', 'payer', 'cascade_type']),
        ]

    def __str__(self):
        return f"{self.cascade_id}: {self.cascade_type} - {self.claim_count} claims"


class PreDenialWarning(BaseModel):
    """
    Predictive pre-denial warnings.

    ML-powered predictions of likely denials before they occur,
    enabling proactive intervention.
    """

    customer = models.ForeignKey('payrixa.Customer', on_delete=models.CASCADE,
                                related_name='pre_denial_warnings')

    # Warning identification
    warning_id = models.CharField(max_length=50, db_index=True)

    # Prediction target
    claim_record = models.ForeignKey(
        'payrixa.ClaimRecord',
        on_delete=models.CASCADE,
        related_name='pre_denial_warnings',
        null=True,
        blank=True,
        help_text='Specific claim at risk (if available)'
    )

    # Warning type
    warning_type = models.CharField(
        max_length=50,
        choices=[
            ('auth_missing', 'Authorization Missing'),
            ('doc_incomplete', 'Documentation Incomplete'),
            ('coding_error', 'Coding Error Likely'),
            ('policy_violation', 'Policy Violation Risk'),
            ('payer_pattern', 'Payer Pattern Match'),
        ]
    )

    # Prediction details
    predicted_denial_reason = models.CharField(max_length=255)
    denial_probability = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text='Predicted probability of denial (0-1)'
    )
    confidence_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text='Model confidence in prediction'
    )

    # Risk factors
    risk_factors = models.JSONField(
        default=list,
        help_text='List of identified risk factors: [{factor, weight}]'
    )

    # Contextual data
    payer = models.CharField(max_length=255)
    cpt_code = models.CharField(max_length=50, blank=True)
    estimated_claim_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )

    # Recommendations
    recommended_actions = models.JSONField(
        default=list,
        help_text='Recommended actions to prevent denial: [{action, priority}]'
    )
    intervention_deadline = models.DateField(
        null=True,
        blank=True,
        help_text='Deadline for intervention'
    )

    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('intervened', 'Intervention Taken'),
            ('expired', 'Expired'),
            ('confirmed', 'Denial Confirmed'),
            ('avoided', 'Denial Avoided'),
        ],
        default='active',
        db_index=True
    )

    # Outcome tracking
    actual_outcome = models.CharField(
        max_length=20,
        blank=True,
        choices=[
            ('paid', 'Paid'),
            ('denied', 'Denied'),
            ('pending', 'Pending'),
        ],
        help_text='Actual claim outcome (for model feedback)'
    )
    intervention_taken = models.TextField(
        blank=True,
        help_text='Description of intervention taken'
    )

    # Model metadata
    model_version = models.CharField(
        max_length=50,
        default='v1.0',
        help_text='ML model version used for prediction'
    )
    prediction_features = models.JSONField(
        default=dict,
        help_text='Features used in prediction (for explainability)'
    )

    # Tenant isolation
    objects = CustomerScopedManager()
    all_objects = models.Manager()

    class Meta:
        verbose_name = 'Pre-Denial Warning'
        verbose_name_plural = 'Pre-Denial Warnings'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', 'status', '-created_at']),
            models.Index(fields=['customer', 'payer', 'status']),
            models.Index(fields=['customer', 'denial_probability']),
        ]

    def __str__(self):
        return f"{self.warning_id}: {self.warning_type} - {self.denial_probability:.0%} probability"


class AppealTemplate(BaseModel):
    """
    Auto-generated appeal templates for denied claims.

    Uses AI to generate customized appeal letters based on
    denial reason, payer policies, and historical success patterns.
    """

    customer = models.ForeignKey('payrixa.Customer', on_delete=models.CASCADE,
                                related_name='appeal_templates')

    # Template identification
    template_id = models.CharField(max_length=50, db_index=True)
    template_name = models.CharField(max_length=200)

    # Applicability
    denial_reason_code = models.CharField(max_length=50, blank=True)
    denial_reason_pattern = models.CharField(
        max_length=255,
        blank=True,
        help_text='Regex pattern for denial reason text matching'
    )
    payer = models.CharField(
        max_length=255,
        blank=True,
        help_text='Specific payer (if template is payer-specific)'
    )
    cpt_codes = models.JSONField(
        default=list,
        blank=True,
        help_text='CPT codes this template applies to'
    )

    # Template content
    appeal_letter_template = models.TextField(
        help_text='Appeal letter template with {variable} placeholders'
    )
    required_documentation = models.JSONField(
        default=list,
        help_text='List of required supporting documents'
    )

    # Success metrics
    times_used = models.IntegerField(default=0)
    success_count = models.IntegerField(
        default=0,
        help_text='Number of successful appeals using this template'
    )
    success_rate = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text='Success rate (0-1)'
    )

    # AI generation metadata
    generated_by_ai = models.BooleanField(default=True)
    generation_confidence = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        default=0.8
    )
    ai_model_version = models.CharField(max_length=50, default='gpt-4')

    # Template status
    active = models.BooleanField(default=True, db_index=True)
    approved_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_appeal_templates'
    )

    # Tenant isolation
    objects = CustomerScopedManager()
    all_objects = models.Manager()

    class Meta:
        verbose_name = 'Appeal Template'
        verbose_name_plural = 'Appeal Templates'
        ordering = ['-success_rate', '-times_used']
        indexes = [
            models.Index(fields=['customer', 'active', '-success_rate']),
            models.Index(fields=['customer', 'denial_reason_code']),
            models.Index(fields=['customer', 'payer']),
        ]

    def __str__(self):
        return f"{self.template_name} - {self.success_rate:.0%} success rate"


class AppealGeneration(BaseModel):
    """
    Generated appeals for specific denied claims.

    Links generated appeal content to specific denied claims.
    """

    customer = models.ForeignKey('payrixa.Customer', on_delete=models.CASCADE,
                                related_name='appeal_generations')

    # Appeal identification
    appeal_id = models.CharField(max_length=50, db_index=True)

    # Related entities
    claim_record = models.ForeignKey(
        'payrixa.ClaimRecord',
        on_delete=models.CASCADE,
        related_name='appeals'
    )
    template_used = models.ForeignKey(
        AppealTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_appeals'
    )

    # Generated content
    appeal_letter = models.TextField(
        help_text='Generated appeal letter content'
    )
    required_documentation = models.JSONField(
        default=list,
        help_text='List of required supporting documents'
    )

    # Appeal details
    denial_reason = models.CharField(max_length=255)
    appeal_reason = models.TextField(
        help_text='Reason/argument for appeal'
    )
    supporting_evidence = models.JSONField(
        default=list,
        help_text='List of supporting evidence points'
    )

    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=[
            ('draft', 'Draft'),
            ('ready', 'Ready to Submit'),
            ('submitted', 'Submitted'),
            ('under_review', 'Under Review'),
            ('approved', 'Approved'),
            ('denied', 'Denied'),
            ('abandoned', 'Abandoned'),
        ],
        default='draft',
        db_index=True
    )

    # Dates
    generated_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    # Outcome
    outcome = models.CharField(
        max_length=20,
        blank=True,
        choices=[
            ('approved', 'Appeal Approved'),
            ('partial', 'Partially Approved'),
            ('denied', 'Appeal Denied'),
        ]
    )
    recovered_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Amount recovered from successful appeal'
    )

    # AI metadata
    generation_confidence = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        default=0.8
    )
    ai_model_version = models.CharField(max_length=50, default='gpt-4')

    # User interactions
    edited_by_user = models.BooleanField(
        default=False,
        help_text='Whether user manually edited the generated appeal'
    )

    # Tenant isolation
    objects = CustomerScopedManager()
    all_objects = models.Manager()

    class Meta:
        verbose_name = 'Appeal Generation'
        verbose_name_plural = 'Appeal Generations'
        ordering = ['-generated_at']
        indexes = [
            models.Index(fields=['customer', 'status', '-generated_at']),
            models.Index(fields=['customer', 'claim_record']),
            models.Index(fields=['customer', 'outcome']),
        ]

    def __str__(self):
        return f"{self.appeal_id}: Claim {self.claim_record.id} - {self.status}"
