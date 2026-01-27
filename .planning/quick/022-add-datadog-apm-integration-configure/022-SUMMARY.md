---
phase: quick-022
plan: 01
subsystem: monitoring
completed: 2026-01-27
duration: 5 min

tags:
  - monitoring
  - apm
  - performance
  - datadog
  - distributed-tracing
  - hipaa

requires:
  - quick-013  # Sentry error tracking (pattern reference)
  - quick-001  # Prometheus metrics

provides:
  - datadog-apm-integration
  - distributed-tracing
  - performance-monitoring
  - hipaa-compliant-tracing

affects:
  - production-observability
  - performance-analysis
  - service-correlation

tech-stack:
  added:
    - ddtrace~=2.7.0
  patterns:
    - agent-based-apm
    - automatic-instrumentation
    - distributed-tracing
    - environment-tagging

key-files:
  created: []
  modified:
    - requirements.txt
    - upstream/settings/prod.py
    - .env.production.example

decisions:
  - slug: datadog-100-percent-sampling
    title: 100% APM sampling for DataDog
    status: decided
    context: Unlike Sentry (10% traces_sample_rate), DataDog is purpose-built for APM and designed to handle high transaction volume
    decision: Use analytics_sample_rate=1.0 for comprehensive performance monitoring
    consequences: Complete performance visibility with minimal overhead, DataDog's agent architecture handles volume efficiently

  - slug: agent-based-architecture
    title: Use DataDog Agent for trace collection
    status: decided
    context: DataDog offers two approaches - direct API or local agent
    decision: Configure trace_agent_url to localhost:8126 (local agent)
    consequences: Better performance (local buffering), network resilience, agent handles sampling and aggregation

  - slug: hipaa-compliant-tracing
    title: Disable PII/PHI capture in traces
    status: decided
    context: APM traces could inadvertently capture sensitive data in query strings or user identifiers
    decision: Set trace_query_string=False and include_user_name=False
    consequences: HIPAA compliance maintained, reduced risk of PHI exposure, slight reduction in debugging detail

  - slug: service-correlation-tags
    title: Match Sentry environment tags
    status: decided
    context: Both Sentry and DataDog monitor the same application
    decision: Use consistent env/version/service tags (DD_ENV matches SENTRY_ENVIRONMENT)
    consequences: Easy correlation between error tracking and performance traces, unified observability

metrics:
  tasks_completed: 3
  tasks_total: 3
  commits: 3
  files_modified: 3
  files_created: 0
---

# Quick Task 022: DataDog APM Integration

**One-liner:** Agent-based DataDog APM with automatic Django/Celery/Redis instrumentation and HIPAA-compliant trace configuration

## What Was Built

Integrated DataDog APM (Application Performance Monitoring) to provide comprehensive distributed tracing and performance monitoring for the Django application, Celery tasks, and Redis operations.

### Components

1. **Dependency**: Added ddtrace~=2.7.0 with automatic instrumentation support
2. **Production Configuration**: DataDog APM settings in prod.py with:
   - Automatic instrumentation via patch_all() for Django, Celery, Redis, psycopg2
   - 100% APM sampling for complete performance visibility
   - Distributed tracing across service boundaries
   - Environment tags for service correlation (env, version, service)
   - HIPAA compliance (no query strings, no user names)
   - Agent-based architecture (localhost:8126)
3. **Documentation**: Complete environment variable guide in .env.production.example

### Integration Points

- **Django**: Automatic middleware instrumentation for request/response tracing
- **Celery**: Task execution tracing with distributed context propagation
- **Redis**: Cache and queue operation monitoring
- **PostgreSQL**: Database query performance tracking (via psycopg2)
- **Sentry**: Shared environment tags for error-to-performance correlation

## Task Breakdown

| Task | Type | Description | Commit | Files |
|------|------|-------------|--------|-------|
| 1 | auto | Add ddtrace dependency | a7b0a550 | requirements.txt |
| 2 | auto | Configure DataDog APM in production | dde5a66a | upstream/settings/prod.py |
| 3 | auto | Document environment variables | 5ce1c73c | .env.production.example |

## Key Decisions Made

### 1. 100% APM Sampling vs Sentry's 10%

**Context**: Sentry uses 10% traces_sample_rate for cost management

**Decision**: Configure DataDog with 100% APM sampling (analytics_sample_rate=1.0)

**Rationale**:
- DataDog is purpose-built for high-volume APM (Sentry is primarily error tracking)
- Agent-based architecture efficiently handles full sampling
- Comprehensive performance visibility critical for optimization
- DataDog's pricing model designed for high transaction volume

**Impact**: Complete performance data with minimal overhead, no sampling gaps

### 2. Agent-Based Architecture

**Context**: DataDog supports direct API or local agent deployment

**Decision**: Use local DataDog Agent (localhost:8126) for trace collection

**Rationale**:
- Better performance through local buffering and batching
- Network resilience (agent retries failed uploads)
- Agent handles intelligent sampling and aggregation
- Industry best practice for production deployments

**Impact**: Requires agent installation but provides better reliability

### 3. HIPAA Compliance Settings

**Context**: APM traces can capture request data including query parameters and user info

**Decision**: Disabled trace_query_string and include_user_name

**Rationale**:
- Query parameters may contain PHI (patient IDs, names, dates)
- User names are PII that shouldn't leave the system
- Request/response bodies already excluded by default
- Defense-in-depth compliance approach

**Impact**: HIPAA compliance maintained, minimal impact on debugging capability

