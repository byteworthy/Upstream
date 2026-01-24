from typing import Optional, Dict, List, Tuple, Any
from datetime import date, timedelta
from django.db import transaction
from django.utils import timezone
from upstream.models import ClaimRecord, ReportRun, DriftEvent, Customer
from upstream.constants import (
    DRIFT_BASELINE_DAYS,
    DRIFT_CURRENT_DAYS,
    DRIFT_MIN_VOLUME,
    DENIAL_RATE_ABSOLUTE_THRESHOLD,
    DENIAL_RATE_RELATIVE_THRESHOLD,
    DECISION_TIME_ABSOLUTE_THRESHOLD_DAYS,
    DECISION_TIME_RELATIVE_THRESHOLD,
    DENIAL_DELTA_SEVERITY_MULTIPLIER,
    DECISION_TIME_SEVERITY_DIVISOR,
    CONFIDENCE_VOLUME_MULTIPLIER,
)
import statistics

def compute_weekly_payer_drift(
    customer: Customer,
    baseline_days: int = DRIFT_BASELINE_DAYS,
    current_days: int = DRIFT_CURRENT_DAYS,
    min_volume: int = DRIFT_MIN_VOLUME,
    as_of_date: Optional[date] = None,
    report_run: Optional[ReportRun] = None
) -> ReportRun:
    """
    Compute payer drift metrics and create DriftEvent records.

    Args:
        customer: Customer object
        baseline_days: Number of days in baseline window (default from constants)
        current_days: Number of days in current window (default from constants)
        min_volume: Minimum volume threshold for both windows (default from constants)
        as_of_date: Date to use as reference point (defaults to today)
        report_run: Optional existing ReportRun to use (creates new if None)

    Returns:
        ReportRun object with results
    """
    if as_of_date is None:
        as_of_date = timezone.now().date()

    # Calculate date windows
    baseline_start = as_of_date - timedelta(days=current_days + baseline_days)
    baseline_end = as_of_date - timedelta(days=current_days)
    current_start = baseline_end
    current_end = as_of_date

    # Create or use existing ReportRun
    if report_run is None:
        report_run = ReportRun.objects.create(
            customer=customer,
            run_type='weekly',
            status='running',
            started_at=timezone.now()
        )

    try:
        with transaction.atomic():
            # Get claim records for both windows
            baseline_records = ClaimRecord.objects.filter(
                customer=customer,
                submitted_date__gte=baseline_start,
                submitted_date__lt=baseline_end,
                outcome__in=['PAID', 'DENIED']
            )

            current_records = ClaimRecord.objects.filter(
                customer=customer,
                submitted_date__gte=current_start,
                submitted_date__lt=current_end,
                outcome__in=['PAID', 'DENIED']
            )

            # Group by payer and cpt_group
            baseline_groups = {}
            current_groups = {}

            # Process baseline records
            for record in baseline_records:
                key = (record.payer, record.cpt_group)
                if key not in baseline_groups:
                    baseline_groups[key] = {
                        'paid': 0,
                        'denied': 0,
                        'decision_times': []
                    }
                if record.outcome == 'PAID':
                    baseline_groups[key]['paid'] += 1
                else:
                    baseline_groups[key]['denied'] += 1
                # Calculate decision time in days
                decision_time = (record.decided_date - record.submitted_date).days
                baseline_groups[key]['decision_times'].append(decision_time)

            # Process current records
            for record in current_records:
                key = (record.payer, record.cpt_group)
                if key not in current_groups:
                    current_groups[key] = {
                        'paid': 0,
                        'denied': 0,
                        'decision_times': []
                    }
                if record.outcome == 'PAID':
                    current_groups[key]['paid'] += 1
                else:
                    current_groups[key]['denied'] += 1
                # Calculate decision time in days
                decision_time = (record.decided_date - record.submitted_date).days
                current_groups[key]['decision_times'].append(decision_time)

            # Find all unique groups to consider
            all_groups = set(baseline_groups.keys()) | set(current_groups.keys())
            groups_considered = len(all_groups)
            events_created = 0

            # Analyze each group
            for payer, cpt_group in all_groups:
                baseline_data = baseline_groups.get((payer, cpt_group), {})
                current_data = current_groups.get((payer, cpt_group), {})

                # Check volume requirements
                baseline_volume = baseline_data.get('paid', 0) + baseline_data.get('denied', 0)
                current_volume = current_data.get('paid', 0) + current_data.get('denied', 0)

                if baseline_volume < min_volume or current_volume < min_volume:
                    continue

                # Calculate denial rates
                baseline_denial_rate = 0
                if baseline_volume > 0:
                    baseline_denial_rate = baseline_data.get('denied', 0) / baseline_volume

                current_denial_rate = 0
                if current_volume > 0:
                    current_denial_rate = current_data.get('denied', 0) / current_volume

                # Check denial rate drift
                denial_delta = current_denial_rate - baseline_denial_rate
                if abs(denial_delta) >= DENIAL_RATE_ABSOLUTE_THRESHOLD or (baseline_denial_rate > 0 and abs(denial_delta / baseline_denial_rate) >= DENIAL_RATE_RELATIVE_THRESHOLD):
                    # Calculate severity and confidence
                    severity = min(abs(denial_delta) * DENIAL_DELTA_SEVERITY_MULTIPLIER, 1.0)  # Scale to 0-1 range
                    confidence = min((baseline_volume + current_volume) / (min_volume * CONFIDENCE_VOLUME_MULTIPLIER), 1.0)  # Cap at 1.0

                    DriftEvent.objects.create(
                        customer=customer,
                        report_run=report_run,
                        payer=payer,
                        cpt_group=cpt_group,
                        drift_type='DENIAL_RATE',
                        baseline_value=baseline_denial_rate,
                        current_value=current_denial_rate,
                        delta_value=denial_delta,
                        severity=severity,
                        confidence=confidence,
                        baseline_start=baseline_start,
                        baseline_end=baseline_end,
                        current_start=current_start,
                        current_end=current_end
                    )
                    events_created += 1

                # Calculate decision times (median)
                baseline_decision_time = None
                if baseline_data.get('decision_times'):
                    baseline_decision_time = statistics.median(baseline_data['decision_times'])

                current_decision_time = None
                if current_data.get('decision_times'):
                    current_decision_time = statistics.median(current_data['decision_times'])

                # Check decision time drift
                if baseline_decision_time is not None and current_decision_time is not None:
                    decision_delta = current_decision_time - baseline_decision_time
                    if abs(decision_delta) >= DECISION_TIME_ABSOLUTE_THRESHOLD_DAYS or (baseline_decision_time > 0 and abs(decision_delta / baseline_decision_time) >= DECISION_TIME_RELATIVE_THRESHOLD):
                        # Calculate severity and confidence
                        severity = min(abs(decision_delta) / DECISION_TIME_SEVERITY_DIVISOR, 1.0)  # Scale to 0-1 range
                        confidence = min((baseline_volume + current_volume) / (min_volume * CONFIDENCE_VOLUME_MULTIPLIER), 1.0)  # Cap at 1.0

                        DriftEvent.objects.create(
                            customer=customer,
                            report_run=report_run,
                            payer=payer,
                            cpt_group=cpt_group,
                            drift_type='DECISION_TIME',
                            baseline_value=baseline_decision_time,
                            current_value=current_decision_time,
                            delta_value=decision_delta,
                            severity=severity,
                            confidence=confidence,
                            baseline_start=baseline_start,
                            baseline_end=baseline_end,
                            current_start=current_start,
                            current_end=current_end
                        )
                        events_created += 1

            # Update report run with summary
            report_run.summary_json = {
                'baseline_start': baseline_start.isoformat(),
                'baseline_end': baseline_end.isoformat(),
                'current_start': current_start.isoformat(),
                'current_end': current_end.isoformat(),
                'groups_considered': groups_considered,
                'events_created': events_created,
                'parameters': {
                    'baseline_days': baseline_days,
                    'current_days': current_days,
                    'min_volume': min_volume,
                    'as_of_date': as_of_date.isoformat()
                }
            }
            report_run.status = 'success'
            report_run.finished_at = timezone.now()
            report_run.save()

            return report_run

    except Exception as e:
        # Handle failure - mark report run as failed and clean up any drift events
        report_run.status = 'failed'
        report_run.finished_at = timezone.now()
        report_run.summary_json = {
            'error': str(e),
            'baseline_start': baseline_start.isoformat(),
            'baseline_end': baseline_end.isoformat(),
            'current_start': current_start.isoformat(),
            'current_end': current_end.isoformat(),
            'parameters': {
                'baseline_days': baseline_days,
                'current_days': current_days,
                'min_volume': min_volume,
                'as_of_date': as_of_date.isoformat()
            }
        }
        report_run.save()

        # Delete any drift events that might have been created
        DriftEvent.objects.filter(report_run=report_run).delete()

        raise
