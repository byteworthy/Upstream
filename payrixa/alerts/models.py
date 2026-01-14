from django.db import models
from django.utils import timezone
from payrixa.core.models import BaseModel

class AlertRule(BaseModel):
    """Alert rules and conditions for drift event monitoring."""
    customer = models.ForeignKey('payrixa.Customer', on_delete=models.CASCADE, related_name='alert_rules')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    scope = models.JSONField(default=dict, blank=True, help_text='JSON scope filter (payer, cpt_group, etc.)')
    metric = models.CharField(max_length=50, choices=[
        ('severity', 'Drift Severity'),
        ('denial_rate_delta', 'Denial Rate Delta'),
        ('decision_time_delta', 'Decision Time Delta'),
    ], default='severity')
    threshold_type = models.CharField(max_length=20, choices=[
        ('gt', 'Greater Than'),
        ('gte', 'Greater Than or Equal'),
        ('lt', 'Less Than'),
        ('lte', 'Less Than or Equal'),
        ('eq', 'Equal'),
    ], default='gte')
    threshold_value = models.FloatField(default=0.7, help_text='Threshold value for triggering alert')
    enabled = models.BooleanField(default=True)
    severity = models.CharField(max_length=20, choices=[
        ('info', 'Informational'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
        ('emergency', 'Emergency'),
    ], default='warning')

    class Meta:
        verbose_name = 'Alert Rule'
        verbose_name_plural = 'Alert Rules'
        unique_together = ('customer', 'name')

    def __str__(self):
        return f"{self.name} ({self.severity})"

    def evaluate(self, drift_event):
        """Evaluate if this rule triggers for a given drift event."""
        if not self.enabled:
            return False
        scope = self.scope or {}
        if scope.get('payer') and drift_event.payer != scope['payer']:
            return False
        if scope.get('cpt_group') and drift_event.cpt_group != scope['cpt_group']:
            return False
        if self.metric == 'severity':
            value = drift_event.severity
        elif self.metric == 'denial_rate_delta' and drift_event.drift_type == 'DENIAL_RATE':
            value = drift_event.delta_value
        elif self.metric == 'decision_time_delta' and drift_event.drift_type == 'DECISION_TIME':
            value = drift_event.delta_value
        else:
            value = drift_event.severity
        if self.threshold_type == 'gt':
            return value > self.threshold_value
        elif self.threshold_type == 'gte':
            return value >= self.threshold_value
        elif self.threshold_type == 'lt':
            return value < self.threshold_value
        elif self.threshold_type == 'lte':
            return value <= self.threshold_value
        elif self.threshold_type == 'eq':
            return value == self.threshold_value
        return False


class NotificationChannel(BaseModel):
    """Notification channels for sending alerts."""
    customer = models.ForeignKey('payrixa.Customer', on_delete=models.CASCADE, related_name='notification_channels')
    name = models.CharField(max_length=100)
    channel_type = models.CharField(max_length=20, choices=[('email', 'Email'), ('webhook', 'Webhook'), ('slack', 'Slack')], default='email')
    config = models.JSONField(default=dict, help_text='Channel-specific configuration')
    enabled = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Notification Channel'
        verbose_name_plural = 'Notification Channels'
        unique_together = ('customer', 'name')


class AlertEvent(BaseModel):
    """Alert events triggered by drift events."""
    customer = models.ForeignKey('payrixa.Customer', on_delete=models.CASCADE, related_name='alert_events')
    alert_rule = models.ForeignKey(AlertRule, on_delete=models.CASCADE, related_name='events')
    drift_event = models.ForeignKey('payrixa.DriftEvent', on_delete=models.CASCADE, related_name='alert_events', null=True, blank=True)
    report_run = models.ForeignKey('payrixa.ReportRun', on_delete=models.CASCADE, related_name='alert_events', null=True, blank=True)
    triggered_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'), ('sent', 'Sent'), ('failed', 'Failed'), ('acknowledged', 'Acknowledged'), ('resolved', 'Resolved'),
    ], default='pending')
    payload = models.JSONField(default=dict, blank=True)
    notification_sent_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'Alert Event'
        verbose_name_plural = 'Alert Events'
        ordering = ['-triggered_at']


class Alert(BaseModel):
    """Generated alerts and notifications (legacy)."""
    rule = models.ForeignKey(AlertRule, on_delete=models.PROTECT, null=True, blank=True)
    title = models.CharField(max_length=200)
    message = models.TextField()
    severity = models.CharField(max_length=20, choices=[('info', 'Informational'), ('warning', 'Warning'), ('critical', 'Critical'), ('emergency', 'Emergency')])
    status = models.CharField(max_length=20, choices=[('new', 'New'), ('acknowledged', 'Acknowledged'), ('resolved', 'Resolved'), ('escalated', 'Escalated')], default='new')
    related_entity_type = models.CharField(max_length=50, blank=True, null=True)
    related_entity_id = models.CharField(max_length=100, blank=True, null=True)
    resolution_notes = models.TextField(blank=True, null=True)
    resolved_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_alerts')
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Alert'
        verbose_name_plural = 'Alerts'
        ordering = ['-created_at']
