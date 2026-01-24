"""
Django settings for Upstream project.

This is a thin wrapper that imports all settings from upstream.settings.dev
for development purposes.

For environment-specific settings:
- Development: Uses this file (imports upstream.settings.dev)
- Production: Use upstream.settings.prod (requires env vars)
"""

# Import all development settings from Upstream
# This includes base settings + SECRET_KEY, DEBUG, ALLOWED_HOSTS, DATABASE, EMAIL
from upstream.settings.dev import *  # noqa: F401, F403
