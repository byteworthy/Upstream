"""Alert services for evaluating drift events, delay signals, and sending notifications."""
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
from payrixa.products.delayguard.models import PaymentDelaySignal
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


def evaluate_payment_delay_signal(payment_delay_signal):
    """
    Evaluate a payment delay signal against alert rules for the customer.

    Creates AlertEvent instances for DelayGuard signals similar to how
    evaluate_drift_event handles DriftWatch signals.
    """
    from payrixa.core.services import create_audit_event

    alert_events = []

    # For now, use a simplified rule evaluation
    # DelayGuard signals are self-contained with severity/confidence scoring
    # We create an alert for any signal that meets minimum thresholds

    # Skip low-severity signals with low confidence
    if payment_delay_signal.severity == 'low' and payment_delay_signal.confidence < 0.5:
        logger.info(f"Skipping low-severity, low-confidence signal for {payment_delay_signal.payer}")
        return alert_events

    # Check for duplicate alert event
    existing = AlertEvent.objects.filter(
        payment_delay_signal=payment_delay_signal
    ).first()

    if existing:
        logger.info(f"Alert event already exists for payment delay signal {payment_delay_signal.id}")
        alert_events.append(existing)
        return alert_events

    # Find a matching alert rule (or use default)
    # For now, we'll use a simple rule match based on severity
    alert_rule = AlertRule.objects.filter(
        customer=payment_delay_signal.customer,
        enabled=True
    ).first()

    if not alert_rule:
        logger.warning(f"No enabled alert rules found for customer {payment_delay_signal.customer}")
        return alert_events

    # Build payload
    payload = {
        'product_name': 'DelayGuard',
        'signal_type': 'payment_delay_drift',
        'entity_label': payment_delay_signal.payer,
        'payer': payment_delay_signal.payer,
        'baseline_avg_days': payment_delay_signal.baseline_avg_days,
        'current_avg_days': payment_delay_signal.current_avg_days,
        'delta_days': payment_delay_signal.delta_days,
        'delta_percent': payment_delay_signal.delta_percent,
        'severity': payment_delay_signal.severity,
        'confidence': payment_delay_signal.confidence,
        'estimated_dollars_at_risk': str(payment_delay_signal.estimated_dollars_at_risk),
        'rule_name': alert_rule.name,
    }

    # Create alert event
    alert_event = AlertEvent.objects.create(
        customer=payment_delay_signal.customer,
        alert_rule=alert_rule,
        payment_delay_signal=payment_delay_signal,
        triggered_at=timezone.now(),
        status='pending',
        payload=payload
    )
    alert_events.append(alert_event)

    logger.info(f"DelayGuard alert created for {payment_delay_signal.payer}: +{payment_delay_signal.delta_days:.1f} days")

    # Create audit event
    create_audit_event(
        action='alert_event_created',
        entity_type='AlertEvent',
        entity_id=alert_event.id,
        customer=alert_event.customer,
        metadata={
            'product': 'DelayGuard',
            'alert_rule': alert_rule.name,
            'payment_delay_signal_id': payment_delay_signal.id,
            'payer': payment_delay_signal.payer,
            'severity': payment_delay_signal.severity,
            'delta_days': payment_delay_signal.delta_days,
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
    """
    Check if an alert should be suppressed based on:
    1. Time-based cooldown (4 hours)
    2. Operator judgments (marked as "noise")
    """
    from payrixa.alerts.models import OperatorJudgment

    if not evidence_payload:
        return False

    product_name = evidence_payload.get('product_name')
    signal_type = evidence_payload.get('signal_type')
    entity_label = evidence_payload.get('entity_label')

    # Check 1: Time-based cooldown suppression (existing logic)
    window_start = timezone.now() - ALERT_SUPPRESSION_COOLDOWN
    recent_alert = AlertEvent.objects.filter(
        customer=customer,
        status='sent',
        notification_sent_at__gte=window_start,
        payload__product_name=product_name,
        payload__signal_type=signal_type,
        payload__entity_label=entity_label,
    ).exists()

    if recent_alert:
        logger.info(f"Alert suppressed: cooldown window (entity={entity_label}, signal={signal_type})")
        return True

    # Check 2: Operator noise judgment suppression
    # Look for similar alerts marked as "noise" in the last 30 days
    # IMPORTANT: Filter by judgment creation date, not alert creation date
    noise_window_start = timezone.now() - timezone.timedelta(days=30)
    similar_noise_alerts = AlertEvent.objects.filter(
        customer=customer,
        payload__product_name=product_name,
        payload__signal_type=signal_type,
        payload__entity_label=entity_label,
        operator_judgments__verdict='noise',
        operator_judgments__created_at__gte=noise_window_start,
    ).distinct()

    if similar_noise_alerts.exists():
        # Count how many times this pattern was marked noise
        noise_count = similar_noise_alerts.count()

        # If marked as noise 2+ times in 30 days, suppress it
        if noise_count >= 2:
            logger.info(
                f"Alert suppressed: operator noise pattern "
                f"(entity={entity_label}, signal={signal_type}, noise_count={noise_count})"
            )
            return True

    return False

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

def get_suppression_context(alert_event):
    """
    Get context about similar alerts and operator judgments.
    Used to display badges showing operator memory.
    """
    from payrixa.alerts.models import OperatorJudgment

    if not alert_event.drift_event:
        return None

    customer = alert_event.customer
    drift_event = alert_event.drift_event

    # Look for similar alerts in the last 60 days
    similar_window = timezone.now() - timezone.timedelta(days=60)
    similar_alerts = AlertEvent.objects.filter(
        customer=customer,
        created_at__gte=similar_window,
        payload__entity_label=drift_event.payer,
        payload__signal_type=drift_event.drift_type,
    ).exclude(id=alert_event.id).prefetch_related('operator_judgments')

    if not similar_alerts.exists():
        return None

    # Count judgments by verdict
    noise_count = 0
    real_count = 0
    followup_count = 0

    for similar_alert in similar_alerts:
        for judgment in similar_alert.operator_judgments.all():
            if judgment.verdict == 'noise':
                noise_count += 1
            elif judgment.verdict == 'real':
                real_count += 1
            elif judgment.verdict == 'needs_followup':
                followup_count += 1

    # Determine dominant pattern
    if noise_count >= 2:
        return {
            'type': 'noise',
            'count': noise_count,
            'message': f'Similar alerts marked as noise {noise_count} times in last 60 days'
        }
    elif real_count >= 1:
        return {
            'type': 'confirmed',
            'count': real_count,
            'message': f'Similar alerts confirmed real {real_count} times in last 60 days'
        }
    elif followup_count >= 1:
        return {
            'type': 'pending',
            'count': followup_count,
            'message': f'Similar alerts need follow-up {followup_count} times in last 60 days'
        }

    return None


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
