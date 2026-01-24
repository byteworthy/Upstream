# Alert Systems: Implementation & Testing Guide

**Generated:** 2026-01-22
**Purpose:** Step-by-step implementation and comprehensive testing
**Status:** Production-Ready Reference

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Step-by-Step Implementation](#step-by-step-implementation)
3. [Comprehensive Testing](#comprehensive-testing)
4. [Performance Optimization](#performance-optimization)
5. [Deployment Guide](#deployment-guide)
6. [Troubleshooting](#troubleshooting)

---

## Quick Start

### 30-Second Overview

```bash
# 1. Run migrations
python manage.py makemigrations alerts
python manage.py migrate

# 2. Create alert rules
python manage.py shell
>>> from upstream.alerts.models import AlertRule, Customer
>>> customer = Customer.objects.first()
>>> AlertRule.objects.create(
...     customer=customer,
...     name="High Payer Drift",
...     alert_type="PAYER_DRIFT",
...     threshold_value=0.15,
...     enabled=True
... )

# 3. Run alert detection
python manage.py detect_alerts --all

# 4. Process pending alerts
python manage.py process_alerts
```

---

## Step-by-Step Implementation

### Phase 1: Core Hardening (Week 1-2)

#### Step 1.1: Install Security Modules

Create the new security modules:

```bash
# Create directory structure
mkdir -p upstream/alerts/{detectors,tests}
touch upstream/alerts/detectors/__init__.py
touch upstream/alerts/tests/__init__.py

# Copy files from SECURITY_HARDENING_FIXES.md:
# - processing.py
# - suppression.py
# - confidence.py
# - pii_sanitizer.py
# - webhook_security.py
# - validation.py
# - authorization.py
# - email_security.py
# - dead_letter_queue.py
# - audit.py
# - rate_limiter.py
# - metrics.py
```

#### Step 1.2: Update Models

**File:** `upstream/alerts/models.py`

Add the DeadLetterQueue and AlertAuditLog models:

```python
# Add to existing models.py

from django.db import models
from django.utils import timezone


class DeadLetterQueue(models.Model):
    """Store failed critical alerts for retry."""

    alert_event = models.ForeignKey(
        'AlertEvent',
        on_delete=models.CASCADE,
        related_name='dlq_entries'
    )

    failure_reason = models.TextField()
    failure_timestamp = models.DateTimeField(default=timezone.now)
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=5)
    next_retry_at = models.DateTimeField()

    payload_snapshot = models.JSONField()

    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending Retry'),
            ('retrying', 'Retrying'),
            ('exhausted', 'Retries Exhausted'),
            ('recovered', 'Recovered')
        ],
        default='pending'
    )

    class Meta:
        db_table = 'alert_dead_letter_queue'
        indexes = [
            models.Index(fields=['status', 'next_retry_at']),
            models.Index(fields=['alert_event']),
        ]


class AlertAuditLog(models.Model):
    """Immutable audit log for all alert operations."""

    user = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    user_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    action = models.CharField(
        max_length=50,
        db_index=True
    )

    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    alert_event = models.ForeignKey(
        'AlertEvent',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )

    customer = models.ForeignKey(
        'upstream.Customer',
        on_delete=models.CASCADE,
        related_name='alert_audit_logs'
    )

    details = models.JSONField(default=dict)
    session_id = models.CharField(max_length=100, blank=True)
    request_id = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = 'alert_audit_log'
        ordering = ['-timestamp']
```

#### Step 1.3: Add Database Constraints

Create migration:

```bash
python manage.py makemigrations alerts --name security_hardening
```

Edit the migration to add constraints:

```python
# upstream/alerts/migrations/000X_security_hardening.py

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('alerts', '000X_previous_migration'),
    ]

    operations = [
        # Prevent duplicate alerts (race condition fix)
        migrations.AddConstraint(
            model_name='alertevent',
            constraint=models.UniqueConstraint(
                fields=['drift_event', 'alert_rule'],
                name='unique_alert_per_drift_rule',
                condition=models.Q(drift_event__isnull=False)
            ),
        ),

        # Performance indexes
        migrations.AddIndex(
            model_name='alertevent',
            index=models.Index(
                fields=['customer', 'status', 'notification_sent_at'],
                name='idx_alert_suppression'
            ),
        ),

        migrations.AddIndex(
            model_name='alertevent',
            index=models.Index(
                fields=['customer', 'triggered_at'],
                name='idx_alert_customer_time'
            ),
        ),

        # Data validation constraints
        migrations.AddConstraint(
            model_name='alertevent',
            constraint=models.CheckConstraint(
                check=models.Q(status__in=['pending', 'sent', 'failed', 'suppressed', 'resolved']),
                name='valid_alert_status'
            ),
        ),
    ]
```

Run migration:

```bash
python manage.py migrate alerts
```

#### Step 1.4: Update Existing Services

**File:** `upstream/alerts/services.py`

Replace the existing functions with the hardened versions:

```python
"""
Alert services - PRODUCTION HARDENED VERSION
"""

from typing import List, Dict, Optional
import logging
import time
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.db import transaction, IntegrityError

from .models import AlertRule, AlertEvent, NotificationChannel
from upstream.models import DriftEvent, Customer

# Import new security modules
from .processing import AlertProcessingEngine
from .suppression import SuppressionEngine
from .confidence import ConfidenceScorer
from .pii_sanitizer import PIISanitizer, safe_logger
from .validation import PayloadValidator
from .audit import AlertAuditLog
from .rate_limiter import AlertRateLimiter
from .metrics import AlertMetrics
from .dead_letter_queue import DeadLetterQueue

# Use PII-safe logger
logger = safe_logger()

# Initialize engines
processing_engine = AlertProcessingEngine()
suppression_engine = SuppressionEngine()
confidence_scorer = ConfidenceScorer()


@transaction.atomic
def evaluate_drift_event(drift_event):
    """
    Evaluate drift event against alert rules - PRODUCTION HARDENED.

    Security:
    - Race condition prevention via database locks
    - Input validation
    - PII sanitization
    - Audit logging
    """
    start_time = time.time()

    alert_events = []

    # Lock drift event to prevent concurrent processing
    try:
        drift_event = DriftEvent.objects.select_for_update().get(id=drift_event.id)
    except DriftEvent.DoesNotExist:
        logger.error("DriftEvent not found", drift_event_id=drift_event.id)
        return []

    # Get alert rules with locking
    alert_rules = AlertRule.objects.filter(
        customer=drift_event.customer,
        enabled=True
    ).select_for_update(skip_locked=True)

    for rule in alert_rules:
        if rule.evaluate(drift_event):
            # Rate limit check
            allowed, reason = AlertRateLimiter.check_rate_limit(
                drift_event.customer_id,
                drift_event.drift_type,
                drift_event.severity
            )

            if not allowed:
                logger.warning(
                    "Alert rate limited",
                    customer_id=drift_event.customer_id,
                    reason=reason
                )
                continue

            # Build payload with security
            payload = _build_secure_alert_payload(drift_event, rule)

            # Validate payload
            try:
                payload = PayloadValidator.sanitize_and_validate(payload)
            except Exception as e:
                logger.error("Payload validation failed", error=str(e))
                continue

            # Create alert with race condition handling
            try:
                alert_event, created = AlertEvent.objects.get_or_create(
                    drift_event=drift_event,
                    alert_rule=rule,
                    defaults={
                        'customer': drift_event.customer,
                        'report_run': drift_event.report_run,
                        'triggered_at': timezone.now(),
                        'status': 'pending',
                        'payload': payload
                    }
                )

                if created:
                    # Increment rate limit counters
                    AlertRateLimiter.increment_counters(
                        drift_event.customer_id,
                        drift_event.drift_type,
                        drift_event.severity
                    )

                    # Record metrics
                    AlertMetrics.record_alert_created(
                        drift_event.customer_id,
                        drift_event.severity,
                        drift_event.drift_type
                    )

                    # Audit log
                    AlertAuditLog.log(
                        action='alert_created',
                        customer=drift_event.customer,
                        alert_event=alert_event,
                        details={
                            'alert_rule': rule.name,
                            'drift_event_id': drift_event.id,
                            'payer': PIISanitizer.sanitize_string(drift_event.payer),
                            'severity': drift_event.severity,
                            'confidence': payload.get('confidence')
                        }
                    )

                    logger.info(
                        "Alert created",
                        rule_name=rule.name,
                        drift_event_id=drift_event.id
                    )
                else:
                    logger.info(
                        "Alert already exists",
                        rule_name=rule.name,
                        drift_event_id=drift_event.id
                    )

                alert_events.append(alert_event)

            except IntegrityError as e:
                # Another process created it - fetch it
                logger.warning("Race condition detected", error=str(e))
                alert_event = AlertEvent.objects.filter(
                    drift_event=drift_event,
                    alert_rule=rule
                ).first()

                if alert_event:
                    alert_events.append(alert_event)

    # Record processing time
    duration_ms = (time.time() - start_time) * 1000
    AlertMetrics.record_processing_time('evaluate_drift_event', duration_ms)

    return alert_events


def _build_secure_alert_payload(drift_event, rule):
    """Build alert payload with security and confidence scoring."""

    # Calculate confidence
    confidence_data = {
        'sample_count': getattr(drift_event, 'sample_count', 20),
        'baseline_value': float(drift_event.baseline_value or 0),
        'current_value': float(drift_event.current_value or 0),
        'baseline_std': float(getattr(drift_event, 'baseline_std',
                                    drift_event.baseline_value * 0.1 if drift_event.baseline_value else 0)),
        'consecutive_days_triggered': 1,  # TODO: Track this
        'historical_real_ratio': 0.5  # TODO: Calculate from OperatorJudgment
    }
    confidence_result = confidence_scorer.calculate_confidence(confidence_data)

    # Build payload with sanitization
    payload = {
        'product_name': 'DriftWatch',
        'signal_type': PIISanitizer.sanitize_string(drift_event.drift_type),
        'entity_label': PIISanitizer.sanitize_string(drift_event.payer),
        'payer': PIISanitizer.sanitize_string(drift_event.payer),
        'cpt_group': PIISanitizer.sanitize_string(drift_event.cpt_group),
        'drift_type': PIISanitizer.sanitize_string(drift_event.drift_type),
        'baseline_value': float(drift_event.baseline_value or 0),
        'current_value': float(drift_event.current_value or 0),
        'delta_value': float(drift_event.delta_value or 0),
        'severity': _sanitize_severity(drift_event.severity),
        'rule_name': PIISanitizer.sanitize_string(rule.name),
        'rule_threshold': float(rule.threshold_value or 0),
        'confidence': confidence_result['confidence'],
        'confidence_breakdown': confidence_result['breakdown'],
        'confidence_interpretation': confidence_result['interpretation']
    }

    return payload


def _sanitize_severity(severity):
    """Validate severity value."""
    allowed = ['info', 'warning', 'critical', 'emergency']
    return severity if severity in allowed else 'warning'


def send_alert_notification(alert_event):
    """
    Send notification for alert - PRODUCTION HARDENED.

    Security:
    - Idempotency check
    - Intelligent suppression
    - PII sanitization
    - Error handling with DLQ
    """
    start_time = time.time()

    # Idempotency check
    if alert_event.status == 'sent':
        logger.info("Alert already sent (idempotent)", alert_id=alert_event.id)
        return True

    # Skip if failed (manual intervention required)
    if alert_event.status == 'failed':
        logger.info("Alert marked failed, skipping", alert_id=alert_event.id)
        return False

    # Intelligent suppression check
    should_suppress, context = suppression_engine.should_suppress(alert_event)

    if should_suppress:
        alert_event.status = 'suppressed'
        alert_event.notification_sent_at = timezone.now()
        alert_event.error_message = f"Suppressed: {context.get('reason')}"
        alert_event.save()

        # Record metrics
        AlertMetrics.record_alert_suppressed(
            alert_event.customer_id,
            context.get('reason', 'unknown')
        )

        # Audit log
        AlertAuditLog.log(
            action='alert_suppressed',
            customer=alert_event.customer,
            alert_event=alert_event,
            details=context
        )

        logger.info("Alert suppressed", alert_id=alert_event.id, context=context)
        return True

    # Get notification channels
    customer = alert_event.customer
    alert_rule = alert_event.alert_rule

    if alert_rule.routing_channels.exists():
        channels = alert_rule.routing_channels.filter(enabled=True)
    else:
        channels = NotificationChannel.objects.filter(customer=customer, enabled=True)

    success = False
    error_message = None

    try:
        for channel in channels:
            if channel.channel_type == 'email':
                success = _send_email_notification_secure(alert_event, channel)
            elif channel.channel_type == 'slack':
                success = _send_slack_notification(alert_event, channel)
            elif channel.channel_type == 'webhook':
                success = _send_webhook_notification_secure(alert_event, channel)

        if not channels.exists():
            success = _send_default_email_notification_secure(alert_event)

        if success:
            alert_event.status = 'sent'
            alert_event.notification_sent_at = timezone.now()
            alert_event.error_message = None
            alert_event.save()

            # Record metrics
            duration_ms = (time.time() - start_time) * 1000
            AlertMetrics.record_alert_sent(alert_event.customer_id, duration_ms)

            # Audit log
            AlertAuditLog.log(
                action='alert_sent',
                customer=alert_event.customer,
                alert_event=alert_event,
                details={
                    'notification_sent_at': alert_event.notification_sent_at.isoformat(),
                    'channels': [ch.channel_type for ch in channels]
                }
            )

            logger.info("Alert sent successfully", alert_id=alert_event.id)

    except Exception as e:
        error_message = str(e)
        error_type = e.__class__.__name__

        alert_event.status = 'failed'
        alert_event.error_message = error_message[:500]  # Limit size
        alert_event.save()

        # Record metrics
        AlertMetrics.record_alert_failed(alert_event.customer_id, error_type)

        # Add to Dead Letter Queue for retry
        DeadLetterQueue.add_to_queue(alert_event, error_message)

        # Audit log
        AlertAuditLog.log(
            action='alert_failed',
            customer=alert_event.customer,
            alert_event=alert_event,
            details={
                'error_type': error_type,
                'error_message': error_message[:200]  # Truncate for audit
            }
        )

        logger.error("Alert failed", alert_id=alert_event.id, error=error_message)
        success = False

    return success


def _send_email_notification_secure(alert_event, channel):
    """Send email with security hardening."""
    from .email_security import SecureEmailSender

    config = channel.config or {}
    recipients = config.get('recipients', [])

    if not recipients:
        return False

    # Build email content (sanitized)
    subject = f"[{alert_event.payload.get('severity', 'INFO').upper()}] Upstream Alert"

    html_body = render_to_string('alerts/email_template.html', {
        'alert': alert_event,
        'payload': PIISanitizer.sanitize_dict(alert_event.payload)
    })

    # Send securely
    success, error = SecureEmailSender.send_alert_email(
        recipients=recipients,
        subject=subject,
        html_body=html_body
    )

    return success


def _send_default_email_notification_secure(alert_event):
    """Send default email securely."""
    from .email_security import SecureEmailSender

    recipients = [getattr(settings, 'DEFAULT_ALERT_EMAIL', 'alerts@example.com')]

    subject = f"[{alert_event.payload.get('severity', 'INFO').upper()}] Upstream Alert"

    html_body = render_to_string('alerts/email_template.html', {
        'alert': alert_event,
        'payload': PIISanitizer.sanitize_dict(alert_event.payload)
    })

    success, error = SecureEmailSender.send_alert_email(
        recipients=recipients,
        subject=subject,
        html_body=html_body
    )

    return success


def _send_webhook_notification_secure(alert_event, channel):
    """Send webhook with security."""
    from .webhook_security import SecureWebhookDelivery

    config = channel.config or {}
    webhook_url = config.get('url')

    if not webhook_url:
        return False

    # Get customer-specific secret key
    secret_key = config.get('secret_key') or settings.WEBHOOK_SECRET_KEY

    webhook_delivery = SecureWebhookDelivery(secret_key=secret_key)

    # Prepare payload (sanitized)
    payload = PIISanitizer.sanitize_dict(alert_event.payload)

    success, response_code, error = webhook_delivery.deliver_webhook(
        webhook_url=webhook_url,
        payload=payload,
        customer_id=alert_event.customer_id
    )

    return success


def process_pending_alerts():
    """Process pending alerts with parallel execution."""
    pending_alerts = list(AlertEvent.objects.filter(status='pending').select_related('customer', 'alert_rule'))

    if not pending_alerts:
        return {'total': 0, 'sent': 0, 'failed': 0}

    results = processing_engine.process_alert_batch(
        pending_alerts,
        max_workers=5
    )

    return {
        'total': len(pending_alerts),
        'sent': len(results['succeeded']),
        'failed': len(results['failed']),
        'rate_limited': len(results['rate_limited']),
        'circuit_open': len(results['circuit_open'])
    }


def process_dead_letter_queue():
    """Process failed alerts in DLQ."""
    results = DeadLetterQueue.process_pending_retries()

    logger.info(
        "DLQ processing complete",
        recovered=results['recovered'],
        failed=results['failed'],
        exhausted=results['exhausted']
    )

    return results
```

---

## Comprehensive Testing

### Unit Tests

**File:** `upstream/alerts/tests/test_security.py`

```python
"""
Comprehensive security tests for alert system.
"""

from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from datetime import timedelta

from upstream.models import Customer, DriftEvent
from upstream.alerts.models import AlertEvent, AlertRule
from upstream.alerts.pii_sanitizer import PIISanitizer
from upstream.alerts.validation import PayloadValidator
from upstream.alerts.authorization import AlertAuthorization
from upstream.alerts.suppression import SuppressionEngine
from upstream.alerts.webhook_security import SecureWebhookDelivery
from upstream.alerts.email_security import SecureEmailSender

User = get_user_model()


class PIISanitizerTestCase(TestCase):
    """Test PII sanitization."""

    def test_ssn_redaction(self):
        """Test SSN is redacted."""
        text = "Patient SSN is 123-45-6789"
        sanitized = PIISanitizer.sanitize_string(text)
        self.assertNotIn('123-45-6789', sanitized)
        self.assertIn('XXX-XX-XXXX', sanitized)

    def test_email_redaction(self):
        """Test email is redacted."""
        text = "Contact patient@example.com for details"
        sanitized = PIISanitizer.sanitize_string(text)
        self.assertNotIn('patient@example.com', sanitized)
        self.assertIn('[EMAIL_REDACTED]', sanitized)

    def test_dict_sanitization(self):
        """Test dictionary PII fields are sanitized."""
        data = {
            'patient_name': 'John Doe',
            'payer': 'Aetna',
            'ssn': '123-45-6789'
        }
        sanitized = PIISanitizer.sanitize_dict(data, hash_pii=False)
        self.assertEqual(sanitized['patient_name'], '[REDACTED]')
        self.assertEqual(sanitized['payer'], 'Aetna')  # Not PII
        self.assertEqual(sanitized['ssn'], '[REDACTED]')

    def test_nested_dict_sanitization(self):
        """Test nested dictionary sanitization."""
        data = {
            'alert': {
                'patient_name': 'Jane Doe',
                'claim_id': '12345'
            }
        }
        sanitized = PIISanitizer.sanitize_dict(data, hash_pii=False)
        self.assertEqual(sanitized['alert']['patient_name'], '[REDACTED]')
        self.assertEqual(sanitized['alert']['claim_id'], '12345')


class PayloadValidatorTestCase(TestCase):
    """Test payload validation."""

    def test_valid_payload(self):
        """Test valid payload passes."""
        payload = {
            'severity': 'warning',
            'payer': 'Aetna',
            'value': 123.45
        }
        validated = PayloadValidator.validate_payload(payload)
        self.assertEqual(validated, payload)

    def test_oversized_payload_rejected(self):
        """Test oversized payload is rejected."""
        payload = {
            'data': 'x' * (PayloadValidator.MAX_PAYLOAD_SIZE_BYTES + 1)
        }
        with self.assertRaises(ValidationError):
            PayloadValidator.validate_payload(payload)

    def test_deep_nesting_rejected(self):
        """Test deeply nested payload is rejected."""
        payload = {'a': {'b': {'c': {'d': {'e': {'f': {'g': 'too deep'}}}}}}}}
        with self.assertRaises(ValidationError):
            PayloadValidator.validate_payload(payload)

    def test_too_many_keys_rejected(self):
        """Test payload with too many keys is rejected."""
        payload = {f'key_{i}': i for i in range(PayloadValidator.MAX_DICT_KEYS + 1)}
        with self.assertRaises(ValidationError):
            PayloadValidator.validate_payload(payload)


class AuthorizationTestCase(TransactionTestCase):
    """Test authorization controls."""

    def setUp(self):
        self.customer1 = Customer.objects.create(name="Hospital A")
        self.customer2 = Customer.objects.create(name="Hospital B")

        self.user1 = User.objects.create_user(username='user1', password='pass')
        self.user1.customer = self.customer1
        self.user1.save()

        self.user2 = User.objects.create_user(username='user2', password='pass')
        self.user2.customer = self.customer2
        self.user2.save()

        self.drift_event = DriftEvent.objects.create(
            customer=self.customer1,
            payer='Aetna',
            drift_type='DENIAL_RATE',
            severity='warning',
            baseline_value=0.1,
            current_value=0.25,
            delta_value=0.15
        )

        self.rule = AlertRule.objects.create(
            customer=self.customer1,
            name='Test Rule',
            alert_type='PAYER_DRIFT',
            threshold_value=0.15,
            enabled=True
        )

        self.alert = AlertEvent.objects.create(
            customer=self.customer1,
            alert_rule=self.rule,
            drift_event=self.drift_event,
            status='pending',
            payload={}
        )

    def test_user_can_access_own_customer_alert(self):
        """Test user can access alerts for their customer."""
        try:
            AlertAuthorization.check_alert_access(self.user1, self.alert)
        except PermissionDenied:
            self.fail("User should have access to own customer's alerts")

    def test_user_cannot_access_other_customer_alert(self):
        """Test user cannot access other customer's alerts (IDOR prevention)."""
        with self.assertRaises(PermissionDenied):
            AlertAuthorization.check_alert_access(self.user2, self.alert)

    def test_unauthenticated_user_denied(self):
        """Test unauthenticated user is denied."""
        unauthenticated_user = User()
        with self.assertRaises(PermissionDenied):
            AlertAuthorization.check_alert_access(unauthenticated_user, self.alert)


class SuppressionEngineTestCase(TransactionTestCase):
    """Test intelligent suppression."""

    def setUp(self):
        self.customer = Customer.objects.create(name="Test Hospital")
        self.drift_event = DriftEvent.objects.create(
            customer=self.customer,
            payer='Aetna',
            drift_type='DENIAL_RATE',
            severity='warning',
            baseline_value=0.1,
            current_value=0.25,
            delta_value=0.15
        )
        self.rule = AlertRule.objects.create(
            customer=self.customer,
            name='Test Rule',
            alert_type='PAYER_DRIFT',
            threshold_value=0.15,
            enabled=True
        )
        self.engine = SuppressionEngine()

    def test_first_alert_not_suppressed(self):
        """Test first alert is not suppressed."""
        alert = AlertEvent.objects.create(
            customer=self.customer,
            alert_rule=self.rule,
            drift_event=self.drift_event,
            status='pending',
            payload={
                'product_name': 'DriftWatch',
                'signal_type': 'PAYER_DRIFT',
                'entity_label': 'Aetna',
                'severity': 'warning'
            }
        )

        should_suppress, context = self.engine.should_suppress(alert)
        self.assertFalse(should_suppress)

    def test_duplicate_alert_within_window_suppressed(self):
        """Test duplicate alert within window is suppressed."""
        # Create first alert
        alert1 = AlertEvent.objects.create(
            customer=self.customer,
            alert_rule=self.rule,
            drift_event=self.drift_event,
            triggered_at=timezone.now() - timedelta(hours=1),
            status='sent',
            notification_sent_at=timezone.now() - timedelta(hours=1),
            payload={
                'product_name': 'DriftWatch',
                'signal_type': 'PAYER_DRIFT',
                'entity_label': 'Aetna',
                'severity': 'warning'
            }
        )

        # Create duplicate alert
        alert2 = AlertEvent.objects.create(
            customer=self.customer,
            alert_rule=self.rule,
            status='pending',
            payload={
                'product_name': 'DriftWatch',
                'signal_type': 'PAYER_DRIFT',
                'entity_label': 'Aetna',
                'severity': 'warning'
            }
        )

        should_suppress, context = self.engine.should_suppress(alert2)
        self.assertTrue(should_suppress)
        self.assertEqual(context['reason'], 'standard_deduplication')


class WebhookSecurityTestCase(TestCase):
    """Test webhook security."""

    def setUp(self):
        self.webhook = SecureWebhookDelivery(secret_key='test_secret_123')

    def test_signature_generation(self):
        """Test HMAC signature generation."""
        payload = '{"test": "data"}'
        signature = self.webhook._generate_signature(payload)
        self.assertTrue(signature.startswith('sha256='))
        self.assertEqual(len(signature), 71)  # sha256= + 64 hex chars

    def test_timestamp_validation(self):
        """Test timestamp validation prevents replay attacks."""
        import time
        import json

        payload_dict = {'test': 'data'}
        old_timestamp = int(time.time()) - 400  # 400 seconds ago (outside tolerance)
        nonce = self.webhook._generate_nonce()

        secure_payload = {
            'timestamp': old_timestamp,
            'nonce': nonce,
            'data': payload_dict
        }
        payload_json = json.dumps(secure_payload, sort_keys=True)
        signature = self.webhook._generate_signature(payload_json)

        valid, error = self.webhook.verify_webhook(payload_json, signature, old_timestamp, nonce)
        self.assertFalse(valid)
        self.assertIn('replay attack', error.lower())


class EmailSecurityTestCase(TestCase):
    """Test email security."""

    def test_header_injection_prevention(self):
        """Test email header injection is prevented."""
        subject = "Test\r\nBcc: attacker@evil.com"
        safe_subject = SecureEmailSender._sanitize_subject(subject)
        self.assertNotIn('\r', safe_subject)
        self.assertNotIn('\n', safe_subject)
        self.assertNotIn('Bcc:', safe_subject)

    def test_invalid_email_rejected(self):
        """Test invalid email addresses are rejected."""
        recipients = ['valid@example.com', 'invalid-email', 'another@example.com']
        with self.assertRaises(ValidationError):
            SecureEmailSender._validate_recipients(recipients)

    def test_too_many_recipients_rejected(self):
        """Test too many recipients is rejected."""
        recipients = [f'user{i}@example.com' for i in range(51)]
        with self.assertRaises(ValidationError):
            SecureEmailSender._validate_recipients(recipients)
```

### Integration Tests

**File:** `upstream/alerts/tests/test_integration.py`

```python
"""
Integration tests for end-to-end alert flow.
"""

from django.test import TransactionTestCase
from django.utils import timezone
from datetime import timedelta

from upstream.models import Customer, DriftEvent, ClaimRecord
from upstream.alerts.models import AlertEvent, AlertRule
from upstream.alerts.services import evaluate_drift_event, process_pending_alerts
from upstream.alerts.detectors.underpayment import UnderpaymentDetector
from upstream.alerts.detectors.payment_delay import PaymentDelayDetector


class EndToEndAlertFlowTestCase(TransactionTestCase):
    """Test complete alert workflow."""

    def setUp(self):
        self.customer = Customer.objects.create(name="Integration Test Hospital")

        self.rule = AlertRule.objects.create(
            customer=self.customer,
            name='Payer Drift Detection',
            alert_type='PAYER_DRIFT',
            threshold_value=0.15,
            enabled=True
        )

    def test_complete_alert_workflow(self):
        """Test drift detection -> alert creation -> notification."""

        # Step 1: Create drift event
        drift_event = DriftEvent.objects.create(
            customer=self.customer,
            payer='Aetna',
            cpt_group='99213-99215',
            drift_type='DENIAL_RATE',
            severity='warning',
            baseline_value=0.10,
            current_value=0.28,
            delta_value=0.18,
            detected_date=timezone.now().date()
        )

        # Step 2: Evaluate drift event
        alert_events = evaluate_drift_event(drift_event)

        # Assertions
        self.assertEqual(len(alert_events), 1, "Should create one alert")
        alert = alert_events[0]
        self.assertEqual(alert.status, 'pending')
        self.assertEqual(alert.customer, self.customer)
        self.assertEqual(alert.drift_event, drift_event)
        self.assertEqual(alert.alert_rule, self.rule)

        # Verify payload
        self.assertIn('confidence', alert.payload)
        self.assertIn('payer', alert.payload)
        self.assertEqual(alert.payload['payer'], 'Aetna')

        # Step 3: Process pending alerts
        results = process_pending_alerts()

        # Should attempt to send
        self.assertEqual(results['total'], 1)

        # Reload alert
        alert.refresh_from_db()

        # Should be marked as sent or failed (depending on email config)
        self.assertIn(alert.status, ['sent', 'failed'])


class UnderpaymentDetectorIntegrationTestCase(TransactionTestCase):
    """Test underpayment detector with real data."""

    def setUp(self):
        self.customer = Customer.objects.create(name="Underpayment Test Hospital")
        self.detector = UnderpaymentDetector()

        # Create baseline claims (180-90 days ago)
        baseline_start = timezone.now().date() - timedelta(days=180)
        baseline_end = timezone.now().date() - timedelta(days=90)

        for i in range(30):
            ClaimRecord.objects.create(
                customer=self.customer,
                payer="Blue Cross",
                cpt="99214",
                submitted_date=baseline_start + timedelta(days=i),
                decided_date=baseline_start + timedelta(days=i+20),
                outcome="PAID",
                allowed_amount=150.00,  # Baseline: $150
                claim_total=150.00
            )

        # Create recent claims with underpayment (last 90 days)
        recent_start = timezone.now().date() - timedelta(days=90)

        for i in range(30):
            ClaimRecord.objects.create(
                customer=self.customer,
                payer="Blue Cross",
                cpt="99214",
                submitted_date=recent_start + timedelta(days=i),
                decided_date=recent_start + timedelta(days=i+20),
                outcome="PAID",
                allowed_amount=120.00,  # Current: $120 (20% underpayment!)
                claim_total=150.00
            )

    def test_underpayment_detection(self):
        """Test underpayment is detected."""
        alerts = self.detector.detect_underpayments(self.customer)

        self.assertEqual(len(alerts), 1, "Should detect one underpayment alert")

        alert_data = alerts[0]
        self.assertEqual(alert_data['payer'], "Blue Cross")
        self.assertEqual(alert_data['cpt_code'], "99214")
        self.assertAlmostEqual(alert_data['expected_allowed'], 150.00, delta=1.0)
        self.assertAlmostEqual(alert_data['actual_allowed'], 120.00, delta=1.0)
        self.assertAlmostEqual(alert_data['variance_pct'], 20.0, delta=1.0)
        self.assertEqual(alert_data['claim_count'], 30)

        # Check dollar impact
        expected_impact = (150.00 - 120.00) * 30
        self.assertAlmostEqual(alert_data['monthly_dollar_impact'], expected_impact, delta=10.0)


class PaymentDelayDetectorIntegrationTestCase(TransactionTestCase):
    """Test payment delay detector."""

    def setUp(self):
        self.customer = Customer.objects.create(name="Payment Delay Test Hospital")
        self.detector = PaymentDelayDetector()

        # Create baseline claims (normal payment time: ~25 days)
        baseline_start = timezone.now().date() - timedelta(days=120)
        baseline_end = timezone.now().date() - timedelta(days=30)

        for i in range(25):
            submit_date = baseline_start + timedelta(days=i)
            ClaimRecord.objects.create(
                customer=self.customer,
                payer="Cigna",
                cpt="99213",
                submitted_date=submit_date,
                decided_date=submit_date + timedelta(days=25),  # Normal: 25 days
                outcome="PAID",
                allowed_amount=100.00
            )

        # Create recent claims with delay (payment time: ~45 days)
        recent_start = timezone.now().date() - timedelta(days=25)

        for i in range(20):
            submit_date = recent_start + timedelta(days=i)
            ClaimRecord.objects.create(
                customer=self.customer,
                payer="Cigna",
                cpt="99213",
                submitted_date=submit_date,
                decided_date=submit_date + timedelta(days=45),  # Delayed: 45 days!
                outcome="PAID",
                allowed_amount=100.00
            )

    def test_payment_delay_detection(self):
        """Test payment delay is detected."""
        alerts = self.detector.detect_payment_delays(self.customer)

        self.assertEqual(len(alerts), 1, "Should detect one payment delay alert")

        alert_data = alerts[0]
        self.assertEqual(alert_data['payer'], "Cigna")
        self.assertAlmostEqual(alert_data['baseline_avg_days'], 25, delta=2)
        self.assertAlmostEqual(alert_data['current_avg_days'], 45, delta=2)
        self.assertAlmostEqual(alert_data['delay_delta_days'], 20, delta=3)
        self.assertEqual(alert_data['severity'], 'critical')  # 20 days delay is critical
```

### Load Testing

**File:** `upstream/alerts/tests/test_performance.py`

```python
"""
Performance and load tests.
"""

from django.test import TransactionTestCase
from django.utils import timezone
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from upstream.models import Customer, DriftEvent
from upstream.alerts.models import AlertEvent, AlertRule
from upstream.alerts.services import evaluate_drift_event
from upstream.alerts.processing import AlertProcessingEngine


class PerformanceTestCase(TransactionTestCase):
    """Test performance under load."""

    def setUp(self):
        self.customer = Customer.objects.create(name="Performance Test Hospital")
        self.rule = AlertRule.objects.create(
            customer=self.customer,
            name='Test Rule',
            alert_type='PAYER_DRIFT',
            threshold_value=0.15,
            enabled=True
        )

    def test_concurrent_alert_creation_no_duplicates(self):
        """Test concurrent alert creation doesn't create duplicates."""

        drift_event = DriftEvent.objects.create(
            customer=self.customer,
            payer='Aetna',
            drift_type='DENIAL_RATE',
            severity='warning',
            baseline_value=0.10,
            current_value=0.28,
            delta_value=0.18
        )

        # Try to create alert 10 times concurrently
        def create_alert():
            return evaluate_drift_event(drift_event)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_alert) for _ in range(10)]
            results = [future.result() for future in as_completed(futures)]

        # Count total alert events created
        total_alerts = AlertEvent.objects.filter(
            drift_event=drift_event,
            alert_rule=self.rule
        ).count()

        # Should only create ONE alert despite 10 concurrent attempts
        self.assertEqual(total_alerts, 1, "Should not create duplicate alerts")

    def test_batch_processing_performance(self):
        """Test batch processing performance."""

        # Create 100 pending alerts
        alerts = []
        for i in range(100):
            drift_event = DriftEvent.objects.create(
                customer=self.customer,
                payer=f'Payer_{i}',
                drift_type='DENIAL_RATE',
                severity='warning',
                baseline_value=0.10,
                current_value=0.25,
                delta_value=0.15
            )

            alert = AlertEvent.objects.create(
                customer=self.customer,
                alert_rule=self.rule,
                drift_event=drift_event,
                status='pending',
                payload={}
            )
            alerts.append(alert)

        # Process in batch
        engine = AlertProcessingEngine()

        start_time = time.time()
        results = engine.process_alert_batch(alerts, max_workers=5)
        duration = time.time() - start_time

        # Should process 100 alerts in <30 seconds (throughput > 3/sec)
        self.assertLess(duration, 30, f"Batch processing too slow: {duration}s for 100 alerts")

        print(f"\nProcessed 100 alerts in {duration:.2f}s ({100/duration:.1f} alerts/sec)")
```

---

## Deployment Guide

### Production Checklist

```bash
# 1. Environment Variables
export DJANGO_SECRET_KEY='your-secret-key'
export DATABASE_URL='postgresql://...'
export REDIS_URL='redis://...'
export WEBHOOK_SECRET_KEY='your-webhook-secret'
export DEFAULT_ALERT_EMAIL='alerts@yourcompany.com'
export PORTAL_BASE_URL='https://portal.yourcompany.com'

# 2. Install Dependencies
pip install -r requirements.txt

# 3. Run Migrations
python manage.py migrate

# 4. Collect Static Files
python manage.py collectstatic --noinput

# 5. Create Superuser
python manage.py createsuperuser

# 6. Setup Scheduled Tasks (using Django-Q or Celery)
python manage.py qcluster  # Start task processor

# 7. Setup Monitoring
# - Configure Sentry for error tracking
# - Configure Prometheus metrics endpoint
# - Setup CloudWatch/DataDog alerts

# 8. Run Production Server
gunicorn upstream.wsgi:application --bind 0.0.0.0:8000 --workers 4
```

### Monitoring Dashboard

Create a simple dashboard endpoint:

**File:** `upstream/alerts/views.py` (ADD)

```python
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .metrics import AlertMetrics
from .models import AlertEvent, DeadLetterQueue
from django.utils import timezone
from datetime import timedelta


@login_required
def alert_metrics_dashboard(request):
    """Alert system health dashboard."""

    customer = request.user.customer

    # Get metrics for last 24 hours
    cutoff = timezone.now() - timedelta(hours=24)

    stats = {
        'last_24_hours': {
            'alerts_created': AlertEvent.objects.filter(
                customer=customer,
                triggered_at__gte=cutoff
            ).count(),

            'alerts_sent': AlertEvent.objects.filter(
                customer=customer,
                status='sent',
                notification_sent_at__gte=cutoff
            ).count(),

            'alerts_failed': AlertEvent.objects.filter(
                customer=customer,
                status='failed',
                triggered_at__gte=cutoff
            ).count(),

            'alerts_suppressed': AlertEvent.objects.filter(
                customer=customer,
                status='suppressed',
                triggered_at__gte=cutoff
            ).count(),
        },

        'dlq_status': {
            'pending': DeadLetterQueue.objects.filter(status='pending').count(),
            'retrying': DeadLetterQueue.objects.filter(status='retrying').count(),
            'exhausted': DeadLetterQueue.objects.filter(status='exhausted').count(),
        },

        'by_severity': {
            'emergency': AlertEvent.objects.filter(
                customer=customer,
                triggered_at__gte=cutoff,
                payload__severity='emergency'
            ).count(),
            'critical': AlertEvent.objects.filter(
                customer=customer,
                triggered_at__gte=cutoff,
                payload__severity='critical'
            ).count(),
            'warning': AlertEvent.objects.filter(
                customer=customer,
                triggered_at__gte=cutoff,
                payload__severity='warning'
            ).count(),
        }
    }

    return JsonResponse(stats)
```

---

## Troubleshooting

### Common Issues

**Issue: Duplicate alerts created**
```
Solution: Check that unique constraint migration has been applied
Verify: python manage.py showmigrations alerts
```

**Issue: Alerts not being sent**
```
Check:
1. Dead letter queue: DeadLetterQueue.objects.filter(status='exhausted')
2. Circuit breaker state (may be open due to repeated failures)
3. Email configuration (SMTP settings)
4. Rate limits (may have hit ceiling)
```

**Issue: Performance degradation**
```
Check:
1. Database indexes: python manage.py sqlmigrate alerts 0002
2. Alert volume: AlertMetrics.get_metrics_summary()
3. Slow queries: Enable Django Debug Toolbar
4. Cache hit rate: Redis monitoring
```

**Issue: PII data in logs**
```
Verify: All logging uses safe_logger() from pii_sanitizer
Audit: grep -r "logger.info" --include="*.py" | grep -v "safe_logger"
```

---

**END OF IMPLEMENTATION & TESTING GUIDE**
