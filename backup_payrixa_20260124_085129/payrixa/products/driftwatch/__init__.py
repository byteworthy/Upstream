"""
DriftWatch Product Module.

Hub v1 Configuration:
- One signal type only: DENIAL_RATE
- Uses existing DriftEvent model from upstream.models
"""

# DriftWatch V1: Locked to DENIAL_RATE drift type
# Do NOT add additional drift types for V1
DRIFTWATCH_V1_EVENT_TYPE = 'DENIAL_RATE'
# DriftWatch product - V1
# Uses existing DriftEvent model from upstream.models
# No new models for V1
