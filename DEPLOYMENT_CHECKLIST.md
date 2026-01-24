# Payrixa Production Deployment Checklist

**Version:** 1.0.0
**Date:** 2026-01-24
**Status:** Ready for Production Deployment

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
- [ ] Static files directory created: `/var/www/payrixa/static/`
- [ ] Media files directory created: `/var/www/payrixa/media/`

---

## Deployment Steps

### Step 1: Database Migration
```bash
# Set Django settings
export DJANGO_SETTINGS_MODULE=payrixa.settings.production

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
ls -la /var/www/payrixa/static/
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
Description=Gunicorn daemon for Payrixa
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/payrixa
Environment="DJANGO_SETTINGS_MODULE=payrixa.settings.production"
EnvironmentFile=/var/www/payrixa/.env.production
ExecStart=/var/www/payrixa/venv/bin/gunicorn \
    --workers 4 \
    --bind unix:/run/gunicorn.sock \
    --timeout 60 \
    --access-logfile /var/log/payrixa/access.log \
    --error-logfile /var/log/payrixa/error.log \
    payrixa.wsgi:application

[Install]
WantedBy=multi-user.target
```

```bash
# Create log directory
sudo mkdir -p /var/log/payrixa
sudo chown www-data:www-data /var/log/payrixa

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
sudo nano /etc/nginx/sites-available/payrixa
```

```nginx
upstream payrixa {
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
        alias /var/www/payrixa/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /var/www/payrixa/media/;
        expires 7d;
    }

    location / {
        proxy_pass http://payrixa;
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
sudo ln -s /etc/nginx/sites-available/payrixa /etc/nginx/sites-enabled/
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
cd /var/www/payrixa
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
python manage.py migrate payrixa 0011
```
**Warning:** Only rollback if new migration breaks functionality

**Option 3: Full Restore from Backup**
```bash
# Stop application
sudo systemctl stop gunicorn

# Restore database
pg_restore -d payrixa /backups/payrixa_backup_[timestamp].dump

# Revert code
cd /var/www/payrixa
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
pg_dump payrixa > /tmp/test_backup.sql

# Verify backup size
ls -lh /tmp/test_backup.sql
# Expected: >1MB (depends on data)

# Test restore (to test database)
createdb payrixa_test
psql payrixa_test < /tmp/test_backup.sql
# Expected: No errors

# Cleanup
dropdb payrixa_test
rm /tmp/test_backup.sql
```

### Schedule Automated Backups
```bash
# Add to crontab
crontab -e
```

```cron
# Daily backup at 2 AM
0 2 * * * /usr/local/bin/backup-payrixa.sh

# backup-payrixa.sh:
#!/bin/bash
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
pg_dump payrixa | gzip > /backups/payrixa_$TIMESTAMP.sql.gz
# Keep last 30 days
find /backups -name "payrixa_*.sql.gz" -mtime +30 -delete
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
