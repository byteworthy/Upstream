#!/usr/bin/env python
"""
Smoke Test Suite for Staging Environment

Quick validation tests to run after deployment to verify:
1. Application is running
2. Database connectivity
3. Redis cache connectivity
4. Critical pages load
5. Authentication works
6. Product dashboards accessible
7. API endpoints respond

Usage:
    python smoke_tests.py --env staging
    python smoke_tests.py --env production --critical-only
"""

import sys
import os
import argparse
import requests
import time
from datetime import datetime

# Django setup for database tests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'upstream.settings.prod')

import django
django.setup()

from django.conf import settings
from django.db import connection
from django.core.cache import cache
from django.contrib.auth.models import User


class SmokeTestRunner:
    """Run smoke tests against deployed environment."""

    def __init__(self, base_url, critical_only=False):
        self.base_url = base_url.rstrip('/')
        self.critical_only = critical_only
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.results = []

    def run_all(self):
        """Run all smoke tests."""
        print("=" * 70)
        print(f"🔥 SMOKE TESTS - {self.base_url}")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)

        # Critical tests (always run)
        self.test_health_endpoint()
        self.test_database_connection()
        self.test_redis_connection()
        self.test_home_page()
        self.test_login_page()

        if not self.critical_only:
            # Non-critical tests
            self.test_static_files()
            self.test_admin_page()
            self.test_api_health()
            self.test_product_dashboards()
            self.test_migrations_applied()

        self.print_summary()
        return self.failed == 0

    def test_health_endpoint(self):
        """Test /health/ endpoint responds."""
        print("\n[TEST] Health endpoint...")
        try:
            response = requests.get(f"{self.base_url}/health/", timeout=5)

            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'healthy':
                    self.pass_test("Health endpoint OK", data)
                else:
                    self.fail_test("Health endpoint returned unhealthy status", data)
            else:
                self.fail_test(f"Health endpoint returned {response.status_code}")

        except Exception as e:
            self.fail_test(f"Health endpoint failed: {str(e)}")

    def test_database_connection(self):
        """Test database connection works."""
        print("\n[TEST] Database connection...")
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()

                if result == (1,):
                    self.pass_test(f"Database connected ({connection.vendor})")
                else:
                    self.fail_test("Database query returned unexpected result")

        except Exception as e:
            self.fail_test(f"Database connection failed: {str(e)}")

    def test_redis_connection(self):
        """Test Redis cache connection."""
        print("\n[TEST] Redis cache connection...")
        try:
            # Try to set and get a test value
            test_key = 'smoke_test_key'
            test_value = f'smoke_test_{int(time.time())}'

            cache.set(test_key, test_value, 60)
            retrieved = cache.get(test_key)

            if retrieved == test_value:
                self.pass_test("Redis cache operational")
                cache.delete(test_key)
            else:
                self.warn_test("Redis cache not working, falling back to local cache")

        except Exception as e:
            self.warn_test(f"Redis connection issue: {str(e)}")

    def test_home_page(self):
        """Test home page loads."""
        print("\n[TEST] Home page...")
        try:
            response = requests.get(f"{self.base_url}/", timeout=10)

            if response.status_code == 200:
                self.pass_test("Home page loads")
            elif response.status_code in [301, 302]:
                self.pass_test(f"Home page redirects to {response.headers.get('Location')}")
            else:
                self.fail_test(f"Home page returned {response.status_code}")

        except Exception as e:
            self.fail_test(f"Home page failed: {str(e)}")

    def test_login_page(self):
        """Test login page loads."""
        print("\n[TEST] Login page...")
        try:
            response = requests.get(f"{self.base_url}/accounts/login/", timeout=10)

            if response.status_code == 200:
                if 'login' in response.text.lower() or 'username' in response.text.lower():
                    self.pass_test("Login page loads with form")
                else:
                    self.fail_test("Login page loads but form not found")
            else:
                self.fail_test(f"Login page returned {response.status_code}")

        except Exception as e:
            self.fail_test(f"Login page failed: {str(e)}")

    def test_static_files(self):
        """Test static files are accessible."""
        print("\n[TEST] Static files...")
        try:
            # Try to access common static file
            response = requests.get(f"{self.base_url}/static/upstream/css/style.css", timeout=5)

            if response.status_code == 200:
                self.pass_test("Static files accessible")
            elif response.status_code == 404:
                self.warn_test("Static file not found (may need collectstatic)")
            else:
                self.fail_test(f"Static files returned {response.status_code}")

        except Exception as e:
            self.warn_test(f"Static files check failed: {str(e)}")

    def test_admin_page(self):
        """Test Django admin loads."""
        print("\n[TEST] Admin page...")
        try:
            response = requests.get(f"{self.base_url}/admin/", timeout=10)

            if response.status_code in [200, 302]:
                self.pass_test("Admin page accessible")
            else:
                self.fail_test(f"Admin page returned {response.status_code}")

        except Exception as e:
            self.fail_test(f"Admin page failed: {str(e)}")

    def test_api_health(self):
        """Test API health endpoint."""
        print("\n[TEST] API health...")
        try:
            response = requests.get(f"{self.base_url}/api/health/", timeout=5)

            if response.status_code == 200:
                self.pass_test("API health endpoint OK")
            elif response.status_code == 404:
                self.warn_test("API health endpoint not found (may not be implemented)")
            else:
                self.fail_test(f"API health returned {response.status_code}")

        except Exception as e:
            self.warn_test(f"API health check skipped: {str(e)}")

    def test_product_dashboards(self):
        """Test product dashboard pages load (with authentication required)."""
        print("\n[TEST] Product dashboards...")

        dashboards = [
            '/portal/products/axis/',
            '/portal/products/driftwatch/',
            '/portal/products/denialscope/',
            '/portal/products/delayguard/',
        ]

        accessible = 0
        requires_auth = 0

        for path in dashboards:
            try:
                response = requests.get(f"{self.base_url}{path}", timeout=5, allow_redirects=False)

                if response.status_code in [301, 302]:
                    # Should redirect to login
                    requires_auth += 1
                elif response.status_code == 200:
                    accessible += 1

            except Exception:
                pass

        if requires_auth == len(dashboards):
            self.pass_test(f"All {len(dashboards)} product dashboards require authentication")
        elif accessible > 0:
            self.warn_test(f"{accessible}/{len(dashboards)} dashboards accessible without auth")
        else:
            self.fail_test("Product dashboards not accessible")

    def test_migrations_applied(self):
        """Test database migrations are applied."""
        print("\n[TEST] Database migrations...")
        try:
            from django.db.migrations.executor import MigrationExecutor

            executor = MigrationExecutor(connection)
            plan = executor.migration_plan(executor.loader.graph.leaf_nodes())

            if not plan:
                self.pass_test("All migrations applied")
            else:
                pending = len(plan)
                self.fail_test(f"{pending} migrations pending")

        except Exception as e:
            self.warn_test(f"Migration check failed: {str(e)}")

    def pass_test(self, message, details=None):
        """Mark test as passed."""
        self.passed += 1
        print(f"  ✅ PASS: {message}")
        if details:
            print(f"     Details: {details}")
        self.results.append(('PASS', message))

    def fail_test(self, message, details=None):
        """Mark test as failed."""
        self.failed += 1
        print(f"  ❌ FAIL: {message}")
        if details:
            print(f"     Details: {details}")
        self.results.append(('FAIL', message))

    def warn_test(self, message):
        """Mark test as warning."""
        self.warnings += 1
        print(f"  ⚠️  WARN: {message}")
        self.results.append(('WARN', message))

    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 70)
        print("SMOKE TEST SUMMARY")
        print("=" * 70)

        total = self.passed + self.failed + self.warnings

        print(f"Total Tests: {total}")
        print(f"  ✅ Passed:   {self.passed}")
        print(f"  ❌ Failed:   {self.failed}")
        print(f"  ⚠️  Warnings: {self.warnings}")

        if self.failed == 0:
            print("\n🎉 All critical tests passed! Deployment looks good.")
        else:
            print(f"\n⚠️  {self.failed} test(s) failed. Review before proceeding.")

        print("=" * 70)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Run smoke tests against deployed environment')
    parser.add_argument('--env', choices=['local', 'staging', 'production'], default='local',
                        help='Environment to test')
    parser.add_argument('--url', type=str, help='Custom base URL')
    parser.add_argument('--critical-only', action='store_true',
                        help='Run only critical tests')

    args = parser.parse_args()

    # Determine base URL
    if args.url:
        base_url = args.url
    elif args.env == 'local':
        base_url = 'http://localhost:8000'
    elif args.env == 'staging':
        base_url = os.getenv('STAGING_URL', 'https://staging.upstream.cx')
    elif args.env == 'production':
        base_url = os.getenv('PRODUCTION_URL', 'https://upstream.cx')
    else:
        print("Error: Could not determine base URL")
        sys.exit(1)

    print(f"Environment: {args.env}")
    print(f"Base URL: {base_url}")

    # Run tests
    runner = SmokeTestRunner(base_url, critical_only=args.critical_only)
    success = runner.run_all()

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
