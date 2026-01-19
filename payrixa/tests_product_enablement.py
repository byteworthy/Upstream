from django.test import TestCase
from django.contrib.auth.models import User
from payrixa.models import Customer, UserProfile
from payrixa.core.models import ProductConfig


class ProductEnablementTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(name='Enablement Customer')
        self.user = User.objects.create_user(username='enablement_user', password='pass')
        UserProfile.objects.create(user=self.user, customer=self.customer, role='admin')
        self.client.force_login(self.user)

    def test_navigation_defaults_to_payrixa_core(self):
        response = self.client.get('/portal/uploads/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Payrixa Core')
        self.assertNotContains(response, 'DenialScope')

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
        self.assertContains(dashboard_response, 'No denial data yet')

    def test_denialscope_forbidden_when_disabled(self):
        ProductConfig.objects.create(
            customer=self.customer,
            product_slug='denialscope',
            enabled=False
        )
        response = self.client.get('/portal/products/denialscope/')
        self.assertEqual(response.status_code, 403)
