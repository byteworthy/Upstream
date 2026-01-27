"""
Service Layer Tests

Comprehensive tests for DataQualityService, ReportGenerationService,
and AlertProcessingService.

Tests services in isolation with mock data - no database dependencies.
"""

import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock

from upstream.services.data_quality import DataQualityService
from upstream.services.report_generation import ReportGenerationService
from upstream.services.alert_processing import AlertProcessingService


# ============================================================================
# DataQualityService Tests (10 tests)
# ============================================================================


class TestDataQualityService:
    """Tests for DataQualityService validation methods."""

    def test_validate_upload_format_valid_csv(self):
        """Test valid CSV file passes validation."""
        mock_file = Mock()
        mock_file.size = 1024 * 1024  # 1MB

        result = DataQualityService.validate_upload_format(mock_file, "data.csv")

        assert result["valid"] is True
        assert len(result["errors"]) == 0
        assert result["file_size_mb"] == pytest.approx(1.0)

    def test_validate_upload_format_file_too_large(self):
        """Test file size limit enforcement."""
        mock_file = Mock()
        mock_file.size = 101 * 1024 * 1024  # 101MB

        result = DataQualityService.validate_upload_format(mock_file, "data.csv")

        assert result["valid"] is False
        assert any("too large" in err.lower() for err in result["errors"])

    def test_validate_upload_format_invalid_extension(self):
        """Test file extension validation."""
        mock_file = Mock()
        mock_file.size = 1024

        result = DataQualityService.validate_upload_format(mock_file, "data.xlsx")

        assert result["valid"] is False
        assert any("csv" in err.lower() for err in result["errors"])

    def test_validate_claim_data_valid_row(self):
        """Test valid claim row passes validation."""
        claim_row = {
            "payer": "Blue Cross",
            "cpt": "99213",
            "submitted_date": "2024-01-01",
            "decided_date": "2024-01-05",
            "outcome": "PAID",
            "allowed_amount": "150.00",
        }

        errors = DataQualityService.validate_claim_data(claim_row, 1)

        assert len(errors) == 0

    def test_validate_claim_data_missing_required_field(self):
        """Test missing required field validation."""
        claim_row = {
            "payer": "Aetna",
            "cpt": "99213"
            # Missing submitted_date, decided_date, outcome
        }

        errors = DataQualityService.validate_claim_data(claim_row, 2)

        assert len(errors) >= 3
        assert any("submitted_date" in err for err in errors)

    def test_validate_claim_data_phi_detection(self):
        """Test PHI detection in payer field."""
        claim_row = {
            "payer": "John Smith",  # Looks like patient name
            "cpt": "99213",
            "submitted_date": "2024-01-01",
            "decided_date": "2024-01-05",
            "outcome": "PAID",
        }

        errors = DataQualityService.validate_claim_data(claim_row, 3)

        assert len(errors) > 0
        assert any("privacy" in err.lower() or "phi" in err.lower() for err in errors)

    def test_validate_claim_data_invalid_outcome(self):
        """Test invalid outcome value validation."""
        claim_row = {
            "payer": "Medicare",
            "cpt": "99213",
            "submitted_date": "2024-01-01",
            "decided_date": "2024-01-05",
            "outcome": "MAYBE",  # Invalid
        }

        errors = DataQualityService.validate_claim_data(claim_row, 4)

        assert len(errors) > 0
        assert any("outcome" in err.lower() for err in errors)

    def test_validate_claim_data_negative_amount(self):
        """Test negative amount validation."""
        claim_row = {
            "payer": "Cigna",
            "cpt": "99213",
            "submitted_date": "2024-01-01",
            "decided_date": "2024-01-05",
            "outcome": "PAID",
            "allowed_amount": "-50.00",
        }

        errors = DataQualityService.validate_claim_data(claim_row, 5)

        assert len(errors) > 0
        assert any("negative" in err.lower() for err in errors)

    def test_compute_data_quality_score_perfect(self):
        """Test quality score calculation for perfect data."""
        score = DataQualityService.compute_data_quality_score(
            total_rows=100, accepted_rows=100, rejected_rows=0
        )

        assert score == 1.0

    def test_compute_data_quality_score_partial(self):
        """Test quality score calculation for partial acceptance."""
        score = DataQualityService.compute_data_quality_score(
            total_rows=100, accepted_rows=95, rejected_rows=5
        )

        assert score == 0.95

    def test_compute_data_quality_score_zero_rows(self):
        """Test quality score with zero rows."""
        score = DataQualityService.compute_data_quality_score(
            total_rows=0, accepted_rows=0, rejected_rows=0
        )

        assert score == 0.0

    def test_flag_suspicious_patterns_high_payer_concentration(self):
        """Test detection of high payer concentration."""
        claims = [{"payer": "PayerA", "outcome": "PAID"} for _ in range(85)] + [
            {"payer": "PayerB", "outcome": "PAID"} for _ in range(15)
        ]

        patterns = DataQualityService.flag_suspicious_patterns(
            claims, min_pattern_count=10
        )

        assert len(patterns) > 0
        concentration_patterns = [
            p for p in patterns if p["pattern_type"] == "high_payer_concentration"
        ]
        assert len(concentration_patterns) > 0

    def test_flag_suspicious_patterns_high_denial_rate(self):
        """Test detection of high denial rate."""
        claims = [{"payer": "TestPayer", "outcome": "DENIED"} for _ in range(60)] + [
            {"payer": "TestPayer", "outcome": "PAID"} for _ in range(40)
        ]

        patterns = DataQualityService.flag_suspicious_patterns(
            claims, min_pattern_count=10
        )

        denial_patterns = [
            p for p in patterns if p["pattern_type"] == "high_denial_rate"
        ]
        assert len(denial_patterns) > 0
        assert denial_patterns[0]["severity"] == "high"

    def test_flag_suspicious_patterns_zero_amounts(self):
        """Test detection of zero allowed amounts."""
        claims = [
            {"payer": "TestPayer", "outcome": "PAID", "allowed_amount": Decimal("0.00")}
            for _ in range(15)
        ]

        patterns = DataQualityService.flag_suspicious_patterns(
            claims, min_pattern_count=10
        )

        zero_patterns = [
            p for p in patterns if p["pattern_type"] == "zero_allowed_amounts"
        ]
        assert len(zero_patterns) > 0


