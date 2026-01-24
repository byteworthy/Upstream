"""
Upstream API Permissions

Custom permission classes for multi-tenant access control.
Ensures users can only access data belonging to their customer.
"""

from typing import Optional, Any
from django.contrib.auth.models import User
from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.views import APIView


class IsCustomerMember(permissions.BasePermission):
    """
    Ensures the authenticated user belongs to the customer whose
    data they are trying to access.
    """
    
    message = "You do not have permission to access this customer's data."
    
    def has_permission(self, request: Request, view: APIView) -> bool:
        # User must be authenticated
        if not request.user or not request.user.is_authenticated:
            return False

        # Superusers have access to all data
        if request.user.is_superuser:
            return True

        # User must have a profile with a customer
        return hasattr(request.user, 'profile') and request.user.profile.customer is not None

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        # Superusers can access anything
        if request.user.is_superuser:
            return True

        # Get the customer from the object
        customer = self._get_customer_from_object(obj)
        if customer is None:
            return False

        # Compare with user's customer
        return request.user.profile.customer == customer

    def _get_customer_from_object(self, obj: Any) -> Optional[Any]:
        """Extract customer from various model types."""
        # Direct customer field
        if hasattr(obj, 'customer'):
            return obj.customer
        
        # For Customer model itself
        if obj.__class__.__name__ == 'Customer':
            return obj
        
        # For UserProfile
        if hasattr(obj, 'customer'):
            return obj.customer
        
        return None


class IsCustomerAdmin(permissions.BasePermission):
    """
    Permission for administrative actions within a customer.
    Currently same as IsCustomerMember but can be extended
    for role-based access within organizations.
    """
    
    message = "You do not have admin permissions for this customer."
    
    def has_permission(self, request: Request, view: APIView) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        # For now, all customer members are admins
        # Future: check for admin role in UserProfile
        return hasattr(request.user, 'profile') and request.user.profile.customer is not None

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        if request.user.is_superuser:
            return True

        customer = getattr(obj, 'customer', None)
        if customer is None and obj.__class__.__name__ == 'Customer':
            customer = obj

        if customer is None:
            return False

        return request.user.profile.customer == customer


class ReadOnly(permissions.BasePermission):
    """
    Allow read-only access.
    """
    
    def has_permission(self, request: Request, view: APIView) -> bool:
        return request.method in permissions.SAFE_METHODS


def get_user_customer(user: User) -> Optional[Any]:
    """
    Utility function to get the customer for a user.
    Returns None if user is not associated with a customer.
    """
    if user.is_superuser:
        return None  # Superusers operate in a special context
    
    if hasattr(user, 'profile') and user.profile.customer:
        return user.profile.customer
    
    return None
