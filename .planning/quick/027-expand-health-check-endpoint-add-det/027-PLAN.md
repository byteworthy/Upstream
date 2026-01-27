---
phase: quick-027
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - upstream/api/views.py
  - upstream/api/tests/test_health_check.py
autonomous: true

must_haves:
  truths:
    - "Health check endpoint returns detailed status for database, Redis, Celery, and disk"
    - "Health check fails with 503 if any critical service is unavailable"
    - "Health check response includes version and timestamp"
    - "Tests validate all health check scenarios (healthy, db failure, redis failure, etc.)"
  artifacts:
    - path: "upstream/api/views.py"
      provides: "Expanded HealthCheckView with detailed checks"
      min_lines: 2050
    - path: "upstream/api/tests/test_health_check.py"
      provides: "Health check test suite"
      min_lines: 100
  key_links:
    - from: "upstream/api/views.py"
      to: "django.db.connection"
      via: "Database connectivity check"
      pattern: "connection\\.ensure_connection"
    - from: "upstream/api/views.py"
      to: "django.core.cache"
      via: "Redis availability check"
      pattern: "cache\\.set.*cache\\.get"
    - from: "upstream/api/views.py"
      to: "celery.app.control.inspect"
      via: "Celery worker status check"
      pattern: "inspect.*active"
---

<objective>
Expand health check endpoint with detailed health checks for database connectivity, Redis availability, Celery worker status, and disk space monitoring.

Purpose: Provide comprehensive health monitoring for deployment validation, load balancer health checks, and operational monitoring. Currently the health check only returns basic status - needs detailed checks for all critical services.

Output: Production-ready health check endpoint with detailed status for all dependencies and comprehensive test coverage.
</objective>

<execution_context>
@/home/codespace/.claude/get-shit-done/workflows/execute-plan.md
@/home/codespace/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@upstream/api/views.py (lines 1948-1982: Current HealthCheckView)
@upstream/settings/base.py (lines 282-340: Redis, Celery, cache config)

## Current Implementation

The health check endpoint at `/api/health/` currently returns only basic status:
```python
{
    "status": "healthy",
    "version": "1.0.0",
    "timestamp": "2024-03-15T10:30:00Z"
}
```

## Required Checks

**1. Database Connectivity**
- Check: `connection.ensure_connection()` succeeds
- Failure: Cannot execute queries, data layer unavailable

**2. Redis Availability**
- Check: `cache.set()` and `cache.get()` succeed
- Failure: Caching disabled, session storage may fail

**3. Celery Worker Status**
- Check: At least one worker is active via `app.control.inspect().active()`
- Failure: Async tasks won't process (reports, drift detection)

**4. Disk Space**
- Check: At least 10% disk space available via `shutil.disk_usage()`
- Warning: < 20% available (approaching limit)
- Failure: < 10% available (critical)

## Configuration

- REDIS_URL: `redis://localhost:6379` (default)
- CELERY_BROKER_URL: Uses Redis DB 0
- CELERY_ENABLED: Can be disabled in dev (check before inspecting workers)
- Database: SQLite in dev, PostgreSQL in production

## Response Format

**200 OK (all healthy):**
```json
{
    "status": "healthy",
    "version": "1.0.0",
    "timestamp": "2024-03-15T10:30:00Z",
    "checks": {
        "database": {"status": "healthy", "latency_ms": 2.3},
        "redis": {"status": "healthy", "latency_ms": 1.1},
        "celery": {"status": "healthy", "workers": 2},
        "disk": {"status": "healthy", "percent_free": 45.2, "free_gb": 15.8}
    }
}
```

**503 Service Unavailable (degraded):**
```json
{
    "status": "unhealthy",
    "version": "1.0.0",
    "timestamp": "2024-03-15T10:30:00Z",
    "checks": {
        "database": {"status": "healthy", "latency_ms": 2.3},
        "redis": {"status": "unhealthy", "error": "Connection refused"},
        "celery": {"status": "healthy", "workers": 2},
        "disk": {"status": "healthy", "percent_free": 45.2, "free_gb": 15.8}
    }
}
```

