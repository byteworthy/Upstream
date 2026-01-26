"""
API Filter classes for Upstream ViewSets.

Uses django-filter for declarative, validated filtering with automatic
OpenAPI documentation via drf-spectacular.
"""

from django_filters import rest_framework as filters

from upstream.models import ClaimRecord, DriftEvent


class ClaimRecordFilter(filters.FilterSet):
    """
    FilterSet for ClaimRecord with date range and text filtering.

    Replaces hand-rolled filter logic in ClaimRecordViewSet.get_queryset().
    """
    # Text filters with icontains for partial matching
    payer = filters.CharFilter(field_name='payer', lookup_expr='icontains')

    # Exact match for outcome (PAID, DENIED, OTHER)
    outcome = filters.CharFilter(field_name='outcome', lookup_expr='iexact')

    # Date range filters for decided_date
    start_date = filters.DateFilter(field_name='decided_date', lookup_expr='gte')
    end_date = filters.DateFilter(field_name='decided_date', lookup_expr='lte')

    # Additional useful filters
    claim_number = filters.CharFilter(field_name='claim_number', lookup_expr='icontains')
    cpt_code = filters.CharFilter(field_name='cpt_code', lookup_expr='exact')

    class Meta:
        model = ClaimRecord
        fields = ['payer', 'outcome', 'start_date', 'end_date', 'claim_number', 'cpt_code']


class DriftEventFilter(filters.FilterSet):
    """
    FilterSet for DriftEvent with severity range and type filtering.

    Replaces hand-rolled filter logic in DriftEventViewSet.get_queryset().
    """
    # Text filter for payer with partial matching
    payer = filters.CharFilter(field_name='payer', lookup_expr='icontains')

    # Exact match for drift_type (case-insensitive)
    drift_type = filters.CharFilter(field_name='drift_type', lookup_expr='iexact')

    # Severity range filters
    min_severity = filters.NumberFilter(field_name='severity', lookup_expr='gte')
    max_severity = filters.NumberFilter(field_name='severity', lookup_expr='lte')

    # Date range filters
    created_after = filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')

    # Report run filter for getting events from specific run
    report_run = filters.NumberFilter(field_name='report_run_id', lookup_expr='exact')

    class Meta:
        model = DriftEvent
        fields = ['payer', 'drift_type', 'min_severity', 'max_severity',
                  'created_after', 'created_before', 'report_run']
