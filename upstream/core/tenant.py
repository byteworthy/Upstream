"""
Tenant isolation system for Upstream.

Provides automatic customer filtering at the ORM level to prevent data leakage.
"""
import threading
from contextlib import contextmanager
from django.db import models
from typing import Optional

# Thread-local storage for current customer context
_thread_locals = threading.local()


def set_current_customer(customer):
    """Set the current customer in thread-local storage."""
    _thread_locals.customer = customer


def get_current_customer():
    """Get the current customer from thread-local storage."""
    return getattr(_thread_locals, 'customer', None)


def clear_current_customer():
    """Clear the current customer from thread-local storage."""
    if hasattr(_thread_locals, 'customer'):
        delattr(_thread_locals, 'customer')


@contextmanager
def customer_context(customer):
    """
    Context manager for temporarily setting the current customer.

    Usage:
        with customer_context(some_customer):
            # All queries here are auto-filtered to some_customer
            uploads = Upload.objects.all()
    """
    old_customer = get_current_customer()
    set_current_customer(customer)
    try:
        yield
    finally:
        if old_customer:
            set_current_customer(old_customer)
        else:
            clear_current_customer()


class CustomerScopedQuerySet(models.QuerySet):
    """QuerySet that automatically filters by current customer."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._auto_filter_applied = False

    def _clone(self):
        """Preserve the auto filter flag when cloning."""
        clone = super()._clone()
        clone._auto_filter_applied = self._auto_filter_applied
        return clone

    def _apply_customer_filter(self):
        """Apply customer filter if not already applied."""
        if not self._auto_filter_applied:
            customer = get_current_customer()

            # Apply the filter by modifying the queryset in-place
            if customer is not None:
                # Add customer filter to the query
                self.query.add_q(models.Q(customer=customer))
            else:
                # No customer context - force empty result
                self.query.add_q(models.Q(pk__in=[]))

            self._auto_filter_applied = True

    def _fetch_all(self):
        """
        Override _fetch_all to apply customer filter before executing query.
        This is called by Django before any query execution.
        """
        self._apply_customer_filter()
        super()._fetch_all()

    def count(self):
        """
        Override count() to ensure customer filter is applied.
        Django's count() optimization bypasses _fetch_all(), so we need this.
        """
        self._apply_customer_filter()
        return super().count()

    def exists(self):
        """
        Override exists() to ensure customer filter is applied.
        """
        self._apply_customer_filter()
        return super().exists()


class CustomerScopedManager(models.Manager):
    """
    Manager that automatically filters querysets by the current customer.

    Usage in models:
        class Upload(models.Model):
            customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
            # ... other fields ...

            objects = CustomerScopedManager()
            all_objects = models.Manager()  # Unfiltered access for superusers
    """

    def get_queryset(self):
        """Return a customer-scoped queryset."""
        return CustomerScopedQuerySet(self.model, using=self._db)

    def for_customer(self, customer):
        """
        Explicitly get objects for a specific customer.

        This bypasses thread-local filtering and is useful for:
        - Admin operations
        - Background tasks
        - Cross-customer queries (with proper authorization)
        """
        qs = self.get_queryset()
        # Mark filter as already applied to prevent double-filtering
        qs._auto_filter_applied = True
        return qs.filter(customer=customer)

    def unscoped(self):
        """
        Get unfiltered queryset (for superusers/admin only).

        WARNING: This bypasses tenant isolation. Use with extreme caution.
        """
        # Return the base queryset without customer filtering
        return super().get_queryset()


class TenantIsolationMiddleware:
    """
    Middleware to set the current customer in thread-local storage.

    This ensures all ORM queries are automatically scoped to the user's customer.
    """

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

        # Superusers: don't set customer (they can see all data)
        # This is intentional - superusers need cross-customer visibility

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
