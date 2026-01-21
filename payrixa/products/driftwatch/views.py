"""
DriftWatch views.

Hub v1: Dashboard reading from existing DriftEvent model.
Filtered to DENIAL_RATE type only for v1.
No new models - reuses payrixa.models.DriftEvent.
"""

from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Avg, Max

from payrixa.utils import get_current_customer
from payrixa.models import DriftEvent, ReportRun
from payrixa.products.driftwatch import DRIFTWATCH_V1_EVENT_TYPE
from payrixa.services.evidence_payload import build_driftwatch_evidence_payload
from payrixa.permissions import ProductEnabledMixin


class DriftWatchDashboardView(LoginRequiredMixin, ProductEnabledMixin, TemplateView):
    """
    DriftWatch dashboard showing denial rate drift signals.
    
    Hub v1: Filtered to DENIAL_RATE type only.
    Uses existing DriftEvent model - NO new models for V1.
    """
    template_name = 'payrixa/products/driftwatch_dashboard.html'
    product_slug = 'driftwatch'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        try:
            customer = get_current_customer(self.request)
            context['customer'] = customer

            # Hub v1: Filter to DENIAL_RATE type only
            base_queryset = DriftEvent.objects.filter(
                customer=customer,
                drift_type=DRIFTWATCH_V1_EVENT_TYPE
            )
            
            # Get recent drift events for display (sliced)
            drift_events = base_queryset.order_by('-created_at')[:50]

            # Summary metrics (from v1 filtered queryset)
            total_events = base_queryset.count()

            # Top payers by drift frequency (v1 type only)
            top_payers = base_queryset.values('payer').annotate(
                event_count=Count('id'),
                avg_severity=Avg('severity'),
                max_delta=Max('delta_value')
            ).order_by('-event_count')[:5]

            # Recent report runs
            recent_runs = ReportRun.objects.filter(
                customer=customer
            ).order_by('-started_at')[:5]

            latest_event = drift_events[0] if drift_events else None
            evidence_payload = build_driftwatch_evidence_payload(latest_event, drift_events)

            context.update({
                'drift_events': drift_events,
                'total_events': total_events,
                'top_payers': top_payers,
                'recent_runs': recent_runs,
                'evidence_payload': evidence_payload,
                # V1 signal type constant
                'v1_signal_type': DRIFTWATCH_V1_EVENT_TYPE,
            })

        except ValueError as e:
            context['error'] = str(e)

        return context
