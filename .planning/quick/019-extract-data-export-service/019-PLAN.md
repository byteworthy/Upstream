---
task_id: "019"
type: quick
title: "Extract data export service"
autonomous: true
files_modified:
  - upstream/services/data_export.py
  - upstream/services/__init__.py

must_haves:
  truths:
    - "Generic CSV, JSON, PDF export utilities exist in dedicated service"
    - "Service provides reusable export functions for any queryset/data"
    - "Service is framework-agnostic and accepts plain Python data structures"
  artifacts:
    - path: "upstream/services/data_export.py"
      provides: "DataExportService class with export utilities"
      min_lines: 150
      exports: ["DataExportService"]
    - path: "upstream/services/__init__.py"
      provides: "Service exports including DataExportService"
      contains: "DataExportService"
  key_links:
    - from: "upstream/exports/services.py"
      to: "upstream/services/data_export.py"
      via: "can use generic export utilities instead of duplicating logic"
      pattern: "csv\\.writer|json\\.dumps|BytesIO"
---

<objective>
Extract generic data export utilities (CSV, JSON, PDF) from scattered view/service code into a centralized `DataExportService`.

**Purpose:** Consolidates export logic currently duplicated across `upstream/exports/services.py` (Excel), `upstream/reporting/services.py` (CSV for drift events), and views (JSON serialization). Creates reusable utilities for exporting querysets, dicts, and lists to common formats.

**Output:** New `services/data_export.py` with stateless utility methods for CSV, JSON, and PDF generation that any part of the codebase can use.
</objective>

<execution_context>
@/home/codespace/.claude/get-shit-done/workflows/execute-quick.md
@/home/codespace/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@upstream/exports/services.py
@upstream/reporting/services.py
@upstream/services/report_generation.py

**Current State:** Export functionality is scattered:
1. `upstream/exports/services.py` - Excel exports with openpyxl (drift events, alerts, weekly summary)
2. `upstream/reporting/services.py` - CSV export for drift events (lines 26-100)
3. `upstream/services/report_generation.py` - PDF generation with weasyprint (lines 355-400)
4. Various views - JSON serialization with `json.dumps()`

**Duplication:** CSV writing logic, file path generation, BytesIO handling, headers/styling repeated across files.

**Goal:** Create `DataExportService` with generic utilities:
- `export_to_csv(data, headers, file_path=None)` - returns file path or BytesIO
- `export_to_json(data, file_path=None)` - returns JSON string or writes to file
- `export_to_pdf(html_content, file_path=None)` - returns BytesIO with PDF
- `queryset_to_csv(queryset, fields)` - convenience for Django querysets
- `queryset_to_json(queryset, fields)` - convenience for Django querysets

**Pattern:** Follow established service pattern (stateless static methods, accepts data structures, returns results).
</context>

<tasks>

<task type="auto">
  <name>Create DataExportService with CSV, JSON, PDF utilities</name>
  <files>upstream/services/data_export.py</files>
  <action>
Create new service class with generic export utilities. Extract patterns from existing code but make them reusable and framework-agnostic.

**Service structure:**

