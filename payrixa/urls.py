from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.views.generic import RedirectView
from . import views
from payrixa.products.denialscope.views import DenialScopeDashboardView

urlpatterns = [
    # Root redirect to uploads
    path("", RedirectView.as_view(pattern_name="uploads"), name="portal_root"),

    # Portal pages (all protected by login_required)
    path("uploads/", login_required(views.UploadsView.as_view()), name="uploads"),
    path("settings/", login_required(views.SettingsView.as_view()), name="settings"),
    path("mappings/", login_required(views.MappingsView.as_view()), name="mappings"),
    path("drift-feed/", login_required(views.DriftFeedView.as_view()), name="drift_feed"),
    path("reports/", login_required(views.ReportsView.as_view()), name="reports"),
    
    # Product line dashboards (Sprint 1 scaffolding)
    path("products/denialscope/", login_required(DenialScopeDashboardView.as_view()), name="denialscope_dashboard"),
    path("insights/", login_required(views.InsightsFeedView.as_view()), name="insights_feed"),

    # Authentication
    path("login/", auth_views.LoginView.as_view(template_name="payrixa/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
