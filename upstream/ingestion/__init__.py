"""
Upstream Ingestion Module

Provides unified ingestion spine for all data sources.
"""

from .services import IngestionService, publish_event

__all__ = ['IngestionService', 'publish_event']
