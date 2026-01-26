# Architecture

**Analysis Date:** 2026-01-26

## Pattern Overview

**Overall:** Layered Django Application with Multi-Tenant Architecture

**Key Characteristics:**
- Multi-tenant isolation at the ORM level using `CustomerScopedManager`
- RESTful API layer built with Django REST Framework
- Asynchronous task processing via Celery for heavy operations
- Domain-driven modules for distinct business concerns (alerts, drift detection, reporting)
- Middleware-based request tracking and metrics collection
- Explicit audit logging for compliance and debugging

## Layers

**Presentation Layer (API):**
- Purpose: RESTful endpoints for client-server communication
- Location: `upstream/api/` (views, serializers, permissions, throttling)
- Contains: ViewSets, Serializers, API permissions, authentication views, throttle classes
- Depends on: Models, Services, Auth
- Used by: Frontend clients, external integrations, webhooks

**API Views:**
- Location: `upstream/api/views.py`
- Pattern: DRF ViewSets with `CustomerFilterMixin` for multi-tenant filtering
- Key ViewSets: `CustomerViewSet`, `UploadViewSet`, `ClaimRecordViewSet`, `ReportRunViewSet`, `AlertEventViewSet`, `DriftEventViewSet`
- Auth: JWT tokens with rate limiting on auth endpoints (`ThrottledTokenObtainPairView`)

**Service Layer:**
- Purpose: Business logic and domain operations
- Location: `upstream/services/`, `upstream/alerts/services.py`, `upstream/integrations/services.py`, `upstream/exports/services.py`, `upstream/core/`
- Contains: Drift detection, alert management, webhook delivery, audit event creation, data quality validation
- Depends on: Models, external APIs, caching
- Used by: Views, Tasks, Management commands

**Model Layer (Persistence):**
- Purpose: Data persistence and relationships
- Location: `upstream/models.py`, `upstream/core/models.py`, `upstream/alerts/models.py`, etc.
- Contains: Customer, Upload, ClaimRecord, ReportRun, DriftEvent, AlertEvent, DomainAuditEvent, etc.
- Features: Multi-tenant isolation via `CustomerScopedManager`, CHECK constraints for data integrity, comprehensive indexing for query optimization
- Relationships: Customer as root aggregate, related entities scoped to customer

**Task Layer (Asynchronous):**
- Purpose: Background job processing for long-running operations
- Location: `upstream/tasks.py`, `upstream/celery.py`
- Contains: `run_drift_detection_task`, `send_alert_task`, `send_webhook_task`, `generate_report_task`
- Base: All tasks inherit from `MonitoredTask` for automatic metrics tracking
- Queue: Redis-backed Celery with monitoring via `upstream/celery_monitoring.py`

**Integration Layer:**
- Purpose: External API communication and data ingestion
- Location: `upstream/integrations/services.py`, `upstream/ingestion/services.py`
- Contains: Webhook delivery, token-based ingestion, external API clients
- Pattern: Services encapsulate external dependencies, allowing tests to mock easily

**Middleware Layer:**
- Purpose: Cross-cutting concerns before/after request processing
- Location: `upstream/middleware.py`
- Components:
  - `RequestIdMiddleware`: Assigns UUID to each request for tracing
  - `RequestTimingMiddleware`: Tracks request duration
  - `MetricsCollectionMiddleware`: Collects prometheus metrics
  - `ProductEnablementMiddleware`: Enforces product-line feature flags
  - `SimpleRateLimitMiddleware`: Per-IP rate limiting
  - Health check middleware for fast `/health/` responses

## Data Flow

**File Upload Flow:**

1. **Request** → User uploads CSV via `POST /api/v1/uploads/`
2. **API View** → `UploadViewSet.create()` validates customer, file size, encoding
3. **Model Save** → `Upload` record created with `status="processing"`
4. **Task Queue** → Background task triggered to process file
5. **Celery Task** → CSV parsing, row-by-row validation against rules
6. **Quality Service** → `DataQualityService` validates each row, tracks errors/warnings
7. **Model Update** → `DataQualityReport` created with metrics, Upload status set to "success"/"failed"
8. **Audit** → `DomainAuditEvent` logged via `audit_upload_created()`

**Drift Detection Flow:**

1. **Trigger** → Manual API call or scheduled task `run_drift_detection_task(customer_id)`
2. **Service** → `detect_drift_events(customer)` loads customer claims and rules
3. **Analysis** → Payer drift service compares recent claims against historical patterns
4. **Events** → For each detected drift, create `DriftEvent` model
5. **Alerts** → If alert rules match, async task `send_alert_task()` queues alert
6. **Delivery** → Alert service routes to email/Slack/webhook based on rules
7. **Tracking** → `AlertEvent` and `WebhookDelivery` records track outcomes

