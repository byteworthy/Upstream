"""
DenialScope computation service.

Computes daily aggregates and denial signals from ClaimRecord data.
"""

from datetime import timedelta
from django.db import transaction
from django.db.models import Count, Sum, Q
from django.utils import timezone

from payrixa.models import ClaimRecord
from payrixa.ingestion.services import publish_event
from payrixa.products.denialscope.models import DenialAggregate, DenialSignal


class DenialScopeComputationService:
    """
    Service to compute DenialScope aggregates and signals.
    """

    def __init__(self, customer):
        self.customer = customer

    def compute(self, start_date=None, end_date=None, min_volume=10):
        """
        Compute aggregates and signals for a date range.
        
        Args:
            start_date: Start date (inclusive). Defaults to 30 days ago.
            end_date: End date (exclusive). Defaults to today.
            min_volume: Minimum volume threshold for signals.
        
        Returns:
            dict with computed aggregates count and signals count
        """
        if end_date is None:
            end_date = timezone.now().date()
        if start_date is None:
            start_date = end_date - timedelta(days=30)

        with transaction.atomic():
            # Clear existing aggregates in range (idempotent)
            DenialAggregate.objects.filter(
                customer=self.customer,
                aggregate_date__gte=start_date,
                aggregate_date__lt=end_date
            ).delete()

            # Compute daily aggregates
            aggregates = self._compute_daily_aggregates(start_date, end_date)
            DenialAggregate.objects.bulk_create(aggregates)

            # Clear existing signals for this run window (idempotent)
            DenialSignal.objects.filter(
                customer=self.customer,
                window_start_date__gte=start_date,
                window_end_date__lte=end_date
            ).delete()

            # Compute signals
            signals = self._compute_signals(start_date, end_date, min_volume)

            return {
                'aggregates_created': len(aggregates),
                'signals_created': len(signals),
                'start_date': start_date,
                'end_date': end_date,
            }

    def _compute_daily_aggregates(self, start_date, end_date):
        """Compute daily denial aggregates by payer and reason."""
        # Base queryset
        base_qs = ClaimRecord.objects.filter(
            customer=self.customer,
            submitted_date__gte=start_date,
            submitted_date__lt=end_date,
        )

        # Aggregate by day, payer, and denial reason
        aggregates_qs = base_qs.values(
            'submitted_date',
            'payer',
            'denial_reason_code',
            'denial_reason_text',
        ).annotate(
            total_submitted_count=Count('id'),
            total_submitted_dollars=Sum('allowed_amount'),
            denied_count=Count('id', filter=Q(outcome='DENIED')),
            denied_dollars=Sum('allowed_amount', filter=Q(outcome='DENIED')),
        )

        aggregates = []
        for row in aggregates_qs:
            total_submitted = row['total_submitted_count'] or 0
            denied_count = row['denied_count'] or 0

            denial_rate = 0.0
            if total_submitted > 0:
                denial_rate = denied_count / total_submitted

            denial_reason = row['denial_reason_code'] or row['denial_reason_text'] or 'DENIED'

            aggregate = DenialAggregate(
                customer=self.customer,
                payer=row['payer'],
                denial_reason=denial_reason,
                cpt_code=None,
                aggregate_date=row['submitted_date'],
                denied_count=denied_count,
                denied_dollars=row['denied_dollars'] or 0,
                total_submitted_count=total_submitted,
                total_submitted_dollars=row['total_submitted_dollars'] or 0,
                denial_rate=denial_rate,
            )
            aggregates.append(aggregate)

        return aggregates

    def _compute_signals(self, start_date, end_date, min_volume):
        """
        Compute DenialScope signals using simple baseline vs recent windows.
        """
        # Define windows
        recent_end = end_date
        recent_start = max(start_date, end_date - timedelta(days=7))
        baseline_end = recent_start
        baseline_start = max(start_date, baseline_end - timedelta(days=21))

        # Fetch aggregates for baseline and recent
        baseline_aggregates = DenialAggregate.objects.filter(
            customer=self.customer,
            aggregate_date__gte=baseline_start,
            aggregate_date__lt=baseline_end
        )

        recent_aggregates = DenialAggregate.objects.filter(
            customer=self.customer,
            aggregate_date__gte=recent_start,
            aggregate_date__lt=recent_end
        )

        # Group aggregates by payer and reason
        def group_aggregates(aggregates_qs):
            grouped = {}
            for agg in aggregates_qs:
                key = (agg.payer, agg.denial_reason)
                if key not in grouped:
                    grouped[key] = {
                        'denied_count': 0,
                        'denied_dollars': 0,
                        'total_submitted_count': 0,
                        'total_submitted_dollars': 0,
                        'aggregates': []
                    }
                grouped[key]['denied_count'] += agg.denied_count
                grouped[key]['denied_dollars'] += float(agg.denied_dollars)
                grouped[key]['total_submitted_count'] += agg.total_submitted_count
                grouped[key]['total_submitted_dollars'] += float(agg.total_submitted_dollars)
                grouped[key]['aggregates'].append(agg)
            return grouped

        baseline_grouped = group_aggregates(baseline_aggregates)
        recent_grouped = group_aggregates(recent_aggregates)

        signals = []

        # Signal 1: New denial reason emergence
        for key, recent_data in recent_grouped.items():
            payer, denial_reason = key
            if key not in baseline_grouped and recent_data['denied_count'] >= min_volume:
                signal = self._create_signal(
                    signal_type='new_denial_reason',
                    payer=payer,
                    denial_reason=denial_reason,
                    window_start=recent_start,
                    window_end=recent_end,
                    severity='high',
                    confidence=0.8,
                    summary=f"New denial reason '{denial_reason}' appeared for {payer} with {recent_data['denied_count']} denials",
                    details={
                        'denied_count': recent_data['denied_count'],
                        'recent_window': f"{recent_start} to {recent_end}"
                    },
                    aggregates=recent_data['aggregates']
                )
                signals.append(signal)

        # Signal 2: Denial rate spike
        for key, recent_data in recent_grouped.items():
            payer, denial_reason = key
            baseline_data = baseline_grouped.get(key)
            if not baseline_data:
                continue

            baseline_denial_rate = 0
            if baseline_data['total_submitted_count'] > 0:
                baseline_denial_rate = baseline_data['denied_count'] / baseline_data['total_submitted_count']

            recent_denial_rate = 0
            if recent_data['total_submitted_count'] > 0:
                recent_denial_rate = recent_data['denied_count'] / recent_data['total_submitted_count']

            if recent_data['total_submitted_count'] >= min_volume and baseline_data['total_submitted_count'] >= min_volume:
                rate_delta = recent_denial_rate - baseline_denial_rate
                if rate_delta >= 0.05 or (baseline_denial_rate > 0 and rate_delta / baseline_denial_rate >= 0.5):
                    severity = self._severity_from_delta(rate_delta)
                    confidence = min((recent_data['total_submitted_count'] + baseline_data['total_submitted_count']) / (min_volume * 4), 1.0)

                    signal = self._create_signal(
                        signal_type='denial_rate_spike',
                        payer=payer,
                        denial_reason=denial_reason,
                        window_start=recent_start,
                        window_end=recent_end,
                        severity=severity,
                        confidence=confidence,
                        summary=f"Denial rate spiked for {payer} ({denial_reason}) from {baseline_denial_rate:.1%} to {recent_denial_rate:.1%}",
                        details={
                            'baseline_denial_rate': baseline_denial_rate,
                            'recent_denial_rate': recent_denial_rate,
                            'rate_delta': rate_delta,
                            'baseline_count': baseline_data['total_submitted_count'],
                            'recent_count': recent_data['total_submitted_count']
                        },
                        aggregates=recent_data['aggregates']
                    )
                    signals.append(signal)

        # Signal 3: Denial dollars spike or volume spike
        for key, recent_data in recent_grouped.items():
            payer, denial_reason = key
            baseline_data = baseline_grouped.get(key)
            if not baseline_data:
                continue

            # Prefer dollars if available
            if baseline_data['denied_dollars'] > 0 and recent_data['denied_dollars'] > 0:
                baseline_value = baseline_data['denied_dollars']
                recent_value = recent_data['denied_dollars']
                signal_type = 'denial_dollars_spike'
                label = 'denial dollars'
            else:
                baseline_value = baseline_data['denied_count']
                recent_value = recent_data['denied_count']
                signal_type = 'denial_volume_spike'
                label = 'denial volume'

            if baseline_value >= min_volume and recent_value >= min_volume:
                delta = recent_value - baseline_value
                if baseline_value > 0 and delta / baseline_value >= 0.5:
                    severity = self._severity_from_delta(delta / baseline_value)
                    confidence = min((recent_value + baseline_value) / (min_volume * 4), 1.0)

                    signal = self._create_signal(
                        signal_type=signal_type,
                        payer=payer,
                        denial_reason=denial_reason,
                        window_start=recent_start,
                        window_end=recent_end,
                        severity=severity,
                        confidence=confidence,
                        summary=f"{label.title()} spiked for {payer} ({denial_reason}) from {baseline_value:.0f} to {recent_value:.0f}",
                        details={
                            'baseline_value': baseline_value,
                            'recent_value': recent_value,
                            'delta': delta,
                            'metric': label
                        },
                        aggregates=recent_data['aggregates']
                    )
                    signals.append(signal)

        return signals

    def _severity_from_delta(self, delta):
        """Map delta ratio to severity level."""
        if delta >= 1.0:
            return 'critical'
        if delta >= 0.75:
            return 'high'
        if delta >= 0.5:
            return 'medium'
        return 'low'

    def _create_signal(self, signal_type, payer, denial_reason, window_start, window_end,
                       severity, confidence, summary, details, aggregates):
        """Create signal and publish SystemEvent."""
        signal = DenialSignal.objects.create(
            customer=self.customer,
            signal_type=signal_type,
            payer=payer,
            denial_reason=denial_reason,
            window_start_date=window_start,
            window_end_date=window_end,
            severity=severity,
            confidence=confidence,
            summary_text=summary,
            details=details,
        )

        if aggregates:
            signal.related_aggregates.add(*aggregates)

        # Publish SystemEvent
        publish_event(
            customer=self.customer,
            event_type='denialscope_signal_created',
            payload={
                'title': f"DenialScope: {signal.get_signal_type_display()}",
                'summary': summary,
                'signal_type': signal_type,
                'payer': payer,
                'denial_reason': denial_reason,
                'severity': severity,
                'details': details
            }
        )

        return signal
