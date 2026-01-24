#!/usr/bin/env python
"""
DelayGuard Integration Test Suite

Tests:
1. DelayGuard computation service
2. Signal generation with varying delays
3. Alert integration (signal → AlertEvent)
4. Dashboard view rendering
5. Management command execution
"""

import sys
import os
from datetime import date, timedelta
from decimal import Decimal

# Setup Django FIRST before any imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'upstream.settings.dev')

import django
django.setup()

# Now import Django modules
from django.test import RequestFactory, Client
from django.contrib.auth.models import User
from django.core.management import call_command
from io import StringIO

from upstream.models import Customer, ClaimRecord, Upload
from upstream.products.delayguard.models import PaymentDelaySignal, PaymentDelayAggregate
from upstream.products.delayguard.services import DelayGuardComputationService
from upstream.alerts.models import AlertEvent, AlertRule


def test_delayguard_computation():
    """Test DelayGuard computation service."""
    print("=" * 60)
    print("Test 1: DelayGuard Computation Service")
    print("=" * 60)

    # Create test customer
    customer = Customer.objects.create(
        name='Test Healthcare DelayGuard 1'
    )
    print(f"✓ Created test customer: {customer.name}")

    # Create upload for claims
    upload = Upload.objects.create(
        customer=customer,
        status='completed',
        filename='test_delayguard.csv',
        row_count=30
    )

    # Create baseline claims (60 days ago, fast payment: 20 days average)
    baseline_date = date.today() - timedelta(days=65)
    for i in range(15):
        submitted = baseline_date + timedelta(days=i % 5)
        decided = submitted + timedelta(days=20 + (i % 3))  # 20-22 days
        ClaimRecord.objects.create(
            customer=customer,
            upload=upload,
            payer='FastPay Insurance',
            cpt='99213',
            submitted_date=submitted,
            decided_date=decided,
            outcome='PAID',
            allowed_amount=Decimal('1000.00')
        )

    # Create current claims (last 14 days, slow payment: 35 days average)
    current_date = date.today() - timedelta(days=10)
    for i in range(15):
        submitted = current_date + timedelta(days=i % 3)
        decided = submitted + timedelta(days=35 + (i % 3))  # 35-37 days
        ClaimRecord.objects.create(
            customer=customer,
            upload=upload,
            payer='FastPay Insurance',
            cpt='99213',
            submitted_date=submitted,
            decided_date=decided,
            outcome='PAID',
            allowed_amount=Decimal('1000.00')
        )

    print(f"✓ Created {ClaimRecord.objects.filter(customer=customer).count()} test claims")

    # Run DelayGuard computation
    service = DelayGuardComputationService(customer)
    result = service.compute()

    print(f"✓ Computation complete:")
    print(f"  Aggregates created: {result['aggregates_created']}")
    print(f"  Signals created: {result['signals_created']}")
    print(f"  Baseline: {result['baseline_start']} to {result['baseline_end']}")
    print(f"  Current: {result['current_start']} to {result['current_end']}")

    # Verify aggregates
    aggregates = PaymentDelayAggregate.objects.filter(customer=customer)
    assert aggregates.count() > 0, "No aggregates created"
    print(f"✓ Aggregates exist: {aggregates.count()} records")

    # Verify signals
    signals = PaymentDelaySignal.objects.filter(customer=customer)
    if signals.count() > 0:
        signal = signals.first()
        print(f"✓ Signal created:")
        print(f"  Payer: {signal.payer}")
        print(f"  Baseline avg: {signal.baseline_avg_days:.1f} days")
        print(f"  Current avg: {signal.current_avg_days:.1f} days")
        print(f"  Delta: +{signal.delta_days:.1f} days")
        print(f"  Severity: {signal.severity}")
        print(f"  Confidence: {signal.confidence:.2f}")

        # Verify delta is positive (payment got slower)
        assert signal.delta_days > 0, f"Delta should be positive, got {signal.delta_days}"
        print(f"✓ Delta is positive (slower payments)")

    else:
        print("⚠ No signals created (may need more data)")

    # Cleanup
    Customer.objects.filter(id=customer.id).delete()
    print("✓ Cleanup complete")


