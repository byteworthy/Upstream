"""
Resilience patterns for EHR API calls.

Implements retry logic with exponential backoff and circuit breakers
to prevent cascade failures when EHR systems are unavailable.
"""

import time
import threading
import logging
from datetime import datetime, timedelta
from functools import wraps
from typing import Callable, TypeVar, Optional, Any
from django.core.cache import cache

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitBreakerOpen(Exception):
    """Exception raised when circuit breaker is open."""
    pass


class CircuitBreaker:
    """
    Circuit breaker implementation for EHR API calls.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Failure threshold exceeded, requests blocked
    - HALF_OPEN: Testing if service recovered

    Configuration:
    - Opens after 5 consecutive failures
    - Half-open test after 5 minutes
    - Tracks failure counts per connection
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 300,  # 5 minutes
        half_open_max_calls: int = 3,
    ):
        """
        Initialize circuit breaker.

        Args:
            name: Unique identifier for this circuit breaker
            failure_threshold: Number of consecutive failures before opening
            recovery_timeout: Seconds to wait before half-open test
            half_open_max_calls: Max test calls in half-open state
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self._lock = threading.RLock()

        # State keys for cache
        self._state_key = f"circuit_breaker:{name}:state"
        self._failure_count_key = f"circuit_breaker:{name}:failures"
        self._last_failure_key = f"circuit_breaker:{name}:last_failure"
        self._half_open_calls_key = f"circuit_breaker:{name}:half_open_calls"

    @property
    def state(self) -> str:
        """Get current circuit breaker state."""
        state = cache.get(self._state_key)
        if state is None:
            return self.CLOSED
        return state

    @state.setter
    def state(self, value: str):
        """Set circuit breaker state."""
        cache.set(self._state_key, value, timeout=86400)  # 24 hours

    @property
    def failure_count(self) -> int:
        """Get current failure count."""
        count = cache.get(self._failure_count_key)
        return count if count is not None else 0

    @failure_count.setter
    def failure_count(self, value: int):
        """Set failure count."""
        cache.set(self._failure_count_key, value, timeout=86400)

    @property
    def last_failure_time(self) -> Optional[datetime]:
        """Get time of last failure."""
        return cache.get(self._last_failure_key)

    @last_failure_time.setter
    def last_failure_time(self, value: datetime):
        """Set last failure time."""
        cache.set(self._last_failure_key, value, timeout=86400)

    @property
    def half_open_calls(self) -> int:
        """Get number of calls in half-open state."""
        count = cache.get(self._half_open_calls_key)
        return count if count is not None else 0

    @half_open_calls.setter
    def half_open_calls(self, value: int):
        """Set half-open call count."""
        cache.set(self._half_open_calls_key, value, timeout=86400)

    def can_execute(self) -> bool:
        """Check if request can proceed through circuit breaker."""
        with self._lock:
            current_state = self.state

            if current_state == self.CLOSED:
                return True

            if current_state == self.OPEN:
                # Check if recovery timeout has passed
                last_failure = self.last_failure_time
                if last_failure is not None:
                    elapsed = (datetime.now() - last_failure).total_seconds()
                    if elapsed >= self.recovery_timeout:
                        # Transition to half-open
                        self.state = self.HALF_OPEN
                        self.half_open_calls = 0
                        logger.info(
                            f"Circuit breaker '{self.name}' transitioning to HALF_OPEN"
                        )
                        return True
                return False

            if current_state == self.HALF_OPEN:
                # Allow limited calls in half-open state
                if self.half_open_calls < self.half_open_max_calls:
                    return True
                return False

            return False

    def record_success(self):
        """Record a successful call."""
        with self._lock:
            if self.state == self.HALF_OPEN:
                self.half_open_calls += 1
                if self.half_open_calls >= self.half_open_max_calls:
                    # All test calls succeeded, close circuit
                    self.state = self.CLOSED
                    self.failure_count = 0
                    logger.info(
                        f"Circuit breaker '{self.name}' closed after successful recovery"
                    )
            else:
                # Reset failure count on success
                self.failure_count = 0

    def record_failure(self, error: Optional[Exception] = None):
        """Record a failed call."""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = datetime.now()

            if self.state == self.HALF_OPEN:
                # Failure in half-open, reopen circuit
                self.state = self.OPEN
                logger.warning(
                    f"Circuit breaker '{self.name}' reopened after failure in HALF_OPEN: {error}"
                )
            elif self.failure_count >= self.failure_threshold:
                # Threshold exceeded, open circuit
                self.state = self.OPEN
                logger.warning(
                    f"Circuit breaker '{self.name}' opened after {self.failure_count} failures"
                )

    def reset(self):
        """Reset circuit breaker to closed state."""
        with self._lock:
            self.state = self.CLOSED
            self.failure_count = 0
            self.half_open_calls = 0
            cache.delete(self._last_failure_key)
            logger.info(f"Circuit breaker '{self.name}' reset to CLOSED")


