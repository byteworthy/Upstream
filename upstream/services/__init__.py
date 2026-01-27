"""
Upstream Service Layer

Business logic services extracted from views for better testability
and separation of concerns.

Services are stateless and framework-agnostic - they accept domain
objects and return structured results. Views remain thin - they call
service methods and format results into HTTP responses.
"""

from .data_quality import DataQualityService
from .report_generation import ReportGenerationService
from .alert_processing import AlertProcessingService

__all__ = [
    "DataQualityService",
    "ReportGenerationService",
    "AlertProcessingService",
]
