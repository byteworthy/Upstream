"""
Data Quality Reporting and Dashboard Service.

Generates comprehensive quality reports, trends, and dashboards
for data quality visibility.
"""

from datetime import datetime, timedelta
from typing import Dict, List
from django.db.models import Avg, Count, Sum, Q, F
from django.utils import timezone
from decimal import Decimal


class DataQualityReportingService:
    """
    Generate comprehensive data quality reports and dashboards.

    Provides:
    - Upload quality summaries
    - Quality trend analysis
    - Validation failure reports
    - Anomaly dashboards
    """

    def __init__(self, customer):
        self.customer = customer

    def generate_upload_quality_summary(self, upload) -> Dict:
        """
        Generate comprehensive quality summary for an upload.

        Returns detailed quality metrics, validation results,
        and actionable recommendations.
        """
        from upstream.models import DataQualityReport
        from upstream.core.validation_models import ValidationResult, DataAnomalyDetection

        # Get quality report
        try:
            quality_report = upload.quality_report
        except DataQualityReport.DoesNotExist:
            return {
                'status': 'no_report',
                'message': 'No quality report available for this upload'
            }

        # Get validation failures grouped by rule
        validation_failures = ValidationResult.objects.filter(
            customer=self.customer,
            upload=upload,
            passed=False
        ).values(
            'validation_rule__code',
            'validation_rule__name',
            'severity'
        ).annotate(
            count=Count('id')
        ).order_by('-count')

        # Get anomalies
        anomalies = DataAnomalyDetection.objects.filter(
            customer=self.customer,
            upload=upload
        ).order_by('-severity', '-anomaly_score')

        # Calculate quality grade
        quality_score = quality_report.quality_score
        quality_grade = quality_report.quality_score  # This returns letter grade

        # Generate recommendations
        recommendations = self._generate_recommendations(
            quality_report,
            validation_failures,
            anomalies
        )

        summary = {
            'upload_id': upload.id,
            'filename': upload.filename,
            'uploaded_at': upload.uploaded_at,
            'processed_at': upload.processing_completed_at,

            # Overall metrics
            'total_rows': quality_report.total_rows,
            'accepted_rows': quality_report.accepted_rows,
            'rejected_rows': quality_report.rejected_rows,
            'acceptance_rate': quality_report.quality_score * 100 if quality_report.quality_score else 0,
            'quality_score': quality_score,
            'quality_grade': self._get_quality_grade(quality_score),

            # Rejection breakdown
            'rejection_summary': quality_report.get_rejection_summary(),

            # Validation failures
            'validation_failures': list(validation_failures),
            'top_validation_issues': list(validation_failures[:5]),

            # Anomalies
            'anomaly_count': anomalies.count(),
            'critical_anomalies': anomalies.filter(severity='critical').count(),
            'anomaly_details': [
                {
                    'type': a.anomaly_type,
                    'severity': a.severity,
                    'description': a.description,
                    'affected_rows': a.affected_row_count,
                    'recommended_action': a.recommended_action,
                }
                for a in anomalies
            ],

            # Recommendations
            'recommendations': recommendations,

            # Pass/Fail determination
            'passed_quality_check': quality_score >= 0.95 if quality_score else False,
            'has_critical_issues': anomalies.filter(severity='critical').exists(),
        }

        return summary

    def generate_quality_trend_report(self, days: int = 30) -> Dict:
        """
        Generate quality trend report for the last N days.

        Shows quality metrics trending over time.
        """
        from upstream.models import Upload, DataQualityReport
        from upstream.core.validation_models import DataQualityMetric

        start_date = timezone.now() - timedelta(days=days)

        # Get uploads in period
        uploads = Upload.objects.filter(
            customer=self.customer,
            uploaded_at__gte=start_date,
            status__in=['success', 'partial']
        ).order_by('uploaded_at')

        # Daily quality scores
        daily_quality = []
        for upload in uploads:
            try:
                quality_report = upload.quality_report
                daily_quality.append({
                    'date': upload.uploaded_at.date(),
                    'filename': upload.filename,
                    'quality_score': quality_report.quality_score,
                    'acceptance_rate': quality_report.quality_score * 100,
                    'total_rows': quality_report.total_rows,
                    'rejected_rows': quality_report.rejected_rows,
                })
            except DataQualityReport.DoesNotExist:
                continue

        # Calculate averages
        avg_quality_score = sum(d['quality_score'] for d in daily_quality) / len(daily_quality) if daily_quality else 0

        # Get quality metrics
        metrics = DataQualityMetric.objects.filter(
            customer=self.customer,
            measurement_date__gte=start_date.date()
        ).order_by('measurement_date')

        metrics_by_type = {}
        for metric in metrics:
            if metric.metric_type not in metrics_by_type:
                metrics_by_type[metric.metric_type] = []
            metrics_by_type[metric.metric_type].append({
                'date': metric.measurement_date,
                'score': metric.score,
                'grade': metric.quality_grade,
            })

        # Identify trends
        trends = self._identify_quality_trends(daily_quality)

        return {
            'period_days': days,
            'start_date': start_date.date(),
            'end_date': timezone.now().date(),
            'uploads_analyzed': len(daily_quality),
            'average_quality_score': avg_quality_score,
            'average_acceptance_rate': avg_quality_score * 100,
            'daily_quality': daily_quality,
            'metrics_by_type': metrics_by_type,
            'trends': trends,
        }

    def generate_validation_failure_report(self, days: int = 30) -> Dict:
        """
        Generate report on validation failures.

        Shows which validation rules are failing most frequently.
        """
        from upstream.core.validation_models import ValidationResult, ValidationRule

        start_date = timezone.now() - timedelta(days=days)

        # Get all validation failures in period
        failures = ValidationResult.objects.filter(
            customer=self.customer,
            created_at__gte=start_date,
            passed=False
        )

        # Group by validation rule
        failures_by_rule = failures.values(
            'validation_rule__code',
            'validation_rule__name',
            'validation_rule__rule_type',
            'severity'
        ).annotate(
            failure_count=Count('id')
        ).order_by('-failure_count')

        # Group by field
        failures_by_field = failures.values(
            'field_name'
        ).annotate(
            failure_count=Count('id')
        ).order_by('-failure_count')

        # Get severity breakdown
        severity_breakdown = failures.values('severity').annotate(
            count=Count('id')
        )

        # Most common error messages
        common_errors = failures.values('error_message').annotate(
            count=Count('id')
        ).order_by('-count')[:10]

        return {
            'period_days': days,
            'total_failures': failures.count(),
            'failures_by_rule': list(failures_by_rule),
            'top_failing_rules': list(failures_by_rule[:10]),
            'failures_by_field': list(failures_by_field),
            'severity_breakdown': {
                item['severity']: item['count']
                for item in severity_breakdown
            },
            'common_error_messages': list(common_errors),
        }

    def generate_anomaly_dashboard(self, days: int = 30) -> Dict:
        """
        Generate dashboard for data anomalies.

        Shows detected anomalies and their impact.
        """
        from upstream.core.validation_models import DataAnomalyDetection

        start_date = timezone.now() - timedelta(days=days)

        anomalies = DataAnomalyDetection.objects.filter(
            customer=self.customer,
            detected_at__gte=start_date
        )

        # Group by type
        by_type = anomalies.values('anomaly_type').annotate(
            count=Count('id'),
            avg_score=Avg('anomaly_score')
        ).order_by('-count')

        # Group by severity
        by_severity = anomalies.values('severity').annotate(
            count=Count('id')
        ).order_by('-count')

        # Unacknowledged anomalies
        unacknowledged = anomalies.filter(acknowledged=False).order_by(
            '-severity', '-anomaly_score'
        )

        # Recent critical anomalies
        critical = anomalies.filter(severity='critical').order_by('-detected_at')[:10]

        return {
            'period_days': days,
            'total_anomalies': anomalies.count(),
            'unacknowledged_count': unacknowledged.count(),
            'critical_count': critical.count(),
            'by_type': list(by_type),
            'by_severity': {item['severity']: item['count'] for item in by_severity},
            'unacknowledged_anomalies': [
                {
                    'id': a.id,
                    'type': a.anomaly_type,
                    'severity': a.severity,
                    'score': a.anomaly_score,
                    'description': a.description,
                    'detected_at': a.detected_at,
                    'recommended_action': a.recommended_action,
                }
                for a in unacknowledged
            ],
            'recent_critical': [
                {
                    'id': a.id,
                    'type': a.anomaly_type,
                    'description': a.description,
                    'detected_at': a.detected_at,
                    'acknowledged': a.acknowledged,
                }
                for a in critical
            ],
        }

    def generate_quality_scorecard(self) -> Dict:
        """
        Generate overall quality scorecard for customer.

        High-level summary of data quality health.
        """
        from upstream.models import Upload, DataQualityReport
        from upstream.core.validation_models import DataQualityMetric, DataAnomalyDetection

        # Last 30 days
        thirty_days_ago = timezone.now() - timedelta(days=30)

        # Recent uploads
        recent_uploads = Upload.objects.filter(
            customer=self.customer,
            uploaded_at__gte=thirty_days_ago,
            status__in=['success', 'partial']
        )

        # Calculate average quality score
        quality_reports = DataQualityReport.objects.filter(
            customer=self.customer,
            created_at__gte=thirty_days_ago
        )

        avg_quality_score = 0
        if quality_reports.exists():
            total_accepted = quality_reports.aggregate(Sum('accepted_rows'))['accepted_rows__sum'] or 0
            total_rows = quality_reports.aggregate(Sum('total_rows'))['total_rows__sum'] or 0
            avg_quality_score = (total_accepted / total_rows) if total_rows > 0 else 0

        # Latest quality metrics
        latest_metrics = {}
        for metric_type in ['completeness', 'accuracy', 'validity', 'timeliness']:
            latest = DataQualityMetric.objects.filter(
                customer=self.customer,
                metric_type=metric_type
            ).order_by('-measurement_date').first()

            if latest:
                latest_metrics[metric_type] = {
                    'score': latest.score,
                    'grade': latest.quality_grade,
                    'date': latest.measurement_date,
                }

        # Open issues
        open_anomalies = DataAnomalyDetection.objects.filter(
            customer=self.customer,
            acknowledged=False
        )

        critical_anomalies = open_anomalies.filter(severity='critical').count()

        # Overall health score (0-100)
        health_score = self._calculate_health_score(
            avg_quality_score,
            latest_metrics,
            critical_anomalies
        )

        return {
            'period': 'Last 30 days',
            'overall_health_score': health_score,
            'overall_health_grade': self._get_quality_grade(health_score / 100),
            'average_quality_score': avg_quality_score,
            'average_acceptance_rate': avg_quality_score * 100,
            'uploads_count': recent_uploads.count(),
            'total_rows_processed': quality_reports.aggregate(Sum('total_rows'))['total_rows__sum'] or 0,
            'quality_metrics': latest_metrics,
            'open_issues': {
                'total_anomalies': open_anomalies.count(),
                'critical': critical_anomalies,
                'high': open_anomalies.filter(severity='high').count(),
                'medium': open_anomalies.filter(severity='medium').count(),
            },
            'status': self._get_health_status(health_score),
        }

    def _generate_recommendations(self, quality_report, validation_failures, anomalies) -> List[str]:
        """Generate actionable recommendations based on quality issues."""
        recommendations = []

        # Check acceptance rate
        if quality_report.quality_score < 0.8:
            recommendations.append(
                f"Low acceptance rate ({quality_report.quality_score*100:.1f}%). "
                "Review data source quality and validation rules."
            )

        # Check top validation failures
        if validation_failures:
            top_failure = validation_failures[0]
            if top_failure['count'] > quality_report.total_rows * 0.1:
                recommendations.append(
                    f"High failure rate for rule '{top_failure['validation_rule__name']}' "
                    f"({top_failure['count']} failures). Consider reviewing this rule or data source."
                )

        # Check PHI detections
        if quality_report.phi_detections > 0:
            recommendations.append(
                f"⚠️ {quality_report.phi_detections} potential PHI detections. "
                "Review and remove any patient identifiable information."
            )

        # Check anomalies
        critical_anomalies = [a for a in anomalies if a.severity == 'critical']
        if critical_anomalies:
            recommendations.append(
                f"🚨 {len(critical_anomalies)} critical anomalies detected. "
                "Review anomalies immediately before processing data."
            )

        # Check missing fields
        if quality_report.missing_fields > quality_report.total_rows * 0.05:
            recommendations.append(
                f"{quality_report.missing_fields} rows with missing required fields. "
                "Ensure all required fields are populated in source data."
            )

        if not recommendations:
            recommendations.append("✅ No major quality issues detected. Data looks good!")

        return recommendations

    def _identify_quality_trends(self, daily_quality: List[Dict]) -> Dict:
        """Identify trends in quality data."""
        if len(daily_quality) < 7:
            return {'status': 'insufficient_data'}

        # Calculate trend (improving/degrading/stable)
        recent = daily_quality[-7:]
        older = daily_quality[-14:-7] if len(daily_quality) >= 14 else daily_quality[:7]

        recent_avg = sum(d['quality_score'] for d in recent) / len(recent)
        older_avg = sum(d['quality_score'] for d in older) / len(older)

        change = recent_avg - older_avg

        if change > 0.05:
            trend = 'improving'
            trend_description = f"Quality improving (+{change*100:.1f}%)"
        elif change < -0.05:
            trend = 'degrading'
            trend_description = f"Quality degrading ({change*100:.1f}%)"
        else:
            trend = 'stable'
            trend_description = "Quality stable"

        return {
            'trend': trend,
            'description': trend_description,
            'recent_average': recent_avg,
            'previous_average': older_avg,
            'change_percentage': change * 100,
        }

    def _calculate_health_score(self, avg_quality_score: float, metrics: Dict, critical_anomalies: int) -> int:
        """Calculate overall health score (0-100)."""
        # Base score from quality
        score = avg_quality_score * 70  # 70% weight

        # Add points for good metrics
        if metrics:
            metric_avg = sum(m['score'] for m in metrics.values()) / len(metrics)
            score += metric_avg * 20  # 20% weight

        # Deduct points for critical issues
        score -= critical_anomalies * 5  # -5 points per critical anomaly

        return max(0, min(100, int(score)))

    def _get_quality_grade(self, score: float) -> str:
        """Convert quality score to letter grade."""
        if score >= 0.95:
            return 'A+'
        elif score >= 0.90:
            return 'A'
        elif score >= 0.85:
            return 'B+'
        elif score >= 0.80:
            return 'B'
        elif score >= 0.75:
            return 'C+'
        elif score >= 0.70:
            return 'C'
        elif score >= 0.60:
            return 'D'
        else:
            return 'F'

    def _get_health_status(self, health_score: int) -> str:
        """Get health status from score."""
        if health_score >= 90:
            return 'excellent'
        elif health_score >= 75:
            return 'good'
        elif health_score >= 60:
            return 'fair'
        else:
            return 'poor'
