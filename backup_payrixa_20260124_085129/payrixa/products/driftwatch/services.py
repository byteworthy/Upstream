"""
DriftWatch Advanced Signal Detection Service.

Implements comprehensive payer behavior monitoring with multiple signal types:
- Denial Rate Drift
- Payment Amount Variance (Underpayment Detection)
- Payment Delay
- Authorization Failure Spike
- Approval Rate Changes
- Processing Time Drift

Each signal includes statistical confidence scoring, baseline comparison,
and actionable intelligence for revenue recovery.
"""

from datetime import timedelta
from decimal import Decimal
from django.db import transaction
from django.db.models import Count, Sum, Avg, StdDev, Q, F
from django.utils import timezone
import numpy as np
from typing import Dict, List, Tuple, Optional

from upstream.models import ClaimRecord, DriftEvent, ReportRun
from upstream.ingestion.services import publish_event


class DriftWatchSignalService:
    """
    Advanced multi-dimensional payer drift detection.

    Detects 6 types of drift signals with statistical rigor:
    1. Denial Rate Drift
    2. Underpayment Variance
    3. Payment Delay
    4. Authorization Failure Spike
    5. Approval Rate Decline
    6. Processing Time Drift
    """

    # Statistical thresholds
    MIN_SAMPLE_SIZE = 20  # Minimum claims for statistical significance
    SIGNIFICANCE_THRESHOLD = 0.05  # p-value threshold

    # Business thresholds
    DENIAL_RATE_THRESHOLD = 0.05  # 5 percentage point increase
    UNDERPAYMENT_THRESHOLD = 0.05  # 5% underpayment
    PAYMENT_DELAY_THRESHOLD = 7  # 7 days increase
    AUTH_FAILURE_THRESHOLD = 0.10  # 10 percentage point increase

    def __init__(self, customer):
        self.customer = customer

    @transaction.atomic
    def compute_all_signals(self, report_run: ReportRun, start_date=None, end_date=None) -> Dict:
        """
        Compute all drift signals for a report run.

        Returns summary of signals created by type.
        """
        if end_date is None:
            end_date = timezone.now().date()
        if start_date is None:
            start_date = end_date - timedelta(days=90)

        # Define time windows
        current_end = end_date
        current_start = max(start_date, current_end - timedelta(days=14))
        baseline_end = current_start
        baseline_start = max(start_date, baseline_end - timedelta(days=90))

        results = {
            'signals_created': 0,
            'by_type': {},
            'baseline_window': (baseline_start, baseline_end),
            'current_window': (current_start, current_end),
        }

        # 1. Denial Rate Drift
        denial_signals = self.detect_denial_rate_drift(
            report_run, baseline_start, baseline_end, current_start, current_end
        )
        results['by_type']['denial_rate'] = len(denial_signals)
        results['signals_created'] += len(denial_signals)

        # 2. Underpayment Variance
        underpayment_signals = self.detect_underpayment_variance(
            report_run, baseline_start, baseline_end, current_start, current_end
        )
        results['by_type']['underpayment'] = len(underpayment_signals)
        results['signals_created'] += len(underpayment_signals)

        # 3. Payment Delay
        delay_signals = self.detect_payment_delay(
            report_run, baseline_start, baseline_end, current_start, current_end
        )
        results['by_type']['payment_delay'] = len(delay_signals)
        results['signals_created'] += len(delay_signals)

        # 4. Authorization Failure Spike
        auth_signals = self.detect_auth_failure_spike(
            report_run, baseline_start, baseline_end, current_start, current_end
        )
        results['by_type']['auth_failure'] = len(auth_signals)
        results['signals_created'] += len(auth_signals)

        # 5. Approval Rate Decline
        approval_signals = self.detect_approval_rate_decline(
            report_run, baseline_start, baseline_end, current_start, current_end
        )
        results['by_type']['approval_rate'] = len(approval_signals)
        results['signals_created'] += len(approval_signals)

        # 6. Processing Time Drift
        processing_signals = self.detect_processing_time_drift(
            report_run, baseline_start, baseline_end, current_start, current_end
        )
        results['by_type']['processing_time'] = len(processing_signals)
        results['signals_created'] += len(processing_signals)

        return results

    def detect_denial_rate_drift(
        self, report_run, baseline_start, baseline_end, current_start, current_end
    ) -> List[DriftEvent]:
        """Detect denial rate drift by payer and CPT group."""
        signals = []

        # Group claims by payer and CPT group
        baseline_stats = self._get_denial_stats(baseline_start, baseline_end)
        current_stats = self._get_denial_stats(current_start, current_end)

        for key, current_data in current_stats.items():
            payer, cpt_group = key
            baseline_data = baseline_stats.get(key)

            if not baseline_data:
                continue

            # Require minimum sample size
            if (baseline_data['total'] < self.MIN_SAMPLE_SIZE or
                current_data['total'] < self.MIN_SAMPLE_SIZE):
                continue

            baseline_rate = baseline_data['denial_rate']
            current_rate = current_data['denial_rate']
            delta = current_rate - baseline_rate

            # Check if drift exceeds threshold
            if delta >= self.DENIAL_RATE_THRESHOLD:
                # Calculate statistical confidence
                confidence, p_value = self._calculate_proportion_confidence(
                    baseline_data['denials'], baseline_data['total'],
                    current_data['denials'], current_data['total']
                )

                # Calculate severity
                severity = self._calculate_severity(delta, baseline_rate)

                # Estimate revenue impact
                avg_allowed = current_data['avg_allowed'] or Decimal('0')
                estimated_impact = float(delta * current_data['total'] * avg_allowed)

                signal = DriftEvent.objects.create(
                    customer=self.customer,
                    report_run=report_run,
                    payer=payer,
                    cpt_group=cpt_group,
                    drift_type='DENIAL_RATE',
                    baseline_value=baseline_rate,
                    current_value=current_rate,
                    delta_value=delta,
                    severity=severity,
                    confidence=confidence,
                    baseline_start=baseline_start,
                    baseline_end=baseline_end,
                    current_start=current_start,
                    current_end=current_end,
                    baseline_sample_size=baseline_data['total'],
                    current_sample_size=current_data['total'],
                    baseline_std_dev=baseline_data.get('std_dev'),
                    statistical_significance=p_value,
                    estimated_revenue_impact=Decimal(str(estimated_impact)),
                    trend_direction='degrading',
                    potential_root_causes=[
                        {'cause': 'Payer policy change', 'likelihood': 0.7},
                        {'cause': 'Coding issues', 'likelihood': 0.5},
                        {'cause': 'Documentation deficiency', 'likelihood': 0.4},
                    ]
                )

                signals.append(signal)

                # Publish event
                self._publish_drift_event(signal, 'Denial Rate Drift')

        return signals

    def detect_underpayment_variance(
        self, report_run, baseline_start, baseline_end, current_start, current_end
    ) -> List[DriftEvent]:
        """
        Detect underpayment variance - payers paying less than historical baseline.

        This is HIGH SIGNAL for revenue recovery opportunities.
        """
        signals = []

        # Get payment stats by payer and CPT
        baseline_stats = self._get_payment_stats(baseline_start, baseline_end)
        current_stats = self._get_payment_stats(current_start, current_end)

        for key, current_data in current_stats.items():
            payer, cpt_group = key
            baseline_data = baseline_stats.get(key)

            if not baseline_data:
                continue

            # Require minimum sample size
            if (baseline_data['count'] < self.MIN_SAMPLE_SIZE or
                current_data['count'] < self.MIN_SAMPLE_SIZE):
                continue

            baseline_avg = float(baseline_data['avg_allowed'])
            current_avg = float(current_data['avg_allowed'])

            if baseline_avg == 0:
                continue

            # Calculate variance percentage
            variance = (baseline_avg - current_avg) / baseline_avg

            # Alert if underpayment exceeds threshold
            if variance >= self.UNDERPAYMENT_THRESHOLD:
                # Calculate revenue impact
                total_impact = variance * baseline_avg * current_data['count']

                # Statistical confidence
                confidence = self._calculate_continuous_confidence(
                    baseline_data['count'], baseline_data.get('std_dev', 0),
                    current_data['count'], current_data.get('std_dev', 0)
                )

                severity = self._calculate_severity(variance, 0.05)

                signal = DriftEvent.objects.create(
                    customer=self.customer,
                    report_run=report_run,
                    payer=payer,
                    cpt_group=cpt_group,
                    drift_type='PAYMENT_AMOUNT',
                    baseline_value=baseline_avg,
                    current_value=current_avg,
                    delta_value=baseline_avg - current_avg,
                    severity=severity,
                    confidence=confidence,
                    baseline_start=baseline_start,
                    baseline_end=baseline_end,
                    current_start=current_start,
                    current_end=current_end,
                    baseline_sample_size=baseline_data['count'],
                    current_sample_size=current_data['count'],
                    baseline_std_dev=baseline_data.get('std_dev'),
                    estimated_revenue_impact=Decimal(str(total_impact)),
                    trend_direction='degrading',
                    potential_root_causes=[
                        {'cause': 'Contract violation', 'likelihood': 0.8},
                        {'cause': 'Reimbursement rate reduction', 'likelihood': 0.6},
                        {'cause': 'Modifier bundling', 'likelihood': 0.5},
                    ]
                )

                signals.append(signal)
                self._publish_drift_event(signal, 'Underpayment Variance')

        return signals

    def detect_payment_delay(
        self, report_run, baseline_start, baseline_end, current_start, current_end
    ) -> List[DriftEvent]:
        """Detect increases in payment processing time."""
        signals = []

        # Get payment timing stats
        baseline_stats = self._get_payment_timing_stats(baseline_start, baseline_end)
        current_stats = self._get_payment_timing_stats(current_start, current_end)

        for key, current_data in current_stats.items():
            payer, cpt_group = key
            baseline_data = baseline_stats.get(key)

            if not baseline_data:
                continue

            if (baseline_data['count'] < self.MIN_SAMPLE_SIZE or
                current_data['count'] < self.MIN_SAMPLE_SIZE):
                continue

            baseline_days = baseline_data['avg_days']
            current_days = current_data['avg_days']
            delta_days = current_days - baseline_days

            # Alert if delay increased significantly
            if delta_days >= self.PAYMENT_DELAY_THRESHOLD:
                confidence = self._calculate_continuous_confidence(
                    baseline_data['count'], baseline_data.get('std_dev', 0),
                    current_data['count'], current_data.get('std_dev', 0)
                )

                severity = self._calculate_severity(delta_days / 30, 0.2)  # Normalize to 0-1

                # Calculate cash flow impact (time value of money)
                avg_payment = current_data.get('avg_payment', 0)
                cash_flow_impact = (delta_days / 365) * avg_payment * current_data['count']

                signal = DriftEvent.objects.create(
                    customer=self.customer,
                    report_run=report_run,
                    payer=payer,
                    cpt_group=cpt_group,
                    drift_type='PROCESSING_DELAY',
                    baseline_value=baseline_days,
                    current_value=current_days,
                    delta_value=delta_days,
                    severity=severity,
                    confidence=confidence,
                    baseline_start=baseline_start,
                    baseline_end=baseline_end,
                    current_start=current_start,
                    current_end=current_end,
                    baseline_sample_size=baseline_data['count'],
                    current_sample_size=current_data['count'],
                    baseline_std_dev=baseline_data.get('std_dev'),
                    estimated_revenue_impact=Decimal(str(cash_flow_impact)),
                    trend_direction='degrading',
                    potential_root_causes=[
                        {'cause': 'Payer cash flow issues', 'likelihood': 0.6},
                        {'cause': 'Increased claim review', 'likelihood': 0.5},
                        {'cause': 'System processing delays', 'likelihood': 0.4},
                    ]
                )

                signals.append(signal)
                self._publish_drift_event(signal, 'Payment Delay')

        return signals

    def detect_auth_failure_spike(
        self, report_run, baseline_start, baseline_end, current_start, current_end
    ) -> List[DriftEvent]:
        """Detect spikes in authorization-related denials."""
        signals = []

        # Get auth denial stats
        baseline_stats = self._get_auth_denial_stats(baseline_start, baseline_end)
        current_stats = self._get_auth_denial_stats(current_start, current_end)

        for key, current_data in current_stats.items():
            payer, cpt_group = key
            baseline_data = baseline_stats.get(key)

            if not baseline_data:
                continue

            if (baseline_data['total'] < self.MIN_SAMPLE_SIZE or
                current_data['total'] < self.MIN_SAMPLE_SIZE):
                continue

            baseline_rate = baseline_data['auth_failure_rate']
            current_rate = current_data['auth_failure_rate']
            delta = current_rate - baseline_rate

            if delta >= self.AUTH_FAILURE_THRESHOLD:
                confidence, p_value = self._calculate_proportion_confidence(
                    baseline_data['auth_failures'], baseline_data['total'],
                    current_data['auth_failures'], current_data['total']
                )

                severity = self._calculate_severity(delta, 0.1)

                # Revenue impact = failed auths * avg claim value
                avg_allowed = current_data.get('avg_allowed', Decimal('0'))
                impact = float(current_data['auth_failures'] * avg_allowed)

                signal = DriftEvent.objects.create(
                    customer=self.customer,
                    report_run=report_run,
                    payer=payer,
                    cpt_group=cpt_group,
                    drift_type='AUTH_FAILURE_RATE',
                    baseline_value=baseline_rate,
                    current_value=current_rate,
                    delta_value=delta,
                    severity=severity,
                    confidence=confidence,
                    baseline_start=baseline_start,
                    baseline_end=baseline_end,
                    current_start=current_start,
                    current_end=current_end,
                    baseline_sample_size=baseline_data['total'],
                    current_sample_size=current_data['total'],
                    statistical_significance=p_value,
                    estimated_revenue_impact=Decimal(str(impact)),
                    trend_direction='degrading',
                    potential_root_causes=[
                        {'cause': 'Authorization policy change', 'likelihood': 0.8},
                        {'cause': 'Internal workflow breakdown', 'likelihood': 0.6},
                        {'cause': 'New CPT code requirements', 'likelihood': 0.5},
                    ]
                )

                signals.append(signal)
                self._publish_drift_event(signal, 'Authorization Failure Spike')

        return signals

    def detect_approval_rate_decline(
        self, report_run, baseline_start, baseline_end, current_start, current_end
    ) -> List[DriftEvent]:
        """Detect decline in approval rates (inverse of denial rate with nuance)."""
        signals = []

        # Similar to denial rate but focuses on approved claims
        baseline_stats = self._get_approval_stats(baseline_start, baseline_end)
        current_stats = self._get_approval_stats(current_start, current_end)

        for key, current_data in current_stats.items():
            payer, cpt_group = key
            baseline_data = baseline_stats.get(key)

            if not baseline_data:
                continue

            if (baseline_data['total'] < self.MIN_SAMPLE_SIZE or
                current_data['total'] < self.MIN_SAMPLE_SIZE):
                continue

            baseline_rate = baseline_data['approval_rate']
            current_rate = current_data['approval_rate']
            delta = baseline_rate - current_rate  # Decline is negative

            # Alert if approval rate declined significantly
            if delta >= 0.05:  # 5% decline
                confidence, p_value = self._calculate_proportion_confidence(
                    baseline_data['approved'], baseline_data['total'],
                    current_data['approved'], current_data['total']
                )

                severity = self._calculate_severity(delta, 0.05)

                signal = DriftEvent.objects.create(
                    customer=self.customer,
                    report_run=report_run,
                    payer=payer,
                    cpt_group=cpt_group,
                    drift_type='APPROVAL_RATE',
                    baseline_value=baseline_rate,
                    current_value=current_rate,
                    delta_value=-delta,  # Make positive for display
                    severity=severity,
                    confidence=confidence,
                    baseline_start=baseline_start,
                    baseline_end=baseline_end,
                    current_start=current_start,
                    current_end=current_end,
                    baseline_sample_size=baseline_data['total'],
                    current_sample_size=current_data['total'],
                    statistical_significance=p_value,
                    trend_direction='degrading',
                )

                signals.append(signal)
                self._publish_drift_event(signal, 'Approval Rate Decline')

        return signals

    def detect_processing_time_drift(
        self, report_run, baseline_start, baseline_end, current_start, current_end
    ) -> List[DriftEvent]:
        """Detect changes in claim adjudication time (submitted to decided)."""
        signals = []

        baseline_stats = self._get_processing_time_stats(baseline_start, baseline_end)
        current_stats = self._get_processing_time_stats(current_start, current_end)

        for key, current_data in current_stats.items():
            payer, cpt_group = key
            baseline_data = baseline_stats.get(key)

            if not baseline_data:
                continue

            if (baseline_data['count'] < self.MIN_SAMPLE_SIZE or
                current_data['count'] < self.MIN_SAMPLE_SIZE):
                continue

            baseline_days = baseline_data['avg_days']
            current_days = current_data['avg_days']
            delta_days = current_days - baseline_days

            # Alert if processing time increased by 5+ days
            if delta_days >= 5:
                confidence = self._calculate_continuous_confidence(
                    baseline_data['count'], baseline_data.get('std_dev', 0),
                    current_data['count'], current_data.get('std_dev', 0)
                )

                severity = self._calculate_severity(delta_days / 30, 0.2)

                signal = DriftEvent.objects.create(
                    customer=self.customer,
                    report_run=report_run,
                    payer=payer,
                    cpt_group=cpt_group,
                    drift_type='DECISION_TIME',
                    baseline_value=baseline_days,
                    current_value=current_days,
                    delta_value=delta_days,
                    severity=severity,
                    confidence=confidence,
                    baseline_start=baseline_start,
                    baseline_end=baseline_end,
                    current_start=current_start,
                    current_end=current_end,
                    baseline_sample_size=baseline_data['count'],
                    current_sample_size=current_data['count'],
                    baseline_std_dev=baseline_data.get('std_dev'),
                    trend_direction='degrading',
                )

                signals.append(signal)
                self._publish_drift_event(signal, 'Processing Time Drift')

        return signals

    # === Helper Methods: Stats Aggregation ===

    def _get_denial_stats(self, start_date, end_date) -> Dict:
        """Get denial statistics grouped by payer and CPT group."""
        stats = {}

        claims = ClaimRecord.objects.filter(
            customer=self.customer,
            decided_date__gte=start_date,
            decided_date__lt=end_date
        ).values('payer', 'cpt_group').annotate(
            total=Count('id'),
            denials=Count('id', filter=Q(outcome='DENIED')),
            avg_allowed=Avg('allowed_amount')
        )

        for row in claims:
            key = (row['payer'], row['cpt_group'])
            total = row['total']
            denials = row['denials']

            stats[key] = {
                'total': total,
                'denials': denials,
                'denial_rate': denials / total if total > 0 else 0,
                'avg_allowed': row['avg_allowed'],
            }

        return stats

    def _get_payment_stats(self, start_date, end_date) -> Dict:
        """Get payment amount statistics."""
        stats = {}

        claims = ClaimRecord.objects.filter(
            customer=self.customer,
            decided_date__gte=start_date,
            decided_date__lt=end_date,
            outcome='PAID',
            allowed_amount__isnull=False
        ).values('payer', 'cpt_group').annotate(
            count=Count('id'),
            avg_allowed=Avg('allowed_amount'),
            std_dev=StdDev('allowed_amount')
        )

        for row in claims:
            key = (row['payer'], row['cpt_group'])
            stats[key] = {
                'count': row['count'],
                'avg_allowed': row['avg_allowed'],
                'std_dev': row['std_dev'],
            }

        return stats

    def _get_payment_timing_stats(self, start_date, end_date) -> Dict:
        """Get payment timing statistics."""
        stats = {}

        # Only include claims with payment_date
        claims = ClaimRecord.objects.filter(
            customer=self.customer,
            decided_date__gte=start_date,
            decided_date__lt=end_date,
            outcome='PAID',
            payment_date__isnull=False
        ).values('payer', 'cpt_group').annotate(
            count=Count('id'),
            avg_payment=Avg('paid_amount')
        )

        for row in claims:
            key = (row['payer'], row['cpt_group'])

            # Calculate average days to payment
            claim_subset = ClaimRecord.objects.filter(
                customer=self.customer,
                payer=row['payer'],
                cpt_group=row['cpt_group'],
                decided_date__gte=start_date,
                decided_date__lt=end_date,
                payment_date__isnull=False
            )

            days_list = []
            for claim in claim_subset:
                if claim.submitted_date and claim.payment_date:
                    days = (claim.payment_date - claim.submitted_date).days
                    days_list.append(days)

            if days_list:
                stats[key] = {
                    'count': row['count'],
                    'avg_days': np.mean(days_list),
                    'std_dev': np.std(days_list),
                    'avg_payment': row['avg_payment'],
                }

        return stats

    def _get_auth_denial_stats(self, start_date, end_date) -> Dict:
        """Get authorization failure statistics."""
        stats = {}

        # Claims requiring auth
        claims = ClaimRecord.objects.filter(
            customer=self.customer,
            decided_date__gte=start_date,
            decided_date__lt=end_date,
            authorization_required=True
        ).values('payer', 'cpt_group').annotate(
            total=Count('id'),
            auth_failures=Count('id', filter=Q(
                outcome='DENIED',
                denial_reason_code__icontains='auth'
            ) | Q(
                outcome='DENIED',
                denial_reason_text__icontains='authorization'
            )),
            avg_allowed=Avg('allowed_amount')
        )

        for row in claims:
            key = (row['payer'], row['cpt_group'])
            total = row['total']
            failures = row['auth_failures']

            stats[key] = {
                'total': total,
                'auth_failures': failures,
                'auth_failure_rate': failures / total if total > 0 else 0,
                'avg_allowed': row['avg_allowed'],
            }

        return stats

    def _get_approval_stats(self, start_date, end_date) -> Dict:
        """Get approval rate statistics."""
        stats = {}

        claims = ClaimRecord.objects.filter(
            customer=self.customer,
            decided_date__gte=start_date,
            decided_date__lt=end_date
        ).values('payer', 'cpt_group').annotate(
            total=Count('id'),
            approved=Count('id', filter=Q(outcome='PAID'))
        )

        for row in claims:
            key = (row['payer'], row['cpt_group'])
            total = row['total']
            approved = row['approved']

            stats[key] = {
                'total': total,
                'approved': approved,
                'approval_rate': approved / total if total > 0 else 0,
            }

        return stats

    def _get_processing_time_stats(self, start_date, end_date) -> Dict:
        """Get claim processing time statistics."""
        stats = {}

        claims = ClaimRecord.objects.filter(
            customer=self.customer,
            decided_date__gte=start_date,
            decided_date__lt=end_date
        ).values('payer', 'cpt_group')

        for row in claims.iterator():
            key = (row['payer'], row['cpt_group'])

            # Get days to decision for this group
            claim_subset = ClaimRecord.objects.filter(
                customer=self.customer,
                payer=row['payer'],
                cpt_group=row['cpt_group'],
                decided_date__gte=start_date,
                decided_date__lt=end_date
            )

            days_list = []
            for claim in claim_subset:
                if claim.submitted_date and claim.decided_date:
                    days = (claim.decided_date - claim.submitted_date).days
                    days_list.append(days)

            if days_list and len(days_list) >= self.MIN_SAMPLE_SIZE:
                stats[key] = {
                    'count': len(days_list),
                    'avg_days': np.mean(days_list),
                    'std_dev': np.std(days_list),
                }

        return stats

    # === Helper Methods: Statistics ===

    def _calculate_proportion_confidence(
        self, baseline_successes, baseline_total, current_successes, current_total
    ) -> Tuple[float, float]:
        """
        Calculate confidence and p-value for proportion comparison.

        Uses two-proportion z-test.
        """
        if baseline_total == 0 or current_total == 0:
            return 0.5, 1.0

        p1 = baseline_successes / baseline_total
        p2 = current_successes / current_total

        # Pooled proportion
        p_pool = (baseline_successes + current_successes) / (baseline_total + current_total)

        # Standard error
        se = np.sqrt(p_pool * (1 - p_pool) * (1/baseline_total + 1/current_total))

        if se == 0:
            return 0.5, 1.0

        # Z-score
        z = abs(p2 - p1) / se

        # Approximate p-value (two-tailed)
        from scipy import stats
        p_value = 2 * (1 - stats.norm.cdf(z))

        # Confidence based on sample size and significance
        confidence = min((baseline_total + current_total) / 100, 1.0)
        if p_value < 0.05:
            confidence = min(confidence + 0.2, 1.0)

        return confidence, p_value

    def _calculate_continuous_confidence(
        self, baseline_n, baseline_std, current_n, current_std
    ) -> float:
        """Calculate confidence for continuous variable comparison."""
        # Base confidence on sample sizes
        total_n = baseline_n + current_n
        confidence = min(total_n / 100, 0.9)

        # Increase confidence if low variance
        if baseline_std and current_std:
            avg_std = (baseline_std + current_std) / 2
            if avg_std < 10:  # Low variance
                confidence = min(confidence + 0.1, 1.0)

        return confidence

    def _calculate_severity(self, delta, threshold) -> float:
        """
        Calculate severity score (0.0 to 1.0) based on delta and threshold.

        Severity increases non-linearly with delta.
        """
        if delta <= threshold:
            return max(0.0, delta / threshold * 0.5)

        # Above threshold, severity increases more rapidly
        excess = (delta - threshold) / threshold
        severity = 0.5 + (0.5 * min(excess, 2.0) / 2.0)

        return min(severity, 1.0)

    def _publish_drift_event(self, signal: DriftEvent, event_title: str):
        """Publish system event for drift signal."""
        publish_event(
            customer=self.customer,
            event_type='driftwatch_signal_created',
            payload={
                'title': f"DriftWatch: {event_title}",
                'payer': signal.payer,
                'cpt_group': signal.cpt_group,
                'drift_type': signal.drift_type,
                'severity': signal.severity,
                'confidence': signal.confidence,
                'baseline_value': signal.baseline_value,
                'current_value': signal.current_value,
                'delta': signal.delta_value,
                'revenue_impact': float(signal.estimated_revenue_impact or 0),
                'summary': f"{signal.payer} - {signal.cpt_group}: {signal.drift_type} "
                          f"changed from {signal.baseline_value:.2f} to {signal.current_value:.2f}"
            }
        )
