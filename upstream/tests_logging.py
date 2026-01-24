"""
Tests for structured logging utilities.

Tests the logging context management, formatters, and middleware.
"""

import logging
from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User

from upstream.models import Customer, UserProfile
from upstream.logging_utils import (
    get_logger,
    set_log_context,
    clear_log_context,
    get_log_context,
    add_log_context,
    extract_request_context,
    StructuredLogFormatter,
)
from upstream.middleware import StructuredLoggingMiddleware


class LoggingContextTests(TestCase):
    """Tests for logging context management."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear any existing context
        clear_log_context()

    def tearDown(self):
        """Clean up after tests."""
        clear_log_context()

    def test_set_and_get_context(self):
        """Context can be set and retrieved."""
        set_log_context(customer_id=123, user_id=456)
        context = get_log_context()

        self.assertEqual(context['customer_id'], 123)
        self.assertEqual(context['user_id'], 456)

    def test_clear_context(self):
        """Context can be cleared."""
        set_log_context(customer_id=123)
        self.assertIn('customer_id', get_log_context())

        clear_log_context()
        self.assertEqual(get_log_context(), {})

    def test_context_manager(self):
        """Context manager adds and restores context."""
        # Set initial context
        set_log_context(customer_id=123)

        # Add temporary context
        with add_log_context(user_id=456, operation='test'):
            context = get_log_context()
            self.assertEqual(context['customer_id'], 123)
            self.assertEqual(context['user_id'], 456)
            self.assertEqual(context['operation'], 'test')

        # Context should be restored (customer_id remains, user_id removed)
        context = get_log_context()
        self.assertEqual(context['customer_id'], 123)
        self.assertNotIn('user_id', context)
        self.assertNotIn('operation', context)

    def test_nested_context_managers(self):
        """Nested context managers work correctly."""
        with add_log_context(level1='a'):
            self.assertEqual(get_log_context()['level1'], 'a')

            with add_log_context(level2='b'):
                context = get_log_context()
                self.assertEqual(context['level1'], 'a')
                self.assertEqual(context['level2'], 'b')

            # Inner context removed
            context = get_log_context()
            self.assertEqual(context['level1'], 'a')
            self.assertNotIn('level2', context)

        # All context removed
        self.assertEqual(get_log_context(), {})


class RequestContextExtractionTests(TestCase):
    """Tests for extracting context from HTTP requests."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.customer = Customer.objects.create(name='Test Hospital')
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass'
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            customer=self.customer
        )

    def test_extract_context_from_authenticated_request(self):
        """Context is extracted from authenticated request."""
        request = self.factory.get('/api/v1/dashboard/')
        request.user = self.user

        context = extract_request_context(request)

        self.assertEqual(context['user_id'], self.user.id)
        self.assertEqual(context['username'], 'testuser')
        self.assertEqual(context['customer_id'], self.customer.id)
        self.assertEqual(context['customer_name'], 'Test Hospital')
        self.assertEqual(context['method'], 'GET')
        self.assertEqual(context['path'], '/api/v1/dashboard/')

    def test_extract_context_from_unauthenticated_request(self):
        """Context is extracted from unauthenticated request."""
        from django.contrib.auth.models import AnonymousUser

        request = self.factory.get('/api/v1/health/')
        request.user = AnonymousUser()

        context = extract_request_context(request)

        # Should not include user/customer info
        self.assertNotIn('user_id', context)
        self.assertNotIn('customer_id', context)

        # Should include request metadata
        self.assertEqual(context['method'], 'GET')
        self.assertEqual(context['path'], '/api/v1/health/')

    def test_extract_context_includes_ip_address(self):
        """Context includes client IP address."""
        request = self.factory.get('/')
        request.user = self.user

        # Simulate X-Forwarded-For header
        request.META['HTTP_X_FORWARDED_FOR'] = '192.168.1.100, 10.0.0.1'

        context = extract_request_context(request)

        # Should extract first IP from X-Forwarded-For
        self.assertEqual(context['ip'], '192.168.1.100')