### 4. Service Correlation Tags

**Context**: Both Sentry and DataDog monitor the same services

**Decision**: Use matching environment tags (DD_ENV = SENTRY_ENVIRONMENT, shared DD_VERSION)

**Rationale**:
- Enables correlation between error spikes and performance degradation
- Unified view across monitoring tools
- Consistent deployment tracking
- Simplifies incident investigation

**Impact**: Operators can quickly correlate Sentry errors with DataDog traces

## Configuration Details

### DataDog Settings

```python
# Production configuration (upstream/settings/prod.py)
dd_config.django["service_name"] = "upstream-api"
dd_config.django["distributed_tracing_enabled"] = True
dd_config.django["analytics_enabled"] = True
dd_config.django["analytics_sample_rate"] = 1.0  # 100% sampling

# HIPAA Compliance
dd_config.django["trace_query_string"] = False
dd_config.django["include_user_name"] = False

# Environment tags
dd_config.env = "production"
dd_config.version = git_commit_sha
dd_config.service = "upstream-api"
```

### Environment Variables

Required:
- `DD_API_KEY`: DataDog API key from organization settings
- `DD_SERVICE`: Service name (e.g., "upstream-api")
- `DD_ENV`: Environment name (production, staging, development)

Optional:
- `DD_SITE`: Region (datadoghq.com or datadoghq.eu)
- `DD_VERSION`: Release version (git SHA or semantic version)

### Automatic Instrumentation

patch_all() instruments:
- Django views and middleware
- Celery tasks and workers
- Redis commands (cache, queues)
- PostgreSQL queries (psycopg2)
- HTTP requests (requests, urllib3)
- Template rendering

## Verification Results

✅ Settings validation: `python manage.py check --settings=upstream.settings.prod` passes
✅ Import test: Production settings load without errors (with or without DD_API_KEY)
✅ Dependency check: ddtrace 2.7.10 installed
✅ Configuration completeness: All environment variables documented
✅ HIPAA compliance: Query strings and user names disabled

## Deviations from Plan

None - plan executed exactly as written.

## Integration Testing

Full integration testing requires:

1. **DataDog Account**: Active DataDog account with API key
2. **Agent Installation**:
   ```bash
   # Install DataDog Agent
   DD_API_KEY=<key> bash -c "$(curl -L https://s3.amazonaws.com/dd-agent/scripts/install_script.sh)"

   # Start agent
   sudo systemctl start datadog-agent

   # Verify agent status
   sudo datadog-agent status
   ```
3. **Environment Configuration**:
   ```bash
   export DD_API_KEY=<your-api-key>
   export DD_SERVICE=upstream-api
   export DD_ENV=development
   export DD_VERSION=$(git rev-parse --short HEAD)
   ```
4. **Run Application**:
   ```bash
   # Start with DataDog instrumentation
   ddtrace-run python manage.py runserver

   # Or for production
   ddtrace-run gunicorn upstream.wsgi
   ```
5. **Verification**: Check DataDog APM dashboard for:
   - Service "upstream-api" appears
   - Requests traced end-to-end
   - Database queries visible
   - Celery tasks tracked
   - Redis operations monitored

## Monitoring Stack Summary

After this task, complete observability stack:

| Tool | Purpose | Sampling | Data Collected |
|------|---------|----------|----------------|
| **Sentry** | Error tracking | 10% traces | Exceptions, stack traces, error context |
| **DataDog APM** | Performance monitoring | 100% traces | Request latency, DB queries, service calls |
| **Prometheus** | Metrics | All requests | HTTP status codes, response times, counts |
| **Structured Logging** | Audit trail | All events | HIPAA audit logs, security events |

## Next Steps

### Immediate (Required for Production)

1. **Install DataDog Agent** on production servers
2. **Configure environment variables** in deployment pipeline
3. **Set DD_VERSION** to git SHA in CI/CD
4. **Verify agent connectivity** to DataDog intake

### Short-term (Recommended)

1. **Create DataDog Dashboards**:
   - API endpoint performance
   - Database query performance
   - Celery task duration
   - Error rate correlation with Sentry

2. **Set up APM Alerts**:
   - p95 latency > 1s
   - Error rate > 5%
   - Slow database queries > 500ms
   - Celery task failures

3. **Enable Profiling** (optional):
   - CPU profiling for hot paths
   - Memory profiling for leaks
   - Requires additional configuration

### Long-term (Optimization)

1. **Trace analysis** for optimization opportunities
2. **Service map review** to understand dependencies
3. **Historical trend analysis** for capacity planning
4. **Correlation** between deployments and performance changes

## References

- DataDog APM Python: https://docs.datadoghq.com/tracing/setup_overview/setup/python/
- Agent Installation: https://docs.datadoghq.com/agent/
- Django Integration: https://ddtrace.readthedocs.io/en/stable/integrations.html#django
- HIPAA Compliance: https://www.datadoghq.com/legal/hipaa/
- Pattern Reference: quick-013 (Sentry integration in prod.py lines 207-283)

## Related Tasks

- quick-001: Prometheus metrics endpoint
- quick-002: Structured JSON logging
- quick-013: Sentry error tracking integration
- Future: Custom DataDog dashboards and alerts

---

**Task Status**: ✅ Complete
**Commits**: a7b0a550, dde5a66a, 5ce1c73c
**Duration**: ~5 minutes
**Next**: Task 023 (Custom Grafana dashboards) or continue with planned phases
