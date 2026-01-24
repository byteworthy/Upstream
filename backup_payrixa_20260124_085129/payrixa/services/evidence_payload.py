"""Shared evidence payload builder for Hub v1 products."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from django.db.models import Sum

from upstream.products.driftwatch import DRIFTWATCH_V1_EVENT_TYPE


def get_alert_interpretation(evidence_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Generate operator-friendly interpretation of an alert.
    
    Returns a dict with:
        - urgency_level: 'high', 'medium', or 'low'
        - urgency_label: Human-readable urgency (e.g., "Investigate Today")
        - plain_language: One-sentence explanation of what this means
        - historical_context: Whether this is new, recurring, or trending
        - action_steps: List of recommended next steps
        - is_likely_noise: Boolean indicating if this might be noise
    """
    if not evidence_payload:
        return _default_interpretation()
    
    severity = evidence_payload.get('severity')
    delta = evidence_payload.get('delta')
    signal_type = evidence_payload.get('signal_type', '')
    product_name = evidence_payload.get('product_name', 'Upstream')
    entity_label = evidence_payload.get('entity_label', 'Unknown')
    
    # Normalize severity to float
    severity_value = _normalize_severity(severity)
    delta_value = _normalize_delta(delta)
    
    # Determine urgency
    urgency = _calculate_urgency(severity_value, delta_value)
    
    # Generate plain language explanation
    plain_language = _generate_plain_language(
        product_name, signal_type, entity_label, severity_value, delta_value
    )
    
    # Determine if likely noise
    is_likely_noise = severity_value < 0.3 and abs(delta_value) < 0.05
    
    # Generate action steps based on urgency
    action_steps = _generate_action_steps(urgency['level'], signal_type, entity_label)
    
    # Historical context (placeholder - would need DB lookup for real implementation)
    historical_context = _generate_historical_context(severity_value)
    
    return {
        'urgency_level': urgency['level'],
        'urgency_label': urgency['label'],
        'plain_language': plain_language,
        'historical_context': historical_context,
        'action_steps': action_steps,
        'is_likely_noise': is_likely_noise,
    }


def _default_interpretation() -> Dict[str, Any]:
    """Return default interpretation when no evidence is available."""
    return {
        'urgency_level': 'medium',
        'urgency_label': 'Review This Week',
        'plain_language': 'This signal indicates a change in payer behavior that falls outside normal patterns.',
        'historical_context': None,
        'action_steps': [
            'Review the evidence table to identify affected claims',
            'Check payer correspondence for policy changes',
            'Brief your billing team on what to watch',
            'Monitor for recurrence in next week\'s report',
        ],
        'is_likely_noise': False,
    }


def _normalize_severity(severity) -> float:
    """Convert severity to float value between 0 and 1."""
    if severity is None:
        return 0.5
    if isinstance(severity, str):
        severity_map = {'low': 0.25, 'medium': 0.5, 'high': 0.75, 'critical': 0.9}
        return severity_map.get(severity.lower(), 0.5)
    try:
        return float(severity)
    except (TypeError, ValueError):
        return 0.5


def _normalize_delta(delta) -> float:
    """Convert delta to float value."""
    if delta is None:
        return 0.0
    try:
        return float(delta)
    except (TypeError, ValueError):
        return 0.0


def _calculate_urgency(severity_value: float, delta_value: float) -> Dict[str, str]:
    """Calculate urgency level and label based on severity and delta."""
    # High urgency: high severity OR large delta (>10 points)
    if severity_value >= 0.7 or abs(delta_value) >= 0.10:
        return {'level': 'high', 'label': 'Investigate Today'}
    
    # Medium urgency: medium severity OR moderate delta (5-10 points)
    if severity_value >= 0.4 or abs(delta_value) >= 0.05:
        return {'level': 'medium', 'label': 'Review This Week'}
    
    # Low urgency: everything else
    return {'level': 'low', 'label': 'Monitor for Trend'}


def _generate_plain_language(
    product_name: str,
    signal_type: str,
    entity_label: str,
    severity_value: float,
    delta_value: float
) -> str:
    """Generate a plain-language explanation of the signal."""
    # DriftWatch explanations
    if signal_type == 'DENIAL_RATE':
        if delta_value > 0:
            direction = "increased"
            impact = "more of your claims are being denied"
        else:
            direction = "decreased"
            impact = "fewer claims are being denied (good news, verify it's real)"
        
        points = abs(delta_value) * 100
        if severity_value >= 0.7:
            urgency = "This is a significant shift that warrants immediate attention."
        elif severity_value >= 0.4:
            urgency = "This is notable but not critical—review when you can this week."
        else:
            urgency = "This is a small change—watch for it to continue before acting."
        
        return f"{entity_label}'s denial rate has {direction} by {points:.1f} percentage points. This means {impact}. {urgency}"
    
    # DenialScope explanations
    if signal_type == 'denial_dollars_spike':
        if severity_value >= 0.7:
            return f"There's a significant spike in denial dollars from {entity_label}. This could indicate a contract change, policy update, or systemic coding issue that needs investigation today."
        elif severity_value >= 0.4:
            return f"Denial dollars from {entity_label} have increased above normal variance. This is worth reviewing this week to understand the cause."
        else:
            return f"Minor increase in denial dollars from {entity_label}. Monitor this payer for continued variance."
    
    # Generic fallback
    return f"A change has been detected for {entity_label} that falls outside normal patterns. Review the evidence to understand the cause."


def _generate_action_steps(urgency_level: str, signal_type: str, entity_label: str) -> List[str]:
    """Generate recommended action steps based on urgency and signal type."""
    if urgency_level == 'high':
        return [
            f"Pull 5-10 sample claims from {entity_label} from the evidence table",
            "Review denial reasons and payer correspondence for policy changes",
            "Check if contract terms were recently updated",
            "Brief your billing team today on what to watch",
            "Consider reaching out to your payer representative if pattern continues",
        ]
    elif urgency_level == 'medium':
        return [
            "Review the evidence table to identify which claims are affected",
            "Compare to previous weeks—is this a new pattern or recurring?",
            "Schedule review with billing leadership this week",
            "Document for your next payer contract discussion",
        ]
    else:  # low
        return [
            "Note this signal for awareness",
            "No immediate action required",
            "Watch for recurrence in next week's report",
            "If pattern continues for 2-3 weeks, escalate to medium priority",
        ]


def _generate_historical_context(severity_value: float) -> str:
    """Generate historical context message.
    
    Note: This is a simplified version. A full implementation would:
    - Query AlertEvent history for this (customer, signal_type, entity)
    - Determine if this is first occurrence, recurring, or trending
    """
    # Placeholder implementation - returns context based on severity
    # Real implementation would check AlertEvent history
    if severity_value >= 0.7:
        return "This appears to be a new or escalating pattern that hasn't been seen at this level recently."
    elif severity_value >= 0.4:
        return "Similar signals have been detected before. Compare to previous alerts for this payer."
    else:
        return "This is a minor variance that may resolve on its own. Watch for continuation."


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
