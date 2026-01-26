# Testing Patterns

**Analysis Date:** 2026-01-26

## Test Framework

**Runner:**
- pytest (configured in `pytest.ini`)
- pytest-django plugin for Django integration
- pytest-cov for coverage reporting

**Assertion Library:**
- Django's TestCase built-in assertions: `assertEqual()`, `assertIn()`, etc.
- Standard Python assert statements for unit tests
- DRF's APITestCase for API testing: `self.assertEqual(response.status_code, 200)`

**Run Commands:**
```bash
pytest upstream                     # Run all tests in upstream app
pytest upstream/tests_api.py        # Run specific test file
pytest -v                           # Run with verbose output
pytest --cov=upstream               # Run with coverage
pytest -k "test_name"               # Run tests matching pattern
pytest --pdb                        # Enter debugger on failures
```

## Test File Organization

**Location:**
- Test files co-located with source: `upstream/alerts/tests_services.py` alongside `upstream/alerts/services.py`
- Top-level test files for integration: `test_monitoring.py`, `test_production_readiness.py` in project root
- Fixture files: `upstream/test_fixtures.py`

**Naming:**
- `test_*.py`: Prefix pattern (preferred)
- `tests_*.py`: Alternative pattern (used for service-specific tests)
- `tests.py`: Single file for smaller modules (e.g., `upstream/tests.py`)

**Structure:**
```
upstream/
├── services/
│   ├── payer_drift.py
│   └── tests_evidence_payload.py      # Tests for evidence_payload.py
├── alerts/
│   ├── services.py
│   └── tests_services.py              # Tests for services.py
├── tests.py                            # Core model and view tests
├── tests_api.py                        # API endpoint tests
├── tests_logging.py                    # Logging utilities tests
└── test_fixtures.py                    # Shared test data factories
```

## Test Structure

**Suite Organization:**
```python
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APITestCase, APIClient
from unittest.mock import patch, MagicMock
from upstream.models import Customer, DriftEvent

class EvaluateDriftEventTests(TestCase):
    """Tests for evaluate_drift_event function."""

    def setUp(self):
        """Create test fixtures and set customer context."""
        self.customer = Customer.objects.create(name="Test Healthcare Corp")
        set_current_customer(self.customer)

    def tearDown(self):
        """Clean up customer context."""
        clear_current_customer()

    def test_evaluate_drift_event_creates_alert(self):
        """Test that drift event evaluation creates alert when rule matches."""
        # Arrange: Set up test data
        rule = AlertRule.objects.create(
            customer=self.customer,
            name="High Denial Rate Alert",
            enabled=True,
            metric="severity",
            threshold_type="gte",
            threshold_value=0.70,
        )

        # Act: Execute function under test
        alert_events = evaluate_drift_event(self.drift_event)

        # Assert: Verify expected outcomes
        self.assertEqual(len(alert_events), 1)
        self.assertEqual(alert_events[0].alert_rule, rule)
```

**Patterns:**
- **Setup/Teardown:** `setUp()` creates test fixtures; `tearDown()` cleans up resources and context
- **Docstrings:** All test methods have clear docstrings explaining what is tested
- **Arrange-Act-Assert:** Tests follow AAA pattern with clear sections
- **Customer Context:** All tests set customer context to ensure tenant isolation works

## Mocking

**Framework:** Python's `unittest.mock` (patch, MagicMock)

**Patterns:**
```python
from unittest.mock import patch, MagicMock

# Mock external service calls
@patch('upstream.services.evidence_payload.build_driftwatch_evidence_payload')
def test_alert_with_mocked_evidence(self, mock_evidence):
    """Test alert processing with mocked evidence building."""
    mock_evidence.return_value = {"signal_type": "test"}

    alert_events = evaluate_drift_event(self.drift_event)

    mock_evidence.assert_called_once()
    self.assertEqual(len(alert_events), 1)

# Mock Django cache
@patch('django.core.cache.cache.get')
@patch('django.core.cache.cache.set')
def test_cache_operations(self, mock_set, mock_get):
    """Test that cache operations are called correctly."""
    mock_get.return_value = None

    result = get_or_set_cache('key', lambda: 'value')

    mock_get.assert_called_with('key')
    mock_set.assert_called_with('key', 'value', 300)
```

