# Upstream Alert Systems: Production Hardening & Amplification

**Generated:** 2026-01-22
**Priority:** Highest Signal, Lowest Noise - Money-Moving Alerts
**Based on:** Developer feedback + existing comprehensive plans

---

## Executive Summary

This document implements production-grade hardening of existing alerts and adds the **highest-signal, lowest-noise** alerting systems that:
- **Move Money**: Direct revenue recovery or prevention
- **Surface Real Risk Early**: Before small issues become massive losses
- **Justify Enforcement**: Clear data for payer negotiations
- **Flawless Execution**: Idempotent, secure, auditable, resilient

### Core Focus (Developer's Tier 1)

1. **Payer Drift Alerts** - Silent reimbursement changes
2. **Underpayment Variance Alerts** - Systematic underpayments
3. **Denial Pattern Change Alerts** - Policy shifts and spikes
4. **Payment Delay Alerts** - Cash flow killers
5. **Authorization Failure Spike Alerts** - Workflow decay or rule changes

Plus 5-10 additional alerts per module to reach 10-15 total per module.

---

## Part 1: Core Alert System Hardening

### Current State Analysis

**Existing Strengths:**
- ✅ Alert generation (DriftWatch, DenialScope)
- ✅ Email notification system
- ✅ Operator feedback (OperatorJudgment model)
- ✅ Basic suppression (4-hour window)
- ✅ Evidence payload generation
- ✅ Audit logging (SystemEvent)

**Critical Gaps:**
- ❌ No retry queue for transient failures
- ❌ Simple suppression doesn't learn from operator feedback
- ❌ No confidence scoring (binary threshold decisions)
- ❌ No rate limiting (alert storms possible)
- ❌ Webhook signatures without replay protection
- ❌ No parallel processing (single-threaded bottleneck)
- ❌ No statistical significance testing
- ❌ Limited error context in failures

### Hardening Implementation

#### 1.1 Alert Processing Engine (Resilient, Parallel)

**File:** `upstream/alerts/processing.py` (NEW)

```python
"""
Production-grade alert processing engine with:
- Parallel processing with fault isolation
- Circuit breaker pattern
- Retry queue with exponential backoff
- Rate limiting
- Comprehensive error handling
"""

import logging
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.db import transaction
from django.utils import timezone
from django.core.cache import cache
from .models import AlertEvent, NotificationChannel
from upstream.core.models import SystemEvent

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Circuit breaker to prevent cascading failures."""

    def __init__(self, failure_threshold=5, recovery_timeout=300):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN

    def allow(self):
        """Check if circuit allows requests."""
        if self.state == 'CLOSED':
            return True

        if self.state == 'OPEN':
            # Check if recovery timeout elapsed
            if self.last_failure_time and \
               (timezone.now() - self.last_failure_time).total_seconds() >= self.recovery_timeout:
                self.state = 'HALF_OPEN'
                return True
            return False

        # HALF_OPEN: allow one request to test
        return True

    def record_success(self):
        """Record successful request."""
        if self.state == 'HALF_OPEN':
            self.state = 'CLOSED'
            self.failure_count = 0

    def record_failure(self):
        """Record failed request."""
        self.failure_count += 1
        self.last_failure_time = timezone.now()

        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'
            logger.error(f"Circuit breaker opened after {self.failure_count} failures")


class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(self, max_per_minute=100):
        self.max_per_minute = max_per_minute

    def allow(self, customer_id):
        """Check if customer is within rate limit."""
        key = f"alert_rate:{customer_id}"
        count = cache.get(key, 0)

        if count >= self.max_per_minute:
            logger.warning(f"Rate limit exceeded for customer {customer_id}: {count}/{self.max_per_minute}")
            return False

        cache.set(key, count + 1, timeout=60)
        return True


class AlertProcessingEngine:
    """Production-grade alert processing with resilience and observability."""

    def __init__(self):
        self.circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=300)
        self.rate_limiter = RateLimiter(max_per_minute=100)

    def process_alert_batch(self, alert_events, max_workers=5):
        """
        Process alerts in parallel with fault isolation.

        Returns:
            dict with succeeded, failed, rate_limited, circuit_open lists
        """
        results = {
            'succeeded': [],
            'failed': [],
            'rate_limited': [],
            'circuit_open': []
        }

        if not alert_events:
            return results

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self._process_single_alert, alert): alert
                for alert in alert_events
            }

            for future in as_completed(futures):
                alert = futures[future]
                try:
                    result = future.result(timeout=30)
                    results['succeeded'].append((alert, result))
                except Exception as e:
                    error_type = e.__class__.__name__

                    if 'CircuitBreakerOpen' in error_type:
                        results['circuit_open'].append(alert)
                    elif 'RateLimitExceeded' in error_type:
                        results['rate_limited'].append(alert)
                    else:
                        results['failed'].append((alert, str(e)))
                        logger.error(f"Alert {alert.id} processing failed: {e}")

        # Log summary
        logger.info(f"Alert batch processed: {len(results['succeeded'])} succeeded, "
                   f"{len(results['failed'])} failed, {len(results['rate_limited'])} rate limited, "
                   f"{len(results['circuit_open'])} circuit open")

        return results

    @transaction.atomic
    def _process_single_alert(self, alert_event):
        """Process single alert with full error context and idempotency."""

        # Idempotency check
        if alert_event.status == 'sent':
            logger.info(f"Alert {alert_event.id} already sent, skipping")
            return {'status': 'already_sent', 'idempotent': True}

        # Rate limit check
        if not self.rate_limiter.allow(alert_event.customer_id):
            raise RateLimitExceeded(f"Customer {alert_event.customer_id} rate limit exceeded")

        # Circuit breaker check
        if not self.circuit_breaker.allow():
            raise CircuitBreakerOpen("Alert delivery circuit breaker is open")

        try:
            # Import here to avoid circular dependency
            from .services import send_alert_notification

            # Process alert
            success = send_alert_notification(alert_event)

            if success:
                self.circuit_breaker.record_success()

                # Audit event
                SystemEvent.objects.create(
                    customer=alert_event.customer,
                    event_type='alert_processed_success',
                    entity_type='AlertEvent',
                    entity_id=str(alert_event.id),
                    metadata={
                        'alert_id': str(alert_event.id),
                        'severity': alert_event.payload.get('severity'),
                        'payer': alert_event.payload.get('payer')
                    }
                )

                return {'status': 'sent', 'success': True}
            else:
                self.circuit_breaker.record_failure()
                raise AlertDeliveryFailed("Alert delivery returned False")

        except Exception as e:
            self.circuit_breaker.record_failure()

            # Update alert with error
            alert_event.status = 'failed'
            alert_event.error_message = f"{e.__class__.__name__}: {str(e)}"
            alert_event.save()

            # Detailed error audit
            SystemEvent.objects.create(
                customer=alert_event.customer,
                event_type='alert_processed_failure',
                entity_type='AlertEvent',
                entity_id=str(alert_event.id),
                metadata={
                    'alert_id': str(alert_event.id),
                    'error_type': e.__class__.__name__,
                    'error_message': str(e),
                    'stack_trace': traceback.format_exc()[:1000]  # Truncate for storage
                }
            )

            raise


class RateLimitExceeded(Exception):
    """Rate limit exceeded exception."""
    pass


class CircuitBreakerOpen(Exception):
    """Circuit breaker open exception."""
    pass


class AlertDeliveryFailed(Exception):
    """Alert delivery failed exception."""
    pass
```

