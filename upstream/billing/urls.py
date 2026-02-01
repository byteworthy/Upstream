"""
Billing URL configuration.
"""

from django.urls import path
from upstream.billing import views

app_name = "billing"

urlpatterns = [
    path("stripe/", views.stripe_webhook, name="stripe_webhook"),
]
