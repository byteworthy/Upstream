"""
Feature flag service for checking flag status.

Usage:
    from upstream.feature_flags import is_feature_enabled

    if is_feature_enabled("new_dashboard", user=request.user):
        # Show new dashboard
    else:
        # Show old dashboard
"""

import hashlib
import logging
from typing import Optional
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

CACHE_TIMEOUT = 60  # Cache flag values for 60 seconds


def get_environment() -> str:
    """Get the current environment name."""
    return getattr(settings, "ENVIRONMENT", "development")


def get_feature_flag(flag_name: str):
    """
    Get a feature flag by name.

    Returns None if flag doesn't exist.
    """
    # Import here to avoid circular imports
    from upstream.feature_flags.models import FeatureFlag

    cache_key = f"feature_flag:{flag_name}"
    flag = cache.get(cache_key)

    if flag is None:
        try:
            flag = FeatureFlag.objects.get(name=flag_name)
            cache.set(cache_key, flag, CACHE_TIMEOUT)
        except FeatureFlag.DoesNotExist:
            return None

    return flag


def _get_rollout_bucket(flag_name: str, identifier: str) -> int:
    """
    Get a consistent bucket (0-99) for a flag/identifier combination.

    Uses MD5 hashing to ensure consistent results across requests.
    """
    hash_input = f"{flag_name}:{identifier}"
    hash_value = hashlib.md5(hash_input.encode()).hexdigest()
    # Use first 8 hex chars as integer, mod 100 for bucket
    return int(hash_value[:8], 16) % 100


def is_feature_enabled(
    flag_name: str,
    user=None,
    customer=None,
    default: bool = False,
) -> bool:
    """
    Check if a feature flag is enabled for a user/customer.

    Evaluation order:
    1. Check if flag exists and is globally enabled
    2. Check environment-specific setting
    3. Check for user-specific override
    4. Check for customer-specific override
    5. Check rollout percentage

    Args:
        flag_name: Name of the feature flag
        user: User model instance (optional)
        customer: Customer model instance (optional)
        default: Default value if flag doesn't exist

    Returns:
        bool: Whether the feature is enabled
    """
    # Import here to avoid circular imports
    from upstream.feature_flags.models import FeatureFlagOverride

    # Get the flag
    flag = get_feature_flag(flag_name)

    if flag is None:
        logger.debug(f"Feature flag '{flag_name}' not found, using default: {default}")
        return default

    # Check master switch
    if not flag.enabled:
        return False

    # Check environment-specific setting
    env = get_environment()
    if env == "development" and not flag.enabled_in_development:
        return False
    if env == "staging" and not flag.enabled_in_staging:
        return False
    if env == "production" and not flag.enabled_in_production:
        return False

    # Check for user override
    if user and user.is_authenticated:
        cache_key = f"feature_override:{flag_name}:user:{user.id}"
        override = cache.get(cache_key)

        if override is None:
            try:
                override = FeatureFlagOverride.objects.get(
                    feature_flag=flag,
                    user=user,
                )
                cache.set(cache_key, override, CACHE_TIMEOUT)
            except FeatureFlagOverride.DoesNotExist:
                cache.set(cache_key, "none", CACHE_TIMEOUT)
                override = None

        if override and override != "none":
            return override.override_value == FeatureFlagOverride.OVERRIDE_ENABLED

    # Check for customer override
    if customer:
        cache_key = f"feature_override:{flag_name}:customer:{customer.id}"
        override = cache.get(cache_key)

        if override is None:
            try:
                override = FeatureFlagOverride.objects.get(
                    feature_flag=flag,
                    customer=customer,
                )
                cache.set(cache_key, override, CACHE_TIMEOUT)
            except FeatureFlagOverride.DoesNotExist:
                cache.set(cache_key, "none", CACHE_TIMEOUT)
                override = None

        if override and override != "none":
            return override.override_value == FeatureFlagOverride.OVERRIDE_ENABLED

    # Check rollout percentage
    if flag.rollout_percentage == 100:
        return True
    if flag.rollout_percentage == 0:
        return False

    # Determine identifier for bucketing
    if user and user.is_authenticated:
        identifier = str(user.id)
    elif customer:
        identifier = str(customer.id)
    else:
        # No identifier, use flag default behavior
        return flag.rollout_percentage >= 50

    # Check if user's bucket is within rollout percentage
    bucket = _get_rollout_bucket(flag_name, identifier)
    return bucket < flag.rollout_percentage


def get_all_flags_for_user(user=None, customer=None) -> dict:
    """
    Get all feature flags and their status for a user.

    Useful for sending to frontend to enable client-side checks.

    Returns:
        dict: Map of flag_name -> enabled status
    """
    from upstream.feature_flags.models import FeatureFlag

    flags = {}

    for flag in FeatureFlag.objects.filter(enabled=True):
        flags[flag.name] = is_feature_enabled(
            flag.name,
            user=user,
            customer=customer,
        )

    return flags


def clear_flag_cache(flag_name: str) -> None:
    """
    Clear cache for a specific feature flag.

    Call this when a flag is updated.
    """
    cache.delete(f"feature_flag:{flag_name}")
    # Note: Override caches are cleared by user/customer ID,
    # which is harder to clear globally. They expire after CACHE_TIMEOUT.


def set_flag_for_user(
    flag_name: str,
    user,
    enabled: bool,
    reason: str = "",
    created_by=None,
) -> None:
    """
    Set a feature flag override for a specific user.

    Args:
        flag_name: Name of the feature flag
        user: User model instance
        enabled: Whether to enable or disable
        reason: Reason for the override (for audit)
        created_by: User creating the override
    """
    from upstream.feature_flags.models import FeatureFlag, FeatureFlagOverride

    flag = get_feature_flag(flag_name)
    if not flag:
        raise ValueError(f"Feature flag '{flag_name}' not found")

    override_value = (
        FeatureFlagOverride.OVERRIDE_ENABLED
        if enabled
        else FeatureFlagOverride.OVERRIDE_DISABLED
    )

    FeatureFlagOverride.objects.update_or_create(
        feature_flag=flag,
        user=user,
        defaults={
            "override_value": override_value,
            "reason": reason,
            "created_by": created_by,
        },
    )

    # Clear cache
    cache.delete(f"feature_override:{flag_name}:user:{user.id}")


def set_flag_for_customer(
    flag_name: str,
    customer,
    enabled: bool,
    reason: str = "",
    created_by=None,
) -> None:
    """
    Set a feature flag override for a specific customer.

    Args:
        flag_name: Name of the feature flag
        customer: Customer model instance
        enabled: Whether to enable or disable
        reason: Reason for the override (for audit)
        created_by: User creating the override
    """
    from upstream.feature_flags.models import FeatureFlag, FeatureFlagOverride

    flag = get_feature_flag(flag_name)
    if not flag:
        raise ValueError(f"Feature flag '{flag_name}' not found")

    override_value = (
        FeatureFlagOverride.OVERRIDE_ENABLED
        if enabled
        else FeatureFlagOverride.OVERRIDE_DISABLED
    )

    FeatureFlagOverride.objects.update_or_create(
        feature_flag=flag,
        customer=customer,
        defaults={
            "override_value": override_value,
            "reason": reason,
            "created_by": created_by,
        },
    )

    # Clear cache
    cache.delete(f"feature_override:{flag_name}:customer:{customer.id}")
