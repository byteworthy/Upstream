"""
Production environment validation.

Call from gunicorn prestart hook or docker entrypoint to fail fast
with a clear message when required env vars are missing.
"""
import os
import sys

REQUIRED_VARS = [
    'SECRET_KEY',
    'ALLOWED_HOSTS',
    'MAILGUN_API_KEY',
    'MAILGUN_DOMAIN',
]

# Optional vars with recommended defaults
RECOMMENDED_VARS = [
    'DATABASE_URL',
    'PORTAL_BASE_URL',
    'DEFAULT_FROM_EMAIL',
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
    
    # Warn about missing recommended vars
    unset_recommended = [var for var in RECOMMENDED_VARS if not os.getenv(var)]
    if unset_recommended:
        print(f"WARNING: Recommended env vars not set: {', '.join(unset_recommended)}")
    
    print("✓ All required env vars present")
    return True


if __name__ == '__main__':
    validate_env()
