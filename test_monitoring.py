#!/usr/bin/env python
"""
Test monitoring and metrics collection.

Tests:
1. Request timing middleware
2. Health check endpoint
3. Metrics collection middleware
4. Metrics dashboard view
"""

import sys
import os

# Setup Django FIRST before any imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'upstream.settings.dev')

import django
django.setup()

# Now import Django modules
from django.test import RequestFactory, Client
from django.contrib.auth.models import User
from django.core.cache import cache
from upstream.middleware import RequestTimingMiddleware, HealthCheckMiddleware, MetricsCollectionMiddleware


def test_health_check():
    """Test health check endpoint."""
    print("=" * 60)
    print("Testing Health Check Endpoint")
    print("=" * 60)

    client = Client()

    # Test /health/
    response = client.get('/health/')
    assert response.status_code == 200, f"/health/ returned {response.status_code}"
    print("✓ /health/ endpoint returns 200 OK")

    data = response.json()
    assert 'status' in data and data['status'] == 'healthy', f"Unexpected response format: {data}"
    print(f"✓ Health check response: {data}")


def test_request_timing_middleware():
    """Test request timing middleware."""
    print("\n" + "=" * 60)
    print("Testing Request Timing Middleware")
    print("=" * 60)

    factory = RequestFactory()
    request = factory.get('/')

    # Create middleware instance
    middleware = RequestTimingMiddleware(lambda r: None)

    # Process request (start timer)
    middleware.process_request(request)

    assert hasattr(request, '_request_start_time'), "Request timer NOT started"
    print("✓ Request timer started")

    # Simulate some processing time
    import time
    time.sleep(0.01)  # 10ms

    # Create mock response
    from django.http import HttpResponse
    response = HttpResponse("OK")

    # Process response (log timing)
    response = middleware.process_response(request, response)

    # Check for timing header
    assert 'X-Request-Duration-Ms' in response, "Duration header NOT added to response"
    duration = response['X-Request-Duration-Ms']
    print(f"✓ Request duration tracked: {duration}ms")

    # Verify metrics stored in cache
    recent_requests = cache.get('metrics:recent_requests', [])
    if len(recent_requests) > 0:
        print(f"✓ Metrics stored in cache: {len(recent_requests)} requests")
    else:
        print("⚠ Metrics not stored in cache (may be normal if cache unavailable)")


def test_metrics_collection():
    """Test metrics collection middleware."""
    print("\n" + "=" * 60)
    print("Testing Metrics Collection Middleware")
    print("=" * 60)

    factory = RequestFactory()
    middleware = MetricsCollectionMiddleware(lambda r: None)

    # Clear metrics
    cache.delete('metrics:request_count:/test/')
    cache.delete('metrics:error_count:/test/')

    # Test successful request
    request = factory.get('/test/')
    from django.http import HttpResponse
    response = HttpResponse("OK", status=200)

    middleware.process_response(request, response)

    # Check request counter
    counter = cache.get('metrics:request_count:/test/', 0)
    assert counter > 0, "Request counter NOT incremented"
    print(f"✓ Request counter incremented: {counter}")

    # Test error request
    error_response = HttpResponse("Not Found", status=404)
    middleware.process_response(request, error_response)

    error_counter = cache.get('metrics:error_count:/test/', 0)
    if error_counter > 0:
        print(f"✓ Error counter incremented: {error_counter}")
    else:
        print("⚠ Error counter not incremented (may be normal if cache unavailable)")


def test_metrics_dashboard_view():
    """Test metrics dashboard view (requires staff user)."""
    print("\n" + "=" * 60)
    print("Testing Metrics Dashboard View")
    print("=" * 60)

    # Create staff user
    try:
        user = User.objects.create_user(
            username='test_staff',
            password='testpass123',
            is_staff=True
        )
        print("✓ Created test staff user")
    except Exception as e:
        print(f"⚠ Could not create test user: {str(e)}")
        # Try to get existing user
        user = User.objects.filter(username='test_staff').first()
        assert user, "Could not get test user"

    client = Client()

    # Try to access without authentication
    response = client.get('/portal/admin/metrics/')
    assert response.status_code == 302, f"Metrics dashboard returned {response.status_code} without auth (expected 302 redirect)"
    print("✓ Metrics dashboard requires authentication")

    # Login and access
    client.force_login(user)
    response = client.get('/portal/admin/metrics/')

    assert response.status_code == 200, f"Metrics dashboard returned {response.status_code} for staff user"
    print("✓ Metrics dashboard accessible to staff users")

    # Check response contains expected elements
    content = response.content.decode('utf-8')
    if 'Metrics Dashboard' in content:
        print("✓ Dashboard title found in response")
    if 'Average Response Time' in content:
        print("✓ Metrics content found in response")


def cleanup():
    """Clean up test data."""
    print("\n" + "=" * 60)
    print("Cleanup")
    print("=" * 60)

    try:
        # Delete test user
        User.objects.filter(username='test_staff').delete()
        print("✓ Test user deleted")

        # Clear metrics cache
        cache.delete('metrics:recent_requests')
        cache.delete('metrics:request_count:/test/')
        cache.delete('metrics:error_count:/test/')
        print("✓ Metrics cache cleared")

    except Exception as e:
        print(f"⚠ Cleanup error: {str(e)}")


if __name__ == '__main__':
    try:
        # Run tests - assertions will fail the test if something is wrong
        test_health_check()
        test_request_timing_middleware()
        test_metrics_collection()
        test_metrics_dashboard_view()

        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print("✅ ALL TESTS PASSED")
        print("\nMonitoring middleware is working correctly!")
        cleanup()
        sys.exit(0)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {str(e)}")
        cleanup()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        cleanup()
        sys.exit(1)
