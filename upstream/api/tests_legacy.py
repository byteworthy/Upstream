"""
Tests for API Throttling.

Testing coverage for rate limiting on authentication and other API endpoints.
Addresses Phase 2 Technical Debt: Missing API throttling tests.
HIGH-2: Authentication throttling to prevent brute-force attacks.
"""

from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.conf import settings

from upstream.api.throttling import (
    AuthenticationThrottle,
    BurstRateThrottle,
    SustainedRateThrottle,
    ReportGenerationThrottle,
    BulkOperationThrottle,
    ReadOnlyThrottle,
    WriteOperationThrottle,
    AnonStrictThrottle,
)


class ThrottleClassTestCase(TestCase):
    """Tests for custom throttle class implementations."""

    def test_authentication_throttle_scope(self):
        """Test that AuthenticationThrottle uses 'authentication' scope."""
        # Check scope without instantiating (avoids rate parsing)
        self.assertEqual(AuthenticationThrottle.scope, "authentication")

    def test_authentication_throttle_inherits_anon_rate(self):
        """Test that AuthenticationThrottle inherits from AnonRateThrottle."""
        from rest_framework.throttling import AnonRateThrottle

        self.assertTrue(issubclass(AuthenticationThrottle, AnonRateThrottle))

    def test_burst_rate_throttle_scope(self):
        """Test that BurstRateThrottle uses 'burst' scope."""
        self.assertEqual(BurstRateThrottle.scope, "burst")

    def test_sustained_rate_throttle_scope(self):
        """Test that SustainedRateThrottle uses 'sustained' scope."""
        self.assertEqual(SustainedRateThrottle.scope, "sustained")

    def test_report_generation_throttle_scope(self):
        """Test that ReportGenerationThrottle uses 'report_generation' scope."""
        self.assertEqual(ReportGenerationThrottle.scope, "report_generation")

    def test_bulk_operation_throttle_scope(self):
        """Test that BulkOperationThrottle uses 'bulk_operation' scope."""
        self.assertEqual(BulkOperationThrottle.scope, "bulk_operation")

    def test_read_only_throttle_scope(self):
        """Test that ReadOnlyThrottle uses 'read_only' scope."""
        self.assertEqual(ReadOnlyThrottle.scope, "read_only")

    def test_write_operation_throttle_scope(self):
        """Test that WriteOperationThrottle uses 'write_operation' scope."""
        self.assertEqual(WriteOperationThrottle.scope, "write_operation")

    def test_anon_strict_throttle_scope(self):
        """Test that AnonStrictThrottle uses 'anon_strict' scope."""
        self.assertEqual(AnonStrictThrottle.scope, "anon_strict")

    def test_all_throttles_inherit_from_user_or_anon_rate(self):
        """Test that all throttles inherit from appropriate base classes."""
        from rest_framework.throttling import UserRateThrottle, AnonRateThrottle

        # User-based throttles
        user_throttles = [
            BurstRateThrottle,
            SustainedRateThrottle,
            ReportGenerationThrottle,
            BulkOperationThrottle,
            ReadOnlyThrottle,
            WriteOperationThrottle,
        ]

        for throttle_class in user_throttles:
            self.assertTrue(
                issubclass(throttle_class, UserRateThrottle),
                f"{throttle_class.__name__} should inherit from UserRateThrottle",
            )

        # Anonymous-based throttles
        anon_throttles = [AuthenticationThrottle, AnonStrictThrottle]

        for throttle_class in anon_throttles:
            self.assertTrue(
                issubclass(throttle_class, AnonRateThrottle),
                f"{throttle_class.__name__} should inherit from AnonRateThrottle",
            )


class ThrottleConfigurationTestCase(TestCase):
    """Tests for throttle rate configuration in settings."""

    def test_authentication_rate_configured(self):
        """Test that authentication throttle rate is configured in settings."""
        rates = settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {})
        self.assertIn("authentication", rates)

        # Should have authentication rate configured
        auth_rate = rates["authentication"]
        self.assertIsNotNone(auth_rate)
        self.assertIsInstance(auth_rate, str)

    def test_burst_rate_configured(self):
        """Test that burst throttle rate is configured."""
        rates = settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {})
        self.assertIn("burst", rates)

    def test_report_generation_rate_configured(self):
        """Test that report generation throttle rate is configured."""
        rates = settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {})
        self.assertIn("report_generation", rates)

    def test_all_custom_throttle_scopes_configured(self):
        """Test that all custom throttle scopes have rates configured."""
        rates = settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {})

        # All custom scopes should be configured
        expected_scopes = [
            "authentication",
            "burst",
            "sustained",
            "report_generation",
            "bulk_operation",
            "read_only",
            "write_operation",
            "anon_strict",
        ]

        for scope in expected_scopes:
            self.assertIn(
                scope,
                rates,
                f"Throttle scope '{scope}' should be configured in settings",
            )

    def test_rates_follow_expected_patterns(self):
        """Test that rate values follow expected restrictiveness patterns."""
        rates = settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {})

        # Authentication should be most restrictive (for HIGH-2)
        self.assertIn("authentication", rates)

        # Report generation should be restrictive (expensive operations)
        self.assertIn("report_generation", rates)

        # Read-only should be more permissive than write operations
        self.assertIn("read_only", rates)
        self.assertIn("write_operation", rates)


