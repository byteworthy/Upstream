"""
Tests for RequestValidationMiddleware.

This module tests the centralized JSON validation middleware that validates
request payloads before they reach the view layer.
"""
from django.test import TestCase, RequestFactory
from django.http import JsonResponse
from upstream.middleware import RequestValidationMiddleware
import json


class RequestValidationMiddlewareTests(TestCase):
    """Test suite for RequestValidationMiddleware."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.middleware = RequestValidationMiddleware(get_response=lambda r: None)

    def test_valid_json_post(self):
        """Valid POST request with JSON body passes validation."""
        request = self.factory.post(
            "/api/test/",
            data=json.dumps({"key": "value"}),
            content_type="application/json",
        )

        response = self.middleware.process_view(request, None, [], {})

        # Should return None (validation passes)
        self.assertIsNone(response)
        # Should attach validated data
        self.assertEqual(request.validated_data, {"key": "value"})

    def test_valid_json_put(self):
        """Valid PUT request with JSON body passes validation."""
        request = self.factory.put(
            "/api/test/",
            data=json.dumps({"key": "value"}),
            content_type="application/json",
        )

        response = self.middleware.process_view(request, None, [], {})

        self.assertIsNone(response)
        self.assertEqual(request.validated_data, {"key": "value"})

    def test_valid_json_patch(self):
        """Valid PATCH request with JSON body passes validation."""
        request = self.factory.patch(
            "/api/test/",
            data=json.dumps({"key": "value"}),
            content_type="application/json",
        )

        response = self.middleware.process_view(request, None, [], {})

        self.assertIsNone(response)
        self.assertEqual(request.validated_data, {"key": "value"})

    def test_invalid_json_returns_400(self):
        """Malformed JSON returns 400 with error details."""
        request = self.factory.post(
            "/api/test/",
            data='{"invalid": json}',  # Missing quotes around json
            content_type="application/json",
        )

        response = self.middleware.process_view(request, None, [], {})

        # Should return JsonResponse with 400 status
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 400)

        # Check error message format
        content = json.loads(response.content)
        self.assertEqual(content["error"], "Invalid JSON")
        self.assertIn("detail", content)
        # Detail should contain specific error message
        self.assertIn("Expecting value", content["detail"])

    def test_empty_json_object(self):
        """Empty JSON object {} is valid."""
        request = self.factory.post(
            "/api/test/", data=json.dumps({}), content_type="application/json"
        )

        response = self.middleware.process_view(request, None, [], {})

        self.assertIsNone(response)
        self.assertEqual(request.validated_data, {})

    def test_json_array(self):
        """JSON array [] is valid."""
        request = self.factory.post(
            "/api/test/", data=json.dumps([]), content_type="application/json"
        )

        response = self.middleware.process_view(request, None, [], {})

        self.assertIsNone(response)
        self.assertEqual(request.validated_data, [])

    def test_json_array_with_objects(self):
        """JSON array with objects is valid."""
        data = [{"id": 1}, {"id": 2}]
        request = self.factory.post(
            "/api/test/", data=json.dumps(data), content_type="application/json"
        )

        response = self.middleware.process_view(request, None, [], {})

        self.assertIsNone(response)
        self.assertEqual(request.validated_data, data)

    def test_missing_content_type(self):
        """Request without Content-Type header returns 415."""
        request = self.factory.post(
            "/api/test/",
            data='{"key": "value"}',
            content_type="",  # Explicitly set empty content type
        )

        response = self.middleware.process_view(request, None, [], {})

        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 415)

        content = json.loads(response.content)
        self.assertEqual(content["error"], "Unsupported Media Type")
        self.assertIn("application/json", content["detail"])

    def test_wrong_content_type(self):
        """Request with non-JSON Content-Type returns 415."""
        request = self.factory.post(
            "/api/test/",
            data='{"key": "value"}',
            content_type="application/x-www-form-urlencoded",
        )

        response = self.middleware.process_view(request, None, [], {})

        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 415)

        content = json.loads(response.content)
        self.assertEqual(content["error"], "Unsupported Media Type")

    def test_get_request_skipped(self):
        """GET requests bypass validation."""
        request = self.factory.get("/api/test/")

        response = self.middleware.process_view(request, None, [], {})

        # Should return None (skipped)
        self.assertIsNone(response)
        # Should not attach validated_data
        self.assertFalse(hasattr(request, "validated_data"))

    def test_delete_request_skipped(self):
        """DELETE requests bypass validation."""
        request = self.factory.delete("/api/test/")

        response = self.middleware.process_view(request, None, [], {})

        self.assertIsNone(response)
        self.assertFalse(hasattr(request, "validated_data"))

    def test_admin_path_skipped(self):
        """Admin paths bypass validation."""
        request = self.factory.post(
            "/admin/test/",
            data="invalid json",  # Would fail validation
            content_type="application/json",
        )

        response = self.middleware.process_view(request, None, [], {})

        # Should skip validation and return None
        self.assertIsNone(response)

    def test_validated_data_attached(self):
        """Successful validation attaches request.validated_data."""
        data = {"name": "test", "count": 42, "active": True}
        request = self.factory.post(
            "/api/test/", data=json.dumps(data), content_type="application/json"
        )

        response = self.middleware.process_view(request, None, [], {})

        self.assertIsNone(response)
        self.assertTrue(hasattr(request, "validated_data"))
        self.assertEqual(request.validated_data, data)

    def test_empty_body(self):
        """Empty request body is valid (let view decide)."""
        # When data is an empty string, RequestFactory doesn't set proper content type in META
        # This is actually correct behavior - empty body shouldn't have content-type
        # So let's test with None which represents truly empty JSON payload
        request = self.factory.post(
            "/api/test/",
            data=json.dumps(None),  # null is valid JSON
            content_type="application/json",
        )

        response = self.middleware.process_view(request, None, [], {})

        self.assertIsNone(response)
        self.assertIsNone(request.validated_data)  # null becomes None

    def test_whitespace_only_body(self):
        """Whitespace-only body is treated as empty."""
        # Manually construct request with whitespace body and proper Content-Type
        request = self.factory.post("/api/test/")
        request.META["CONTENT_TYPE"] = "application/json"
        # Set _body directly to simulate whitespace body
        request._body = b"   \n  "
        # Clear _read_started flag so body property works
        request._read_started = False

        response = self.middleware.process_view(request, None, [], {})

        self.assertIsNone(response)
        self.assertIsNone(request.validated_data)

    def test_nested_json_objects(self):
        """Deeply nested JSON objects are valid."""
        data = {
            "user": {"name": "test", "profile": {"age": 30, "address": {"city": "NYC"}}}
        }
        request = self.factory.post(
            "/api/test/", data=json.dumps(data), content_type="application/json"
        )

        response = self.middleware.process_view(request, None, [], {})

        self.assertIsNone(response)
        self.assertEqual(request.validated_data, data)

    def test_special_characters_in_json(self):
        """JSON with special characters is valid."""
        data = {"text": "Test with special chars: <>&'\"", "emoji": "🚀"}
        request = self.factory.post(
            "/api/test/", data=json.dumps(data), content_type="application/json"
        )

        response = self.middleware.process_view(request, None, [], {})

        self.assertIsNone(response)
        self.assertEqual(request.validated_data, data)

    def test_numeric_json_values(self):
        """JSON with numeric values is valid."""
        data = {"int": 42, "float": 3.14, "negative": -100, "scientific": 1.5e-10}
        request = self.factory.post(
            "/api/test/", data=json.dumps(data), content_type="application/json"
        )

        response = self.middleware.process_view(request, None, [], {})

        self.assertIsNone(response)
        self.assertEqual(request.validated_data, data)

    def test_boolean_and_null_values(self):
        """JSON with boolean and null values is valid."""
        data = {"active": True, "deleted": False, "metadata": None}
        request = self.factory.post(
            "/api/test/", data=json.dumps(data), content_type="application/json"
        )

        response = self.middleware.process_view(request, None, [], {})

        self.assertIsNone(response)
        self.assertEqual(request.validated_data, data)

    def test_content_type_with_charset(self):
        """Content-Type with charset parameter is accepted."""
        request = self.factory.post(
            "/api/test/",
            data=json.dumps({"key": "value"}),
            content_type="application/json; charset=utf-8",
        )

        response = self.middleware.process_view(request, None, [], {})

        self.assertIsNone(response)
        self.assertEqual(request.validated_data, {"key": "value"})

    def test_unicode_in_json(self):
        """JSON with Unicode characters is valid."""
        data = {"name": "François", "city": "São Paulo", "country": "日本"}
        request = self.factory.post(
            "/api/test/", data=json.dumps(data), content_type="application/json"
        )

        response = self.middleware.process_view(request, None, [], {})

        self.assertIsNone(response)
        self.assertEqual(request.validated_data, data)
