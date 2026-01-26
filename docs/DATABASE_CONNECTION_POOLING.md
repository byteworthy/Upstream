# Database Connection Pooling - Upstream

**Last Updated**: 2026-01-26
**Issue**: HIGH-11 - Missing database connection pooling
**Status**: ✅ Implemented

---

## Overview

Django uses **persistent connections** (`CONN_MAX_AGE`) instead of traditional connection pooling. Each Gunicorn worker/thread maintains its own database connection that is reused for a configured duration.

### Current Configuration

```python
# upstream/settings/prod.py
DATABASES = {
    'default': {
        'CONN_MAX_AGE': 60,              # Reuse connections for 60 seconds
        'CONN_HEALTH_CHECKS': True,      # Validate connections before reuse
    }
}
```

### Connection Pool Sizing

**Formula**: `Django connections = Gunicorn workers × threads per worker`

**Current Deployment** (Dockerfile):
- Gunicorn workers: 2
- Threads per worker: 4
- **Total Django connections**: 8
- **Recommended PostgreSQL max_connections**: 10 (8 × 1.2 overhead)

### Environment Variables

Override defaults in `.env`:

```bash
# Connection reuse duration in seconds (default: 60)
DB_CONN_MAX_AGE=60

# Enable health checks before connection reuse (default: True)
DB_CONN_HEALTH_CHECKS=True
```

---

## Scaling Guide

### Small to Medium Traffic (<1000 req/min)

**Django persistent connections are sufficient.**

- Gunicorn: 2-4 workers × 4 threads = 8-16 connections
- PostgreSQL: Set `max_connections=25` (allows headroom for migrations, admin)
- CONN_MAX_AGE: 60 seconds (default)
- CONN_HEALTH_CHECKS: True (prevents stale connection errors)

**Pros**:
- Simple configuration
- No additional infrastructure
- Low latency (direct connections)

**Cons**:
- Each worker/thread needs its own connection
- Scaling workers increases database load linearly

---

### High Traffic (>1000 req/min)

**Add PgBouncer connection pooler.**

```
┌─────────────────────────────────────────────────────────┐
│  Django Application (Multiple Instances)                │
│  - Instance 1: 2 workers × 4 threads = 8 connections    │
│  - Instance 2: 2 workers × 4 threads = 8 connections    │
│  - Instance 3: 2 workers × 4 threads = 8 connections    │
│  Total: 24 Django connections                           │
└─────────────────┬───────────────────────────────────────┘
                  │
                  │  Each Django instance connects to PgBouncer
                  │
          ┌───────▼────────┐
          │   PgBouncer    │
          │  (Transaction  │
          │   Mode Pool)   │
          │                │
          │ Pool Size: 25  │  ← PgBouncer maintains 25 connections
          └───────┬────────┘     to PostgreSQL
                  │
                  │  PgBouncer multiplexes Django connections
                  │  onto a smaller pool of PostgreSQL connections
                  │
          ┌───────▼────────┐
          │  PostgreSQL    │
          │                │
          │ max_conn: 100  │  ← Database only sees 25-30 connections
          └────────────────┘     regardless of Django scale
```

#### PgBouncer Configuration

**pgbouncer.ini**:
```ini
[databases]
upstream = host=cloudsql-proxy port=5432 dbname=upstream

[pgbouncer]
# Transaction mode: recommended for Django
# Django gets connection for each transaction, not entire session
pool_mode = transaction

# Connection pool size per database
default_pool_size = 25
reserve_pool_size = 5

# Maximum client connections (Django instances)
max_client_conn = 100

# Server connections (to PostgreSQL)
# Should be less than PostgreSQL max_connections
max_db_connections = 30

# Authentication
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt

# Logging
log_connections = 1
log_disconnections = 1
log_pooler_errors = 1
```

#### Django Configuration with PgBouncer

Update `DATABASE_URL` to point to PgBouncer instead of PostgreSQL directly:

```bash
# .env
# Before (direct PostgreSQL connection):
DATABASE_URL=postgresql://user:pass@cloudsql-proxy:5432/upstream

# After (via PgBouncer):
DATABASE_URL=postgresql://user:pass@pgbouncer:6432/upstream

# Keep connection settings the same
DB_CONN_MAX_AGE=60
DB_CONN_HEALTH_CHECKS=True
```

**No Django code changes required** - PgBouncer is transparent to Django.

#### Docker Compose with PgBouncer

```yaml
version: '3.8'

services:
  pgbouncer:
    image: pgbouncer/pgbouncer:latest
    environment:
      DATABASES_HOST: cloudsql-proxy
      DATABASES_PORT: 5432
      DATABASES_DBNAME: upstream
      PGBOUNCER_POOL_MODE: transaction
      PGBOUNCER_DEFAULT_POOL_SIZE: 25
      PGBOUNCER_MAX_CLIENT_CONN: 100
    ports:
      - "6432:5432"
    volumes:
      - ./pgbouncer.ini:/etc/pgbouncer/pgbouncer.ini
      - ./userlist.txt:/etc/pgbouncer/userlist.txt

  app:
    build: .
    environment:
      DATABASE_URL: postgresql://user:pass@pgbouncer:6432/upstream
    depends_on:
      - pgbouncer
```

