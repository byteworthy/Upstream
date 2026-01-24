"""
DelayGuard domain models.

Stores computed payment delay analytics, not raw claims.
Payment delay drift detection based on days-to-payment metrics.
"""

from decimal import Decimal

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from payrixa.core.models import BaseModel


class PaymentDelayAggregate(BaseModel):
    """
    Daily payment delay aggregates by payer.
    
    Stores computed facts about payment timing, not raw claim data.
    Tenant-scoped: every query MUST filter by customer.
    """
    
    customer = models.ForeignKey('payrixa.Customer', on_delete=models.CASCADE, 
                                related_name='payment_delay_aggregates')
    payer = models.CharField(max_length=255, db_index=True)
    
    # Date aggregation
    aggregate_date = models.DateField(db_index=True, help_text='Day of aggregation')
    
    # Payment delay metrics
    claim_count = models.IntegerField(default=0, help_text='Total claims with valid dates')
    total_days_to_payment = models.IntegerField(default=0, help_text='Sum of days to payment')
    avg_days_to_payment = models.FloatField(default=0.0, help_text='Average days to payment')
    min_days_to_payment = models.IntegerField(null=True, blank=True, help_text='Minimum days to payment')
    max_days_to_payment = models.IntegerField(null=True, blank=True, help_text='Maximum days to payment')
    
    # Dollar metrics for cash impact estimation
    total_billed_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Sum of allowed_amount for included claims'
    )
    
    # Data quality metrics
    total_rows_evaluated = models.IntegerField(default=0, help_text='Total rows including missing dates')
    rows_with_valid_dates = models.IntegerField(default=0, help_text='Rows with both submitted and decided dates')
    date_completeness_ratio = models.FloatField(default=0.0, 
                                               validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
                                               help_text='Ratio of valid rows to total rows')
    
    class Meta:
        verbose_name = 'Payment Delay Aggregate'
        verbose_name_plural = 'Payment Delay Aggregates'
        ordering = ['-aggregate_date', '-claim_count']
        indexes = [
            models.Index(fields=['customer', 'aggregate_date']),
            models.Index(fields=['customer', 'payer', 'aggregate_date']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['customer', 'payer', 'aggregate_date'],
                name='unique_payment_delay_aggregate'
            )
        ]
    
    def __str__(self):
        return f"{self.customer.name} - {self.payer} - {self.aggregate_date} - {self.avg_days_to_payment:.1f} days"


class PaymentDelaySignal(BaseModel):
    """
    Detected payment delay signals and anomalies.
    
    Represents meaningful events like payment latency spikes vs baseline.
    Tenant-scoped: every query MUST filter by customer.
    """
    
    SIGNAL_TYPES = [
        ('payment_delay_drift', 'Payment Delay Drift'),
    ]
    
    SEVERITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    customer = models.ForeignKey('payrixa.Customer', on_delete=models.CASCADE,
                                related_name='payment_delay_signals')
    signal_type = models.CharField(max_length=50, choices=SIGNAL_TYPES, db_index=True)
    
    # Signal context
    payer = models.CharField(max_length=255, db_index=True)
    
    # Time window
    window_start_date = models.DateField()
    window_end_date = models.DateField()
    
    # Baseline comparison window
    baseline_start_date = models.DateField()
    baseline_end_date = models.DateField()
    
    # Signal metrics
    baseline_avg_days = models.FloatField(help_text='Baseline average days to payment')
    current_avg_days = models.FloatField(help_text='Current window average days to payment')
    delta_days = models.FloatField(help_text='Change in days (positive = slower)')
    delta_percent = models.FloatField(help_text='Percentage change from baseline')
    
    # Sample sizes
    baseline_claim_count = models.IntegerField(help_text='Claims in baseline window')
    current_claim_count = models.IntegerField(help_text='Claims in current window')
    
    # Cash impact estimation
    estimated_dollars_at_risk = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        help_text='Estimated cash impact from delayed payments'
    )
    
    # Signal metadata
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS, default='medium', db_index=True)
    confidence = models.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
                                  help_text='Confidence score 0-1 based on sample size and data quality')
    
    # Human-readable summary
    summary_text = models.TextField(help_text='Human-readable signal summary')
    
    # Signal details (flexible payload for evidence)
    details = models.JSONField(default=dict, help_text='Signal-specific metrics and context')
    
    # Query fingerprint for deduplication
    fingerprint = models.CharField(max_length=255, db_index=True, 
                                  help_text='Deterministic fingerprint of query criteria')
    
    # Data quality warnings
    data_quality_warnings = models.JSONField(default=list, blank=True,
                                            help_text='List of data quality issues encountered')
    
    # Related aggregates (optional references)
    related_aggregates = models.ManyToManyField(PaymentDelayAggregate, blank=True,
                                               related_name='signals')
    
    class Meta:
        verbose_name = 'Payment Delay Signal'
        verbose_name_plural = 'Payment Delay Signals'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', '-created_at']),
            models.Index(fields=['customer', 'signal_type', '-created_at']),
            models.Index(fields=['customer', 'severity', '-created_at']),
            models.Index(fields=['customer', 'payer', '-created_at']),
            models.Index(fields=['fingerprint']),
        ]
    
    def __str__(self):
        return f"{self.customer.name} - {self.payer} - {self.severity} - {self.delta_days:+.1f} days"


