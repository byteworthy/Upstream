"""
Tests for custom middleware functionality.

Validates that:
- GZip compression works correctly with min_length=500 setting
- Large responses (> 500 bytes) are compressed
- Small responses (< 500 bytes) are not compressed
- API JSON responses are compressed when large enough
"""

import gzip
import json
from django.test import TestCase, RequestFactory, Client
from django.http import HttpResponse
from upstream.middleware import ConfigurableGZipMiddleware


class GZipCompressionTests(TestCase):
    """Test suite for ConfigurableGZipMiddleware compression behavior."""

    def setUp(self):
        """Set up test client and request factory."""
        self.client = Client()
        self.factory = RequestFactory()

    def test_gzip_compression_large_response(self):
        """Test that large responses (> 500 bytes) are compressed."""
        # Create a response with 1000 bytes of content
        content = "x" * 1000

        def get_response(request):
            return HttpResponse(content, content_type="text/plain")

        # Create middleware and request
        middleware = ConfigurableGZipMiddleware(get_response)
        request = self.factory.get("/test/")
        request.META["HTTP_ACCEPT_ENCODING"] = "gzip"

        # Get response through middleware
        response = middleware(request)

        # Should have Content-Encoding: gzip header
        self.assertEqual(response.get("Content-Encoding"), "gzip")

        # Decompress and verify content
        decompressed = gzip.decompress(response.content)
        self.assertEqual(decompressed.decode("utf-8"), content)

        # Verify compressed content is smaller than original
        self.assertLess(len(response.content), len(content.encode("utf-8")))

    def test_gzip_no_compression_small_response(self):
        """Test that small responses (< 500 bytes) are not compressed."""
        # Create a response with 300 bytes of content (below min_length=500)
        content = "x" * 300

        def get_response(request):
            return HttpResponse(content, content_type="text/plain")

        # Create middleware and request
        middleware = ConfigurableGZipMiddleware(get_response)
        request = self.factory.get("/test/")
        request.META["HTTP_ACCEPT_ENCODING"] = "gzip"

        # Get response through middleware
        response = middleware(request)

        # Should NOT have Content-Encoding: gzip header
        self.assertIsNone(response.get("Content-Encoding"))

        # Content should be unchanged (not compressed)
        self.assertEqual(response.content.decode("utf-8"), content)

    def test_gzip_compression_json_api(self):
        """Test that API JSON responses are compressed when large enough."""
        # Make a real API request to /api/v1/health/
        response = self.client.get(
            "/api/v1/health/", HTTP_ACCEPT_ENCODING="gzip, deflate"
        )

        # Health endpoint returns small JSON, but let's test the mechanism
        # If response is large enough (> 500 bytes), it should be compressed
        if len(response.content) > 500:
            self.assertEqual(response.get("Content-Encoding"), "gzip")

            # Decompress and verify valid JSON
            decompressed = gzip.decompress(response.content)
            data = json.loads(decompressed.decode("utf-8"))

            # Should have expected health check structure
            self.assertIn("status", data)
        else:
            # Small response, should not be compressed
            # This is the expected case for health endpoint
            self.assertIsNone(response.get("Content-Encoding"))

            # Should still be valid JSON
            data = json.loads(response.content.decode("utf-8"))
            self.assertIn("status", data)

    def test_gzip_compression_boundary_500_bytes(self):
        """Test compression behavior at the 500 byte boundary."""
        # Test exactly 499 bytes (should NOT compress)
        content_499 = "x" * 499

        def get_response_499(request):
            return HttpResponse(content_499, content_type="text/plain")

        middleware = ConfigurableGZipMiddleware(get_response_499)
        request = self.factory.get("/test/")
        request.META["HTTP_ACCEPT_ENCODING"] = "gzip"

        response_499 = middleware(request)
        self.assertIsNone(response_499.get("Content-Encoding"))

        # Test exactly 501 bytes (should compress)
        content_501 = "x" * 501

        def get_response_501(request):
            return HttpResponse(content_501, content_type="text/plain")

        middleware = ConfigurableGZipMiddleware(get_response_501)
        request = self.factory.get("/test/")
        request.META["HTTP_ACCEPT_ENCODING"] = "gzip"

        response_501 = middleware(request)
        self.assertEqual(response_501.get("Content-Encoding"), "gzip")

    def test_gzip_compression_without_accept_encoding(self):
        """Test that responses without Accept-Encoding header are not compressed."""
        content = "x" * 1000

        def get_response(request):
            return HttpResponse(content, content_type="text/plain")

        middleware = ConfigurableGZipMiddleware(get_response)
        request = self.factory.get("/test/")
        # No Accept-Encoding header

        response = middleware(request)

        # Should NOT be compressed (client doesn't support it)
        self.assertIsNone(response.get("Content-Encoding"))
        self.assertEqual(response.content.decode("utf-8"), content)

    def test_gzip_compression_json_content_type(self):
        """Test compression works for application/json content type."""
        # Create large JSON response
        data = {"items": [{"id": i, "name": f"Item {i}"} for i in range(100)]}
        content = json.dumps(data)
        self.assertGreater(len(content), 500)  # Ensure it's large enough

        def get_response(request):
            return HttpResponse(content, content_type="application/json")

        middleware = ConfigurableGZipMiddleware(get_response)
        request = self.factory.get("/test/")
        request.META["HTTP_ACCEPT_ENCODING"] = "gzip"

        response = middleware(request)

        # Should be compressed
        self.assertEqual(response.get("Content-Encoding"), "gzip")

        # Verify decompression produces valid JSON
        decompressed = gzip.decompress(response.content)
        decompressed_data = json.loads(decompressed.decode("utf-8"))
        self.assertEqual(decompressed_data, data)
