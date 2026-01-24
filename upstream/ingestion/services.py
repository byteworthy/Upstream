"""
Ingestion services for Upstream.

Provides unified ingestion and event publishing.
"""

import logging
from django.utils import timezone
from django.db import transaction
from upstream.middleware import get_request_id
from .models import IngestionRecord, SystemEvent

logger = logging.getLogger(__name__)


def publish_event(customer, event_type, payload=None, related_ingestion=None, 
                  related_drift_event=None, related_alert=None):
    """
    Publish a system event to the event log.
    
    This is the single fanout point for all system events.
    Future modules can subscribe by querying this log or using Django signals.
    
    Args:
        customer: Customer instance
        event_type: Event type string (from SystemEvent.EVENT_TYPES)
        payload: Optional dict with event-specific data
        related_ingestion: Optional IngestionRecord reference
        related_drift_event: Optional DriftEvent reference
        related_alert: Optional AlertEvent reference
    
    Returns:
        SystemEvent instance
    """
    if payload is None:
        payload = {}
    
    request_id = get_request_id()
    
    event = SystemEvent.objects.create(
        customer=customer,
        event_type=event_type,
        payload=payload,
        request_id=request_id,
        related_ingestion=related_ingestion,
        related_drift_event=related_drift_event,
        related_alert=related_alert
    )
    
    logger.info(f"Event published: {event_type} for customer {customer.id} (request_id: {request_id})")
    
    # Future: Add signal dispatch here for subscribers
    # Example: event_published.send(sender=SystemEvent, event=event)
    
    return event


class IngestionService:
    """
    Unified ingestion service for all data sources.
    
    Usage:
        service = IngestionService(customer, source_type='webhook', created_by=user)
        record = service.create_record(payload_metadata, idempotency_key='...')
        service.mark_processed(record)
    """
    
    def __init__(self, customer, source_type, created_by=None):
        """
        Initialize ingestion service.
        
        Args:
            customer: Customer instance
            source_type: One of IngestionRecord.SOURCE_TYPES
            created_by: Optional User who initiated ingestion
        """
        self.customer = customer
        self.source_type = source_type
        self.created_by = created_by
    
    def create_record(self, payload_metadata, idempotency_key=None, record_count=None):
        """
        Create a durable ingestion record.
        
        Args:
            payload_metadata: Dict with metadata about the payload
            idempotency_key: Optional unique key to prevent duplicates
            record_count: Optional count of records in payload
        
        Returns:
            IngestionRecord instance
        
        Raises:
            ValueError: If idempotency_key already exists for this customer
        """
        # Check for duplicate idempotency key
        if idempotency_key:
            existing = IngestionRecord.objects.filter(
                customer=self.customer,
                idempotency_key=idempotency_key
            ).first()
            
            if existing:
                logger.warning(
                    f"Duplicate ingestion attempt: customer={self.customer.id} "
                    f"idempotency_key={idempotency_key}"
                )
                raise ValueError(f"Duplicate ingestion: idempotency_key '{idempotency_key}' already exists")
        
        # Create ingestion record
        with transaction.atomic():
            record = IngestionRecord.objects.create(
                customer=self.customer,
                source_type=self.source_type,
                idempotency_key=idempotency_key,
                status='pending',
                payload_metadata=payload_metadata,
                record_count=record_count,
                created_by=self.created_by
            )
            
            # Publish event
            publish_event(
                customer=self.customer,
                event_type='ingestion_received',
                payload={
                    'source_type': self.source_type,
                    'record_count': record_count,
                    'has_idempotency_key': bool(idempotency_key)
                },
                related_ingestion=record
            )
            
            logger.info(
                f"Ingestion record created: id={record.id} customer={self.customer.id} "
                f"source={self.source_type}"
            )
        
        return record
    
    def mark_processing(self, record):
        """Mark an ingestion record as processing."""
        record.status = 'processing'
        record.save(update_fields=['status', 'updated_at'])
        logger.debug(f"Ingestion {record.id} marked as processing")
    
    def mark_processed(self, record, record_count=None):
        """
        Mark an ingestion record as successfully processed.
        
        Args:
            record: IngestionRecord instance
            record_count: Optional final count of records processed
        """
        with transaction.atomic():
            record.status = 'processed'
            record.processed_at = timezone.now()
            if record_count is not None:
                record.record_count = record_count
            record.save(update_fields=['status', 'processed_at', 'record_count', 'updated_at'])
            
            # Publish event
            publish_event(
                customer=self.customer,
                event_type='ingestion_processed',
                payload={
                    'source_type': self.source_type,
                    'record_count': record.record_count
                },
                related_ingestion=record
            )
            
            logger.info(f"Ingestion {record.id} marked as processed")
    
    def mark_failed(self, record, error_message):
        """
        Mark an ingestion record as failed.
        
        Args:
            record: IngestionRecord instance
            error_message: Error description
        """
        with transaction.atomic():
            record.status = 'failed'
            record.error_message = error_message
            record.save(update_fields=['status', 'error_message', 'updated_at'])
            
            # Publish event
            publish_event(
                customer=self.customer,
                event_type='ingestion_failed',
                payload={
                    'source_type': self.source_type,
                    'error': error_message
                },
                related_ingestion=record
            )
            
            logger.error(f"Ingestion {record.id} marked as failed: {error_message}")
    
    @staticmethod
    def get_recent_ingestions(customer, limit=50):
        """
        Get recent ingestion records for a customer.
        
        Args:
            customer: Customer instance
            limit: Maximum number of records to return
        
        Returns:
            QuerySet of IngestionRecord
        """
        return IngestionRecord.objects.filter(
            customer=customer
        ).select_related('created_by').order_by('-created_at')[:limit]
    
    @staticmethod
    def get_recent_events(customer, event_type=None, limit=100):
        """
        Get recent system events for a customer.
        
        Args:
            customer: Customer instance
            event_type: Optional event type filter
            limit: Maximum number of events to return
        
        Returns:
            QuerySet of SystemEvent
        """
        events = SystemEvent.objects.filter(customer=customer)
        
        if event_type:
            events = events.filter(event_type=event_type)
        
        return events.select_related(
            'related_ingestion',
            'related_drift_event',
            'related_alert'
        ).order_by('-created_at')[:limit]