#### 1.2 Intelligent Suppression Engine

**File:** `upstream/alerts/suppression.py` (NEW)

```python
"""
Intelligent suppression with learning from operator feedback.

Key Features:
- Severity-aware suppression windows
- Operator feedback learning
- Escalation detection (don't suppress if getting worse)
- Regression detection (previously resolved, now back)
"""

from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Q
from .models import AlertEvent, OperatorJudgment


class SuppressionEngine:
    """Intelligent alert suppression with learning and severity awareness."""

    # Suppression windows by severity and verdict
    SUPPRESSION_RULES = {
        ('emergency', 'noise'): timedelta(days=30),
        ('critical', 'noise'): timedelta(days=14),
        ('warning', 'noise'): timedelta(days=7),
        ('info', 'noise'): timedelta(days=3),

        ('emergency', 'real'): timedelta(hours=1),  # Short window for real emergencies
        ('critical', 'real'): timedelta(hours=4),
        ('warning', 'real'): timedelta(hours=12),
        ('info', 'real'): timedelta(days=1),

        ('emergency', 'needs_followup'): timedelta(hours=2),
        ('critical', 'needs_followup'): timedelta(hours=8),
        ('warning', 'needs_followup'): timedelta(hours=24),
    }

    def should_suppress(self, alert_event):
        """
        Determine if alert should be suppressed based on history and learning.

        Returns:
            tuple: (should_suppress: bool, context: dict)
        """

        # Get fingerprint for similar alert detection
        fingerprint = self._get_fingerprint(alert_event)

        # Find recent similar alerts
        recent_similar = self._get_recent_similar_alerts(
            alert_event.customer,
            fingerprint,
            lookback_days=30
        )

        if not recent_similar:
            return False, None  # No suppression, no context

        # Analyze operator feedback patterns
        feedback_analysis = self._analyze_feedback_patterns(recent_similar)

        # Rule 1: High noise ratio -> suppress with learned window
        if feedback_analysis['noise_ratio'] > 0.8:  # 80%+ marked as noise
            severity = alert_event.payload.get('severity', 'warning')
            window = self.SUPPRESSION_RULES.get(
                (severity, 'noise'),
                timedelta(days=7)
            )

            if self._within_window(recent_similar[0], window):
                return True, {
                    'reason': 'operator_learned_noise',
                    'noise_ratio': feedback_analysis['noise_ratio'],
                    'similar_count': len(recent_similar),
                    'suppress_until': recent_similar[0].triggered_at + window
                }

        # Rule 2: Escalating severity -> don't suppress
        if self._is_escalating(alert_event, recent_similar):
            return False, {
                'reason': 'escalating_severity',
                'previous_severity': recent_similar[0].payload.get('severity'),
                'current_severity': alert_event.payload.get('severity'),
                'recommendation': 'Do not suppress - issue is getting worse'
            }

        # Rule 3: Regression detection -> don't suppress
        if self._is_regression(alert_event, recent_similar):
            resolved_alert = next(
                (a for a in recent_similar if a.status == 'resolved'),
                None
            )
            if resolved_alert:
                return False, {
                    'reason': 'regression_detected',
                    'last_resolved': resolved_alert.updated_at,
                    'days_since_resolution': (timezone.now() - resolved_alert.updated_at).days,
                    'recommendation': 'Do not suppress - previously resolved issue has returned'
                }

        # Rule 4: Standard deduplication
        window = timedelta(hours=4)  # Default window
        if self._within_window(recent_similar[0], window):
            return True, {
                'reason': 'standard_deduplication',
                'last_alert': recent_similar[0].triggered_at,
                'suppress_until': recent_similar[0].triggered_at + window
            }

        return False, None

    def _get_fingerprint(self, alert_event):
        """Generate fingerprint for alert similarity matching."""
        payload = alert_event.payload
        return {
            'product': payload.get('product_name'),
            'signal_type': payload.get('signal_type'),
            'entity': payload.get('entity_label'),  # payer name
            'cpt_group': payload.get('cpt_group'),
        }

    def _get_recent_similar_alerts(self, customer, fingerprint, lookback_days=30):
        """Get recent alerts matching fingerprint."""
        cutoff = timezone.now() - timedelta(days=lookback_days)

        alerts = AlertEvent.objects.filter(
            customer=customer,
            triggered_at__gte=cutoff,
            payload__product_name=fingerprint['product'],
            payload__signal_type=fingerprint['signal_type'],
            payload__entity_label=fingerprint['entity']
        ).order_by('-triggered_at')

        return list(alerts[:10])  # Limit to recent 10

    def _analyze_feedback_patterns(self, alert_events):
        """Analyze operator feedback to detect noise patterns."""
        alert_ids = [a.id for a in alert_events]
        judgments = OperatorJudgment.objects.filter(
            alert_event_id__in=alert_ids
        )

        total = judgments.count()
        if total == 0:
            return {'noise_ratio': 0, 'real_ratio': 0, 'followup_ratio': 0}

        noise_count = judgments.filter(verdict='noise').count()
        real_count = judgments.filter(verdict='real').count()
        followup_count = judgments.filter(verdict='needs_followup').count()

        return {
            'noise_ratio': noise_count / total,
            'real_ratio': real_count / total,
            'followup_ratio': followup_count / total,
            'total_judgments': total
        }

    def _is_escalating(self, current_alert, previous_alerts):
        """Check if severity is escalating."""
        severity_order = {'info': 1, 'warning': 2, 'critical': 3, 'emergency': 4}

        current_level = severity_order.get(
            current_alert.payload.get('severity', 'warning'), 2
        )
        previous_level = severity_order.get(
            previous_alerts[0].payload.get('severity', 'warning'), 2
        )

        return current_level > previous_level

    def _is_regression(self, current_alert, previous_alerts):
        """Check if this is a regression of a resolved issue."""
        for prev in previous_alerts[:5]:
            if prev.status == 'resolved':
                days_since = (timezone.now() - prev.updated_at).days
                if days_since >= 3:  # Resolved more than 3 days ago
                    return True
        return False

    def _within_window(self, alert_event, window):
        """Check if alert is within suppression window."""
        if not alert_event:
            return False
        return (timezone.now() - alert_event.triggered_at) < window
```

