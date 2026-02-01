"""
PT/OT Time-Based CPT Codes Constants.

This module contains the standard time-based CPT codes used in Physical Therapy
and Occupational Therapy billing. The 8-minute rule requires tracking time
spent on each service to determine billable units.

Per the 8-minute rule:
- 8-22 minutes = 1 unit
- 23-37 minutes = 2 units
- 38-52 minutes = 3 units
- 53-67 minutes = 4 units
- And so on...
"""

from django.conf import settings

# Standard time duration (minutes) for time-based PT/OT CPT codes
# Each code maps to its standard 15-minute unit duration
# Format: {'CPT_CODE': minutes_per_unit}

TIME_BASED_CPTS = {
    # Therapeutic Exercises
    "97110": 15,  # Therapeutic exercises (strength, endurance, flexibility)
    # Neuromuscular Re-education
    "97112": 15,  # Neuromuscular re-education (movement, balance)
    # Aquatic Therapy
    "97113": 15,  # Aquatic therapy with therapeutic exercises
    # Gait Training
    "97116": 15,  # Gait training (includes stair climbing)
    # Therapeutic Activities
    "97530": 15,  # Therapeutic activities (functional performance)
    # Manual Therapy
    "97140": 15,  # Manual therapy (mobilization/manipulation)
    # Cognitive Skills Development
    "97129": 15,  # Cognitive function interventions (initial 15 min)
    "97130": 15,  # Cognitive function interventions (each addl 15 min)
    # Self-Care/Home Management Training
    "97535": 15,  # Self-care/home management training (ADL)
    # Community/Work Reintegration Training
    "97537": 15,  # Community/work reintegration training
    # Wheelchair Management Training
    "97542": 15,  # Wheelchair management/propulsion training
    # Work Conditioning
    "97545": 120,  # Work hardening/conditioning (initial 2 hours)
    "97546": 60,  # Work hardening/conditioning (each addl hour)
    # Sensory Integration
    "97533": 15,  # Sensory integrative techniques
    # Orthotic/Prosthetic Management
    "97760": 15,  # Orthotic management and training (initial)
    "97761": 15,  # Prosthetic training (initial)
    "97763": 15,  # Orthotic/prosthetic management (subsequent)
    # Electrical Stimulation (Attended)
    "97032": 15,  # Electrical stimulation (manual), each 15 min
    # Iontophoresis
    "97033": 15,  # Iontophoresis, each 15 minutes
    # Ultrasound
    "97035": 15,  # Ultrasound, each 15 minutes
    # Vasopneumatic Devices
    "97016": 15,  # Vasopneumatic devices application
    # Traction (Mechanical)
    "97012": 15,  # Traction, mechanical
    # Contrast Baths
    "97034": 15,  # Contrast baths, each 15 minutes
    # Whirlpool
    "97022": 15,  # Whirlpool
    # Massage
    "97124": 15,  # Massage (effleurage, petrissage, tapotement)
    # Group Therapy
    "97150": 15,  # Group therapeutic procedures (2+ patients)
    # Physical Performance Test
    "97750": 15,  # Physical performance test with written report
    # Athletic Training Evaluation
    "97169": 15,  # Athletic training evaluation, low complexity
    "97170": 15,  # Athletic training evaluation, moderate complexity
    "97171": 15,  # Athletic training evaluation, high complexity
    # Athletic Training Re-evaluation
    "97172": 15,  # Athletic training re-evaluation
    # Dry Needling
    "20560": 15,  # Needle insertion without injection; 1-2 muscles
    "20561": 15,  # Needle insertion without injection; 3+ muscles
    # Additional Neuromuscular Codes
    "97014": 15,  # Electrical stimulation (unattended)
    # Hot/Cold Packs (non-billable but tracked for total treatment time)
    "97010": 15,  # Hot or cold packs application
    # Paraffin Bath
    "97018": 15,  # Paraffin bath
}

# Service-based (untimed) CPT codes - included for reference
# These are billed per service, not per unit of time
SERVICE_BASED_CPTS = {
    "97161": "PT evaluation, low complexity",
    "97162": "PT evaluation, moderate complexity",
    "97163": "PT evaluation, high complexity",
    "97164": "PT re-evaluation",
    "97165": "OT evaluation, low complexity",
    "97166": "OT evaluation, moderate complexity",
    "97167": "OT evaluation, high complexity",
    "97168": "OT re-evaluation",
}

# 8-Minute Rule thresholds for unit calculation
# Total minutes: minimum-maximum range for each unit count
EIGHT_MINUTE_RULE_THRESHOLDS = {
    1: (8, 22),  # 1 unit: 8-22 minutes
    2: (23, 37),  # 2 units: 23-37 minutes
    3: (38, 52),  # 3 units: 38-52 minutes
    4: (53, 67),  # 4 units: 53-67 minutes
    5: (68, 82),  # 5 units: 68-82 minutes
    6: (83, 97),  # 6 units: 83-97 minutes
    7: (98, 112),  # 7 units: 98-112 minutes
    8: (113, 127),  # 8 units: 113-127 minutes
}

# Default variance threshold for underpayment detection
DEFAULT_VARIANCE_THRESHOLD = 0.85  # 85% of expected payment

# Severity thresholds
VARIANCE_WARNING_THRESHOLD = 0.85  # Warning at 85%
VARIANCE_HIGH_THRESHOLD = 0.70  # High severity at 70%
VARIANCE_CRITICAL_THRESHOLD = 0.50  # Critical at 50%


