# Coding Conventions

**Analysis Date:** 2026-01-26

## Naming Patterns

**Files:**
- Python modules use lowercase with underscores: `payer_drift.py`, `alert_services.py`
- Test files follow patterns: `test_*.py`, `tests_*.py`, or `tests.py` (see pytest.ini)
- Class-based modules use PascalCase for class names: `DenialScopeComputationService`

**Functions:**
- Snake_case for all function definitions: `compute_weekly_payer_drift()`, `evaluate_drift_event()`
- Private functions prefixed with underscore: `_is_suppressed()`, `_log_context()`
- Task functions use descriptive names with `_task` suffix: `run_drift_detection_task()`, `send_alert_task()`

**Variables:**
- Snake_case for all variable names: `baseline_records`, `drift_event`, `customer_id`
- Constants in UPPER_CASE: `DRIFT_BASELINE_DAYS`, `ALERT_SUPPRESSION_COOLDOWN_HOURS`, `SEVERITY_THRESHOLD_CRITICAL`
- Private variables prefixed with underscore: `_log_context`, `_request_start_time`

**Types:**
- Django model fields use lowercase: `uploaded_at`, `decided_date`, `allowed_amount`
- Serializer fields match model fields or add computed fields with SerializerMethodField: `delta_percent`, `severity_label`
- Type hints used extensively: `from typing import Optional, Dict, Any`

## Code Style

**Formatting:**
- Tool: Black (configured in `.pre-commit-config.yaml`)
- Line length: 88 characters (Black default)
- Configured in `.pre-commit-config.yaml`: `args: ['--line-length=88']`

**Linting:**
- Tool: Flake8 (configured in `.pre-commit-config.yaml`)
- Line length: 88 characters
- Ignored rules: E203, W503 (whitespace rules conflicting with Black)
- Configured: `args: ['--max-line-length=88', '--extend-ignore=E203,W503']`

**Code Organization:**
- Imports organized in groups: standard library, third-party, local/relative
- Type checking imports guarded: `if TYPE_CHECKING:` (coverage exclusion in pytest.ini)

## Import Organization

**Order:**
1. Standard library imports (e.g., `typing`, `datetime`, `logging`)
2. Django imports (e.g., `from django.db`, `from django.conf`)
3. Third-party imports (e.g., `rest_framework`, `celery`)
4. Local/relative imports (e.g., `from upstream.models`, `from .services`)

**Path Aliases:**
- No special path aliases configured; uses Django app-relative imports
- Absolute imports preferred: `from upstream.models import Customer`

**Example (from `upstream/alerts/services.py`):**
```python
import logging
import os
import uuid
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from .models import AlertRule, AlertEvent, NotificationChannel
from upstream.services.evidence_payload import (
    build_driftwatch_evidence_payload,
    get_alert_interpretation,
)
from upstream.constants import (
    ALERT_SUPPRESSION_COOLDOWN_HOURS,
    ALERT_SUPPRESSION_NOISE_WINDOW_DAYS,
    ...
)
```

## Error Handling

**Patterns:**
- Exceptions raised explicitly for known error conditions
- Try/except blocks used for transactional operations (see `upstream/services/payer_drift.py`)
- Django's transaction.atomic() used for database consistency
- Logging on error with context: `logger.error(f"Error in drift detection task for customer {customer_id}: {str(e)}")`
- Custom exceptions inherit from Django's exception classes where applicable

**Example (from `upstream/tasks.py`):**
```python
try:
    customer = Customer.objects.get(id=customer_id)
    results = detect_drift_events(customer, **kwargs)
    logger.info(f"Completed drift detection for customer {customer_id}: {len(results)} events")
    return {"customer_id": customer_id, "events_detected": len(results), "status": "success"}
except Exception as e:
    logger.error(f"Error in drift detection task for customer {customer_id}: {str(e)}")
    raise
```

## Logging

**Framework:** Python's standard `logging` module (configured in `upstream/logging_config.py`)

**Patterns:**
- Get logger with module name: `logger = logging.getLogger(__name__)`
- Use contextual logger adapter for automatic context injection: `from upstream.logging_utils import get_logger`
- Log at appropriate levels: DEBUG for detailed, INFO for state changes, ERROR for failures
- Structured logging with extra dict: `logger.info("message", extra={'key': 'value'})`
- Context variables set via: `set_log_context(customer_id=..., user_id=...)`

