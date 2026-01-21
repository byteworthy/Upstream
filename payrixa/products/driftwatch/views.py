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
from payrixa.services.evidence_payload import build_driftwatch_evidence_payload, get_alert_interpretation
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
            drift_events_qs = base_queryset.order_by('-created_at')[:50]
            
            # Add interpretation to each event for dashboard display (Deliverable 6)
            drift_events = []
            for event in drift_events_qs:
                # Build a mini payload for interpretation
                event_payload = {
                    'severity': event.severity,
                    'delta': event.delta_value,
                    'signal_type': event.drift_type,
                    'entity_label': event.payer,
                    'product_name': 'DriftWatch',
                }
                interp = get_alert_interpretation(event_payload)
                # Attach interpretation to event as dict for template access
                drift_events.append({
                    'event': event,
                    'payer': event.payer,
                    'cpt_group': event.cpt_group,
                    'drift_type': event.drift_type,
                    'baseline_value': event.baseline_value,
                    'current_value': event.current_value,
                    'delta_value': event.delta_value,
                    'severity': event.severity,
                    'confidence': event.confidence,
                    'created_at': event.created_at,
                    'urgency_label': interp['urgency_label'],
                    'urgency_level': interp['urgency_level'],
                    'plain_language': interp['plain_language'],
                    'is_likely_noise': interp['is_likely_noise'],
                })

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

            # For evidence payload, use the raw event object
            latest_raw_event = drift_events_qs.first() if drift_events_qs.exists() else None
            evidence_payload = build_driftwatch_evidence_payload(latest_raw_event, list(drift_events_qs))

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