#### 1.3 Confidence Scoring System

**File:** `upstream/alerts/confidence.py` (NEW)

```python
"""
Statistical confidence scoring for alert reliability.

Factors:
1. Sample size adequacy
2. Statistical significance (t-test approximation)
3. Baseline stability
4. Temporal consistency
5. Historical pattern match
"""

import math


class ConfidenceScorer:
    """Calculate multi-dimensional confidence score (0.0 - 1.0) for alerts."""

    def calculate_confidence(self, alert_data):
        """
        Calculate confidence score with breakdown.

        Args:
            alert_data: dict with keys:
                - sample_count: number of data points
                - baseline_value: baseline mean
                - current_value: current value
                - baseline_std: baseline standard deviation
                - consecutive_days_triggered: days in a row
                - historical_real_ratio: % of similar past alerts marked "real"

        Returns:
            dict: {
                'confidence': float (0-1),
                'breakdown': dict of component scores,
                'interpretation': str
            }
        """

        scores = {
            'sample_size': self._score_sample_size(alert_data),
            'statistical_significance': self._score_significance(alert_data),
            'baseline_stability': self._score_baseline_stability(alert_data),
            'temporal_consistency': self._score_temporal_consistency(alert_data),
            'historical_match': self._score_historical_match(alert_data)
        }

        # Weighted average (sample size and significance most important)
        weights = {
            'sample_size': 0.3,
            'statistical_significance': 0.3,
            'baseline_stability': 0.2,
            'temporal_consistency': 0.1,
            'historical_match': 0.1
        }

        confidence = sum(scores[k] * weights[k] for k in scores)

        return {
            'confidence': confidence,
            'breakdown': scores,
            'interpretation': self._interpret_confidence(confidence),
            'weights': weights
        }

    def _score_sample_size(self, alert_data):
        """Score based on sample size adequacy."""
        count = alert_data.get('sample_count', 0)

        # Statistical power thresholds
        if count >= 100: return 1.0    # Excellent
        if count >= 50: return 0.9     # Good
        if count >= 30: return 0.7     # Adequate
        if count >= 10: return 0.5     # Marginal
        return 0.3                      # Weak

    def _score_significance(self, alert_data):
        """Score based on statistical significance (t-test approximation)."""
        baseline = alert_data.get('baseline_value', 0)
        current = alert_data.get('current_value', 0)
        baseline_std = alert_data.get('baseline_std', 0)
        sample_count = alert_data.get('sample_count', 0)

        if baseline_std == 0 or sample_count < 2:
            return 0.5  # Can't calculate, neutral score

        # Simple t-test approximation
        t_stat = abs(current - baseline) / (baseline_std / math.sqrt(sample_count))

        # Map t-statistic to confidence
        if t_stat >= 3.0: return 1.0    # p < 0.003 (very significant)
        if t_stat >= 2.5: return 0.9    # p < 0.01
        if t_stat >= 2.0: return 0.8    # p < 0.05
        if t_stat >= 1.5: return 0.6    # p < 0.15
        return 0.4                       # Not significant

    def _score_baseline_stability(self, alert_data):
        """Score based on baseline stability (coefficient of variation)."""
        baseline_std = alert_data.get('baseline_std', 0)
        baseline_mean = alert_data.get('baseline_value', 1)

        if baseline_mean == 0:
            return 0.5  # Can't calculate, neutral

        # Coefficient of variation
        cv = baseline_std / baseline_mean

        # Lower variation = more stable = higher confidence
        if cv <= 0.1: return 1.0     # Very stable
        if cv <= 0.2: return 0.8     # Stable
        if cv <= 0.4: return 0.6     # Moderate
        if cv <= 0.6: return 0.4     # Unstable
        return 0.2                    # Very unstable

    def _score_temporal_consistency(self, alert_data):
        """Score based on temporal consistency (consecutive days triggered)."""
        consecutive_days = alert_data.get('consecutive_days_triggered', 1)

        if consecutive_days >= 5: return 1.0
        if consecutive_days >= 3: return 0.8
        if consecutive_days >= 2: return 0.6
        return 0.4

    def _score_historical_match(self, alert_data):
        """Score based on historical pattern match (operator feedback)."""
        historical_real_ratio = alert_data.get('historical_real_ratio', 0.5)
        return historical_real_ratio

    def _interpret_confidence(self, confidence):
        """Human-readable confidence interpretation."""
        if confidence >= 0.9: return 'very_high'
        if confidence >= 0.75: return 'high'
        if confidence >= 0.6: return 'medium'
        if confidence >= 0.4: return 'low'
        return 'very_low'
```

**Integration into existing services:**

Update `upstream/alerts/services.py`:

