from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.views.generic import RedirectView
from . import views
from payrixa.products.denialscope.views import DenialScopeDashboardView
from payrixa.products.driftwatch.views import DriftWatchDashboardView
from payrixa.products.delayguard.views import DelayGuardDashboardView
from payrixa.views.metrics import MetricsDashboardView

urlpatterns = [
    # Root redirect to Axis hub
    path("", RedirectView.as_view(pattern_name="axis_hub"), name="portal_root"),

    # Axis Hub - Primary entry point (Hub v1)
    path("axis/", login_required(views.AxisHubView.as_view()), name="axis_hub"),
    # Backward compatibility redirect
    path("products/", RedirectView.as_view(pattern_name="axis_hub"), name="products_redirect"),

    # Portal pages (all protected by login_required)
    path("uploads/", login_required(views.UploadsView.as_view()), name="uploads"),
    path("settings/", login_required(views.SettingsView.as_view()), name="settings"),
    path("mappings/", login_required(views.MappingsView.as_view()), name="mappings"),
    path("drift-feed/", login_required(views.DriftFeedView.as_view()), name="drift_feed"),
    path("reports/", login_required(views.ReportsView.as_view()), name="reports"),
    
    # Product line dashboards (Hub v1: DenialScope + DriftWatch + DelayGuard)
    path("products/denialscope/", login_required(DenialScopeDashboardView.as_view()), name="denialscope_dashboard"),
    path("products/driftwatch/", login_required(DriftWatchDashboardView.as_view()), name="driftwatch_dashboard"),
    path("products/delayguard/", login_required(DelayGuardDashboardView.as_view()), name="delayguard_dashboard"),
    path("insights/", login_required(views.InsightsFeedView.as_view()), name="insights_feed"),

    # Alert deep dive (Phase 4)
    path("alerts/<int:alert_id>/deep-dive/", login_required(views.AlertDeepDiveView.as_view()), name="alert_deep_dive"),

    # Admin/Monitoring (Staff only - decorator applied in view)
    path("admin/metrics/", MetricsDashboardView.as_view(), name="metrics_dashboard"),

    # Authentication
    path("login/", auth_views.LoginView.as_view(template_name="payrixa/login.html"), name="login"),
    path("logout/", views.CustomLogoutView.as_view(), name="logout"),
]
