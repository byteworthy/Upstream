"""
Custom middleware for Upstream.
"""
from typing import Optional, Union
import uuid
import threading
import time
import logging
import re
from collections import defaultdict
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from django.core.cache import cache
from django.middleware.gzip import GZipMiddleware, compress_string, compress_sequence
from django.utils.cache import patch_vary_headers

logger = logging.getLogger(__name__)

# Regex from Django's GZipMiddleware
re_accepts_gzip = re.compile(r"\bgzip\b")

# Thread-local storage for request_id
_request_id_storage = threading.local()


class ConfigurableGZipMiddleware(GZipMiddleware):
    """
    Configurable GZip compression middleware with optimized min_length setting.

    Django's default GZipMiddleware hardcodes min_length=200 bytes, which is too
    aggressive - compression overhead on small responses (10-20 bytes of headers,
    CPU time) often exceeds the bandwidth savings.

    This middleware uses min_length=500 by default, which provides better balance:
    - Responses < 500 bytes: Skip compression (overhead > savings)
    - Responses > 500 bytes: Compress with gzip (typically 60-80% size reduction)

    Configuration:
        Add to MIDDLEWARE in settings.py:

        MIDDLEWARE = [
            'django.middleware.security.SecurityMiddleware',
            'upstream.middleware.ConfigurableGZipMiddleware',
            # ... rest of middleware ...
        ]

    Parameters:
        min_length (int): Minimum response size in bytes to compress. Default: 500
        compresslevel (int): Gzip compression level (1-9). Default: 6 (balanced)

    Performance notes:
        - compresslevel=6: Balanced speed/compression (Django default)
        - Higher levels (7-9): Better compression, slower CPU
        - Lower levels (1-5): Faster, less compression
    """

    # Class-level attributes that override Django's GZipMiddleware defaults
    min_length = 500  # Override Django's default of 200
    max_random_bytes = 100  # Keep Django's default
    compresslevel = 6  # Keep Django's default

    def __init__(self, get_response=None, min_length=500, compresslevel=6):
        """
        Initialize middleware with configurable compression settings.

        Args:
            get_response: Django middleware callback
            min_length: Minimum response size in bytes to compress (default: 500)
            compresslevel: Gzip compression level 1-9 (default: 6)
        """
        # Set instance attributes for compression configuration
        # Django's GZipMiddleware reads these attributes via getattr
        self.min_length = min_length
        self.compresslevel = compresslevel
        super().__init__(get_response)

    def process_response(self, request, response):
        """
        Override Django's process_response to use configurable min_length.

        Django's GZipMiddleware hardcodes min_length=200 in the process_response
        method, so we need to override it to use our configurable min_length.
        """
        # It's not worth attempting to compress really short responses.
        if not response.streaming and len(response.content) < self.min_length:
            return response

        # Avoid gzipping if we've already got a content-encoding.
        if response.has_header("Content-Encoding"):
            return response

        patch_vary_headers(response, ("Accept-Encoding",))

        ae = request.META.get("HTTP_ACCEPT_ENCODING", "")
        if not re_accepts_gzip.search(ae):
            return response

        if response.streaming:
            if response.is_async:
                # pull to lexical scope to capture fixed reference in case
                # streaming_content is set again later.
                orignal_iterator = response.streaming_content

                async def gzip_wrapper():
                    async for chunk in orignal_iterator:
                        yield compress_string(
                            chunk,
                            max_random_bytes=self.max_random_bytes,
                        )

                response.streaming_content = gzip_wrapper()
            else:
                response.streaming_content = compress_sequence(
                    response.streaming_content,
                    max_random_bytes=self.max_random_bytes,
                )
            # Delete the `Content-Length` header for streaming content, because
            # we won't know the compressed size until we stream it.
            del response.headers["Content-Length"]
        else:
            # Return the compressed content only if it's actually shorter.
            compressed_content = compress_string(
                response.content,
                max_random_bytes=self.max_random_bytes,
            )
            if len(compressed_content) >= len(response.content):
                return response
            response.content = compressed_content
            response.headers["Content-Length"] = str(len(response.content))

        # If there is a strong ETag, make it weak to fulfill the requirements
        # of RFC 9110 Section 8.8.1 while also allowing conditional request
        # matches on ETags.
        etag = response.get("ETag")
        if etag and etag.startswith('"'):
            response.headers["ETag"] = "W/" + etag
        response.headers["Content-Encoding"] = "gzip"

        return response


