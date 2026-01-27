"""
Tests for health check endpoint.

Tests validate detailed health checks for database, Redis, Celery workers,
and disk space monitoring.
"""

from django.test import TestCase, override_settings
from django.urls import reverse
from unittest.mock import patch, MagicMock
from django.core.cache import cache
from django.db import connection


class HealthCheckEndpointTests(TestCase):
    """Test health check endpoint with detailed checks."""

    def setUp(self):
        self.url = reverse("api-health")
        # Clear cache before each test
        cache.clear()

    def test_health_check_all_healthy(self):
        """Health check returns 200 when all services healthy."""
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Verify structure
        self.assertEqual(data["status"], "healthy")
        self.assertIn("version", data)
        self.assertIn("timestamp", data)
        self.assertIn("checks", data)

        # Verify all checks present
        checks = data["checks"]
        self.assertIn("database", checks)
        self.assertIn("redis", checks)
        self.assertIn("celery", checks)
        self.assertIn("disk", checks)

        # Verify healthy checks have expected fields
        self.assertEqual(checks["database"]["status"], "healthy")
        self.assertIn("latency_ms", checks["database"])

        self.assertEqual(checks["redis"]["status"], "healthy")
        self.assertIn("latency_ms", checks["redis"])

        # Celery may be disabled in dev
        self.assertIn(checks["celery"]["status"], ["healthy", "disabled"])

        # Disk may be warning or healthy
        self.assertIn(checks["disk"]["status"], ["healthy", "warning"])
        self.assertIn("percent_free", checks["disk"])
        self.assertIn("free_gb", checks["disk"])

    @patch("upstream.api.views.connection")
    def test_health_check_database_failure(self, mock_connection):
        """Health check returns 503 when database unavailable."""
        mock_connection.ensure_connection.side_effect = Exception("Connection refused")

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 503)
        data = response.json()

        self.assertEqual(data["status"], "unhealthy")
        self.assertEqual(data["checks"]["database"]["status"], "unhealthy")
        self.assertIn("error", data["checks"]["database"])

    @patch("upstream.api.views.cache")
    def test_health_check_redis_failure(self, mock_cache):
        """Health check returns 503 when Redis unavailable."""
        mock_cache.set.side_effect = Exception("Redis connection error")

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 503)
        data = response.json()

        self.assertEqual(data["status"], "unhealthy")
        self.assertEqual(data["checks"]["redis"]["status"], "unhealthy")
        self.assertIn("error", data["checks"]["redis"])

    @patch("upstream.api.views.cache")
    def test_health_check_redis_mismatch(self, mock_cache):
        """Health check detects cache get/set mismatch."""
        mock_cache.set.return_value = None
        mock_cache.get.return_value = "wrong_value"

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 503)
        data = response.json()

        self.assertEqual(data["checks"]["redis"]["status"], "unhealthy")
        self.assertIn("mismatch", data["checks"]["redis"]["error"])

    @override_settings(CELERY_ENABLED=True)
    @patch("upstream.celery.app")
    def test_health_check_celery_no_workers(self, mock_app):
        """Health check returns 503 when no Celery workers available."""
        mock_inspect = MagicMock()
        mock_inspect.active.return_value = None
        mock_app.control.inspect.return_value = mock_inspect

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 503)
        data = response.json()

        self.assertEqual(data["checks"]["celery"]["status"], "unhealthy")
        self.assertIn("error", data["checks"]["celery"])

    @override_settings(CELERY_ENABLED=True)
    @patch("upstream.celery.app")
    def test_health_check_celery_healthy(self, mock_app):
        """Health check succeeds when Celery workers available."""
        mock_inspect = MagicMock()
        mock_inspect.active.return_value = {"worker1@host": [], "worker2@host": []}
        mock_app.control.inspect.return_value = mock_inspect

        response = self.client.get(self.url)

        # Should be 200 if only Celery was mocked
        data = response.json()

        self.assertEqual(data["checks"]["celery"]["status"], "healthy")
        self.assertEqual(data["checks"]["celery"]["workers"], 2)

    @override_settings(CELERY_ENABLED=False)
    def test_health_check_celery_disabled(self):
        """Health check shows Celery as disabled when CELERY_ENABLED=False."""
        response = self.client.get(self.url)

        data = response.json()

        self.assertEqual(data["checks"]["celery"]["status"], "disabled")

    @patch("upstream.api.views.shutil")
    def test_health_check_disk_warning(self, mock_shutil):
        """Health check shows warning when disk space < 20%."""
        mock_usage = MagicMock()
        mock_usage.total = 100 * (1024**3)  # 100 GB
        mock_usage.free = 15 * (1024**3)  # 15 GB (15% free)
        mock_shutil.disk_usage.return_value = mock_usage

        response = self.client.get(self.url)

        # Should be 200 (warning is not unhealthy)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["checks"]["disk"]["status"], "warning")
        self.assertAlmostEqual(data["checks"]["disk"]["percent_free"], 15.0, places=1)

    @patch("upstream.api.views.shutil")
    def test_health_check_disk_critical(self, mock_shutil):
        """Health check returns 503 when disk space < 10%."""
        mock_usage = MagicMock()
        mock_usage.total = 100 * (1024**3)  # 100 GB
        mock_usage.free = 5 * (1024**3)  # 5 GB (5% free)
        mock_shutil.disk_usage.return_value = mock_usage

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 503)
        data = response.json()

        self.assertEqual(data["status"], "unhealthy")
        self.assertEqual(data["checks"]["disk"]["status"], "unhealthy")
        self.assertIn("error", data["checks"]["disk"])

    def test_health_check_no_authentication_required(self):
        """Health check endpoint does not require authentication."""
        # This test verifies permission_classes = [] works
        response = self.client.get(self.url)

        # Should not return 401 or 403
        self.assertNotEqual(response.status_code, 401)
        self.assertNotEqual(response.status_code, 403)
        self.assertIn(response.status_code, [200, 503])

    def test_health_check_response_time(self):
        """Health check responds quickly (< 5 seconds)."""
        import time

        start = time.time()
        response = self.client.get(self.url)
        duration = time.time() - start

        self.assertLess(duration, 5.0, "Health check took too long")
        self.assertIn(response.status_code, [200, 503])
