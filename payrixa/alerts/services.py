"""Alert services for evaluating drift events and sending notifications."""
from typing import List, Dict, Optional, Union, Any
import logging
import os
import uuid
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from .models import AlertRule, AlertEvent, NotificationChannel
from payrixa.models import DriftEvent, Customer
from payrixa.services.evidence_payload import build_driftwatch_evidence_payload, get_alert_interpretation

logger = logging.getLogger(__name__)

ALERT_SUPPRESSION_COOLDOWN = timezone.timedelta(hours=4)

def evaluate_drift_event(drift_event):
    """Evaluate a drift event against all active alert rules for the customer."""
    from payrixa.core.services import create_audit_event
    
    alert_events = []
    alert_rules = AlertRule.objects.filter(customer=drift_event.customer, enabled=True)
    for rule in alert_rules:
        if rule.evaluate(drift_event):
            # Check for duplicate alert event to prevent re-creation
            existing = AlertEvent.objects.filter(
                drift_event=drift_event,
                alert_rule=rule
            ).first()
            
            if existing:
                logger.info(f"Alert event already exists for rule {rule.name} and drift event {drift_event.id}")
                alert_events.append(existing)
                continue
            
            payload = {
                'product_name': 'DriftWatch',
                'signal_type': drift_event.drift_type,
                'entity_label': drift_event.payer,
                'payer': drift_event.payer,
                'cpt_group': drift_event.cpt_group,
                'drift_type': drift_event.drift_type,
                'baseline_value': drift_event.baseline_value,
                'current_value': drift_event.current_value,
                'delta_value': drift_event.delta_value,
                'severity': drift_event.severity,
                'rule_name': rule.name,
                'rule_threshold': rule.threshold_value,
            }
            alert_event = AlertEvent.objects.create(
                customer=drift_event.customer, alert_rule=rule, drift_event=drift_event,
                report_run=drift_event.report_run, triggered_at=timezone.now(), status='pending', payload=payload
            )
            alert_events.append(alert_event)
            logger.info(f"Alert triggered: {rule.name} for drift event {drift_event.id}")
            
            # Create audit event
            create_audit_event(
                action='alert_event_created',
                entity_type='AlertEvent',
                entity_id=alert_event.id,
                customer=alert_event.customer,
                metadata={
                    'alert_rule': rule.name,
                    'drift_event_id': drift_event.id,
                    'payer': drift_event.payer,
                    'severity': drift_event.severity
                }
            )
    return alert_events

def send_alert_notification(alert_event):
    """Send notification for an alert event via configured channels (idempotent)."""
    from payrixa.core.services import create_audit_event
    
    # Idempotency check: skip if already sent
    if alert_event.status == 'sent':
        logger.info(f"Alert event {alert_event.id} already sent, skipping")
        return True
    
    # Skip if already failed (manual intervention required)
    if alert_event.status == 'failed':
        logger.info(f"Alert event {alert_event.id} marked as failed, skipping")
        return False
    
    customer = alert_event.customer
    alert_rule = alert_event.alert_rule
    
    # Advanced routing: Use rule-specific channels if configured
    if alert_rule.routing_channels.exists():
        channels = alert_rule.routing_channels.filter(enabled=True)
    else:
        channels = NotificationChannel.objects.filter(customer=customer, enabled=True)

    evidence_payload = build_driftwatch_evidence_payload(
        alert_event.drift_event,
        [alert_event.drift_event] if alert_event.drift_event else [],
    )

    if _is_suppressed(alert_event.customer, evidence_payload):
        alert_event.status = 'sent'
        alert_event.notification_sent_at = timezone.now()
        alert_event.error_message = 'suppressed'
        alert_event.save()
        logger.info(f"Alert event {alert_event.id} suppressed within cooldown window")
        return True
    
    success = False
    error_message = None
    
    try:
        for channel in channels:
            if channel.channel_type == 'email':
                success = send_email_notification(alert_event, channel, evidence_payload)
            elif channel.channel_type == 'slack':
                success = send_slack_notification(alert_event, channel)
            elif channel.channel_type == 'webhook':
                # Webhook handled separately by send_webhooks command
                logger.info(f"Skipping webhook channel {channel.id} - handled by send_webhooks command")
        
        if not channels.exists():
            success = send_default_email_notification(alert_event, evidence_payload)
        
        if success:
            alert_event.status = 'sent'
            alert_event.notification_sent_at = timezone.now()
            alert_event.error_message = None
            alert_event.save()
            
            # Create audit event for successful send
            create_audit_event(
                action='alert_event_sent',
                entity_type='AlertEvent',
                entity_id=alert_event.id,
                customer=alert_event.customer,
                metadata={
                    'alert_rule': alert_event.alert_rule.name,
                    'payer': alert_event.payload.get('payer'),
                    'notification_sent_at': alert_event.notification_sent_at.isoformat()
                }
            )
            logger.info(f"Alert event {alert_event.id} sent successfully")
    except Exception as e:
        error_message = str(e)
        alert_event.status = 'failed'
        alert_event.error_message = error_message
        alert_event.save()
        
        # Create audit event for failed send
        create_audit_event(
            action='alert_event_failed',
            entity_type='AlertEvent',
            entity_id=alert_event.id,
            customer=alert_event.customer,
            metadata={
                'alert_rule': alert_event.alert_rule.name,
                'error_message': error_message
            }
        )
        logger.error(f"Alert event {alert_event.id} failed: {error_message}")
        success = False
    
    return success

