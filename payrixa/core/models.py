from django.db import models

class BaseModel(models.Model):
    """Abstract base model with common fields for all Payrixa models."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_created')
    updated_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_updated')
    class Meta:
        abstract = True

class SystemConfiguration(models.Model):
    """Global system configuration settings."""
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.TextField(blank=True, null=True)
    class Meta:
        verbose_name = 'System Configuration'
        verbose_name_plural = 'System Configurations'
    def __str__(self):
        return f"{self.key}: {self.value}"

class DomainAuditEvent(models.Model):
    """Domain-specific audit events for tracking key business actions."""
    ACTION_CHOICES = [
        ('upload_created', 'Upload Created'), ('report_exported', 'Report Exported'),
        ('alert_rule_created', 'Alert Rule Created'), ('alert_rule_updated', 'Alert Rule Updated'),
        ('alert_rule_deleted', 'Alert Rule Deleted'), 
        ('alert_event_created', 'Alert Event Created'),
        ('alert_event_sent', 'Alert Event Sent'),
        ('alert_event_failed', 'Alert Event Failed'),
        ('webhook_delivery_attempted', 'Webhook Delivery Attempted'),
        ('webhook_delivery_sent', 'Webhook Delivery Sent'),
        ('webhook_delivery_failed', 'Webhook Delivery Failed'),
        ('webhook_endpoint_created', 'Webhook Endpoint Created'), ('webhook_endpoint_updated', 'Webhook Endpoint Updated'),
        ('webhook_endpoint_deleted', 'Webhook Endpoint Deleted'), ('drift_event_created', 'Drift Event Created'),
        ('report_run_started', 'Report Run Started'), ('report_run_completed', 'Report Run Completed'),
        ('member_added', 'Member Added'), ('member_removed', 'Member Removed'),
        ('role_changed', 'Role Changed'),
        ('alert_routing_updated', 'Alert Routing Updated'),
        ('slack_webhook_updated', 'Slack Webhook Updated'),
    ]
    customer = models.ForeignKey('payrixa.Customer', on_delete=models.CASCADE, related_name='domain_audit_events', null=True, blank=True)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    entity_type = models.CharField(max_length=100)
    entity_id = models.CharField(max_length=100, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    request_id = models.CharField(max_length=64, blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)
    user = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='domain_audit_events')
    class Meta:
        verbose_name = 'Domain Audit Event'
        verbose_name_plural = 'Domain Audit Events'
        ordering = ['-timestamp']
    def __str__(self):
        return f"{self.action} - {self.entity_type}:{self.entity_id} at {self.timestamp}"