```python
# Add imports at top
from .processing import AlertProcessingEngine
from .suppression import SuppressionEngine
from .confidence import ConfidenceScorer

# Initialize engines (module-level)
processing_engine = AlertProcessingEngine()
suppression_engine = SuppressionEngine()
confidence_scorer = ConfidenceScorer()

# Update evaluate_drift_event to add confidence scoring
def evaluate_drift_event(drift_event):
    """Evaluate a drift event against all active alert rules with confidence scoring."""
    from upstream.core.services import create_audit_event

    alert_events = []
    alert_rules = AlertRule.objects.filter(customer=drift_event.customer, enabled=True)

    for rule in alert_rules:
        if rule.evaluate(drift_event):
            # Check for existing alert (idempotency)
            existing = AlertEvent.objects.filter(
                drift_event=drift_event,
                alert_rule=rule
            ).first()

            if existing:
                logger.info(f"Alert event already exists for rule {rule.name}")
                alert_events.append(existing)
                continue

            # Calculate confidence score
            confidence_data = {
                'sample_count': getattr(drift_event, 'sample_count', 20),
                'baseline_value': drift_event.baseline_value,
                'current_value': drift_event.current_value,
                'baseline_std': getattr(drift_event, 'baseline_std', drift_event.baseline_value * 0.1),
                'consecutive_days_triggered': 1,  # TODO: track this
                'historical_real_ratio': 0.5  # TODO: calculate from OperatorJudgment
            }
            confidence_result = confidence_scorer.calculate_confidence(confidence_data)

            # Build payload with confidence
            payload = {
                'product_name': 'DriftWatch',
                'signal_type': drift_event.drift_type,
                'entity_label': drift_event.payer,
                'payer': drift_event.payer,
                'cpt_group': drift_event.cpt_group,
                'drift_type': drift_event.drift_type,
                'baseline_value': drift_event.baseline_value,
                'current_value': drift_event.current_value,
                'delta_value': drift_event.delta_value,
                'severity': drift_event.severity,
                'rule_name': rule.name,
                'rule_threshold': rule.threshold_value,
                'confidence': confidence_result['confidence'],
                'confidence_breakdown': confidence_result['breakdown'],
                'confidence_interpretation': confidence_result['interpretation']
            }

            # Create alert event
            alert_event = AlertEvent.objects.create(
                customer=drift_event.customer,
                alert_rule=rule,
                drift_event=drift_event,
                report_run=drift_event.report_run,
                triggered_at=timezone.now(),
                status='pending',
                payload=payload
            )
            alert_events.append(alert_event)

            # Audit
            create_audit_event(
                action='alert_event_created',
                entity_type='AlertEvent',
                entity_id=alert_event.id,
                customer=alert_event.customer,
                metadata={
                    'alert_rule': rule.name,
                    'drift_event_id': drift_event.id,
                    'payer': drift_event.payer,
                    'severity': drift_event.severity,
                    'confidence': confidence_result['confidence']
                }
            )

    return alert_events


# Update _is_suppressed to use new SuppressionEngine
def _is_suppressed(customer, evidence_payload, alert_event=None):
    """Check if alert should be suppressed using intelligent suppression."""
    if not evidence_payload:
        return False

    if alert_event:
        # Use new suppression engine
        should_suppress, context = suppression_engine.should_suppress(alert_event)
        if should_suppress and context:
            logger.info(f"Alert {alert_event.id} suppressed: {context['reason']}")
        return should_suppress

    # Fallback to simple window check (for backwards compatibility)
    window_start = timezone.now() - ALERT_SUPPRESSION_COOLDOWN
    return AlertEvent.objects.filter(
        customer=customer,
        status='sent',
        notification_sent_at__gte=window_start,
        payload__product_name=evidence_payload.get('product_name'),
        payload__signal_type=evidence_payload.get('signal_type'),
        payload__entity_label=evidence_payload.get('entity_label'),
    ).exists()


# Update process_pending_alerts to use parallel processing
def process_pending_alerts():
    """Process all pending alert events with parallel execution."""
    pending_alerts = list(AlertEvent.objects.filter(status='pending'))

    if not pending_alerts:
        return {'total': 0, 'sent': 0, 'failed': 0}

    results_summary = processing_engine.process_alert_batch(
        pending_alerts,
        max_workers=5
    )

    return {
        'total': len(pending_alerts),
        'sent': len(results_summary['succeeded']),
        'failed': len(results_summary['failed']),
        'rate_limited': len(results_summary['rate_limited']),
        'circuit_open': len(results_summary['circuit_open'])
    }
```

---

## Part 2: Tier 1 Highest-Signal Alerts (Money-Moving)

These are the alerts your developer identified as the **absolute core set** that justify enforcement and recover cash fastest.

### 2.1 Enhanced Payer Drift Alert (Already Exists - Amplify)

**Status:** ENHANCE EXISTING
**Current:** Single-metric drift (denial_rate OR decision_time)
**Enhancement:** Multi-dimensional composite scoring

**File:** Update `upstream/services/drift_detection.py`

Add composite drift scoring:

```python
def calculate_composite_drift_score(payer_data):
    """
    Multi-dimensional payer drift detection.

    Metrics:
    - denial_rate_delta (40% weight)
    - payment_amount_delta (30% weight) - NEW
    - approval_rate_delta (20% weight) - NEW
    - processing_time_delta (10% weight) - NEW

    Returns composite score (0-1)
    """

    # Denial rate drift (already exists)
    denial_delta = payer_data.get('denial_rate_delta', 0)

    # Payment amount drift (NEW)
    baseline_payment = payer_data.get('baseline_avg_payment', 0)
    current_payment = payer_data.get('current_avg_payment', 0)
    payment_delta = 0
    if baseline_payment > 0:
        payment_delta = (baseline_payment - current_payment) / baseline_payment

    # Approval rate drift (NEW)
    baseline_approval = payer_data.get('baseline_approval_rate', 1.0)
    current_approval = payer_data.get('current_approval_rate', 1.0)
    approval_delta = baseline_approval - current_approval

    # Processing time drift (NEW)
    baseline_time = payer_data.get('baseline_processing_days', 30)
    current_time = payer_data.get('current_processing_days', 30)
    time_delta = 0
    if baseline_time > 0:
        time_delta = (current_time - baseline_time) / baseline_time

    # Weighted composite score
    composite_score = (
        denial_delta * 0.4 +
        payment_delta * 0.3 +
        approval_delta * 0.2 +
        time_delta * 0.1
    )

    return max(0, min(1, composite_score))  # Clamp to [0, 1]
```

**Alert Threshold:** `composite_score > 0.15` (15% weighted change)

### 2.2 Underpayment Variance Alert (NEW - Tier 1 Priority)

**Why It Matters:** Direct revenue loss. Clean enforcement path. Money left on table.

**File:** `upstream/alerts/detectors/underpayment.py` (NEW)