```python
"""
Data export service for Upstream.

Provides generic utilities for exporting data to CSV, JSON, and PDF formats.
Reusable across views, tasks, and other services.
"""

import csv
import json
import os
from typing import Optional, Dict, Any, List, Union, IO
from datetime import datetime
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
        file_path: Optional[str] = None
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
        # Implementation: Use csv.DictWriter
        # If headers not provided, extract from first row keys
        # If file_path provided, write to disk
        # Otherwise, write to StringIO and return
        pass

    @staticmethod
    def export_to_json(
        data: Union[List, Dict],
        file_path: Optional[str] = None,
        indent: int = 2
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
        # Implementation: Use json.dumps with indent
        # If file_path provided, write to disk
        # Otherwise, return JSON string
        pass

    @staticmethod
    def export_to_pdf(
        html_content: str,
        file_path: Optional[str] = None,
        stylesheets: Optional[List[str]] = None
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
        # Implementation: Use weasyprint.HTML().write_pdf()
        # If file_path provided, write to disk
        # Otherwise, write to BytesIO and return
        # Handle stylesheets parameter
        pass

    @staticmethod
    def queryset_to_csv(
        queryset: QuerySet,
        fields: List[str],
        headers: Optional[List[str]] = None,
        file_path: Optional[str] = None
    ) -> Union[str, StringIO]:
        """
        Export Django queryset to CSV format.

        Convenience method that extracts values_list from queryset
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
        # Implementation: Convert queryset.values(*fields) to list of dicts
        # Call export_to_csv with converted data
        pass

    @staticmethod
    def queryset_to_json(
        queryset: QuerySet,
        fields: Optional[List[str]] = None,
        file_path: Optional[str] = None
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
        # Implementation: Convert queryset to list of dicts
        # Handle datetime serialization (use .isoformat())
        # Call export_to_json with converted data
        pass

    @staticmethod
    def generate_file_path(
        base_name: str,
        extension: str,
        directory: Optional[str] = None,
        timestamp: bool = True
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
        # Implementation: Use datetime.now().strftime("%Y%m%d_%H%M%S")
        # Create directory if not exists (os.makedirs)
        # Return full path
        pass
```

**Implementation notes:**
- Import csv, json, os, datetime, BytesIO, StringIO, weasyprint.HTML
- Use try/except for file operations (IOError, OSError)
- Log errors with logger.error()
- Handle empty data gracefully (return empty file/buffer)
- For datetime objects in JSON, use default=str or custom serializer
- Follow patterns from existing code but make generic/reusable

**DO NOT duplicate Excel export logic** - that stays in `upstream/exports/services.py` since it's domain-specific (styling, multi-sheet, etc.). This service is for simple, generic exports.
  </action>
  <verify>
```bash
# Verify service exists with all methods
python -c "
from upstream.services.data_export import DataExportService
import inspect

methods = [m for m in dir(DataExportService) if not m.startswith('_')]
expected = ['export_to_csv', 'export_to_json', 'export_to_pdf', 'queryset_to_csv', 'queryset_to_json', 'generate_file_path']

print(f'Methods found: {methods}')
for method in expected:
    assert method in methods, f'Missing method: {method}'
print('✓ All required methods present')
"

# Verify imports work
python -c "from upstream.services.data_export import DataExportService; print('✓ Service imports successfully')"
```
  </verify>
  <done>
- `upstream/services/data_export.py` exists with DataExportService class
- Six public static methods: export_to_csv, export_to_json, export_to_pdf, queryset_to_csv, queryset_to_json, generate_file_path
- Service handles file writing and buffer returns based on file_path parameter
- Service includes error handling and logging
- Follows stateless pattern with no instance state
  </done>
</task>

<task type="auto">
  <name>Update service exports</name>
  <files>upstream/services/__init__.py</files>
  <action>
Add DataExportService to exports following existing pattern:

```python
from .data_export import DataExportService

__all__ = [
    "DataQualityService",
    "ReportGenerationService",
    "AlertProcessingService",
    "ReportSchedulerService",
    "DataExportService",  # NEW
]
```

Maintain alphabetical or logical ordering of exports.
  </action>
  <verify>
```bash
# Verify service is exported
python -c "from upstream.services import DataExportService; print('✓ DataExportService exported from services package')"

# Verify all exports still work
python -c "
from upstream.services import (
    DataQualityService,
    ReportGenerationService,
    AlertProcessingService,
    ReportSchedulerService,
    DataExportService
)
print('✓ All services import successfully')
"
```
  </verify>
  <done>
- `upstream/services/__init__.py` includes DataExportService in imports and __all__
- Service can be imported via `from upstream.services import DataExportService`
- No existing service exports broken
  </done>
</task>

<task type="auto">
  <name>Test service utilities with real data</name>
  <files></files>
  <action>
Create quick manual tests to verify service functionality:

