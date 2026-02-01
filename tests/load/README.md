# Load Testing

This directory contains load tests for Upstream Healthcare using [Locust](https://locust.io/).

## Quick Start

### Install Locust

```bash
pip install locust
```

### Run Tests Locally

Start the application first, then run Locust:

```bash
# Start web UI (recommended for development)
locust -f tests/load/locustfile.py --host=http://localhost:8000

# Open browser to http://localhost:8089
```

### Run Headless (CI/CD)

```bash
locust -f tests/load/locustfile.py \
    --host=http://localhost:8000 \
    --users 100 \
    --spawn-rate 10 \
    --run-time 5m \
    --headless \
    --csv=results/load_test
```

## User Classes

### SignupFlowUser
Simulates users going through the complete signup process:
- Landing page visits
- Pricing page visits
- Account registration

### BrowsingUser
Simulates casual browsers on the marketing site:
- Landing page
- Features page
- Pricing page
- Case studies
- Security page

### APIUser
Simulates authenticated users accessing the API:
- Claims listing
- Dashboard data
- Usage statistics
- Health checks

### StripeWebhookUser
Simulates Stripe webhook events:
- checkout.session.completed
- customer.subscription.updated
- invoice.payment_succeeded

## Test Scenarios

### Signup Load Test
Tests capacity for new user signups:

```bash
locust -f tests/load/locustfile.py \
    --host=https://staging.upstream.com \
    --users 50 \
    --spawn-rate 5 \
    --run-time 10m \
    --headless \
    --only-summary
```

### Marketing Site Stress Test
Tests marketing site under high traffic:

```bash
locust -f tests/load/locustfile.py \
    --host=https://staging.upstream.com \
    --users 500 \
    --spawn-rate 50 \
    --run-time 15m \
    --headless \
    --tags browsing
```

### API Soak Test
Long-running test for memory leaks:

```bash
locust -f tests/load/locustfile.py \
    --host=https://staging.upstream.com \
    --users 100 \
    --spawn-rate 10 \
    --run-time 1h \
    --headless \
    --tags api
```

## Performance Targets

| Metric | Target | Critical |
|--------|--------|----------|
| p95 Response Time | < 500ms | < 2000ms |
| Error Rate | < 0.1% | < 1% |
| Throughput | > 100 RPS | > 50 RPS |

## Distributed Mode

For higher load, run Locust in distributed mode:

```bash
# Master
locust -f tests/load/locustfile.py --master

# Workers (run on multiple machines)
locust -f tests/load/locustfile.py --worker --master-host=<master-ip>
```

## Environment Variables

- `LOCUST_HOST`: Default host URL
- `LOCUST_USERS`: Default number of users
- `LOCUST_SPAWN_RATE`: Default spawn rate

## Results

Results are written to the `results/` directory:
- `load_test_stats.csv`: Per-request statistics
- `load_test_failures.csv`: Failure details
- `load_test_stats_history.csv`: Time-series data

## Best Practices

1. **Always test on staging first** - Never run load tests against production without approval

2. **Start small** - Begin with 10-20 users and scale up

3. **Monitor backend** - Watch CPU, memory, database connections during tests

4. **Clean up test data** - Remove test accounts after testing

5. **Run during off-peak** - Schedule tests when traffic is low
