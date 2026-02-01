---
phase: quick-003
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - upstream/models.py
  - upstream/products/denialscope/advanced_models.py
  - upstream/products/delayguard/models.py
autonomous: true

must_haves:
  truths:
    - "Invalid enum values for Upload.status are rejected at database level"
    - "Confidence scores outside 0-1 range are rejected at database level"
    - "Database enforces data integrity rules without relying on application code"
  artifacts:
    - path: "upstream/models.py"
      provides: "Upload.status CHECK constraint"
      contains: "CheckConstraint.*status.*in"
    - path: "upstream/products/denialscope/advanced_models.py"
      provides: "CHECK constraints for confidence scores in DenialCluster, DenialCascade, PreDenialWarning"
      contains: "CheckConstraint.*confidence"
    - path: "upstream/products/delayguard/models.py"
      provides: "CHECK constraint for PaymentDelaySignal.confidence"
      contains: "CheckConstraint.*confidence"
  key_links:
    - from: "Model Meta.constraints"
      to: "Database schema"
      via: "Django migration system"
      pattern: "CheckConstraint"
---

<objective>
Add database-level CHECK constraints for data integrity validation across Upload status enums and confidence score fields.

Purpose: Enforce data integrity at the database level as defense-in-depth beyond Django validators, preventing invalid data from being inserted via raw SQL, bulk operations, or external tools.

Output: CHECK constraints on Upload.status enum validation and confidence_score fields (0-1 range) across multiple models, plus migration file.
</objective>

<execution_context>
@/home/codespace/.claude/get-shit-done/workflows/execute-plan.md
@/home/codespace/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@upstream/models.py
@upstream/products/denialscope/advanced_models.py
@upstream/products/delayguard/models.py

## Current State

Phases 1, 2, 4, 5 complete. Phase 3 (OpenAPI Documentation & Error Standardization) in progress.

**Existing CHECK constraints:**
- ClaimRecord: amount fields (allowed_amount, billed_amount, paid_amount >= 0), data_quality_score (0-1), dates logical order
- DriftEvent: severity (0-1), confidence (0-1), statistical_significance (0-1) - ALREADY COMPLETE
- Upload: row counts >= 0, date_min <= date_max
- DataQualityReport: all count fields >= 0, accepted/rejected <= total

**Missing CHECK constraints:**
- Upload.status: Should validate against STATUS_CHOICES enum values
- DenialCluster.cluster_confidence: Has validators, needs DB constraint
- DenialCascade.confidence_score: Has validators, needs DB constraint
- PreDenialWarning.confidence_score: Has validators, needs DB constraint
- PreDenialWarning.denial_probability: Has validators, needs DB constraint
- PaymentDelaySignal.confidence: Has validators, needs DB constraint

**Note:** ClaimRecord amount fields and DriftEvent severity/confidence already have CHECK constraints. This task focuses on the remaining gaps.
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add CHECK constraints to models</name>
  <files>
    upstream/models.py
    upstream/products/denialscope/advanced_models.py
    upstream/products/delayguard/models.py
  </files>
  <action>
Add CHECK constraints to model Meta.constraints sections:

**upstream/models.py - Upload model:**
Add to existing constraints list:
```python
models.CheckConstraint(
    check=models.Q(status__in=['processing', 'success', 'failed', 'partial']),
    name='upload_status_valid',
),
```

**upstream/products/denialscope/advanced_models.py:**

For DenialCluster model, add constraints section to Meta:
```python
constraints = [
    models.CheckConstraint(
        check=models.Q(cluster_confidence__gte=0.0) & models.Q(cluster_confidence__lte=1.0),
        name='denialcluster_confidence_range',
    ),
]
```

For DenialCascade model, add constraints section to Meta:
```python
constraints = [
    models.CheckConstraint(
        check=models.Q(confidence_score__gte=0.0) & models.Q(confidence_score__lte=1.0),
        name='denialcascade_confidence_range',
    ),
]
```

For PreDenialWarning model, add constraints section to Meta:
```python
constraints = [
    models.CheckConstraint(
        check=models.Q(denial_probability__gte=0.0) & models.Q(denial_probability__lte=1.0),
        name='predenialwarning_probability_range',
    ),
    models.CheckConstraint(
        check=models.Q(confidence_score__gte=0.0) & models.Q(confidence_score__lte=1.0),
        name='predenialwarning_confidence_range',
    ),
]
```

**upstream/products/delayguard/models.py:**

For PaymentDelaySignal model, add to existing constraints list (after unique constraint):
```python
models.CheckConstraint(
    check=models.Q(confidence__gte=0.0) & models.Q(confidence__lte=1.0),
    name='paymentdelaysignal_confidence_range',
),
```

Place constraints immediately after indexes in each Meta class. Follow existing constraint patterns in the codebase (use & for AND, | for OR).
  </action>
  <verify>
```bash
# Verify constraints added to all models
grep -n "upload_status_valid" upstream/models.py
grep -n "denialcluster_confidence_range" upstream/products/denialscope/advanced_models.py
grep -n "denialcascade_confidence_range" upstream/products/denialscope/advanced_models.py
grep -n "predenialwarning.*_range" upstream/products/denialscope/advanced_models.py
grep -n "paymentdelaysignal_confidence_range" upstream/products/delayguard/models.py

# Verify constraint syntax is valid
python manage.py check
```
  </verify>
  <done>