**Warnings (200 OK with warnings):**
```json
{
    "status": "healthy",
    "version": "1.0.0",
    "timestamp": "2024-03-15T10:30:00Z",
    "checks": {
        "database": {"status": "healthy", "latency_ms": 2.3},
        "redis": {"status": "healthy", "latency_ms": 1.1},
        "celery": {"status": "healthy", "workers": 2},
        "disk": {"status": "warning", "percent_free": 15.5, "free_gb": 5.2}
    }
}
```
</context>

<tasks>

<task type="auto">
  <name>Task 1: Expand HealthCheckView with detailed health checks</name>
  <files>upstream/api/views.py</files>
  <action>
Expand the HealthCheckView class (currently lines 1948-1982) with detailed health checks:

**1. Add imports at top of file:**
- `from django.db import connection`
- `from django.core.cache import cache`
- `from django.conf import settings`
- `import time`
- `import shutil`

**2. Create helper methods in HealthCheckView:**

```python
def check_database(self):
    """Check database connectivity and measure latency."""
    try:
        start = time.time()
        connection.ensure_connection()
        latency_ms = (time.time() - start) * 1000
        return {"status": "healthy", "latency_ms": round(latency_ms, 1)}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

def check_redis(self):
    """Check Redis availability via cache operations."""
    try:
        start = time.time()
        test_key = "health_check_test"
        test_value = "ok"
        cache.set(test_key, test_value, timeout=10)
        result = cache.get(test_key)
        latency_ms = (time.time() - start) * 1000

        if result != test_value:
            return {"status": "unhealthy", "error": "Cache get/set mismatch"}

        return {"status": "healthy", "latency_ms": round(latency_ms, 1)}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

def check_celery(self):
    """Check Celery worker availability."""
    # Skip check if Celery is disabled (dev environments)
    if not getattr(settings, 'CELERY_ENABLED', False):
        return {"status": "disabled"}

    try:
        from upstream.celery import app
        inspect = app.control.inspect()
        active = inspect.active()

        if active is None:
            return {"status": "unhealthy", "error": "No workers responding"}

        worker_count = len(active.keys())
        return {"status": "healthy", "workers": worker_count}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

def check_disk_space(self):
    """Check disk space availability."""
    try:
        disk = shutil.disk_usage('/')
        percent_free = (disk.free / disk.total) * 100
        free_gb = disk.free / (1024 ** 3)

        # Critical threshold: < 10% free
        if percent_free < 10:
            return {
                "status": "unhealthy",
                "percent_free": round(percent_free, 1),
                "free_gb": round(free_gb, 1),
                "error": "Disk space critically low"
            }
        # Warning threshold: < 20% free
        elif percent_free < 20:
            return {
                "status": "warning",
                "percent_free": round(percent_free, 1),
                "free_gb": round(free_gb, 1)
            }
        else:
            return {
                "status": "healthy",
                "percent_free": round(percent_free, 1),
                "free_gb": round(free_gb, 1)
            }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
```

**3. Update get() method:**

Replace the simple return with:

```python
def get(self, request):
    # Run all health checks
    checks = {
        "database": self.check_database(),
        "redis": self.check_redis(),
        "celery": self.check_celery(),
        "disk": self.check_disk_space(),
    }

    # Determine overall status
    overall_status = "healthy"
    for check_name, check_result in checks.items():
        if check_result.get("status") == "unhealthy":
            overall_status = "unhealthy"
            break

    response_data = {
        "status": overall_status,
        "version": "1.0.0",
        "timestamp": timezone.now().isoformat(),
        "checks": checks,
    }

    # Return 503 if any check is unhealthy
    status_code = 503 if overall_status == "unhealthy" else 200

    return Response(response_data, status=status_code)
```

**4. Update OpenAPI documentation:**

Update the `@extend_schema` decorator to document new response format with examples showing healthy, degraded, and warning states.

**Why this approach:**
- Each check is isolated in its own method for testability
- Latency measurement helps diagnose slow dependencies
- Celery check respects CELERY_ENABLED setting (dev vs prod)
- Disk check has two thresholds (warning at 20%, critical at 10%)
- Overall status is "unhealthy" if ANY check fails (fail-fast for load balancers)
- 503 status code signals load balancers to route traffic elsewhere
  </action>
  <verify>
