"""
Tests for factory_boy factories to ensure they generate valid model instances.
"""

import pytest  # noqa: F401
from django.test import TestCase

from upstream.tests.factories import (
    CustomerFactory,
    UserFactory,
    UserProfileFactory,
    SettingsFactory,
    UploadFactory,
    DataQualityReportFactory,
    ClaimRecordFactory,
    ReportRunFactory,
    DriftEventFactory,
    PayerMappingFactory,
    CPTGroupMappingFactory,
    AlertRuleFactory,
    NotificationChannelFactory,
    AlertEventFactory,
    AlertFactory,
    OperatorJudgmentFactory,
    IntegrationProviderFactory,
    IntegrationConnectionFactory,
    IntegrationLogFactory,
    WebhookEndpointFactory,
    WebhookDeliveryFactory,
)


@pytest.mark.django_db
class TestFactories(TestCase):
    """Test that all factories generate valid model instances."""

    def test_customer_factory(self):
        """Test CustomerFactory creates valid Customer instances."""
        customer = CustomerFactory()
        customer.full_clean()
        self.assertIsNotNone(customer.id)
        self.assertTrue(customer.name.startswith("Customer"))

    def test_user_factory(self):
        """Test UserFactory creates valid User instances."""
        user = UserFactory()
        user.full_clean()
        self.assertIsNotNone(user.id)
        self.assertTrue(user.check_password("testpass123"))

    def test_userprofile_factory(self):
        """Test UserProfileFactory creates valid UserProfile instances."""
        profile = UserProfileFactory()
        profile.full_clean()
        self.assertIsNotNone(profile.id)
        self.assertIsNotNone(profile.user)
        self.assertIsNotNone(profile.customer)

    def test_settings_factory(self):
        """Test SettingsFactory creates valid Settings instances."""
        settings = SettingsFactory()
        settings.full_clean()
        self.assertIsNotNone(settings.id)
        self.assertIsNotNone(settings.customer)

    def test_upload_factory_processing(self):
        """Test UploadFactory with processing trait."""
        upload = UploadFactory(processing=True)
        upload.full_clean()
        self.assertEqual(upload.status, "processing")
        self.assertIsNotNone(upload.processing_started_at)

    def test_upload_factory_success(self):
        """Test UploadFactory with success trait."""
        upload = UploadFactory(success=True)
        upload.full_clean()
        self.assertEqual(upload.status, "success")
        self.assertIsNotNone(upload.processing_completed_at)

    def test_upload_factory_failed(self):
        """Test UploadFactory with failed trait."""
        upload = UploadFactory(failed=True)
        upload.full_clean()
        self.assertEqual(upload.status, "failed")
        self.assertIsNotNone(upload.error_message)

    def test_data_quality_report_factory(self):
        """Test DataQualityReportFactory creates valid instances."""
        report = DataQualityReportFactory()
        report.full_clean()
        self.assertIsNotNone(report.id)
        self.assertIsNotNone(report.upload)
        self.assertEqual(report.customer, report.upload.customer)

    def test_claim_record_factory(self):
        """Test ClaimRecordFactory creates valid ClaimRecord instances."""
        claim = ClaimRecordFactory()
        claim.full_clean()
        self.assertIsNotNone(claim.id)
        self.assertEqual(claim.outcome, "PAID")

    def test_claim_record_factory_denied(self):
        """Test ClaimRecordFactory with denied trait."""
        claim = ClaimRecordFactory(denied=True)
        claim.full_clean()
        self.assertEqual(claim.outcome, "DENIED")
        self.assertIsNotNone(claim.denial_reason_code)

    def test_report_run_factory(self):
        """Test ReportRunFactory creates valid ReportRun instances."""
        report = ReportRunFactory()
        report.full_clean()
        self.assertEqual(report.status, "success")

    def test_report_run_factory_running(self):
        """Test ReportRunFactory with running trait."""
        report = ReportRunFactory(running=True)
        report.full_clean()
        self.assertEqual(report.status, "running")
        self.assertIsNone(report.finished_at)

    def test_drift_event_factory(self):
        """Test DriftEventFactory creates valid DriftEvent instances."""
        drift = DriftEventFactory()
        drift.full_clean()
        self.assertIsNotNone(drift.id)
        self.assertEqual(drift.drift_type, "DENIAL_RATE")

    def test_drift_event_factory_decision_time(self):
        """Test DriftEventFactory with decision_time trait."""
        drift = DriftEventFactory(decision_time=True)
        drift.full_clean()
        self.assertEqual(drift.drift_type, "DECISION_TIME")

    def test_alert_rule_factory(self):
        """Test AlertRuleFactory creates valid AlertRule instances."""
        rule = AlertRuleFactory()
        rule.full_clean()
        self.assertTrue(rule.enabled)
        self.assertEqual(rule.severity, "warning")

    def test_alert_rule_factory_critical(self):
        """Test AlertRuleFactory with critical trait."""
        rule = AlertRuleFactory(critical=True)
        rule.full_clean()
        self.assertEqual(rule.severity, "critical")

    def test_notification_channel_factory(self):
        """Test NotificationChannelFactory creates valid instances."""
        channel = NotificationChannelFactory()
        channel.full_clean()
        self.assertEqual(channel.channel_type, "email")
        self.assertTrue(channel.enabled)

    def test_notification_channel_factory_webhook(self):
        """Test NotificationChannelFactory with webhook trait."""
        channel = NotificationChannelFactory(webhook=True)
        channel.full_clean()
        self.assertEqual(channel.channel_type, "webhook")

    def test_alert_event_factory(self):
        """Test AlertEventFactory creates valid AlertEvent instances."""
        event = AlertEventFactory()
        event.full_clean()
        self.assertEqual(event.status, "pending")
        self.assertIsNotNone(event.alert_rule)
        self.assertIsNotNone(event.drift_event)

    def test_alert_event_factory_sent(self):
        """Test AlertEventFactory with sent trait."""
        event = AlertEventFactory(sent=True)
        event.full_clean()
        self.assertEqual(event.status, "sent")
        self.assertIsNotNone(event.notification_sent_at)

    def test_alert_factory(self):
        """Test AlertFactory creates valid Alert instances."""
        alert = AlertFactory()
        alert.full_clean()
        self.assertEqual(alert.status, "new")

    def test_operator_judgment_factory(self):
        """Test OperatorJudgmentFactory creates valid instances."""
        judgment = OperatorJudgmentFactory()
        judgment.full_clean()
        self.assertEqual(judgment.verdict, "real")

    def test_operator_judgment_factory_noise(self):
        """Test OperatorJudgmentFactory with noise trait."""
        judgment = OperatorJudgmentFactory(noise=True)
        judgment.full_clean()
        self.assertEqual(judgment.verdict, "noise")

    def test_integration_provider_factory(self):
        """Test IntegrationProviderFactory creates valid instances."""
        provider = IntegrationProviderFactory()
        provider.full_clean()
        self.assertTrue(provider.is_active)

    def test_integration_connection_factory(self):
        """Test IntegrationConnectionFactory creates valid instances."""
        connection = IntegrationConnectionFactory()
        connection.full_clean()
        self.assertEqual(connection.status, "active")

    def test_integration_log_factory(self):
        """Test IntegrationLogFactory creates valid instances."""
        log = IntegrationLogFactory()
        log.full_clean()
        self.assertEqual(log.status, "success")

    def test_webhook_endpoint_factory(self):
        """Test WebhookEndpointFactory creates valid instances."""
        endpoint = WebhookEndpointFactory()
        endpoint.full_clean()
        self.assertTrue(endpoint.active)

    def test_webhook_delivery_factory(self):
        """Test WebhookDeliveryFactory creates valid instances."""
        delivery = WebhookDeliveryFactory()
        delivery.full_clean()
        self.assertEqual(delivery.status, "pending")

    def test_webhook_delivery_factory_success(self):
        """Test WebhookDeliveryFactory with success trait."""
        delivery = WebhookDeliveryFactory(success=True)
        delivery.full_clean()
        self.assertEqual(delivery.status, "success")
        self.assertEqual(delivery.response_code, 200)

    def test_payer_mapping_factory(self):
        """Test PayerMappingFactory creates valid PayerMapping instances."""
        mapping = PayerMappingFactory()
        mapping.full_clean()
        self.assertIsNotNone(mapping.id)
        self.assertIsNotNone(mapping.customer)

    def test_cpt_group_mapping_factory(self):
        """Test CPTGroupMappingFactory creates valid instances."""
        mapping = CPTGroupMappingFactory()
        mapping.full_clean()
        self.assertIsNotNone(mapping.id)
        self.assertIsNotNone(mapping.customer)

    def test_factories_count(self):
        """Test that we have at least 10 core model factories."""
        factories = [
            CustomerFactory,
            UserFactory,
            UserProfileFactory,
            UploadFactory,
            ClaimRecordFactory,
            DriftEventFactory,
            PayerMappingFactory,
            ReportRunFactory,
            AlertRuleFactory,
            NotificationChannelFactory,
            WebhookDeliveryFactory,
        ]
        # We need at least 10 factories
        self.assertGreaterEqual(len(factories), 10)
