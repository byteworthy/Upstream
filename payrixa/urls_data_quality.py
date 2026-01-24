"""
URL patterns for Data Quality views.
"""

from django.urls import path
from payrixa.views_data_quality import (
    data_quality_dashboard,
    upload_quality_detail,
    validation_rules_dashboard,
    quality_trends,
    anomaly_dashboard,
    acknowledge_anomaly,
    quality_metrics_chart_data,
    validation_failure_chart_data,
)

urlpatterns = [
    # Main dashboard
    path('quality/', data_quality_dashboard, name='data_quality_dashboard'),

    # Upload quality detail
    path('quality/upload/<int:upload_id>/', upload_quality_detail, name='upload_quality_detail'),

    # Validation rules
    path('quality/rules/', validation_rules_dashboard, name='validation_rules_dashboard'),

    # Quality trends
    path('quality/trends/', quality_trends, name='quality_trends'),

    # Anomalies
    path('quality/anomalies/', anomaly_dashboard, name='anomaly_dashboard'),
    path('api/quality/anomaly/<int:anomaly_id>/acknowledge/', acknowledge_anomaly, name='acknowledge_anomaly'),

    # API endpoints for charts
    path('api/quality/metrics/chart-data/', quality_metrics_chart_data, name='quality_metrics_chart_data'),
    path('api/quality/validation/chart-data/', validation_failure_chart_data, name='validation_failure_chart_data'),
]
