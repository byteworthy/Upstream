#!/usr/bin/env python
"""
Rename Script: Upstream → Upstream

Comprehensively renames the entire codebase from Upstream to Upstream.

This script:
1. Renames the main Django app directory (upstream/ → upstream/)
2. Updates all Python imports
3. Updates Django settings
4. Updates WSGI/ASGI configuration
5. Updates Docker configs
6. Updates GCP configs
7. Updates documentation
8. Deletes old migrations and prepares for fresh ones
9. Updates URLs and routes
10. Creates git commit

Usage:
    python rename_to_upstream.py --execute

Options:
    --dry-run     Show what would change (default)
    --execute     Actually perform the rename
    --backup      Create backup before rename
"""

import os
import sys
import shutil
import re
from pathlib import Path
from datetime import datetime
import argparse

# Color codes
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
RED = '\033[0;31m'
BLUE = '\033[0;34m'
NC = '\033[0m'  # No Color

def log_info(msg):
    print(f"{BLUE}[INFO]{NC} {msg}")

def log_success(msg):
    print(f"{GREEN}[SUCCESS]{NC} {msg}")

def log_warning(msg):
    print(f"{YELLOW}[WARNING]{NC} {msg}")

def log_error(msg):
    print(f"{RED}[ERROR]{NC} {msg}")


