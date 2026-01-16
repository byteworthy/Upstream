# Payrixa Settings Guide

## Overview

The Payrixa project uses a split settings structure to separate development and production configurations. This ensures security best practices in production while maintaining ease of use in development.

## Settings Structure

```
payrixa/settings/
├── __init__.py     # Package documentation
├── base.py         # Shared settings for all environments
├── dev.py          # Development-specific settings (default)
└── prod.py         # Production-specific settings with security hardening
```

## Using Different Settings

### Development (Default)

By default, the project uses development settings:

```bash
python manage.py runserver
python manage.py test
python manage.py migrate
```

### Production

To use production settings, set the `DJANGO_SETTINGS_MODULE` environment variable:

```bash
export DJANGO_SETTINGS_MODULE=payrixa.settings.prod
python manage.py check
python manage.py migrate
gunicorn hello_world.wsgi:application
```

Or set it inline for a single command:

```bash
DJANGO_SETTINGS_MODULE=payrixa.settings.prod python manage.py check
```

## Development Settings (dev.py)

Development settings include:

- **DEBUG = True** - Enables detailed error pages
- **SQLite database** - Simple file-based database for local development
- **Console email backend** - Emails printed to console instead of sent
- **Relaxed security settings** - HTTPS not required, insecure defaults allowed
- **Default SECRET_KEY** - Auto-generated insecure key for convenience

## Production Settings (prod.py)

Production settings enforce:

### Security

- **DEBUG = False** (always)
- **SECRET_KEY** - Must be set via environment variable (no default)
- **ALLOWED_HOSTS** - Must be set via environment variable (no wildcard default)
- **SESSION_COOKIE_SECURE = True** (always)
- **CSRF_COOKIE_SECURE = True** (always)
- **SECURE_SSL_REDIRECT = True** (configurable, default True)
- **HSTS settings** - Configurable via environment variables

### Database

- **PostgreSQL** - Production-ready database
- Supports `DATABASE_URL` format or individual connection parameters
- **SSL mode = require** for PHI compliance

### Email

- **Anymail with Mailgun** - Production email provider
- Requires `MAILGUN_API_KEY` and `MAILGUN_DOMAIN` environment variables
- SMTP fallback settings available

## Required Environment Variables

### Development (.env file)

```bash
# Optional - uses defaults if not set
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

### Production

```bash
# Required
SECRET_KEY=your-production-secret-key-here
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
MAILGUN_API_KEY=your-mailgun-api-key
MAILGUN_DOMAIN=mg.yourdomain.com

# Database - Option 1: DATABASE_URL
DATABASE_URL=postgres://user:password@host:port/database

# Database - Option 2: Individual parameters
DB_NAME=payrixa
DB_USER=payrixa
DB_PASSWORD=your-secure-password
DB_HOST=your-db-host.rds.amazonaws.com
DB_PORT=5432

# Optional security settings
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True

# Email settings (optional, for SMTP fallback)
EMAIL_HOST=smtp.mailgun.org
EMAIL_PORT=587
EMAIL_HOST_USER=postmaster@mg.yourdomain.com
EMAIL_HOST_PASSWORD=your-smtp-password
EMAIL_USE_TLS=True

DEFAULT_FROM_EMAIL=alerts@yourdomain.com
```

## Email Configuration

### Development

Emails are printed to the console by default. To test with a different backend:

```bash
EMAIL_BACKEND=django.core.mail.backends.filebased.EmailBackend
EMAIL_FILE_PATH=/tmp/app-emails
```

### Production

Configure Mailgun via Anymail:

1. Sign up for Mailgun: https://www.mailgun.com/
2. Get your API key and domain
3. Set environment variables:
   ```bash
   MAILGUN_API_KEY=your-api-key
   MAILGUN_DOMAIN=mg.yourdomain.com
   ```

Other supported providers (change `EMAIL_BACKEND`):
- `anymail.backends.sendgrid.EmailBackend` (SendGrid)
- `anymail.backends.amazon_ses.EmailBackend` (AWS SES)
- `anymail.backends.postmark.EmailBackend` (Postmark)

## Testing

### Run All Tests

```bash
python manage.py test
```

### Run Email Tests Only

```bash
python manage.py test payrixa.tests_email
```

### Test Production Settings

```bash
# This will fail without required env vars (expected)
DJANGO_SETTINGS_MODULE=payrixa.settings.prod python manage.py check

# Test with required vars
MAILGUN_API_KEY=test \
MAILGUN_DOMAIN=test.example.com \
SECRET_KEY=test-secret \
ALLOWED_HOSTS=example.com \
DJANGO_SETTINGS_MODULE=payrixa.settings.prod \
python manage.py check
```

## Deployment Checklist

Before deploying to production:

1. ✅ Set all required environment variables
2. ✅ Generate a secure SECRET_KEY (use `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`)
3. ✅ Configure PostgreSQL database
4. ✅ Set up Mailgun or another email provider
5. ✅ Configure ALLOWED_HOSTS with your domain(s)
6. ✅ Run migrations: `python manage.py migrate`
7. ✅ Collect static files: `python manage.py collectstatic`
8. ✅ Run system check: `python manage.py check --deploy`
9. ✅ Set `DJANGO_SETTINGS_MODULE=payrixa.settings.prod` in your deployment environment

## Troubleshooting

### "UndefinedValueError: SECRET_KEY not found"

This is expected in production. Set the SECRET_KEY environment variable.

### "UndefinedValueError: ALLOWED_HOSTS not found"

This is expected in production. Set the ALLOWED_HOSTS environment variable.

### "UndefinedValueError: MAILGUN_API_KEY not found"

This is expected in production. Set the MAILGUN_API_KEY and MAILGUN_DOMAIN environment variables.

### Emails not sending in development

This is normal - emails are printed to the console by default. Check the terminal output where you ran `runserver`.

### Database connection error in production

Ensure your PostgreSQL database is running and environment variables are set correctly. Check:
- DB_HOST is accessible
- DB_USER has correct permissions
- DB_PASSWORD is correct
- Database name exists

## Migration from Old Settings

If upgrading from the old `hello_world/settings.py` file:

1. The new settings split is already configured in `manage.py`, `wsgi.py`, and `asgi.py`
2. Development behavior is identical - no changes needed
3. The old `hello_world/settings.py` file can be kept as a backup or removed
4. Update any deployment scripts to use `DJANGO_SETTINGS_MODULE=payrixa.settings.prod`

## Security Notes

- **Never commit .env files** to version control
- **Rotate SECRET_KEY** regularly in production
- **Use different SECRET_KEY** for each environment
- **Enable HSTS** for production domains
- **Review ALLOWED_HOSTS** carefully - never use wildcard in production
- **Use strong database passwords** and rotate them periodically
- **Enable database SSL** (already configured in prod.py)
