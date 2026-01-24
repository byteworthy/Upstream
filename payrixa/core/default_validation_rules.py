"""
Default validation rules for data quality.

These rules are created automatically for new customers.
"""

from django.db import transaction


DEFAULT_VALIDATION_RULES = [
    # Required field rules
    {
        'name': 'Payer Required',
        'code': 'REQ_PAYER',
        'rule_type': 'required_field',
        'field_name': 'payer',
        'severity': 'error',
        'error_message_template': 'Payer field is required',
        'remediation_guidance': 'Ensure every claim has a payer name',
        'execution_order': 10,
    },
    {
        'name': 'CPT Code Required',
        'code': 'REQ_CPT',
        'rule_type': 'required_field',
        'field_name': 'cpt',
        'severity': 'error',
        'error_message_template': 'CPT code is required',
        'remediation_guidance': 'Ensure every claim has a CPT code',
        'execution_order': 11,
    },
    {
        'name': 'Submitted Date Required',
        'code': 'REQ_SUBMITTED_DATE',
        'rule_type': 'required_field',
        'field_name': 'submitted_date',
        'severity': 'error',
        'error_message_template': 'Submitted date is required',
        'remediation_guidance': 'Ensure every claim has a submission date',
        'execution_order': 12,
    },
    {
        'name': 'Decided Date Required',
        'code': 'REQ_DECIDED_DATE',
        'rule_type': 'required_field',
        'field_name': 'decided_date',
        'severity': 'error',
        'error_message_template': 'Decided date is required',
        'remediation_guidance': 'Ensure every claim has a decision date',
        'execution_order': 13,
    },
    {
        'name': 'Outcome Required',
        'code': 'REQ_OUTCOME',
        'rule_type': 'required_field',
        'field_name': 'outcome',
        'severity': 'error',
        'error_message_template': 'Outcome is required',
        'remediation_guidance': 'Outcome must be PAID, DENIED, or OTHER',
        'execution_order': 14,
    },

    # Format validation rules
    {
        'name': 'CPT Code Format',
        'code': 'FMT_CPT',
        'rule_type': 'format_check',
        'field_name': 'cpt',
        'validation_logic': {
            'pattern': r'^\d{5}$'
        },
        'severity': 'warning',
        'error_message_template': 'CPT code {value} should be 5 digits',
        'remediation_guidance': 'CPT codes are typically 5-digit numeric codes',
        'execution_order': 20,
    },
    {
        'name': 'Denial Code Format',
        'code': 'FMT_DENIAL_CODE',
        'rule_type': 'format_check',
        'field_name': 'denial_reason_code',
        'validation_logic': {
            'pattern': r'^[A-Z]{2}-\d+'
        },
        'severity': 'warning',
        'error_message_template': 'Denial code {value} should follow format XX-NNN',
        'remediation_guidance': 'Standard denial codes are like CO-45, PR-96, etc.',
        'execution_order': 21,
    },

    # Range validation rules
    {
        'name': 'Allowed Amount Range',
        'code': 'RNG_ALLOWED_AMT',
        'rule_type': 'range_check',
        'field_name': 'allowed_amount',
        'validation_logic': {
            'min': 0,
            'max': 1000000  # $1M max per claim (configurable)
        },
        'severity': 'warning',
        'error_message_template': 'Allowed amount should be between $0 and $1,000,000',
        'remediation_guidance': 'Check for data entry errors or unusual claims',
        'execution_order': 30,
    },

    # Date logic rules
    {
        'name': 'Decision After Submission',
        'code': 'DATE_DECISION_AFTER_SUBMISSION',
        'rule_type': 'date_logic',
        'validation_logic': {
            'date1_field': 'decided_date',
            'date2_field': 'submitted_date',
            'comparison': 'after'
        },
        'severity': 'error',
        'error_message_template': 'Decision date must be after submission date',
        'remediation_guidance': 'Verify dates are entered correctly',
        'execution_order': 40,
    },
    {
        'name': 'Submission Date Not Future',
        'code': 'DATE_SUBMITTED_NOT_FUTURE',
        'rule_type': 'date_logic',
        'validation_logic': {
            'date1_field': 'submitted_date',
            'date2_field': '__today__',
            'comparison': 'before'
        },
        'severity': 'error',
        'error_message_template': 'Submission date cannot be in the future',
        'remediation_guidance': 'Check date format and values',
        'execution_order': 41,
    },

    # PHI detection rules
    {
        'name': 'PHI in Payer Field',
        'code': 'PHI_PAYER',
        'rule_type': 'phi_detection',
        'field_name': 'payer',
        'severity': 'error',
        'error_message_template': 'Potential PHI detected in payer field',
        'remediation_guidance': 'Remove patient names, SSNs, or other PHI from payer field',
        'execution_order': 50,
    },
    {
        'name': 'PHI in Denial Reason',
        'code': 'PHI_DENIAL',
        'rule_type': 'phi_detection',
        'field_name': 'denial_reason_text',
        'severity': 'warning',
        'error_message_template': 'Potential PHI in denial reason text',
        'remediation_guidance': 'Ensure denial reasons do not contain patient identifiers',
        'execution_order': 51,
    },

    # Reference data validation
    {
        'name': 'Valid Outcome Values',
        'code': 'REF_OUTCOME',
        'rule_type': 'reference_check',
        'field_name': 'outcome',
        'validation_logic': {
            'allowed_values': ['PAID', 'DENIED', 'OTHER']
        },
        'severity': 'error',
        'error_message_template': 'Outcome must be PAID, DENIED, or OTHER',
        'remediation_guidance': 'Check outcome field values',
        'execution_order': 60,
    },

    # Business rules
    {
        'name': 'Denied Claims Need Reason',
        'code': 'BIZ_DENIAL_REASON',
        'rule_type': 'business_rule',
        'validation_logic': {
            'rule_name': 'denial_requires_reason'
        },
        'severity': 'warning',
        'error_message_template': 'Denied claims should have a denial reason code',
        'remediation_guidance': 'Add denial reason codes for better analytics',
        'execution_order': 70,
    },
]


@transaction.atomic
def create_default_rules_for_customer(customer):
    """Create default validation rules for a customer."""
    from payrixa.core.validation_models import ValidationRule

    created_rules = []

    for rule_data in DEFAULT_VALIDATION_RULES:
        rule, created = ValidationRule.objects.get_or_create(
            customer=customer,
            code=rule_data['code'],
            defaults=rule_data
        )

        if created:
            created_rules.append(rule)

    return created_rules


def get_validation_rule_statistics(customer):
    """Get statistics on validation rules usage."""
    from payrixa.core.validation_models import ValidationRule, ValidationResult
    from django.db.models import Count

    rules = ValidationRule.objects.filter(customer=customer)

    stats = []
    for rule in rules:
        failures = ValidationResult.objects.filter(
            customer=customer,
            validation_rule=rule,
            passed=False
        ).count()

        stats.append({
            'rule_code': rule.code,
            'rule_name': rule.name,
            'enabled': rule.enabled,
            'severity': rule.severity,
            'failure_count': failures,
        })

    return sorted(stats, key=lambda x: x['failure_count'], reverse=True)
