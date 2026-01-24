"""
Upstream API Serializers

DRF serializers for all Upstream models with proper field exposure
and security considerations for PHI data.
"""

from rest_framework import serializers
from ..models import (
    Customer, Settings, Upload, ClaimRecord,
    ReportRun, DriftEvent, UserProfile, PayerMapping, CPTGroupMapping
)
from upstream.alerts.models import AlertEvent, OperatorJudgment


class CustomerSerializer(serializers.ModelSerializer):
    """Serializer for Customer model."""
    
    class Meta:
        model = Customer
        fields = ['id', 'name']
        read_only_fields = ['id']


class SettingsSerializer(serializers.ModelSerializer):
    """Serializer for Settings model."""
    
    class Meta:
        model = Settings
        fields = ['id', 'customer', 'to_email', 'cc_email', 'attach_pdf']
        read_only_fields = ['id', 'customer']


class UploadSerializer(serializers.ModelSerializer):
    """Serializer for Upload model."""
    
    class Meta:
        model = Upload
        fields = [
            'id', 'customer', 'uploaded_at', 'filename', 'status',
            'error_message', 'row_count', 'date_min', 'date_max'
        ]
        read_only_fields = ['id', 'customer', 'uploaded_at', 'status', 'error_message', 'row_count']


class UploadSummarySerializer(serializers.ModelSerializer):
    """Lightweight serializer for Upload listings."""
    
    class Meta:
        model = Upload
        fields = ['id', 'filename', 'uploaded_at', 'status', 'row_count']


class ClaimRecordSerializer(serializers.ModelSerializer):
    """Serializer for ClaimRecord model."""
    
    class Meta:
        model = ClaimRecord
        fields = [
            'id', 'customer', 'upload', 'payer', 'cpt', 'cpt_group',
            'submitted_date', 'decided_date', 'outcome', 'allowed_amount'
        ]
        read_only_fields = ['id', 'customer', 'upload']


class ClaimRecordSummarySerializer(serializers.ModelSerializer):
    """Lightweight serializer for ClaimRecord listings."""
    
    class Meta:
        model = ClaimRecord
        fields = ['id', 'payer', 'cpt', 'outcome', 'decided_date']


