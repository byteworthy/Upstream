"""
Tests for Evidence Payload Service.

Testing coverage for alert interpretation and evidence payload building.
Addresses Phase 2 Technical Debt: Missing tests for EvidencePayload.
"""

from django.test import TestCase
from unittest.mock import Mock
from datetime import date

from upstream.services.evidence_payload import (
    get_alert_interpretation,
    _normalize_severity,
    _normalize_delta,
    _calculate_urgency,
    _generate_plain_language,
    _generate_action_steps,
    _generate_historical_context,
    _format_date_range,
    build_denialscope_evidence_payload,
    build_driftwatch_evidence_payload,
)
from upstream.constants import (
    SEVERITY_THRESHOLD_CRITICAL,
    SEVERITY_THRESHOLD_MEDIUM,
    SEVERITY_THRESHOLD_LOW,
    ALERT_HIGH_URGENCY_DELTA,
    ALERT_MEDIUM_URGENCY_DELTA,
)


class NormalizeFunctionsTestCase(TestCase):
    """Tests for normalization utility functions."""

    def test_normalize_severity_float(self):
        """Test that float severity values are returned as-is."""
        self.assertEqual(_normalize_severity(0.8), 0.8)
        self.assertEqual(_normalize_severity(0.5), 0.5)
        self.assertEqual(_normalize_severity(0.0), 0.0)
        self.assertEqual(_normalize_severity(1.0), 1.0)

    def test_normalize_severity_string(self):
        """Test that string severity values are mapped to numeric."""
        # Should map known severity strings
        self.assertGreater(_normalize_severity("high"), 0.5)
        self.assertGreater(_normalize_severity("HIGH"), 0.5)
        self.assertGreater(_normalize_severity("medium"), 0.2)
        self.assertLess(_normalize_severity("low"), 0.5)

    def test_normalize_severity_none(self):
        """Test that None severity returns default."""
        result = _normalize_severity(None)
        self.assertIsInstance(result, float)
        self.assertGreaterEqual(result, 0.0)
        self.assertLessEqual(result, 1.0)

    def test_normalize_severity_invalid(self):
        """Test that invalid severity returns default."""
        result = _normalize_severity("invalid")
        self.assertIsInstance(result, float)
        result_none = _normalize_severity(None)
        self.assertEqual(result, result_none)

    def test_normalize_delta_float(self):
        """Test that float delta values are returned as-is."""
        self.assertEqual(_normalize_delta(0.15), 0.15)
        self.assertEqual(_normalize_delta(-0.25), -0.25)
        self.assertEqual(_normalize_delta(0.0), 0.0)

    def test_normalize_delta_int(self):
        """Test that int delta values are converted to float."""
        self.assertEqual(_normalize_delta(10), 10.0)
        self.assertEqual(_normalize_delta(-5), -5.0)

    def test_normalize_delta_string(self):
        """Test that string delta values are converted to float."""
        self.assertEqual(_normalize_delta("0.15"), 0.15)
        self.assertEqual(_normalize_delta("-0.25"), -0.25)

    def test_normalize_delta_none(self):
        """Test that None delta returns 0.0."""
        self.assertEqual(_normalize_delta(None), 0.0)

    def test_normalize_delta_invalid(self):
        """Test that invalid delta returns 0.0."""
        self.assertEqual(_normalize_delta("invalid"), 0.0)
        self.assertEqual(_normalize_delta([]), 0.0)


class CalculateUrgencyTestCase(TestCase):
    """Tests for urgency calculation logic."""

    def test_high_urgency_critical_severity(self):
        """Test that critical severity results in high urgency."""
        result = _calculate_urgency(SEVERITY_THRESHOLD_CRITICAL, 0.0)
        self.assertEqual(result["level"], "high")
        self.assertEqual(result["label"], "Investigate Today")

    def test_high_urgency_large_delta(self):
        """Test that large delta results in high urgency."""
        result = _calculate_urgency(0.5, ALERT_HIGH_URGENCY_DELTA)
        self.assertEqual(result["level"], "high")
        self.assertEqual(result["label"], "Investigate Today")

        # Negative delta should also trigger high urgency
        result = _calculate_urgency(0.5, -ALERT_HIGH_URGENCY_DELTA)
        self.assertEqual(result["level"], "high")

    def test_medium_urgency_medium_severity(self):
        """Test that medium severity results in medium urgency."""
        result = _calculate_urgency(SEVERITY_THRESHOLD_MEDIUM, 0.0)
        self.assertEqual(result["level"], "medium")
        self.assertEqual(result["label"], "Review This Week")

    def test_medium_urgency_moderate_delta(self):
        """Test that moderate delta results in medium urgency."""
        result = _calculate_urgency(0.3, ALERT_MEDIUM_URGENCY_DELTA)
        self.assertEqual(result["level"], "medium")

    def test_low_urgency(self):
        """Test that low severity and small delta result in low urgency."""
        result = _calculate_urgency(SEVERITY_THRESHOLD_LOW, 0.01)
        self.assertEqual(result["level"], "low")
        self.assertEqual(result["label"], "Monitor for Trend")


