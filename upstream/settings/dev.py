"""
Development settings for Upstream project.

Inherits from base settings and adds development-specific configuration.
"""

from .base import *

# =============================================================================
# SECURITY SETTINGS (Development)
# =============================================================================

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config(
    "SECRET_KEY", default="django-insecure-dev-key-change-in-production"
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config("DEBUG", default=True, cast=bool)

ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1").split(",")

# HTTPS settings (disabled in development)
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=False, cast=bool)
SESSION_COOKIE_SECURE = config("SESSION_COOKIE_SECURE", default=False, cast=bool)
CSRF_COOKIE_SECURE = config("CSRF_COOKIE_SECURE", default=False, cast=bool)
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# Update JWT signing key
SIMPLE_JWT["SIGNING_KEY"] = SECRET_KEY

# =============================================================================
# DATABASE
# =============================================================================

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# =============================================================================
# EMAIL CONFIGURATION (Development)
# =============================================================================

EMAIL_BACKEND = config(
    "EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
)

DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="alerts@upstream.cx")

# =============================================================================
# LOGGING (Development)
# =============================================================================

from upstream.logging_config import get_logging_config

# Override base logging with development settings
# - Enables DEBUG level logging
# - Uses SelectivePHIScrubberFilter (less aggressive)
# - Includes debug.log file with verbose output
LOGGING = get_logging_config(
    base_dir=BASE_DIR,
    environment="development",
    log_level="DEBUG",
)

# =============================================================================
# FIELD ENCRYPTION KEY (Development)
# =============================================================================

# Set field encryption key for development (must be valid Fernet key)
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
if not FIELD_ENCRYPTION_KEY:
    # Valid Fernet key for development (NOT for production use)
    FIELD_ENCRYPTION_KEY = (
        "x-MJZzq3Q6Vi3-4tTZP9GHRGGJcPVzo54lBGQXxXRc0="  # pragma: allowlist secret
    )

# =============================================================================
# CODE QUALITY AUDITOR CONFIGURATION
# =============================================================================

CODE_QUALITY_AUDITOR = {
    "enabled": True,
    "block_on_critical": True,
    "block_on_high": False,
    "excluded_paths": [
        "migrations/",
        "tests/",
        "test_*.py",
        "*_test.py",
        "tests_*.py",
        "logging_filters.py",  # PHI detection implementation
        "__pycache__/",
        ".venv/",
        "venv/",
        "staticfiles/",
    ],
    "phi_detection": {
        # Don't flag variable/function names that reference PHI types
        "ignore_variable_names": True,
        # Don't flag comments that mention PHI types
        "ignore_comments": True,
        # Only flag actual PHI values (SSN patterns, real dates, etc.)
        "only_flag_actual_values": True,
        # Whitelist for non-PHI terms that might be flagged
        "whitelist": [
            "blue cross",
            "bcbs",
            "medicare",
            "medicaid",
            "cigna",
            "aetna",
            "humana",
            "united healthcare",
            "ssn_pattern",  # Variable name
            "ssn_reference",  # Variable name
            "dob_reference",  # Variable name
            "mrn_reference",  # Variable name
            "patient_name_variable",  # Variable name
        ],
    },
}

# Test Coverage Analyzer
TEST_COVERAGE_THRESHOLDS = {
    "overall": 75,
    "critical_paths": 100,  # PHI detection, auth, tenant isolation
}

# HIPAA Compliance Monitor
HIPAA_COMPLIANCE_CHECKS = {
    "session_timeout": 1800,  # 30 minutes
    "require_audit_logging": True,
    "require_field_encryption": True,
}
