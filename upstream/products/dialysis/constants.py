"""
Dialysis MA Variance Detection Constants.

Configuration values for Medicare Advantage variance detection,
including known MA payers and payment variance thresholds.

Values can be overridden via Django settings:
- DIALYSIS_VARIANCE_THRESHOLD: Override default 0.85 threshold
- DIALYSIS_HIGH_VARIANCE_THRESHOLD: Override default 0.70 critical threshold
- DIALYSIS_MA_PAYER_LIST: Override list of known MA payers
"""

from decimal import Decimal
from django.conf import settings

# =============================================================================
# Variance Thresholds
# =============================================================================

# Default variance threshold - payments below 85% of Medicare baseline
# trigger alerts
VARIANCE_THRESHOLD = Decimal(getattr(settings, "DIALYSIS_VARIANCE_THRESHOLD", "0.85"))

# High variance threshold - payments below 70% of Medicare baseline
# are critical
HIGH_VARIANCE_THRESHOLD = Decimal(
    getattr(settings, "DIALYSIS_HIGH_VARIANCE_THRESHOLD", "0.70")
)

# Minimum sample size for reliable variance detection
MIN_BASELINE_SAMPLE_SIZE = getattr(settings, "DIALYSIS_MIN_SAMPLE_SIZE", 100)


# =============================================================================
# Medicare Advantage Payer List
# =============================================================================

# Major Medicare Advantage payers by enrollment
# Source: CMS Medicare Advantage Enrollment Data (2024)
# These payers account for approximately 80% of MA enrollment
DEFAULT_MA_PAYER_LIST = [
    # National MA Plans
    "UnitedHealthcare Medicare Advantage",
    "Humana Medicare Advantage",
    "CVS Health / Aetna Medicare",
    "Kaiser Permanente Medicare",
    "Cigna Medicare Advantage",
    "Centene / WellCare Medicare",
    "Anthem Blue Cross Medicare",
    "Blue Cross Blue Shield MA",
    "Molina Healthcare Medicare",
    "Elevance Health Medicare",
    # Regional MA Plans
    "Devoted Health Medicare",
    "Alignment Healthcare Medicare",
    "Clover Health Medicare",
    "Bright Health Medicare",
    "Oscar Health Medicare",
    "Scan Health Plan Medicare",
    "Priority Health Medicare",
    "Health Net Medicare",
    "AvMed Medicare",
    "SelectHealth Medicare",
]

# Allow override from settings
MA_PAYER_LIST = getattr(settings, "DIALYSIS_MA_PAYER_LIST", DEFAULT_MA_PAYER_LIST)


# =============================================================================
# Dialysis-Specific CPT Codes
# =============================================================================

# Common dialysis CPT codes for baseline tracking
# These are the most frequently billed dialysis procedure codes
DIALYSIS_CPT_CODES = {
    # Hemodialysis
    "90935": "Hemodialysis (single evaluation)",
    "90937": "Hemodialysis (multiple evaluations)",
    "90940": "Hemodialysis access flow study",
    "90945": "Dialysis procedure other than hemodialysis (single)",
    "90947": "Dialysis procedure other than hemodialysis (multiple)",
    # Peritoneal Dialysis
    "90951": "ESRD services, <2 years, 4+ visits/month",
    "90952": "ESRD services, <2 years, 2-3 visits/month",
    "90953": "ESRD services, <2 years, 1 visit/month",
    "90954": "ESRD services, 2-11 years, 4+ visits/month",
    "90955": "ESRD services, 2-11 years, 2-3 visits/month",
    "90956": "ESRD services, 2-11 years, 1 visit/month",
    "90957": "ESRD services, 12-19 years, 4+ visits/month",
    "90958": "ESRD services, 12-19 years, 2-3 visits/month",
    "90959": "ESRD services, 12-19 years, 1 visit/month",
    "90960": "ESRD services, 20+ years, 4+ visits/month",
    "90961": "ESRD services, 20+ years, 2-3 visits/month",
    "90962": "ESRD services, 20+ years, 1 visit/month",
    "90963": "ESRD home dialysis per month, <2 years",
    "90964": "ESRD home dialysis per month, 2-11 years",
    "90965": "ESRD home dialysis per month, 12-19 years",
    "90966": "ESRD home dialysis per month, 20+ years",
    # Dialysis Training
    "90989": "Dialysis training, complete course",
    "90993": "Dialysis training, incomplete",
    # Dialysis Access Procedures
    "36800": "Insertion of cannula for hemodialysis",
    "36810": "Insertion of cannula for hemodialysis (arteriovenous)",
    "36815": "Insertion of cannula for hemodialysis (arteriovenous bypass)",
    "36818": "Arteriovenous fistula creation",
    "36819": "Arteriovenous fistula upper arm",
    "36820": "Arteriovenous fistula forearm",
    "36821": "Arteriovenous fistula (direct arteriovenous)",
    "36825": "Arteriovenous fistula, autogenous graft",
    "36830": "Arteriovenous fistula, non-autogenous graft",
    "36831": "Thrombectomy arteriovenous fistula",
    "36832": "Revision arteriovenous fistula",
    "36833": "Revision arteriovenous fistula (w/ thrombectomy)",
}


