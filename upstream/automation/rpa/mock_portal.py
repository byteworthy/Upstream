"""
Mock Payer Portal Implementation for Testing and Development.

Provides a fully functional mock implementation of PayerPortalBase
that simulates payer portal interactions without requiring actual
portal credentials or network access.

Features:
- Configurable failure rates for testing error handling
- Simulated processing delays for realistic timing
- Deterministic confirmation number generation
- Full audit trail of operations
"""

import random
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from django.utils import timezone

from .base import (
    PayerPortalBase,
    ReauthRequest,
    AppealRequest,
    SubmissionResult,
    StatusResult,
    PortalAuthenticationError,
    PortalSubmissionError,
    PortalLookupError,
)


class MockPayerPortal(PayerPortalBase):
    """
    Mock implementation of PayerPortalBase for testing.

    Simulates payer portal interactions with configurable behavior:
    - Configurable failure rate for testing error handling
    - Simulated processing delay for realistic timing
    - Generates mock confirmation numbers
    - Tracks all submissions for verification

    Usage:
        # Basic usage
        portal = MockPayerPortal("Aetna")
        portal.login()
        result = portal.submit_reauth_request(request)

        # With failure simulation
        portal = MockPayerPortal("Aetna", fail_rate=0.1)  # 10% failure rate

        # With context manager
        with MockPayerPortal("Aetna") as portal:
            result = portal.submit_reauth_request(request)

    Attributes:
        fail_rate: Probability of simulated failures (0.0-1.0)
        delay_seconds: Simulated processing delay in seconds
        submissions: List of all submissions made through this portal
    """

    # Track all submissions across instances for testing
    _all_submissions: Dict[str, Dict[str, Any]] = {}

    def __init__(
        self,
        payer: str,
        fail_rate: float = 0.0,
        delay_seconds: float = 0.1,
        timeout: int = 30,
        max_retries: int = 3,
    ):
        """
        Initialize mock portal.

        Args:
            payer: Name of the payer to simulate
            fail_rate: Probability of simulated failures (0.0-1.0)
            delay_seconds: Simulated processing delay
            timeout: Request timeout (not used in mock)
            max_retries: Max retries (not used in mock)
        """
        super().__init__(payer, timeout, max_retries)
        self.fail_rate = max(0.0, min(1.0, fail_rate))  # Clamp to 0-1
        self.delay_seconds = max(0.0, delay_seconds)
        self.submissions: List[Dict[str, Any]] = []
        self._login_attempts = 0
        self._credentials_valid = True

    def set_credentials_valid(self, valid: bool) -> None:
        """Set whether credentials should be treated as valid."""
        self._credentials_valid = valid

    def login(self) -> bool:
        """
        Simulate portal login.

        Returns:
            True if login successful

        Raises:
            PortalAuthenticationError: If credentials invalid or fail_rate triggered
        """
        self._login_attempts += 1
        self._simulate_delay()

        # Check credentials
        if not self._credentials_valid:
            raise PortalAuthenticationError(
                f"Invalid credentials for {self.payer} portal"
            )

        # Simulate random failure
        if self._should_fail():
            raise PortalAuthenticationError(
                f"Portal temporarily unavailable for {self.payer}"
            )

        self._session_active = True
        return True

    def logout(self) -> bool:
        """
        Simulate portal logout.

        Returns:
            True always (logout always succeeds in mock)
        """
        self._session_active = False
        return True

    def submit_reauth_request(self, request: ReauthRequest) -> SubmissionResult:
        """
        Simulate reauthorization request submission.

        Args:
            request: ReauthRequest with submission data

        Returns:
            SubmissionResult with mock confirmation number

        Raises:
            PortalSubmissionError: If fail_rate triggered
        """
        self._simulate_delay()

        # Simulate random failure
        if self._should_fail():
            return SubmissionResult(
                success=False,
                confirmation_number=None,
                submitted_at=timezone.now(),
                payer=self.payer,
                error_message="Portal temporarily unavailable. Please try again.",
                error_code="MOCK_TEMP_ERROR",
            )

        # Generate mock confirmation number
        confirmation = self._generate_confirmation("REAUTH")

        # Calculate estimated response date (3-5 business days)
        estimated_response = timezone.now() + timedelta(days=random.randint(3, 5))

        result = SubmissionResult(
            success=True,
            confirmation_number=confirmation,
            submitted_at=timezone.now(),
            payer=self.payer,
            response_data={
                "auth_number": request.auth_number,
                "patient_id": request.patient_id,
                "units_requested": request.units_requested,
                "service_type": request.service_type,
            },
            estimated_response_date=estimated_response,
            portal_url=f"https://mock.{self.payer.lower()}.com/status/{confirmation}",
        )

        # Track submission
        submission_record = {
            "type": "reauth",
            "request": request,
            "result": result,
            "timestamp": timezone.now(),
        }
        self.submissions.append(submission_record)
        self._all_submissions[confirmation] = submission_record

        return result

    def submit_appeal(self, appeal: AppealRequest) -> SubmissionResult:
        """
        Simulate appeal submission.

        Args:
            appeal: AppealRequest with appeal data

        Returns:
            SubmissionResult with mock confirmation number

        Raises:
            PortalSubmissionError: If fail_rate triggered
        """
        self._simulate_delay()

        # Simulate random failure
        if self._should_fail():
            return SubmissionResult(
                success=False,
                confirmation_number=None,
                submitted_at=timezone.now(),
                payer=self.payer,
                error_message="Appeal submission failed. Portal maintenance in progress.",
                error_code="MOCK_MAINTENANCE",
            )

        # Generate mock confirmation number
        confirmation = self._generate_confirmation("APPEAL")

        # Appeals typically take longer (10-30 days)
        estimated_response = timezone.now() + timedelta(days=random.randint(10, 30))

        result = SubmissionResult(
            success=True,
            confirmation_number=confirmation,
            submitted_at=timezone.now(),
            payer=self.payer,
            response_data={
                "claim_id": appeal.claim_id,
                "denial_reason": appeal.denial_reason,
                "appeal_level": appeal.appeal_level,
                "documents_attached": len(appeal.supporting_docs),
            },
            estimated_response_date=estimated_response,
            portal_url=f"https://mock.{self.payer.lower()}.com/appeals/{confirmation}",
        )

        # Track submission
        submission_record = {
            "type": "appeal",
            "request": appeal,
            "result": result,
            "timestamp": timezone.now(),
        }
        self.submissions.append(submission_record)
        self._all_submissions[confirmation] = submission_record

        return result

    def check_status(self, confirmation_number: str) -> StatusResult:
        """
        Simulate status check for a previous submission.

        Args:
            confirmation_number: Confirmation number to look up

        Returns:
            StatusResult with mock status

        Raises:
            PortalLookupError: If confirmation number not found
        """
        self._simulate_delay()

        # Look up submission
        submission = self._all_submissions.get(confirmation_number)

        if not submission:
            raise PortalLookupError(
                f"Confirmation number {confirmation_number} not found"
            )

        # Simulate status progression based on time elapsed
        submitted_at = submission["timestamp"]
        elapsed = timezone.now() - submitted_at

        if elapsed < timedelta(hours=1):
            status = "pending"
            details = "Submission received, awaiting review"
        elif elapsed < timedelta(days=1):
            status = "in_review"
            details = "Under clinical review"
        elif elapsed < timedelta(days=3):
            status = "in_review"
            details = "Medical director review in progress"
        else:
            # After 3 days, randomly approve or deny (80% approval rate)
            if random.random() < 0.8:
                status = "approved"
                details = "Request approved"
            else:
                status = "denied"
                details = "Request denied - additional documentation required"

        return StatusResult(
            confirmation_number=confirmation_number,
            status=status,
            status_date=timezone.now(),
            payer=self.payer,
            details=details,
            next_action=self._get_next_action(status),
            response_data={
                "submission_type": submission["type"],
                "elapsed_hours": elapsed.total_seconds() / 3600,
            },
        )

    def _generate_confirmation(self, prefix: str) -> str:
        """Generate a mock confirmation number."""
        unique_id = uuid.uuid4().hex[:8].upper()
        return f"MOCK-{prefix}-{unique_id}"

    def _should_fail(self) -> bool:
        """Determine if this operation should fail based on fail_rate."""
        return random.random() < self.fail_rate

    def _simulate_delay(self) -> None:
        """Simulate network/processing delay."""
        if self.delay_seconds > 0:
            time.sleep(self.delay_seconds)

    def _get_next_action(self, status: str) -> Optional[str]:
        """Get recommended next action based on status."""
        actions = {
            "pending": "Wait for initial review",
            "in_review": "No action required - check back in 24-48 hours",
            "approved": "Authorization active - proceed with services",
            "denied": "Review denial reason and consider appeal",
            "expired": "Submit new authorization request",
        }
        return actions.get(status)

    @classmethod
    def clear_all_submissions(cls) -> None:
        """Clear all tracked submissions (for test cleanup)."""
        cls._all_submissions.clear()

    @classmethod
    def get_submission(cls, confirmation_number: str) -> Optional[Dict[str, Any]]:
        """Get a submission by confirmation number."""
        return cls._all_submissions.get(confirmation_number)
