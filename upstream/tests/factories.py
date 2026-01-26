"""
Factory classes for generating test data for core models.

Uses factory_boy to create valid test instances with sensible defaults.
Supports trait customization for common scenarios
(e.g., processing/complete/failed states).
"""

import factory
from factory.django import DjangoModelFactory
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from upstream.models import (
    Customer,
    Settings,
    Upload,
    DataQualityReport,
    ClaimRecord,
    ReportRun,
    DriftEvent,
    UserProfile,
    PayerMapping,
    CPTGroupMapping,
)
from upstream.alerts.models import (
    AlertRule,
    NotificationChannel,
    AlertEvent,
    Alert,
    OperatorJudgment,
)
from upstream.integrations.models import (
    IntegrationProvider,
    IntegrationConnection,
    IntegrationLog,
    WebhookEndpoint,
    WebhookDelivery,
)


class CustomerFactory(DjangoModelFactory):
    """Factory for Customer model."""

    class Meta:
        model = Customer
        django_get_or_create = ("name",)

    name = factory.Sequence(lambda n: f"Customer {n}")


class UserFactory(DjangoModelFactory):
    """Factory for Django User model."""

    class Meta:
        model = User
        django_get_or_create = ("username",)

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    is_active = True
    is_staff = False
    is_superuser = False

    @factory.post_generation
    def password(obj, create, extracted, **kwargs):
        """Set password after creation."""
        if not create:
            return
        if extracted:
            obj.set_password(extracted)
        else:
            obj.set_password("testpass123")


class UserProfileFactory(DjangoModelFactory):
    """Factory for UserProfile model."""

    class Meta:
        model = UserProfile

    user = factory.SubFactory(UserFactory)
    customer = factory.SubFactory(CustomerFactory)
    role = "viewer"


class SettingsFactory(DjangoModelFactory):
    """Factory for Settings model."""

    class Meta:
        model = Settings

    customer = factory.SubFactory(CustomerFactory)
    to_email = factory.Faker("email")
    cc_email = factory.Faker("email")
    attach_pdf = True


class UploadFactory(DjangoModelFactory):
    """Factory for Upload model."""

    class Meta:
        model = Upload

    customer = factory.SubFactory(CustomerFactory)
    uploaded_at = factory.LazyFunction(timezone.now)
    filename = factory.Faker("file_name", extension="csv")
    status = "processing"
    row_count = factory.Faker("random_int", min=10, max=1000)
    date_min = factory.Faker("date_between", start_date="-2y", end_date="-1y")
    date_max = factory.LazyAttribute(
        lambda obj: obj.date_min + timedelta(days=90) if obj.date_min else None
    )
    uploaded_by = factory.SubFactory(UserFactory)
    upload_source = "web_ui"
    accepted_row_count = factory.LazyAttribute(lambda obj: int(obj.row_count * 0.9))
    rejected_row_count = factory.LazyAttribute(
        lambda obj: obj.row_count - obj.accepted_row_count
    )
    warning_row_count = 0
    file_size_bytes = factory.Faker("random_int", min=1024, max=10485760)
    file_hash = factory.Faker("sha256")
    file_encoding = "utf-8"

    class Params:
        processing = factory.Trait(
            status="processing",
            processing_started_at=factory.LazyFunction(timezone.now),
        )
        success = factory.Trait(
            status="success",
            processing_started_at=factory.LazyFunction(
                lambda: timezone.now() - timedelta(minutes=5)
            ),
            processing_completed_at=factory.LazyFunction(timezone.now),
            processing_duration_seconds=300,
        )
        failed = factory.Trait(
            status="failed",
            error_message="Processing failed due to validation errors",
            processing_started_at=factory.LazyFunction(
                lambda: timezone.now() - timedelta(minutes=2)
            ),
            processing_completed_at=factory.LazyFunction(timezone.now),
            processing_duration_seconds=120,
        )
        partial = factory.Trait(
            status="partial",
            processing_started_at=factory.LazyFunction(
                lambda: timezone.now() - timedelta(minutes=5)
            ),
            processing_completed_at=factory.LazyFunction(timezone.now),
            processing_duration_seconds=300,
        )


