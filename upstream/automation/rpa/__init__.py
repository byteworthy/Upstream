"""
RPA (Robotic Process Automation) Module for Payer Portal Integrations.

This module provides the infrastructure for automating interactions with
payer portals for reauthorization requests, appeals, and status checks.

Exports:
    - PayerPortalBase: Abstract base class for portal implementations
    - MockPayerPortal: Mock implementation for testing
    - ReauthRequest: Data structure for reauth submissions
    - AppealRequest: Data structure for appeal submissions
    - SubmissionResult: Standardized portal response
    - StatusResult: Status check response
    - get_portal_for_payer: Factory function to get appropriate portal
    - Portal exceptions

Usage:
    from upstream.automation.rpa import get_portal_for_payer, ReauthRequest

    portal = get_portal_for_payer("Aetna")
    portal.login()

    request = ReauthRequest(
        auth_number="AUTH123",
        patient_id="PAT456",
        payer="Aetna",
        service_type="PT",
        units_requested=12,
    )

    result = portal.submit_reauth_request(request)
    if result.success:
        print(f"Confirmation: {result.confirmation_number}")
"""

from typing import Dict, Type, Optional

from .base import (
    PayerPortalBase,
    ReauthRequest,
    AppealRequest,
    SubmissionResult,
    StatusResult,
    PortalError,
    PortalAuthenticationError,
    PortalConnectionError,
    PortalSubmissionError,
    PortalSessionExpiredError,
    PortalLookupError,
)
from .mock_portal import MockPayerPortal


# Registry of available portal implementations
# Add real implementations here as they are developed
_PORTAL_REGISTRY: Dict[str, Type[PayerPortalBase]] = {
    # Real implementations (to be added)
    # "aetna": AetnaPortal,
    # "unitedhealthcare": UnitedHealthcarePortal,
    # "bcbs": BlueCrossPortal,
    # "humana": HumanaPortal,
    # "cigna": CignaPortal,
}


def get_portal_for_payer(
    payer: str,
    use_mock: bool = True,
    fail_rate: float = 0.0,
    **kwargs,
) -> PayerPortalBase:
    """
    Factory function to get the appropriate portal for a payer.

    Returns a real portal implementation if available, otherwise
    returns a MockPayerPortal for testing/development.

    Args:
        payer: Name of the payer (e.g., 'Aetna', 'UnitedHealthcare')
        use_mock: If True, always return mock portal (for testing)
        fail_rate: Failure rate for mock portal (0.0-1.0)
        **kwargs: Additional arguments passed to portal constructor

    Returns:
        PayerPortalBase implementation for the specified payer

    Examples:
        # Get portal (will use mock if no real implementation)
        portal = get_portal_for_payer("Aetna")

        # Force mock for testing
        portal = get_portal_for_payer("Aetna", use_mock=True, fail_rate=0.1)

        # Get real portal if available
        portal = get_portal_for_payer("Aetna", use_mock=False)
    """
    payer_key = payer.lower().replace(" ", "").replace("-", "")

    # Check for real implementation
    if not use_mock and payer_key in _PORTAL_REGISTRY:
        portal_class = _PORTAL_REGISTRY[payer_key]
        return portal_class(payer=payer, **kwargs)

    # Return mock portal
    return MockPayerPortal(
        payer=payer,
        fail_rate=fail_rate,
        **kwargs,
    )


def register_portal(payer: str, portal_class: Type[PayerPortalBase]) -> None:
    """
    Register a new portal implementation.

    Args:
        payer: Name of the payer
        portal_class: Portal class that implements PayerPortalBase
    """
    payer_key = payer.lower().replace(" ", "").replace("-", "")
    _PORTAL_REGISTRY[payer_key] = portal_class


def get_available_portals() -> Dict[str, bool]:
    """
    Get list of payers and whether real implementation exists.

    Returns:
        Dict mapping payer names to availability status
    """
    common_payers = [
        "Aetna",
        "UnitedHealthcare",
        "Blue Cross Blue Shield",
        "Humana",
        "Cigna",
        "Medicare",
        "Medicaid",
    ]

    return {
        payer: payer.lower().replace(" ", "").replace("-", "") in _PORTAL_REGISTRY
        for payer in common_payers
    }


__all__ = [
    # Base classes
    "PayerPortalBase",
    "MockPayerPortal",
    # Data structures
    "ReauthRequest",
    "AppealRequest",
    "SubmissionResult",
    "StatusResult",
    # Factory functions
    "get_portal_for_payer",
    "register_portal",
    "get_available_portals",
    # Exceptions
    "PortalError",
    "PortalAuthenticationError",
    "PortalConnectionError",
    "PortalSubmissionError",
    "PortalSessionExpiredError",
    "PortalLookupError",
]
