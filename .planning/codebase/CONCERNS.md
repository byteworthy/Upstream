# Codebase Concerns

**Analysis Date:** 2026-01-26

## Tech Debt

**Large Monolithic Files:**
- Issue: Multiple files exceed 800+ lines, creating maintenance and testing challenges
- Files:
  - `upstream/views/__init__.py` (967 lines)
  - `upstream/models.py` (966 lines)
  - `upstream/api/views.py` (881 lines)
  - `upstream/tests.py` (880 lines)
  - `upstream/products/driftwatch/services.py` (933 lines)
  - `upstream/products/delayguard/services.py` (914 lines)
- Impact: Single points of failure, difficult to test individual functions, high cognitive load, increased risk of merge conflicts
- Fix approach: Extract related functionality into smaller modules (e.g., separate service classes, split views into multiple viewsets)

**Cache Configuration Fallback Issues:**
- Issue: Redis connection failure is caught with broad `Exception` handler, silently falling back to local memory cache
- Files: `upstream/settings/base.py` lines 256-285
- Impact: In production, memory cache silently replaces Redis without alerting operators. Memory cache is not suitable for multi-process environments (each process has isolated cache). Silent failures hide real infrastructure problems.
- Fix approach:
  - Distinguish between transient failures and configuration errors
  - Log Redis availability at startup
  - In production, fail fast if Redis is unavailable (don't silently degrade)
  - Add explicit environment variable to control fallback behavior

**Database Connection Max Age Not Optimized for Concurrent Workloads:**
- Issue: Default `DB_CONN_MAX_AGE` is 60 seconds, but no connection pooling configured
- Files: `upstream/settings/prod.py` lines 102-123, 132, 146
- Impact: Each Gunicorn worker maintains its own connection that gets recycled every 60 seconds, creating connection churn. At scale (>100 req/min), database overhead increases significantly. PgBouncer recommended but not implemented.
- Fix approach:
  - For MVP (single worker): Keep 60s
  - For scaling: Implement PgBouncer in transaction mode, increase max_connections to match pooling strategy
  - Add connection pool health checks
  - Monitor connection reuse metrics

## Known Bugs

**Tenant Isolation Bypass Risk in CustomerScopedManager:**
- Symptoms: Superusers and background tasks can access unscoped data via `.unscoped()` method without explicit authorization checks
- Files:
  - `upstream/core/tenant.py` lines 135-142 (unscoped method)
  - `upstream/api/views.py` lines 80-99 (superuser check)
  - `upstream/views/__init__.py` lines 45-50, 62-65 (bypassing with all_objects)
- Trigger: Any call to `.unscoped()` or `.all_objects` without customer context set, or superuser accessing API without explicit customer parameter
- Workaround: Currently relies on permission checks being enforced at view layer, but tenant isolation can be breached if view permissions are not properly validated
- Fix approach:
  - Add audit logging for all unscoped access
  - Require explicit customer ID parameter in unscoped queries
  - Add tests for tenant isolation enforcement
  - Consider role-based access control instead of just superuser flag

**Silent Failures in Alert Evaluation:**
- Symptoms: Alert evaluation can return None for multiple edge cases without logging why
- Files: `upstream/alerts/services.py` lines 43-130 (evaluate_drift_event), multiple return None statements
- Trigger: When AlertRule.evaluate() fails, when no rules match, when drift_event is in invalid state
- Impact: Background tasks can silently skip alerting without visibility into why, creating missed notifications
- Fix approach:
  - Replace `return None` with explicit error results that include reason
  - Add mandatory logging for all evaluation paths
  - Track metrics for skipped/filtered evaluations
  - Add integration tests that verify logging occurs

**Incomplete TODO Comments in Backup Schema:**
- Symptoms: Legacy backup code still has incomplete implementations
- Files: `backup_payrixa_20260124_085129/payrixa/api/views.py` lines 248, 387, 557
- Trigger: Using old payrixa backup code as reference
- Impact: If backup code is ever restored/used, async tasks won't execute properly, trend data won't compute
- Fix approach: Either fully complete backup code or delete if not needed. Add code review checklist for TODOs before shipping

## Security Considerations

**DEBUG Mode Check Inconsistency:**
- Risk: Multiple settings files check `settings.DEBUG`, but no enforcement that DEBUG=False in production
- Files: `upstream/settings/prod.py` line 31, `upstream/monitoring_checks.py` line 127
- Current mitigation: Production checklist in docs, validation script at deploy time
- Recommendations:
  - Add pre-deployment validation that fails the build if DEBUG=True
  - Use Django's system check framework to enforce DEBUG=False on startup
  - Add encrypted secret key validation in monitoring_checks.py

**Broad Exception Handling in Monitoring Checks:**
- Risk: Multiple except Exception blocks that catch and suppress all errors
- Files: `upstream/monitoring_checks.py` lines 98, 127, 145, 239
- Current mitigation: Errors are logged, but broad exception handling could mask real issues
- Recommendations:
  - Catch specific exception types (ImportError, ConnectionError, etc.)
  - Re-raise unexpected exceptions
  - Log the actual exception type and traceback

**PHI Detection Hardcoded Names:**
- Risk: PHI validation uses hardcoded list of common names - list is finite and can be bypassed
- Files: `upstream/views/__init__.py` lines 73-100+
- Current mitigation: Part of multi-layer validation, not sole PHI protection
- Recommendations:
  - Document that this is best-effort validation, not guaranteed
  - Consider using industry-standard patterns (SSN masking, date patterns)
  - Add option for organizations to provide additional sensitive keywords
  - Log all PHI detections to audit trail

**Field Encryption Optional in MVP:**
- Risk: REAL_DATA_MODE allows production with unencrypted PHI when FIELD_ENCRYPTION_KEY not set
- Files: `upstream/settings/prod.py` lines 66-99
- Current mitigation: Enforced via settings validation only
- Recommendations:
  - Add database-level encryption (transparent data encryption)
  - Enforce encrypted fields at model level for HIPAA fields
  - Add warning logs if REAL_DATA_MODE=True but encryption not enabled
  - Consider making encryption non-optional for production

## Performance Bottlenecks

**Query Optimization Relies on Manual Prefetch:**
- Problem: Multiple viewsets and services require explicit select_related/prefetch_related calls
- Files:
  - `upstream/api/views.py` lines 642-646 (AlertEventViewSet)
  - `upstream/views/__init__.py` lines 13-20 (dashboard queries)
  - `upstream/products/delayguard/views.py` (prefetch calls)
- Cause: CustomerScopedManager bypasses standard Django ORM optimization, requires manual query optimization
- Improvement path:
  - Create base ViewSet class that automatically applies default prefetch_related
  - Build query optimization test that catches missing prefetch in list/retrieve operations
  - Document prefetch requirements in API documentation

**Large Initial Migration File:**
- Problem: `upstream/migrations/0001_initial.py` is 4,771 lines - extremely large for initial migration
- Files: `upstream/migrations/0001_initial.py`
- Cause: All models created in single migration instead of logical groups
- Impact: First time setup is slow, harder to review, difficult to recover from if partial application
- Improvement path:
  - For new projects: Break initial schema into 3-5 migrations by domain (auth, core, products, alerts)
  - Current state: Keep as-is (safer than trying to split existing migration)
  - For future: Create new migration files for new features

**Data Quality Validation Loads All Rules Without Filtering:**
- Problem: validate_upload loads ALL enabled rules for every row, including ones that don't apply
- Files: `upstream/core/data_quality_service.py` lines 46-51
- Cause: No rule pre-filtering by context (e.g., only rules for this payer)
- Impact: Validation scales poorly with number of rules and rows (O(rows × rules))
- Improvement path:
  - Add rule applicability filtering: `filter(applies_to_payer=payer)`, `filter(applies_to_cpt=cpt_code)`
  - Cache filtered rule sets per customer+context
  - Add performance test for validation with 1000+ rows and 100+ rules

## Fragile Areas

**Tenant Isolation at Middleware Layer:**
- Files: `upstream/core/tenant.py` lines 145-179
- Why fragile:
  - Uses thread-local storage which can leak across requests in async contexts
  - Superuser check at middleware level can be bypassed if authentication middleware fails
  - Background tasks must manually set customer context - easy to forget
  - No automatic cleanup if view raises exception (relies on finally block)
- Safe modification:
  - Always wrap background tasks with customer_context() context manager
  - Never cache current_customer() result - call it fresh each time
  - Add tests that verify context clears even on exception
  - Consider moving to request-scoped storage for async compatibility
- Test coverage: `upstream/tests_tenant_isolation.py` exists but coverage gaps in background task scenarios

**Alert Suppression Logic Complex and Brittle:**
- Files: `upstream/alerts/services.py` lines 43-130
- Why fragile:
  - Multiple overlapping suppression strategies (cooldown, noise window, feedback)
  - Suppression rules embedded in evaluate() logic, not centralized
  - No explicit suppression decision logging
  - Dependencies on timezone.now() make testing difficult
- Safe modification:
  - Extract suppression logic to separate class with testable methods
  - Add suppression_reason to AlertEvent model
  - Make timezone handling injectable for testing
  - Document all suppression rules in single place
- Test coverage: Partial coverage in alerts/tests_services.py, missing edge cases

**Data Quality Service Validation Results Not Atomic:**
- Files: `upstream/core/data_quality_service.py` lines 34-100
- Why fragile:
  - Creates ValidationResult records inside loop per row - could partially fail
  - Exception during validation leaves incomplete results in database
  - No rollback of previously created records
  - Query for existing rules happens once - rules can't be updated mid-validation
- Safe modification:
  - Wrap entire validation in transaction.atomic() (currently only on method, not per-row)
  - Collect all errors first, then batch create in single bulk_create()
  - Add validation state machine to track progress (pending → validating → complete → committed)
- Test coverage: Good in core/tests_data_quality.py, but missing failure scenario tests

**Encrypted Fields Configuration Optional:**
- Files: `upstream/settings/prod.py` lines 66-99
- Why fragile:
  - REAL_DATA_MODE = False by default, but code assumes it can be enabled without additional setup
  - encrypted_model_fields library may not handle all field types
  - Migration from unencrypted to encrypted requires data re-encryption (not implemented)
- Safe modification:
  - Add pre-startup check that encrypted fields are actually encrypted in database
  - Provide encryption key rotation script
  - Add warning if REAL_DATA_MODE = True and any sensitive fields are unencrypted
  - Document encryption key backup procedures
- Test coverage: No explicit tests for encryption in test.py

## Scaling Limits

**Memory-Only Cache in Development Breaks Multi-Process:**
- Current capacity: Single process only (suitable for development)
- Limit: Any multi-process deployment (Gunicorn workers) breaks cache coherency
- Cause: LocMemCache is per-process, not shared
- Scaling path:
  - Require Redis in all environments except single-worker dev
  - Add health check that detects memory cache in production and warns
  - Consider implementing cache warmup for payer/CPT mappings at startup

**Single Redis Instance Not Suitable for High Availability:**
- Current capacity: Single Redis instance handles cache + Celery broker + result backend
- Limit: Redis failure causes complete application degradation (no caching, no task queue)
- Scaling path:
  - Separate Redis instances: one for cache, one for Celery (different failure domains)
  - Implement Redis Sentinel for high availability
  - Add failover monitoring and alerts

**CustomerScopedManager Query Filtering at Python Level:**
- Current capacity: Works fine for <1000 customers with moderate query load
- Limit: Each query must add customer filter after execution, not in SQL WHERE clause optimization
- Cause: Thread-local context added at QuerySet level, not SQL generation level
- Scaling path:
  - Consider explicit customer_id parameter in all queries (easier to optimize)
  - Profile queries to identify N+1 problems at scale
  - If scaling beyond 10,000 customers: migrate to explicit partitioning by customer_id

**Large Upload File Handling:**
- Current capacity: 10 MB limit set in DATA_UPLOAD_MAX_MEMORY_SIZE
- Limit: Entire file loaded into memory for processing - 10 MB × num_workers = potential memory exhaustion
- Scaling path:
  - Implement streaming CSV parsing (chunked reads)
  - Add file upload to object storage (S3) with background processing
  - Implement row-at-a-time processing instead of loading full file

## Dependencies at Risk

**Django 5.2 with Uncertain LTS Status:**
- Risk: Django 5.2 is a minor release, uncertain long-term support
- Files: `setup.py` or `requirements.txt` (if present - not found)
- Impact: May need to upgrade to 5.3+ or 6.0 within 12-18 months
- Migration plan:
  - Track Django release schedule
  - Plan upgrade path before LTS deadline
  - Add Django upgrade tests to CI pipeline

**auditlog Package Unmaintained Variants:**
- Risk: Multiple versions of django-auditlog exist, some unmaintained
- Files: `upstream/settings/base.py` line 29 (installed_apps)
- Current mitigation: Using maintained version, but need to monitor
- Migration plan:
  - Document which auditlog version is used
  - Set up dependency update alerts
  - Have alternative audit implementations ready if needed

**encrypted_model_fields Has Limited Field Type Support:**
- Risk: Not all Django field types are supported for encryption
- Files: `upstream/settings/base.py` line 30 (installed_apps)
- Impact: JSONField and custom fields may not encrypt properly
- Mitigation:
  - Only use encrypted fields for standard types (CharField, DateField, DecimalField)
  - Test any custom field types before using them encrypted
  - Add validation in model that checks encrypted fields are supported

## Missing Critical Features

**No Database Transaction Logging for Audit:**
- Problem: Changes to sensitive data (customer settings, alert rules) are not logged to database
- Blocks: Cannot prove who changed what and when for compliance
- Impact: Audit trail exists for API but not for admin changes
- Fix:
  - Configure auditlog to track changes to Settings, AlertRule, PayerMapping models
  - Add audit middleware that logs all write operations
  - Integrate with AuditlogMiddleware already in MIDDLEWARE

**No Rate Limiting on API Endpoints:**
- Problem: API endpoints defined but no rate limiting
- Blocks: Cannot protect against brute force, resource exhaustion
- Files: `upstream/api/views.py` lines 29-34 define throttling classes but not all endpoints use them
- Impact: Large customers could accidentally DOS their own system
- Fix:
  - Apply default throttle to all ViewSets (class-level attribute)
  - Add stricter throttles to sensitive endpoints (token auth, report generation)
  - Add per-customer quota limits based on service tier

**No Graceful Degradation for Celery Disabled:**
- Problem: Some features may require Celery but code doesn't check CELERY_ENABLED
- Files: `upstream/settings/base.py` line 323
- Impact: If Celery is disabled and code calls async task, it will fail
- Fix:
  - Create task_enabled() check function
  - Wrap all celery.apply_async() with feature check
  - Provide synchronous fallback or clear error if feature requires Celery

## Test Coverage Gaps

**Tenant Isolation in Background Tasks:**
- Untested area: Background task execution with customer context isolation
- Files: `upstream/celery_monitoring.py`, `upstream/alerts/services.py` - evaluate_drift_event
- Risk: Tasks may process data for wrong customer due to missing context setup
- Priority: High - security-critical
- Add tests for:
  - Task execution with explicit customer_context()
  - Cleanup of customer context between tasks
  - Superuser override not leaking to next task

**API Throttling Implementation:**
- Untested area: ReportGenerationThrottle, BulkOperationThrottle, ReadOnlyThrottle defined but not applied
- Files: `upstream/api/throttling.py` (if exists) or not implemented
- Risk: Throttle classes exist but endpoints may not use them
- Priority: High - DoS risk
- Add tests for:
  - Throttling applied to heavy endpoints
  - Per-customer limits enforced
  - Throttle headers returned correctly

**Data Quality Service Edge Cases:**
- Untested area: Validation with empty uploads, special characters, boundary values
- Files: `upstream/core/data_quality_service.py` validate_upload method
- Risk: Validation might fail silently on edge cases
- Priority: Medium - data quality issue
- Add tests for:
  - Empty file (0 rows)
  - Very large file (1M+ rows)
  - Special characters in field values
  - NULL/empty field handling
  - Exception recovery (partial failure)

**Cache Invalidation Strategy:**
- Untested area: Cache invalidation when data changes
- Files: Multiple uses of cache.get_or_set() without clear invalidation
- Risk: Stale payer/CPT mappings served to users, drift event cache out of sync
- Priority: Medium - consistency issue
- Add tests for:
  - Cache invalidation on PayerMapping.save()
  - Cache invalidation on AlertRule state change
  - Cache consistency across processes (if multi-process)

**Error Handling in API Views:**
- Untested area: Exception handling in feedback(), dashboard() action methods
- Files: `upstream/api/views.py` lines 651-710+
- Risk: Unexpected exceptions not handled, may leak sensitive info
- Priority: Medium - reliability + security
- Add tests for:
  - AlertEvent not found (404)
  - Invalid feedback data (400)
  - Database errors during judgment creation (500)
  - Permission denied (403)

---

*Concerns audit: 2026-01-26*
