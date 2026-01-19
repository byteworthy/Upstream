from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from payrixa.utils import get_current_customer
from payrixa.permissions import ProductEnabledMixin


class DenialScopeDashboardView(LoginRequiredMixin, ProductEnabledMixin, View):
    """DenialScope product dashboard - Sprint 1 scaffolding only."""
    template_name = 'payrixa/products/denialscope_dashboard.html'
    product_slug = 'denialscope'
    
    def get(self, request):
        try:
            customer = get_current_customer(request)
            return render(request, self.template_name, {
                'customer': customer,
                'product_name': 'DenialScope',
            })
        except ValueError as e:
            from django.contrib import messages
            from django.shortcuts import redirect
            messages.error(request, str(e))
            return redirect('portal_root')
