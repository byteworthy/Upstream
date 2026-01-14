import secrets
from django.db import models
from django.utils import timezone
from payrixa.core.models import BaseModel

class IntegrationProvider(BaseModel):
    """Third-party integration providers."""
    name = models.CharField(max_length=100, unique=True)
    provider_type = models.CharField(max_length=50, choices=[
        ('ehr', 'Electronic Health Record'), ('practice_management', 'Practice Management'),
        ('billing', 'Billing System'), ('payer', 'Payer System'), ('analytics', 'Analytics Platform'),
        ('communication', 'Communication Platform'), ('other', 'Other'),
    ])
    description = models.TextField(blank=True, null=True)
    api_documentation_url = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    class Meta:
        verbose_name = 'Integration Provider'
        verbose_name_plural = 'Integration Providers'
    def __str__(self):
        return self.name

class IntegrationConnection(BaseModel):
    """Active integration connections."""
    provider = models.ForeignKey(IntegrationProvider, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    connection_type = models.CharField(max_length=50, choices=[
        ('api', 'REST API'), ('sftp', 'SFTP'), ('database', 'Direct Database'), ('webhook', 'Webhook'), ('file', 'File Exchange'),
    ])
    base_url = models.URLField(blank=True, null=True)
    credentials = models.JSONField(blank=True, null=True)
    configuration = models.JSONField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=[('active', 'Active'), ('inactive', 'Inactive'), ('testing', 'Testing'), ('failed', 'Failed')], default='testing')
    last_successful_sync = models.DateTimeField(null=True, blank=True)
    last_error_message = models.TextField(blank=True, null=True)
    class Meta:
        verbose_name = 'Integration Connection'
        verbose_name_plural = 'Integration Connections'
    def __str__(self):
        return f"{self.name} ({self.provider.name})"

class IntegrationLog(BaseModel):
    """Log of integration activities."""
    connection = models.ForeignKey(IntegrationConnection, on_delete=models.CASCADE)
    operation_type = models.CharField(max_length=50, choices=[('sync', 'Data Synchronization'), ('query', 'Data Query'), ('push', 'Data Push'), ('pull', 'Data Pull'), ('test', 'Connection Test')])
    status = models.CharField(max_length=20, choices=[('success', 'Success'), ('failed', 'Failed'), ('partial', 'Partial Success'), ('timeout', 'Timeout')])
    records_processed = models.IntegerField(default=0)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)
    request_payload = models.JSONField(blank=True, null=True)
    response_payload = models.JSONField(blank=True, null=True)
    class Meta:
        verbose_name = 'Integration Log'
        verbose_name_plural = 'Integration Logs'
        ordering = ['-start_time']

class WebhookEndpoint(BaseModel):
    """Webhook endpoints for external integrations."""
    customer = models.ForeignKey('payrixa.Customer', on_delete=models.CASCADE, related_name='webhook_endpoints')
    name = models.CharField(max_length=100)
    url = models.URLField()
    secret = models.CharField(max_length=64, blank=True, help_text='HMAC signing secret')
    active = models.BooleanField(default=True)
    event_types = models.JSONField(default=list, help_text='List of event types to send')
    class Meta:
        verbose_name = 'Webhook Endpoint'
        verbose_name_plural = 'Webhook Endpoints'
        unique_together = ('customer', 'name')
    def __str__(self):
        return f"{self.name} ({self.url})"
    def save(self, *args, **kwargs):
        if not self.secret:
            self.secret = secrets.token_hex(32)
        super().save(*args, **kwargs)

class WebhookDelivery(BaseModel):
    """Webhook delivery attempts and status."""
    endpoint = models.ForeignKey(WebhookEndpoint, on_delete=models.CASCADE, related_name='deliveries')
    event_type = models.CharField(max_length=50)
    payload = models.JSONField()
    status = models.CharField(max_length=20, choices=[('pending', 'Pending'), ('success', 'Success'), ('failed', 'Failed'), ('retrying', 'Retrying')], default='pending')
    attempts = models.IntegerField(default=0)
    max_attempts = models.IntegerField(default=5)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, null=True)
    response_code = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True, null=True)
    class Meta:
        verbose_name = 'Webhook Delivery'
        verbose_name_plural = 'Webhook Deliveries'
        ordering = ['-created_at']
    def schedule_next_attempt(self):
        """Calculate next retry time with exponential backoff."""
        if self.attempts >= self.max_attempts:
            self.status = 'failed'
            self.save()
            return None
        delay_minutes = 2 ** self.attempts
        self.next_attempt_at = timezone.now() + timezone.timedelta(minutes=delay_minutes)
        self.status = 'retrying'
        self.save()
        return self.next_attempt_at
