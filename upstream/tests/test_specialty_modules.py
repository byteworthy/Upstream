"""
Tests for the Specialty Module System.

Tests:
1. Customer.enabled_specialties property
2. Customer.has_specialty() method
3. CustomerSpecialtyModule enable/disable
4. Cannot disable primary specialty
5. API endpoints for specialty management
"""

from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth.models import User

from upstream.models import Customer, CustomerSpecialtyModule, UserProfile


class CustomerSpecialtyModelTests(TestCase):
    """Test Customer model specialty methods."""

    def setUp(self):
        """Create test customer."""
        self.customer = Customer.objects.create(name="Test Customer")

    def test_enabled_specialties_empty_when_no_specialty(self):
        """Customer with no specialty_type should have empty enabled_specialties."""
        self.assertEqual(self.customer.enabled_specialties, [])

    def test_enabled_specialties_includes_primary(self):
        """enabled_specialties should include primary specialty."""
        self.customer.specialty_type = "DIALYSIS"
        self.customer.save()

        self.assertIn("DIALYSIS", self.customer.enabled_specialties)

    def test_has_specialty_checks_primary_first(self):
        """has_specialty should return True for primary specialty."""
        self.customer.specialty_type = "DIALYSIS"
        self.customer.save()

        self.assertTrue(self.customer.has_specialty("DIALYSIS"))

    def test_has_specialty_case_insensitive(self):
        """has_specialty should be case-insensitive."""
        self.customer.specialty_type = "DIALYSIS"
        self.customer.save()

        self.assertTrue(self.customer.has_specialty("dialysis"))
        self.assertTrue(self.customer.has_specialty("Dialysis"))
        self.assertTrue(self.customer.has_specialty("DIALYSIS"))

    def test_has_specialty_returns_false_for_missing(self):
        """has_specialty should return False for non-enabled specialty."""
        self.customer.specialty_type = "DIALYSIS"
        self.customer.save()

        self.assertFalse(self.customer.has_specialty("ABA"))
        self.assertFalse(self.customer.has_specialty("IMAGING"))

    def test_enable_specialty_module(self):
        """Enabling a specialty module should add it to enabled_specialties."""
        self.customer.specialty_type = "DIALYSIS"
        self.customer.save()

        # Enable ABA module
        CustomerSpecialtyModule.objects.create(
            customer=self.customer,
            specialty="ABA",
            enabled=True,
        )

        self.assertIn("ABA", self.customer.enabled_specialties)
        self.assertTrue(self.customer.has_specialty("ABA"))

    def test_disable_specialty_module(self):
        """Disabling a specialty module should remove it from enabled_specialties."""
        self.customer.specialty_type = "DIALYSIS"
        self.customer.save()

        # Create and then disable ABA module
        module = CustomerSpecialtyModule.objects.create(
            customer=self.customer,
            specialty="ABA",
            enabled=True,
        )

        self.assertIn("ABA", self.customer.enabled_specialties)

        module.enabled = False
        module.save()

        self.assertNotIn("ABA", self.customer.enabled_specialties)
        self.assertFalse(self.customer.has_specialty("ABA"))

    def test_enabled_specialties_includes_all_enabled_modules(self):
        """enabled_specialties should include primary + all enabled modules."""
        self.customer.specialty_type = "DIALYSIS"
        self.customer.save()

        CustomerSpecialtyModule.objects.create(
            customer=self.customer,
            specialty="ABA",
            enabled=True,
        )
        CustomerSpecialtyModule.objects.create(
            customer=self.customer,
            specialty="IMAGING",
            enabled=True,
        )
        CustomerSpecialtyModule.objects.create(
            customer=self.customer,
            specialty="PTOT",
            enabled=False,  # Disabled
        )

        specialties = self.customer.enabled_specialties
        self.assertIn("DIALYSIS", specialties)
        self.assertIn("ABA", specialties)
        self.assertIn("IMAGING", specialties)
        self.assertNotIn("PTOT", specialties)
        self.assertEqual(len(specialties), 3)