class GeneratePlainLanguageTestCase(TestCase):
    """Tests for plain language generation."""

    def test_denial_rate_increase_critical(self):
        """Test plain language for critical denial rate increase."""
        text = _generate_plain_language(
            product_name="DriftWatch",
            signal_type="DENIAL_RATE",
            entity_label="Aetna",
            severity_value=SEVERITY_THRESHOLD_CRITICAL,
            delta_value=0.15,  # 15 percentage points
        )

        self.assertIn("Aetna", text)
        self.assertIn("increased", text)
        self.assertIn("15.0", text)
        self.assertIn("immediate attention", text.lower())

    def test_denial_rate_decrease(self):
        """Test plain language for denial rate decrease."""
        text = _generate_plain_language(
            product_name="DriftWatch",
            signal_type="DENIAL_RATE",
            entity_label="UnitedHealth",
            severity_value=SEVERITY_THRESHOLD_MEDIUM,
            delta_value=-0.10,
        )

        self.assertIn("UnitedHealth", text)
        self.assertIn("decreased", text)
        self.assertIn("10.0", text)
        self.assertIn("good news", text.lower())

    def test_denial_dollars_spike_critical(self):
        """Test plain language for critical denial dollars spike."""
        text = _generate_plain_language(
            product_name="DenialScope",
            signal_type="denial_dollars_spike",
            entity_label="BCBS",
            severity_value=SEVERITY_THRESHOLD_CRITICAL,
            delta_value=0.0,
        )

        self.assertIn("BCBS", text)
        self.assertIn("significant spike", text.lower())
        self.assertIn("investigation today", text.lower())

    def test_denial_dollars_spike_medium(self):
        """Test plain language for medium denial dollars spike."""
        text = _generate_plain_language(
            product_name="DenialScope",
            signal_type="denial_dollars_spike",
            entity_label="Cigna",
            severity_value=SEVERITY_THRESHOLD_MEDIUM,
            delta_value=0.0,
        )

        self.assertIn("Cigna", text)
        self.assertIn("this week", text.lower())

    def test_generic_signal_fallback(self):
        """Test plain language for unknown signal types."""
        text = _generate_plain_language(
            product_name="Unknown",
            signal_type="unknown_type",
            entity_label="TestPayer",
            severity_value=0.5,
            delta_value=0.0,
        )

        self.assertIn("TestPayer", text)
        self.assertIn("change has been detected", text.lower())


class GenerateActionStepsTestCase(TestCase):
    """Tests for action step generation."""

    def test_high_urgency_actions(self):
        """Test that high urgency generates immediate action steps."""
        steps = _generate_action_steps("high", "DENIAL_RATE", "Aetna")

        self.assertIsInstance(steps, list)
        self.assertGreater(len(steps), 3)
        self.assertTrue(any("today" in step.lower() for step in steps))
        self.assertTrue(any("Aetna" in step for step in steps))

    def test_medium_urgency_actions(self):
        """Test that medium urgency generates weekly review steps."""
        steps = _generate_action_steps("medium", "denial_dollars_spike", "BCBS")

        self.assertIsInstance(steps, list)
        self.assertGreater(len(steps), 2)
        self.assertTrue(any("this week" in step.lower() for step in steps))

    def test_low_urgency_actions(self):
        """Test that low urgency generates monitoring steps."""
        steps = _generate_action_steps("low", "DENIAL_RATE", "Cigna")

        self.assertIsInstance(steps, list)
        self.assertTrue(
            any("no immediate action" in step.lower() for step in steps)
        )
        self.assertTrue(any("watch" in step.lower() for step in steps))


