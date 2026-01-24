"""
Data Quality and Validation Visibility Views.

Provides comprehensive dashboards and reports for:
- Upload quality summaries
- Validation failure reports
- Data quality trends
- Anomaly dashboards
- Quality scorecards
"""

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta

from payrixa.models import Upload, DataQualityReport, Customer
from payrixa.core.validation_models import (
    ValidationRule, ValidationResult, DataQualityMetric,
    DataAnomalyDetection, ClaimValidationHistory
)
from payrixa.core.quality_reporting_service import DataQualityReportingService
from payrixa.core.default_validation_rules import get_validation_rule_statistics


@login_required
def data_quality_dashboard(request):
    """
    Main data quality dashboard.

    Shows overall quality health, recent uploads, and key metrics.
    """
    customer = request.user.profile.customer

    # Get quality reporting service
    reporting_service = DataQualityReportingService(customer)

    # Get quality scorecard
    scorecard = reporting_service.generate_quality_scorecard()

    # Get recent uploads
    recent_uploads = Upload.objects.filter(
        customer=customer
    ).order_by('-uploaded_at')[:10]

    # Add quality scores to uploads
    uploads_with_quality = []
    for upload in recent_uploads:
        try:
            quality_report = upload.quality_report
            uploads_with_quality.append({
                'upload': upload,
                'quality_report': quality_report,
                'has_report': True,
            })
        except DataQualityReport.DoesNotExist:
            uploads_with_quality.append({
                'upload': upload,
                'quality_report': None,
                'has_report': False,
            })

    # Get recent anomalies
    recent_anomalies = DataAnomalyDetection.objects.filter(
        customer=customer,
        acknowledged=False
    ).order_by('-detected_at')[:5]

    # Get quality trend (last 30 days)
    trend_report = reporting_service.generate_quality_trend_report(days=30)

    context = {
        'customer': customer,
        'scorecard': scorecard,
        'recent_uploads': uploads_with_quality,
        'recent_anomalies': recent_anomalies,
        'trend_report': trend_report,
        'page_title': 'Data Quality Dashboard',
    }

    return render(request, 'payrixa/data_quality/dashboard.html', context)


@login_required
def upload_quality_detail(request, upload_id):
    """
    Detailed quality report for a specific upload.

    Shows validation failures, anomalies, and recommendations.
    """
    customer = request.user.profile.customer
    upload = get_object_or_404(Upload, id=upload_id, customer=customer)

    # Get quality reporting service
    reporting_service = DataQualityReportingService(customer)

    # Generate comprehensive quality summary
    quality_summary = reporting_service.generate_upload_quality_summary(upload)

    # Get validation results grouped by severity
    validation_results = ValidationResult.objects.filter(
        customer=customer,
        upload=upload,
        passed=False
    ).order_by('-severity', 'validation_rule__code')[:100]

    # Get anomalies
    anomalies = DataAnomalyDetection.objects.filter(
        customer=customer,
        upload=upload
    ).order_by('-severity', '-anomaly_score')

    context = {
        'customer': customer,
        'upload': upload,
        'quality_summary': quality_summary,
        'validation_results': validation_results,
        'anomalies': anomalies,
        'page_title': f'Quality Report: {upload.filename}',
    }

    return render(request, 'payrixa/data_quality/upload_detail.html', context)


@login_required
def validation_rules_dashboard(request):
    """
    Dashboard showing all validation rules and their performance.
    """
    customer = request.user.profile.customer

    # Get all validation rules
    rules = ValidationRule.objects.filter(customer=customer).order_by('execution_order')

    # Get rule statistics
    rule_stats = get_validation_rule_statistics(customer)

    # Get recent validation failures
    recent_failures = ValidationResult.objects.filter(
        customer=customer,
        passed=False
    ).select_related('validation_rule').order_by('-created_at')[:50]

    context = {
        'customer': customer,
        'rules': rules,
        'rule_stats': rule_stats,
        'recent_failures': recent_failures,
        'page_title': 'Validation Rules',
    }

    return render(request, 'payrixa/data_quality/validation_rules.html', context)


