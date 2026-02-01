"""
RPA (Robotic Process Automation) Base Module for Payer Portal Integrations.

Provides abstract base class and data structures for automating interactions
with payer portals for reauthorization requests, appeals, and status checks.

Architecture:
- PayerPortalBase: Abstract interface all portal implementations must follow
- ReauthRequest: Data structure for reauthorization submission
- AppealRequest: Data structure for appeal submission
- SubmissionResult: Standardized response from portal operations
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any


@dataclass
class ReauthRequest:
    """
    Data structure for reauthorization request submission.

    Contains all information needed to submit a reauthorization
    request to a payer portal.

    Attributes:
        auth_number: Original authorization number being renewed
        patient_id: Patient identifier in the billing system
        payer: Payer name or ID (e.g., 'Aetna', 'UnitedHealthcare')
        service_type: Type of service requiring authorization
        units_requested: Number of units/visits being requested
        utilization_report_url: URL to supporting utilization documentation
        start_date: Requested start date for new authorization
        end_date: Requested end date for new authorization
        diagnosis_codes: List of ICD-10 diagnosis codes
        cpt_codes: List of CPT procedure codes
        clinical_notes: Optional clinical justification notes
        urgency: Request urgency level (standard, urgent, emergency)
    """

    auth_number: str
    patient_id: str
    payer: str
    service_type: str
    units_requested: int
    utilization_report_url: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    diagnosis_codes: List[str] = field(default_factory=list)
    cpt_codes: List[str] = field(default_factory=list)
    clinical_notes: Optional[str] = None
    urgency: str = "standard"  # standard, urgent, emergency


@dataclass
class AppealRequest:
    """
    Data structure for appeal submission.

    Contains all information needed to submit an appeal
    for a denied claim or authorization.

    Attributes:
        claim_id: Internal claim identifier
        payer: Payer name or ID
        denial_reason: Reason code or description from denial
        appeal_letter: Full text of the appeal letter
        supporting_docs: List of URLs or paths to supporting documents
        original_dos: Original date of service
        billed_amount: Original amount billed
        appeal_level: Level of appeal (first, second, external)
        deadline: Appeal submission deadline
        contact_info: Provider contact information for response
    """

    claim_id: str
    payer: str
    denial_reason: str
    appeal_letter: str
    supporting_docs: List[str] = field(default_factory=list)
    original_dos: Optional[datetime] = None
    billed_amount: Optional[float] = None
    appeal_level: str = "first"  # first, second, external
    deadline: Optional[datetime] = None
    contact_info: Optional[Dict[str, str]] = None


@dataclass
class SubmissionResult:
    """
    Standardized result from portal submission operations.

    Provides a consistent response format across all payer portals.

    Attributes:
        success: Whether the submission was successful
        confirmation_number: Portal-assigned confirmation/reference number
        submitted_at: Timestamp when submission was completed
        payer: Payer the submission was made to
        error_message: Error description if submission failed
        error_code: Payer-specific error code if available
        response_data: Additional response data from portal
        estimated_response_date: Expected date for payer response
        portal_url: URL to track submission status
    """

    success: bool
    confirmation_number: Optional[str]
    submitted_at: datetime
    payer: str
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    response_data: Dict[str, Any] = field(default_factory=dict)
    estimated_response_date: Optional[datetime] = None
    portal_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "confirmation_number": self.confirmation_number,
            "submitted_at": self.submitted_at.isoformat()
            if self.submitted_at
            else None,
            "payer": self.payer,
            "error_message": self.error_message,
            "error_code": self.error_code,
            "response_data": self.response_data,
            "estimated_response_date": (
                self.estimated_response_date.isoformat()
                if self.estimated_response_date
                else None
            ),
            "portal_url": self.portal_url,
        }


@dataclass
class StatusResult:
    """
    Result from checking submission status.

    Attributes:
        confirmation_number: The confirmation number being checked
        status: Current status (pending, approved, denied, in_review)
        status_date: Date of last status update
        payer: Payer name
        details: Additional status details
        next_action: Recommended next action if any
    """

    confirmation_number: str
    status: str  # pending, approved, denied, in_review, expired
    status_date: datetime
    payer: str
    details: Optional[str] = None
    next_action: Optional[str] = None
    response_data: Dict[str, Any] = field(default_factory=dict)


class PayerPortalBase(ABC):
    """
    Abstract base class for payer portal integrations.

    All payer portal implementations must inherit from this class
    and implement the required abstract methods.

    The portal abstraction enables:
    - Consistent interface across all payers
    - Easy addition of new payer integrations
    - Mock implementations for testing
    - Audit logging of all portal interactions

    Usage:
        class AetnaPortal(PayerPortalBase):
            def login(self) -> bool:
                # Implement Aetna-specific login
                pass

            def submit_reauth_request(self, request: ReauthRequest) -> SubmissionResult:
                # Implement Aetna reauth submission
                pass
            ...

    Attributes:
        payer: Name of the payer this portal handles
        timeout: Request timeout in seconds
        max_retries: Maximum retry attempts for failed requests
    """

    def __init__(
        self,
        payer: str,
        timeout: int = 30,
        max_retries: int = 3,
    ):
        """
        Initialize the portal connection.

        Args:
            payer: Name of the payer (e.g., 'Aetna', 'UnitedHealthcare')
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts for transient failures
        """
        self.payer = payer
        self.timeout = timeout
        self.max_retries = max_retries
        self._session_active = False

    @abstractmethod
    def login(self) -> bool:
        """
        Authenticate with the payer portal.

        Returns:
            True if login successful, False otherwise.

        Raises:
            PortalAuthenticationError: If credentials are invalid
            PortalConnectionError: If portal is unreachable
        """
        pass

    @abstractmethod
    def logout(self) -> bool:
        """
        End the portal session.

        Returns:
            True if logout successful, False otherwise.
        """
        pass

    @abstractmethod
    def submit_reauth_request(self, request: ReauthRequest) -> SubmissionResult:
        """
        Submit a reauthorization request to the payer portal.

        Args:
            request: ReauthRequest containing all submission data

        Returns:
            SubmissionResult with confirmation number or error details

        Raises:
            PortalSubmissionError: If submission fails
            PortalSessionExpiredError: If session has expired
        """
        pass

    @abstractmethod
    def submit_appeal(self, appeal: AppealRequest) -> SubmissionResult:
        """
        Submit an appeal for a denied claim.

        Args:
            appeal: AppealRequest containing appeal letter and supporting docs

        Returns:
            SubmissionResult with confirmation number or error details

        Raises:
            PortalSubmissionError: If submission fails
            PortalSessionExpiredError: If session has expired
        """
        pass

    @abstractmethod
    def check_status(self, confirmation_number: str) -> StatusResult:
        """
        Check the status of a previous submission.

        Args:
            confirmation_number: The confirmation number from submission

        Returns:
            StatusResult with current status information

        Raises:
            PortalLookupError: If confirmation number not found
        """
        pass

    @property
    def is_authenticated(self) -> bool:
        """Check if currently authenticated with the portal."""
        return self._session_active

    def __enter__(self):
        """Context manager entry - login to portal."""
        self.login()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - logout from portal."""
        self.logout()
        return False


# Custom exceptions for portal operations
class PortalError(Exception):
    """Base exception for portal operations."""

    pass


class PortalAuthenticationError(PortalError):
    """Raised when portal authentication fails."""

    pass


class PortalConnectionError(PortalError):
    """Raised when portal is unreachable."""

    pass


class PortalSubmissionError(PortalError):
    """Raised when submission to portal fails."""

    pass


class PortalSessionExpiredError(PortalError):
    """Raised when portal session has expired."""

    pass


class PortalLookupError(PortalError):
    """Raised when lookup fails (e.g., confirmation number not found)."""

    pass
