"""Alert services for evaluating drift events and sending notifications."""
import logging
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from .models import AlertRule, AlertEvent, NotificationChannel
from payrixa.models import DriftEvent

logger = logging.getLogger(__name__)

def evaluate_drift_event(drift_event):
    """Evaluate a drift event against all active alert rules for the customer."""
    alert_events = []
    alert_rules = AlertRule.objects.filter(customer=drift_event.customer, enabled=True)
    for rule in alert_rules:
        if rule.evaluate(drift_event):
            payload = {
                'payer': drift_event.payer, 'cpt_group': drift_event.cpt_group, 'drift_type': drift_event.drift_type,
                'baseline_value': drift_event.baseline_value, 'current_value': drift_event.current_value,
                'delta_value': drift_event.delta_value, 'severity': drift_event.severity,
                'rule_name': rule.name, 'rule_threshold': rule.threshold_value,
            }
            alert_event = AlertEvent.objects.create(
                customer=drift_event.customer, alert_rule=rule, drift_event=drift_event,
                report_run=drift_event.report_run, triggered_at=timezone.now(), status='pending', payload=payload
            )
            alert_events.append(alert_event)
            logger.info(f"Alert triggered: {rule.name} for drift event {drift_event.id}")
    return alert_events

def send_alert_notification(alert_event):
    """Send notification for an alert event via configured channels."""
    customer = alert_event.customer
    channels = NotificationChannel.objects.filter(customer=customer, enabled=True)
    success = False
    for channel in channels:
        if channel.channel_type == 'email':
            success = send_email_notification(alert_event, channel)
    if not channels.exists():
        success = send_default_email_notification(alert_event)
    if success:
        alert_event.status = 'sent'
        alert_event.notification_sent_at = timezone.now()
        alert_event.save()
    return success

def send_email_notification(alert_event, channel):
    """Send email notification for an alert event."""
    config = channel.config or {}
    recipients = config.get('recipients', [])
    if not recipients:
        return False
    payload = alert_event.payload
    subject = f"[Payrixa Alert] {alert_event.alert_rule.name} - {payload.get('payer', 'Unknown')}"
    message = f"Alert: {alert_event.alert_rule.name}\nPayer: {payload.get('payer', 'N/A')}\nDrift Type: {payload.get('drift_type', 'N/A')}\nSeverity: {payload.get('severity', 'N/A')}\nTriggered at: {alert_event.triggered_at}"
    send_mail(subject=subject, message=message, from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'alerts@payrixa.com'), recipient_list=recipients, fail_silently=False)
    return True

def send_default_email_notification(alert_event):
    """Send email notification using default settings."""
    recipients = [getattr(settings, 'DEFAULT_ALERT_EMAIL', 'alerts@example.com')]
    payload = alert_event.payload
    subject = f"[Payrixa Alert] {alert_event.alert_rule.name}"
    message = f"Alert: {alert_event.alert_rule.name}\nPayer: {payload.get('payer', 'N/A')}\nSeverity: {payload.get('severity', 'N/A')}"
    send_mail(subject=subject, message=message, from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'alerts@payrixa.com'), recipient_list=recipients, fail_silently=False)
    return True

def process_pending_alerts():
    """Process all pending alert events and send notifications."""
    pending_alerts = AlertEvent.objects.filter(status='pending')
    results = {'total': pending_alerts.count(), 'sent': 0, 'failed': 0}
    for alert_event in pending_alerts:
        try:
            if send_alert_notification(alert_event):
                results['sent'] += 1
            else:
                results['failed'] += 1
        except Exception as e:
            logger.error(f"Error processing alert {alert_event.id}: {str(e)}")
            results['failed'] += 1
    return results
