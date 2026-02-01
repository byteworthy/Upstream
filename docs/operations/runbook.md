# Upstream Healthcare Operations Runbook

## Quick Reference

| Service | Health Endpoint | Logs | Metrics |
|---------|-----------------|------|---------|
| Web App | `/health/` | `kubectl logs -l app=upstream-web` | Prometheus |
| Workers | N/A | `kubectl logs -l app=upstream-worker` | Prometheus |
| Redis | `redis-cli ping` | CloudWatch | Redis metrics |
| PostgreSQL | `pg_isready` | CloudWatch | RDS metrics |

## Common Operations

### Restart Application

```bash
# Rolling restart (zero downtime)
kubectl rollout restart deployment/upstream-web

# Check status
kubectl rollout status deployment/upstream-web
```

### Scale Application

```bash
# Scale web pods
kubectl scale deployment/upstream-web --replicas=5

# Scale workers
kubectl scale deployment/upstream-worker --replicas=3
```

### View Logs

```bash
# Live logs from web pods
kubectl logs -f deployment/upstream-web --all-containers

# Logs from specific pod
kubectl logs -f pod/upstream-web-xxxxx

# Filter by time
kubectl logs deployment/upstream-web --since=1h
```

### Database Operations

```bash
# Open Django shell
kubectl exec -it deployment/upstream-web -- python manage.py shell

# Run migrations
kubectl exec -it deployment/upstream-web -- python manage.py migrate

# Create superuser
kubectl exec -it deployment/upstream-web -- python manage.py createsuperuser
```

### Cache Operations

```bash
# Clear Django cache
kubectl exec -it deployment/upstream-web -- python manage.py clearcache

# Connect to Redis
kubectl exec -it deployment/upstream-redis -- redis-cli

# Flush Redis (DANGER: clears all cache)
# redis-cli FLUSHALL
```

## Incident Response

### High Error Rate

1. Check error logs for patterns:
   ```bash
   kubectl logs deployment/upstream-web --since=10m | grep -i error
   ```

2. Check database connectivity:
   ```bash
   kubectl exec -it deployment/upstream-web -- python manage.py dbshell
   ```

3. Check external service health:
   - Stripe API status: https://status.stripe.com
   - AWS status: https://health.aws.amazon.com

4. If needed, scale up:
   ```bash
   kubectl scale deployment/upstream-web --replicas=10
   ```

### High Latency

1. Check database slow queries in CloudWatch

2. Check Redis performance:
   ```bash
   redis-cli INFO stats
   ```

3. Review recent deployments for regression

4. Check for traffic spike in metrics

### Memory Issues

1. Check pod memory usage:
   ```bash
   kubectl top pods
   ```

2. Check for memory leaks in metrics

3. Restart affected pods:
   ```bash
   kubectl delete pod <pod-name>
   ```

### Database Connection Issues

1. Check RDS status in AWS Console

2. Verify security groups allow connections

3. Check connection pool exhaustion:
   ```sql
   SELECT count(*) FROM pg_stat_activity;
   ```

4. If pool exhausted, restart pods to release connections

## Maintenance Procedures

### Database Backup Verification

```bash
# List recent backups
aws rds describe-db-snapshots --db-instance-identifier upstream-prod

# Test restore to staging (manual process in AWS Console)
```

### SSL Certificate Renewal

1. Check certificate expiration:
   ```bash
   kubectl get certificate -n upstream
   ```

2. If using cert-manager, renewal is automatic

3. For manual certificates, update secret:
   ```bash
   kubectl create secret tls upstream-tls --cert=tls.crt --key=tls.key
   ```

### Dependency Updates

1. Review security advisories
2. Update requirements.txt with tested versions
3. Test on staging
4. Deploy with normal deployment process

## Monitoring Alerts

### Alert: High Error Rate (>1%)

**Severity**: Critical

**Actions**:
1. Check logs for error patterns
2. Identify affected endpoints
3. Rollback if recent deployment
4. Escalate to engineering if needed

### Alert: High Latency (p95 > 2s)

**Severity**: Warning

**Actions**:
1. Check database performance
2. Check cache hit rates
3. Review traffic patterns
4. Scale if traffic-related

### Alert: Pod Restarts

**Severity**: Warning

**Actions**:
1. Check pod events: `kubectl describe pod <name>`
2. Check for OOM kills
3. Review logs before restart
4. Increase resources if needed

### Alert: Disk Space Low

**Severity**: Warning

**Actions**:
1. Check log rotation
2. Clean up old data if applicable
3. Expand volume if needed

## Security Procedures

### Suspected Security Incident

1. **DO NOT** delete any data or logs
2. Notify security team immediately
3. Preserve evidence
4. Isolate affected systems if needed
5. Follow incident response plan

### Secret Rotation

1. Generate new credentials
2. Update Kubernetes secrets
3. Rollout restart affected deployments
4. Verify new credentials work
5. Revoke old credentials

### Access Audit

```bash
# Review Django admin access
kubectl exec -it deployment/upstream-web -- python manage.py shell
>>> from django.contrib.admin.models import LogEntry
>>> LogEntry.objects.all()[:50]
```

## Contacts

| Role | Name | Contact |
|------|------|---------|
| On-Call Engineer | PagerDuty | |
| Engineering Lead | | |
| Security Team | | security@upstreamhealthcare.com |
| AWS Support | | AWS Console |

---

*Last Updated: February 2026*
