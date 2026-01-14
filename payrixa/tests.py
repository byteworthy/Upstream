from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.messages.storage.fallback import FallbackStorage
from payrixa.models import Customer, UserProfile, Upload, ClaimRecord, ReportRun, DriftEvent
from payrixa.views import UploadsView
from payrixa.utils import get_current_customer
from payrixa.services.payer_drift import compute_weekly_payer_drift
import csv
import io
from datetime import datetime, timedelta
from django.utils import timezone

class CSVUploadTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.customer = Customer.objects.create(name='Test Customer')
        self.profile = UserProfile.objects.create(user=self.user, customer=self.customer)

        # Create a mock request with authenticated user
        self.request = self.factory.get('/uploads/')
        self.request.user = self.user

    def create_csv_file(self, data, filename='test.csv'):
        """Helper to create a CSV file for testing."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerows(data)
        content = output.getvalue().encode('utf-8')
        return SimpleUploadedFile(filename, content, content_type='text/csv')

    def test_valid_csv_upload(self):
        """Test successful CSV upload with valid data."""
        # Create valid CSV data
        csv_data = [
            ['payer', 'cpt', 'submitted_date', 'decided_date', 'outcome', 'allowed_amount'],
            ['UnitedHealthcare', '99213', '2023-01-15', '2023-01-20', 'PAID', '100.50'],
            ['Aetna', '99214', '2023-01-16', '2023-01-21', 'DENIED', '150.75'],
            ['Cigna', '99213', '01/17/2023', '01/22/2023', 'paid', '125.00'],
        ]

        csv_file = self.create_csv_file(csv_data)

        # Create POST request with CSV file
        request = self.factory.post('/uploads/', {'csv_file': csv_file})
        request.user = self.user

        # Set up messages storage
        request.session = {}
        request._messages = FallbackStorage(request)

        # Process the upload
        view = UploadsView()
        response = view.post(request)

        # Check that upload was created successfully
        upload = Upload.objects.latest('uploaded_at')
        self.assertEqual(upload.status, 'success')
        self.assertEqual(upload.row_count, 3)
        self.assertEqual(upload.filename, 'test.csv')

        # Check that claim records were created
        claim_records = ClaimRecord.objects.filter(upload=upload)
        self.assertEqual(claim_records.count(), 3)

        # Check first record
        record1 = claim_records[0]
        self.assertEqual(record1.payer, 'UnitedHealthcare')
        self.assertEqual(record1.cpt, '99213')
        self.assertEqual(record1.outcome, 'PAID')
        self.assertEqual(record1.allowed_amount, 100.50)

    def test_missing_required_column(self):
        """Test CSV upload with missing required column."""
        # Create CSV without required 'outcome' column
        csv_data = [
            ['payer', 'cpt', 'submitted_date', 'decided_date'],
            ['UnitedHealthcare', '99213', '2023-01-15', '2023-01-20'],
        ]

        csv_file = self.create_csv_file(csv_data)

        request = self.factory.post('/uploads/', {'csv_file': csv_file})
        request.user = self.user

        # Set up messages storage
        request.session = {}
        request._messages = FallbackStorage(request)

        view = UploadsView()
        response = view.post(request)

        # Check that upload failed
        upload = Upload.objects.latest('uploaded_at')
        self.assertEqual(upload.status, 'failed')
        self.assertIn('Missing required column: outcome', upload.error_message)

        # Check that no claim records were created
        self.assertEqual(ClaimRecord.objects.count(), 0)

    def test_invalid_date_format(self):
        """Test CSV upload with invalid date format."""
        csv_data = [
            ['payer', 'cpt', 'submitted_date', 'decided_date', 'outcome'],
            ['UnitedHealthcare', '99213', '2023-01-15', 'invalid-date', 'PAID'],
        ]

        csv_file = self.create_csv_file(csv_data)

        request = self.factory.post('/uploads/', {'csv_file': csv_file})
        request.user = self.user

        # Set up messages storage
        request.session = {}
        request._messages = FallbackStorage(request)

        view = UploadsView()
        response = view.post(request)

        # Check that upload failed
        upload = Upload.objects.latest('uploaded_at')
        self.assertEqual(upload.status, 'failed')
        self.assertIn('Error processing row 2', upload.error_message)
        self.assertIn('Invalid decided_date format', upload.error_message)

        # Check that no claim records were created
        self.assertEqual(ClaimRecord.objects.count(), 0)

    def test_missing_decided_date(self):
        """Test CSV upload with missing decided_date (should fail for MVP)."""
        csv_data = [
            ['payer', 'cpt', 'submitted_date', 'decided_date', 'outcome'],
            ['UnitedHealthcare', '99213', '2023-01-15', '', 'PAID'],
        ]

        csv_file = self.create_csv_file(csv_data)

        request = self.factory.post('/uploads/', {'csv_file': csv_file})
        request.user = self.user

        # Set up messages storage
        request.session = {}
        request._messages = FallbackStorage(request)

        view = UploadsView()
        response = view.post(request)

        # Check that upload failed
        upload = Upload.objects.latest('uploaded_at')
        self.assertEqual(upload.status, 'failed')
        self.assertIn('Missing required field', upload.error_message)
        self.assertIn('decided_date', upload.error_message)
        self.assertIn('row 2', upload.error_message)

        # Check that no claim records were created
        self.assertEqual(ClaimRecord.objects.count(), 0)

    def test_extra_columns_ignored(self):
        """Test that extra columns are ignored (not stored)."""
        csv_data = [
            ['payer', 'cpt', 'submitted_date', 'decided_date', 'outcome', 'patient_name', 'ssn'],
            ['UnitedHealthcare', '99213', '2023-01-15', '2023-01-20', 'PAID', 'John Doe', '123-45-6789'],
        ]

        csv_file = self.create_csv_file(csv_data)

        request = self.factory.post('/uploads/', {'csv_file': csv_file})
        request.user = self.user

        # Set up messages storage
        request.session = {}
        request._messages = FallbackStorage(request)

        view = UploadsView()
        response = view.post(request)

        # Check that upload succeeded (extra columns ignored)
        upload = Upload.objects.latest('uploaded_at')
        self.assertEqual(upload.status, 'success')
        self.assertEqual(upload.row_count, 1)

        # Check that claim record was created without extra data
        record = ClaimRecord.objects.get(upload=upload)
        self.assertEqual(record.payer, 'UnitedHealthcare')
        # Verify that patient_name and ssn were not stored
        self.assertFalse(hasattr(record, 'patient_name'))
        self.assertFalse(hasattr(record, 'ssn'))

    def test_date_formats(self):
        """Test various valid date formats."""
        csv_data = [
            ['payer', 'cpt', 'submitted_date', 'decided_date', 'outcome'],
            ['Test1', '99213', '2023-01-15', '2023-01-20', 'PAID'],  # ISO format
            ['Test2', '99213', '01/16/2023', '01/21/2023', 'PAID'],  # US format
            ['Test3', '99213', '2023/01/17', '2023/01/22', 'PAID'],  # YYYY/MM/DD format
        ]

        csv_file = self.create_csv_file(csv_data)

        request = self.factory.post('/uploads/', {'csv_file': csv_file})
        request.user = self.user

        # Set up messages storage
        request.session = {}
        request._messages = FallbackStorage(request)

        view = UploadsView()
        response = view.post(request)

        # Check that upload succeeded
        upload = Upload.objects.latest('uploaded_at')
        self.assertEqual(upload.status, 'success')
        self.assertEqual(upload.row_count, 3)

        # Check dates were parsed correctly
        records = ClaimRecord.objects.filter(upload=upload).order_by('id')
        self.assertEqual(records[0].submitted_date, datetime.strptime('2023-01-15', '%Y-%m-%d').date())
        self.assertEqual(records[1].submitted_date, datetime.strptime('01/16/2023', '%m/%d/%Y').date())
        self.assertEqual(records[2].submitted_date, datetime.strptime('2023/01/17', '%Y/%m/%d').date())

    def test_outcome_normalization(self):
        """Test outcome normalization."""
        csv_data = [
            ['payer', 'cpt', 'submitted_date', 'decided_date', 'outcome'],
            ['Test1', '99213', '2023-01-15', '2023-01-20', 'paid'],
            ['Test2', '99213', '2023-01-15', '2023-01-20', 'APPROVED'],
            ['Test3', '99213', '2023-01-15', '2023-01-20', 'DENIED'],
            ['Test4', '99213', '2023-01-15', '2023-01-20', 'REJECTED'],
            ['Test5', '99213', '2023-01-15', '2023-01-20', 'PENDING'],
        ]

        csv_file = self.create_csv_file(csv_data)

        request = self.factory.post('/uploads/', {'csv_file': csv_file})
        request.user = self.user

        # Set up messages storage
        request.session = {}
        request._messages = FallbackStorage(request)

        view = UploadsView()
        response = view.post(request)

        # Check that upload succeeded
        upload = Upload.objects.latest('uploaded_at')
        self.assertEqual(upload.status, 'success')

        # Check outcome normalization
        records = ClaimRecord.objects.filter(upload=upload).order_by('id')
        self.assertEqual(records[0].outcome, 'PAID')  # 'paid' -> 'PAID'
        self.assertEqual(records[1].outcome, 'PAID')  # 'APPROVED' -> 'PAID'
        self.assertEqual(records[2].outcome, 'DENIED')  # 'DENIED' -> 'DENIED'
        self.assertEqual(records[3].outcome, 'DENIED')  # 'REJECTED' -> 'DENIED'
        self.assertEqual(records[4].outcome, 'OTHER')  # 'PENDING' -> 'OTHER'

class PayerDriftTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(name='Test Customer')
        self.as_of_date = timezone.now().date()

    def create_claim_record(self, payer, cpt_group, submitted_date, decided_date, outcome):
        """Helper to create a claim record."""
        upload = Upload.objects.create(
            customer=self.customer,
            filename='test.csv',
            status='success',
            row_count=1
        )

        return ClaimRecord.objects.create(
            customer=self.customer,
            upload=upload,
            payer=payer,
            cpt='12345',
            cpt_group=cpt_group,
            submitted_date=submitted_date,
            decided_date=decided_date,
            outcome=outcome
        )

    def test_denial_rate_drift_up(self):
        """Test that DriftEvents are created when denial rate drifts up in current window."""
        # Create baseline records (90 days ago) - low denial rate
        baseline_start = self.as_of_date - timedelta(days=104)  # 90 + 14
        baseline_end = self.as_of_date - timedelta(days=14)

        for i in range(50):  # 50 total, 10 denied = 20% denial rate
            submitted_date = baseline_start + timedelta(days=i % 30)
            decided_date = submitted_date + timedelta(days=5)
            outcome = 'DENIED' if i < 10 else 'PAID'
            self.create_claim_record('UnitedHealthcare', 'EVAL', submitted_date, decided_date, outcome)

        # Create current records (last 14 days) - high denial rate
        current_start = baseline_end
        current_end = self.as_of_date

        for i in range(50):  # 50 total, 30 denied = 60% denial rate
            submitted_date = current_start + timedelta(days=i % 10)
            decided_date = submitted_date + timedelta(days=5)
            outcome = 'DENIED' if i < 30 else 'PAID'
            self.create_claim_record('UnitedHealthcare', 'EVAL', submitted_date, decided_date, outcome)

        # Run computation
        report_run = compute_weekly_payer_drift(
            customer=self.customer,
            baseline_days=90,
            current_days=14,
            min_volume=30,
            as_of_date=self.as_of_date
        )

        # Check results
        self.assertEqual(report_run.status, 'success')
        self.assertEqual(report_run.summary_json['events_created'], 1)

        # Check drift event
        drift_events = DriftEvent.objects.filter(report_run=report_run)
        self.assertEqual(drift_events.count(), 1)

        event = drift_events.first()
        self.assertEqual(event.drift_type, 'DENIAL_RATE')
        self.assertEqual(event.payer, 'UnitedHealthcare')
        self.assertEqual(event.cpt_group, 'EVAL')
        self.assertAlmostEqual(event.baseline_value, 0.2, places=1)  # 20% denial rate
        self.assertAlmostEqual(event.current_value, 0.6, places=1)   # 60% denial rate
        self.assertAlmostEqual(event.delta_value, 0.4, places=1)     # +40% delta

    def test_decision_time_drift_up(self):
        """Test that DriftEvents are created when decision time drifts up."""
        # Create baseline records - fast decisions (5 days)
        baseline_start = self.as_of_date - timedelta(days=104)  # 90 + 14
        baseline_end = self.as_of_date - timedelta(days=14)

        for i in range(40):
            submitted_date = baseline_start + timedelta(days=i % 20)
            decided_date = submitted_date + timedelta(days=5)  # Fast decisions
            self.create_claim_record('Aetna', 'SURG', submitted_date, decided_date, 'PAID')

        # Create current records - slow decisions (15 days)
        current_start = baseline_end
        current_end = self.as_of_date

        for i in range(40):
            submitted_date = current_start + timedelta(days=i % 10)
            decided_date = submitted_date + timedelta(days=15)  # Slow decisions
            self.create_claim_record('Aetna', 'SURG', submitted_date, decided_date, 'PAID')

        # Run computation
        report_run = compute_weekly_payer_drift(
            customer=self.customer,
            baseline_days=90,
            current_days=14,
            min_volume=30,
            as_of_date=self.as_of_date
        )

        # Check results
        self.assertEqual(report_run.status, 'success')
        self.assertEqual(report_run.summary_json['events_created'], 1)

        # Check drift event
        drift_events = DriftEvent.objects.filter(report_run=report_run)
        self.assertEqual(drift_events.count(), 1)

        event = drift_events.first()
        self.assertEqual(event.drift_type, 'DECISION_TIME')
        self.assertEqual(event.payer, 'Aetna')
        self.assertEqual(event.cpt_group, 'SURG')
        self.assertEqual(event.baseline_value, 5.0)   # 5 days median
        self.assertEqual(event.current_value, 15.0)   # 15 days median
        self.assertEqual(event.delta_value, 10.0)     # +10 days delta

    def test_no_events_below_min_volume(self):
        """Test that no DriftEvents are created when volume is below threshold."""
        # Create baseline records - below min volume
        baseline_start = self.as_of_date - timedelta(days=104)
        baseline_end = self.as_of_date - timedelta(days=14)

        for i in range(20):  # Only 20 records - below min_volume of 30
            submitted_date = baseline_start + timedelta(days=i)
            decided_date = submitted_date + timedelta(days=5)
            self.create_claim_record('Cigna', 'RAD', submitted_date, decided_date, 'PAID')

        # Create current records - above min volume but baseline is below
        current_start = baseline_end
        current_end = self.as_of_date

        for i in range(40):
            submitted_date = current_start + timedelta(days=i % 10)
            decided_date = submitted_date + timedelta(days=10)
            self.create_claim_record('Cigna', 'RAD', submitted_date, decided_date, 'DENIED')

        # Run computation
        report_run = compute_weekly_payer_drift(
            customer=self.customer,
            baseline_days=90,
            current_days=14,
            min_volume=30,
            as_of_date=self.as_of_date
        )

        # Check results - should have no events due to low baseline volume
        self.assertEqual(report_run.status, 'success')
        self.assertEqual(report_run.summary_json['events_created'], 0)
        self.assertEqual(DriftEvent.objects.filter(report_run=report_run).count(), 0)

    def test_baseline_zero_denial_rate(self):
        """Test handling of baseline zero denial rate safely."""
        # Create baseline records - all paid (0% denial rate)
        baseline_start = self.as_of_date - timedelta(days=104)
        baseline_end = self.as_of_date - timedelta(days=14)

        for i in range(40):
            submitted_date = baseline_start + timedelta(days=i % 20)
            decided_date = submitted_date + timedelta(days=5)
            self.create_claim_record('BlueCross', 'PATH', submitted_date, decided_date, 'PAID')

        # Create current records - some denied
        current_start = baseline_end
        current_end = self.as_of_date

        for i in range(40):
            submitted_date = current_start + timedelta(days=i % 10)
            decided_date = submitted_date + timedelta(days=5)
            outcome = 'DENIED' if i < 5 else 'PAID'
            self.create_claim_record('BlueCross', 'PATH', submitted_date, decided_date, outcome)

        # Run computation - should not crash
        report_run = compute_weekly_payer_drift(
            customer=self.customer,
            baseline_days=90,
            current_days=14,
            min_volume=30,
            as_of_date=self.as_of_date
        )

        # Should create event for denial rate drift (0% -> 12.5%)
        self.assertEqual(report_run.status, 'success')
        self.assertEqual(report_run.summary_json['events_created'], 1)

        event = DriftEvent.objects.get(report_run=report_run)
        self.assertEqual(event.drift_type, 'DENIAL_RATE')
        self.assertEqual(event.baseline_value, 0.0)
        self.assertAlmostEqual(event.current_value, 0.125, places=3)

    def test_atomicity_on_exception(self):
        """Test that exceptions result in failed ReportRun and no DriftEvents."""
        # Create some baseline data
        baseline_start = self.as_of_date - timedelta(days=104)
        baseline_end = self.as_of_date - timedelta(days=14)

        for i in range(30):
            submitted_date = baseline_start + timedelta(days=i)
            decided_date = submitted_date + timedelta(days=5)
            self.create_claim_record('TestPayer', 'TEST', submitted_date, decided_date, 'PAID')

        # Temporarily break the service to simulate an exception
        original_compute = compute_weekly_payer_drift

        def failing_compute(*args, **kwargs):
            # Start the computation but force an exception
            report_run = original_compute(*args, **kwargs)
            # Simulate an exception after some processing
            raise ValueError("Simulated exception for testing")

        # Monkey patch to simulate failure
        import payrixa.services.payer_drift
        payrixa.services.payer_drift.compute_weekly_payer_drift = failing_compute

        try:
            # This should fail
            with self.assertRaises(ValueError):
                compute_weekly_payer_drift(
                    customer=self.customer,
                    baseline_days=90,
                    current_days=14,
                    min_volume=30,
                    as_of_date=self.as_of_date
                )

            # Check that report run was marked as failed
            report_run = ReportRun.objects.latest('started_at')
            self.assertEqual(report_run.status, 'failed')
            self.assertIsNotNone(report_run.finished_at)
            self.assertIn('Simulated exception for testing', report_run.summary_json.get('error', ''))

            # Check that no drift events were created
            self.assertEqual(DriftEvent.objects.filter(report_run=report_run).count(), 0)

        finally:
            # Restore original function
            payrixa.services.payer_drift.compute_weekly_payer_drift = original_compute
<task_progress>
- [x] Inspect current model fields (no changes yet)
- [x] Create payer_drift.py service module
- [x] Implement compute_weekly_payer_drift function
- [x] Add management command
- [x] Update reports page
- [x] Add tests
</task_progress>
</write_to_file>
