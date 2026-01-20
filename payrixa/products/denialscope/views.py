from datetime import timedelta
from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.utils import timezone
from django.db.models import Sum
from payrixa.utils import get_current_customer
from payrixa.permissions import ProductEnabledMixin
from payrixa.products.denialscope.models import DenialAggregate, DenialSignal


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

            signals = DenialSignal.objects.filter(customer=customer).order_by('-created_at')[:10]

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

            # Table data: top denial reasons by payer
            top_denials_by_payer = aggregates.values('payer', 'denial_reason').annotate(
                denied_count=Sum('denied_count'),
                total_submitted=Sum('total_submitted_count'),
            ).order_by('-denied_count')[:20]

            for row in top_denials_by_payer:
                total_submitted = row['total_submitted'] or 0
                denial_rate = (row['denied_count'] / total_submitted) if total_submitted > 0 else 0
                row['denial_rate_percent'] = denial_rate * 100

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
                'top_denials_by_payer': top_denials_by_payer,
                'signals': signals,
            })
        except ValueError as e:
            from django.contrib import messages
            from django.shortcuts import redirect
            messages.error(request, str(e))
            return redirect('portal_root')