```bash
cd /workspaces/codespaces-django

# Test CSV export
python -c "
from upstream.services.data_export import DataExportService
from io import StringIO

# Test basic CSV export to buffer
data = [
    {'name': 'Alice', 'age': 30, 'role': 'admin'},
    {'name': 'Bob', 'age': 25, 'role': 'user'}
]
csv_buffer = DataExportService.export_to_csv(data)
content = csv_buffer.getvalue() if isinstance(csv_buffer, StringIO) else csv_buffer
print('CSV Export Test:')
print(content)
assert 'name' in content and 'Alice' in content
print('✓ CSV export works')
"

# Test JSON export
python -c "
from upstream.services.data_export import DataExportService

# Test JSON export to string
data = {'users': [{'id': 1, 'name': 'Alice'}], 'count': 1}
json_str = DataExportService.export_to_json(data)
print('JSON Export Test:')
print(json_str)
assert '\"name\": \"Alice\"' in json_str
print('✓ JSON export works')
"

# Test file path generation
python -c "
from upstream.services.data_export import DataExportService
import os

path = DataExportService.generate_file_path('test_export', 'csv')
print(f'Generated path: {path}')
assert 'test_export' in path and '.csv' in path
print('✓ File path generation works')
"

# Test queryset export with real model
python -c "
from upstream.services.data_export import DataExportService
from upstream.models import Customer

# Test queryset to JSON (if customers exist)
customers = Customer.objects.all()[:5]
if customers.exists():
    json_str = DataExportService.queryset_to_json(
        customers,
        fields=['id', 'name']
    )
    print('Queryset JSON Test:')
    print(json_str[:200])  # First 200 chars
    print('✓ Queryset JSON export works')
else:
    print('⚠ No customers to test with')
"
```

**Expected:** All tests pass with output showing generated CSV, JSON, file paths. If any test fails, fix the service implementation.

**Note:** PDF export test skipped here (requires HTML) - that's tested implicitly via existing report generation if needed.
  </action>
  <verify>
```bash
# Run manual tests and capture output
cd /workspaces/codespaces-django
python -c "
from upstream.services.data_export import DataExportService

# CSV test
data = [{'a': 1, 'b': 2}]
csv_result = DataExportService.export_to_csv(data)
print('✓ CSV export successful')

# JSON test
json_result = DataExportService.export_to_json({'test': 'data'})
print('✓ JSON export successful')

# File path test
path = DataExportService.generate_file_path('test', 'txt')
print(f'✓ File path generation successful: {path}')

print('All utility methods working')
"
```
  </verify>
  <done>
- CSV export works with list of dicts
- JSON export works with dicts and lists
- File path generation creates valid paths with timestamps
- Queryset convenience methods work with Django models
- Service is ready for use across codebase
  </done>
</task>

</tasks>

<verification>
**Service Layer:**
- [ ] `upstream/services/data_export.py` exists with DataExportService
- [ ] Service class is stateless with static methods
- [ ] Service exports: export_to_csv, export_to_json, export_to_pdf, queryset_to_csv, queryset_to_json, generate_file_path
- [ ] Each method handles both file writing and buffer returns

**Integration:**
- [ ] `upstream/services/__init__.py` exports DataExportService
- [ ] Service can be imported: `from upstream.services import DataExportService`
- [ ] No existing service exports broken

**Functionality:**
- [ ] CSV export produces valid CSV with headers
- [ ] JSON export produces valid JSON strings
- [ ] File path generation creates directories and adds timestamps
- [ ] Queryset methods work with Django models
</verification>

<success_criteria>
**Measurable outcomes:**
1. `upstream/services/data_export.py` exists with 150+ lines
2. Service class exports 6 static methods
3. `upstream/services/__init__.py` includes DataExportService in __all__
4. Manual tests pass (CSV, JSON, file path generation work)

**Observable behavior:**
- Generic export utilities centralized in one service
- Any code can import and use export functions
- No duplication of CSV/JSON/PDF generation logic
- Service follows established stateless pattern
- Future views/tasks can use these utilities instead of inline export code
</success_criteria>

<output>
After completion, create `.planning/quick/019-extract-data-export-service/019-SUMMARY.md` following the standard template with:
- Changes made (new service, updated exports)
- Files created/modified
- Manual test verification results
- Examples of how to use the service
</output>
