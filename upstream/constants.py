"""
Upstream Constants and Configuration Values.

Centralized location for magic numbers, thresholds, and configuration values
used throughout the application. This makes the codebase more maintainable
and allows easy tuning of business logic parameters.
"""

# =============================================================================
# Severity Thresholds
# =============================================================================

# Severity value thresholds for alert classification
SEVERITY_THRESHOLD_CRITICAL = 0.7  # >= 0.7 is critical/high urgency
SEVERITY_THRESHOLD_MEDIUM = 0.4  # >= 0.4 is medium urgency
SEVERITY_THRESHOLD_LOW = 0.3  # < 0.3 is low urgency

# Severity mapping from string to numeric values
SEVERITY_NUMERIC_VALUES = {
    "low": 0.25,
    "medium": 0.5,
    "high": 0.75,
    "critical": 0.9,
}

# Default severity when unable to determine
SEVERITY_DEFAULT = 0.5


# =============================================================================
# Drift Detection Configuration
# =============================================================================

# Time window configuration for drift detection
DRIFT_BASELINE_DAYS = 90  # Historical baseline period (default: 90 days)
DRIFT_CURRENT_DAYS = 14  # Current comparison period (default: 14 days)

# Minimum volume thresholds for statistical significance
DRIFT_MIN_VOLUME = 30  # Minimum claims in both windows for drift detection

# Denial rate drift thresholds
DENIAL_RATE_ABSOLUTE_THRESHOLD = 0.05  # 5 percentage points absolute change
DENIAL_RATE_RELATIVE_THRESHOLD = 0.5  # 50% relative change

# Decision time drift thresholds
DECISION_TIME_ABSOLUTE_THRESHOLD_DAYS = 3  # 3 days absolute change
DECISION_TIME_RELATIVE_THRESHOLD = 0.5  # 50% relative change

# Severity calculation multipliers
DENIAL_DELTA_SEVERITY_MULTIPLIER = 2.0  # Scale denial delta to 0-1 range
DECISION_TIME_SEVERITY_DIVISOR = 10.0  # Scale decision time to 0-1 range

# Confidence calculation
CONFIDENCE_VOLUME_MULTIPLIER = 4  # Volume factor for confidence calculation


# =============================================================================
# Alert Configuration
# =============================================================================

# Alert suppression configuration
ALERT_SUPPRESSION_COOLDOWN_HOURS = 4  # Hours between similar alerts
ALERT_SUPPRESSION_NOISE_WINDOW_DAYS = 30  # Days to look back for noise patterns
ALERT_SUPPRESSION_NOISE_THRESHOLD = 2  # Number of "noise" judgments to suppress

# Historical context window
ALERT_HISTORICAL_CONTEXT_DAYS = 60  # Days to look back for similar alerts

# Delta thresholds for urgency calculation
ALERT_HIGH_URGENCY_DELTA = 0.10  # >= 10 percentage points is high urgency
ALERT_MEDIUM_URGENCY_DELTA = 0.05  # >= 5 percentage points is medium urgency


# =============================================================================
# Payment Delay Signal Configuration
# =============================================================================

# Minimum confidence threshold for low severity signals
PAYMENT_DELAY_MIN_CONFIDENCE_LOW_SEVERITY = 0.5


# =============================================================================
# DelayGuard Urgency Thresholds
# =============================================================================

# Delta days thresholds for urgency classification (DelayGuard)
DELAYGUARD_URGENT_THRESHOLD_DAYS = 15  # >= 15 days delta is URGENT
DELAYGUARD_HIGH_THRESHOLD_DAYS = 10  # >= 10 days delta is HIGH
DELAYGUARD_MEDIUM_THRESHOLD_DAYS = 5  # >= 5 days delta is MEDIUM
DELAYGUARD_LOW_THRESHOLD_DAYS = 3  # >= 3 days delta is LOW


# =============================================================================
# Processing Time Drift Configuration
# =============================================================================

