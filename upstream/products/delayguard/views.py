"""
DelayGuard views.

Hub v1: Dashboard showing payment delay drift signals.
Reads from PaymentDelaySignal model.
"""

from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Avg, Max, Sum, Q
from django.utils import timezone
from datetime import timedelta
from django.core.cache import cache
import hashlib
import json

from upstream.utils import get_current_customer
from upstream.alerts.models import AlertEvent, OperatorJudgment
from upstream.products.delayguard.models import PaymentDelaySignal
from upstream.products.delayguard import DELAYGUARD_V1_SIGNAL_TYPE
from upstream.permissions import ProductEnabledMixin
from upstream.constants import (
    DELAYGUARD_URGENT_THRESHOLD_DAYS,
    DELAYGUARD_HIGH_THRESHOLD_DAYS,
    DELAYGUARD_MEDIUM_THRESHOLD_DAYS,
    DELAYGUARD_LOW_THRESHOLD_DAYS,
    CACHE_TTL_MEDIUM,  # 15 minutes
)


class DelayGuardDashboardView(LoginRequiredMixin, ProductEnabledMixin, TemplateView):
    """
    DelayGuard dashboard showing payment delay drift signals.

    Hub v1: Shows payment_delay_drift type only.
    Displays signals when payers are taking longer to process claims.
    """

    template_name = "upstream/products/delayguard_dashboard.html"
    product_slug = "delayguard"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        try:
            customer = get_current_customer(self.request)
            context["customer"] = customer

            # Get payment delay signals
            base_queryset = PaymentDelaySignal.objects.filter(
                customer=customer, signal_type="payment_delay_drift"
            )

            # Get recent signals for display
            # HIGH-3: Prefetch related alert events and judgments to avoid N+1 queries
            signals_qs = base_queryset.prefetch_related(
                "alert_events", "alert_events__operator_judgments"
            ).order_by("-created_at")[:50]

            # Build signal display data with interpretation
            signals = []
            for signal in signals_qs:
                # Get associated alert event (if exists) for operator feedback
                # Use prefetched data instead of querying
                alert_events = list(signal.alert_events.all())
                alert_event = alert_events[0] if alert_events else None

                latest_judgment = None
                if alert_event:
                    judgments = list(alert_event.operator_judgments.all())
                    if judgments:
                        # Sort in Python since already prefetched
                        latest_judgment = max(judgments, key=lambda j: j.created_at)

                # Check for similar alerts
                suppression_context = self._check_similar_alerts(customer, signal)

                # Calculate urgency based on severity and delta
                urgency_level, urgency_label = self._get_urgency(signal)

                signals.append(
                    {
                        "signal": signal,
                        "alert_event_id": alert_event.id if alert_event else None,
                        "payer": signal.payer,
                        "baseline_avg_days": signal.baseline_avg_days,
                        "current_avg_days": signal.current_avg_days,
                        "delta_days": signal.delta_days,
                        "delta_percent": signal.delta_percent,
                        "severity": signal.severity,
                        "confidence": signal.confidence,
                        "estimated_dollars_at_risk": signal.estimated_dollars_at_risk,
                        "created_at": signal.created_at,
                        "urgency_label": urgency_label,
                        "urgency_level": urgency_level,
                        "has_judgment": latest_judgment is not None,
                        "judgment_verdict": latest_judgment.verdict
                        if latest_judgment
                        else None,
                        "suppression_context": suppression_context,
                    }
                )

            # Optimize: Combine multiple separate queries into single aggregate
            # Before: 5 separate queries (total_signals, avg_delta, total_at_risk,
            #         critical_count, high_count)
            # After: 1 aggregate query with conditional aggregation
            summary_metrics = base_queryset.aggregate(
                total_signals=Count("id"),
                avg_delta=Avg("delta_days"),
                total_at_risk=Sum("estimated_dollars_at_risk"),
                critical_count=Count("id", filter=Q(severity="critical")),
                high_count=Count("id", filter=Q(severity="high")),
            )

            total_signals = summary_metrics["total_signals"] or 0
            avg_delta = summary_metrics["avg_delta"] or 0
            total_at_risk = summary_metrics["total_at_risk"] or 0
            critical_count = summary_metrics["critical_count"] or 0
            high_count = summary_metrics["high_count"] or 0

            # Top payers by delay frequency
            top_payers = (
                base_queryset.values("payer")
                .annotate(
                    signal_count=Count("id"),
                    avg_delta=Avg("delta_days"),
                    max_delta=Max("delta_days"),
                    total_at_risk=Sum("estimated_dollars_at_risk"),
                )
                .order_by("-signal_count")[:5]
            )

            # Recovery ledger stats
            recovery_stats = self._get_recovery_stats(customer)

            context.update(
                {
                    "signals": signals,
                    "total_signals": total_signals,
                    "avg_delta": avg_delta,
                    "total_at_risk": total_at_risk,
                    "top_payers": top_payers,
                    "critical_count": critical_count,
                    "high_count": high_count,
                    "v1_signal_type": DELAYGUARD_V1_SIGNAL_TYPE,
                    "recovery_stats": recovery_stats,
                }
            )

        except ValueError as e:
            context["error"] = str(e)

        return context

    def _get_urgency(self, signal):
        """
        Map severity and delta to urgency level and label.

        Returns (urgency_level, urgency_label) tuple.
        """
        if (
            signal.severity == "critical"
            or signal.delta_days >= DELAYGUARD_URGENT_THRESHOLD_DAYS
        ):
            return 5, "URGENT"
        elif (
            signal.severity == "high"
            or signal.delta_days >= DELAYGUARD_HIGH_THRESHOLD_DAYS
        ):
            return 4, "HIGH"
        elif (
            signal.severity == "medium"
            or signal.delta_days >= DELAYGUARD_MEDIUM_THRESHOLD_DAYS
        ):
            return 3, "MEDIUM"
        elif signal.delta_days >= DELAYGUARD_LOW_THRESHOLD_DAYS:
            return 2, "LOW"
        else:
            return 1, "INFO"

    def _get_recovery_stats(self, customer):
        """Calculate recovery ledger statistics."""
        now = timezone.now()

        # This month's recoveries
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        this_month = OperatorJudgment.objects.filter(
            customer=customer,
            recovered_amount__isnull=False,
            recovered_date__gte=month_start.date(),
        ).aggregate(total=Sum("recovered_amount"), count=Count("id"))

        # Last 30 days
        thirty_days_ago = (now - timedelta(days=30)).date()
        last_30_days = OperatorJudgment.objects.filter(
            customer=customer,
            recovered_amount__isnull=False,
            recovered_date__gte=thirty_days_ago,
        ).aggregate(total=Sum("recovered_amount"), count=Count("id"))

        # All time
        all_time = OperatorJudgment.objects.filter(
            customer=customer, recovered_amount__isnull=False
        ).aggregate(total=Sum("recovered_amount"), count=Count("id"))

        # Recent recoveries (all products)
        recent_recoveries = (
            OperatorJudgment.objects.filter(
                customer=customer, recovered_amount__isnull=False
            )
            .select_related("alert_event", "operator")
            .order_by("-recovered_date")[:5]
        )

        return {
            "this_month_total": this_month["total"] or 0,
            "this_month_count": this_month["count"] or 0,
            "last_30_days_total": last_30_days["total"] or 0,
            "last_30_days_count": last_30_days["count"] or 0,
            "all_time_total": all_time["total"] or 0,
            "all_time_count": all_time["count"] or 0,
            "recent_recoveries": recent_recoveries,
        }

    def _check_similar_alerts(self, customer, signal):
        """
        Check if similar alerts have been previously judged.

        Uses Redis caching to avoid repeated DB queries for the same
        customer/payer/signal_type combination.
        Cache TTL: 15 minutes (CACHE_TTL_MEDIUM)
        """
        # Build cache key: alert_suppression:{customer_id}:{payer}:{signal_type}
        cache_key_data = f"{customer.id}:{signal.payer}:{signal.signal_type}"
        cache_key_hash = hashlib.md5(cache_key_data.encode()).hexdigest()
        cache_key = f"alert_suppression:{cache_key_hash}"

        # Try cache first
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            # Cached result is serialized JSON
            return json.loads(cached_result) if cached_result != "null" else None

        # Cache miss - query database
        # Look for similar signals: same payer, same signal type
        similar_signals = (
            PaymentDelaySignal.objects.filter(
                customer=customer, payer=signal.payer, signal_type=signal.signal_type
            )
            .exclude(id=signal.id)
            .order_by("-created_at")[:10]
        )

        if not similar_signals.exists():
            # Cache negative result to avoid repeated queries
            cache.set(cache_key, "null", CACHE_TTL_MEDIUM)
            return None

        # Find alerts for these similar signals that have been judged
        similar_alert_ids = AlertEvent.objects.filter(
            payment_delay_signal__in=similar_signals
        ).values_list("id", flat=True)

        similar_judgments = OperatorJudgment.objects.filter(
            alert_event_id__in=similar_alert_ids, customer=customer
        ).order_by("-created_at")

        if not similar_judgments.exists():
            # Cache negative result
            cache.set(cache_key, "null", CACHE_TTL_MEDIUM)
            return None

        # Get most recent judgment
        latest_similar = similar_judgments.first()

        # Determine context message
        days_ago = (timezone.now().date() - latest_similar.created_at.date()).days

        result = None
        if latest_similar.verdict == "noise":
            result = {
                "type": "noise",
                "message": f"Similar alert marked as noise {days_ago} days ago",
                "verdict": "noise",
                "days_ago": days_ago,
            }
        elif latest_similar.verdict == "real":
            result = {
                "type": "confirmed",
                "message": f"Similar alert confirmed real {days_ago} days ago",
                "verdict": "real",
                "days_ago": days_ago,
                "recovered_amount": float(latest_similar.recovered_amount)
                if latest_similar.recovered_amount
                else None,
            }
        elif latest_similar.verdict == "needs_followup":
            result = {
                "type": "pending",
                "message": (
                    f"Similar alert flagged for follow-up "
                    f"{days_ago} days ago (unresolved)"
                ),
                "verdict": "needs_followup",
                "days_ago": days_ago,
            }

        # Cache result (serialize to JSON)
        cache.set(
            cache_key, json.dumps(result) if result else "null", CACHE_TTL_MEDIUM
        )

        return result