class DriftEventSerializer(serializers.ModelSerializer):
    """Serializer for DriftEvent model with computed fields."""
    
    delta_percent = serializers.SerializerMethodField()
    severity_label = serializers.SerializerMethodField()
    
    class Meta:
        model = DriftEvent
        fields = [
            'id', 'customer', 'report_run', 'payer', 'cpt_group',
            'drift_type', 'baseline_value', 'current_value', 'delta_value',
            'delta_percent', 'severity', 'severity_label', 'confidence',
            'baseline_start', 'baseline_end', 'current_start', 'current_end',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_delta_percent(self, obj):
        """Calculate percentage change from baseline."""
        if obj.baseline_value and obj.baseline_value != 0:
            return round((obj.delta_value / obj.baseline_value) * 100, 2)
        return None
    
    def get_severity_label(self, obj):
        """Human-readable severity label."""
        if obj.severity >= 0.8:
            return 'CRITICAL'
        elif obj.severity >= 0.6:
            return 'HIGH'
        elif obj.severity >= 0.4:
            return 'MEDIUM'
        else:
            return 'LOW'


class ReportRunSerializer(serializers.ModelSerializer):
    """Serializer for ReportRun model with nested drift events."""
    
    drift_events = DriftEventSerializer(many=True, read_only=True)
    drift_event_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ReportRun
        fields = [
            'id', 'customer', 'run_type', 'started_at', 'finished_at',
            'status', 'summary_json', 'drift_events', 'drift_event_count'
        ]
        read_only_fields = ['id', 'started_at', 'finished_at', 'status', 'summary_json']
    
    def get_drift_event_count(self, obj):
        """Count of drift events in this report."""
        return obj.drift_events.count()


class ReportRunSummarySerializer(serializers.ModelSerializer):
    """Lightweight serializer for ReportRun listings."""
    
    drift_event_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ReportRun
        fields = ['id', 'run_type', 'started_at', 'status', 'drift_event_count']
    
    def get_drift_event_count(self, obj):
        return obj.drift_events.count()


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for UserProfile model."""
    
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    
    class Meta:
        model = UserProfile
        fields = ['id', 'username', 'email', 'customer', 'customer_name']
        read_only_fields = ['id', 'username', 'email']


class PayerMappingSerializer(serializers.ModelSerializer):
    """Serializer for PayerMapping model."""
    
    class Meta:
        model = PayerMapping
        fields = ['id', 'customer', 'raw_name', 'normalized_name']
        read_only_fields = ['id', 'customer']


class CPTGroupMappingSerializer(serializers.ModelSerializer):
    """Serializer for CPTGroupMapping model."""
    
    class Meta:
        model = CPTGroupMapping
        fields = ['id', 'customer', 'cpt_code', 'cpt_group']
        read_only_fields = ['id', 'customer']


# =============================================================================
# Analytics Serializers (for dashboard/reporting endpoints)
# =============================================================================

class PayerSummarySerializer(serializers.Serializer):
    """Aggregated payer statistics."""
    
    payer = serializers.CharField()
    total_claims = serializers.IntegerField()
    paid_count = serializers.IntegerField()
    denied_count = serializers.IntegerField()
    other_count = serializers.IntegerField()
    denial_rate = serializers.FloatField()
    avg_allowed_amount = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)


class DriftInsightSerializer(serializers.Serializer):
    """AI-generated insight for drift events."""
    
    event_id = serializers.IntegerField()
    payer = serializers.CharField()
    insight_text = serializers.CharField()
    recommendation = serializers.CharField()
    confidence_score = serializers.FloatField()


class DashboardSerializer(serializers.Serializer):
    """Dashboard overview data."""

    total_claims = serializers.IntegerField()
    total_uploads = serializers.IntegerField()
    active_drift_events = serializers.IntegerField()
    last_report_date = serializers.DateTimeField(allow_null=True)
    denial_rate_trend = serializers.ListField(child=serializers.DictField())
    top_drift_payers = serializers.ListField(child=serializers.DictField())


# =============================================================================
# Alert & Operator Judgment Serializers
# =============================================================================

class OperatorJudgmentSerializer(serializers.ModelSerializer):
    """Serializer for OperatorJudgment model."""

    operator_username = serializers.CharField(source='operator.username', read_only=True)

    class Meta:
        model = OperatorJudgment
        fields = [
            'id', 'customer', 'alert_event', 'verdict', 'reason_codes_json',
            'recovered_amount', 'recovered_date', 'notes', 'operator',
            'operator_username', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'customer', 'operator', 'operator_username', 'created_at', 'updated_at']


class AlertEventSerializer(serializers.ModelSerializer):
    """Serializer for AlertEvent model with operator judgments."""

    operator_judgments = OperatorJudgmentSerializer(many=True, read_only=True)
    has_judgment = serializers.SerializerMethodField()
    latest_judgment_verdict = serializers.SerializerMethodField()

    class Meta:
        model = AlertEvent
        fields = [
            'id', 'customer', 'alert_rule', 'drift_event', 'report_run',
            'triggered_at', 'status', 'payload', 'notification_sent_at',
            'error_message', 'operator_judgments', 'has_judgment',
            'latest_judgment_verdict', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'triggered_at']

    def get_has_judgment(self, obj):
        """Check if this alert has any operator judgment."""
        return obj.operator_judgments.exists()

    def get_latest_judgment_verdict(self, obj):
        """Get the most recent operator judgment verdict."""
        latest = obj.operator_judgments.order_by('-created_at').first()
        return latest.verdict if latest else None


class OperatorFeedbackSerializer(serializers.Serializer):
    """Serializer for operator feedback submission."""

    verdict = serializers.ChoiceField(choices=[('noise', 'Noise'), ('real', 'Real/Legitimate'), ('needs_followup', 'Needs Follow-up')])
    reason_codes = serializers.ListField(child=serializers.CharField(), required=False, allow_empty=True)
    recovered_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    recovered_date = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)
