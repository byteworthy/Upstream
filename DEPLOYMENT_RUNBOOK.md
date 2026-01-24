# Deployment Runbook: Phase 2 + DelayGuard

**Version:** 1.0
**Last Updated:** 2026-01-24
**Target:** Staging → Production

## Pre-Deployment Checklist

### Code Readiness ✅
- [x] All Phase 2 fixes complete (11/11)
- [x] DelayGuard integration complete
- [x] Code review passed (Grade: A)
- [x] All tests passing (8/8 = 100%)
- [x] Security audit passed (Zero critical issues)
- [ ] GitHub commits pushed (blocked - requires manual push)
- [x] Documentation complete (18 files)

### Environment Preparation
- [ ] Staging environment provisioned
- [ ] Database backed up
- [ ] Redis cache server running
- [ ] Environment variables configured
- [ ] SSL certificates valid
- [ ] DNS records updated

### Database Migrations Ready
- [x] 5 new migrations created (0014-0018)
- [x] Migrations tested locally
- [x] No destructive operations
- [x] Rollback plan documented
- [ ] Migration time estimated (<5 minutes expected)

---

## Deployment Steps

### Step 1: Push to GitHub (MANUAL)

```bash
# Current status: 12 commits ready locally
# Commit 22fa416: security cache hashing + code review
# Commit 0349010: Phase 2 + DelayGuard (main commit)

# User needs to manually push due to token permissions:
git push origin main

# Verify push success:
git log origin/main --oneline -5
```

**Expected Output:**
```
22fa416 security: Upgrade cache key hashing from MD5 to SHA256
0349010 feat: Complete Phase 2 production readiness + DelayGuard integration
a78f27b docs: Update roadmap - Phase 4 complete
1dda079 feat: Amplify operator memory with recovery ledger
1afa167 docs: Update roadmap with completion status
```

---

### Step 2: Deploy to Staging

```bash
# Option A: Automated deployment
./deploy_staging.sh

# Option B: Dry run first (recommended)
./deploy_staging.sh --dry-run

# Option C: Manual deployment
git pull origin main
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --no-input
sudo systemctl restart gunicorn  # or your service manager
```

**Staging URL:** https://staging.upstream.cx (update as needed)

---

### Step 3: Run Smoke Tests

```bash
# Critical tests only (fast)
python smoke_tests.py --env staging --critical-only

# Full test suite
python smoke_tests.py --env staging
```

**Expected Results:**
- ✅ Health endpoint returns 200 OK
- ✅ Database connected
- ✅ Redis cache operational
- ✅ Home page loads
- ✅ Login page loads
- ✅ All dashboards require authentication
- ✅ All migrations applied

---

### Step 4: Manual Testing

#### Test 1: DriftWatch Dashboard
1. Login as staff user
2. Navigate to /portal/products/driftwatch/
3. Verify drift events display
4. Test operator actions (real/noise/needs follow-up)
5. Check recovery ledger updates

#### Test 2: DenialScope Dashboard
1. Navigate to /portal/products/denialscope/
2. Verify denial signals display
3. Test deep dive modal
4. Check suppression context badges

#### Test 3: DelayGuard Dashboard (NEW)
1. Navigate to /portal/products/delayguard/
2. Verify payment delay signals display
3. Check severity scoring (critical/high/medium/low)
4. Verify dollars-at-risk calculation
5. Test operator feedback integration
6. Check top payers section

#### Test 4: Data Quality Reports (NEW)
1. Navigate to /portal/data-quality/
2. Upload a test CSV file
3. Verify validation errors display
4. Check quality score calculation
5. Test anomaly detection

#### Test 5: Performance
1. Check upload processing time (<30 seconds for 1000 rows)
2. Verify cache hit rate (should be >95% after warmup)
3. Monitor request timing (most requests <500ms)
4. Check Redis stats in monitoring dashboard

#### Test 6: Security
1. Verify session timeout (30 minutes)
2. Test PHI detection in uploads
3. Check Sentry error tracking (trigger test error)
4. Verify HTTPS redirect
5. Check CSRF protection on forms

---

### Step 5: Performance Validation