# ============================================================================
# ReportGenerationService Tests (10 tests)
# ============================================================================


class TestReportGenerationService:
    """Tests for ReportGenerationService report generation methods."""

    def test_generate_payer_summary_empty_claims(self):
        """Test payer summary with no claims."""
        summary = ReportGenerationService.generate_payer_summary(
            customer_id=1,
            date_range=(date(2024, 1, 1), date(2024, 1, 31)),
            claim_records=[],
        )

        assert summary["total_claims"] == 0
        assert len(summary["payers"]) == 0
        assert summary["overall_approval_rate"] == 0.0

    def test_generate_payer_summary_single_payer(self):
        """Test payer summary with single payer."""
        claims = [{"payer": "Aetna", "outcome": "PAID"} for _ in range(8)] + [
            {"payer": "Aetna", "outcome": "DENIED"} for _ in range(2)
        ]

        summary = ReportGenerationService.generate_payer_summary(
            customer_id=1,
            date_range=(date(2024, 1, 1), date(2024, 1, 31)),
            claim_records=claims,
        )

        assert summary["total_claims"] == 10
        assert len(summary["payers"]) == 1
        assert summary["payers"][0]["payer_name"] == "Aetna"
        assert summary["payers"][0]["approval_rate"] == 80.0

    def test_generate_payer_summary_multiple_payers(self):
        """Test payer summary with multiple payers."""
        claims = (
            [{"payer": "Aetna", "outcome": "PAID"} for _ in range(10)]
            + [{"payer": "Cigna", "outcome": "PAID"} for _ in range(5)]
            + [{"payer": "Medicare", "outcome": "DENIED"} for _ in range(3)]
        )

        summary = ReportGenerationService.generate_payer_summary(
            customer_id=1,
            date_range=(date(2024, 1, 1), date(2024, 1, 31)),
            claim_records=claims,
        )

        assert summary["total_claims"] == 18
        assert len(summary["payers"]) == 3
        # Should be sorted by count descending
        assert summary["payers"][0]["payer_name"] == "Aetna"

    def test_generate_drift_report_empty_events(self):
        """Test drift report with no events."""
        report = ReportGenerationService.generate_drift_report(
            customer_id=1, drift_events=[]
        )

        assert report["total_events"] == 0
        assert "no drift events" in report["summary_text"].lower()

    def test_generate_drift_report_with_filters(self):
        """Test drift report with severity filter."""
        events = [
            {"payer": "Aetna", "severity": 0.9, "drift_type": "DENIAL_RATE"},
            {"payer": "Cigna", "severity": 0.5, "drift_type": "DENIAL_RATE"},
            {"payer": "Medicare", "severity": 0.3, "drift_type": "DENIAL_RATE"},
        ]

        report = ReportGenerationService.generate_drift_report(
            customer_id=1, filters={"min_severity": 0.7}, drift_events=events
        )

        assert report["total_events"] == 1  # Only severity >= 0.7

    def test_generate_drift_report_severity_categorization(self):
        """Test drift events are categorized by severity."""
        events = [
            {"severity": 0.9, "drift_type": "DENIAL_RATE", "payer": "A"},  # high
            {"severity": 0.6, "drift_type": "DENIAL_RATE", "payer": "B"},  # medium
            {"severity": 0.2, "drift_type": "DENIAL_RATE", "payer": "C"},  # low
        ]

        report = ReportGenerationService.generate_drift_report(
            customer_id=1, drift_events=events
        )

        assert report["events_by_severity"]["high"] == 1
        assert report["events_by_severity"]["medium"] == 1
        assert report["events_by_severity"]["low"] == 1

    def test_generate_drift_report_critical_events(self):
        """Test critical events are identified."""
        events = [
            {
                "severity": 0.95,
                "drift_type": "DENIAL_RATE",
                "payer": "Aetna",
                "delta_value": 0.2,
            },
            {
                "severity": 0.5,
                "drift_type": "DENIAL_RATE",
                "payer": "Cigna",
                "delta_value": 0.1,
            },
        ]

        report = ReportGenerationService.generate_drift_report(
            customer_id=1, drift_events=events
        )

        assert len(report["critical_events"]) == 1
        assert report["critical_events"][0]["severity"] == 0.95

    def test_generate_recovery_stats_empty_claims(self):
        """Test recovery stats with no claims."""
        stats = ReportGenerationService.generate_recovery_stats(
            customer_id=1, claim_records=[]
        )

        assert stats["total_billed"] == Decimal("0.00")
        assert stats["recovery_rate"] == 0.0

    def test_generate_recovery_stats_full_recovery(self):
        """Test recovery stats with full payment recovery."""
        claims = [
            {
                "billed_amount": "100.00",
                "allowed_amount": "80.00",
                "paid_amount": "80.00",
            }
            for _ in range(5)
        ]

        stats = ReportGenerationService.generate_recovery_stats(
            customer_id=1, claim_records=claims
        )

        assert stats["total_billed"] == Decimal("500.00")
        assert stats["total_paid"] == Decimal("400.00")
        assert stats["recovery_rate"] == 80.0

    def test_generate_recovery_stats_underpayments(self):
        """Test detection of underpayments."""
        claims = [
            {
                "billed_amount": "100.00",
                "allowed_amount": "80.00",
                "paid_amount": "70.00",  # Underpaid by $10
            }
            for _ in range(3)
        ]

        stats = ReportGenerationService.generate_recovery_stats(
            customer_id=1, claim_records=claims
        )

        assert stats["underpayment_count"] == 3
        assert stats["underpayment_amount"] == Decimal("30.00")

    def test_format_report_for_export_pdf(self):
        """Test formatting report for PDF export."""
        report_data = {
            "report_type": "payer_summary",
            "payers": [{"payer_name": "Aetna", "total_claims": 10}],
        }

        export_data = ReportGenerationService.format_report_for_export(
            report_data, "pdf"
        )

        assert export_data["format"] == "pdf"
        assert "title" in export_data
        assert len(export_data["sections"]) > 0

    def test_format_report_for_export_invalid_format(self):
        """Test error handling for invalid export format."""
        with pytest.raises(ValueError):
            ReportGenerationService.format_report_for_export(
                {"report_type": "test"}, "invalid"
            )


