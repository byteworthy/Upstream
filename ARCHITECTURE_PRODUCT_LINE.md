# Payrixa Product Line Architecture

This document defines the product line architecture for the first deployable suite:
- Payrixa Core
- DenialScope
- ContractIQ
- OpsVariance
- AuthSignal

Scope: Web app only. No desktop application.

## 1. System architecture

**Payrixa Core remains the signal engine.** It owns payer drift detection, claim pattern variance, signal generation, and alert creation. Core logic stays in current locations for Sprint 1 to avoid behavior changes.

**Module isolation.** Each additional product is an isolated Django app that owns its own tables, services, and templates. Products do not import each other’s models. Cross-product insights flow only through shared read models and the SystemEvent feed.

**Data boundaries.**
- Product-owned tables are writeable only by the owning product.
- Shared tables (Customer, Upload, SystemEvent) are read-only outside their owner.
- No direct joins across product tables in application code.

**Cross-product insight sharing.**
- Products publish events into SystemEvent using a shared publish_event entry point.
- Dashboards can render cross-product signals by reading SystemEvent without importing product models.
- Any shared summaries are created as read-only view models or service outputs, not shared tables.

## 2. Django project and folder structure

Sprint 1 adds new folders without moving existing logic.

```
payrixa/
├── core/                      # Shared primitives (BaseModel, SystemConfiguration)
├── products/                  # Product apps (new)
│   ├── denialscope/           # Denial pattern intelligence
│   ├── contractiq/            # Contract intelligence
│   ├── opsvariance/           # Operational drift
│   └── authsignal/            # Prior authorization risk
├── platform/                  # Logical grouping for existing platform services (no moves in Sprint 1)
│   ├── ingestion/             # Existing ingestion spine
│   ├── alerts/                # Existing alerting
│   ├── exports/               # Existing exports
│   └── integrations/          # Existing integrations
├── ui/                        # UI shell and shared components (new)
│   ├── shell/                 # Navigation, base layout helpers
│   ├── components/            # Reusable widgets, empty states, filters
│   └── dashboards/            # Product-specific templates
├── api/                       # Existing API layer
├── templates/payrixa/         # Existing templates (base.html stays unchanged)
└── [existing files remain in place]
```

**Payrixa Core product app**: deferred to Sprint 2 to avoid duplicate sources of truth.

## 3. UI and UX system architecture

**Unified UI shell.** The existing top navigation remains. New product nav items are added conditionally based on enablement. No base template rewrites.

**Product-specific dashboards.** Each product has a dedicated dashboard page that extends the existing base layout. Sprint 1 dashboards show empty states only.

**Shared insight feed.** A shared insight feed page reads SystemEvent for the current customer and renders an empty state when no events exist.

**Consistent patterns.**
- Global filters and date range patterns are consistent across dashboards.
- Empty, loading, and error states are explicit and consistent.
- Accessibility: focus states, semantic headings, and readable contrast.
- Performance: server-rendered templates, minimal payload.

## 4. Dashboard information design

**Payrixa Core**
- Primary dashboard: existing drift feed page (Payrixa Core signal feed)
- Key widgets: drift summary, top movers, recent alerts
- Key tables: drift events by payer, drift events by CPT group
- Trend charts: denial rate drift over time, decision time variance
- Alert cards: highest severity drift events
- Drill-down: payer → CPT group → claim sample
- Data shape (templates):
  - `drift_events`: list of {payer, cpt_group, drift_type, severity, baseline_value, current_value, delta_value, current_start, current_end}
  - `alert_events`: list of {severity, title, created_at}

**DenialScope**
- Primary dashboard: denialscope dashboard
- Key widgets: denial reason volume, new reason emergence
- Key tables: denial reasons by volume, denial reasons by payer
- Trend charts: top denial reason trendlines
- Alert cards: new denial codes detected
- Drill-down: denial reason → payer → claim examples
- Data shape (templates):
  - `denial_reasons`: list of {code, description, count, change_pct}
  - `new_denials`: list of {code, first_seen_at}

**ContractIQ**
- Primary dashboard: contractiq dashboard
- Key widgets: variance summary, silent change alerts
- Key tables: expected vs actual reimbursement by payer
- Trend charts: variance trend per payer
- Alert cards: silent contract changes
- Drill-down: payer → contract term → claim variance
- Data shape (templates):
  - `contract_variances`: list of {payer, expected_amount, actual_amount, variance_amount}

**OpsVariance**
- Primary dashboard: opsvariance dashboard
- Key widgets: visit volume variance, no-show rate, cancellation rate
- Key tables: service line variance
- Trend charts: volume by day/week, no-show trend
- Alert cards: abnormal operational shifts
- Drill-down: service line → provider → schedule view
- Data shape (templates):
  - `volume_variances`: list of {service_line, baseline, current, delta}

