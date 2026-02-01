"""
Locust Load Testing Base Classes and Configuration for Upstream API.

This module provides reusable base classes for Locust load testing:
- Authentication helpers for JWT token management
- Configuration for target environments
- Response validation utilities
- Performance metrics collection

Performance Targets:
- Signup flow: <500ms p95 response time, 50 concurrent users
- API endpoints: <500ms p95 for list, <200ms p95 for detail
- Error rate: <1%

Usage:
    from upstream.tests_performance_base import (
        AuthenticatedUser,
        UnauthenticatedUser,
        LoadTestConfig,
    )

    class MyLoadTest(AuthenticatedUser):
        @task
        def test_endpoint(self):
            self.get_with_auth("/api/v1/endpoint/")
"""

from locust import HttpUser, between, events
import os
import logging
import time
from dataclasses import dataclass
from typing import Optional

# Configure logging for load tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class LoadTestConfig:
    """
    Configuration settings for load testing environments.

    Attributes:
        host: Target host URL (e.g., http://localhost:8000)
        default_username: Default user for authentication
        default_password: Default password for authentication
        admin_username: Admin user for privileged operations
        admin_password: Admin password
        response_timeout: Maximum response time in seconds
        p95_list_threshold_ms: P95 threshold for list endpoints (ms)
        p95_detail_threshold_ms: P95 threshold for detail endpoints (ms)
        max_error_rate: Maximum acceptable error rate (0.01 = 1%)
    """

    host: str = os.environ.get("LOCUST_HOST", "http://localhost:8000")
    default_username: str = os.environ.get("LOCUST_USERNAME", "user_a")
    default_password: str = os.environ.get(
        "LOCUST_PASSWORD", "testpass123"
    )  # pragma: allowlist secret
    admin_username: str = os.environ.get("LOCUST_ADMIN_USERNAME", "admin")
    admin_password: str = os.environ.get(
        "LOCUST_ADMIN_PASSWORD", "adminpass123"
    )  # pragma: allowlist secret
    response_timeout: int = int(os.environ.get("LOCUST_TIMEOUT", "30"))
    p95_list_threshold_ms: int = int(os.environ.get("P95_LIST_THRESHOLD_MS", "500"))
    p95_detail_threshold_ms: int = int(os.environ.get("P95_DETAIL_THRESHOLD_MS", "200"))
    max_error_rate: float = float(os.environ.get("MAX_ERROR_RATE", "0.01"))


# Global config instance
config = LoadTestConfig()


class BaseUser(HttpUser):
    """
    Base user class with common utilities for all load test users.

    Provides:
    - Response validation helpers
    - Performance metrics tracking
    - Error handling utilities
    """

    abstract = True  # Don't run this class directly
    wait_time = between(1, 3)  # Realistic pacing between requests

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.request_count = 0
        self.error_count = 0

    def validate_response(
        self,
        response,
        expected_status: int = 200,
        allow_not_found: bool = False,
    ) -> bool:
        """
        Validate response status code and mark success/failure.

        Args:
            response: Locust response object with catch_response=True
            expected_status: Expected HTTP status code
            allow_not_found: If True, 404 is considered acceptable

        Returns:
            True if response is valid, False otherwise
        """
        self.request_count += 1

        if response.status_code == expected_status:
            response.success()
            return True
        elif allow_not_found and response.status_code == 404:
            response.success()
            return True
        else:
            self.error_count += 1
            response.failure(f"Expected {expected_status}, got {response.status_code}")
            return False

    def get_error_rate(self) -> float:
        """Calculate current error rate."""
        if self.request_count == 0:
            return 0.0
        return self.error_count / self.request_count


