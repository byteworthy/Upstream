# Tenant Isolation Architecture

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Core Components](#core-components)
4. [Implementation Guide](#implementation-guide)
5. [Security Guarantees](#security-guarantees)
6. [Performance Considerations](#performance-considerations)
7. [Troubleshooting](#troubleshooting)
8. [Migration Guide](#migration-guide)

---

## Overview

### What is Tenant Isolation?

Tenant isolation ensures that each customer (tenant) can only access their own data, even though all customers share the same database and application instance.

**Key Benefits:**
- 🔒 **Security**: Customers cannot see each other's data
- 💰 **Cost Efficiency**: Single database, shared infrastructure
- 🚀 **Scalability**: Easy to onboard new customers
- 🛠️ **Maintainability**: Single codebase for all customers

### Architecture Style

Upstream uses **Shared Database, Shared Schema** multi-tenancy:

```
┌──────────────────────────────────────┐
│         Single Database              │
│  ┌────────────────────────────────┐  │
│  │     customers table            │  │
│  │  id │ name                     │  │
│  │  1  │ Hospital A               │  │
│  │  2  │ Hospital B               │  │
│  └────────────────────────────────┘  │
│  ┌────────────────────────────────┐  │
│  │     uploads table              │  │
│  │  id │ customer_id │ filename   │  │
│  │  1  │  1          │ a.csv      │  │ ← Hospital A
│  │  2  │  1          │ b.csv      │  │ ← Hospital A
│  │  3  │  2          │ c.csv      │  │ ← Hospital B
│  └────────────────────────────────┘  │
└──────────────────────────────────────┘
```

**Alternative approaches we DON'T use:**
- ❌ Separate database per tenant (higher cost, harder to maintain)
- ❌ Separate schema per tenant (migration complexity)

---

## Architecture

### Request Flow

```
1. HTTP Request
   ↓
2. TenantIsolationMiddleware
   ├─ Get authenticated user
   ├─ Look up user's customer
   └─ Set customer in thread-local storage
   ↓
3. View/API Endpoint
   ├─ Uses CustomerScopedManager
   └─ Queries auto-filtered by customer
   ↓
4. Response sent
   ↓
5. Middleware clears thread-local storage
```

### Thread-Local Storage

Tenant isolation uses Python's `threading.local()` to store the current customer per request:

```python
# Each thread (request) gets its own storage
_thread_locals = threading.local()

def set_current_customer(customer):
    """Set current customer for this thread/request."""
    _thread_locals.customer = customer

def get_current_customer():
    """Get current customer for this thread/request."""
    return getattr(_thread_locals, 'customer', None)

def clear_current_customer():
    """Clear current customer (end of request)."""
    if hasattr(_thread_locals, 'customer'):
        delattr(_thread_locals, 'customer')
```

**Why thread-local storage?**
- ✅ Automatic scoping per request
- ✅ No need to pass customer everywhere
- ✅ Works with Django's request/response cycle
- ✅ Thread-safe for concurrent requests

---

## Core Components

### 1. CustomerScopedQuerySet

Automatically filters queries by the current customer:

```python
class CustomerScopedQuerySet(models.QuerySet):
    """QuerySet that auto-filters by current customer."""

    def _apply_customer_filter(self):
        """Apply customer filter if not already applied."""
        if hasattr(self, '_auto_filter_applied'):
            return  # Already filtered

        customer = get_current_customer()
        if customer is not None:
            # Add customer filter to query
            self.query.add_q(Q(customer=customer))

        # Mark as filtered to prevent double-filtering
        self._auto_filter_applied = True

    def _fetch_all(self):
        """Apply filter before executing query."""
        self._apply_customer_filter()
        super()._fetch_all()

    def count(self):
        """Apply filter for count() optimization."""
        self._apply_customer_filter()
        return super().count()

    def exists(self):
        """Apply filter for exists() optimization."""
        self._apply_customer_filter()
        return super().exists()
```

### 2. CustomerScopedManager

Provides filtered and unfiltered access:

```python
class CustomerScopedManager(models.Manager):
    """Manager with automatic customer filtering."""

    def get_queryset(self):
        """Return customer-scoped queryset."""
        return CustomerScopedQuerySet(self.model, using=self._db)

    def for_customer(self, customer):
        """
        Explicitly query for a specific customer.
        Bypasses thread-local filtering.
        """
        qs = self.get_queryset()
        qs._auto_filter_applied = True  # Mark as manually filtered
        return qs.filter(customer=customer)

    def unscoped(self):
        """
        Get unfiltered queryset.
        Use with caution - only for admin operations.
        """
        qs = self.get_queryset()
        qs._auto_filter_applied = True  # Skip auto-filtering
        return qs
```

### 3. TenantIsolationMiddleware

Sets customer context for each request:

```python
class TenantIsolationMiddleware:
    """Middleware to set current customer in thread-local storage."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Clear any existing customer context
        clear_current_customer()

        # Set customer if user is authenticated
        if request.user.is_authenticated and not request.user.is_superuser:
            # Regular users: set their customer
            if hasattr(request.user, 'profile') and request.user.profile.customer:
                set_current_customer(request.user.profile.customer)

        # Superusers: don't set customer (cross-tenant access)

        try:
            response = self.get_response(request)
        finally:
            # Always clean up after request
            clear_current_customer()

        return response

    def process_exception(self, request, exception):
        """Ensure customer context is cleared even on exception."""
        clear_current_customer()
        return None
```

### 4. Model Integration

Add tenant isolation to a model:

```python
class Upload(models.Model):
    """File upload model with tenant isolation."""

    # Foreign key to Customer (required for tenant isolation)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='uploads'
    )

    filename = models.CharField(max_length=255)
    status = models.CharField(max_length=20)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    # Default manager with auto-filtering
    objects = CustomerScopedManager()

    # Unfiltered manager for admin/background tasks
    all_objects = models.Manager()

    class Meta:
        db_table = 'upstream_uploads'
        indexes = [
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['customer', 'uploaded_at']),
        ]
```

**Key points:**
- ✅ `customer` foreign key required
- ✅ `objects` = CustomerScopedManager (default, auto-filters)
- ✅ `all_objects` = models.Manager (bypass, unfiltered)
- ✅ Add indexes on customer + other fields

---

## Implementation Guide

### Adding Tenant Isolation to a New Model

**Step 1: Add customer foreign key**

```python
class YourModel(models.Model):
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='your_models'
    )

    # Your other fields...
```

**Step 2: Add managers**

```python
    # Default manager with auto-filtering
    objects = CustomerScopedManager()

    # Unfiltered manager for special cases
    all_objects = models.Manager()
```

**Step 3: Create migration**

```bash
python manage.py makemigrations
python manage.py migrate
```

**Step 4: Add indexes**

```python
    class Meta:
        indexes = [
            # Always index customer + common query fields
            models.Index(fields=['customer', 'created_at']),
            models.Index(fields=['customer', 'status']),
        ]
```

**Step 5: Update views/services**

```python
# Views automatically get customer filtering via middleware
def list_your_models(request):
    # Automatically filtered to request.user's customer
    your_models = YourModel.objects.all()
    return render(request, 'list.html', {'objects': your_models})
```

### Adding Tenant Isolation to Existing Model

**Step 1: Add customer field (nullable first)**

```python
# migration 000X_add_customer_to_yourmodel.py
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('upstream', '000X_previous_migration'),
    ]

    operations = [
        migrations.AddField(
            model_name='yourmodel',
            name='customer',
            field=models.ForeignKey(
                'Customer',
                on_delete=models.CASCADE,
                null=True,  # Allow null initially
                blank=True,
                related_name='your_models'
            ),
        ),
    ]
```

**Step 2: Backfill customer data**

```python
# migration 000X_backfill_customer.py
from django.db import migrations

def backfill_customer(apps, schema_editor):
    """Assign existing records to a customer."""
    YourModel = apps.get_model('upstream', 'YourModel')
    Customer = apps.get_model('upstream', 'Customer')

    # Strategy depends on your data
    # Option 1: All records belong to first customer
    first_customer = Customer.objects.first()
    YourModel.objects.filter(customer__isnull=True).update(
        customer=first_customer
    )

    # Option 2: Determine customer from related data
    for obj in YourModel.objects.filter(customer__isnull=True):
        customer = determine_customer(obj)  # Your logic
        obj.customer = customer
        obj.save()

class Migration(migrations.Migration):
    dependencies = [
        ('upstream', '000X_add_customer_to_yourmodel'),
    ]

    operations = [
        migrations.RunPython(
            backfill_customer,
            reverse_code=migrations.RunPython.noop
        ),
    ]
```

**Step 3: Make customer required**

```python
# migration 000X_make_customer_required.py
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('upstream', '000X_backfill_customer'),
    ]

    operations = [
        migrations.AlterField(
            model_name='yourmodel',
            name='customer',
            field=models.ForeignKey(
                'Customer',
                on_delete=models.CASCADE,
                null=False,  # Now required
                blank=False,
                related_name='your_models'
            ),
        ),
    ]
```

**Step 4: Add managers and indexes**

Follow steps 2-4 from "Adding Tenant Isolation to a New Model" above.

---

## Security Guarantees

### What Tenant Isolation Protects

✅ **Cross-tenant data access via ORM**
```python
# Even if malicious user tries to access other customer's data
Upload.objects.filter(customer_id=999)  # Returns empty (auto-filtered)
```

✅ **Cross-tenant data access via API**
```python
# API endpoints respect tenant boundaries
GET /api/v1/uploads/  # Only returns current user's customer uploads
```

✅ **Cross-tenant updates/deletes**
```python
# Cannot update/delete other customer's data
Upload.objects.filter(id=other_customer_upload_id).delete()  # Does nothing
```

### What Tenant Isolation Does NOT Protect

❌ **Raw SQL queries**
```python
# Raw SQL bypasses ORM filtering
cursor.execute("SELECT * FROM uploads WHERE customer_id = %s", [999])
# This WILL return other customer's data!

# Solution: Use ORM or manually add customer filter
cursor.execute(
    "SELECT * FROM uploads WHERE customer_id = %s",
    [get_current_customer().id]
)
```

❌ **Admin operations with all_objects**
```python
# Admin can bypass filtering
Upload.all_objects.filter(customer_id=999)  # Returns data!

# This is intentional for admin operations
# But requires proper authorization checks
```

❌ **Background tasks without customer context**
```python
# Background task has no request context
@shared_task
def process_upload(upload_id):
    upload = Upload.objects.get(id=upload_id)  # May fail!

# Solution: Use all_objects and get customer explicitly
@shared_task
def process_upload(upload_id):
    upload = Upload.all_objects.get(id=upload_id)
    customer = upload.customer
    # Use customer explicitly
```

### Security Best Practices

1. **Always verify customer ownership in admin views**
```python
@admin_required
def admin_view(request, upload_id):
    upload = Upload.all_objects.get(id=upload_id)

    # Verify user has permission for this customer
    if not request.user.can_access_customer(upload.customer):
        raise PermissionDenied

    # Safe to proceed...
```

2. **Use customer_context in background tasks**
```python
@shared_task
def process_report(report_run_id):
    report_run = ReportRun.all_objects.get(id=report_run_id)

    # Set customer context for duration of task
    with customer_context(report_run.customer):
        # All queries now scoped to this customer
        drift_events = compute_drift(report_run)
```

3. **Audit cross-customer access**
```python
# Log when all_objects or for_customer is used
import logging

logger = logging.getLogger('tenant_isolation')

def admin_customer_query(customer_id, user):
    """Log cross-customer queries by admins."""
    logger.warning(
        f"Admin {user.username} queried customer {customer_id}",
        extra={'user_id': user.id, 'customer_id': customer_id}
    )
    return Upload.objects.for_customer(customer_id)
```

---

## Performance Considerations

### Query Performance

**Auto-filtering adds WHERE clause to every query:**

```sql
-- Without tenant isolation
SELECT * FROM uploads WHERE status = 'success';

-- With tenant isolation
SELECT * FROM uploads
WHERE customer_id = 123 AND status = 'success';
```

**Impact:**
- ✅ Minimal overhead (single equality check)
- ✅ Improves performance (fewer rows scanned)
- ✅ Better cache locality (same customer data together)

### Indexing Strategy

**Always index customer + frequently queried fields:**

```python
class Meta:
    indexes = [
        # Good: Composite indexes with customer first
        models.Index(fields=['customer', 'status']),
        models.Index(fields=['customer', 'created_at']),
        models.Index(fields=['customer', 'uploaded_at']),

        # Also keep single-column indexes if needed
        models.Index(fields=['status']),  # For admin views
    ]
```

**Index usage:**

```sql
-- Uses index: customer_status_idx
SELECT * FROM uploads
WHERE customer_id = 123 AND status = 'success';

-- Uses index: customer_created_at_idx
SELECT * FROM uploads
WHERE customer_id = 123
ORDER BY created_at DESC
LIMIT 10;
```

### N+1 Query Prevention

**Problem: N+1 queries across customers**

```python
# Bad: Queries each customer separately
for customer in Customer.objects.all():
    uploads_count = Upload.objects.for_customer(customer).count()
```

**Solution: Aggregate or batch**

```python
# Good: Single aggregated query
from django.db.models import Count

customer_stats = Customer.objects.annotate(
    uploads_count=Count('uploads')
)
```

### Caching Considerations

**Cache keys should include customer ID:**

```python
# Bad: Global cache key
cache_key = 'dashboard_data'
data = cache.get(cache_key)  # Cross-customer contamination!

# Good: Customer-specific cache key
cache_key = f'dashboard_data:customer:{customer.id}'
data = cache.get(cache_key)  # Isolated per customer
```

**Cache invalidation:**

```python
def invalidate_customer_cache(customer):
    """Invalidate all cached data for a customer."""
    patterns = [
        f'dashboard:customer:{customer.id}',
        f'reports:customer:{customer.id}',
        f'statistics:customer:{customer.id}',
    ]
    for pattern in patterns:
        cache.delete(pattern)
```

---

## Troubleshooting

### Problem: Empty QuerySets in Production

**Symptoms:**
```python
Upload.objects.all()  # Returns empty even though data exists
```

**Causes:**
1. No customer set in thread-local storage
2. Background task without customer context
3. Admin operation using wrong manager

**Solutions:**

```python
# Check if customer is set
customer = get_current_customer()
print(f"Current customer: {customer}")  # None?

# For background tasks, use all_objects
upload = Upload.all_objects.get(id=upload_id)

# For admin, use for_customer
uploads = Upload.objects.for_customer(customer)
```

### Problem: Cross-Customer Data Leakage

**Symptoms:**
```python
# User sees data from another customer
```

**Investigation:**

1. Check if customer foreign key exists:
```python
# Make sure model has customer field
assert hasattr(Upload, 'customer')
```

2. Check if managers are set correctly:
```python
# Verify CustomerScopedManager is used
assert isinstance(Upload.objects, CustomerScopedManager)
```

3. Check middleware configuration:
```python
# In settings.py, verify middleware order
MIDDLEWARE = [
    ...
    'upstream.core.tenant.TenantIsolationMiddleware',  # Must be here
    ...
]
```

4. Check user profile:
```python
# Verify user has customer assigned
user = User.objects.get(username='test')
assert hasattr(user, 'profile')
assert user.profile.customer is not None
```

### Problem: Tests Failing with "DoesNotExist"

**Symptoms:**
```python
Upload.DoesNotExist: Upload matching query does not exist.
```

**Solution:**
Use `all_objects` for test data creation:

```python
# Bad
self.upload = Upload.objects.create(...)  # Fails!

# Good
self.upload = Upload.all_objects.create(...)  # Works!
```

See [TESTING.md](TESTING.md) for comprehensive testing guide.

### Problem: update_or_create Double-Filtering

**Symptoms:**
```python
# update_or_create doesn't find existing record
obj, created = Model.objects.update_or_create(...)
# created=True even though record exists
```

**Solution:**
Use `all_objects` for update_or_create:

```python
# Bad
obj, created = Model.objects.update_or_create(
    field=value,
    defaults={...}
)

# Good
obj, created = Model.all_objects.update_or_create(
    customer=customer,
    field=value,
    defaults={...}
)
```

---

## Migration Guide

### Migrating from No Tenant Isolation

**Planning:**

1. **Identify models to migrate**
   - Models with customer data
   - Models without customer reference

2. **Plan migration strategy**
   - Can you determine customer from existing data?
   - Need manual data cleanup?
   - Can you deploy incrementally?

3. **Create migration timeline**
   - Add fields (nullable)
   - Backfill data
   - Make fields required
   - Update application code
   - Deploy

**Example Migration:**

See "Adding Tenant Isolation to Existing Model" section above for detailed steps.

### Testing Migration

1. **Test with production data copy**
```bash
# Copy production database to staging
pg_dump production_db | psql staging_db

# Run migrations on staging
python manage.py migrate

# Verify data integrity
python manage.py check_tenant_isolation
```

2. **Validate customer assignments**
```python
# Check for records without customer
from upstream.models import Upload

orphaned = Upload.objects.filter(customer__isnull=True)
assert orphaned.count() == 0, "Found orphaned records!"
```

3. **Test cross-customer isolation**
```python
# Verify customer A cannot see customer B's data
with customer_context(customer_a):
    customer_b_data = Upload.objects.filter(customer=customer_b)
    assert customer_b_data.count() == 0
```

---

## Advanced Topics

### Custom Manager Methods

Add custom filtering to your manager:

```python
class UploadManager(CustomerScopedManager):
    """Custom manager for Upload model."""

    def successful(self):
        """Get successful uploads for current customer."""
        return self.get_queryset().filter(status='success')

    def recent(self, days=7):
        """Get uploads from last N days for current customer."""
        cutoff = timezone.now() - timedelta(days=days)
        return self.get_queryset().filter(uploaded_at__gte=cutoff)

class Upload(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    # ... fields ...

    objects = UploadManager()  # Use custom manager
    all_objects = models.Manager()
```

Usage:

```python
# Auto-filtered to current customer
recent_successful = Upload.objects.successful().recent(days=7)
```

### Multi-Tenant Reporting

For cross-customer reports (admin only):

```python
def generate_platform_report():
    """Generate report across all customers."""
    stats = []

    for customer in Customer.objects.all():
        # Use for_customer for explicit filtering
        uploads = Upload.objects.for_customer(customer)

        stats.append({
            'customer': customer.name,
            'total_uploads': uploads.count(),
            'successful_uploads': uploads.filter(status='success').count(),
        })

    return stats
```

### Soft Deletes with Tenant Isolation

```python
class SoftDeleteCustomerScopedManager(CustomerScopedManager):
    """Manager with soft delete support."""

    def get_queryset(self):
        """Return queryset excluding soft-deleted records."""
        qs = super().get_queryset()
        return qs.filter(deleted_at__isnull=True)

    def with_deleted(self):
        """Include soft-deleted records."""
        return super().get_queryset()

class YourModel(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteCustomerScopedManager()
    all_objects = models.Manager()

    def soft_delete(self):
        """Soft delete this record."""
        self.deleted_at = timezone.now()
        self.save()
```

---

## References

- [TESTING.md](TESTING.md) - Testing with tenant isolation
- [Django Multi-Tenant Patterns](https://books.agiliq.com/projects/django-multi-tenant/en/latest/)
- [Row-Level Security in PostgreSQL](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)

---

## Questions?

- **Architecture questions**: Ask in #engineering
- **Security concerns**: Contact security team
- **Bug reports**: File issue with "tenant-isolation" label