```bash
# Monitor application metrics
python manage.py shell
>>> from django.core.cache import cache
>>> from upstream.cache import get_cache_stats
>>> get_cache_stats()

# Expected:
# - hit_rate: >95%
# - used_memory: <500MB
# - connected_clients: >0
```

---

### Step 6: Database Validation

```bash
# Verify migrations applied
python manage.py showmigrations

# Check new models exist
python manage.py shell
>>> from upstream.products.delayguard.models import PaymentDelaySignal
>>> PaymentDelaySignal.objects.count()  # Should be 0 initially

# Verify indexes created (PostgreSQL only)
python manage.py dbshell
postgres=# \di+ *_idx
# Should show all 29 indexes from Phase 2
```

---

### Step 7: User Acceptance Testing

**Test Users:**
- [ ] Create test customer account
- [ ] Upload sample claims data (healthcare_claims_sample.csv)
- [ ] Run DelayGuard computation
- [ ] Verify signals generated
- [ ] Test operator workflow (judgment, recovery tracking)

**Success Criteria:**
- All 3 product dashboards functional
- Alerts generate and display correctly
- Operator actions persist
- Recovery ledger updates
- No 500 errors in logs

---

## Production Deployment

### Pre-Production Checklist
- [ ] Staging tests passed (100%)
- [ ] User acceptance testing complete
- [ ] Stakeholders notified
- [ ] Maintenance window scheduled
- [ ] Rollback plan reviewed
- [ ] Production backup completed
- [ ] Monitoring alerts configured

### Production Deployment Steps

```bash
# 1. Enable maintenance mode
# (Configure based on your setup)

# 2. Backup production database
pg_dump -U postgres upstream_prod > backup_prod_$(date +%Y%m%d_%H%M%S).sql

# 3. Deploy code
git pull origin main
pip install -r requirements.txt --no-cache-dir

# 4. Run migrations (with downtime)
python manage.py migrate

# 5. Collect static files
python manage.py collectstatic --no-input --clear

# 6. Restart services
sudo systemctl restart gunicorn
sudo systemctl restart celery  # if using Celery

# 7. Disable maintenance mode

# 8. Run smoke tests
python smoke_tests.py --env production --critical-only

# 9. Monitor for 30 minutes
# Watch logs, metrics, error rates
```

---

## Rollback Procedure

### If deployment fails in staging:

```bash
./deploy_staging.sh --rollback
```

### If deployment fails in production:

```bash
# 1. Enable maintenance mode

# 2. Revert to previous commit
git log --oneline -5  # Find previous commit hash
git reset --hard <previous-commit-hash>

# 3. Rollback migrations
python manage.py migrate upstream 0013  # Before Phase 2 migrations

# 4. Restart services
sudo systemctl restart gunicorn

# 5. Restore database if needed
psql -U postgres upstream_prod < backup_prod_TIMESTAMP.sql

# 6. Disable maintenance mode

# 7. Notify stakeholders
```

---

## Monitoring Post-Deployment

### Critical Metrics (First 1 Hour)

**Application Health:**
- [ ] Error rate <0.1%
- [ ] Response time p95 <1000ms
- [ ] Request throughput stable
- [ ] No 500 errors

**Database:**
- [ ] Connection pool healthy
- [ ] Query performance stable
- [ ] No slow queries (>2s)
- [ ] Migration rollback available

**Cache:**
- [ ] Redis hit rate >95%
- [ ] Cache memory <80% used
- [ ] No connection errors

**Security:**
- [ ] No PHI leaks in Sentry
- [ ] Session timeout working
- [ ] HTTPS enforced
- [ ] CSRF protection active

### Monitoring Commands

```bash
# Watch application logs
tail -f /var/log/gunicorn/error.log

# Monitor Redis
redis-cli INFO stats

# Check Django logs
tail -f /var/log/django/payrixa.log

# System resource usage
htop
```

---

## Post-Deployment Tasks

### Immediate (Within 1 Hour)
- [ ] Verify all smoke tests pass
- [ ] Check error logs (should be clean)
- [ ] Monitor application metrics
- [ ] Test critical user flows
- [ ] Notify team of successful deployment

