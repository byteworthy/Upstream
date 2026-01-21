"""Shared evidence payload builder for Hub v1 products."""
from __future__ import annotations

from typing import Iterable, List, Optional

from django.db.models import Sum

from payrixa.products.driftwatch import DRIFTWATCH_V1_EVENT_TYPE


def _format_date_range(start_date, end_date) -> str:
    if start_date and end_date:
        return f"{start_date} → {end_date}"
    if start_date:
        return f"From {start_date}"
    if end_date:
        return f"Through {end_date}"
    return "-"


def build_denialscope_evidence_payload(
    signal,
    aggregates,
    start_date,
    end_date,
) -> dict:
    """Build shared evidence payload for DenialScope.

    Uses DenialSignal and DenialAggregate data to populate the payload.
    """
    details = (signal.details or {}) if signal else {}

    baseline_value = details.get('baseline_value')
    current_value = details.get('recent_value')
    delta = details.get('delta')

    if baseline_value is None:
        baseline_value = details.get('baseline_denial_rate')
    if current_value is None:
        current_value = details.get('recent_denial_rate')
    if delta is None:
        delta = details.get('rate_delta')

    baseline_count = details.get('baseline_count')
    current_count = details.get('recent_count')

    evidence_rows = []
    if aggregates is not None:
        evidence_rows = list(
            aggregates.values('payer', 'denial_reason').annotate(
                denied_count=Sum('denied_count'),
                total_submitted=Sum('total_submitted_count'),
            ).order_by('-denied_count')[:20]
        )
        for row in evidence_rows:
            total_submitted = row['total_submitted'] or 0
            denial_rate = (row['denied_count'] / total_submitted) if total_submitted > 0 else 0
            row['denial_rate_percent'] = denial_rate * 100

    payload = {
        'product_name': 'DenialScope',
        'signal_type': signal.signal_type if signal else 'denial_dollars_spike',
        'entity_label': signal.payer if signal else '-',
        'date_range': _format_date_range(start_date, end_date),
        'baseline_value': baseline_value,
        'baseline_count': baseline_count,
        'current_value': current_value,
        'current_count': current_count,
        'delta': delta,
        'confidence': signal.confidence if signal else None,
        'severity': signal.severity if signal else None,
        'one_sentence_explanation': signal.summary_text if signal else 'No DenialScope signals yet.',
        'evidence_rows': evidence_rows,
    }
    return payload


def build_driftwatch_evidence_payload(
    drift_event,
    drift_events: Iterable,
) -> dict:
    """Build shared evidence payload for DriftWatch."""
    drift_events_list = list(drift_events) if drift_events is not None else []

    baseline_value = drift_event.baseline_value if drift_event else None
    current_value = drift_event.current_value if drift_event else None
    delta = drift_event.delta_value if drift_event else None
    confidence = drift_event.confidence if drift_event else None
    severity = drift_event.severity if drift_event else None

    if drift_event:
        explanation = (
            f"Denial rate for {drift_event.payer} moved from "
            f"{drift_event.baseline_value:.1%} to {drift_event.current_value:.1%} "
            f"({drift_event.delta_value:+.1%})."
        )
    else:
        explanation = 'No DriftWatch signals yet.'

    evidence_rows: List[dict] = []
    for event in drift_events_list[:20]:
        evidence_rows.append({
            'payer': event.payer,
            'cpt_group': event.cpt_group,
            'drift_type': event.drift_type,
            'baseline_value': event.baseline_value,
            'current_value': event.current_value,
            'delta_value': event.delta_value,
            'severity': event.severity,
            'confidence': event.confidence,
        })

    payload = {
        'product_name': 'DriftWatch',
        'signal_type': drift_event.drift_type if drift_event else DRIFTWATCH_V1_EVENT_TYPE,
        'entity_label': drift_event.payer if drift_event else '-',
        'date_range': _format_date_range(
            drift_event.baseline_start if drift_event else None,
            drift_event.current_end if drift_event else None,
        ),
        'baseline_value': baseline_value,
        'baseline_count': None,
        'current_value': current_value,
        'current_count': None,
        'delta': delta,
        'confidence': confidence,
        'severity': severity,
        'one_sentence_explanation': explanation,
        'evidence_rows': evidence_rows,
    }
    return payload