class PaymentDelayClaimSet(BaseModel):
    """
    Frozen claim set used for evidence generation.
    
    Immutable after creation - append-only pattern.
    Contains deterministic fingerprint of the exact claims used.
    """
    
    customer = models.ForeignKey('payrixa.Customer', on_delete=models.CASCADE,
                                related_name='payment_delay_claimsets')
    signal = models.ForeignKey(PaymentDelaySignal, on_delete=models.CASCADE,
                              related_name='claimsets')
    
    # Frozen query criteria
    payer = models.CharField(max_length=255)
    window_start_date = models.DateField()
    window_end_date = models.DateField()
    
    # Claim data (frozen)
    row_count = models.IntegerField(help_text='Number of claims in this set')
    totals_json = models.JSONField(default=dict, help_text='Aggregate totals for the claim set')
    source_refs_json = models.JSONField(default=list, blank=True, 
                                       help_text='List of claim IDs or surrogate keys')
    
    # Deterministic fingerprint
    fingerprint = models.CharField(max_length=255, db_index=True,
                                  help_text='SHA256 of sorted claim IDs')
    
    frozen_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Payment Delay Claim Set'
        verbose_name_plural = 'Payment Delay Claim Sets'
        ordering = ['-frozen_at']
        indexes = [
            models.Index(fields=['customer', '-frozen_at']),
            models.Index(fields=['fingerprint']),
        ]
    
    def __str__(self):
        return f"ClaimSet for {self.payer} ({self.row_count} claims)"


class PaymentDelayEvidenceArtifact(BaseModel):
    """
    Generated evidence artifact for a payment delay signal.
    
    Immutable after creation - append-only pattern.
    Contains structured evidence payload for deep dive and export.
    """
    
    customer = models.ForeignKey('payrixa.Customer', on_delete=models.CASCADE,
                                related_name='payment_delay_evidence')
    signal = models.ForeignKey(PaymentDelaySignal, on_delete=models.CASCADE,
                              related_name='evidence_artifacts')
    claimset = models.ForeignKey(PaymentDelayClaimSet, on_delete=models.CASCADE,
                                related_name='evidence_artifacts', null=True, blank=True)
    
    # Evidence payload (structured JSON)
    payload_json = models.JSONField(default=dict, help_text='Structured evidence payload')
    
    # Generation metadata
    generated_at = models.DateTimeField(auto_now_add=True)
    generation_duration_ms = models.IntegerField(null=True, blank=True,
                                                help_text='Time to generate in milliseconds')
    
    class Meta:
        verbose_name = 'Payment Delay Evidence Artifact'
        verbose_name_plural = 'Payment Delay Evidence Artifacts'
        ordering = ['-generated_at']
        indexes = [
            models.Index(fields=['customer', '-generated_at']),
            models.Index(fields=['signal']),
        ]
    
    def __str__(self):
        return f"Evidence for Signal {self.signal.pk}"
