---
phase: quick-029
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - upstream/tests/test_performance_regression.py
  - scripts/check_performance_regression.py
  - .github/workflows/ci.yml
autonomous: true

must_haves:
  truths:
    - "CI fails when p95 latency regresses >20% from baseline"
    - "CI fails when error rate increases >2% from baseline"
    - "Baseline metrics stored in version control"
    - "Performance results automatically compared to baseline on every test run"
  artifacts:
    - path: "upstream/tests/test_performance_regression.py"
      provides: "Django test case for regression detection"
      min_lines: 80
    - path: "scripts/check_performance_regression.py"
      provides: "CLI script for CI integration"
      exports: ["check_regression", "load_baseline", "save_baseline"]
    - path: "perf_baseline.json"
      provides: "Historical baseline metrics"
      contains: "p50, p95, p99, error_rate"
  key_links:
    - from: ".github/workflows/ci.yml"
      to: "scripts/check_performance_regression.py"
      via: "invoked after Locust run"
      pattern: "python scripts/check_performance_regression.py"
    - from: "scripts/check_performance_regression.py"
      to: "perf_results_stats.csv"
      via: "reads Locust CSV output"
      pattern: "perf_results_stats.csv"
    - from: "scripts/check_performance_regression.py"
      to: "perf_baseline.json"
      via: "loads historical baseline"
      pattern: "json.load.*perf_baseline"
---

<objective>
Add automated performance regression detection that compares current Locust test results against historical baselines and fails CI when performance degrades significantly.

Purpose: Catch performance regressions early in CI before they reach production, using historical metrics as the baseline for comparison rather than fixed thresholds.

Output: Regression detection script, baseline storage, and CI integration that validates performance hasn't degraded >20% for latency or >2% for error rates.
</objective>

<execution_context>
@/home/codespace/.claude/get-shit-done/workflows/execute-plan.md
@/home/codespace/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md

# Existing performance testing infrastructure
@upstream/tests_performance.py
@.github/workflows/ci.yml
@locustfile.py
</context>

<tasks>

<task type="auto">
  <name>Create baseline storage and regression detection script</name>
  <files>
scripts/check_performance_regression.py
perf_baseline.json
  </files>
  <action>
Create `scripts/check_performance_regression.py` that:
- Reads Locust CSV results from `perf_results_stats.csv` (Aggregated row)
- Loads baseline metrics from `perf_baseline.json` if exists
- Compares current vs baseline with thresholds:
  - p50 regression > 20%: WARNING
  - p95 regression > 20%: FAIL
  - p99 regression > 25%: WARNING
  - Error rate increase > 2%: FAIL
  - Throughput decrease > 30%: WARNING
- If no baseline exists, save current run as baseline (bootstrap mode)
- Outputs comparison table showing current vs baseline vs % change
- Exit code 1 on FAIL, 0 on PASS/WARNING
- Include `--update-baseline` flag to manually update baseline after legitimate changes
- Include `--strict` flag to treat warnings as failures

CLI usage:
```bash
# Normal CI check (fails on regression)
python scripts/check_performance_regression.py perf_results_stats.csv

# Bootstrap initial baseline
python scripts/check_performance_regression.py perf_results_stats.csv --update-baseline

# Strict mode (treat warnings as failures)
python scripts/check_performance_regression.py perf_results_stats.csv --strict
```

Create initial `perf_baseline.json` with structure:
```json
{
  "version": "1.0",
  "timestamp": "2026-01-27T00:00:00Z",
  "commit": "abc123",
  "metrics": {
    "p50": 120.0,
    "p95": 350.0,
    "p99": 480.0,
    "avg_response_time": 150.0,
    "requests_per_sec": 15.0,
    "error_rate": 0.5,
    "total_requests": 450
  },
  "notes": "Initial baseline from Phase 5 completion"
}
```

Use realistic baseline values from Phase 5 (p95 ~350ms, error rate <1%). Script should handle missing baseline gracefully.
  </action>
  <verify>
```bash
# Verify script exists and is executable
python scripts/check_performance_regression.py --help

# Test with mock data
echo "Type,Name,Request Count,Failure Count,Median Response Time,Average Response Time,Min Response Time,Max Response Time,Average Content Size,Requests/s,Failures/s,50%,66%,75%,80%,90%,95%,98%,99%,99.9%,99.99%,100%" > test_results.csv
echo "None,Aggregated,450,2,120,150,45,890,1024,15.0,0.066,120,180,220,250,300,350,420,480,650,890,890" >> test_results.csv
python scripts/check_performance_regression.py test_results.csv
```
  </verify>
  <done>