```python
"""
Underpayment Variance Detection

Detects systematic underpayments relative to contract or historical allowed amounts.
"""

from django.db.models import Avg, Sum, Count, StdDev, F
from django.utils import timezone
from datetime import timedelta
from upstream.models import ClaimRecord, Customer
from upstream.alerts.confidence import ConfidenceScorer

confidence_scorer = ConfidenceScorer()


class UnderpaymentDetector:
    """Detect systematic underpayments by payer."""

    MINIMUM_CLAIMS = 20  # Minimum sample size
    VARIANCE_THRESHOLD = 0.05  # 5% variance threshold
    DOLLAR_THRESHOLD = 5000  # $5k monthly impact threshold

    def detect_underpayments(self, customer, lookback_days=90):
        """
        Detect underpayments for a customer.

        Returns list of underpayment alerts.
        """
        cutoff_date = timezone.now().date() - timedelta(days=lookback_days)

        # Get paid claims
        paid_claims = ClaimRecord.objects.filter(
            customer=customer,
            outcome='PAID',
            decided_date__gte=cutoff_date,
            allowed_amount__isnull=False,
            allowed_amount__gt=0
        )

        alerts = []

        # Group by payer and CPT
        payer_cpt_groups = paid_claims.values('payer', 'cpt').annotate(
            claim_count=Count('id'),
            avg_allowed=Avg('allowed_amount'),
            total_allowed=Sum('allowed_amount'),
            std_allowed=StdDev('allowed_amount')
        ).filter(claim_count__gte=self.MINIMUM_CLAIMS)

        for group in payer_cpt_groups:
            # Calculate expected allowed amount (use historical baseline or contract)
            expected_allowed = self._get_expected_allowed(
                customer,
                group['payer'],
                group['cpt']
            )

            if not expected_allowed:
                continue  # No baseline available

            # Calculate variance
            actual_allowed = group['avg_allowed']
            variance = (expected_allowed - actual_allowed) / expected_allowed

            # Calculate dollar impact
            dollar_impact = (expected_allowed - actual_allowed) * group['claim_count']

            # Check thresholds
            if variance > self.VARIANCE_THRESHOLD and dollar_impact > self.DOLLAR_THRESHOLD:
                # Calculate confidence
                confidence_data = {
                    'sample_count': group['claim_count'],
                    'baseline_value': expected_allowed,
                    'current_value': actual_allowed,
                    'baseline_std': group['std_allowed'] or (expected_allowed * 0.1),
                    'consecutive_days_triggered': 1,
                    'historical_real_ratio': 0.7  # High default (underpayment is usually real)
                }
                confidence_result = confidence_scorer.calculate_confidence(confidence_data)

                # Get sample claims for evidence
                sample_claims = paid_claims.filter(
                    payer=group['payer'],
                    cpt=group['cpt']
                ).order_by('-decided_date')[:10]

                alerts.append({
                    'signal_type': 'UNDERPAYMENT_VARIANCE',
                    'payer': group['payer'],
                    'cpt_code': group['cpt'],
                    'expected_allowed': float(expected_allowed),
                    'actual_allowed': float(actual_allowed),
                    'variance_pct': float(variance * 100),
                    'claim_count': group['claim_count'],
                    'monthly_dollar_impact': float(dollar_impact),
                    'confidence': confidence_result['confidence'],
                    'confidence_interpretation': confidence_result['interpretation'],
                    'sample_claim_ids': [c.id for c in sample_claims],
                    'severity': self._calculate_severity(variance, dollar_impact),
                    'recommended_action': 'Submit payment variance report to payer and request retroactive adjustment'
                })

        return alerts

    def _get_expected_allowed(self, customer, payer, cpt_code):
        """
        Get expected allowed amount for payer/CPT.

        Priority:
        1. Contract allowed amount (if available)
        2. Historical 90-day average (if no contract)
        """
        # TODO: Implement contract lookup when contract data available
        # For now, use historical average from 180-90 days ago as baseline

        baseline_start = timezone.now().date() - timedelta(days=180)
        baseline_end = timezone.now().date() - timedelta(days=90)

        baseline_avg = ClaimRecord.objects.filter(
            customer=customer,
            payer=payer,
            cpt=cpt_code,
            outcome='PAID',
            decided_date__gte=baseline_start,
            decided_date__lt=baseline_end,
            allowed_amount__isnull=False
        ).aggregate(avg=Avg('allowed_amount'))['avg']

        return baseline_avg

    def _calculate_severity(self, variance, dollar_impact):
        """Calculate alert severity based on variance and impact."""
        if dollar_impact > 50000 or variance > 0.2:  # >$50k or >20% variance
            return 'critical'
        elif dollar_impact > 20000 or variance > 0.15:
            return 'warning'
        else:
            return 'info'
```

### 2.3 Payment Delay Alert (NEW - Tier 1 Priority)

**Why It Matters:** Cash flow killer. Early warning before AR explodes.

**File:** `upstream/alerts/detectors/payment_delay.py` (NEW)

```python
"""
Payment Delay Detection

Detects payers taking longer to pay than historical norms.
Critical for cash flow management.
"""

from django.db.models import Avg, F, ExpressionWrapper, fields
from django.utils import timezone
from datetime import timedelta
from upstream.models import ClaimRecord


class PaymentDelayDetector:
    """Detect payment delays by payer."""

    MINIMUM_CLAIMS = 15  # Minimum sample for current window
    DELAY_DAYS_THRESHOLD = 7  # Alert if 7+ days slower
    DELAY_PCT_THRESHOLD = 0.3  # Alert if 30% slower

    def detect_payment_delays(self, customer, baseline_days=90, current_days=14):
        """
        Detect payment delays for a customer.

        Args:
            baseline_days: Days for historical baseline (default 90)
            current_days: Days for current window (default 14)

        Returns list of payment delay alerts.
        """
        now = timezone.now().date()

        # Baseline period (90-14 days ago)
        baseline_start = now - timedelta(days=baseline_days + current_days)
        baseline_end = now - timedelta(days=current_days)

        # Current period (last 14 days)
        current_start = baseline_end
        current_end = now

        alerts = []

        # Get unique payers
        payers = ClaimRecord.objects.filter(
            customer=customer,
            outcome='PAID'
        ).values_list('payer', flat=True).distinct()

        for payer in payers:
            # Calculate baseline avg days to payment
            baseline_claims = ClaimRecord.objects.filter(
                customer=customer,
                payer=payer,
                outcome='PAID',
                decided_date__gte=baseline_start,
                decided_date__lt=baseline_end
            ).annotate(
                days_to_payment=ExpressionWrapper(
                    F('decided_date') - F('submitted_date'),
                    output_field=fields.DurationField()
                )
            )

            baseline_stats = baseline_claims.aggregate(
                avg_days=Avg('days_to_payment'),
                count=Count('id')
            )

            if not baseline_stats['avg_days'] or baseline_stats['count'] < 20:
                continue  # Insufficient baseline data

            baseline_avg_days = baseline_stats['avg_days'].days

            # Calculate current avg days to payment
            current_claims = ClaimRecord.objects.filter(
                customer=customer,
                payer=payer,
                outcome='PAID',
                decided_date__gte=current_start,
                decided_date__lt=current_end
            ).annotate(
                days_to_payment=ExpressionWrapper(
                    F('decided_date') - F('submitted_date'),
                    output_field=fields.DurationField()
                )
            )

            current_stats = current_claims.aggregate(
                avg_days=Avg('days_to_payment'),
                count=Count('id')
            )

            if not current_stats['avg_days'] or current_stats['count'] < self.MINIMUM_CLAIMS:
                continue  # Insufficient current data

            current_avg_days = current_stats['avg_days'].days

            # Calculate delay
            delay_delta = current_avg_days - baseline_avg_days
            delay_pct = delay_delta / baseline_avg_days if baseline_avg_days > 0 else 0

            # Check thresholds
            if delay_delta > self.DELAY_DAYS_THRESHOLD or delay_pct > self.DELAY_PCT_THRESHOLD:
                # Calculate cash flow impact
                total_ar = ClaimRecord.objects.filter(
                    customer=customer,
                    payer=payer,
                    outcome='PAID',
                    decided_date__gte=current_start
                ).aggregate(total=Sum('allowed_amount'))['total'] or 0

                # Delayed dollars = claims in pipeline * delay days * daily burn rate
                # Simplified: use total_ar as proxy

                alerts.append({
                    'signal_type': 'PAYMENT_DELAY',
                    'payer': payer,
                    'baseline_avg_days': baseline_avg_days,
                    'current_avg_days': current_avg_days,
                    'delay_delta_days': delay_delta,
                    'delay_pct': float(delay_pct * 100),
                    'current_sample_count': current_stats['count'],
                    'estimated_ar_impact': float(total_ar),
                    'severity': self._calculate_severity(delay_delta, delay_pct),
                    'recommended_action': f'Escalate to payer - payment delays beyond acceptable window. Request expedited processing.'
                })

        return alerts

    def _calculate_severity(self, delay_days, delay_pct):
        """Calculate alert severity."""
        if delay_days > 30 or delay_pct > 0.5:  # >30 days or >50% slower
            return 'critical'
        elif delay_days > 14 or delay_pct > 0.4:
            return 'warning'
        else:
            return 'info'
```

