# Technology Stack

**Analysis Date:** 2026-01-26

## Languages

**Primary:**
- Python 3.12 - Backend application and business logic (`upstream/`, management commands, tests)

**Secondary:**
- JavaScript/TypeScript - Frontend development (optional, used via docker-compose for separate frontend service on port 3000)
- YAML - Configuration files (docker-compose, GitHub Actions, Prometheus)

## Runtime

**Environment:**
- Python 3.12-slim (Docker base image: `python:3.12-slim`)

**Package Manager:**
- pip with constraints and lock files
  - `requirements.txt` - Version constraints (~= semver) for dependencies
  - `requirements-lock.txt` - Exact pinned versions for reproducible production deployments

## Frameworks

**Core:**
- Django 5.2.2 - Web framework and ORM
- Django REST Framework 3.15.0 - REST API implementation
- djangorestframework-simplejwt 5.3.0 - JWT authentication for APIs

**Task Processing:**
- Celery 5.3.4 - Asynchronous task queue for background jobs
- Redis 5.0.1 - Message broker and result backend for Celery (also used for caching)

**Testing:**
- pytest 8.3.3 - Test runner
- pytest-django 4.9.0 - Django pytest plugin
- pytest-cov 6.0.0 - Coverage reporting

**Build/Dev:**
- Gunicorn 23.0.0 - Production WSGI server (2 workers, 4 threads, gthread worker class)
- WhiteNoise 6.6.0 - Static file serving in production
- django-browser-reload 1.13.0 - Development auto-reload for HTML/CSS changes

## Key Dependencies

**Security & Compliance:**
- django-encrypted-model-fields 0.6.5 - Field-level encryption for PHI data
- django-auditlog 3.0.0 - Audit trail logging for HIPAA compliance
- cryptography 42.0.0 - Cryptographic operations (Fernet key generation, field encryption)

**API Layer:**
- django-cors-headers 4.3.0 - CORS support for cross-origin requests
- drf-spectacular 0.27.0 - OpenAPI 3.0 schema generation and documentation

**Performance & Quality:**
- prometheus-client 0.19.0 - Prometheus metrics export
- django-prometheus 2.3.1 - Django-specific Prometheus instrumentation
- sentry-sdk[django] 1.40.0 - Error tracking and APM (optional, requires SENTRY_DSN)

**Reporting & Email:**
- django-anymail 11.0 - Unified email backend (supports Mailgun, SendGrid, etc.)
- weasyprint 62.0 - HTML-to-PDF rendering for alert reports
- openpyxl 3.1.2 - Excel file generation for exports

**Database & Configuration:**
- psycopg2-binary 2.9.9 - PostgreSQL database adapter
- dj-database-url 2.1.0 - Database URL parsing (12-factor app pattern)
- python-decouple 3.8 - Environment variable management

**Development & Monitoring:**
- locust 2.20.0 - Load testing framework
- memory-profiler 0.61.0 - Memory usage profiling
- sqlparse 0.5.1 - SQL parsing (Django dependency)

## Configuration

**Environment:**
- Configuration via environment variables using `python-decouple` (config function)
- Critical variables:
  - `SECRET_KEY` - Django secret (required in production, auto-generated in dev)
  - `DEBUG` - Debug mode (True in dev, False in production)
  - `ALLOWED_HOSTS` - Comma-separated list of allowed hostnames
  - `DATABASE_URL` or individual `DB_*` variables - PostgreSQL connection
  - `REDIS_URL` - Redis connection for caching and Celery
  - `FIELD_ENCRYPTION_KEY` - Fernet key for PHI encryption (required when `REAL_DATA_MODE=True`)
  - `REAL_DATA_MODE` - Boolean to enable/disable real patient data handling
  - `PORTAL_BASE_URL` - Base URL for portal links in emails

**Build:**
- `Dockerfile` - Multi-stage build optimized for Google Cloud Run
  - Development target: Django development server with auto-reload
  - Production target: Gunicorn with optimized settings
- `docker-compose.yml` - Local development orchestration:
  - PostgreSQL 15 (alpine) on port 5432
  - Redis 7 (alpine) on port 6379
  - Django web service on port 8000
  - Celery worker for async tasks
  - Celery Beat for scheduled tasks
  - Prometheus on port 9090 (metrics collection)
  - Grafana on port 3000 (metrics visualization)

**Settings Files:**
- `upstream/settings/base.py` - Shared settings (all environments)
- `upstream/settings/dev.py` - Development overrides (console email, SQLite fallback)
- `upstream/settings/prod.py` - Production enforcements (HTTPS, real email, Sentry integration)
- `upstream/settings/test.py` - Testing overrides (in-memory cache, test database)

## Platform Requirements

**Development:**
- Python 3.12
- PostgreSQL 15+ (or SQLite fallback for local dev)
- Redis 7+ (optional, falls back to local memory cache)
- Docker & Docker Compose (recommended for consistency)

**Production:**
- PostgreSQL 15+ with SSL support (`sslmode=require`)
- Redis 7+ for Celery broker and result backend
- Deployed on Google Cloud Run (requires PORT environment variable)
- HTTPS/TLS required (SECURE_SSL_REDIRECT=True)
- Email service: Mailgun or SendGrid (via django-anymail) or console backend for MVP
- Sentry account (optional, for error tracking)

## Static Files & Storage

**Static Files:**
- WhiteNoise handles compression and caching in production
- Storage backend: `whitenoise.storage.CompressedManifestStaticFilesStorage`
- Static root: `/app/hello_world/staticfiles` (collected during Docker build)

**Media Files:**
- Local filesystem: `/app/hello_world/media`
- Generated reports (PDFs, Excel) stored here
- Must be mounted as persistent volume in production

---

*Stack analysis: 2026-01-26*
