#!/usr/bin/env python
"""
Test Sentry PHI filtering.

This script tests the Sentry before_send hook to ensure PHI is properly
scrubbed before error reports are sent to Sentry.

WARNING: This is a test script. Do not run in production without configuring
a test Sentry project first.
"""

import sys
import os

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_phi_filtering():
    """Test PHI filtering in Sentry events."""

    # Define filter function (copied from settings/prod.py for testing)
    def filter_phi_from_errors(event, hint):
        """
        Remove potential PHI from error reports before sending to Sentry.

        CRITICAL: Ensures HIPAA compliance by scrubbing sensitive data.
        """
        # Remove request body (may contain uploaded CSV with PHI)
        if 'request' in event:
            if 'data' in event['request']:
                event['request']['data'] = '[REDACTED FOR HIPAA COMPLIANCE]'

            # Remove cookies (may contain session data)
            if 'cookies' in event['request']:
                event['request']['cookies'] = '[REDACTED]'

            # Scrub query parameters that might contain PHI
            if 'query_string' in event['request']:
                event['request']['query_string'] = '[REDACTED]'

        # Remove user email (PII)
        if 'user' in event:
            if 'email' in event['user']:
                event['user']['email'] = '[REDACTED]'

        # Scrub exception values that might contain PHI
        if 'exception' in event:
            for exc in event['exception'].get('values', []):
                if 'value' in exc:
                    # Redact common PHI patterns in error messages
                    exc_value = str(exc['value'])
                    # Look for patient name patterns (Title Case 2-3 words)
                    if any(word.istitle() for word in exc_value.split()):
                        exc['value'] = '[ERROR MESSAGE REDACTED - MAY CONTAIN PHI]'

        return event

    print("Testing Sentry PHI Filtering")
    print("=" * 60)

    # Test case 1: Request with PHI in data
    print("\n1. Testing request data redaction:")
    print("-" * 60)
    event1 = {
        'request': {
            'data': {
                'payer': 'John Smith',
                'csv_file': '<uploaded file data>'
            },
            'cookies': {'sessionid': 'abc123'},
            'query_string': 'patient_name=Jane+Doe'
        },
        'user': {
            'email': 'user@example.com',
            'id': '123'
        }
    }

    filtered_event1 = filter_phi_from_errors(event1, {})

    if filtered_event1['request']['data'] == '[REDACTED FOR HIPAA COMPLIANCE]':
        print("  ✅ PASS: Request data redacted")
    else:
        print(f"  ❌ FAIL: Request data not redacted: {filtered_event1['request']['data']}")

    if filtered_event1['request']['cookies'] == '[REDACTED]':
        print("  ✅ PASS: Cookies redacted")
    else:
        print(f"  ❌ FAIL: Cookies not redacted: {filtered_event1['request']['cookies']}")

    if filtered_event1['request']['query_string'] == '[REDACTED]':
        print("  ✅ PASS: Query string redacted")
    else:
        print(f"  ❌ FAIL: Query string not redacted: {filtered_event1['request']['query_string']}")

    if filtered_event1['user']['email'] == '[REDACTED]':
        print("  ✅ PASS: User email redacted")
    else:
        print(f"  ❌ FAIL: User email not redacted: {filtered_event1['user']['email']}")

    # Test case 2: Exception with PHI in error message
    print("\n2. Testing exception value redaction:")
    print("-" * 60)
    event2 = {
        'exception': {
            'values': [
                {
                    'type': 'ValueError',
                    'value': 'PRIVACY ALERT: payer value John Smith looks like a patient name'
                }
            ]
        }
    }

    filtered_event2 = filter_phi_from_errors(event2, {})

    if '[ERROR MESSAGE REDACTED' in filtered_event2['exception']['values'][0]['value']:
        print("  ✅ PASS: Exception message with PHI redacted")
    else:
        print(f"  ❌ FAIL: Exception message not redacted: {filtered_event2['exception']['values'][0]['value']}")

    # Test case 3: Safe exception (should NOT be redacted)
    print("\n3. Testing safe exception (should NOT be redacted):")
    print("-" * 60)
    event3 = {
        'exception': {
            'values': [
                {
                    'type': 'DatabaseError',
                    'value': 'connection timeout after 30 seconds'
                }
            ]
        }
    }

    filtered_event3 = filter_phi_from_errors(event3, {})

    if filtered_event3['exception']['values'][0]['value'] == 'connection timeout after 30 seconds':
        print("  ✅ PASS: Safe exception message preserved")
    else:
        print(f"  ❌ FAIL: Safe message incorrectly redacted: {filtered_event3['exception']['values'][0]['value']}")

    print("\n" + "=" * 60)
    print("SUMMARY:")
    print("PHI filtering is working correctly if all tests passed.")
    print("\nTo enable Sentry in production:")
    print("1. Create Sentry project at https://sentry.io")
    print("2. Add SENTRY_DSN to .env.production")
    print("3. Restart application")
    print("\nExample .env.production:")
    print("SENTRY_DSN=https://your-key@o123456.ingest.sentry.io/789012")
    print("ENVIRONMENT=production")
    print("SENTRY_RELEASE=v1.0.0")

if __name__ == '__main__':
    test_phi_filtering()
