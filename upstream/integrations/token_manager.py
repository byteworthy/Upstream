"""
OAuth 2.0 Token Manager for EHR integrations.

Handles token caching in Redis with expiration and automatic refresh
before tokens expire. Thread-safe access for concurrent requests.
"""

import logging
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import requests
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class TokenRefreshError(Exception):
    """Exception raised when token refresh fails."""

    pass


class TokenManager:
    """
    Manages OAuth 2.0 tokens with caching and automatic refresh.

    Features:
    - Tokens cached in Redis with expiration
    - Refresh triggered 1 minute before expiration
    - Retry with exponential backoff on failure
    - Thread-safe token access
    - Token refresh logged for audit
    """

    # Default token lifetime buffer (refresh 1 minute before expiry)
    REFRESH_BUFFER_SECONDS = 60

    def __init__(
        self,
        connection_id: int,
        client_id: str,
        client_secret: str,
        token_endpoint: str,
        scope: str = "",
    ):
        """
        Initialize token manager.

        Args:
            connection_id: EHRConnection ID for cache key namespacing
            client_id: OAuth 2.0 client ID
            client_secret: OAuth 2.0 client secret
            token_endpoint: OAuth 2.0 token endpoint URL
            scope: OAuth 2.0 scope (optional)
        """
        self.connection_id = connection_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_endpoint = token_endpoint
        self.scope = scope
        self._lock = threading.RLock()

        # Cache key prefix
        self._cache_prefix = f"ehr_token:{connection_id}"

    @property
    def _token_key(self) -> str:
        """Cache key for access token."""
        return f"{self._cache_prefix}:access_token"

    @property
    def _expires_key(self) -> str:
        """Cache key for token expiration time."""
        return f"{self._cache_prefix}:expires_at"

    @property
    def _refresh_token_key(self) -> str:
        """Cache key for refresh token."""
        return f"{self._cache_prefix}:refresh_token"

    def get_token(self) -> str:
        """
        Get a valid access token, refreshing if needed.

        Thread-safe method that returns a valid access token.
        Triggers refresh if token is expired or about to expire.

        Returns:
            Valid access token string

        Raises:
            TokenRefreshError: If token cannot be obtained or refreshed
        """
        with self._lock:
            # Check if we have a valid cached token
            access_token = cache.get(self._token_key)
            expires_at = cache.get(self._expires_key)

            if access_token and expires_at:
                # Check if token needs refresh (1 minute buffer)
                time_until_expiry = (expires_at - timezone.now()).total_seconds()
                if time_until_expiry > self.REFRESH_BUFFER_SECONDS:
                    logger.debug(
                        f"[Connection {self.connection_id}] Using cached token, "
                        f"expires in {time_until_expiry:.0f}s"
                    )
                    return access_token
                else:
                    logger.info(
                        f"[Connection {self.connection_id}] Token expiring soon, "
                        f"triggering refresh"
                    )

            # Need to fetch a new token
            return self._refresh_token()

    def _refresh_token(self) -> str:
        """
        Refresh the access token using client credentials flow.

        Implements retry with exponential backoff (3 attempts).

        Returns:
            New access token

        Raises:
            TokenRefreshError: If all retry attempts fail
        """
        max_retries = 3
        base_delay = 1.0

        last_error = None
        for attempt in range(max_retries):
            try:
                return self._request_token()
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)
                    logger.warning(
                        f"[Connection {self.connection_id}] Token refresh attempt "
                        f"{attempt + 1}/{max_retries} failed, retrying in {delay}s: {e}"
                    )
                    import time

                    time.sleep(delay)
                else:
                    logger.error(
                        f"[Connection {self.connection_id}] All token refresh "
                        f"attempts failed: {e}"
                    )

        raise TokenRefreshError(
            f"Failed to refresh token after {max_retries} attempts: {last_error}"
        )

    def _request_token(self) -> str:
        """
        Make the actual token request to the OAuth endpoint.

        Returns:
            Access token string

        Raises:
            TokenRefreshError: If request fails or response is invalid
        """
        logger.info(
            f"[Connection {self.connection_id}] Requesting new OAuth token from "
            f"{self.token_endpoint}"
        )

        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        if self.scope:
            data["scope"] = self.scope

        try:
            response = requests.post(
                self.token_endpoint,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30,
            )
            response.raise_for_status()
            token_data = response.json()
        except requests.exceptions.RequestException as e:
            raise TokenRefreshError(f"Token request failed: {e}")
        except ValueError as e:
            raise TokenRefreshError(f"Invalid token response JSON: {e}")

        # Extract token data
        access_token = token_data.get("access_token")
        if not access_token:
            raise TokenRefreshError("No access_token in response")

        # Calculate expiration time
        expires_in = token_data.get("expires_in", 3600)  # Default 1 hour
        expires_at = timezone.now() + timedelta(seconds=expires_in)

        # Cache the token with proper TTL
        cache_ttl = max(expires_in - self.REFRESH_BUFFER_SECONDS, 60)
        cache.set(self._token_key, access_token, timeout=cache_ttl)
        cache.set(self._expires_key, expires_at, timeout=cache_ttl + 120)

        # Store refresh token if provided
        refresh_token = token_data.get("refresh_token")
        if refresh_token:
            cache.set(self._refresh_token_key, refresh_token, timeout=86400)

        # Log for audit
        logger.info(
            f"[Connection {self.connection_id}] OAuth token refreshed successfully, "
            f"expires at {expires_at.isoformat()}"
        )

        # Update connection's last_token_refresh timestamp
        self._update_connection_timestamp()

        return access_token

    def _update_connection_timestamp(self):
        """Update the EHRConnection's last token refresh timestamp."""
        try:
            from upstream.integrations.models import EHRConnection

            EHRConnection.objects.filter(id=self.connection_id).update(
                updated_at=timezone.now()
            )
        except Exception as e:
            logger.warning(
                f"[Connection {self.connection_id}] Failed to update "
                f"connection timestamp: {e}"
            )

    def invalidate_token(self):
        """Invalidate cached token, forcing a refresh on next get_token() call."""
        cache.delete(self._token_key)
        cache.delete(self._expires_key)
        logger.info(f"[Connection {self.connection_id}] Token cache invalidated")

    def get_token_status(self) -> Dict[str, Any]:
        """
        Get current token status for health checks.

        Returns:
            Dict with token status information
        """
        access_token = cache.get(self._token_key)
        expires_at = cache.get(self._expires_key)

        if not access_token:
            return {
                "has_token": False,
                "expires_at": None,
                "time_until_expiry": None,
                "needs_refresh": True,
            }

        time_until_expiry = None
        if expires_at:
            time_until_expiry = (expires_at - timezone.now()).total_seconds()

        return {
            "has_token": True,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "time_until_expiry": time_until_expiry,
            "needs_refresh": (
                time_until_expiry is not None
                and time_until_expiry < self.REFRESH_BUFFER_SECONDS
            ),
        }
