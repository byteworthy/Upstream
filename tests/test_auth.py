"""
Locust Load Tests for Authentication Flows.

Tests user registration, login, token refresh, and token verification
endpoints under load.

Target Performance:
- Login: <500ms p95 response time
- Token refresh: <200ms p95 response time
- Token verify: <100ms p95 response time
- Error rate: <1%

Usage:
    # Run auth flow tests only
    locust -f tests/test_auth.py --host http://localhost:8000

    # Run headless for CI
    locust -f tests/test_auth.py --headless -u 50 -r 5 -t 60s \
        --host http://localhost:8000 --csv=auth_results
"""

import logging
import random
import string
import sys
import time
from pathlib import Path

from locust import between, events, task

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from upstream.tests_performance_base import (  # noqa: E402
    BaseUser,
    config,
)

logger = logging.getLogger(__name__)


def generate_random_username(prefix: str = "loadtest_") -> str:
    """Generate a random username for signup tests."""
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{prefix}{suffix}"


def generate_random_email(domain: str = "loadtest.example.com") -> str:
    """Generate a random email for signup tests."""
    local_part = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
    return f"{local_part}@{domain}"


def generate_random_password(length: int = 12) -> str:
    """Generate a random secure password for signup tests."""
    chars = string.ascii_letters + string.digits + "!@#$%^&*()"
    password = "".join(random.choices(chars, k=length))
    # Ensure at least one of each type
    password = (
        random.choice(string.ascii_uppercase)
        + random.choice(string.ascii_lowercase)
        + random.choice(string.digits)
        + random.choice("!@#$%^&*()")
        + password[4:]
    )
    return password


