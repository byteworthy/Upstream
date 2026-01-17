"""
Ingestion models for Payrixa.

Provides durable storage for all ingestion attempts and internal events.
"""

from django.db import models
from django.contrib.auth.models import User
from payrixa.core.models import BaseModel


class IngestionRecord(BaseModel):
    """
    Durable record of all data ingestion attempts.
    
    Supports multiple ingestion modes: batch upload, webhook, streaming.
    """
    
    SOURCE_TYPES = [
        ('batch_upload', 'Batch Upload'),
        ('webhook', 'Webhook'),
        ('api', 'API'),
        ('streaming', 'Streaming'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('processed', 'Processed'),
        ('failed', 'Failed'),
    ]
    
    customer = models.ForeignKey('payrixa.Customer', on_delete=models.CASCADE, related_name='ingestion_records')
    source_type = models.CharField(max_length=50, choices=SOURCE_TYPES)
    idempotency_key = models.CharField(max_length=255, blank=True, null=True, db_index=True, 
                                       help_text='Unique key to prevent duplicate processing')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    payload_metadata = models.JSONField(default=dict, help_text='Metadata about the ingested payload')
    record_count = models.IntegerField(null=True, blank=True, help_text='Number of records in payload')
    error_message = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                   related_name='ingestions_created')
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Ingestion Record'
        verbose_name_plural = 'Ingestion Records'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', 'status', '-created_at']),
            models.Index(fields=['customer', 'source_type', '-created_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['customer', 'idempotency_key'],
                condition=models.Q(idempotency_key__isnull=False),
                name='unique_customer_idempotency_key'
            )
        ]
    
    def __str__(self):
        return f"{self.source_type} ingestion for {self.customer.name} - {self.status}"


class SystemEvent(BaseModel):
    """
    Append-only event log for internal system events.
    
    Captures all significant system actions for audit and future fanout.
    """
    
    EVENT_TYPES = [
        ('ingestion_received', 'Ingestion Received'),
        ('ingestion_processed', 'Ingestion Processed'),
        ('ingestion_failed', 'Ingestion Failed'),
        ('drift_detected', 'Drift Detected'),
        ('alert_created', 'Alert Created'),
        ('export_generated', 'Export Generated'),
        ('report_generated', 'Report Generated'),
        ('webhook_sent', 'Webhook Sent'),
        ('email_sent', 'Email Sent'),
    ]
    
    customer = models.ForeignKey('payrixa.Customer', on_delete=models.CASCADE, related_name='system_events')
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES, db_index=True)
    payload = models.JSONField(default=dict, help_text='Event-specific data')
    request_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    
    # Related object pointers (optional)
    related_ingestion = models.ForeignKey(IngestionRecord, on_delete=models.SET_NULL, 
                                         null=True, blank=True, related_name='events')
    related_drift_event = models.ForeignKey('payrixa.DriftEvent', on_delete=models.SET_NULL,
                                           null=True, blank=True, related_name='system_events')
    related_alert = models.ForeignKey('payrixa.AlertEvent', on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name='system_events')
    
    class Meta:
        verbose_name = 'System Event'
        verbose_name_plural = 'System Events'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', 'event_type', '-created_at']),
            models.Index(fields=['customer', '-created_at']),
            models.Index(fields=['event_type', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.event_type} for {self.customer.name} at {self.created_at}"


class IngestionToken(BaseModel):
    """
    API tokens for webhook ingestion authentication.
    
    Each customer can have multiple tokens for different integrations.
    """
    
    customer = models.ForeignKey('payrixa.Customer', on_delete=models.CASCADE, related_name='ingestion_tokens')
    name = models.CharField(max_length=100, help_text='Friendly name for this token')
    token = models.CharField(max_length=64, unique=True, db_index=True)
    is_active = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True, help_text='Optional expiration date')
    
    class Meta:
        verbose_name = 'Ingestion Token'
        verbose_name_plural = 'Ingestion Tokens'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} for {self.customer.name}"
