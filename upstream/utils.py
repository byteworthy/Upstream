import re
from django.http import HttpRequest


# PHI Detection - Common first names for detection
COMMON_FIRST_NAMES = {
    "john",
    "mary",
    "michael",
    "sarah",
    "david",
    "jennifer",
    "james",
    "patricia",
    "robert",
    "linda",
    "william",
    "barbara",
    "richard",
    "elizabeth",
    "joseph",
    "susan",
    "thomas",
    "jessica",
    "charles",
    "karen",
    "christopher",
    "nancy",
    "daniel",
    "betty",
    "matthew",
    "margaret",
    "anthony",
    "sandra",
    "donald",
    "ashley",
    "mark",
    "dorothy",
    "paul",
    "kimberly",
    "steven",
    "emily",
    "andrew",
    "donna",
    "joshua",
    "michelle",
    "kenneth",
    "carol",
}

# PHI Patterns
SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b|\b\d{9}\b")
DOB_PATTERN = re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}\b")
PHONE_PATTERN = re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b")
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
MRN_PATTERN = re.compile(r"\bMRN[:\s]*\d+\b", re.IGNORECASE)


def detect_phi(text):
    """
    Detect potential PHI (Protected Health Information) in text.

    Returns:
        (has_phi, message): Tuple of boolean and error message
    """
    if not text or not isinstance(text, str):
        return False, ""

    text_lower = text.lower()
    words = text_lower.split()

    # Check for common first names
    for word in words:
        clean_word = re.sub(r"[^\w\s]", "", word)
        if clean_word in COMMON_FIRST_NAMES:
            return True, f"Field may contain PHI: '{word}' appears to be a name"

    # Check for SSN
    if SSN_PATTERN.search(text):
        return True, "Field contains SSN pattern"

    # Check for date of birth patterns
    if DOB_PATTERN.search(text):
        return True, "Field contains date pattern (possible DOB)"

    # Check for phone numbers
    if PHONE_PATTERN.search(text):
        return True, "Field contains phone number"

    # Check for email addresses
    if EMAIL_PATTERN.search(text):
        return True, "Field contains email address"

    # Check for MRN
    if MRN_PATTERN.search(text):
        return True, "Field contains MRN (Medical Record Number)"

    return False, ""


def scrub_phi(text):
    """Remove potential PHI from text for logging purposes."""
    if not text or not isinstance(text, str):
        return text

    # Scrub SSN
    text = SSN_PATTERN.sub("[SSN REDACTED]", text)

    # Scrub phone
    text = PHONE_PATTERN.sub("[PHONE REDACTED]", text)

    # Scrub email
    text = EMAIL_PATTERN.sub("[EMAIL REDACTED]", text)

    # Scrub MRN
    text = MRN_PATTERN.sub("[MRN REDACTED]", text)

    return text


def get_current_customer(request: HttpRequest):
    """
    Get the current customer associated with the logged-in user.

    Args:
        request: Django HttpRequest object

    Returns:
        Customer: The customer associated with the user

    Raises:
        ValueError: If user is not authenticated or doesn't have a profile/customer
    """
    # Lazy import to avoid circular dependency
    from upstream.models import Customer  # noqa: F401

    if not request.user.is_authenticated:
        raise ValueError("User is not authenticated")

    if not hasattr(request.user, "profile"):
        raise ValueError("User does not have a profile")

    if not request.user.profile.customer:
        raise ValueError("User profile is not associated with a customer")

    return request.user.profile.customer
