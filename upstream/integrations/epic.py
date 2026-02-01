"""
Epic FHIR R4 Client for EHR Integration.

Provides client class for Epic FHIR R4 API with:
- OAuth 2.0 client credentials authentication
- Token management with automatic refresh
- ExplanationOfBenefit resource fetching
- Pagination handling for large result sets
- Resilience patterns (retry, circuit breaker)
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Generator
from urllib.parse import urljoin, urlencode
import requests
from django.utils import timezone

from upstream.integrations.models import EHRConnection, EHRSyncLog
from upstream.integrations.token_manager import TokenManager, TokenRefreshError
from upstream.integrations.fhir_parser import FHIRParser, FHIRParseError
from upstream.integrations.resilience import (
    ResilientClient,
    CircuitBreakerOpen,
    get_circuit_breaker,
)

logger = logging.getLogger(__name__)


class EpicFHIRError(Exception):
    """Exception raised for Epic FHIR API errors."""
    pass


class EpicFHIRClient(ResilientClient):
    """
    Client for Epic FHIR R4 API.

    Handles OAuth 2.0 authentication, token refresh, and FHIR resource fetching
    with built-in resilience patterns.

    Usage:
        connection = EHRConnection.objects.get(id=connection_id)
        client = EpicFHIRClient(connection)
        eobs = client.fetch_eobs(since=datetime.now() - timedelta(days=1))
    """

    # Default Epic scopes for EOB access
    DEFAULT_SCOPES = "system/ExplanationOfBenefit.read system/Patient.read"

    # Pagination settings
    DEFAULT_PAGE_SIZE = 100
    MAX_RESULTS = 10000  # Safety limit

    def __init__(self, connection: EHRConnection):
        """
        Initialize Epic FHIR client.

        Args:
            connection: EHRConnection model instance with Epic credentials
        """
        if connection.ehr_type != "epic":
            raise ValueError(f"Connection type must be 'epic', got '{connection.ehr_type}'")

        super().__init__(
            connection_name=f"epic_{connection.id}",
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

    def get_token(self) -> str:
        """
        Get a valid OAuth 2.0 access token.

        Returns:
            Valid access token string

        Raises:
            TokenRefreshError: If token cannot be obtained
        """
        return self.token_manager.get_token()

    def _make_request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make authenticated FHIR API request.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full URL or path relative to FHIR endpoint
            params: Query parameters
            json_data: JSON body for POST requests

        Returns:
            Response JSON as dict

        Raises:
            EpicFHIRError: If request fails
        """
        if not url.startswith("http"):
            url = urljoin(self.fhir_endpoint + "/", url.lstrip("/"))

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
            if response.status_code == 401:
                # Token may have expired, invalidate and retry
                self.token_manager.invalidate_token()
                raise EpicFHIRError("Unauthorized - token invalidated for retry")
            response.raise_for_status()
            return response.json()

        try:
            return self.execute_with_resilience(
                operation=do_request,
                operation_name=f"{method} {url}",
            )
        except CircuitBreakerOpen:
            raise EpicFHIRError(
                f"Circuit breaker open for connection {self.connection.name}"
            )
        except requests.exceptions.RequestException as e:
            raise EpicFHIRError(f"Request failed: {e}")

    def fetch_eobs(
        self,
        since: Optional[datetime] = None,
        patient_id: Optional[str] = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Fetch ExplanationOfBenefit resources with pagination.

        Args:
            since: Only fetch EOBs updated since this datetime
            patient_id: Filter by patient ID (optional)
            page_size: Number of results per page

        Yields:
            Parsed EOB data dicts compatible with ClaimRecord

        Raises:
            EpicFHIRError: If API request fails
        """
        params = {
            "_count": min(page_size, 100),  # Epic max is usually 100
            "_sort": "-_lastUpdated",
        }

        if since:
            # Format as FHIR instant
            since_str = since.strftime("%Y-%m-%dT%H:%M:%SZ")
            params["_lastUpdated"] = f"ge{since_str}"

        if patient_id:
            params["patient"] = patient_id

        url = f"{self.fhir_endpoint}/ExplanationOfBenefit"
        total_fetched = 0

        while url and total_fetched < self.MAX_RESULTS:
            logger.info(f"[{self.connection.name}] Fetching EOBs from {url}")

            response = self._make_request("GET", url, params=params if "?" not in url else None)

            # Process entries in bundle
            entries = response.get("entry", [])
            for entry in entries:
                resource = entry.get("resource", {})
                if resource.get("resourceType") == "ExplanationOfBenefit":
                    try:
                        parsed = self.parser.parse_eob(resource)
                        yield parsed
                        total_fetched += 1
                    except FHIRParseError as e:
                        logger.warning(
                            f"[{self.connection.name}] Failed to parse EOB "
                            f"{resource.get('id')}: {e}"
                        )

            # Get next page URL from bundle links
            url = self._get_next_page_url(response)
            params = None  # Params are included in next URL

        logger.info(f"[{self.connection.name}] Fetched {total_fetched} EOBs total")

    def fetch_eobs_batch(
        self,
        since: Optional[datetime] = None,
        patient_id: Optional[str] = None,
        max_results: int = 1000,
    ) -> List[Dict[str, Any]]:
        """
        Fetch EOBs and return as list (convenience method).

        Args:
            since: Only fetch EOBs updated since this datetime
            patient_id: Filter by patient ID (optional)
            max_results: Maximum results to return

        Returns:
            List of parsed EOB data dicts
        """
        results = []
        for eob in self.fetch_eobs(since=since, patient_id=patient_id):
            results.append(eob)
            if len(results) >= max_results:
                break
        return results

    def _get_next_page_url(self, bundle: Dict[str, Any]) -> Optional[str]:
        """Extract next page URL from FHIR bundle links."""
        links = bundle.get("link", [])
        for link in links:
            if link.get("relation") == "next":
                return link.get("url")
        return None

    def test_connection(self) -> Dict[str, Any]:
        """
        Test the Epic FHIR connection.

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

            # Test API connectivity with metadata endpoint
            metadata = self._make_request("GET", "metadata")
            result["api_status"] = "success"
            result["fhir_version"] = metadata.get("fhirVersion", "unknown")
            result["success"] = True

        except TokenRefreshError as e:
            result["token_status"] = "failed"
            result["error"] = f"Token error: {e}"
        except EpicFHIRError as e:
            result["api_status"] = "failed"
            result["error"] = f"API error: {e}"
        except Exception as e:
            result["error"] = f"Unexpected error: {e}"

        return result

    def get_health_status(self) -> Dict[str, Any]:
        """
        Get health status for monitoring.

        Returns:
            Dict with health status information
        """
        token_status = self.token_manager.get_token_status()

        return {
            "connection_id": self.connection.id,
            "connection_name": self.connection.name,
            "ehr_type": "epic",
            "circuit_breaker_state": self.circuit_breaker.state,
            "circuit_breaker_failures": self.circuit_breaker.failure_count,
            "token_status": token_status,
            "last_poll": self.connection.last_poll,
            "enabled": self.connection.enabled,
        }


def create_epic_client(connection_id: int) -> EpicFHIRClient:
    """
    Factory function to create Epic client from connection ID.

    Args:
        connection_id: EHRConnection primary key

    Returns:
        EpicFHIRClient instance

    Raises:
        EHRConnection.DoesNotExist: If connection not found
        ValueError: If connection is not Epic type
    """
    connection = EHRConnection.objects.get(id=connection_id)
    return EpicFHIRClient(connection)


def poll_epic_for_customer(connection: EHRConnection) -> EHRSyncLog:
    """
    Poll Epic for new claims and create ClaimRecords.

    Args:
        connection: EHRConnection instance for Epic

    Returns:
        EHRSyncLog with sync results
    """
    from upstream.models import ClaimRecord, Upload, Customer
    from django.db import transaction

    # Create sync log
    sync_log = EHRSyncLog.objects.create(
        connection=connection,
        status="success",
    )

    try:
        client = EpicFHIRClient(connection)

        # Determine since timestamp
        since = connection.last_poll
        if not since:
            since = timezone.now() - timedelta(days=7)  # Default to last 7 days

        # Fetch EOBs
        records_fetched = 0
        records_created = 0
        records_updated = 0
        records_skipped = 0

        # Get or create upload record for EHR data
        upload, _ = Upload.objects.get_or_create(
            customer=connection.customer,
            filename=f"ehr_epic_{connection.id}_{timezone.now().strftime('%Y%m%d')}",
            defaults={
                "status": "success",
                "upload_source": "batch",
            }
        )

        with transaction.atomic():
            for eob_data in client.fetch_eobs(since=since):
                records_fetched += 1

                # Check for existing record by source hash
                existing = ClaimRecord.objects.filter(
                    customer=connection.customer,
                    source_data_hash=eob_data.get("source_data_hash"),
                ).first()

                if existing:
                    records_skipped += 1
                    continue

                # Create new ClaimRecord
                try:
                    ClaimRecord.objects.create(
                        customer=connection.customer,
                        upload=upload,
                        payer=eob_data.get("payer", "Unknown"),
                        cpt=eob_data.get("cpt", ""),
                        submitted_date=eob_data.get("submitted_date"),
                        decided_date=eob_data.get("decided_date"),
                        outcome=eob_data.get("outcome", "OTHER"),
                        allowed_amount=eob_data.get("allowed_amount"),
                        billed_amount=eob_data.get("billed_amount"),
                        paid_amount=eob_data.get("paid_amount"),
                        payment_date=eob_data.get("payment_date"),
                        modifier_codes=eob_data.get("modifier_codes", []),
                        diagnosis_codes=eob_data.get("diagnosis_codes", []),
                        procedure_count=eob_data.get("procedure_count", 1),
                        submitted_via="ehr_webhook",
                        source_data_hash=eob_data.get("source_data_hash"),
                    )
                    records_created += 1
                except Exception as e:
                    logger.warning(f"Failed to create ClaimRecord: {e}")
                    records_skipped += 1

        # Update sync log
        sync_log.completed_at = timezone.now()
        sync_log.records_fetched = records_fetched
        sync_log.records_created = records_created
        sync_log.records_updated = records_updated
        sync_log.records_skipped = records_skipped
        sync_log.save()

        # Update connection last poll time
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
