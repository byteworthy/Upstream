"""
Test fixtures and helpers for Upstream multi-tenant testing.

This module provides reusable test fixtures and utilities that follow
tenant isolation best practices.

Usage:
    from upstream.test_fixtures import TenantTestMixin

    class MyTest(TenantTestMixin, TestCase):
        def test_something(self):
            customer = self.create_customer('Hospital A')
            user = self.create_user(customer, 'testuser')
            # ...
"""

from typing import List, Optional
from decimal import Decimal
from datetime import date, timedelta

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.cache import cache

from upstream.models import (
    Customer,
    UserProfile,
    Upload,
    ClaimRecord,
    ReportRun,
    DriftEvent,
)
from upstream.alerts.models import AlertRule, AlertEvent, NotificationChannel
from upstream.automation.models import (
    ClaimScore,
    CustomerAutomationProfile,
    ShadowModeResult,
)
from upstream.integrations.models import EHRConnection, EHRSyncLog


class TenantTestMixin:
    """
    Mixin providing common tenant test utilities.

    Add this to any TestCase to get helper methods for creating test data.

    Example:
        class MyTest(TenantTestMixin, TestCase):
            def setUp(self):
                super().setUp()
                self.customer = self.create_customer('Hospital A')
                self.user = self.create_user(self.customer)

            def test_something(self):
                claims = self.create_claims(self.customer, count=50)
                # ... test with claims
    """

    def setUp(self):
        """Clear cache before each test."""
        super().setUp()
        cache.clear()

    def create_customer(self, name: str = "Test Hospital") -> Customer:
        """Create a test customer."""
        return Customer.objects.create(name=name)

    def create_user(
        self,
        customer: Customer,
        username: str = "testuser",
        password: str = "testpass123",
        email: Optional[str] = None,
        role: str = "user",
    ) -> User:
        """Create a test user linked to a customer."""
        if email is None:
            email = f"{username}@example.com"

        user = User.objects.create_user(
            username=username, password=password, email=email
        )

        UserProfile.objects.create(user=user, customer=customer, role=role)

        return user

    def create_upload(
        self,
        customer: Customer,
        filename: str = "test.csv",
        status: str = "success",
        row_count: int = 100,
        **kwargs,
    ) -> Upload:
        """Create a test upload."""
        return Upload.all_objects.create(
            customer=customer,
            filename=filename,
            status=status,
            row_count=row_count,
            **kwargs,
        )

    def create_claims(
        self,
        customer: Customer,
        payer: str = "Medicare",
        cpt_group: str = "SURGERY",
        count: int = 100,
        outcome_ratio: float = 0.5,
        base_date: Optional[date] = None,
        **kwargs,
    ) -> List[ClaimRecord]:
        """Create test claim records."""
        if base_date is None:
            base_date = timezone.now().date()

        claims = []
        for i in range(count):
            outcome = "PAID" if i < (count * outcome_ratio) else "DENIED"
            days_ago = i % 30
            submitted_date = base_date - timedelta(days=days_ago)
            decided_date = submitted_date + timedelta(days=7)

            claim = ClaimRecord.all_objects.create(
                customer=customer,
                payer=payer,
                cpt="99213",
                cpt_group=cpt_group,
                outcome=outcome,
                submitted_date=submitted_date,
                decided_date=decided_date,
                allowed_amount=Decimal("150.00")
                if outcome == "PAID"
                else Decimal("0.00"),
                submitted_via="csv_upload",  # Default for test fixtures
                **kwargs,
            )
            claims.append(claim)

        return claims

    def create_report_run(
        self,
        customer: Customer,
        status: str = "success",
        run_type: str = "weekly",
        **kwargs,
    ) -> ReportRun:
        """Create a test report run."""
        defaults = {
            "started_at": timezone.now() - timedelta(hours=1),
            "finished_at": timezone.now(),
            "summary_json": {"events_created": 0},
        }
        defaults.update(kwargs)

        return ReportRun.all_objects.create(
            customer=customer, run_type=run_type, status=status, **defaults
        )

    def create_drift_event(
        self,
        customer: Customer,
        report_run: Optional[ReportRun] = None,
        payer: str = "Medicare",
        cpt_group: str = "SURGERY",
        drift_type: str = "DENIAL_RATE",
        severity: float = 0.75,
        **kwargs,
    ) -> DriftEvent:
        """Create a test drift event."""
        if report_run is None:
            report_run = self.create_report_run(customer)

        defaults = {
            "baseline_value": 0.15,
            "current_value": 0.35,
            "delta_value": 0.20,
            "confidence": 0.90,
            "baseline_start": timezone.now().date() - timedelta(days=104),
            "baseline_end": timezone.now().date() - timedelta(days=14),
            "current_start": timezone.now().date() - timedelta(days=14),
            "current_end": timezone.now().date(),
        }
        defaults.update(kwargs)

        return DriftEvent.all_objects.create(
            customer=customer,
            report_run=report_run,
            payer=payer,
            cpt_group=cpt_group,
            drift_type=drift_type,
            severity=severity,
            **defaults,
        )

    def create_alert_rule(
        self,
        customer: Customer,
        name: str = "Test Alert Rule",
        metric: str = "severity",
        threshold_value: float = 0.7,
        severity: str = "critical",
        **kwargs,
    ) -> AlertRule:
        """Create a test alert rule."""
        return AlertRule.all_objects.create(
            customer=customer,
            name=name,
            metric=metric,
            threshold_value=threshold_value,
            severity=severity,
            enabled=True,
            **kwargs,
        )

    def create_alert_event(
        self,
        customer: Customer,
        alert_rule: AlertRule,
        drift_event: Optional[DriftEvent] = None,
        report_run: Optional[ReportRun] = None,
        status: str = "pending",
        **kwargs,
    ) -> AlertEvent:
        """Create a test alert event."""
        if drift_event is None:
            drift_event = self.create_drift_event(customer, report_run=report_run)

        if report_run is None:
            report_run = drift_event.report_run

        defaults = {
            "payload": {
                "payer": drift_event.payer,
                "drift_type": drift_event.drift_type,
                "severity": drift_event.severity,
            }
        }
        defaults.update(kwargs)

        return AlertEvent.all_objects.create(
            customer=customer,
            alert_rule=alert_rule,
            drift_event=drift_event,
            report_run=report_run,
            status=status,
            **defaults,
        )

    def create_notification_channel(
        self,
        customer: Customer,
        name: str = "Test Channel",
        channel_type: str = "email",
        config: Optional[dict] = None,
        **kwargs,
    ) -> NotificationChannel:
        """Create a test notification channel."""
        if config is None:
            if channel_type == "email":
                config = {"recipients": ["test@example.com"]}
            elif channel_type == "slack":
                config = {"webhook_url": "https://hooks.slack.com/test"}
            else:
                config = {}

        return NotificationChannel.all_objects.create(
            customer=customer,
            name=name,
            channel_type=channel_type,
            config=config,
            enabled=True,
            **kwargs,
        )

    # =================================================================
    # Automation Model Fixtures (Story #17)
    # =================================================================

    def create_claim_score(
        self,
        customer: Customer,
        claim: Optional[ClaimRecord] = None,
        overall_confidence: float = 0.85,
        coding_confidence: float = 0.90,
        eligibility_confidence: float = 0.80,
        medical_necessity_confidence: float = 0.82,
        documentation_completeness: float = 0.88,
        denial_risk_score: float = 0.20,
        fraud_risk_score: float = 0.05,
        compliance_risk_score: float = 0.10,
        recommended_action: str = "queue_review",
        automation_tier: int = 2,
        requires_human_review: bool = False,
        **kwargs,
    ) -> ClaimScore:
        """
        Create a test ClaimScore with realistic default values.

        Args:
            customer: Customer who owns this score
            claim: Associated ClaimRecord (created if not provided)
            overall_confidence: Combined confidence score (0.0-1.0)
            coding_confidence: CPT coding accuracy confidence
            eligibility_confidence: Patient eligibility confidence
            medical_necessity_confidence: Medical necessity criteria confidence
            documentation_completeness: Documentation completeness score
            denial_risk_score: Historical denial risk (0.0-1.0)
            fraud_risk_score: Fraud detection risk score
            compliance_risk_score: Compliance violation risk
            recommended_action: One of auto_execute, queue_review, escalate, block
            automation_tier: 1 (auto), 2 (review), or 3 (escalate)
            requires_human_review: Whether human review is required by regulation

        Returns:
            Created ClaimScore instance
        """
        if claim is None:
            # Create a claim if not provided
            upload = self.create_upload(customer)
            claim = ClaimRecord.all_objects.create(
                customer=customer,
                upload=upload,
                payer="TestPayer",
                cpt="99213",
                cpt_group="EVAL",
                submitted_date=timezone.now().date() - timedelta(days=10),
                decided_date=timezone.now().date() - timedelta(days=5),
                outcome="PAID",
                allowed_amount=Decimal("150.00"),
                submitted_via="csv_upload",
            )

        defaults = {
            "model_version": "rf_v1.0",
            "feature_importance": {"payer_history": 0.35, "cpt_denial_rate": 0.25},
            "prediction_reasoning": "Test score with moderate confidence",
            "red_line_reason": "",
        }
        defaults.update(kwargs)

        return ClaimScore.objects.create(
            customer=customer,
            claim=claim,
            overall_confidence=overall_confidence,
            coding_confidence=coding_confidence,
            eligibility_confidence=eligibility_confidence,
            medical_necessity_confidence=medical_necessity_confidence,
            documentation_completeness=documentation_completeness,
            denial_risk_score=denial_risk_score,
            fraud_risk_score=fraud_risk_score,
            compliance_risk_score=compliance_risk_score,
            recommended_action=recommended_action,
            automation_tier=automation_tier,
            requires_human_review=requires_human_review,
            **defaults,
        )

    def create_automation_profile(
        self,
        customer: Customer,
        automation_stage: str = "observe",
        auto_execute_confidence: float = 0.95,
        auto_execute_max_amount: Decimal = Decimal("1000.00"),
        queue_review_min_confidence: float = 0.70,
        queue_review_max_amount: Decimal = Decimal("10000.00"),
        escalate_min_amount: Decimal = Decimal("10000.00"),
        shadow_mode_enabled: bool = True,
        **kwargs,
    ) -> CustomerAutomationProfile:
        """
        Create a CustomerAutomationProfile with configurable thresholds.

        Args:
            customer: Customer to create profile for
            automation_stage: Trust calibration stage:
                - observe: AI recommends, human acts
                - suggest: AI pre-fills, human confirms
                - act_notify: AI executes, human notified
                - full_autonomy: AI executes silently
            auto_execute_confidence: Minimum confidence for Tier 1 (auto-execute)
            auto_execute_max_amount: Maximum dollar amount for Tier 1
            queue_review_min_confidence: Minimum confidence for Tier 2 (review)
            queue_review_max_amount: Maximum amount before escalation
            escalate_min_amount: Dollar amount triggering escalation
            shadow_mode_enabled: Whether shadow mode is active

        Returns:
            Created CustomerAutomationProfile instance
        """
        defaults = {
            "auto_submit_claims": False,
            "auto_check_status": True,
            "auto_verify_eligibility": True,
            "auto_submit_prior_auth": False,
            "auto_modify_codes": False,
            "auto_submit_appeals": False,  # Always false by regulation
            "shadow_mode_min_accuracy": 0.95,
            "notify_on_auto_execute": False,
            "notify_on_escalation": True,
            "notification_email": "",
            "undo_window_hours": 2,
            "audit_all_actions": True,
        }
        defaults.update(kwargs)

        return CustomerAutomationProfile.objects.create(
            customer=customer,
            automation_stage=automation_stage,
            auto_execute_confidence=auto_execute_confidence,
            auto_execute_max_amount=auto_execute_max_amount,
            queue_review_min_confidence=queue_review_min_confidence,
            queue_review_max_amount=queue_review_max_amount,
            escalate_min_amount=escalate_min_amount,
            shadow_mode_enabled=shadow_mode_enabled,
            **defaults,
        )

    def create_shadow_result(
        self,
        customer: Customer,
        claim_score: Optional[ClaimScore] = None,
        human_decision_user: Optional[User] = None,
        ai_recommended_action: str = "queue_review",
        ai_confidence: float = 0.85,
        human_action_taken: str = "queue_review",
        actions_match: bool = True,
        outcome: str = "true_positive",
        **kwargs,
    ) -> ShadowModeResult:
        """
        Create a ShadowModeResult for testing accuracy calculations.

        Args:
            customer: Customer who owns this result
            claim_score: Associated ClaimScore (created if not provided)
            human_decision_user: User who made the human decision
            ai_recommended_action: What AI recommended
            ai_confidence: AI's confidence in recommendation
            human_action_taken: What human actually did
            actions_match: Whether AI matched human decision
            outcome: Classification of result:
                - true_positive: AI correct
                - true_negative: AI correct
                - false_positive: AI wrong
                - false_negative: AI wrong

        Returns:
            Created ShadowModeResult instance
        """
        if claim_score is None:
            claim_score = self.create_claim_score(
                customer=customer,
                overall_confidence=ai_confidence,
                recommended_action=ai_recommended_action,
            )

        if human_decision_user is None:
            human_decision_user = self.create_user(
                customer, username=f"reviewer_{customer.id}"
            )

        defaults = {
            "human_decision_timestamp": timezone.now(),
            "discrepancy_reason": "" if actions_match else "Test discrepancy reason",
        }
        defaults.update(kwargs)

        return ShadowModeResult.objects.create(
            customer=customer,
            claim_score=claim_score,
            ai_recommended_action=ai_recommended_action,
            ai_confidence=ai_confidence,
            human_action_taken=human_action_taken,
            human_decision_user=human_decision_user,
            actions_match=actions_match,
            outcome=outcome,
            **defaults,
        )

    # =================================================================
    # EHR Integration Fixtures (Milestone 04)
    # =================================================================

    def create_ehr_connection(
        self,
        customer: Customer,
        name: str = "Test EHR Connection",
        ehr_type: str = "epic",
        client_id: str = "test-client-id",
        client_secret: str = "test-client-secret",
        oauth_endpoint: str = "https://fhir.epic.com/oauth2/token",
        fhir_endpoint: str = "https://fhir.epic.com/api/FHIR/R4",
        enabled: bool = True,
        health_status: str = "healthy",
        **kwargs,
    ) -> EHRConnection:
        """
        Create a test EHRConnection for EHR integration testing.

        Args:
            customer: Customer who owns this connection
            name: Friendly name for the connection
            ehr_type: EHR vendor type (epic, cerner, athena)
            client_id: OAuth 2.0 client ID
            client_secret: OAuth 2.0 client secret (encrypted at rest)
            oauth_endpoint: OAuth 2.0 token endpoint URL
            fhir_endpoint: FHIR API base URL
            enabled: Whether connection is active
            health_status: Current connection health (healthy, degraded, unhealthy, unknown)

        Returns:
            Created EHRConnection instance
        """
        return EHRConnection.objects.create(
            customer=customer,
            name=name,
            ehr_type=ehr_type,
            client_id=client_id,
            client_secret=client_secret,
            oauth_endpoint=oauth_endpoint,
            fhir_endpoint=fhir_endpoint,
            enabled=enabled,
            health_status=health_status,
            **kwargs,
        )

    def create_ehr_sync_log(
        self,
        connection: EHRConnection,
        status: str = "success",
        records_fetched: int = 100,
        records_created: int = 95,
        records_updated: int = 3,
        records_skipped: int = 2,
        error_message: Optional[str] = None,
        **kwargs,
    ) -> EHRSyncLog:
        """
        Create a test EHRSyncLog for sync audit tracking.

        Args:
            connection: EHRConnection this log is for
            status: Sync status (success, error, partial)
            records_fetched: Number of records fetched from EHR
            records_created: Number of ClaimRecords created
            records_updated: Number of ClaimRecords updated
            records_skipped: Number of records skipped (duplicates)
            error_message: Error details if sync failed

        Returns:
            Created EHRSyncLog instance
        """
        defaults = {
            "completed_at": timezone.now() if status == "success" else None,
            "sync_metadata": {"page_count": 2, "last_cursor": "abc123"},
        }
        defaults.update(kwargs)

        return EHRSyncLog.objects.create(
            connection=connection,
            status=status,
            records_fetched=records_fetched,
            records_created=records_created,
            records_updated=records_updated,
            records_skipped=records_skipped,
            error_message=error_message,
            **defaults,
        )