# Processing time drift thresholds (DriftWatch)
PROCESSING_TIME_DRIFT_THRESHOLD_DAYS = (
    5  # Alert if processing time increased by 5+ days
)
PROCESSING_TIME_DRIFT_NORMALIZATION_DIVISOR = (
    30  # Normalize days to months for severity calc
)
PROCESSING_TIME_DRIFT_SEVERITY_THRESHOLD = (
    0.2  # Minimum severity threshold for processing time drift
)


# =============================================================================
# Cache Configuration
# =============================================================================

# Default cache TTL values (seconds)
CACHE_TTL_SHORT = 300  # 5 minutes - for frequently changing data
CACHE_TTL_MEDIUM = 900  # 15 minutes - for moderately stable data
CACHE_TTL_LONG = 3600  # 1 hour - for stable data
CACHE_TTL_VERY_LONG = 86400  # 24 hours - for very stable data

# Cache key maximum length before hashing
CACHE_KEY_MAX_LENGTH = 200


# =============================================================================
# Query Optimization
# =============================================================================

# Pagination limits
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100

# Query timeouts (seconds)
QUERY_TIMEOUT_DEFAULT = 30
QUERY_TIMEOUT_REPORT = 60
QUERY_TIMEOUT_EXPORT = 300


# =============================================================================
# Data Quality Thresholds
# =============================================================================

# Completeness thresholds
DATA_QUALITY_COMPLETENESS_EXCELLENT = 0.95  # >= 95% complete
DATA_QUALITY_COMPLETENESS_GOOD = 0.80  # >= 80% complete
DATA_QUALITY_COMPLETENESS_FAIR = 0.60  # >= 60% complete

# Accuracy thresholds
DATA_QUALITY_ACCURACY_EXCELLENT = 0.98  # >= 98% accurate
DATA_QUALITY_ACCURACY_GOOD = 0.90  # >= 90% accurate
DATA_QUALITY_ACCURACY_FAIR = 0.75  # >= 75% accurate


# =============================================================================
# Report Generation
# =============================================================================

# Default report parameters
REPORT_MAX_TOP_ITEMS = 20  # Maximum items in "top N" lists
REPORT_TREND_DAYS = 30  # Days for trend analysis
REPORT_ARTIFACT_RETENTION_DAYS = 90  # Days to retain report artifacts


# =============================================================================
# Integration Configuration
# =============================================================================

# Webhook retry configuration
WEBHOOK_MAX_RETRIES = 3
WEBHOOK_RETRY_DELAY_SECONDS = 60
WEBHOOK_TIMEOUT_SECONDS = 10

# Email configuration
EMAIL_MAX_RECIPIENTS = 50
EMAIL_ATTACHMENT_MAX_SIZE_MB = 10


# =============================================================================
# Security Configuration
# =============================================================================

# Rate limiting
RATE_LIMIT_DEFAULT = "100/hour"
RATE_LIMIT_AUTHENTICATED = "1000/hour"
RATE_LIMIT_API_STRICT = "60/minute"

# Token expiration
TOKEN_ACCESS_LIFETIME_MINUTES = 60
TOKEN_REFRESH_LIFETIME_DAYS = 7


# =============================================================================
# Celery Task Configuration
# =============================================================================

# Task timeouts (seconds)
CELERY_TASK_SOFT_TIME_LIMIT = 300  # 5 minutes soft limit
CELERY_TASK_TIME_LIMIT = 600  # 10 minutes hard limit
CELERY_REPORT_TASK_TIME_LIMIT = 1800  # 30 minutes for reports

# Task retry configuration
CELERY_MAX_RETRIES = 3
CELERY_RETRY_BACKOFF = 60  # Seconds


# =============================================================================
# Statistical Analysis
# =============================================================================

# Statistical significance thresholds
STATISTICAL_SIGNIFICANCE_P_VALUE = 0.05  # p < 0.05 for significance
STATISTICAL_CONFIDENCE_INTERVAL = 0.95  # 95% confidence interval

# Outlier detection
OUTLIER_ZSCORE_THRESHOLD = 3.0  # Z-score > 3.0 is an outlier
OUTLIER_IQR_MULTIPLIER = 1.5  # IQR * 1.5 for outlier boundaries


