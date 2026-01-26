# Requirements: Phase 3 Technical Debt Remediation

**Defined:** 2026-01-26
**Core Value:** Production-ready database performance and API reliability

## v1 Requirements

Requirements for Phase 3 completion. Each maps to roadmap phases.

### Database Optimization

- [ ] **DB-01**: Fix transaction isolation for concurrent drift detection - Drift computations run concurrently without race conditions or duplicate alert creation
- [ ] **DB-02**: Implement unique constraints for data integrity - Add UniqueConstraint on key fields with backwards-compatible 3-phase migrations

### API Improvements

- [x] **API-01**: Add pagination to custom actions - All custom ViewSet @action methods return paginated responses
- [x] **API-02**: Implement SearchFilter and DjangoFilterBackend - Users can search and filter API list endpoints by key fields
- [ ] **API-03**: Standardize error responses - All endpoints return consistent error format with status codes, detail messages, and field-level errors
- [ ] **API-04**: Add complete OpenAPI documentation - drf-spectacular generates 100% API docs with examples for all endpoints

### Testing

- [ ] **TEST-01**: Create webhook integration tests - Test webhook delivery, retry logic, signature validation, and idempotency with real HTTP calls
- [ ] **TEST-02**: Add performance tests - Locust load tests validate p95 response times <500ms under realistic load patterns
- [ ] **TEST-03**: Fix disabled rollback test - Deployment workflow rollback test passes and validates automated rollback functionality
- [ ] **TEST-04**: Add RBAC cross-role tests - Test suite validates customer isolation works across superuser, customer admin, and regular user roles

## v2 Requirements

Deferred to Phase 4 and beyond.

### Polish & Documentation

- **DOC-01**: Implement password reset flow
- **DOC-02**: Add HATEOAS links to API responses
- **DOC-03**: Enable structured logging (JSON format)
- **DOC-04**: Add deployment notifications (Slack/email)
- **DOC-05**: Monitoring improvements (custom Prometheus metrics)

### Architecture

- **ARCH-01**: Separate Redis instances for cache vs Celery
- **ARCH-02**: Implement Redis Sentinel for high availability
- **ARCH-03**: Add connection pooling with PgBouncer
- **ARCH-04**: Streaming CSV processing for large uploads

## Out of Scope

Explicitly excluded to prevent scope creep.

| Feature | Reason |
|---------|--------|
| GraphQL API | Adds complexity without value for healthcare SaaS use case |
| Real-time WebSockets | Polling is sufficient; WebSockets add operational complexity |
| Unfiltered SELECT FOR UPDATE | Causes table-level locks and deadlocks; must be selective |
| Global SERIALIZABLE isolation | Performance killer; use READ COMMITTED + selective locks |
| drf-yasg for OpenAPI | Unmaintained, OpenAPI 2.0 only; use drf-spectacular instead |
| psycopg3 migration | Too risky for zero-downtime requirement; defer to post-Phase 3 |
| New features or capabilities | Technical debt remediation only; no product enhancements |
| Frontend changes | Backend-only scope |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DB-01 | Phase 1 | Complete |
| DB-02 | Phase 1 | Complete |
| API-01 | Phase 2 | Complete |
| API-02 | Phase 2 | Complete |
| API-03 | Phase 3 | Pending |
| API-04 | Phase 3 | Pending |
| TEST-01 | Phase 4 | Pending |
| TEST-04 | Phase 4 | Pending |
| TEST-02 | Phase 5 | Pending |
| TEST-03 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 10 total
- Mapped to phases: 10/10 (100% coverage)
- Complete: 2/10 (20%)
- Unmapped: 0

---
*Requirements defined: 2026-01-26*
*Last updated: 2026-01-26 after roadmap creation*
