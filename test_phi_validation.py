#!/usr/bin/env python
"""
Test PHI validation in CSV upload.

This script tests the validate_not_phi function to ensure it correctly
identifies and rejects patient-like names while allowing payer names.
"""

import sys
import os

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hello_world.settings')
import django
django.setup()

from payrixa.views import validate_not_phi

def test_phi_validation():
    """Test PHI validation with various inputs."""

    print("Testing PHI Validation")
    print("=" * 60)

    # Test cases that SHOULD be rejected (look like patient names)
    should_reject = [
        "John Smith",
        "Mary Johnson",
        "Robert Williams",
        "Patricia Brown",
        "Michael Davis",
        "Jennifer Miller"
    ]

    # Test cases that SHOULD be accepted (payer names)
    should_accept = [
        "Blue Cross Blue Shield",
        "Medicare",
        "Aetna",
        "UnitedHealthcare",
        "Humana",
        "Cigna",
        "Anthem",
        "Kaiser Permanente",
        "BCBS of Texas",
        "Medicare Part B",
        "Medicaid",
        "Tricare",
        "VA Benefits"
    ]

    # Test rejections
    print("\n1. Testing values that should be REJECTED (patient names):")
    print("-" * 60)
    rejected_count = 0
    for value in should_reject:
        try:
            validate_not_phi(value, field_name='payer')
            print(f"  ❌ FAIL: '{value}' was NOT rejected (should have been)")
        except ValueError as e:
            print(f"  ✅ PASS: '{value}' was correctly rejected")
            rejected_count += 1

    print(f"\nRejection test: {rejected_count}/{len(should_reject)} passed")

    # Test acceptances
    print("\n2. Testing values that should be ACCEPTED (payer names):")
    print("-" * 60)
    accepted_count = 0
    for value in should_accept:
        try:
            validate_not_phi(value, field_name='payer')
            print(f"  ✅ PASS: '{value}' was correctly accepted")
            accepted_count += 1
        except ValueError as e:
            print(f"  ❌ FAIL: '{value}' was rejected (should have been accepted)")
            print(f"      Error: {e}")

    print(f"\nAcceptance test: {accepted_count}/{len(should_accept)} passed")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY:")
    total_tests = len(should_reject) + len(should_accept)
    passed_tests = rejected_count + accepted_count
    print(f"Total tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {total_tests - passed_tests}")

    if passed_tests == total_tests:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️ {total_tests - passed_tests} test(s) failed")
        return 1

if __name__ == '__main__':
    exit_code = test_phi_validation()
    sys.exit(exit_code)