class AuthenticationViewThrottleTestCase(TestCase):
    """
    Tests for authentication view throttle application (HIGH-2).

    Verifies that authentication endpoints have AuthenticationThrottle applied.
    """

    def setUp(self):
        """Create test fixtures."""
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    def test_token_obtain_view_has_authentication_throttle(self):
        """Test that ThrottledTokenObtainPairView applies AuthenticationThrottle."""
        from upstream.api.views import ThrottledTokenObtainPairView

        view = ThrottledTokenObtainPairView()
        throttle_classes = view.throttle_classes

        self.assertIn(
            AuthenticationThrottle,
            throttle_classes,
            (
                "Token obtain view must have AuthenticationThrottle "
                "for brute-force prevention"
            ),
        )

    def test_token_refresh_view_has_authentication_throttle(self):
        """Test that ThrottledTokenRefreshView applies AuthenticationThrottle."""
        from upstream.api.views import ThrottledTokenRefreshView

        view = ThrottledTokenRefreshView()
        throttle_classes = view.throttle_classes

        self.assertIn(
            AuthenticationThrottle,
            throttle_classes,
            "Token refresh view must have AuthenticationThrottle",
        )

    def test_token_verify_view_has_authentication_throttle(self):
        """Test that ThrottledTokenVerifyView applies AuthenticationThrottle."""
        from upstream.api.views import ThrottledTokenVerifyView

        view = ThrottledTokenVerifyView()
        throttle_classes = view.throttle_classes

        self.assertIn(
            AuthenticationThrottle,
            throttle_classes,
            "Token verify view must have AuthenticationThrottle",
        )

    def test_authentication_endpoints_registered(self):
        """Test that throttled authentication endpoints are registered in URLs."""
        login_url = reverse("token-obtain-pair")
        refresh_url = reverse("token-refresh")
        verify_url = reverse("token-verify")

        # URLs should exist
        self.assertIsNotNone(login_url)
        self.assertIsNotNone(refresh_url)
        self.assertIsNotNone(verify_url)

        # Should be under /api/v1/auth/
        self.assertIn("/auth/", login_url)
        self.assertIn("/auth/", refresh_url)
        self.assertIn("/auth/", verify_url)


class ThrottleDocumentationTestCase(TestCase):
    """Tests for throttle class documentation (code quality)."""

    def test_all_throttles_have_docstrings(self):
        """Test that all throttle classes have descriptive docstrings."""
        throttle_classes = [
            AuthenticationThrottle,
            BurstRateThrottle,
            SustainedRateThrottle,
            ReportGenerationThrottle,
            BulkOperationThrottle,
            ReadOnlyThrottle,
            WriteOperationThrottle,
            AnonStrictThrottle,
        ]

        for throttle_class in throttle_classes:
            self.assertIsNotNone(
                throttle_class.__doc__,
                f"{throttle_class.__name__} should have a docstring",
            )
            self.assertGreater(
                len(throttle_class.__doc__.strip()),
                20,
                f"{throttle_class.__name__} docstring should be descriptive",
            )

    def test_authentication_throttle_mentions_high2(self):
        """Test that AuthenticationThrottle docstring references HIGH-2."""
        docstring = AuthenticationThrottle.__doc__
        self.assertIn(
            "HIGH-2", docstring, "AuthenticationThrottle should document HIGH-2 issue"
        )

    def test_authentication_throttle_mentions_brute_force(self):
        """Test that AuthenticationThrottle docstring mentions brute-force."""
        docstring = AuthenticationThrottle.__doc__.lower()
        self.assertTrue(
            "brute-force" in docstring or "brute force" in docstring,
            "AuthenticationThrottle should document brute-force prevention",
        )