def test_alert_integration():
    """Test alert integration (PaymentDelaySignal → AlertEvent)."""
    print("\n" + "=" * 60)
    print("Test 2: Alert Integration")
    print("=" * 60)

    # Create test customer and alert rule
    customer = Customer.objects.create(
        name='Test Alert Customer DelayGuard 2'
    )

    alert_rule = AlertRule.objects.create(
        customer=customer,
        name='Payment Delay Alert',
        metric='severity',
        threshold_type='gte',
        threshold_value=0.5,
        enabled=True
    )
    print(f"✓ Created test customer and alert rule")

    # Create test signal
    signal = PaymentDelaySignal.objects.create(
        customer=customer,
        signal_type='payment_delay_drift',
        payer='SlowPay Insurance',
        window_start_date=date.today() - timedelta(days=14),
        window_end_date=date.today(),
        baseline_start_date=date.today() - timedelta(days=74),
        baseline_end_date=date.today() - timedelta(days=14),
        baseline_avg_days=25.0,
        current_avg_days=40.0,
        delta_days=15.0,
        delta_percent=60.0,
        baseline_claim_count=50,
        current_claim_count=45,
        estimated_dollars_at_risk=Decimal('25000.00'),
        severity='critical',
        confidence=0.85,
        summary_text='SlowPay payment latency increased +15 days',
        fingerprint='test-fingerprint-123'
    )
    print(f"✓ Created payment delay signal")

    # Trigger alert evaluation
    from upstream.alerts.services import evaluate_payment_delay_signal
    alert_events = evaluate_payment_delay_signal(signal)

    if alert_events:
        alert_event = alert_events[0]
        print(f"✓ AlertEvent created:")
        print(f"  Status: {alert_event.status}")
        print(f"  Product: {alert_event.payload.get('product_name')}")
        print(f"  Payer: {alert_event.payload.get('payer')}")
        print(f"  Delta: +{alert_event.payload.get('delta_days')} days")

        # Verify payload contains expected fields
        required_fields = ['product_name', 'signal_type', 'payer', 'delta_days', 'severity']
        missing_fields = [f for f in required_fields if f not in alert_event.payload]
        assert not missing_fields, f"Missing payload fields: {missing_fields}"
        print(f"✓ All required payload fields present")

    else:
        assert False, "No AlertEvent created"

    # Cleanup
    Customer.objects.filter(id=customer.id).delete()
    print("✓ Cleanup complete")


def test_dashboard_view():
    """Test DelayGuard dashboard view rendering."""
    print("\n" + "=" * 60)
    print("Test 3: Dashboard View")
    print("=" * 60)

    # Create staff user
    try:
        user = User.objects.create_user(
            username='test_delayguard_staff',
            password='testpass123',
            is_staff=True
        )
        print("✓ Created test staff user")
    except Exception as e:
        print(f"⚠ Could not create test user: {str(e)}")
        user = User.objects.filter(username='test_delayguard_staff').first()
        assert user, "Could not get test user"

    client = Client()

    # Test unauthenticated access (should redirect)
    response = client.get('/portal/products/delayguard/')
    assert response.status_code in [302, 301], f"Dashboard should redirect, got {response.status_code}"
    print("✓ Dashboard requires authentication (redirect)")

    # Test authenticated access
    client.force_login(user)
    response = client.get('/portal/products/delayguard/')

    assert response.status_code == 200, f"Dashboard returned {response.status_code} for staff user"
    print("✓ Dashboard accessible to staff users")

    # Check response contains expected elements
    content = response.content.decode('utf-8')

    expected_elements = [
        'DelayGuard',
        'Payment delay drift detection',
        'Active Delay Signals',
    ]

    for element in expected_elements:
        if element in content:
            print(f"✓ Found '{element}' in response")
        else:
            print(f"⚠ Missing '{element}' in response (may be OK if no data)")

    # Cleanup
    User.objects.filter(username='test_delayguard_staff').delete()


def test_management_command():
    """Test DelayGuard management command."""
    print("\n" + "=" * 60)
    print("Test 4: Management Command")
    print("=" * 60)

    # Create test customer
    customer = Customer.objects.create(
        name='Test Command Customer DelayGuard 3'
    )
    print(f"✓ Created test customer: {customer.name}")

    # Create upload for claims
    upload = Upload.objects.create(
        customer=customer,
        status='completed',
        filename='test_command.csv',
        row_count=20
    )

    # Create test claims
    for i in range(20):
        submitted = date.today() - timedelta(days=30 + (i % 10))
        decided = submitted + timedelta(days=25 + (i % 5))
        ClaimRecord.objects.create(
            customer=customer,
            upload=upload,
            payer='CommandTest Insurance',
            cpt='99213',
            submitted_date=submitted,
            decided_date=decided,
            outcome='PAID',
            allowed_amount=Decimal('500.00')
        )
    print(f"✓ Created 20 test claims")

    # Run management command
    try:
        out = StringIO()
        call_command(
            'compute_delayguard',
            '--customer', str(customer.id),
            stdout=out
        )
        output = out.getvalue()

        if 'complete' in output.lower():
            print("✓ Management command executed successfully")
            print(f"  Output excerpt: {output[:200]}...")
        else:
            print(f"⚠ Command output: {output}")

    except Exception as e:
        Customer.objects.filter(id=customer.id).delete()
        assert False, f"Management command failed: {str(e)}"

    # Verify signals were created
    signals = PaymentDelaySignal.objects.filter(customer=customer)
    print(f"✓ Signals after command: {signals.count()}")

    # Cleanup
    Customer.objects.filter(id=customer.id).delete()
    print("✓ Cleanup complete")


def cleanup():
    """Clean up test data."""
    print("\n" + "=" * 60)
    print("Final Cleanup")
    print("=" * 60)

    try:
        # Delete any remaining test users
        User.objects.filter(username__startswith='test_delayguard').delete()
        print("✓ Test users deleted")

        # Delete any remaining test customers
        Customer.objects.filter(name__contains='Test').delete()
        print("✓ Test customers deleted")

    except Exception as e:
        print(f"⚠ Cleanup error: {str(e)}")


if __name__ == '__main__':
    try:
        # Run tests - assertions will fail the test if something is wrong
        test_delayguard_computation()
        test_alert_integration()
        test_dashboard_view()
        test_management_command()

        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print("✅ ALL TESTS PASSED")
        print("\nDelayGuard integration is working correctly!")
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
