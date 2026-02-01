"""
Django base settings for Upstream project.

Shared settings that are common to both development and production environments.
"""

import os
from pathlib import Path
from datetime import timedelta
from decouple import config
import redis

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# =============================================================================
# APPLICATION DEFINITION
# =============================================================================

INSTALLED_APPS = [
    # Django core
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party - Security & Compliance
    "auditlog",
    "encrypted_model_fields",
    # Third-party - API
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",  # HIGH-1: Enable JWT blacklist
    "corsheaders",
    "drf_spectacular",
    "django_filters",
    # Third-party - Monitoring
    "django_prometheus",
    # Third-party - Development
    "django_browser_reload",
    # Upstream application
    "upstream.apps.UpstreamConfig",
    "upstream.automation.apps.AutomationConfig",
    "upstream.billing.apps.BillingConfig",
    "upstream.feature_flags.apps.FeatureFlagsConfig",
]

MIDDLEWARE = [
    # Security headers (must be first for early-return responses)
    "upstream.middleware.SecurityHeadersMiddleware",
    "upstream.middleware.HealthCheckMiddleware",  # Early exit for health checks
    "django_prometheus.middleware.PrometheusBeforeMiddleware",
    "django.middleware.security.SecurityMiddleware",
    # QW-3: Compress with min_length=500 (60-80% size reduction)
    "upstream.middleware.ConfigurableGZipMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.http.ConditionalGetMiddleware",  # QW-3: ETag support for caching
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "upstream.middleware.RequestIdMiddleware",
    "upstream.middleware.RequestTimingMiddleware",  # Track request timing
    "upstream.middleware.MetricsCollectionMiddleware",  # Collect metrics
    "upstream.middleware.ProductEnablementMiddleware",
    "auditlog.middleware.AuditlogMiddleware",
    "django_browser_reload.middleware.BrowserReloadMiddleware",
    "upstream.middleware.ApiVersionMiddleware",
    "upstream.middleware.RateLimitHeadersMiddleware",
    # Request validation middleware - validates JSON payloads before view execution
    "upstream.middleware.RequestValidationMiddleware",
    "django_prometheus.middleware.PrometheusAfterMiddleware",
]

X_FRAME_OPTIONS = "DENY"

# =============================================================================
# SECURITY & DATA UPLOAD LIMITS
# =============================================================================

# Limit request body size to prevent DoS attacks via huge webhook payloads
# 10 MB limit (reasonable for structured JSON data, prevents memory exhaustion)
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB in bytes
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB in bytes

ROOT_URLCONF = "hello_world.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "hello_world" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "hello_world.wsgi.application"

# =============================================================================
# AUTHENTICATION & PASSWORD VALIDATION
# =============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},  # HIPAA-recommended minimum
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Password reset link expires after 24 hours
PASSWORD_RESET_TIMEOUT = 86400  # 24 hours in seconds

# Login settings
LOGIN_URL = "/portal/login/"
LOGIN_REDIRECT_URL = "/portal/"
LOGOUT_REDIRECT_URL = "/portal/login/"

# =============================================================================
# DJANGO REST FRAMEWORK
# =============================================================================

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        # Default rates
        "anon": "100/h",
        "user": "1000/h",
        # QW-5: Granular rate limiting for different operation types
        "burst": "60/m",  # High-frequency bursts (1 req/sec)
        "sustained": "10000/d",  # Daily limit for sustained usage
        "report_generation": "10/h",  # Expensive: report generation
        "bulk_operation": "20/h",  # Expensive: file uploads, batch ops
        "read_only": "2000/h",  # Liberal: read operations
        "write_operation": "500/h",  # Moderate: write operations
        "anon_strict": "30/h",  # Very strict for anonymous users
        # Note: DRF throttle parser doesn't support custom time periods like "15m"
        # Using "5/h" as closest approximation (5 per hour instead of 5 per 15 minutes)
        "authentication": "5/h",  # HIGH-2: Prevent brute-force attacks
    },
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "EXCEPTION_HANDLER": "upstream.api.exceptions.custom_exception_handler",
}

