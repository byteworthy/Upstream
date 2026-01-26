#!/usr/bin/env python3
"""
Migration Safety Validator for Upstream

Validates that database migrations are safe before deployment to prevent
production downtime and data loss.

Usage:
    python scripts/validate_migrations.py
    python scripts/validate_migrations.py --strict

Exit codes:
    0 - All validations passed
    1 - Critical migration safety issues found
    2 - Warnings detected (can proceed with caution)
"""

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


class MigrationValidator:
    """Validates migration safety before deployment."""

    def __init__(self, strict=False):
        self.strict = strict
        self.errors = 0
        self.warnings = 0
        self.checks_passed = 0

    def run_command(self, cmd, check=True):
        """Run a shell command and return the result."""
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                check=check,
            )
            return result
        except subprocess.CalledProcessError as e:
            return e

    def check_uncommitted_migrations(self):
        """Check for uncommitted model changes that need migrations."""
        print(f"{Colors.BLUE}🔍 Checking for uncommitted " f"migrations...{Colors.END}")

        result = self.run_command(
            "python manage.py makemigrations --check --dry-run --noinput",
            check=False,
        )

        if result.returncode == 0:
            print(f"{Colors.GREEN}✓ No uncommitted migrations " f"found{Colors.END}")
            self.checks_passed += 1
            return True
        else:
            print(f"{Colors.RED}✗ Uncommitted migrations " f"detected!{Colors.END}")
            print(f"{Colors.RED}{result.stderr}{Colors.END}")
            print(
                f"\n{Colors.YELLOW}Fix: Run 'python manage.py makemigrations' "
                f"and commit the generated migration files.{Colors.END}\n"
            )
            self.errors += 1
            return False

    def check_migration_plan(self):
        """Verify migrations can be applied and show the plan."""
        print(f"{Colors.BLUE}🔍 Verifying migration plan...{Colors.END}")

        result = self.run_command("python manage.py migrate --plan", check=False)

        if result.returncode == 0:
            # Check if there are pending migrations
            if "Planned operations:" in result.stdout or (
                "No planned migration operations" in result.stdout
            ):
                print(f"{Colors.GREEN}✓ Migration plan is " f"valid{Colors.END}")
                if "Planned operations:" in result.stdout:
                    print(f"\n{Colors.BLUE}Pending migrations:{Colors.END}")
                    print(result.stdout)
                self.checks_passed += 1
                return True
        else:
            print(f"{Colors.RED}✗ Migration plan " f"validation failed!{Colors.END}")
            print(f"{Colors.RED}{result.stderr}{Colors.END}")
            self.errors += 1
            return False

    def check_migration_conflicts(self):
        """Check for migration conflicts."""
        print(f"{Colors.BLUE}🔍 Checking for migration " f"conflicts...{Colors.END}")

        result = self.run_command(
            "python manage.py makemigrations --check --dry-run --noinput",
            check=False,
        )

        # Check for conflict indicators
        if "Conflicting migrations detected" in result.stderr:
            print(f"{Colors.RED}✗ Migration conflicts " f"detected!{Colors.END}")
            print(f"{Colors.RED}{result.stderr}{Colors.END}")
            self.errors += 1
            return False
        else:
            print(f"{Colors.GREEN}✓ No migration conflicts " f"found{Colors.END}")
            self.checks_passed += 1
            return True

    def check_deployment_settings(self):
        """Run Django deployment checks."""
        print(f"{Colors.BLUE}🔍 Running deployment " f"checks...{Colors.END}")

        # Temporarily set DEBUG=False for deployment checks
        env = os.environ.copy()
        env["DEBUG"] = "False"

        result = self.run_command(
            "DJANGO_SETTINGS_MODULE=upstream.settings.prod "
            "python manage.py check --deploy",
            check=False,
        )

        if result.returncode == 0:
            print(f"{Colors.GREEN}✓ Deployment checks " f"passed{Colors.END}")
            self.checks_passed += 1
            return True
        else:
            # Deployment checks might have warnings, not necessarily errors
            warning_count = result.stdout.count("?:")
            error_count = result.stdout.count("ERRORS")

            if error_count > 0:
                print(f"{Colors.RED}✗ Deployment check " f"errors found!{Colors.END}")
                print(f"{Colors.RED}{result.stdout}{Colors.END}")
                self.errors += 1
                return False
            elif warning_count > 0:
                print(
                    f"{Colors.YELLOW}⚠ Deployment warnings "
                    f"({warning_count} issues){Colors.END}"
                )
                print(f"{Colors.YELLOW}{result.stdout}{Colors.END}")
                self.warnings += 1
                return True
            else:
                print(f"{Colors.GREEN}✓ Deployment checks " f"passed{Colors.END}")
                self.checks_passed += 1
                return True

    def check_dangerous_operations(self):
        """Scan migrations for potentially dangerous operations."""
        print(f"{Colors.BLUE}🔍 Scanning for dangerous " f"operations...{Colors.END}")

        dangerous_patterns = {
            "RemoveField": "Field removal (potential data loss)",
            "DeleteModel": "Model deletion (data loss)",
            "AlterField": "Field alteration (verify data compatibility)",
            "RenameField": "Field rename (verify data migration)",
            "RenameModel": "Model rename (verify foreign keys)",
        }

        # Get list of unapplied migrations
        result = self.run_command(
            "python manage.py showmigrations --plan | grep '\\[ \\]'",
            check=False,
        )

        if result.returncode != 0 or not result.stdout.strip():
            print(f"{Colors.GREEN}✓ No pending migrations to " f"scan{Colors.END}")
            self.checks_passed += 1
            return True

        # Read migration files and scan for dangerous operations
        migrations_dir = PROJECT_ROOT / "upstream" / "migrations"
        dangerous_found = []

        for migration_file in migrations_dir.glob("*.py"):
            if migration_file.name == "__init__.py":
                continue

            content = migration_file.read_text()
            for pattern, description in dangerous_patterns.items():
                if f"migrations.{pattern}" in content:
                    dangerous_found.append((migration_file.name, pattern, description))

        if dangerous_found:
            print(
                f"{Colors.YELLOW}⚠ Potentially dangerous operations "
                f"detected:{Colors.END}\n"
            )
            for filename, pattern, description in dangerous_found:
                print(
                    f"  {Colors.YELLOW}• {filename}: {pattern} - "
                    f"{description}{Colors.END}"
                )
            print(
                f"\n{Colors.YELLOW}Recommendation: Review these migrations "
                f"carefully and ensure:\n"
                f"  1. Data migration scripts are in place if needed\n"
                f"  2. Backups are created before deployment\n"
                f"  3. Changes are tested in staging "
                f"environment{Colors.END}\n"
            )
            self.warnings += 1
            return True
        else:
            print(f"{Colors.GREEN}✓ No dangerous operations " f"detected{Colors.END}")
            self.checks_passed += 1
            return True

    def validate_all(self):
        """Run all validation checks."""
        print(f"{Colors.BOLD}{'='*70}{Colors.END}")
        print(f"{Colors.BOLD}Migration Safety Validation{Colors.END}")
        print(f"{Colors.BOLD}{'='*70}{Colors.END}\n")

        # Run all checks
        self.check_uncommitted_migrations()
        self.check_migration_conflicts()
        self.check_migration_plan()
        self.check_dangerous_operations()
        self.check_deployment_settings()

        # Print summary
        self.print_summary()
        return self.get_exit_code()

    def print_summary(self):
        """Print validation summary."""
        print(f"\n{Colors.BOLD}{'='*70}{Colors.END}")
        print(f"{Colors.BOLD}Summary{Colors.END}")
        print(f"{Colors.BOLD}{'='*70}{Colors.END}\n")

        print(f"Checks Passed: {Colors.GREEN}{self.checks_passed}{Colors.END}")
        if self.errors > 0:
            print(f"Errors: {Colors.RED}{self.errors}{Colors.END}")
        if self.warnings > 0:
            print(f"Warnings: {Colors.YELLOW}{self.warnings}{Colors.END}")

        print()

    def get_exit_code(self):
        """Get exit code based on validation results."""
        if self.errors > 0:
            print(f"{Colors.RED}{Colors.BOLD}DEPLOYMENT BLOCKED:{Colors.END} ")
            print(
                f"{Colors.RED}Critical migration safety issues must be "
                f"fixed before deployment.{Colors.END}\n"
            )
            return 1
        elif self.warnings > 0 and self.strict:
            print(
                f"{Colors.YELLOW}{Colors.BOLD}DEPLOYMENT BLOCKED "
                f"(STRICT MODE):{Colors.END} "
            )
            print(
                f"{Colors.YELLOW}Warnings detected. Review and fix before "
                f"deploying.{Colors.END}\n"
            )
            return 2
        elif self.warnings > 0:
            print(
                f"{Colors.YELLOW}{Colors.BOLD}DEPLOYMENT ALLOWED WITH "
                f"CAUTION:{Colors.END} "
            )
            print(
                f"{Colors.YELLOW}Warnings detected. Review before "
                f"deploying to production.{Colors.END}\n"
            )
            return 0  # Allow with warnings in non-strict mode
        else:
            print(f"{Colors.GREEN}{Colors.BOLD}✓ SAFE TO " f"DEPLOY{Colors.END}")
            print(
                f"{Colors.GREEN}All migration safety checks " f"passed!{Colors.END}\n"
            )
            return 0


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate migration safety before deployment"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Block deployment on warnings (not just errors)",
    )
    args = parser.parse_args()

    validator = MigrationValidator(strict=args.strict)
    exit_code = validator.validate_all()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
