"""
DelayGuard computation service.

Computes daily payment delay aggregates and signals from ClaimRecord data.
Detects meaningful increases in payment latency versus historical baseline.

This module provides the core computation logic for the DelayGuard product,
which monitors payment timing patterns and generates alerts when payers
begin taking longer to process claims than their historical baseline.

Example usage:
    >>> from upstream.products.delayguard.services import DelayGuardComputationService
    >>> service = DelayGuardComputationService(customer=customer)
    >>> result = service.compute(end_date=date.today())
    >>> print(f"Created {result['signals_created']} signals")
"""

from __future__ import annotations

import hashlib
import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Literal, TypedDict, Union, cast

from django.db import models, transaction
from django.db.models import Count, Max, Min, Sum, F, QuerySet
from django.utils import timezone

from upstream.models import ClaimRecord, Customer
from upstream.ingestion.services import publish_event
from upstream.products.delayguard import (
    DELAYGUARD_V1_SIGNAL_TYPE,
    DELAYGUARD_CURRENT_WINDOW_DAYS,
    DELAYGUARD_BASELINE_WINDOW_DAYS,
    DELAYGUARD_SEVERITY_THRESHOLDS,
    DELAYGUARD_MIN_SAMPLE_SIZE,
    DELAYGUARD_MIN_DATE_COMPLETENESS,
)
from upstream.products.delayguard.models import (
    PaymentDelayAggregate,
    PaymentDelaySignal,
    PaymentDelayClaimSet,
    PaymentDelayEvidenceArtifact,
)

if TYPE_CHECKING:
    from datetime import datetime

logger = logging.getLogger(__name__)


# =============================================================================
# Type Definitions
# =============================================================================

class DataQualityWarning(TypedDict):
    """
    Warning about data quality issues encountered during computation.
    
    Attributes:
        payer: The payer identifier associated with the warning.
        warning: Human-readable description of the data quality issue.
    """
    payer: str
    warning: str


class PayerAggregatedMetrics(TypedDict):
    """
    Aggregated payment delay metrics for a single payer.
    
    These metrics are computed by summing daily aggregates within a window.
    Used internally to compare baseline vs current window performance.
    
    Attributes:
        claim_count: Total number of claims with valid payment dates.
        total_days: Sum of all days-to-payment values.
        total_billed: Total dollar amount across all claims.
        completeness_sum: Sum of date_completeness_ratio values.
        agg_count: Number of daily aggregates contributing to this summary.
        aggregates: List of PaymentDelayAggregate instances.
    """
    claim_count: int
    total_days: int
    total_billed: Decimal
    completeness_sum: float
    agg_count: int
    aggregates: list[PaymentDelayAggregate]


class ComputeResult(TypedDict):
    """
    Result of a DelayGuard computation run.
    
    Returned by DelayGuardComputationService.compute() to provide
    summary information about what was computed and any issues found.
    
    Attributes:
        aggregates_created: Number of PaymentDelayAggregate records created.
        signals_created: Number of PaymentDelaySignal records created.
        baseline_start: Start date of the baseline comparison window.
        baseline_end: End date of the baseline comparison window.
        current_start: Start date of the current analysis window.
        current_end: End date of the current analysis window.
        data_quality_warnings: List of data quality issues encountered.
    """
    aggregates_created: int
    signals_created: int
    baseline_start: date
    baseline_end: date
    current_start: date
    current_end: date
    data_quality_warnings: list[DataQualityWarning]


class SignalDetails(TypedDict):
    """
    Detailed metrics stored in PaymentDelaySignal.details JSON field.

    Provides context for deep-dive analysis and evidence generation.

    Attributes:
        baseline_window: Human-readable baseline window date range.
        current_window: Human-readable current window date range.
        baseline_avg_days: Average days-to-payment in baseline window.
        current_avg_days: Average days-to-payment in current window.
        delta_days: Absolute change in average days-to-payment.
        delta_percent: Percentage change from baseline.
    """
    baseline_window: str
    current_window: str
    baseline_avg_days: float
    current_avg_days: float
    delta_days: float
    delta_percent: float


