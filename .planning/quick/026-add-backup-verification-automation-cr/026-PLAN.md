---
phase: quick-026
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - scripts/test_backup_restore.py
  - .github/workflows/ci.yml
autonomous: true

must_haves:
  truths:
    - PostgreSQL backup can be created and validated in CI
    - Backup restore procedure can be tested automatically
    - Test failures are caught before production deployment
  artifacts:
    - path: "scripts/test_backup_restore.py"
      provides: "Automated backup restore testing script"
      min_lines: 150
      exports: ["test_backup_creation", "test_backup_restore", "test_backup_validation"]
    - path: ".github/workflows/ci.yml"
      provides: "CI job for backup verification"
      contains: "backup-verification"
  key_links:
    - from: ".github/workflows/ci.yml"
      to: "scripts/test_backup_restore.py"
      via: "python scripts/test_backup_restore.py"
      pattern: "python.*test_backup_restore"
    - from: "scripts/test_backup_restore.py"
      to: "pg_dump|pg_restore"
      via: "subprocess calls to PostgreSQL backup utilities"
      pattern: "pg_dump|pg_restore"
---

<objective>
Add automated backup verification to CI pipeline to ensure PostgreSQL backup/restore procedures work correctly before production deployment.

Purpose: Prevent backup procedure failures in production by testing backup creation, validation, and restore in CI.
Output: Test script that validates backup/restore workflow + CI integration that runs on every commit.
</objective>

<execution_context>
@/home/codespace/.claude/get-shit-done/workflows/execute-plan.md
@/home/codespace/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@.agents/skills/automating-database-backups/scripts/backup_validator.py
@.agents/skills/managing-database-recovery/scripts/validate_backup.sh
@.github/workflows/ci.yml
</context>

<tasks>

<task type="auto">
  <name>Create backup verification test script</name>
  <files>scripts/test_backup_restore.py</files>
  <action>
Create Python script scripts/test_backup_restore.py that:

**Backup Creation Test:**
- Uses Django's database connection settings to get PostgreSQL credentials
- Creates test database with sample data (2-3 tables, 100 rows)
- Runs pg_dump to create backup file (SQL format)
- Validates backup file exists and has reasonable size (>1KB)
- Uses subprocess to call pg_dump with proper connection params

**Backup Validation Test:**
- Leverages existing backup_validator.py patterns from .agents/skills/
- Validates PostgreSQL backup format (checks for "PostgreSQL database dump" header)
- Calculates SHA256 checksum of backup file
- Verifies backup is not empty or corrupted
- Reports validation errors clearly

**Restore Verification Test:**
- Creates fresh temporary database for restore test
- Runs pg_restore or psql to restore from backup file
- Queries restored database to verify data integrity (row counts match)
- Validates schema objects exist (tables, indexes)
- Cleans up temporary database after test

**Implementation Details:**
- Use Django's settings.DATABASES['default'] for connection params
- Use tempfile.TemporaryDirectory() for backup file storage
- Use unittest.TestCase for test structure (3 test methods)
- Add --verbose flag for detailed output
- Exit code 0 on success, 1 on failure
- Timeout protection (30s per operation)
- Handle pg_dump/pg_restore not found gracefully (skip with warning)

**Error Handling:**
- Wrap all subprocess calls in try/except with clear error messages
- Clean up temp files and databases even on failure (try/finally)
- Log each step for debugging
- Don't expose database credentials in output (use [REDACTED])
  </action>
  <verify>
Run script manually:
```bash
python scripts/test_backup_restore.py --verbose
```
Verify output shows 3 tests passing (create, validate, restore).
  </verify>
  <done>
- scripts/test_backup_restore.py exists with 150+ lines
- Script has 3 test methods: test_backup_creation, test_backup_validation, test_backup_restore
- Manual run succeeds with exit code 0
- Script handles missing pg_dump/pg_restore gracefully
  </done>
</task>

<task type="auto">
  <name>Add backup verification job to CI workflow</name>
  <files>.github/workflows/ci.yml</files>
  <action>
Add new job to .github/workflows/ci.yml:

**Job Configuration:**
- Job name: "backup-verification"
- runs-on: ubuntu-latest
- Add PostgreSQL service container (postgres:15, port 5432)
- Service environment: POSTGRES_PASSWORD=postgres, POSTGRES_DB=test_db
- Service health check: pg_isready with retries

