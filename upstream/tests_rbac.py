"""
Tests for RBAC (Role-Based Access Control) system.
"""

from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from django.http import HttpResponseForbidden
from upstream.models import Customer, UserProfile
from upstream.permissions import (
    has_permission, 
    get_user_profile,
    validate_role_change,
    validate_remove_member,
    is_last_owner
)


class RBACPermissionTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(name='Test Customer')
        
        # Create users with different roles
        self.owner_user = User.objects.create_user(username='owner', password='pass')
        self.owner_profile = UserProfile.objects.create(
            user=self.owner_user,
            customer=self.customer,
            role='owner'
        )
        
        self.admin_user = User.objects.create_user(username='admin', password='pass')
        self.admin_profile = UserProfile.objects.create(
            user=self.admin_user,
            customer=self.customer,
            role='admin'
        )
        
        self.analyst_user = User.objects.create_user(username='analyst', password='pass')
        self.analyst_profile = UserProfile.objects.create(
            user=self.analyst_user,
            customer=self.customer,
            role='analyst'
        )
        
        self.viewer_user = User.objects.create_user(username='viewer', password='pass')
        self.viewer_profile = UserProfile.objects.create(
            user=self.viewer_user,
            customer=self.customer,
            role='viewer'
        )

    def test_owner_permissions(self):
        """Test that owners have all permissions."""
        self.assertTrue(has_permission(self.owner_user, 'view_reports'))
        self.assertTrue(has_permission(self.owner_user, 'upload_claims'))
        self.assertTrue(has_permission(self.owner_user, 'manage_mappings'))
        self.assertTrue(has_permission(self.owner_user, 'manage_alerts'))
        self.assertTrue(has_permission(self.owner_user, 'manage_webhooks'))
        self.assertTrue(has_permission(self.owner_user, 'manage_users'))
        self.assertTrue(has_permission(self.owner_user, 'manage_configuration'))

    def test_admin_permissions(self):
        """Test that admins have admin-level permissions."""
        self.assertTrue(has_permission(self.admin_user, 'view_reports'))
        self.assertTrue(has_permission(self.admin_user, 'upload_claims'))
        self.assertTrue(has_permission(self.admin_user, 'manage_mappings'))
        self.assertTrue(has_permission(self.admin_user, 'manage_alerts'))
        self.assertTrue(has_permission(self.admin_user, 'manage_webhooks'))
        self.assertTrue(has_permission(self.admin_user, 'manage_users'))
        self.assertTrue(has_permission(self.admin_user, 'manage_configuration'))

    def test_analyst_permissions(self):
        """Test that analysts have analyst-level permissions."""
        self.assertTrue(has_permission(self.analyst_user, 'view_reports'))
        self.assertTrue(has_permission(self.analyst_user, 'upload_claims'))
        self.assertTrue(has_permission(self.analyst_user, 'manage_mappings'))
        self.assertFalse(has_permission(self.analyst_user, 'manage_alerts'))
        self.assertFalse(has_permission(self.analyst_user, 'manage_webhooks'))
        self.assertFalse(has_permission(self.analyst_user, 'manage_users'))
        self.assertFalse(has_permission(self.analyst_user, 'manage_configuration'))

    def test_viewer_permissions(self):
        """Test that viewers have view-only permissions."""
        self.assertTrue(has_permission(self.viewer_user, 'view_reports'))
        self.assertFalse(has_permission(self.viewer_user, 'upload_claims'))
        self.assertFalse(has_permission(self.viewer_user, 'manage_mappings'))
        self.assertFalse(has_permission(self.viewer_user, 'manage_alerts'))
        self.assertFalse(has_permission(self.viewer_user, 'manage_webhooks'))
        self.assertFalse(has_permission(self.viewer_user, 'manage_users'))
        self.assertFalse(has_permission(self.viewer_user, 'manage_configuration'))

    def test_unauthenticated_user_no_permissions(self):
        """Test that unauthenticated users have no permissions."""
        anon_user = User()
        self.assertFalse(has_permission(anon_user, 'view_reports'))
        self.assertFalse(has_permission(anon_user, 'upload_claims'))
        self.assertFalse(has_permission(anon_user, 'manage_configuration'))

    def test_last_owner_protection(self):
        """Test that the last owner cannot be removed/demoted."""
        # Owner is the only owner
        self.assertTrue(is_last_owner(self.owner_profile))
        
        # Try to remove last owner
        valid, error = validate_remove_member(self.owner_user, self.owner_profile)
        self.assertFalse(valid)
        self.assertIn('last owner', error.lower())
        
        # Try to demote last owner
        valid, error = validate_role_change(self.owner_user, self.owner_profile, 'admin')
        self.assertFalse(valid)
        self.assertIn('last owner', error.lower())

    def test_multiple_owners_allows_demotion(self):
        """Test that when there are multiple owners, one can be demoted."""
        # Create second owner
        owner2_user = User.objects.create_user(username='owner2', password='pass')
        owner2_profile = UserProfile.objects.create(
            user=owner2_user,
            customer=self.customer,
            role='owner'
        )
        
        # Now first owner is not the last owner
        self.assertFalse(is_last_owner(self.owner_profile))
        
        # Should be able to demote first owner
        valid, error = validate_role_change(self.owner_user, self.owner_profile, 'admin')
        self.assertTrue(valid)
        self.assertIsNone(error)

    def test_admin_cannot_promote_to_owner(self):
        """Test that admins cannot promote users to owner."""
        # Admin tries to promote viewer to owner
        valid, error = validate_role_change(self.admin_user, self.viewer_profile, 'owner')
        self.assertFalse(valid)
        self.assertIn('only owners', error.lower())

    def test_admin_cannot_modify_owner(self):
        """Test that admins cannot modify owner roles."""
        valid, error = validate_role_change(self.admin_user, self.owner_profile, 'admin')
        self.assertFalse(valid)
        # Error message could be either "cannot modify" or about role restriction
        self.assertTrue('cannot modify' in error.lower() or 'owner' in error.lower())

    def test_owner_can_promote_to_admin(self):
        """Test that owners can promote users to admin."""
        valid, error = validate_role_change(self.owner_user, self.analyst_profile, 'admin')
        self.assertTrue(valid)
        self.assertIsNone(error)

    def test_admin_can_promote_analyst_to_analyst(self):
        """Test that admins can change analyst/viewer roles."""
        valid, error = validate_role_change(self.admin_user, self.viewer_profile, 'analyst')
        self.assertTrue(valid)
        self.assertIsNone(error)

    def test_viewer_cannot_manage_users(self):
        """Test that viewers cannot manage users."""
        valid, error = validate_role_change(self.viewer_user, self.analyst_profile, 'viewer')
        self.assertFalse(valid)
        self.assertIn('do not have permission', error.lower())


class RBACViewPermissionTests(TestCase):
    """Test permission checks for views using the mixin."""
    
    def setUp(self):
        self.customer = Customer.objects.create(name='Test Customer')
        
        self.analyst_user = User.objects.create_user(username='analyst', password='pass')
        self.analyst_profile = UserProfile.objects.create(
            user=self.analyst_user,
            customer=self.customer,
            role='analyst'
        )
        
        self.viewer_user = User.objects.create_user(username='viewer', password='pass')
        self.viewer_profile = UserProfile.objects.create(
            user=self.viewer_user,
            customer=self.customer,
            role='viewer'
        )

    def test_upload_claims_permission_check(self):
        """Test that upload_claims permission is checked correctly."""
        # Analyst should have permission
        self.assertTrue(has_permission(self.analyst_user, 'upload_claims'))
        # Viewer should not
        self.assertFalse(has_permission(self.viewer_user, 'upload_claims'))

    def test_manage_mappings_permission_check(self):
        """Test that manage_mappings permission is checked correctly."""
        # Analyst should have permission
        self.assertTrue(has_permission(self.analyst_user, 'manage_mappings'))
        # Viewer should not
        self.assertFalse(has_permission(self.viewer_user, 'manage_mappings'))