**Alert Routing & Dispatch:**

1. **Alert Creation** → `AlertEvent` created by drift detection or external trigger
2. **Rule Matching** → Alert service checks configured rules (`AlertRule`) per customer
3. **Channel Selection** → Route via email, Slack webhook, or webhook endpoint based on rule
4. **Task Dispatch** → `send_alert_task()` enqueued with alert ID
5. **Send** → Service attempts delivery; on failure, retries with exponential backoff
6. **Audit** → `WebhookDelivery` model tracks attempt (status, payload, response)

**Claim Record Ingestion:**

1. **Token Auth** → External system posts to `POST /api/v1/ingest/webhook/` with token
2. **Validation** → `WebhookIngestionView` verifies `IngestionToken`
3. **Parsing** → Extract and validate claim fields (date formats, field presence, PHI)
4. **Creation** → Create `ClaimRecord` scoped to customer
5. **Indexing** → Covering indexes support fast queries by (customer, payer, date_of_service)
6. **Audit** → Implicit via auditlog middleware on model creation

**State Management:**

- **Multi-tenant State**: Isolated by `customer_id` field on all models; automatic via `CustomerScopedManager.get_queryset()` filtering
- **Processing State**: Upload status ("processing" → "success"/"failed"), tracked with timing metadata
- **Cache State**: Report aggregates cached in Redis with TTL to balance freshness vs. performance
- **Async State**: Celery task results tracked in monitoring service, no persistent result storage

## Key Abstractions

**BaseModel (Abstract):**
- Purpose: Common audit trail fields for all models
- Location: `upstream/core/models.py`
- Pattern: Provides `created_at`, `updated_at`, `created_by`, `updated_by` to track data lineage
- Used by: Most domain models

**CustomerScopedManager (ORM Manager):**
- Purpose: Automatic multi-tenant filtering to prevent data leakage
- Location: `upstream/core/tenant.py`
- Pattern: Overrides `get_queryset()` to filter by authenticated user's customer
- Models using: `Upload`, `DataQualityReport`, `Settings`, and others
- Behavior: Superusers see all data; regular users see only their customer

**ValidationRule & DataQualityService:**
- Purpose: Pluggable validation logic for CSV rows
- Location: `upstream/core/data_quality_service.py`, `upstream/core/validation_models.py`, `upstream/core/default_validation_rules.py`
- Pattern: Rules defined as Django models, evaluated in isolation per row
- Examples: Required field check, date format validation, PHI detection (regex/pattern matching)

**MonitoredTask (Celery Base):**
- Purpose: Wraps Celery tasks with automatic metrics collection
- Location: `upstream/celery_monitoring.py`
- Pattern: Tracks task start, duration, success/failure in Prometheus metrics
- Features: Records task_name, customer_id, status labels for aggregation

**DriftDetectionService:**
- Purpose: Encapsulates payer claim drift analysis logic
- Location: `upstream/services/payer_drift.py`
- Pattern: Stateless function `detect_drift_events(customer, **kwargs)` returns list of `DriftEvent` records
- Algorithm: Compares claim patterns against configured baselines per payer

