# Performance & Load Testing Guide

This document describes the performance testing tools and procedures for Upstream.

## Overview

Upstream includes comprehensive performance testing tools:
1. **Synthetic Data Generation** - Create large datasets for testing
2. **Drift Detection Benchmarking** - Measure drift algorithm performance
3. **API Load Testing** - Test API endpoints under load with Locust

## Synthetic Data Generation

Generate large datasets to test performance at scale.

### Usage

```bash
# Generate 100K claim records
python manage.py generate_synthetic_data --records 100000 --customer 1

# Generate 1M records in batches of 5000
python manage.py generate_synthetic_data --records 1000000 --customer 1 --batch-size 5000
```

### Parameters

- `--records` - Number of claim records to generate
- `--customer` - Customer ID to associate records with
- `--batch-size` - Batch size for bulk creation (default: 1000)

### Performance Characteristics

- **100K records**: ~10-15 seconds
- **500K records**: ~50-60 seconds
- **1M records**: ~2-3 minutes

## Drift Detection Benchmarking

Measure the performance of the drift detection algorithm.

### Usage

```bash
# Run benchmark with default 3 runs
python manage.py benchmark_drift --customer 1

# Run with 5 benchmark iterations
python manage.py benchmark_drift --customer 1 --runs 5
```

### Metrics Tracked

- **Runtime** - Total execution time
- **Memory usage** - Peak memory consumption
- **Throughput** - Claims processed per second
- **Events detected** - Number of drift events found

### Expected Performance

| Dataset Size | Target Throughput | Target Memory |
|--------------|-------------------|---------------|
| 10K claims   | >10,000 claims/s  | <50 MB        |
| 100K claims  | >5,000 claims/s   | <200 MB       |
| 500K claims  | >2,000 claims/s   | <500 MB       |
| 1M claims    | >1,000 claims/s   | <1 GB         |

### Performance Assessment

The benchmark automatically assesses performance:
- **Excellent**: >10,000 claims/sec
- **Good**: >5,000 claims/sec
- **Acceptable**: >1,000 claims/sec
- **Needs optimization**: <1,000 claims/sec

## API Load Testing with Locust

Test API endpoints under concurrent load.

### Setup

```bash
# Install Locust (already in requirements.txt)
pip install locust

# Start Locust
locust --host=http://localhost:8000

# Or specify users and spawn rate directly
locust --host=http://localhost:8000 --users 100 --spawn-rate 10
```

### Web Interface

Open http://localhost:8089 to:
1. Set number of users (concurrent connections)
2. Set spawn rate (users per second)
3. Start/stop tests
4. View real-time statistics and charts

### User Classes

**PayrixaAPIUser** (default)
- Simulates authenticated API users
- Tests: health, dashboard, drift feed, payer summary, claims

**AdminUser**
- Simulates administrative users
- Tests: customer management, report runs

**UnauthenticatedUser**
- Tests authentication/authorization
- Expects 401/403 responses

### Running Specific User Classes

```bash
# Run only API users
locust --host=http://localhost:8000 PayrixaAPIUser

# Run mix of user types
locust --host=http://localhost:8000 PayrixaAPIUser AdminUser
```

### Key Metrics

- **Requests per second (RPS)** - Throughput
- **Response time (p50, p95, p99)** - Latency percentiles
- **Failure rate** - Error percentage
- **Number of users** - Concurrent connections

### Performance Targets

| Endpoint | Target RPS | Target p95 Latency |
|----------|------------|-------------------|
| Health   | 1000+      | <50ms             |
| Dashboard| 500+       | <200ms            |
| Drift Feed| 300+      | <500ms            |
| Claims   | 200+       | <1000ms           |

## Running Performance Tests in CI

Add performance regression tests to CI:

```yaml
# .github/workflows/performance.yml
name: Performance Tests
on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly
  workflow_dispatch:  # Manual trigger

jobs:
  benchmark:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Generate test data
        run: python manage.py generate_synthetic_data --records 10000 --customer 1
      - name: Run benchmark
        run: python manage.py benchmark_drift --customer 1 --runs 3
```

## Profiling Slow Operations

### CPU Profiling

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Your code here
detect_drift_events(customer)

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)  # Top 20 functions
```

### Memory Profiling

```python
from memory_profiler import profile

@profile
def my_function():
    # Your code here
    pass
```

Run with:
```bash
python -m memory_profiler your_script.py
```

## Optimization Tips

### Database Queries

1. **Use select_related/prefetch_related**
   ```python
   ClaimRecord.objects.select_related('customer').filter(...)
   ```

2. **Add database indexes**
   ```python
   class Meta:
       indexes = [
           models.Index(fields=['customer', 'service_date']),
       ]
   ```

3. **Use bulk operations**
   ```python
   ClaimRecord.objects.bulk_create(claims, batch_size=1000)
   ```

### Caching

1. **Cache expensive computations**
   ```python
   from django.core.cache import cache
   
   result = cache.get('drift_summary_1')
   if not result:
       result = expensive_calculation()
       cache.set('drift_summary_1', result, timeout=3600)
   ```

2. **Use Redis for session storage**
   ```python
   SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
   SESSION_CACHE_ALIAS = 'default'
   ```

### API Optimization

1. **Pagination** - Always paginate large result sets
2. **Field selection** - Return only needed fields
3. **Compression** - Enable gzip middleware
4. **Rate limiting** - Prevent abuse

## Troubleshooting

### Slow Drift Detection

1. Check database query count with Django Debug Toolbar
2. Add indexes on frequently queried fields
3. Consider query optimization or denormalization
4. Use database explain analyze

### High Memory Usage

1. Process data in batches/chunks
2. Use database cursors for large querysets
3. Avoid loading entire datasets into memory
4. Profile with memory_profiler

### API Timeouts

1. Check database connection pooling
2. Verify no N+1 query problems
3. Add caching for expensive operations
4. Consider async processing for long-running tasks

## Best Practices

1. **Test at scale** - Use realistic dataset sizes
2. **Measure regularly** - Track performance over time
3. **Set baselines** - Know your performance targets
4. **Monitor in production** - Use Prometheus/Grafana
5. **Profile before optimizing** - Find actual bottlenecks
6. **Document changes** - Track what improved performance

## Additional Resources

- [Django Performance Tips](https://docs.djangoproject.com/en/stable/topics/performance/)
- [Locust Documentation](https://docs.locust.io/)
- [Python Profiling Guide](https://docs.python.org/3/library/profile.html)
