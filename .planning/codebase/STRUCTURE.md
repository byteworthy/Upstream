# Codebase Structure

**Analysis Date:** 2026-01-26

## Directory Layout

```
/workspaces/codespaces-django/
├── hello_world/                    # Django project wrapper (WSGI/ASGI entry point)
│   ├── settings.py                # Imports settings from upstream.settings.dev
│   ├── urls.py                    # Root URL router (main, admin, API)
│   ├── asgi.py                    # ASGI entry for async servers
│   ├── wsgi.py                    # WSGI entry for traditional servers
│   ├── core/                      # Core web views and templates
│   ├── static/                    # Static files (CSS, JS, images)
│   └── templates/                 # HTML templates for web interface
│
├── upstream/                       # Main Django application (multi-tenant SaaS)
│   ├── models.py                  # Core domain models (Customer, Upload, ClaimRecord, etc.) - 966 lines
│   ├── models_agents.py           # Agent-specific models
│   ├── admin.py                   # Django admin configuration
│   ├── urls.py                    # Portal/web interface routes
│   ├── urls_data_quality.py       # Data quality dashboard routes
│   ├── apps.py                    # Django app configuration
│   ├── celery.py                  # Celery configuration and task autodiscovery
│   ├── tasks.py                   # Celery tasks (async operations)
│   ├── cache.py                   # Cache utilities and key definitions
│   ├── constants.py               # Global constants (product choices, etc.)
│   ├── check_env.py               # Environment variable validation
│   ├── env_permissions.py         # Permission/environment checks
│   ├── metrics.py                 # Custom Prometheus metrics
│   ├── middleware.py              # Custom middleware (request tracking, rate limiting, health checks)
│   ├── logging_config.py          # Logging configuration (formatters, handlers)
│   ├── logging_filters.py         # Sensitive data filtering for logs
│   ├── logging_utils.py           # Logging utilities
│   ├── celery_monitoring.py       # Task monitoring and metrics
│   │
│   ├── api/                       # REST API layer
│   │   ├── views.py              # DRF ViewSets (Customer, Upload, Claims, Reports, Alerts, etc.)
│   │   ├── serializers.py        # DRF Serializers (model-to-JSON conversion)
│   │   ├── permissions.py        # Custom permission classes (IsCustomerMember)
│   │   ├── throttling.py         # Custom throttle classes (rate limiting by operation type)
│   │   └── urls.py               # API route definitions, OpenAPI schema routes
│   │
│   ├── core/                      # Core business domain
│   │   ├── models.py              # BaseModel abstract, DomainAuditEvent, ProductConfig
│   │   ├── services.py            # Audit event creation functions
│   │   ├── tenant.py              # CustomerScopedManager for multi-tenant ORM filtering
│   │   ├── data_quality_service.py # CSV validation engine (23 KB)
│   │   ├── quality_reporting_service.py # Report generation for validation results
│   │   ├── validation_models.py   # Validation rule definitions and engine
│   │   ├── default_validation_rules.py # Built-in validation rules
│   │   ├── migrations/            # Database schema migrations
│   │   └── tests_data_quality.py  # Unit tests for validation (35 KB)
│   │
│   ├── services/                  # Domain-specific business logic
│   │   ├── base_drift_detection.py # Abstract drift detection base class
│   │   ├── payer_drift.py         # Payer drift detection algorithm
│   │   ├── evidence_payload.py    # Claim evidence payload construction
│   │   └── tests_evidence_payload.py # Tests for evidence generation
│   │
│   ├── alerts/                    # Alert management system
│   │   ├── models.py              # AlertRule, AlertEvent, WebhookEndpoint, OperatorJudgment
│   │   ├── services.py            # Alert routing, email/Slack/webhook dispatch (27 KB)
│   │   ├── tests_services.py      # Alert service tests (22 KB)
│   │   └── migrations/            # Schema migrations
│   │
│   ├── ingestion/                 # Webhook ingestion system
│   │   ├── models.py              # IngestionToken, WebhookPayload
│   │   ├── services.py            # Token validation, payload parsing
│   │   └── tests.py               # Integration tests (18 KB)
│   │
│   ├── integrations/              # External API integrations
│   │   ├── models.py              # WebhookDelivery, ExternalSystem
│   │   ├── services.py            # Webhook delivery, retry logic
│   │   └── migrations/            # Schema migrations
│   │
│   ├── exports/                   # Report export functionality
│   │   ├── services.py            # PDF/CSV export generation
│   │   └── __init__.py
│   │
│   ├── reporting/                 # Report generation system
│   │   ├── models.py              # ReportRun, ReportArtifact
│   │   ├── services.py            # Report template rendering, data aggregation
│   │   └── migrations/            # Schema migrations
│   │
│   ├── analytics/                 # Analytics and dashboards
│   │   └── (minimal; mostly in views and API serializers)
│   │
│   ├── products/                  # Product line configuration
│   │   └── (minimal; feature flags stored in ProductConfig model)
│   │
│   ├── claims/                    # Claims module (if used)
│   │   └── (minimal or empty)
│   │
│   ├── views/                     # Portal and custom HTTP views
│   │   ├── __init__.py           # Main portal views (dashboard, list views)
│   │   ├── celery_health.py      # Celery health check endpoint
│   │   ├── monitoring_status.py  # System monitoring status endpoint
│   │   └── metrics.py            # Metrics endpoint helpers
│   │
│   ├── settings/                  # Django settings by environment
│   │   ├── base.py               # Shared settings (apps, middleware, databases, security)
│   │   ├── dev.py                # Development settings (DEBUG=True, local DB)
│   │   ├── prod.py               # Production settings (hardened security, external DB)
│   │   ├── test.py               # Test settings (in-memory DB, disabled cache)
│   │   └── __init__.py
│   │
│   ├── management/                # Django management commands
│   │   └── commands/             # Custom CLI operations
│   │
│   ├── fixtures/                  # Test data and sample data
│   │
│   ├── migrations/                # Database schema migrations (13 migration files)
│   │   ├── 0001_initial.py       # Initial schema (183 KB - large)
│   │   ├── 0002-0009_*.py        # Incremental performance and constraint improvements
│   │   ├── 0010_add_missing_indexes_phase3.py
│   │   ├── 0011_add_covering_indexes_phase3.py
│   │   ├── 0012_add_check_constraints_phase3.py
│   │   ├── 0013_*.py             # Most recent constraints
│   │   └── __init__.py
│   │
│   ├── static/                    # Static assets served by Django
│   │
│   ├── templates/                 # HTML templates
│   │   ├── upstream/             # App-specific templates (dashboards, email templates)
│   │   ├── email/                # Email templates for alerts
│   │   └── email_test_template.html
│   │
│   ├── templatetags/              # Custom Django template filters/tags
│   │
│   ├── ui/                        # Frontend components (if React/Vue)
│   │
│   └── __init__.py
│
├── scripts/                       # Utility scripts for common tasks
│   └── (automation, data migration, etc.)
│
├── monitoring/                    # Monitoring configuration
│   ├── grafana/                  # Grafana dashboards (JSON)
│   └── prometheus/               # Prometheus config
│
├── reports/                       # Generated reports output
│
├── logs/                          # Application logs
│   └── archive/                  # Old logs
│
├── .planning/                     # GSD command outputs
│   └── codebase/                 # This analysis
│
├── manage.py                      # Django CLI entry point
├── pyproject.toml                 # Python project metadata
├── requirements.txt               # Python dependencies
├── .env.example                   # Environment variables template
├── .env.production.example        # Production environment template
├── docker-compose.yml             # Local development container setup
├── Dockerfile                     # Production container image
│
└── (test files, CI configs, docs at root)
    ├── smoke_tests.py
    ├── test_*.py                 # Various integration/smoke tests
    ├── .github/workflows/         # GitHub Actions CI/CD
    └── docs/                      # Project documentation
```

