"""
Data export service for Upstream.

Provides generic utilities for exporting data to CSV, JSON, and PDF formats.
Reusable across views, tasks, and other services.
"""

import csv
import json
import os
from typing import Optional, Dict, Any, List, Union
from datetime import datetime, date, time
from decimal import Decimal
from io import BytesIO, StringIO
from django.conf import settings
from django.db.models import QuerySet
from weasyprint import HTML
import logging

logger = logging.getLogger(__name__)


class DataExportService:
    """
    Stateless service for exporting data to various formats.

    Provides generic utilities for CSV, JSON, and PDF generation.
    All methods are static - no instance state.
    """

    @staticmethod
    def export_to_csv(
        data: List[Dict[str, Any]],
        headers: Optional[List[str]] = None,
        file_path: Optional[str] = None,
    ) -> Union[str, StringIO]:
        """
        Export list of dicts to CSV format.

        Args:
            data: List of dictionaries with row data
            headers: Column headers (defaults to keys from first row)
            file_path: Optional file path to write to (returns path)
                      If None, returns StringIO buffer

        Returns:
            str: File path if file_path provided
            StringIO: CSV content buffer if file_path is None

        Example:
            data = [
                {"name": "Alice", "age": 30},
                {"name": "Bob", "age": 25}
            ]
            csv_buffer = DataExportService.export_to_csv(data)
        """
        try:
            # Handle empty data
            if not data:
                if file_path:
                    with open(file_path, "w", newline="") as f:
                        f.write("")
                    return file_path
                return StringIO("")

            # Extract headers from first row if not provided
            if headers is None:
                headers = list(data[0].keys())

            # Write to file or buffer
            if file_path:
                with open(file_path, "w", newline="") as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=headers)
                    writer.writeheader()
                    writer.writerows(data)
                logger.debug(f"CSV exported to file: {file_path}")
                return file_path
            else:
                output = StringIO()
                writer = csv.DictWriter(output, fieldnames=headers)
                writer.writeheader()
                writer.writerows(data)
                output.seek(0)
                logger.debug(f"CSV exported to buffer ({len(data)} rows)")
                return output

        except (IOError, OSError) as e:
            logger.error(f"CSV export failed due to file system error: {str(e)}")
            raise IOError(f"CSV export failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in CSV export: {str(e)}", exc_info=True)
            raise

    @staticmethod
    def export_to_json(
        data: Union[List, Dict], file_path: Optional[str] = None, indent: int = 2
    ) -> Union[str, str]:
        """
        Export data to JSON format.

        Args:
            data: Data structure to serialize (list or dict)
            file_path: Optional file path to write to (returns path)
                      If None, returns JSON string
            indent: JSON indentation level (default: 2)

        Returns:
            str: File path if file_path provided
            str: JSON string if file_path is None

        Example:
            data = {"users": [{"id": 1, "name": "Alice"}]}
            json_str = DataExportService.export_to_json(data)
        """
        try:
            # Custom JSON serializer for Django/Python types
            def json_serializer(obj):
                """Handle datetime, date, time, Decimal objects."""
                if isinstance(obj, (datetime, date, time)):
                    return obj.isoformat()
                elif isinstance(obj, Decimal):
                    return float(obj)
                return str(obj)

            # Serialize to JSON
            json_str = json.dumps(data, indent=indent, default=json_serializer)

            # Write to file or return string
            if file_path:
                with open(file_path, "w") as f:
                    f.write(json_str)
                logger.debug(f"JSON exported to file: {file_path}")
                return file_path
            else:
                logger.debug(f"JSON exported to string ({len(json_str)} chars)")
                return json_str

        except (IOError, OSError) as e:
            logger.error(f"JSON export failed due to file system error: {str(e)}")
            raise IOError(f"JSON export failed: {str(e)}")
        except (TypeError, ValueError) as e:
            logger.error(f"JSON serialization failed: {str(e)}")
            raise ValueError(f"JSON serialization failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in JSON export: {str(e)}", exc_info=True)
            raise

    @staticmethod
    def export_to_pdf(
        html_content: str,
        file_path: Optional[str] = None,
        stylesheets: Optional[List[str]] = None,
    ) -> Union[str, BytesIO]:
        """
        Export HTML content to PDF format using weasyprint.

        Args:
            html_content: HTML string to convert
            file_path: Optional file path to write to (returns path)
                      If None, returns BytesIO buffer
            stylesheets: Optional list of CSS file paths

        Returns:
            str: File path if file_path provided
            BytesIO: PDF content buffer if file_path is None

        Example:
            html = "<h1>Report</h1><p>Data here</p>"
            pdf_buffer = DataExportService.export_to_pdf(html)
        """
        try:
            # Generate PDF using WeasyPrint
            html_obj = HTML(string=html_content)

            if file_path:
                # Write directly to file
                html_obj.write_pdf(file_path, stylesheets=stylesheets)
                logger.debug(f"PDF exported to file: {file_path}")
                return file_path
            else:
                # Write to BytesIO buffer
                output = BytesIO()
                html_obj.write_pdf(output, stylesheets=stylesheets)
                output.seek(0)
                logger.debug(f"PDF exported to buffer")
                return output

        except (IOError, OSError) as e:
            logger.error(f"PDF export failed due to file system error: {str(e)}")
            raise IOError(f"PDF export failed: {str(e)}")
        except Exception as e:
            logger.error(f"PDF generation failed: {str(e)}", exc_info=True)
            raise

    @staticmethod
    def queryset_to_csv(
        queryset: QuerySet,
        fields: List[str],
        headers: Optional[List[str]] = None,
        file_path: Optional[str] = None,
    ) -> Union[str, StringIO]:
        """
        Export Django queryset to CSV format.

        Convenience method that extracts values from queryset
        and delegates to export_to_csv.

        Args:
            queryset: Django QuerySet to export
            fields: Model field names to include
            headers: Column headers (defaults to field names)
            file_path: Optional file path to write to

        Returns:
            str: File path if file_path provided
            StringIO: CSV content buffer if file_path is None

        Example:
            from upstream.models import DriftEvent
            events = DriftEvent.objects.filter(severity__gte=0.7)
            csv_path = DataExportService.queryset_to_csv(
                events,
                fields=["payer", "severity", "delta_value"],
                file_path="/tmp/high_severity.csv"
            )
        """
        try:
            # Convert queryset to list of dicts
            data = list(queryset.values(*fields))

            # Use field names as headers if not provided
            if headers is None:
                headers = fields

            # Delegate to export_to_csv
            return DataExportService.export_to_csv(
                data=data, headers=headers, file_path=file_path
            )

        except Exception as e:
            logger.error(f"Queryset to CSV conversion failed: {str(e)}", exc_info=True)
            raise

    @staticmethod
    def queryset_to_json(
        queryset: QuerySet,
        fields: Optional[List[str]] = None,
        file_path: Optional[str] = None,
    ) -> Union[str, str]:
        """
        Export Django queryset to JSON format.

        Convenience method that serializes queryset to JSON.

        Args:
            queryset: Django QuerySet to export
            fields: Model field names to include (None = all fields)
            file_path: Optional file path to write to

        Returns:
            str: File path if file_path provided
            str: JSON string if file_path is None

        Example:
            from upstream.models import AlertEvent
            alerts = AlertEvent.objects.filter(status="pending")
            json_str = DataExportService.queryset_to_json(
                alerts,
                fields=["id", "status", "triggered_at"]
            )
        """
        try:
            # Convert queryset to list of dicts
            if fields:
                data = list(queryset.values(*fields))
            else:
                data = list(queryset.values())

            # Delegate to export_to_json
            return DataExportService.export_to_json(data=data, file_path=file_path)

        except Exception as e:
            logger.error(f"Queryset to JSON conversion failed: {str(e)}", exc_info=True)
            raise

    @staticmethod
    def generate_file_path(
        base_name: str,
        extension: str,
        directory: Optional[str] = None,
        timestamp: bool = True,
    ) -> str:
        """
        Generate file path for exports with optional timestamp.

        Args:
            base_name: Base filename (e.g., "drift_events")
            extension: File extension without dot (e.g., "csv")
            directory: Directory path (defaults to settings.BASE_DIR/reports)
            timestamp: Whether to include timestamp in filename

        Returns:
            str: Full file path with directory created

        Example:
            path = DataExportService.generate_file_path(
                "drift_events", "csv", timestamp=True
            )
            # Returns: /path/to/reports/drift_events_20240127_143022.csv
        """
        try:
            # Use default directory if not provided
            if directory is None:
                directory = os.path.join(settings.BASE_DIR, "reports")

            # Create directory if it doesn't exist
            os.makedirs(directory, exist_ok=True)

            # Build filename with optional timestamp
            if timestamp:
                timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{base_name}_{timestamp_str}.{extension}"
            else:
                filename = f"{base_name}.{extension}"

            # Return full path
            file_path = os.path.join(directory, filename)
            logger.debug("Generated file path: %s", file_path)
            return file_path

        except (IOError, OSError) as e:
            logger.error(f"File path generation failed: {str(e)}")
            raise IOError(f"File path generation failed: {str(e)}")
        except Exception as e:
            logger.error(
                f"Unexpected error in file path generation: {str(e)}", exc_info=True
            )
            raise
