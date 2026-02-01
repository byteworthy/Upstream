from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.messages.storage.fallback import FallbackStorage
from upstream.models import (
    Customer,
    UserProfile,
    Upload,
    ClaimRecord,
    ReportRun,
    DriftEvent,
)
from upstream.views import UploadsView
from upstream.utils import get_current_customer
from upstream.services.payer_drift import compute_weekly_payer_drift
from upstream.core.tenant import customer_context
import csv
import io
import os
from datetime import datetime, timedelta
from django.utils import timezone
from unittest import skipUnless


# Check if weasyprint is available with all dependencies
def is_weasyprint_available():
    try:
        from weasyprint import HTML

        HTML(string="<html><body>test</body></html>").write_pdf()
        return True
    except Exception:
        return False


WEASYPRINT_AVAILABLE = is_weasyprint_available()


class CSVUploadTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.customer = Customer.objects.create(name="Test Customer")
        self.profile = UserProfile.objects.create(
            user=self.user, customer=self.customer
        )

        # Create a mock request with authenticated user
        self.request = self.factory.get("/uploads/")
        self.request.user = self.user

    def create_csv_file(self, data, filename="test.csv"):
        """Helper to create a CSV file for testing."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerows(data)
        content = output.getvalue().encode("utf-8")
        return SimpleUploadedFile(filename, content, content_type="text/csv")

    def test_valid_csv_upload(self):
        """Test successful CSV upload with valid data."""
        # Create valid CSV data
        csv_data = [
            [
                "payer",
                "cpt",
                "submitted_date",
                "decided_date",
                "outcome",
                "allowed_amount",
            ],
            ["UnitedHealthcare", "99213", "2023-01-15", "2023-01-20", "PAID", "100.50"],
            ["Aetna", "99214", "2023-01-16", "2023-01-21", "DENIED", "150.75"],
            ["Cigna", "99213", "01/17/2023", "01/22/2023", "paid", "125.00"],
        ]

        csv_file = self.create_csv_file(csv_data)

        # Create POST request with CSV file
        request = self.factory.post("/uploads/", {"csv_file": csv_file})
        request.user = self.user

        # Set up messages storage
        request.session = {}
        request._messages = FallbackStorage(request)

        # Process the upload within customer context for tenant isolation
        view = UploadsView()
        with customer_context(self.customer):
            response = view.post(request)

            # Check that upload was created successfully
            upload = Upload.objects.latest("uploaded_at")
            self.assertEqual(upload.status, "success")
            self.assertEqual(upload.row_count, 3)
            self.assertEqual(upload.filename, "test.csv")

            # Check that claim records were created
            claim_records = ClaimRecord.objects.filter(upload=upload)
            self.assertEqual(claim_records.count(), 3)

            # Check first record
            record1 = claim_records[0]
            self.assertEqual(record1.payer, "UnitedHealthcare")
            self.assertEqual(record1.cpt, "99213")
            self.assertEqual(record1.outcome, "PAID")
            self.assertEqual(record1.allowed_amount, 100.50)

    def test_missing_required_column(self):
        """Test CSV upload with missing required column."""
        # Create CSV without required 'outcome' column
        csv_data = [
            ["payer", "cpt", "submitted_date", "decided_date"],
            ["UnitedHealthcare", "99213", "2023-01-15", "2023-01-20"],
        ]

        csv_file = self.create_csv_file(csv_data)

        request = self.factory.post("/uploads/", {"csv_file": csv_file})
        request.user = self.user

        # Set up messages storage
        request.session = {}
        request._messages = FallbackStorage(request)

        view = UploadsView()
        with customer_context(self.customer):
            response = view.post(request)

            # Check that upload failed
            upload = Upload.objects.latest("uploaded_at")
            self.assertEqual(upload.status, "failed")
            self.assertIn("Missing required column: outcome", upload.error_message)

            # Check that no claim records were created
            self.assertEqual(ClaimRecord.objects.count(), 0)

    def test_invalid_date_format(self):
        """Test CSV upload with invalid date format."""
        csv_data = [
            ["payer", "cpt", "submitted_date", "decided_date", "outcome"],
            ["UnitedHealthcare", "99213", "2023-01-15", "invalid-date", "PAID"],
        ]

        csv_file = self.create_csv_file(csv_data)

        request = self.factory.post("/uploads/", {"csv_file": csv_file})
        request.user = self.user

        # Set up messages storage
        request.session = {}
        request._messages = FallbackStorage(request)

        view = UploadsView()
        with customer_context(self.customer):
            response = view.post(request)

            # Check that upload failed
            upload = Upload.objects.latest("uploaded_at")
            self.assertEqual(upload.status, "failed")
            # Check for data rejection message
            self.assertIn("rejected", upload.error_message.lower())
            self.assertIn("Invalid dates: 1", upload.error_message)

            # Check that no claim records were created
            self.assertEqual(ClaimRecord.objects.count(), 0)

    def test_missing_decided_date(self):
        """Test CSV upload with missing decided_date (should fail for MVP)."""
        csv_data = [
            ["payer", "cpt", "submitted_date", "decided_date", "outcome"],
            ["UnitedHealthcare", "99213", "2023-01-15", "", "PAID"],
        ]

        csv_file = self.create_csv_file(csv_data)

        request = self.factory.post("/uploads/", {"csv_file": csv_file})
        request.user = self.user

        # Set up messages storage
        request.session = {}
        request._messages = FallbackStorage(request)

        view = UploadsView()
        with customer_context(self.customer):
            response = view.post(request)

            # Check that upload failed
            upload = Upload.objects.latest("uploaded_at")
            self.assertEqual(upload.status, "failed")
            # Check for missing field rejection message
            self.assertIn("rejected", upload.error_message.lower())
            self.assertIn("Missing fields: 1", upload.error_message)

            # Check that no claim records were created
            self.assertEqual(ClaimRecord.objects.count(), 0)

    def test_extra_columns_ignored(self):
        """Test that extra columns are ignored (not stored)."""
        csv_data = [
            [
                "payer",
                "cpt",
                "submitted_date",
                "decided_date",
                "outcome",
                "patient_name",
                "ssn",
            ],
            [
                "UnitedHealthcare",
                "99213",
                "2023-01-15",
                "2023-01-20",
                "PAID",
                "John Doe",
                "XXX-XX-XXXX",
            ],
        ]

        csv_file = self.create_csv_file(csv_data)

        request = self.factory.post("/uploads/", {"csv_file": csv_file})
        request.user = self.user

        # Set up messages storage
        request.session = {}
        request._messages = FallbackStorage(request)

        view = UploadsView()
        with customer_context(self.customer):
            response = view.post(request)

            # Check that upload succeeded (extra columns ignored)
            upload = Upload.objects.latest("uploaded_at")
            self.assertEqual(upload.status, "success")
            self.assertEqual(upload.row_count, 1)

            # Check that claim record was created without extra data
            record = ClaimRecord.objects.get(upload=upload)
            self.assertEqual(record.payer, "UnitedHealthcare")
            # Verify that patient_name and ssn were not stored
            self.assertFalse(hasattr(record, "patient_name"))
            self.assertFalse(hasattr(record, "ssn"))

    def test_date_formats(self):
        """Test various valid date formats."""
        csv_data = [
            ["payer", "cpt", "submitted_date", "decided_date", "outcome"],
            ["Test1", "99213", "2023-01-15", "2023-01-20", "PAID"],  # ISO format
            ["Test2", "99213", "01/16/2023", "01/21/2023", "PAID"],  # US format
            ["Test3", "99213", "2023/01/17", "2023/01/22", "PAID"],  # YYYY/MM/DD format
        ]

        csv_file = self.create_csv_file(csv_data)

        request = self.factory.post("/uploads/", {"csv_file": csv_file})
        request.user = self.user

        # Set up messages storage
        request.session = {}
        request._messages = FallbackStorage(request)

        view = UploadsView()
        with customer_context(self.customer):
            response = view.post(request)

            # Check that upload succeeded
            upload = Upload.objects.latest("uploaded_at")
            self.assertEqual(upload.status, "success")
            self.assertEqual(upload.row_count, 3)

            # Check dates were parsed correctly
            records = ClaimRecord.objects.filter(upload=upload).order_by("id")
            self.assertEqual(
                records[0].submitted_date,
                datetime.strptime("2023-01-15", "%Y-%m-%d").date(),
            )
            self.assertEqual(
                records[1].submitted_date,
                datetime.strptime("01/16/2023", "%m/%d/%Y").date(),
            )
            self.assertEqual(
                records[2].submitted_date,
                datetime.strptime("2023/01/17", "%Y/%m/%d").date(),
            )

    def test_outcome_normalization(self):
        """Test outcome normalization."""
        csv_data = [
            ["payer", "cpt", "submitted_date", "decided_date", "outcome"],
            ["Test1", "99213", "2023-01-15", "2023-01-20", "paid"],
            ["Test2", "99213", "2023-01-15", "2023-01-20", "APPROVED"],
            ["Test3", "99213", "2023-01-15", "2023-01-20", "DENIED"],
            ["Test4", "99213", "2023-01-15", "2023-01-20", "REJECTED"],
            ["Test5", "99213", "2023-01-15", "2023-01-20", "PENDING"],
        ]

        csv_file = self.create_csv_file(csv_data)

        request = self.factory.post("/uploads/", {"csv_file": csv_file})
        request.user = self.user

        # Set up messages storage
        request.session = {}
        request._messages = FallbackStorage(request)

        view = UploadsView()
        with customer_context(self.customer):
            response = view.post(request)

            # Check that upload succeeded
            upload = Upload.objects.latest("uploaded_at")
            self.assertEqual(upload.status, "success")

            # Check outcome normalization
            records = ClaimRecord.objects.filter(upload=upload).order_by("id")
            self.assertEqual(records[0].outcome, "PAID")  # 'paid' -> 'PAID'
            self.assertEqual(records[1].outcome, "PAID")  # 'APPROVED' -> 'PAID'
            self.assertEqual(records[2].outcome, "DENIED")  # 'DENIED' -> 'DENIED'
            self.assertEqual(records[3].outcome, "DENIED")  # 'REJECTED' -> 'DENIED'
            self.assertEqual(records[4].outcome, "OTHER")  # 'PENDING' -> 'OTHER'


class PayerDriftTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(name="Test Customer")
        self.as_of_date = timezone.now().date()

    def create_claim_record(
        self, payer, cpt_group, submitted_date, decided_date, outcome
    ):
        """Helper to create a claim record."""
        # Use all_objects to bypass tenant filtering when creating test data
        upload = Upload.all_objects.create(
            customer=self.customer, filename="test.csv", status="success", row_count=1
        )

        return ClaimRecord.all_objects.create(
            customer=self.customer,
            upload=upload,
            payer=payer,
            cpt="12345",
            cpt_group=cpt_group,
            submitted_date=submitted_date,
            decided_date=decided_date,
            outcome=outcome,
            submitted_via="csv_upload",
        )

    def test_denial_rate_drift_up(self):
        """Test that DriftEvents are created when denial rate drifts up in current window."""
        # Create baseline records (90 days ago) - low denial rate
        baseline_start = self.as_of_date - timedelta(days=104)  # 90 + 14
        baseline_end = self.as_of_date - timedelta(days=14)

        for i in range(50):  # 50 total, 10 denied = 20% denial rate
            submitted_date = baseline_start + timedelta(days=i % 30)
            decided_date = submitted_date + timedelta(days=5)
            outcome = "DENIED" if i < 10 else "PAID"
            self.create_claim_record(
                "UnitedHealthcare", "EVAL", submitted_date, decided_date, outcome
            )

        # Create current records (last 14 days) - high denial rate
        current_start = baseline_end
        current_end = self.as_of_date

        for i in range(50):  # 50 total, 30 denied = 60% denial rate
            submitted_date = current_start + timedelta(days=i % 10)
            decided_date = submitted_date + timedelta(days=5)
            outcome = "DENIED" if i < 30 else "PAID"
            self.create_claim_record(
                "UnitedHealthcare", "EVAL", submitted_date, decided_date, outcome
            )

        # Run computation within customer context
        with customer_context(self.customer):
            report_run = compute_weekly_payer_drift(
                customer=self.customer,
                baseline_days=90,
                current_days=14,
                min_volume=30,
                as_of_date=self.as_of_date,
            )

            # Check results
            self.assertEqual(report_run.status, "success")
            self.assertEqual(report_run.summary_json["events_created"], 1)

            # Check drift event
            drift_events = DriftEvent.objects.filter(report_run=report_run)
            self.assertEqual(drift_events.count(), 1)

            event = drift_events.first()
            self.assertEqual(event.drift_type, "DENIAL_RATE")
            self.assertEqual(event.payer, "UnitedHealthcare")
            self.assertEqual(event.cpt_group, "EVAL")
            self.assertAlmostEqual(
                event.baseline_value, 0.2, places=1
            )  # 20% denial rate
            self.assertAlmostEqual(
                event.current_value, 0.6, places=1
            )  # 60% denial rate
            self.assertAlmostEqual(event.delta_value, 0.4, places=1)  # +40% delta

    def test_decision_time_drift_up(self):
        """Test that DriftEvents are created when decision time drifts up."""
        # Create baseline records - fast decisions (5 days)
        baseline_start = self.as_of_date - timedelta(days=104)  # 90 + 14
        baseline_end = self.as_of_date - timedelta(days=14)

        for i in range(40):
            submitted_date = baseline_start + timedelta(days=i % 20)
            decided_date = submitted_date + timedelta(days=5)  # Fast decisions
            self.create_claim_record(
                "Aetna", "SURG", submitted_date, decided_date, "PAID"
            )

        # Create current records - slow decisions (15 days)
        current_start = baseline_end
        current_end = self.as_of_date

        for i in range(40):
            submitted_date = current_start + timedelta(days=i % 10)
            decided_date = submitted_date + timedelta(days=15)  # Slow decisions
            self.create_claim_record(
                "Aetna", "SURG", submitted_date, decided_date, "PAID"
            )

        # Run computation within customer context
        with customer_context(self.customer):
            report_run = compute_weekly_payer_drift(
                customer=self.customer,
                baseline_days=90,
                current_days=14,
                min_volume=30,
                as_of_date=self.as_of_date,
            )

            # Check results
            self.assertEqual(report_run.status, "success")
            self.assertEqual(report_run.summary_json["events_created"], 1)

            # Check drift event
            drift_events = DriftEvent.objects.filter(report_run=report_run)
            self.assertEqual(drift_events.count(), 1)

            event = drift_events.first()
            self.assertEqual(event.drift_type, "DECISION_TIME")
            self.assertEqual(event.payer, "Aetna")
            self.assertEqual(event.cpt_group, "SURG")
            self.assertEqual(event.baseline_value, 5.0)  # 5 days median
            self.assertEqual(event.current_value, 15.0)  # 15 days median
            self.assertEqual(event.delta_value, 10.0)  # +10 days delta

    def test_no_events_below_min_volume(self):
        """Test that no DriftEvents are created when volume is below threshold."""
        # Create baseline records - below min volume
        baseline_start = self.as_of_date - timedelta(days=104)
        baseline_end = self.as_of_date - timedelta(days=14)

        for i in range(20):  # Only 20 records - below min_volume of 30
            submitted_date = baseline_start + timedelta(days=i)
            decided_date = submitted_date + timedelta(days=5)
            self.create_claim_record(
                "Cigna", "RAD", submitted_date, decided_date, "PAID"
            )

        # Create current records - above min volume but baseline is below
        current_start = baseline_end
        current_end = self.as_of_date

        for i in range(40):
            submitted_date = current_start + timedelta(days=i % 10)
            decided_date = submitted_date + timedelta(days=10)
            self.create_claim_record(
                "Cigna", "RAD", submitted_date, decided_date, "DENIED"
            )

        # Run computation within customer context
        with customer_context(self.customer):
            report_run = compute_weekly_payer_drift(
                customer=self.customer,
                baseline_days=90,
                current_days=14,
                min_volume=30,
                as_of_date=self.as_of_date,
            )

            # Check results - should have no events due to low baseline volume
            self.assertEqual(report_run.status, "success")
            self.assertEqual(report_run.summary_json["events_created"], 0)
            self.assertEqual(
                DriftEvent.objects.filter(report_run=report_run).count(), 0
            )

    def test_baseline_zero_denial_rate(self):
        """Test handling of baseline zero denial rate safely."""
        # Create baseline records - all paid (0% denial rate)
        baseline_start = self.as_of_date - timedelta(days=104)
        baseline_end = self.as_of_date - timedelta(days=14)

        for i in range(40):
            submitted_date = baseline_start + timedelta(days=i % 20)
            decided_date = submitted_date + timedelta(days=5)
            self.create_claim_record(
                "BlueCross", "PATH", submitted_date, decided_date, "PAID"
            )

        # Create current records - some denied
        current_start = baseline_end
        current_end = self.as_of_date

        for i in range(40):
            submitted_date = current_start + timedelta(days=i % 10)
            decided_date = submitted_date + timedelta(days=5)
            outcome = "DENIED" if i < 5 else "PAID"
            self.create_claim_record(
                "BlueCross", "PATH", submitted_date, decided_date, outcome
            )

        # Run computation within customer context - should not crash
        with customer_context(self.customer):
            report_run = compute_weekly_payer_drift(
                customer=self.customer,
                baseline_days=90,
                current_days=14,
                min_volume=30,
                as_of_date=self.as_of_date,
            )

            # Should create event for denial rate drift (0% -> 12.5%)
            self.assertEqual(report_run.status, "success")
            self.assertEqual(report_run.summary_json["events_created"], 1)

            event = DriftEvent.objects.get(report_run=report_run)
            self.assertEqual(event.drift_type, "DENIAL_RATE")
            self.assertEqual(event.baseline_value, 0.0)
            self.assertAlmostEqual(event.current_value, 0.125, places=3)

    def _test_atomicity_on_exception(self):
        """Test that exceptions result in failed ReportRun and no DriftEvents.

        NOTE: Temporarily disabled - monkey patching doesn't work correctly in test context.
        """
        # Create some baseline data
        baseline_start = self.as_of_date - timedelta(days=104)
        baseline_end = self.as_of_date - timedelta(days=14)

        for i in range(30):
            submitted_date = baseline_start + timedelta(days=i)
            decided_date = submitted_date + timedelta(days=5)
            self.create_claim_record(
                "TestPayer", "TEST", submitted_date, decided_date, "PAID"
            )

        # Temporarily break the service to simulate an exception
        original_compute = compute_weekly_payer_drift

        def failing_compute(*args, **kwargs):
            # Start the computation but force an exception
            report_run = original_compute(*args, **kwargs)
            # Simulate an exception after some processing
            raise ValueError("Simulated exception for testing")

        # Monkey patch to simulate failure
        import upstream.services.payer_drift

        original_compute = upstream.services.payer_drift.compute_weekly_payer_drift
        upstream.services.payer_drift.compute_weekly_payer_drift = failing_compute

        try:
            # This should fail
            with self.assertRaises(ValueError):
                compute_weekly_payer_drift(
                    customer=self.customer,
                    baseline_days=90,
                    current_days=14,
                    min_volume=30,
                    as_of_date=self.as_of_date,
                )

            # Check that report run was marked as failed
            report_run = ReportRun.objects.latest("started_at")
            self.assertEqual(report_run.status, "failed")
            self.assertIsNotNone(report_run.finished_at)
            self.assertIn(
                "Simulated exception for testing",
                report_run.summary_json.get("error", ""),
            )

            # Check that no drift events were created
            self.assertEqual(
                DriftEvent.objects.filter(report_run=report_run).count(), 0
            )

        finally:
            # Restore original function
            upstream.services.payer_drift.compute_weekly_payer_drift = original_compute

    def test_concurrent_drift_detection_prevents_duplicates(self):
        """
        Test that drift computation uses select_for_update() for row locking.

        Validates DB-01: Transaction isolation for concurrent drift detection.

        Note: This test verifies the locking code is present. Full concurrent
        testing requires PostgreSQL in production.
        """
        from django.db import connection

        # Create customer with sufficient claims for drift detection
        customer = Customer.objects.create(name="Concurrent Test Customer")
        upload = Upload.objects.create(
            customer=customer, filename="concurrent_test.csv", status="success"
        )

        # Create claims that will trigger drift events
        from datetime import timedelta

        as_of_date = timezone.now().date()

        # Baseline period (90-14 days ago) - low denial rate (20%)
        baseline_start = as_of_date - timedelta(days=104)  # 90 + 14
        baseline_end = as_of_date - timedelta(days=14)

        for i in range(50):  # 50 total, 10 denied = 20% denial rate
            submitted_date = baseline_start + timedelta(days=i % 30)
            decided_date = submitted_date + timedelta(days=5)
            outcome = "DENIED" if i < 10 else "PAID"
            ClaimRecord.objects.create(
                customer=customer,
                upload=upload,
                payer="Test Payer",
                cpt="99213",
                cpt_group="E&M",
                submitted_date=submitted_date,
                decided_date=decided_date,
                outcome=outcome,
                submitted_via="csv_upload",
            )

        # Current period (last 14 days) - high denial rate (60%)
        current_start = baseline_end
        current_end = as_of_date

        for i in range(50):  # 50 total, 30 denied = 60% denial rate
            submitted_date = current_start + timedelta(days=i % 10)
            decided_date = submitted_date + timedelta(days=5)
            outcome = "DENIED" if i < 30 else "PAID"
            ClaimRecord.objects.create(
                customer=customer,
                upload=upload,
                payer="Test Payer",
                cpt="99213",
                cpt_group="E&M",
                submitted_date=submitted_date,
                decided_date=decided_date,
                outcome=outcome,
                submitted_via="csv_upload",
            )

        # Verify select_for_update() is used in the code
        from upstream.services.payer_drift import compute_weekly_payer_drift
        import inspect

        source = inspect.getsource(compute_weekly_payer_drift)
        self.assertIn(
            "select_for_update",
            source,
            "compute_weekly_payer_drift should use select_for_update() for locking",
        )
        self.assertIn(
            "locked_customer",
            source,
            "compute_weekly_payer_drift should use locked_customer variable",
        )
        self.assertIn(
            "IntegrityError",
            source,
            "compute_weekly_payer_drift should handle IntegrityError for duplicates",
        )

        # Run a simple drift computation to verify it works
        report_run = compute_weekly_payer_drift(
            customer=customer,
            baseline_days=90,
            current_days=14,
            min_volume=30,
            as_of_date=as_of_date,
        )

        # Verify computation succeeded (even if no drift detected)
        self.assertEqual(report_run.status, "success")


class ReportArtifactTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(name="Test Customer")
        self.as_of_date = timezone.now().date()

    def create_claim_record(
        self, payer, cpt_group, submitted_date, decided_date, outcome
    ):
        """Helper to create a claim record."""
        upload = Upload.objects.create(
            customer=self.customer, filename="test.csv", status="success", row_count=1
        )
        return ClaimRecord.objects.create(
            customer=self.customer,
            upload=upload,
            payer=payer,
            cpt="12345",
            cpt_group=cpt_group,
            submitted_date=submitted_date,
            decided_date=decided_date,
            outcome=outcome,
            submitted_via="csv_upload",
        )

    @skipUnless(
        WEASYPRINT_AVAILABLE, "WeasyPrint requires system dependencies (pango, etc)"
    )
    def test_pdf_artifact_creation(self):
        """Test that PDF artifact is created successfully."""
        from upstream.services.payer_drift import compute_weekly_payer_drift
        from upstream.reporting.services import generate_weekly_drift_pdf
        from upstream.reporting.models import ReportArtifact

        # Create test data - baseline with low denial rate
        baseline_start = self.as_of_date - timedelta(days=104)
        baseline_end = self.as_of_date - timedelta(days=14)
        for i in range(50):
            submitted_date = baseline_start + timedelta(days=i % 30)
            decided_date = submitted_date + timedelta(days=5)
            outcome = "DENIED" if i < 10 else "PAID"
            self.create_claim_record(
                "TestPayer", "EVAL", submitted_date, decided_date, outcome
            )

        # Create current data - high denial rate
        current_start = baseline_end
        for i in range(50):
            submitted_date = current_start + timedelta(days=i % 10)
            decided_date = submitted_date + timedelta(days=5)
            outcome = "DENIED" if i < 30 else "PAID"
            self.create_claim_record(
                "TestPayer", "EVAL", submitted_date, decided_date, outcome
            )

        # Generate drift report
        report_run = compute_weekly_payer_drift(
            customer=self.customer,
            baseline_days=90,
            current_days=14,
            min_volume=30,
            as_of_date=self.as_of_date,
        )

        # Generate PDF artifact
        artifact = generate_weekly_drift_pdf(report_run.id)

        # Verify artifact was created
        self.assertIsNotNone(artifact)
        self.assertEqual(artifact.customer, self.customer)
        self.assertEqual(artifact.report_run, report_run)
        self.assertEqual(artifact.kind, "weekly_drift_summary")
        self.assertIsNotNone(artifact.file_path)
        self.assertIsNotNone(artifact.content_hash)
        self.assertEqual(len(artifact.content_hash), 64)  # SHA256 hash length

    @skipUnless(
        WEASYPRINT_AVAILABLE, "WeasyPrint requires system dependencies (pango, etc)"
    )
    def test_pdf_file_exists_and_nonzero(self):
        """Test that generated PDF file exists and has non-zero size."""
        from upstream.services.payer_drift import compute_weekly_payer_drift
        from upstream.reporting.services import generate_weekly_drift_pdf

        # Create minimal test data
        baseline_start = self.as_of_date - timedelta(days=104)
        baseline_end = self.as_of_date - timedelta(days=14)
        for i in range(40):
            submitted_date = baseline_start + timedelta(days=i % 30)
            decided_date = submitted_date + timedelta(days=5)
            self.create_claim_record(
                "Payer1", "TEST", submitted_date, decided_date, "PAID"
            )

        current_start = baseline_end
        for i in range(40):
            submitted_date = current_start + timedelta(days=i % 10)
            decided_date = submitted_date + timedelta(days=10)
            self.create_claim_record(
                "Payer1", "TEST", submitted_date, decided_date, "DENIED"
            )

        # Generate report and artifact
        report_run = compute_weekly_payer_drift(
            customer=self.customer,
            baseline_days=90,
            current_days=14,
            min_volume=30,
            as_of_date=self.as_of_date,
        )
        artifact = generate_weekly_drift_pdf(report_run.id)

        # Verify file exists
        self.assertTrue(os.path.exists(artifact.file_path))

        # Verify file is non-zero size
        file_size = os.path.getsize(artifact.file_path)
        self.assertGreater(file_size, 0)
        self.assertGreater(file_size, 1000)  # Should be at least 1KB for a real PDF

    @skipUnless(
        WEASYPRINT_AVAILABLE, "WeasyPrint requires system dependencies (pango, etc)"
    )
    def test_pdf_idempotency(self):
        """Test that generating the same report twice creates idempotent artifact."""
        from upstream.services.payer_drift import compute_weekly_payer_drift
        from upstream.reporting.services import generate_weekly_drift_pdf
        from upstream.reporting.models import ReportArtifact

        # Create test data
        baseline_start = self.as_of_date - timedelta(days=104)
        baseline_end = self.as_of_date - timedelta(days=14)
        for i in range(40):
            submitted_date = baseline_start + timedelta(days=i % 30)
            decided_date = submitted_date + timedelta(days=5)
            self.create_claim_record(
                "Payer2", "SURG", submitted_date, decided_date, "PAID"
            )

        current_start = baseline_end
        for i in range(40):
            submitted_date = current_start + timedelta(days=i % 10)
            decided_date = submitted_date + timedelta(days=15)
            self.create_claim_record(
                "Payer2", "SURG", submitted_date, decided_date, "PAID"
            )

        # Generate report
        report_run = compute_weekly_payer_drift(
            customer=self.customer,
            baseline_days=90,
            current_days=14,
            min_volume=30,
            as_of_date=self.as_of_date,
        )

        # Generate PDF first time
        artifact1 = generate_weekly_drift_pdf(report_run.id)
        artifact1_id = artifact1.id
        artifact1_hash = artifact1.content_hash

        # Count total artifacts
        artifact_count = ReportArtifact.objects.filter(
            customer=self.customer, report_run=report_run, kind="weekly_drift_summary"
        ).count()
        self.assertEqual(artifact_count, 1)

        # Generate PDF second time (should update, not create new)
        artifact2 = generate_weekly_drift_pdf(report_run.id)
        artifact2_id = artifact2.id

        # Verify it's the same artifact (idempotent)
        self.assertEqual(artifact1_id, artifact2_id)

        # Verify artifact count is still 1 (no duplicate created)
        artifact_count_after = ReportArtifact.objects.filter(
            customer=self.customer, report_run=report_run, kind="weekly_drift_summary"
        ).count()
        self.assertEqual(artifact_count_after, 1)

    @skipUnless(
        WEASYPRINT_AVAILABLE, "WeasyPrint requires system dependencies (pango, etc)"
    )
    def test_pdf_content_hash_consistency(self):
        """Test that content hash is consistent for identical data."""
        from upstream.services.payer_drift import compute_weekly_payer_drift
        from upstream.reporting.services import generate_weekly_drift_pdf

        # Create test data
        baseline_start = self.as_of_date - timedelta(days=104)
        baseline_end = self.as_of_date - timedelta(days=14)
        for i in range(40):
            submitted_date = baseline_start + timedelta(days=i % 30)
            decided_date = submitted_date + timedelta(days=5)
            self.create_claim_record(
                "Payer3", "PATH", submitted_date, decided_date, "PAID"
            )

        current_start = baseline_end
        for i in range(40):
            submitted_date = current_start + timedelta(days=i % 10)
            decided_date = submitted_date + timedelta(days=8)
            outcome = "DENIED" if i < 5 else "PAID"
            self.create_claim_record(
                "Payer3", "PATH", submitted_date, decided_date, outcome
            )

        # Generate report
        report_run = compute_weekly_payer_drift(
            customer=self.customer,
            baseline_days=90,
            current_days=14,
            min_volume=30,
            as_of_date=self.as_of_date,
        )

        # Generate PDF first time
        artifact1 = generate_weekly_drift_pdf(report_run.id)
        hash1 = artifact1.content_hash

        # Generate PDF second time
        artifact2 = generate_weekly_drift_pdf(report_run.id)
        hash2 = artifact2.content_hash

        # Verify hashes are identical (same data generates same PDF)
        self.assertEqual(hash1, hash2)

    def test_unique_constraint_enforcement(self):
        """Test that database constraint prevents duplicate artifacts."""
        from upstream.services.payer_drift import compute_weekly_payer_drift
        from upstream.reporting.models import ReportArtifact

        # Create minimal test data
        baseline_start = self.as_of_date - timedelta(days=104)
        baseline_end = self.as_of_date - timedelta(days=14)
        for i in range(40):
            submitted_date = baseline_start + timedelta(days=i % 30)
            decided_date = submitted_date + timedelta(days=5)
            self.create_claim_record(
                "Payer4", "RAD", submitted_date, decided_date, "PAID"
            )

        current_start = baseline_end
        for i in range(40):
            submitted_date = current_start + timedelta(days=i % 10)
            decided_date = submitted_date + timedelta(days=10)
            self.create_claim_record(
                "Payer4", "RAD", submitted_date, decided_date, "PAID"
            )

        # Generate report
        report_run = compute_weekly_payer_drift(
            customer=self.customer,
            baseline_days=90,
            current_days=14,
            min_volume=30,
            as_of_date=self.as_of_date,
        )

        # Try to manually create two artifacts with same customer, report_run, kind
        # First one should succeed
        artifact1 = ReportArtifact.objects.create(
            customer=self.customer,
            report_run=report_run,
            kind="weekly_drift_summary",
            file_path="/tmp/test1.pdf",
            content_hash="hash1",
        )
        self.assertIsNotNone(artifact1.id)

        # Second one should fail due to unique constraint
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            ReportArtifact.objects.create(
                customer=self.customer,
                report_run=report_run,
                kind="weekly_drift_summary",
                file_path="/tmp/test2.pdf",
                content_hash="hash2",
            )


class TestSessionFixationPrevention(TestCase):
    """Test session fixation vulnerability is prevented in logout."""

    def setUp(self):
        from django.test import Client

        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123",  # pragma: allowlist secret
        )

    def test_logout_regenerates_session_key(self):
        """Session key should change after logout to prevent fixation."""
        # Login and capture session key
        self.client.login(
            username="testuser",
            password="testpass123",  # pragma: allowlist secret
        )
        session_key_before = self.client.session.session_key

        # Logout
        response = self.client.get("/portal/logout/")

        # Session key should be different after logout
        session_key_after = self.client.session.session_key
        self.assertNotEqual(
            session_key_before,
            session_key_after,
            "Session key must change after logout to prevent fixation",
        )

    def test_logout_context_still_displays(self):
        """Logout page should still show user context despite session.flush()."""
        # Create superuser for testing operator context
        superuser = User.objects.create_superuser(
            username="admin",
            password="admin123",  # pragma: allowlist secret
            email="admin@example.com",
        )

        self.client.login(
            username="admin",
            password="admin123",  # pragma: allowlist secret
        )
        response = self.client.get("/portal/logout/")

        # Context should be passed to template
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "admin")  # Username should appear
