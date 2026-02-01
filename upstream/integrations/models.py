import secrets
from django.db import models
from django.utils import timezone
from encrypted_model_fields.fields import EncryptedCharField
from upstream.core.models import BaseModel


class EHRConnection(BaseModel):
    """
    EHR connection credentials per customer with encrypted secrets.

    Stores OAuth 2.0 credentials for Epic, Cerner, and athenahealth integrations.
    Secrets are encrypted at rest using django-encrypted-model-fields.
    """

    EHR_TYPE_CHOICES = [
        ("epic", "Epic FHIR R4"),
        ("cerner", "Cerner/Oracle Health"),
        ("athena", "athenahealth"),
    ]

    customer = models.ForeignKey(
        "upstream.Customer",
        on_delete=models.CASCADE,
        related_name="ehr_connections",
    )
    ehr_type = models.CharField(
        max_length=20,
        choices=EHR_TYPE_CHOICES,
        db_index=True,
        help_text="EHR vendor type",
    )
    name = models.CharField(
        max_length=100,
        help_text="Friendly name for this connection (e.g., 'Main Hospital Epic')",
    )
    client_id = models.CharField(
        max_length=255,
        help_text="OAuth 2.0 client ID",
    )
    client_secret = EncryptedCharField(
        max_length=500,
        help_text="OAuth 2.0 client secret (encrypted at rest)",
    )
    oauth_endpoint = models.URLField(
        help_text="OAuth 2.0 token endpoint URL",
    )
    fhir_endpoint = models.URLField(
        help_text="FHIR API base URL",
    )
    enabled = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this connection is active",
    )
    last_poll = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last successful poll timestamp",
    )
    last_error = models.TextField(
        blank=True,
        null=True,
        help_text="Last error message if connection failed",
    )
    health_status = models.CharField(
        max_length=20,
        choices=[
            ("healthy", "Healthy"),
            ("degraded", "Degraded"),
            ("unhealthy", "Unhealthy"),
            ("unknown", "Unknown"),
        ],
        default="unknown",
        db_index=True,
        help_text="Current connection health status",
    )
    health_checked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last health check timestamp",
    )

    class Meta:
        verbose_name = "EHR Connection"
        verbose_name_plural = "EHR Connections"
        unique_together = ("customer", "name")
        indexes = [
            models.Index(
                fields=["customer", "ehr_type", "enabled"],
                name="idx_ehrconnection_lookup",
            ),
            models.Index(
                fields=["enabled", "ehr_type"],
                name="idx_ehrconnection_polling",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_ehr_type_display()}) - {self.customer.name}"

    @property
    def masked_client_secret(self):
        """Return masked version of client secret for display."""
        if self.client_secret:
            return f"{'*' * 8}...{'*' * 4}"
        return None


class EHRSyncLog(BaseModel):
    """
    Track EHR synchronization attempts, successes, and failures.

    Provides audit trail for all EHR polling operations with 90-day retention.
    """

    STATUS_CHOICES = [
        ("success", "Success"),
        ("error", "Error"),
        ("partial", "Partial Success"),
    ]

    connection = models.ForeignKey(
        EHRConnection,
        on_delete=models.CASCADE,
        related_name="sync_logs",
    )
    started_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="success",
        db_index=True,
    )
    records_fetched = models.IntegerField(
        default=0,
        help_text="Number of records fetched from EHR",
    )
    records_created = models.IntegerField(
        default=0,
        help_text="Number of ClaimRecords created",
    )
    records_updated = models.IntegerField(
        default=0,
        help_text="Number of ClaimRecords updated",
    )
    records_skipped = models.IntegerField(
        default=0,
        help_text="Number of records skipped (duplicates)",
    )
    error_message = models.TextField(
        blank=True,
        null=True,
        help_text="Error details if sync failed",
    )
    sync_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional sync metadata (pagination info, etc.)",
    )

    class Meta:
        verbose_name = "EHR Sync Log"
        verbose_name_plural = "EHR Sync Logs"
        ordering = ["-started_at"]
        indexes = [
            models.Index(
                fields=["connection", "-started_at"],
                name="idx_ehrsynclog_history",
            ),
            models.Index(
                fields=["status", "-started_at"],
                name="idx_ehrsynclog_status",
            ),
            models.Index(
                fields=["-started_at"],
                name="idx_ehrsynclog_retention",
            ),
        ]

    def __str__(self):
        return f"Sync {self.connection.name} at {self.started_at} - {self.status}"

    @property
    def duration_seconds(self):
        """Calculate sync duration in seconds."""
        if self.completed_at and self.started_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class IntegrationProvider(BaseModel):
    """Third-party integration providers."""

    name = models.CharField(max_length=100, unique=True)
    provider_type = models.CharField(
        max_length=50,
        choices=[
            ("ehr", "Electronic Health Record"),
            ("practice_management", "Practice Management"),
            ("billing", "Billing System"),
            ("payer", "Payer System"),
            ("analytics", "Analytics Platform"),
            ("communication", "Communication Platform"),
            ("other", "Other"),
        ],
    )
    description = models.TextField(blank=True, null=True)
    api_documentation_url = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Integration Provider"
        verbose_name_plural = "Integration Providers"

    def __str__(self):
        return self.name


