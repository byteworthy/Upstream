"""
Smoke tests for email functionality to ensure proper configuration and template rendering.
"""

from django.core import mail
from django.test import TestCase, override_settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

class EmailSmokeTest(TestCase):
    """Test email backend configuration and basic functionality."""

    def test_email_backend_configuration(self):
        """Test that email backend is properly configured."""
        # This test ensures no import errors and basic email functionality works
        self.assertIsNotNone(mail.get_connection())

    def test_send_simple_email(self):
        """Test sending a simple email using Django's mail outbox."""
        # Send a test email
        email = EmailMessage(
            subject="Test Email",
            body="This is a test email body.",
            from_email="test@upstream.cx",
            to=["recipient@upstream.cx"],
        )
        email.send()

        # Check that the email was sent (using test outbox)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Test Email")
        self.assertEqual(mail.outbox[0].body, "This is a test email body.")
        self.assertEqual(mail.outbox[0].from_email, "test@upstream.cx")
        self.assertEqual(mail.outbox[0].to, ["recipient@upstream.cx"])

    def test_email_template_rendering(self):
        """Test that email templates can be rendered properly."""
        # Test rendering a simple template
        context = {
            "title": "Test Alert",
            "message": "This is a test alert message.",
            "details": "Additional details about the alert."
        }

        # Render template content
        html_content = render_to_string("email_test_template.html", context)

        # Verify the template was rendered with the context
        self.assertIn("Test Alert", html_content)
        self.assertIn("This is a test alert message", html_content)
        self.assertIn("Additional details about the alert", html_content)

    def test_email_with_html_content(self):
        """Test sending an email with HTML content."""
        html_content = "<h1>Test HTML Email</h1><p>This is HTML content.</p>"

        email = EmailMessage(
            subject="HTML Test Email",
            body="This is the plain text version.",
            from_email="test@upstream.cx",
            to=["recipient@upstream.cx"],
        )
        email.content_subtype = "html"
        email.body = html_content
        email.send()

        # Check that the HTML email was sent
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "HTML Test Email")
        self.assertIn("<h1>Test HTML Email</h1>", mail.outbox[0].body)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_email_backend_switching(self):
        """Test that email backend can be switched without errors."""
        # This test ensures that switching between backends works
        email = EmailMessage(
            subject="Backend Switch Test",
            body="Testing backend switching.",
            from_email="test@upstream.cx",
            to=["test@upstream.cx"],
        )
        email.send()

        # Verify email was sent with the overridden backend
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Backend Switch Test")
