"""
Custom throttle classes for API rate limiting.

QW-5: Enhanced rate limiting for different operation types.
"""

from rest_framework.throttling import UserRateThrottle, AnonRateThrottle


class BurstRateThrottle(UserRateThrottle):
    """
    Throttle for high-frequency bursts of requests.
    Allows short bursts but prevents sustained high load.
    """

    scope = "burst"


class SustainedRateThrottle(UserRateThrottle):
    """
    Throttle for sustained request rates over longer periods.
    Prevents resource exhaustion from sustained high usage.
    """

    scope = "sustained"


class ReportGenerationThrottle(UserRateThrottle):
    """
    Strict throttle for expensive report generation operations.
    Reports are CPU/memory intensive and should be rate-limited aggressively.
    """

    scope = "report_generation"


class BulkOperationThrottle(UserRateThrottle):
    """
    Throttle for bulk operations like file uploads and batch processing.
    These operations are I/O intensive and should be rate-limited.
    """

    scope = "bulk_operation"


class ReadOnlyThrottle(UserRateThrottle):
    """
    Liberal throttle for read-only operations.
    Allows high read rates but still prevents abuse.
    """

    scope = "read_only"


class WriteOperationThrottle(UserRateThrottle):
    """
    Moderate throttle for write operations.
    More restrictive than reads but less than expensive operations.
    """

    scope = "write_operation"


class AnonStrictThrottle(AnonRateThrottle):
    """
    Very strict throttle for anonymous users.
    Prevents abuse while allowing limited public access.
    """

    scope = "anon_strict"


class AuthenticationThrottle(AnonRateThrottle):
    """
    Strict throttle for authentication endpoints (HIGH-2).
    Prevents brute-force password attacks by limiting login attempts.
    5 attempts per 15 minutes provides security without impacting legitimate users.
    """

    scope = "authentication"
