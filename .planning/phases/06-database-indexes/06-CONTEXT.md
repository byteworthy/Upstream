# Phase 6: Database Indexes - Context

**Gathered:** 2026-02-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Add missing database indexes to improve query performance for webhook retry logic, alert rule evaluation, user profile lookups, and integration log queries. Focus on the 5 models specified in the roadmap: UserProfile, AlertRule, NotificationChannel, WebhookDelivery, IntegrationLog.

</domain>

<decisions>
## Implementation Decisions

### Execution Approach
- Fast execution prioritized (consistent with Phase 1-5 velocity)
- Minimal discussion overhead - trust Claude's judgment on database optimization best practices
- Follow Django and PostgreSQL conventions for index design

### Claude's Discretion

Claude has full discretion to make all implementation decisions for this phase:

**Index selection & design:**
- Which columns to index based on query analysis
- Index types (B-tree, partial, covering, composite)
- Index naming conventions
- Whether to use unique indexes where applicable

**Migration strategy:**
- CREATE INDEX CONCURRENTLY for zero-downtime
- Single migration vs multiple migrations
- Rollback safety approach
- Order of index creation

**Query analysis:**
- How to identify slow queries needing indexes
- Tools/methods for query plan analysis
- Performance improvement validation criteria

**Testing & validation:**
- Query plan verification approach (EXPLAIN ANALYZE)
- Performance metrics to capture
- Test coverage for indexed queries

</decisions>

<specifics>
## Specific Ideas

- Complement Phase 1 database work (transaction isolation and unique constraints)
- Build on existing covering indexes from quick-006 (aggregate query optimization)
- Maintain consistency with Phase 1's three-phase migration approach where appropriate
- Follow established patterns from quick tasks for database optimization

</specifics>

<deferred>
## Deferred Ideas

None — discussion focused on execution approach, technical decisions delegated to Claude.

</deferred>

---

*Phase: 06-database-indexes*
*Context gathered: 2026-02-01*