All 6 CHECK constraints added to model Meta classes, `python manage.py check` passes with no errors.
  </done>
</task>

<task type="auto">
  <name>Task 2: Generate and apply migration</name>
  <files>
    upstream/migrations/0019_*.py
  </files>
  <action>
Generate migration for the new CHECK constraints and apply it:

```bash
python manage.py makemigrations upstream -n "add_check_constraints_data_integrity"
python manage.py migrate upstream
```

Verify migration includes all 6 CHECK constraints:
- upload_status_valid
- denialcluster_confidence_range
- denialcascade_confidence_range
- predenialwarning_probability_range
- predenialwarning_confidence_range
- paymentdelaysignal_confidence_range

If migration includes any unrelated changes (e.g., from other modified models), this is expected - Django detects all model changes.
  </action>
  <verify>
```bash
# Verify migration created and applied
ls -la upstream/migrations/0019_*
python manage.py showmigrations upstream | tail -3

# Verify constraints exist in database (SQLite)
python manage.py dbshell <<EOF
.schema upstream_upload
.schema upstream_denialcluster
.schema upstream_denialcascade
.schema upstream_predenialwarning
.schema upstream_paymentdelaysignal
EOF

# Test constraint enforcement (should fail)
python manage.py shell <<EOF
from upstream.models import Upload, Customer
c = Customer.objects.first()
# Try invalid status - should raise IntegrityError
try:
    Upload.objects.create(customer=c, filename='test.csv', status='invalid')
    print("ERROR: Invalid status was allowed")
except Exception as e:
    print(f"PASS: Constraint enforced - {type(e).__name__}")
EOF
```
  </verify>
  <done>
Migration 0019 created and applied successfully, database schema includes all 6 CHECK constraints, test confirms Upload.status validation prevents invalid enum values at database level.
  </done>
</task>

<task type="auto">
  <name>Task 3: Validate existing data compatibility</name>
  <files></files>
  <action>
Verify that existing data in the database satisfies the new CHECK constraints:

```bash
python manage.py shell <<EOF
from upstream.models import Upload
from upstream.products.denialscope.advanced_models import DenialCluster, DenialCascade, PreDenialWarning
from upstream.products.delayguard.models import PaymentDelaySignal

# Check Upload status values
invalid_uploads = Upload.objects.exclude(status__in=['processing', 'success', 'failed', 'partial']).count()
print(f"Invalid Upload.status: {invalid_uploads}")

# Check confidence score ranges (if any records exist)
if DenialCluster.objects.exists():
    invalid_dc = DenialCluster.objects.filter(
        models.Q(cluster_confidence__lt=0.0) | models.Q(cluster_confidence__gt=1.0)
    ).count()
    print(f"Invalid DenialCluster.cluster_confidence: {invalid_dc}")

if DenialCascade.objects.exists():
    invalid_cascade = DenialCascade.objects.filter(
        models.Q(confidence_score__lt=0.0) | models.Q(confidence_score__gt=1.0)
    ).count()
    print(f"Invalid DenialCascade.confidence_score: {invalid_cascade}")

if PreDenialWarning.objects.exists():
    invalid_pdw = PreDenialWarning.objects.filter(
        models.Q(denial_probability__lt=0.0) | models.Q(denial_probability__gt=1.0) |
        models.Q(confidence_score__lt=0.0) | models.Q(confidence_score__gt=1.0)
    ).count()
    print(f"Invalid PreDenialWarning scores: {invalid_pdw}")

if PaymentDelaySignal.objects.exists():
    invalid_pds = PaymentDelaySignal.objects.filter(
        models.Q(confidence__lt=0.0) | models.Q(confidence__gt=1.0)
    ).count()
    print(f"Invalid PaymentDelaySignal.confidence: {invalid_pds}")

print("Data validation complete")
EOF
```

If any invalid data is found, it should be cleaned up before the constraints were added by the migration. Since we're adding constraints to existing validated fields, this is a verification step.
  </action>
  <verify>
```bash
# Verify validation script ran successfully
echo $?
```
  </verify>
  <done>
Data validation confirms no existing records violate the new CHECK constraints (or constraints were successfully applied with no conflicts).
  </done>
</task>

</tasks>

<verification>
1. All 6 CHECK constraints added to model files
2. Migration 0019 generated and applied
3. Database schema includes all constraints
4. Test confirms invalid Upload.status raises IntegrityError
5. Existing data validated (no constraint violations)
6. `python manage.py check` passes
</verification>

<success_criteria>
- Upload.status CHECK constraint prevents invalid enum values
- DenialCluster.cluster_confidence CHECK constraint enforces 0-1 range
- DenialCascade.confidence_score CHECK constraint enforces 0-1 range
- PreDenialWarning.denial_probability and confidence_score CHECK constraints enforce 0-1 range
- PaymentDelaySignal.confidence CHECK constraint enforces 0-1 range
- Migration applied successfully to database
- All constraints testable via intentional violation attempts
- No existing data violates new constraints
</success_criteria>

<output>
After completion, create `.planning/quick/003-add-database-check-constraints-for-data/003-SUMMARY.md`
</output>
