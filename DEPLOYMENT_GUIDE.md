# Upstream Deployment Guide
**Comprehensive deployment guide for all environments**

---

## Quick Start (2-4 hours)

This section provides a fast-track deployment for experienced DevOps teams.


---

## 🚀 Overview

This guide helps you safely deploy Upstream to production with all security settings properly configured.

**Estimated Time:** 2-4 hours (first deployment)

---

## 📋 Prerequisites

- [ ] Linux server (Ubuntu 22.04+ recommended)
- [ ] PostgreSQL 14+ database
- [ ] Redis 7+ server
- [ ] Domain name with DNS configured
- [ ] SSL/TLS certificate (Let's Encrypt or commercial)
- [ ] Email service account (Mailgun, SendGrid, etc.)
- [ ] (Optional) Sentry account for error tracking

---

## 🔐 Step 1: Environment Configuration

### 1.1 Copy Production Template

```bash
cp .env.production.example .env.production
chmod 600 .env.production  # Restrict to owner only
```

### 1.2 Generate Strong SECRET_KEY

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copy the output to `SECRET_KEY` in `.env.production`

### 1.3 Generate Field Encryption Key (if handling real PHI)

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Copy the output to `FIELD_ENCRYPTION_KEY` in `.env.production`

### 1.4 Fill in Required Settings

Edit `.env.production` and set ALL required values:

**Critical Settings:**
- `SECRET_KEY` - Generated above
- `DEBUG=False` - MUST be False
- `ALLOWED_HOSTS` - Your domain(s), comma-separated
- `DATABASE_URL` - PostgreSQL connection string with SSL
- `REDIS_URL` - Redis connection string
- `EMAIL_BACKEND` - Real email service (not console)
- `DEFAULT_FROM_EMAIL` - Your sender email
- `PORTAL_BASE_URL` - Your HTTPS domain

**Security Settings:**
- `SECURE_SSL_REDIRECT=True`
- `SESSION_COOKIE_SECURE=True`
- `CSRF_COOKIE_SECURE=True`
- `SECURE_HSTS_SECONDS=31536000`

---

## ✅ Step 2: Validate Configuration

### 2.1 Run Production Validator

```bash
# Load production environment
export DJANGO_SETTINGS_MODULE=upstream.settings.prod
export $(cat .env.production | xargs)

# Run validation
python scripts/validate_production_settings.py
```

**Expected Output:**
```
✓ READY FOR PRODUCTION DEPLOYMENT
All security checks passed!
```

### 2.2 Fix Any Issues

If the validator reports errors:

**Critical Failures (Exit Code 1):**
- MUST fix before deployment
- Usually: DEBUG=True, weak SECRET_KEY, missing ALLOWED_HOSTS

**Errors (Exit Code 1):**
- Should fix before deployment
- Usually: missing HTTPS settings, email configuration

**Warnings (Exit Code 2):**
- Can proceed with caution
- Usually: optional features not configured

### 2.3 Run Django Deployment Check

```bash
python manage.py check --deploy
```

Address any warnings that appear.

---

## 🗄️ Step 3: Database Setup

### 3.1 Create PostgreSQL Database

```sql
-- On your PostgreSQL server:
CREATE DATABASE upstream;
CREATE USER upstream_user WITH PASSWORD 'secure-password-here';
GRANT ALL PRIVILEGES ON DATABASE upstream TO upstream_user;

-- Enable required extensions
\c upstream
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- For text search
```

### 3.2 Configure DATABASE_URL

In `.env.production`:
```bash
DATABASE_URL=postgres://upstream_user:secure-password-here@db.example.com:5432/upstream?sslmode=require
```

### 3.3 Run Migrations

```bash
python manage.py migrate
```

**Expected:** All migrations run successfully

### 3.4 Verify Migrations

```bash
python manage.py showmigrations
```

**Expected:** All migrations marked [X]

---

## 👤 Step 4: Create Admin User

```bash
python manage.py createsuperuser
```

Follow prompts:
- **Username:** admin
- **Email:** admin@yourdomain.com
- **Password:** (use a strong password)

---

## 📦 Step 5: Static Files

### 5.1 Create Static Directory

```bash
sudo mkdir -p /var/www/upstream/static
sudo mkdir -p /var/www/upstream/media
sudo chown -R $USER:$USER /var/www/upstream
```

### 5.2 Collect Static Files

```bash
python manage.py collectstatic --noinput
```

**Expected:** All static files copied to `/var/www/upstream/static/`

---

## 🚦 Step 6: Application Server (Gunicorn)

### 6.1 Install Gunicorn

```bash
pip install gunicorn
```

### 6.2 Test Gunicorn

```bash
gunicorn hello_world.wsgi:application --bind 0.0.0.0:8000
```

Visit: http://your-server-ip:8000

**Expected:** Application loads (without static files yet)

### 6.3 Create Systemd Service

Create `/etc/systemd/system/upstream.service`:

```ini
[Unit]
Description=Upstream Gunicorn Application
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/path/to/upstream
EnvironmentFile=/path/to/upstream/.env.production
ExecStart=/path/to/venv/bin/gunicorn \
  --workers 4 \
  --bind unix:/run/upstream.sock \
  hello_world.wsgi:application

[Install]
WantedBy=multi-user.target
```

### 6.4 Start Service

```bash
sudo systemctl daemon-reload
sudo systemctl start upstream
sudo systemctl enable upstream
sudo systemctl status upstream
```

**Expected:** Service running (active)

---

## 🌐 Step 7: Web Server (Nginx)

### 7.1 Install Nginx

```bash
sudo apt update
sudo apt install nginx
```

### 7.2 Configure Nginx

Create `/etc/nginx/sites-available/upstream`:

```nginx
upstream upstream_app {
    server unix:/run/upstream.sock fail_timeout=0;
}

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Static files
    location /static/ {
        alias /var/www/upstream/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /var/www/upstream/media/;
        expires 7d;
        add_header Cache-Control "public";
    }

    # Application
    location / {
        proxy_pass http://upstream_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Health check endpoint
    location /health/ {
        access_log off;
        proxy_pass http://upstream_app;
    }
}
```

### 7.3 Enable Site

```bash
sudo ln -s /etc/nginx/sites-available/upstream /etc/nginx/sites-enabled/
sudo nginx -t  # Test configuration
sudo systemctl restart nginx
```

---

## 🔥 Step 8: Background Tasks (Celery)

### 8.1 Create Celery Service

Create `/etc/systemd/system/celery.service`:

```ini
[Unit]
Description=Upstream Celery Worker
After=network.target

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory=/path/to/upstream
EnvironmentFile=/path/to/upstream/.env.production
ExecStart=/path/to/venv/bin/celery -A hello_world worker \
  --loglevel=info \
  --logfile=/var/log/celery/worker.log

[Install]
WantedBy=multi-user.target
```

### 8.2 Create Celery Beat Service (for scheduled tasks)

Create `/etc/systemd/system/celerybeat.service`:

```ini
[Unit]
Description=Upstream Celery Beat
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/path/to/upstream
EnvironmentFile=/path/to/upstream/.env.production
ExecStart=/path/to/venv/bin/celery -A hello_world beat \
  --loglevel=info \
  --logfile=/var/log/celery/beat.log

[Install]
WantedBy=multi-user.target
```

### 8.3 Start Services

```bash
sudo mkdir -p /var/log/celery
sudo chown www-data:www-data /var/log/celery

sudo systemctl daemon-reload
sudo systemctl start celery
sudo systemctl start celerybeat
sudo systemctl enable celery
sudo systemctl enable celerybeat
```

---

## ✅ Step 9: Final Verification

### 9.1 Health Check

```bash
curl https://yourdomain.com/health/
```

**Expected:** `{"status": "ok"}`

### 9.2 Admin Panel

Visit: https://yourdomain.com/admin/

**Expected:** Login page with HTTPS

### 9.3 Test User Registration

1. Visit portal
2. Register new user
3. Check email delivery
4. Verify email links use HTTPS

### 9.4 Check Logs

```bash
# Application logs
sudo journalctl -u upstream -f

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# Celery logs
sudo tail -f /var/log/celery/worker.log
```

---

## 📊 Step 10: Monitoring Setup

### 10.1 Sentry Error Tracking

If configured in `.env.production`:

1. Visit your Sentry dashboard
2. Trigger a test error:
   ```python
   # In Django shell
   raise Exception("Test Sentry integration")
   ```
3. Verify error appears in Sentry

### 10.2 Uptime Monitoring

Set up external uptime monitoring:
- [Pingdom](https://www.pingdom.com/)
- [UptimeRobot](https://uptimerobot.com/)
- [StatusCake](https://www.statuscake.com/)

Monitor:
- `https://yourdomain.com/health/` (every 5 minutes)

### 10.3 Log Aggregation

Consider setting up:
- Papertrail, Loggly, or Datadog for log aggregation
- Prometheus + Grafana for metrics

---

## 🔄 Step 11: Backup Strategy

### 11.1 Database Backups

Create `/usr/local/bin/backup-upstream.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/backups/upstream"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_NAME="upstream"

mkdir -p $BACKUP_DIR

# Backup database
pg_dump -h db.example.com -U upstream_user $DB_NAME | \
  gzip > $BACKUP_DIR/db_$TIMESTAMP.sql.gz

# Backup media files
tar -czf $BACKUP_DIR/media_$TIMESTAMP.tar.gz /var/www/upstream/media/

# Keep only last 30 days
find $BACKUP_DIR -type f -mtime +30 -delete

echo "Backup completed: $TIMESTAMP"
```

### 11.2 Schedule Backups

```bash
sudo chmod +x /usr/local/bin/backup-upstream.sh

# Add to crontab
sudo crontab -e

# Daily backups at 2 AM
0 2 * * * /usr/local/bin/backup-upstream.sh
```

### 11.3 Test Restore

```bash
# Test database restore
gunzip -c /backups/upstream/db_TIMESTAMP.sql.gz | \
  psql -h localhost -U upstream_user upstream_test
```

---

## 🚨 Troubleshooting

### Issue: "DisallowedHost" Error

**Solution:** Add domain to ALLOWED_HOSTS in `.env.production`

### Issue: Static Files Not Loading

**Solutions:**
1. Run `python manage.py collectstatic --noinput`
2. Check Nginx static file paths
3. Verify file permissions

### Issue: 502 Bad Gateway

**Solutions:**
1. Check if Gunicorn is running: `sudo systemctl status upstream`
2. Check socket file exists: `ls -l /run/upstream.sock`
3. Check logs: `sudo journalctl -u upstream -n 50`

### Issue: Database Connection Failed

**Solutions:**
1. Verify DATABASE_URL in `.env.production`
2. Check PostgreSQL is running
3. Test connection: `psql $DATABASE_URL`
4. Check firewall rules

### Issue: Email Not Sending

**Solutions:**
1. Verify EMAIL_BACKEND is not console backend
2. Check email service credentials
3. Test manually: `python manage.py sendtestemail you@example.com`

---

## 📚 Post-Deployment Checklist

After successful deployment:

- [ ] Document server credentials in secure location
- [ ] Set up monitoring alerts
- [ ] Schedule regular backups
- [ ] Configure log rotation
- [ ] Set up SSL certificate auto-renewal
- [ ] Create runbook for common operations
- [ ] Train team on deployment process
- [ ] Set up staging environment
- [ ] Document rollback procedure
- [ ] Schedule regular security audits

---

## 🔒 Security Best Practices

1. **Credentials:**
   - Use unique passwords for each service
   - Store credentials in secure vault (1Password, Vault, AWS Secrets Manager)
   - Rotate credentials regularly

2. **Access Control:**
   - Use SSH keys (disable password auth)
   - Limit sudo access
   - Enable firewall (ufw/iptables)
   - Use VPN for database access

3. **Updates:**
   - Enable automatic security updates
   - Monitor CVE announcements
   - Test updates in staging first

4. **Monitoring:**
   - Set up intrusion detection
   - Monitor failed login attempts
   - Track unusual traffic patterns
   - Review logs regularly

---

## 📞 Support

- **Documentation:** [upstream/docs](./docs/)
- **Issues:** [GitHub Issues](https://github.com/yourorg/upstream/issues)
- **Security:** security@yourdomain.com
- **Emergency Runbook:** [DEPLOYMENT_RUNBOOK.md](./DEPLOYMENT_RUNBOOK.md)

---

**Next Steps:** [DEPLOYMENT_RUNBOOK.md](./DEPLOYMENT_RUNBOOK.md) - Day-to-day operations guide

---

## Pre-Deployment Checklist

Complete this checklist before deploying to production.


---

## Pre-Deployment Checklist

### Code & Repository
- [x] All Phase 2 fixes merged to main branch
- [x] All tests passing (100% success rate)
- [x] Git tags created for release version
- [ ] Production branch created from main
- [ ] Rollback commits identified and documented

### Environment Setup
- [ ] Production server provisioned (recommended: 4 CPU, 8GB RAM minimum)
- [ ] PostgreSQL 14+ installed and configured
- [ ] Redis 7+ installed and configured
- [ ] Python 3.11+ installed
- [ ] Nginx installed
- [ ] SSL/TLS certificates obtained (Let's Encrypt or commercial)
- [ ] Domain DNS configured

### Configuration Files
- [ ] `.env.production` created from template
- [ ] `SECRET_KEY` generated (use: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`)
- [ ] `DATABASE_URL` configured
- [ ] `REDIS_URL` configured
- [ ] `ALLOWED_HOSTS` set to production domain(s)
- [ ] `SENTRY_DSN` configured for error tracking
- [ ] Email settings configured for password resets
- [ ] All secrets stored securely (vault or AWS Secrets Manager)

### Database
- [ ] PostgreSQL database created
- [ ] Database user created with appropriate permissions
- [ ] Database connection tested from application server
- [ ] Backup system configured (daily automated backups)
- [ ] Backup restore procedure tested

### Application Installation
- [ ] Application code deployed to production server
- [ ] Virtual environment created
- [ ] Dependencies installed: `pip install -r requirements.txt`
- [ ] Environment variables loaded
- [ ] Static files directory created: `/var/www/upstream/static/`
- [ ] Media files directory created: `/var/www/upstream/media/`

---

## Deployment Steps

### Step 1: Database Migration
```bash
# Set Django settings
export DJANGO_SETTINGS_MODULE=upstream.settings.production

# Run migrations
python manage.py migrate

# Verify migrations
python manage.py showmigrations
```
**Expected:** All migrations marked with [X]

**Verification:** Check for these migrations:
- [X] 0012_add_database_indexes
- [X] 0013_data_quality_report

---

### Step 2: Static Files
```bash
# Collect static files
python manage.py collectstatic --noinput

# Verify static files
ls -la /var/www/upstream/static/
```
**Expected:** CSS, JS, and image files present

---

### Step 3: Create Superuser
```bash
# Create admin user
python manage.py createsuperuser

# Follow prompts:
# Username: admin
# Email: admin@yourdomain.com
# Password: [secure password]
```
**Expected:** Superuser created successfully

---

### Step 4: Test Database Connection
```bash
# Django shell test
python manage.py shell

# Run these commands:
from django.db import connection
connection.ensure_connection()
print("Database connected:", connection.is_usable())
exit()
```
**Expected:** "Database connected: True"

---

### Step 5: Configure Gunicorn
```bash
# Create Gunicorn service file
sudo nano /etc/systemd/system/gunicorn.service
```

```ini
[Unit]
Description=Gunicorn daemon for Upstream
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/upstream
Environment="DJANGO_SETTINGS_MODULE=upstream.settings.production"
EnvironmentFile=/var/www/upstream/.env.production
ExecStart=/var/www/upstream/venv/bin/gunicorn \
    --workers 4 \
    --bind unix:/run/gunicorn.sock \
    --timeout 60 \
    --access-logfile /var/log/upstream/access.log \
    --error-logfile /var/log/upstream/error.log \
    upstream.wsgi:application

[Install]
WantedBy=multi-user.target
```

```bash
# Create log directory
sudo mkdir -p /var/log/upstream
sudo chown www-data:www-data /var/log/upstream

# Enable and start Gunicorn
sudo systemctl enable gunicorn
sudo systemctl start gunicorn
sudo systemctl status gunicorn
```
**Expected:** Active (running)

---

### Step 6: Configure Nginx
```bash
# Create Nginx site config
sudo nano /etc/nginx/sites-available/upstream
```

```nginx
upstream upstream {
    server unix:/run/gunicorn.sock fail_timeout=0;
}

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    client_max_body_size 50M;

    location /static/ {
        alias /var/www/upstream/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /var/www/upstream/media/;
        expires 7d;
    }

    location / {
        proxy_pass http://upstream;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/upstream /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```
**Expected:** Configuration test successful

---

### Step 7: SSL Certificate (Let's Encrypt)
```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Test auto-renewal
sudo certbot renew --dry-run
```
**Expected:** Certificate obtained and installed

---

## Post-Deployment Verification

### Health Checks
```bash
# 1. Health endpoint
curl https://yourdomain.com/health/
# Expected: {"status": "healthy", "timestamp": 1737706800.0}

# 2. Admin login
# Visit: https://yourdomain.com/portal/login/
# Expected: Login page loads

# 3. Metrics dashboard (staff only)
# Visit: https://yourdomain.com/portal/admin/metrics/
# Expected: Dashboard loads with metrics

# 4. Prometheus metrics
curl https://yourdomain.com/metrics
# Expected: Prometheus metrics output
```

### Functional Tests
- [ ] Can log in with superuser credentials
- [ ] Can access Axis Hub dashboard
- [ ] Can create a test customer
- [ ] Can upload a sample CSV file
- [ ] Can view uploaded claims
- [ ] Can see drift events
- [ ] Can view alerts
- [ ] Metrics dashboard shows recent requests
- [ ] Session timeout works (wait 30 minutes)

### Performance Tests
```bash
# 1. Response time test
curl -w "@curl-format.txt" -o /dev/null -s https://yourdomain.com/portal/axis/

# curl-format.txt:
# time_total: %{time_total}s
# Expected: <1s for dashboard load

# 2. Check request timing header
curl -I https://yourdomain.com/portal/axis/
# Expected: X-Request-Duration-Ms: <500ms

# 3. Cache test (upload CSV twice, second should be faster)
# Expected: ~5s first upload, ~2s second upload
```

### Security Tests
- [ ] HTTP redirects to HTTPS
- [ ] Session cookie has HTTPOnly flag
- [ ] Session expires after 30 minutes idle
- [ ] PHI detection blocks "John Smith" in payer names
- [ ] Non-staff users cannot access /portal/admin/metrics/
- [ ] CSRF protection enabled (test form without token)

### Monitoring Setup
- [ ] Sentry receiving error events (test by triggering 500 error)
- [ ] Prometheus scraping metrics endpoint
- [ ] Grafana dashboards configured (if using)
- [ ] Alert rules configured (if using AlertManager)

---

## Rollback Procedure

### If Critical Issues Detected:

**Option 1: Quick Rollback (Gunicorn)**
```bash
# Stop current version
sudo systemctl stop gunicorn

# Revert code to previous version
cd /var/www/upstream
git checkout [previous-release-tag]

# Restart Gunicorn
sudo systemctl start gunicorn
```
**Downtime:** ~30 seconds

**Option 2: Database Rollback**
```bash
# If migrations need rollback
python manage.py migrate [app_name] [previous_migration_number]

# Example:
python manage.py migrate upstream 0011
```
**Warning:** Only rollback if new migration breaks functionality

**Option 3: Full Restore from Backup**
```bash
# Stop application
sudo systemctl stop gunicorn

# Restore database
pg_restore -d upstream /backups/upstream_backup_[timestamp].dump

# Revert code
cd /var/www/upstream
git checkout [previous-release-tag]

# Start application
sudo systemctl start gunicorn
```
**Downtime:** 5-10 minutes depending on database size

---

## Backup Verification

### Database Backup Test
```bash
# Create test backup
pg_dump upstream > /tmp/test_backup.sql

# Verify backup size
ls -lh /tmp/test_backup.sql
# Expected: >1MB (depends on data)

# Test restore (to test database)
createdb upstream_test
psql upstream_test < /tmp/test_backup.sql
# Expected: No errors

# Cleanup
dropdb upstream_test
rm /tmp/test_backup.sql
```

### Schedule Automated Backups
```bash
# Add to crontab
crontab -e
```

```cron
# Daily backup at 2 AM
0 2 * * * /usr/local/bin/backup-upstream.sh

# backup-upstream.sh:
#!/bin/bash
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
pg_dump upstream | gzip > /backups/upstream_$TIMESTAMP.sql.gz
# Keep last 30 days
find /backups -name "upstream_*.sql.gz" -mtime +30 -delete
```

---

## Monitoring Dashboard Access

### Staff User Setup
```bash
# Create staff user for operators
python manage.py shell

from django.contrib.auth.models import User
user = User.objects.create_user('operator1', 'operator1@yourdomain.com', 'secure_password')
user.is_staff = True
user.save()
exit()
```

### Dashboard URLs
- **Metrics Dashboard:** https://yourdomain.com/portal/admin/metrics/
- **Prometheus Metrics:** https://yourdomain.com/metrics
- **Health Check:** https://yourdomain.com/health/

### Key Metrics to Monitor
- Average Response Time: <500ms (warn if >1s)
- Active Users: Track during business hours
- Error Rate: <1% (alert if >5%)
- Cache Hit Rate: >80% (investigate if <70%)
- Slow Requests: <5 per hour (investigate if >20)

---

## Production Readiness Sign-Off

### Development Team
- [x] All Phase 2 fixes implemented
- [x] Test suites passing (100%)
- [x] Documentation complete
- [x] Code reviewed and approved

### Operations Team
- [ ] Infrastructure provisioned
- [ ] Deployment tested in staging
- [ ] Backup procedures validated
- [ ] Monitoring configured
- [ ] Rollback procedures tested

### Security Team
- [ ] Security audit completed
- [ ] Penetration testing passed
- [ ] HIPAA compliance verified
- [ ] SSL/TLS configured
- [ ] Secret management validated

### Business Team
- [ ] User acceptance testing completed
- [ ] Training materials reviewed
- [ ] Support procedures documented
- [ ] Go-live date confirmed

---

## Emergency Contacts

### During Deployment
- **Lead Developer:** [contact info]
- **DevOps Engineer:** [contact info]
- **Database Administrator:** [contact info]

### Post-Deployment
- **On-Call Engineer:** [contact info]
- **Sentry Alerts:** [webhook/email]
- **Monitoring Alerts:** [PagerDuty/Slack]

---

## Success Criteria

### Deployment Successful When:
- [x] All health checks passing
- [x] Application accessible via HTTPS
- [x] Admin can log in
- [x] Test CSV upload completes successfully
- [x] Metrics dashboard shows data
- [x] No errors in Sentry
- [x] Response times <500ms
- [x] Session timeout working (30 min)

### Ready for User Traffic When:
- [ ] All success criteria met
- [ ] Smoke tests passed
- [ ] Monitoring validated
- [ ] Operations team trained
- [ ] Support procedures ready

---

## Notes

### Database Size Estimates
- Empty database: ~50MB
- Per customer (1 year data): ~100MB
- 100 customers: ~10GB
- Recommended disk: 50GB minimum

### Expected Load (per customer)
- Daily uploads: 1-5
- Daily active users: 2-10
- Monthly claims: 1,000-50,000
- Concurrent users: <50

### Performance Targets
- Dashboard load: <1s
- CSV upload (1,000 rows): <5s
- Report generation: <10s
- API response: <200ms

---

**Document Version:** 1.0.0
**Last Updated:** 2026-01-24
**Next Review:** Post-deployment (1 week after go-live)

---

## Detailed Setup Instructions

Step-by-step deployment procedures for all environments.


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
git clone https://github.com/your-org/upstream.git /opt/upstream
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
gunicorn hello_world.wsgi:application --bind unix:/run/upstream.sock --workers 4
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

Create `/etc/systemd/system/upstream.service`:

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
    --bind unix:/run/upstream.sock \
    hello_world.wsgi:application
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Start the service:

```bash
sudo systemctl enable upstream.service
sudo systemctl start upstream.service
sudo systemctl status upstream.service
```

---

## Web Server (Nginx)

Create `/etc/nginx/sites-available/upstream`:

```nginx
upstream upstream_app {
    server unix:/run/upstream.sock fail_timeout=0;
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
sudo systemctl status upstream.service
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
sudo journalctl -u upstream.service -n 100

# Test manually
cd /opt/upstream
source venv/bin/activate
export $(cat .env.production | xargs)
gunicorn hello_world.wsgi:application --bind 0.0.0.0:8000
```

### 502 Bad Gateway

- Check Gunicorn is running: `sudo systemctl status upstream.service`
- Check socket exists: `ls -la /run/upstream.sock`
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
sudo systemctl restart upstream.service

# View logs
sudo journalctl -u upstream.service -f

# Manual backup
sudo /usr/local/bin/upstream-backup.sh

# Clear cache
cd /opt/upstream
source venv/bin/activate
python manage.py shell -c "from django.core.cache import cache; cache.clear()"
```

---

**For support:** devops@upstream.cx

---

## GCP Quick Start (20 minutes)

Fast deployment to Google Cloud Platform.

**⚡ Get Upstream running on Google Cloud in 20 minutes**

## Prerequisites (5 minutes)

```bash
# 1. Install Google Cloud SDK
brew install google-cloud-sdk    # macOS
# OR download: https://cloud.google.com/sdk/docs/install

# 2. Login to GCP
gcloud auth login

# 3. Set your project ID
export GCP_PROJECT_ID="your-project-id"
gcloud config set project $GCP_PROJECT_ID
```

---

## Deploy to GCP (15 minutes)

### Step 1: Setup Infrastructure (One-Time, ~10 minutes)

```bash
./deploy_gcp.sh setup
```

**This creates:**
- ✅ Cloud SQL PostgreSQL database
- ✅ Memorystore Redis cache
- ✅ Cloud Storage bucket
- ✅ Secret Manager secrets

**⚠️ SAVE THE DATABASE PASSWORD shown during setup!**

---

### Step 2: Deploy Application (~5 minutes)

```bash
./deploy_gcp.sh deploy
```

**This does:**
- ✅ Builds Docker image
- ✅ Runs database migrations
- ✅ Deploys to Cloud Run
- ✅ Configures environment

---

### Step 3: Verify Deployment (1 minute)

```bash
# Check status
./deploy_gcp.sh status

# Get service URL
SERVICE_URL=$(gcloud run services describe upstream-staging \
    --region=us-central1 \
    --format="get(status.url)")

echo "Service URL: $SERVICE_URL"

# Test health endpoint
curl $SERVICE_URL/health/

# Run smoke tests
python smoke_tests.py --url $SERVICE_URL --critical-only
```

---

## Common Commands

```bash
# View logs
./deploy_gcp.sh logs

# Rollback deployment
./deploy_gcp.sh rollback

# Update application (after code changes)
git push origin main
./deploy_gcp.sh deploy

# SSH into database
gcloud sql connect upstream-db --user=upstream
```

---

## Costs

**Staging Environment:** ~$75/month
- Cloud Run: ~$30
- Cloud SQL: ~$15
- Redis: ~$30

**Production Environment:** ~$500/month

---

## Troubleshooting

### Deployment fails?
```bash
gcloud builds list
gcloud builds log <BUILD_ID>
```

### Can't connect to database?
```bash
gcloud sql instances describe upstream-db
gcloud sql connect upstream-db --user=upstream
```

### Service not responding?
```bash
./deploy_gcp.sh logs
gcloud run services describe upstream-staging --region=us-central1
```

---

## Next Steps

1. ✅ Configure custom domain
2. ✅ Set up monitoring alerts
3. ✅ Create production environment
4. ✅ Configure CI/CD pipeline

**Full Documentation:** See `GCP_DEPLOYMENT_GUIDE.md`

---

**Need Help?**
- GCP Console: https://console.cloud.google.com
- Cloud Run Docs: https://cloud.google.com/run/docs
- Support: https://cloud.google.com/support

---

## Additional Resources

- **Comprehensive GCP Deployment:** See [GCP_DEPLOYMENT_GUIDE.md](GCP_DEPLOYMENT_GUIDE.md)
- **Day-to-Day Operations:** See [DEPLOYMENT_RUNBOOK.md](DEPLOYMENT_RUNBOOK.md)
- **Performance Monitoring:** See [MONITORING.md](MONITORING.md)
- **Security Considerations:** See [SECURITY_AUDIT_REPORT.md](SECURITY_AUDIT_REPORT.md)

---

*Generated by consolidating DEPLOYMENT.md, DEPLOYMENT_CHECKLIST.md, PRODUCTION_DEPLOYMENT_GUIDE.md, and GCP_QUICK_START.md*