class GenerateHistoricalContextTestCase(TestCase):
    """Tests for historical context generation."""

    def test_critical_severity_context(self):
        """Test context message for critical severity."""
        context = _generate_historical_context(SEVERITY_THRESHOLD_CRITICAL)
        self.assertIn("new", context.lower())

    def test_medium_severity_context(self):
        """Test context message for medium severity."""
        context = _generate_historical_context(SEVERITY_THRESHOLD_MEDIUM)
        self.assertIn("similar", context.lower())

    def test_low_severity_context(self):
        """Test context message for low severity."""
        context = _generate_historical_context(SEVERITY_THRESHOLD_LOW)
        self.assertIn("minor", context.lower())


class FormatDateRangeTestCase(TestCase):
    """Tests for date range formatting."""

    def test_both_dates(self):
        """Test formatting with both start and end dates."""
        start = date(2024, 1, 1)
        end = date(2024, 1, 31)
        result = _format_date_range(start, end)
        self.assertEqual(result, "2024-01-01 → 2024-01-31")

    def test_start_date_only(self):
        """Test formatting with only start date."""
        start = date(2024, 1, 1)
        result = _format_date_range(start, None)
        self.assertEqual(result, "From 2024-01-01")

    def test_end_date_only(self):
        """Test formatting with only end date."""
        end = date(2024, 1, 31)
        result = _format_date_range(None, end)
        self.assertEqual(result, "Through 2024-01-31")

    def test_no_dates(self):
        """Test formatting with no dates."""
        result = _format_date_range(None, None)
        self.assertEqual(result, "-")


class GetAlertInterpretationTestCase(TestCase):
    """Tests for the main get_alert_interpretation function."""

    def test_interpretation_with_valid_payload(self):
        """Test interpretation generation with valid evidence payload."""
        evidence = {
            "severity": "high",
            "delta": 0.15,
            "signal_type": "DENIAL_RATE",
            "product_name": "DriftWatch",
            "entity_label": "Aetna",
        }

        result = get_alert_interpretation(evidence)

        # Verify structure
        self.assertIn("urgency_level", result)
        self.assertIn("urgency_label", result)
        self.assertIn("plain_language", result)
        self.assertIn("historical_context", result)
        self.assertIn("action_steps", result)
        self.assertIn("is_likely_noise", result)

        # Verify high urgency for high severity + large delta
        self.assertEqual(result["urgency_level"], "high")
        self.assertEqual(result["urgency_label"], "Investigate Today")

        # Verify not noise
        self.assertFalse(result["is_likely_noise"])

    def test_interpretation_with_empty_payload(self):
        """Test interpretation with empty payload returns defaults."""
        result = get_alert_interpretation({})

        self.assertEqual(result["urgency_level"], "medium")
        self.assertEqual(result["urgency_label"], "Review This Week")
        self.assertIsNotNone(result["plain_language"])
        self.assertIsInstance(result["action_steps"], list)
        self.assertFalse(result["is_likely_noise"])

    def test_interpretation_with_none_payload(self):
        """Test interpretation with None payload returns defaults."""
        result = get_alert_interpretation(None)

        self.assertEqual(result["urgency_level"], "medium")
        self.assertIsNotNone(result["plain_language"])

    def test_interpretation_identifies_noise(self):
        """Test that low severity + small delta is identified as noise."""
        evidence = {
            "severity": 0.1,  # Very low severity
            "delta": 0.01,  # Very small delta
            "signal_type": "DENIAL_RATE",
            "product_name": "DriftWatch",
            "entity_label": "TestPayer",
        }

        result = get_alert_interpretation(evidence)

        self.assertTrue(result["is_likely_noise"])
        self.assertEqual(result["urgency_level"], "low")


