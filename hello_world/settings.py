"""
Django settings for Payrixa project.

This is a thin wrapper that imports all settings from payrixa.settings.dev
for development purposes.

For environment-specific settings:
- Development: Uses this file (imports payrixa.settings.dev)
- Production: Use payrixa.settings.prod (requires env vars)
"""

# Import all development settings from Payrixa
# This includes base settings + SECRET_KEY, DEBUG, ALLOWED_HOSTS, DATABASE, EMAIL
from payrixa.settings.dev import *  # noqa: F401, F403
