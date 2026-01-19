# Payrixa Project Status

## Purpose
Payrixa is a healthcare revenue cycle intelligence platform that detects payer behavior drift through statistical analysis of claims data. It provides actionable alerts when denial rates, decision times, or other key metrics deviate from historical baselines.

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

### Chunks 7-17: Platform Hardening (Complete ✅)

| Chunk | Feature | Status | Commit |
|-------|---------|--------|--------|
| 7 | API endpoint tests | ✅ Complete | - |
| 8 | Docker containerization | ✅ Complete | - |
| 9 | GitHub Actions CI | ✅ Complete | - |
| 10 | Celery async tasks | ✅ Complete | - |
| 11 | Monitoring stack (Prometheus/Grafana) | ✅ Complete | - |
| 12 | Performance and load testing | ✅ Complete | - |
| 13 | Slack integration and routing | ✅ Complete | ba8a00c |
| 14 | RBAC and permissions | ✅ Complete | 78faa62 |
| 15 | Excel exports | ✅ Complete | e3411c9 |
| 16 | Retention and rate limiting | ✅ Complete | bcd55aa |
| 17 | Ingestion spine and event log | ✅ Complete | 48a4d49 |

### Latest Features (Chunks 15-17)

**Chunk 15: Excel Export System**
- Multi-sheet Excel exports (summary + details)
- Customer-scoped with isolation
- Audit logging for compliance
- BytesIO streaming (no disk writes)

**Chunk 16: Operational Hardening**
- Data retention policies (uploads: 90d, artifacts: 30-90d, reports: 365d)
- Cleanup management command with dry-run mode
- In-memory rate limiting (100 req/60s, configurable)
- Per-IP tracking with 429 responses

**Chunk 17: Ingestion Spine (Critical Architecture)**
- Unified IngestionService for batch/webhook/streaming
- Append-only SystemEvent log for audit and fanout
- Token-based webhook authentication
- Idempotency support
- `publish_event()` - single fanout point for all system events
- Clean seams for future modules (DenialScope, ContractIQ)

## Test Suite Status
- **109 tests passing**
- **4 tests skipped** (external service integrations)
- **0 failures**
- All tests green ✅

## Running the Project

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Run checks
python manage.py check

# Run tests
python manage.py test

# Run development server
python manage.py runserver
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

## Next Steps

### Product Line Evolution
Payrixa is evolving from a single-product platform into a cohesive healthcare intelligence suite with 5 separate products:

**First Deployable Suite (5 Products)**:
1. **Payrixa Core** — External revenue risk signal detection (payer drift, existing)
2. **DenialScope** — Denial pattern intelligence and trend detection
3. **ContractIQ** — Payer contract intelligence and silent change detection
4. **OpsVariance** — Operational behavior drift (volume, no-shows, auth lag)
5. **AuthSignal** — Prior authorization risk tracking

### Sprint 1 Status (Scaffolding Only)
Sprint 1 implements architecture scaffolding only. No product analytics are implemented yet.

**Delivered**:
- Product enablement model (ProductConfig)
- Conditional product navigation
- DenialScope dashboard stub (empty state only)
- Insights feed stub (SystemEvent-driven)
- Product enablement gating (middleware + permissions)

**Not Delivered Yet**:
- DenialScope analytics
- ContractIQ parsing
- OpsVariance analytics
- AuthSignal analytics
- Payrixa Core refactor into product app

**Architecture Foundation Ready**:
With Chunk 17 ingestion spine complete, product line architecture can proceed:
- `IngestionService` for unified data entry across products
- `SystemEvent` log for cross-product insights and audit
- `ProductConfig` model for customer-level product enablement
- Strict data boundaries between products
- Existing RBAC and tenant isolation

**Next**: See `ARCHITECTURE_PRODUCT_LINE.md` for detailed product line architecture and Sprint 1 implementation details.

## Documentation
- `README.md` - Quick start and overview
- `SETTINGS_GUIDE.md` - Environment configuration
- `DOCKER.md` - Container setup
- `MONITORING.md` - Prometheus/Grafana setup
- `PERFORMANCE.md` - Load testing guide
- `CHANGELOG.md` - Version history
