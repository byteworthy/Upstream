"""
Settings package for Payrixa project.

This package contains environment-specific Django settings:
- base.py: Shared settings common to all environments
- dev.py: Development settings (default)
- prod.py: Production settings with security hardening

To use production settings, set the DJANGO_SETTINGS_MODULE environment variable:
    export DJANGO_SETTINGS_MODULE=payrixa.settings.prod
"""
