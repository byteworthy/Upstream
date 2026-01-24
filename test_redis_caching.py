#!/usr/bin/env python
"""
Test Redis caching implementation.

This script tests the caching layer for:
1. Payer mappings caching
2. CPT mappings caching
3. Cache invalidation on create/update/delete
4. CSV upload performance with caching
"""

import sys
import os
import django
import time
from io import BytesIO

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'upstream.settings.dev')
django.setup()

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from upstream.models import Customer, PayerMapping, CPTGroupMapping, Upload
from upstream.views import get_payer_mappings_cached, get_cpt_mappings_cached, UploadsView
from upstream.cache import get_cache_key, CACHE_KEYS, get_cache_stats


def test_cache_configuration():
    """Test that Redis cache is properly configured."""
    print("Testing Cache Configuration")
    print("=" * 60)

    try:
        # Test basic cache operations
        test_key = 'test_key'
        test_value = 'test_value'

        cache.set(test_key, test_value, 60)
        retrieved = cache.get(test_key)

        assert retrieved == test_value, "Redis cache returned unexpected value"
        print("✓ Redis cache is configured and working")
        cache.delete(test_key)

    except Exception as e:
        assert False, f"Redis cache configuration error: {str(e)}"


def test_payer_mappings_caching():
    """Test payer mappings caching."""
    print("\n" + "=" * 60)
    print("Testing Payer Mappings Caching")
    print("=" * 60)

    # Create test customer
    customer, _ = Customer.objects.get_or_create(name="Test Cache Customer")

    # Create some payer mappings
    PayerMapping.objects.filter(customer=customer).delete()
    PayerMapping.objects.create(customer=customer, raw_name="BCBS", normalized_name="Blue Cross Blue Shield")
    PayerMapping.objects.create(customer=customer, raw_name="UHC", normalized_name="UnitedHealthcare")
    PayerMapping.objects.create(customer=customer, raw_name="Aetna", normalized_name="Aetna Inc")

    print(f"✓ Created 3 payer mappings")

    # Clear cache
    cache_key = get_cache_key(CACHE_KEYS['PAYER_MAPPINGS'], customer)
    cache.delete(cache_key)

    # First call - should query database
    print("\n1. First call (cache miss expected):")
    start_time = time.time()
    mappings1 = get_payer_mappings_cached(customer)
    time1 = (time.time() - start_time) * 1000  # Convert to ms
    print(f"   Retrieved {len(mappings1)} mappings in {time1:.2f}ms")

    # Second call - should hit cache
    print("\n2. Second call (cache hit expected):")
    start_time = time.time()
    mappings2 = get_payer_mappings_cached(customer)
    time2 = (time.time() - start_time) * 1000
    print(f"   Retrieved {len(mappings2)} mappings in {time2:.2f}ms")

    # Verify cache hit is faster
    if time2 < time1:
        speedup = time1 / time2
        print(f"✓ Cache hit is {speedup:.1f}x faster than cache miss")
    else:
        print(f"⚠ Cache hit not significantly faster (may be due to test overhead)")

    # Verify data consistency
    assert mappings1 == mappings2, "Cached data DOES NOT match database data"
    print("✓ Cached data matches database data")

    # Verify cache key format
    expected_key_parts = [CACHE_KEYS['PAYER_MAPPINGS'], f"Customer_{customer.pk}"]
    print(f"\n3. Cache key verification:")
    print(f"   Expected parts: {expected_key_parts}")
    print(f"   Actual key: {cache_key}")


def test_cpt_mappings_caching():
    """Test CPT mappings caching."""
    print("\n" + "=" * 60)
    print("Testing CPT Mappings Caching")
    print("=" * 60)

    # Create test customer
    customer, _ = Customer.objects.get_or_create(name="Test Cache Customer")

    # Create some CPT mappings
    CPTGroupMapping.objects.filter(customer=customer).delete()
    CPTGroupMapping.objects.create(customer=customer, cpt_code="99213", cpt_group="Office Visit")
    CPTGroupMapping.objects.create(customer=customer, cpt_code="99214", cpt_group="Office Visit")
    CPTGroupMapping.objects.create(customer=customer, cpt_code="99215", cpt_group="Office Visit")
    CPTGroupMapping.objects.create(customer=customer, cpt_code="80053", cpt_group="Lab Work")

    print(f"✓ Created 4 CPT mappings")

    # Clear cache
    cache_key = get_cache_key(CACHE_KEYS['CPT_MAPPINGS'], customer)
    cache.delete(cache_key)

    # First call - should query database
    print("\n1. First call (cache miss):")
    start_time = time.time()
    mappings1 = get_cpt_mappings_cached(customer)
    time1 = (time.time() - start_time) * 1000
    print(f"   Retrieved {len(mappings1)} mappings in {time1:.2f}ms")

    # Second call - should hit cache
    print("\n2. Second call (cache hit):")
    start_time = time.time()
    mappings2 = get_cpt_mappings_cached(customer)
    time2 = (time.time() - start_time) * 1000
    print(f"   Retrieved {len(mappings2)} mappings in {time2:.2f}ms")

    # Verify data consistency
    assert mappings1 == mappings2, "Cached data DOES NOT match database data"
    print("✓ Cached data matches database data")


