"""
Production environment validation.

Call from gunicorn prestart hook or docker entrypoint to fail fast
with a clear message when required env vars are missing.

V1 MVP: Mailgun is NOT required yet. Email backend can be configured later.
PORTAL_BASE_URL is required to ensure all links in emails are correct.
"""
import os
import sys

# Core required vars for production deployment
REQUIRED_VARS = [
    'SECRET_KEY',
    'ALLOWED_HOSTS',
    'PORTAL_BASE_URL',  # Required - broken links are a product bug
]

# Email provider vars - optional until provider is chosen
# When ready for Mailgun, move these to REQUIRED_VARS
EMAIL_PROVIDER_VARS = [
    'MAILGUN_API_KEY',
    'MAILGUN_DOMAIN',
]

# Optional vars with recommended defaults
RECOMMENDED_VARS = [
    'DATABASE_URL',
    'DEFAULT_FROM_EMAIL',
    'EMAIL_BACKEND',  # Defaults to console in dev, anymail in prod
]


def validate_env():
    """Validate required environment variables are set."""
    missing = [var for var in REQUIRED_VARS if not os.getenv(var)]
    
    if missing:
        print(f"ERROR: Missing required env vars: {', '.join(missing)}")
        print("\nRequired variables:")
        for var in REQUIRED_VARS:
            status = "✓" if os.getenv(var) else "✗"
            print(f"  {status} {var}")
        print("\nSet these in your environment or .env file before starting.")
        sys.exit(1)
    
    # Check email provider (optional but warn)
    email_backend = os.getenv('EMAIL_BACKEND', '')
    if 'anymail' in email_backend.lower() or 'mailgun' in email_backend.lower():
        missing_email = [var for var in EMAIL_PROVIDER_VARS if not os.getenv(var)]
        if missing_email:
            print(f"WARNING: Mailgun backend configured but missing: {', '.join(missing_email)}")
            print("  Email delivery will fail without these vars.")
    
    # Warn about missing recommended vars
    unset_recommended = [var for var in RECOMMENDED_VARS if not os.getenv(var)]
    if unset_recommended:
        print(f"INFO: Optional env vars not set: {', '.join(unset_recommended)}")
    
    print("✓ All required env vars present")
    return True


if __name__ == '__main__':
    validate_env()
