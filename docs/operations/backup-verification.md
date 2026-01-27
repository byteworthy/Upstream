# Backup Verification Automation

## Overview

Automated testing system for PostgreSQL backup and restore procedures, ensuring disaster recovery capabilities remain functional. Runs in CI/CD pipeline on every commit to main/develop branches.

## Quick Start

```bash
# Run backup verification tests (requires PostgreSQL)
python scripts/test_backup_restore.py --verbose

# View CI results
# Visit GitHub Actions → backup-verification job
```

## Architecture

### Test Script

**Location:** `scripts/test_backup_restore.py`

**Purpose:** Validates complete backup/restore lifecycle

**Test Suite:**

1. **Backup Creation Test**
   - Uses `pg_dump` to create plain SQL backup
   - Validates file creation and minimum size (>1KB)
   - Records backup file path for subsequent tests

2. **Backup Validation Test**
   - Checks PostgreSQL dump format signature
   - Calculates SHA256 checksum for integrity verification
   - Validates content is readable (>90% printable characters)
   - Detects corruption indicators

3. **Backup Restore Test**
   - Creates temporary test database
   - Restores backup using `psql`
   - Verifies schema integrity (table count)
   - Cleans up temporary resources automatically

**Environment Compatibility:**
- Requires PostgreSQL database (skips gracefully on SQLite)
- Requires PostgreSQL client tools: `pg_dump`, `pg_restore`, `psql`
- Supports Django settings via `DJANGO_SETTINGS_MODULE`
- Handles both `DATABASE_URL` and individual connection parameters

### CI Integration

**Location:** `.github/workflows/ci.yml`

**Job:** `backup-verification`

**Configuration:**
```yaml
services:
  postgres:
    image: postgres:15
    env:
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: test_db
    options: >-
      --health-cmd pg_isready
      --health-interval 10s
      --health-timeout 5s
      --health-retries 5
```

**Execution Flow:**
1. Checkout code
2. Set up Python 3.12 with pip caching
3. Install system dependencies (PostgreSQL client tools)
4. Install Python dependencies
5. Configure environment (.env with DATABASE_URL)
6. Run Django migrations (populates test database)
7. Execute backup verification script

**Timing:** Runs in parallel with `test` and `performance` jobs
**Duration:** Typically <2 minutes
**Triggers:** Push to main/develop, pull requests

## Running Tests

### In CI (Automatic)

Tests run automatically on:
- Push to `main` or `develop` branches
- Pull requests targeting `main` or `develop`

View results: **GitHub Actions** → **CI** workflow → **backup-verification** job

### Locally (Manual)

**Prerequisites:**
```bash
# PostgreSQL must be running and accessible
# Database credentials in .env or settings

# Install PostgreSQL client tools (if not present)
# Ubuntu/Debian:
sudo apt-get install postgresql-client

# macOS:
brew install postgresql
```

**Run tests:**
```bash
# Standard output
python scripts/test_backup_restore.py

# Verbose output (recommended)
python scripts/test_backup_restore.py --verbose

# Example verbose output:
# [INFO] ============================================================
# [INFO] TEST 1: Backup Creation
# [INFO] ============================================================
# [INFO] Creating backup of database: test_db
# [INFO] Backup file: /tmp/tmp_xyz/test_backup.sql
# [INFO] ✓ pg_dump completed successfully
# [INFO] ✓ Backup file size: 45,678 bytes (44.61 KB)
# [INFO] ✓ TEST 1 PASSED: Backup created successfully
```

**Development environment behavior:**
- SQLite (default dev): Tests skip with message "Backup tests require PostgreSQL"
- PostgreSQL: Tests run normally

## Database Configuration

### PostgreSQL Requirements

**Minimum version:** PostgreSQL 10+
**Required permissions:**
- `pg_dump` access (read database)
- `CREATE DATABASE` (for restore test)
- `DROP DATABASE` (for cleanup)

### Connection Methods

**Method 1: DATABASE_URL (recommended)**
```bash
# .env
DATABASE_URL=postgresql://user:password@localhost:5432/mydb  # pragma: allowlist secret
```

**Method 2: Individual parameters**
```bash
# .env
DB_ENGINE=django.db.backends.postgresql
DB_NAME=mydb
DB_USER=myuser
DB_PASSWORD=mypassword
DB_HOST=localhost
DB_PORT=5432
```

### CI Database Configuration

GitHub Actions uses service container:
```yaml
DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test_db  # pragma: allowlist secret
```