**Example (from `upstream/logging_utils.py`):**
```python
logger = get_logger(__name__)

# Context automatically included in all subsequent logs
with add_log_context(customer_id=customer.id, user_id=user.id):
    logger.info("Processing upload", extra={'upload_id': upload.id})
```

## Comments

**When to Comment:**
- Explain "why" not "what" - the code should be self-documenting
- Add comments for non-obvious logic or temporary workarounds
- Reference issue numbers or technical debt items: `# HIGH-14: Add db_index for query performance`
- Add comments for performance optimizations explaining the trade-off

**JSDoc/TSDoc:**
- Function docstrings follow Google style with Args, Returns, Raises sections
- Module-level docstrings describe purpose and key functions

**Example (from `upstream/services/payer_drift.py`):**
```python
def compute_weekly_payer_drift(
    customer: Customer,
    baseline_days: int = DRIFT_BASELINE_DAYS,
    current_days: int = DRIFT_CURRENT_DAYS,
    min_volume: int = DRIFT_MIN_VOLUME,
    as_of_date: Optional[date] = None,
    report_run: Optional[ReportRun] = None,
) -> ReportRun:
    """
    Compute payer drift metrics and create DriftEvent records.

    Args:
        customer: Customer object
        baseline_days: Number of days in baseline window (default from constants)
        current_days: Number of days in current window (default from constants)
        min_volume: Minimum volume threshold for both windows (default from constants)
        as_of_date: Date to use as reference point (defaults to today)
        report_run: Optional existing ReportRun to use (creates new if None)

    Returns:
        ReportRun object with results
    """
```

## Function Design

**Size:** Functions kept relatively small (<100 lines) with clear single responsibility

**Parameters:**
- Use type hints: `def function(customer: Customer, days: int = 30) -> Dict[str, Any]:`
- Prefer keyword arguments for clarity
- Use dataclasses or named tuples for complex parameter sets

**Return Values:**
- Include type hints on all functions
- Return dicts with consistent keys: `{"status": "success", "count": 0, "errors": []}`
- Raise exceptions rather than return error status codes

## Module Design

**Exports:**
- Explicit imports from modules: `from .models import AlertRule, AlertEvent`
- Functions exported at module level; no "barrel" files pattern
- Django models imported from `upstream.models`
- Services imported from `upstream.services` or product-specific paths

**Barrel Files:**
- Not used; imports are explicit and specific
- `__init__.py` files in packages are minimal

## Class and Model Design

**Django Models:**
- Inherit from `django.db.models.Model`
- Use descriptive field names: `uploaded_at`, `decided_date`, `allowed_amount`
- Add db_index=True for frequently queried fields (see `upload_at`, `date_min`, `date_max` in Upload model)
- Include help_text for clarity: `help_text="SHA-256 hash for deduplication"`
- Use choices for categorical fields with UPPERCASE constants

**Example (from `upstream/models.py`):**
```python
class Upload(models.Model):
    STATUS_CHOICES = [
        ("processing", "Processing"),
        ("success", "Success"),
        ("failed", "Failed"),
        ("partial", "Partial Success"),
    ]

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="uploads"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True, db_index=True)
    filename = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="processing"
    )
    validation_errors = models.JSONField(
        default=list, blank=True, help_text="Summary of validation errors by type"
    )
```

**Services:**
- Class-based services: `class DenialScopeComputationService:`
- Service methods return dicts or Django model instances
- Initialization accepts required context (customer, etc.)

**API Views/Serializers:**
- Use DRF's `viewsets.ModelViewSet` for CRUD operations
- Mixins used for common functionality (e.g., `CustomerFilterMixin`)
- Serializers inherit from `serializers.ModelSerializer` or `serializers.Serializer`

## Tenant Isolation Pattern

**Standard Approach:**
- All views use `CustomerFilterMixin` to auto-filter by user's customer
- Models have custom managers: `objects = CustomerScopedManager()` and `all_objects = models.Manager()`
- Context manager used: `from upstream.core.tenant import customer_context`
- Tests set customer context in setUp/tearDown

**Example (from tests):**
```python
def setUp(self):
    self.customer = Customer.objects.create(name="Test Healthcare Corp")
    set_current_customer(self.customer)

def tearDown(self):
    clear_current_customer()
```

---

*Convention analysis: 2026-01-26*