class DaysAggregationData(TypedDict, total=False):
    """
    Database aggregation result for days-to-payment calculations.

    This represents the raw output from Django ORM aggregate queries
    on ClaimRecord data. Used internally in _compute_daily_aggregates.

    Attributes:
        submitted_date: The date claims were submitted (grouping key).
        payer: The payer identifier (grouping key).
        claim_count: Number of claims with valid payment dates.
        total_days: Sum of days-to-payment values (may be timedelta or int).
        min_days: Minimum days-to-payment in the group (may be timedelta or int).
        max_days: Maximum days-to-payment in the group (may be timedelta or int).
        total_billed: Sum of allowed_amount values across claims.

    Note:
        total=False allows all fields to be optional, matching Django's
        .values() behavior where fields may be absent.
    """
    submitted_date: date
    payer: str
    claim_count: int
    total_days: Union[timedelta, int]
    min_days: Union[timedelta, int, None]
    max_days: Union[timedelta, int, None]
    total_billed: Decimal


# Type alias for severity levels with strict validation
SeverityLevel = Literal['low', 'medium', 'high', 'critical']


# =============================================================================
# Main Service Class
# =============================================================================

class DelayGuardComputationService:
    """
    Service to compute DelayGuard aggregates and signals.
    
    This service implements the core DelayGuard algorithm:
    1. Compute daily payment delay aggregates from ClaimRecord data
    2. Compare current window (recent 14 days) against baseline (prior 60 days)
    3. Generate signals when payment latency has meaningfully increased
    4. Apply deduplication to prevent alert fatigue
    
    The service is tenant-scoped: every query filters by customer to ensure
    strict data isolation in multi-tenant deployments.
    
    Attributes:
        customer: The Customer instance this service operates on.
        data_quality_warnings: List of warnings accumulated during computation.
    
    Example:
        >>> from upstream.products.delayguard.services import DelayGuardComputationService
        >>> from upstream.models import Customer
        >>> 
        >>> customer = Customer.objects.get(slug='acme-health')
        >>> service = DelayGuardComputationService(customer=customer)
        >>> result = service.compute()
        >>> 
        >>> if result['signals_created'] > 0:
        ...     print(f"Found {result['signals_created']} payment delay issues")
    
    Note:
        This service is idempotent. Running compute() multiple times with the
        same parameters will produce the same result, clearing and recreating
        aggregates and signals for the specified time window.
    """

    def __init__(self, customer: Customer) -> None:
        """
        Initialize the DelayGuard computation service.
        
        Args:
            customer: The Customer instance to compute aggregates and signals for.
                     All queries will be scoped to this customer.
        
        Raises:
            TypeError: If customer is None or not a Customer instance.
        """
        if customer is None:
            raise TypeError("customer cannot be None")
        self.customer: Customer = customer
        self.data_quality_warnings: list[DataQualityWarning] = []

    def compute(
        self,
        end_date: date | None = None,
        current_window_days: int = DELAYGUARD_CURRENT_WINDOW_DAYS,
        baseline_window_days: int = DELAYGUARD_BASELINE_WINDOW_DAYS,
        min_sample_size: int = DELAYGUARD_MIN_SAMPLE_SIZE,
    ) -> ComputeResult:
        """
        Compute aggregates and signals for payment delay drift.
        
        This is the main entry point for DelayGuard computation. It performs:
        1. Idempotent cleanup of existing data in the target window
        2. Daily aggregate computation from ClaimRecord data
        3. Baseline vs current window comparison per payer
        4. Signal generation with severity and confidence scoring
        5. Fingerprint-based deduplication
        
        Args:
            end_date: End date for the current analysis window. Defaults to today.
                     The current window extends backward from this date.
            current_window_days: Number of days in the current window. Default is 14.
                                This is the "recent" period being evaluated.
            baseline_window_days: Number of days in the baseline window. Default is 60.
                                 This is the historical reference period.
            min_sample_size: Minimum number of claims required for signal generation.
                            Payers with fewer claims are excluded. Default is 10.
        
        Returns:
            ComputeResult dict containing:
                - aggregates_created: Count of PaymentDelayAggregate records created
                - signals_created: Count of PaymentDelaySignal records created
                - baseline_start/end: Date range for baseline comparison
                - current_start/end: Date range for current window
                - data_quality_warnings: List of DataQualityWarning dicts
        
        Raises:
            django.db.DatabaseError: If there's a database connectivity issue.
        
        Example:
            >>> service = DelayGuardComputationService(customer)
            >>> result = service.compute(
            ...     end_date=date(2026, 1, 15),
            ...     current_window_days=7,
            ...     min_sample_size=5
            ... )
            >>> print(f"Baseline: {result['baseline_start']} to {result['baseline_end']}")
        
        Note:
            The method runs within a database transaction to ensure atomicity.
            Either all changes are committed, or none are.
        """
        if end_date is None:
            end_date = timezone.now().date()

        # Define windows
        current_end: date = end_date
        current_start: date = current_end - timedelta(days=current_window_days)
        baseline_end: date = current_start
        baseline_start: date = baseline_end - timedelta(days=baseline_window_days)

        with transaction.atomic():
            # Clear existing aggregates in range (idempotent)
            PaymentDelayAggregate.objects.filter(
                customer=self.customer,
                aggregate_date__gte=baseline_start,
                aggregate_date__lt=current_end
            ).delete()

            # Compute daily aggregates
            aggregates: list[PaymentDelayAggregate] = self._compute_daily_aggregates(
                baseline_start, current_end
            )
            PaymentDelayAggregate.objects.bulk_create(aggregates)

            # Clear existing signals for this run window (idempotent)
            PaymentDelaySignal.objects.filter(
                customer=self.customer,
                window_end_date=current_end,
            ).delete()

            # Compute signals
            signals: list[PaymentDelaySignal] = self._compute_signals(
                baseline_start, baseline_end,
                current_start, current_end,
                min_sample_size
            )

            return ComputeResult(
                aggregates_created=len(aggregates),
                signals_created=len(signals),
                baseline_start=baseline_start,
                baseline_end=baseline_end,
                current_start=current_start,
                current_end=current_end,
                data_quality_warnings=self.data_quality_warnings,
            )

    def _compute_daily_aggregates(
        self,
        start_date: date,
        end_date: date
    ) -> list[PaymentDelayAggregate]:
        """
        Compute daily payment delay aggregates by payer.
        
        This method queries ClaimRecord data and produces one PaymentDelayAggregate
        per (payer, date) combination. It calculates:
        - Average, min, max days from submission to decision
        - Total claims processed and dollar amounts
        - Data quality metrics (date completeness ratio)
        
        Args:
            start_date: Start date (inclusive) for the aggregation period.
            end_date: End date (exclusive) for the aggregation period.
        
        Returns:
            List of PaymentDelayAggregate instances (not yet saved to DB).
            These are ready for bulk_create().
        
        Note:
            Days-to-payment is calculated as: decided_date - submitted_date.
            Claims missing either date are tracked for data quality metrics
            but excluded from the days-to-payment calculations.
        """
        # Base queryset - tenant scoped
        base_qs: QuerySet[ClaimRecord] = ClaimRecord.objects.filter(
            customer=self.customer,
            submitted_date__gte=start_date,
            submitted_date__lt=end_date,
        )

        # Aggregate by day and payer for row counts
        aggregates_qs = base_qs.values(
            'submitted_date',
            'payer',
        ).annotate(
            total_rows=Count('id'),
            valid_rows=Count('id', filter=~(
                models.Q(submitted_date__isnull=True) | 
                models.Q(decided_date__isnull=True)
            )),
            total_allowed=Sum('allowed_amount'),
        )

        # For days-to-payment, we need claims with both dates
        days_qs = base_qs.filter(
            submitted_date__isnull=False,
            decided_date__isnull=False,
        ).annotate(
            days_to_pay=F('decided_date') - F('submitted_date')
        ).values('submitted_date', 'payer').annotate(
            claim_count=Count('id'),
            total_days=Sum(F('decided_date') - F('submitted_date')),
            min_days=Min(F('decided_date') - F('submitted_date')),
            max_days=Max(F('decided_date') - F('submitted_date')),
            total_billed=Sum('allowed_amount'),
        )

        # Build aggregates
        aggregates: list[PaymentDelayAggregate] = []
        days_data: dict[tuple[date, str], DaysAggregationData] = {
            (r['submitted_date'], r['payer']): r for r in days_qs  # type: ignore[misc]
        }

        for row in aggregates_qs:
            key: tuple[date, str] = (row['submitted_date'], row['payer'])
            days_info: DaysAggregationData = days_data.get(key, {})

            claim_count: int = days_info.get('claim_count', 0)
            total_days_val: Union[timedelta, int, None] = days_info.get('total_days')

            # Convert timedelta to int days if needed
            # Django's date arithmetic can return either timedelta or int depending on backend
            total_days_int: int
            if total_days_val is not None:
                if isinstance(total_days_val, timedelta):
                    total_days_int = total_days_val.days
                else:
                    total_days_int = int(total_days_val)
            else:
                total_days_int = 0

            avg_days: float = total_days_int / claim_count if claim_count > 0 else 0.0

            # Convert min/max days from timedelta to int if needed
            min_days_raw: Union[timedelta, int, None] = days_info.get('min_days')
            max_days_raw: Union[timedelta, int, None] = days_info.get('max_days')

            min_days: int | None = None
            if min_days_raw is not None:
                if isinstance(min_days_raw, timedelta):
                    min_days = min_days_raw.days
                else:
                    min_days = int(min_days_raw)

            max_days: int | None = None
            if max_days_raw is not None:
                if isinstance(max_days_raw, timedelta):
                    max_days = max_days_raw.days
                else:
                    max_days = int(max_days_raw)

            total_rows: int = row['total_rows'] or 0
            valid_rows: int = row['valid_rows'] or 0
            completeness: float = valid_rows / total_rows if total_rows > 0 else 0.0

            aggregate = PaymentDelayAggregate(
                customer=self.customer,
                payer=row['payer'],
                aggregate_date=row['submitted_date'],
                claim_count=claim_count,
                total_days_to_payment=total_days_int,
                avg_days_to_payment=avg_days,
                min_days_to_payment=min_days,
                max_days_to_payment=max_days,
                total_billed_amount=days_info.get('total_billed') or Decimal('0.00'),
                total_rows_evaluated=total_rows,
                rows_with_valid_dates=valid_rows,
                date_completeness_ratio=completeness,
            )
            aggregates.append(aggregate)

        return aggregates

    def _compute_signals(
        self,
        baseline_start: date,
        baseline_end: date,
        current_start: date,
        current_end: date,
        min_sample_size: int
    ) -> list[PaymentDelaySignal]:
        """
        Compute DelayGuard signals using baseline vs current window comparison.
        
        For each payer, this method:
        1. Aggregates metrics across the baseline and current windows
        2. Calculates the change in average days-to-payment
        3. Generates a signal if payment latency has meaningfully increased
        4. Applies deduplication via fingerprinting
        
        Args:
            baseline_start: Start date (inclusive) of the baseline window.
            baseline_end: End date (exclusive) of the baseline window.
            current_start: Start date (inclusive) of the current window.
            current_end: End date (exclusive) of the current window.
            min_sample_size: Minimum claims required in both windows for signal generation.
        
        Returns:
            List of PaymentDelaySignal instances that were created and saved.
            Only signals with positive delta (slower payments) are returned.
        
        Note:
            Signals are only generated when:
            - Both windows have at least min_sample_size claims
            - Payment latency has increased (positive delta)
            - The signal fingerprint doesn't already exist (deduplication)
        """
        # Fetch aggregates for baseline and current
        baseline_aggregates: QuerySet[PaymentDelayAggregate] = PaymentDelayAggregate.objects.filter(
            customer=self.customer,
            aggregate_date__gte=baseline_start,
            aggregate_date__lt=baseline_end
        )

        current_aggregates: QuerySet[PaymentDelayAggregate] = PaymentDelayAggregate.objects.filter(
            customer=self.customer,
            aggregate_date__gte=current_start,
            aggregate_date__lt=current_end
        )

        # Group by payer
        baseline_grouped: dict[str, PayerAggregatedMetrics] = self._group_by_payer(baseline_aggregates)
        current_grouped: dict[str, PayerAggregatedMetrics] = self._group_by_payer(current_aggregates)

        signals: list[PaymentDelaySignal] = []

        for payer, current_data in current_grouped.items():
            baseline_data: PayerAggregatedMetrics | None = baseline_grouped.get(payer)

            if not baseline_data:
                continue

            # Check minimum sample sizes
            if current_data['claim_count'] < min_sample_size:
                continue
            if baseline_data['claim_count'] < min_sample_size:
                continue

            # Calculate averages
            baseline_avg: float = baseline_data['total_days'] / baseline_data['claim_count']
            current_avg: float = current_data['total_days'] / current_data['claim_count']

            delta_days: float = current_avg - baseline_avg
            delta_percent: float = (delta_days / baseline_avg * 100) if baseline_avg > 0 else 0.0

            # Data quality check
            avg_completeness: float = current_data['completeness_sum'] / current_data['agg_count']
            if avg_completeness < DELAYGUARD_MIN_DATE_COMPLETENESS:
                self.data_quality_warnings.append(DataQualityWarning(
                    payer=payer,
                    warning=f'Low date completeness ({avg_completeness:.1%})',
                ))

            # Only create signal if delta is positive (payments getting slower)
            if delta_days <= 0:
                continue

            # Calculate confidence based on sample size and data quality
            confidence: float = self._calculate_confidence(
                current_data['claim_count'],
                baseline_data['claim_count'],
                avg_completeness,
                min_sample_size
            )

            # Calculate severity
            severity: SeverityLevel = self._severity_from_delta_and_confidence(delta_days, confidence)

            # Skip low severity signals
            if severity == 'low' and delta_days < 2:
                continue

            # Estimate dollars at risk (simplified: daily cash flow impact)
            avg_daily_billed: Decimal = current_data['total_billed'] / current_data['agg_count']
            estimated_dollars_at_risk: Decimal = avg_daily_billed * Decimal(str(delta_days))

            # Generate fingerprint for dedupe
            fingerprint: str = self._generate_fingerprint(
                payer, current_start, current_end
            )

            # Check for existing active signal with same fingerprint
            existing: PaymentDelaySignal | None = PaymentDelaySignal.objects.filter(
                customer=self.customer,
                fingerprint=fingerprint,
            ).first()

            if existing:
                logger.info(f"Signal already exists for {payer} with fingerprint {fingerprint}")
                continue

            signal: PaymentDelaySignal = self._create_signal(
                payer=payer,
                baseline_start=baseline_start,
                baseline_end=baseline_end,
                current_start=current_start,
                current_end=current_end,
                baseline_avg=baseline_avg,
                current_avg=current_avg,
                delta_days=delta_days,
                delta_percent=delta_percent,
                baseline_claim_count=baseline_data['claim_count'],
                current_claim_count=current_data['claim_count'],
                estimated_dollars_at_risk=estimated_dollars_at_risk,
                severity=severity,
                confidence=confidence,
                fingerprint=fingerprint,
                aggregates=current_data['aggregates'],
            )
            signals.append(signal)

        return signals

    def _group_by_payer(
        self,
        aggregates_qs: QuerySet[PaymentDelayAggregate]
    ) -> dict[str, PayerAggregatedMetrics]:
        """
        Group payment delay aggregates by payer.
        
        Sums up daily aggregates to produce per-payer totals suitable
        for baseline vs current window comparison.
        
        Args:
            aggregates_qs: QuerySet of PaymentDelayAggregate records.
        
        Returns:
            Dictionary mapping payer name to PayerAggregatedMetrics.
        """
        grouped: dict[str, PayerAggregatedMetrics] = {}
        
        for agg in aggregates_qs:
            if agg.payer not in grouped:
                grouped[agg.payer] = PayerAggregatedMetrics(
                    claim_count=0,
                    total_days=0,
                    total_billed=Decimal('0.00'),
                    completeness_sum=0.0,
                    agg_count=0,
                    aggregates=[]
                )
            grouped[agg.payer]['claim_count'] += agg.claim_count
            grouped[agg.payer]['total_days'] += agg.total_days_to_payment
            grouped[agg.payer]['total_billed'] += agg.total_billed_amount
            grouped[agg.payer]['completeness_sum'] += agg.date_completeness_ratio
            grouped[agg.payer]['agg_count'] += 1
            grouped[agg.payer]['aggregates'].append(agg)
        
        return grouped

    def _calculate_confidence(
        self,
        current_count: int,
        baseline_count: int,
        completeness: float,
        min_sample: int
    ) -> float:
        """
        Calculate confidence score based on sample size and data quality.
        
        The confidence score (0.0 to 1.0) reflects how reliable the signal is.
        Higher sample sizes and better data completeness produce higher confidence.
        
        The formula weights:
        - Sample size factor (70%): Based on total claims vs 4x minimum
        - Data completeness factor (30%): Based on date field availability
        
        Args:
            current_count: Number of claims in the current window.
            baseline_count: Number of claims in the baseline window.
            completeness: Average date completeness ratio (0.0 to 1.0).
            min_sample: Minimum sample size threshold.
        
        Returns:
            Confidence score between 0.0 and 1.0.
        
        Example:
            >>> confidence = service._calculate_confidence(
            ...     current_count=100,
            ...     baseline_count=400,
            ...     completeness=0.95,
            ...     min_sample=10
            ... )
            >>> print(f"Confidence: {confidence:.2f}")  # Output: Confidence: 0.98
        """
        # Base confidence from sample size
        sample_factor: float = min(1.0, (current_count + baseline_count) / (min_sample * 4))
        
        # Adjust for data completeness
        completeness_factor: float = min(1.0, completeness / DELAYGUARD_MIN_DATE_COMPLETENESS)
        
        confidence: float = sample_factor * 0.7 + completeness_factor * 0.3
        return min(1.0, max(0.0, confidence))

    def _severity_from_delta_and_confidence(
        self,
        delta_days: float,
        confidence: float
    ) -> SeverityLevel:
        """
        Map delta days and confidence to severity level.

        Uses DELAYGUARD_SEVERITY_THRESHOLDS to determine severity.
        Thresholds are evaluated in order; the first match is returned.

        Args:
            delta_days: Change in average days-to-payment (positive = slower).
            confidence: Confidence score (0.0 to 1.0).

        Returns:
            Severity level string: 'critical', 'high', 'medium', or 'low'.

        Example:
            >>> severity = service._severity_from_delta_and_confidence(
            ...     delta_days=12.5,
            ...     confidence=0.85
            ... )
            >>> print(severity)  # Output: 'critical'
        """
        for threshold_days, threshold_confidence, severity in DELAYGUARD_SEVERITY_THRESHOLDS:
            if delta_days >= threshold_days and confidence >= threshold_confidence:
                return cast(SeverityLevel, severity)
        return 'low'

    def _generate_fingerprint(
        self,
        payer: str,
        start_date: date,
        end_date: date
    ) -> str:
        """
        Generate deterministic fingerprint for deduplication.
        
        The fingerprint uniquely identifies a signal based on:
        - Customer ID
        - Payer name
        - Analysis window dates
        - Signal type
        
        Args:
            payer: Payer identifier string.
            start_date: Start date of the current window.
            end_date: End date of the current window.
        
        Returns:
            32-character hexadecimal fingerprint string.
        
        Note:
            Using the same inputs will always produce the same fingerprint,
            enabling reliable deduplication across computation runs.
        """
        customer_id: int = cast(int, self.customer.pk)
        key: str = f"{customer_id}:{payer}:{start_date}:{end_date}:payment_delay_drift"
        return hashlib.sha256(key.encode()).hexdigest()[:32]

    def _create_signal(
        self,
        payer: str,
        baseline_start: date,
        baseline_end: date,
        current_start: date,
        current_end: date,
        baseline_avg: float,
        current_avg: float,
        delta_days: float,
        delta_percent: float,
        baseline_claim_count: int,
        current_claim_count: int,
        estimated_dollars_at_risk: Decimal,
        severity: SeverityLevel,
        confidence: float,
        fingerprint: str,
        aggregates: list[PaymentDelayAggregate],
    ) -> PaymentDelaySignal:
        """
        Create a PaymentDelaySignal and publish a SystemEvent.
        
        This method:
        1. Builds a human-readable summary
        2. Creates the PaymentDelaySignal record
        3. Associates related aggregates
        4. Publishes a SystemEvent for alert routing
        
        Args:
            payer: Payer identifier string.
            baseline_start: Start date of the baseline window.
            baseline_end: End date of the baseline window.
            current_start: Start date of the current window.
            current_end: End date of the current window.
            baseline_avg: Average days-to-payment in baseline window.
            current_avg: Average days-to-payment in current window.
            delta_days: Change in average days (positive = slower).
            delta_percent: Percentage change from baseline.
            baseline_claim_count: Number of claims in baseline window.
            current_claim_count: Number of claims in current window.
            estimated_dollars_at_risk: Estimated cash impact from delay.
            severity: Severity level string.
            confidence: Confidence score (0.0 to 1.0).
            fingerprint: Unique fingerprint for deduplication.
            aggregates: List of PaymentDelayAggregate instances to associate.
        
        Returns:
            The created PaymentDelaySignal instance.
        
        Side Effects:
            - Creates a PaymentDelaySignal record in the database
            - Publishes a 'delayguard_signal_created' SystemEvent
            - Logs the signal creation
        """
        summary: str = (
            f"{payer} payment latency increased from {baseline_avg:.1f} to {current_avg:.1f} days "
            f"({delta_days:+.1f} days, {delta_percent:+.1f}%)"
        )

        details: SignalDetails = SignalDetails(
            baseline_window=f"{baseline_start} to {baseline_end}",
            current_window=f"{current_start} to {current_end}",
            baseline_avg_days=baseline_avg,
            current_avg_days=current_avg,
            delta_days=delta_days,
            delta_percent=delta_percent,
        )

        signal: PaymentDelaySignal = PaymentDelaySignal.objects.create(
            customer=self.customer,
            signal_type='payment_delay_drift',
            payer=payer,
            window_start_date=current_start,
            window_end_date=current_end,
            baseline_start_date=baseline_start,
            baseline_end_date=baseline_end,
            baseline_avg_days=baseline_avg,
            current_avg_days=current_avg,
            delta_days=delta_days,
            delta_percent=delta_percent,
            baseline_claim_count=baseline_claim_count,
            current_claim_count=current_claim_count,
            estimated_dollars_at_risk=estimated_dollars_at_risk,
            severity=severity,
            confidence=confidence,
            summary_text=summary,
            fingerprint=fingerprint,
            data_quality_warnings=self.data_quality_warnings,
            details=details,
        )

        if aggregates:
            signal.related_aggregates.add(*aggregates)

        # Publish SystemEvent for alert routing
        publish_event(
            customer=self.customer,
            event_type='delayguard_signal_created',
            payload={
                'title': "DelayGuard: Payment Delay Drift",
                'summary': summary,
                'signal_type': 'payment_delay_drift',
                'payer': payer,
                'severity': severity,
                'delta_days': delta_days,
                'estimated_dollars_at_risk': str(estimated_dollars_at_risk),
            }
        )

        # Create AlertEvent from signal for unified alerting
        from upstream.alerts.services import evaluate_payment_delay_signal
        evaluate_payment_delay_signal(signal)

        logger.info(f"DelayGuard signal created: {payer} +{delta_days:.1f} days ({severity})")

        return signal
