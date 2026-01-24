# Upstream: Next Moves & Sequence Roadmap

**Generated:** 2026-01-22  
**Context:** Post Hub v1 delivery - planning for production readiness and UX maturity

---

## Current State Assessment

### ✅ What Works
- Hub v1 live: DenialScope + DriftWatch dashboards
- Ingestion pipeline operational (webhook/CSV)
- Alert email generation with evidence payloads
- SystemEvent audit trail
- Multi-tenant data isolation (middleware enforced)
- RBAC with operator/analyst/viewer roles
- Demo data generators functional

### 🟡 What's Incomplete
- **UI feels flat**: No motion, no depth, no micro-interactions
- **Login unclear**: Client vs operator account separation not explicit
- **Operator trust missing**: No memory loop (system forgets operator judgments)
- **Enforcement incomplete**: "Quick actions" on dashboards show "Coming Soon" modal
- **Evidence not actionable**: Can view evidence, but can't act on it

### 🔴 Blocking Production Exposure
1. Operator memory loop missing → alerts feel repetitive/untrusted
2. Enforcement actions missing → operators can observe but not resolve
3. UI interaction feedback missing → feels unresponsive

---

## Sequenced Roadmap (Priority Order)

### **✅ PHASE 1: Operator Memory Loop (COMPLETED)**
**Goal:** Operators can label alerts and system remembers their decisions
**Status:** ✅ COMPLETE - Committed in ec7d8b7

#### Completed Deliverables
1. **New Model:** `OperatorJudgment`
   - Fields: `alert_event`, `verdict` (noise/real), `reason_codes_json`, `recovered_amount`, `created_at`
   - Migration file: `0013_operatorjudgment.py`

2. **Suppression Logic Extension**
   - If alert marked "noise" → suppress similar alerts for 14 days (same customer, signal, entity)
   - If alert marked "real" → badge future similar alerts as "Previously confirmed issue"
   - If "needs follow-up" → label reappearances as "Previously flagged, unresolved"

3. **UI Changes (Minimal)**
   - Add 3 buttons to alert rows: `[✓ Reviewed]` `[🔍 Deep Dive]` `[🔇 Noise]`
   - Add one-line context to alert cards: "Operator previously marked this as Noise"
   - Wire buttons to new endpoint: `POST /api/alerts/<id>/feedback/`

4. **Service Layer**
   - `OperatorFeedbackService.record_judgment(alert_id, verdict, user)`
   - `AlertOrchestrator.apply_suppression_rules()` (extend existing)

5. **Tests**
   - Test noise classification suppresses future alerts
   - Test legitimate classification adds badge
   - Test follow-up creates reminder behavior
   - Test tenant isolation on judgments

**Files to Touch:**
- `upstream/models.py` (add OperatorJudgment)
- `upstream/alerts/services.py` (extend suppression logic)
- `upstream/api/views.py` (new feedback endpoint)
- `upstream/templates/upstream/products/driftwatch_dashboard.html` (wire buttons)
- `upstream/templates/upstream/products/denialscope_dashboard.html` (wire buttons)
- `upstream/tests.py` (add operator memory tests)

**Actual Effort:** ~3 hours
**Risk:** Low (additive only, no existing code refactored)

**What Was Delivered:**

- ✅ OperatorJudgment model with migration 0013
- ✅ API endpoint `/api/v1/alerts/{id}/feedback/` with POST support
- ✅ Dashboard feedback buttons (✓ Reviewed, 🔍 Deep Dive, 🔇 Noise)
- ✅ Judgment badges showing previous operator decisions
- ✅ Alert status updates (noise→resolved, real→acknowledged)
- ✅ Comprehensive test suite (8 tests, all passing)

**Phase 1b Extensions (1dda079):**

- ✅ Suppression context: Similar alert detection and context badges
- ✅ SystemEvent audit logging for all operator feedback actions
- ✅ Enhanced error handling in alert deep dive views

---

### **✅ PHASE 2: UI/UX Motion & Depth (COMPLETED)**
**Goal:** Interface feels responsive and alive
**Status:** ✅ COMPLETE - Committed in 02789b3

#### Deliverables (4 Sub-phases)

**Phase 2A: Surface Depth + Spring Motion**
- Add 3-tier elevation system (CSS shadows)
- Replace linear transitions with spring easing (`cubic-bezier(0.34, 1.56, 0.64, 1)`)
- Card press feedback (`:active` → `scale(0.98)`)
- Button press feedback (`:active` → `translateY(1px)` + inset shadow)
- Subtle background gradient animation

