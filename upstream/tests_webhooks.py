"""
Comprehensive webhook integration tests.

Tests webhook delivery, retry logic, signature validation, and idempotency
using real HTTP responses via the responses library.
"""
import responses
from django.test import TestCase
from datetime import timedelta

from upstream.models import Customer
from upstream.integrations.models import WebhookEndpoint, WebhookDelivery
from upstream.services.webhook_processor import (
    deliver_webhook,
    create_webhook_delivery,
)
from upstream.integrations.services import generate_signature


class WebhookTestCase(TestCase):
    """Base test case for webhook integration tests."""

    def setUp(self):
        """Set up test fixtures."""
        self.customer = Customer.objects.create(name="Webhook Test Customer")

        self.endpoint = WebhookEndpoint.objects.create(
            customer=self.customer,
            name="Test Webhook Endpoint",
            url="https://webhook.test/receive",
            secret="test_secret_key_for_signing",  # pragma: allowlist secret
            active=True,
            event_types=["drift_detected", "report_completed"],
        )

    def create_webhook_delivery(
        self, event_type="drift_detected", payload=None, status="pending"
    ):
        """Helper to create a WebhookDelivery for testing."""
        if payload is None:
            payload = {
                "event_type": event_type,
                "data": {
                    "payer": "UnitedHealthcare",
                    "severity": 0.8,
                    "drift_type": "DENIAL_RATE",
                },
            }

        return WebhookDelivery.objects.create(
            endpoint=self.endpoint,
            event_type=event_type,
            payload=payload,
            status=status,
        )

    def validate_signature(self, request_headers, payload):
        """Helper to validate HMAC signature from request headers."""
        if "X-Signature" not in request_headers:
            return False

        received_signature = request_headers["X-Signature"]
        expected_signature = generate_signature(payload, self.endpoint.secret)

        return received_signature == expected_signature


class WebhookDeliveryTests(WebhookTestCase):
    """Tests for webhook delivery success scenarios."""

    @responses.activate
    def test_webhook_delivery_success(self):
        """Test that successful webhook delivery marks status as success."""
        # Mock HTTP 200 response
        responses.add(
            responses.POST,
            "https://webhook.test/receive",
            status=200,
            json={"status": "received"},
        )

        # Create delivery
        delivery = self.create_webhook_delivery()

        # Deliver webhook
        success = deliver_webhook(delivery)

        # Verify success
        self.assertTrue(success)

        # Reload from database
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, "success")
        self.assertEqual(delivery.attempts, 1)
        self.assertEqual(delivery.response_code, 200)
        self.assertIsNotNone(delivery.last_attempt_at)

    @responses.activate
    def test_webhook_signature_header(self):
        """Test webhook includes HMAC-SHA256 signature in header."""
        # Mock HTTP 200 response
        responses.add(responses.POST, "https://webhook.test/receive", status=200)

        # Create and deliver webhook
        delivery = self.create_webhook_delivery()
        deliver_webhook(delivery)

        # Verify request was made
        self.assertEqual(len(responses.calls), 1)

        # Inspect request headers
        request = responses.calls[0].request
        self.assertIn("X-Signature", request.headers)

        # Validate signature
        delivery.refresh_from_db()
        is_valid = self.validate_signature(request.headers, delivery.payload)
        self.assertTrue(is_valid, "Webhook signature should be valid")

    @responses.activate
    def test_webhook_payload_structure(self):
        """Test that webhook payload contains required fields and metadata."""
        # Mock HTTP 200 response
        responses.add(responses.POST, "https://webhook.test/receive", status=200)

        # Create and deliver webhook
        delivery = self.create_webhook_delivery()
        deliver_webhook(delivery)

        # Verify request was made
        self.assertEqual(len(responses.calls), 1)

        # Verify Content-Type header
        request = responses.calls[0].request
        self.assertEqual(request.headers["Content-Type"], "application/json")

        # Verify payload structure
        delivery.refresh_from_db()
        self.assertIn("metadata", delivery.payload)
        self.assertIn("request_id", delivery.payload["metadata"])
        self.assertIsNotNone(delivery.payload["metadata"]["request_id"])
        self.assertIn("event_type", delivery.payload)