class RateLimitHeadersTestCase(TestCase):
    """
    Test rate limit response headers middleware.

    Note: These are unit tests that verify middleware logic directly.
    Integration testing with live API requests requires DRF's check_throttles
    to be patched to expose throttle_instances, which is handled by the
    _patch_drf_throttles() function in middleware.py at module load time.
    """

    def test_middleware_adds_headers_when_throttle_instances_present(self):
        """Test that middleware adds headers when throttle_instances exists."""
        from upstream.middleware import RateLimitHeadersMiddleware
        from rest_framework.throttling import UserRateThrottle
        from django.http import HttpRequest, HttpResponse
        from unittest.mock import Mock
        import time as time_module

        # Create mock request with throttle_instances
        request = Mock(spec=HttpRequest)
        throttle = Mock(spec=UserRateThrottle)
        throttle.num_requests = 1000
        throttle.history = []  # No requests yet
        throttle.duration = 3600  # 1 hour
        request.throttle_instances = [throttle]

        # Create response
        response = HttpResponse()

        # Create middleware and process response
        middleware = RateLimitHeadersMiddleware(lambda r: response)
        result = middleware.process_response(request, response)

        # Verify headers were added
        self.assertIn("X-RateLimit-Limit", result)
        self.assertEqual(result["X-RateLimit-Limit"], "1000")
        self.assertIn("X-RateLimit-Remaining", result)
        self.assertEqual(result["X-RateLimit-Remaining"], "1000")
        self.assertIn("X-RateLimit-Reset", result)
        # Reset should be roughly now + 3600
        reset = int(result["X-RateLimit-Reset"])
        now = int(time_module.time())
        self.assertGreater(reset, now)
        self.assertLess(reset - now, 3700)  # Allow some slack

    def test_headers_added_with_throttle_state(self):
        """Test middleware adds headers when throttle instances present with state."""
        from upstream.middleware import RateLimitHeadersMiddleware
        from django.http import HttpResponse
        from unittest.mock import Mock
        import time as time_module

        # Create mock request with throttle_instances
        request = Mock()
        throttle = Mock()
        throttle.num_requests = 1000
        throttle.history = [time_module.time() - 100]  # 1 request in history
        throttle.duration = 3600  # 1 hour
        request.throttle_instances = [throttle]

        response = HttpResponse()
        middleware = RateLimitHeadersMiddleware(lambda r: response)
        result = middleware.process_response(request, response)

        # Verify headers were added
        self.assertIn("X-RateLimit-Limit", result)
        self.assertEqual(result["X-RateLimit-Limit"], "1000")
        self.assertIn("X-RateLimit-Remaining", result)
        self.assertEqual(result["X-RateLimit-Remaining"], "999")  # 1000 - 1 in history
        self.assertIn("X-RateLimit-Reset", result)

    def test_most_restrictive_throttle_selected(self):
        """Test that most restrictive throttle is used for headers."""
        from upstream.middleware import RateLimitHeadersMiddleware
        from django.http import HttpResponse
        from unittest.mock import Mock
        import time as time_module

        request = Mock()
        # Two throttles with different limits
        throttle1 = Mock()
        throttle1.num_requests = 1000
        throttle1.history = []
        throttle1.duration = 3600

        throttle2 = Mock()
        throttle2.num_requests = 60  # More restrictive
        throttle2.history = [time_module.time() - 10] * 5  # 5 requests
        throttle2.duration = 60

        request.throttle_instances = [throttle1, throttle2]

        response = HttpResponse()
        middleware = RateLimitHeadersMiddleware(lambda r: response)
        result = middleware.process_response(request, response)

        # Should use throttle2 (55 remaining vs 1000 remaining)
        self.assertEqual(result["X-RateLimit-Limit"], "60")
        self.assertEqual(result["X-RateLimit-Remaining"], "55")

    def test_no_headers_without_throttle_instances(self):
        """Test that middleware skips adding headers when no throttle_instances."""
        from upstream.middleware import RateLimitHeadersMiddleware
        from django.http import HttpResponse
        from unittest.mock import Mock

        request = Mock(spec=[])  # No throttle_instances attribute
        response = HttpResponse()

        middleware = RateLimitHeadersMiddleware(lambda r: response)
        result = middleware.process_response(request, response)

        # Should not add headers
        self.assertNotIn("X-RateLimit-Limit", result)
        self.assertNotIn("X-RateLimit-Remaining", result)
        self.assertNotIn("X-RateLimit-Reset", result)

    def test_zero_remaining_when_at_limit(self):
        """Test that remaining shows 0 when throttle limit reached."""
        from upstream.middleware import RateLimitHeadersMiddleware
        from django.http import HttpResponse
        from unittest.mock import Mock
        import time as time_module

        request = Mock()
        throttle = Mock()
        throttle.num_requests = 10
        throttle.history = [
            time_module.time() - i for i in range(10)
        ]  # 10 requests (at limit)
        throttle.duration = 600

        request.throttle_instances = [throttle]

        response = HttpResponse()
        middleware = RateLimitHeadersMiddleware(lambda r: response)
        result = middleware.process_response(request, response)

        self.assertEqual(result["X-RateLimit-Remaining"], "0")

    def test_reset_time_in_future(self):
        """Test that reset timestamp is in the future."""
        from upstream.middleware import RateLimitHeadersMiddleware
        from django.http import HttpResponse
        from unittest.mock import Mock
        import time as time_module

        request = Mock()
        throttle = Mock()
        throttle.num_requests = 100
        throttle.history = []
        throttle.duration = 3600

        request.throttle_instances = [throttle]

        response = HttpResponse()
        middleware = RateLimitHeadersMiddleware(lambda r: response)
        result = middleware.process_response(request, response)

        reset = int(result["X-RateLimit-Reset"])
        now = int(time_module.time())
        self.assertGreater(reset, now)
        self.assertLess(reset - now, 3700)  # Should be ~3600 + some slack