class CustomerSpecialtyModuleModelTests(TestCase):
    """Test CustomerSpecialtyModule model."""

    def setUp(self):
        """Create test customer."""
        self.customer = Customer.objects.create(
            name="Test Customer", specialty_type="DIALYSIS"
        )

    def test_unique_together_constraint(self):
        """Cannot create duplicate specialty modules for same customer."""
        CustomerSpecialtyModule.objects.create(
            customer=self.customer,
            specialty="ABA",
            enabled=True,
        )

        with self.assertRaises(Exception):
            CustomerSpecialtyModule.objects.create(
                customer=self.customer,
                specialty="ABA",
                enabled=True,
            )

    def test_str_representation(self):
        """Test string representation of specialty module."""
        module = CustomerSpecialtyModule.objects.create(
            customer=self.customer,
            specialty="ABA",
            enabled=True,
        )

        self.assertIn("Test Customer", str(module))
        self.assertIn("ABA", str(module))
        self.assertIn("enabled", str(module))

    def test_is_primary_flag(self):
        """Test is_primary flag on specialty module."""
        module = CustomerSpecialtyModule.objects.create(
            customer=self.customer,
            specialty="ABA",
            enabled=True,
            is_primary=True,
        )

        self.assertTrue(module.is_primary)
        self.assertIn("primary", str(module))


class CustomerSpecialtyAPITests(APITestCase):
    """Test API endpoints for specialty module management."""

    def setUp(self):
        """Create test user, customer, and profile."""
        self.customer = Customer.objects.create(name="Test Customer")
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",  # pragma: allowlist secret
        )
        UserProfile.objects.create(
            user=self.user,
            customer=self.customer,
            role="admin",
        )
        self.client.force_authenticate(user=self.user)

    def test_me_endpoint_returns_customer_info(self):
        """GET /customers/me/ should return customer with specialty info."""
        self.customer.specialty_type = "DIALYSIS"
        self.customer.save()

        response = self.client.get("/api/v1/customers/me/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["specialty_type"], "DIALYSIS")
        self.assertIn("DIALYSIS", response.data["enabled_specialties"])

    def test_set_primary_specialty(self):
        """POST /customers/set_primary_specialty/ should set primary specialty."""
        response = self.client.post(
            "/api/v1/customers/set_primary_specialty/",
            {"specialty_type": "DIALYSIS"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.customer.refresh_from_db()
        self.assertEqual(self.customer.specialty_type, "DIALYSIS")

    def test_enable_specialty(self):
        """POST /customers/enable_specialty/ should enable add-on module."""
        self.customer.specialty_type = "DIALYSIS"
        self.customer.save()

        response = self.client.post(
            "/api/v1/customers/enable_specialty/",
            {"specialty": "ABA"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertTrue(self.customer.has_specialty("ABA"))
        self.assertTrue(
            CustomerSpecialtyModule.objects.filter(
                customer=self.customer,
                specialty="ABA",
                enabled=True,
            ).exists()
        )

    def test_disable_specialty(self):
        """POST /customers/disable_specialty/ should disable add-on module."""
        self.customer.specialty_type = "DIALYSIS"
        self.customer.save()

        # First enable ABA
        CustomerSpecialtyModule.objects.create(
            customer=self.customer,
            specialty="ABA",
            enabled=True,
        )

        response = self.client.post(
            "/api/v1/customers/disable_specialty/",
            {"specialty": "ABA"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(self.customer.has_specialty("ABA"))

    def test_cannot_disable_primary_specialty(self):
        """Cannot disable primary specialty via API."""
        self.customer.specialty_type = "DIALYSIS"
        self.customer.save()

        response = self.client.post(
            "/api/v1/customers/disable_specialty/",
            {"specialty": "DIALYSIS"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("primary", response.data.get("error", "").lower())

    def test_set_primary_specialty_invalid_type(self):
        """Setting invalid specialty type should fail."""
        response = self.client.post(
            "/api/v1/customers/set_primary_specialty/",
            {"specialty_type": "INVALID"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
