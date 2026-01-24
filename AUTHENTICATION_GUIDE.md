# Upstream Authentication & Multi-Tenancy Guide

**Last Updated:** 2026-01-22
**Version:** Hub v1

---

## Overview

Upstream uses a **multi-tenant architecture** with role-based access control (RBAC). This guide explains how authentication and tenant separation work.

---

## Account Types

### 1. **Operator Accounts** (Internal Staff)

**Who:** Upstream employees, support staff, system administrators

**How to Create:**
```bash
python manage.py createsuperuser
```

**Characteristics:**
- Created with Django's `createsuperuser` command
- `is_superuser = True`
- `is_staff = True`
- **No UserProfile required** - not linked to a customer
- Can access **all customer data** across the platform
- Displayed in UI as: `Operator | All Customers`

**Use Cases:**
- System administration
- Customer support
- Debugging issues across tenants
- Platform monitoring

---

### 2. **Client Accounts** (Customer Users)

**Who:** Healthcare organization staff using Upstream for their claims analysis

**How to Create:**
```python
from django.contrib.auth.models import User
from upstream.models import Customer, UserProfile

# Create user
user = User.objects.create_user(
    username='john.doe',
    email='john@hospital.com',
    password='secure_password'
)

# Link to customer with role
customer = Customer.objects.get(name='Memorial Hospital')
UserProfile.objects.create(
    user=user,
    customer=customer,
    role='admin'  # or 'owner', 'analyst', 'viewer'
)
```

**Characteristics:**
- Must have a `UserProfile` linked to a `Customer`
- Can only access **their own customer's data**
- Has one of 4 roles: Owner, Admin, Analyst, or Viewer
- Displayed in UI as: `Customer Name | Role`

---

## Login Flow

### Current Implementation (Hub v1)

1. **User visits:** `/portal/login/`
2. **Enters credentials** (username + password)
3. **Django authenticates** via standard session-based auth
4. **On success:**
   - Session created with `request.user` set
   - Redirected to `/portal/axis/` (Axis Hub)
5. **Navigation shows:**
   - Operators see: `Operator | All Customers`
   - Clients see: `Customer Name | Role`

### Entry Points

| URL | Purpose | Who Can Use |
|-----|---------|-------------|
| `/portal/login/` | Main login page | Everyone (operators + clients) |
| `/portal/logout/` | Logout with context display | Authenticated users |

---

## User Interface Indicators

### Navigation Header (Phase 3 Enhancement)

The navigation header now shows clear tenant and role context:

**For Operators:**
```
Upstream [Operator | All Customers] Axis DenialScope ... Logout
```

**For Clients:**
```
Upstream [Memorial Hospital | Admin] Axis DenialScope ... Logout
```

