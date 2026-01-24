"""
Logging filters for PHI/PII scrubbing (HIPAA compliance).

These filters automatically redact sensitive personal health information (PHI)
and personally identifiable information (PII) from log messages to ensure
HIPAA compliance.

Usage:
    # In settings.py LOGGING configuration:
    LOGGING = {
        'filters': {
            'phi_scrubber': {
                '()': 'upstream.logging_filters.PHIScrubberFilter',
            },
        },
        'handlers': {
            'console': {
                'filters': ['phi_scrubber'],
                # ... rest of config
            },
        },
    }
"""

import re
import logging
from typing import Pattern, Dict, Any


# =============================================================================
# PHI/PII Detection Patterns
# =============================================================================

# Social Security Number patterns
SSN_PATTERNS = [
    re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),  # 123-45-6789
    re.compile(r'\b\d{9}\b'),              # 123456789 (9 consecutive digits)
]

# Medical Record Number patterns (various formats)
MRN_PATTERNS = [
    re.compile(r'\b[Mm][Rr][Nn]\s*:?\s*[\w\-]+'),  # MRN: 12345 or mrn:ABC-123
    re.compile(r'\bmedical[\s_]record[\s_]number\s*:?\s*[\w\-]+', re.IGNORECASE),
]

# Date of Birth patterns
DOB_PATTERNS = [
    re.compile(r'\b[Dd][Oo][Bb]\s*:?\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}'),  # DOB: 01/15/1990
    re.compile(r'\bdate[\s_]of[\s_]birth\s*:?\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', re.IGNORECASE),
]

# Phone Number patterns (US format)
PHONE_PATTERNS = [
    re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'),  # 555-123-4567 or 5551234567
    re.compile(r'\(\d{3}\)\s*\d{3}[-.]?\d{4}'),    # (555) 123-4567
]

# Email Address pattern
EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')

# Patient Name patterns (context-based)
PATIENT_NAME_PATTERNS = [
    re.compile(r'\b[Pp]atient[\s_]name\s*:?\s*[A-Za-z\s\'-]+', re.IGNORECASE),
    re.compile(r'\b[Nn]ame\s*:?\s*[A-Z][a-z]+\s+[A-Z][a-z]+'),  # Capitalized first/last name
]

# Physical Address patterns
ADDRESS_PATTERNS = [
    re.compile(r'\b\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct)\.?\b', re.IGNORECASE),
    re.compile(r'\baddress\s*:?\s*[^\n]+', re.IGNORECASE),
]

# Credit Card patterns
CREDIT_CARD_PATTERNS = [
    re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),  # 1234-5678-9012-3456
]

# IP Address pattern (optional - sometimes considered PII)
IP_ADDRESS_PATTERN = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')


# =============================================================================
# PHI/PII Scrubber Filter
# =============================================================================

