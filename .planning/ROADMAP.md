# Roadmap: Phase 3 Technical Debt Remediation

## Overview

Phase 3 delivers production-ready database performance and API reliability through systematic remediation of 10 medium-priority technical debt items. We start with database correctness (transaction isolation and unique constraints), build API usability layers (pagination, filtering, documentation, error handling), and validate with comprehensive testing (webhooks, RBAC, performance, deployment rollback). The journey progresses from foundation (data integrity) to polish (testing and observability).

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Transaction Isolation & Unique Constraints** - Database correctness foundation
- [x] **Phase 2: API Pagination & Filtering** - List endpoint usability
- [x] **Phase 3: OpenAPI Documentation & Error Standardization** - API developer experience
- [x] **Phase 4: Webhook & RBAC Testing** - Integration test coverage
- [x] **Phase 5: Performance Testing & Rollback Fix** - Production reliability validation
- [x] **Phase 6: Database Indexes** - Query performance optimization
- [ ] **Phase 7: Frontend Unit Tests for Critical Components** - Specialty module test coverage

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

**Completed:** 2026-01-26

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
**Plans**: 2 plans

Plans:
- [x] 03-01-PLAN.md — Add @extend_schema decorators to all ViewSets with tags and examples
- [x] 03-02-PLAN.md — Standardize error responses and document in OpenAPI schema

**Completed:** 2026-02-01

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
- [x] 04-01-PLAN.md — Webhook integration tests with responses library (delivery, retry, signature, idempotency)
- [x] 04-02-PLAN.md — RBAC customer isolation tests across all ViewSets (superuser, admin, viewer roles)

**Completed:** 2026-01-26

### Phase 5: Performance Testing & Rollback Fix
**Goal**: Load testing validates production performance targets and deployment rollback automation works
**Depends on**: Phase 4
**Requirements**: TEST-02, TEST-03
**Success Criteria** (what must be TRUE):
  1. Locust load tests validate p95 response times <500ms for key endpoints under realistic load
  2. Load tests identify performance bottlenecks (database queries, Celery tasks, serialization)
  3. Deployment workflow rollback test passes and validates automated rollback functionality
  4. Performance test suite runs in CI and fails if response time SLAs violated
**Plans**: 2 plans

Plans:
- [x] 05-01-PLAN.md — Create Locust performance test suite and CI integration
- [x] 05-02-PLAN.md — Create deployment rollback test and workflow integration

**Completed:** 2026-01-26

### Phase 6: Database Indexes
**Goal**: Add missing database indexes to improve query performance for webhook retry logic, alert rule evaluation, and user profile lookups
**Depends on**: Phase 1 (complements database work)
**Requirements**: DB-03 (implicit - query performance optimization)
**Success Criteria** (what must be TRUE):
  1. Webhook retry queries use indexes instead of full table scans
  2. Alert rule evaluation queries use indexes for enabled+customer filters
  3. User profile lookups use indexes for foreign key relationships
  4. Integration log queries use indexes for connection history and status monitoring
**Plans**: 1 plan

Plans:
- [x] 06-01-PLAN.md — Add composite (customer, role) index to UserProfile and partial (customer, -routing_priority) index to AlertRule

**Completed:** 2026-02-01

### Phase 7: Frontend Unit Tests for Critical Components
**Goal**: Achieve 80%+ test coverage on the specialty module system through comprehensive unit tests for CustomerContext, SpecialtyRoute, Settings, Dashboard, and Sidebar components
**Depends on**: Phase 6
**Requirements**: Frontend test coverage for specialty module system
**Success Criteria** (what must be TRUE):
  1. CustomerContext tests validate enableSpecialty, disableSpecialty, hasSpecialty functions
  2. SpecialtyRoute tests confirm route guard redirects correctly for unauthorized specialty access
  3. Settings SpecialtyModulesCard tests validate toggle enable/disable functionality
  4. Dashboard SpecialtyWidgets tests verify conditional rendering based on enabled specialties
  5. Sidebar tests confirm dynamic navigation updates based on specialty configuration
**Plans**: 3 plans

Plans:
- [ ] 07-01-PLAN.md — SpecialtyRoute and Sidebar component tests (routing guards, dynamic navigation)
- [ ] 07-02-PLAN.md — Settings SpecialtyModulesCard tests (toggle enable/disable functionality)
- [ ] 07-03-PLAN.md — Dashboard SpecialtyWidgets tests and full suite verification

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Transaction Isolation & Unique Constraints | 2/2 | Complete | 2026-01-26 |
| 2. API Pagination & Filtering | 2/2 | Complete | 2026-01-26 |
| 3. OpenAPI Documentation & Error Standardization | 2/2 | Complete | 2026-02-01 |
| 4. Webhook & RBAC Testing | 2/2 | Complete | 2026-01-26 |
| 5. Performance Testing & Rollback Fix | 2/2 | Complete | 2026-01-26 |
| 6. Database Indexes | 1/1 | Complete | 2026-02-01 |
| 7. Frontend Unit Tests for Critical Components | 0/3 | Planned | - |