**What to Mock:**
- External API calls (email, webhooks, third-party services)
- Database operations in unit tests (use fixtures or factories instead for integration tests)
- Time/timezone dependencies (use `timezone.now()` and mock if needed)
- Celery tasks (use `@patch` to verify they're called without executing)

**What NOT to Mock:**
- Django ORM operations in integration tests (test actual database behavior)
- Model save/delete operations (test full lifecycle)
- Core business logic (test actual calculations and transformations)
- Tenant isolation checks (ensure they work end-to-end)

## Fixtures and Factories

**Test Data:**
Test data is created directly using Django ORM in setUp():

```python
def setUp(self):
    """Create test fixtures for API tests."""
    # Create customers
    self.customer_a = Customer.objects.create(name='Customer A')
    self.customer_b = Customer.objects.create(name='Customer B')

    # Create users for Customer A
    self.user_a = User.objects.create_user(
        username='user_a',
        email='user_a@example.com',
        password='testpass123'
    )
    self.profile_a = UserProfile.objects.create(
        user=self.user_a,
        customer=self.customer_a
    )
```

**Helper Methods:**
Classes define reusable helper methods for common test setup:

```python
class APITestBase(APITestCase):
    def get_tokens_for_user(self, user):
        """Helper to get JWT tokens for a user."""
        response = self.client.post(f'{API_BASE}/auth/token/', {
            'username': user.username,
            'password': 'testpass123'
        })
        return response.data

    def authenticate_as(self, user):
        """Helper to authenticate client as a specific user."""
        tokens = self.get_tokens_for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    def create_upload_for_customer(self, customer):
        """Helper to create an upload for a customer."""
        return Upload.all_objects.create(
            customer=customer,
            filename='test.csv',
            status='success',
            row_count=100
        )
```

**Location:**
- Test fixture helpers defined in test class: `upstream/tests_api.py` has APITestBase with shared helpers
- Shared fixtures: `upstream/test_fixtures.py` (imported into test classes)
- CSV creation helper: `def create_csv_file(self, data, filename="test.csv"):` in `upstream/tests.py`

## Coverage

**Requirements:**
- Minimum coverage threshold: 25% (set in `pytest.ini`: `--cov-fail-under=25`)
- Target: Increment quarterly toward 70%
- Coverage gap noted in TECHNICAL_DEBT.md: "Code Coverage Enforcement"

**View Coverage:**
```bash
pytest --cov=upstream --cov-report=html     # Generate HTML report in htmlcov/
pytest --cov=upstream --cov-report=term-missing  # Show uncovered lines in terminal
```

**Coverage Exclusions (from pytest.ini):**
```
omit =
    */migrations/*          # Database migrations
    */tests/*               # Test files themselves
    */test_*.py             # Test modules
    */__pycache__/*
    */node_modules/*
    */venv/*
    manage.py
    */settings/*.py
    */wsgi.py
    */asgi.py

exclude_lines =
    pragma: no cover        # Explicit pragma
    raise AssertionError
    raise NotImplementedError
    if TYPE_CHECKING:       # Type-checking only code
    @overload
    if settings.DEBUG:      # Development-only code
    if __name__ == .__main__.:
    @abc.abstractmethod     # Abstract methods
    @abstractmethod
```

## Test Types

**Unit Tests:**
- Test individual functions in isolation
- Mock external dependencies
- Fast, focused on business logic
- Example: `test_evaluate_drift_event_creates_alert()` in `upstream/alerts/tests_services.py`

**Integration Tests:**
- Test interaction between components
- Use real database (within test transaction)
- Test full workflow end-to-end
- Example: `test_valid_csv_upload()` in `upstream/tests.py` (creates Upload, ClaimRecord, verifies data)

**API Tests:**
- Inherit from `APITestCase` (DRF's extended TestCase)
- Use APIClient for requests: `self.client.post()`
- Test authentication, permissions, serialization
- Example: `upstream/tests_api.py` tests API endpoints with JWT auth

**E2E Tests:**
- Test full feature workflows with real database
- Currently use pytest with Django TestCase as pseudo-E2E
- Examples: `test_production_readiness.py` (production validation tests)

## Common Patterns

**Async Testing:**
- Async celery tasks are tested by verifying they're called correctly (mocked in unit tests)
- Integration tests wait for task completion using synchronous helpers
- See `upstream/tasks.py` tests that verify task signatures without executing

**Error Testing:**
```python
def test_drift_event_with_invalid_data(self):
    """Test that invalid drift data raises validation error."""
    with self.assertRaises(ValidationError):
        drift_event = DriftEvent(
            customer=self.customer,
            baseline_value=Decimal("-0.10"),  # Invalid: negative rate
        )
        drift_event.full_clean()  # Triggers validation
```

**Database Transaction Testing:**
```python
def test_atomic_operation_rollback(self):
    """Test that failed operations rollback correctly."""
    initial_count = DriftEvent.objects.count()

    with self.assertRaises(Exception):
        with transaction.atomic():
            DriftEvent.objects.create(...)  # First creation
            raise Exception("Simulate failure")  # Should rollback everything

    # Verify rollback occurred
    self.assertEqual(DriftEvent.objects.count(), initial_count)
```

**Tenant Isolation Testing:**
```python
def test_tenant_isolation_prevents_cross_access(self):
    """Test that Customer A cannot see Customer B's data."""
    # Customer A views with their data
    set_current_customer(self.customer_a)
    uploads_a = Upload.objects.all()  # Should only see Customer A uploads

    # Verify Customer B uploads are excluded
    for upload in uploads_a:
        self.assertEqual(upload.customer, self.customer_a)

    # Switch to Customer B
    set_current_customer(self.customer_b)
    uploads_b = Upload.objects.all()  # Should only see Customer B uploads

    # Verify they're different
    self.assertNotEqual(set(uploads_a), set(uploads_b))
```

**Request/Response Testing:**
```python
def test_api_response_structure(self):
    """Test that API response has correct structure and status code."""
    response = self.client.get('/api/v1/drift-events/')

    self.assertEqual(response.status_code, 200)
    self.assertIn('results', response.data)
    self.assertIsInstance(response.data['results'], list)

    if response.data['results']:
        result = response.data['results'][0]
        self.assertIn('id', result)
        self.assertIn('severity', result)
```

## Test Fixtures and Data Setup

**Django Test Database:**
- Each test gets fresh database (within transaction, rolled back after test)
- Use `django.test.TestCase` (with transactions) or `django.test.TransactionTestCase` (without)
- Clear cache between tests: `cache.clear()` in setUp()

**Example (from `upstream/tests_api.py`):**
```python
def setUp(self):
    """Set up test fixtures for API tests."""
    # Clear cache to prevent test pollution
    from django.core.cache import cache
    cache.clear()

    # Create customers
    self.customer_a = Customer.objects.create(name='Customer A')
    self.customer_b = Customer.objects.create(name='Customer B')
```

## Testing Best Practices

1. **Isolation:** Each test should be independent; use setUp/tearDown
2. **Clarity:** Test names describe what is being tested
3. **Speed:** Mock slow operations; only real DB/network when testing integration
4. **Tenant Safety:** Always set customer context in tests to verify isolation
5. **Assertions:** One logical assertion per test (can have multiple assertion statements)
6. **Descriptive Failures:** Use messages in assertions: `self.assertEqual(a, b, "Expected X when Y")`

---

*Testing analysis: 2026-01-26*