**Steps:**
1. Checkout code (actions/checkout@v4)
2. Set up Python 3.12 (actions/setup-python@v5 with cache: 'pip')
3. Install PostgreSQL client tools (apt-get install postgresql-client)
4. Install Python dependencies (pip install -r requirements.txt)
5. Set up Django environment (.env with DATABASE_URL pointing to service)
6. Run Django migrations (python manage.py migrate --noinput)
7. Load test fixtures if available (python manage.py loaddata test_data || true)
8. Run backup verification script (python scripts/test_backup_restore.py --verbose)

**Environment Variables:**
- DATABASE_URL=postgresql://postgres:postgres@localhost:5432/test_db
- SECRET_KEY=ci-test-secret-key
- DEBUG=True
- DJANGO_SETTINGS_MODULE=aidscope.settings

**Placement:**
- Add after existing "test" job
- No dependencies (runs in parallel with tests)
- Should complete in <2 minutes

**Why this approach:**
- Service container provides real PostgreSQL for testing (not SQLite)
- Separate job isolates backup testing from unit tests
- Parallel execution saves CI time
- Validates backup procedures in production-like environment
  </action>
  <verify>
Check workflow file:
```bash
cat .github/workflows/ci.yml | grep -A 30 "backup-verification"
```
Validate YAML syntax:
```bash
yamllint .github/workflows/ci.yml || python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
```
  </verify>
  <done>
- .github/workflows/ci.yml contains backup-verification job
- Job has PostgreSQL service container configured
- Job runs scripts/test_backup_restore.py with --verbose flag
- YAML syntax is valid
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <what-built>
Backup verification automation with test script and CI integration.

Automated:
- scripts/test_backup_restore.py created with backup creation, validation, and restore tests
- .github/workflows/ci.yml updated with backup-verification job
- PostgreSQL service container configured in CI
  </what-built>
  <how-to-verify>
1. **Check CI workflow runs:**
   - Visit https://github.com/YOUR_ORG/YOUR_REPO/actions
   - Find latest workflow run for this branch
   - Verify "backup-verification" job appears and succeeds
   - Check job logs show 3 tests passing (create, validate, restore)

2. **Test locally (if possible):**
   ```bash
   # Requires PostgreSQL running locally
   python scripts/test_backup_restore.py --verbose
   ```
   Expected: All tests pass, backup file created/restored successfully

3. **Verify test coverage:**
   - Test creates backup file with pg_dump
   - Test validates backup format and checksum
   - Test restores to temporary database and verifies data
   - Test cleans up temporary resources

4. **Check error handling:**
   - Script handles missing PostgreSQL tools gracefully
   - CI job fails fast if backup procedures break
   - Error messages are clear and actionable

**Expected outcomes:**
- CI pipeline includes backup verification on every commit
- Backup procedure failures caught before production
- Test completes in <2 minutes
- No false positives or flaky tests
  </how-to-verify>
  <resume-signal>
Type "approved" if backup verification works in CI, or describe any issues found.
  </resume-signal>
</task>

</tasks>

<verification>
**Automated Tests:**
- python scripts/test_backup_restore.py runs successfully
- CI backup-verification job passes
- Backup file creation succeeds
- Backup validation succeeds
- Restore procedure succeeds

**Integration Checks:**
- CI workflow YAML is valid
- PostgreSQL service container starts correctly
- Script connects to database using Django settings
- All temporary resources cleaned up after test

**Quality Checks:**
- Script has proper error handling (try/except/finally)
- No database credentials exposed in logs
- Tests complete in reasonable time (<2 minutes)
- Clear success/failure messages for debugging
</verification>

<success_criteria>
**Measurable Outcomes:**
- [ ] scripts/test_backup_restore.py exists and runs without errors
- [ ] Script validates backup creation, validation, and restore workflow
- [ ] CI workflow includes backup-verification job
- [ ] Job runs on every push/PR to main/develop branches
- [ ] Backup procedure failures cause CI to fail (preventing bad deploys)
- [ ] Test completes in <2 minutes in CI

**Operational Benefits:**
- Backup procedures validated before production deployment
- Confidence in disaster recovery capabilities
- Automated regression detection for backup/restore changes
- HIPAA compliance improved (verified backup recoverability)
</success_criteria>

<output>
After completion, create `.planning/quick/026-add-backup-verification-automation-cr/026-SUMMARY.md` with:
- Test script implementation details
- CI integration configuration
- Sample test output showing successful backup/restore verification
- Recommended next steps (if any)
</output>
