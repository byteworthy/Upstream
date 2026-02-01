---
phase: quick-006
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - upstream/models.py
  - upstream/migrations/0XXX_add_covering_indexes.py
autonomous: true

must_haves:
  truths:
    - "Database queries filtering by customer + date + outcome/severity/status retrieve all needed columns without additional lookups"
    - "Index-only scans possible for common query patterns"
    - "Query planner chooses covering indexes for filtered list views"
  artifacts:
    - path: "upstream/models.py"
      provides: "Covering index definitions on ClaimRecord, DriftEvent, Upload"
      contains: "models.Index"
    - path: "upstream/migrations/0XXX_add_covering_indexes.py"
      provides: "Migration to create covering indexes"
      exports: ["Migration"]
  key_links:
    - from: "upstream/models.py"
      to: "PostgreSQL indexes"
      via: "Django migration system"
      pattern: "models\\.Index.*fields=\\["
---

<objective>
Add covering indexes to optimize common query patterns for ClaimRecord, DriftEvent, and Upload models.

Purpose: Reduce database round-trips by enabling index-only scans for frequently filtered list views (customer scoped queries with date ordering and status/outcome/severity filters).

Output: Migration file adding three covering composite indexes
</objective>

<execution_context>
@/home/codespace/.claude/get-shit-done/workflows/execute-plan.md
@/home/codespace/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@upstream/models.py

## Background

This is a quick optimization task to add covering indexes for three models that have frequent customer-scoped queries with date ordering and status filtering:

1. **ClaimRecord**: Queries filter by customer + outcome + decided_date
2. **DriftEvent**: Queries filter by customer + created_at + severity
3. **Upload**: Queries filter by customer + uploaded_at + status

Covering indexes include all columns needed by the query, allowing index-only scans without table lookups.

## Existing Index Analysis

**ClaimRecord** currently has:
- `claim_cust_decdate_idx` on (customer, decided_date)
- `claim_cust_outcome_idx` on (customer, outcome, decided_date)
- But outcome is in position 2, not optimal for queries that filter by customer + decided_date first, then outcome

**DriftEvent** currently has:
- `drift_cust_created_idx` on (customer, -created_at)
- `drift_cust_type_date_idx` on (customer, drift_type, -created_at)
- No index including severity for common dashboard queries

**Upload** currently has:
- `upload_cust_date_idx` on (customer, uploaded_at)
- `upload_cust_status_idx` on (customer, status)
- These are separate - not a covering index

## Note on DriftEvent Field

The task description mentions `detected_at` but the model uses `created_at` (line 669 in models.py). We'll use `created_at` which is the actual timestamp field.
</context>

<tasks>

<task type="auto">
  <name>Add covering indexes to models and generate migration</name>
  <files>
    upstream/models.py
    upstream/migrations/0XXX_add_covering_indexes.py
  </files>
  <action>
Add three covering composite indexes to optimize common query patterns:

1. **ClaimRecord** - Add covering index for customer + decided_date + outcome queries:
   ```python
   models.Index(
       fields=["customer", "-decided_date", "outcome"],
       name="claim_cust_date_outcome_cov"
   )
   ```
   This enables index-only scans for queries filtering by customer, ordering by decided_date DESC, and selecting by outcome. Column order: customer (equality filter) -> decided_date (range/order) -> outcome (included for covering).

2. **DriftEvent** - Add covering index for customer + created_at + severity queries:
   ```python
   models.Index(
       fields=["customer", "-created_at", "severity"],
       name="drift_cust_date_sev_cov"
   )
   ```
   This enables index-only scans for dashboard queries filtering by customer, ordering by created_at DESC, with severity for display. Used in drift feed queries.

3. **Upload** - Add covering index for customer + uploaded_at + status queries:
   ```python
   models.Index(
       fields=["customer", "-uploaded_at", "status"],
       name="upload_cust_date_status_cov"
   )
   ```
   This enables index-only scans for upload list views filtering by customer, ordering by upload date DESC, and displaying status.

Add these indexes to the existing `indexes = [...]` arrays in each model's Meta class. Place them after existing indexes for clarity.

After updating models.py, generate the migration:
```bash
cd /workspaces/codespaces-django
source .venv/bin/activate
python manage.py makemigrations upstream -n add_covering_indexes
```

The migration will add all three indexes in a single migration file.

**Why these column orders:**
- Customer first: All queries are tenant-scoped (CustomerScopedManager)
- Date second with DESC: Primary ordering for list views
- Status/outcome/severity last: Filtering or display columns included for covering
- Descending order (-field) matches typical "newest first" UI patterns
  </action>
  <verify>
Verify indexes added to models:
```bash
grep -A 2 "claim_cust_date_outcome_cov\|drift_cust_date_sev_cov\|upload_cust_date_status_cov" /workspaces/codespaces-django/upstream/models.py
```

Verify migration created:
```bash
ls -la /workspaces/codespaces-django/upstream/migrations/*_add_covering_indexes.py
cat /workspaces/codespaces-django/upstream/migrations/*_add_covering_indexes.py | head -50
```

Check migration has AddIndex operations for all three models:
```bash
grep -c "AddIndex" /workspaces/codespaces-django/upstream/migrations/*_add_covering_indexes.py
```
(Should output: 3)
  </verify>
  <done>
