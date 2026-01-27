---
phase: quick-022
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - requirements.txt
  - upstream/settings/prod.py
  - .env.production.example
autonomous: true

user_setup:
  - service: datadog
    why: "Application Performance Monitoring (APM) and distributed tracing"
    env_vars:
      - name: DD_API_KEY
        source: "DataDog Dashboard -> Organization Settings -> API Keys"
      - name: DD_SITE
        source: "Set to 'datadoghq.com' (US) or 'datadoghq.eu' (EU) based on your account region"
      - name: DD_SERVICE
        source: "Set to your service name (e.g., 'upstream-api')"
      - name: DD_ENV
        source: "Set to 'production', 'staging', or 'development'"
      - name: DD_VERSION
        source: "Set via CI/CD or manually (e.g., git commit SHA)"

must_haves:
  truths:
    - "DataDog APM captures traces in production when DD_API_KEY is set"
    - "DataDog includes environment tags for service, env, and version"
    - "DataDog integrates with Django, Celery, and Redis"
    - "Configuration follows same pattern as existing Sentry setup"
  artifacts:
    - path: "requirements.txt"
      provides: "ddtrace dependency"
      contains: "ddtrace"
    - path: "upstream/settings/prod.py"
      provides: "DataDog APM configuration"
      contains: "ddtrace"
      min_lines: 30
    - path: ".env.production.example"
      provides: "DataDog environment variable documentation"
      contains: "DD_API_KEY"
  key_links:
    - from: "upstream/settings/prod.py"
      to: "ddtrace.patch_all()"
      via: "automatic instrumentation initialization"
      pattern: "patch_all"
---

<objective>
Add DataDog APM integration with automatic instrumentation for Django, Celery, and Redis to provide distributed tracing and performance monitoring in production.

Purpose: Enable comprehensive performance monitoring with request tracing, database query analysis, and external service latency tracking similar to existing Sentry integration.
Output: DataDog APM configured with environment tags, automatic instrumentation, and HIPAA-compliant configuration.
</objective>

<execution_context>
@/home/codespace/.claude/get-shit-done/workflows/execute-plan.md
@/home/codespace/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md

Current monitoring stack:
- Sentry for error tracking (configured in prod.py with environment tags)
- Prometheus for metrics (prometheus_client~=0.19.0)
- Structured JSON logging (python-json-logger~=2.0.7)

This task adds DataDog APM to complement existing monitoring:
- Sentry: Error tracking and basic performance sampling (10% traces_sample_rate)
- DataDog: Deep APM with automatic instrumentation, distributed tracing, profiling
- Both configured with environment tags for filtering and correlation

Pattern reference: quick-013 Sentry integration (lines 207-283 in prod.py)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add ddtrace dependency</name>
  <files>requirements.txt</files>
  <action>
Add DataDog APM dependency to requirements.txt after the Monitoring & Metrics section (after line 55):

```python
# Monitoring & Metrics
prometheus-client~=0.19.0
django-prometheus~=2.3.1
sentry-sdk[django]~=1.40.0
ddtrace~=2.7.0  # DataDog APM - automatic instrumentation for Django/Celery/Redis
```

Use version ~=2.7.0 (latest stable as of Jan 2025).

Install in development environment:
```bash
pip install ddtrace~=2.7.0
```

Regenerate lock file:
```bash
pip freeze > requirements-lock.txt
```
  </action>
  <verify>
grep "ddtrace" requirements.txt shows the dependency
grep "ddtrace" requirements-lock.txt shows the pinned version
pip show ddtrace returns package info
  </verify>
  <done>
ddtrace is added to requirements.txt and installed in the environment
  </done>
</task>

<task type="auto">
  <name>Task 2: Configure DataDog APM in production settings</name>
  <files>upstream/settings/prod.py</files>
  <action>
Add DataDog APM configuration to upstream/settings/prod.py after the Sentry section (after line 283).

Add this section:

```python
# =============================================================================
# APPLICATION PERFORMANCE MONITORING (DataDog APM)
# =============================================================================

DD_API_KEY = config("DD_API_KEY", default=None)

if DD_API_KEY:
    from ddtrace import patch_all, config as dd_config

    # Configure DataDog APM settings before patching
    dd_config.django["service_name"] = config("DD_SERVICE", default="upstream-api")
    dd_config.django["distributed_tracing_enabled"] = True
    dd_config.django["analytics_enabled"] = True
    dd_config.django["analytics_sample_rate"] = 1.0  # 100% APM sampling

    # Configure trace agent
    dd_config.trace_agent_url = "http://localhost:8126"  # Standard DataDog agent port

    # Environment and version tags (correlate with Sentry)
    dd_config.env = config("DD_ENV", default="production")
    dd_config.version = config("DD_VERSION", default=None)
    dd_config.service = config("DD_SERVICE", default="upstream-api")

    # HIPAA Compliance: Disable automatic tagging of sensitive data
    # By default, ddtrace does not capture request/response bodies
    # These settings ensure no PII/PHI is sent to DataDog
    dd_config.django["trace_query_string"] = False  # Don't trace query params (may contain PHI)
    dd_config.django["include_user_name"] = False  # Don't include user names (PII)

    # Celery configuration
    dd_config.celery["distributed_tracing_enabled"] = True
    dd_config.celery["analytics_enabled"] = True

    # Redis configuration
    dd_config.redis["service_name"] = f"{config('DD_SERVICE', default='upstream')}-redis"

    # Apply automatic instrumentation to all supported libraries
    # This patches: Django, Celery, Redis, psycopg2, requests, urllib3
    patch_all()

    # Note: DataDog agent must be running to receive traces
    # Install: https://docs.datadoghq.com/agent/
    # Agent listens on localhost:8126 by default
else:
    # DataDog not configured - traces will only be captured by Sentry
    pass
```