class IntegrationConnection(BaseModel):
    """Active integration connections."""

    provider = models.ForeignKey(IntegrationProvider, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    connection_type = models.CharField(
        max_length=50,
        choices=[
            ("api", "REST API"),
            ("sftp", "SFTP"),
            ("database", "Direct Database"),
            ("webhook", "Webhook"),
            ("file", "File Exchange"),
        ],
    )
    base_url = models.URLField(blank=True, null=True)
    credentials = models.JSONField(blank=True, null=True)
    configuration = models.JSONField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ("active", "Active"),
            ("inactive", "Inactive"),
            ("testing", "Testing"),
            ("failed", "Failed"),
        ],
        default="testing",
    )
    last_successful_sync = models.DateTimeField(null=True, blank=True)
    last_error_message = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Integration Connection"
        verbose_name_plural = "Integration Connections"

    def __str__(self):
        return f"{self.name} ({self.provider.name})"


class IntegrationLog(BaseModel):
    """Log of integration activities."""

    connection = models.ForeignKey(IntegrationConnection, on_delete=models.CASCADE)
    operation_type = models.CharField(
        max_length=50,
        choices=[
            ("sync", "Data Synchronization"),
            ("query", "Data Query"),
            ("push", "Data Push"),
            ("pull", "Data Pull"),
            ("test", "Connection Test"),
        ],
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ("success", "Success"),
            ("failed", "Failed"),
            ("partial", "Partial Success"),
            ("timeout", "Timeout"),
        ],
    )
    records_processed = models.IntegerField(default=0)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)
    request_payload = models.JSONField(blank=True, null=True)
    response_payload = models.JSONField(blank=True, null=True)

    class Meta:
        verbose_name = "Integration Log"
        verbose_name_plural = "Integration Logs"
        ordering = ["-start_time"]
        indexes = [
            models.Index(
                fields=["connection", "-start_time"],
                name="idx_integrationlog_history",
            ),
        ]


class WebhookEndpoint(BaseModel):
    """Webhook endpoints for external integrations."""

    customer = models.ForeignKey(
        "upstream.Customer", on_delete=models.CASCADE, related_name="webhook_endpoints"
    )
    name = models.CharField(max_length=100)
    url = models.URLField()
    secret = models.CharField(
        max_length=64, blank=True, help_text="HMAC signing secret"
    )
    active = models.BooleanField(default=True)
    event_types = models.JSONField(
        default=list, help_text="List of event types to send"
    )

    class Meta:
        verbose_name = "Webhook Endpoint"
        verbose_name_plural = "Webhook Endpoints"
        unique_together = ("customer", "name")

    def __str__(self):
        return f"{self.name} ({self.url})"

    def save(self, *args, **kwargs):
        if not self.secret:
            self.secret = secrets.token_hex(32)
        super().save(*args, **kwargs)


class WebhookDelivery(BaseModel):
    """Webhook delivery attempts and status."""

    endpoint = models.ForeignKey(
        WebhookEndpoint, on_delete=models.CASCADE, related_name="deliveries"
    )
    event_type = models.CharField(max_length=50)
    payload = models.JSONField()
    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("success", "Success"),
            ("failed", "Failed"),
            ("retrying", "Retrying"),
        ],
        default="pending",
    )
    attempts = models.IntegerField(default=0)
    max_attempts = models.IntegerField(default=5)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, null=True)
    response_code = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Webhook Delivery"
        verbose_name_plural = "Webhook Deliveries"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["status", "next_attempt_at"],
                name="idx_webhookdelivery_retry",
            ),
        ]

    def schedule_next_attempt(self):
        """Calculate next retry time with exponential backoff."""
        if self.attempts >= self.max_attempts:
            self.status = "failed"
            self.save()
            return None
        delay_minutes = 2**self.attempts
        self.next_attempt_at = timezone.now() + timezone.timedelta(
            minutes=delay_minutes
        )
        self.status = "retrying"
        self.save()
        return self.next_attempt_at