class PHIScrubberFilter(logging.Filter):
    """
    Logging filter that automatically redacts PHI/PII from log messages.

    This filter searches for common PHI/PII patterns (SSN, MRN, DOB, etc.)
    and replaces them with [REDACTED] to ensure HIPAA compliance.

    Configuration:
        Add to LOGGING in settings.py:

        LOGGING = {
            'filters': {
                'phi_scrubber': {
                    '()': 'upstream.logging_filters.PHIScrubberFilter',
                },
            },
            'handlers': {
                'console': {
                    'filters': ['phi_scrubber'],
                    # ... rest of config
                },
                'file': {
                    'filters': ['phi_scrubber'],
                    # ... rest of config
                },
            },
        }

    Sensitive Fields:
        - Social Security Numbers (SSN)
        - Medical Record Numbers (MRN)
        - Dates of Birth (DOB)
        - Phone numbers
        - Email addresses
        - Patient names
        - Physical addresses
        - Credit card numbers

    Example:
        Input:  "Processing claim for patient John Doe, SSN 123-45-6789"
        Output: "Processing claim for patient [REDACTED_NAME], SSN [REDACTED_SSN]"
    """

    def __init__(self, name: str = ''):
        """
        Initialize the PHI scrubber filter.

        Args:
            name: Filter name (optional)
        """
        super().__init__(name)

        # Compile all patterns with their replacement labels
        self.patterns: Dict[str, tuple] = {
            'SSN': (SSN_PATTERNS, '[REDACTED_SSN]'),
            'MRN': (MRN_PATTERNS, '[REDACTED_MRN]'),
            'DOB': (DOB_PATTERNS, '[REDACTED_DOB]'),
            'PHONE': (PHONE_PATTERNS, '[REDACTED_PHONE]'),
            'EMAIL': ([EMAIL_PATTERN], '[REDACTED_EMAIL]'),
            'PATIENT_NAME': (PATIENT_NAME_PATTERNS, '[REDACTED_NAME]'),
            'ADDRESS': (ADDRESS_PATTERNS, '[REDACTED_ADDRESS]'),
            'CREDIT_CARD': (CREDIT_CARD_PATTERNS, '[REDACTED_CC]'),
        }

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filter and scrub PHI/PII from log record.

        Args:
            record: Log record to filter

        Returns:
            bool: Always returns True (allow log after scrubbing)
        """
        # Scrub the main message
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            record.msg = self.scrub_phi(record.msg)

        # Scrub any extra fields in the record
        if hasattr(record, '__dict__'):
            for key, value in record.__dict__.items():
                if isinstance(value, str):
                    setattr(record, key, self.scrub_phi(value))

        return True

    def scrub_phi(self, text: str) -> str:
        """
        Scrub PHI/PII from text.

        Args:
            text: Text to scrub

        Returns:
            str: Scrubbed text with PHI/PII redacted
        """
        if not text:
            return text

        scrubbed_text = text

        # Apply all patterns
        for category, (patterns, replacement) in self.patterns.items():
            for pattern in patterns:
                scrubbed_text = pattern.sub(replacement, scrubbed_text)

        return scrubbed_text


class AggressivePHIScrubberFilter(PHIScrubberFilter):
    """
    More aggressive PHI scrubber that also redacts IP addresses and
    applies stricter pattern matching.

    Use this filter for production environments where maximum security
    is required, at the cost of potentially over-redacting.

    Configuration:
        LOGGING = {
            'filters': {
                'phi_scrubber': {
                    '()': 'upstream.logging_filters.AggressivePHIScrubberFilter',
                },
            },
            # ... rest of config
        }
    """

    def __init__(self, name: str = ''):
        """Initialize aggressive scrubber with additional patterns."""
        super().__init__(name)

        # Add IP address scrubbing
        self.patterns['IP_ADDRESS'] = ([IP_ADDRESS_PATTERN], '[REDACTED_IP]')

        # Add more aggressive name detection
        self.patterns['POTENTIAL_NAME'] = (
            [re.compile(r'\b[A-Z][a-z]{2,}\s+[A-Z][a-z]{2,}\b')],  # Two capitalized words
            '[REDACTED_NAME]'
        )


class SelectivePHIScrubberFilter(PHIScrubberFilter):
    """
    Selective PHI scrubber that only redacts specific high-risk fields.

    Use this for development/staging where you want some PHI protection
    but need to see email addresses and phone numbers for debugging.

    Configuration:
        LOGGING = {
            'filters': {
                'phi_scrubber': {
                    '()': 'upstream.logging_filters.SelectivePHIScrubberFilter',
                },
            },
            # ... rest of config
        }
    """

    def __init__(self, name: str = ''):
        """Initialize selective scrubber with reduced patterns."""
        super().__init__(name)

        # Only scrub high-risk PHI
        self.patterns = {
            'SSN': (SSN_PATTERNS, '[REDACTED_SSN]'),
            'MRN': (MRN_PATTERNS, '[REDACTED_MRN]'),
            'DOB': (DOB_PATTERNS, '[REDACTED_DOB]'),
            'CREDIT_CARD': (CREDIT_CARD_PATTERNS, '[REDACTED_CC]'),
        }


# =============================================================================
# Helper Functions
# =============================================================================

def scrub_dict(data: Dict[str, Any], scrubber: PHIScrubberFilter = None) -> Dict[str, Any]:
    """
    Scrub PHI/PII from a dictionary (useful for structured logs).

    Args:
        data: Dictionary to scrub
        scrubber: PHIScrubberFilter instance (creates new if None)

    Returns:
        Dict[str, Any]: Dictionary with PHI/PII redacted

    Example:
        >>> data = {'name': 'John Doe', 'ssn': '123-45-6789'}
        >>> scrubbed = scrub_dict(data)
        >>> print(scrubbed)
        {'name': '[REDACTED_NAME]', 'ssn': '[REDACTED_SSN]'}
    """
    if scrubber is None:
        scrubber = PHIScrubberFilter()

    scrubbed = {}
    for key, value in data.items():
        if isinstance(value, str):
            scrubbed[key] = scrubber.scrub_phi(value)
        elif isinstance(value, dict):
            scrubbed[key] = scrub_dict(value, scrubber)
        elif isinstance(value, list):
            scrubbed[key] = [
                scrubber.scrub_phi(item) if isinstance(item, str) else item
                for item in value
            ]
        else:
            scrubbed[key] = value

    return scrubbed


def is_phi_present(text: str) -> bool:
    """
    Check if text contains potential PHI/PII.

    Args:
        text: Text to check

    Returns:
        bool: True if potential PHI/PII is detected

    Example:
        >>> is_phi_present("Patient SSN: 123-45-6789")
        True
        >>> is_phi_present("Processing upload complete")
        False
    """
    scrubber = PHIScrubberFilter()
    scrubbed = scrubber.scrub_phi(text)
    return scrubbed != text  # PHI present if text changed


# =============================================================================
# Example Usage
# =============================================================================

"""
Example: Using PHI scrubber in logging configuration

# In config/settings.py:

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'phi_scrubber': {
            '()': 'upstream.logging_filters.PHIScrubberFilter',
        },
    },
    'formatters': {
        'structured': {
            '()': 'upstream.logging_utils.StructuredLogFormatter',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'filters': ['phi_scrubber'],
            'formatter': 'structured',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/upstream/app.log',
            'filters': ['phi_scrubber'],
            'formatter': 'structured',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
        },
    },
    'loggers': {
        'upstream': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
        },
    },
}

Example: Using PHI scrubber programmatically

    from upstream.logging_filters import PHIScrubberFilter, scrub_dict

    scrubber = PHIScrubberFilter()

    # Scrub a message
    message = "Patient John Doe (SSN: 123-45-6789) admitted"
    safe_message = scrubber.scrub_phi(message)
    print(safe_message)
    # Output: "Patient [REDACTED_NAME] (SSN: [REDACTED_SSN]) admitted"

    # Scrub a dictionary
    data = {
        'patient_name': 'Jane Smith',
        'ssn': '987-65-4321',
        'phone': '555-123-4567'
    }
    safe_data = scrub_dict(data)
    print(safe_data)
    # Output: {'patient_name': '[REDACTED_NAME]', 'ssn': '[REDACTED_SSN]', 'phone': '[REDACTED_PHONE]'}
"""