### 2.4 Authorization Failure Spike Alert (NEW - Tier 1 Priority)

**Why It Matters:** Often signals payer rule changes or internal workflow decay. High recovery potential.

**File:** `upstream/alerts/detectors/auth_failure.py` (NEW)

```python
"""
Authorization Failure Spike Detection

Detects increases in auth-related denials beyond baseline.
"""

from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from upstream.models import ClaimRecord


class AuthFailureDetector:
    """Detect authorization failure spikes."""

    # Auth-related denial reason keywords (configurable by payer)
    AUTH_DENIAL_KEYWORDS = [
        'prior authorization',
        'authorization required',
        'authorization expired',
        'services not authorized',
        'auth',
        'pre-cert',
        'precertification'
    ]

    SPIKE_THRESHOLD = 0.05  # 5 percentage points
    SPIKE_MULTIPLIER = 1.5  # 50% relative increase

    def detect_auth_failures(self, customer, baseline_days=90, current_days=14):
        """Detect auth failure spikes for a customer."""
        now = timezone.now().date()

        baseline_start = now - timedelta(days=baseline_days + current_days)
        baseline_end = now - timedelta(days=current_days)
        current_start = baseline_end
        current_end = now

        alerts = []

        # Get unique payers
        payers = ClaimRecord.objects.filter(
            customer=customer
        ).values_list('payer', flat=True).distinct()

        for payer in payers:
            # Baseline auth denial rate
            baseline_total = ClaimRecord.objects.filter(
                customer=customer,
                payer=payer,
                decided_date__gte=baseline_start,
                decided_date__lt=baseline_end
            ).count()

            if baseline_total < 50:
                continue  # Insufficient baseline

            baseline_auth_denials = self._count_auth_denials(
                customer, payer, baseline_start, baseline_end
            )
            baseline_auth_rate = baseline_auth_denials / baseline_total

            # Current auth denial rate
            current_total = ClaimRecord.objects.filter(
                customer=customer,
                payer=payer,
                decided_date__gte=current_start,
                decided_date__lt=current_end
            ).count()

            if current_total < 20:
                continue  # Insufficient current data

            current_auth_denials = self._count_auth_denials(
                customer, payer, current_start, current_end
            )
            current_auth_rate = current_auth_denials / current_total

            # Calculate spike
            spike = current_auth_rate - baseline_auth_rate
            spike_multiplier = current_auth_rate / baseline_auth_rate if baseline_auth_rate > 0 else 0

            # Check thresholds
            if spike > self.SPIKE_THRESHOLD or spike_multiplier > self.SPIKE_MULTIPLIER:
                # Root cause analysis
                root_cause = self._analyze_root_cause(customer, payer, current_start, current_end)

                alerts.append({
                    'signal_type': 'AUTH_FAILURE_SPIKE',
                    'payer': payer,
                    'baseline_auth_rate': float(baseline_auth_rate * 100),
                    'current_auth_rate': float(current_auth_rate * 100),
                    'spike_percentage_points': float(spike * 100),
                    'spike_multiplier': float(spike_multiplier),
                    'auth_denials_count': current_auth_denials,
                    'total_claims': current_total,
                    'root_cause_analysis': root_cause,
                    'severity': self._calculate_severity(spike, current_auth_denials),
                    'recommended_action': self._recommended_action(root_cause)
                })

        return alerts

    def _count_auth_denials(self, customer, payer, start_date, end_date):
        """Count claims with auth-related denials."""
        # Build Q object for auth-related denial reasons
        auth_q = Q()
        for keyword in self.AUTH_DENIAL_KEYWORDS:
            auth_q |= Q(denial_reason_text__icontains=keyword)

        return ClaimRecord.objects.filter(
            customer=customer,
            payer=payer,
            outcome='DENIED',
            decided_date__gte=start_date,
            decided_date__lt=end_date
        ).filter(auth_q).count()

    def _analyze_root_cause(self, customer, payer, start_date, end_date):
        """Analyze root cause of auth failures."""
        # Build Q object for auth keywords
        auth_q = Q()
        for keyword in self.AUTH_DENIAL_KEYWORDS:
            auth_q |= Q(denial_reason_text__icontains=keyword)

        auth_denials = ClaimRecord.objects.filter(
            customer=customer,
            payer=payer,
            outcome='DENIED',
            decided_date__gte=start_date,
            decided_date__lt=end_date
        ).filter(auth_q)

        # Group by CPT code (which services affected?)
        cpt_breakdown = auth_denials.values('cpt').annotate(
            count=Count('id')
        ).order_by('-count')[:5]

        return {
            'top_cpt_codes_affected': [
                {'cpt': item['cpt'], 'count': item['count']}
                for item in cpt_breakdown
            ],
            'hypothesis': self._generate_hypothesis(cpt_breakdown)
        }

    def _generate_hypothesis(self, cpt_breakdown):
        """Generate hypothesis about root cause."""
        if len(cpt_breakdown) == 1:
            return f"Concentrated in CPT {cpt_breakdown[0]['cpt']} - likely payer policy change for this service"
        elif len(cpt_breakdown) >= 3:
            return "Widespread across multiple CPT codes - likely internal workflow issue or broad payer policy change"
        else:
            return "Affecting multiple services - investigate payer auth requirements and internal auth request workflow"

    def _calculate_severity(self, spike, denial_count):
        """Calculate severity."""
        if spike > 0.15 or denial_count > 50:  # >15 pct points or >50 denials
            return 'critical'
        elif spike > 0.10 or denial_count > 20:
            return 'warning'
        else:
            return 'info'

    def _recommended_action(self, root_cause):
        """Generate recommended action."""
        hypothesis = root_cause.get('hypothesis', '')

        if 'policy change' in hypothesis.lower():
            return "Contact payer to confirm auth policy changes. Update internal auth requirement database. Review recent payer bulletins."
        elif 'workflow' in hypothesis.lower():
            return "Review internal auth request workflow. Check staff training on auth requirements. Verify auth requests being submitted timely."
        else:
            return "Investigate auth failure reasons. Review payer-specific auth requirements. Consider process improvement."
```

### 2.5 Repeat Offender Alert (NEW - Tier 1 Priority)

