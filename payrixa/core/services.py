"""Core services for domain audit logging."""
import logging
from .models import DomainAuditEvent
from payrixa.middleware import get_request_id

logger = logging.getLogger(__name__)

def create_audit_event(action, entity_type, entity_id=None, customer=None, user=None, metadata=None, request_id=None):
    """Create a domain audit event."""
    if request_id is None:
        request_id = get_request_id()
    audit_event = DomainAuditEvent.objects.create(
        action=action, entity_type=entity_type, entity_id=str(entity_id) if entity_id else None,
        customer=customer, user=user, metadata=metadata or {}, request_id=request_id
    )
    logger.info(f"Audit event created: {action} on {entity_type}:{entity_id}")
    return audit_event

def audit_upload_created(upload, user=None):
    """Create audit event for upload creation."""
    return create_audit_event(action='upload_created', entity_type='Upload', entity_id=upload.id, customer=upload.customer, user=user, metadata={'filename': upload.filename, 'row_count': upload.row_count, 'status': upload.status})

def audit_report_exported(artifact, user=None):
    """Create audit event for report export."""
    return create_audit_event(action='report_exported', entity_type='ReportArtifact', entity_id=artifact.id, customer=artifact.customer, user=user, metadata={'format': artifact.format, 'report_run_id': artifact.report_run_id, 'file_path': artifact.file_path})

def audit_alert_rule_change(alert_rule, action, user=None):
    """Create audit event for alert rule changes."""
    return create_audit_event(action=action, entity_type='AlertRule', entity_id=alert_rule.id, customer=alert_rule.customer, user=user, metadata={'name': alert_rule.name, 'metric': alert_rule.metric, 'threshold_value': alert_rule.threshold_value, 'enabled': alert_rule.enabled})

def audit_webhook_delivery(delivery, user=None):
    """Create audit event for webhook delivery attempt."""
    return create_audit_event(action='webhook_delivery_attempted', entity_type='WebhookDelivery', entity_id=delivery.id, customer=delivery.endpoint.customer, user=user, metadata={'endpoint_name': delivery.endpoint.name, 'event_type': delivery.event_type, 'status': delivery.status, 'attempts': delivery.attempts})