@login_required
def quality_trends(request):
    """
    Quality trends and analytics over time.
    """
    customer = request.user.profile.customer

    # Get time period from query params
    days = int(request.GET.get('days', 30))

    # Get quality reporting service
    reporting_service = DataQualityReportingService(customer)

    # Generate trend report
    trend_report = reporting_service.generate_quality_trend_report(days=days)

    # Get validation failure report
    failure_report = reporting_service.generate_validation_failure_report(days=days)

    # Get quality metrics
    quality_metrics = DataQualityMetric.objects.filter(
        customer=customer,
        measurement_date__gte=timezone.now().date() - timedelta(days=days)
    ).order_by('measurement_date', 'metric_type')

    # Group metrics by type
    metrics_by_type = {}
    for metric in quality_metrics:
        if metric.metric_type not in metrics_by_type:
            metrics_by_type[metric.metric_type] = []
        metrics_by_type[metric.metric_type].append({
            'date': metric.measurement_date,
            'score': metric.score,
            'grade': metric.quality_grade,
        })

    context = {
        'customer': customer,
        'days': days,
        'trend_report': trend_report,
        'failure_report': failure_report,
        'metrics_by_type': metrics_by_type,
        'page_title': f'Quality Trends ({days} days)',
    }

    return render(request, 'payrixa/data_quality/trends.html', context)


@login_required
def anomaly_dashboard(request):
    """
    Dashboard for data anomalies.
    """
    customer = request.user.profile.customer

    # Get time period
    days = int(request.GET.get('days', 30))

    # Get quality reporting service
    reporting_service = DataQualityReportingService(customer)

    # Generate anomaly dashboard
    anomaly_report = reporting_service.generate_anomaly_dashboard(days=days)

    # Get unacknowledged anomalies
    unacknowledged = DataAnomalyDetection.objects.filter(
        customer=customer,
        acknowledged=False
    ).order_by('-severity', '-anomaly_score')

    context = {
        'customer': customer,
        'days': days,
        'anomaly_report': anomaly_report,
        'unacknowledged_anomalies': unacknowledged,
        'page_title': 'Data Anomalies',
    }

    return render(request, 'payrixa/data_quality/anomalies.html', context)


@login_required
def acknowledge_anomaly(request, anomaly_id):
    """
    Acknowledge an anomaly (AJAX endpoint).
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)

    customer = request.user.profile.customer
    anomaly = get_object_or_404(
        DataAnomalyDetection,
        id=anomaly_id,
        customer=customer
    )

    anomaly.acknowledged = True
    anomaly.acknowledged_by = request.user
    anomaly.acknowledged_at = timezone.now()
    anomaly.resolution_notes = request.POST.get('notes', '')
    anomaly.save()

    return JsonResponse({
        'success': True,
        'anomaly_id': anomaly.id,
        'acknowledged_at': anomaly.acknowledged_at.isoformat(),
    })


@login_required
def quality_metrics_chart_data(request):
    """
    API endpoint for quality metrics chart data (AJAX).
    """
    customer = request.user.profile.customer
    metric_type = request.GET.get('metric_type', 'completeness')
    days = int(request.GET.get('days', 30))

    start_date = timezone.now().date() - timedelta(days=days)

    metrics = DataQualityMetric.objects.filter(
        customer=customer,
        metric_type=metric_type,
        measurement_date__gte=start_date
    ).order_by('measurement_date')

    data = {
        'labels': [m.measurement_date.isoformat() for m in metrics],
        'scores': [m.score for m in metrics],
        'grades': [m.quality_grade for m in metrics],
    }

    return JsonResponse(data)


@login_required
def validation_failure_chart_data(request):
    """
    API endpoint for validation failure chart data (AJAX).
    """
    customer = request.user.profile.customer
    days = int(request.GET.get('days', 30))

    start_date = timezone.now() - timedelta(days=days)

    # Get failures grouped by rule type
    failures = ValidationResult.objects.filter(
        customer=customer,
        passed=False,
        created_at__gte=start_date
    ).values('validation_rule__rule_type').annotate(
        count=Count('id')
    )

    data = {
        'labels': [f['validation_rule__rule_type'] for f in failures],
        'counts': [f['count'] for f in failures],
    }

    return JsonResponse(data)


# Import missing Count
from django.db.models import Count
