from django.urls import path
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.views.generic import RedirectView
from . import views
from upstream.products.denialscope.views import DenialScopeDashboardView
from upstream.products.driftwatch.views import DriftWatchDashboardView
from upstream.products.delayguard.views import DelayGuardDashboardView
from upstream.views.metrics import MetricsDashboardView
from upstream.views.webhooks import ehr_webhook

urlpatterns = [
    # Root redirect to Axis hub
    path("", RedirectView.as_view(pattern_name="axis_hub"), name="portal_root"),
    # API Webhooks (unauthenticated - signature validation in view)
    path(
        "api/v1/webhooks/ehr/<str:provider>/",
        ehr_webhook,
        name="ehr_webhook",
    ),
    # Axis Hub - Primary entry point (Hub v1)
    path("axis/", login_required(views.AxisHubView.as_view()), name="axis_hub"),
    # Backward compatibility redirect
    path(
        "products/",
        RedirectView.as_view(pattern_name="axis_hub"),
        name="products_redirect",
    ),
    # Portal pages (all protected by login_required)
    path("uploads/", login_required(views.UploadsView.as_view()), name="uploads"),
    path("settings/", login_required(views.SettingsView.as_view()), name="settings"),
    path("mappings/", login_required(views.MappingsView.as_view()), name="mappings"),
    path(
        "drift-feed/", login_required(views.DriftFeedView.as_view()), name="drift_feed"
    ),
    path("reports/", login_required(views.ReportsView.as_view()), name="reports"),
    # Product line dashboards (Hub v1: DenialScope + DriftWatch + DelayGuard)
    path(
        "products/denialscope/",
        login_required(DenialScopeDashboardView.as_view()),
        name="denialscope_dashboard",
    ),
    path(
        "products/driftwatch/",
        login_required(DriftWatchDashboardView.as_view()),
        name="driftwatch_dashboard",
    ),
    path(
        "products/delayguard/",
        login_required(DelayGuardDashboardView.as_view()),
        name="delayguard_dashboard",
    ),
    path(
        "insights/",
        login_required(views.InsightsFeedView.as_view()),
        name="insights_feed",
    ),
    # Alert deep dive (Phase 4)
    path(
        "alerts/<int:alert_id>/deep-dive/",
        login_required(views.AlertDeepDiveView.as_view()),
        name="alert_deep_dive",
    ),
    # Admin/Monitoring (Staff only - decorator applied in view)
    path("admin/metrics/", MetricsDashboardView.as_view(), name="metrics_dashboard"),
    # Authentication
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="upstream/login.html"),
        name="login",
    ),
    path("logout/", views.CustomLogoutView.as_view(), name="logout"),
    # Password Reset
    path(
        "password_reset/",
        auth_views.PasswordResetView.as_view(
            template_name="registration/password_reset_form.html",
            email_template_name="registration/password_reset_email.html",
            subject_template_name="registration/password_reset_subject.txt",
        ),
        name="password_reset",
    ),
    path(
        "password_reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="registration/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="registration/password_reset_confirm.html"
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="registration/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
]
