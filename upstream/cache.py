"""
Cache utilities for Upstream.

Provides easy-to-use caching decorators and functions for frequently accessed data.
Uses Redis for fast in-memory caching with configurable TTLs.
"""

from typing import Any, Callable, Dict, Optional, TypeVar
from django.core.cache import cache
from django.conf import settings
from functools import wraps
import hashlib
import json
import logging

logger = logging.getLogger(__name__)

# Type variable for generic return types
T = TypeVar('T')


def get_cache_key(prefix: str, *args: Any, **kwargs: Any) -> str:
    """
    Generate a deterministic cache key from arguments.

    Args:
        prefix: Cache key prefix (e.g., 'payer_mappings')
        *args: Positional arguments to include in key
        **kwargs: Keyword arguments to include in key

    Returns:
        str: Cache key like 'upstream:payer_mappings:customer_1'
    """
    # Start with prefix
    parts = [prefix]

    # Add positional args
    for arg in args:
        if hasattr(arg, 'pk'):
            # Django model instance - use pk
            parts.append(f"{arg.__class__.__name__}_{arg.pk}")
        else:
            parts.append(str(arg))

    # Add keyword args (sorted for consistency)
    for key in sorted(kwargs.keys()):
        value = kwargs[key]
        if hasattr(value, 'pk'):
            parts.append(f"{key}_{value.__class__.__name__}_{value.pk}")
        else:
            parts.append(f"{key}_{value}")

    # Join parts
    cache_key = ':'.join(parts)

    # Hash if too long (Redis key limit is 512MB but shorter is better)
    if len(cache_key) > 200:
        hash_suffix = hashlib.sha256(cache_key.encode()).hexdigest()[:16]
        cache_key = f"{prefix}:{hash_suffix}"

    return cache_key


def cache_result(cache_key_prefix: str, ttl: Optional[int] = None) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to cache function results.

    Usage:
        @cache_result('payer_mappings', ttl=900)
        def get_payer_mappings(customer):
            return PayerMapping.objects.filter(customer=customer)

    Args:
        cache_key_prefix: Prefix for cache key
        ttl: Time to live in seconds (uses CACHE_TTL config if not specified)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            # Generate cache key from function args
            cache_key = get_cache_key(cache_key_prefix, *args, **kwargs)

            # Try to get from cache
            result = cache.get(cache_key)

            if result is not None:
                logger.debug(f"Cache HIT: {cache_key}")
                return result

            # Cache miss - call function
            logger.debug(f"Cache MISS: {cache_key}")
            result = func(*args, **kwargs)

            # Determine TTL
            timeout = ttl
            if timeout is None:
                # Use configured TTL if available
                cache_ttl_config = getattr(settings, 'CACHE_TTL', {})
                timeout = cache_ttl_config.get(cache_key_prefix, 300)  # Default 5 minutes

            # Store in cache
            cache.set(cache_key, result, timeout)
            logger.debug(f"Cache SET: {cache_key} (TTL={timeout}s)")

            return result

        return wrapper
    return decorator


def invalidate_cache(cache_key_prefix: str, *args: Any, **kwargs: Any) -> None:
    """
    Invalidate a specific cache entry.

    Usage:
        invalidate_cache('payer_mappings', customer)

    Args:
        cache_key_prefix: Prefix for cache key
        *args: Positional arguments used to generate key
        **kwargs: Keyword arguments used to generate key
    """
    cache_key = get_cache_key(cache_key_prefix, *args, **kwargs)
    cache.delete(cache_key)
    logger.info(f"Cache INVALIDATED: {cache_key}")


def invalidate_cache_pattern(pattern: str) -> int:
    """
    Invalidate all cache entries matching a pattern.

    Note: This requires Redis and uses SCAN to avoid blocking.

    Usage:
        invalidate_cache_pattern('payer_mappings:*')

    Args:
        pattern: Pattern to match (supports * wildcard)

    Returns:
        int: Number of keys deleted
    """
    try:
        # Get Redis client from cache backend
        redis_client = cache._cache.get_client()

        # Use SCAN to iterate through keys (non-blocking)
        cursor = 0
        deleted_count = 0

        while True:
            cursor, keys = redis_client.scan(
                cursor=cursor,
                match=f"upstream:{pattern}",
                count=100
            )

            if keys:
                # Delete keys
                redis_client.delete(*keys)
                deleted_count += len(keys)

            # SCAN returns 0 when iteration is complete
            if cursor == 0:
                break

        logger.info(f"Cache PATTERN INVALIDATED: {pattern} ({deleted_count} keys deleted)")
        return deleted_count

    except Exception as e:
        logger.error(f"Error invalidating cache pattern '{pattern}': {str(e)}")
        return 0


def get_or_set_cache(cache_key: str, callable_func: Callable[[], T], timeout: int = 300) -> T:
    """
    Get from cache or set if not exists.

    Usage:
        mappings = get_or_set_cache(
            'payer_mappings:customer_1',
            lambda: PayerMapping.objects.filter(customer=customer),
            timeout=900
        )

    Args:
        cache_key: Cache key
        callable_func: Function to call if cache miss
        timeout: TTL in seconds

    Returns:
        Cached or computed value
    """
    result = cache.get(cache_key)

    if result is not None:
        logger.debug(f"Cache HIT: {cache_key}")
        return result

    logger.debug(f"Cache MISS: {cache_key}")
    result = callable_func()
    cache.set(cache_key, result, timeout)
    logger.debug(f"Cache SET: {cache_key} (TTL={timeout}s)")

    return result


def warm_cache(cache_key: str, value: Any, timeout: int = 300) -> None:
    """
    Proactively warm the cache with a value.

    Usage:
        warm_cache('payer_mappings:customer_1', mappings, timeout=900)

    Args:
        cache_key: Cache key
        value: Value to cache
        timeout: TTL in seconds
    """
    cache.set(cache_key, value, timeout)
    logger.info(f"Cache WARMED: {cache_key} (TTL={timeout}s)")


def get_cache_stats() -> Dict[str, Any]:
    """
    Get cache statistics (if Redis supports INFO command).

    Returns:
        dict: Cache statistics including hits, misses, hit rate, memory usage
    """
    try:
        redis_client = cache._cache.get_client()
        info = redis_client.info('stats')

        return {
            'total_commands': info.get('total_commands_processed', 0),
            'keyspace_hits': info.get('keyspace_hits', 0),
            'keyspace_misses': info.get('keyspace_misses', 0),
            'hit_rate': (
                info.get('keyspace_hits', 0) /
                max(info.get('keyspace_hits', 0) + info.get('keyspace_misses', 0), 1)
            ) * 100,
            'connected_clients': info.get('connected_clients', 0),
            'used_memory_human': redis_client.info('memory').get('used_memory_human', '0'),
        }
    except Exception as e:
        logger.error(f"Error getting cache stats: {str(e)}")
        return {}


# Cache key prefixes (for consistency)
CACHE_KEYS = {
    'PAYER_MAPPINGS': 'payer_mappings',
    'CPT_MAPPINGS': 'cpt_mappings',
    'DRIFT_EVENTS': 'drift_events',
    'ALERT_EVENTS': 'alert_events',
    'REPORT_RUNS': 'report_runs',
    'QUALITY_REPORTS': 'quality_reports',
    'USER_PROFILE': 'user_profile',
}
