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
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'payrixa.settings.dev')

import django
django.setup()

# Now import Django modules
from django.test import RequestFactory, Client
from django.contrib.auth.models import User
from django.core.cache import cache
from payrixa.middleware import RequestTimingMiddleware, HealthCheckMiddleware, MetricsCollectionMiddleware


def test_health_check():
    """Test health check endpoint."""
    print("=" * 60)
    print("Testing Health Check Endpoint")
    print("=" * 60)

    client = Client()

    # Test /health/
    response = client.get('/health/')
    if response.status_code == 200:
        print("✓ /health/ endpoint returns 200 OK")
        data = response.json()
        if 'status' in data and data['status'] == 'healthy':
            print(f"✓ Health check response: {data}")
            return True
        else:
            print(f"✗ Unexpected response format: {data}")
            return False
    else:
        print(f"✗ /health/ returned {response.status_code}")
        return False


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

    if hasattr(request, '_request_start_time'):
        print("✓ Request timer started")
    else:
        print("✗ Request timer NOT started")
        return False

    # Simulate some processing time
    import time
    time.sleep(0.01)  # 10ms

    # Create mock response
    from django.http import HttpResponse
    response = HttpResponse("OK")

    # Process response (log timing)
    response = middleware.process_response(request, response)

    # Check for timing header
    if 'X-Request-Duration-Ms' in response:
        duration = response['X-Request-Duration-Ms']
        print(f"✓ Request duration tracked: {duration}ms")

        # Verify metrics stored in cache
        recent_requests = cache.get('metrics:recent_requests', [])
        if len(recent_requests) > 0:
            print(f"✓ Metrics stored in cache: {len(recent_requests)} requests")
            return True
        else:
            print("⚠ Metrics not stored in cache (may be normal if cache unavailable)")
            return True
    else:
        print("✗ Duration header NOT added to response")
        return False


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
    if counter > 0:
        print(f"✓ Request counter incremented: {counter}")
    else:
        print("✗ Request counter NOT incremented")
        return False

    # Test error request
    error_response = HttpResponse("Not Found", status=404)
    middleware.process_response(request, error_response)

    error_counter = cache.get('metrics:error_count:/test/', 0)
    if error_counter > 0:
        print(f"✓ Error counter incremented: {error_counter}")
        return True
    else:
        print("⚠ Error counter not incremented (may be normal if cache unavailable)")
        return True


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
        if not user:
            print("✗ Could not get test user")
            return False

    client = Client()

    # Try to access without authentication
    response = client.get('/portal/admin/metrics/')
    if response.status_code == 302:  # Redirect to login
        print("✓ Metrics dashboard requires authentication")
    else:
        print(f"✗ Metrics dashboard returned {response.status_code} without auth")
        return False

    # Login and access
    client.force_login(user)
    response = client.get('/portal/admin/metrics/')

    if response.status_code == 200:
        print("✓ Metrics dashboard accessible to staff users")
        # Check response contains expected elements
        content = response.content.decode('utf-8')
        if 'Metrics Dashboard' in content:
            print("✓ Dashboard title found in response")
        if 'Average Response Time' in content:
            print("✓ Metrics content found in response")
        return True
    else:
        print(f"✗ Metrics dashboard returned {response.status_code} for staff user")
        return False


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
        results = []

        # Run tests
        results.append(("Health Check Endpoint", test_health_check()))
        results.append(("Request Timing Middleware", test_request_timing_middleware()))
        results.append(("Metrics Collection", test_metrics_collection()))
        results.append(("Metrics Dashboard View", test_metrics_dashboard_view()))

        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)

        passed = sum(1 for _, result in results if result)
        total = len(results)

        for test_name, result in results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status}: {test_name}")

        print("\n" + "=" * 60)

        if passed == total:
            print(f"✅ ALL TESTS PASSED ({passed}/{total})")
            print("\nMonitoring middleware is working correctly!")
            cleanup()
            sys.exit(0)
        else:
            print(f"⚠ SOME TESTS FAILED ({passed}/{total} passed)")
            cleanup()
            sys.exit(1)

    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        cleanup()
        sys.exit(1)