**AuthSignal**
- Primary dashboard: authsignal dashboard
- Key widgets: auth turnaround time, approval fallout rate
- Key tables: service line exposure
- Trend charts: auth turnaround by payer
- Alert cards: high-risk service lines
- Drill-down: service line → payer → auth status
- Data shape (templates):
  - `auth_metrics`: list of {service_line, avg_turnaround_days, approval_rate}

## 5. Data ownership and boundaries

**Owned by Payrixa Core (existing):**
- ClaimRecord, DriftEvent, ReportRun, Upload, PayerMapping, CPTGroupMapping

**Owned by DenialScope (future):**
- DenialReason, DenialTrend

**Owned by ContractIQ (future):**
- Contract, ContractTerm, ContractVariance

**Owned by OpsVariance (future):**
- OpsMetric, OpsVarianceEvent

**Owned by AuthSignal (future):**
- AuthorizationRecord, AuthRiskSignal

**Shared read-only:**
- Customer
- SystemEvent

**Strict rules:**
- Products do not import each other’s models.
- Products only reference Customer by FK.
- Cross-product correlations use SystemEvent and service outputs.

## 6. API and internal service boundaries

**Service layer patterns:**
- Each product exposes read-model builders (e.g., `get_denialscope_dashboard(customer, filters)`)
- API layer calls service functions and returns dictionaries
- Templates render dictionaries, not model objects

**SystemEvent fanout:**
- Products emit SystemEvent via a shared publish_event function
- Insight feed reads SystemEvent only
- No direct event fanout between product models

**Coupling prevention:**
- No imports from `products/*/models.py` across product boundaries
- No shared “analytics” tables
- No shared mutable model base classes beyond BaseModel

## 7. Enablement and SKU separation

**Product enablement model:**
- ProductConfig: `{customer, product_slug, enabled, config_json, created_at, updated_at}`
- Product slugs: `payrixa-core`, `denialscope`, `contractiq`, `opsvariance`, `authsignal`

**UI enforcement:**
- Navigation shows only enabled products
- Empty state dashboards still require enablement

**API enforcement:**
- Middleware injects `request.enabled_products`
- View decorators guard access for disabled products
- Admin toggles per customer

**Billing separation (future):**
- ProductConfig allows future billing without refactoring

## 8. Anti-patterns to avoid

- Importing product models across domains
- Creating a global analytics table shared by all products
- Hiding product logic inside templates
- Building cross-product joins in Django ORM
- Coupling product services to each other’s service functions
- Overwriting or forking Payrixa Core logic in new apps

## 9. Sprint 1 execution plan

**Goal:** Architecture scaffolding and UI foundation only.

**Tasks (in order):**
1. Create `products/` folder with 4 empty Django apps (DenialScope, ContractIQ, OpsVariance, AuthSignal)
2. Add ProductConfig model and admin toggle
3. Add product-aware navigation (additive only, base layout unchanged)
4. Create stub dashboards for Payrixa Core (existing drift feed) and DenialScope (empty state)
5. Create shared insight feed page backed by SystemEvent (empty state if none)
6. Add enablement middleware and permission gates
7. Add tests for enablement and nav visibility
8. Run `python manage.py check` and `python manage.py test`

**Sprint 1 deliverables:**
- Folder structure in place
- Product enablement model
- Unified UI shell with conditional navigation
- Stub dashboards (Payrixa Core + DenialScope)
- Insight feed stub
- Tests for gating and nav visibility

**Sprint 1 constraints:**
- No new business logic
- No analytics for new products
- No Payrixa Core code moves

## 10. Readiness checklist

- [ ] Parallel development safe (isolated product apps)
- [ ] UI consistency enforced (base template preserved)
- [ ] Data contracts clear (service boundaries documented)
- [ ] Payrixa Core logic protected (no moves in Sprint 1)
- [ ] Product enablement implemented
- [ ] Navigation gated by enablement
- [ ] Tests cover gating and nav visibility

## Sprint 1 status (post-implementation update)

**Status:** Complete. Sprint 1 is scaffolding only. No product analytics implemented.

**Delivered**:
- Product enablement model (ProductConfig)
- Conditional product navigation
- DenialScope dashboard stub (empty state only)
- Insights feed stub (SystemEvent-driven)
- Product enablement gating (middleware + permissions)
- Tests for enablement and navigation

**Not Delivered Yet**:
- DenialScope analytics
- ContractIQ parsing
- OpsVariance analytics
- AuthSignal analytics
- Payrixa Core refactor into product app