# ============================================================================
# AlertProcessingService Tests (10 tests)
# ============================================================================


class TestAlertProcessingService:
    """Tests for AlertProcessingService alert processing methods."""

    def test_evaluate_alert_rules_no_triggers(self):
        """Test no alerts triggered when below threshold."""
        events = [{"id": 1, "severity": 0.3, "drift_type": "DENIAL_RATE"}]
        rules = [{"id": 1, "enabled": True, "threshold_value": 0.7}]

        alerts = AlertProcessingService.evaluate_alert_rules(events, rules)

        assert len(alerts) == 0

    def test_evaluate_alert_rules_threshold_trigger(self):
        """Test alert triggered when threshold exceeded."""
        events = [
            {"id": 1, "payer": "Aetna", "severity": 0.9, "drift_type": "DENIAL_RATE"}
        ]
        rules = [
            {"id": 1, "name": "High Severity", "enabled": True, "threshold_value": 0.7}
        ]

        alerts = AlertProcessingService.evaluate_alert_rules(events, rules)

        assert len(alerts) == 1
        assert alerts[0]["rule_id"] == 1
        assert alerts[0]["severity"] == 0.9

    def test_evaluate_alert_rules_disabled_rule(self):
        """Test disabled rules don't trigger."""
        events = [{"id": 1, "severity": 0.9, "drift_type": "DENIAL_RATE"}]
        rules = [{"id": 1, "enabled": False, "threshold_value": 0.5}]

        alerts = AlertProcessingService.evaluate_alert_rules(events, rules)

        assert len(alerts) == 0

    def test_evaluate_alert_rules_drift_type_filter(self):
        """Test drift type filtering in rules."""
        events = [
            {"id": 1, "severity": 0.9, "drift_type": "DENIAL_RATE"},
            {"id": 2, "severity": 0.9, "drift_type": "PAYMENT_AMOUNT"},
        ]
        rules = [
            {
                "id": 1,
                "enabled": True,
                "threshold_value": 0.5,
                "drift_type_filter": "DENIAL_RATE",
            }
        ]

        alerts = AlertProcessingService.evaluate_alert_rules(events, rules)

        assert len(alerts) == 1  # Only DENIAL_RATE event

    def test_process_alert_delivery_disabled_channel(self):
        """Test disabled channels are skipped."""
        alert = {"id": 1, "severity": 0.8, "payload": {}}
        channels = [{"id": 1, "type": "email", "enabled": False}]

        deliveries = AlertProcessingService.process_alert_delivery(alert, channels)

        assert len(deliveries) == 1
        assert deliveries[0]["status"] == "skipped"
        assert "disabled" in deliveries[0]["skip_reason"].lower()

    def test_process_alert_delivery_multiple_channels(self):
        """Test delivery to multiple channels."""
        alert = {"id": 1, "severity": 0.8, "payload": {"payer": "Aetna"}}
        channels = [
            {"id": 1, "type": "email", "enabled": True},
            {"id": 2, "type": "slack", "enabled": True},
        ]

        deliveries = AlertProcessingService.process_alert_delivery(alert, channels)

        assert len(deliveries) == 2
        assert all(d["status"] == "pending" for d in deliveries)

    def test_compute_alert_priority_high_severity(self):
        """Test priority calculation for high severity."""
        alert_data = {
            "severity": 0.9,
            "delta_value": 0.2,
            "baseline_value": 0.5,
            "drift_type": "DENIAL_RATE",
        }

        priority = AlertProcessingService.compute_alert_priority(alert_data)

        assert priority >= 8  # High severity + critical type

    def test_compute_alert_priority_low_severity(self):
        """Test priority calculation for low severity."""
        alert_data = {
            "severity": 0.2,
            "delta_value": 0.05,
            "baseline_value": 0.5,
            "drift_type": "OTHER",
        }

        priority = AlertProcessingService.compute_alert_priority(alert_data)

        assert priority <= 3

    def test_compute_alert_priority_persistent_issue(self):
        """Test priority boost for persistent issues."""
        alert_data = {
            "severity": 0.5,
            "delta_value": 0.1,
            "baseline_value": 0.5,
            "consecutive_periods": 3,
        }

        priority = AlertProcessingService.compute_alert_priority(alert_data)

        # Should get +2 boost for 3 consecutive periods
        assert priority >= 5

    def test_should_suppress_alert_cooldown(self):
        """Test cooldown suppression."""
        alert = {
            "product_name": "DriftWatch",
            "signal_type": "DENIAL_RATE",
            "entity_label": "Aetna",
        }

        recent_time = (datetime.now() - timedelta(hours=2)).isoformat()
        history = [
            {
                "status": "sent",
                "notification_sent_at": recent_time,
                "payload": {
                    "product_name": "DriftWatch",
                    "signal_type": "DENIAL_RATE",
                    "entity_label": "Aetna",
                },
                "operator_judgments": [],
            }
        ]

        decision = AlertProcessingService.should_suppress_alert(
            alert, history, cooldown_hours=4
        )

        assert decision["suppressed"] is True
        assert decision["reason"] == "cooldown"

    def test_should_suppress_alert_noise_pattern(self):
        """Test noise pattern suppression."""
        alert = {
            "product_name": "DriftWatch",
            "signal_type": "DENIAL_RATE",
            "entity_label": "Aetna",
        }

        # Create history with 3 noise judgments within window
        recent_time = (datetime.now() - timedelta(days=3)).isoformat()
        history = [
            {
                "payload": {
                    "product_name": "DriftWatch",
                    "signal_type": "DENIAL_RATE",
                    "entity_label": "Aetna",
                },
                "operator_judgments": [{"verdict": "noise", "created_at": recent_time}],
            }
            for _ in range(3)
        ]

        decision = AlertProcessingService.should_suppress_alert(
            alert, history, noise_threshold=3
        )

        assert decision["suppressed"] is True
        assert decision["reason"] == "noise_pattern"

    def test_should_suppress_alert_no_suppression(self):
        """Test no suppression when conditions not met."""
        alert = {
            "product_name": "DriftWatch",
            "signal_type": "DENIAL_RATE",
            "entity_label": "Aetna",
        }

        decision = AlertProcessingService.should_suppress_alert(
            alert, [], cooldown_hours=4
        )

        assert decision["suppressed"] is False
        assert decision["reason"] is None
