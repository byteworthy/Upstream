"""
Utility functions and mappings for specialty module management.

Provides:
- Alert type to specialty mappings
- Specialty navigation configuration
- Helper functions for specialty detection
"""

from typing import List, Optional

# Mapping of alert_type to specialty code
# Used for backfilling existing alerts and creating new alerts
ALERT_TYPE_TO_SPECIALTY = {
    # Dialysis alerts
    "dialysis_ma_variance": "DIALYSIS",
    "dialysis_ma_payment_variance": "DIALYSIS",
    "dialysis_esrd_pps": "DIALYSIS",
    "dialysis_payment_spike": "DIALYSIS",
    "dialysis_tdapa_tpnies": "DIALYSIS",
    # ABA Therapy alerts
    "aba_utilization": "ABA",
    "aba_unit_exhaustion": "ABA",
    "aba_authorization_expiring": "ABA",
    "aba_reauth_expiration": "ABA",
    "aba_credential_expiration": "ABA",
    "aba_bcba_expiring": "ABA",
    # Imaging alerts
    "imaging_missing_pa": "IMAGING",
    "imaging_documentation": "IMAGING",
    "imaging_incomplete_documentation": "IMAGING",
    "imaging_rbm_pa_required": "IMAGING",
    "imaging_auc_noncompliant": "IMAGING",
    # Home Health alerts
    "homehealth_pdgm_mismatch": "HOME_HEALTH",
    "homehealth_f2f_timing": "HOME_HEALTH",
    "homehealth_noa_deadline": "HOME_HEALTH",
    "homehealth_recertification_due": "HOME_HEALTH",
    "homehealth_cert_expiring": "HOME_HEALTH",
    # PT/OT alerts
    "ptot_8_minute_violation": "PTOT",
    "ptot_8_minute_rule": "PTOT",
    "ptot_unit_overbilling": "PTOT",
    "ptot_missing_kx_modifier": "PTOT",
    "ptot_gcode_missing": "PTOT",
    "ptot_gcode_validation": "PTOT",
    "ptot_progress_report_due": "PTOT",
}

# Specialty navigation configuration for frontend
SPECIALTY_NAV_CONFIG = {
    "DIALYSIS": {
        "label": "Dialysis",
        "icon": "Activity",  # Lucide icon name
        "description": "MA payment variance detection",
        "routes": ["/specialty/dialysis"],
        "features": [
            "MA Payment Variance Detection",
            "ESRD PPS Monitoring",
            "TDAPA/TPNIES Add-on Tracking",
        ],
    },
    "ABA": {
        "label": "ABA Therapy",
        "icon": "Users",
        "description": "Authorization tracking & unit monitoring",
        "routes": ["/authorizations", "/specialty/aba"],
        "features": [
            "Authorization Cycle Tracking",
            "Visit Exhaustion Projection",
            "BCBA Credential Tracking",
        ],
    },
    "IMAGING": {
        "label": "Imaging",
        "icon": "Scan",
        "description": "Prior auth requirements & RBM tracking",
        "routes": ["/specialty/imaging"],
        "features": [
            "RBM Requirement Tracking",
            "AUC Compliance Validation",
            "Medical Necessity Scoring",
        ],
    },
    "HOME_HEALTH": {
        "label": "Home Health",
        "icon": "Home",
        "description": "PDGM validation & F2F tracking",
        "routes": ["/authorizations", "/specialty/homehealth"],
        "features": [
            "PDGM Grouper Validation",
            "Face-to-Face Timing",
            "NOA Deadline Tracking",
            "Certification Cycle Management",
        ],
    },
    "PTOT": {
        "label": "PT/OT",
        "icon": "HeartPulse",
        "description": "8-minute rule & G-code validation",
        "routes": ["/specialty/ptot"],
        "features": [
            "8-Minute Rule Validation",
            "KX Modifier Tracking",
            "G-Code Reporting",
        ],
    },
}

# All valid specialty codes
VALID_SPECIALTIES = list(SPECIALTY_NAV_CONFIG.keys())


def get_specialty_from_alert_type(alert_type: str) -> str:
    """
    Map alert type to specialty code.

    Args:
        alert_type: The alert type string (e.g., 'dialysis_ma_variance')

    Returns:
        Specialty code (e.g., 'DIALYSIS') or 'CORE' if not found
    """
    return ALERT_TYPE_TO_SPECIALTY.get(alert_type, "CORE")


def get_alert_types_for_specialty(specialty: str) -> List[str]:
    """
    Get all alert types for a given specialty.

    Args:
        specialty: Specialty code (e.g., 'DIALYSIS')

    Returns:
        List of alert type strings
    """
    return [
        alert_type
        for alert_type, spec in ALERT_TYPE_TO_SPECIALTY.items()
        if spec == specialty.upper()
    ]


def get_specialty_label(specialty: str) -> str:
    """
    Get human-readable label for a specialty code.

    Args:
        specialty: Specialty code (e.g., 'DIALYSIS')

    Returns:
        Human-readable label (e.g., 'Dialysis')
    """
    config = SPECIALTY_NAV_CONFIG.get(specialty.upper(), {})
    return config.get("label", specialty)


def get_specialty_icon(specialty: str) -> str:
    """
    Get icon name for a specialty code.

    Args:
        specialty: Specialty code (e.g., 'DIALYSIS')

    Returns:
        Lucide icon name (e.g., 'Activity')
    """
    config = SPECIALTY_NAV_CONFIG.get(specialty.upper(), {})
    return config.get("icon", "Folder")


def is_valid_specialty(specialty: str) -> bool:
    """
    Check if a specialty code is valid.

    Args:
        specialty: Specialty code to validate

    Returns:
        True if valid, False otherwise
    """
    return specialty.upper() in VALID_SPECIALTIES


def infer_specialty_from_alert_payload(payload: dict) -> Optional[str]:
    """
    Infer specialty from alert payload data.

    Attempts to determine specialty from:
    1. Explicit 'type' field in payload
    2. Prefix matching on 'type' field
    3. Other payload hints

    Args:
        payload: Alert payload dictionary

    Returns:
        Specialty code or None if cannot be inferred
    """
    if not payload:
        return None

    # Check explicit type field
    alert_type = payload.get("type", "")
    if alert_type:
        specialty = ALERT_TYPE_TO_SPECIALTY.get(alert_type)
        if specialty:
            return specialty

        # Try prefix matching
        for prefix, spec in [
            ("dialysis_", "DIALYSIS"),
            ("aba_", "ABA"),
            ("imaging_", "IMAGING"),
            ("homehealth_", "HOME_HEALTH"),
            ("ptot_", "PTOT"),
        ]:
            if alert_type.startswith(prefix):
                return spec

    return None
