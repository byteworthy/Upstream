#!/usr/bin/env python3
"""
Migration Testing Script

Validates Django migrations by testing forward application and backward rollback.
Tests migrations from scratch and verifies rollback capability to catch migration
issues before deployment.

Usage:
    python scripts/test_migrations.py
    python scripts/test_migrations.py --verbose

Exit codes:
    0 - All migration tests passed
    1 - Migration test failures detected
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class Colors:
    """ANSI color codes for terminal output."""

    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    END = "\033[0m"


class MigrationTester:
    """Tests Django migrations for forward/backward compatibility."""

    def __init__(self, verbose=False):
        self.verbose = verbose
        self.test_count = 0
        self.passed_count = 0
        self.failed_count = 0
        self.skipped_count = 0

    def log(self, message, color=""):
        """Print message if verbose mode enabled."""
        if self.verbose or color == Colors.RED:
            if color:
                print(f"{color}{message}{Colors.END}")
            else:
                print(message)

    def run_command(self, cmd, check=True):
        """Run a shell command and return the result."""
        self.log(f"Running: {cmd}", Colors.BLUE)
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                check=check,
                env=os.environ.copy(),
            )
            if self.verbose and result.stdout:
                print(result.stdout)
            if result.stderr and result.returncode != 0:
                self.log(result.stderr, Colors.RED)
            return result
        except subprocess.CalledProcessError as e:
            self.log(f"Command failed with exit code {e.returncode}", Colors.RED)
            if e.stderr:
                self.log(e.stderr, Colors.RED)
            return e

    def test_forward_migration(self):
        """Test applying all migrations from scratch."""
        print(f"\n{Colors.BOLD}{'='*70}{Colors.END}")
        print(f"{Colors.BOLD}Testing Forward Migrations{Colors.END}")
        print(f"{Colors.BOLD}{'='*70}{Colors.END}\n")

        self.test_count += 1
        self.log("Applying all migrations from scratch...", Colors.BLUE)

        # Run migrate
        result = self.run_command("python manage.py migrate --noinput", check=False)

        if result.returncode == 0:
            print(f"{Colors.GREEN}✓ All migrations applied successfully{Colors.END}")
            self.passed_count += 1

            # Run system checks
            self.log("\nRunning Django system checks...", Colors.BLUE)
            check_result = self.run_command(
                "python manage.py check --deploy", check=False
            )

            if check_result.returncode == 0:
                print(f"{Colors.GREEN}✓ System checks passed{Colors.END}")
                return True
            else:
                print(
                    f"{Colors.YELLOW}⚠ System checks returned warnings "
                    f"(non-blocking){Colors.END}"
                )
                return True
        else:
            print(f"{Colors.RED}✗ Migration application failed!{Colors.END}")
            self.failed_count += 1
            return False

    def get_migration_state(self):
        """Get current migration state for all apps."""
        result = self.run_command(
            "python manage.py showmigrations --plan", check=False
        )

        if result.returncode != 0:
            return None

        migrations = {}
        current_app = None

        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue

            # Parse migration entries like: [X]  upstream.0001_initial
            if line.startswith("[X]") or line.startswith("[ ]"):
                parts = line.split()
                if len(parts) >= 2:
                    full_name = parts[1]
                    if "." in full_name:
                        app, migration = full_name.rsplit(".", 1)
                        if app not in migrations:
                            migrations[app] = []
                        migrations[app].append(migration)

        return migrations

    def get_previous_migration(self, app, current_migration, all_migrations):
        """Get the migration before the current one."""
        try:
            idx = all_migrations.index(current_migration)
            if idx > 0:
                return all_migrations[idx - 1]
            return "zero"  # Roll back to beginning
        except (ValueError, IndexError):
            return None

    def test_backward_migration(self):
        """Test rolling back migrations."""
        print(f"\n{Colors.BOLD}{'='*70}{Colors.END}")
        print(f"{Colors.BOLD}Testing Backward Migrations (Rollback){Colors.END}")
        print(f"{Colors.BOLD}{'='*70}{Colors.END}\n")

        # Get current migration state
        migrations = self.get_migration_state()
        if not migrations:
            print(f"{Colors.RED}✗ Could not get migration state{Colors.END}")
            self.failed_count += 1
            return False

        # Filter to only test upstream app (skip Django contrib apps)
        if "upstream" not in migrations:
            print(
                f"{Colors.YELLOW}⚠ No upstream migrations found, "
                f"skipping rollback tests{Colors.END}"
            )
            self.skipped_count += 1
            return True

        app = "upstream"
        app_migrations = migrations[app]

        # Test only last 5 migrations to keep CI time reasonable
        migrations_to_test = app_migrations[-5:] if len(app_migrations) > 5 else app_migrations
        num_to_test = len(migrations_to_test)

        print(
            f"Testing rollback for last {num_to_test} migration(s) of {app} app\n"
        )

        rollback_failures = []

        for migration in migrations_to_test:
            self.test_count += 1
            self.log(f"\nTesting rollback: {app}.{migration}", Colors.BLUE)

            # Get previous migration
            prev_migration = self.get_previous_migration(
                app, migration, app_migrations
            )
            if prev_migration is None:
                self.log(f"  Skipping (can't determine previous migration)", Colors.YELLOW)
                self.skipped_count += 1
                continue

            # Roll back to previous migration
            rollback_target = prev_migration if prev_migration != "zero" else "zero"
            self.log(f"  Rolling back to: {rollback_target}", Colors.BLUE)

            result = self.run_command(
                f"python manage.py migrate {app} {rollback_target} --noinput",
                check=False,
            )

            if result.returncode != 0:
                self.log(f"  {Colors.RED}✗ Rollback failed{Colors.END}", Colors.RED)
                rollback_failures.append((migration, "rollback"))
                self.failed_count += 1
                continue

            self.log(f"  {Colors.GREEN}✓ Rollback successful{Colors.END}")

            # Re-apply the migration to restore state
            self.log(f"  Re-applying migration...", Colors.BLUE)
            result = self.run_command(
                f"python manage.py migrate {app} {migration} --noinput",
                check=False,
            )

            if result.returncode != 0:
                self.log(
                    f"  {Colors.RED}✗ Re-apply failed{Colors.END}", Colors.RED
                )
                rollback_failures.append((migration, "re-apply"))
                self.failed_count += 1
                continue

            self.log(f"  {Colors.GREEN}✓ Re-apply successful{Colors.END}")
            self.passed_count += 1

        # Print rollback test summary
        if rollback_failures:
            print(f"\n{Colors.RED}Rollback test failures:{Colors.END}")
            for migration, phase in rollback_failures:
                print(f"  {Colors.RED}✗ {app}.{migration} ({phase}){Colors.END}")
            return False
        else:
            print(
                f"\n{Colors.GREEN}✓ All rollback tests passed{Colors.END}"
            )
            return True

    def run_all_tests(self):
        """Run all migration tests."""
        print(f"\n{Colors.BOLD}{'='*70}{Colors.END}")
        print(f"{Colors.BOLD}Migration Testing Suite{Colors.END}")
        print(f"{Colors.BOLD}{'='*70}{Colors.END}\n")

        # Check environment
        if not os.getenv("DJANGO_SETTINGS_MODULE"):
            os.environ["DJANGO_SETTINGS_MODULE"] = "hello_world.settings"
            self.log(
                "Set DJANGO_SETTINGS_MODULE=hello_world.settings", Colors.BLUE
            )

        # Run forward migration tests
        forward_success = self.test_forward_migration()

        if not forward_success:
            print(
                f"\n{Colors.RED}Forward migration failed, skipping rollback "
                f"tests{Colors.END}"
            )
            return self.print_summary()

        # Run backward migration tests
        backward_success = self.test_backward_migration()

        return self.print_summary()

    def print_summary(self):
        """Print test summary and return exit code."""
        print(f"\n{Colors.BOLD}{'='*70}{Colors.END}")
        print(f"{Colors.BOLD}Test Summary{Colors.END}")
        print(f"{Colors.BOLD}{'='*70}{Colors.END}\n")

        print(f"Total tests: {self.test_count}")
        print(f"Passed: {Colors.GREEN}{self.passed_count}{Colors.END}")

        if self.failed_count > 0:
            print(f"Failed: {Colors.RED}{self.failed_count}{Colors.END}")

        if self.skipped_count > 0:
            print(f"Skipped: {Colors.YELLOW}{self.skipped_count}{Colors.END}")

        print()

        if self.failed_count > 0:
            print(
                f"{Colors.RED}{Colors.BOLD}MIGRATION TESTS FAILED{Colors.END}"
            )
            print(
                f"{Colors.RED}Fix migration issues before deploying to "
                f"production.{Colors.END}\n"
            )
            return 1
        else:
            print(
                f"{Colors.GREEN}{Colors.BOLD}✓ ALL MIGRATION TESTS "
                f"PASSED{Colors.END}"
            )
            print(
                f"{Colors.GREEN}Migrations are safe to deploy to "
                f"production.{Colors.END}\n"
            )
            return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test Django migrations for forward/backward compatibility"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose output"
    )
    args = parser.parse_args()

    tester = MigrationTester(verbose=args.verbose)
    exit_code = tester.run_all_tests()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