# JWT Settings
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": None,  # Will be set in environment-specific settings
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# API Documentation
SPECTACULAR_SETTINGS = {
    "TITLE": "Upstream API",
    "DESCRIPTION": "Early-warning intelligence for healthcare revenue operations",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # Tag-based organization for API documentation
    "TAGS": [
        {
            "name": "Customers",
            "description": "Customer account management and information",
        },
        {
            "name": "Settings",
            "description": "Customer settings and notification preferences",
        },
        {
            "name": "Uploads",
            "description": "File upload processing and claim data ingestion",
        },
        {
            "name": "Claims",
            "description": "Claim record operations and analytics",
        },
        {
            "name": "Reports",
            "description": "Report generation, retrieval, and drift analysis",
        },
        {
            "name": "Drift Detection",
            "description": "Drift event detection and monitoring",
        },
        {
            "name": "Configuration",
            "description": "Payer mappings and CPT group configuration",
        },
        {
            "name": "Alerts",
            "description": "Alert events and operator feedback",
        },
        {
            "name": "Dashboard",
            "description": "Dashboard overview and summary statistics",
        },
        {
            "name": "Webhook Ingestion",
            "description": "Webhook data ingestion endpoints",
        },
        {
            "name": "Health",
            "description": "API health check and service status",
        },
        {
            "name": "Authentication",
            "description": "JWT authentication and token management",
        },
    ],
    # Server configuration for different environments
    "SERVERS": [
        {
            "url": "https://api.upstream.example.com",
            "description": "Production server",
        },
        {
            "url": "http://localhost:8000",
            "description": "Development server",
        },
    ],
    # Security scheme for JWT Bearer authentication
    "SECURITY": [{"Bearer": []}],
    # Component schema configuration
    "COMPONENT_SPLIT_REQUEST": True,  # Separate request/response schemas
    # Postprocessing hooks for future customization
    "POSTPROCESSING_HOOKS": [],
    # Note: Multiple models use 'status' field with different choice sets.
    # drf-spectacular auto-generates enum names (StatusB74Enum, StatusDcfEnum).
    # This doesn't affect functionality - API schema works correctly.
}

# =============================================================================
# CORS SETTINGS
# =============================================================================

CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS", default="http://localhost:3000,http://127.0.0.1:3000"
).split(",")

CORS_ALLOW_CREDENTIALS = True

# Expose custom headers to cross-origin JavaScript clients
# Without this, headers are sent but inaccessible via response.headers.get()
CORS_EXPOSE_HEADERS = [
    "API-Version",  # From ApiVersionMiddleware - track API version
    "X-Request-Id",  # From RequestIdMiddleware - request tracing
    "X-Request-Duration-Ms",  # From RequestTimingMiddleware - perf
    "ETag",  # From ConditionalGetMiddleware - conditional requests
    "Last-Modified",  # Standard caching header
    "Cache-Control",  # Standard caching header
]

# =============================================================================
# AUDIT LOGGING (HIPAA Compliance)
# =============================================================================

AUDITLOG_INCLUDE_ALL_MODELS = True

# =============================================================================
# INTERNATIONALIZATION
# =============================================================================

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# =============================================================================
# STATIC FILES
# =============================================================================

STATICFILES_DIRS = [
    BASE_DIR / "hello_world" / "static",
]

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "hello_world" / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "hello_world" / "media"

# =============================================================================
# DEFAULT FIELD TYPE
# =============================================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# =============================================================================
# LOGGING (Audit Trail with Retention Policy)
# =============================================================================

from upstream.logging_config import get_logging_config  # noqa: E402