def with_circuit_breaker(
    circuit_breaker: CircuitBreaker,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to apply circuit breaker pattern to a function.

    Args:
        circuit_breaker: CircuitBreaker instance to use

    Raises:
        CircuitBreakerOpen: If circuit is open and request blocked
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            if not circuit_breaker.can_execute():
                raise CircuitBreakerOpen(
                    f"Circuit breaker '{circuit_breaker.name}' is open"
                )
            try:
                result = func(*args, **kwargs)
                circuit_breaker.record_success()
                return result
            except Exception as e:
                circuit_breaker.record_failure(e)
                raise
        return wrapper
    return decorator


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    retryable_exceptions: tuple = (Exception,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for retry with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff calculation
        retryable_exceptions: Tuple of exception types to retry on

    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = min(
                            base_delay * (exponential_base ** attempt),
                            max_delay
                        )
                        logger.warning(
                            f"Retry {attempt + 1}/{max_retries} for {func.__name__} "
                            f"after {delay:.2f}s delay: {e}"
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"All {max_retries} retries exhausted for {func.__name__}: {e}"
                        )
            raise last_exception
        return wrapper
    return decorator


class ResilientClient:
    """
    Base class for resilient EHR API clients.

    Provides:
    - Automatic retry with exponential backoff
    - Circuit breaker protection
    - Logging for audit trail
    """

    def __init__(
        self,
        connection_name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 300,
        max_retries: int = 3,
    ):
        """
        Initialize resilient client.

        Args:
            connection_name: Name for circuit breaker identification
            failure_threshold: Failures before circuit opens
            recovery_timeout: Seconds before half-open test
            max_retries: Maximum retry attempts
        """
        self.connection_name = connection_name
        self.max_retries = max_retries
        self.circuit_breaker = CircuitBreaker(
            name=connection_name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
        )

    def execute_with_resilience(
        self,
        operation: Callable[[], T],
        operation_name: str = "operation",
    ) -> T:
        """
        Execute an operation with retry and circuit breaker protection.

        Args:
            operation: Callable to execute
            operation_name: Name for logging

        Returns:
            Result of the operation

        Raises:
            CircuitBreakerOpen: If circuit breaker is open
            Exception: If all retries exhausted
        """
        if not self.circuit_breaker.can_execute():
            raise CircuitBreakerOpen(
                f"Circuit breaker '{self.connection_name}' is open"
            )

        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                result = operation()
                self.circuit_breaker.record_success()
                return result
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries:
                    delay = min(1.0 * (2 ** attempt), 60.0)
                    logger.warning(
                        f"[{self.connection_name}] Retry {attempt + 1}/{self.max_retries} "
                        f"for {operation_name} after {delay:.2f}s: {e}"
                    )
                    time.sleep(delay)
                else:
                    self.circuit_breaker.record_failure(e)
                    logger.error(
                        f"[{self.connection_name}] All retries exhausted for "
                        f"{operation_name}: {e}"
                    )

        raise last_exception


def get_circuit_breaker(connection_id: int) -> CircuitBreaker:
    """
    Get or create circuit breaker for an EHR connection.

    Args:
        connection_id: EHRConnection primary key

    Returns:
        CircuitBreaker instance for the connection
    """
    return CircuitBreaker(name=f"ehr_connection_{connection_id}")
