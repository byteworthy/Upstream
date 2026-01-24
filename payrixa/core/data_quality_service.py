"""
Comprehensive data quality validation and reporting service.

Implements multi-layered data quality checks, anomaly detection,
and quality metric tracking.
"""

import hashlib
import re
from typing import Dict, List, Tuple, Any
from decimal import Decimal
from datetime import datetime, timedelta
from django.db import transaction
from django.utils import timezone
from django.db.models import Avg, StdDev, Count, Q
import numpy as np


class DataQualityService:
    """
    Comprehensive data quality validation and monitoring.

    Provides:
    - Rule-based validation
    - Statistical anomaly detection
    - Quality metric calculation
    - Trending and monitoring
    """

    def __init__(self, customer):
        self.customer = customer

    @transaction.atomic
    def validate_upload(self, upload, rows_data: List[Dict]) -> Dict:
        """
        Validate uploaded data against all enabled rules.

        Returns summary of validation results.
        """
        from payrixa.core.validation_models import (
            ValidationRule, ValidationResult, ClaimValidationHistory,
            DataAnomalyDetection
        )
        from payrixa.models import DataQualityReport

        # Get all enabled validation rules
        rules = ValidationRule.objects.filter(
            customer=self.customer,
            enabled=True,
            applies_to_entity='claim_record'
        ).order_by('execution_order')

        # Track results
        validation_summary = {
            'total_rows': len(rows_data),
            'accepted_rows': 0,
            'rejected_rows': 0,
            'errors_by_type': {},
            'warnings': [],
            'rejection_details': {},
        }

        # Validate each row
        for row_idx, row_data in enumerate(rows_data):
            row_number = row_idx + 1
            row_errors = []
            row_warnings = []

            # Apply each validation rule
            for rule in rules:
                result = self._execute_validation_rule(rule, row_data, row_number)

                if not result['passed']:
                    # Create validation result record
                    ValidationResult.objects.create(
                        customer=self.customer,
                        upload=upload,
                        validation_rule=rule,
                        row_number=row_number,
                        field_name=result.get('field_name', ''),
                        field_value=result.get('field_value', ''),
                        passed=False,
                        error_message=result['error_message'],
                        severity=rule.severity,
                        context_data=row_data
                    )

                    if rule.severity == 'error':
                        row_errors.append(result['error_message'])
                        # Track error types
                        error_type = rule.rule_type
                        validation_summary['errors_by_type'][error_type] = \
                            validation_summary['errors_by_type'].get(error_type, 0) + 1
                    elif rule.severity == 'warning':
                        row_warnings.append(result['error_message'])

            # Determine row acceptance
            if row_errors:
                validation_summary['rejected_rows'] += 1
                validation_summary['rejection_details'][row_number] = row_errors[0]
            else:
                validation_summary['accepted_rows'] += 1

            if row_warnings:
                validation_summary['warnings'].append({
                    'row': row_number,
                    'messages': row_warnings
                })

        # Create quality report
        quality_report = DataQualityReport.objects.create(
            upload=upload,
            customer=self.customer,
            total_rows=validation_summary['total_rows'],
            accepted_rows=validation_summary['accepted_rows'],
            rejected_rows=validation_summary['rejected_rows'],
            rejection_details=validation_summary['rejection_details'],
            warnings=validation_summary['warnings'],
            phi_detections=validation_summary['errors_by_type'].get('phi_detection', 0),
            missing_fields=validation_summary['errors_by_type'].get('required_field', 0),
            invalid_dates=validation_summary['errors_by_type'].get('date_logic', 0),
            invalid_values=validation_summary['errors_by_type'].get('format_check', 0) +
                          validation_summary['errors_by_type'].get('range_check', 0),
        )

        # Update upload with summary
        upload.accepted_row_count = validation_summary['accepted_rows']
        upload.rejected_row_count = validation_summary['rejected_rows']
        upload.warning_row_count = len(validation_summary['warnings'])
        upload.data_quality_issues = validation_summary['errors_by_type']
        upload.save(update_fields=[
            'accepted_row_count', 'rejected_row_count',
            'warning_row_count', 'data_quality_issues'
        ])

        # Detect anomalies
        anomalies = self._detect_upload_anomalies(upload, rows_data)

        return {
            'summary': validation_summary,
            'quality_report': quality_report,
            'anomalies': anomalies,
        }

    def _execute_validation_rule(self, rule, row_data: Dict, row_number: int) -> Dict:
        """Execute a single validation rule against row data."""
        rule_type = rule.rule_type
        field_name = rule.field_name
        logic = rule.validation_logic

        try:
            if rule_type == 'required_field':
                return self._validate_required_field(rule, row_data, field_name)
            elif rule_type == 'format_check':
                return self._validate_format(rule, row_data, field_name, logic)
            elif rule_type == 'range_check':
                return self._validate_range(rule, row_data, field_name, logic)
            elif rule_type == 'date_logic':
                return self._validate_date_logic(rule, row_data, logic)
            elif rule_type == 'phi_detection':
                return self._validate_phi(rule, row_data, field_name)
            elif rule_type == 'reference_check':
                return self._validate_reference(rule, row_data, field_name, logic)
            elif rule_type == 'business_rule':
                return self._validate_business_rule(rule, row_data, logic)
            else:
                return {'passed': True}
        except Exception as e:
            return {
                'passed': False,
                'error_message': f"Validation error: {str(e)}",
                'field_name': field_name,
            }

    def _validate_required_field(self, rule, row_data: Dict, field_name: str) -> Dict:
        """Validate that required field is present and non-empty."""
        value = row_data.get(field_name)

        if value is None or (isinstance(value, str) and not value.strip()):
            return {
                'passed': False,
                'error_message': rule.error_message_template.format(field=field_name),
                'field_name': field_name,
                'field_value': str(value) if value is not None else '',
            }

        return {'passed': True}

    def _validate_format(self, rule, row_data: Dict, field_name: str, logic: Dict) -> Dict:
        """Validate field format using regex or pattern."""
        value = row_data.get(field_name, '')
        pattern = logic.get('pattern', '')

        if not value:
            return {'passed': True}  # Empty is OK for optional fields

        if pattern and not re.match(pattern, str(value)):
            return {
                'passed': False,
                'error_message': rule.error_message_template.format(
                    field=field_name,
                    value=value,
                    pattern=pattern
                ),
                'field_name': field_name,
                'field_value': str(value),
            }

        return {'passed': True}

    def _validate_range(self, rule, row_data: Dict, field_name: str, logic: Dict) -> Dict:
        """Validate numeric value is within acceptable range."""
        value = row_data.get(field_name)

        if value is None or value == '':
            return {'passed': True}  # Empty is OK

        try:
            numeric_value = float(value)
            min_val = logic.get('min')
            max_val = logic.get('max')

            if min_val is not None and numeric_value < min_val:
                return {
                    'passed': False,
                    'error_message': f"{field_name} value {numeric_value} is below minimum {min_val}",
                    'field_name': field_name,
                    'field_value': str(value),
                }

            if max_val is not None and numeric_value > max_val:
                return {
                    'passed': False,
                    'error_message': f"{field_name} value {numeric_value} exceeds maximum {max_val}",
                    'field_name': field_name,
                    'field_value': str(value),
                }

            return {'passed': True}

        except (ValueError, TypeError):
            return {
                'passed': False,
                'error_message': f"{field_name} must be a number",
                'field_name': field_name,
                'field_value': str(value),
            }

    def _validate_date_logic(self, rule, row_data: Dict, logic: Dict) -> Dict:
        """Validate date logic (e.g., decided_date must be after submitted_date)."""
        date1_field = logic.get('date1_field')
        date2_field = logic.get('date2_field')
        comparison = logic.get('comparison', 'after')  # 'after', 'before', 'same'

        date1 = row_data.get(date1_field)
        date2 = row_data.get(date2_field)

        if not date1 or not date2:
            return {'passed': True}  # Can't validate if dates missing

        # Dates should already be parsed by CSV processor
        if comparison == 'after' and date1 <= date2:
            return {
                'passed': False,
                'error_message': f"{date1_field} must be after {date2_field}",
                'field_name': date1_field,
                'field_value': str(date1),
            }

        if comparison == 'before' and date1 >= date2:
            return {
                'passed': False,
                'error_message': f"{date1_field} must be before {date2_field}",
                'field_name': date1_field,
                'field_value': str(date1),
            }

        return {'passed': True}

    def _validate_phi(self, rule, row_data: Dict, field_name: str) -> Dict:
        """Check for potential PHI in fields."""
        value = str(row_data.get(field_name, ''))

        if not value:
            return {'passed': True}

        # Simple PHI detection patterns
        phi_patterns = [
            (r'\b\d{3}-\d{2}-\d{4}\b', 'SSN'),  # SSN pattern
            (r'\b[A-Z]{2}\d{6}\b', 'MRN'),  # Medical record number
            (r'\b\d{3}-\d{3}-\d{4}\b', 'Phone'),  # Phone number
        ]

        for pattern, phi_type in phi_patterns:
            if re.search(pattern, value):
                return {
                    'passed': False,
                    'error_message': f"Potential {phi_type} detected in {field_name}",
                    'field_name': field_name,
                    'field_value': '[REDACTED]',
                }

        return {'passed': True}

    def _validate_reference(self, rule, row_data: Dict, field_name: str, logic: Dict) -> Dict:
        """Validate value against reference data."""
        value = row_data.get(field_name)
        allowed_values = logic.get('allowed_values', [])

        if not value:
            return {'passed': True}

        if allowed_values and value not in allowed_values:
            return {
                'passed': False,
                'error_message': f"{field_name} value '{value}' not in allowed list",
                'field_name': field_name,
                'field_value': str(value),
            }

        return {'passed': True}

    def _validate_business_rule(self, rule, row_data: Dict, logic: Dict) -> Dict:
        """Execute custom business rule."""
        # Business rules are defined in logic dict
        # Example: if outcome='DENIED', denial_reason_code must be present
        rule_name = logic.get('rule_name')

        if rule_name == 'denial_requires_reason':
            outcome = row_data.get('outcome')
            denial_reason = row_data.get('denial_reason_code')

            if outcome == 'DENIED' and not denial_reason:
                return {
                    'passed': False,
                    'error_message': "Denied claims must have a denial reason code",
                    'field_name': 'denial_reason_code',
                    'field_value': '',
                }

        return {'passed': True}

    def _detect_upload_anomalies(self, upload, rows_data: List[Dict]) -> List:
        """Detect statistical anomalies in uploaded data."""
        from payrixa.core.validation_models import DataAnomalyDetection

        anomalies = []

        # 1. Volume anomaly detection
        volume_anomaly = self._detect_volume_anomaly(upload, len(rows_data))
        if volume_anomaly:
            anomalies.append(volume_anomaly)

        # 2. Missing data spike
        missing_spike = self._detect_missing_data_spike(rows_data)
        if missing_spike:
            anomalies.append(missing_spike)

        # 3. Distribution shift detection
        distribution_shift = self._detect_distribution_shift(rows_data)
        if distribution_shift:
            anomalies.extend(distribution_shift)

        # Create anomaly records
        for anomaly_data in anomalies:
            DataAnomalyDetection.objects.create(
                customer=self.customer,
                upload=upload,
                **anomaly_data
            )

        return anomalies

    def _detect_volume_anomaly(self, upload, current_row_count: int) -> Dict:
        """Detect unusual upload volume."""
        from payrixa.models import Upload

        # Get historical average
        recent_uploads = Upload.objects.filter(
            customer=self.customer,
            status='success',
            uploaded_at__gte=timezone.now() - timedelta(days=30)
        ).exclude(id=upload.id)

        stats = recent_uploads.aggregate(
            avg=Avg('row_count'),
            std=StdDev('row_count')
        )

        if not stats['avg'] or not stats['std']:
            return None

        avg_rows = stats['avg']
        std_rows = stats['std']

        # Calculate z-score
        z_score = abs((current_row_count - avg_rows) / std_rows) if std_rows > 0 else 0

        if z_score > 3:  # More than 3 standard deviations
            return {
                'anomaly_type': 'volume_anomaly',
                'severity': 'high' if z_score > 5 else 'medium',
                'anomaly_score': min(z_score / 10, 1.0),
                'confidence': 0.9,
                'description': f"Upload volume ({current_row_count} rows) is {z_score:.1f} "
                              f"standard deviations from average ({avg_rows:.0f} rows)",
                'statistical_details': {
                    'current_count': current_row_count,
                    'avg_count': avg_rows,
                    'std_dev': std_rows,
                    'z_score': z_score,
                },
                'affected_row_count': current_row_count,
                'recommended_action': 'Review upload source - significant volume change detected',
            }

        return None

    def _detect_missing_data_spike(self, rows_data: List[Dict]) -> Dict:
        """Detect spike in missing/empty fields."""
        if not rows_data:
            return None

        # Count missing values per field
        field_missing_counts = {}
        for row in rows_data:
            for field, value in row.items():
                if value is None or (isinstance(value, str) and not value.strip()):
                    field_missing_counts[field] = field_missing_counts.get(field, 0) + 1

        total_rows = len(rows_data)

        # Check for fields with >20% missing
        problematic_fields = {
            field: count
            for field, count in field_missing_counts.items()
            if count / total_rows > 0.2
        }

        if problematic_fields:
            max_field = max(problematic_fields, key=problematic_fields.get)
            missing_rate = problematic_fields[max_field] / total_rows

            return {
                'anomaly_type': 'missing_data_spike',
                'field_name': max_field,
                'severity': 'high' if missing_rate > 0.5 else 'medium',
                'anomaly_score': missing_rate,
                'confidence': 0.95,
                'description': f"Field '{max_field}' has {missing_rate*100:.1f}% missing values",
                'statistical_details': {
                    'field_missing_counts': problematic_fields,
                    'total_rows': total_rows,
                },
                'affected_row_count': problematic_fields[max_field],
                'recommended_action': f"Review data source - high missing rate for {max_field}",
            }

        return None

    def _detect_distribution_shift(self, rows_data: List[Dict]) -> List[Dict]:
        """Detect shifts in data distributions (e.g., outcome mix)."""
        anomalies = []

        if not rows_data:
            return anomalies

        # Analyze outcome distribution
        outcome_counts = {}
        for row in rows_data:
            outcome = row.get('outcome', 'UNKNOWN')
            outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1

        total = len(rows_data)

        # Expected distribution (rough baseline)
        expected_distributions = {
            'PAID': 0.75,  # Expect ~75% paid
            'DENIED': 0.15,  # Expect ~15% denied
            'OTHER': 0.10,  # Expect ~10% other
        }

        for outcome, expected_pct in expected_distributions.items():
            actual_count = outcome_counts.get(outcome, 0)
            actual_pct = actual_count / total

            # Check for significant deviation (>15 percentage points)
            deviation = abs(actual_pct - expected_pct)

            if deviation > 0.15:
                anomalies.append({
                    'anomaly_type': 'distribution_shift',
                    'severity': 'high' if deviation > 0.30 else 'medium',
                    'anomaly_score': min(deviation / 0.5, 1.0),
                    'confidence': 0.8,
                    'description': f"Outcome '{outcome}' is {actual_pct*100:.1f}% "
                                  f"(expected ~{expected_pct*100:.0f}%)",
                    'statistical_details': {
                        'outcome': outcome,
                        'actual_percentage': actual_pct,
                        'expected_percentage': expected_pct,
                        'deviation': deviation,
                        'actual_count': actual_count,
                    },
                    'affected_row_count': total,
                    'recommended_action': f"Review {outcome} claims - unusual distribution",
                })

        return anomalies

    def calculate_quality_metrics(self, start_date, end_date) -> List[Dict]:
        """Calculate comprehensive quality metrics for a time period."""
        from payrixa.core.validation_models import DataQualityMetric
        from payrixa.models import ClaimRecord, Upload

        metrics = []
        measurement_date = end_date

        # 1. Completeness metric
        total_claims = ClaimRecord.objects.filter(
            customer=self.customer,
            processed_at__date__range=[start_date, end_date]
        ).count()

        if total_claims > 0:
            # Count claims with all required fields populated
            complete_claims = ClaimRecord.objects.filter(
                customer=self.customer,
                processed_at__date__range=[start_date, end_date]
            ).exclude(
                Q(payer__isnull=True) | Q(payer='') |
                Q(cpt__isnull=True) | Q(cpt='') |
                Q(allowed_amount__isnull=True)
            ).count()

            completeness_score = complete_claims / total_claims

            metrics.append({
                'metric_type': 'completeness',
                'metric_name': 'Claim Data Completeness',
                'measurement_date': measurement_date,
                'score': completeness_score,
                'sample_size': total_claims,
                'passed_count': complete_claims,
                'failed_count': total_claims - complete_claims,
                'details': {
                    'fields_checked': ['payer', 'cpt', 'allowed_amount'],
                },
            })

        # 2. Validity metric (validation passed rate)
        validated_claims = ClaimRecord.objects.filter(
            customer=self.customer,
            processed_at__date__range=[start_date, end_date],
            validation_passed__isnull=False
        )

        total_validated = validated_claims.count()
        if total_validated > 0:
            passed_validation = validated_claims.filter(validation_passed=True).count()
            validity_score = passed_validation / total_validated

            metrics.append({
                'metric_type': 'validity',
                'metric_name': 'Claim Validation Pass Rate',
                'measurement_date': measurement_date,
                'score': validity_score,
                'sample_size': total_validated,
                'passed_count': passed_validation,
                'failed_count': total_validated - passed_validation,
            })

        # 3. Timeliness metric (upload freshness)
        uploads = Upload.objects.filter(
            customer=self.customer,
            uploaded_at__date__range=[start_date, end_date],
            status='success'
        )

        for upload in uploads:
            if upload.date_max and upload.uploaded_at:
                days_lag = (upload.uploaded_at.date() - upload.date_max).days
                # Score: 1.0 if uploaded same day, decreases with lag
                timeliness_score = max(0.0, 1.0 - (days_lag / 30))

                metrics.append({
                    'metric_type': 'timeliness',
                    'metric_name': 'Upload Timeliness',
                    'measurement_date': upload.uploaded_at.date(),
                    'score': timeliness_score,
                    'sample_size': 1,
                    'passed_count': 1 if days_lag <= 7 else 0,
                    'failed_count': 0 if days_lag <= 7 else 1,
                    'details': {
                        'upload_id': upload.id,
                        'days_lag': days_lag,
                    },
                })

        # Create metric records
        for metric_data in metrics:
            DataQualityMetric.objects.create(
                customer=self.customer,
                **metric_data
            )

        return metrics