## Security Considerations

### Credential Protection

1. **Password redaction in logs**
   - Script automatically redacts passwords from error messages
   - PGPASSWORD set via environment variable (not CLI args)

2. **Temporary file cleanup**
   - Backup files stored in ephemeral temp directories
   - Automatic cleanup on test completion
   - Cleanup runs even if tests fail

3. **Test database isolation**
   - Creates unique temporary databases (timestamped names)
   - Terminates connections before cleanup
   - No impact on production data

### Best Practices

- Never commit `.env` files with real credentials
- Use GitHub Secrets for production backup verification
- Rotate database passwords regularly
- Limit test database to non-sensitive data

## Troubleshooting

### Tests Skip in Development

**Symptom:** "Backup tests require PostgreSQL, found: django.db.backends.sqlite3"

**Resolution:** Expected behavior in SQLite environments. Tests run in CI with PostgreSQL.

### PostgreSQL Tools Not Found

**Symptom:** "PostgreSQL client tools (pg_dump, pg_restore, psql) not available"

**Resolution:**
```bash
# Ubuntu/Debian
sudo apt-get install postgresql-client

# macOS
brew install postgresql

# Alpine Linux (Docker)
apk add postgresql-client
```

### Connection Refused

**Symptom:** "could not connect to server: Connection refused"

**Resolution:**
1. Verify PostgreSQL is running: `pg_isready -h localhost`
2. Check DATABASE_URL credentials
3. Verify firewall/network settings
4. Ensure PostgreSQL accepts connections on specified port

### Permission Denied

**Symptom:** "permission denied to create database"

**Resolution:**
1. User needs `CREATEDB` privilege: `ALTER USER myuser CREATEDB;`
2. Or use superuser for tests (not recommended for production)

### Backup File Too Small

**Symptom:** "Backup file is suspiciously small: 512 bytes"

**Resolution:**
1. Check database has data: `SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public';`
2. Verify migrations ran: `python manage.py migrate --check`
3. Check pg_dump errors: Run with `--verbose` flag

### Restore Errors

**Symptom:** "ERROR: relation 'table_name' already exists"

**Resolution:**
1. Cleanup failed: Temporary database not dropped
2. Manual cleanup: `DROP DATABASE IF EXISTS test_restore_*;`
3. Check for orphaned connections: `SELECT * FROM pg_stat_activity;`

## Maintenance

### Adding New Tests

To extend test coverage:

1. Add new test method to `BackupVerificationTests` class
2. Follow naming convention: `test_backup_*`
3. Use `self._log()` for verbose output
4. Clean up resources in tearDown or with context managers
5. Test locally before committing

Example:
```python
def test_backup_compression(self):
    """Test that compressed backups can be created and validated."""
    self._log("Testing compressed backup format...")

    # Implementation here

    self._log("✓ Compressed backup test passed")
```

### Updating PostgreSQL Version

1. Update service container image in `.github/workflows/ci.yml`
2. Test with new version locally
3. Update documentation

Example:
```yaml
services:
  postgres:
    image: postgres:16  # Updated from 15
```

### Performance Optimization

Current benchmarks (GitHub Actions):
- Backup creation: ~5-10 seconds
- Validation: <1 second
- Restore: ~10-15 seconds
- **Total:** ~30 seconds

To improve performance:
- Use custom format (`-F c`) instead of plain SQL (smaller files)
- Reduce test data volume
- Parallel restore with `pg_restore -j N`

### Monitoring

**Metrics to track:**
- Test execution time trend
- Backup file size trend
- Test failure rate
- CI job success rate

**Alerts to configure:**
- Consecutive test failures (indicates backup procedure broken)
- Execution time >5 minutes (indicates performance degradation)
- Backup file size <10KB (indicates empty or corrupted backup)

## Related Documentation

- [Disaster Recovery Plan](./disaster-recovery.md) - Full DR procedures
- [Database Operations](./database-operations.md) - General database management
- [CI/CD Pipeline](../development/ci-cd.md) - GitHub Actions workflows
- [Production Backups](./production-backups.md) - Production backup schedules

## Support

**Questions or issues?**
- Check troubleshooting section above
- Review test logs: `python scripts/test_backup_restore.py --verbose`
- Check CI job logs in GitHub Actions
- Open issue with "backup-verification" label

## Changelog

### Version 1.0.0 (2026-01-27)
- Initial implementation
- PostgreSQL backup/restore test suite
- CI/CD integration
- Comprehensive documentation