- `scripts/check_performance_regression.py` exists with load_baseline(), save_baseline(), check_regression() functions
- `perf_baseline.json` exists with initial Phase 5 baseline metrics
- Script reads Locust CSV, compares to baseline, exits with appropriate code
- `--update-baseline` flag creates/updates baseline file
- `--strict` flag treats warnings as failures
  </done>
</task>

<task type="auto">
  <name>Integrate regression detection into CI workflow</name>
  <files>
.github/workflows/ci.yml
  </files>
  <action>
In `.github/workflows/ci.yml`, update the `performance` job to replace the existing "Check performance thresholds" step with regression detection:

Replace this step (lines ~124-155):
```yaml
- name: Check performance thresholds
  run: |
    # Parse CSV results and check p95 < 500ms
    python -c "..."
```

With:
```yaml
- name: Check performance regression
  run: |
    python scripts/check_performance_regression.py perf_results_stats.csv
  continue-on-error: false

- name: Show performance comparison
  if: always()
  run: |
    echo "Performance Baseline Comparison:"
    python scripts/check_performance_regression.py perf_results_stats.csv --verbose || true
```

Keep the existing "Upload performance results" step (lines 157-163) unchanged.

Add comment above new step explaining:
```yaml
# Compare against baseline (perf_baseline.json) - fails if p95 regresses >20% or errors increase >2%
```

This replaces the hardcoded threshold check (p95 < 500ms) with baseline comparison, enabling detection of gradual performance degradation over time.
  </action>
  <verify>
```bash
# Verify CI workflow syntax
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"

# Verify regression check is in CI
grep -A 2 "Check performance regression" .github/workflows/ci.yml

# Verify baseline file is tracked
git ls-files | grep perf_baseline.json
```
  </verify>
  <done>
- CI workflow calls `check_performance_regression.py` instead of inline Python threshold check
- Workflow fails on regression detection (p95 >20% slower or error rate >2% higher)
- Performance comparison shown in CI logs via --verbose flag
- `perf_baseline.json` committed to version control for consistent baselines
  </done>
</task>

<task type="auto">
  <name>Add Django test case for regression detection logic</name>
  <files>
upstream/tests/test_performance_regression.py
  </files>
  <action>
Create `upstream/tests/test_performance_regression.py` with Django TestCase that validates the regression detection logic:

```python
"""
Tests for performance regression detection.

Validates that the regression detection script correctly identifies
performance degradations by comparing current metrics against baselines.
"""

from django.test import TestCase
import json
import tempfile
import csv
from pathlib import Path
import sys

# Import from scripts/ directory
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scripts.check_performance_regression import (
    load_baseline, save_baseline, check_regression, parse_locust_csv
)


class PerformanceRegressionTests(TestCase):
    """Test suite for performance regression detection."""

    def setUp(self):
        """Create temporary files for testing."""
        self.baseline_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.csv_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv')

    def tearDown(self):
        """Clean up temporary files."""
        Path(self.baseline_file.name).unlink(missing_ok=True)
        Path(self.csv_file.name).unlink(missing_ok=True)

    def test_load_baseline_missing_file(self):
        """Should return None when baseline file doesn't exist."""
        baseline = load_baseline('/nonexistent/baseline.json')
        self.assertIsNone(baseline)

    def test_save_and_load_baseline(self):
        """Should save and load baseline correctly."""
        metrics = {
            'p50': 120.0,
            'p95': 350.0,
            'error_rate': 0.5
        }
        save_baseline(self.baseline_file.name, metrics, commit='abc123')

        loaded = load_baseline(self.baseline_file.name)
        self.assertEqual(loaded['metrics']['p50'], 120.0)
        self.assertEqual(loaded['metrics']['p95'], 350.0)
        self.assertEqual(loaded['commit'], 'abc123')

    def test_regression_detection_passes(self):
        """Should pass when performance is within acceptable range."""
        baseline = {
            'metrics': {
                'p50': 100.0,
                'p95': 300.0,
                'error_rate': 1.0
            }
        }
        current = {
            'p50': 110.0,  # +10% (acceptable)
            'p95': 330.0,  # +10% (acceptable)
            'error_rate': 1.5  # +0.5% (acceptable)
        }

        result = check_regression(current, baseline)
        self.assertTrue(result['passed'])
        self.assertEqual(len(result['failures']), 0)

    def test_regression_detection_fails_p95(self):
        """Should fail when p95 regresses >20%."""
        baseline = {
            'metrics': {
                'p50': 100.0,
                'p95': 300.0,
                'error_rate': 1.0
            }
        }
        current = {
            'p50': 110.0,
            'p95': 400.0,  # +33% (FAIL)
            'error_rate': 1.5
        }

        result = check_regression(current, baseline)
        self.assertFalse(result['passed'])
        self.assertIn('p95', [f['metric'] for f in result['failures']])

    def test_regression_detection_fails_error_rate(self):
        """Should fail when error rate increases >2%."""
        baseline = {
            'metrics': {
                'p50': 100.0,
                'p95': 300.0,
                'error_rate': 1.0
            }
        }
        current = {
            'p50': 110.0,
            'p95': 330.0,
            'error_rate': 3.5  # +2.5% (FAIL)
        }

        result = check_regression(current, baseline)
        self.assertFalse(result['passed'])
        self.assertIn('error_rate', [f['metric'] for f in result['failures']])

    def test_parse_locust_csv(self):
        """Should parse Locust CSV correctly."""
        # Write CSV with Locust format
        writer = csv.writer(self.csv_file)
        writer.writerow(['Type', 'Name', 'Request Count', 'Failure Count', '50%', '95%', '99%', 'Average Response Time', 'Requests/s'])
        writer.writerow(['None', 'Aggregated', '450', '2', '120', '350', '480', '150', '15.0'])
        self.csv_file.close()

        metrics = parse_locust_csv(self.csv_file.name)
        self.assertEqual(metrics['p50'], 120.0)
        self.assertEqual(metrics['p95'], 350.0)
        self.assertEqual(metrics['p99'], 480.0)
        self.assertAlmostEqual(metrics['error_rate'], 0.44, places=1)  # 2/450*100
```

Test covers:
- Baseline loading (missing file returns None)
- Baseline saving/loading roundtrip
- Regression detection passes (within thresholds)
- Regression detection fails (p95 >20%)
- Regression detection fails (error rate >2%)
- CSV parsing from Locust output format
  </action>
  <verify>
```bash
# Run regression tests
python manage.py test upstream.tests.test_performance_regression -v2

# Verify all tests pass
python manage.py test upstream.tests.test_performance_regression --failfast
```
  </verify>
  <done>
- `upstream/tests/test_performance_regression.py` exists with 6+ test methods
- Tests validate baseline loading, saving, regression detection pass/fail scenarios
- Tests cover CSV parsing from Locust output format
- All tests pass when run via `manage.py test`
  </done>
</task>

</tasks>

<verification>
**Automated validation:**
```bash
# 1. Run Django tests for regression detection logic
python manage.py test upstream.tests.test_performance_regression

# 2. Test script with mock baseline (should pass)
python scripts/check_performance_regression.py perf_results_stats.csv --verbose

# 3. Test baseline update functionality
python scripts/check_performance_regression.py perf_results_stats.csv --update-baseline

# 4. Verify CI workflow syntax
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
```

**Integration check:**
- CI performance job uses new regression detection instead of hardcoded thresholds
- Baseline file tracked in git for consistent comparison across runs
- Script handles missing baseline gracefully (bootstrap mode)
</verification>

<success_criteria>
**Measurable outcomes:**
- [ ] Script detects p95 regressions >20% and exits with code 1
- [ ] Script detects error rate increases >2% and exits with code 1
- [ ] Baseline stored in version control (`perf_baseline.json`)
- [ ] CI workflow integrated with regression check replacing hardcoded thresholds
- [ ] Django tests validate regression detection logic (6+ tests, all pass)
- [ ] `--update-baseline` flag allows manual baseline updates after legitimate changes

**Observable behavior:**
- CI fails when performance degrades significantly from baseline
- Developers can see performance comparison in CI logs
- Baseline can be updated after intentional performance improvements or infrastructure changes
</success_criteria>

<output>
After completion, create `.planning/quick/029-add-performance-regression-tests-crea/029-SUMMARY.md`
</output>