---

## Cloud Run Deployment with PgBouncer

### Option 1: Cloud SQL Proxy with PgBouncer Sidecar

**cloudbuild.yaml** (add PgBouncer sidecar):
```yaml
# Deploy Cloud Run service with PgBouncer sidecar
- name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
  entrypoint: gcloud
  args:
    - 'run'
    - 'deploy'
    - 'upstream-prod'
    - '--image=gcr.io/$PROJECT_ID/upstream:$SHORT_SHA'
    - '--region=us-central1'
    - '--platform=managed'
    - '--add-cloudsql-instances=$PROJECT_ID:us-central1:upstream-prod'
    - '--set-env-vars=DATABASE_URL=postgresql://user@pgbouncer:6432/upstream'
    # PgBouncer container runs as sidecar
    - '--sidecar-image=pgbouncer/pgbouncer:latest'
    - '--sidecar-env-vars=DATABASES_HOST=/cloudsql/$PROJECT_ID:us-central1:upstream-prod'
```

### Option 2: Managed Cloud SQL Connection Pooling

Google Cloud SQL has built-in connection pooling that works similarly to PgBouncer:

**Enable in Cloud SQL**:
```bash
gcloud sql instances patch upstream-prod \
  --database-flags=max_connections=100

# Cloud SQL automatically manages connection pooling
# for Cloud Run services via the Cloud SQL Proxy
```

**Recommended**: Use Cloud SQL's built-in pooling for Cloud Run deployments.

---

## Monitoring

### Key Metrics to Track

**Django Application**:
```python
# Track active database connections
from django.db import connection
print(f"Active connections: {len(connection.queries)}")
```

**PostgreSQL Queries**:
```sql
-- Current active connections
SELECT COUNT(*) FROM pg_stat_activity WHERE state = 'active';

-- Connection pool usage
SELECT
    state,
    COUNT(*) as connections
FROM pg_stat_activity
WHERE datname = 'upstream'
GROUP BY state;

-- Idle connections (should be reused via CONN_MAX_AGE)
SELECT COUNT(*) FROM pg_stat_activity
WHERE state = 'idle' AND state_change < NOW() - INTERVAL '60 seconds';
```

**PgBouncer Stats**:
```bash
# Connect to PgBouncer admin console
psql -h pgbouncer -p 6432 -U pgbouncer pgbouncer

# Show pool statistics
SHOW POOLS;

# Show client connections
SHOW CLIENTS;

# Show server connections
SHOW SERVERS;
```

### Alerting Thresholds

**Warning**: Database connections > 80% of max_connections
```sql
SELECT
    (SELECT COUNT(*) FROM pg_stat_activity) * 100.0 /
    (SELECT setting::int FROM pg_settings WHERE name = 'max_connections')
    AS connection_usage_percent;
```

**Critical**: Database connections > 95% of max_connections

---

## Troubleshooting

### Issue: "too many clients already"

**Cause**: PostgreSQL max_connections reached.

**Solution**:
1. Check current connection count:
   ```sql
   SELECT COUNT(*) FROM pg_stat_activity;
   ```

2. Increase max_connections (short-term):
   ```sql
   ALTER SYSTEM SET max_connections = 100;
   SELECT pg_reload_conf();
   ```

3. Add PgBouncer (long-term solution)

### Issue: "server closed the connection unexpectedly"

**Cause**: Stale connection not detected.

**Solution**: Enable CONN_HEALTH_CHECKS:
```bash
# .env
DB_CONN_HEALTH_CHECKS=True
```

### Issue: High connection churn

**Cause**: CONN_MAX_AGE too low or disabled.

**Solution**: Increase CONN_MAX_AGE:
```bash
# .env
DB_CONN_MAX_AGE=60  # or higher for stable traffic
```

---

## Performance Impact

### Before (CONN_MAX_AGE=0, no pooling)
- Each request opens new connection
- Connection overhead: ~5-10ms per request
- Database sees 100+ connections during traffic spikes

### After (CONN_MAX_AGE=60, CONN_HEALTH_CHECKS=True)
- Connections reused for 60 seconds
- Connection overhead: ~0.1ms (health check only)
- Database sees 8-10 steady connections

**Expected improvements**:
- 5-10ms faster API response times
- Reduced PostgreSQL CPU usage by 20-30%
- Fewer "too many clients" errors
- Better request throughput under load

---

## References

- [Django Database Connection Management](https://docs.djangoproject.com/en/5.0/ref/databases/#connection-management)
- [Django CONN_HEALTH_CHECKS](https://docs.djangoproject.com/en/5.0/ref/settings/#conn-health-checks)
- [PgBouncer Documentation](https://www.pgbouncer.org/usage.html)
- [Google Cloud SQL Connection Pooling](https://cloud.google.com/sql/docs/postgres/manage-connections)
