# External Integrations

**Analysis Date:** 2026-01-26

## APIs & External Services

**Email Delivery:**
- Mailgun (primary for production)
  - SDK/Client: `django-anymail` (11.0)
  - Auth: `MAILGUN_API_KEY`, `MAILGUN_DOMAIN` environment variables
  - Fallback: Console backend (prints to stdout) for development/MVP
  - Alternative: SendGrid supported via `django-anymail`

**Webhook Delivery:**
- Custom outgoing webhook support implemented in `upstream/integrations/services.py`
  - Signed delivery: HMAC-SHA256 signatures on X-Signature header
  - Retry logic: Automatic exponential backoff for failed deliveries
  - Event types: Configurable per endpoint (stored in `WebhookEndpoint` model)
  - Delivery tracking: Full audit trail in `WebhookDelivery` model

**HTTP Clients:**
- `requests` library used throughout for external API calls:
  - Email service integrations: `upstream/alerts/services.py`
  - Webhook delivery: `upstream/integrations/services.py`
  - General HTTP operations in various service modules

## Data Storage

**Databases:**
- PostgreSQL 15+ (production) or SQLite (development)
  - Connection method: `django.db.backends.postgresql`
  - Connection pooling: Django persistent connections (conn_max_age=60s default)
  - SSL support: `sslmode=require` for production
  - Connection env vars: `DATABASE_URL` (preferred) or `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`
  - Audit logging: All model changes tracked via `django-auditlog` (HIPAA compliance)

**Caching:**
- Redis 7+ (production)
  - Connection: `REDIS_URL` environment variable
  - Cache TTL: Variable by data type (5-60 minutes for real-time data, up to 1 hour for user profiles)
  - Fallback: Local in-memory cache if Redis unavailable (LocMemCache with 10k max entries)
  - Session storage: Redis backend for session data
  - Celery broker: Redis database 0
  - Cache database: Redis database 1

**File Storage:**
- Local filesystem only (no cloud storage integration)
  - Static files: `hello_world/staticfiles/` (collected via WhiteNoise)
  - Media files: `hello_world/media/` (user uploads, generated reports)
  - Reports directory: `/app/reports` (mounted as persistent volume in production)
  - Logs directory: `/app/logs` (audit trail and application logs)

## Authentication & Identity

**Auth Provider:**
- Custom Django authentication (not OAuth/SAML)
  - Session-based for web portal (`upstream/views/`, `upstream/ui/`)
  - JWT-based for REST API clients
  - Token implementation: `djangorestframework-simplejwt` (5.3.0)
  - JWT settings: 30-minute access tokens, 1-day refresh tokens, rotation enabled
  - Blacklist: Token blacklist enabled after rotation (high-security)
  - Rate limiting: 5 auth attempts per 15 minutes (brute-force protection)

**User Management:**
- Django built-in User model with custom profile extensions
- Password validation: 12-character minimum (HIPAA-recommended), common password checks
- Session timeout: 30 minutes idle (healthcare security standard)
- CSRF protection: Lax SameSite policy with explicit origin whitelisting

## Monitoring & Observability

**Error Tracking:**
- Sentry (optional, via `sentry-sdk[django]` 1.40.0)
  - Enabled when `SENTRY_DSN` environment variable is set
  - Integrations: Django, Celery, Redis
  - Performance monitoring: 10% trace sample rate
  - PHI scrubbing: Custom `filter_phi_from_errors()` function removes:
    - Request bodies (CSV uploads with patient data)
    - Cookies and query strings
    - User emails
    - Error messages containing patient names
  - Send PII: Disabled (no personally identifiable data)
  - Release tracking: Via `SENTRY_RELEASE` environment variable
  - Multi-server support: `SERVER_NAME` environment variable for deployment correlation

**Metrics & Observability:**
- Prometheus (via `prometheus-client` 0.19.0 and `django-prometheus` 2.3.1)
  - Metrics endpoint: `/metrics/` (auto-registered by django-prometheus)
  - Instrumentation: Middleware-based request/response metrics
  - Tracked metrics: Request duration, status codes, exception counts
  - Docker compose includes: Prometheus server (port 9090) + Grafana (port 3000)
  - Custom app metrics: Alert tracking, report generation, drift detection

