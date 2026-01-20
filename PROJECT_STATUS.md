# Payrixa Project Status

## Purpose
Payrixa is a healthcare revenue cycle intelligence platform that detects payer behavior drift through statistical analysis of claims data. It provides actionable alerts when denial rates, decision times, or other key metrics deviate from historical baselines.

## V1 Focus: DenialScope
**One product. One signal. One story.**

V1 focuses exclusively on DenialScope — denial pattern intelligence and trend detection. Other product modules (ContractIQ, OpsVariance, AuthSignal) are scaffolded but disabled. This keeps V1 sharp and trustworthy.

### DenialScope Signal Chain ✅
1. **Data ingestion** → Claims uploaded with denial reason codes
2. **Aggregate computation** → Daily denial aggregates by payer/reason
3. **Signal detection** → Denial rate spikes, dollar spikes, new denial reasons
4. **Dashboard display** → Real metrics, real signals, real evidence
5. **SystemEvent publishing** → Signals flow to event log for audit

### Verified Signal Output
```
Signal: denial_dollars_spike
  Payer: Blue Cross Blue Shield
  Severity: critical
  Confidence: 1.0
  Summary: Denial Dollars spiked from $1,650 to $4,200
```

## Tech Stack
- **Backend**: Django 5.1.5, Python 3.12
- **Database**: PostgreSQL (production), SQLite (dev)
- **API**: Django REST Framework, JWT auth, OpenAPI/Swagger
- **Async**: Celery with Redis
- **Monitoring**: Prometheus + Grafana
- **Containerization**: Docker + Docker Compose
- **CI/CD**: GitHub Actions

## Feature Status

### Core Platform (Production Ready ✅)
- Multi-tenant customer management with RBAC
- Payer behavior drift detection engine
- Statistical analysis (denial rate, decision time, allowed amount)
- Weekly automated reporting with PDF/CSV exports
- Alert rules and event-driven notifications
- Email and webhook delivery channels
- Audit logging and domain events

### DenialScope (V1 Product ✅)
- Daily denial aggregate computation
- Signal detection: rate spikes, dollar spikes, new denial reasons
- Baseline vs recent window comparison
- Confidence scoring
- SystemEvent publishing
- Real dashboard with real metrics
- Deterministic test data generator (`generate_denialscope_test_data`)

### Platform Hardening (Complete ✅)

| Chunk | Feature | Status |
|-------|---------|--------|
| 7 | API endpoint tests | ✅ Complete |
| 8 | Docker containerization | ✅ Complete |
| 9 | GitHub Actions CI | ✅ Complete |
| 10 | Celery async tasks | ✅ Complete |
| 11 | Monitoring stack (Prometheus/Grafana) | ✅ Complete |
| 12 | Performance and load testing | ✅ Complete |
| 13 | Slack integration and routing | ✅ Complete |
| 14 | RBAC and permissions | ✅ Complete |
| 15 | Excel exports | ✅ Complete |
| 16 | Retention and rate limiting | ✅ Complete |
| 17 | Ingestion spine and event log | ✅ Complete |

## Test Suite Status
- **117 tests passing**
- **4 tests skipped** (external service integrations)
- **0 failures**
- All tests green ✅

## Running the Project

### Quick Start with Demo Data
```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Load demo customer
python manage.py loaddata demo_data

# Generate test claims with denial spike pattern
python manage.py generate_denialscope_test_data --customer 1 --clear

# Compute DenialScope signals
python manage.py compute_denialscope --customer 1

# Run development server
python manage.py runserver
```

### Expected Output
```
Computing DenialScope for Riverside Family Practice...
✓ DenialScope computation complete
  Aggregates created: 46
  Signals created: 1
```

### Docker
```bash
# Start all services
docker-compose up

# Run tests in Docker
docker-compose run app python manage.py test
```

### CI/CD
GitHub Actions runs on every push:
- Django system checks
- Full test suite
- PostgreSQL service container

## Known Skipped Tests
- 4 tests skip external service dependencies (email SMTP, Slack webhooks)
- These are integration tests requiring live credentials
- Unit test coverage is complete

## Product Line Architecture

### V1 Active Products
| Product | Status | Analytics |
|---------|--------|-----------|
| **DenialScope** | ✅ Active | ✅ Real signals |

### Future Products (Scaffolded, Disabled)
| Product | Status | Analytics |
|---------|--------|-----------|
| Payrixa Core | Gated | ✅ Real (drift detection) |
| ContractIQ | Hidden | ❌ Stub only |
| OpsVariance | Hidden | ❌ Stub only |
| AuthSignal | Hidden | ❌ Stub only |

**Note**: Other products are scaffolded but hidden from navigation. V1 ships with DenialScope only to maintain focus and trust.

## Documentation
- `README.md` - Quick start and overview
- `SETTINGS_GUIDE.md` - Environment configuration
- `DOCKER.md` - Container setup
- `MONITORING.md` - Prometheus/Grafana setup
- `PERFORMANCE.md` - Load testing guide
- `CHANGELOG.md` - Version history
- `ARCHITECTURE_PRODUCT_LINE.md` - Multi-product architecture