def send_email_notification(alert_event, channel, evidence_payload):
    """Send email notification with HTML body and PDF attachment for an alert event."""
    config = channel.config or {}
    recipients = config.get('recipients', [])
    if not recipients:
        return False
    
    return _send_email_with_pdf(alert_event, recipients, evidence_payload)

def send_default_email_notification(alert_event, evidence_payload):
    """Send email notification using default settings with HTML body and PDF attachment."""
    recipients = [getattr(settings, 'DEFAULT_ALERT_EMAIL', 'alerts@example.com')]
    return _send_email_with_pdf(alert_event, recipients, evidence_payload)

def _send_email_with_pdf(alert_event, recipients, evidence_payload):
    """Send branded HTML email with PDF attachment."""
    from payrixa.middleware import get_request_id
    from payrixa.reporting.services import generate_weekly_drift_pdf
    from payrixa.reporting.models import ReportArtifact
    
    # Gather context data
    customer = alert_event.customer
    report_run = alert_event.report_run

    severity_label = _severity_label(evidence_payload.get('severity'))
    product_name = evidence_payload.get('product_name', 'Payrixa')
    summary_sentence = evidence_payload.get('one_sentence_explanation', '')
    
    # Portal URL from settings (no fallback - must be configured)
    portal_url = f"{settings.PORTAL_BASE_URL}/portal/"
    
    # Request ID for traceability
    request_id = get_request_id() or str(uuid.uuid4())
    
    # Render subject
    subject_context = {
        'customer_name': customer.name,
        'product_name': product_name,
        'severity': severity_label,
    }
    subject = render_to_string('email/alert_email_subject.txt', subject_context).strip()

    # Generate interpretation for operator guidance
    interpretation = get_alert_interpretation(evidence_payload)
    
    # Render HTML body
    html_context = {
        'customer_name': customer.name,
        'product_name': product_name,
        'severity': severity_label,
        'summary_sentence': summary_sentence,
        'evidence_payload': evidence_payload,
        'interpretation': interpretation,
        'portal_url': portal_url,
        'request_id': request_id
    }
    html_body = render_to_string('email/alert_email_body.html', html_context)
    
    # Plain text fallback
    text_body = (
        f"{product_name} Alert - {customer.name}\n\n"
        f"{summary_sentence}\n\n"
        f"View the full report: {portal_url}\n\n"
        f"Request ID: {request_id}"
    )
    
    # Create email
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'alerts@payrixa.com'),
        to=recipients
    )
    email.attach_alternative(html_body, "text/html")
    
    # Attach PDF if report_run exists and PDF attachment is enabled
    attach_pdf = getattr(settings, 'ALERT_ATTACH_PDF', False)
    if report_run and attach_pdf:
        try:
            # Try to fetch existing artifact
            artifact = ReportArtifact.objects.filter(
                customer=customer,
                report_run=report_run,
                kind='weekly_drift_summary'
            ).first()
            
            # Generate if missing
            if not artifact:
                logger.info(f"Generating missing PDF artifact for report run {report_run.id}")
                artifact = generate_weekly_drift_pdf(report_run.id)
            
            # Attach PDF
            if artifact and artifact.file_path and os.path.exists(artifact.file_path):
                with open(artifact.file_path, 'rb') as pdf_file:
                    pdf_content = pdf_file.read()
                    filename = f"payrixa_weekly_drift_{customer.name.replace(' ', '_').lower()}.pdf"
                    email.attach(filename, pdf_content, 'application/pdf')
                    logger.info(f"Attached PDF artifact {artifact.id} to email")
            else:
                logger.warning(f"PDF artifact file not found at {artifact.file_path if artifact else 'N/A'}")
        except Exception as e:
            logger.error(f"Failed to attach PDF to email: {str(e)}")
            # Continue without attachment - don't fail the email send
    elif report_run and not attach_pdf:
        logger.debug(f"PDF attachment disabled (ALERT_ATTACH_PDF=False), skipping for report run {report_run.id}")
    
    # Send email
    email.send(fail_silently=False)
    return True