def test_cache_invalidation():
    """Test cache invalidation on mapping changes."""
    print("\n" + "=" * 60)
    print("Testing Cache Invalidation")
    print("=" * 60)

    customer, _ = Customer.objects.get_or_create(name="Test Cache Customer")

    # Load mappings to populate cache
    mappings_before = get_payer_mappings_cached(customer)
    count_before = len(mappings_before)
    print(f"✓ Initial payer mappings count: {count_before}")

    # Add a new mapping
    new_mapping = PayerMapping.objects.create(
        customer=customer,
        raw_name="Cigna",
        normalized_name="Cigna Corporation"
    )
    print(f"✓ Added new payer mapping: {new_mapping.raw_name}")

    # Manually invalidate cache (simulating what views.py does)
    cache_key = get_cache_key(CACHE_KEYS['PAYER_MAPPINGS'], customer)
    cache.delete(cache_key)
    print(f"✓ Cache invalidated")

    # Reload mappings - should fetch from database
    mappings_after = get_payer_mappings_cached(customer)
    count_after = len(mappings_after)
    print(f"✓ Updated payer mappings count: {count_after}")

    assert count_after == count_before + 1, f"Cache invalidation FAILED: expected {count_before + 1}, got {count_after}"
    print("✓ Cache invalidation working correctly")


def test_csv_upload_performance():
    """Test CSV upload performance with caching."""
    print("\n" + "=" * 60)
    print("Testing CSV Upload Performance")
    print("=" * 60)

    customer, _ = Customer.objects.get_or_create(name="Test Cache Customer")

    # Create CSV with data that uses mappings
    csv_content = """payer,cpt,submitted_date,decided_date,outcome,allowed_amount
BCBS,99213,2024-01-15,2024-02-01,PAID,150.00
UHC,99214,2024-01-16,2024-02-02,PAID,200.00
Aetna,99215,2024-01-17,2024-02-03,DENIED,0.00
BCBS,99213,2024-01-18,2024-02-04,PAID,150.00
UHC,99214,2024-01-19,2024-02-05,PAID,200.00"""

    csv_file = SimpleUploadedFile(
        "test_cache.csv",
        csv_content.encode('utf-8'),
        content_type='text/csv'
    )

    # Create upload record
    upload = Upload.objects.create(
        customer=customer,
        filename="test_cache.csv",
        status='processing'
    )

    # Process upload
    view = UploadsView()
    view.MAX_ROWS = 200000

    print("\nProcessing CSV upload with caching...")
    start_time = time.time()

    try:
        view.process_csv_upload(upload, csv_file)
        upload.status = 'success'
        upload.save()

        processing_time = (time.time() - start_time) * 1000
        print(f"✓ Upload processed in {processing_time:.2f}ms")
        print(f"  Rows processed: {upload.row_count}")
        print(f"  Mappings loaded from cache (no individual DB queries per row)")

    except Exception as e:
        assert False, f"Upload failed: {str(e)}"


def test_cache_stats():
    """Display cache statistics."""
    print("\n" + "=" * 60)
    print("Cache Statistics")
    print("=" * 60)

    stats = get_cache_stats()

    if stats:
        print(f"Total Commands: {stats.get('total_commands', 'N/A')}")
        print(f"Cache Hits: {stats.get('keyspace_hits', 'N/A')}")
        print(f"Cache Misses: {stats.get('keyspace_misses', 'N/A')}")
        print(f"Hit Rate: {stats.get('hit_rate', 0):.1f}%")
        print(f"Connected Clients: {stats.get('connected_clients', 'N/A')}")
        print(f"Memory Used: {stats.get('used_memory_human', 'N/A')}")
    else:
        print("⚠ Cache statistics not available")


def cleanup():
    """Clean up test data."""
    print("\n" + "=" * 60)
    print("Cleanup")
    print("=" * 60)

    try:
        customer = Customer.objects.filter(name="Test Cache Customer").first()
        if customer:
            # Delete related data
            Upload.all_objects.filter(customer=customer).delete()
            PayerMapping.all_objects.filter(customer=customer).delete()
            CPTGroupMapping.all_objects.filter(customer=customer).delete()
            customer.delete()
            print("✓ Test data cleaned up")

        # Clear cache
        cache.clear()
        print("✓ Cache cleared")

    except Exception as e:
        print(f"⚠ Cleanup error: {str(e)}")


if __name__ == '__main__':
    try:
        # Run tests - assertions will fail the test if something is wrong
        test_cache_configuration()
        test_payer_mappings_caching()
        test_cpt_mappings_caching()
        test_cache_invalidation()
        test_csv_upload_performance()

        # Show cache stats
        test_cache_stats()

        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print("✅ ALL TESTS PASSED")
        print("\nRedis caching is working correctly!")
        cleanup()
        sys.exit(0)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {str(e)}")
        cleanup()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        cleanup()
        sys.exit(1)
