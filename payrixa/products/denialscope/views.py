from datetime import timedelta
from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.utils import timezone
from django.db.models import Sum
from payrixa.utils import get_current_customer
from payrixa.permissions import ProductEnabledMixin
from payrixa.products.denialscope.models import DenialAggregate, DenialSignal
from payrixa.services.evidence_payload import build_denialscope_evidence_payload, get_alert_interpretation


class DenialScopeDashboardView(LoginRequiredMixin, ProductEnabledMixin, View):
    """DenialScope product dashboard - Sprint 2 analytics."""
    template_name = 'payrixa/products/denialscope_dashboard.html'
    product_slug = 'denialscope'

    def get(self, request):
        try:
            customer = get_current_customer(request)
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=30)

            aggregates = DenialAggregate.objects.filter(
                customer=customer,
                aggregate_date__gte=start_date,
                aggregate_date__lt=end_date
            )

            # Hub v1: filter to denial_dollars_spike only
            signals_qs = DenialSignal.objects.filter(
                customer=customer,
                signal_type='denial_dollars_spike'
            ).order_by('-created_at')[:10]
            
            # Add interpretation to each signal for dashboard display (Deliverable 6)
            signals = []
            for signal in signals_qs:
                # Build a mini payload for interpretation
                details = signal.details or {}
                signal_payload = {
                    'severity': signal.severity,
                    'delta': details.get('delta') or details.get('rate_delta'),
                    'signal_type': signal.signal_type,
                    'entity_label': signal.payer,
                    'product_name': 'DenialScope',
                }
                interp = get_alert_interpretation(signal_payload)
                signals.append({
                    'signal': signal,
                    'signal_type': signal.signal_type,
                    'get_signal_type_display': signal.get_signal_type_display(),
                    'payer': signal.payer,
                    'severity': signal.severity,
                    'summary_text': signal.summary_text,
                    'created_at': signal.created_at,
                    'urgency_label': interp['urgency_label'],
                    'urgency_level': interp['urgency_level'],
                    'plain_language': interp['plain_language'],
                    'is_likely_noise': interp['is_likely_noise'],
                })

            total_denials = aggregates.aggregate(total=Sum('denied_count'))['total'] or 0

            # Top payer by denials
            top_payer = None
            top_payer_count = 0
            payer_totals = aggregates.values('payer').annotate(total=Sum('denied_count')).order_by('-total')
            if payer_totals:
                top_payer = payer_totals[0]['payer']
                top_payer_count = payer_totals[0]['total'] or 0

            # Top denial reason
            top_reason = None
            top_reason_count = 0
            reason_totals = aggregates.values('denial_reason').annotate(total=Sum('denied_count')).order_by('-total')
            if reason_totals:
                top_reason = reason_totals[0]['denial_reason']
                top_reason_count = reason_totals[0]['total'] or 0

            # Shared evidence payload (Hub v1)
            latest_signal = signals_qs.first() if signals_qs.exists() else None
            evidence_payload = build_denialscope_evidence_payload(
                latest_signal,
                aggregates,
                start_date,
                end_date,
            )

            last_computed = aggregates.order_by('-updated_at').first()

            return render(request, self.template_name, {
                'customer': customer,
                'product_name': 'DenialScope',
                'start_date': start_date,
                'end_date': end_date,
                'last_computed': last_computed.updated_at if last_computed else None,
                'total_denials': total_denials,
                'top_payer': top_payer,
                'top_payer_count': top_payer_count,
                'top_reason': top_reason,
                'top_reason_count': top_reason_count,
                'signals': signals,
                'evidence_payload': evidence_payload,
                'top_denials_by_payer': evidence_payload['evidence_rows'],
            })
        except ValueError as e:
            from django.contrib import messages
            from django.shortcuts import redirect
            messages.error(request, str(e))
            return redirect('portal_root')
