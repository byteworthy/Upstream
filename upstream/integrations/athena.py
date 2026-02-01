"""
athenahealth Client for EHR Integration.

Provides client class for athenahealth REST API with:
- OAuth 2.0 authentication
- Claims endpoint integration
- athena-specific data format handling
- Mapping to standard ClaimRecord fields
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Generator
from decimal import Decimal
import hashlib
import requests
from django.utils import timezone

from upstream.integrations.models import EHRConnection, EHRSyncLog
from upstream.integrations.token_manager import TokenManager, TokenRefreshError
from upstream.integrations.resilience import (
    ResilientClient,
    CircuitBreakerOpen,
)

logger = logging.getLogger(__name__)


class AthenaError(Exception):
    """Exception raised for athenahealth API errors."""

    pass


class AthenaHealthClient(ResilientClient):
    """
    Client for athenahealth REST API.

    athenahealth uses a proprietary REST API format (not FHIR) for claims data.
    This client handles authentication and maps athena responses to ClaimRecord format.

    Usage:
        connection = EHRConnection.objects.get(id=connection_id)
        client = AthenaHealthClient(connection)
        claims = client.fetch_claims(since=datetime.now() - timedelta(days=1))
    """

    # Default athena scopes
    DEFAULT_SCOPES = "athena/service/Athenanet.Claims"

    # Pagination settings
    DEFAULT_PAGE_SIZE = 100
    MAX_RESULTS = 10000

    def __init__(self, connection: EHRConnection):
        """
        Initialize athenahealth client.

        Args:
            connection: EHRConnection model instance with athena credentials
        """
        if connection.ehr_type != "athena":
            raise ValueError(
                f"Connection type must be 'athena', got '{connection.ehr_type}'"
            )

        super().__init__(
            connection_name=f"athena_{connection.id}",
            failure_threshold=5,
            recovery_timeout=300,
            max_retries=3,
        )

        self.connection = connection
        self.api_endpoint = connection.fhir_endpoint.rstrip("/")
        self.customer_salt = str(connection.customer_id)

        # Get practice ID from configuration (JSON field, may not exist)
        configuration = getattr(connection, "configuration", None) or {}
        self.practice_id = configuration.get("practice_id", "")

        # Initialize token manager
        self.token_manager = TokenManager(
            connection_id=connection.id,
            client_id=connection.client_id,
            client_secret=connection.client_secret,
            token_endpoint=connection.oauth_endpoint,
            scope=self.DEFAULT_SCOPES,
        )

    def get_token(self) -> str:
        """Get a valid OAuth 2.0 access token."""
        return self.token_manager.get_token()

    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make authenticated athenahealth API request.

        Args:
            method: HTTP method
            endpoint: API endpoint path
            params: Query parameters
            json_data: JSON body for POST requests

        Returns:
            Response JSON as dict
        """
        url = f"{self.api_endpoint}/{self.practice_id}/{endpoint.lstrip('/')}"

        token = self.get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
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
                self.token_manager.invalidate_token()
                raise AthenaError("Unauthorized - token invalidated for retry")

            if response.status_code == 429:
                # athena rate limiting
                retry_after = int(response.headers.get("Retry-After", 60))
                logger.warning(
                    f"[{self.connection.name}] Rate limited, waiting {retry_after}s"
                )
                import time

                time.sleep(retry_after)
                raise AthenaError("Rate limited - retrying")

            response.raise_for_status()
            return response.json()

        try:
            return self.execute_with_resilience(
                operation=do_request,
                operation_name=f"{method} {endpoint}",
            )
        except CircuitBreakerOpen:
            raise AthenaError(
                f"Circuit breaker open for connection {self.connection.name}"
            )
        except requests.exceptions.RequestException as e:
            raise AthenaError(f"Request failed: {e}")

    def fetch_claims(
        self,
        since: Optional[datetime] = None,
        patient_id: Optional[str] = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Fetch claims from athenahealth /claims endpoint.

        Args:
            since: Only fetch claims created/modified since this datetime
            patient_id: Filter by patient ID (optional)
            page_size: Number of results per page

        Yields:
            Parsed claim data dicts compatible with ClaimRecord
        """
        params = {
            "limit": min(page_size, 100),
        }

        if since:
            # athena uses different date format
            params["servicedate"] = f">={since.strftime('%m/%d/%Y')}"

        if patient_id:
            params["patientid"] = patient_id

        offset = 0
        total_fetched = 0

        while total_fetched < self.MAX_RESULTS:
            params["offset"] = offset
            logger.info(f"[{self.connection.name}] Fetching claims, offset={offset}")

            try:
                response = self._make_request("GET", "claims", params=params)
            except AthenaError as e:
                logger.error(f"[{self.connection.name}] Failed to fetch claims: {e}")
                break

            claims = response.get("claims", response.get("data", []))
            if not claims:
                break

            for claim in claims:
                try:
                    parsed = self._parse_athena_claim(claim)
                    yield parsed
                    total_fetched += 1
                except Exception as e:
                    logger.warning(
                        f"[{self.connection.name}] Failed to parse claim "
                        f"{claim.get('claimid')}: {e}"
                    )

            # Check for more pages
            total_count = response.get("totalcount", 0)
            if offset + len(claims) >= total_count:
                break
            offset += len(claims)

        logger.info(f"[{self.connection.name}] Fetched {total_fetched} claims total")

    def _parse_athena_claim(self, claim: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse athenahealth claim into ClaimRecord format.

        athena claims have a different structure than FHIR resources.

        Args:
            claim: athenahealth claim object

        Returns:
            Dict with ClaimRecord-compatible fields
        """
        # Extract patient identifier and hash it
        patient_id = claim.get("patientid", "")
        patient_hash = hashlib.sha256(
            f"{self.customer_salt}:{patient_id}".encode()
        ).hexdigest()

        # Extract payer information
        payer = claim.get("primaryinsurancepackage", {}).get("name", "")
        if not payer:
            payer = claim.get("primarypayername", "Unknown")

        # Extract dates
        service_date = self._parse_athena_date(claim.get("servicedate"))
        filed_date = self._parse_athena_date(claim.get("fileddate"))
        adjudication_date = self._parse_athena_date(claim.get("adjudicationdate"))

        # Use filed_date as submitted, adjudication as decided
        submitted_date = filed_date or service_date or timezone.now().date()
        decided_date = adjudication_date or submitted_date

        # Extract amounts
        billed_amount = self._parse_amount(claim.get("chargeamount"))
        allowed_amount = self._parse_amount(claim.get("allowedamount"))
        paid_amount = self._parse_amount(claim.get("paidamount"))

        # Extract procedure codes
        procedures = claim.get("procedures", [])
        cpt_codes = []
        modifiers = []
        for proc in procedures:
            if proc.get("procedurecode"):
                cpt_codes.append(proc.get("procedurecode"))
            proc_mods = proc.get("modifiers", [])
            modifiers.extend(proc_mods)

        # Extract diagnosis codes
        diagnoses = claim.get("diagnoses", [])
        diagnosis_codes = [d.get("code") for d in diagnoses if d.get("code")]

        # Determine outcome
        claim_status = claim.get("claimstatus", "").lower()
        outcome = self._map_athena_status_to_outcome(claim_status)

        # Compute source hash for deduplication
        import json

        source_hash = hashlib.sha256(
            json.dumps(claim, sort_keys=True).encode()
        ).hexdigest()

        return {
            "source_id": claim.get("claimid", ""),
            "patient_mrn_hash": patient_hash,
            "payer": payer,
            "cpt": cpt_codes[0] if cpt_codes else "",
            "modifier_codes": list(set(modifiers)),
            "diagnosis_codes": list(set(diagnosis_codes)),
            "procedure_count": max(len(cpt_codes), 1),
            "submitted_date": submitted_date,
            "decided_date": decided_date,
            "payment_date": self._parse_athena_date(claim.get("paymentdate")),
            "outcome": outcome,
            "billed_amount": billed_amount,
            "allowed_amount": allowed_amount,
            "paid_amount": paid_amount,
            "submitted_via": "ehr_webhook",
            "source_data_hash": source_hash,
        }

    def _parse_athena_date(self, date_str: Optional[str]):
        """
        Parse athenahealth date format.

        athena typically uses MM/DD/YYYY format.
        """
        if not date_str:
            return None
        try:
            # Try MM/DD/YYYY first
            return datetime.strptime(date_str, "%m/%d/%Y").date()
        except ValueError:
            try:
                # Try YYYY-MM-DD
                return datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                logger.warning(f"Failed to parse athena date: {date_str}")
                return None

    def _parse_amount(self, amount: Any) -> Optional[Decimal]:
        """Parse amount to Decimal."""
        if amount is None:
            return None
        try:
            return Decimal(str(amount).replace(",", "").replace("$", ""))
        except Exception:
            return None

    def _map_athena_status_to_outcome(self, status: str) -> str:
        """Map athena claim status to ClaimRecord outcome."""
        status = status.lower()

        if status in ("paid", "processed", "complete", "finalized"):
            return "PAID"
        elif status in ("denied", "rejected", "void"):
            return "DENIED"
        else:
            return "OTHER"

    def test_connection(self) -> Dict[str, Any]:
        """Test the athenahealth connection."""
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

            # Test API connectivity - use practice endpoint
            practice_info = self._make_request("GET", "practiceinfo")
            result["api_status"] = "success"
            result["practice_name"] = practice_info.get("practicename", "")
            result["success"] = True

        except TokenRefreshError as e:
            result["token_status"] = "failed"
            result["error"] = f"Token error: {e}"
        except AthenaError as e:
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
            "ehr_type": "athena",
            "circuit_breaker_state": self.circuit_breaker.state,
            "circuit_breaker_failures": self.circuit_breaker.failure_count,
            "token_status": token_status,
            "last_poll": self.connection.last_poll,
            "enabled": self.connection.enabled,
        }


def create_athena_client(connection_id: int) -> AthenaHealthClient:
    """Factory function to create athena client from connection ID."""
    connection = EHRConnection.objects.get(id=connection_id)
    return AthenaHealthClient(connection)


def poll_athena_for_customer(connection: EHRConnection) -> EHRSyncLog:
    """
    Poll athenahealth for new claims and create ClaimRecords.

    Args:
        connection: EHRConnection instance for athena

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
        client = AthenaHealthClient(connection)

        since = connection.last_poll
        if not since:
            since = timezone.now() - timedelta(days=7)

        records_fetched = 0
        records_created = 0
        records_skipped = 0

        upload, _ = Upload.objects.get_or_create(
            customer=connection.customer,
            filename=f"ehr_athena_{connection.id}_{timezone.now().strftime('%Y%m%d')}",
            defaults={
                "status": "success",
                "upload_source": "batch",
            },
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
                        payment_date=claim_data.get("payment_date"),
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
