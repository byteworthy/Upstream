# Changelog

All notable changes to this project will be documented in this file.

## [0.4.0] - 2026-01-19

### Added
- Product line scaffolding (Sprint 1)
- ProductConfig model for customer-level product enablement
- Product enablement gating (middleware + view mixin)
- DenialScope dashboard stub (empty state only)
- Insights feed stub (SystemEvent-driven)
- Enablement navigation gating in base template
- New tests for product enablement and navigation

### Notes
- Scaffolding only; no new product analytics implemented
- Payrixa Core logic remains in place (no refactor)

## [0.3.0] - 2026-01-17

### Added
- **Platform Hardening Complete (Chunks 7-17)**
  - Chunk 13: Slack integration with advanced routing rules (ba8a00c)
  - Chunk 14: RBAC granularity and configuration UI (78faa62)
  - Chunk 15: Excel export system with multi-sheet support (e3411c9)
  - Chunk 16: Data retention policies and rate limiting (bcd55aa)
  - Chunk 17: Ingestion spine and event log architecture (48a4d49)

### Chunk 15: Excel Export System
- Multi-sheet Excel exports (summary + details tabs)
- Customer-scoped exports with tenant isolation
- Audit logging for compliance
- BytesIO streaming (no disk I/O)
- Export service for drift events, alert events, weekly summaries
- Added openpyxl~=3.1.2

### Chunk 16: Operational Hardening
- Data retention policies with configurable timeframes
  - Uploads: 90 days
  - Drift events: 180 days (orphaned only)
  - Report runs: 365 days
  - CSV artifacts: 30 days
  - PDF artifacts: 90 days
- Management command `cleanup_old_data` with dry-run mode
- In-memory rate limiting middleware (100 req/60s default)
- Per-IP request tracking with automatic cleanup
- 429 responses with Retry-After headers

### Chunk 17: Ingestion Spine (Critical Architecture)
- **IngestionService**: Unified entry point for all data sources
  - Supports batch upload, webhook, API, streaming modes
  - Idempotency key support to prevent duplicates
  - Durable IngestionRecord model with status tracking
- **SystemEvent**: Append-only event log for audit and fanout
  - Event types: ingestion_received, ingestion_processed, drift_detected, alert_created, etc.
  - Links to related objects (ingestion, drift, alerts)
  - Request ID tracking for distributed tracing
- **publish_event()**: Single fanout point for all system events
- **Webhook ingestion endpoint**: `/api/v1/ingest/webhook/`
  - Token-based authentication (IngestionToken model)
  - Token rotation and expiration support
  - Rate limiting and RBAC enforced
- **Clean architecture seams** for future modules (DenialScope, ContractIQ, etc.)

### Technical
- Added packages: openpyxl
- New models: IngestionRecord, SystemEvent, IngestionToken
- New middleware: SimpleRateLimitMiddleware
- New management commands: cleanup_old_data
- Migration: 0008_alter_domainauditevent_action_ingestionrecord_and_more

## [0.2.0] - 2026-01-14

### Added
- **REST API Layer** — Full Django REST Framework implementation
  - JWT authentication with token refresh
  - Multi-tenant permission system (IsCustomerMember)
  - ViewSets for all core models
  - OpenAPI documentation (Swagger/ReDoc) at `/api/v1/docs/`
  - Dashboard endpoint with aggregate statistics
  - Health check endpoint
- **Security & Compliance**
  - django-auditlog for HIPAA-compliant audit trails
  - django-encrypted-model-fields for PHI encryption
  - Enhanced session security (1-hour timeout, secure cookies)
  - 12-character minimum password requirement
  - Rate limiting on API endpoints
- **Demo Data Fixture** — `python manage.py loaddata demo_data` for onboarding
- **Enhanced Configuration**
  - Comprehensive `.env.example` with all settings documented
  - PostgreSQL configuration ready (commented for production)
  - CORS settings for frontend clients
  - Email configuration via Anymail

### Changed
- Renamed project from 'DriftWatch' to 'Payrixa' across codebase
- Reorganized settings.py with clear section headers
- README polished with brand voice, tech stack rationale, and roadmap
- Minimum password length increased to 12 characters

### Technical
- Added packages: djangorestframework, djangorestframework-simplejwt, django-cors-headers, drf-spectacular, django-auditlog, django-encrypted-model-fields, django-anymail, weasyprint, psycopg2-binary, django-q2

## [0.1.0] - 2026-01-12

### Added
- Initial project structure with Django 5.x
- Multi-tenant Customer model
- ClaimRecord model with CSV upload processing
- Payer name normalization (PayerMapping)
- CPT code grouping (CPTGroupMapping)
- Weekly payer drift detection algorithm
- ReportRun and DriftEvent models
- Management command: `run_weekly_payer_drift`
- Basic web portal templates

## Roadmap

### Phase 2 (Planned)
- Trend visualization charts
- Custom date range analysis
- Email alert delivery with PDF attachments
- CPT group-level drift detection

### Phase 3 (Planned)
- SSO/SAML authentication
- Role-based access control
- Webhook integrations
- API rate limit dashboard
