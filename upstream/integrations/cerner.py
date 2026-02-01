"""
Cerner/Oracle Health FHIR Client for EHR Integration.

Provides client class for Cerner FHIR API with:
- OAuth 2.0 authentication
- Claim resource fetching (Cerner uses Claim instead of EOB)
- Cerner-specific FHIR extensions handling
- Rate limiting to respect API limits
- Resilience patterns (retry, circuit breaker)
"""

import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Generator
from urllib.parse import urljoin
import requests
from django.utils import timezone

from upstream.integrations.models import EHRConnection, EHRSyncLog
from upstream.integrations.token_manager import TokenManager, TokenRefreshError
from upstream.integrations.fhir_parser import FHIRParser, FHIRParseError
from upstream.integrations.resilience import (
    ResilientClient,
    CircuitBreakerOpen,
)

logger = logging.getLogger(__name__)


class CernerFHIRError(Exception):
    """Exception raised for Cerner FHIR API errors."""
    pass


class CernerFHIRClient(ResilientClient):
    """
    Client for Cerner/Oracle Health FHIR API.

    Handles OAuth 2.0 authentication, token refresh, and FHIR resource fetching
    with built-in rate limiting and resilience patterns.

    Note: Cerner typically uses Claim resources rather than ExplanationOfBenefit
    for pre-adjudication claims.

    Usage:
        connection = EHRConnection.objects.get(id=connection_id)
        client = CernerFHIRClient(connection)
        claims = client.fetch_claims(since=datetime.now() - timedelta(days=1))
    """

    # Default Cerner scopes
    DEFAULT_SCOPES = "system/Claim.read system/Patient.read"

    # Rate limiting settings (Cerner typically allows 10 req/sec)
    RATE_LIMIT_DELAY = 0.1  # 100ms between requests
    MAX_REQUESTS_PER_MINUTE = 60

    # Pagination settings
    DEFAULT_PAGE_SIZE = 50  # Cerner default is often lower than Epic
    MAX_RESULTS = 10000

    def __init__(self, connection: EHRConnection):
        """
        Initialize Cerner FHIR client.

        Args:
            connection: EHRConnection model instance with Cerner credentials
        """
        if connection.ehr_type != "cerner":
            raise ValueError(f"Connection type must be 'cerner', got '{connection.ehr_type}'")

        super().__init__(
            connection_name=f"cerner_{connection.id}",
            failure_threshold=5,
            recovery_timeout=300,
            max_retries=3,
        )

        self.connection = connection
        self.fhir_endpoint = connection.fhir_endpoint.rstrip("/")

        # Initialize token manager
        self.token_manager = TokenManager(
            connection_id=connection.id,
            client_id=connection.client_id,
            client_secret=connection.client_secret,
            token_endpoint=connection.oauth_endpoint,
            scope=self.DEFAULT_SCOPES,
        )

        # FHIR parser for response handling
        self.parser = FHIRParser(customer_salt=str(connection.customer_id))

        # Rate limiting state
        self._last_request_time = 0.0
        self._request_count_this_minute = 0
        self._minute_start_time = time.time()

    def _apply_rate_limit(self):
        """Apply rate limiting between requests."""
        current_time = time.time()

        # Reset minute counter if needed
        if current_time - self._minute_start_time >= 60:
            self._request_count_this_minute = 0
            self._minute_start_time = current_time

        # Check if we've hit the per-minute limit
        if self._request_count_this_minute >= self.MAX_REQUESTS_PER_MINUTE:
            sleep_time = 60 - (current_time - self._minute_start_time)
            if sleep_time > 0:
                logger.info(
                    f"[{self.connection.name}] Rate limit reached, "
                    f"sleeping {sleep_time:.1f}s"
                )
                time.sleep(sleep_time)
                self._request_count_this_minute = 0
                self._minute_start_time = time.time()

        # Ensure minimum delay between requests
        time_since_last = current_time - self._last_request_time
        if time_since_last < self.RATE_LIMIT_DELAY:
            time.sleep(self.RATE_LIMIT_DELAY - time_since_last)

        self._last_request_time = time.time()
        self._request_count_this_minute += 1

    def get_token(self) -> str:
        """Get a valid OAuth 2.0 access token."""
        return self.token_manager.get_token()

    def _make_request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make authenticated FHIR API request with rate limiting.

        Args:
            method: HTTP method
            url: Full URL or path relative to FHIR endpoint
            params: Query parameters
            json_data: JSON body for POST requests

        Returns:
            Response JSON as dict
        """
        if not url.startswith("http"):
            url = urljoin(self.fhir_endpoint + "/", url.lstrip("/"))

        self._apply_rate_limit()

        token = self.get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/fhir+json",
            "Content-Type": "application/fhir+json",
        }

        def do_request():
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_data,
                timeout=30,
            )

            # Handle rate limiting responses
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                logger.warning(
                    f"[{self.connection.name}] Rate limited, "
                    f"waiting {retry_after}s"
                )
                time.sleep(retry_after)
                raise CernerFHIRError("Rate limited - retrying")

            if response.status_code == 401:
                self.token_manager.invalidate_token()
                raise CernerFHIRError("Unauthorized - token invalidated for retry")

            response.raise_for_status()
            return response.json()

        try:
            return self.execute_with_resilience(
                operation=do_request,
                operation_name=f"{method} {url}",
            )
        except CircuitBreakerOpen:
            raise CernerFHIRError(
                f"Circuit breaker open for connection {self.connection.name}"
            )
        except requests.exceptions.RequestException as e:
            raise CernerFHIRError(f"Request failed: {e}")

    def fetch_claims(
        self,
        since: Optional[datetime] = None,
        patient_id: Optional[str] = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Fetch Claim resources with pagination.

        Args:
            since: Only fetch claims updated since this datetime
            patient_id: Filter by patient ID (optional)
            page_size: Number of results per page

        Yields:
            Parsed claim data dicts compatible with ClaimRecord
        """
        params = {
            "_count": min(page_size, 50),
            "_sort": "-_lastUpdated",
        }

        if since:
            since_str = since.strftime("%Y-%m-%dT%H:%M:%SZ")
            params["_lastUpdated"] = f"ge{since_str}"

        if patient_id:
            params["patient"] = patient_id

        url = f"{self.fhir_endpoint}/Claim"
        total_fetched = 0

        while url and total_fetched < self.MAX_RESULTS:
            logger.info(f"[{self.connection.name}] Fetching claims from {url}")

            response = self._make_request(
                "GET", url,
                params=params if "?" not in url else None
            )

            # Process entries in bundle
            entries = response.get("entry", [])
            for entry in entries:
                resource = entry.get("resource", {})
                if resource.get("resourceType") == "Claim":
                    try:
                        # Handle Cerner-specific extensions
                        parsed = self._parse_cerner_claim(resource)
                        yield parsed
                        total_fetched += 1
                    except FHIRParseError as e:
                        logger.warning(
                            f"[{self.connection.name}] Failed to parse claim "
                            f"{resource.get('id')}: {e}"
                        )

            # Get next page URL
            url = self._get_next_page_url(response)
            params = None

        logger.info(f"[{self.connection.name}] Fetched {total_fetched} claims total")

    def _parse_cerner_claim(self, claim: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse Cerner Claim with extension handling.

        Args:
            claim: FHIR R4 Claim resource

        Returns:
            Dict with ClaimRecord-compatible fields
        """
        # Use base parser
        parsed = self.parser.parse_claim(claim)

        # Handle Cerner-specific extensions
        extensions = claim.get("extension", [])
        for ext in extensions:
            url = ext.get("url", "")

            # Cerner authorization number extension
            if "authorization" in url.lower():
                auth_ref = ext.get("valueReference", {})
                parsed["authorization_number"] = auth_ref.get("reference", "")

            # Cerner clinical notes reference
            if "clinical-notes" in url.lower():
                parsed["clinical_notes_reference"] = ext.get("valueReference", {}).get("reference")

        return parsed

    def _get_next_page_url(self, bundle: Dict[str, Any]) -> Optional[str]:
        """Extract next page URL from FHIR bundle links."""
        links = bundle.get("link", [])
        for link in links:
            if link.get("relation") == "next":
                return link.get("url")
        return None

    def test_connection(self) -> Dict[str, Any]:
        """
        Test the Cerner FHIR connection.

        Returns:
            Dict with connection test results
        """
        result = {
            "success": False,
            "token_status": None,
            "api_status": None,
            "error": None,
        }

        try:
            # Test token retrieval
            token = self.get_token()
            result["token_status"] = "success" if token else "failed"

            # Test API connectivity
            metadata = self._make_request("GET", "metadata")
            result["api_status"] = "success"
            result["fhir_version"] = metadata.get("fhirVersion", "unknown")
            result["success"] = True

        except TokenRefreshError as e:
            result["token_status"] = "failed"
            result["error"] = f"Token error: {e}"
        except CernerFHIRError as e:
            result["api_status"] = "failed"
            result["error"] = f"API error: {e}"
        except Exception as e:
            result["error"] = f"Unexpected error: {e}"

        return result

    def get_health_status(self) -> Dict[str, Any]:
        """Get health status for monitoring."""
        token_status = self.token_manager.get_token_status()

        return {
            "connection_id": self.connection.id,
            "connection_name": self.connection.name,
            "ehr_type": "cerner",
            "circuit_breaker_state": self.circuit_breaker.state,
            "circuit_breaker_failures": self.circuit_breaker.failure_count,
            "token_status": token_status,
            "last_poll": self.connection.last_poll,
            "enabled": self.connection.enabled,
        }


def create_cerner_client(connection_id: int) -> CernerFHIRClient:
    """
    Factory function to create Cerner client from connection ID.

    Args:
        connection_id: EHRConnection primary key

    Returns:
        CernerFHIRClient instance
    """
    connection = EHRConnection.objects.get(id=connection_id)
    return CernerFHIRClient(connection)


def poll_cerner_for_customer(connection: EHRConnection) -> EHRSyncLog:
    """
    Poll Cerner for new claims and create ClaimRecords.

    Args:
        connection: EHRConnection instance for Cerner

    Returns:
        EHRSyncLog with sync results
    """
    from upstream.models import ClaimRecord, Upload
    from django.db import transaction

    sync_log = EHRSyncLog.objects.create(
        connection=connection,
        status="success",
    )

    try:
        client = CernerFHIRClient(connection)

        since = connection.last_poll
        if not since:
            since = timezone.now() - timedelta(days=7)

        records_fetched = 0
        records_created = 0
        records_skipped = 0

        upload, _ = Upload.objects.get_or_create(
            customer=connection.customer,
            filename=f"ehr_cerner_{connection.id}_{timezone.now().strftime('%Y%m%d')}",
            defaults={
                "status": "success",
                "upload_source": "batch",
            }
        )

        with transaction.atomic():
            for claim_data in client.fetch_claims(since=since):
                records_fetched += 1

                existing = ClaimRecord.objects.filter(
                    customer=connection.customer,
                    source_data_hash=claim_data.get("source_data_hash"),
                ).first()

                if existing:
                    records_skipped += 1
                    continue

                try:
                    ClaimRecord.objects.create(
                        customer=connection.customer,
                        upload=upload,
                        payer=claim_data.get("payer", "Unknown"),
                        cpt=claim_data.get("cpt", ""),
                        submitted_date=claim_data.get("submitted_date"),
                        decided_date=claim_data.get("decided_date"),
                        outcome=claim_data.get("outcome", "OTHER"),
                        allowed_amount=claim_data.get("allowed_amount"),
                        billed_amount=claim_data.get("billed_amount"),
                        paid_amount=claim_data.get("paid_amount"),
                        modifier_codes=claim_data.get("modifier_codes", []),
                        diagnosis_codes=claim_data.get("diagnosis_codes", []),
                        procedure_count=claim_data.get("procedure_count", 1),
                        submitted_via="ehr_webhook",
                        source_data_hash=claim_data.get("source_data_hash"),
                    )
                    records_created += 1
                except Exception as e:
                    logger.warning(f"Failed to create ClaimRecord: {e}")
                    records_skipped += 1

        sync_log.completed_at = timezone.now()
        sync_log.records_fetched = records_fetched
        sync_log.records_created = records_created
        sync_log.records_skipped = records_skipped
        sync_log.save()

        connection.last_poll = timezone.now()
        connection.health_status = "healthy"
        connection.health_checked_at = timezone.now()
        connection.last_error = None
        connection.save()

        logger.info(
            f"[{connection.name}] Sync complete: fetched={records_fetched}, "
            f"created={records_created}, skipped={records_skipped}"
        )

    except Exception as e:
        sync_log.status = "error"
        sync_log.error_message = str(e)
        sync_log.completed_at = timezone.now()
        sync_log.save()

        connection.health_status = "unhealthy"
        connection.last_error = str(e)
        connection.health_checked_at = timezone.now()
        connection.save()

        logger.error(f"[{connection.name}] Sync failed: {e}")

    return sync_log
