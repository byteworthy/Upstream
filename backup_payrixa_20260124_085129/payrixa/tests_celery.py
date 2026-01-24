"""
Tests for Celery async tasks.

These tests verify that Celery tasks can be imported and are properly registered.
"""

from django.test import TestCase, override_settings


# Configure Celery to run tasks eagerly (synchronously) in tests
@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
    CELERY_ENABLED=False,
)
class CeleryTaskTests(TestCase):
    """Test suite for Celery async tasks."""

    def test_task_imports(self):
        """Test that all task functions can be imported."""
        from upstream.tasks import (
            run_drift_detection_task,
            send_alert_task,
            send_webhook_task,
            generate_report_artifact_task,
            send_scheduled_report_task,
            enqueue_or_run_sync,
        )
        
        self.assertIsNotNone(run_drift_detection_task)
        self.assertIsNotNone(send_alert_task)
        self.assertIsNotNone(send_webhook_task)
        self.assertIsNotNone(generate_report_artifact_task)
        self.assertIsNotNone(send_scheduled_report_task)
        self.assertIsNotNone(enqueue_or_run_sync)

    def test_drift_detection_task_structure(self):
        """Test drift detection task has correct structure."""
        from upstream.tasks import run_drift_detection_task
        
        self.assertEqual(
            run_drift_detection_task.name,
            'upstream.tasks.run_drift_detection'
        )

    def test_alert_task_structure(self):
        """Test alert task has correct structure."""
        from upstream.tasks import send_alert_task
        
        self.assertEqual(
            send_alert_task.name,
            'upstream.tasks.send_alert'
        )

    def test_webhook_task_structure(self):
        """Test webhook task has correct structure."""
        from upstream.tasks import send_webhook_task
        
        self.assertEqual(
            send_webhook_task.name,
            'upstream.tasks.send_webhook'
        )

    def test_report_artifact_task_structure(self):
        """Test report artifact generation task has correct structure."""
        from upstream.tasks import generate_report_artifact_task
        
        self.assertEqual(
            generate_report_artifact_task.name,
            'upstream.tasks.generate_report_artifact'
        )

    def test_scheduled_report_task_structure(self):
        """Test scheduled report task has correct structure."""
        from upstream.tasks import send_scheduled_report_task
        
        self.assertEqual(
            send_scheduled_report_task.name,
            'upstream.tasks.send_scheduled_report'
        )

    def test_tasks_are_registered(self):
        """Test that tasks are properly registered with Celery."""
        from upstream.celery import app
        
        registered_tasks = list(app.tasks.keys())
        
        # Check that our tasks are registered
        self.assertIn('upstream.tasks.run_drift_detection', registered_tasks)
        self.assertIn('upstream.tasks.send_alert', registered_tasks)
        self.assertIn('upstream.tasks.send_webhook', registered_tasks)
        self.assertIn('upstream.tasks.generate_report_artifact', registered_tasks)
        self.assertIn('upstream.tasks.send_scheduled_report', registered_tasks)


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class CeleryConfigurationTests(TestCase):
    """Test Celery configuration."""

    def test_celery_app_exists(self):
        """Test that Celery app is properly configured."""
        from upstream.celery import app
        
        self.assertIsNotNone(app)
        self.assertEqual(app.main, 'upstream')

    def test_celery_autodiscover_works(self):
        """Test that Celery can autodiscover tasks."""
        from upstream.celery import app
        
        # Autodiscover should have found our tasks
        task_names = [name for name in app.tasks.keys() if name.startswith('upstream')]
        self.assertGreater(len(task_names), 0)
