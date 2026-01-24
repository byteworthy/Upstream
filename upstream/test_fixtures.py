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
    Customer, UserProfile, Upload, ClaimRecord,
    ReportRun, DriftEvent
)
from upstream.alerts.models import AlertRule, AlertEvent, NotificationChannel


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

    def create_customer(self, name: str = 'Test Hospital') -> Customer:
        """Create a test customer."""
        return Customer.objects.create(name=name)

    def create_user(
        self,
        customer: Customer,
        username: str = 'testuser',
        password: str = 'testpass123',
        email: Optional[str] = None,
        role: str = 'user'
    ) -> User:
        """Create a test user linked to a customer."""
        if email is None:
            email = f'{username}@example.com'

        user = User.objects.create_user(
            username=username,
            password=password,
            email=email
        )

        UserProfile.objects.create(
            user=user,
            customer=customer,
            role=role
        )

        return user

    def create_upload(
        self,
        customer: Customer,
        filename: str = 'test.csv',
        status: str = 'success',
        row_count: int = 100,
        **kwargs
    ) -> Upload:
        """Create a test upload."""
        return Upload.all_objects.create(
            customer=customer,
            filename=filename,
            status=status,
            row_count=row_count,
            **kwargs
        )

    def create_claims(
        self,
        customer: Customer,
        payer: str = 'Medicare',
        cpt_group: str = 'SURGERY',
        count: int = 100,
        outcome_ratio: float = 0.5,
        base_date: Optional[date] = None,
        **kwargs
    ) -> List[ClaimRecord]:
        """Create test claim records."""
        if base_date is None:
            base_date = timezone.now().date()

        claims = []
        for i in range(count):
            outcome = 'PAID' if i < (count * outcome_ratio) else 'DENIED'
            days_ago = i % 30
            submitted_date = base_date - timedelta(days=days_ago)
            decided_date = submitted_date + timedelta(days=7)

            claim = ClaimRecord.all_objects.create(
                customer=customer,
                payer=payer,
                cpt='99213',
                cpt_group=cpt_group,
                outcome=outcome,
                submitted_date=submitted_date,
                decided_date=decided_date,
                allowed_amount=Decimal('150.00') if outcome == 'PAID' else Decimal('0.00'),
                **kwargs
            )
            claims.append(claim)

        return claims

    def create_report_run(
        self,
        customer: Customer,
        status: str = 'success',
        run_type: str = 'weekly',
        **kwargs
    ) -> ReportRun:
        """Create a test report run."""
        defaults = {
            'started_at': timezone.now() - timedelta(hours=1),
            'finished_at': timezone.now(),
            'summary_json': {'events_created': 0}
        }
        defaults.update(kwargs)

        return ReportRun.all_objects.create(
            customer=customer,
            run_type=run_type,
            status=status,
            **defaults
        )

    def create_drift_event(
        self,
        customer: Customer,
        report_run: Optional[ReportRun] = None,
        payer: str = 'Medicare',
        cpt_group: str = 'SURGERY',
        drift_type: str = 'DENIAL_RATE',
        severity: float = 0.75,
        **kwargs
    ) -> DriftEvent:
        """Create a test drift event."""
        if report_run is None:
            report_run = self.create_report_run(customer)

        defaults = {
            'baseline_value': 0.15,
            'current_value': 0.35,
            'delta_value': 0.20,
            'confidence': 0.90,
            'baseline_start': timezone.now().date() - timedelta(days=104),
            'baseline_end': timezone.now().date() - timedelta(days=14),
            'current_start': timezone.now().date() - timedelta(days=14),
            'current_end': timezone.now().date()
        }
        defaults.update(kwargs)

        return DriftEvent.all_objects.create(
            customer=customer,
            report_run=report_run,
            payer=payer,
            cpt_group=cpt_group,
            drift_type=drift_type,
            severity=severity,
            **defaults
        )

    def create_alert_rule(
        self,
        customer: Customer,
        name: str = 'Test Alert Rule',
        metric: str = 'severity',
        threshold_value: float = 0.7,
        severity: str = 'critical',
        **kwargs
    ) -> AlertRule:
        """Create a test alert rule."""
        return AlertRule.all_objects.create(
            customer=customer,
            name=name,
            metric=metric,
            threshold_value=threshold_value,
            severity=severity,
            enabled=True,
            **kwargs
        )

    def create_alert_event(
        self,
        customer: Customer,
        alert_rule: AlertRule,
        drift_event: Optional[DriftEvent] = None,
        report_run: Optional[ReportRun] = None,
        status: str = 'pending',
        **kwargs
    ) -> AlertEvent:
        """Create a test alert event."""
        if drift_event is None:
            drift_event = self.create_drift_event(customer, report_run=report_run)

        if report_run is None:
            report_run = drift_event.report_run

        defaults = {
            'payload': {
                'payer': drift_event.payer,
                'drift_type': drift_event.drift_type,
                'severity': drift_event.severity,
            }
        }
        defaults.update(kwargs)

        return AlertEvent.all_objects.create(
            customer=customer,
            alert_rule=alert_rule,
            drift_event=drift_event,
            report_run=report_run,
            status=status,
            **defaults
        )

    def create_notification_channel(
        self,
        customer: Customer,
        name: str = 'Test Channel',
        channel_type: str = 'email',
        config: Optional[dict] = None,
        **kwargs
    ) -> NotificationChannel:
        """Create a test notification channel."""
        if config is None:
            if channel_type == 'email':
                config = {'recipients': ['test@example.com']}
            elif channel_type == 'slack':
                config = {'webhook_url': 'https://hooks.slack.com/test'}
            else:
                config = {}

        return NotificationChannel.all_objects.create(
            customer=customer,
            name=name,
            channel_type=channel_type,
            config=config,
            enabled=True,
            **kwargs
        )