class DataQualityReportFactory(DjangoModelFactory):
    """Factory for DataQualityReport model."""

    class Meta:
        model = DataQualityReport

    upload = factory.SubFactory(UploadFactory)
    customer = factory.LazyAttribute(lambda obj: obj.upload.customer)
    total_rows = factory.LazyAttribute(lambda obj: obj.upload.row_count or 100)
    accepted_rows = factory.LazyAttribute(
        lambda obj: obj.upload.accepted_row_count or 90
    )
    rejected_rows = factory.LazyAttribute(
        lambda obj: obj.upload.rejected_row_count or 10
    )
    rejection_details = {"1": "Missing required field"}
    warnings = [{"row": 5, "message": "Potential data quality issue"}]
    phi_detections = 0
    missing_fields = factory.LazyAttribute(
        lambda obj: max(0, obj.rejected_rows // 2) if obj.rejected_rows else 0
    )
    invalid_dates = factory.LazyAttribute(
        lambda obj: (
            max(0, obj.rejected_rows - obj.missing_fields) if obj.rejected_rows else 0
        )
    )
    invalid_values = 0


class ClaimRecordFactory(DjangoModelFactory):
    """Factory for ClaimRecord model."""

    class Meta:
        model = ClaimRecord

    upload = factory.SubFactory(UploadFactory)
    customer = factory.LazyAttribute(lambda obj: obj.upload.customer)
    payer = factory.Faker("company")
    cpt = factory.Faker(
        "random_element", elements=["99213", "99214", "99215", "99385", "99386"]
    )
    cpt_group = factory.LazyAttribute(lambda obj: f"Group-{obj.cpt[:3]}")
    submitted_date = factory.Faker("date_between", start_date="-1y", end_date="-30d")
    decided_date = factory.LazyAttribute(
        lambda obj: (
            obj.submitted_date + timedelta(days=30) if obj.submitted_date else None
        )
    )
    outcome = "PAID"
    billed_amount = factory.Faker(
        "pydecimal", left_digits=4, right_digits=2, positive=True
    )
    allowed_amount = factory.LazyAttribute(
        lambda obj: (
            (obj.billed_amount * Decimal("0.9")).quantize(Decimal("0.01"))
            if obj.billed_amount
            else None
        )
    )
    paid_amount = factory.LazyAttribute(
        lambda obj: (
            (obj.billed_amount * Decimal("0.8")).quantize(Decimal("0.01"))
            if obj.billed_amount
            else None
        )
    )
    validation_passed = True

    class Params:
        denied = factory.Trait(
            outcome="DENIED",
            denial_reason_code=factory.Faker(
                "random_element",
                elements=["CO-16", "CO-45", "CO-50", "PR-1"],
            ),
            denial_reason_text=factory.Faker(
                "random_element",
                elements=[
                    "Medical necessity",
                    "Prior authorization required",
                    "Coding error",
                    "Timely filing limit",
                ],
            ),
            paid_amount=Decimal("0.00"),
            allowed_amount=Decimal("0.00"),
        )


class ReportRunFactory(DjangoModelFactory):
    """Factory for ReportRun model."""

    class Meta:
        model = ReportRun

    customer = factory.SubFactory(CustomerFactory)
    run_type = "weekly"
    status = "success"
    started_at = factory.LazyFunction(lambda: timezone.now() - timedelta(minutes=10))
    finished_at = factory.LazyFunction(timezone.now)
    summary_json = factory.Dict({"total_records": 100, "drift_detected": 5})

    class Params:
        running = factory.Trait(
            status="running",
            finished_at=None,
            summary_json=None,
        )
        failed = factory.Trait(
            status="failed",
        )


class DriftEventFactory(DjangoModelFactory):
    """Factory for DriftEvent model."""

    class Meta:
        model = DriftEvent

    customer = factory.SubFactory(CustomerFactory)
    report_run = factory.SubFactory(
        ReportRunFactory, customer=factory.SelfAttribute("..customer")
    )
    drift_type = "DENIAL_RATE"
    payer = factory.Sequence(lambda n: f"Payer-{n}")
    cpt_group = factory.Sequence(lambda n: f"Group-{n % 100}")
    baseline_start = factory.Faker("date_between", start_date="-120d", end_date="-90d")
    baseline_end = factory.Faker("date_between", start_date="-89d", end_date="-60d")
    current_start = factory.Faker("date_between", start_date="-59d", end_date="-30d")
    current_end = factory.Faker("date_between", start_date="-29d", end_date="today")
    baseline_value = 0.25
    current_value = 0.40
    delta_value = factory.LazyAttribute(
        lambda obj: obj.current_value - obj.baseline_value
    )
    severity = factory.LazyAttribute(lambda obj: min(abs(obj.delta_value) * 2, 1.0))
    confidence = 0.95
    baseline_sample_size = factory.Faker("random_int", min=100, max=1000)
    current_sample_size = factory.Faker("random_int", min=100, max=1000)
    statistical_significance = 0.01
    trend_direction = "degrading"
    created_at = factory.LazyFunction(timezone.now)

    class Params:
        decision_time = factory.Trait(
            drift_type="DECISION_TIME",
        )
        high_severity = factory.Trait(
            severity=0.9,
        )
        improving = factory.Trait(
            trend_direction="improving",
            severity=0.3,
        )


class PayerMappingFactory(DjangoModelFactory):
    """Factory for PayerMapping model."""

    class Meta:
        model = PayerMapping

    customer = factory.SubFactory(CustomerFactory)
    raw_name = factory.Faker("company")
    normalized_name = factory.LazyAttribute(lambda obj: obj.raw_name.upper())


class CPTGroupMappingFactory(DjangoModelFactory):
    """Factory for CPTGroupMapping model."""

    class Meta:
        model = CPTGroupMapping

    customer = factory.SubFactory(CustomerFactory)
    cpt_code = factory.Faker(
        "random_element",
        elements=["99213", "99214", "99215", "99385", "99386", "99395", "99396"],
    )
    cpt_group = factory.LazyAttribute(lambda obj: f"Group-{obj.cpt_code[:3]}")


class AlertRuleFactory(DjangoModelFactory):
    """Factory for AlertRule model."""

    class Meta:
        model = AlertRule

    customer = factory.SubFactory(CustomerFactory)
    name = factory.Sequence(lambda n: f"Alert Rule {n}")
    description = factory.Faker("sentence")
    scope = factory.Dict({})
    metric = "severity"
    threshold_type = "gte"
    threshold_value = 0.7
    enabled = True
    severity = "warning"
    routing_priority = 0
    routing_tags = factory.List([])

    class Params:
        critical = factory.Trait(
            severity="critical",
            threshold_value=0.9,
        )
        disabled = factory.Trait(
            enabled=False,
        )


class NotificationChannelFactory(DjangoModelFactory):
    """Factory for NotificationChannel model."""

    class Meta:
        model = NotificationChannel

    customer = factory.SubFactory(CustomerFactory)
    name = factory.Sequence(lambda n: f"Channel {n}")
    channel_type = "email"
    config = factory.Dict({"to": "alerts@example.com"})
    enabled = True

    class Params:
        webhook = factory.Trait(
            channel_type="webhook",
            config=factory.Dict({"url": "https://webhook.example.com/alerts"}),
        )
        slack = factory.Trait(
            channel_type="slack",
            config=factory.Dict(
                {"webhook_url": "https://hooks.slack.com/services/XXX"}
            ),
        )


class AlertEventFactory(DjangoModelFactory):
    """Factory for AlertEvent model."""

    class Meta:
        model = AlertEvent

    customer = factory.SubFactory(CustomerFactory)
    alert_rule = factory.SubFactory(
        AlertRuleFactory, customer=factory.SelfAttribute("..customer")
    )
    drift_event = factory.SubFactory(
        DriftEventFactory, customer=factory.SelfAttribute("..customer")
    )
    triggered_at = factory.LazyFunction(timezone.now)
    status = "pending"
    payload = factory.Dict({})

    class Params:
        sent = factory.Trait(
            status="sent",
            notification_sent_at=factory.LazyFunction(timezone.now),
        )
        failed = factory.Trait(
            status="failed",
            error_message="Failed to send notification",
        )


class AlertFactory(DjangoModelFactory):
    """Factory for Alert model (legacy)."""

    class Meta:
        model = Alert

    rule = factory.SubFactory(AlertRuleFactory)
    title = factory.Faker("sentence", nb_words=6)
    message = factory.Faker("paragraph")
    severity = "warning"
    status = "new"

    class Params:
        acknowledged = factory.Trait(
            status="acknowledged",
        )
        resolved = factory.Trait(
            status="resolved",
            resolved_at=factory.LazyFunction(timezone.now),
            resolved_by=factory.SubFactory(UserFactory),
        )


class OperatorJudgmentFactory(DjangoModelFactory):
    """Factory for OperatorJudgment model."""

    class Meta:
        model = OperatorJudgment

    customer = factory.SubFactory(CustomerFactory)
    alert_event = factory.SubFactory(
        AlertEventFactory, customer=factory.SelfAttribute("..customer")
    )
    verdict = "real"
    reason_codes_json = factory.List([])
    notes = factory.Faker("paragraph")
    operator = factory.SubFactory(UserFactory)

    class Params:
        noise = factory.Trait(
            verdict="noise",
            reason_codes_json=factory.List(["false_positive"]),
        )
        recovered = factory.Trait(
            verdict="real",
            recovered_amount=Decimal("1500.00"),
            recovered_date=factory.LazyFunction(lambda: timezone.now().date()),
        )


class IntegrationProviderFactory(DjangoModelFactory):
    """Factory for IntegrationProvider model."""

    class Meta:
        model = IntegrationProvider

    name = factory.Sequence(lambda n: f"Provider {n}")
    provider_type = "ehr"
    description = factory.Faker("paragraph")
    api_documentation_url = factory.Faker("url")
    is_active = True


class IntegrationConnectionFactory(DjangoModelFactory):
    """Factory for IntegrationConnection model."""

    class Meta:
        model = IntegrationConnection

    provider = factory.SubFactory(IntegrationProviderFactory)
    name = factory.Sequence(lambda n: f"Connection {n}")
    connection_type = "api"
    base_url = factory.Faker("url")
    credentials = factory.Dict({"api_key": "test_key_123"})
    configuration = factory.Dict({})
    status = "active"

    class Params:
        testing = factory.Trait(
            status="testing",
        )
        failed = factory.Trait(
            status="failed",
            last_error_message="Connection timeout",
        )


class IntegrationLogFactory(DjangoModelFactory):
    """Factory for IntegrationLog model."""

    class Meta:
        model = IntegrationLog

    connection = factory.SubFactory(IntegrationConnectionFactory)
    operation_type = "sync"
    status = "success"
    records_processed = factory.Faker("random_int", min=0, max=1000)
    start_time = factory.LazyFunction(lambda: timezone.now() - timedelta(minutes=5))
    end_time = factory.LazyFunction(timezone.now)

    class Params:
        failed = factory.Trait(
            status="failed",
            error_message="Synchronization failed",
        )


class WebhookEndpointFactory(DjangoModelFactory):
    """Factory for WebhookEndpoint model."""

    class Meta:
        model = WebhookEndpoint

    customer = factory.SubFactory(CustomerFactory)
    name = factory.Sequence(lambda n: f"Webhook {n}")
    url = factory.Faker("url")
    secret = factory.Faker("sha256")
    active = True
    event_types = factory.List(["drift.detected", "alert.triggered"])


class WebhookDeliveryFactory(DjangoModelFactory):
    """Factory for WebhookDelivery model."""

    class Meta:
        model = WebhookDelivery

    endpoint = factory.SubFactory(WebhookEndpointFactory)
    event_type = "drift.detected"
    payload = factory.Dict({"event": "test"})
    status = "pending"
    attempts = 0
    max_attempts = 5

    class Params:
        success = factory.Trait(
            status="success",
            attempts=1,
            last_attempt_at=factory.LazyFunction(timezone.now),
            response_code=200,
        )
        failed = factory.Trait(
            status="failed",
            attempts=5,
            last_attempt_at=factory.LazyFunction(timezone.now),
            last_error="Max retries exceeded",
            response_code=500,
        )