**DomainAuditEvent:**
- Purpose: Business-level audit trail (separate from Django's auditlog)
- Location: `upstream/core/models.py`
- Pattern: Explicit action choices (upload_created, report_exported, alert_rule_updated, etc.) with optional metadata
- Indexed by: (customer, action, timestamp), (entity_type, entity_id, timestamp), (user, timestamp)

## Entry Points

**HTTP Entry Points:**

- **Root URL Router**: `hello_world/urls.py` → Maps root "/" and "/admin/" to Django admin, "/portal/" to main app, "/api/v1/" to REST API
- **Main App URLs**: `upstream/urls.py` (portal web interface routes)
- **API URLs**: `upstream/api/urls.py` (RESTful endpoints with OpenAPI schema)
- **Data Quality Dashboards**: `upstream/urls_data_quality.py` (HTML dashboards for internal ops)

**Key API Endpoints:**

- `POST /api/v1/auth/token/` → Get JWT token (rate-limited)
- `GET/POST /api/v1/uploads/` → Manage file uploads
- `GET /api/v1/claims/` → Query claim records (filtered by customer)
- `GET /api/v1/reports/` → View generated reports
- `POST /api/v1/ingest/webhook/` → External claim ingestion
- `GET /api/v1/health/` → Health check (no auth)
- `GET /api/v1/monitoring/status/` → Monitoring status
- `GET /metrics` → Prometheus metrics endpoint

**Management Commands:**

- Location: `upstream/management/commands/`
- Trigger: `python manage.py <command_name>`
- Examples: Data cleanup, periodic maintenance, report generation

**Background Tasks:**

- **Trigger**: Celery beat schedule (via `CELERY_BEAT_SCHEDULE` config) or explicit task queue
- **Examples**: Drift detection scheduled daily, alert retry on failure, webhook delivery retry
- **Monitoring**: Health check at `/api/v1/celery/health/`, task status at `/api/v1/celery/tasks/`

**Webhooks (Incoming):**

- **Endpoint**: `POST /api/v1/ingest/webhook/`
- **Trigger**: External claim systems post claim records
- **Auth**: Token-based (lookup in `IngestionToken` model)
- **Response**: 202 Accepted (async processing)

**Webhooks (Outgoing):**

- **Trigger**: Alert events, report completion
- **Storage**: `WebhookDelivery` records track payload + response
- **Retry**: Exponential backoff if delivery fails
- **Auth**: Webhook endpoint has secret for signature verification

## Error Handling

**Strategy:** Layered error handling with explicit exception types and safe fallbacks

**Patterns:**

1. **API Layer** → `ValidationError` for invalid input, returns 400 with error details
2. **Service Layer** → Domain exceptions (e.g., `CustomerNotFound`, `InvalidDriftThreshold`) propagate up
3. **Task Layer** → Exceptions caught, logged with context, task marked as failed; Celery retry configured
4. **Database Layer** → Constraint violations (CHECK constraints, unique constraints) raise `IntegrityError`, caught and converted to API error response

**Error Response Format (REST):**

```json
{
  "error": "Detailed message or error code",
  "status": 400
}
```

**Logging Strategy:**

- All significant actions logged via `logging` module configured in `upstream/logging_config.py`
- Sensitive data filtered by `upstream/logging_filters.py` (removes PII/PHI)
- Request-scoped logging: each request has unique `request_id` attached to logs
- Structured logging with JSON output in production for log aggregation

## Cross-Cutting Concerns

**Logging:**
- Framework: Python `logging` module with structured JSON output
- Config: `upstream/logging_config.py` defines handler, formatter, filters
- Request Tracking: `RequestIdMiddleware` generates UUID, propagates via thread-local storage
- Sensitive Data: `logging_filters.py` masks credit cards, SSNs, API keys before logging

**Validation:**
- **Input Validation**: Serializers (DRF) validate API requests before view processing
- **CSV Row Validation**: Custom rules engine in `DataQualityService` validates individual rows
- **Database Constraints**: CHECK constraints prevent negative counts, ensure date ranges logical
- **Business Validation**: Services implement domain rules (e.g., alert threshold ranges, payer mapping constraints)

**Authentication:**
- Method: JWT tokens via `rest_framework_simplejwt`
- Token Endpoints: Rate-limited via `AuthenticationThrottle` to prevent brute-force
- Verification: `TokenVerifyView` checks token validity
- Refresh: `TokenRefreshView` issues new token from valid refresh token
- Superuser Fallback: Admin users bypass customer scoping, see all data

**Authorization:**
- **Customer Isolation**: `IsCustomerMember` permission ensures users can only access their customer's data
- **Mixin Filtering**: `CustomerFilterMixin` on ViewSets automatically filters querysets
- **Role Support**: `upstream.models.TeamMember` model tracks user roles per customer (not yet fully implemented in auth)

**Monitoring & Observability:**
- **Metrics**: Prometheus metrics collected via `django_prometheus` middleware
- **Custom Metrics**: Business metrics (uploads processed, drift events detected) via `upstream/metrics.py`
- **Celery Monitoring**: Task execution metrics via `MonitoredTask` and `celery_monitoring.py`
- **Health Checks**: Fast `/health/` endpoint, Celery health at `/api/v1/celery/health/`, monitoring status at `/api/v1/monitoring/status/`
- **Request Tracing**: Request IDs propagated through logs and response headers (`X-Request-Id`)

**Caching:**
- **Framework**: Redis-backed Django cache
- **Usage**: Report aggregates cached with TTL; customer settings cached per request
- **Invalidation**: Time-based TTL (no event-based invalidation currently)

**Rate Limiting:**
- **Authentication Endpoints**: `AuthenticationThrottle` limits token requests to prevent brute-force
- **Report Generation**: `ReportGenerationThrottle` limits heavy operations
- **Bulk Operations**: `BulkOperationThrottle` limits batch uploads
- **Read-Only**: `ReadOnlyThrottle` applied globally to GET requests
- **Fallback**: Memory-based `SimpleRateLimitMiddleware` as backup (production should use Redis)

---

*Architecture analysis: 2026-01-26*
