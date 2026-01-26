# Migration Safety Guide

**Last Updated**: 2026-01-26
**Status**: Production-Ready

---

## Overview

This guide documents Upstream's migration safety system, which prevents production downtime and data loss from unsafe database migrations.

## Why Migration Safety Matters

Database migrations in production can cause:
- **Downtime**: Destructive migrations lock tables or fail mid-execution
- **Data Loss**: Field/model deletions without proper data migration
- **Rollback Issues**: Irreversible changes that break rollback capability
- **HIPAA Violations**: Audit trail destruction from CASCADE deletes

## Automated Safety Checks

### What Gets Checked

1. **Uncommitted Migrations**
   - Detects model changes that haven't been turned into migration files
   - Prevents "Your models have changes not reflected in migrations" errors

2. **Migration Conflicts**
   - Identifies conflicting migrations from parallel development
   - Catches merge conflicts in migration dependency chains

3. **Migration Plan Validation**
   - Verifies migrations can be applied without errors
   - Shows exactly what will happen during deployment

4. **Dangerous Operations Detection**
   - Scans for field/model deletions
   - Flags operations requiring data migration
   - Warns about rename operations that may break foreign keys

5. **Deployment Readiness**
   - Runs Django's built-in `check --deploy` validation
   - Verifies security settings, DEBUG mode, etc.

### Where Checks Run

| Environment | Trigger | Strict Mode | Blocks Deploy? |
|-------------|---------|-------------|----------------|
| **Local Development** | Manual | Optional | No (warnings only) |
| **CI/CD (GitHub Actions)** | Every PR | ✓ Yes | ✓ Yes |
| **Cloud Build (GCP)** | Production deploy | ✓ Yes | ✓ Yes |
| **Pre-commit Hook** | Git commit | No | No (warnings only) |

---

## Usage

### Local Validation (Before Commit)

```bash
# Basic check (allows warnings)
python scripts/validate_migrations.py

# Strict mode (blocks on warnings)
python scripts/validate_migrations.py --strict
```

**Output Example**:
```
======================================================================
Migration Safety Validation
======================================================================

🔍 Checking for uncommitted migrations...
✓ No uncommitted migrations found
🔍 Checking for migration conflicts...
✓ No migration conflicts found
🔍 Verifying migration plan...
✓ Migration plan is valid

Pending migrations:
Planned operations:
upstream.0003_add_performance_indexes
  → Create index idx_claim_payer_outcome (fields: payer, outcome)
  → Create index idx_drift_computed (fields: customer, computed_date)

🔍 Scanning for dangerous operations...
⚠ Potentially dangerous operations detected:

  • 0003_remove_old_field.py: RemoveField - Field removal (potential data loss)

Recommendation: Review these migrations carefully and ensure:
  1. Data migration scripts are in place if needed
  2. Backups are created before deployment
  3. Changes are tested in staging environment

🔍 Running deployment checks...
✓ Deployment checks passed

======================================================================
Summary
======================================================================

Checks Passed: 4
Warnings: 1

⚠ DEPLOYMENT ALLOWED WITH CAUTION:
Warnings detected. Review before deploying to production.
```

### CI/CD Integration

#### GitHub Actions (Automatic)

Migration safety checks run automatically on:
- Pull requests to `main` or `develop`
- Tagged releases (`v*`)
- Manual deployments via workflow_dispatch

**Workflow File**: `.github/workflows/deploy.yml`

```yaml
- name: Check migration safety
  run: |
    python scripts/validate_migrations.py --strict
  env:
    SECRET_KEY: ci-test-secret-key
    DEBUG: 'False'
```

#### Google Cloud Build (Automatic)

Cloud Build validates migrations before deploying to Cloud Run.

**Build File**: `cloudbuild.yaml`

```yaml
# Step 4: Migration safety checks
- name: 'gcr.io/$PROJECT_ID/upstream:$BUILD_ID'
  entrypoint: 'python'
  args:
    - 'manage.py'
    - 'makemigrations'
    - '--check'
    - '--dry-run'
    - '--noinput'
```

---

## Common Scenarios

### Scenario 1: Adding a New Field

**Safe Migration**:
```python
class Migration(migrations.Migration):
    operations = [
        migrations.AddField(
            model_name='claimrecord',
            name='denial_reason',
            field=models.CharField(max_length=500, blank=True, default=''),
        ),
    ]
```