# Use centralized logging configuration with:
# - Automatic log rotation (daily at midnight)
# - Retention policies (DEBUG: 7d, INFO: 30d, WARNING/ERROR: 90d, AUDIT: 7y)
# - PHI/PII scrubbing on all handlers (HIPAA compliance)
# - Structured logging for log aggregation
LOGGING = get_logging_config(
    base_dir=BASE_DIR,
    environment="production",  # Overridden in dev.py and test.py
    log_level="INFO",
)

# =============================================================================
# CACHE SETTINGS
# =============================================================================

# Cache Configuration
# Production: Use Redis for high-performance distributed caching
# Development/Testing: Falls back to local memory cache if Redis unavailable
REDIS_URL = config("REDIS_URL", default="redis://localhost:6379")

# Try Redis first, fall back to local memory cache if unavailable
try:
    # Test Redis connection
    r = redis.Redis.from_url(f"{REDIS_URL}/1", socket_connect_timeout=1)
    r.ping()
    r.close()

    # Redis available - use it
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": f"{REDIS_URL}/1",  # Use database 1 for cache
            "KEY_PREFIX": "upstream",
            "TIMEOUT": 300,  # 5 minutes default
        }
    }
    print("✓ Using Redis cache")

except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError, Exception):
    # Redis not available - fall back to local memory cache
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "upstream-cache",
            "OPTIONS": {
                "MAX_ENTRIES": 10000,
            },
            "TIMEOUT": 300,  # 5 minutes default
        }
    }
    print("⚠ Redis unavailable - using local memory cache (development only)")

# Cache timeouts for different data types
CACHE_TTL = {
    "payer_mappings": 60 * 15,  # 15 minutes (frequently accessed, rarely changes)
    "cpt_mappings": 60 * 15,  # 15 minutes (frequently accessed, rarely changes)
    "drift_events": 60 * 5,  # 5 minutes (real-time data, update frequently)
    "alert_events": 60 * 5,  # 5 minutes (real-time data, update frequently)
    "report_runs": 60 * 10,  # 10 minutes (moderate update frequency)
    "quality_reports": 60 * 30,  # 30 minutes (historical data, rarely changes)
    "user_profile": 60 * 60,  # 1 hour (rarely changes during session)
}

# =============================================================================
# CELERY SETTINGS
# =============================================================================

# Celery Configuration
CELERY_BROKER_URL = config("CELERY_BROKER_URL", default=f"{REDIS_URL}/0")
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND", default=f"{REDIS_URL}/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 minutes

# Celery Beat Schedule (for periodic tasks)
CELERY_BEAT_SCHEDULE = {
    # Example: Weekly drift detection (can be triggered manually or scheduled)
    # 'weekly-drift-detection': {
    #     'task': 'upstream.tasks.run_drift_detection',
    #     'schedule': crontab(day_of_week='monday', hour=2, minute=0),
    # },
}

# Enable Celery (can be disabled in development)
CELERY_ENABLED = config("CELERY_ENABLED", default=False, cast=bool)

# =============================================================================
# FLOWER CONFIGURATION
# =============================================================================

# Flower Configuration
# Dashboard for monitoring Celery workers, tasks, and queues
FLOWER_BASIC_AUTH_USERNAME = config("FLOWER_BASIC_AUTH_USERNAME", default="admin")
FLOWER_BASIC_AUTH_PASSWORD = config(
    "FLOWER_BASIC_AUTH_PASSWORD", default="flower_dev_pass"
)
FLOWER_PORT = config("FLOWER_PORT", default="5555", cast=int)
# Note: In production, use strong password and consider additional security
# (VPN, firewall rules, OAuth)

# =============================================================================
# MONITORING ALERTS (Platform Health)
# =============================================================================

