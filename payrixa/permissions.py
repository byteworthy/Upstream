"""
RBAC Permission Service for Payrixa.

Provides permission checks and decorators for enforcing access control.
"""

import logging
from functools import wraps
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied

logger = logging.getLogger(__name__)


def get_user_profile(user):
    """Get user profile, returns None if not found."""
    if not user or not user.is_authenticated:
        return None
    try:
        return user.profile
    except Exception:
        return None


def has_permission(user, permission_name):
    """
    Check if user has a specific permission.
    
    Permission names:
    - view_reports: View dashboards, drift feed, reports
    - upload_claims: Upload claim files
    - manage_mappings: Manage payer/CPT mappings
    - manage_alerts: Manage alert rules and routing
    - manage_webhooks: Manage webhooks
    - manage_users: Manage team members and roles
    - manage_configuration: Access configuration section (owner/admin)
    """
    profile = get_user_profile(user)
    if not profile:
        return False
    
    permission_map = {
        'view_reports': profile.can_view_reports,
        'upload_claims': profile.can_upload_claims,
        'manage_mappings': profile.can_manage_mappings,
        'manage_alerts': profile.can_manage_alerts,
        'manage_webhooks': profile.can_manage_webhooks,
        'manage_users': profile.can_manage_users,
        'manage_configuration': profile.is_admin,
    }
    
    return permission_map.get(permission_name, False)


def permission_required(permission_name, redirect_url='portal_root'):
    """
    Decorator for views that require a specific permission.
    Returns 403 if permission denied.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not has_permission(request.user, permission_name):
                logger.warning(
                    f"Permission denied: user={request.user.username if request.user.is_authenticated else 'anonymous'} "
                    f"permission={permission_name} path={request.path}"
                )
                messages.error(request, "You do not have permission to access this page.")
                return HttpResponseForbidden("Permission denied")
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


class PermissionRequiredMixin:
    """
    Mixin for class-based views that require a specific permission.
    Set permission_required attribute on the view class.
    """
    permission_required = None
    
    def dispatch(self, request, *args, **kwargs):
        if self.permission_required:
            if not has_permission(request.user, self.permission_required):
                logger.warning(
                    f"Permission denied: user={request.user.username if request.user.is_authenticated else 'anonymous'} "
                    f"permission={self.permission_required} path={request.path}"
                )
                messages.error(request, "You do not have permission to access this page.")
                return HttpResponseForbidden("Permission denied")
        return super().dispatch(request, *args, **kwargs)


def can_manage_member(acting_user, target_profile):
    """
    Check if acting_user can manage (edit/remove) target_profile.
    
    Rules:
    - Owners can manage anyone
    - Admins can manage analysts and viewers, but not owners or other admins
    - Cannot remove the last owner
    """
    acting_profile = get_user_profile(acting_user)
    if not acting_profile:
        return False
    
    if not acting_profile.can_manage_users:
        return False
    
    # Owners can manage anyone
    if acting_profile.is_owner:
        return True
    
    # Admins cannot manage owners or other admins
    if target_profile.role in ('owner', 'admin'):
        return False
    
    return True


def is_last_owner(profile):
    """Check if this profile is the last owner of the customer."""
    if profile.role != 'owner':
        return False
    
    from payrixa.models import UserProfile
    owner_count = UserProfile.objects.filter(
        customer=profile.customer,
        role='owner'
    ).count()
    
    return owner_count <= 1


def validate_role_change(acting_user, target_profile, new_role):
    """
    Validate a role change operation.
    
    Returns (is_valid, error_message)
    """
    acting_profile = get_user_profile(acting_user)
    if not acting_profile:
        return False, "Not authenticated"
    
    if not acting_profile.can_manage_users:
        return False, "You do not have permission to manage users"
    
    # Admins cannot promote to owner or admin
    if not acting_profile.is_owner:
        if new_role in ('owner', 'admin'):
            return False, "Only owners can assign owner or admin roles"
        if target_profile.role in ('owner', 'admin'):
            return False, "You cannot modify owner or admin roles"
    
    # Cannot demote the last owner (check after permission check)
    if target_profile.role == 'owner' and new_role != 'owner':
        if is_last_owner(target_profile):
            return False, "Cannot remove the last owner. Promote another user to owner first."
    
    return True, None


def validate_remove_member(acting_user, target_profile):
    """
    Validate a member removal operation.
    
    Returns (is_valid, error_message)
    """
    acting_profile = get_user_profile(acting_user)
    if not acting_profile:
        return False, "Not authenticated"
    
    if not acting_profile.can_manage_users:
        return False, "You do not have permission to manage users"
    
    # Cannot remove the last owner
    if is_last_owner(target_profile):
        return False, "Cannot remove the last owner. Transfer ownership first."
    
    # Admins cannot remove owners or other admins
    if not acting_profile.is_owner:
        if target_profile.role in ('owner', 'admin'):
            return False, "You cannot remove owners or admins"
    
    return True, None


def get_user_permissions(user):
    """
    Get all permissions for a user as a dict for template context.
    """
    profile = get_user_profile(user)
    if not profile:
        return {
            'can_view_reports': False,
            'can_upload_claims': False,
            'can_manage_mappings': False,
            'can_manage_alerts': False,
            'can_manage_webhooks': False,
            'can_manage_users': False,
            'can_manage_configuration': False,
            'role': None,
            'is_owner': False,
            'is_admin': False,
        }
    
    return {
        'can_view_reports': profile.can_view_reports,
        'can_upload_claims': profile.can_upload_claims,
        'can_manage_mappings': profile.can_manage_mappings,
        'can_manage_alerts': profile.can_manage_alerts,
        'can_manage_webhooks': profile.can_manage_webhooks,
        'can_manage_users': profile.can_manage_users,
        'can_manage_configuration': profile.is_admin,
        'role': profile.role,
        'is_owner': profile.is_owner,
        'is_admin': profile.is_admin,
    }
