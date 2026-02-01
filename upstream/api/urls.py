"""
Upstream API URL Configuration

RESTful API routes using DRF routers.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

from .views import (
    CustomerViewSet,
    SettingsViewSet,
    UploadViewSet,
    ClaimRecordViewSet,
    ReportRunViewSet,
    # HIGH-2: Use throttled JWT views instead of standard ones
    ThrottledTokenObtainPairView,
    ThrottledTokenRefreshView,
    ThrottledTokenVerifyView,
    DriftEventViewSet,
    PayerMappingViewSet,
    CPTGroupMappingViewSet,
    AlertEventViewSet,
    DashboardView,
    HealthCheckView,
    WebhookIngestionView,
    EpicEHRWebhookView,
    # Automation ViewSets
    ClaimScoreViewSet,
    CustomerAutomationProfileViewSet,
    ShadowModeResultViewSet,
)
from upstream.views.celery_health import (
    celery_health_check,
    celery_tasks,
    celery_stats,
)
from upstream.views.monitoring_status import monitoring_status

# Create router and register viewsets
router = DefaultRouter()
router.register(r"customers", CustomerViewSet, basename="customer")
router.register(r"settings", SettingsViewSet, basename="settings")
router.register(r"uploads", UploadViewSet, basename="upload")
router.register(r"claims", ClaimRecordViewSet, basename="claim")
router.register(r"reports", ReportRunViewSet, basename="report")
router.register(r"drift-events", DriftEventViewSet, basename="drift-event")
router.register(r"payer-mappings", PayerMappingViewSet, basename="payer-mapping")
router.register(r"cpt-mappings", CPTGroupMappingViewSet, basename="cpt-mapping")
router.register(r"alerts", AlertEventViewSet, basename="alert-event")
# Automation routes
router.register(r"claim-scores", ClaimScoreViewSet, basename="claim-score")
router.register(
    r"automation-profiles",
    CustomerAutomationProfileViewSet,
    basename="automation-profile",
)
router.register(r"shadow-results", ShadowModeResultViewSet, basename="shadow-result")

urlpatterns = [
    # Health check (no auth)
    path("health/", HealthCheckView.as_view(), name="api-health"),
    # Monitoring status (no auth - for monitoring tools)
    path("monitoring/status/", monitoring_status, name="monitoring-status"),
    # Celery health checks (no auth - for monitoring tools)
    path("celery/health/", celery_health_check, name="celery-health"),
    path("celery/tasks/", celery_tasks, name="celery-tasks"),
    path("celery/stats/", celery_stats, name="celery-stats"),
    # Webhook ingestion (token auth)
    path("ingest/webhook/", WebhookIngestionView.as_view(), name="api-webhook-ingest"),
    # EHR webhook endpoints (Story 7: Epic webhook receiver)
    path(
        "webhooks/ehr/epic/",
        EpicEHRWebhookView.as_view(),
        name="api-epic-ehr-webhook",
    ),
    path(
        "webhooks/ehr/epic/<int:connection_id>/",
        EpicEHRWebhookView.as_view(),
        name="api-epic-ehr-webhook-connection",
    ),
    # Dashboard
    path("dashboard/", DashboardView.as_view(), name="api-dashboard"),
    # JWT Authentication (HIGH-2: Rate-limited to prevent brute-force attacks)
    path(
        "auth/token/", ThrottledTokenObtainPairView.as_view(), name="token-obtain-pair"
    ),
    path(
        "auth/token/refresh/", ThrottledTokenRefreshView.as_view(), name="token-refresh"
    ),
    path("auth/token/verify/", ThrottledTokenVerifyView.as_view(), name="token-verify"),
    # API Documentation
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    # Router URLs
    path("", include(router.urls)),
]