## Directory Purposes

**hello_world/**
- Purpose: Django project wrapper providing WSGI/ASGI entry points
- Contains: Settings import, URL routing, static file serving
- Key files: `settings.py` (imports upstream.settings), `urls.py` (root routing), `asgi.py`, `wsgi.py`

**upstream/ (Main App)**
- Purpose: Core SaaS application containing all business logic
- Contains: Models, API, services, background tasks, database schema
- Key patterns: Multi-tenant isolation, DRF ViewSets, Celery tasks

**upstream/api/**
- Purpose: RESTful API layer
- Contains: ViewSets (CRUD endpoints), Serializers (data transformation), Permissions (access control), Throttling (rate limiting)
- Key pattern: `CustomerFilterMixin` ensures all queries filtered to user's customer
- Entry: `/api/v1/` routes in `urls.py`

**upstream/core/**
- Purpose: Core domain models and validation logic
- Contains: Data quality validation engine, audit event services, tenant isolation manager
- Key patterns: Abstract `BaseModel` for audit fields, `CustomerScopedManager` for ORM filtering
- Service: `data_quality_service.py` validates CSV rows against configurable rules (23 KB implementation)

**upstream/services/**
- Purpose: Complex business logic encapsulated as services
- Contains: Drift detection algorithms, evidence payload construction
- Pattern: Stateless functions/classes that operate on models and return domain objects

**upstream/alerts/**
- Purpose: Alert management system
- Contains: AlertRule/AlertEvent models, routing/dispatch logic (email, Slack, webhook)
- Key service: `alerts/services.py` (27 KB) handles all alert operations

**upstream/ingestion/**
- Purpose: Webhook ingestion for external claim systems
- Contains: Token validation, payload parsing, async processing
- Pattern: Token-based auth, immediate 202 response, background task processing

**upstream/integrations/**
- Purpose: Outbound webhook delivery and external API integrations
- Contains: WebhookDelivery model, retry logic, signature generation
- Pattern: Async task delivery with exponential backoff

**upstream/exports/**
- Purpose: Report export functionality (PDF, CSV, Excel)
- Contains: Export format handlers, file generation

**upstream/reporting/**
- Purpose: Report generation system
- Contains: ReportRun/ReportArtifact models, template rendering, data aggregation
- Pattern: Scheduled or on-demand report generation via Celery

**upstream/settings/**
- Purpose: Environment-specific Django configuration
- Contains: Base settings (dev, prod, test variants)
- Pattern: Base settings imported by dev/prod/test, each adds environment-specific overrides

**upstream/migrations/**
- Purpose: Database schema version control
- Contains: 13 migration files (from 0001_initial through 0013_*)
- Recent: Phase 3 optimizations added covering indexes, CHECK constraints, missing indexes

**upstream/templates/**
- Purpose: HTML template rendering
- Contains: Portal dashboards, email templates for alerts
- Pattern: Django template language with context data from views

## Key File Locations

**Entry Points:**

- `hello_world/wsgi.py` - Production WSGI server entry point
- `hello_world/asgi.py` - ASGI server entry point (async)
- `hello_world/urls.py` - Root URL dispatcher
- `upstream/celery.py` - Celery app initialization
- `manage.py` - Django management CLI

**Configuration:**

- `upstream/settings/base.py` - Shared settings (INSTALLED_APPS, MIDDLEWARE, DATABASES, CACHES, etc.)
- `upstream/settings/dev.py` - Development overrides (DEBUG=True, local SQLite or Postgres)
- `upstream/settings/prod.py` - Production overrides (hardened CSRF, HTTPS, external database)
- `upstream/middleware.py` - Request tracking, health checks, rate limiting
- `upstream/logging_config.py` - Structured logging with JSON formatting

**Core Logic:**

- `upstream/models.py` - Main domain models (966 lines)
- `upstream/api/views.py` - DRF ViewSets and API endpoints (31 KB)
- `upstream/core/data_quality_service.py` - CSV validation engine (23 KB)
- `upstream/alerts/services.py` - Alert management and dispatch (27 KB)
- `upstream/services/payer_drift.py` - Drift detection algorithm (11 KB)
- `upstream/tasks.py` - Celery background tasks

**Testing:**

- `upstream/core/tests_data_quality.py` - Quality validation tests (35 KB)
- `upstream/alerts/tests_services.py` - Alert service tests (22 KB)
- `upstream/api/tests.py` - API endpoint tests (10 KB)
- `upstream/ingestion/tests.py` - Ingestion system tests (18 KB)
- Root level: `smoke_tests.py`, `test_*.py` - Integration tests

**Monitoring & Observability:**

- `upstream/metrics.py` - Custom business metrics
- `upstream/celery_monitoring.py` - Task monitoring and metrics (13 KB)
- `upstream/logging_config.py` - Centralized logging setup (18 KB)
- `upstream/logging_filters.py` - PII/PHI redaction (11 KB)
- `upstream/views/monitoring_status.py` - Monitoring status endpoint
- `upstream/views/celery_health.py` - Celery health check

## Naming Conventions

**Files:**

- `models.py` - Django ORM model definitions (one per module/app)
- `services.py` - Business logic services (one per module)
- `views.py` - HTTP view handlers (API or web)
- `serializers.py` - DRF serializers for API (in api/ directory)
- `urls.py` - URL routing definitions
- `permissions.py` - DRF permission classes
- `throttling.py` - DRF throttle classes
- `tasks.py` - Celery async tasks
- `tests_*.py` or `test_*.py` - Test files (prefer `test_` prefix for pytest)
- `*_service.py` - Service modules with business logic (e.g., `data_quality_service.py`)
- `*_models.py` - Model definitions (used when module has both models and services, e.g., `models.py` and `*_models.py`)

**Directories:**

- Lowercase with underscores: `data_quality/`, `api/`, `integrations/`, `alerts/`
- Module names match app names in INSTALLED_APPS
- Subdirectories by function: `migrations/`, `management/`, `templatetags/`

**Classes:**

- PascalCase: `CustomerViewSet`, `DataQualityService`, `AlertRule`, `IngestionToken`
- Mixins suffix with "Mixin": `CustomerFilterMixin`, `BaseModel`
- Managers/QuerySets suffix with "Manager" or "QuerySet": `CustomerScopedManager`

**Functions & Methods:**

- snake_case: `detect_drift_events()`, `create_audit_event()`, `send_alert_task()`
- Task function names match Celery task names: `run_drift_detection_task`

**Constants:**

- UPPERCASE_WITH_UNDERSCORES: `CELERY_ENABLED`, `STATUS_CHOICES`
- Defined in `constants.py` for global app constants

**Models & Database:**

- Singular noun names: `Customer`, `Upload`, `ClaimRecord`, `DriftEvent`
- Relationships use ForeignKey to related model: `customer = models.ForeignKey(Customer)`
- Manager field: `objects = CustomManager()`
- Query methods use `get_queryset()`, `filter()`, `annotate()`

## Where to Add New Code

**New Feature (End-to-End):**

1. **Database Schema**: Define model in `upstream/models.py` or domain-specific module
2. **Migrations**: Auto-generate via `python manage.py makemigrations`, add indexes/constraints if needed in `upstream/migrations/`
3. **API Endpoint**: Add ViewSet in `upstream/api/views.py`, Serializer in `upstream/api/serializers.py`
4. **Service Layer**: Complex logic in `upstream/services/*.py` or domain module
5. **Tests**: Add to `upstream/api/tests.py` or domain-specific `tests.py`
6. **URLs**: Register route in `upstream/api/urls.py`

**New Component/Module (e.g., new product line):**

- Primary code: `upstream/products/` directory with `models.py`, `services.py`, `views.py`
- Tests: `upstream/products/tests.py`
- Registration: Add to INSTALLED_APPS in `upstream/settings/base.py`
- URLs: Add include in `upstream/api/urls.py` if API-facing

**Utilities & Helpers:**

- Shared helpers: `upstream/services/` (stateless functions)
- Validation rules: `upstream/core/validation_models.py` and `default_validation_rules.py`
- Logging utilities: `upstream/logging_utils.py`
- Cache utilities: `upstream/cache.py`
- Constants: `upstream/constants.py`

**Background Tasks:**

- Task definition: `upstream/tasks.py` (add `@shared_task` decorated function)
- Base class: Inherit from `MonitoredTask` for automatic metrics
- Execution: Triggered by Celery beat schedule or explicit queue
- Monitoring: Task health check at `/api/v1/celery/health/`

**API Permissions & Throttling:**

- Permission classes: `upstream/api/permissions.py`
- Throttle classes: `upstream/api/throttling.py`
- Assignment: Apply to ViewSet via `permission_classes = [...]` and `throttle_classes = [...]`

**Database Indexes:**

- Pattern: Add `db_index=True` to field in model, or explicit `indexes = [models.Index(...)]` in Meta
- Large tables (Upload, ClaimRecord, DriftEvent): Use covering indexes for common query patterns
- Example: `models.Index(fields=['customer', 'uploaded_at', 'status'], name='upload_customer_date_status_idx')`

**Validation Rules:**

- Template: Create class inheriting from abstract rule in `upstream/core/validation_models.py`
- Registration: Add instance to `ValidationRule` model or define in `default_validation_rules.py`
- Execution: Service calls `rule.validate(row)` returning True/False + optional error message

## Special Directories

**upstream/migrations/**
- Purpose: Version control for database schema
- Generated: By `python manage.py makemigrations`
- Committed: Yes, always commit migrations
- Pattern: Sequential numbering (0001, 0002, ...), immutable once committed
- Recent activity: Phase 3 optimization added 3 migrations for indexes and constraints

**upstream/fixtures/**
- Purpose: Sample data for tests and development
- Generated: By `python manage.py dumpdata` or manually created JSON
- Committed: Yes
- Loading: `python manage.py loaddata fixture_name.json`

**upstream/management/commands/**
- Purpose: Custom Django management commands
- Pattern: One command per file, inherit from `BaseCommand`
- Execution: `python manage.py command_name --arg=value`
- Typical uses: Data cleanup, reporting, scheduled maintenance

**upstream/templatetags/**
- Purpose: Custom Django template filters and tags
- Pattern: Module with `register = template.Library()`, decorate functions with `@register.filter` or `@register.tag`
- Usage: Load in template with `{% load custom_tags %}`

**monitoring/ & logs/**
- Purpose: Prometheus/Grafana config and application logs
- Generated: Prometheus scrapes `/metrics`, logs written by app
- Committed: Monitoring configs yes, logs no (gitignored)
- Cleanup: Log archive rotated by systemd or external tool

---

*Structure analysis: 2026-01-26*