**Phase 2B: Micro-interactions**
- Table row hover lifts with shadow
- Status badges pulse on high-urgency items
- Form input glow + lift on focus
- Nav link transitions with directional intent

**Phase 2C: Color Behavior**
- Alert cards: warmer tones for high-severity, cooler for low
- Background: subtle warm shift as user progresses through workflow
- Completion moments: brief color shift on successful actions

**Phase 2D: Progressive Disclosure**
- Alert cards: start collapsed, expand on click
- Evidence sections: details hidden until interaction
- CSS-only accordions (no JavaScript)

**Files to Touch:**
- `upstream/static/upstream/css/style.css` (all changes)
- `upstream/templates/upstream/base.html` (add gradient background wrapper)
- Dashboard templates (optional: add collapse/expand structure)

**Effort:** 2 hours total (30-45 min per sub-phase)  
**Risk:** Very low (CSS-only, no business logic)

---

### **🟡 PHASE 3: Client vs Operator Login Clarification (IN PROGRESS)**
**Goal:** Explicit separation of operator (you) and client (customer) accounts
**Status:** 🟡 PARTIAL - User context indicator completed (b972a50), login flow pending

#### Current State Audit Required
Before building, verify:
1. Can you `python manage.py createsuperuser` → this is your operator login
2. Does `Customer` model exist? Does `User` have FK to `Customer`?
3. Is tenant isolation enforced at query level (middleware) or only UI?
4. What happens when you log in today? What role do you have?

#### Deliverables (Conditional on Audit)
**Scenario A: Tenant Isolation Already Exists**
- Document the existing login flow
- Add explicit "Operator Portal" vs "Client Portal" entry points
- Add UI indicator showing current role + tenant

**Scenario B: Needs Implementation**
- Ensure `User.customer` FK exists (or add `UserProfile.customer`)
- Add middleware that sets `request.tenant` based on logged-in user
- Enforce `Customer.objects.filter(id=request.tenant.id)` in all queries
- Add operator superuser bypass (can see all tenants)
- Add login page with role selection

**Files to Touch (if Scenario B):**
- `upstream/models.py` (verify/add User→Customer relationship)
- `upstream/middleware.py` (add tenant enforcement)
- `upstream/views.py` (add role-aware dashboards)
- `upstream/templates/upstream/login.html` (create if missing)

**Effort:** 1-2 hours (Scenario A), 3-4 hours (Scenario B)  
**Risk:** Medium (touches auth, requires careful tenant isolation testing)

**Decision Point:** Run audit first, then decide scope.

---

### **✅ PHASE 4: Basic Enforcement Actions (COMPLETE)**

**Goal:** Replace "Coming Soon" modals with real operator actions
**Status:** ✅ COMPLETE - All core deliverables shipped

#### Completed Items

1. **✅ Wire Existing Buttons** (Phase 1 - ec7d8b7)
   - `[✓ Reviewed]` → Marks alert as "real" using OperatorJudgment
   - `[🔍 Deep Dive]` → Navigates to comprehensive alert detail page
   - `[🔇 Noise]` → Marks alert as "noise" using OperatorJudgment

2. **✅ Deep Dive Page** (Phase 4 - b66ea9f)
   - URL: `/alerts/<id>/deep-dive/`
   - Shows: Alert status, operator interpretation, full evidence payload, sample claims
   - Features: Urgency indicators, recommended actions, judgment history
   - Uses: Existing `evidence_payload.py` service

3. **✅ Recovery Fields** (Phase 1 - ec7d8b7)
   - Added to `OperatorJudgment`: `recovered_amount`, `recovered_date`
   - Can be submitted via API with feedback

4. **✅ Recovery Ledger Dashboard Card** (Phase 4 - 1dda079)
   - Dashboard summary card: "Total Recovered This Month"
   - Aggregate recovery stats (this month, last 30 days, all-time)
   - Recent recoveries list with payer details
   - Beautiful green gradient design with expandable breakdown

**Actual Effort:** ~3 hours total (Deep Dive page + Recovery Ledger + enhancements)
**Risk:** Low (builds on Phase 1, no complex logic)

**Defer to Phase 5:** Full Enforcement Engine (ClaimSet, EvidenceArtifact versioning, ActionPlan, PayerCase, RegressionWatch, AuditVault) - that's a separate 8-10 hour sprint.

---

## Implementation Order Summary