# =============================================================================
# Alert Configuration
# =============================================================================

# Alert severity mapping based on variance ratio
VARIANCE_SEVERITY_MAP = {
    "critical": {
        "min_ratio": Decimal("0"),
        "max_ratio": HIGH_VARIANCE_THRESHOLD,
    },
    "high": {
        "min_ratio": HIGH_VARIANCE_THRESHOLD,
        "max_ratio": Decimal("0.80"),
    },
    "medium": {
        "min_ratio": Decimal("0.80"),
        "max_ratio": VARIANCE_THRESHOLD,
    },
    "none": {
        "min_ratio": VARIANCE_THRESHOLD,
        "max_ratio": Decimal("1.00"),
    },
}

# Annual treatment assumption for projected loss calculation
# Standard dialysis: 3 treatments/week = 156 treatments/year
ANNUAL_DIALYSIS_TREATMENTS = 156


# =============================================================================
# Revenue Loss Calculation
# =============================================================================

# Minimum variance amount to trigger projected loss calculation
MIN_VARIANCE_FOR_PROJECTION = Decimal("10.00")

# Confidence factors for projected loss estimates
PROJECTION_CONFIDENCE_FACTORS = {
    "high": 0.9,  # Historical data available for 12+ months
    "medium": 0.7,  # Historical data available for 6-12 months
    "low": 0.5,  # Historical data available for <6 months
}


def get_variance_threshold():
    """Get the current variance threshold, allowing runtime override."""
    setting_value = getattr(
        settings, "DIALYSIS_VARIANCE_THRESHOLD", str(VARIANCE_THRESHOLD)
    )
    return Decimal(setting_value)


def get_high_variance_threshold():
    """Get current high variance threshold, allowing runtime override."""
    setting_value = getattr(
        settings,
        "DIALYSIS_HIGH_VARIANCE_THRESHOLD",
        str(HIGH_VARIANCE_THRESHOLD),
    )
    return Decimal(setting_value)


def get_ma_payer_list():
    """Get the current MA payer list, allowing runtime override."""
    return getattr(settings, "DIALYSIS_MA_PAYER_LIST", MA_PAYER_LIST)


def is_ma_payer(payer_name: str) -> bool:
    """
    Check if a payer is a known Medicare Advantage payer.

    Performs case-insensitive partial matching.

    Args:
        payer_name: Name of the payer to check

    Returns:
        True if payer is a known MA payer, False otherwise
    """
    if not payer_name:
        return False

    payer_lower = payer_name.lower()
    ma_payers = get_ma_payer_list()

    for ma_payer in ma_payers:
        if ma_payer.lower() in payer_lower or payer_lower in ma_payer.lower():
            return True

    # Also check for common MA indicators
    ma_indicators = ["medicare advantage", "ma ", "mapd", "medicare part c"]
    return any(indicator in payer_lower for indicator in ma_indicators)