class StructuredLogFormatterTests(TestCase):
    """Tests for structured log formatter."""

    def setUp(self):
        """Set up test fixtures."""
        self.formatter = StructuredLogFormatter()

    def test_format_simple_message(self):
        """Simple messages are formatted correctly."""
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg='Test message',
            args=(),
            exc_info=None
        )

        formatted = self.formatter.format(record)

        self.assertIn('INFO', formatted)
        # Message with spaces is quoted
        self.assertIn('message="Test message"', formatted)

    def test_format_message_with_context(self):
        """Messages with context include all fields."""
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg='Processing upload',
            args=(),
            exc_info=None
        )

        # Add context fields
        record.customer_id = 123
        record.user_id = 456
        record.request_id = 'abc-def'

        formatted = self.formatter.format(record)

        self.assertIn('customer_id=123', formatted)
        self.assertIn('user_id=456', formatted)
        self.assertIn('request_id=abc-def', formatted)
        # Message with spaces is quoted
        self.assertIn('message="Processing upload"', formatted)

    def test_format_message_with_spaces(self):
        """Messages with spaces are quoted."""
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg='Upload processing complete',
            args=(),
            exc_info=None
        )

        formatted = self.formatter.format(record)

        # Message with spaces should be quoted
        self.assertIn('message="Upload processing complete"', formatted)


class LoggerAdapterTests(TestCase):
    """Tests for contextual logger adapter."""

    def setUp(self):
        """Set up test fixtures."""
        clear_log_context()

    def tearDown(self):
        """Clean up after tests."""
        clear_log_context()

    def test_logger_includes_context(self):
        """Logger automatically includes context in log records."""
        import io

        # Set up context
        set_log_context(customer_id=123, user_id=456)

        # Create logger with string handler
        logger = get_logger('test')
        handler = logging.StreamHandler(io.StringIO())
        handler.setFormatter(StructuredLogFormatter())
        logger.logger.addHandler(handler)
        logger.logger.setLevel(logging.INFO)

        # Log a message
        logger.info("Test message")

        # Get the formatted output
        output = handler.stream.getvalue()

        # Should include context
        self.assertIn('customer_id=123', output)
        self.assertIn('user_id=456', output)
        # Message with spaces is quoted
        self.assertIn('message="Test message"', output)


