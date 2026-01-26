"""
DriftWatch views.

Hub v1: Dashboard reading from existing DriftEvent model.
Filtered to DENIAL_RATE type only for v1.
No new models - reuses upstream.models.DriftEvent.
"""

from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Avg, Max, Sum
from django.utils import timezone
from datetime import timedelta

from upstream.utils import get_current_customer
from upstream.models import DriftEvent, ReportRun
from upstream.alerts.models import AlertEvent, OperatorJudgment
from upstream.products.driftwatch import DRIFTWATCH_V1_EVENT_TYPE
from upstream.services.evidence_payload import (
    build_driftwatch_evidence_payload,
    get_alert_interpretation,
)
from upstream.permissions import ProductEnabledMixin


class DriftWatchDashboardView(LoginRequiredMixin, ProductEnabledMixin, TemplateView):
    """
    DriftWatch dashboard showing denial rate drift signals.

    Hub v1: Filtered to DENIAL_RATE type only.
    Uses existing DriftEvent model - NO new models for V1.
    """

    template_name = "upstream/products/driftwatch_dashboard.html"
    product_slug = "driftwatch"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        try:
            customer = get_current_customer(self.request)
            context["customer"] = customer

            # Hub v1: Filter to DENIAL_RATE type only
            base_queryset = DriftEvent.objects.filter(
                customer=customer, drift_type=DRIFTWATCH_V1_EVENT_TYPE
            )

            # Get recent drift events for display (sliced)
            drift_events_qs = base_queryset.order_by("-created_at")[:50]

            # Add interpretation to each event for dashboard display (Deliverable 6)
            drift_events = []
            for event in drift_events_qs:
                # Build a mini payload for interpretation
                event_payload = {
                    "severity": event.severity,
                    "delta": event.delta_value,
                    "signal_type": event.drift_type,
                    "entity_label": event.payer,
                    "product_name": "DriftWatch",
                }
                interp = get_alert_interpretation(event_payload)

                # Get associated alert event (if exists) for operator feedback
                alert_event = AlertEvent.objects.filter(drift_event=event).first()
                latest_judgment = None
                suppression_context = None

                if alert_event and alert_event.operator_judgments.exists():
                    latest_judgment = alert_event.operator_judgments.order_by(
                        "-created_at"
                    ).first()

                # Check for similar alerts that were previously judged (Phase 1b)
                suppression_context = self._check_similar_alerts(customer, event)

                # Attach interpretation to event as dict for template access
                drift_events.append(
                    {
                        "event": event,
                        "alert_event_id": alert_event.id if alert_event else None,
                        "payer": event.payer,
                        "cpt_group": event.cpt_group,
                        "drift_type": event.drift_type,
                        "baseline_value": event.baseline_value,
                        "current_value": event.current_value,
                        "delta_value": event.delta_value,
                        "severity": event.severity,
                        "confidence": event.confidence,
                        "created_at": event.created_at,
                        "urgency_label": interp["urgency_label"],
                        "urgency_level": interp["urgency_level"],
                        "plain_language": interp["plain_language"],
                        "is_likely_noise": interp["is_likely_noise"],
                        "has_judgment": latest_judgment is not None,
                        "judgment_verdict": latest_judgment.verdict
                        if latest_judgment
                        else None,
                        "suppression_context": suppression_context,
                    }
                )

            # Summary metrics (from v1 filtered queryset)
            total_events = base_queryset.count()

            # Top payers by drift frequency (v1 type only)
            top_payers = (
                base_queryset.values("payer")
                .annotate(
                    event_count=Count("id"),
                    avg_severity=Avg("severity"),
                    max_delta=Max("delta_value"),
                )
                .order_by("-event_count")[:5]
            )

            # Recent report runs
            recent_runs = ReportRun.objects.filter(customer=customer).order_by(
                "-started_at"
            )[:5]

            # For evidence payload, use the raw event object
            latest_raw_event = (
                drift_events_qs.first() if drift_events_qs.exists() else None
            )
            evidence_payload = build_driftwatch_evidence_payload(
                latest_raw_event, list(drift_events_qs)
            )

            # Recovery ledger stats (Phase 4)
            recovery_stats = self._get_recovery_stats(customer)

            context.update(
                {
                    "drift_events": drift_events,
                    "total_events": total_events,
                    "top_payers": top_payers,
                    "recent_runs": recent_runs,
                    "evidence_payload": evidence_payload,
                    # V1 signal type constant
                    "v1_signal_type": DRIFTWATCH_V1_EVENT_TYPE,
                    # Recovery ledger
                    "recovery_stats": recovery_stats,
                }
            )

        except ValueError as e:
            context["error"] = str(e)

        return context

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

        # Recent recoveries
        recent_recoveries = (
            OperatorJudgment.objects.filter(
                customer=customer, recovered_amount__isnull=False
            )
            .select_related("alert_event__drift_event", "operator")
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

    def _check_similar_alerts(self, customer, drift_event):
        """Check if similar alerts have been previously judged (Phase 1b)."""
        # Look for similar drift events: same payer, same CPT group, same drift type
        similar_drift_events = (
            DriftEvent.objects.filter(
                customer=customer,
                payer=drift_event.payer,
                cpt_group=drift_event.cpt_group,
                drift_type=drift_event.drift_type,
            )
            .exclude(id=drift_event.id)
            .order_by("-created_at")[:10]
        )

        if not similar_drift_events.exists():
            return None

        # Find alerts for these similar drift events that have been judged
        similar_alert_ids = AlertEvent.objects.filter(
            drift_event__in=similar_drift_events
        ).values_list("id", flat=True)

        similar_judgments = OperatorJudgment.objects.filter(
            alert_event_id__in=similar_alert_ids, customer=customer
        ).order_by("-created_at")

        if not similar_judgments.exists():
            return None

        # Get most recent judgment
        latest_similar = similar_judgments.first()

        # Determine context message
        days_ago = (timezone.now().date() - latest_similar.created_at.date()).days

        if latest_similar.verdict == "noise":
            return {
                "type": "noise",
                "message": f"Similar alert marked as noise {days_ago} days ago",
                "verdict": "noise",
                "days_ago": days_ago,
            }
        elif latest_similar.verdict == "real":
            return {
                "type": "confirmed",
                "message": f"Similar alert confirmed real {days_ago} days ago",
                "verdict": "real",
                "days_ago": days_ago,
                "recovered_amount": latest_similar.recovered_amount,
            }
        elif latest_similar.verdict == "needs_followup":
            return {
                "type": "pending",
                "message": f"Similar alert flagged for follow-up {days_ago} days ago (unresolved)",
                "verdict": "needs_followup",
                "days_ago": days_ago,
            }

        return None
