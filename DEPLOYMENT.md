# Upstream Production Deployment Guide

**Version:** 1.0  
**Last Updated:** 2026-01-24  
**Target Audience:** DevOps engineers, System administrators

---

## Quick Start

For experienced DevOps teams, here's the 10-minute deployment:

```bash
# 1. Install dependencies
sudo apt install -y python3.12 postgresql-14 redis nginx certbot

# 2. Create database
sudo -u postgres createuser upstream_user --pwprompt
sudo -u postgres createdb upstream_prod --owner=upstream_user

# 3. Clone and configure
git clone https://github.com/your-org/payrixa.git /opt/upstream
cd /opt/upstream
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt gunicorn

# 4. Configure environment (see .env.production template below)
cp .env.example .env.production
nano .env.production

# 5. Run migrations and collect static
python manage.py migrate
python manage.py collectstatic --noinput

# 6. Start with Gunicorn (systemd service recommended - see below)
gunicorn hello_world.wsgi:application --bind unix:/run/payrixa.sock --workers 4
```

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Configuration](#environment-configuration)
3. [Database Setup](#database-setup)
4. [Application Deployment](#application-deployment)
5. [Web Server (Nginx)](#web-server-nginx)
6. [SSL Certificate](#ssl-certificate)
7. [Background Workers (Celery)](#background-workers-celery)
8. [Monitoring](#monitoring)
9. [Backups](#backups)
10. [Verification & Testing](#verification--testing)
11. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Server Requirements

**Minimum:**
- OS: Ubuntu 22.04 LTS
- CPU: 4 cores
- RAM: 8GB
- Storage: 100GB SSD
- Ports: 80, 443, 22

**Recommended for Production:**
- CPU: 8 cores
- RAM: 16GB
- Storage: 250GB SSD

### Install System Dependencies

```bash
sudo apt update
sudo apt install -y \
    python3.12 python3.12-venv python3-pip \
    postgresql-14 postgresql-contrib \
    redis-server \
    nginx \
    git \
    certbot python3-certbot-nginx \
    supervisor
```

---

## Environment Configuration

### Required Environment Variables

Create `/opt/upstream/.env.production`:

```bash
# Django Core
SECRET_KEY=generate-with-python-manage-py-shell-get-random-secret-key
DJANGO_SETTINGS_MODULE=upstream.settings.prod
DEBUG=False
ALLOWED_HOSTS=upstream.cx,www.upstream.cx

# Database
DATABASE_URL=postgresql://upstream_user:SECURE_PASSWORD@localhost:5432/upstream_prod

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True

# Application
PORTAL_BASE_URL=https://upstream.cx

# Email (Mailgun example)
EMAIL_BACKEND=anymail.backends.mailgun.EmailBackend
MAILGUN_API_KEY=your-mailgun-api-key
MAILGUN_DOMAIN=mg.upstream.cx
DEFAULT_FROM_EMAIL=alerts@upstream.cx

# PHI Encryption (REQUIRED)
# Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
FIELD_ENCRYPTION_KEY=your-fernet-key-here
REAL_DATA_MODE=True

# Monitoring (optional)
SENTRY_DSN=https://your-sentry-dsn
```

### Secure the Environment File

```bash
sudo chmod 600 /opt/upstream/.env.production
sudo chown upstream:upstream /opt/upstream/.env.production
```

---

## Database Setup

### Create PostgreSQL Database

```bash
# Create database user
sudo -u postgres createuser upstream_user --no-superuser --no-createdb --no-createrole --pwprompt

# Create database
sudo -u postgres createdb upstream_prod --owner=upstream_user

# Run migrations
cd /opt/upstream
source venv/bin/activate
export $(cat .env.production | xargs)
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

---

## Application Deployment

### Gunicorn Systemd Service

Create `/etc/systemd/system/payrixa.service`:

```ini
[Unit]
Description=Upstream Gunicorn
After=network.target postgresql.service redis.service

[Service]
Type=notify
User=upstream
Group=upstream
WorkingDirectory=/opt/upstream
EnvironmentFile=/opt/upstream/.env.production
ExecStart=/opt/upstream/venv/bin/gunicorn \
    --workers 4 \
    --timeout 120 \
    --bind unix:/run/payrixa.sock \
    hello_world.wsgi:application
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Start the service:

```bash
sudo systemctl enable payrixa.service
sudo systemctl start payrixa.service
sudo systemctl status payrixa.service
```

---

## Web Server (Nginx)

Create `/etc/nginx/sites-available/upstream`:

```nginx
upstream upstream_app {
    server unix:/run/payrixa.sock fail_timeout=0;
}

server {
    listen 80;
    server_name upstream.cx www.upstream.cx;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name upstream.cx www.upstream.cx;

    ssl_certificate /etc/letsencrypt/live/upstream.cx/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/upstream.cx/privkey.pem;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;

    client_max_body_size 50M;

    location /static/ {
        alias /opt/upstream/hello_world/staticfiles/;
        expires 30d;
    }

    location /media/ {
        alias /opt/upstream/hello_world/media/;
    }

    location / {
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_pass http://upstream_app;
    }
}
```

Enable and restart:

```bash
sudo ln -s /etc/nginx/sites-available/upstream /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## SSL Certificate

```bash
sudo certbot --nginx -d upstream.cx -d www.upstream.cx
sudo certbot renew --dry-run  # Test auto-renewal
```

---

## Background Workers (Celery)

### Celery Beat Service

Create `/etc/systemd/system/upstream-beat.service`:

```ini
[Unit]
Description=Upstream Celery Beat
After=network.target redis.service

[Service]
Type=simple
User=upstream
WorkingDirectory=/opt/upstream
EnvironmentFile=/opt/upstream/.env.production
ExecStart=/opt/upstream/venv/bin/celery -A hello_world beat --loglevel=info
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

### Celery Worker Service

Create `/etc/systemd/system/upstream-worker.service`:

```ini
[Unit]
Description=Upstream Celery Worker
After=network.target redis.service

[Service]
Type=simple
User=upstream
WorkingDirectory=/opt/upstream
EnvironmentFile=/opt/upstream/.env.production
ExecStart=/opt/upstream/venv/bin/celery -A hello_world worker --loglevel=info --concurrency=2
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Start services:

```bash
sudo systemctl enable upstream-beat.service upstream-worker.service
sudo systemctl start upstream-beat.service upstream-worker.service
```

---

## Monitoring

### Error Tracking (Sentry)

**Recommended for production to catch and track errors.**

1. Create Sentry account at https://sentry.io
2. Create new project (select "Django" as platform)
3. Copy the DSN from project settings

Add to `.env.production`:

```bash
# Error tracking
SENTRY_DSN=https://your-key@o123456.ingest.sentry.io/789012
ENVIRONMENT=production
SENTRY_RELEASE=v1.0.0  # Optional: track which version is deployed
```

**PHI Protection:** Sentry is configured to automatically scrub PHI before sending error reports. This includes:
- Request bodies (CSV uploads)
- Cookies and session data
- Query parameters
- User email addresses
- Exception messages containing patient-like names

Test PHI filtering:
```bash
cd /opt/upstream
python test_sentry_phi_filtering.py
```

### Performance Monitoring (Prometheus & Grafana)

Install Prometheus and Grafana (optional):

```bash
# See MONITORING.md for detailed setup
```

---

## Backups

Create `/usr/local/bin/upstream-backup.sh`:

```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/var/backups/upstream"
DB_NAME="upstream_prod"
DB_USER="upstream_user"

mkdir -p "$BACKUP_DIR"
pg_dump -U "$DB_USER" -Fc "$DB_NAME" > "$BACKUP_DIR/upstream_$DATE.dump"

# Compress old backups (>7 days)
find "$BACKUP_DIR" -name "*.dump" -mtime +7 -exec gzip {} \;

# Delete old backups (>30 days)
find "$BACKUP_DIR" -name "*.dump.gz" -mtime +30 -delete

echo "Backup completed: upstream_$DATE.dump"
```

Schedule daily backups:

```bash
sudo chmod +x /usr/local/bin/upstream-backup.sh
sudo crontab -e

# Add:
0 2 * * * /usr/local/bin/upstream-backup.sh >> /var/log/upstream_backup.log 2>&1
```

---

## Verification & Testing

### Smoke Tests

```bash
# Health check
curl -I https://upstream.cx/api/v1/health/

# Login page
curl https://upstream.cx/login/ | grep "Upstream"

# Static files
curl -I https://upstream.cx/static/upstream/css/style.css
```

### Service Status

```bash
sudo systemctl status payrixa.service
sudo systemctl status upstream-beat.service
sudo systemctl status upstream-worker.service
sudo systemctl status nginx
sudo systemctl status postgresql
sudo systemctl status redis
```

---

## Troubleshooting

### Gunicorn Won't Start

```bash
# Check logs
sudo journalctl -u payrixa.service -n 100

# Test manually
cd /opt/upstream
source venv/bin/activate
export $(cat .env.production | xargs)
gunicorn hello_world.wsgi:application --bind 0.0.0.0:8000
```

### 502 Bad Gateway

- Check Gunicorn is running: `sudo systemctl status payrixa.service`
- Check socket exists: `ls -la /run/payrixa.sock`
- Check Nginx config: `sudo nginx -t`

### Database Connection Errors

```bash
# Test connection
psql -U upstream_user -d upstream_prod -h localhost

# Check DATABASE_URL in .env.production
cat /opt/upstream/.env.production | grep DATABASE_URL
```

---

## Security Checklist

- [ ] SECRET_KEY is unique and secure
- [ ] DEBUG=False in production
- [ ] ALLOWED_HOSTS configured
- [ ] SSL certificate installed
- [ ] Firewall configured (only 80, 443, 22 open)
- [ ] .env.production has 600 permissions
- [ ] FIELD_ENCRYPTION_KEY set
- [ ] Backups automated and tested
- [ ] Session timeout set (30 minutes)
- [ ] Security headers configured

---

## Maintenance

```bash
# Restart application
sudo systemctl restart payrixa.service

# View logs
sudo journalctl -u payrixa.service -f

# Manual backup
sudo /usr/local/bin/upstream-backup.sh

# Clear cache
cd /opt/upstream
source venv/bin/activate
python manage.py shell -c "from django.core.cache import cache; cache.clear()"
```

---

**For support:** devops@upstream.cx
