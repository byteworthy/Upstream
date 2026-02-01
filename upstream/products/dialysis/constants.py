"""
Dialysis Specialty Constants

Configuration for Medicare Advantage payer detection and variance thresholds.
"""

from django.conf import settings

# Major Medicare Advantage payers (for MA identification)
# This list is used to identify if a payer is an MA plan
MA_PAYER_LIST = [
    "Humana",
    "UnitedHealthcare",
    "UHC",
    "Aetna Medicare",
    "Cigna Medicare",
    "Anthem Medicare",
    "WellCare",
    "Centene",
    "Molina Medicare",
    "Kaiser Medicare",
    "BCBS Medicare",
    "Blue Cross Medicare",
    "Clover Health",
    "Oscar Health Medicare",
    "Alignment Healthcare",
    "Devoted Health",
    "Bright Health Medicare",
    "Lasso Healthcare",
    "Medicare Advantage",
    "MA Plan",
]

# Variance thresholds for MA payment comparison
# If MA payment / Traditional Medicare baseline < threshold, trigger alert
VARIANCE_THRESHOLD = getattr(settings, "DIALYSIS_VARIANCE_THRESHOLD", 0.85)
HIGH_VARIANCE_THRESHOLD = getattr(settings, "DIALYSIS_HIGH_VARIANCE_THRESHOLD", 0.70)

# Severity mapping based on payment ratio
VARIANCE_SEVERITY_MAP = {
    # ratio >= 0.85: No alert
    # ratio < 0.85: MEDIUM severity
    # ratio < 0.70: HIGH severity
    # ratio < 0.50: CRITICAL severity
    "critical_threshold": 0.50,
    "high_threshold": HIGH_VARIANCE_THRESHOLD,
    "medium_threshold": VARIANCE_THRESHOLD,
}

# Alert severity levels
SEVERITY_CRITICAL = "CRITICAL"
SEVERITY_HIGH = "HIGH"
SEVERITY_MEDIUM = "MEDIUM"
SEVERITY_LOW = "LOW"

# Common dialysis CPT codes with descriptions
DIALYSIS_CPT_CODES = {
    # Hemodialysis
    "90935": "Hemodialysis, single evaluation",
    "90937": "Hemodialysis, repeated evaluation",
    "90940": "Hemodialysis access flow study",
    # ESRD-related services
    "90951": "ESRD monthly outpatient services, age <2",
    "90952": "ESRD monthly outpatient services, age 2-11, 4+ visits",
    "90953": "ESRD monthly outpatient services, age 2-11, 2-3 visits",
    "90954": "ESRD monthly outpatient services, age 2-11, 1 visit",
    "90955": "ESRD monthly outpatient services, age 12-19, 4+ visits",
    "90956": "ESRD monthly outpatient services, age 12-19, 2-3 visits",
    "90957": "ESRD monthly outpatient services, age 12-19, 1 visit",
    "90958": "ESRD monthly outpatient services, age 20+, 4+ visits",
    "90959": "ESRD monthly outpatient services, age 20+, 2-3 visits",
    "90960": "ESRD monthly outpatient services, age 20+, 1 visit",
    "90961": "ESRD monthly outpatient services, in-home patient, age <2",
    "90962": "ESRD monthly outpatient services, in-home patient, age 2-11",
    "90963": "ESRD monthly outpatient services, in-home patient, age 12-19",
    "90964": "ESRD monthly outpatient services, in-home patient, age 20+",
    "90965": "ESRD-related services, home dialysis training, day 1",
    "90966": "ESRD-related services, home dialysis training, each add'l day",
    "90967": "ESRD-related services, home dialysis training, complete",
    # Peritoneal dialysis
    "90945": "Peritoneal dialysis, single evaluation",
    "90947": "Peritoneal dialysis, repeated evaluation",
    # Dialysis access management
    "36800": "Insertion of cannula for hemodialysis",
    "36810": "Insertion of cannula for hemodialysis, other than end",
    "36815": "Insertion of cannula for hemodialysis, external revision",
    "36818": "Arteriovenous anastomosis, open; by upper arm cephalic vein",
    "36819": "Arteriovenous anastomosis, open; by upper arm basilic vein",
    "36820": "Arteriovenous anastomosis, open; by forearm vein",
    "36821": "Arteriovenous anastomosis, open; direct, any site",
    "36825": "Creation of arteriovenous fistula by other than direct",
    "36830": "Creation of arteriovenous fistula, nonautogenous",
    "36831": "Thrombectomy, open, arteriovenous fistula without revision",
    "36832": "Revision, open, arteriovenous fistula",
    "36833": "Revision, open, arteriovenous fistula with thrombectomy",
}

# Annual revenue calculation - assumes monthly claim volume
ANNUAL_CLAIM_MULTIPLIER = 12


def is_ma_payer(payer_name: str) -> bool:
    """
    Check if a payer name indicates a Medicare Advantage plan.

    Args:
        payer_name: The name of the payer to check

    Returns:
        True if the payer appears to be an MA plan, False otherwise
    """
    if not payer_name:
        return False
    payer_lower = payer_name.lower()
    for ma_payer in MA_PAYER_LIST:
        if ma_payer.lower() in payer_lower:
            return True
    return False


def get_severity_for_ratio(ratio: float) -> str:
    """
    Determine alert severity based on payment ratio.

    Args:
        ratio: The ratio of MA payment to Medicare baseline (0.0 to 1.0)

    Returns:
        Severity level string (CRITICAL, HIGH, MEDIUM, or None if no alert needed)
    """
    if ratio < VARIANCE_SEVERITY_MAP["critical_threshold"]:
        return SEVERITY_CRITICAL
    elif ratio < VARIANCE_SEVERITY_MAP["high_threshold"]:
        return SEVERITY_HIGH
    elif ratio < VARIANCE_SEVERITY_MAP["medium_threshold"]:
        return SEVERITY_MEDIUM
    return None