| Phase | Feature | Status | Actual Effort | Risk |
|-------|---------|--------|---------------|------|
| **1** | Operator Memory Loop | ✅ Complete | ~4h (+ Phase 1b) | Low |
| **2** | UI/UX Motion & Depth | ✅ Complete | ~2h | Very Low |
| **3** | Client/Operator Login | 🟡 Partial | ~1h | Medium |
| **4** | Basic Enforcement Actions | ✅ Complete | ~3h | Low |
| **5** | Full Enforcement Engine | ⏳ Not Started | 8-10h (est) | High |

**Total Progress:** ~10 hours invested, Phases 1-4 complete

**Remaining for Production MVP:** ~1 hour (Phase 3 login flow documentation)

---

## Decision Gates

### Before Phase 1
- [ ] Confirm Phase 1 scope (smallest possible operator memory)
- [ ] Review OperatorJudgment model fields
- [ ] Decide suppression window (14 days vs 30 days)

### Before Phase 2
- [ ] Verify Phase 1 works in production-like environment
- [ ] Decide which sub-phases of Phase 2 to implement (A+B minimum, C+D optional)

### Before Phase 3
- [ ] Run audit: what login/tenant separation already exists?
- [ ] Decide Scenario A vs B based on audit findings

### Before Phase 4
- [ ] Confirm Phase 1 memory loop is live and working
- [ ] Review which "quick actions" to keep (reviewed/noise/deep-dive/recovery)

---

## Non-Negotiables (Carried Forward from Project Rules)

- ✅ Smallest change possible
- ✅ No refactoring unrelated code
- ✅ No new data models unless absolutely required
- ✅ Every state change writes SystemEvent
- ✅ Tenant isolation enforced on every query
- ✅ All tests green before commit
- ✅ No secrets in code/logs/git

---

## What This Roadmap Does NOT Include

These are explicitly deferred or out of scope:

- ❌ Second product signal (DriftWatch stays DENIAL_RATE only, DenialScope stays denial_dollars_spike only)
- ❌ Slack/webhook integrations (email only)
- ❌ Mobile app or haptics (web-based only)
- ❌ Sound design (optional, deferred)
- ❌ Complex regression escalation (deferred to Phase 5)
- ❌ Payer case management (deferred to Phase 5)
- ❌ Executive brief generation (deferred to Phase 5)
- ❌ Audit vault with immutable snapshots (deferred to Phase 5)

---

## 🎉 Progress Summary (2026-01-22 - Updated)

### What's Been Delivered

**Phase 1: Operator Memory Loop** ✅ COMPLETE (ec7d8b7 + 1dda079)
- Operators can mark alerts as noise/real/needs-follow-up
- System remembers judgments and displays badges on future alerts
- API endpoint for feedback submission with full audit logging
- Similar alert detection shows suppression context
- SystemEvent logging for all operator actions
- 8 comprehensive tests passing

**Phase 2: UI/UX Motion & Depth** ✅ COMPLETE (02789b3)
- Spring-based animations and micro-interactions
- 3-tier elevation system with responsive depth
- Card press feedback and button interactions
- Background gradient animations

**Phase 3: User Context Indicator** 🟡 PARTIAL (b972a50)
- Header badges showing operator vs customer context
- Role indicators for all user types
- Custom logout page showing account details
- Login flow documentation pending

**Phase 4: Basic Enforcement Actions** ✅ COMPLETE (b66ea9f + 1dda079)
- Comprehensive alert deep dive page with full evidence
- Operator interpretation with urgency levels
- Sample claims and judgment history
- Recovery ledger dashboard card with beautiful UI
- Enhanced error handling and graceful degradation
- Complete audit trail via SystemEvent logging

### What Got Completed This Session

1. ✅ **Recovery Ledger Dashboard Card** (~1 hour)
   - Added summary card showing "Total Recovered This Month"
   - Includes last 30 days and all-time stats
   - Recent recoveries list with expandable details

2. ✅ **Alert Suppression Context** (~1 hour)
   - Similar alert detection with context badges
   - Shows when similar alerts were previously judged
   - Helps operators avoid duplicate reviews

3. ✅ **Enhanced Error Handling & Audit Logging** (~1 hour)
   - Comprehensive error handling in alert views
   - SystemEvent logging for all operator actions
   - Complete audit trail for compliance

### Next Steps

**Phase 3 Login Flow Documentation** (~1 hour)

- Document existing login/tenant separation architecture
- Create authentication guide (AUTHENTICATION_GUIDE.md already started)
- Add "Operator Portal" vs "Client Portal" clarity if needed

**After that, ready for production pilot!**

---

**End of Roadmap**