### Within 24 Hours
- [ ] Run full test suite against production
- [ ] Generate DelayGuard signals for all customers
- [ ] Review data quality reports
- [ ] Check cache performance metrics
- [ ] Update documentation

### Within 1 Week
- [ ] Gather user feedback
- [ ] Address any minor issues discovered
- [ ] Optimize slow queries if any
- [ ] Review Sentry error reports
- [ ] Plan next iteration

---

## Troubleshooting

### Issue: Migration Fails

**Symptoms:** `python manage.py migrate` errors out

**Solution:**
```bash
# Check migration status
python manage.py showmigrations

# Try migrate with verbosity
python manage.py migrate --verbosity 3

# If stuck, fake the migration (dangerous!)
# python manage.py migrate --fake upstream 0018

# Rollback to safe point
python manage.py migrate upstream 0013
```

### Issue: Redis Connection Errors

**Symptoms:** "Connection refused" or cache misses

**Solution:**
```bash
# Check Redis status
sudo systemctl status redis

# Restart Redis
sudo systemctl restart redis

# Test connection
redis-cli ping  # Should return PONG

# Application will fall back to local cache
```

### Issue: Static Files Not Loading

**Symptoms:** CSS/JS 404 errors

**Solution:**
```bash
# Recollect static files
python manage.py collectstatic --no-input --clear

# Check STATIC_ROOT setting
python manage.py shell
>>> from django.conf import settings
>>> settings.STATIC_ROOT

# Verify web server configuration (nginx/apache)
```

### Issue: High Memory Usage

**Symptoms:** Server memory >80%

**Solution:**
```bash
# Check Redis memory
redis-cli INFO memory

# Clear cache if needed
python manage.py shell
>>> from django.core.cache import cache
>>> cache.clear()

# Restart services
sudo systemctl restart gunicorn
```

---

## Success Criteria

### Staging Deployment Success
- ✅ All smoke tests pass (100%)
- ✅ No critical errors in logs
- ✅ All 3 product dashboards accessible
- ✅ Performance metrics within SLA
- ✅ Security checks pass

### Production Deployment Success
- ✅ Zero downtime deployment
- ✅ All user flows functional
- ✅ Error rate <0.1%
- ✅ Response time p95 <1s
- ✅ User feedback positive
- ✅ No rollback needed

---

## Contacts

**Deployment Team:**
- Lead Developer: [Name]
- DevOps Engineer: [Name]
- QA Engineer: [Name]

**Escalation:**
- On-call Engineer: [Phone]
- CTO: [Email]

**Support:**
- Sentry: https://sentry.io/upstream
- Monitoring: [Grafana/DataDog URL]
- Logs: [CloudWatch/Splunk URL]

---

## Deployment History

| Date | Environment | Commit | Status | Notes |
|------|-------------|--------|--------|-------|
| 2026-01-24 | Local | 22fa416 | ✅ Success | Code review complete |
| TBD | Staging | 22fa416 | Pending | Awaiting GitHub push |
| TBD | Production | 22fa416 | Pending | Post-staging validation |

---

## Appendix: File Manifest

**Files Changed:** 85 files (+31,609 lines, -186 lines)

**New Product Files (DelayGuard):**
- upstream/products/delayguard/models.py
- upstream/products/delayguard/services.py
- upstream/products/delayguard/views.py
- upstream/templates/upstream/products/delayguard_dashboard.html
- upstream/management/commands/compute_delayguard.py

**New Infrastructure:**
- upstream/cache.py
- upstream/middleware.py (enhanced)
- upstream/views/metrics.py
- upstream/core/data_quality_service.py

**New Migrations:**
- 0014_alertevent_indexes.py
- 0015_dataqualityreport.py
- 0016_appealgeneration_appealtemplate.py
- 0017_paymentdelayaggregate_and_more.py
- 0018_alertevent_payment_delay_signal.py

**Documentation:**
- CODE_REVIEW_REPORT.md
- DEPLOYMENT_RUNBOOK.md (this file)
- PHASE_2_COMPLETION_REPORT.md
- DELAYGUARD_INTEGRATION_SUMMARY.md
- (15 additional docs)

---

**End of Deployment Runbook**