class AuthenticatedUser(BaseUser):
    """
    Base class for authenticated load test users.

    Handles JWT token acquisition and provides authenticated request helpers.

    Usage:
        class MyTest(AuthenticatedUser):
            @task
            def test_endpoint(self):
                self.get_with_auth("/api/v1/claims/")
    """

    abstract = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.headers: dict = {}
        self.username: str = config.default_username
        self.password: str = config.default_password
        self._token_expiry: float = 0

    def on_start(self):
        """Authenticate and obtain JWT token before running tasks."""
        self._authenticate()

    def _authenticate(self) -> bool:
        """
        Perform JWT authentication.

        Returns:
            True if authentication succeeded, False otherwise
        """
        response = self.client.post(
            "/api/v1/auth/token/",
            json={"username": self.username, "password": self.password},
            catch_response=True,
        )

        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access")
            self.refresh_token = data.get("refresh")
            self.headers = {"Authorization": f"Bearer {self.token}"}
            # Token typically valid for 5 minutes, refresh at 4
            self._token_expiry = time.time() + 240
            response.success()
            logger.info(f"Authenticated as {self.username}")
            return True
        else:
            self.headers = {}
            response.failure(f"Authentication failed: {response.status_code}")
            logger.warning(f"Authentication failed for {self.username}")
            return False

    def _refresh_token_if_needed(self):
        """Refresh JWT token if expiring soon."""
        if time.time() > self._token_expiry and self.refresh_token:
            response = self.client.post(
                "/api/v1/auth/token/refresh/",
                json={"refresh": self.refresh_token},
                catch_response=True,
            )
            if response.status_code == 200:
                data = response.json()
                self.token = data.get("access")
                self.headers = {"Authorization": f"Bearer {self.token}"}
                self._token_expiry = time.time() + 240
                response.success()
            else:
                # Re-authenticate if refresh fails
                response.failure(f"Token refresh failed: {response.status_code}")
                self._authenticate()

    def get_with_auth(
        self,
        url: str,
        expected_status: int = 200,
        allow_not_found: bool = False,
        name: Optional[str] = None,
        **kwargs,
    ):
        """
        Perform authenticated GET request with validation.

        Args:
            url: Request URL
            expected_status: Expected HTTP status code
            allow_not_found: If True, 404 is acceptable
            name: Optional name for request grouping in stats
            **kwargs: Additional arguments to pass to client.get()

        Returns:
            Response object
        """
        self._refresh_token_if_needed()
        with self.client.get(
            url,
            headers=self.headers,
            catch_response=True,
            name=name,
            **kwargs,
        ) as response:
            self.validate_response(response, expected_status, allow_not_found)
            return response

    def post_with_auth(
        self,
        url: str,
        json_data: dict = None,
        expected_status: int = 201,
        name: Optional[str] = None,
        **kwargs,
    ):
        """
        Perform authenticated POST request with validation.

        Args:
            url: Request URL
            json_data: JSON payload
            expected_status: Expected HTTP status code
            name: Optional name for request grouping in stats
            **kwargs: Additional arguments to pass to client.post()

        Returns:
            Response object
        """
        self._refresh_token_if_needed()
        with self.client.post(
            url,
            json=json_data,
            headers=self.headers,
            catch_response=True,
            name=name,
            **kwargs,
        ) as response:
            self.validate_response(response, expected_status)
            return response

    def patch_with_auth(
        self,
        url: str,
        json_data: dict = None,
        expected_status: int = 200,
        name: Optional[str] = None,
        **kwargs,
    ):
        """
        Perform authenticated PATCH request with validation.

        Args:
            url: Request URL
            json_data: JSON payload
            expected_status: Expected HTTP status code
            name: Optional name for request grouping in stats
            **kwargs: Additional arguments to pass to client.patch()

        Returns:
            Response object
        """
        self._refresh_token_if_needed()
        with self.client.patch(
            url,
            json=json_data,
            headers=self.headers,
            catch_response=True,
            name=name,
            **kwargs,
        ) as response:
            self.validate_response(response, expected_status)
            return response

    def delete_with_auth(
        self,
        url: str,
        expected_status: int = 204,
        name: Optional[str] = None,
        **kwargs,
    ):
        """
        Perform authenticated DELETE request with validation.

        Args:
            url: Request URL
            expected_status: Expected HTTP status code
            name: Optional name for request grouping in stats
            **kwargs: Additional arguments to pass to client.delete()

        Returns:
            Response object
        """
        self._refresh_token_if_needed()
        with self.client.delete(
            url,
            headers=self.headers,
            catch_response=True,
            name=name,
            **kwargs,
        ) as response:
            self.validate_response(response, expected_status)
            return response


