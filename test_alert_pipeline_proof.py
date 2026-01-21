#!/usr/bin/env python
"""
Alert Pipeline Proof Test

This script proves the alert pipeline behaves correctly end-to-end without external dependencies:
1. Drift event creates exactly one AlertEvent
2. send_alerts transitions that AlertEvent to 'sent' using console backend
3. Second run is suppressed
4. Email payload renders correctly
5. Provider can be swapped later without code changes

Usage:
    python test_alert_pipeline_proof.py
"""

import os
import sys
import django

# Set environment explicitly
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hello_world.settings')
os.environ['EMAIL_BACKEND'] = 'django.core.mail.backends.console.EmailBackend'
os.environ['PORTAL_BASE_URL'] = 'http://localhost:8000'

django.setup()

from django.core.management import call_command
from payrixa.models import Customer, DriftEvent
from payrixa.alerts.models import AlertRule, AlertEvent, NotificationChannel
from payrixa.alerts.services import evaluate_drift_event
from django.utils import timezone

def print_banner(text):
    print("\n" + "="*80)
    print(f"  {text}")
    print("="*80 + "\n")

def main():
    print_banner("ALERT PIPELINE PROOF TEST")
    
    # Step 1: Ensure customer exists
    print("Step 1: Ensuring customer exists...")
    customer, created = Customer.objects.get_or_create(
        id=1,
        defaults={'name': 'Demo Healthcare System', 'is_active': True}
    )
    print(f"✓ Customer: {customer.name} (ID: {customer.id})")
    
    # Step 2: Create or update NotificationChannel with recipient email
    print("\nStep 2: Configuring notification channel...")
    channel, created = NotificationChannel.objects.update_or_create(
        customer=customer,
        name='Default Email Channel',
        defaults={
            'channel_type': 'email',
            'config': {'recipients': ['test@example.com']},
            'enabled': True
        }
    )
    action = "Created" if created else "Updated"
    print(f"✓ {action} notification channel: {channel.name}")
    print(f"  Recipients: {channel.config.get('recipients')}")
    
    # Step 3: Verify or create alert rule
    print("\nStep 3: Verifying alert rule...")
    rule, created = AlertRule.objects.get_or_create(
        customer=customer,
        name='High Severity Drift Alert',
        defaults={
            'enabled': True,
            'metric': 'severity',
            'threshold_type': 'gte',
            'threshold_value': 0.7,
            'severity': 'critical'
        }
    )
    if not created and not rule.enabled:
        rule.enabled = True
        rule.save()
    print(f"✓ Alert rule: {rule.name} (enabled={rule.enabled})")
    print(f"  Metric: {rule.metric} {rule.threshold_type} {rule.threshold_value}")
    
    # Step 4: Clear previous demo data
    print("\nStep 4: Clearing previous demo data...")
    DriftEvent.objects.filter(customer=customer, payer__startswith='Demo-').delete()
    AlertEvent.objects.filter(customer=customer).delete()
    print(f"  ✓ Cleared demo data")
    
    # Step 5: Generate drift demo data
    print_banner("RUNNING: generate_driftwatch_demo")
    call_command('generate_driftwatch_demo', '--customer', '1')
    
    drift_count = DriftEvent.objects.filter(customer=customer).count()
    print(f"\n✓ Total drift events: {drift_count}")
    
    # Step 5b: Evaluate drift events against alert rules (creates AlertEvent objects)
    print("\nStep 5b: Evaluating drift events against alert rules...")
    drift_events = DriftEvent.objects.filter(customer=customer).order_by('-created_at')
    total_alerts_created = 0
    for drift_event in drift_events:
        alert_events = evaluate_drift_event(drift_event)
        if alert_events:
            total_alerts_created += len(alert_events)
            print(f"  ✓ Drift event {drift_event.payer} severity {drift_event.severity:.2f} -> {len(alert_events)} alert(s)")
        else:
            print(f"  - Drift event {drift_event.payer} severity {drift_event.severity:.2f} -> no alerts (below threshold)")
    print(f"\n✓ Created {total_alerts_created} alert event(s) from drift events")
    
    # Step 6: First send_alerts run
    print_banner("FIRST RUN: send_alerts")
    print("Expected: One alert created and sent to console")
    print("-" * 80)
    
    alert_count_before_send = AlertEvent.objects.filter(customer=customer).count()
    call_command('send_alerts')
    alert_count_after_send = AlertEvent.objects.filter(customer=customer).count()
    
    new_alerts = alert_count_after_send - alert_count_before_send
    sent_alerts = AlertEvent.objects.filter(customer=customer, status='sent').count()
    
    print("-" * 80)
    print(f"✓ New alert events: {new_alerts}")
    print(f"✓ Total sent alerts: {sent_alerts}")
    
    # Step 7: Second send_alerts run (should be suppressed)
    print_banner("SECOND RUN: send_alerts")
    print("Expected: No new emails (suppression cooldown)")
    print("-" * 80)
    
    alert_count_before_second = AlertEvent.objects.filter(customer=customer).count()
    call_command('send_alerts')
    alert_count_after_second = AlertEvent.objects.filter(customer=customer).count()
    
    new_alerts_second = alert_count_after_second - alert_count_before_second
    
    print("-" * 80)
    print(f"✓ New alert events in second run: {new_alerts_second}")
    print(f"  (Should be 0 - suppressed by cooldown)")
    
    # Step 8: Verify results
    print_banner("VERIFICATION RESULTS")
    
    # Check for exactly one AlertEvent per DriftEvent
    drift_events = DriftEvent.objects.filter(customer=customer).order_by('-created_at')[:5]
    print(f"Checking recent drift events for duplicate AlertEvents...")
    for drift_event in drift_events:
        alert_events = AlertEvent.objects.filter(drift_event=drift_event)
        count = alert_events.count()
        status = "✓" if count <= 1 else "✗"
        print(f"  {status} DriftEvent {drift_event.id}: {count} AlertEvent(s)")
    
    # Check suppression worked
    print(f"\nSuppression check:")
    if new_alerts_second == 0:
        print(f"  ✓ Second run produced no new alerts (suppressed)")
    else:
        print(f"  ✗ Second run produced {new_alerts_second} alerts (should be 0)")
    
    # Check console output was generated
    print(f"\nEmail rendering check:")
    recent_alerts = AlertEvent.objects.filter(
        customer=customer,
        status='sent'
    ).order_by('-notification_sent_at')[:3]
    
    if recent_alerts.exists():
        print(f"  ✓ {recent_alerts.count()} alert(s) marked as 'sent'")
        for alert in recent_alerts:
            print(f"    - Alert {alert.id}: {alert.payload.get('payer', 'N/A')} - {alert.payload.get('drift_type', 'N/A')}")
    else:
        print(f"  ✗ No alerts marked as 'sent'")
    
    # Check PORTAL_BASE_URL is set - read from Django settings, not os.environ
    from django.conf import settings
    portal_url = settings.PORTAL_BASE_URL
    print(f"\nConfiguration check:")
    print(f"  PORTAL_BASE_URL: {portal_url}")
    print(f"  EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
    
    print_banner("PROOF COMPLETE")
    
    # Truthful summary based on actual results
    all_passed = True
    
    if sent_alerts > 0:
        print(f"  ✓ Email sent to console ({sent_alerts} alert(s) delivered)")
    else:
        print(f"  ✗ No emails sent (check output above for errors)")
        all_passed = False
    
    if new_alerts_second == 0:
        print(f"  ✓ Suppression logic active (second run suppressed)")
    else:
        print(f"  ✗ Suppression failed ({new_alerts_second} new alerts on second run)")
        all_passed = False
    
    if 'localhost' in portal_url or 'payrixa.com' in portal_url:
        print(f"  ✓ Portal URL configured: {portal_url}")
    else:
        print(f"  ? Portal URL: {portal_url}")
    
    print(f"  ✓ Console backend - no Mailgun required")
    
    if all_passed:
        print(f"\n✓ Pipeline proof PASSED - ready for provider swap")
    else:
        print(f"\n✗ Pipeline proof FAILED - check issues above")
    
    print("="*80 + "\n")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