**Why Safe**:
- Uses `blank=True` and `default=''` (no NOT NULL constraint issues)
- Additive change (doesn't break existing code)
- Reversible (can be rolled back)

**Validation Result**: ✓ Pass

---

### Scenario 2: Removing a Field (DANGEROUS)

**Dangerous Migration**:
```python
class Migration(migrations.Migration):
    operations = [
        migrations.RemoveField(
            model_name='claimrecord',
            name='legacy_status',
        ),
    ]
```

**Why Dangerous**:
- **Data Loss**: Field data is permanently deleted
- **Irreversible**: Cannot be rolled back
- **Code Break Risk**: If any code still references this field

**Validation Result**: ⚠ Warning - "Field removal (potential data loss)"

**Best Practice**:
1. Deploy code that stops writing to the field
2. Monitor for 1+ week to ensure no errors
3. Create data migration to archive the data if needed
4. Then deploy the RemoveField migration

---

### Scenario 3: Renaming a Field

**Risky Migration**:
```python
class Migration(migrations.Migration):
    operations = [
        migrations.RenameField(
            model_name='claimrecord',
            old_name='payer_name',
            new_name='payer',
        ),
    ]
```

**Why Risky**:
- Django generates SQL `ALTER TABLE RENAME COLUMN`
- If foreign keys exist, they may break
- Old code still using `payer_name` will fail

**Validation Result**: ⚠ Warning - "Field rename (verify data migration)"

**Best Practice**:
1. Use a 3-step migration:
   - Add new field `payer` with data migration from `payer_name`
   - Deploy code using `payer`
   - Remove `payer_name` in a later migration

---

### Scenario 4: Adding a Non-Nullable Field

**DANGEROUS (Will Fail)**:
```python
class Migration(migrations.Migration):
    operations = [
        migrations.AddField(
            model_name='claimrecord',
            name='required_field',
            field=models.CharField(max_length=100),  # ❌ No default!
        ),
    ]
```

**Why This Fails**:
- Existing rows don't have a value for `required_field`
- Database rejects the migration

**Validation Result**: ✗ Error - Migration will fail on existing data

**Fix**:
```python
# Option 1: Add with default
field=models.CharField(max_length=100, default='UNKNOWN')

# Option 2: Two-step migration
# Step 1: Add as nullable
field=models.CharField(max_length=100, null=True)
# Step 2: Populate via data migration
# Step 3: Alter to NOT NULL (separate migration)
```

---

## Dangerous Operations Reference

| Operation | Risk Level | Data Loss? | Description |
|-----------|------------|------------|-------------|
| `AddField` (nullable) | ✓ Safe | No | Adds optional field |
| `AddField` (non-null, no default) | ✗ CRITICAL | No | **Will fail** on existing rows |
| `RemoveField` | ⚠ HIGH | **Yes** | Permanent data deletion |
| `DeleteModel` | ⚠ CRITICAL | **Yes** | Deletes entire table |
| `RenameField` | ⚠ MEDIUM | No | Can break foreign keys |
| `RenameModel` | ⚠ MEDIUM | No | Renames table, breaks FKs |
| `AlterField` (type change) | ⚠ HIGH | Possible | May fail on incompatible data |
| `AlterField` (add constraint) | ⚠ MEDIUM | No | Can fail if data violates constraint |

---

## Pre-Deployment Checklist

Before deploying migrations to production:

- [ ] Run `python scripts/validate_migrations.py --strict`
- [ ] Review all pending migrations in `showmigrations --plan`
- [ ] Test migrations on a staging database with production-like data
- [ ] Create database backup (automated in Cloud Build)
- [ ] Verify no dangerous operations without data migration
- [ ] Check that migrations are reversible (if rollback is needed)
- [ ] Confirm no uncommitted model changes
- [ ] Ensure migration dependencies are correct

---

## Emergency Rollback Procedure

If a migration causes production issues:

### 1. Quick Rollback (If Migration is Reversible)

```bash
# Find the last good migration
python manage.py showmigrations upstream

# Roll back to it
python manage.py migrate upstream 0002_previous_good_migration
```

### 2. Code Rollback (If Migration is Irreversible)

```bash
# Roll back the code deployment (Cloud Run)
gcloud run services update-traffic upstream-staging \
  --to-revisions=upstream-staging-00042-abc=100

# Restore database from backup (if data loss occurred)
gcloud sql backups restore BACKUP_ID \
  --backup-instance=upstream-prod \
  --restore-instance=upstream-prod
```

---

## Best Practices

### 1. Always Use Reversible Migrations

- Avoid `RunPython` without `reverse_code`
- Avoid `RunSQL` without reverse SQL
- Test rollback before deploying

### 2. Split Large Migrations

Instead of:
```python
# ❌ Single migration with 10 operations
```

Do:
```python
# ✓ Multiple smaller migrations
# 0003_add_indexes.py
# 0004_add_fields.py
# 0005_data_migration.py
```

### 3. Use Data Migrations for Complex Changes

```python
from django.db import migrations

def populate_new_field(apps, schema_editor):
    ClaimRecord = apps.get_model('upstream', 'ClaimRecord')
    for record in ClaimRecord.objects.all():
        record.new_field = calculate_value(record)
        record.save()

class Migration(migrations.Migration):
    operations = [
        migrations.RunPython(populate_new_field),
    ]
```

### 4. Test with Production-Scale Data

- Use staging environment with recent production snapshot
- Test with realistic data volumes
- Measure migration execution time

---

## Troubleshooting

### "Your models have changes not reflected in migrations"

**Cause**: Model changes without creating migrations

**Fix**:
```bash
python manage.py makemigrations
git add upstream/migrations/
git commit -m "feat: add migration for model changes"
```

---

### "Conflicting migrations detected"

**Cause**: Two branches created migrations with the same number

**Fix**:
```bash
# Rename one migration file
mv upstream/migrations/0003_auto.py upstream/migrations/0004_auto.py

# Update dependencies in 0004_auto.py
dependencies = [
    ('upstream', '0003_previous_migration'),
]
```

---

### "Migration is not reversible"

**Cause**: Migration has `RunPython` or `RunSQL` without reverse

**Fix**:
```python
operations = [
    migrations.RunPython(
        forwards_func,
        reverse_code=backwards_func,  # Add this!
    ),
]
```

---

## Related Documentation

- [Django Migrations Best Practices](https://docs.djangoproject.com/en/stable/topics/migrations/)
- [Upstream Database Schema](./DATABASE_SCHEMA.md)
- [Deployment Procedures](./DEPLOYMENT.md)
- [HIPAA Compliance Requirements](./HIPAA_COMPLIANCE.md)

---

## Support

If you encounter migration issues:

1. Check this guide first
2. Run `python scripts/validate_migrations.py` for diagnostics
3. Review recent migrations in `upstream/migrations/`
4. Contact the engineering team via Slack #engineering

**Emergency Contact**: For production migration failures, contact on-call engineer immediately.