class BuildDenialscopePayloadTestCase(TestCase):
    """Tests for DenialScope evidence payload builder."""

    def test_build_payload_with_signal(self):
        """Test payload building with valid signal."""
        # Create mock signal
        signal = Mock()
        signal.signal_type = "denial_dollars_spike"
        signal.payer = "Aetna"
        signal.confidence = 0.85
        signal.severity = "high"
        signal.summary_text = "Test summary"
        signal.details = {
            "baseline_value": 0.15,
            "recent_value": 0.25,
            "delta": 0.10,
            "baseline_count": 100,
            "recent_count": 120,
        }

        # Create mock aggregates QuerySet
        aggregates = Mock()
        aggregates.values.return_value = aggregates
        aggregates.annotate.return_value = aggregates
        aggregates.order_by.return_value = []

        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 31)

        payload = build_denialscope_evidence_payload(
            signal, aggregates, start_date, end_date
        )

        # Verify structure
        self.assertEqual(payload["product_name"], "DenialScope")
        self.assertEqual(payload["signal_type"], "denial_dollars_spike")
        self.assertEqual(payload["entity_label"], "Aetna")
        self.assertIn("2024-01-01", payload["date_range"])
        self.assertEqual(payload["baseline_value"], 0.15)
        self.assertEqual(payload["current_value"], 0.25)
        self.assertEqual(payload["delta"], 0.10)
        self.assertEqual(payload["confidence"], 0.85)
        self.assertEqual(payload["severity"], "high")
        self.assertEqual(payload["one_sentence_explanation"], "Test summary")

    def test_build_payload_with_none_signal(self):
        """Test payload building with None signal (graceful handling)."""
        payload = build_denialscope_evidence_payload(
            None, None, date(2024, 1, 1), date(2024, 1, 31)
        )

        # Should return payload with defaults
        self.assertEqual(payload["product_name"], "DenialScope")
        self.assertEqual(payload["entity_label"], "-")
        self.assertEqual(
            payload["one_sentence_explanation"], "No DenialScope signals yet."
        )


class BuildDriftwatchPayloadTestCase(TestCase):
    """Tests for DriftWatch evidence payload builder."""

    def test_build_payload_with_drift_event(self):
        """Test payload building with valid drift event."""
        # Create mock drift event
        drift_event = Mock()
        drift_event.payer = "UnitedHealth"
        drift_event.baseline_value = 0.10
        drift_event.current_value = 0.18
        drift_event.delta_value = 0.08
        drift_event.confidence = 0.90
        drift_event.severity = "medium"
        drift_event.drift_type = "DENIAL_RATE"
        drift_event.baseline_start = date(2023, 11, 1)
        drift_event.current_end = date(2024, 1, 31)

        # Create mock drift events list
        drift_events = [drift_event]

        payload = build_driftwatch_evidence_payload(drift_event, drift_events)

        # Verify structure
        self.assertEqual(payload["product_name"], "DriftWatch")
        self.assertEqual(payload["signal_type"], "DENIAL_RATE")
        self.assertEqual(payload["entity_label"], "UnitedHealth")
        self.assertIn("2023-11-01", payload["date_range"])
        self.assertEqual(payload["baseline_value"], 0.10)
        self.assertEqual(payload["current_value"], 0.18)
        self.assertEqual(payload["delta"], 0.08)
        self.assertEqual(payload["confidence"], 0.90)
        self.assertEqual(payload["severity"], "medium")
        self.assertIn("UnitedHealth", payload["one_sentence_explanation"])
        self.assertIn("10.0%", payload["one_sentence_explanation"])
        self.assertIn("18.0%", payload["one_sentence_explanation"])

    def test_build_payload_with_multiple_events(self):
        """Test that evidence_rows are limited to 20 items."""
        drift_event = Mock()
        drift_event.payer = "TestPayer"
        drift_event.baseline_value = 0.10
        drift_event.current_value = 0.15
        drift_event.delta_value = 0.05
        drift_event.confidence = 0.80
        drift_event.severity = "low"
        drift_event.drift_type = "DENIAL_RATE"
        drift_event.baseline_start = None
        drift_event.current_end = None

        # Create 25 mock events
        drift_events = []
        for i in range(25):
            event = Mock()
            event.payer = f"Payer{i}"
            event.cpt_group = f"CPT{i}"
            event.drift_type = "DENIAL_RATE"
            event.baseline_value = 0.10
            event.current_value = 0.15
            event.delta_value = 0.05
            event.severity = "low"
            event.confidence = 0.80
            drift_events.append(event)

        payload = build_driftwatch_evidence_payload(drift_event, drift_events)

        # Should only include first 20
        self.assertEqual(len(payload["evidence_rows"]), 20)

    def test_build_payload_with_none_drift_event(self):
        """Test payload building with None drift event (graceful handling)."""
        payload = build_driftwatch_evidence_payload(None, [])

        # Should return payload with defaults
        self.assertEqual(payload["product_name"], "DriftWatch")
        self.assertEqual(payload["entity_label"], "-")
        self.assertEqual(
            payload["one_sentence_explanation"], "No DriftWatch signals yet."
        )
