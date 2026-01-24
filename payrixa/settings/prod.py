"""
Production settings for Payrixa project.

Inherits from base settings and enforces secure production defaults.
"""

import os
from .base import *

# =============================================================================
# WHITENOISE STATIC FILES (Production)
# =============================================================================

# Insert WhiteNoise middleware after SecurityMiddleware
MIDDLEWARE.insert(
    MIDDLEWARE.index('django.middleware.security.SecurityMiddleware') + 1,
    'whitenoise.middleware.WhiteNoiseMiddleware',
)

# WhiteNoise storage backend for compressed and cached static files
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# =============================================================================
# SECURITY SETTINGS (Production)
# =============================================================================

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config("SECRET_KEY")  # Required in production, no default

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False  # Always False in production

# ALLOWED_HOSTS must come from env and must not default to wildcard
# Strip whitespace to avoid invisible bugs
ALLOWED_HOSTS = [h.strip() for h in config('ALLOWED_HOSTS').split(',') if h.strip()]

# HTTPS settings (enabled in production)
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)
SESSION_COOKIE_SECURE = True  # Always True in production
CSRF_COOKIE_SECURE = True  # Always True in production
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# HSTS settings configurable via env
SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=31536000, cast=int)  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = config("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True, cast=bool)
SECURE_HSTS_PRELOAD = config("SECURE_HSTS_PRELOAD", default=True, cast=bool)

# CSRF trusted origins for production (comma-separated domains with scheme)
# Example: CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
_csrf_origins = config('CSRF_TRUSTED_ORIGINS', default='')
if _csrf_origins:
    CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_origins.split(',') if o.strip()]

# Update JWT signing key
SIMPLE_JWT['SIGNING_KEY'] = SECRET_KEY

# =============================================================================
# DATA MODE & ENCRYPTION (PHI Protection)
# =============================================================================

# REAL_DATA_MODE: Set to True when handling real patient data (PHI)
# When True, FIELD_ENCRYPTION_KEY is required and validated
# When False (default), allows MVP demo with synthetic data
REAL_DATA_MODE = config("REAL_DATA_MODE", default=False, cast=bool)

if REAL_DATA_MODE:
    # Production with real PHI - encryption is REQUIRED
    encryption_key = config("FIELD_ENCRYPTION_KEY", default=None)
    
    if not encryption_key:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured(
            "FIELD_ENCRYPTION_KEY is REQUIRED when REAL_DATA_MODE=True. "
            "Generate a key with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    
    if len(encryption_key) < 32:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured(
            f"FIELD_ENCRYPTION_KEY must be at least 32 bytes (got {len(encryption_key)}). "
            "Use Fernet.generate_key() to generate a secure key."
        )
    
    # Override base setting with validated key
    FIELD_ENCRYPTION_KEY = encryption_key
else:
    # MVP demo mode with synthetic data - encryption optional
    # Inherits from base.py (defaults to empty string for dev compatibility)
    pass

# =============================================================================
# DATABASE
# =============================================================================

# Production: Prefer DATABASE_URL for 12-factor compliance
# SSL mode is controlled via the URL itself (e.g., ?sslmode=require for prod)
if 'DATABASE_URL' in os.environ:
    import dj_database_url
    DATABASES = {
        'default': dj_database_url.parse(
            os.environ['DATABASE_URL'],
            conn_max_age=60,
        )
    }
else:
    # Fallback: individual env vars (deprecated, prefer DATABASE_URL)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("DB_NAME", default="payrixa"),
            "USER": config("DB_USER", default="payrixa"),
            "PASSWORD": config("DB_PASSWORD", default=""),
            "HOST": config("DB_HOST", default="localhost"),
            "PORT": config("DB_PORT", default="5432"),
            "OPTIONS": {
                "sslmode": config("DB_SSLMODE", default="require"),
            },
        }
    }

# =============================================================================
# EMAIL CONFIGURATION (Production)
# =============================================================================

# Email backend: configurable via env, defaults to console for MVP
# Set EMAIL_BACKEND=anymail.backends.mailgun.EmailBackend to use Mailgun
EMAIL_BACKEND = config(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.console.EmailBackend'
)

# Anymail configuration (only used if EMAIL_BACKEND is set to Anymail)
# Check if Mailgun credentials are provided
MAILGUN_API_KEY = config("MAILGUN_API_KEY", default=None)
MAILGUN_DOMAIN = config("MAILGUN_DOMAIN", default=None)

if MAILGUN_API_KEY and MAILGUN_DOMAIN:
    # Mailgun is configured - set up Anymail
    ANYMAIL = {
        "MAILGUN_API_KEY": MAILGUN_API_KEY,
        "MAILGUN_SENDER_DOMAIN": MAILGUN_DOMAIN,
    }
    # Email server settings (for SMTP fallback)
    EMAIL_HOST = config('EMAIL_HOST', default='smtp.mailgun.org')
    EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
    EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
    EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
    EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
else:
    # No Mailgun configured - console backend will be used
    # Emails will print to stdout (suitable for MVP/testing)
    pass

DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='alerts@payrixa.com')

# =============================================================================
# ERROR TRACKING (Sentry)
# =============================================================================

SENTRY_DSN = config('SENTRY_DSN', default=None)

if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.redis import RedisIntegration

    def filter_phi_from_errors(event, hint):
        """
        Remove potential PHI from error reports before sending to Sentry.

        CRITICAL: Ensures HIPAA compliance by scrubbing sensitive data.
        """
        # Remove request body (may contain uploaded CSV with PHI)
        if 'request' in event:
            if 'data' in event['request']:
                event['request']['data'] = '[REDACTED FOR HIPAA COMPLIANCE]'

            # Remove cookies (may contain session data)
            if 'cookies' in event['request']:
                event['request']['cookies'] = '[REDACTED]'

            # Scrub query parameters that might contain PHI
            if 'query_string' in event['request']:
                event['request']['query_string'] = '[REDACTED]'

        # Remove user email (PII)
        if 'user' in event:
            if 'email' in event['user']:
                event['user']['email'] = '[REDACTED]'

        # Scrub exception values that might contain PHI
        if 'exception' in event:
            for exc in event['exception'].get('values', []):
                if 'value' in exc:
                    # Redact common PHI patterns in error messages
                    exc_value = str(exc['value'])
                    # Look for patient name patterns (Title Case 2-3 words)
                    if any(word.istitle() for word in exc_value.split()):
                        exc['value'] = '[ERROR MESSAGE REDACTED - MAY CONTAIN PHI]'

        return event

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
            RedisIntegration(),
        ],
        environment=config('ENVIRONMENT', default='production'),

        # Performance monitoring (10% of transactions)
        traces_sample_rate=0.1,

        # Send only errors and warnings (not info/debug)
        # This reduces noise and focuses on actionable issues
        # Note: Django DEBUG=False already filters debug logs

        # HIPAA Compliance: Scrub PHI before sending
        before_send=filter_phi_from_errors,

        # Never send PII
        send_default_pii=False,

        # Release tracking for deployment correlation
        release=config('SENTRY_RELEASE', default=None),

        # Attach server name for multi-server deployments
        server_name=config('SERVER_NAME', default=None),
    )
else:
    # Sentry not configured - errors will only appear in logs
    pass
