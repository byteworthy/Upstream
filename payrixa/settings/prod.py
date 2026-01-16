"""
Production settings for Payrixa project.

Inherits from base settings and enforces secure production defaults.
"""

import os
from .base import *

# =============================================================================
# SECURITY SETTINGS (Production)
# =============================================================================

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config("SECRET_KEY")  # Required in production, no default

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False  # Always False in production

# ALLOWED_HOSTS must come from env and must not default to wildcard
ALLOWED_HOSTS = config('ALLOWED_HOSTS').split(',')  # Required in production, no default

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

# Update JWT signing key
SIMPLE_JWT['SIGNING_KEY'] = SECRET_KEY

# =============================================================================
# DATABASE
# =============================================================================

# PostgreSQL configuration for production
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME", default="payrixa"),
        "USER": config("DB_USER", default="payrixa"),
        "PASSWORD": config("DB_PASSWORD", default=""),
        "HOST": config("DB_HOST", default="localhost"),
        "PORT": config("DB_PORT", default="5432"),
        "OPTIONS": {
            "sslmode": "require",  # Required for PHI compliance
        },
    }
}

# Support DATABASE_URL format as well
if 'DATABASE_URL' in os.environ:
    import dj_database_url
    DATABASES['default'] = dj_database_url.parse(config('DATABASE_URL'))

# =============================================================================
# EMAIL CONFIGURATION (Production)
# =============================================================================

# Configure Anymail via env only for production
EMAIL_BACKEND = config('EMAIL_BACKEND', default='anymail.backends.mailgun.EmailBackend')

# Anymail configuration
ANYMAIL = {
    "MAILGUN_API_KEY": config("MAILGUN_API_KEY"),
    "MAILGUN_SENDER_DOMAIN": config("MAILGUN_DOMAIN"),
}

DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='alerts@payrixa.com')

# Email server settings (for SMTP fallback)
EMAIL_HOST = config('EMAIL_HOST', default='smtp.mailgun.org')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
