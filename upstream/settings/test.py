"""
Test settings for Upstream Healthcare Platform.
Optimized for fast test execution with in-memory databases
and simplified configurations.
"""
from .base import *  # noqa: F403, F405
import os

# Override SECRET_KEY for tests (not used in production)
SECRET_KEY = "test-secret-key-not-for-production-use-only"  # pragma: allowlist secret  # noqa: E501

# JWT Settings for tests
SIMPLE_JWT["SIGNING_KEY"] = SECRET_KEY  # noqa: F405

# Use in-memory SQLite for fast tests (override DATABASE_URL if set)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# If DATABASE_URL is explicitly set (like in CI), use it instead
if "DATABASE_URL" in os.environ:
    import dj_database_url

    DATABASES["default"] = dj_database_url.config(
        default=os.environ["DATABASE_URL"],
        conn_max_age=0,  # Don't reuse connections in tests
    )

# Use in-memory cache for tests
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-cache",
    }
}

# Disable password hashing for faster user creation in tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Fast email backend for tests
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Disable Celery in tests
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Disable migrations for faster test database creation (optional)
# Uncomment if test suite becomes slow:
# class DisableMigrations:
#     def __contains__(self, item):
#         return True
#     def __getitem__(self, item):
#         return None
# MIGRATION_MODULES = DisableMigrations()

# Disable logging during tests to reduce noise
LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "CRITICAL",
        },
    },
}

# Test-specific feature flags
SLACK_ENABLED = False
ALERT_ATTACH_PDF = False

# Minimal CORS for tests
CORS_ALLOWED_ORIGINS = ["http://localhost:3000", "http://testserver"]

# Set field encryption key for tests
if not FIELD_ENCRYPTION_KEY:  # noqa: F405
    FIELD_ENCRYPTION_KEY = "test-encryption-key-32-bytes-long!!"  # noqa: F405

# Portal URL for email template tests
PORTAL_BASE_URL = "http://testserver"

# Debug mode off in tests (matches production behavior)
DEBUG = False

# Allowed hosts for tests
ALLOWED_HOSTS = ["*"]

# Disable browser reload middleware in tests
MIDDLEWARE = [m for m in MIDDLEWARE if "BrowserReloadMiddleware" not in m]  # noqa: F405

# Remove prometheus middleware in tests (cleaner test output)
MIDDLEWARE = [  # noqa: F405
    m
    for m in MIDDLEWARE  # noqa: F405
    if "PrometheusBeforeMiddleware" not in m
    and "PrometheusAfterMiddleware" not in m
]
