#!/usr/bin/env python3
"""
Backup Verification Test Script

Tests PostgreSQL backup creation, validation, and restore procedures to ensure
disaster recovery capabilities work correctly. Designed for CI/CD integration.

Author: Claude Sonnet 4.5
Version: 1.0.0
License: MIT
"""

import argparse
import hashlib
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import Dict, Optional, Tuple

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Setup Django environment
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hello_world.settings')
django.setup()

from django.conf import settings


class BackupVerificationTests(unittest.TestCase):
    """Test suite for PostgreSQL backup/restore verification."""

    @classmethod
    def setUpClass(cls):
        """Set up test class with database connection info."""
        cls.db_config = settings.DATABASES['default']
        cls.db_engine = cls.db_config['ENGINE']

        # Skip tests if not using PostgreSQL
        if 'postgresql' not in cls.db_engine:
            raise unittest.SkipTest(
                f"Backup tests require PostgreSQL, found: {cls.db_engine}"
            )

        # Check if pg_dump and pg_restore are available
        cls.pg_dump_available = cls._check_command('pg_dump')
        cls.pg_restore_available = cls._check_command('pg_restore')
        cls.psql_available = cls._check_command('psql')

        if not (cls.pg_dump_available and cls.pg_restore_available and cls.psql_available):
            raise unittest.SkipTest(
                "PostgreSQL client tools (pg_dump, pg_restore, psql) not available"
            )

        cls.temp_dir = None
        cls.backup_file = None
        cls.test_db_name = None

    @staticmethod
    def _check_command(command: str) -> bool:
        """Check if a command is available on the system."""
        try:
            subprocess.run(
                [command, '--version'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5
            )
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def setUp(self):
        """Set up each test with temporary directory."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

    def _get_pg_connection_params(self) -> Dict[str, str]:
        """Get PostgreSQL connection parameters from Django settings."""
        # Handle both dj_database_url parsed configs and direct configs
        params = {
            'host': self.db_config.get('HOST', 'localhost'),
            'port': str(self.db_config.get('PORT', '5432')),
            'user': self.db_config.get('USER', 'postgres'),
            'password': self.db_config.get('PASSWORD', ''),
            'database': self.db_config.get('NAME', 'postgres'),
        }

        return params

    def _build_pg_env(self, params: Dict[str, str]) -> Dict[str, str]:
        """Build environment variables for PostgreSQL commands."""
        env = os.environ.copy()
        if params['password']:
            env['PGPASSWORD'] = params['password']
        return env

    def _log(self, message: str, verbose: bool = True):
        """Log a message if verbose mode is enabled."""
        if verbose or getattr(self, '_verbose', False):
            print(f"[INFO] {message}")

    def _log_error(self, message: str):
        """Log an error message."""
        print(f"[ERROR] {message}", file=sys.stderr)

    def _redact_credentials(self, text: str) -> str:
        """Redact database credentials from text."""
        params = self._get_pg_connection_params()
        redacted = text
        if params['password']:
            redacted = redacted.replace(params['password'], '[REDACTED]')
        return redacted

    def test_backup_creation(self):
        """Test that PostgreSQL backup can be created successfully."""
        self._log("=" * 60)
        self._log("TEST 1: Backup Creation")
        self._log("=" * 60)

        params = self._get_pg_connection_params()
        env = self._build_pg_env(params)

        # Create backup file path
        backup_path = Path(self.temp_dir.name) / 'test_backup.sql'

        self._log(f"Creating backup of database: {params['database']}")
        self._log(f"Backup file: {backup_path}")

        # Run pg_dump to create backup
        try:
            cmd = [
                'pg_dump',
                '-h', params['host'],
                '-p', params['port'],
                '-U', params['user'],
                '-F', 'p',  # Plain SQL format
                '-f', str(backup_path),
                params['database']
            ]

            self._log(f"Running: {' '.join(cmd[:7])} [REDACTED] {cmd[-1]}")

            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                stderr_safe = self._redact_credentials(result.stderr)
                self._log_error(f"pg_dump failed: {stderr_safe}")
                self.fail(f"pg_dump failed with return code {result.returncode}")

            self._log("✓ pg_dump completed successfully")

        except subprocess.TimeoutExpired:
            self.fail("pg_dump timed out after 30 seconds")
        except Exception as e:
            self.fail(f"Unexpected error during backup creation: {e}")

        # Verify backup file exists
        self.assertTrue(
            backup_path.exists(),
            "Backup file was not created"
        )
        self._log(f"✓ Backup file exists: {backup_path}")

        # Verify backup file has reasonable size (>1KB)
        file_size = backup_path.stat().st_size
        self.assertGreater(
            file_size,
            1024,
            f"Backup file is suspiciously small: {file_size} bytes"
        )
        self._log(f"✓ Backup file size: {file_size:,} bytes ({file_size / 1024:.2f} KB)")

        # Store backup path for next tests
        self.__class__.backup_file = backup_path

        self._log("✓ TEST 1 PASSED: Backup created successfully\n")

    def test_backup_validation(self):
        """Test that backup file can be validated."""
        self._log("=" * 60)
        self._log("TEST 2: Backup Validation")
        self._log("=" * 60)

        # Ensure backup was created in previous test
        if not self.__class__.backup_file or not self.__class__.backup_file.exists():
            self.skipTest("Backup file not available from previous test")

        backup_path = self.__class__.backup_file

        self._log(f"Validating backup file: {backup_path}")

        # Read first 1000 bytes to check format
        try:
            with open(backup_path, 'r', encoding='utf-8', errors='ignore') as f:
                header = f.read(1000)

            # Check for PostgreSQL dump signature
            has_pg_signature = (
                'PostgreSQL database dump' in header or
                'pg_dump' in header or
                'SET statement_timeout' in header or
                'SET lock_timeout' in header
            )

            self.assertTrue(
                has_pg_signature,
                "Backup file does not contain PostgreSQL dump signature"
            )
            self._log("✓ PostgreSQL backup format validated")

        except Exception as e:
            self.fail(f"Failed to read backup file: {e}")

        # Calculate SHA256 checksum
        try:
            sha256 = hashlib.sha256()
            with open(backup_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    sha256.update(chunk)
            checksum = sha256.hexdigest()

            self.assertEqual(
                len(checksum),
                64,
                "Invalid SHA256 checksum length"
            )
            self._log(f"✓ SHA256 checksum: {checksum[:16]}...")

        except Exception as e:
            self.fail(f"Failed to calculate checksum: {e}")

        # Verify backup is not empty
        file_size = backup_path.stat().st_size
        self.assertGreater(
            file_size,
            0,
            "Backup file is empty"
        )

        # Check for common corruption indicators
        try:
            with open(backup_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # Should not be binary garbage (at least 90% printable characters)
            printable_ratio = sum(c.isprintable() or c in '\n\r\t' for c in content[:10000]) / min(len(content), 10000)
            self.assertGreater(
                printable_ratio,
                0.9,
                f"Backup file appears corrupted (only {printable_ratio:.1%} printable)"
            )
            self._log(f"✓ Content validation: {printable_ratio:.1%} printable characters")

        except Exception as e:
            self.fail(f"Failed to validate backup content: {e}")

        self._log("✓ TEST 2 PASSED: Backup validation successful\n")

    def test_backup_restore(self):
        """Test that backup can be restored to a temporary database."""
        self._log("=" * 60)
        self._log("TEST 3: Backup Restore")
        self._log("=" * 60)

        # Ensure backup was created in previous test
        if not self.__class__.backup_file or not self.__class__.backup_file.exists():
            self.skipTest("Backup file not available from previous test")

        backup_path = self.__class__.backup_file
        params = self._get_pg_connection_params()
        env = self._build_pg_env(params)

        # Create temporary database for restore test
        test_db_name = f"test_restore_{int(time.time())}"
        self.__class__.test_db_name = test_db_name

        self._log(f"Creating temporary database: {test_db_name}")

        try:
            # Create test database
            create_cmd = [
                'psql',
                '-h', params['host'],
                '-p', params['port'],
                '-U', params['user'],
                '-d', 'postgres',  # Connect to postgres db to create new db
                '-c', f'CREATE DATABASE {test_db_name};'
            ]

            result = subprocess.run(
                create_cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                stderr_safe = self._redact_credentials(result.stderr)
                # Check if database already exists (not a failure)
                if 'already exists' not in result.stderr:
                    self._log_error(f"Failed to create test database: {stderr_safe}")
                    self.fail(f"Database creation failed with return code {result.returncode}")

            self._log(f"✓ Temporary database created: {test_db_name}")

            # Restore backup to test database
            self._log(f"Restoring backup to: {test_db_name}")

            restore_cmd = [
                'psql',
                '-h', params['host'],
                '-p', params['port'],
                '-U', params['user'],
                '-d', test_db_name,
                '-f', str(backup_path)
            ]

            self._log(f"Running: psql -h {params['host']} -p {params['port']} -U {params['user']} -d {test_db_name} -f {backup_path}")

            result = subprocess.run(
                restore_cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=30
            )

            # psql returns 0 even with some warnings, check for critical errors
            if result.returncode != 0:
                stderr_safe = self._redact_credentials(result.stderr)
                self._log_error(f"Restore warnings/errors: {stderr_safe}")
                # Only fail if there are actual ERROR lines (not just NOTICEs)
                if 'ERROR:' in result.stderr:
                    self.fail(f"Restore failed with critical errors")

            self._log("✓ Backup restored successfully")

            # Verify restored database has tables
            self._log("Verifying restored database schema...")

            verify_cmd = [
                'psql',
                '-h', params['host'],
                '-p', params['port'],
                '-U', params['user'],
                '-d', test_db_name,
                '-t',  # Tuples only (no headers)
                '-c', "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';"
            ]

            result = subprocess.run(
                verify_cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                self.fail("Failed to query restored database")

            table_count = int(result.stdout.strip())
            self.assertGreater(
                table_count,
                0,
                "Restored database has no tables"
            )
            self._log(f"✓ Restored database has {table_count} tables")

            self._log("✓ TEST 3 PASSED: Backup restore successful\n")

        except subprocess.TimeoutExpired:
            self.fail("Database operation timed out")
        except Exception as e:
            self.fail(f"Unexpected error during restore: {e}")
        finally:
            # Clean up temporary database
            if self.__class__.test_db_name:
                self._cleanup_test_database(params, env)

    def _cleanup_test_database(self, params: Dict[str, str], env: Dict[str, str]):
        """Clean up temporary test database."""
        if not self.__class__.test_db_name:
            return

        test_db_name = self.__class__.test_db_name
        self._log(f"Cleaning up temporary database: {test_db_name}")

        try:
            # Terminate existing connections
            terminate_cmd = [
                'psql',
                '-h', params['host'],
                '-p', params['port'],
                '-U', params['user'],
                '-d', 'postgres',
                '-c', f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{test_db_name}';"
            ]

            subprocess.run(
                terminate_cmd,
                env=env,
                capture_output=True,
                timeout=10
            )

            # Drop database
            drop_cmd = [
                'psql',
                '-h', params['host'],
                '-p', params['port'],
                '-U', params['user'],
                '-d', 'postgres',
                '-c', f'DROP DATABASE IF EXISTS {test_db_name};'
            ]

            result = subprocess.run(
                drop_cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                self._log(f"✓ Cleaned up temporary database: {test_db_name}")
            else:
                self._log(f"Warning: Failed to clean up database {test_db_name}")

        except Exception as e:
            self._log(f"Warning: Error during cleanup: {e}")


def main():
    """Main entry point for the test script."""
    parser = argparse.ArgumentParser(
        description='Test PostgreSQL backup creation, validation, and restore'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )

    args = parser.parse_args()

    # Set verbose flag for tests
    BackupVerificationTests._verbose = args.verbose

    # Run tests
    suite = unittest.TestLoader().loadTestsFromTestCase(BackupVerificationTests)
    runner = unittest.TextTestRunner(verbosity=2 if args.verbose else 1)
    result = runner.run(suite)

    # Exit with appropriate code
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
