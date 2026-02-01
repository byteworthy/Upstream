# Production Deployment Checklist

**Upstream Healthcare Platform**

Version 1.0 | February 2026

---

## Overview

This checklist provides a comprehensive guide for deploying Upstream Healthcare Platform to a production environment. Follow each section in order and verify all items before proceeding to the next section.

**Deployment Team Lead**: _________________________
**Deployment Date**: _________________________
**Target Environment**: _________________________

---

## Pre-Deployment Checklist

### 1. Code and Build Verification

- [ ] All code changes merged to release branch
- [ ] CI/CD pipeline passed all stages
- [ ] All unit tests passing
- [ ] All integration tests passing
- [ ] Code coverage meets minimum threshold (25%)
- [ ] Security scans completed with no critical/high findings
- [ ] Dependency vulnerabilities addressed
- [ ] Docker images built and tagged
- [ ] Image vulnerability scan passed

### 2. Change Management

- [ ] Change request approved
- [ ] Deployment window confirmed
- [ ] Stakeholders notified
- [ ] On-call team briefed
- [ ] Rollback plan reviewed

---

## Environment Variables

### Required Environment Variables

Configure all required environment variables before deployment:

#### Django Settings

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `DJANGO_SETTINGS_MODULE` | Django settings module path | `upstream.settings.production` | Yes |
| `DJANGO_SECRET_KEY` | Django secret key (generate unique) | `your-secure-secret-key` | Yes |
| `DEBUG` | Debug mode (must be False in production) | `False` | Yes |
| `ALLOWED_HOSTS` | Comma-separated list of allowed hostnames | `api.upstream-healthcare.com,www.upstream-healthcare.com` | Yes |

#### Database Configuration

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `DATABASE_URL` | PostgreSQL connection URL | `postgres://user:pass@host:5432/dbname` | Yes |
| `DB_CONN_MAX_AGE` | Database connection max age (seconds) | `300` | No |
| `DB_POOL_SIZE` | Connection pool size | `10` | No |
| `DB_MAX_OVERFLOW` | Max connection overflow | `5` | No |

#### Redis/Cache Configuration

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `REDIS_URL` | Redis connection URL | `redis://host:6379/0` | Yes |
| `CACHE_TTL` | Default cache TTL (seconds) | `3600` | No |

#### Celery Configuration

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `CELERY_BROKER_URL` | Celery broker URL | `redis://host:6379/1` | Yes |
| `CELERY_RESULT_BACKEND` | Celery result backend | `redis://host:6379/2` | Yes |
| `CELERY_WORKER_CONCURRENCY` | Worker concurrency | `4` | No |

#### Security Settings

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `CORS_ALLOWED_ORIGINS` | Allowed CORS origins | `https://app.upstream-healthcare.com` | Yes |
| `CSRF_TRUSTED_ORIGINS` | Trusted CSRF origins | `https://app.upstream-healthcare.com` | Yes |
| `SESSION_COOKIE_SECURE` | Secure session cookies | `True` | Yes |
| `CSRF_COOKIE_SECURE` | Secure CSRF cookies | `True` | Yes |

#### Authentication

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `JWT_SECRET_KEY` | JWT signing key | `your-jwt-secret-key` | Yes |
| `JWT_ACCESS_TOKEN_LIFETIME` | Access token lifetime (minutes) | `60` | No |
| `JWT_REFRESH_TOKEN_LIFETIME` | Refresh token lifetime (days) | `7` | No |

#### Storage Configuration

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `AWS_ACCESS_KEY_ID` | AWS access key ID | `AKIAIOSFODNN7EXAMPLE` | Yes* |
| `AWS_SECRET_ACCESS_KEY` | AWS secret access key | `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` | Yes* |
| `AWS_STORAGE_BUCKET_NAME` | S3 bucket name | `upstream-production-files` | Yes* |
| `AWS_S3_REGION_NAME` | S3 region | `us-east-1` | Yes* |

*Or equivalent GCP credentials if using Google Cloud Storage

#### Email Configuration

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `EMAIL_HOST` | SMTP host | `smtp.sendgrid.net` | Yes |
| `EMAIL_PORT` | SMTP port | `587` | Yes |
| `EMAIL_HOST_USER` | SMTP username | `apikey` | Yes |
| `EMAIL_HOST_PASSWORD` | SMTP password/API key | `SG.xxxx` | Yes |
| `DEFAULT_FROM_EMAIL` | Default sender email | `noreply@upstream-healthcare.com` | Yes |