```bash
# Start dev server
python manage.py runserver &
SERVER_PID=$!
sleep 3

# Test health check returns detailed status
curl -s http://localhost:8000/api/health/ | python -m json.tool

# Verify response has all required fields
curl -s http://localhost:8000/api/health/ | grep -q '"database"' && echo "✓ Database check present"
curl -s http://localhost:8000/api/health/ | grep -q '"redis"' && echo "✓ Redis check present"
curl -s http://localhost:8000/api/health/ | grep -q '"celery"' && echo "✓ Celery check present"
curl -s http://localhost:8000/api/health/ | grep -q '"disk"' && echo "✓ Disk check present"

# Kill server
kill $SERVER_PID
```
  </verify>
  <done>HealthCheckView returns detailed JSON with database, redis, celery, and disk checks. Returns 503 if any check is unhealthy. Each check includes status and relevant metrics (latency_ms, workers, percent_free, etc.)</done>
</task>

<task type="auto">
  <name>Task 2: Create comprehensive health check test suite</name>
  <files>upstream/api/tests/test_health_check.py</files>
  <action>
Create new test file `upstream/api/tests/test_health_check.py` with comprehensive test coverage:

**Test structure:**

```python
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
        self.url = reverse('health-check')
        # Clear cache before each test
        cache.clear()

    def test_health_check_all_healthy(self):
        """Health check returns 200 when all services healthy."""
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Verify structure
        self.assertEqual(data['status'], 'healthy')
        self.assertIn('version', data)
        self.assertIn('timestamp', data)
        self.assertIn('checks', data)

        # Verify all checks present
        checks = data['checks']
        self.assertIn('database', checks)
        self.assertIn('redis', checks)
        self.assertIn('celery', checks)
        self.assertIn('disk', checks)

        # Verify healthy checks have expected fields
        self.assertEqual(checks['database']['status'], 'healthy')
        self.assertIn('latency_ms', checks['database'])

        self.assertEqual(checks['redis']['status'], 'healthy')
        self.assertIn('latency_ms', checks['redis'])

        # Celery may be disabled in dev
        self.assertIn(checks['celery']['status'], ['healthy', 'disabled'])

        self.assertEqual(checks['disk']['status'], 'healthy')
        self.assertIn('percent_free', checks['disk'])
        self.assertIn('free_gb', checks['disk'])

    @patch('upstream.api.views.connection')
    def test_health_check_database_failure(self, mock_connection):
        """Health check returns 503 when database unavailable."""
        mock_connection.ensure_connection.side_effect = Exception("Connection refused")

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 503)
        data = response.json()

        self.assertEqual(data['status'], 'unhealthy')
        self.assertEqual(data['checks']['database']['status'], 'unhealthy')
        self.assertIn('error', data['checks']['database'])

    @patch('upstream.api.views.cache')
    def test_health_check_redis_failure(self, mock_cache):
        """Health check returns 503 when Redis unavailable."""
        mock_cache.set.side_effect = Exception("Redis connection error")

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 503)
        data = response.json()

        self.assertEqual(data['status'], 'unhealthy')
        self.assertEqual(data['checks']['redis']['status'], 'unhealthy')
        self.assertIn('error', data['checks']['redis'])

    @patch('upstream.api.views.cache')
    def test_health_check_redis_mismatch(self, mock_cache):
        """Health check detects cache get/set mismatch."""
        mock_cache.set.return_value = None
        mock_cache.get.return_value = "wrong_value"

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 503)
        data = response.json()

        self.assertEqual(data['checks']['redis']['status'], 'unhealthy')
        self.assertIn('mismatch', data['checks']['redis']['error'])

    @override_settings(CELERY_ENABLED=True)
    @patch('upstream.api.views.app')
    def test_health_check_celery_no_workers(self, mock_app):
        """Health check returns 503 when no Celery workers available."""
        mock_inspect = MagicMock()
        mock_inspect.active.return_value = None
        mock_app.control.inspect.return_value = mock_inspect

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 503)
        data = response.json()

        self.assertEqual(data['checks']['celery']['status'], 'unhealthy')
        self.assertIn('error', data['checks']['celery'])

    @override_settings(CELERY_ENABLED=True)
    @patch('upstream.api.views.app')
    def test_health_check_celery_healthy(self, mock_app):
        """Health check succeeds when Celery workers available."""
        mock_inspect = MagicMock()
        mock_inspect.active.return_value = {
            'worker1@host': [],
            'worker2@host': []
        }
        mock_app.control.inspect.return_value = mock_inspect

        response = self.client.get(self.url)

        # Should be 200 if only Celery was mocked
        data = response.json()

        self.assertEqual(data['checks']['celery']['status'], 'healthy')
        self.assertEqual(data['checks']['celery']['workers'], 2)

    @override_settings(CELERY_ENABLED=False)
    def test_health_check_celery_disabled(self):
        """Health check shows Celery as disabled when CELERY_ENABLED=False."""
        response = self.client.get(self.url)

        data = response.json()

        self.assertEqual(data['checks']['celery']['status'], 'disabled')

    @patch('upstream.api.views.shutil')
    def test_health_check_disk_warning(self, mock_shutil):
        """Health check shows warning when disk space < 20%."""
        mock_usage = MagicMock()
        mock_usage.total = 100 * (1024 ** 3)  # 100 GB
        mock_usage.free = 15 * (1024 ** 3)    # 15 GB (15% free)
        mock_shutil.disk_usage.return_value = mock_usage

        response = self.client.get(self.url)

        # Should be 200 (warning is not unhealthy)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data['status'], 'healthy')
        self.assertEqual(data['checks']['disk']['status'], 'warning')
        self.assertAlmostEqual(data['checks']['disk']['percent_free'], 15.0, places=1)

    @patch('upstream.api.views.shutil')
    def test_health_check_disk_critical(self, mock_shutil):
        """Health check returns 503 when disk space < 10%."""
        mock_usage = MagicMock()
        mock_usage.total = 100 * (1024 ** 3)  # 100 GB
        mock_usage.free = 5 * (1024 ** 3)     # 5 GB (5% free)
        mock_shutil.disk_usage.return_value = mock_usage

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 503)
        data = response.json()

        self.assertEqual(data['status'], 'unhealthy')
        self.assertEqual(data['checks']['disk']['status'], 'unhealthy')
        self.assertIn('error', data['checks']['disk'])

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
```