**Why It Matters:** Indicates intentional or systemic payer behavior. Justifies escalation.

**File:** `upstream/alerts/detectors/repeat_offender.py` (NEW)

```python
"""
Repeat Offender Detection

Detects when same payer issue recurs after resolution.
Indicates systematic or intentional payer behavior.
"""

from django.utils import timezone
from datetime import timedelta
from upstream.alerts.models import AlertEvent, OperatorJudgment


class RepeatOffenderDetector:
    """Detect repeat offender patterns."""

    RECURRENCE_WINDOW_DAYS = 30  # Consider recurrence if within 30 days
    MAGNITUDE_TOLERANCE = 0.2  # Within 20% of previous magnitude

    def detect_repeat_offenders(self, customer):
        """
        Detect repeat offenders for a customer.

        Returns list of repeat offender alerts.
        """
        alerts = []

        # Get all resolved alerts in last 90 days
        cutoff = timezone.now() - timedelta(days=90)
        resolved_alerts = AlertEvent.objects.filter(
            customer=customer,
            status='resolved',
            updated_at__gte=cutoff
        ).select_related('alert_rule', 'drift_event')

        for resolved_alert in resolved_alerts:
            # Check for recurrence
            recurrence = self._check_recurrence(resolved_alert)

            if recurrence:
                # Count total recurrences
                recurrence_count = self._count_recurrences(resolved_alert)

                alerts.append({
                    'signal_type': 'REPEAT_OFFENDER',
                    'payer': resolved_alert.payload.get('payer'),
                    'original_signal_type': resolved_alert.payload.get('signal_type'),
                    'previous_alert_id': str(resolved_alert.id),
                    'days_since_resolution': (timezone.now() - resolved_alert.updated_at).days,
                    'recurrence_alert_id': str(recurrence.id),
                    'magnitude_comparison': {
                        'previous': resolved_alert.payload.get('severity'),
                        'current': recurrence.payload.get('severity')
                    },
                    'recurrence_count': recurrence_count,
                    'severity': self._escalate_severity(recurrence_count),
                    'pattern_analysis': self._analyze_pattern(resolved_alert, recurrence),
                    'recommended_action': self._recommended_action(recurrence_count)
                })

        return alerts

    def _check_recurrence(self, resolved_alert):
        """Check if same issue has recurred."""
        # Look for alerts with same fingerprint triggered after resolution
        fingerprint_match = AlertEvent.objects.filter(
            customer=resolved_alert.customer,
            payload__payer=resolved_alert.payload.get('payer'),
            payload__signal_type=resolved_alert.payload.get('signal_type'),
            triggered_at__gt=resolved_alert.updated_at,
            triggered_at__lte=resolved_alert.updated_at + timedelta(days=self.RECURRENCE_WINDOW_DAYS)
        ).exclude(
            id=resolved_alert.id
        ).first()

        if not fingerprint_match:
            return None

        # Check magnitude similarity
        prev_severity = self._severity_to_numeric(resolved_alert.payload.get('severity'))
        curr_severity = self._severity_to_numeric(fingerprint_match.payload.get('severity'))

        if abs(curr_severity - prev_severity) / prev_severity <= self.MAGNITUDE_TOLERANCE:
            return fingerprint_match

        return None

    def _count_recurrences(self, resolved_alert):
        """Count total recurrences of this issue."""
        return AlertEvent.objects.filter(
            customer=resolved_alert.customer,
            payload__payer=resolved_alert.payload.get('payer'),
            payload__signal_type=resolved_alert.payload.get('signal_type'),
            triggered_at__gte=resolved_alert.triggered_at
        ).count()

    def _analyze_pattern(self, original, recurrence):
        """Analyze recurrence pattern."""
        days_between = (recurrence.triggered_at - original.updated_at).days

        # Check if occurs at same time of month
        original_day = original.triggered_at.day
        recurrence_day = recurrence.triggered_at.day

        pattern = {
            'days_between_occurrences': days_between,
            'temporal_pattern': 'Same time of month' if abs(original_day - recurrence_day) <= 3 else 'No clear temporal pattern'
        }

        # Check CPT pattern
        if original.payload.get('cpt_group') == recurrence.payload.get('cpt_group'):
            pattern['cpt_pattern'] = f"Same CPT group: {original.payload.get('cpt_group')}"

        return pattern

    def _severity_to_numeric(self, severity):
        """Convert severity to numeric value."""
        severity_map = {'info': 1, 'warning': 2, 'critical': 3, 'emergency': 4}
        return severity_map.get(severity, 2)

    def _escalate_severity(self, recurrence_count):
        """Escalate severity based on recurrence count."""
        if recurrence_count >= 3:
            return 'emergency'  # 3rd+ recurrence = intentional/systemic
        elif recurrence_count == 2:
            return 'critical'
        else:
            return 'warning'

    def _recommended_action(self, recurrence_count):
        """Generate recommended action based on recurrence count."""
        if recurrence_count >= 3:
            return "ESCALATE: Systematic payer behavior detected. Recommend contract review, executive escalation, or network termination consideration."
        elif recurrence_count == 2:
            return "Escalate to payer account representative. Document pattern. Request written explanation and corrective action plan."
        else:
            return "Monitor closely. If recurs again within 30 days, escalate to payer management."
```

---

## Part 3: Integration & Deployment

### 3.1 Management Command for Alert Detection

**File:** `upstream/management/commands/detect_alerts.py` (NEW)

