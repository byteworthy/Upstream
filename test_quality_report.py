#!/usr/bin/env python
"""
Test Data Quality Report implementation.

This script tests the quality report functionality by uploading a CSV file
with various validation issues and verifying the quality report is created correctly.
"""

import sys
import os
import django
from io import BytesIO

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'upstream.settings.dev')
django.setup()

from django.core.files.uploadedfile import SimpleUploadedFile
from upstream.models import Customer, Upload, DataQualityReport
from upstream.views import UploadsView

def test_quality_report():
    """Test quality report creation with mixed valid/invalid data."""

    print("Testing Data Quality Report Implementation")
    print("=" * 60)

    # Create test customer
    customer, _ = Customer.objects.get_or_create(name="Test Quality Customer")
    print(f"✓ Created test customer: {customer.name}")

    # Create test CSV with various validation issues
    csv_content = """payer,cpt,submitted_date,decided_date,outcome,allowed_amount
Blue Cross Blue Shield,99213,2024-01-15,2024-02-01,PAID,150.00
Medicare,99214,2024-01-16,2024-02-02,PAID,200.00
John Smith,99215,2024-01-17,2024-02-03,DENIED,0.00
Aetna,99213,2024-01-18,2024-02-04,PAID,150.00
Mary Johnson,99214,2024-01-19,2024-02-05,DENIED,0.00
UnitedHealthcare,99213,,2024-02-06,PAID,150.00
Cigna,99214,2024-01-21,invalid-date,PAID,200.00
Anthem,99213,2024-01-22,2024-02-08,APPROVED,145.00
Humana,,2024-01-23,2024-02-09,PAID,180.00
TriCare,99215,2024-01-24,2024-02-10,PAID,250.00"""

    csv_file = SimpleUploadedFile(
        "test_quality.csv",
        csv_content.encode('utf-8'),
        content_type='text/csv'
    )

    print(f"\n✓ Created test CSV with 10 rows")
    print("  Expected issues:")
    print("    - 2 rows with PHI (John Smith, Mary Johnson)")
    print("    - 1 row with missing submitted_date")
    print("    - 1 row with invalid date format")
    print("    - 1 row with missing CPT code")
    print("    - Expected accepted: 5 rows")

    # Create upload record
    upload = Upload.objects.create(
        customer=customer,
        filename="test_quality.csv",
        status='processing'
    )
    print(f"\n✓ Created upload record: {upload.id}")

    # Process the upload
    view = UploadsView()
    view.MAX_ROWS = 200000

    try:
        print("\n⏳ Processing CSV upload...")
        view.process_csv_upload(upload, csv_file)
        upload.status = 'success'
        upload.save()
        print("✓ Upload processed successfully")
    except Exception as e:
        upload.status = 'failed'
        upload.error_message = str(e)
        upload.save()
        print(f"✗ Upload failed: {str(e)}")
        return False

    # Refresh upload from database
    upload.refresh_from_db()

    # Verify quality report was created
    # Use all_objects manager since we're not in a request context with customer scope
    try:
        quality_report = DataQualityReport.all_objects.get(upload=upload)
        print(f"\n✓ Quality report created: {quality_report.id}")
    except DataQualityReport.DoesNotExist:
        print("✗ Quality report was NOT created")
        print(f"  Debug: Upload ID = {upload.id}")
        print(f"  Debug: Upload Customer = {upload.customer_id}")
        print(f"  Debug: Total DataQualityReports = {DataQualityReport.objects.count()}")
        all_reports = DataQualityReport.objects.all()
        for report in all_reports:
            print(f"  Debug: Report {report.id} -> Upload {report.upload_id} (Customer {report.customer_id})")

        # Check if CustomerScopedManager is filtering it out
        print(f"  Debug: All objects count = {DataQualityReport.all_objects.count()}")
        all_reports_unfiltered = DataQualityReport.all_objects.all()
        for report in all_reports_unfiltered:
            print(f"  Debug (unfiltered): Report {report.id} -> Upload {report.upload_id} (Customer {report.customer_id})")
        return False

    # Verify quality metrics
    print("\n" + "=" * 60)
    print("QUALITY REPORT RESULTS:")
    print("=" * 60)

    results = []

    # Total rows
    expected_total = 10
    if quality_report.total_rows == expected_total:
        print(f"✓ Total rows: {quality_report.total_rows} (expected {expected_total})")
        results.append(True)
    else:
        print(f"✗ Total rows: {quality_report.total_rows} (expected {expected_total})")
        results.append(False)

    # Accepted rows
    expected_accepted = 5
    if quality_report.accepted_rows == expected_accepted:
        print(f"✓ Accepted rows: {quality_report.accepted_rows} (expected {expected_accepted})")
        results.append(True)
    else:
        print(f"✗ Accepted rows: {quality_report.accepted_rows} (expected {expected_accepted})")
        results.append(False)

    # Rejected rows
    expected_rejected = 5
    if quality_report.rejected_rows == expected_rejected:
        print(f"✓ Rejected rows: {quality_report.rejected_rows} (expected {expected_rejected})")
        results.append(True)
    else:
        print(f"✗ Rejected rows: {quality_report.rejected_rows} (expected {expected_rejected})")
        results.append(False)

    # PHI detections
    expected_phi = 2
    if quality_report.phi_detections == expected_phi:
        print(f"✓ PHI detections: {quality_report.phi_detections} (expected {expected_phi})")
        results.append(True)
    else:
        print(f"✗ PHI detections: {quality_report.phi_detections} (expected {expected_phi})")
        results.append(False)

    # Missing fields
    expected_missing = 2
    if quality_report.missing_fields == expected_missing:
        print(f"✓ Missing fields: {quality_report.missing_fields} (expected {expected_missing})")
        results.append(True)
    else:
        print(f"✗ Missing fields: {quality_report.missing_fields} (expected {expected_missing})")
        results.append(False)

    # Invalid dates
    expected_invalid_dates = 1
    if quality_report.invalid_dates == expected_invalid_dates:
        print(f"✓ Invalid dates: {quality_report.invalid_dates} (expected {expected_invalid_dates})")
        results.append(True)
    else:
        print(f"✗ Invalid dates: {quality_report.invalid_dates} (expected {expected_invalid_dates})")
        results.append(False)

    # Quality score
    expected_score = 0.5  # 5/10 = 50%
    if abs(quality_report.quality_score - expected_score) < 0.01:
        print(f"✓ Quality score: {quality_report.quality_score:.1%} (expected {expected_score:.1%})")
        results.append(True)
    else:
        print(f"✗ Quality score: {quality_report.quality_score:.1%} (expected {expected_score:.1%})")
        results.append(False)

    # Rejection details
    if len(quality_report.rejection_details) == expected_rejected:
        print(f"✓ Rejection details: {len(quality_report.rejection_details)} entries")
        results.append(True)
    else:
        print(f"✗ Rejection details: {len(quality_report.rejection_details)} entries (expected {expected_rejected})")
        results.append(False)

    # Show rejection details
    print("\n" + "-" * 60)
    print("REJECTION DETAILS:")
    print("-" * 60)
    for row_num, reason in sorted(quality_report.rejection_details.items(), key=lambda x: int(x[0])):
        print(f"  Row {row_num}: {reason[:80]}")

    # Show warnings
    if quality_report.warnings:
        print("\n" + "-" * 60)
        print("WARNINGS:")
        print("-" * 60)
        for warning in quality_report.warnings:
            print(f"  Row {warning['row']}: {warning['message']}")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY:")
    print("=" * 60)

    passed = sum(results)
    total = len(results)

    if all(results):
        print(f"✅ ALL TESTS PASSED ({passed}/{total})")
        print("\nQuality report implementation is working correctly!")
        return True
    else:
        print(f"❌ SOME TESTS FAILED ({passed}/{total} passed)")
        print("\nPlease review the failures above.")
        return False

    # Cleanup
    print("\n" + "=" * 60)
    print("CLEANUP:")
    print("=" * 60)

    # Delete test data
    quality_report.delete()
    upload.delete()
    customer.delete()
    print("✓ Test data cleaned up")

if __name__ == '__main__':
    try:
        success = test_quality_report()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
