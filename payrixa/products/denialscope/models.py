"""
DenialScope domain models.

Stores computed denial analytics, not raw claims.
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from payrixa.core.models import BaseModel


class DenialAggregate(BaseModel):
    """
    Daily denial aggregates by payer and reason.
    
    Stores computed facts about denials, not raw claim data.
    """
    
    customer = models.ForeignKey('payrixa.Customer', on_delete=models.CASCADE, 
                                related_name='denial_aggregates')
    payer = models.CharField(max_length=255, db_index=True)
    denial_reason = models.CharField(max_length=255, blank=True, null=True, 
                                    help_text='Denial reason code or generic "DENIED"')
    cpt_code = models.CharField(max_length=50, blank=True, null=True,
                               help_text='Optional CPT code filter')
    
    # Date aggregation
    aggregate_date = models.DateField(db_index=True, help_text='Day of aggregation')
    
    # Denial metrics
    denied_count = models.IntegerField(default=0)
    denied_dollars = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                        help_text='Sum of allowed_amount for denials')
    
    # Total metrics for rate calculation
    total_submitted_count = models.IntegerField(default=0, 
                                               help_text='Total claims submitted to this payer on this day')
    total_submitted_dollars = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Computed rates
    denial_rate = models.FloatField(default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    
    class Meta:
        verbose_name = 'Denial Aggregate'
        verbose_name_plural = 'Denial Aggregates'
        ordering = ['-aggregate_date', '-denied_count']
        indexes = [
            models.Index(fields=['customer', 'aggregate_date']),
            models.Index(fields=['customer', 'payer', 'aggregate_date']),
            models.Index(fields=['customer', 'payer', 'denial_reason', 'aggregate_date']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['customer', 'payer', 'denial_reason', 'cpt_code', 'aggregate_date'],
                name='unique_denial_aggregate'
            )
        ]
    
    def __str__(self):
        reason_str = self.denial_reason or 'All'
        return f"{self.customer.name} - {self.payer} - {reason_str} - {self.aggregate_date}"


class DenialSignal(BaseModel):
    """
    Detected denial signals and anomalies.
    
    Represents meaningful events like spikes, new denial reasons, etc.
    """
    
    SIGNAL_TYPES = [
        ('new_denial_reason', 'New Denial Reason'),
        ('denial_rate_spike', 'Denial Rate Spike'),
        ('denial_volume_spike', 'Denial Volume Spike'),
        ('denial_dollars_spike', 'Denial Dollars Spike'),
    ]
    
    SEVERITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    customer = models.ForeignKey('payrixa.Customer', on_delete=models.CASCADE,
                                related_name='denial_signals')
    signal_type = models.CharField(max_length=50, choices=SIGNAL_TYPES, db_index=True)
    
    # Signal context
    payer = models.CharField(max_length=255, db_index=True)
    denial_reason = models.CharField(max_length=255, blank=True, null=True)
    
    # Time window
    window_start_date = models.DateField()
    window_end_date = models.DateField()
    
    # Signal metadata
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS, default='medium', db_index=True)
    confidence = models.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
                                  help_text='Confidence score 0-1')
    
    # Human-readable summary
    summary_text = models.TextField(help_text='Human-readable signal summary')
    
    # Signal details (flexible payload)
    details = models.JSONField(default=dict, help_text='Signal-specific metrics and context')
    
    # Related aggregates (optional references)
    related_aggregates = models.ManyToManyField(DenialAggregate, blank=True,
                                               related_name='signals')
    
    class Meta:
        verbose_name = 'Denial Signal'
        verbose_name_plural = 'Denial Signals'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', '-created_at']),
            models.Index(fields=['customer', 'signal_type', '-created_at']),
            models.Index(fields=['customer', 'severity', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.customer.name} - {self.signal_type} - {self.payer} - {self.severity}"