# =============================================================================
# DenialScope Configuration
# =============================================================================

# Dollar spike detection threshold (DenialScope)
DENIAL_DOLLARS_SPIKE_THRESHOLD = 50000  # $50K weekly denial dollars triggers alert


# =============================================================================
# Business Logic Constants
# =============================================================================

# Claim status values
CLAIM_STATUS_PAID = "PAID"
CLAIM_STATUS_DENIED = "DENIED"
CLAIM_STATUS_PENDING = "PENDING"
CLAIM_STATUS_CANCELLED = "CANCELLED"

# Valid claim outcomes for analysis
CLAIM_VALID_OUTCOMES = [CLAIM_STATUS_PAID, CLAIM_STATUS_DENIED]

# Report run types
REPORT_TYPE_WEEKLY = "weekly"
REPORT_TYPE_MONTHLY = "monthly"
REPORT_TYPE_ADHOC = "adhoc"

# Drift event types
DRIFT_TYPE_DENIAL_RATE = "DENIAL_RATE"
DRIFT_TYPE_DECISION_TIME = "DECISION_TIME"
DRIFT_TYPE_ALLOWED_AMOUNT = "ALLOWED_AMOUNT"

# Trend directions
TREND_DIRECTION_INCREASING = "increasing"
TREND_DIRECTION_DECREASING = "decreasing"
TREND_DIRECTION_STABLE = "stable"


# =============================================================================
# UI/Display Constants
# =============================================================================

# Chart colors (severity-based)
COLOR_CRITICAL = "#d32f2f"  # Red
COLOR_HIGH = "#ff9800"  # Orange
COLOR_MEDIUM = "#ffc107"  # Amber
COLOR_LOW = "#2196f3"  # Blue
COLOR_INFO = "#4caf50"  # Green

# Date format patterns
DATE_FORMAT_DISPLAY = "%Y-%m-%d"
DATE_FORMAT_LONG = "%B %d, %Y"
DATETIME_FORMAT_DISPLAY = "%Y-%m-%d %H:%M:%S"
DATETIME_FORMAT_ISO = "%Y-%m-%dT%H:%M:%SZ"


# =============================================================================
# File Processing
# =============================================================================

# Upload file constraints
UPLOAD_MAX_FILE_SIZE_MB = 100
UPLOAD_MAX_ROWS = 1000000  # 1 million rows
UPLOAD_BATCH_SIZE = 1000  # Process in batches of 1000

# Supported file formats
UPLOAD_SUPPORTED_FORMATS = [".csv", ".xlsx", ".xls", ".tsv"]


# =============================================================================
# Helper Functions
# =============================================================================


def get_severity_label(severity_value: float) -> str:
    """
    Convert numeric severity to human-readable label.

    Args:
        severity_value: Numeric severity (0.0 to 1.0)

    Returns:
        str: Severity label ('critical', 'high', 'medium', or 'low')
    """
    if severity_value >= SEVERITY_THRESHOLD_CRITICAL:
        return "critical"
    elif severity_value >= SEVERITY_THRESHOLD_MEDIUM:
        return "medium"
    else:
        return "low"


def get_urgency_info(severity_value: float, delta_value: float) -> dict:
    """
    Calculate urgency level and label based on severity and delta.

    Args:
        severity_value: Numeric severity (0.0 to 1.0)
        delta_value: Numeric delta/change value

    Returns:
        dict: {'level': str, 'label': str} with urgency information
    """
    if (
        severity_value >= SEVERITY_THRESHOLD_CRITICAL
        or abs(delta_value) >= ALERT_HIGH_URGENCY_DELTA
    ):
        return {"level": "high", "label": "Investigate Today"}
    elif (
        severity_value >= SEVERITY_THRESHOLD_MEDIUM
        or abs(delta_value) >= ALERT_MEDIUM_URGENCY_DELTA
    ):
        return {"level": "medium", "label": "Review This Week"}
    else:
        return {"level": "low", "label": "Monitor for Trend"}
