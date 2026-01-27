"""
Tests for EHR webhook receiver endpoints.
"""

import json
from unittest.mock import patch
from django.test import TestCase, Client
from django.urls import reverse
from upstream.models import Customer


class EHRWebhookTestCase(TestCase):
    """Test EHR webhook receiver endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.customer = Customer.objects.create(name="TestCustomer")
        self.webhook_url = reverse("ehr_webhook", kwargs={"provider": "epic"})

        self.valid_fhir_payload = {
            "resourceType": "Claim",
            "id": "claim-123",
            "patient": {"reference": "Patient/456"},
            "provider": {"reference": "Organization/789"},
            "billablePeriod": {"start": "2024-01-01", "end": "2024-01-31"},
            "item": [
                {
                    "productOrService": {"coding": [{"code": "97153"}]},
                    "unitPrice": {"value": 150.00},
                }
            ],
            "insurer": {"display": "Blue Cross"},
        }

    def test_webhook_missing_api_key(self):
        """Test webhook rejects requests without API key."""
        response = self.client.post(
            self.webhook_url,
            data=json.dumps(self.valid_fhir_payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)
        data = response.json()
        self.assertIn("Missing X-API-Key header", data["error"])

    def test_webhook_invalid_api_key(self):
        """Test webhook rejects requests with invalid API key."""
        response = self.client.post(
            self.webhook_url,
            data=json.dumps(self.valid_fhir_payload),
            content_type="application/json",
            HTTP_X_API_KEY="invalid-key",  # pragma: allowlist secret
        )
        self.assertEqual(response.status_code, 401)
        data = response.json()
        self.assertIn("Invalid API key", data["error"])

    @patch("upstream.tasks.process_claim_with_automation")
    def test_webhook_valid_request(self, mock_task):
        """Test webhook accepts valid FHIR claim with proper API key."""
        # Mock Celery task
        mock_task.delay.return_value.id = "test-task-id-123"

        response = self.client.post(
            self.webhook_url,
            data=json.dumps(self.valid_fhir_payload),
            content_type="application/json",
            HTTP_X_API_KEY=self.customer.name,
        )
        self.assertEqual(response.status_code, 202)
        data = response.json()
        self.assertEqual(data["status"], "accepted")
        self.assertIn("task_id", data)
        self.assertIn("message", data)

        # Verify Celery task was called
        mock_task.delay.assert_called_once()

    def test_webhook_invalid_json(self):
        """Test webhook rejects malformed JSON."""
        response = self.client.post(
            self.webhook_url,
            data="invalid json {",
            content_type="application/json",
            HTTP_X_API_KEY=self.customer.name,
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        # Middleware catches JSON errors and returns "Invalid JSON"
        self.assertEqual(data["error"], "Invalid JSON")

    def test_webhook_invalid_resource_type(self):
        """Test webhook rejects non-Claim FHIR resources."""
        invalid_payload = {"resourceType": "Patient", "id": "123"}
        response = self.client.post(
            self.webhook_url,
            data=json.dumps(invalid_payload),
            content_type="application/json",
            HTTP_X_API_KEY=self.customer.name,
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["error"], 'Invalid resourceType. Expected "Claim"')

    def test_webhook_get_method_not_allowed(self):
        """Test webhook only accepts POST requests."""
        response = self.client.get(
            self.webhook_url,
            HTTP_X_API_KEY=self.customer.name,
        )
        self.assertEqual(response.status_code, 405)

    @patch("upstream.tasks.process_claim_with_automation")
    def test_webhook_case_insensitive_api_key_header(self, mock_task):
        """Test webhook accepts both X-API-Key and X-Api-Key headers."""
        # Mock Celery task
        mock_task.delay.return_value.id = "test-task-id-123"

        # Test lowercase variant
        response = self.client.post(
            self.webhook_url,
            data=json.dumps(self.valid_fhir_payload),
            content_type="application/json",
            HTTP_X_Api_Key=self.customer.name,
        )
        self.assertEqual(response.status_code, 202)

    def test_webhook_logs_authentication_attempt(self):
        """Test webhook logs authentication failures for security monitoring."""
        # Make invalid request
        with self.assertLogs("upstream.views.webhooks", level="WARNING") as logs:
            self.client.post(
                self.webhook_url,
                data=json.dumps(self.valid_fhir_payload),
                content_type="application/json",
                HTTP_X_API_KEY="invalid-key",  # pragma: allowlist secret
            )

        # Verify log contains security warning
        log_output = "\n".join(logs.output)
        self.assertIn("invalid api key", log_output.lower())
