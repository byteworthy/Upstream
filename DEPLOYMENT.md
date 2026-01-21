# Payrixa Deployment Guide

MVP1 deployment path covering one production-like workflow.

## Prerequisites

- Python 3.12+
- PostgreSQL 13+
- Docker & Docker Compose (for local Postgres)
- Mailgun account for email delivery

## Required Environment Variables

```bash
# Security (required)
SECRET_KEY=your-production-secret-key  # Generate with: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
CSRF_TRUSTED_ORIGINS=https://yourdomain.com

# Database (required for production)
DATABASE_URL=postgresql://user:pass@host:5432/payrixa

# Email (required)
MAILGUN_API_KEY=key-xxxxx
MAILGUN_DOMAIN=mg.yourdomain.com

# Optional but recommended
DEFAULT_FROM_EMAIL=alerts@yourdomain.com
PORTAL_BASE_URL=https://yourdomain.com
```

## Gate B: Postgres Workflow Verification

Run this sequence to prove the full value chain on Postgres:

### 1. Start Postgres

```bash
docker-compose up -d db
```

### 2. Set Environment

```bash
export DATABASE_URL="postgresql://payrixa:payrixa@localhost:5432/payrixa"
export DJANGO_SETTINGS_MODULE=payrixa.settings.prod
export SECRET_KEY="dev-secret-key-change-in-prod"
export ALLOWED_HOSTS="localhost,127.0.0.1"
export MAILGUN_API_KEY="test"
export MAILGUN_DOMAIN="test"
export SECURE_SSL_REDIRECT=False
```

### 3. Migrate Database

```bash
python manage.py migrate
```

### 4. Load Demo Data and Run Pipelines

```bash
# Load fixtures
python manage.py loaddata payrixa/fixtures/demo_data.json

# Generate DenialScope test data
python manage.py generate_denialscope_test_data --customer 1

# Compute DenialScope signals
python manage.py compute_denialscope --customer 1

# Generate DriftWatch demo events
python manage.py generate_driftwatch_demo --customer 1
```

### 5. Verify Dashboards

```bash
python manage.py runserver --insecure
```

Open in browser:
- http://127.0.0.1:8000/portal/products/denialscope/
- http://127.0.0.1:8000/portal/products/driftwatch/

Verify both render with non-empty data tables.

## Gate A: Production Static Files

### Install WhiteNoise

WhiteNoise is already in requirements.txt and configured in prod settings.

```bash
pip install -r requirements.txt
python manage.py collectstatic --noinput
```

Verify static files load:
```bash
DJANGO_SETTINGS_MODULE=payrixa.settings.prod python manage.py runserver --insecure
# Open http://127.0.0.1:8000/ and verify CSS loads
```

## Gate C: Product Enablement Verification

```bash
python manage.py test payrixa.tests_product_enablement -v2
```

Expected: All tests pass, including:
- `test_driftwatch_accessible_when_enabled`
- `test_driftwatch_forbidden_when_disabled`
- `test_denialscope_forbidden_when_disabled`

## Gate D: Alert Pipeline Verification

```bash
python manage.py test payrixa.tests_delivery.AlertDeliveryTests.test_suppression_window_prevents_duplicate_sends -v2
```

Expected: Test passes, proving suppression works.

## Production Deployment Steps

### 1. Validate Environment

```bash
python -m payrixa.check_env
```

### 2. Run Migrations

```bash
python manage.py migrate
```

### 3. Collect Static Files

```bash
python manage.py collectstatic --noinput
```

### 4. Start Gunicorn

```bash
gunicorn hello_world.wsgi:application --bind 0.0.0.0:8000 --workers 2
```

### 5. Verify Health

```bash
curl http://localhost:8000/api/v1/health/
# Expected: {"status": "healthy", ...}
```

## Rollback Procedure

1. Revert to previous migration:
   ```bash
   python manage.py migrate payrixa <previous_migration_number>
   ```

2. Deploy previous code version

3. Restart gunicorn

## Docker Deployment

```bash
# Build
docker build --target production -t payrixa:latest .

# Run with env file
docker run --env-file .env.prod -p 8000:8000 payrixa:latest
```

## Troubleshooting

### Static files 404
- Verify `collectstatic` ran successfully
- Check `STATIC_ROOT` permissions
- Ensure WhiteNoise middleware is in position after SecurityMiddleware

### Database connection errors
- Verify `DATABASE_URL` format
- Check PostgreSQL is running: `docker-compose ps`
- Test connection: `python manage.py dbshell`

### Email not sending
- Verify Mailgun credentials
- Check domain is verified in Mailgun dashboard
- Test with console backend first: `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend`
