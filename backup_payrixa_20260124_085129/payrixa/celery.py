"""
Celery configuration for Upstream.

This module initializes the Celery application for asynchronous task processing.
"""

import os
from celery import Celery
from decouple import config

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'upstream.settings')

# Create Celery app
app = Celery('upstream')

# Load configuration from Django settings with the CELERY namespace
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

# Check if Celery is enabled via environment variable
CELERY_ENABLED = config('CELERY_ENABLED', default=False, cast=bool)


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task to test Celery is working."""
    print(f'Request: {self.request!r}')