class CodebaseRenamer:
    """Handles renaming Upstream to Upstream across the entire codebase."""

    def __init__(self, dry_run=True, create_backup=False):
        self.dry_run = dry_run
        self.create_backup = create_backup
        self.root_dir = Path.cwd()

        # Rename mappings
        self.old_name = "upstream"
        self.new_name = "upstream"
        self.old_name_title = "Upstream"
        self.new_name_title = "Upstream"

        # Track changes
        self.files_to_rename = []
        self.files_to_modify = []
        self.dirs_to_rename = []

    def backup_codebase(self):
        """Create backup of current codebase."""
        if not self.create_backup:
            return

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = self.root_dir / f"backup_upstream_{timestamp}"

        log_info(f"Creating backup at {backup_dir}")

        if not self.dry_run:
            # Copy specific important directories
            for item in ['upstream', 'hello_world', 'requirements.txt', 'manage.py']:
                src = self.root_dir / item
                if src.exists():
                    dst = backup_dir / item
                    if src.is_dir():
                        shutil.copytree(src, dst)
                    else:
                        backup_dir.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src, dst)

        log_success(f"Backup created: {backup_dir}")

    def find_files_to_process(self):
        """Find all files that need to be renamed or modified."""
        log_info("Scanning codebase for files to process...")

        # Patterns to exclude
        exclude_patterns = {
            '.git', '__pycache__', 'node_modules', '.pytest_cache',
            'staticfiles', 'media', '.venv', 'venv', 'env',
            '.agents', '.claude', 'backup_*', '*.pyc', '*.pyo'
        }

        # File extensions to process
        process_extensions = {
            '.py', '.md', '.txt', '.yaml', '.yml', '.sh',
            '.html', '.js', '.css', '.json', '.toml', '.cfg',
            '.ini', '.conf', '.env.example'
        }

        for path in self.root_dir.rglob('*'):
            # Skip excluded patterns
            if any(pattern in str(path) for pattern in exclude_patterns):
                continue

            # Check if file needs processing
            if path.is_file():
                if path.suffix in process_extensions or path.name in ['Dockerfile', 'Procfile']:
                    self.files_to_modify.append(path)

            # Check if directory needs renaming
            elif path.is_dir() and self.old_name in path.name:
                self.dirs_to_rename.append(path)

        log_success(f"Found {len(self.files_to_modify)} files to modify")
        log_success(f"Found {len(self.dirs_to_rename)} directories to rename")

    def update_file_content(self, file_path):
        """Update content of a single file."""
        try:
            # Read file
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            original_content = content

            # Apply replacements
            replacements = [
                # Python imports
                (r'from upstream\.', 'from upstream.'),
                (r'import upstream\.', 'import upstream.'),
                (r'from upstream import', 'from upstream import'),
                (r'import upstream\b', 'import upstream'),

                # Django app references
                (r'"upstream\.', '"upstream.'),
                (r"'upstream\.", "'upstream."),

                # Settings and configs
                (r'upstream\.settings', 'upstream.settings'),
                (r'upstream\.urls', 'upstream.urls'),
                (r'upstream\.wsgi', 'upstream.wsgi'),
                (r'upstream\.asgi', 'upstream.asgi'),

                # Database table prefixes (in migrations)
                (r'upstream_', 'upstream_'),

                # Docker/GCP service names
                (r'upstream-staging', 'upstream-staging'),
                (r'upstream-production', 'upstream-production'),
                (r'upstream-db', 'upstream-db'),
                (r'upstream-redis', 'upstream-redis'),

                # GCP project references
                (r'upstream-static', 'upstream-static'),
                (r'gcr\.io/[^/]+/upstream:', 'gcr.io/$PROJECT_ID/upstream:'),

                # Display names (case-sensitive)
                (r'\bPayrixa\b', 'Upstream'),

                # Documentation and comments
                (r'upstream\.com', 'upstream.cx'),

                # Package/module names in lowercase contexts
                (r'\bpayrixa\b(?!\.)', 'upstream'),
            ]

            for pattern, replacement in replacements:
                content = re.sub(pattern, replacement, content)

            # Check if file changed
            if content != original_content:
                if not self.dry_run:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                return True

            return False

        except Exception as e:
            log_error(f"Error processing {file_path}: {str(e)}")
            return False

    def rename_directory(self, old_path):
        """Rename a directory."""
        new_path = Path(str(old_path).replace(self.old_name, self.new_name))

        if not self.dry_run:
            if new_path.exists():
                log_warning(f"Target already exists: {new_path}")
                return False

            old_path.rename(new_path)

        return True

    def delete_migrations(self):
        """Delete old migration files (we'll create fresh ones)."""
        log_info("Deleting old migration files...")

        migrations_dir = self.root_dir / self.new_name / 'migrations'

        if not migrations_dir.exists():
            log_warning(f"Migrations directory not found: {migrations_dir}")
            return

        deleted_count = 0
        for migration_file in migrations_dir.glob('*.py'):
            if migration_file.name != '__init__.py':
                if not self.dry_run:
                    migration_file.unlink()
                deleted_count += 1
                log_info(f"  Deleted: {migration_file.name}")

        log_success(f"Deleted {deleted_count} migration files")
        log_info("Run 'python manage.py makemigrations' to create fresh migrations")

    def execute_rename(self):
        """Execute the full rename process."""
        print("=" * 70)
        print(f"{'DRY RUN - ' if self.dry_run else ''}Renaming Upstream → Upstream")
        print("=" * 70)
        print()

        # Step 1: Backup
        if self.create_backup and not self.dry_run:
            self.backup_codebase()

        # Step 2: Find files
        self.find_files_to_process()

        # Step 3: Update file contents
        log_info("Updating file contents...")
        modified_count = 0
        for file_path in self.files_to_modify:
            if self.update_file_content(file_path):
                modified_count += 1
                if modified_count <= 10 or not self.dry_run:
                    log_info(f"  Modified: {file_path.relative_to(self.root_dir)}")

        if modified_count > 10 and self.dry_run:
            log_info(f"  ... and {modified_count - 10} more files")

        log_success(f"Modified {modified_count} files")

        # Step 4: Rename directories (do this last, after content updates)
        log_info("Renaming directories...")

        # Sort directories by depth (deepest first) to avoid conflicts
        sorted_dirs = sorted(self.dirs_to_rename, key=lambda p: len(p.parts), reverse=True)

        renamed_count = 0
        for old_path in sorted_dirs:
            new_path = Path(str(old_path).replace(self.old_name, self.new_name))
            if self.rename_directory(old_path):
                renamed_count += 1
                log_info(f"  {old_path.relative_to(self.root_dir)} → {new_path.relative_to(self.root_dir)}")

        log_success(f"Renamed {renamed_count} directories")

        # Step 5: Delete old migrations
        if not self.dry_run:
            self.delete_migrations()
        else:
            log_info("Would delete migration files (except __init__.py)")

        # Summary
        print()
        print("=" * 70)
        print("Summary")
        print("=" * 70)
        print(f"Files modified: {modified_count}")
        print(f"Directories renamed: {renamed_count}")
        print()

        if self.dry_run:
            print(f"{YELLOW}This was a DRY RUN. No changes were made.{NC}")
            print(f"Run with --execute to perform the actual rename.")
        else:
            print(f"{GREEN}Rename complete!{NC}")
            print()
            print("Next steps:")
            print("  1. Run tests: python manage.py test")
            print("  2. Create fresh migrations: python manage.py makemigrations")
            print("  3. Apply migrations: python manage.py migrate")
            print("  4. Update requirements if needed")
            print("  5. Commit changes: git add -A && git commit -m 'Rename Upstream to Upstream'")

        print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description='Rename Upstream to Upstream')
    parser.add_argument('--execute', action='store_true', help='Execute the rename (default is dry-run)')
    parser.add_argument('--backup', action='store_true', help='Create backup before rename')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation prompt')

    args = parser.parse_args()

    # Confirm if executing
    if args.execute and not args.yes:
        print()
        print(f"{YELLOW}WARNING: This will rename the entire codebase.{NC}")
        print()
        response = input("Are you sure you want to proceed? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("Aborted.")
            sys.exit(0)
        print()

    # Create renamer and execute
    renamer = CodebaseRenamer(
        dry_run=not args.execute,
        create_backup=args.backup
    )

    renamer.execute_rename()

    sys.exit(0)


if __name__ == '__main__':
    main()
