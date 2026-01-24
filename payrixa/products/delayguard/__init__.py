"""
DelayGuard Product Module.

Hub v1 Configuration:
- One signal type only: PAYMENT_DELAY_DRIFT
- Detects meaningful increase in payment latency for a payer versus historical baseline
- Uses ClaimRecord.submitted_date and ClaimRecord.decided_date for days-to-payment calculation
"""

# DelayGuard V1: Locked to PAYMENT_DELAY_DRIFT signal type
# Do NOT add additional signal types for V1
DELAYGUARD_V1_SIGNAL_TYPE = 'PAYMENT_DELAY_DRIFT'

# Window configuration constants (in days)
DELAYGUARD_CURRENT_WINDOW_DAYS = 14
DELAYGUARD_BASELINE_WINDOW_DAYS = 60

# Severity thresholds (delta_days, min_confidence) -> severity
DELAYGUARD_SEVERITY_THRESHOLDS = [
    (10, 0.75, 'critical'),   # delta >= 10 days, confidence >= 0.75
    (7, 0.65, 'high'),        # delta >= 7 days, confidence >= 0.65
    (4, 0.55, 'medium'),      # delta >= 4 days, confidence >= 0.55
    (0, 0.0, 'low'),          # everything else
]

# Minimum sample size for signal generation
DELAYGUARD_MIN_SAMPLE_SIZE = 10

# Data quality thresholds
DELAYGUARD_MIN_DATE_COMPLETENESS = 0.8  # 80% of rows must have valid dates