Key design decisions:
1. **100% APM sampling**: Unlike Sentry (10%), DataDog is purpose-built for APM and handles high volume
2. **Distributed tracing**: Tracks requests across Django → Celery → Redis
3. **HIPAA compliance**: Disabled query string tracing and user name inclusion
4. **Service correlation**: Same env/version tags as Sentry for cross-tool correlation
5. **Agent-based architecture**: Traces sent to local agent (not directly to DataDog)

Position this section AFTER Sentry (line 283) and BEFORE any Celery/Redis config sections.
  </action>
  <verify>
grep -A 5 "DD_API_KEY" upstream/settings/prod.py shows DataDog configuration
grep "patch_all()" upstream/settings/prod.py shows automatic instrumentation
grep "trace_query_string.*False" upstream/settings/prod.py shows HIPAA compliance setting
python -c "from upstream.settings import prod; print('✓ Settings import successfully')"
  </verify>
  <done>
Production settings include DataDog APM with automatic instrumentation, environment tags, and HIPAA-compliant configuration
  </done>
</task>

<task type="auto">
  <name>Task 3: Document DataDog environment variables</name>
  <files>.env.production.example</files>
  <action>
Add DataDog APM configuration section to .env.production.example after the Sentry section (after line 165).

Add this section:

```bash
# -----------------------------------------------------------------------------
# Application Performance Monitoring (DataDog APM)
# -----------------------------------------------------------------------------

# DataDog API Key for APM traces
# Get from: https://app.datadoghq.com/organization-settings/api-keys
DD_API_KEY=

# DataDog site (region)
# US: datadoghq.com (default)
# EU: datadoghq.eu
DD_SITE=datadoghq.com

# Service name for APM (identifies your application in DataDog)
# Example: upstream-api, upstream-celery
DD_SERVICE=upstream-api

# Environment (should match SENTRY_ENVIRONMENT for correlation)
# Example: production, staging, development
DD_ENV=production

# Version/release identifier (correlate with Sentry releases)
# Recommended: Git commit SHA or semantic version
# Example: 1.2.3 or abc123def
DD_VERSION=

# Note: DataDog Agent must be running to receive traces
# Agent installation: https://docs.datadoghq.com/agent/
# Agent listens on localhost:8126 by default
```

Key documentation points:
1. Cross-reference with Sentry environment variables for correlation
2. Note that DataDog Agent is required (not just SDK)
3. Provide examples for service naming convention
4. Link to agent installation docs

Position this section after Sentry configuration (line 165) and before any other monitoring sections.
  </action>
  <verify>
grep "DD_API_KEY" .env.production.example shows DataDog configuration
grep "datadoghq.com" .env.production.example shows site documentation
grep -c "DD_" .env.production.example returns at least 5 (DD_API_KEY, DD_SITE, DD_SERVICE, DD_ENV, DD_VERSION)
  </verify>
  <done>
.env.production.example documents all DataDog environment variables with clear instructions and cross-references to Sentry
  </done>
</task>

</tasks>

<verification>
After completion:

1. Settings validation:
   ```bash
   python manage.py check --settings=upstream.settings.prod
   ```

2. Import test (without DD_API_KEY set):
   ```python
   # Should import successfully and skip DataDog initialization
   from upstream.settings import prod
   print("✓ Production settings load correctly")
   ```

3. Dependency check:
   ```bash
   pip show ddtrace
   grep ddtrace requirements-lock.txt
   ```

4. Configuration completeness:
   - DataDog APM configured with automatic instrumentation
   - Environment tags match Sentry pattern (env, version, service)
   - HIPAA compliance settings (no query strings, no user names)
   - Documentation includes agent installation instructions

5. Integration test (requires DD_API_KEY and DataDog Agent):
   ```bash
   # Export DD_API_KEY and other variables
   # Start DataDog Agent: sudo systemctl start datadog-agent
   # Run Django with DataDog enabled
   ddtrace-run python manage.py runserver
   # Check DataDog APM dashboard for traces
   ```
</verification>

<success_criteria>
1. ddtrace dependency added to requirements.txt and installed
2. Production settings include DataDog APM configuration with:
   - Automatic instrumentation via patch_all()
   - Environment tags (service, env, version)
   - HIPAA-compliant settings (no query strings, no user names)
   - Django, Celery, and Redis instrumentation enabled
3. .env.production.example documents all DataDog variables
4. Settings import without errors (with or without DD_API_KEY)
5. Configuration follows same pattern as Sentry integration
6. No PHI/PII captured in traces (HIPAA compliance maintained)
</success_criteria>

<output>
After completion, create `.planning/quick/022-add-datadog-apm-integration-configure/022-SUMMARY.md`
</output>
