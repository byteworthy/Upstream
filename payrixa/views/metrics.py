"""
Metrics and monitoring views for Payrixa.

Provides internal metrics dashboard for operators to monitor system health.
"""

import time
from django.views.generic import TemplateView
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.core.cache import cache
from django.db import connection
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


@method_decorator(staff_member_required, name='dispatch')
class MetricsDashboardView(TemplateView):
    """
    Internal metrics dashboard for staff members.

    Shows:
    - Recent request metrics
    - Request counts by endpoint
    - Error rates
    - Active users
    - Cache statistics
    - Database connection pool status
    """

    template_name = "payrixa/admin/metrics_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        try:
            # Get recent requests
            recent_requests = cache.get('metrics:recent_requests', [])
            context['recent_requests'] = recent_requests[-20:]  # Last 20 requests

            # Calculate average response time
            if recent_requests:
                avg_response_time = sum(r['duration_ms'] for r in recent_requests) / len(recent_requests)
                context['avg_response_time'] = f"{avg_response_time:.2f}"
            else:
                context['avg_response_time'] = "N/A"

            # Get request counts by endpoint
            request_counts = self._get_request_counts()
            context['request_counts'] = sorted(request_counts.items(), key=lambda x: x[1], reverse=True)[:10]

            # Get error counts
            error_counts = self._get_error_counts()
            context['error_counts'] = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:10]

            # Active users (last 5 minutes)
            active_users = cache.get('metrics:active_users', set())
            context['active_user_count'] = len(active_users)

            # Cache statistics
            try:
                from payrixa.cache import get_cache_stats
                cache_stats = get_cache_stats()
                context['cache_stats'] = cache_stats
            except Exception as e:
                logger.warning(f"Failed to get cache stats: {str(e)}")
                context['cache_stats'] = {}

            # Database connection info
            context['db_vendor'] = connection.vendor
            context['db_settings'] = {
                'ENGINE': settings.DATABASES['default']['ENGINE'],
                'NAME': settings.DATABASES['default']['NAME'],
            }

            # System info
            context['python_version'] = self._get_python_version()
            context['django_version'] = self._get_django_version()

            # Slow requests
            slow_requests = [r for r in recent_requests if r['duration_ms'] > 2000]
            context['slow_requests'] = sorted(slow_requests, key=lambda x: x['duration_ms'], reverse=True)[:10]

        except Exception as e:
            logger.error(f"Error loading metrics dashboard: {str(e)}")
            context['error'] = str(e)

        return context

    def _get_request_counts(self):
        """Get request counts by endpoint from cache."""
        counts = {}
        try:
            # Scan cache for request_count keys
            # This is a simplified version - in production with Redis, use SCAN
            for key in ['/', '/uploads/', '/drift_feed/', '/reports/', '/settings/', '/mappings/']:
                normalized_key = key
                counter_key = f'metrics:request_count:{normalized_key}'
                count = cache.get(counter_key, 0)
                if count > 0:
                    counts[key] = count
        except Exception as e:
            logger.debug(f"Error getting request counts: {str(e)}")

        return counts

    def _get_error_counts(self):
        """Get error counts by endpoint from cache."""
        errors = {}
        try:
            for key in ['/', '/uploads/', '/drift_feed/', '/reports/', '/settings/', '/mappings/']:
                normalized_key = key
                error_key = f'metrics:error_count:{normalized_key}'
                count = cache.get(error_key, 0)
                if count > 0:
                    errors[key] = count
        except Exception as e:
            logger.debug(f"Error getting error counts: {str(e)}")

        return errors

    def _get_python_version(self):
        """Get Python version."""
        import sys
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    def _get_django_version(self):
        """Get Django version."""
        import django
        return django.get_version()