**Coverage:**
- All services healthy (200 OK)
- Database failure (503)
- Redis failure (503)
- Redis get/set mismatch (503)
- Celery no workers (503)
- Celery healthy with worker count
- Celery disabled (dev mode)
- Disk warning threshold (200 OK with warning)
- Disk critical threshold (503)
- No authentication required
- Response time < 5 seconds

**Why mock approach:**
- Cannot reliably break database in tests (would break test runner)
- Cannot disable Redis without affecting cache-dependent tests
- Cannot control disk space in CI environment
- Mocking allows testing all failure scenarios
  </action>
  <verify>
```bash
# Run health check tests
python manage.py test upstream.api.tests.test_health_check -v 2

# Verify all tests pass
python manage.py test upstream.api.tests.test_health_check --parallel
```
  </verify>
  <done>Test file upstream/api/tests/test_health_check.py exists with 11+ tests covering all health check scenarios (healthy, database failure, redis failure, celery states, disk thresholds, no auth, response time). All tests pass.</done>
</task>

<task type="auto">
  <name>Task 3: Update deployment rollback script to use detailed health checks</name>
  <files>.github/scripts/validate_deployment.sh</files>
  <action>
Update the deployment validation script (created in quick-005) to leverage the detailed health checks:

**Find the health check validation section** (around line 40-50) and enhance it:

**Before:**
```bash
# Check basic health
RESPONSE=$(curl -s http://localhost:8000/api/health/)
if ! echo "$RESPONSE" | grep -q '"status":"healthy"'; then
    echo "Health check failed"
    exit 1
fi
```