- Three covering indexes added to ClaimRecord.Meta.indexes, DriftEvent.Meta.indexes, Upload.Meta.indexes
- Migration file created with AddIndex operations for all three indexes
- Index names follow Django naming pattern: {model}_{fields}_cov suffix
- Column ordering optimized: customer (filter) -> date DESC (order) -> status field (covering)
  </done>
</task>

<task type="auto">
  <name>Apply migration and verify index creation</name>
  <files>
    N/A (database operation)
  </files>
  <action>
Apply the migration to create the indexes in the database:

```bash
cd /workspaces/codespaces-django
source .venv/bin/activate
python manage.py migrate upstream
```

After migration completes, verify indexes exist in PostgreSQL by inspecting the database schema. Use Django dbshell to check:

```bash
python manage.py dbshell <<EOF
-- Check ClaimRecord covering index
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'upstream_claimrecord'
  AND indexname = 'claim_cust_date_outcome_cov';

-- Check DriftEvent covering index
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'upstream_driftevent'
  AND indexname = 'drift_cust_date_sev_cov';

-- Check Upload covering index
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'upstream_upload'
  AND indexname = 'upload_cust_date_status_cov';
EOF
```

**Why this matters:** Covering indexes reduce query time by allowing index-only scans. PostgreSQL can answer queries entirely from the index without accessing the table, significantly improving performance for filtered list views.
  </action>
  <verify>
Verify migration applied:
```bash
python manage.py showmigrations upstream | grep add_covering_indexes
```
(Should show [X] indicating migration applied)

Verify all three indexes created by checking PostgreSQL catalog:
```bash
python manage.py dbshell -c "SELECT COUNT(*) FROM pg_indexes WHERE indexname IN ('claim_cust_date_outcome_cov', 'drift_cust_date_sev_cov', 'upload_cust_date_status_cov');"
```
(Should output: 3)

Test that query planner can use the indexes with EXPLAIN:
```bash
python manage.py shell <<EOF
from upstream.models import ClaimRecord, DriftEvent, Upload, Customer
from django.db import connection

# Get a customer ID for testing
customer = Customer.objects.first()
if customer:
    # Test ClaimRecord covering index
    with connection.cursor() as cursor:
        cursor.execute("EXPLAIN SELECT id, customer_id, decided_date, outcome FROM upstream_claimrecord WHERE customer_id = %s ORDER BY decided_date DESC LIMIT 10", [customer.id])
        print("ClaimRecord query plan:")
        for row in cursor.fetchall():
            print(row[0])

    # Test DriftEvent covering index
    with connection.cursor() as cursor:
        cursor.execute("EXPLAIN SELECT id, customer_id, created_at, severity FROM upstream_driftevent WHERE customer_id = %s ORDER BY created_at DESC LIMIT 10", [customer.id])
        print("\nDriftEvent query plan:")
        for row in cursor.fetchall():
            print(row[0])

    # Test Upload covering index
    with connection.cursor() as cursor:
        cursor.execute("EXPLAIN SELECT id, customer_id, uploaded_at, status FROM upstream_upload WHERE customer_id = %s ORDER BY uploaded_at DESC LIMIT 10", [customer.id])
        print("\nUpload query plan:")
        for row in cursor.fetchall():
            print(row[0])
else:
    print("No customer found - create test data first")
EOF
```
  </verify>
  <done>
- Migration applied successfully (showmigrations shows [X])
- All three covering indexes created in PostgreSQL
- Query planner recognizes and can use the new indexes for common query patterns
- Database ready to serve index-only scans for customer-scoped list views with date ordering and status filtering
  </done>
</task>

</tasks>

<verification>
Final verification checklist:

1. **Model definitions updated:**
   - ClaimRecord.Meta.indexes includes claim_cust_date_outcome_cov
   - DriftEvent.Meta.indexes includes drift_cust_date_sev_cov
   - Upload.Meta.indexes includes upload_cust_date_status_cov

2. **Migration generated and applied:**
   - Migration file exists: upstream/migrations/*_add_covering_indexes.py
   - Migration shows [X] in showmigrations output
   - Three AddIndex operations in migration

3. **Database indexes created:**
   - `SELECT COUNT(*) FROM pg_indexes WHERE indexname IN (...)` returns 3
   - Each index definition matches expected column order

4. **Query planner usage:**
   - EXPLAIN output for ClaimRecord query shows index scan on claim_cust_date_outcome_cov
   - EXPLAIN output for DriftEvent query shows index scan on drift_cust_date_sev_cov
   - EXPLAIN output for Upload query shows index scan on upload_cust_date_status_cov
</verification>

<success_criteria>
- Three covering composite indexes added to models.py
- Migration generated with AddIndex operations for all three models
- Migration applied successfully to database
- PostgreSQL catalog confirms all three indexes exist with correct column definitions
- Query planner can use covering indexes for common customer-scoped list view queries
- No breaking changes to existing functionality (indexes are additive optimization)
</success_criteria>

<output>
After completion, create `.planning/quick/006-add-covering-indexes-for-query-optimiza/006-SUMMARY.md`
</output>