#### Monitoring

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `SENTRY_DSN` | Sentry DSN for error tracking | `https://xxx@sentry.io/xxx` | Yes |
| `PROMETHEUS_MULTIPROC_DIR` | Prometheus multiprocess dir | `/tmp/prometheus` | Yes |
| `LOG_LEVEL` | Application log level | `INFO` | No |

### Environment Variables Verification

```bash
# Verify all required environment variables are set
./scripts/verify-env.sh

# Expected output: All required variables configured
```

- [ ] All required environment variables configured
- [ ] Secrets stored in secure secrets manager (not plain text)
- [ ] Environment variables verification script passed

---

## Database Migrations

### Pre-Migration Steps

1. **Backup Current Database**
   ```bash
   # Create database backup before migration
   pg_dump -h $DB_HOST -U $DB_USER -d $DB_NAME -F c -f backup_$(date +%Y%m%d_%H%M%S).dump
   ```
   - [ ] Database backup completed
   - [ ] Backup verified (size check, table count)
   - [ ] Backup stored in secure location

2. **Review Pending Migrations**
   ```bash
   # List pending migrations
   python manage.py showmigrations --plan | grep -v '\[X\]'
   ```
   - [ ] Pending migrations reviewed
   - [ ] Data migration scripts reviewed
   - [ ] Migration dependencies verified

3. **Test Migrations on Staging**
   ```bash
   # Run migrations on staging first
   python manage.py migrate --database=staging
   ```
   - [ ] Migrations tested on staging environment
   - [ ] No migration errors on staging

### Execute Migrations

```bash
# Apply all pending migrations
python manage.py migrate --noinput

# Verify migration status
python manage.py showmigrations
```

- [ ] All migrations applied successfully
- [ ] No migration errors in logs
- [ ] Database schema matches expected state

### Post-Migration Verification

```bash
# Run Django system check
python manage.py check --deploy

# Verify database connectivity
python manage.py dbshell -c "SELECT 1;"
```

- [ ] Django system check passed
- [ ] Database connectivity verified
- [ ] Application can read/write data

---

## Static Asset Deployment

### Collect Static Files

```bash
# Collect static files to configured storage
python manage.py collectstatic --noinput

# Verify static files collected
ls -la staticfiles/
```

- [ ] Static files collected successfully
- [ ] Static files uploaded to CDN/storage
- [ ] Static file count matches expected

### CDN Configuration

- [ ] CDN cache invalidated for updated assets
- [ ] CDN origin configured correctly
- [ ] CORS headers configured for static assets
- [ ] Cache-Control headers set appropriately

### Asset Verification

```bash
# Verify critical static assets are accessible
curl -I https://cdn.upstream-healthcare.com/static/css/main.css
curl -I https://cdn.upstream-healthcare.com/static/js/app.js
```

- [ ] CSS files accessible
- [ ] JavaScript files accessible
- [ ] Images and fonts accessible
- [ ] API documentation (Swagger/OpenAPI) accessible

---

## DNS Configuration

### DNS Records

Configure the following DNS records:

| Type | Name | Value | TTL | Purpose |
|------|------|-------|-----|---------|
| A | api.upstream-healthcare.com | Load Balancer IP | 300 | API endpoint |
| A | app.upstream-healthcare.com | Load Balancer IP | 300 | Web application |
| CNAME | cdn.upstream-healthcare.com | d1234567.cloudfront.net | 3600 | CDN |
| TXT | _dmarc.upstream-healthcare.com | v=DMARC1; p=quarantine | 3600 | Email security |
| TXT | upstream-healthcare.com | v=spf1 include:sendgrid.net ~all | 3600 | SPF record |
| MX | upstream-healthcare.com | mx.sendgrid.net | 3600 | Email delivery |

### DNS Verification

```bash
# Verify DNS resolution
dig api.upstream-healthcare.com +short
dig app.upstream-healthcare.com +short
dig cdn.upstream-healthcare.com +short
```

- [ ] API domain resolves correctly
- [ ] Web app domain resolves correctly
- [ ] CDN domain resolves correctly
- [ ] Email DNS records configured (SPF, DKIM, DMARC)
- [ ] DNS propagation complete (check with multiple DNS servers)

---

## SSL/TLS Certificate Setup