class AdminUser(AuthenticatedUser):
    """
    Base class for admin load test users.

    Uses admin credentials for privileged operations.
    """

    abstract = True
    wait_time = between(2, 5)  # Slower pacing for admin operations

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.username = config.admin_username
        self.password = config.admin_password


class UnauthenticatedUser(BaseUser):
    """
    Base class for unauthenticated load test users.

    Tests public endpoints and authentication error handling.
    """

    abstract = True
    wait_time = between(1, 2)

    def validate_auth_required(self, response) -> bool:
        """
        Validate that endpoint properly requires authentication.

        Args:
            response: Locust response object with catch_response=True

        Returns:
            True if endpoint correctly returned 401/403
        """
        if response.status_code in [401, 403]:
            response.success()
            return True
        else:
            response.failure(
                f"Expected 401/403 for unauthenticated request, "
                f"got {response.status_code}"
            )
            return False


# Event hooks for metrics collection
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Log when load test starts."""
    logger.info("=" * 60)
    logger.info("Load test starting")
    logger.info(f"Target host: {environment.host}")
    logger.info(f"P95 list threshold: {config.p95_list_threshold_ms}ms")
    logger.info(f"P95 detail threshold: {config.p95_detail_threshold_ms}ms")
    logger.info(f"Max error rate: {config.max_error_rate * 100}%")
    logger.info("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Log summary when load test stops."""
    logger.info("=" * 60)
    logger.info("Load test completed")
    if environment.stats.total.num_requests > 0:
        fail_ratio = environment.stats.total.fail_ratio
        logger.info(f"Total requests: {environment.stats.total.num_requests}")
        logger.info(f"Failure ratio: {fail_ratio * 100:.2f}%")
        if fail_ratio > config.max_error_rate:
            logger.warning(
                f"ALERT: Error rate {fail_ratio * 100:.2f}% exceeds "
                f"threshold {config.max_error_rate * 100}%"
            )
    logger.info("=" * 60)


@events.request.add_listener
def on_request(
    request_type,
    name,
    response_time,
    response_length,
    response,
    exception,
    **kwargs,
):
    """Track slow requests."""
    threshold = config.p95_list_threshold_ms
    if response_time > threshold:
        logger.debug(
            f"Slow request: {request_type} {name} took {response_time:.0f}ms "
            f"(threshold: {threshold}ms)"
        )


# Utility functions for test assertions
def check_p95_threshold(stats, endpoint_name: str, threshold_ms: int) -> bool:
    """
    Check if P95 response time is below threshold.

    Args:
        stats: Locust stats object
        endpoint_name: Name of the endpoint to check
        threshold_ms: P95 threshold in milliseconds

    Returns:
        True if P95 is below threshold, False otherwise
    """
    entry = stats.entries.get((endpoint_name, "GET")) or stats.entries.get(
        (endpoint_name, "POST")
    )
    if entry and entry.num_requests > 0:
        p95 = entry.get_response_time_percentile(0.95)
        return p95 <= threshold_ms
    return True  # No data, assume pass


def check_error_rate(stats, max_rate: float = None) -> bool:
    """
    Check if error rate is below threshold.

    Args:
        stats: Locust stats object
        max_rate: Maximum error rate (default from config)

    Returns:
        True if error rate is acceptable, False otherwise
    """
    if max_rate is None:
        max_rate = config.max_error_rate
    return stats.total.fail_ratio <= max_rate