class AuthenticationLoadUser(BaseUser):
    """
    Load test user for authentication flows.

    Tests login, token refresh, and token verification with
    existing credentials.
    """

    wait_time = between(1, 3)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.access_token = None
        self.refresh_token = None
        self.headers = {}
        # Use config credentials
        self.username = config.default_username
        self.password = config.default_password

    @task(5)
    def login_flow(self):
        """
        Test the login flow: POST to /api/v1/auth/token/

        This is the most common auth operation and should handle
        high concurrent load.
        """
        with self.client.post(
            "/api/v1/auth/token/",
            json={"username": self.username, "password": self.password},
            catch_response=True,
            name="auth/token (login)",
        ) as response:
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get("access")
                self.refresh_token = data.get("refresh")
                self.headers = {"Authorization": f"Bearer {self.access_token}"}
                response.success()
            elif response.status_code == 401:
                # Invalid credentials - expected for load test users
                response.failure("Authentication failed - check test credentials")
            elif response.status_code == 429:
                # Rate limited - expected under heavy load
                response.failure(f"Rate limited: {response.status_code}")
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(3)
    def token_refresh_flow(self):
        """
        Test token refresh: POST to /api/v1/auth/token/refresh/

        Simulates access token refresh before expiry.
        """
        # First ensure we have a refresh token
        if not self.refresh_token:
            self.login_flow()
            if not self.refresh_token:
                return  # Login failed, skip refresh test

        with self.client.post(
            "/api/v1/auth/token/refresh/",
            json={"refresh": self.refresh_token},
            catch_response=True,
            name="auth/token/refresh",
        ) as response:
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get("access")
                self.headers = {"Authorization": f"Bearer {self.access_token}"}
                response.success()
            elif response.status_code == 401:
                # Token expired or invalid - re-login
                self.refresh_token = None
                response.failure("Refresh token invalid")
            elif response.status_code == 429:
                response.failure(f"Rate limited: {response.status_code}")
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(2)
    def token_verify_flow(self):
        """
        Test token verification: POST to /api/v1/auth/token/verify/

        Validates that access tokens are valid.
        """
        # First ensure we have an access token
        if not self.access_token:
            self.login_flow()
            if not self.access_token:
                return  # Login failed, skip verify test

        with self.client.post(
            "/api/v1/auth/token/verify/",
            json={"token": self.access_token},
            catch_response=True,
            name="auth/token/verify",
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 401:
                # Token expired or invalid
                response.failure("Token invalid")
            elif response.status_code == 429:
                response.failure(f"Rate limited: {response.status_code}")
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(1)
    def authenticated_request_after_login(self):
        """
        Test making authenticated requests after login.

        Verifies that the full auth flow works end-to-end.
        """
        # First ensure we have an access token
        if not self.access_token:
            self.login_flow()
            if not self.access_token:
                return

        # Make an authenticated request
        with self.client.get(
            "/api/v1/dashboard/",
            headers=self.headers,
            catch_response=True,
            name="dashboard (post-login)",
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 401:
                # Token may have expired, clear it
                self.access_token = None
                self.refresh_token = None
                response.failure("Auth token rejected")
            else:
                response.failure(f"Unexpected status: {response.status_code}")


class TokenRefreshStressUser(BaseUser):
    """
    Stress test user specifically for token refresh.

    Tests rapid token refresh under high concurrency to ensure
    the refresh endpoint handles load correctly.
    """

    wait_time = between(0.5, 1)  # Faster pacing for stress test

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.access_token = None
        self.refresh_token = None
        self.username = config.default_username
        self.password = config.default_password

    def on_start(self):
        """Authenticate once on start."""
        response = self.client.post(
            "/api/v1/auth/token/",
            json={"username": self.username, "password": self.password},
            catch_response=True,
        )
        if response.status_code == 200:
            data = response.json()
            self.access_token = data.get("access")
            self.refresh_token = data.get("refresh")
            response.success()
        else:
            response.failure(f"Initial auth failed: {response.status_code}")

    @task
    def rapid_token_refresh(self):
        """
        Rapidly refresh tokens to stress the refresh endpoint.
        """
        if not self.refresh_token:
            return

        with self.client.post(
            "/api/v1/auth/token/refresh/",
            json={"refresh": self.refresh_token},
            catch_response=True,
            name="auth/token/refresh (stress)",
        ) as response:
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get("access")
                response.success()
            elif response.status_code == 429:
                # Rate limiting is expected and acceptable under stress
                response.success()  # Don't fail for rate limits in stress test
            else:
                response.failure(f"Unexpected status: {response.status_code}")


class ConcurrentLoginUser(BaseUser):
    """
    Test concurrent login attempts from multiple users.

    Simulates multiple users logging in simultaneously, which is
    common during business hours or after system restarts.
    """

    wait_time = between(2, 5)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Each user instance uses the same credentials (testing concurrent auth)
        self.username = config.default_username
        self.password = config.default_password

    @task
    def concurrent_login(self):
        """
        Perform login with timing measurement.
        """
        start_time = time.time()

        with self.client.post(
            "/api/v1/auth/token/",
            json={"username": self.username, "password": self.password},
            catch_response=True,
            name="auth/token (concurrent)",
        ) as response:
            elapsed_ms = (time.time() - start_time) * 1000

            if response.status_code == 200:
                # Check if response time is acceptable
                if elapsed_ms > config.p95_list_threshold_ms:
                    logger.warning(
                        f"Slow login response: {elapsed_ms:.0f}ms "
                        f"(threshold: {config.p95_list_threshold_ms}ms)"
                    )
                response.success()
            elif response.status_code == 429:
                response.failure("Rate limited during concurrent login")
            else:
                response.failure(f"Login failed: {response.status_code}")


class InvalidAuthUser(BaseUser):
    """
    Test authentication with invalid credentials.

    Ensures the system properly rejects invalid attempts and
    doesn't leak information.
    """

    wait_time = between(2, 4)

    @task(3)
    def invalid_password(self):
        """
        Test login with wrong password.
        """
        with self.client.post(
            "/api/v1/auth/token/",
            json={
                "username": config.default_username,
                "password": "wrong_password_123!",  # pragma: allowlist secret
            },
            catch_response=True,
            name="auth/token (invalid password)",
        ) as response:
            if response.status_code == 401:
                response.success()  # Expected - authentication should fail
            elif response.status_code == 429:
                response.success()  # Rate limiting is acceptable
            else:
                response.failure(
                    f"Expected 401 for invalid password, got {response.status_code}"
                )

    @task(2)
    def invalid_username(self):
        """
        Test login with non-existent username.
        """
        fake_username = generate_random_username("fake_")

        with self.client.post(
            "/api/v1/auth/token/",
            json={
                "username": fake_username,
                "password": "any_password_123!",  # pragma: allowlist secret
            },
            catch_response=True,
            name="auth/token (invalid username)",
        ) as response:
            if response.status_code == 401:
                response.success()  # Expected - authentication should fail
            elif response.status_code == 429:
                response.success()  # Rate limiting is acceptable
            else:
                response.failure(
                    f"Expected 401 for invalid username, got {response.status_code}"
                )

    @task(2)
    def invalid_token_refresh(self):
        """
        Test token refresh with invalid refresh token.
        """
        fake_refresh_token = "invalid.refresh.token"

        with self.client.post(
            "/api/v1/auth/token/refresh/",
            json={"refresh": fake_refresh_token},
            catch_response=True,
            name="auth/token/refresh (invalid)",
        ) as response:
            if response.status_code == 401:
                response.success()  # Expected - invalid token should be rejected
            elif response.status_code == 429:
                response.success()  # Rate limiting is acceptable
            else:
                response.failure(
                    f"Expected 401 for invalid refresh token, "
                    f"got {response.status_code}"
                )

    @task(1)
    def invalid_token_verify(self):
        """
        Test token verification with invalid access token.
        """
        fake_access_token = "invalid.access.token"

        with self.client.post(
            "/api/v1/auth/token/verify/",
            json={"token": fake_access_token},
            catch_response=True,
            name="auth/token/verify (invalid)",
        ) as response:
            if response.status_code == 401:
                response.success()  # Expected - invalid token should be rejected
            elif response.status_code == 429:
                response.success()  # Rate limiting is acceptable
            else:
                response.failure(
                    f"Expected 401 for invalid token verify, got {response.status_code}"
                )


# Event listeners for auth-specific metrics
@events.test_start.add_listener
def on_auth_test_start(environment, **kwargs):
    """Log auth test configuration."""
    logger.info("=" * 60)
    logger.info("Authentication Load Test Starting")
    logger.info(f"Test user: {config.default_username}")
    logger.info(f"Login threshold: {config.p95_list_threshold_ms}ms")
    logger.info(f"Token refresh threshold: {config.p95_detail_threshold_ms}ms")
    logger.info("=" * 60)


@events.test_stop.add_listener
def on_auth_test_stop(environment, **kwargs):
    """Log auth test summary."""
    logger.info("=" * 60)
    logger.info("Authentication Load Test Completed")

    # Log specific endpoint stats if available
    stats = environment.stats
    for name in [
        "auth/token (login)",
        "auth/token/refresh",
        "auth/token/verify",
    ]:
        entry = stats.entries.get((name, "POST"))
        if entry and entry.num_requests > 0:
            logger.info(
                f"{name}: {entry.num_requests} requests, "
                f"avg {entry.avg_response_time:.0f}ms, "
                f"p95 {entry.get_response_time_percentile(0.95):.0f}ms, "
                f"failures {entry.num_failures}"
            )

    logger.info("=" * 60)
