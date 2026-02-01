# Implementation Plan: Fix .env File Permissions (CRIT-9)

**Task ID**: CRIT-9
**Severity**: CRITICAL
**Domain**: Security/DevOps
**HIPAA Impact**: PHI encryption key exposure
**Estimated Effort**: <1 day
**Complexity**: Low (95% confidence)

---

## Overview

This plan addresses a HIPAA-critical security vulnerability where .env files containing the FIELD_ENCRYPTION_KEY (PHI encryption) have world-readable permissions (666). We will immediately fix permissions, add Django startup validation to prevent recurrence, update deployment scripts, and document the security requirement.

## Architecture Decision

**Pattern**: Django AppConfig.ready() Hook for Startup Validation

**Rationale**:
1. Runs early in Django initialization before any requests are processed
2. Idiomatic Django pattern for startup checks
3. Allows conditional checking - only validate when .env exists (Docker/Cloud Run use environment variables, not files)
4. Can differentiate behavior by environment (warn in dev, block in production)

---

## Implementation Steps

### Step 1: Immediate Security Fix - chmod 600 on .env files

**Goal**: Immediately close the security vulnerability by restricting .env file permissions to owner-only read/write

**Files to Modify**:
- `/workspaces/codespaces-django/.env` - Change permissions from 666 to 600

**Implementation Details**:
- Run chmod 600 .env to restrict to owner-only access
- Verify with stat command that permissions are now 600
- Do NOT modify .env.example or .env.production.example (these are templates)
- Git commit this operational fix immediately

**Risks**:
- None - this is a safe file permission change
- If .env is somehow owned by a different user than the app process, may cause startup failure (unlikely)

**Verification**: Run `stat -c '%a' .env` and verify output is 600. Then run `python manage.py check` to ensure Django still starts.

---

### Step 2: Add Startup Permission Validation to AppConfig

**Goal**: Add a ready() method to PayrixaConfig that validates .env permissions at Django startup to prevent future regressions

**Files to Modify**:
- `/workspaces/codespaces-django/upstream/apps.py` - Add ready() method with permission checking logic
- `/workspaces/codespaces-django/upstream/env_permissions.py` - Create new module with EnvPermissionChecker class

**Implementation Details**:
- Create upstream/env_permissions.py with EnvPermissionChecker class
- Implement check_env_permissions() that uses os.stat() to read file mode
- Permission check validates that group and other bits are 0 (i.e., 0o600 or more restrictive)
- Make check conditional: only run if .env file exists (Docker/Cloud Run skip)
- Make check conditional: skip in CI (check GITHUB_ACTIONS, CI env vars)
- Behavior by environment: DEBUG=True → log warning, DEBUG=False → raise ImproperlyConfigured
- Add ready() method to PayrixaConfig that calls the checker
- Use django.core.exceptions.ImproperlyConfigured for production errors

**Risks**:
- If check is too strict, could block legitimate deployments
- Need to ensure CI/CD pipelines are not affected (they use env vars, not .env files)
- Must not break Docker deployments where .env doesn't exist

**Verification**: Create test file that verifies: (1) check passes with 600 permissions, (2) check warns in dev mode with 666, (3) check raises in prod mode with 666, (4) check skips gracefully when .env doesn't exist

---

### Step 3: Add Unit Tests for Permission Validation

**Goal**: Ensure the permission validation logic is thoroughly tested with unit tests covering all scenarios

**Files to Modify**:
- `/workspaces/codespaces-django/upstream/tests_env_permissions.py` - Create new test file

**Implementation Details**:
- Test class TestEnvPermissionChecker with multiple scenarios
- test_secure_permissions_pass: verify 600 permissions pass validation
- test_insecure_permissions_warn_dev: verify 666 permissions warn in DEBUG=True
- test_insecure_permissions_error_prod: verify 666 permissions raise ImproperlyConfigured in DEBUG=False
- test_env_file_missing_skips: verify missing .env is gracefully skipped
- test_ci_environment_skips: verify CI environments skip the check
- Use tempfile and unittest.mock to create isolated test scenarios
- Test with various permission modes: 600, 640, 644, 666, 777

**Risks**:
- Tests need to handle permission changes carefully on the filesystem
- Must use temporary files to avoid affecting the real .env

**Verification**: Run pytest upstream/tests_env_permissions.py -v and verify all tests pass

---

### Step 4: Update Production Validator Script

**Goal**: Add .env file permission validation to the existing production settings validator for deployment-time checking

**Files to Modify**:
- `/workspaces/codespaces-django/scripts/validate_production_settings.py` - Add new validate_env_file_security() method