**After:**
```bash
# Check detailed health with all services
RESPONSE=$(curl -s http://localhost:8000/api/health/)
STATUS=$(echo "$RESPONSE" | python -c "import sys, json; print(json.load(sys.stdin)['status'])" 2>/dev/null)

if [ "$STATUS" != "healthy" ]; then
    echo "❌ Health check failed. Detailed status:"
    echo "$RESPONSE" | python -m json.tool

    # Show which checks failed
    echo ""
    echo "Failed checks:"
    echo "$RESPONSE" | python -c "
import sys, json
data = json.load(sys.stdin)
for name, check in data.get('checks', {}).items():
    if check.get('status') == 'unhealthy':
        error = check.get('error', 'Unknown error')
        print(f'  - {name}: {error}')
    "
    exit 1
fi

# Verify all critical checks are healthy
CHECKS=$(echo "$RESPONSE" | python -c "
import sys, json
data = json.load(sys.stdin)
checks = data.get('checks', {})
healthy = all(
    check.get('status') in ['healthy', 'disabled', 'warning']
    for check in checks.values()
)
print('ok' if healthy else 'failed')
")

if [ "$CHECKS" != "ok" ]; then
    echo "❌ Some health checks are unhealthy"
    echo "$RESPONSE" | python -m json.tool
    exit 1
fi

echo "✓ All health checks passed (database, redis, celery, disk)"

# Show detailed metrics
echo "$RESPONSE" | python -c "
import sys, json
data = json.load(sys.stdin)
checks = data.get('checks', {})
print('  Database latency: {}ms'.format(checks.get('database', {}).get('latency_ms', 'N/A')))
print('  Redis latency: {}ms'.format(checks.get('redis', {}).get('latency_ms', 'N/A')))
print('  Celery workers: {}'.format(checks.get('celery', {}).get('workers', checks.get('celery', {}).get('status'))))
print('  Disk free: {}%'.format(checks.get('disk', {}).get('percent_free', 'N/A')))
"
```

**Why this enhancement:**
- Parses detailed check results to show WHICH service failed
- Accepts "warning" status (disk space warning is not a failure)
- Accepts "disabled" status (Celery may be off in some environments)
- Shows helpful metrics (latency, worker count, disk usage)
- Better error messages for debugging failed deployments
  </action>
  <verify>
```bash
# Verify script exists and has our enhanced logic
grep -q "Failed checks:" .github/scripts/validate_deployment.sh && echo "✓ Enhanced validation present"

# Check syntax
bash -n .github/scripts/validate_deployment.sh
```
  </verify>
  <done>Deployment validation script enhanced to parse detailed health check results, show which specific checks failed, and display helpful metrics (latency, workers, disk usage). Script accepts warning/disabled statuses as non-failures.</done>
</task>

</tasks>

<verification>
1. Health check endpoint responds at /api/health/
2. Response includes detailed checks: database, redis, celery, disk
3. Database check measures latency and catches connection errors
4. Redis check validates cache get/set operations
5. Celery check respects CELERY_ENABLED setting
6. Disk check has warning (20%) and critical (10%) thresholds
7. Overall status is "unhealthy" if ANY check fails
8. Returns 503 status code when unhealthy
9. Test suite covers all health check scenarios
10. Deployment validation script uses detailed health checks
</verification>

<success_criteria>
- [ ] curl http://localhost:8000/api/health/ returns JSON with checks.database, checks.redis, checks.celery, checks.disk
- [ ] Health check returns 503 when any service is unhealthy
- [ ] Health check returns 200 with warnings when disk < 20% but >= 10%
- [ ] Test suite has 11+ tests covering all scenarios
- [ ] python manage.py test upstream.api.tests.test_health_check passes with 0 failures
- [ ] Deployment validation script shows detailed check results
- [ ] Health check completes in < 5 seconds
- [ ] No authentication required to access health endpoint
</success_criteria>

<output>
After completion, create `.planning/quick/027-expand-health-check-endpoint-add-det/027-SUMMARY.md` documenting:
- Detailed health checks implemented (database, redis, celery, disk)
- Response format with status codes (200 vs 503)
- Test coverage (scenarios tested)
- Integration with deployment validation script
- Performance characteristics (latency measurements, timeout behavior)
</output>