def _severity_label(severity_value):
    if severity_value is None:
        return 'unknown'
    if isinstance(severity_value, str):
        return severity_value.lower()
    if severity_value >= 0.7:
        return 'high'
    if severity_value >= 0.4:
        return 'medium'
    return 'low'


def _is_suppressed(customer, evidence_payload):
    if not evidence_payload:
        return False
    window_start = timezone.now() - ALERT_SUPPRESSION_COOLDOWN
    return AlertEvent.objects.filter(
        customer=customer,
        status='sent',
        notification_sent_at__gte=window_start,
        payload__product_name=evidence_payload.get('product_name'),
        payload__signal_type=evidence_payload.get('signal_type'),
        payload__entity_label=evidence_payload.get('entity_label'),
    ).exists()

def send_slack_notification(alert_event, channel):
    """Send Slack notification via webhook."""
    import json
    import requests
    
    # V1: Slack is disabled by default
    if not getattr(settings, 'SLACK_ENABLED', False):
        logger.info(f"Slack disabled (SLACK_ENABLED=False), skipping channel {channel.id}")
        return True  # Return True to not mark as failed
    
    config = channel.config or {}
    webhook_url = config.get('webhook_url')
    
    if not webhook_url:
        logger.error(f"Slack channel {channel.id} missing webhook_url")
        return False
    
    # Gather context data
    customer = alert_event.customer
    payload = alert_event.payload
    drift_event = alert_event.drift_event
    alert_rule = alert_event.alert_rule
    
    # Build summary message
    payer = payload.get('payer', 'Unknown')
    drift_type = payload.get('drift_type', 'Unknown').replace('_', ' ').title()
    delta = payload.get('delta_value', 0)
    severity = payload.get('severity', 0)
    
    # Severity emoji and color
    if severity >= 0.7:
        color = "#d32f2f"  # Red
        emoji = "🚨"
    elif severity >= 0.4:
        color = "#ff9800"  # Orange
        emoji = "⚠️"
    else:
        color = "#2196f3"  # Blue
        emoji = "ℹ️"
    
    # Portal URL from settings
    portal_url = f"{settings.PORTAL_BASE_URL}/portal/"
    
    # Build Slack message with blocks
    slack_payload = {
        "text": f"{emoji} Drift Alert: {payer} {drift_type}",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} Drift Alert Triggered"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Customer:*\n{customer.name}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Rule:*\n{alert_rule.name}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Payer:*\n{payer}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Drift Type:*\n{drift_type}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Delta:*\n{delta:+.2f}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Severity:*\n{severity:.2f}"
                    }
                ]
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View in Payrixa Portal"
                        },
                        "url": portal_url,
                        "style": "primary"
                    }
                ]
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Alert ID: {alert_event.id} | Triggered: {alert_event.triggered_at.strftime('%Y-%m-%d %H:%M:%S UTC')}"
                    }
                ]
            }
        ],
        "attachments": [
            {
                "color": color,
                "text": f"This alert was triggered by the *{alert_rule.name}* rule."
            }
        ]
    }
    
    try:
        response = requests.post(
            webhook_url,
            data=json.dumps(slack_payload),
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        if response.status_code == 200:
            logger.info(f"Slack notification sent successfully for alert event {alert_event.id}")
            return True
        else:
            logger.error(f"Slack notification failed with status {response.status_code}: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to send Slack notification: {str(e)}")
        return False

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