**Implementation Details**:
- Add new method validate_env_file_security() to ProductionValidator class
- Check for common .env file locations: .env, .env.production, .env.local
- Validate permissions are 600 or more restrictive (no group/other access)
- Mark as CRITICAL severity if production .env has insecure permissions
- Add to validate_all() method call sequence
- Use pathlib.Path for cross-platform compatibility

**Risks**:
- Script runs with Django settings loaded - ensure no circular import issues
- May need to handle case where validator runs on machine without .env (CI)

**Verification**: Run python scripts/validate_production_settings.py and verify new check appears in output

---

### Step 5: Update Deployment Script with Permission Fix

**Goal**: Add automatic chmod 600 step to deployment script so permissions are always correct after deploy

**Files to Modify**:
- `/workspaces/codespaces-django/deploy_staging.sh` - Add secure_env_files() function

**Implementation Details**:
- Add new function secure_env_files() after check_prerequisites()
- Function checks if .env exists and runs chmod 600 if found
- Function checks if .env.production exists and runs chmod 600 if found
- Add log_info output for visibility
- Call secure_env_files() early in main() deployment flow (after prerequisites, before other steps)
- Add to DRY_RUN output as well

**Risks**:
- If running as different user than file owner, chmod may fail
- Should handle failure gracefully with warning, not hard error

**Verification**: Run ./deploy_staging.sh --dry-run and verify secure_env_files appears in output

---

### Step 6: Update Documentation

**Goal**: Document the .env permission requirement in all relevant places to prevent future security issues

**Files to Modify**:
- `/workspaces/codespaces-django/.env.example` - Add security note about chmod 600 requirement at top
- `/workspaces/codespaces-django/.env.production.example` - Emphasize chmod 600 in security checklist
- `/workspaces/codespaces-django/.gitignore` - Add .env.production and .env.local if not present

**Implementation Details**:
- Add prominent security banner to .env.example noting chmod 600 requirement
- Update .env.production.example security checklist to make permission check more prominent
- Ensure .gitignore has comprehensive .env* coverage (except templates)
- Add comment explaining why permissions matter (HIPAA, PHI encryption key)

**Risks**:
- Documentation changes are low risk
- Ensure .env.example and .env.production.example remain in git (they are templates)

**Verification**: Review diff to ensure only template files are tracked, actual .env files are ignored

---

### Step 7: Final Verification and Commit

**Goal**: Verify all changes work together and create final commit

**Implementation Details**:
- Run full test suite: pytest upstream/ -v
- Run Django checks: python manage.py check
- Run production validator: python scripts/validate_production_settings.py (expect warnings for dev environment)
- Verify .env has 600 permissions: stat -c '%a' .env
- Create atomic git commit with all changes
- Commit message should reference CRIT-9 and HIPAA compliance

**Risks**:
- If tests fail, may need to debug permission check edge cases

**Verification**: All pytest tests pass, Django check passes, deployment dry-run succeeds

---

## Critical Review Areas

### High Risk
- **upstream/apps.py** - Core Django app config; error here breaks entire application
- **Permission check logic** - Must be bulletproof; false positives could block legitimate deployments

### Needs Review
- **upstream/env_permissions.py** - New security-critical module needs careful review
- **CI/CD environment detection logic** - Must not break GitHub Actions

### Security Considerations
- **FIELD_ENCRYPTION_KEY** protects PHI data - exposure violates HIPAA 45 CFR 164.312(a)(2)(iv)
- **Permission check** must never log or expose the actual key value
- **Production environment** MUST block startup if permissions are insecure

---

## Files Summary

**Total Files to Modify**: 9

1. `.env` - chmod 600 (immediate fix)
2. `upstream/apps.py` - Add ready() hook
3. `upstream/env_permissions.py` - New permission checker module (NEW)
4. `upstream/tests_env_permissions.py` - New test file (NEW)
5. `scripts/validate_production_settings.py` - Add env permission check
6. `deploy_staging.sh` - Add chmod step
7. `.env.example` - Documentation update
8. `.env.production.example` - Documentation update
9. `.gitignore` - Ensure coverage

---

## Success Criteria

- ✅ .env file has 600 permissions
- ✅ Django startup validates permissions (conditional on file existence)
- ✅ Production validator checks .env permissions
- ✅ Deployment script automatically sets secure permissions
- ✅ All tests pass (including new permission tests)
- ✅ Django check passes
- ✅ Documentation updated
- ✅ No CI/CD breakage
- ✅ Docker/Cloud Run deployments unaffected

---

**Complexity**: Low
**Confidence**: 95%
**Reasoning**: Well-understood security fix with clear implementation patterns. The Django AppConfig.ready() pattern is idiomatic and well-documented. Main complexity is conditional logic for different environments (dev/prod/CI/Docker), which is straightforward with environment variable checks.
