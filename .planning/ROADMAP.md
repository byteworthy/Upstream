# Roadmap: Phase 3 Technical Debt Remediation

## Overview

Phase 3 delivers production-ready database performance and API reliability through systematic remediation of 10 medium-priority technical debt items. We start with database correctness (transaction isolation and unique constraints), build API usability layers (pagination, filtering, documentation, error handling), and validate with comprehensive testing (webhooks, RBAC, performance, deployment rollback). The journey progresses from foundation (data integrity) to polish (testing and observability).

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Transaction Isolation & Unique Constraints** - Database correctness foundation
- [ ] **Phase 2: API Pagination & Filtering** - List endpoint usability
- [ ] **Phase 3: OpenAPI Documentation & Error Standardization** - API developer experience
- [ ] **Phase 4: Webhook & RBAC Testing** - Integration test coverage
- [ ] **Phase 5: Performance Testing & Rollback Fix** - Production reliability validation

## Phase Details

### Phase 1: Transaction Isolation & Unique Constraints
**Goal**: Database operations prevent race conditions and maintain data integrity through transaction isolation and unique constraints
**Depends on**: Nothing (first phase)
**Requirements**: DB-01, DB-02
**Success Criteria** (what must be TRUE):
  1. Concurrent drift detection runs on same customer data do not create duplicate alerts
  2. Database rejects duplicate records on key fields (email, claim numbers, tenant+user combinations)
  3. Unique constraint migrations deploy to production without downtime or data loss
  4. Transaction isolation prevents race conditions in drift computation and alert creation
**Plans**: 2 plans

Plans:
- [x] 01-01-PLAN.md — Add transaction isolation with select_for_update() to drift detection
- [x] 01-02-PLAN.md — Implement unique constraints via three-phase migrations

### Phase 2: API Pagination & Filtering
**Goal**: All API list endpoints support pagination and user-driven filtering for large datasets
**Depends on**: Phase 1
**Requirements**: API-01, API-02
**Success Criteria** (what must be TRUE):
  1. Custom ViewSet actions (feedback, dashboard) return paginated responses with page_size control
  2. Users can search API endpoints by key fields (claim numbers, payer names, date ranges)
  3. Users can filter list endpoints using DjangoFilterBackend (status, severity, date ranges)
  4. API documentation shows available filters and search fields for each endpoint
**Plans**: 2 plans

Plans:
- [x] 02-01-PLAN.md — Install django-filter, create FilterSet classes, add filter backends to ViewSets
- [x] 02-02-PLAN.md — Add pagination to custom actions, tests for filtering and pagination

**Completed:** 2026-01-26

### Phase 3: OpenAPI Documentation & Error Standardization
**Goal**: Complete API documentation and consistent error handling across all endpoints
**Depends on**: Phase 2
**Requirements**: API-03, API-04
**Success Criteria** (what must be TRUE):
  1. All endpoints return standardized error responses with status codes, detail messages, and field-level errors
  2. drf-spectacular generates 100% OpenAPI documentation for all endpoints, actions, and filters
  3. API documentation includes request/response examples for every endpoint
  4. Validation errors, authentication errors, and permission errors use consistent format
**Plans**: TBD

Plans:
- [ ] 03-01: TBD
- [ ] 03-02: TBD

### Phase 4: Webhook & RBAC Testing
**Goal**: Integration tests validate webhook delivery and customer isolation across roles
**Depends on**: Phase 3
**Requirements**: TEST-01, TEST-04
**Success Criteria** (what must be TRUE):
  1. Webhook tests validate delivery, retry logic, signature validation, and idempotency with real HTTP calls
  2. RBAC tests confirm superuser can access all customers, customer admin can access own customer, regular user has read-only access
  3. RBAC tests validate customer isolation (user from Customer A cannot access Customer B data)
  4. Test suite fails if webhook delivery or retry logic breaks
**Plans**: 2 plans

Plans:
- [ ] 04-01-PLAN.md — Webhook integration tests with responses library (delivery, retry, signature, idempotency)
- [ ] 04-02-PLAN.md — RBAC customer isolation tests across all ViewSets (superuser, admin, viewer roles)

### Phase 5: Performance Testing & Rollback Fix
**Goal**: Load testing validates production performance targets and deployment rollback automation works
**Depends on**: Phase 4
**Requirements**: TEST-02, TEST-03
**Success Criteria** (what must be TRUE):
  1. Locust load tests validate p95 response times <500ms for key endpoints under realistic load
  2. Load tests identify performance bottlenecks (database queries, Celery tasks, serialization)
  3. Deployment workflow rollback test passes and validates automated rollback functionality
  4. Performance test suite runs in CI and fails if response time SLAs violated
**Plans**: TBD

Plans:
- [ ] 05-01: TBD
- [ ] 05-02: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Transaction Isolation & Unique Constraints | 2/2 | Complete | 2026-01-26 |
| 2. API Pagination & Filtering | 0/2 | Not started | - |
| 3. OpenAPI Documentation & Error Standardization | 0/TBD | Not started | - |
| 4. Webhook & RBAC Testing | 0/2 | Not started | - |
| 5. Performance Testing & Rollback Fix | 0/TBD | Not started | - |
