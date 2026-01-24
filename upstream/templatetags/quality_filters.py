"""
Template filters for data quality displays.
"""

from django import template

register = template.Library()


@register.filter
def quality_badge_class(score):
    """
    Return Bootstrap badge class based on quality score.

    Args:
        score: Quality score from 0.0 to 1.0

    Returns:
        Bootstrap class name (success, warning, danger)
    """
    if score is None:
        return 'secondary'

    if score >= 0.95:
        return 'success'
    elif score >= 0.85:
        return 'info'
    elif score >= 0.70:
        return 'warning'
    else:
        return 'danger'


@register.filter
def grade_color_class(grade):
    """
    Return Bootstrap color class based on letter grade.

    Args:
        grade: Letter grade (A+, A, B+, B, C+, C, D, F)

    Returns:
        Bootstrap class name (success, warning, danger)
    """
    if not grade:
        return 'secondary'

    grade = str(grade).upper()

    if grade in ['A+', 'A']:
        return 'success'
    elif grade in ['B+', 'B']:
        return 'info'
    elif grade in ['C+', 'C']:
        return 'warning'
    else:
        return 'danger'


@register.filter
def severity_badge_class(severity):
    """
    Return Bootstrap badge class based on severity.

    Args:
        severity: Severity level (info, warning, critical, emergency, low, medium, high)

    Returns:
        Bootstrap class name
    """
    if not severity:
        return 'secondary'

    severity = str(severity).lower()

    if severity in ['critical', 'emergency', 'error']:
        return 'danger'
    elif severity in ['high', 'warning']:
        return 'warning'
    elif severity in ['medium', 'info']:
        return 'info'
    else:
        return 'secondary'


@register.filter
def percentage(value):
    """
    Format value as percentage.

    Args:
        value: Float value (0.0 to 1.0)

    Returns:
        Formatted percentage string
    """
    if value is None:
        return '—'

    try:
        return f"{float(value) * 100:.1f}%"
    except (ValueError, TypeError):
        return '—'


@register.filter
def intcomma(value):
    """
    Format integer with comma separators.

    Args:
        value: Integer value

    Returns:
        Formatted string with commas
    """
    if value is None:
        return '—'

    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return '—'


@register.filter
def replace(value, arg):
    """
    Replace substring in string.

    Args:
        value: String value
        arg: String to replace in format "old:new"

    Returns:
        Modified string
    """
    if not value or not arg:
        return value

    try:
        old, new = arg.split(':')
        return str(value).replace(old, new)
    except (ValueError, AttributeError):
        return value