**Logging:**
- Structured logging via Python logging module
  - Configuration: `upstream/logging_config.py` (centralized)
  - Rotation: Daily at midnight with retention policies:
    - DEBUG: 7 days
    - INFO: 30 days
    - WARNING/ERROR: 90 days
    - AUDIT: 7 years (HIPAA compliance)
  - PHI scrubbing: All handlers include `PHIScrubberFilter` (aggressive mode in production)
  - Structured output: JSON-compatible format for log aggregation tools (CloudWatch, Datadog, etc.)
  - Request tracking: Request ID middleware adds unique ID to all logs for correlation

**Health Checks:**
- Custom middleware: `HealthCheckMiddleware` (early exit for monitoring services)
- Docker health checks: Container readiness checks for db, redis, web services
- No separate health check endpoint (uses Django admin or custom view)

## CI/CD & Deployment

**Hosting:**
- Google Cloud Run (primary deployment target)
  - Container: Gunicorn + Django on port 8080 (set via PORT env var)
  - Workers: 2 (configurable)
  - Threads: 4 per worker (gthread worker class)
  - Non-root user: appuser (UID 1000) for security
  - Static files: Collected during Docker build, served by WhiteNoise

**Alternative Deployment:**
- Docker (locally via docker-compose)
- Traditional servers (gunicorn + reverse proxy like nginx)

**Docker Build:**
- Multi-stage production Dockerfile
- System dependencies: PostgreSQL client, gcc, Python dev, libcairo (for PDF rendering)
- Requirements: Uses pinned `requirements-lock.txt` for reproducibility
- User: Non-root appuser for security
- Health checks: Database and Redis readiness checks

**CI/CD Pipeline:**
- GitHub Actions (configured in `.github/`)
- Pre-commit hooks: Black, isort, flake8, mypy, secret scanning
- Tests: pytest with coverage reporting

## Environment Configuration

**Required env vars (Production):**
- `SECRET_KEY` - Django secret (50+ characters)
- `DEBUG=False` - Always False in production
- `ALLOWED_HOSTS` - Comma-separated list (no wildcards)
- `DATABASE_URL` or `DB_*` variables - PostgreSQL with SSL
- `REDIS_URL` - Redis broker for Celery
- `FIELD_ENCRYPTION_KEY` - Fernet key (if `REAL_DATA_MODE=True`)
- `DEFAULT_FROM_EMAIL` - Sender email address
- `PORTAL_BASE_URL` - HTTPS URL for email links

**Email configuration (Production):**
- `EMAIL_BACKEND=anymail.backends.mailgun.EmailBackend`
- `MAILGUN_API_KEY` - API key from Mailgun
- `MAILGUN_DOMAIN` - Domain configured in Mailgun

**Error tracking (Optional but recommended):**
- `SENTRY_DSN` - Sentry project DSN for error tracking
- `SENTRY_RELEASE` - Version tag for deployment tracking
- `ENVIRONMENT=production` - Environment name for Sentry filtering

**Security settings (Production):**
- `SECURE_SSL_REDIRECT=True` - Force HTTPS
- `SESSION_COOKIE_SECURE=True` - Secure cookies only
- `CSRF_COOKIE_SECURE=True` - Secure CSRF cookies
- `SECURE_HSTS_SECONDS=31536000` - HSTS for 1 year
- `SECURE_HSTS_INCLUDE_SUBDOMAINS=True` - Include subdomains
- `CSRF_TRUSTED_ORIGINS` - Comma-separated HTTPS origins (if behind proxy)

**Secrets location:**
- Development: `.env` file (git-ignored, chmod 600)
- Production: Environment variables (managed by deployment platform)
- Never: Commit secrets to version control (`.secrets.baseline` baseline file tracked)

## Webhooks & Callbacks

**Incoming:**
- Webhook reception endpoints: `upstream/integrations/views.py`
- Signature verification: HMAC-SHA256 validation on X-Signature header
- Event types configurable per customer/endpoint
- Automatic retry on failure (with exponential backoff)

**Outgoing:**
- Webhook dispatch: `upstream/integrations/services.py` `deliver_webhook()` function
- Uses `requests` library for HTTP POST
- Payload: JSON with event type, data, and metadata (including request_id for tracing)
- Signature header: X-Signature (HMAC-SHA256)
- Delivery audit: Tracked in `WebhookDelivery` model with response codes and error logs
- Retry schedule: Automatic scheduling for failed deliveries
- Request timeout: 30 seconds per delivery attempt

**Alerts & Notifications:**
- Email alerts: Sent via Mailgun/SendGrid (configured backend)
- Slack alerts: Disabled by default (feature flag: `SLACK_ENABLED`)
- PDF attachments: Disabled by default (feature flag: `ALERT_ATTACH_PDF`)

---

*Integration audit: 2026-01-26*
