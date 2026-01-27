"""
Tests for CORS configuration.

Verifies that CORS settings are properly configured to expose custom headers
to JavaScript clients for API versioning, request tracing, and caching.
"""
from django.test import TestCase, override_settings
from django.conf import settings
from django.test.client import Client


class TestCorsConfiguration(TestCase):
    """Test CORS configuration for custom header exposure."""

    def test_cors_expose_headers_configured(self):
        """Verify CORS_EXPOSE_HEADERS is configured in settings."""
        # CORS_EXPOSE_HEADERS should exist
        self.assertTrue(hasattr(settings, "CORS_EXPOSE_HEADERS"))
        self.assertIsInstance(settings.CORS_EXPOSE_HEADERS, list)
        self.assertGreater(len(settings.CORS_EXPOSE_HEADERS), 0)

    def test_api_version_header_exposed(self):
        """
        Verify API-Version header is exposed for client version detection.

        Without this, JavaScript clients cannot read the API-Version header
        via response.headers.get('API-Version') in fetch() calls.
        """
        self.assertIn("API-Version", settings.CORS_EXPOSE_HEADERS)

    def test_request_id_header_exposed(self):
        """
        Verify X-Request-Id header is exposed for distributed tracing.

        This enables frontend apps to correlate client-side errors with
        backend logs using the request ID.
        """
        self.assertIn("X-Request-Id", settings.CORS_EXPOSE_HEADERS)

    def test_request_duration_header_exposed(self):
        """
        Verify X-Request-Duration-Ms header is exposed for performance
        monitoring.

        This allows frontend apps to track backend response times and set up
        client-side alerting for slow requests.
        """
        self.assertIn("X-Request-Duration-Ms", settings.CORS_EXPOSE_HEADERS)

    def test_etag_header_exposed(self):
        """
        Verify ETag header is exposed for conditional request logic.

        Required for clients to implement efficient caching with
        If-None-Match.
        """
        self.assertIn("ETag", settings.CORS_EXPOSE_HEADERS)

    def test_security_headers_not_exposed(self):
        """
        Verify security headers are NOT in CORS_EXPOSE_HEADERS.

        Security headers (X-Content-Type-Options, X-XSS-Protection, etc.) are
        for browser security policy, not application logic. They should not
        be exposed to JavaScript.
        """
        # These should NOT be in CORS_EXPOSE_HEADERS
        self.assertNotIn("X-Content-Type-Options", settings.CORS_EXPOSE_HEADERS)
        self.assertNotIn("X-XSS-Protection", settings.CORS_EXPOSE_HEADERS)
        self.assertNotIn("Strict-Transport-Security", settings.CORS_EXPOSE_HEADERS)

    @override_settings(CORS_ALLOWED_ORIGINS=["http://testclient.example.com"])
    def test_cors_headers_present_in_response(self):
        """
        Integration test: Verify CORS headers are present in actual responses.

        This tests the full CORS middleware integration, not just settings.
        """
        client = Client()
        response = client.get(
            "/api/v1/health/", HTTP_ORIGIN="http://testclient.example.com"
        )

        # CORS middleware should add Access-Control-Expose-Headers
        self.assertIn("Access-Control-Expose-Headers", response)
