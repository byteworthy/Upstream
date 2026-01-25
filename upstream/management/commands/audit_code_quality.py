"""
Code Quality Auditor Management Command

Scans Django codebase for:
- PHI exposure in code/comments
- Security vulnerabilities
- Linting issues
- Missing customer filters
"""
import ast
import re
import subprocess
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.utils import timezone
from upstream.models_agents import AgentRun, Finding
from upstream.utils import detect_phi


class CodeQualityAuditor:
    """Auditor for code quality, security, and PHI exposure"""

    PHI_PATTERNS = [
        (r"patient[_\s]*name", "patient_name_variable"),
        (r"ssn|social[_\s]*security", "ssn_reference"),
        (r"dob|date[_\s]*of[_\s]*birth", "dob_reference"),
        (r"mrn|medical[_\s]*record", "mrn_reference"),
        (r"\b\d{3}-\d{2}-\d{4}\b", "ssn_pattern"),
    ]

    SECURITY_PATTERNS = [
        (r"cursor\.execute\([^?]*%|cursor\.execute\([^?]*\+", "sql_injection_risk"),
        (r'SECRET_KEY\s*=\s*["\'][^"\']*["\']', "hardcoded_secret"),
        (r'password\s*=\s*["\'][^"\']+["\']', "hardcoded_password"),
        (r'\.raw\(["\'].*%.*["\']', "raw_sql_injection"),
        (r"eval\(", "eval_usage"),
        (r"exec\(", "exec_usage"),
    ]

    CUSTOMER_FILTER_REQUIRED = [
        "ClaimRecord",
        "DriftEvent",
        "Alert",
        "Upload",
        "PayerMapping",
        "Settings",
    ]

    def __init__(self, path=None, fast=False, staged=False):
        self.path = path or settings.BASE_DIR
        self.fast = fast
        self.staged = staged
        self.findings = []
        self.files_scanned = 0

        # Load configuration from settings
        self.config = getattr(settings, "CODE_QUALITY_AUDITOR", {})
        self.phi_config = self.config.get("phi_detection", {})

    def scan(self):
        """Run all scans"""
        print("🔍 Code Quality Auditor")
        print("━" * 50)

        files = self._get_files_to_scan()
        print(f"Scanning {len(files)} Python files...\n")

        for file_path in files:
            self.files_scanned += 1
            self._scan_file(file_path)

        # Run linters
        self._run_black()
        self._run_flake8()
        self._run_django_checks()

        return self.findings

    def _get_files_to_scan(self):
        """Get list of Python files to scan"""
        if self.staged:
            # Get staged files only
            result = subprocess.run(
                ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
                capture_output=True,
                text=True,
            )
            files = [f for f in result.stdout.strip().split("\n") if f.endswith(".py")]
            return [Path(f) for f in files if Path(f).exists()]

        # Scan all Python files
        files = []

        # Scan upstream/ directory
        upstream_dir = settings.BASE_DIR / "upstream"
        if upstream_dir.exists():
            files.extend(upstream_dir.rglob("*.py"))

        # Get excluded paths from configuration
        excluded = self.config.get(
            "excluded_paths",
            [
                "migrations/",
                "__pycache__/",
                "venv/",
                ".venv/",
                "node_modules/",
            ],
        )

        files = [f for f in files if not any(e.rstrip("/") in str(f) for e in excluded)]

        return files

    def _scan_file(self, file_path):
        """Scan a single file"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Scan for PHI
            self._scan_for_phi(file_path, content)

            # Scan for security issues
            self._scan_for_security_issues(file_path, content)

            # Scan for missing customer filters
            self._scan_for_customer_filters(file_path, content)

            # Parse AST for deeper analysis
            try:
                tree = ast.parse(content)
                self._analyze_ast(file_path, tree, content)
            except SyntaxError:
                pass  # Skip files with syntax errors

        except Exception as e:
            print(f"Error scanning {file_path}: {e}")

    def _scan_for_phi(self, file_path, content):
        """Scan for PHI in code and comments"""
        lines = content.split("\n")

        # Get PHI detection configuration
        ignore_variable_names = self.phi_config.get("ignore_variable_names", False)
        ignore_comments = self.phi_config.get("ignore_comments", False)
        only_flag_actual_values = self.phi_config.get("only_flag_actual_values", False)
        whitelist = self.phi_config.get("whitelist", [])

        for line_num, line in enumerate(lines, 1):
            # Skip comments if configured
            if ignore_comments and line.strip().startswith("#"):
                continue

            # Check for PHI patterns
            for pattern, phi_type in self.PHI_PATTERNS:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    # Skip if in test fixtures directory
                    if "fixtures" in str(file_path):
                        continue

                    # Skip whitelisted terms
                    matched_text = match.group(0).lower()
                    if any(wl.lower() in matched_text for wl in whitelist):
                        continue

                    # Skip variable names if configured
                    if (
                        ignore_variable_names
                        and phi_type.endswith("_variable")
                        or phi_type.endswith("_reference")
                    ):
                        continue

                    # If only_flag_actual_values is True, skip pattern names
                    if only_flag_actual_values and phi_type != "ssn_pattern":
                        # Check if it's an actual SSN or just a reference
                        if phi_type in [
                            "ssn_pattern",
                            "dob_reference",
                            "mrn_reference",
                            "patient_name_variable",
                        ]:
                            # Only flag if it looks like actual data
                            if not re.search(
                                r"\b\d{3}-\d{2}-\d{4}\b", line
                            ):  # Not an actual SSN
                                continue

                    # Use upstream PHI detection
                    has_phi, message = detect_phi(line)
                    if has_phi:
                        # Additional whitelist check on the message
                        if any(wl.lower() in message.lower() for wl in whitelist):
                            continue

                        self.findings.append(
                            {
                                "severity": "critical",
                                "category": "phi_exposure",
                                "file_path": str(file_path),
                                "line_number": line_num,
                                "title": f"Potential PHI in code: {phi_type}",
                                "description": message,
                                "code_snippet": line.strip(),
                                "recommendation": (
                                    "Remove PHI or use anonymized "
                                    "identifiers (IDs only)"
                                ),
                            }
                        )

    def _scan_for_security_issues(self, file_path, content):
        """Scan for security vulnerabilities"""
        lines = content.split("\n")

        for line_num, line in enumerate(lines, 1):
            for pattern, issue_type in self.SECURITY_PATTERNS:
                if re.search(pattern, line):
                    severity = "critical" if "injection" in issue_type else "high"

                    self.findings.append(
                        {
                            "severity": severity,
                            "category": "security",
                            "file_path": str(file_path),
                            "line_number": line_num,
                            "title": f"Security issue: {issue_type}",
                            "description": self._get_security_description(issue_type),
                            "code_snippet": line.strip(),
                            "recommendation": self._get_security_recommendation(
                                issue_type
                            ),
                        }
                    )

    def _scan_for_customer_filters(self, file_path, content):
        """Scan for queries missing customer filters"""
        # Skip test files - they intentionally test cross-customer scenarios
        if "test" in str(file_path).lower():
            return

        lines = content.split("\n")

        for line_num, line in enumerate(lines, 1):
            # Check for .objects.all() on customer-scoped models
            for model in self.CUSTOMER_FILTER_REQUIRED:
                if f"{model}.objects.all()" in line:
                    self.findings.append(
                        {
                            "severity": "critical",
                            "category": "multi_tenant_violation",
                            "file_path": str(file_path),
                            "line_number": line_num,
                            "title": f"Missing customer filter on {model}",
                            "description": (
                                f"{model}.objects.all() exposes data "
                                "across all customers"
                            ),
                            "code_snippet": line.strip(),
                            "recommendation": (
                                "Use .filter(customer=customer) instead"
                            ),
                        }
                    )

    def _analyze_ast(self, file_path, tree, content):
        """Analyze AST for deeper issues"""
        for node in ast.walk(tree):
            # Check for missing docstrings on complex functions
            if isinstance(node, ast.FunctionDef):
                if len(node.body) > 10 and not ast.get_docstring(node):
                    self.findings.append(
                        {
                            "severity": "medium",
                            "category": "documentation",
                            "file_path": str(file_path),
                            "line_number": node.lineno,
                            "title": f"Missing docstring on function: {node.name}",
                            "description": "Complex function lacks documentation",
                            "code_snippet": f"def {node.name}(...)",
                            "recommendation": (
                                "Add docstring explaining purpose, " "args, and returns"
                            ),
                        }
                    )

    def _run_black(self):
        """Run Black formatter check"""
        try:
            result = subprocess.run(
                ["black", "--check", "--quiet", "upstream/"],
                capture_output=True,
                text=True,
                cwd=settings.BASE_DIR,
            )

            if result.returncode != 0:
                self.findings.append(
                    {
                        "severity": "low",
                        "category": "formatting",
                        "file_path": "",
                        "line_number": None,
                        "title": "Black formatting issues",
                        "description": "Some files need Black formatting",
                        "code_snippet": result.stdout[:500] if result.stdout else "",
                        "recommendation": "Run: black upstream/",
                    }
                )
        except FileNotFoundError:
            print("⚠️  Black not installed, skipping formatting check")

    def _run_flake8(self):
        """Run Flake8 linter"""
        try:
            result = subprocess.run(
                ["flake8", "upstream/", "--count"],
                capture_output=True,
                text=True,
                cwd=settings.BASE_DIR,
            )

            if result.returncode != 0:
                violations = result.stdout.count("\n")
                self.findings.append(
                    {
                        "severity": "medium",
                        "category": "linting",
                        "file_path": "",
                        "line_number": None,
                        "title": f"Flake8: {violations} style violations",
                        "description": "Code style violations detected",
                        "code_snippet": result.stdout[:500] if result.stdout else "",
                        "recommendation": "Review and fix Flake8 violations",
                    }
                )
        except FileNotFoundError:
            print("⚠️  Flake8 not installed, skipping linting check")

    def _run_django_checks(self):
        """Run Django system checks"""
        from django.core.management import call_command
        from io import StringIO

        output = StringIO()
        try:
            call_command("check", "--deploy", stdout=output, stderr=output)
        except Exception as e:
            self.findings.append(
                {
                    "severity": "high",
                    "category": "django_checks",
                    "file_path": "",
                    "line_number": None,
                    "title": "Django system check failures",
                    "description": str(e),
                    "code_snippet": output.getvalue()[:500],
                    "recommendation": "Fix Django system check issues",
                }
            )

    def _get_security_description(self, issue_type):
        descriptions = {
            "sql_injection_risk": "Raw SQL query vulnerable to injection",
            "hardcoded_secret": "Secret key hardcoded in source code",
            "hardcoded_password": "Password hardcoded in source code",
            "raw_sql_injection": "Raw SQL with string formatting",
            "eval_usage": "Use of eval() is dangerous",
            "exec_usage": "Use of exec() is dangerous",
        }
        return descriptions.get(issue_type, "Security vulnerability detected")

    def _get_security_recommendation(self, issue_type):
        recommendations = {
            "sql_injection_risk": "Use Django ORM with parameterized queries",
            "hardcoded_secret": "Use os.getenv() or Secret Manager",
            "hardcoded_password": "Use environment variables",
            "raw_sql_injection": "Use Django ORM or parameterized queries",
            "eval_usage": "Avoid eval(), use ast.literal_eval() or alternatives",
            "exec_usage": "Avoid exec(), refactor to use functions",
        }
        return recommendations.get(issue_type, "Fix security issue")


class Command(BaseCommand):
    help = "Audit code quality, security, and PHI exposure"

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            type=str,
            help="Path to scan (default: entire project)",
        )
        parser.add_argument(
            "--fast",
            action="store_true",
            help="Fast mode: scan only changed files",
        )
        parser.add_argument(
            "--staged",
            action="store_true",
            help="Scan only staged files (for pre-commit)",
        )
        parser.add_argument(
            "--fail-on",
            choices=["critical", "high", "medium", "low"],
            default="critical",
            help="Exit with error if findings at this level or higher",
        )
        parser.add_argument(
            "--report",
            type=str,
            help="Save report to JSON file",
        )

    def handle(self, *args, **options):
        # Create agent run
        agent_run = AgentRun.objects.create(
            agent_type="code_quality",
            trigger="manual",
            status="running",
            git_branch=self._get_git_branch(),
            git_commit=self._get_git_commit(),
        )

        try:
            # Run auditor
            auditor = CodeQualityAuditor(
                path=options["path"], fast=options["fast"], staged=options["staged"]
            )
            findings = auditor.scan()

            # Save findings to database
            severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}

            for finding_data in findings:
                severity = finding_data.get("severity", "medium")
                severity_counts[severity] = severity_counts.get(severity, 0) + 1

                Finding.objects.create(
                    agent_run=agent_run,
                    severity=severity,
                    category=finding_data["category"],
                    title=finding_data["title"],
                    description=finding_data["description"],
                    file_path=finding_data.get("file_path", ""),
                    line_number=finding_data.get("line_number"),
                    code_snippet=finding_data.get("code_snippet", ""),
                    recommendation=finding_data.get("recommendation", ""),
                )

            # Update agent run
            agent_run.completed_at = timezone.now()
            agent_run.status = "completed"
            agent_run.findings_count = len(findings)
            agent_run.critical_count = severity_counts.get("critical", 0)
            agent_run.high_count = severity_counts.get("high", 0)
            agent_run.medium_count = severity_counts.get("medium", 0)
            agent_run.low_count = severity_counts.get("low", 0)
            agent_run.save()

            # Print summary
            self._print_summary(findings, auditor.files_scanned)

            # Check fail condition
            fail_level = options["fail_on"]
            should_fail = self._should_fail(findings, fail_level)

            if should_fail:
                self.stdout.write(
                    self.style.ERROR(
                        f"\n❌ COMMIT BLOCKED - Fix {fail_level} or higher issues first"
                    )
                )
                raise CommandError("Code quality check failed")
            else:
                self.stdout.write(self.style.SUCCESS("\n✅ Code quality check passed"))

        except Exception as e:
            agent_run.status = "failed"
            agent_run.completed_at = timezone.now()
            agent_run.summary = str(e)
            agent_run.save()
            raise

    def _print_summary(self, findings, files_scanned):
        """Print findings summary"""
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}

        for finding in findings:
            severity = finding.get("severity", "medium")
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

        print("\n" + "━" * 50)
        print(f"Files scanned: {files_scanned}")
        print(f"❌ {severity_counts['critical']} critical")
        print(f"⚠️  {severity_counts['high']} high")
        print(f"ℹ️  {severity_counts['medium']} medium")
        print(f"💡 {severity_counts['low']} low")
        print("━" * 50)

        # Print critical issues
        if severity_counts["critical"] > 0:
            print("\n❌ CRITICAL ISSUES:")
            for finding in findings:
                if finding.get("severity") == "critical":
                    file_path = finding.get("file_path", "unknown")
                    line = finding.get("line_number", "?")
                    title = finding.get("title", "Unknown issue")
                    print(f"  {file_path}:{line} - {title}")

    def _should_fail(self, findings, fail_level):
        """Check if should fail based on severity"""
        severity_order = ["low", "medium", "high", "critical"]
        fail_index = severity_order.index(fail_level)

        for finding in findings:
            severity = finding.get("severity", "medium")
            if severity_order.index(severity) >= fail_index:
                return True

        return False

    def _get_git_branch(self):
        """Get current git branch"""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
            )
            return result.stdout.strip()
        except Exception:
            return ""

    def _get_git_commit(self):
        """Get current git commit hash"""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True
            )
            return result.stdout.strip()
        except Exception:
            return ""