def get_request_id() -> Optional[str]:
    """Get the current request ID from thread-local storage."""
    return getattr(_request_id_storage, "request_id", None)


def set_request_id(request_id: Optional[str]) -> None:
    """Set the request ID in thread-local storage."""
    _request_id_storage.request_id = request_id


class RequestIdMiddleware(MiddlewareMixin):
    """
    Middleware to add request ID to each request.

    If X-Request-Id header exists, use it. Otherwise, generate a UUID.
    The request_id is attached to request.request_id for access in views.
    """

    def process_request(self, request: HttpRequest) -> None:
        """Add request_id to the request object."""
        request_id = request.META.get("HTTP_X_REQUEST_ID")

        if not request_id:
            request_id = str(uuid.uuid4())

        request.request_id = request_id
        set_request_id(request_id)

        return None

    def process_response(
        self, request: HttpRequest, response: HttpResponse
    ) -> HttpResponse:
        """Add request_id to response headers."""
        request_id = getattr(request, "request_id", None)
        if request_id:
            response["X-Request-Id"] = request_id

        set_request_id(None)

        return response


class SimpleRateLimitMiddleware(MiddlewareMixin):
    """
    Simple rate limiting middleware.

    Tracks requests per IP address in memory.
    Not suitable for distributed systems - use Redis-based solution for production.
    """

    # In-memory storage: {ip: [(timestamp, path), ...]}
    _request_log = defaultdict(list)
    _cleanup_interval = 60  # Clean up old entries every 60 seconds
    _last_cleanup = time.time()

    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """Check rate limits before processing request."""
        # Skip rate limiting for certain paths
        if request.path.startswith("/static/") or request.path.startswith("/admin/"):
            return None

        # Get rate limit settings
        rate_limit_enabled = getattr(settings, "RATE_LIMIT_ENABLED", True)
        if not rate_limit_enabled:
            return None

        max_requests = getattr(settings, "RATE_LIMIT_MAX_REQUESTS", 100)
        window_seconds = getattr(settings, "RATE_LIMIT_WINDOW_SECONDS", 60)

        # Get client IP
        ip_address = self._get_client_ip(request)

        # Clean up old entries periodically
        current_time = time.time()
        if current_time - self._last_cleanup > self._cleanup_interval:
            self._cleanup_old_entries(window_seconds)
            SimpleRateLimitMiddleware._last_cleanup = current_time

        # Get recent requests for this IP
        recent_requests = [
            (ts, path)
            for ts, path in self._request_log[ip_address]
            if current_time - ts < window_seconds
        ]

        # Check if rate limit exceeded
        if len(recent_requests) >= max_requests:
            response = HttpResponse(
                "Rate limit exceeded. Please try again later.", status=429
            )
            response["Retry-After"] = str(window_seconds)
            return response

        # Log this request
        self._request_log[ip_address] = recent_requests + [(current_time, request.path)]

        return None

    def _get_client_ip(self, request: HttpRequest) -> str:
        """Extract client IP from request."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR", "unknown")
        return ip

    def _cleanup_old_entries(self, window_seconds: Union[int, float]) -> None:
        """Remove old entries from request log."""
        current_time = time.time()
        for ip in list(self._request_log.keys()):
            self._request_log[ip] = [
                (ts, path)
                for ts, path in self._request_log[ip]
                if current_time - ts < window_seconds
            ]
            if not self._request_log[ip]:
                del self._request_log[ip]


class ProductEnablementMiddleware(MiddlewareMixin):
    """Attach enabled product slugs to the request for navigation gating."""

    def process_request(self, request: HttpRequest) -> None:
        request.enabled_products = set()

        if not request.user.is_authenticated:
            return None

        if not hasattr(request.user, "profile") or not request.user.profile.customer:
            return None

        from upstream.core.models import ProductConfig

        customer = request.user.profile.customer
        all_configs = ProductConfig.objects.filter(customer=customer)

        if not all_configs.exists():
            request.enabled_products = {"upstream-core"}
            return None

        enabled_configs = all_configs.filter(enabled=True)
        request.enabled_products = {config.product_slug for config in enabled_configs}
        return None


class RequestTimingMiddleware(MiddlewareMixin):
    """
    Middleware to track request timing and log slow requests.

    Logs:
    - All requests with timing information
    - Slow requests (>2 seconds) as warnings
    - Very slow requests (>5 seconds) as errors
    """

    def process_request(self, request: HttpRequest) -> None:
        """Start timer when request begins."""
        request._request_start_time = time.time()
        return None

    def process_response(
        self, request: HttpRequest, response: HttpResponse
    ) -> HttpResponse:
        """Log timing when request completes."""
        if hasattr(request, "_request_start_time"):
            duration = time.time() - request._request_start_time
            duration_ms = duration * 1000

            # Build log message
            method = request.method
            path = request.path
            status = response.status_code
            user = (
                request.user.username
                if hasattr(request, "user") and request.user.is_authenticated
                else "anonymous"
            )

            # Log with appropriate level based on duration
            if duration > 5.0:
                logger.error(
                    f"VERY SLOW REQUEST: {method} {path} - {status} - "
                    f"{duration_ms:.0f}ms - user={user}"
                )
            elif duration > 2.0:
                logger.warning(
                    f"SLOW REQUEST: {method} {path} - {status} - "
                    f"{duration_ms:.0f}ms - user={user}"
                )
            else:
                logger.debug(
                    f"REQUEST: {method} {path} - {status} - "
                    f"{duration_ms:.0f}ms - user={user}"
                )

            # Add timing header to response
            response["X-Request-Duration-Ms"] = f"{duration_ms:.2f}"

            # Store metrics in cache for dashboard (keep last 100 requests)
            try:
                metrics_key = "metrics:recent_requests"
                recent_requests = cache.get(metrics_key, [])

                # Add this request
                recent_requests.append(
                    {
                        "timestamp": time.time(),
                        "method": method,
                        "path": path,
                        "status": status,
                        "duration_ms": duration_ms,
                        "user": user,
                    }
                )

                # Keep only last 100
                recent_requests = recent_requests[-100:]

                # Store back in cache (5 minute TTL)
                cache.set(metrics_key, recent_requests, 300)
            except Exception as e:
                logger.debug(f"Failed to store request metrics: {str(e)}")

        return response


class HealthCheckMiddleware(MiddlewareMixin):
    """
    Middleware to handle health check requests efficiently.

    Returns 200 OK for /health/ and /healthz/ without hitting the database.
    Critical for load balancers and container orchestration.
    """

    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """Return early for health check endpoints."""
        if request.path in ["/health/", "/healthz/", "/ping/"]:
            return JsonResponse(
                {
                    "status": "healthy",
                    "timestamp": time.time(),
                }
            )
        return None


class MetricsCollectionMiddleware(MiddlewareMixin):
    """
    Middleware to collect application metrics for monitoring.

    Tracks:
    - Request counts by endpoint
    - Error rates by endpoint
    - Active users (last 5 minutes)
    """

    def process_response(
        self, request: HttpRequest, response: HttpResponse
    ) -> HttpResponse:
        """Collect metrics on response."""
        try:
            # Increment request counter
            path = self._normalize_path(request.path)
            counter_key = f"metrics:request_count:{path}"

            # Use cache.incr with default if key doesn't exist
            try:
                cache.incr(counter_key, delta=1)
            except ValueError:
                # Key doesn't exist, set it
                cache.set(counter_key, 1, 3600)  # 1 hour TTL

            # Track errors
            if response.status_code >= 400:
                error_key = f"metrics:error_count:{path}"
                try:
                    cache.incr(error_key, delta=1)
                except ValueError:
                    cache.set(error_key, 1, 3600)

            # Track active users (last 5 minutes)
            if hasattr(request, "user") and request.user.is_authenticated:
                active_users_key = "metrics:active_users"
                active_users = cache.get(active_users_key, set())
                active_users.add(request.user.id)
                cache.set(active_users_key, active_users, 300)  # 5 minute TTL

        except Exception as e:
            logger.debug(f"Failed to collect metrics: {str(e)}")

        return response

    def _normalize_path(self, path: str) -> str:
        """
        Normalize path to avoid high cardinality metrics.

        Examples:
        - /uploads/123/details/ -> /uploads/{id}/details/
        - /api/v1/customers/456/ -> /api/v1/customers/{id}/
        """
        import re

        # Replace numeric IDs with {id}
        normalized = re.sub(r"/\d+/", "/{id}/", path)
        return normalized


# =============================================================================
# Structured Logging Middleware
# =============================================================================


class StructuredLoggingMiddleware:
    """
    Middleware that automatically injects request context into logs.

    This middleware extracts information from the HTTP request (user, customer,
    request ID, IP address) and adds it to the logging context. All logs
    generated during the request will automatically include this context.

    Configuration:
        Add to MIDDLEWARE in settings.py:

        MIDDLEWARE = [
            'django.middleware.security.SecurityMiddleware',
            # ... other middleware ...
            'upstream.middleware.StructuredLoggingMiddleware',
            # ... rest of middleware ...
        ]

    Benefits:
        - Automatic context injection (no manual set_log_context calls)
        - Every log message includes customer_id, user_id, request_id
        - Easy filtering and debugging in production
        - Consistent logging across the application
    """

    def __init__(self, get_response):
        """Initialize middleware."""
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Process request and inject logging context."""
        from upstream.logging_utils import (
            extract_request_context,
            set_log_context,
            clear_log_context,
            get_logger,
        )

        logger_local = get_logger(__name__)

        # Clear any existing context
        clear_log_context()

        # Extract and set context from request
        try:
            context = extract_request_context(request)
            set_log_context(**context)

            # Log the incoming request
            logger_local.debug(
                "Request received",
                extra={
                    "method": request.method,
                    "path": request.path,
                },
            )

        except Exception as e:
            # Don't fail the request if context extraction fails
            logger_local.warning(
                "Failed to extract request context", extra={"error": str(e)}
            )

        # Process request
        try:
            response = self.get_response(request)

            # Log the response
            logger_local.debug(
                "Request completed", extra={"status_code": response.status_code}
            )

            return response

        except Exception as e:
            # Log unhandled exceptions
            logger_local.error(
                "Unhandled exception during request",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            raise

        finally:
            # Clean up context after request
            clear_log_context()


class SlowRequestLoggingMiddleware:
    """
    Middleware that logs slow requests for performance monitoring.

    Configuration:
        Add to MIDDLEWARE in settings.py and configure threshold:

        MIDDLEWARE = [
            # ... other middleware ...
            'upstream.middleware.SlowRequestLoggingMiddleware',
            # ... rest of middleware ...
        ]

        SLOW_REQUEST_THRESHOLD_MS = 1000  # Log requests slower than 1 second
    """

    def __init__(self, get_response):
        """Initialize middleware."""
        self.get_response = get_response

        # Get threshold from settings (default 1000ms)
        self.threshold_ms = getattr(settings, "SLOW_REQUEST_THRESHOLD_MS", 1000)

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Measure request duration and log if slow."""
        from upstream.logging_utils import get_logger

        logger_local = get_logger(__name__)

        # Record start time
        start_time = time.time()

        # Process request
        response = self.get_response(request)

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Log if slow
        if duration_ms > self.threshold_ms:
            logger_local.warning(
                "Slow request detected",
                extra={
                    "duration_ms": round(duration_ms, 2),
                    "threshold_ms": self.threshold_ms,
                    "method": request.method,
                    "path": request.path,
                },
            )

        return response


class ApiVersionMiddleware(MiddlewareMixin):
    """
    Middleware to add API version header to all responses for client version
    tracking and future backward compatibility.

    This middleware adds an API-Version header to every HTTP response, allowing
    clients to track which version of the API they're interacting with and enabling
    future backward-compatible changes.

    Configuration:
        Add to MIDDLEWARE in settings.py:

        MIDDLEWARE = [
            # ... other middleware ...
            'upstream.middleware.ApiVersionMiddleware',
            # ... rest of middleware ...
        ]

    To update the version:
        Change the VERSION constant below and update docs/API_VERSIONING.md
    """

    VERSION = "1.0.0"

    def process_response(
        self, request: HttpRequest, response: HttpResponse
    ) -> HttpResponse:
        """Add API-Version header to response."""
        response["API-Version"] = self.VERSION
        return response


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Middleware to add security headers to all HTTP responses.

    This middleware adds industry-standard security headers following OWASP best
    practices to protect against common web vulnerabilities.

    Security headers added:
        - X-Content-Type-Options: nosniff
          Prevents browsers from MIME-sniffing responses, forcing declared content-type.
          Protects against drive-by downloads and content injection attacks.

        - X-XSS-Protection: 1; mode=block
          Enables browser XSS filters in blocking mode (defense-in-depth for
          legacy browsers). Modern browsers use Content-Security-Policy instead,
          but this provides backward compatibility for older browsers.

        - Strict-Transport-Security: max-age=31536000; includeSubDomains
          Enforces HTTPS connections for 1 year, including subdomains.
          Prevents protocol downgrade attacks and cookie hijacking.

    Note: X-Frame-Options is already handled by Django's built-in
    XFrameOptionsMiddleware and X_FRAME_OPTIONS setting.

    Configuration:
        Add to MIDDLEWARE in settings.py after SecurityMiddleware:

        MIDDLEWARE = [
            'django.middleware.security.SecurityMiddleware',
            'upstream.middleware.SecurityHeadersMiddleware',
            # ... rest of middleware ...
        ]
    """

    def process_response(
        self, request: HttpRequest, response: HttpResponse
    ) -> HttpResponse:
        """Add security headers to response."""
        # Prevent MIME type sniffing
        response["X-Content-Type-Options"] = "nosniff"

        # Enable browser XSS filters (defense-in-depth for legacy browsers)
        response["X-XSS-Protection"] = "1; mode=block"

        # Enforce HTTPS for 1 year (31536000 seconds)
        response["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response


class RateLimitHeadersMiddleware(MiddlewareMixin):
    """
    Middleware to add rate limit headers to API responses.

    Extracts throttle state from Django REST Framework throttle classes
    and adds standard X-RateLimit-* headers following industry best practices
    used by GitHub, Twitter, Stripe, and other major APIs.

    Headers added:
        - X-RateLimit-Limit: Maximum requests in current window
        - X-RateLimit-Remaining: Requests remaining in window
        - X-RateLimit-Reset: Unix timestamp when quota resets

    Configuration:
        Add to MIDDLEWARE in settings.py after ApiVersionMiddleware:

        MIDDLEWARE = [
            # ... other middleware ...
            'upstream.middleware.ApiVersionMiddleware',
            'upstream.middleware.RateLimitHeadersMiddleware',
            # ... rest of middleware ...
        ]

    Note: Only adds headers for throttled API endpoints (views with
    throttle_classes). Non-API endpoints are unaffected.
    """

    def process_response(
        self, request: HttpRequest, response: HttpResponse
    ) -> HttpResponse:
        """Extract throttle state and add rate limit headers."""
        # Check if view has throttle instances (set by DRF during check_throttles)
        if not hasattr(request, "throttle_instances"):
            return response

        # Find the most restrictive throttle (lowest remaining quota)
        most_restrictive = None
        min_remaining = float("inf")

        for throttle in request.throttle_instances:
            # Only process SimpleRateThrottle subclasses with state
            if not hasattr(throttle, "num_requests") or not hasattr(
                throttle, "history"
            ):
                continue

            # Skip if no rate configured
            if throttle.num_requests is None:
                continue

            # Calculate remaining requests
            remaining = throttle.num_requests - len(throttle.history)

            # Track most restrictive throttle
            if remaining < min_remaining:
                min_remaining = remaining
                most_restrictive = throttle

        # Add headers if we found a throttle with state
        if most_restrictive:
            response["X-RateLimit-Limit"] = str(most_restrictive.num_requests)
            response["X-RateLimit-Remaining"] = str(max(0, min_remaining))

            # Calculate reset time (now + duration)
            reset_time = int(time.time() + most_restrictive.duration)
            response["X-RateLimit-Reset"] = str(reset_time)

        return response


class RequestValidationMiddleware(MiddlewareMixin):
    """
    Middleware for centralized JSON validation before view layer execution.

    This middleware provides request-level validation to catch malformed payloads
    early in the request processing cycle, before they reach view logic. This:
    - Protects against malformed JSON payloads
    - Provides consistent error responses across all API endpoints
    - Reduces boilerplate validation code in views
    - Prevents JSON parsing errors from crashing view logic

    Validation scope:
        - Validates only POST/PUT/PATCH requests (methods that accept request bodies)
        - Checks Content-Type header is application/json
        - Parses JSON and catches JSONDecodeError
        - Attaches parsed data to request.validated_data for view access

    Error response format:
        {
            "error": "Invalid JSON",
            "detail": "Expecting ',' delimiter: line 1 column 15 (char 14)"
        }

    Configuration:
        Add to MIDDLEWARE in settings.py after ApiVersionMiddleware:

        MIDDLEWARE = [
            # ... other middleware ...
            'upstream.middleware.ApiVersionMiddleware',
            'upstream.middleware.RequestValidationMiddleware',
            'django_prometheus.middleware.PrometheusAfterMiddleware',
        ]

    Note: This middleware validates JSON syntax only. Schema validation
    (required fields, data types, business rules) is still handled by
    DRF serializers in view layer.

    Why process_view instead of process_request:
        process_view runs after URL routing, giving access to view_func and
        view_args. This allows future extension for view-specific validation
        rules. process_request runs before routing, so we can't determine
        which endpoint is being called.
    """

    def process_view(
        self, request: HttpRequest, view_func, view_args, view_kwargs
    ) -> Optional[HttpResponse]:
        """
        Validate JSON payloads before view execution.

        Args:
            request: HttpRequest object
            view_func: View function being called
            view_args: Positional args for view
            view_kwargs: Keyword args for view

        Returns:
            None if validation passes (allows request to continue)
            JsonResponse with 400/415 status if validation fails
        """
        import json

        # Only validate POST/PUT/PATCH requests (methods with request bodies)
        if request.method not in ["POST", "PUT", "PATCH"]:
            return None

        # Skip validation for admin paths (admin has its own validation)
        if request.path.startswith("/admin/"):
            return None

        # Check Content-Type header
        content_type = request.META.get("CONTENT_TYPE", "")
        if not content_type.startswith("application/json"):
            # Non-JSON content type - return 415 Unsupported Media Type
            return JsonResponse(
                {
                    "error": "Unsupported Media Type",
                    "detail": f"Expected 'application/json', got '{content_type}'",
                },
                status=415,
            )

        # Parse JSON body
        try:
            # Read and decode request body
            body = request.body.decode("utf-8")

            # Empty body is valid for some endpoints (let view decide)
            if not body.strip():
                request.validated_data = None
                return None

            # Parse JSON
            data = json.loads(body)

            # Attach parsed data to request for view access
            request.validated_data = data

            return None

        except json.JSONDecodeError as e:
            # Invalid JSON - return 400 Bad Request with detailed error
            return JsonResponse(
                {
                    "error": "Invalid JSON",
                    "detail": str(e),
                },
                status=400,
            )

        except UnicodeDecodeError as e:
            # Body is not valid UTF-8
            return JsonResponse(
                {
                    "error": "Invalid encoding",
                    "detail": f"Request body must be UTF-8 encoded: {str(e)}",
                },
                status=400,
            )