**Visual Styling:**
- **Operator badge:** Yellow background (#fff3cd) - clearly distinct
- **Customer badge:** Blue background (#d1ecf1) - organization name
- **Role badges:** Color-coded by role level:
  - Owner: Green (#d4edda)
  - Admin: Blue (#d1ecf1)
  - Analyst: Light blue (#e7f3ff)
  - Viewer: Gray (#f8f9fa)

### Logout Page

When logging out, users see a confirmation showing:
- Which account type was logged out (Operator vs Customer)
- Customer name and role (for client accounts)
- Username
- Button to log in again

---

## Role-Based Access Control (RBAC)

### Roles & Permissions

| Role | Upload Claims | Manage Mappings | Manage Alerts | Manage Users | View Reports |
|------|--------------|----------------|---------------|--------------|--------------|
| **Owner** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Admin** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Analyst** | ✅ | ✅ | ❌ | ❌ | ✅ |
| **Viewer** | ❌ | ❌ | ❌ | ❌ | ✅ |

**Default Role:** `viewer` (most restrictive)

### Permission Checks

**In Views:**
```python
from upstream.permissions import PermissionRequiredMixin

class MyView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'upload_claims'
```

**In Code:**
```python
from upstream.permissions import has_permission

if has_permission(request.user, 'manage_alerts'):
    # User can manage alerts
```

---

## Multi-Tenancy & Data Isolation

### Architecture

Upstream uses **application-level tenant isolation**, not database-level middleware.

**Data Model:**
```
User (Django auth)
  ↓ one-to-one
UserProfile
  ↓ many-to-one
Customer
  ↓ one-to-many
All domain models (Upload, ClaimRecord, DriftEvent, etc.)
```

### Isolation Enforcement

#### Portal Views
Every view calls `get_current_customer(request)`:

```python
from upstream.utils import get_current_customer

customer = get_current_customer(request)
data = SomeModel.objects.filter(customer=customer)
```

**Process:**
1. Checks if user is authenticated
2. If superuser → can access any customer
3. If regular user → checks for `user.profile.customer`
4. Returns customer or raises `ValueError`

#### API Endpoints
Views use `CustomerFilterMixin`:

```python
from upstream.api.views import CustomerFilterMixin

class MyViewSet(CustomerFilterMixin, viewsets.ModelViewSet):
    queryset = MyModel.objects.all()
```

**Process:**
1. Checks if `user.is_superuser` → returns all data
2. Gets customer via `get_user_customer(user)`
3. Filters: `queryset.filter(customer=customer)`
4. Returns filtered queryset

#### Permission Classes
API uses custom permissions:

```python
from upstream.api.permissions import IsCustomerMember

class MyViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsCustomerMember]
```

---

## Security Considerations

### ✅ Implemented Safeguards

1. **Session-based authentication** - Django's built-in security
2. **CSRF protection** - Enabled by default
3. **Role-based permissions** - 4-tier RBAC system
4. **Explicit query filtering** - All views filter by customer
5. **Superuser bypass audit** - Operators clearly identified in UI
6. **Test coverage** - Tenant isolation tests in `tests_api.py`

### ⚠️ Important Notes

**Manual Query Filtering:**
- Tenant isolation is NOT enforced at the database/ORM level
- Developers must remember to call `get_current_customer()` or use `CustomerFilterMixin`
- A query like `Upload.objects.all()` would leak data across customers

**Best Practice:**
Always use the helper patterns:
```python
# GOOD
customer = get_current_customer(request)
uploads = Upload.objects.filter(customer=customer)

# BAD (leaks data!)
uploads = Upload.objects.all()
```

**Production Recommendation:**
For additional safety, consider implementing:
- Custom Django model managers with auto-filtering
- Thread-local storage for current customer
- Database-level row-level security (PostgreSQL RLS)

---

## Common Tasks

### Create a New Customer

```python
from upstream.models import Customer

customer = Customer.objects.create(name="Memorial Hospital")
```

### Create a Client User

```python
from django.contrib.auth.models import User
from upstream.models import Customer, UserProfile

# Get customer
customer = Customer.objects.get(name="Memorial Hospital")

# Create user
user = User.objects.create_user(
    username='jane.smith',
    email='jane@memorial.com',
    password='SecurePassword123!'
)

# Create profile
UserProfile.objects.create(
    user=user,
    customer=customer,
    role='analyst'
)
```

### Change a User's Role

```python
profile = UserProfile.objects.get(user__username='jane.smith')
profile.role = 'admin'
profile.save()
```

### Check Current User's Customer

```python
# In a view with request
from upstream.utils import get_current_customer

try:
    customer = get_current_customer(request)
    print(f"Current customer: {customer.name}")
except ValueError as e:
    print("User has no customer (likely a superuser)")
```

### Verify User Permissions

```python
from upstream.permissions import has_permission

if has_permission(request.user, 'upload_claims'):
    # User can upload claims
    pass
```

---

## Testing Authentication

### Test Superuser Login

```bash
# Create superuser
python manage.py createsuperuser

# Login at /portal/login/
# Should see: "Operator | All Customers" in navigation
```

### Test Client Login

```bash
# Create customer and user (see above)
# Login at /portal/login/
# Should see: "Customer Name | Role" in navigation
```

### Test Tenant Isolation

```python
# In Django shell
from django.test import RequestFactory
from django.contrib.auth.models import User
from upstream.models import Customer, UserProfile, Upload

# Create two customers
c1 = Customer.objects.create(name="Hospital A")
c2 = Customer.objects.create(name="Hospital B")

# Create uploads for each
Upload.objects.create(customer=c1, filename="test1.csv")
Upload.objects.create(customer=c2, filename="test2.csv")

# Create users for each
u1 = User.objects.create_user('user1', password='pass')
u2 = User.objects.create_user('user2', password='pass')
UserProfile.objects.create(user=u1, customer=c1, role='admin')
UserProfile.objects.create(user=u2, customer=c2, role='admin')

# Test isolation
from upstream.utils import get_current_customer

request1 = RequestFactory().get('/')
request1.user = u1
customer1 = get_current_customer(request1)
uploads1 = Upload.objects.filter(customer=customer1)
# Should only see Hospital A's upload
assert uploads1.count() == 1
assert uploads1.first().filename == "test1.csv"
```

---

## Troubleshooting

### Issue: User can't log in

**Check:**
1. Does the User exist? `User.objects.filter(username='...').exists()`
2. Is password correct? Try resetting: `user.set_password('new_pass'); user.save()`
3. Is user active? `user.is_active` should be `True`

### Issue: User sees "No customer associated with user"

**Cause:** User has no `UserProfile`

**Fix:**
```python
from upstream.models import Customer, UserProfile

customer = Customer.objects.get(name='...')
profile = UserProfile.objects.create(
    user=user,
    customer=customer,
    role='viewer'
)
```

### Issue: User can't access certain features

**Check role permissions:**
```python
profile = UserProfile.objects.get(user=user)
print(profile.role)  # Should be owner, admin, analyst, or viewer
print(profile.can_upload_claims)  # Check specific permission
```

### Issue: Operator can't see all customers

**Check superuser status:**
```python
user = User.objects.get(username='operator_name')
print(user.is_superuser)  # Should be True
print(user.is_staff)  # Should be True
```

---

## File Reference

| File | Purpose |
|------|---------|
| `upstream/models.py` | Customer, UserProfile models |
| `upstream/utils.py` | `get_current_customer()` helper |
| `upstream/permissions.py` | RBAC permission checks |
| `upstream/api/permissions.py` | API permission classes |
| `upstream/api/views.py` | `CustomerFilterMixin` |
| `upstream/views.py` | Portal views + CustomLogoutView |
| `upstream/middleware.py` | ProductEnablementMiddleware |
| `upstream/templates/upstream/base.html` | Navigation with tenant indicator |
| `upstream/templates/upstream/logged_out.html` | Logout confirmation page |
| `upstream/templates/upstream/login.html` | Login page |

---

## Changelog

### 2026-01-22 - Phase 3 Enhancements
- ✅ Added tenant and role indicator to navigation header
- ✅ Added context-aware logout page
- ✅ Created this authentication guide
- ✅ Visual distinction between operator and client accounts

### Previous
- Multi-tenant architecture implemented
- RBAC with 4 roles
- Application-level data isolation
- SuperUser bypass for operators

---

**End of Authentication Guide**