def get_time_based_cpts() -> dict:
    """
    Get TIME_BASED_CPTS, allowing override from Django settings.

    Settings key: PTOT_TIME_BASED_CPTS

    Returns:
        dict: CPT code to minutes mapping
    """
    return getattr(settings, "PTOT_TIME_BASED_CPTS", TIME_BASED_CPTS)


def get_service_based_cpts() -> dict:
    """
    Get SERVICE_BASED_CPTS, allowing override from Django settings.

    Settings key: PTOT_SERVICE_BASED_CPTS

    Returns:
        dict: CPT code to description mapping
    """
    return getattr(settings, "PTOT_SERVICE_BASED_CPTS", SERVICE_BASED_CPTS)


def is_time_based_cpt(cpt_code: str) -> bool:
    """
    Check if a CPT code is time-based.

    Args:
        cpt_code: CPT code to check

    Returns:
        bool: True if time-based, False otherwise
    """
    cpts = get_time_based_cpts()
    return cpt_code in cpts


def get_minutes_per_unit(cpt_code: str) -> int:
    """
    Get the standard minutes per unit for a CPT code.

    Args:
        cpt_code: CPT code to look up

    Returns:
        int: Minutes per unit (default 15 if not found)
    """
    cpts = get_time_based_cpts()
    return cpts.get(cpt_code, 15)


def calculate_units_from_minutes(total_minutes: int) -> int:
    """
    Calculate billable units from total treatment minutes using 8-minute rule.

    The 8-minute rule:
    - Less than 8 minutes of a service cannot be billed
    - 8-22 minutes = 1 unit
    - Each additional 15 minutes adds 1 unit

    Args:
        total_minutes: Total treatment time in minutes

    Returns:
        int: Number of billable units
    """
    if total_minutes < 8:
        return 0

    # For 8-22 minutes, 1 unit
    # For 23-37 minutes, 2 units
    # Pattern: (minutes - 8) // 15 + 1
    return (total_minutes - 8) // 15 + 1


def get_variance_threshold() -> float:
    """
    Get variance threshold from settings or default.

    Settings key: PTOT_VARIANCE_THRESHOLD

    Returns:
        float: Variance threshold (default 0.85)
    """
    return getattr(settings, "PTOT_VARIANCE_THRESHOLD", DEFAULT_VARIANCE_THRESHOLD)


# =============================================================================
# G-CODE FUNCTIONAL LIMITATION CONSTANTS
# =============================================================================

# 7 Functional Limitation Categories per CMS
FUNCTIONAL_LIMITATION_CATEGORIES = {
    "MOBILITY": {
        "name": "Mobility",
        "description": "Walking & Moving Around",
        "gcodes": {"current": "G8978", "goal": "G8979", "discharge": "G8980"},
    },
    "CHANGING_POSITION": {
        "name": "Changing/Maintaining Position",
        "description": "Body Positions",
        "gcodes": {"current": "G8981", "goal": "G8982", "discharge": "G8983"},
    },
    "CARRYING": {
        "name": "Carrying/Moving Objects",
        "description": "Lifting & Carrying",
        "gcodes": {"current": "G8984", "goal": "G8985", "discharge": "G8986"},
    },
    "SELF_CARE": {
        "name": "Self Care",
        "description": "ADLs",
        "gcodes": {"current": "G8987", "goal": "G8988", "discharge": "G8989"},
    },
    "OTHER_PT": {
        "name": "Other PT/OT Primary",
        "description": "Other PT/OT",
        "gcodes": {"current": "G8990", "goal": "G8991", "discharge": "G8992"},
    },
    "OTHER_SLP": {
        "name": "Other SLP Primary",
        "description": "Speech-Language",
        "gcodes": {"current": "G8993", "goal": "G8994", "discharge": "G8995"},
    },
    "SWALLOWING": {
        "name": "Swallowing",
        "description": "Eating & Swallowing",
        "gcodes": {"current": "G8996", "goal": "G8997", "discharge": "G8998"},
    },
}

# G-code ranges for validation
GCODE_RANGES = {
    "current": ("G8978", "G8996"),
    "goal": ("G8979", "G8997"),
    "discharge": ("G8980", "G8998"),
}

# Severity modifiers (low to high severity)
SEVERITY_MODIFIERS = ["CH", "CI", "CJ", "CK", "CL", "CM", "CN"]

# Progress report interval (every N visits)
PROGRESS_REPORT_VISIT_INTERVAL = 10

# Reporting types
REPORTING_TYPES = ("EVALUATION", "PROGRESS", "DISCHARGE")

# CPT codes that require G-codes (evaluations)
CPT_CODES_REQUIRING_GCODES = [
    "97161",  # PT Eval Low
    "97162",  # PT Eval Moderate
    "97163",  # PT Eval High
    "97164",  # PT Re-Eval
    "97165",  # OT Eval Low
    "97166",  # OT Eval Moderate
    "97167",  # OT Eval High
    "97168",  # OT Re-Eval
    "92521",  # SLP Eval
    "92522",  # SLP Eval
    "92523",  # SLP Eval
    "92524",  # SLP Eval
]

# Alert thresholds
GCODE_ALERT_THRESHOLDS = {
    "progress_report_warning_visits": 8,  # Alert 2 visits before required
    "progress_report_due_visits": 10,  # Required at this visit
}
