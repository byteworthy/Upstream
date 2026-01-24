from django.test import TestCase
from django.contrib.auth.models import User
from upstream.models import Customer, UserProfile
from upstream.core.models import ProductConfig


class ProductEnablementTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(name='Enablement Customer')
        self.user = User.objects.create_user(username='enablement_user', password='pass')
        UserProfile.objects.create(user=self.user, customer=self.customer, role='admin')
        self.client.force_login(self.user)

    def test_navigation_defaults_to_axis_hub(self):
        """Hub v1: Navigation shows Axis as primary entry."""
        response = self.client.get('/portal/uploads/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Axis')

    def test_denialscope_nav_and_access_when_enabled(self):
        ProductConfig.objects.create(
            customer=self.customer,
            product_slug='denialscope',
            enabled=True
        )
        response = self.client.get('/portal/uploads/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'DenialScope')

        dashboard_response = self.client.get('/portal/products/denialscope/')
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertContains(dashboard_response, 'Total Denials')

    def test_denialscope_forbidden_when_disabled(self):
        ProductConfig.objects.create(
            customer=self.customer,
            product_slug='denialscope',
            enabled=False
        )
        response = self.client.get('/portal/products/denialscope/')
        self.assertEqual(response.status_code, 403)

    def test_driftwatch_accessible_when_enabled(self):
        """DriftWatch dashboard returns 200 when product is enabled."""
        ProductConfig.objects.create(
            customer=self.customer,
            product_slug='driftwatch',
            enabled=True
        )
        response = self.client.get('/portal/products/driftwatch/')
        self.assertEqual(response.status_code, 200)

    def test_driftwatch_forbidden_when_disabled(self):
        """DriftWatch dashboard returns 403 when product is disabled."""
        ProductConfig.objects.create(
            customer=self.customer,
            product_slug='driftwatch',
            enabled=False
        )
        response = self.client.get('/portal/products/driftwatch/')
        self.assertEqual(response.status_code, 403)
