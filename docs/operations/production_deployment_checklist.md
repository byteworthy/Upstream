# Production Deployment Checklist

This checklist ensures a safe and successful deployment to production. Complete all items before deploying.

## Pre-Deployment

### Code Quality
- [ ] All tests pass (`python manage.py test`)
- [ ] Code coverage meets minimum threshold (80%)
- [ ] No critical security vulnerabilities in dependencies
- [ ] Code has been reviewed and approved
- [ ] All merge conflicts resolved

### Database
- [ ] Migrations have been tested on staging
- [ ] Migrations are backwards-compatible (or rollback plan exists)
- [ ] Database backup completed
- [ ] Verify migration doesn't lock tables for extended periods

### Configuration
- [ ] Environment variables verified for production
- [ ] Secrets rotated if needed (API keys, passwords)
- [ ] Feature flags configured for gradual rollout
- [ ] Rate limits configured appropriately

### Dependencies
- [ ] All dependencies pinned to specific versions
- [ ] No known vulnerabilities in dependencies
- [ ] Third-party service credentials verified

## Deployment

### Infrastructure
- [ ] Kubernetes cluster healthy
- [ ] Sufficient resources available (CPU, memory)
- [ ] Load balancer configured correctly
- [ ] SSL certificates valid (not expiring soon)

### Database Migrations
```bash
# Run migrations with timeout
kubectl exec -it deployment/upstream-web -- python manage.py migrate --check
kubectl exec -it deployment/upstream-web -- python manage.py migrate
```

### Application Deployment
```bash
# Deploy with rolling update
kubectl rollout restart deployment/upstream-web
kubectl rollout status deployment/upstream-web

# Verify pods are healthy
kubectl get pods -l app=upstream-web
```

### Health Checks
- [ ] `/health/` endpoint returns 200
- [ ] `/health/db/` endpoint returns 200
- [ ] `/health/redis/` endpoint returns 200
- [ ] Prometheus metrics endpoint accessible

## Post-Deployment

### Verification
- [ ] Application loads without errors
- [ ] Authentication working
- [ ] Core features functional (claim submission, scoring)
- [ ] API endpoints responding correctly
- [ ] WebSocket connections working (if applicable)

### Monitoring
- [ ] Error rates normal (< 0.1%)
- [ ] Response times acceptable (p95 < 500ms)
- [ ] No memory leaks detected
- [ ] CPU utilization stable

### Logging
- [ ] Application logs flowing to centralized logging
- [ ] No unexpected errors in logs
- [ ] Audit logs being recorded

### Alerts
- [ ] Alerting thresholds configured
- [ ] On-call team notified of deployment
- [ ] Escalation path confirmed

## Rollback Plan

### Triggers for Rollback
- Error rate exceeds 1%
- p95 latency exceeds 2 seconds
- Critical security vulnerability discovered
- Data integrity issues detected

### Rollback Steps
```bash
# Revert to previous deployment
kubectl rollout undo deployment/upstream-web

# Verify rollback
kubectl rollout status deployment/upstream-web

# If database migration needs rollback
kubectl exec -it deployment/upstream-web -- python manage.py migrate <app_name> <previous_migration>
```

### Post-Rollback
- [ ] Verify application is stable
- [ ] Notify stakeholders
- [ ] Create incident report
- [ ] Schedule post-mortem

## Security Checklist

### HIPAA Compliance
- [ ] PHI encryption at rest verified
- [ ] PHI encryption in transit verified (TLS 1.2+)
- [ ] Audit logging enabled
- [ ] Access controls properly configured
- [ ] Session timeout configured (15 minutes)

### Security Headers
- [ ] Content-Security-Policy configured
- [ ] X-Frame-Options set to DENY
- [ ] X-Content-Type-Options set to nosniff
- [ ] Strict-Transport-Security enabled

### Authentication
- [ ] MFA enabled for admin accounts
- [ ] Password policies enforced
- [ ] JWT token expiration set correctly
- [ ] Session management working

## Performance Checklist

### Caching
- [ ] Redis cache operational
- [ ] Cache hit rates acceptable (> 90%)
- [ ] Cache TTLs configured appropriately

### Database
- [ ] Connection pooling configured
- [ ] Query performance acceptable
- [ ] No N+1 queries in critical paths
- [ ] Indexes properly utilized

### CDN
- [ ] Static assets served from CDN
- [ ] CDN cache headers configured
- [ ] Compression enabled (gzip/brotli)

## Communication

### Stakeholder Notification
- [ ] Engineering team notified
- [ ] Customer support notified (if user-facing changes)
- [ ] Sales/Account team notified (if new features)
- [ ] Update status page (if applicable)

### Documentation
- [ ] Release notes prepared
- [ ] API documentation updated (if changes)
- [ ] Runbook updated (if new procedures)

---

## Sign-Off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Developer | | | |
| Reviewer | | | |
| DevOps | | | |
| Security | | | |

---

*Last Updated: February 2026*
*Version: 1.0*
