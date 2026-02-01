"""
Feature flags module for gradual rollout management.
"""

from upstream.feature_flags.service import (
    is_feature_enabled,
    get_all_flags_for_user,
    get_feature_flag,
)

__all__ = [
    "is_feature_enabled",
    "get_all_flags_for_user",
    "get_feature_flag",
]