### Certificate Requirements

- [ ] Valid SSL/TLS certificate obtained
- [ ] Certificate covers all required domains (including wildcards if needed)
- [ ] Certificate chain complete (root + intermediate)
- [ ] Certificate expiration date verified (minimum 30 days validity)

### Certificate Installation

```bash
# Verify certificate installation
openssl s_client -connect api.upstream-healthcare.com:443 -servername api.upstream-healthcare.com

# Check certificate expiration
echo | openssl s_client -connect api.upstream-healthcare.com:443 2>/dev/null | openssl x509 -noout -dates
```

- [ ] Certificate installed on load balancer
- [ ] Certificate chain validated
- [ ] HTTPS redirect configured (HTTP -> HTTPS)
- [ ] HSTS header configured

### TLS Configuration Verification

```bash
# Test TLS configuration
nmap --script ssl-enum-ciphers -p 443 api.upstream-healthcare.com

# Or use SSL Labs
# https://www.ssllabs.com/ssltest/
```

- [ ] TLS 1.3 enabled
- [ ] TLS 1.2 and below disabled
- [ ] Strong cipher suites only
- [ ] SSL Labs grade A or higher
- [ ] Certificate transparency logged

### Certificate Renewal

- [ ] Auto-renewal configured (Let's Encrypt / ACM)
- [ ] Certificate expiration monitoring enabled
- [ ] Renewal process documented

---

## Monitoring and Alerting Setup

### Application Monitoring

#### Health Checks

```bash
# Verify health check endpoints
curl https://api.upstream-healthcare.com/health/
curl https://api.upstream-healthcare.com/health/ready/
curl https://api.upstream-healthcare.com/health/live/
```

- [ ] Liveness probe configured (`/health/live/`)
- [ ] Readiness probe configured (`/health/ready/`)
- [ ] Health check endpoint returns 200 OK

#### Prometheus Metrics

- [ ] Prometheus metrics endpoint exposed (`/metrics/`)
- [ ] Prometheus scrape configuration deployed
- [ ] Key metrics being collected:
  - [ ] Request rate and latency
  - [ ] Error rates by endpoint
  - [ ] Database connection pool status
  - [ ] Cache hit/miss rates
  - [ ] Celery queue depth

#### Grafana Dashboards

- [ ] Application overview dashboard deployed
- [ ] Database performance dashboard deployed
- [ ] Infrastructure dashboard deployed
- [ ] Business metrics dashboard deployed

### Infrastructure Monitoring

- [ ] CPU utilization alerts configured
- [ ] Memory utilization alerts configured
- [ ] Disk space alerts configured
- [ ] Network throughput monitoring enabled

### Log Aggregation

- [ ] Application logs shipping to centralized logging
- [ ] Access logs enabled and shipping
- [ ] Error logs with stack traces
- [ ] Audit logs for security events
- [ ] Log retention policy configured (90+ days)

### Alerting Configuration

| Alert | Condition | Severity | Notification |
|-------|-----------|----------|--------------|
| High Error Rate | >1% 5xx errors | Critical | PagerDuty + Slack |
| High Latency | P95 > 500ms | High | Slack |
| Database Connections | >80% pool | High | Slack |
| CPU Utilization | >80% for 5m | Medium | Slack |
| Disk Space | <20% free | High | Slack |
| Certificate Expiry | <30 days | Medium | Email |
| Health Check Failure | 3 consecutive | Critical | PagerDuty |

- [ ] All critical alerts configured
- [ ] Alert notification channels verified
- [ ] On-call rotation configured
- [ ] Escalation policy defined

---

## Backup Verification

### Database Backups

```bash
# Verify backup exists and is recent
aws s3 ls s3://upstream-backups/database/ | tail -5

# Test backup restoration (on separate instance)
pg_restore -h test-db-host -U $DB_USER -d test_restore backup.dump
```

- [ ] Automated backup schedule configured
- [ ] Backup retention policy set (30 days minimum)
- [ ] Backup encryption enabled
- [ ] Cross-region backup replication (if required)
- [ ] Backup restoration tested

### File Storage Backups

- [ ] S3/GCS versioning enabled
- [ ] Cross-region replication configured
- [ ] Lifecycle policies set

### Configuration Backups

- [ ] Infrastructure as Code in version control
- [ ] Secrets backed up in secure vault
- [ ] Environment configurations documented

### Backup Verification Checklist

- [ ] Database backup completed within last 24 hours
- [ ] Backup size consistent with expected data volume
- [ ] Test restore successful
- [ ] Backup monitoring alerts configured
- [ ] Recovery time objective (RTO) achievable
- [ ] Recovery point objective (RPO) met

---

## Rollback Procedure

### Immediate Rollback (< 5 minutes)

If critical issues are detected immediately after deployment:

1. **Revert Container Image**
   ```bash
   # Roll back to previous container version
   kubectl rollout undo deployment/upstream-api
   kubectl rollout undo deployment/upstream-worker

   # Verify rollback status
   kubectl rollout status deployment/upstream-api
   ```

2. **Verify Rollback**
   ```bash
   # Check current running version
   kubectl get pods -o jsonpath='{.items[*].spec.containers[*].image}'

   # Verify health
   curl https://api.upstream-healthcare.com/health/
   ```

- [ ] Previous container images available
- [ ] Rollback command documented
- [ ] Rollback tested in staging

### Database Rollback (If Migration Issues)

If database migration issues are detected:

1. **Stop Application**
   ```bash
   # Scale down to prevent further writes
   kubectl scale deployment/upstream-api --replicas=0
   kubectl scale deployment/upstream-worker --replicas=0
   ```

2. **Restore Database**
   ```bash
   # Restore from pre-deployment backup
   pg_restore -h $DB_HOST -U $DB_USER -d $DB_NAME --clean backup.dump
   ```

3. **Deploy Previous Version**
   ```bash
   # Deploy previous application version
   kubectl rollout undo deployment/upstream-api
   kubectl rollout undo deployment/upstream-worker
   ```

4. **Verify and Scale Up**
   ```bash
   kubectl scale deployment/upstream-api --replicas=3
   kubectl scale deployment/upstream-worker --replicas=2
   ```

- [ ] Database rollback procedure documented
- [ ] Rollback backup identified and accessible
- [ ] Team trained on rollback procedure

### Rollback Decision Criteria

Initiate rollback if any of the following occur:
- [ ] Health check failures for > 2 minutes
- [ ] Error rate > 5% for > 3 minutes
- [ ] Critical functionality broken
- [ ] Data integrity issues detected
- [ ] Security vulnerability discovered

---

## Post-Deployment Verification

### Smoke Tests

```bash
# Run automated smoke tests
./scripts/smoke-tests.sh production

# Manual verification
curl https://api.upstream-healthcare.com/api/v1/status/
```

- [ ] API endpoints responding correctly
- [ ] Authentication working
- [ ] Database read/write operations successful
- [ ] File upload/download working
- [ ] Email sending functional
- [ ] Background job processing active

### Performance Verification

- [ ] Response times within acceptable range
- [ ] No memory leaks detected
- [ ] Database query performance normal
- [ ] Cache hit rates normal

### Security Verification

- [ ] HTTPS enforced on all endpoints
- [ ] Security headers present (CSP, X-Frame-Options, etc.)
- [ ] Authentication required for protected endpoints
- [ ] Rate limiting active

---

## Sign-Off

### Deployment Completed

| Role | Name | Signature | Date/Time |
|------|------|-----------|-----------|
| Deployment Lead | | | |
| QA Verification | | | |
| Security Review | | | |
| Operations Approval | | | |

### Post-Deployment Notes

_Document any issues, workarounds, or observations:_

```
[Notes here]
```

### Deployment Summary

- **Deployment Start Time**: _______________
- **Deployment End Time**: _______________
- **Total Deployment Duration**: _______________
- **Rollback Required**: Yes / No
- **Issues Encountered**: _______________

---

## Appendix: Quick Reference Commands

### Kubernetes Commands

```bash
# Check deployment status
kubectl get deployments -n upstream

# View pod logs
kubectl logs -f deployment/upstream-api -n upstream

# Restart deployment
kubectl rollout restart deployment/upstream-api -n upstream

# Scale deployment
kubectl scale deployment/upstream-api --replicas=5 -n upstream
```

### Database Commands

```bash
# Connect to database
python manage.py dbshell

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

### Celery Commands

```bash
# Check celery status
celery -A upstream inspect active

# Purge queues (use with caution)
celery -A upstream purge
```

---

*This checklist should be reviewed and updated for each deployment. Contact the DevOps team for questions or assistance.*

*Last Updated: February 2026*
