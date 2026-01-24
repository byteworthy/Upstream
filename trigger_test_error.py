#!/usr/bin/env python
"""
Trigger a test error to verify Sentry integration.

This script triggers a test exception to verify that Sentry is properly
configured and receiving error reports.

Usage:
    python trigger_test_error.py

WARNING: Only run this in a test/staging environment or after configuring
a test Sentry project. Do not spam production Sentry with test errors.
"""

import sys
import os

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'payrixa.settings.prod')
import django
django.setup()

def trigger_test_error():
    """Trigger a test exception to verify Sentry integration."""

    print("Triggering test error for Sentry verification...")
    print("=" * 60)

    # Check if Sentry is configured
    from django.conf import settings
    sentry_configured = hasattr(settings, 'SENTRY_DSN') and settings.SENTRY_DSN

    if not sentry_configured:
        print("⚠️  Sentry is NOT configured.")
        print("\nTo configure Sentry:")
        print("1. Add SENTRY_DSN to your .env.production file")
        print("2. Restart the application")
        print("\nExample:")
        print("SENTRY_DSN=https://your-key@o123456.ingest.sentry.io/789012")
        return

    print("✅ Sentry DSN is configured")
    print(f"   Environment: {os.environ.get('ENVIRONMENT', 'not set')}")
    print(f"   Release: {os.environ.get('SENTRY_RELEASE', 'not set')}")

    # Trigger a test exception
    print("\n🚀 Triggering test exception...")
    print("   Check your Sentry dashboard for this error:")
    print("   https://sentry.io/organizations/your-org/issues/")
    print()

    try:
        # Trigger a division by zero error
        result = 1 / 0
    except ZeroDivisionError as e:
        # Capture the exception
        import sentry_sdk
        sentry_sdk.capture_exception(e)

        print("✅ Test exception captured and sent to Sentry")
        print("\n📧 You should receive an email notification (if configured)")
        print("📊 Check your Sentry dashboard to see the error report")
        print()
        print("If you don't see the error in Sentry:")
        print("- Check that SENTRY_DSN is correct")
        print("- Verify your Sentry project settings")
        print("- Check application logs for Sentry connection errors")

if __name__ == '__main__':
    trigger_test_error()
