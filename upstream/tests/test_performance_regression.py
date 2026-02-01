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
    load_baseline,
    save_baseline,
    check_regression,
    parse_locust_csv,
)


class PerformanceRegressionTests(TestCase):
    """Test suite for performance regression detection."""

    def setUp(self):
        """Create temporary files for testing."""
        self.baseline_file = tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".json"
        )
        self.csv_file = tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".csv"
        )

    def tearDown(self):
        """Clean up temporary files."""
        Path(self.baseline_file.name).unlink(missing_ok=True)
        Path(self.csv_file.name).unlink(missing_ok=True)

    def test_load_baseline_missing_file(self):
        """Should return None when baseline file doesn't exist."""
        baseline = load_baseline("/nonexistent/baseline.json")
        self.assertIsNone(baseline)

    def test_save_and_load_baseline(self):
        """Should save and load baseline correctly."""
        metrics = {"p50": 120.0, "p95": 350.0, "error_rate": 0.5}
        save_baseline(self.baseline_file.name, metrics, commit="abc123")

        loaded = load_baseline(self.baseline_file.name)
        self.assertEqual(loaded["metrics"]["p50"], 120.0)
        self.assertEqual(loaded["metrics"]["p95"], 350.0)
        self.assertEqual(loaded["commit"], "abc123")

    def test_regression_detection_passes(self):
        """Should pass when performance is within acceptable range."""
        baseline = {
            "metrics": {
                "p50": 100.0,
                "p95": 300.0,
                "p99": 400.0,
                "error_rate": 1.0,
                "requests_per_sec": 20.0,
            }
        }
        current = {
            "p50": 110.0,  # +10% (acceptable)
            "p95": 330.0,  # +10% (acceptable)
            "p99": 440.0,  # +10% (acceptable)
            "error_rate": 1.5,  # +0.5% (acceptable)
            "requests_per_sec": 18.0,  # -10% (acceptable)
        }

        result = check_regression(current, baseline)
        self.assertTrue(result["passed"])
        self.assertEqual(len(result["failures"]), 0)

    def test_regression_detection_fails_p95(self):
        """Should fail when p95 regresses >20%."""
        baseline = {
            "metrics": {
                "p50": 100.0,
                "p95": 300.0,
                "p99": 400.0,
                "error_rate": 1.0,
                "requests_per_sec": 20.0,
            }
        }
        current = {
            "p50": 110.0,
            "p95": 400.0,  # +33% (FAIL)
            "p99": 500.0,
            "error_rate": 1.5,
            "requests_per_sec": 18.0,
        }

        result = check_regression(current, baseline)
        self.assertFalse(result["passed"])
        self.assertIn("p95", [f["metric"] for f in result["failures"]])

    def test_regression_detection_fails_error_rate(self):
        """Should fail when error rate increases >2%."""
        baseline = {
            "metrics": {
                "p50": 100.0,
                "p95": 300.0,
                "p99": 400.0,
                "error_rate": 1.0,
                "requests_per_sec": 20.0,
            }
        }
        current = {
            "p50": 110.0,
            "p95": 330.0,
            "p99": 440.0,
            "error_rate": 3.5,  # +2.5% (FAIL)
            "requests_per_sec": 18.0,
        }

        result = check_regression(current, baseline)
        self.assertFalse(result["passed"])
        self.assertIn("error_rate", [f["metric"] for f in result["failures"]])

    def test_parse_locust_csv(self):
        """Should parse Locust CSV correctly."""
        # Write CSV with Locust format
        writer = csv.writer(self.csv_file)
        writer.writerow(
            [
                "Type",
                "Name",
                "Request Count",
                "Failure Count",
                "50%",
                "95%",
                "99%",
                "Average Response Time",
                "Requests/s",
            ]
        )
        writer.writerow(
            ["None", "Aggregated", "450", "2", "120", "350", "480", "150", "15.0"]
        )
        self.csv_file.close()

        metrics = parse_locust_csv(self.csv_file.name)
        self.assertEqual(metrics["p50"], 120.0)
        self.assertEqual(metrics["p95"], 350.0)
        self.assertEqual(metrics["p99"], 480.0)
        self.assertAlmostEqual(metrics["error_rate"], 0.44, places=1)  # 2/450*100

    def test_strict_mode_treats_warnings_as_failures(self):
        """Should fail on warnings when strict mode is enabled."""
        baseline = {
            "metrics": {
                "p50": 100.0,
                "p95": 300.0,
                "p99": 400.0,
                "error_rate": 1.0,
                "requests_per_sec": 20.0,
            }
        }
        current = {
            "p50": 125.0,  # +25% (WARNING normally)
            "p95": 330.0,  # +10% (OK)
            "p99": 440.0,  # +10% (OK)
            "error_rate": 1.5,  # +0.5% (OK)
            "requests_per_sec": 18.0,  # -10% (OK)
        }

        # Without strict mode, should pass with warnings
        result = check_regression(current, baseline, strict=False)
        self.assertTrue(result["passed"])
        self.assertEqual(len(result["warnings"]), 1)
        self.assertEqual(len(result["failures"]), 0)

        # With strict mode, should fail
        result_strict = check_regression(current, baseline, strict=True)
        self.assertFalse(result_strict["passed"])
        self.assertEqual(len(result_strict["failures"]), 1)
        self.assertEqual(len(result_strict["warnings"]), 0)

    def test_throughput_regression_warning(self):
        """Should warn when throughput decreases >30%."""
        baseline = {
            "metrics": {
                "p50": 100.0,
                "p95": 300.0,
                "p99": 400.0,
                "error_rate": 1.0,
                "requests_per_sec": 20.0,
            }
        }
        current = {
            "p50": 110.0,
            "p95": 330.0,
            "p99": 440.0,
            "error_rate": 1.5,
            "requests_per_sec": 12.0,  # -40% (WARNING)
        }

        result = check_regression(current, baseline)
        self.assertTrue(result["passed"])  # Only warning, not failure
        self.assertEqual(len(result["warnings"]), 1)
        self.assertIn("requests_per_sec", [w["metric"] for w in result["warnings"]])