class StructuredLoggingMiddlewareTests(TestCase):
    """Tests for structured logging middleware."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.customer = Customer.objects.create(name='Test Hospital')
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass'
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            customer=self.customer
        )

        # Create mock get_response function
        def mock_get_response(request):
            from django.http import HttpResponse
            return HttpResponse("OK")

        self.get_response = mock_get_response
        self.middleware = StructuredLoggingMiddleware(self.get_response)

    def test_middleware_sets_context(self):
        """Middleware sets logging context from request."""
        request = self.factory.get('/api/v1/dashboard/')
        request.user = self.user

        # Clear context before test
        clear_log_context()

        # Process request through middleware
        self.middleware(request)

        # Context should be set during request processing
        # Note: Context is cleared after request, so we can't test it here
        # This test verifies middleware doesn't crash

    def test_middleware_clears_context_after_request(self):
        """Middleware clears context after request completes."""
        request = self.factory.get('/api/v1/dashboard/')
        request.user = self.user

        # Process request
        self.middleware(request)

        # Context should be cleared
        self.assertEqual(get_log_context(), {})

    def test_middleware_handles_exceptions(self):
        """Middleware handles exceptions gracefully."""
        def failing_get_response(request):
            raise ValueError("Test error")

        middleware = StructuredLoggingMiddleware(failing_get_response)

        request = self.factory.get('/api/v1/test/')
        request.user = self.user

        # Should raise exception but not crash on logging
        with self.assertRaises(ValueError):
            middleware(request)

        # Context should still be cleared
        self.assertEqual(get_log_context(), {})


# =============================================================================
# PHI/PII Scrubbing Tests
# =============================================================================

from upstream.logging_filters import (
    PHIScrubberFilter,
    AggressivePHIScrubberFilter,
    SelectivePHIScrubberFilter,
    scrub_dict,
    is_phi_present,
)


class PHIScrubberFilterTests(TestCase):
    """Tests for PHI/PII scrubbing filter."""

    def setUp(self):
        """Set up test fixtures."""
        self.scrubber = PHIScrubberFilter()

    def test_scrub_ssn_dashed(self):
        """SSN with dashes is scrubbed."""
        text = "Patient SSN: 123-45-6789"
        scrubbed = self.scrubber.scrub_phi(text)

        self.assertIn('[REDACTED_SSN]', scrubbed)
        self.assertNotIn('123-45-6789', scrubbed)

    def test_scrub_ssn_no_dashes(self):
        """SSN without dashes is scrubbed."""
        text = "SSN 123456789 found"
        scrubbed = self.scrubber.scrub_phi(text)

        self.assertIn('[REDACTED_SSN]', scrubbed)
        self.assertNotIn('123456789', scrubbed)

    def test_scrub_mrn(self):
        """Medical record number is scrubbed."""
        text = "MRN: ABC-123-456"
        scrubbed = self.scrubber.scrub_phi(text)

        self.assertIn('[REDACTED_MRN]', scrubbed)
        self.assertNotIn('ABC-123-456', scrubbed)

    def test_scrub_dob(self):
        """Date of birth is scrubbed."""
        text = "DOB: 01/15/1990"
        scrubbed = self.scrubber.scrub_phi(text)

        self.assertIn('[REDACTED_DOB]', scrubbed)
        self.assertNotIn('01/15/1990', scrubbed)

    def test_scrub_phone_number(self):
        """Phone number is scrubbed."""
        text = "Call 555-123-4567 for results"
        scrubbed = self.scrubber.scrub_phi(text)

        self.assertIn('[REDACTED_PHONE]', scrubbed)
        self.assertNotIn('555-123-4567', scrubbed)

    def test_scrub_email(self):
        """Email address is scrubbed."""
        text = "Contact patient@example.com"
        scrubbed = self.scrubber.scrub_phi(text)

        self.assertIn('[REDACTED_EMAIL]', scrubbed)
        self.assertNotIn('patient@example.com', scrubbed)

    def test_scrub_patient_name(self):
        """Patient name is scrubbed."""
        text = "Patient Name: John Doe"
        scrubbed = self.scrubber.scrub_phi(text)

        self.assertIn('[REDACTED_NAME]', scrubbed)
        self.assertNotIn('John Doe', scrubbed)

    def test_scrub_address(self):
        """Physical address is scrubbed."""
        text = "Lives at 123 Main Street"
        scrubbed = self.scrubber.scrub_phi(text)

        self.assertIn('[REDACTED_ADDRESS]', scrubbed)
        self.assertNotIn('123 Main Street', scrubbed)

    def test_scrub_credit_card(self):
        """Credit card number is scrubbed."""
        text = "Card: 1234-5678-9012-3456"
        scrubbed = self.scrubber.scrub_phi(text)

        self.assertIn('[REDACTED_CC]', scrubbed)
        self.assertNotIn('1234-5678-9012-3456', scrubbed)

    def test_scrub_multiple_phi_types(self):
        """Multiple PHI types in same text are scrubbed."""
        text = "Patient Name: John Doe, SSN 123-45-6789, phone 555-123-4567"
        scrubbed = self.scrubber.scrub_phi(text)

        self.assertIn('[REDACTED_NAME]', scrubbed)
        self.assertIn('[REDACTED_SSN]', scrubbed)
        self.assertIn('[REDACTED_PHONE]', scrubbed)
        self.assertNotIn('John Doe', scrubbed)
        self.assertNotIn('123-45-6789', scrubbed)
        self.assertNotIn('555-123-4567', scrubbed)

    def test_scrub_safe_text_unchanged(self):
        """Safe text without PHI is not modified."""
        text = "Processing upload complete"
        scrubbed = self.scrubber.scrub_phi(text)

        self.assertEqual(text, scrubbed)

    def test_filter_scrubs_log_record(self):
        """Logging filter scrubs PHI from log records."""
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg='Patient SSN: 123-45-6789',
            args=(),
            exc_info=None
        )

        # Apply filter
        self.scrubber.filter(record)

        # Message should be scrubbed
        self.assertIn('[REDACTED_SSN]', record.msg)
        self.assertNotIn('123-45-6789', record.msg)


class AggressivePHIScrubberTests(TestCase):
    """Tests for aggressive PHI scrubber."""

    def setUp(self):
        """Set up test fixtures."""
        self.scrubber = AggressivePHIScrubberFilter()

    def test_scrubs_ip_addresses(self):
        """Aggressive scrubber redacts IP addresses."""
        text = "Request from 192.168.1.100"
        scrubbed = self.scrubber.scrub_phi(text)

        self.assertIn('[REDACTED_IP]', scrubbed)
        self.assertNotIn('192.168.1.100', scrubbed)

    def test_scrubs_potential_names(self):
        """Aggressive scrubber redacts potential names."""
        text = "Processed by Alice Johnson"
        scrubbed = self.scrubber.scrub_phi(text)

        self.assertIn('[REDACTED_NAME]', scrubbed)
        self.assertNotIn('Alice Johnson', scrubbed)


class SelectivePHIScrubberTests(TestCase):
    """Tests for selective PHI scrubber."""

    def setUp(self):
        """Set up test fixtures."""
        self.scrubber = SelectivePHIScrubberFilter()

    def test_scrubs_high_risk_phi(self):
        """Selective scrubber redacts high-risk PHI."""
        text = "SSN: 123-45-6789"
        scrubbed = self.scrubber.scrub_phi(text)

        self.assertIn('[REDACTED_SSN]', scrubbed)
        self.assertNotIn('123-45-6789', scrubbed)

    def test_preserves_low_risk_phi(self):
        """Selective scrubber preserves phone and email for debugging."""
        text = "Contact: user@example.com or 555-123-4567"
        scrubbed = self.scrubber.scrub_phi(text)

        # Phone and email should NOT be redacted in selective mode
        self.assertIn('user@example.com', scrubbed)
        self.assertIn('555-123-4567', scrubbed)


class PHIHelperFunctionTests(TestCase):
    """Tests for PHI scrubbing helper functions."""

    def test_scrub_dict_simple(self):
        """scrub_dict scrubs PHI from dictionary."""
        data = {
            'patient_phone': '555-123-4567',
            'ssn': '123-45-6789',
            'safe_field': 'Processing complete'
        }

        scrubbed = scrub_dict(data)

        self.assertEqual(scrubbed['safe_field'], 'Processing complete')
        self.assertIn('[REDACTED_PHONE]', scrubbed['patient_phone'])
        self.assertIn('[REDACTED_SSN]', scrubbed['ssn'])

    def test_scrub_dict_nested(self):
        """scrub_dict handles nested dictionaries."""
        data = {
            'patient': {
                'email': 'patient@example.com',
                'ssn': '987-65-4321',
            },
            'status': 'active'
        }

        scrubbed = scrub_dict(data)

        self.assertEqual(scrubbed['status'], 'active')
        self.assertIn('[REDACTED_EMAIL]', scrubbed['patient']['email'])
        self.assertIn('[REDACTED_SSN]', scrubbed['patient']['ssn'])

    def test_scrub_dict_with_lists(self):
        """scrub_dict handles lists in dictionary."""
        data = {
            'contacts': ['555-123-4567', '555-987-6543'],
            'status': 'processing'
        }

        scrubbed = scrub_dict(data)

        self.assertEqual(scrubbed['status'], 'processing')
        self.assertIn('[REDACTED_PHONE]', scrubbed['contacts'][0])
        self.assertIn('[REDACTED_PHONE]', scrubbed['contacts'][1])

    def test_is_phi_present_true(self):
        """is_phi_present detects PHI in text."""
        text = "SSN: 123-45-6789"
        self.assertTrue(is_phi_present(text))

    def test_is_phi_present_false(self):
        """is_phi_present returns False for safe text."""
        text = "Processing upload complete"
        self.assertFalse(is_phi_present(text))
