"""
DenialScope computation service.

Computes daily aggregates and denial signals from ClaimRecord data.
"""

from datetime import timedelta
from django.db import transaction
from django.db.models import Count, Sum, Q
from django.utils import timezone

from upstream.constants import DENIAL_DOLLARS_SPIKE_THRESHOLD
from upstream.models import ClaimRecord
from upstream.ingestion.services import publish_event
from upstream.products.denialscope.models import DenialAggregate, DenialSignal


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
                aggregate_date__lt=end_date,
            ).delete()

            # Compute daily aggregates
            aggregates = self._compute_daily_aggregates(start_date, end_date)
            DenialAggregate.objects.bulk_create(aggregates)

            # Clear existing signals for this run window (idempotent)
            DenialSignal.objects.filter(
                customer=self.customer,
                window_start_date__gte=start_date,
                window_end_date__lte=end_date,
            ).delete()

            # Compute signals
            signals = self._compute_signals(start_date, end_date, min_volume)

            return {
                "aggregates_created": len(aggregates),
                "signals_created": len(signals),
                "start_date": start_date,
                "end_date": end_date,
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
            "submitted_date",
            "payer",
            "denial_reason_code",
            "denial_reason_text",
        ).annotate(
            total_submitted_count=Count("id"),
            total_submitted_dollars=Sum("allowed_amount"),
            denied_count=Count("id", filter=Q(outcome="DENIED")),
            denied_dollars=Sum("allowed_amount", filter=Q(outcome="DENIED")),
        )

        aggregates = []
        for row in aggregates_qs:
            total_submitted = row["total_submitted_count"] or 0
            denied_count = row["denied_count"] or 0

            denial_rate = 0.0
            if total_submitted > 0:
                denial_rate = denied_count / total_submitted

            denial_reason = (
                row["denial_reason_code"] or row["denial_reason_text"] or "DENIED"
            )

            aggregate = DenialAggregate(
                customer=self.customer,
                payer=row["payer"],
                denial_reason=denial_reason,
                cpt_code=None,
                aggregate_date=row["submitted_date"],
                denied_count=denied_count,
                denied_dollars=row["denied_dollars"] or 0,
                total_submitted_count=total_submitted,
                total_submitted_dollars=row["total_submitted_dollars"] or 0,
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

        # CRIT-5: Use database aggregation instead of Python iteration
        # Group aggregates by payer and denial_reason using database query
        baseline_grouped = self._group_aggregates_in_db(baseline_start, baseline_end)
        recent_grouped = self._group_aggregates_in_db(recent_start, recent_end)

        signals = []

        # Signal 1: New denial reason emergence
        for key, recent_data in recent_grouped.items():
            payer, denial_reason = key
            if (
                key not in baseline_grouped
                and recent_data["denied_count"] >= min_volume
            ):
                signal = self._create_signal(
                    signal_type="new_denial_reason",
                    payer=payer,
                    denial_reason=denial_reason,
                    window_start=recent_start,
                    window_end=recent_end,
                    severity="high",
                    confidence=0.8,
                    summary=(
                        f"New denial reason '{denial_reason}' appeared for {payer} "
                        f"with {recent_data['denied_count']} denials"
                    ),
                    details={
                        "denied_count": recent_data["denied_count"],
                        "recent_window": f"{recent_start} to {recent_end}",
                    },
                    aggregates=recent_data["aggregates"],
                )
                signals.append(signal)

        # Signal 2: Denial rate spike
        for key, recent_data in recent_grouped.items():
            payer, denial_reason = key
            baseline_data = baseline_grouped.get(key)
            if not baseline_data:
                continue

            baseline_denial_rate = 0
            if baseline_data["total_submitted_count"] > 0:
                baseline_denial_rate = (
                    baseline_data["denied_count"]
                    / baseline_data["total_submitted_count"]
                )

            recent_denial_rate = 0
            if recent_data["total_submitted_count"] > 0:
                recent_denial_rate = (
                    recent_data["denied_count"] / recent_data["total_submitted_count"]
                )

            if (
                recent_data["total_submitted_count"] >= min_volume
                and baseline_data["total_submitted_count"] >= min_volume
            ):
                rate_delta = recent_denial_rate - baseline_denial_rate
                if rate_delta >= 0.05 or (
                    baseline_denial_rate > 0
                    and rate_delta / baseline_denial_rate >= 0.5
                ):
                    severity = self._severity_from_delta(rate_delta)
                    confidence = min(
                        (
                            recent_data["total_submitted_count"]
                            + baseline_data["total_submitted_count"]
                        )
                        / (min_volume * 4),
                        1.0,
                    )

                    signal = self._create_signal(
                        signal_type="denial_rate_spike",
                        payer=payer,
                        denial_reason=denial_reason,
                        window_start=recent_start,
                        window_end=recent_end,
                        severity=severity,
                        confidence=confidence,
                        summary=(
                            f"Denial rate spiked for {payer} ({denial_reason}) "
                            f"from {baseline_denial_rate:.1%} "
                            f"to {recent_denial_rate:.1%}"
                        ),
                        details={
                            "baseline_denial_rate": baseline_denial_rate,
                            "recent_denial_rate": recent_denial_rate,
                            "rate_delta": rate_delta,
                            "baseline_count": baseline_data["total_submitted_count"],
                            "recent_count": recent_data["total_submitted_count"],
                        },
                        aggregates=recent_data["aggregates"],
                    )
                    signals.append(signal)

        # Signal 3: Denial dollars spike or volume spike
        for key, recent_data in recent_grouped.items():
            payer, denial_reason = key
            baseline_data = baseline_grouped.get(key)
            if not baseline_data:
                continue

            # Prefer dollars if available
            if (
                baseline_data["denied_dollars"] > 0
                and recent_data["denied_dollars"] > 0
            ):
                baseline_value = baseline_data["denied_dollars"]
                recent_value = recent_data["denied_dollars"]
                signal_type = "denial_dollars_spike"
                label = "denial dollars"
            else:
                baseline_value = baseline_data["denied_count"]
                recent_value = recent_data["denied_count"]
                signal_type = "denial_volume_spike"
                label = "denial volume"

            if baseline_value >= min_volume and recent_value >= min_volume:
                delta = recent_value - baseline_value
                if baseline_value > 0 and delta / baseline_value >= 0.5:
                    severity = self._severity_from_delta(delta / baseline_value)
                    confidence = min(
                        (recent_value + baseline_value) / (min_volume * 4), 1.0
                    )

                    signal = self._create_signal(
                        signal_type=signal_type,
                        payer=payer,
                        denial_reason=denial_reason,
                        window_start=recent_start,
                        window_end=recent_end,
                        severity=severity,
                        confidence=confidence,
                        summary=(
                            f"{label.title()} spiked for {payer} ({denial_reason}) "
                            f"from {baseline_value:.0f} to {recent_value:.0f}"
                        ),
                        details={
                            "baseline_value": baseline_value,
                            "recent_value": recent_value,
                            "delta": delta,
                            "metric": label,
                        },
                        aggregates=recent_data["aggregates"],
                    )
                    signals.append(signal)

        # Signal 4: Absolute denial dollars spike (>$50K threshold)
        # This detects when weekly denied dollars exceed the threshold
        # regardless of relative change from baseline
        for key, recent_data in recent_grouped.items():
            payer, denial_reason = key
            denied_dollars = recent_data["denied_dollars"]

            if denied_dollars >= DENIAL_DOLLARS_SPIKE_THRESHOLD:
                # Calculate severity based on how far over threshold
                severity = self._severity_from_dollars_spike(denied_dollars)
                confidence = min(
                    denied_dollars / (DENIAL_DOLLARS_SPIKE_THRESHOLD * 2), 1.0
                )

                signal = self._create_signal(
                    signal_type="denial_dollars_spike",
                    payer=payer,
                    denial_reason=denial_reason,
                    window_start=recent_start,
                    window_end=recent_end,
                    severity=severity,
                    confidence=confidence,
                    summary=(
                        f"Weekly denied dollars for {payer} ({denial_reason}) "
                        f"exceeded ${DENIAL_DOLLARS_SPIKE_THRESHOLD:,.0f} threshold: "
                        f"${denied_dollars:,.2f}"
                    ),
                    details={
                        "denied_dollars": denied_dollars,
                        "threshold": DENIAL_DOLLARS_SPIKE_THRESHOLD,
                        "payer": payer,
                        "denial_reason": denial_reason,
                        "window_start": recent_start.isoformat(),
                        "window_end": recent_end.isoformat(),
                    },
                    aggregates=recent_data["aggregates"],
                )
                signals.append(signal)

        return signals

    def _group_aggregates_in_db(self, start_date, end_date):
        """
        Group aggregates by payer and denial_reason using database aggregation.

        Returns dict keyed by (payer, denial_reason) with summed values.
        """
        # Use database aggregation to group by payer and denial_reason
        grouped_data = (
            DenialAggregate.objects.filter(
                customer=self.customer,
                aggregate_date__gte=start_date,
                aggregate_date__lt=end_date,
            )
            .values("payer", "denial_reason")
            .annotate(
                total_denied=Sum("denied_count"),
                total_denied_dollars=Sum("denied_dollars"),
                total_submitted=Sum("total_submitted_count"),
                total_submitted_dollars=Sum("total_submitted_dollars"),
            )
        )

        # Convert to dict keyed by (payer, denial_reason)
        result = {}
        for row in grouped_data:
            key = (row["payer"], row["denial_reason"])
            result[key] = {
                "denied_count": row["total_denied"] or 0,
                "denied_dollars": float(row["total_denied_dollars"] or 0),
                "total_submitted_count": row["total_submitted"] or 0,
                "total_submitted_dollars": float(row["total_submitted_dollars"] or 0),
                "aggregates": [],  # Populated on-demand when creating signals
            }
        return result

    def _severity_from_delta(self, delta):
        """Map delta ratio to severity level."""
        if delta >= 1.0:
            return "critical"
        if delta >= 0.75:
            return "high"
        if delta >= 0.5:
            return "medium"
        return "low"

    def _severity_from_dollars_spike(self, denied_dollars):
        """Map absolute denied dollars to severity level based on threshold multiples."""
        ratio = denied_dollars / DENIAL_DOLLARS_SPIKE_THRESHOLD
        if ratio >= 3.0:  # 3x threshold ($150K+)
            return "critical"
        if ratio >= 2.0:  # 2x threshold ($100K+)
            return "high"
        if ratio >= 1.5:  # 1.5x threshold ($75K+)
            return "medium"
        return "low"  # Just over threshold

    def _create_signal(
        self,
        signal_type,
        payer,
        denial_reason,
        window_start,
        window_end,
        severity,
        confidence,
        summary,
        details,
        aggregates,
    ):
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

        # CRIT-5: Fetch related aggregates from DB instead of passing them
        # This is more efficient when using database aggregation
        related_aggs = DenialAggregate.objects.filter(
            customer=self.customer,
            payer=payer,
            denial_reason=denial_reason,
            aggregate_date__gte=window_start,
            aggregate_date__lt=window_end,
        )
        if related_aggs.exists():
            signal.related_aggregates.add(*related_aggs)

        # Publish SystemEvent
        publish_event(
            customer=self.customer,
            event_type="denialscope_signal_created",
            payload={
                "title": f"DenialScope: {signal.get_signal_type_display()}",
                "summary": summary,
                "signal_type": signal_type,
                "payer": payer,
                "denial_reason": denial_reason,
                "severity": severity,
                "details": details,
            },
        )

        return signal