class WebhookRetryTests(WebhookTestCase):
    """Tests for webhook retry logic and failure handling."""

    @responses.activate
    def test_webhook_retry_on_500(self):
        """Test that HTTP 500 error triggers retry with exponential backoff."""
        # Mock HTTP 500 response
        responses.add(
            responses.POST,
            "https://webhook.test/receive",
            status=500,
            json={"error": "Internal Server Error"},
        )

        # Create delivery
        delivery = self.create_webhook_delivery()

        # Attempt delivery
        success = deliver_webhook(delivery)

        # Verify failure triggers retry
        self.assertFalse(success)

        # Reload from database
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, "retrying")
        self.assertEqual(delivery.attempts, 1)
        self.assertEqual(delivery.response_code, 500)
        self.assertIsNotNone(delivery.next_attempt_at)
        self.assertIn("HTTP 500", delivery.last_error)

        # Verify exponential backoff (first retry should be ~2 minutes)
        expected_retry_time = delivery.last_attempt_at + timedelta(minutes=2)
        time_diff = abs(
            (delivery.next_attempt_at - expected_retry_time).total_seconds()
        )
        self.assertLess(time_diff, 5, "Retry time should follow exponential backoff")

    @responses.activate
    def test_webhook_max_retries_terminal_failure(self):
        """Test that delivery stops after max_attempts and marks as failed."""
        # Mock HTTP 500 response
        responses.add(
            responses.POST,
            "https://webhook.test/receive",
            status=500,
            json={"error": "Server Error"},
        )

        # Create delivery with max_attempts=3
        delivery = self.create_webhook_delivery()
        delivery.max_attempts = 3
        delivery.save()

        # First attempt
        deliver_webhook(delivery)
        delivery.refresh_from_db()
        self.assertEqual(delivery.attempts, 1)
        self.assertEqual(delivery.status, "retrying")

        # Second attempt
        deliver_webhook(delivery)
        delivery.refresh_from_db()
        self.assertEqual(delivery.attempts, 2)
        self.assertEqual(delivery.status, "retrying")

        # Third attempt (should reach max and mark as failed)
        deliver_webhook(delivery)
        delivery.refresh_from_db()
        self.assertEqual(delivery.attempts, 3)
        self.assertEqual(delivery.status, "failed")
        self.assertIsNone(
            delivery.next_attempt_at, "No more retries after max_attempts"
        )

    @responses.activate
    def test_webhook_timeout_triggers_retry(self):
        """Test that request timeout triggers retry logic."""
        # Mock timeout exception
        responses.add(
            responses.POST,
            "https://webhook.test/receive",
            body=responses.ConnectionError("Connection timeout"),
        )

        # Create delivery
        delivery = self.create_webhook_delivery()

        # Attempt delivery
        success = deliver_webhook(delivery)

        # Verify timeout triggers retry
        self.assertFalse(success)

        # Reload from database
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, "retrying")
        self.assertEqual(delivery.attempts, 1)
        self.assertIsNotNone(delivery.next_attempt_at)
        self.assertIn("Error", delivery.last_error)


class WebhookIdempotencyTests(WebhookTestCase):
    """Tests for webhook idempotency and duplicate prevention."""

    @responses.activate
    def test_webhook_idempotency_key(self):
        """Test that webhook includes consistent request_id for idempotency."""
        # Mock HTTP 200 response
        responses.add(responses.POST, "https://webhook.test/receive", status=200)

        # Create delivery
        delivery = self.create_webhook_delivery()

        # Deliver first time
        deliver_webhook(delivery)
        delivery.refresh_from_db()
        first_request_id = delivery.payload["metadata"]["request_id"]

        # Verify request_id is present and consistent
        self.assertIsNotNone(first_request_id)

        # Attempt second delivery (simulating retry)
        responses.add(responses.POST, "https://webhook.test/receive", status=200)

        deliver_webhook(delivery)
        delivery.refresh_from_db()
        second_request_id = delivery.payload["metadata"]["request_id"]

        # Request ID should remain consistent across retries
        self.assertEqual(
            first_request_id,
            second_request_id,
            "Request ID should be consistent for idempotency",
        )

    @responses.activate
    def test_webhook_inactive_endpoint_skips_delivery(self):
        """Test that inactive endpoints do not create webhook deliveries."""
        # Deactivate endpoint
        self.endpoint.active = False
        self.endpoint.save()

        # Attempt to create webhook delivery
        delivery = create_webhook_delivery(
            endpoint=self.endpoint,
            event_type="drift_detected",
            payload={"test": "data"},
        )

        # Should return None for inactive endpoint
        self.assertIsNone(delivery, "Inactive endpoint should not create delivery")

    @responses.activate
    def test_webhook_wrong_event_type_skips_delivery(self):
        """Test that unsubscribed event types do not create deliveries."""
        # Attempt to create webhook for event type not in endpoint.event_types
        delivery = create_webhook_delivery(
            endpoint=self.endpoint,
            event_type="alert_triggered",  # Not in endpoint types
            payload={"test": "data"},
        )

        # Should return None for unsubscribed event type
        self.assertIsNone(
            delivery, "Unsubscribed event type should not create delivery"
        )


class WebhookHeaderTests(WebhookTestCase):
    """Tests for webhook HTTP headers and metadata."""

    @responses.activate
    def test_webhook_includes_event_type_header(self):
        """Test that webhook includes X-Webhook-Event header."""
        # Mock HTTP 200 response
        responses.add(responses.POST, "https://webhook.test/receive", status=200)

        # Create and deliver webhook
        delivery = self.create_webhook_delivery(event_type="report_completed")
        deliver_webhook(delivery)

        # Verify headers
        request = responses.calls[0].request
        self.assertEqual(request.headers["X-Webhook-Event"], "report_completed")

    @responses.activate
    def test_webhook_includes_delivery_id_header(self):
        """Test that webhook includes X-Webhook-Delivery-ID header."""
        # Mock HTTP 200 response
        responses.add(responses.POST, "https://webhook.test/receive", status=200)

        # Create and deliver webhook
        delivery = self.create_webhook_delivery()
        deliver_webhook(delivery)

        # Verify headers
        request = responses.calls[0].request
        self.assertIn("X-Webhook-Delivery-ID", request.headers)
        self.assertEqual(request.headers["X-Webhook-Delivery-ID"], str(delivery.id))
