"""
Load tests for Upstream Healthcare using Locust.

Run with:
    locust -f tests/load/locustfile.py --host=http://localhost:8000

For headless mode:
    locust -f tests/load/locustfile.py --host=http://localhost:8000 \
           --users 100 --spawn-rate 10 --run-time 5m --headless
"""

import json
import random
import string
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner


def generate_email():
    """Generate a unique test email."""
    random_str = "".join(random.choices(string.ascii_lowercase, k=8))
    return f"loadtest_{random_str}@test.upstream.com"


def generate_password():
    """Generate a test password meeting requirements."""
    return "LoadTest123!@#"


class SignupFlowUser(HttpUser):
    """
    Simulates users going through the signup flow.

    This tests:
    - Landing page load
    - Pricing page load
    - Account creation
    - Plan selection
    - Checkout initiation
    """

    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks

    def on_start(self):
        """Initialize user state."""
        self.email = generate_email()
        self.password = generate_password()
        self.csrf_token = None

    def _get_csrf_token(self, response):
        """Extract CSRF token from response if present."""
        # Look for csrftoken in cookies
        if "csrftoken" in response.cookies:
            self.csrf_token = response.cookies["csrftoken"]
        return self.csrf_token

    @task(3)
    def view_landing_page(self):
        """Visit the marketing landing page."""
        with self.client.get("/", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Landing page returned {response.status_code}")

    @task(2)
    def view_pricing_page(self):
        """Visit the pricing page."""
        with self.client.get("/pricing/", catch_response=True) as response:
            if response.status_code in [200, 302]:
                response.success()
            else:
                response.failure(f"Pricing page returned {response.status_code}")

    @task(1)
    def signup_flow(self):
        """Complete the full signup flow."""
        # Step 1: Load signup page
        with self.client.get(
            "/signup/", catch_response=True, name="/signup/ [GET]"
        ) as response:
            self._get_csrf_token(response)
            if response.status_code not in [200, 302]:
                response.failure(f"Signup page returned {response.status_code}")
                return

        # Step 2: Submit account creation
        headers = {"X-CSRFToken": self.csrf_token} if self.csrf_token else {}
        account_data = {
            "email": self.email,
            "password": self.password,
            "first_name": "Load",
            "last_name": "Test",
            "organization": "Load Test Org",
        }

        with self.client.post(
            "/api/v1/auth/register/",
            json=account_data,
            headers=headers,
            catch_response=True,
            name="/api/v1/auth/register/",
        ) as response:
            if response.status_code in [200, 201, 400]:  # 400 if email exists
                response.success()
            else:
                response.failure(f"Registration returned {response.status_code}")


class BrowsingUser(HttpUser):
    """
    Simulates users browsing the marketing site.

    Lower intensity tasks for realistic traffic mix.
    """

    wait_time = between(2, 5)

    @task(5)
    def view_landing_page(self):
        """Visit landing page."""
        self.client.get("/")

    @task(3)
    def view_features(self):
        """Visit features page."""
        self.client.get("/features/")

    @task(2)
    def view_pricing(self):
        """Visit pricing page."""
        self.client.get("/pricing/")

    @task(1)
    def view_case_studies(self):
        """Visit case studies."""
        self.client.get("/case-studies/")

    @task(1)
    def view_security(self):
        """Visit security page."""
        self.client.get("/security/")


class APIUser(HttpUser):
    """
    Simulates authenticated API users.

    Tests core API endpoints under load.
    """

    wait_time = between(0.5, 2)

    def on_start(self):
        """Authenticate user."""
        self.token = None
        self._login()

    def _login(self):
        """Obtain auth token."""
        # Use test credentials for load testing
        response = self.client.post(
            "/api/v1/auth/login/",
            json={
                "email": "loadtest@upstream.com",
                "password": "LoadTest123!@#",
            },
        )
        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access_token") or data.get("token")

    @property
    def auth_headers(self):
        """Get authorization headers."""
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}

    @task(5)
    def list_claims(self):
        """List claims endpoint."""
        self.client.get("/api/v1/claims/", headers=self.auth_headers)

    @task(3)
    def get_dashboard(self):
        """Dashboard data endpoint."""
        self.client.get("/api/v1/dashboard/", headers=self.auth_headers)

    @task(2)
    def get_usage(self):
        """Usage statistics endpoint."""
        self.client.get("/api/v1/billing/usage/", headers=self.auth_headers)

    @task(1)
    def check_health(self):
        """Health check endpoint."""
        self.client.get("/health/")


class StripeWebhookUser(HttpUser):
    """
    Simulates Stripe webhook events.

    Tests webhook handling capacity.
    """

    wait_time = between(0.1, 0.5)  # Webhooks come fast

    def on_start(self):
        """Initialize webhook data."""
        self.webhook_secret = "whsec_test_load_testing"

    @task
    def send_webhook(self):
        """Send a simulated webhook event."""
        event_types = [
            "checkout.session.completed",
            "customer.subscription.updated",
            "invoice.payment_succeeded",
        ]

        event_data = {
            "id": f"evt_test_{random.randint(1000000, 9999999)}",
            "type": random.choice(event_types),
            "data": {
                "object": {
                    "id": f"sub_test_{random.randint(1000000, 9999999)}",
                    "customer": f"cus_test_{random.randint(1000000, 9999999)}",
                }
            },
        }

        # Note: In real tests, you'd need proper signature
        headers = {
            "Content-Type": "application/json",
            "Stripe-Signature": "t=1234567890,v1=fake_sig_for_load_testing",
        }

        with self.client.post(
            "/api/v1/billing/webhooks/stripe/",
            data=json.dumps(event_data),
            headers=headers,
            catch_response=True,
        ) as response:
            # Expect 400 (invalid signature) in load testing, that's OK
            if response.status_code in [200, 400]:
                response.success()
            else:
                response.failure(f"Webhook returned {response.status_code}")


# Event handlers for custom metrics
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Log when test starts."""
    print("Load test starting...")
    if isinstance(environment.runner, MasterRunner):
        print("Running in distributed mode")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Log final statistics when test ends."""
    print("\nLoad test completed!")
    print(f"Total requests: {environment.stats.total.num_requests}")
    print(f"Failures: {environment.stats.total.num_failures}")
    if environment.stats.total.num_requests > 0:
        failure_rate = (
            environment.stats.total.num_failures / environment.stats.total.num_requests
        ) * 100
        print(f"Failure rate: {failure_rate:.2f}%")
