"""
Behavioral Prediction Engine - Day-3 Early Detection.

This module implements the behavioral prediction engine that compares
denial rates from the last 3 days against the previous 14 days per payer.
Uses chi-square significance testing to detect statistically significant
changes early, enabling 30-60 day warning before traditional monthly
reporting would catch the issue.

Detection Logic:
    - Baseline: Previous 14 days denial rate
    - Current: Last 3 days denial rate
    - Alert trigger: p-value < 0.05 AND rate change > 5%
    - Creates DriftEvent with drift_type='BEHAVIORAL_PREDICTION'
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from django.db import IntegrityError, transaction
from django.utils import timezone
from scipy import stats

from upstream.constants import (
    CONFIDENCE_VOLUME_MULTIPLIER,
    STATISTICAL_SIGNIFICANCE_P_VALUE,
)
from upstream.models import ClaimRecord, Customer, DriftEvent, ReportRun


# Behavioral prediction specific constants
BEHAVIORAL_BASELINE_DAYS = 14  # Previous 14 days for baseline
BEHAVIORAL_CURRENT_DAYS = 3  # Last 3 days for current window
BEHAVIORAL_RATE_CHANGE_THRESHOLD = 0.05  # 5% rate change threshold
BEHAVIORAL_MIN_VOLUME = 10  # Lower threshold for early detection


@dataclass
class BehavioralPredictionResult:
    """Result of a behavioral prediction analysis for a payer."""

    payer: str
    baseline_denial_rate: float
    current_denial_rate: float
    rate_change: float
    p_value: float
    is_significant: bool
    baseline_sample_size: int
    current_sample_size: int
    severity: float
    confidence: float


def compute_behavioral_prediction(
    customer: Customer,
    as_of_date: Optional[date] = None,
    baseline_days: int = BEHAVIORAL_BASELINE_DAYS,
    current_days: int = BEHAVIORAL_CURRENT_DAYS,
    min_volume: int = BEHAVIORAL_MIN_VOLUME,
    rate_change_threshold: float = BEHAVIORAL_RATE_CHANGE_THRESHOLD,
    report_run: Optional[ReportRun] = None,
) -> ReportRun:
    """
    Compute behavioral prediction metrics and create DriftEvent records.

    Compares last 3 days denial rate vs previous 14 days per payer.
    Uses chi-square test for statistical significance. Creates DriftEvent
    with drift_type='BEHAVIORAL_PREDICTION' when p-value < 0.05 AND
    rate change > 5%.

    Args:
        customer: Customer object to analyze
        as_of_date: Reference date (defaults to today)
        baseline_days: Number of days in baseline window (default: 14)
        current_days: Number of days in current window (default: 3)
        min_volume: Minimum claims in both windows (default: 10)
        rate_change_threshold: Minimum rate change to trigger alert (default: 0.05)
        report_run: Optional existing ReportRun to use

    Returns:
        ReportRun object with results

    Concurrency:
        Uses select_for_update() to lock the customer row, preventing
        concurrent behavioral prediction computations for the same customer.
    """
    if as_of_date is None:
        as_of_date = timezone.now().date()

    # Calculate date windows
    # Current window: last 3 days (exclusive of today, so days_ago 1-3)
    # Example: as_of_date=Jan 30, current_days=3
    # current_end = Jan 30 (inclusive using __lte)
    # current_start = Jan 28 (Jan 30 - 2 days)
    current_end = as_of_date
    current_start = as_of_date - timedelta(days=current_days - 1)

    # Baseline window: 14 days before the current window
    # baseline_end = Jan 27 (current_start - 1 day)
    # baseline_start = Jan 14 (baseline_end - 13 days)
    baseline_end = current_start - timedelta(days=1)
    baseline_start = baseline_end - timedelta(days=baseline_days - 1)

    # Create or use existing ReportRun
    # Note: Using "custom" type since behavioral_prediction is not a valid REPORT_TYPE_CHOICE
    if report_run is None:
        report_run = ReportRun.objects.create(
            customer=customer,
            run_type="custom",  # Use custom for behavioral prediction runs
            status="running",
            started_at=timezone.now(),
        )

    try:
        with transaction.atomic():
            # Lock customer row to prevent concurrent computation
            locked_customer = Customer.objects.select_for_update().get(id=customer.id)

            # Query baseline records - group by payer
            # Use submitted_date for behavioral analysis (when claims were submitted)
            # Note: Using all_objects to bypass CustomerScopedManager since we filter by customer explicitly
            baseline_records = ClaimRecord.all_objects.filter(
                customer=locked_customer,
                submitted_date__gte=baseline_start,
                submitted_date__lte=baseline_end,
                outcome__in=["PAID", "DENIED"],
            ).values("payer", "outcome")

            # Query current records - group by payer
            current_records = ClaimRecord.all_objects.filter(
                customer=locked_customer,
                submitted_date__gte=current_start,
                submitted_date__lte=current_end,
                outcome__in=["PAID", "DENIED"],
            ).values("payer", "outcome")

            # Aggregate by payer
            baseline_by_payer = {}
            for record in baseline_records:
                payer = record["payer"]
                if payer not in baseline_by_payer:
                    baseline_by_payer[payer] = {"paid": 0, "denied": 0}
                if record["outcome"] == "PAID":
                    baseline_by_payer[payer]["paid"] += 1
                else:
                    baseline_by_payer[payer]["denied"] += 1

            current_by_payer = {}
            for record in current_records:
                payer = record["payer"]
                if payer not in current_by_payer:
                    current_by_payer[payer] = {"paid": 0, "denied": 0}
                if record["outcome"] == "PAID":
                    current_by_payer[payer]["paid"] += 1
                else:
                    current_by_payer[payer]["denied"] += 1

            # Find all payers present in either window
            all_payers = set(baseline_by_payer.keys()) | set(current_by_payer.keys())
            payers_analyzed = 0
            events_created = 0
            results = []

            for payer in all_payers:
                baseline_data = baseline_by_payer.get(payer, {"paid": 0, "denied": 0})
                current_data = current_by_payer.get(payer, {"paid": 0, "denied": 0})

                baseline_total = baseline_data["paid"] + baseline_data["denied"]
                current_total = current_data["paid"] + current_data["denied"]

                # Check minimum volume requirements
                if baseline_total < min_volume or current_total < min_volume:
                    continue

                payers_analyzed += 1

                # Calculate denial rates
                baseline_denial_rate = baseline_data["denied"] / baseline_total
                current_denial_rate = current_data["denied"] / current_total
                rate_change = current_denial_rate - baseline_denial_rate

                # Chi-square test for significance
                # Contingency table: [[baseline_denied, baseline_paid], [current_denied, current_paid]]
                contingency_table = [
                    [baseline_data["denied"], baseline_data["paid"]],
                    [current_data["denied"], current_data["paid"]],
                ]

                # Perform chi-square test
                try:
                    chi2, p_value, dof, expected = stats.chi2_contingency(
                        contingency_table
                    )
                except ValueError:
                    # Handle edge case where chi2 can't be computed
                    p_value = 1.0

                # Check if significant: p < 0.05 AND rate change > threshold
                is_significant = (
                    p_value < STATISTICAL_SIGNIFICANCE_P_VALUE
                    and abs(rate_change) >= rate_change_threshold
                )

                # Calculate severity based on rate change magnitude
                # Higher rate increase = higher severity
                severity = min(abs(rate_change) * 4.0, 1.0)  # Scale to 0-1

                # Calculate confidence based on sample size
                confidence = min(
                    (baseline_total + current_total)
                    / (min_volume * CONFIDENCE_VOLUME_MULTIPLIER),
                    1.0,
                )

                result = BehavioralPredictionResult(
                    payer=payer,
                    baseline_denial_rate=baseline_denial_rate,
                    current_denial_rate=current_denial_rate,
                    rate_change=rate_change,
                    p_value=p_value,
                    is_significant=is_significant,
                    baseline_sample_size=baseline_total,
                    current_sample_size=current_total,
                    severity=severity,
                    confidence=confidence,
                )
                results.append(result)

                # Create DriftEvent if significant
                if is_significant:
                    try:
                        DriftEvent.objects.create(
                            customer=locked_customer,
                            report_run=report_run,
                            payer=payer,
                            cpt_group="ALL",  # Behavioral prediction is payer-level
                            drift_type="BEHAVIORAL_PREDICTION",
                            baseline_value=baseline_denial_rate,
                            current_value=current_denial_rate,
                            delta_value=rate_change,
                            severity=severity,
                            confidence=confidence,
                            baseline_start=baseline_start,
                            baseline_end=baseline_end,
                            current_start=current_start,
                            current_end=current_end,
                            baseline_sample_size=baseline_total,
                            current_sample_size=current_total,
                            statistical_significance=p_value,
                            trend_direction=(
                                "degrading" if rate_change > 0 else "improving"
                            ),
                        )
                        events_created += 1
                    except IntegrityError:
                        # Duplicate event already exists
                        pass

            # Update report run with summary
            report_run.summary_json = {
                "baseline_start": baseline_start.isoformat(),
                "baseline_end": baseline_end.isoformat(),
                "current_start": current_start.isoformat(),
                "current_end": current_end.isoformat(),
                "payers_analyzed": payers_analyzed,
                "events_created": events_created,
                "significant_predictions": [
                    {
                        "payer": r.payer,
                        "baseline_rate": round(r.baseline_denial_rate, 4),
                        "current_rate": round(r.current_denial_rate, 4),
                        "rate_change": round(r.rate_change, 4),
                        "p_value": round(r.p_value, 4),
                        "severity": round(r.severity, 2),
                    }
                    for r in results
                    if r.is_significant
                ],
                "parameters": {
                    "baseline_days": baseline_days,
                    "current_days": current_days,
                    "min_volume": min_volume,
                    "rate_change_threshold": rate_change_threshold,
                    "as_of_date": as_of_date.isoformat(),
                },
            }
            report_run.status = "success"
            report_run.finished_at = timezone.now()
            report_run.save()

            return report_run

    except Exception as e:
        # Handle failure - mark report run as failed
        report_run.status = "failed"
        report_run.finished_at = timezone.now()
        report_run.summary_json = {
            "error": str(e),
            "baseline_start": baseline_start.isoformat(),
            "baseline_end": baseline_end.isoformat(),
            "current_start": current_start.isoformat(),
            "current_end": current_end.isoformat(),
            "parameters": {
                "baseline_days": baseline_days,
                "current_days": current_days,
                "min_volume": min_volume,
                "rate_change_threshold": rate_change_threshold,
                "as_of_date": as_of_date.isoformat(),
            },
        }
        report_run.save()

        # Delete any drift events that might have been created
        DriftEvent.objects.filter(report_run=report_run).delete()

        raise
