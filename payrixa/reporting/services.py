import csv
import os
from datetime import datetime
from django.conf import settings
from payrixa.models import DriftEvent
from .models import ReportArtifact

def generate_drift_events_csv(report_run, params=None):
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
