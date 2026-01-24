# Testing Guide for Upstream

## Table of Contents

1. [Overview](#overview)
2. [Testing with Tenant Isolation](#testing-with-tenant-isolation)
3. [Manager Usage Patterns](#manager-usage-patterns)
4. [Common Testing Patterns](#common-testing-patterns)
5. [Test Organization](#test-organization)
6. [Running Tests](#running-tests)
7. [Common Pitfalls](#common-pitfalls)
8. [Best Practices](#best-practices)

---

## Overview

Upstream uses Django's testing framework with a multi-tenant architecture. All tests must account for tenant isolation to ensure data is properly scoped to customers.

**Key Testing Principle**: Tests should verify both functionality AND tenant isolation.

---

## Testing with Tenant Isolation

### Architecture Overview

Upstream uses a thread-local based tenant isolation system:

```python
# Thread-local storage holds current customer
_thread_locals = threading.local()

# Manager auto-filters queries by current customer
class CustomerScopedManager(models.Manager):
    def get_queryset(self):
        # Returns queryset that auto-filters by current customer
        return CustomerScopedQuerySet(self.model)

# Middleware sets customer from authenticated user
class TenantIsolationMiddleware:
    def __call__(self, request):
        if request.user.is_authenticated:
            set_current_customer(request.user.profile.customer)
```

### The Golden Rule

**When testing tenant-scoped models:**

1. ✅ Use `all_objects` manager for **test data creation**
2. ✅ Wrap service method calls in `customer_context(customer)`
3. ✅ Use `for_customer(customer)` for **explicit queries**
4. ✅ Clear cache in test setUp to prevent pollution

---

## Manager Usage Patterns

### Available Managers

Every tenant-scoped model has **two managers**:

```python
class Upload(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)

    # Default manager - auto-filters by current customer
    objects = CustomerScopedManager()

    # Unfiltered manager - bypasses auto-filtering
    all_objects = models.Manager()
```

### When to Use Each Manager

#### Use `objects` (Default Manager)

Use in **production code** where you want automatic tenant scoping:

```python
# ✅ In views/API endpoints
def list_uploads(request):
    customer = get_user_customer(request.user)
    with customer_context(customer):
        # Automatically filtered to customer
        uploads = Upload.objects.all()
```

```python
# ✅ In services called from views
def get_customer_statistics(customer):
    with customer_context(customer):
        total_uploads = Upload.objects.count()
        total_claims = ClaimRecord.objects.count()
```

#### Use `all_objects` (Unfiltered Manager)

Use when you need **explicit, unfiltered access**:

```python
# ✅ In test data creation
def setUp(self):
    self.customer = Customer.objects.create(name='Test Hospital')
    self.upload = Upload.all_objects.create(
        customer=self.customer,
        filename='test.csv'
    )
```

```python
# ✅ In background tasks (no request context)
@shared_task
def process_upload(upload_id):
    upload = Upload.all_objects.get(id=upload_id)
    customer = upload.customer
    # ... process upload
```

```python
# ✅ In admin operations
class UploadAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        # Admin needs to see all uploads
        return Upload.all_objects.all()
```

```python
# ✅ In update_or_create to avoid double-filtering
judgment, created = OperatorJudgment.all_objects.update_or_create(
    alert_event=alert_event,
    operator=request.user,
    defaults={...}
)
```

#### Use `for_customer(customer)` Method

Use for **explicit customer filtering** when you have the customer object:

```python
# ✅ In services where you pass customer explicitly
def compute_dashboard_data(customer):
    total_uploads = Upload.objects.for_customer(customer).count()
    total_claims = ClaimRecord.objects.for_customer(customer).count()
    return {'uploads': total_uploads, 'claims': total_claims}
```

```python
# ✅ In cross-customer queries (admin/reporting)
def get_all_customer_stats():
    stats = []
    for customer in Customer.objects.all():
        uploads = Upload.objects.for_customer(customer).count()
        stats.append({'customer': customer.name, 'uploads': uploads})
    return stats
```

### Manager Decision Tree

```
Need to query tenant-scoped model?
│
├─ Is this TEST DATA CREATION?
│  └─ Use all_objects.create()
│
├─ Is this a BACKGROUND TASK?
│  └─ Use all_objects.get() or for_customer()
│
├─ Is this ADMIN/CROSS-CUSTOMER?
│  └─ Use for_customer() or all_objects
│
├─ Is this PRODUCTION CODE with user context?
│  └─ Use objects with customer_context()
│
└─ Is this update_or_create?
   └─ Use all_objects to avoid double-filtering
```

---

## Common Testing Patterns

### Pattern 1: Basic Model Test

```python
from django.test import TestCase
from upstream.models import Customer, Upload

class UploadModelTest(TestCase):
    """Test Upload model functionality."""

    def setUp(self):
        """Create test data using all_objects."""
        self.customer = Customer.objects.create(name='Test Hospital')
        self.upload = Upload.all_objects.create(
            customer=self.customer,
            filename='test.csv',
            status='pending'
        )

    def test_upload_creation(self):
        """Test upload is created correctly."""
        self.assertEqual(self.upload.customer, self.customer)
        self.assertEqual(self.upload.filename, 'test.csv')
        self.assertEqual(self.upload.status, 'pending')
```

### Pattern 2: Service Method Test

```python
from django.test import TestCase
from upstream.core.tenant import customer_context
from upstream.models import Customer, DriftEvent, ReportRun
from upstream.services.payer_drift import compute_weekly_payer_drift

class PayerDriftServiceTest(TestCase):
    """Test payer drift computation service."""

    def setUp(self):
        """Create test data."""
        self.customer = Customer.objects.create(name='Test Hospital')
        # Create test claims data...

    def test_compute_drift(self):
        """Test drift computation."""
        # Wrap service call in customer_context
        with customer_context(self.customer):
            report_run = compute_weekly_payer_drift(self.customer)

        # Verify results using all_objects
        drift_events = DriftEvent.all_objects.filter(report_run=report_run)
        self.assertGreater(drift_events.count(), 0)
```

### Pattern 3: API Endpoint Test

```python
from rest_framework.test import APITestCase
from rest_framework import status
from upstream.models import Customer, User, UserProfile, Upload

class UploadAPITest(APITestCase):
    """Test Upload API endpoints."""

    def setUp(self):
        """Set up test fixtures."""
        # Cache is cleared automatically by base class

        # Create test customer
        self.customer = Customer.objects.create(name='Test Hospital')

        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        UserProfile.objects.create(
            user=self.user,
            customer=self.customer
        )

        # Create test data using all_objects
        self.upload = Upload.all_objects.create(
            customer=self.customer,
            filename='test.csv',
            status='success'
        )

    def test_list_uploads(self):
        """Test listing uploads for authenticated user."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/v1/uploads/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['filename'], 'test.csv')
```

### Pattern 4: Multi-Tenant Isolation Test

```python
from django.test import TestCase
from upstream.models import Customer, Upload

class TenantIsolationTest(TestCase):
    """Test that tenant isolation works correctly."""

    def setUp(self):
        """Create data for multiple customers."""
        self.customer_a = Customer.objects.create(name='Hospital A')
        self.customer_b = Customer.objects.create(name='Hospital B')

        # Create uploads for each customer
        Upload.all_objects.create(
            customer=self.customer_a,
            filename='customer_a.csv'
        )
        Upload.all_objects.create(
            customer=self.customer_b,
            filename='customer_b.csv'
        )

    def test_customer_cannot_see_other_customer_data(self):
        """Test customer A cannot see customer B's data."""
        # Query using for_customer
        customer_a_uploads = Upload.objects.for_customer(self.customer_a)

        self.assertEqual(customer_a_uploads.count(), 1)
        self.assertEqual(
            customer_a_uploads.first().filename,
            'customer_a.csv'
        )
```

### Pattern 5: Alert Suppression Test

```python
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from upstream.core.tenant import customer_context
from upstream.models import Customer, AlertEvent, OperatorJudgment
from upstream.alerts.services import _is_suppressed

class AlertSuppressionTest(TestCase):
    """Test alert suppression logic."""

    def setUp(self):
        """Create test data."""
        self.customer = Customer.objects.create(name='Test Hospital')
        self.user = User.objects.create_user(username='operator')
        # Create alert rule, report run, etc. using all_objects...

    def test_noise_judgment_suppression(self):
        """Multiple noise judgments should suppress similar alerts."""
        evidence_payload = {
            'product_name': 'DriftWatch',
            'signal_type': 'DENIAL_RATE',
            'entity_label': 'BCBS',
        }

        # Create two alerts marked as noise
        for days_ago in [10, 20]:
            alert_event = AlertEvent.all_objects.create(
                customer=self.customer,
                alert_rule=self.alert_rule,
                status='sent',
                notification_sent_at=timezone.now() - timedelta(days=days_ago),
                payload=evidence_payload
            )

            OperatorJudgment.all_objects.create(
                customer=self.customer,
                alert_event=alert_event,
                operator=self.user,
                verdict='noise'
            )

        # Test suppression with customer context
        with customer_context(self.customer):
            result = _is_suppressed(self.customer, evidence_payload)
            self.assertTrue(result)
```

---

## Test Organization

### Test File Structure

```
upstream/
├── tests.py                    # Core model tests
├── tests_api.py               # API endpoint tests
├── tests_delivery.py          # Alert delivery tests
├── tests_routing.py           # Alert routing tests
├── tests_suppression.py       # Alert suppression tests
├── tests_operator_memory.py   # Operator feedback tests
├── tests_exports.py           # Export functionality tests
├── tests_integration_security.py  # Cross-tenant security tests
└── products/
    ├── driftwatch/
    │   └── tests.py           # DriftWatch product tests
    └── denialscope/
        └── tests.py           # DenialScope product tests
```

### Test Class Organization

```python
# Group related tests in classes
class UploadModelTest(TestCase):
    """Test Upload model."""
    pass

class UploadAPITest(APITestCase):
    """Test Upload API endpoints."""
    pass

class UploadServiceTest(TestCase):
    """Test Upload service methods."""
    pass
```

### Test Method Naming

Follow this pattern: `test_<what>_<condition>_<expected_result>`

```python
✅ Good:
def test_upload_with_invalid_csv_raises_error(self):
def test_dashboard_shows_customer_data_only(self):
def test_noise_judgment_suppression_requires_two_judgments(self):

❌ Bad:
def test_upload(self):
def test_dashboard(self):
def test_suppression(self):
```

---

## Running Tests

### Run All Tests

```bash
python manage.py test
```

### Run Specific Test File

```bash
python manage.py test upstream.tests_api
```

### Run Specific Test Class

```bash
python manage.py test upstream.tests_api.UploadAPITest
```

### Run Specific Test Method

```bash
python manage.py test upstream.tests_api.UploadAPITest.test_list_uploads
```

### Run with Verbose Output

```bash
python manage.py test -v 2
```

### Keep Test Database

```bash
python manage.py test --keepdb
```

This speeds up test runs by reusing the test database.

### Run Tests in Parallel

```bash
python manage.py test --parallel
```

---

## Common Pitfalls

### ❌ Pitfall 1: Using `objects` for Test Data Creation

**Problem:**
```python
def setUp(self):
    self.customer = Customer.objects.create(name='Test')
    # This will fail! No customer context set
    self.upload = Upload.objects.create(
        customer=self.customer,
        filename='test.csv'
    )
```

**Error:**
```
Upload.DoesNotExist: Upload matching query does not exist.
```

**Solution:**
```python
def setUp(self):
    self.customer = Customer.objects.create(name='Test')
    # Use all_objects for test data creation
    self.upload = Upload.all_objects.create(
        customer=self.customer,
        filename='test.csv'
    )
```

### ❌ Pitfall 2: Forgetting `customer_context` for Service Calls

**Problem:**
```python
def test_compute_drift(self):
    # This will fail! Service needs customer context
    report_run = compute_weekly_payer_drift(self.customer)
```

**Error:**
```
QuerySet returns empty results even though data exists
```

**Solution:**
```python
def test_compute_drift(self):
    # Wrap service call in customer context
    with customer_context(self.customer):
        report_run = compute_weekly_payer_drift(self.customer)
```

### ❌ Pitfall 3: Cache Pollution Between Tests

**Problem:**
```python
def test_dashboard_first(self):
    # Dashboard data gets cached
    response = self.client.get('/api/v1/dashboard/')

def test_dashboard_second(self):
    # This gets stale cached data from first test!
    response = self.client.get('/api/v1/dashboard/')
```

**Solution:**
Cache is now automatically cleared in `APITestBase.setUp()`. No action needed!

### ❌ Pitfall 4: Using `objects.get()` in Background Tasks

**Problem:**
```python
@shared_task
def process_report(report_run_id):
    # This will fail! No request context in background tasks
    report_run = ReportRun.objects.get(id=report_run_id)
```

**Solution:**
```python
@shared_task
def process_report(report_run_id):
    # Use all_objects in background tasks
    report_run = ReportRun.all_objects.get(id=report_run_id)
    customer = report_run.customer
    # Now use customer explicitly
```

### ❌ Pitfall 5: Double-Filtering with `update_or_create`

**Problem:**
```python
# This can cause issues with auto-filtering
judgment, created = OperatorJudgment.objects.update_or_create(
    alert_event=alert_event,
    operator=user,
    defaults={...}
)
```

**Solution:**
```python
# Use all_objects to avoid double-filtering
judgment, created = OperatorJudgment.all_objects.update_or_create(
    alert_event=alert_event,
    operator=user,
    defaults={...}
)
```

---

## Best Practices

### ✅ DO: Use Descriptive Test Names

```python
✅ Good:
def test_upload_csv_with_1000_claims_processes_successfully(self):
def test_denied_claims_above_threshold_create_alert_event(self):
def test_operator_marking_alert_as_noise_suppresses_future_alerts(self):

❌ Bad:
def test_upload(self):
def test_alert(self):
def test_operator(self):
```

### ✅ DO: Test Edge Cases

```python
def test_compute_drift_with_empty_data_returns_no_events(self):
    """Test drift computation with no claims."""
    with customer_context(self.customer):
        report_run = compute_weekly_payer_drift(self.customer)

    events = DriftEvent.all_objects.filter(report_run=report_run)
    self.assertEqual(events.count(), 0)

def test_compute_drift_with_insufficient_volume_skips_analysis(self):
    """Test drift computation skips groups with low volume."""
    # Create only 5 claims (below min_volume=30)
    # ... create claims ...

    with customer_context(self.customer):
        report_run = compute_weekly_payer_drift(
            self.customer,
            min_volume=30
        )

    events = DriftEvent.all_objects.filter(report_run=report_run)
    self.assertEqual(events.count(), 0)
```

### ✅ DO: Test Tenant Isolation

Every feature should have tests verifying tenant isolation:

```python
def test_customer_a_cannot_see_customer_b_uploads(self):
    """Verify uploads are isolated between customers."""
    # Create upload for customer B
    Upload.all_objects.create(
        customer=self.customer_b,
        filename='customer_b.csv'
    )

    # Customer A should not see it
    with customer_context(self.customer_a):
        uploads = Upload.objects.all()
        self.assertEqual(uploads.count(), 0)

def test_api_endpoint_respects_tenant_boundaries(self):
    """Verify API only returns customer's own data."""
    # Create data for both customers
    Upload.all_objects.create(customer=self.customer_a, filename='a.csv')
    Upload.all_objects.create(customer=self.customer_b, filename='b.csv')

    # Authenticate as customer A
    self.client.force_authenticate(user=self.user_a)
    response = self.client.get('/api/v1/uploads/')

    # Should only see customer A's upload
    self.assertEqual(len(response.data), 1)
    self.assertEqual(response.data[0]['filename'], 'a.csv')
```

### ✅ DO: Use Fixtures for Common Data

```python
class BaseTestCase(TestCase):
    """Base class with common test fixtures."""

    def create_test_customer(self, name='Test Hospital'):
        """Create a test customer."""
        return Customer.objects.create(name=name)

    def create_test_user(self, customer, username='testuser'):
        """Create a test user linked to customer."""
        user = User.objects.create_user(
            username=username,
            password='testpass123'
        )
        UserProfile.objects.create(user=user, customer=customer)
        return user

    def create_test_claims(self, customer, payer, count=100):
        """Create test claim records."""
        claims = []
        for i in range(count):
            claim = ClaimRecord.all_objects.create(
                customer=customer,
                payer=payer,
                cpt='99213',
                outcome='PAID' if i % 2 == 0 else 'DENIED',
                submitted_date=timezone.now().date(),
                decided_date=timezone.now().date()
            )
            claims.append(claim)
        return claims
```

### ✅ DO: Add Docstrings

```python
def test_time_based_suppression_within_cooldown_window(self):
    """
    Test that alerts are suppressed within 4-hour cooldown window.

    When an alert is sent for a specific entity/signal combination,
    subsequent alerts for the same combination should be suppressed
    for 4 hours to prevent notification spam.
    """
    # Test implementation...
```

### ❌ DON'T: Test Multiple Things in One Test

```python
❌ Bad:
def test_upload_and_drift_and_alerts(self):
    # Upload CSV
    # Compute drift
    # Check alerts
    # Test routing
    # Test suppression
    pass  # Too much in one test!

✅ Good:
def test_upload_csv_creates_claim_records(self):
    # Just test upload
    pass

def test_compute_drift_creates_drift_events(self):
    # Just test drift computation
    pass

def test_drift_event_triggers_alert(self):
    # Just test alert creation
    pass
```

### ❌ DON'T: Use Sleep in Tests

```python
❌ Bad:
def test_async_task(self):
    trigger_task()
    time.sleep(5)  # Wait for task to complete
    assert_task_completed()

✅ Good:
def test_async_task(self):
    # Use synchronous execution in tests
    with override_settings(CELERY_TASK_ALWAYS_EAGER=True):
        trigger_task()
        assert_task_completed()
```

### ❌ DON'T: Depend on Test Execution Order

```python
❌ Bad:
class BadTest(TestCase):
    def test_01_create_data(self):
        self.data = create_data()

    def test_02_use_data(self):
        use_data(self.data)  # Depends on test_01!

✅ Good:
class GoodTest(TestCase):
    def setUp(self):
        self.data = create_data()

    def test_use_data(self):
        use_data(self.data)  # Independent
```

---

## Test Coverage Goals

Aim for these coverage levels:

- **Models**: 90%+ coverage
- **Services**: 90%+ coverage
- **API Endpoints**: 95%+ coverage
- **Critical Features** (auth, tenant isolation, billing): 100% coverage

Check coverage:

```bash
coverage run --source='.' manage.py test
coverage report
coverage html  # Generate HTML report
```

---

## Continuous Integration

Tests run automatically on every commit via GitHub Actions:

- All tests must pass
- Code coverage must not decrease
- Linting must pass (black, flake8)
- Security checks must pass (bandit, safety)

---

## Getting Help

- **Stuck on tenant isolation?** See [TENANT_ISOLATION.md](TENANT_ISOLATION.md)
- **Questions?** Ask in #engineering Slack channel
- **Bug in tests?** File an issue with the "testing" label

---

## Quick Reference

### Manager Cheat Sheet

| Situation | Use This |
|-----------|----------|
| Test data creation | `all_objects.create()` |
| Service method tests | `customer_context(customer)` |
| API endpoint tests | `force_authenticate()` + request |
| Background tasks | `all_objects.get()` |
| Admin operations | `for_customer()` or `all_objects` |
| update_or_create | `all_objects.update_or_create()` |

### Common Imports

```python
# Testing
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APITestCase
from rest_framework import status

# Tenant isolation
from upstream.core.tenant import customer_context, get_current_customer

# Models
from upstream.models import (
    Customer, User, UserProfile, Upload, ClaimRecord,
    ReportRun, DriftEvent
)

# Alerts
from upstream.alerts.models import AlertRule, AlertEvent, OperatorJudgment

# Utils
from django.utils import timezone
from datetime import timedelta
```

---

**Remember**: When in doubt, use `all_objects` for test setup and `customer_context` for test execution!
