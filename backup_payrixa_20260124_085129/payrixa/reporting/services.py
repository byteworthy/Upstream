from typing import Optional, Dict, Any, Union
import csv
import os
import hashlib
from datetime import datetime
from django.conf import settings
from django.template.loader import render_to_string
from django.template import Library
from weasyprint import HTML
from upstream.models import DriftEvent, ReportRun
from .models import ReportArtifact

# Template filter for percentage calculation
@Library.filter
def get_percentage(value: Union[int, float], total: Union[int, float]) -> int:
    if total == 0:
        return 0
    return round((value / total) * 100)

def generate_drift_events_csv(report_run: ReportRun, params: Optional[Dict[str, Any]] = None) -> ReportArtifact:
    """Generate CSV export of drift events for a report run."""
    if params is None:
        params = {}
    artifact = ReportArtifact.objects.create(customer=report_run.customer, report_run=report_run, format='csv', status='processing', params=params)
    try:
        drift_events = DriftEvent.objects.filter(report_run=report_run)
        min_severity = params.get('min_severity')
        if min_severity is not None:
            drift_events = drift_events.filter(severity__gte=float(min_severity))
        payer_filter = params.get('payer')
        if payer_filter:
            drift_events = drift_events.filter(payer__icontains=payer_filter)
        reports_dir = os.path.join(settings.BASE_DIR, 'reports')
        os.makedirs(reports_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'drift_events_{report_run.id}_{timestamp}.csv'
        file_path = os.path.join(reports_dir, filename)
        with open(file_path, 'w', newline='') as csvfile:
            fieldnames = ['payer', 'cpt_group', 'drift_type', 'baseline_value', 'current_value', 'delta_value', 'severity', 'confidence', 'baseline_start', 'baseline_end', 'current_start', 'current_end']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for event in drift_events:
                writer.writerow({'payer': event.payer, 'cpt_group': event.cpt_group, 'drift_type': event.drift_type, 'baseline_value': event.baseline_value, 'current_value': event.current_value, 'delta_value': event.delta_value, 'severity': event.severity, 'confidence': event.confidence, 'baseline_start': event.baseline_start, 'baseline_end': event.baseline_end, 'current_start': event.current_start, 'current_end': event.current_end})
        artifact.file_path = file_path
        artifact.status = 'completed'
        artifact.save()
        return artifact
    except Exception as e:
        artifact.status = 'failed'
        artifact.save()
        raise Exception(f"CSV generation failed: {str(e)}")

def generate_weekly_drift_pdf(report_run_id: int) -> ReportArtifact:
    """
    Generate a PDF report artifact from a ReportRun and its DriftEvents.

    Args:
        report_run_id: ID of the ReportRun to generate PDF for

    Returns:
        ReportArtifact: The created or updated artifact

    Raises:
        ReportRun.DoesNotExist: If report run is not found
        Exception: If PDF generation fails
    """
    try:
        # Load report run and drift events
        report_run = ReportRun.objects.get(id=report_run_id)
        drift_events = DriftEvent.objects.filter(report_run=report_run).order_by('-severity', 'payer')

        # Calculate severity counts
        total_events = drift_events.count()
        high_count = drift_events.filter(severity__gte=0.7).count()
        medium_count = drift_events.filter(severity__gte=0.4, severity__lt=0.7).count()
        low_count = drift_events.filter(severity__lt=0.4).count()
        
        # Prepare severity summary with percentages
        severity_summary = []
        if total_events > 0:
            severity_summary = [
                {
                    'label': 'High',
                    'count': high_count,
                    'percentage': round((high_count / total_events) * 100),
                    'color': '#ffc107'
                },
                {
                    'label': 'Medium',
                    'count': medium_count,
                    'percentage': round((medium_count / total_events) * 100),
                    'color': '#ff9800'
                },
                {
                    'label': 'Low',
                    'count': low_count,
                    'percentage': round((low_count / total_events) * 100),
                    'color': '#4caf50'
                }
            ]

        # Calculate unique payer count
        unique_payers = drift_events.values_list('payer', flat=True).distinct().count()

        # Prepare template context
        context = {
            'customer_name': report_run.customer.name,
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'baseline_start': report_run.summary_json.get('baseline_start', 'N/A'),
            'baseline_end': report_run.summary_json.get('baseline_end', 'N/A'),
            'current_start': report_run.summary_json.get('current_start', 'N/A'),
            'current_end': report_run.summary_json.get('current_end', 'N/A'),
            'total_events': total_events,
            'severity_summary': severity_summary,
            'drift_events': drift_events,
            'payer_count': unique_payers
        }

        # Render HTML template
        html_content = render_to_string('upstream/weekly_drift_pdf.html', context)

        # Generate PDF using WeasyPrint
        pdf_file = HTML(string=html_content).write_pdf()

        # Compute content hash for idempotency
        content_hash = hashlib.sha256(pdf_file).hexdigest()

        # Create reports directory if it doesn't exist
        reports_dir = os.path.join(settings.BASE_DIR, 'reports')
        os.makedirs(reports_dir, exist_ok=True)

        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'weekly_drift_{report_run.id}_{timestamp}.pdf'
        file_path = os.path.join(reports_dir, filename)

        # Save PDF file
        with open(file_path, 'wb') as f:
            f.write(pdf_file)

        # Create or update ReportArtifact idempotently
        artifact, created = ReportArtifact.objects.update_or_create(
            customer=report_run.customer,
            report_run=report_run,
            kind='weekly_drift_summary',
            defaults={
                'file_path': file_path,
                'content_hash': content_hash
            }
        )

        return artifact

    except ReportRun.DoesNotExist:
        raise Exception(f"ReportRun with id {report_run_id} not found")
    except Exception as e:
        raise Exception(f"PDF generation failed: {str(e)}")
