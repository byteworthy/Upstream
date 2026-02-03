"""
Tests for DelayGuard Payment Timing Trend Detection.

Tests the PaymentTimingTrendService which detects worsening payment trends
over consecutive weeks (e.g., 45→47→50→52 days = WORSENING trend).
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from upstream.models import Customer, ClaimRecord, Upload
from upstream.products.delayguard.models import PaymentTimingTrend
from upstream.products.delayguard.services import (
    PaymentTimingTrendService,
    detect_payment_timing_trends,
)


@pytest.fixture
def customer(db):
    """Create a test customer."""
    return Customer.objects.create(name="Test Healthcare Trend Detection")


@pytest.fixture
def upload(db, customer):
    """Create a test upload."""
    return Upload.objects.create(
        customer=customer,
        status="success",  # Valid status: processing, success, failed, partial
        filename="test_trends.csv",
        row_count=100,
    )


def create_claims_for_week(customer, upload, payer, week_start, avg_days, count=10):
    """
    Create test claims for a specific week with a given average payment delay.

    Args:
        customer: Customer instance
        upload: Upload instance
        payer: Payer name
        week_start: Start date of the week
        avg_days: Average days-to-payment for this week
        count: Number of claims to create
    """
    for i in range(count):
        # Spread claims across the week (days 0-6 only, within week bounds)
        day_offset = i % 6  # Keep within the week
        submitted = week_start + timedelta(days=day_offset)
        # Vary around the average to create realistic data
        variance = (i % 3) - 1  # -1 to +1 days variance (smaller variance)
        decided = submitted + timedelta(days=int(avg_days) + variance)

        ClaimRecord.objects.create(
            customer=customer,
            upload=upload,
            payer=payer,
            cpt="99213",
            submitted_date=submitted,
            decided_date=decided,
            outcome="PAID",
            allowed_amount=Decimal("1000.00"),
        )


class TestPaymentTimingTrendService:
    """Tests for PaymentTimingTrendService."""

    def test_init_requires_customer(self):
        """Test that service requires a customer."""
        with pytest.raises(TypeError, match="customer cannot be None"):
            PaymentTimingTrendService(None)

    def test_detect_worsening_trend(self, customer, upload):
        """
        Test detection of worsening payment timing trend.

        Creates 4 weeks of data with increasing payment delays:
        Week 1: 45 days, Week 2: 47 days, Week 3: 50 days, Week 4: 52 days
        """
        end_date = date.today()
        payer = "SlowPay Insurance"

        # Create worsening trend data: 45 → 47 → 50 → 52 days
        weekly_delays = [45, 47, 50, 52]

        for week_num, avg_days in enumerate(weekly_delays):
            week_start = end_date - timedelta(days=(4 - week_num) * 7)
            create_claims_for_week(
                customer, upload, payer, week_start, avg_days, count=10
            )

        service = PaymentTimingTrendService(customer)
        results = service.detect_payment_timing_trends(payer=payer, end_date=end_date)

        assert len(results) == 1
        result = results[0]

        assert result["payer"] == payer
        assert result["trend_direction"] == "WORSENING"
        assert result["consecutive_worsening_weeks"] >= 3
        assert result["total_delta_days"] > 0  # Payment got slower
        assert result["baseline_avg_days"] < result["current_avg_days"]
        assert result["severity"] in ["medium", "high", "critical"]
        assert result["estimated_revenue_delay"] > 0

    def test_detect_stable_trend(self, customer, upload):
        """
        Test that stable trends (no significant change) are not flagged.

        Creates 4 weeks of data with consistent payment delays:
        Week 1-4: ~30 days (with minor variance)
        """
        end_date = date.today()
        payer = "StablePay Insurance"

        # Create stable data: ~30 days each week
        for week_num in range(4):
            week_start = end_date - timedelta(days=(4 - week_num) * 7)
            create_claims_for_week(customer, upload, payer, week_start, 30, count=10)

        service = PaymentTimingTrendService(customer)
        results = service.detect_payment_timing_trends(payer=payer, end_date=end_date)

        # Stable trends should not generate results
        assert len(results) == 0

    def test_detect_improving_trend_not_flagged(self, customer, upload):
        """
        Test that improving trends (getting faster) are not flagged.

        Creates 4 weeks of data with decreasing payment delays:
        Week 1: 50 days, Week 2: 45 days, Week 3: 40 days, Week 4: 35 days
        """
        end_date = date.today()
        payer = "ImprovingPay Insurance"

        # Create improving trend: 50 → 45 → 40 → 35 days
        weekly_delays = [50, 45, 40, 35]

        for week_num, avg_days in enumerate(weekly_delays):
            week_start = end_date - timedelta(days=(4 - week_num) * 7)
            create_claims_for_week(
                customer, upload, payer, week_start, avg_days, count=10
            )

        service = PaymentTimingTrendService(customer)
        results = service.detect_payment_timing_trends(payer=payer, end_date=end_date)

        # Improving trends should not generate alerts
        assert len(results) == 0

    def test_absolute_slowdown_detection(self, customer, upload):
        """
        Test detection of absolute slowdown (7+ days increase).

        Creates data where there's a jump but not a consistent trend:
        Week 1: 30 days, Week 2: 32 days, Week 3: 35 days, Week 4: 40 days
        """
        end_date = date.today()
        payer = "JumpPay Insurance"

        # Create data with 10-day increase (30 → 40)
        weekly_delays = [30, 32, 35, 40]

        for week_num, avg_days in enumerate(weekly_delays):
            week_start = end_date - timedelta(days=(4 - week_num) * 7)
            create_claims_for_week(
                customer, upload, payer, week_start, avg_days, count=10
            )

        service = PaymentTimingTrendService(customer)
        results = service.detect_payment_timing_trends(payer=payer, end_date=end_date)

        assert len(results) == 1
        result = results[0]
        assert result["total_delta_days"] >= 7  # Absolute slowdown threshold

    def test_insufficient_data_skipped(self, customer, upload):
        """Test that payers with insufficient data are skipped."""
        end_date = date.today()
        payer = "LowVolume Insurance"

        # Create only 2 claims per week (below MIN_WEEKLY_CLAIMS=5)
        for week_num in range(4):
            week_start = end_date - timedelta(days=(4 - week_num) * 7)
            create_claims_for_week(
                customer, upload, payer, week_start, 30 + week_num * 3, count=2
            )

        service = PaymentTimingTrendService(customer)
        results = service.detect_payment_timing_trends(payer=payer, end_date=end_date)

        # Should be skipped due to insufficient sample size
        assert len(results) == 0

    def test_multiple_payers(self, customer, upload):
        """Test analyzing multiple payers at once."""
        end_date = date.today()

        # Create worsening trend for payer 1 (30→40→50→60 = 30 day increase)
        for week_num, avg_days in enumerate([30, 40, 50, 60]):
            week_start = end_date - timedelta(days=(4 - week_num) * 7)
            create_claims_for_week(
                customer, upload, "Payer A", week_start, avg_days, count=10
            )

        # Create stable data for payer 2
        for week_num in range(4):
            week_start = end_date - timedelta(days=(4 - week_num) * 7)
            create_claims_for_week(
                customer, upload, "Payer B", week_start, 25, count=10
            )

        service = PaymentTimingTrendService(customer)
        results = service.detect_payment_timing_trends(end_date=end_date)

        # Should only detect trend for Payer A (worsening)
        # Payer B should not be detected (stable)
        assert len(results) >= 1
        payer_names = [r["payer"] for r in results]
        assert "Payer A" in payer_names
        assert "Payer B" not in payer_names

    def test_cash_flow_impact_calculation(self, customer, upload):
        """Test that cash flow impact is calculated correctly."""
        end_date = date.today()
        payer = "CashFlow Test Insurance"

        # Create worsening trend
        for week_num, avg_days in enumerate([40, 45, 50, 55]):
            week_start = end_date - timedelta(days=(4 - week_num) * 7)
            create_claims_for_week(
                customer, upload, payer, week_start, avg_days, count=10
            )

        service = PaymentTimingTrendService(customer)
        results = service.detect_payment_timing_trends(payer=payer, end_date=end_date)

        assert len(results) == 1
        result = results[0]

        # Verify cash flow metrics are populated
        assert result["estimated_revenue_delay"] > 0
        assert result["total_billed"] > 0
        assert result["total_claim_count"] == 40  # 10 claims * 4 weeks


class TestSaveAndAlert:
    """Tests for saving trends and creating alerts."""

    def test_save_trend_creates_record(self, customer, upload):
        """Test that save_trend_and_create_alert creates database records."""
        end_date = date.today()
        payer = "SaveTest Insurance"

        # Create worsening trend data
        for week_num, avg_days in enumerate([45, 48, 52, 56]):
            week_start = end_date - timedelta(days=(4 - week_num) * 7)
            create_claims_for_week(
                customer, upload, payer, week_start, avg_days, count=10
            )

        service = PaymentTimingTrendService(customer)
        results = service.detect_payment_timing_trends(payer=payer, end_date=end_date)

        assert len(results) == 1

        # Save the trend
        trend = service.save_trend_and_create_alert(results[0], end_date=end_date)

        # Verify database record
        assert trend.pk is not None
        assert trend.payer == payer
        assert trend.trend_direction == "WORSENING"
        assert trend.customer == customer
        assert len(trend.weekly_metrics) == 4

        # Verify can be retrieved
        saved = PaymentTimingTrend.objects.get(pk=trend.pk)
        assert saved.payer == payer

    def test_deduplication_by_fingerprint(self, customer, upload):
        """Test that duplicate trends are not created."""
        end_date = date.today()
        payer = "DupeTest Insurance"

        # Create trend data
        for week_num, avg_days in enumerate([40, 44, 48, 53]):
            week_start = end_date - timedelta(days=(4 - week_num) * 7)
            create_claims_for_week(
                customer, upload, payer, week_start, avg_days, count=10
            )

        service = PaymentTimingTrendService(customer)
        results = service.detect_payment_timing_trends(payer=payer, end_date=end_date)

        # Save twice
        trend1 = service.save_trend_and_create_alert(results[0], end_date=end_date)
        trend2 = service.save_trend_and_create_alert(results[0], end_date=end_date)

        # Should return same record (deduplication)
        assert trend1.pk == trend2.pk
        assert PaymentTimingTrend.objects.filter(payer=payer).count() == 1


class TestConvenienceFunction:
    """Tests for detect_payment_timing_trends convenience function."""

    def test_detect_and_save(self, customer, upload):
        """Test the convenience function with save_results=True."""
        end_date = date.today()
        payer = "ConvenienceTest Insurance"

        # Create worsening trend
        for week_num, avg_days in enumerate([35, 40, 45, 51]):
            week_start = end_date - timedelta(days=(4 - week_num) * 7)
            create_claims_for_week(
                customer, upload, payer, week_start, avg_days, count=10
            )

        # Use convenience function
        results = detect_payment_timing_trends(
            customer, payer=payer, end_date=end_date, save_results=True
        )

        assert len(results) == 1

        # Verify saved to database
        assert PaymentTimingTrend.objects.filter(
            customer=customer, payer=payer
        ).exists()

    def test_detect_without_save(self, customer, upload):
        """Test the convenience function with save_results=False."""
        end_date = date.today()
        payer = "NoSaveTest Insurance"

        # Create worsening trend
        for week_num, avg_days in enumerate([30, 35, 40, 46]):
            week_start = end_date - timedelta(days=(4 - week_num) * 7)
            create_claims_for_week(
                customer, upload, payer, week_start, avg_days, count=10
            )

        # Use convenience function without saving
        results = detect_payment_timing_trends(
            customer, payer=payer, end_date=end_date, save_results=False
        )

        assert len(results) == 1

        # Should NOT be saved to database
        assert not PaymentTimingTrend.objects.filter(
            customer=customer, payer=payer
        ).exists()


class TestSeverityLevels:
    """Tests for severity level determination."""

    def test_critical_severity(self, customer, upload):
        """Test that large delta + 4 consecutive weeks = critical."""
        end_date = date.today()
        payer = "CriticalTest Insurance"

        # Create severe worsening: 30 → 40 → 50 → 60 (30 day increase over 4 weeks)
        for week_num, avg_days in enumerate([30, 40, 50, 60]):
            week_start = end_date - timedelta(days=(4 - week_num) * 7)
            create_claims_for_week(
                customer, upload, payer, week_start, avg_days, count=15
            )

        service = PaymentTimingTrendService(customer)
        results = service.detect_payment_timing_trends(payer=payer, end_date=end_date)

        assert len(results) == 1
        # Should be high or critical due to large delta and consecutive weeks
        assert results[0]["severity"] in ["high", "critical"]

    def test_medium_severity(self, customer, upload):
        """Test that moderate delta = medium severity."""
        end_date = date.today()
        payer = "MediumTest Insurance"

        # Create moderate worsening: 40 → 43 → 46 → 50 (10 day increase)
        for week_num, avg_days in enumerate([40, 43, 46, 50]):
            week_start = end_date - timedelta(days=(4 - week_num) * 7)
            create_claims_for_week(
                customer, upload, payer, week_start, avg_days, count=10
            )

        service = PaymentTimingTrendService(customer)
        results = service.detect_payment_timing_trends(payer=payer, end_date=end_date)

        assert len(results) == 1
        assert results[0]["severity"] in ["medium", "high"]