# Alert notification channels for platform health monitoring
# These are OPERATOR alerts (system health), distinct from business alerts
MONITORING_ALERTS = {
    "enabled": config("MONITORING_ALERTS_ENABLED", default=True, cast=bool),
    "evaluation_interval": 300,  # seconds (5 minutes)
    "cooldown_period": 300,  # seconds (5 min) - suppress duplicate alerts
    # Email notifications
    "email": {
        "enabled": config("ALERT_EMAIL_ENABLED", default=True, cast=bool),
        "recipients": config(
            "ALERT_EMAIL_RECIPIENTS",
            default="ops@example.com",
            cast=lambda v: [email.strip() for email in v.split(",") if email.strip()],
        ),
        "from_email": config("ALERT_FROM_EMAIL", default="alerts@example.com"),
    },
    # Slack notifications
    "slack": {
        "enabled": config("ALERT_SLACK_ENABLED", default=False, cast=bool),
        "webhook_url": config("ALERT_SLACK_WEBHOOK_URL", default=""),
        "channel": config("ALERT_SLACK_CHANNEL", default="#alerts"),
        "username": "Upstream Monitoring",
        "icon_emoji": ":rotating_light:",
    },
    # Alert thresholds (can be overridden via env vars)
    "thresholds": {
        "error_rate": config(
            "ALERT_THRESHOLD_ERROR_RATE", default=0.05, cast=float
        ),  # 5%
        "response_time_p95": config(
            "ALERT_THRESHOLD_RESPONSE_TIME", default=2000, cast=int
        ),  # ms
        "db_pool_utilization": config(
            "ALERT_THRESHOLD_DB_POOL", default=0.90, cast=float
        ),  # 90%
        "celery_failure_rate": config(
            "ALERT_THRESHOLD_CELERY_FAILURES", default=0.10, cast=float
        ),  # 10%
    },
}

# Prometheus metrics endpoint (for alert rule queries)
PROMETHEUS_METRICS_PATH = "/metrics"

# =============================================================================
# V1 FEATURE FLAGS
# =============================================================================

# V1 ships with email-only alerts. Slack is disabled by default.
SLACK_ENABLED = config("SLACK_ENABLED", default=False, cast=bool)

# V1 ships without PDF attachments due to rendering issues. Can be enabled later.
ALERT_ATTACH_PDF = config("ALERT_ATTACH_PDF", default=False, cast=bool)

# =============================================================================
# PORTAL SETTINGS
# =============================================================================

# Portal base URL used in email templates for links
# Required in production - broken links are a product bug
# Uses os.environ first (for tests), then config (for .env file)
# Default to localhost for dev/test - production should explicitly set this
PORTAL_BASE_URL = os.environ.get(
    "PORTAL_BASE_URL", config("PORTAL_BASE_URL", default="http://localhost:8000")
).rstrip("/")

# =============================================================================
# SECURITY SETTINGS (Common)
# =============================================================================

# Field-level encryption key for PHI data (generate with: Fernet.generate_key())
FIELD_ENCRYPTION_KEY = config("FIELD_ENCRYPTION_KEY", default="")

# Session Security Configuration (Defense-in-depth for HIPAA compliance)
SESSION_ENGINE = (
    "django.contrib.sessions.backends.cache"  # Use Redis for session storage
)
SESSION_CACHE_ALIAS = "default"  # Use default cache (Redis)
SESSION_COOKIE_AGE = 1800  # 30 minutes idle timeout (healthcare standard)
SESSION_EXPIRE_AT_BROWSER_CLOSE = True  # Close browser = logout
SESSION_SAVE_EVERY_REQUEST = (
    True  # Refresh session key on each request (prevents fixation)
)
SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access to session cookie
SESSION_COOKIE_SAMESITE = "Lax"  # CSRF protection (Lax allows normal navigation)
# SESSION_COOKIE_SECURE set in prod.py (requires HTTPS)

# Codespaces configuration
if "CODESPACE_NAME" in os.environ:
    codespace_name = config("CODESPACE_NAME")
    codespace_domain = config("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN")
    CSRF_TRUSTED_ORIGINS = [f"https://{codespace_name}-8000.{codespace_domain}"]