```python
"""
Django management command to detect and generate alerts.

Usage:
    python manage.py detect_alerts --customer=<customer_id>
    python manage.py detect_alerts --all
"""

from django.core.management.base import BaseCommand
from upstream.models import Customer
from upstream.alerts.detectors.underpayment import UnderpaymentDetector
from upstream.alerts.detectors.payment_delay import PaymentDelayDetector
from upstream.alerts.detectors.auth_failure import AuthFailureDetector
from upstream.alerts.detectors.repeat_offender import RepeatOffenderDetector
from upstream.alerts.models import AlertEvent, AlertRule
from upstream.alerts.services import evaluate_drift_event
from django.utils import timezone


class Command(BaseCommand):
    help = 'Detect and generate alerts for customers'

    def add_arguments(self, parser):
        parser.add_argument(
            '--customer',
            type=int,
            help='Customer ID to process'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Process all customers'
        )

    def handle(self, *args, **options):
        # Get customers to process
        if options['customer']:
            customers = Customer.objects.filter(id=options['customer'])
        elif options['all']:
            customers = Customer.objects.all()
        else:
            self.stdout.write(self.style.ERROR('Must specify --customer or --all'))
            return

        # Initialize detectors
        underpayment_detector = UnderpaymentDetector()
        payment_delay_detector = PaymentDelayDetector()
        auth_failure_detector = AuthFailureDetector()
        repeat_offender_detector = RepeatOffenderDetector()

        for customer in customers:
            self.stdout.write(f"\nProcessing customer: {customer.name}")

            alert_count = 0

            # Run underpayment detection
            self.stdout.write("  - Detecting underpayments...")
            underpayments = underpayment_detector.detect_underpayments(customer)
            alert_count += len(underpayments)
            self.stdout.write(f"    Found {len(underpayments)} underpayment alerts")

            # Run payment delay detection
            self.stdout.write("  - Detecting payment delays...")
            delays = payment_delay_detector.detect_payment_delays(customer)
            alert_count += len(delays)
            self.stdout.write(f"    Found {len(delays)} payment delay alerts")

            # Run auth failure detection
            self.stdout.write("  - Detecting auth failures...")
            auth_failures = auth_failure_detector.detect_auth_failures(customer)
            alert_count += len(auth_failures)
            self.stdout.write(f"    Found {len(auth_failures)} auth failure alerts")

            # Run repeat offender detection
            self.stdout.write("  - Detecting repeat offenders...")
            repeat_offenders = repeat_offender_detector.detect_repeat_offenders(customer)
            alert_count += len(repeat_offenders)
            self.stdout.write(f"    Found {len(repeat_offenders)} repeat offender alerts")

            # TODO: Create AlertEvents for each detected alert
            # (Will be implemented in next phase)

            self.stdout.write(self.style.SUCCESS(
                f"  Total alerts for {customer.name}: {alert_count}"
            ))
```

### 3.2 Scheduled Task Configuration

Add to your task scheduler (Celery, Django-Q, etc.):

```python
# upstream/tasks.py

from django_q.tasks import schedule
from django_q.models import Schedule

def setup_alert_detection_schedule():
    """Setup scheduled alert detection tasks."""

    # Run alert detection every 6 hours
    Schedule.objects.get_or_create(
        func='upstream.management.commands.detect_alerts.Command.handle',
        schedule_type=Schedule.HOURLY,
        minutes=6,
        defaults={
            'name': 'Alert Detection - All Customers',
            'kwargs': {'all': True}
        }
    )
```

---

## Part 4: Testing Strategy

### 4.1 Unit Tests for Detectors

**File:** `upstream/alerts/tests/test_detectors.py` (NEW)

```python
"""Unit tests for alert detectors."""

from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from upstream.models import Customer, ClaimRecord
from upstream.alerts.detectors.underpayment import UnderpaymentDetector
from upstream.alerts.detectors.payment_delay import PaymentDelayDetector


class UnderpaymentDetectorTestCase(TestCase):

    def setUp(self):
        self.customer = Customer.objects.create(name="Test Hospital")
        self.detector = UnderpaymentDetector()

    def test_detect_underpayment_basic(self):
        """Test basic underpayment detection."""
        # Create baseline claims (90-180 days ago)
        baseline_start = timezone.now().date() - timedelta(days=180)
        baseline_end = timezone.now().date() - timedelta(days=90)

        for i in range(25):
            ClaimRecord.objects.create(
                customer=self.customer,
                payer="Aetna",
                cpt="99213",
                submitted_date=baseline_start + timedelta(days=i),
                decided_date=baseline_start + timedelta(days=i+30),
                outcome="PAID",
                allowed_amount=100.00  # Baseline: $100
            )

        # Create recent claims with underpayment (last 90 days)
        recent_start = timezone.now().date() - timedelta(days=90)

        for i in range(25):
            ClaimRecord.objects.create(
                customer=self.customer,
                payer="Aetna",
                cpt="99213",
                submitted_date=recent_start + timedelta(days=i),
                decided_date=recent_start + timedelta(days=i+30),
                outcome="PAID",
                allowed_amount=85.00  # Current: $85 (15% underpayment)
            )

        # Run detection
        alerts = self.detector.detect_underpayments(self.customer)

        # Assertions
        self.assertEqual(len(alerts), 1, "Should detect 1 underpayment alert")
        alert = alerts[0]
        self.assertEqual(alert['payer'], "Aetna")
        self.assertEqual(alert['cpt_code'], "99213")
        self.assertAlmostEqual(alert['variance_pct'], 15.0, delta=1.0)
        self.assertEqual(alert['claim_count'], 25)


# Add similar test cases for other detectors
```

---

## Part 5: Module Recommendations (Beyond Core 3)

Based on your developer's feedback and the comprehensive plans, here are the **RECOMMENDED** additional modules:

### Priority 1: PayerWatch (Module 4)
- **Contract Rate Variance**: Direct revenue recovery
- **Timely Payment Violations**: Legal enforcement + interest
- **Contract Renewal Optimization**: Strategic leverage
- **15 total alerts** focused on payer relationship management
- **ROI:** $50-150k/year

### Priority 2: RevenueWatch (Module 5)
- **AR Aging Monitoring**: Cash flow protection
- **Charge Capture Leakage**: Direct revenue recovery
- **Clean Claim Rate**: Operational efficiency
- **15 total alerts** for end-to-end revenue cycle
- **ROI:** $75-200k/year

### Consider Later: ComplianceWatch (Module 6)
- High ROI but complex (requires NLP)
- Fraud/audit risk mitigation
- **ROI:** $100-500k/year (risk avoidance)
- Implement after core modules proven

---

## Part 6: Next Steps & Implementation Roadmap

### Week 1-2: Core Hardening ✅
1. Implement AlertProcessingEngine (parallel, resilient)
2. Implement SuppressionEngine (learning-based)
3. Implement ConfidenceScorer (statistical)
4. Update existing services to use new engines
5. Comprehensive testing

### Week 3-4: Tier 1 Alerts 🎯
1. Enhance Payer Drift (composite scoring)
2. Implement Underpayment Variance
3. Implement Payment Delay
4. Implement Auth Failure Spike
5. Implement Repeat Offender
6. Create management command
7. Setup scheduled tasks
8. Testing & validation

### Week 5-6: Reach 10-15 Alerts per Module
1. Add 5-8 additional high-value alerts per module
2. Integration testing
3. Performance optimization
4. Documentation

### Week 7+: Additional Modules
1. PayerWatch implementation
2. RevenueWatch implementation
3. Production deployment
4. Customer training

---

## Success Metrics

### Operational
- **Alert Precision:** >80% marked "real" by operators
- **Processing Latency:** <100ms avg, <500ms p99
- **Uptime:** 99.9%
- **False Positive Rate:** <10%

### Business Impact
- **Revenue Recovered:** Track via OperatorJudgment.recovered_amount
- **Denials Prevented:** Pre-submission alerts acted on
- **Time to Detection:** <24 hours for issues
- **Operator Efficiency:** 3x alerts processed per hour

---

**END OF IMPLEMENTATION PLAN**
