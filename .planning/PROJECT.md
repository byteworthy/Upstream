# Upstream Product Requirements Document (PRD)
## Autonomous Revenue Intelligence Platform for Specialty Healthcare

**Version:** 1.0
**Last Updated:** February 1, 2026
**Author:** Kev
**Status:** Active Development (Phase 3 Technical Debt)

---

## Executive Summary

### Product Vision

Upstream is the first **autonomous revenue intelligence platform** that both prevents denials before they happen AND detects problems after submission—purpose-built for 5-25 provider specialty healthcare practices (ABA, PT/OT, dialysis, imaging, home health).

Unlike Adonis Intelligence ($54M raised) which focuses on post-submission detection with manual approval workflows, Upstream combines:

1. **Prevention Layer** - 30-day authorization alerts, pre-submission risk scoring, calendar-based warnings
2. **Detection Layer** - Real-time denial patterns, payment timing trends, payer behavior changes
3. **Autonomous Execution** - Threshold-based automation that executes low-risk actions without approval

### Product Positioning

**Target Market:** Mid-market specialty practices ignored by enterprise RCM vendors
**Primary Users:** Billing Managers, Practice Administrators, CFOs
**Core Differentiation:** Prevention + Detection + Autonomous Execution in one platform
**Pricing:** $299-999/month (vs Adonis $6K+/year)
**Implementation:** 30 days (vs Adonis 6 months)

### Success Metrics

**Product Metrics:**
- Prevention: 60%+ of authorization expiration denials avoided
- Detection: 95%+ denial pattern alerts within 48 hours
- Autonomy: 70%+ of routine actions execute without human approval
- Accuracy: 95%+ autonomous action success rate

**Business Metrics:**
- Month 6: 20-25 paying customers, $12K-15K MRR
- Month 12: 40-50 customers, $25K-30K MRR
- Month 24: 100-130 customers, $80K-100K MRR ($1M ARR)
- Churn: <10% annual

---

## Part 1: Core Features & Requirements

### 1.1 Prevention Layer (NEW - Adonis doesn't have)

#### Feature 1.1.1: Authorization Expiration Tracking

**Problem:** ABA/PT/imaging practices lose 15-30% of claims to expired authorizations because tracking is manual (spreadsheets, calendars)

**Solution:** Automated tracking with 30/14/3 day alerts

**Requirements:**

```yaml
Data Model:
  Authorization:
    - auth_number (string, unique)
    - patient_id (string, hashed for HIPAA)
    - payer (string)
    - service_type (string: "ABA", "PT", "OT", "Imaging", etc.)
    - cpt_codes (array)
    - auth_start_date (date)
    - auth_expiration_date (date)
    - units_authorized (integer)
    - units_used (integer)
    - status (enum: ACTIVE, EXPIRING_SOON, EXPIRED, RENEWED)
    - auto_alert_enabled (boolean, default: true)
    - auto_reauth_enabled (boolean, default: false)

Alert Triggers:
  - 30 days before expiration: severity=MEDIUM, action="Schedule re-auth request"
  - 14 days before expiration: severity=HIGH, action="Submit re-auth request NOW"
  - 3 days before expiration: severity=CRITICAL, action="URGENT: Authorization expires in 3 days"
  - Unit exhaustion projection: If (units_remaining / avg_daily_usage) < days_until_expiration
    Then alert: "Will exhaust units before expiration"

Unit Consumption Tracking:
  - Link claims to authorizations via patient_id + service_type + date_range
  - Increment units_used when claim submitted
  - Calculate avg_daily_usage = units_used / days_since_start
  - Project exhaustion_date = today + (units_remaining / avg_daily_usage)

Autonomous Actions (if auto_reauth_enabled=true):
  Threshold: authorization expires in 21+ days AND confidence >95%
  Action: Auto-generate re-auth request with utilization report
  Execution: Submit via payer portal RPA OR queue for manual submission
  Notification: Email after submission with confirmation number
  Audit: Log all autonomous re-auth requests with outcomes
```

**User Stories:**

- US-1.1.1a: As a Billing Manager, I want to receive email alerts 30 days before authorizations expire, so I can request re-authorization before it lapses.
- US-1.1.1b: As a Practice Administrator, I want the system to automatically submit re-authorization requests for low-risk renewals, so my team doesn't waste time on routine paperwork.
- US-1.1.1c: As a CFO, I want to see how many authorization-related denials we prevented this month, so I can measure ROI.

**Acceptance Criteria:**

- [ ] System ingests authorization data via CSV upload
- [ ] System ingests authorization data via athenahealth FHIR API (Coverage resource)
- [ ] Alert fires 30 days before expiration (±1 day tolerance)
- [ ] Alert email includes: auth number, payer, expiration date, units remaining, action link
- [ ] Autonomous re-auth only executes if auto_reauth_enabled=true AND confidence >95%
- [ ] Dashboard shows: active auths, expiring soon, recently expired, autonomous submissions
- [ ] Audit trail logs all alert deliveries and autonomous actions

---

#### Feature 1.1.2: Pre-Submission Risk Scoring

**Problem:** Practices submit high-risk claims blindly, resulting in 10-15% denial rates

**Solution:** 0-100 risk score calculated before submission with auto-hold for high-risk claims

**Requirements:**

```yaml
Risk Scoring Algorithm:
  Inputs:
    - CPT code
    - Modifier codes
    - Diagnosis codes (ICD-10)
    - Payer
    - Patient age
    - Recent denial history (last 30 days, same payer+CPT)

  Factors (weighted):
    1. Historical Denial Rate (40% weight):
       - Lookup denial rate for (payer, CPT) combination
       - If sample_size < 10: use CPT average across all payers
       - Formula: base_risk = denial_rate * 40

    2. Missing Required Modifiers (20% weight):
       - Query PayerRule table for required_modifiers
       - If modifier missing: +20 points
       - If modifier incorrect: +15 points

    3. Recent Denial Streak (20% weight):
       - Count denials in last 30 days for same payer+CPT
       - If count >= 3: +20 points
       - If count >= 1: +10 points

    4. Diagnosis-CPT Mismatch (10% weight):
       - Check if diagnosis supports medical necessity for CPT
       - If no match in DiagnosisCPTRule table: +10 points

    5. Authorization Status (10% weight):
       - If PA required but not obtained: +10 points
       - If PA expired: +10 points

  Output:
    - risk_score (0-100, integer)
    - risk_category (LOW <40, MEDIUM 40-69, HIGH ≥70)
    - risk_factors (array of contributing issues)
    - recommendation (string: "SUBMIT" | "REVIEW" | "HOLD")
    - auto_fix_actions (array of automated fixes available)

Autonomous Actions:
  IF risk_score < 40 AND no missing_modifiers:
    Action: Auto-submit claim (no human approval needed)
    Notification: Daily digest of auto-submitted claims

  IF risk_score 40-69 OR fixable issues exist:
    Action: Queue for review with AI recommendations
    Notification: Dashboard alert with "1-click fix" options

  IF risk_score >= 70:
    Action: Auto-hold claim, escalate to billing manager
    Notification: Immediate email with risk factors and evidence

Auto-Fix Capabilities:
  - Add missing required modifiers (if confidence >95%)
  - Suggest alternative diagnosis codes for medical necessity
  - Flag authorization requirement before submission
```

**User Stories:**

- US-1.1.2a: As a Billing Manager, I want to see risk scores before submitting claims, so I can fix high-risk claims before they deny.
- US-1.1.2b: As a Biller, I want the system to automatically add missing modifiers to low-risk claims, so I don't waste time on routine fixes.
- US-1.1.2c: As a Practice Administrator, I want high-risk claims to be held automatically, so junior staff don't submit problematic claims.

**Acceptance Criteria:**

- [ ] Risk score calculates in <2 seconds per claim
- [ ] Risk score accuracy validated: 75%+ of HIGH scores actually deny if submitted unchanged
- [ ] Auto-fix for missing modifiers works for top 10 most common modifiers
- [ ] Dashboard shows: claims ready to submit, claims needing review, claims on hold
- [ ] Autonomous modifier additions logged with before/after comparison
- [ ] Users can override auto-hold with justification (logged in audit trail)

---

### 1.2 Detection Layer (Match Adonis)

#### Feature 1.2.1: DriftWatch - Denial Rate Pattern Detection

**Problem:** Payer denial behavior changes gradually; practices don't notice until 2-4 weeks later

**Solution:** Week-over-week statistical comparison with alerts on significant changes

**Requirements:**

```yaml
Algorithm:
  Baseline Calculation:
    - Period: Last 13 weeks (excluding current week)
    - Metrics: denial_rate = denied_claims / total_claims (by payer)
    - Statistical measures: mean, standard_deviation, 95th_percentile

  Current Period:
    - Period: Last 7 days (rolling window)
    - Calculate: current_denial_rate

  Significance Testing:
    - Test: Chi-square test for independence
    - Threshold: p-value < 0.05 (95% confidence)
    - Minimum sample: 10 claims minimum per period

  Alert Trigger:
    IF current_denial_rate > (baseline_mean * 1.5) AND p-value < 0.05:
      severity = HIGH
    ELSE IF current_denial_rate > (baseline_mean * 1.25) AND p-value < 0.05:
      severity = MEDIUM

Alert Contents:
  - Title: "Denial Rate Spike: [Payer]"
  - Baseline rate: "8.2% (last 13 weeks)"
  - Current rate: "15.4% (last 7 days)"
  - Change: "+87% increase"
  - Statistical confidence: "95% (p=0.03)"
  - Affected CPT codes: Top 3 CPT codes with highest denial counts
  - Top denial reasons: CARC codes with counts
  - Evidence table: List of denied claims with details
  - Recommended actions
```

**Status:** ✅ Implemented (DriftEvent model, detection algorithms)

---

#### Feature 1.2.2: DelayGuard - Payment Timing Trend Detection

**Problem:** Payment slowdowns precede denial spikes but aren't detected until cash flow crisis

**Solution:** Track payment timing trends with 3-week progressive worsening detection

**Requirements:**

```yaml
Algorithm:
  Baseline Calculation:
    - Period: Last 13 weeks
    - Metric: median_payment_days = median(paid_date - submitted_date)
    - Separate tracking for PAID claims only (exclude DENIED)

  Current Trend:
    - Week 1 (most recent): median_payment_days_w1
    - Week 2: median_payment_days_w2
    - Week 3: median_payment_days_w3

  Trend Detection:
    Progressive Worsening:
      IF w1 > w2 > w3 AND (w1 - w3) > 7 days:
        trend = "WORSENING"
        severity = HIGH

    Absolute Slowdown:
      IF w1 > (baseline_median * 1.3):
        trend = "SIGNIFICANT_SLOWDOWN"
        severity = HIGH

  Cash Flow Impact Calculation:
    avg_weekly_revenue = SUM(paid_amount) / 13 weeks
    delayed_revenue = (current_payment_days - baseline_days) / 7 * avg_weekly_revenue
```

---

#### Feature 1.2.3: Real-Time EHR Integration (athenahealth FHIR)

**Problem:** Weekly batch CSV uploads are too slow to compete with Adonis's 24-48 hour alerts

**Solution:** Real-time webhooks from athenahealth for claim submission/adjudication events

**Requirements:**

```yaml
athenahealth Event Subscription Platform Integration:

  Authentication:
    - Method: OAuth 2.0 (2-legged)
    - Scopes: SubscriptionTopic.read, Subscription.write, Subscription.read
    - Credentials: Stored in Google Secret Manager

  Webhook Endpoint:
    - URL: https://api.upstream.cx/webhooks/athena
    - Method: POST
    - Response: Must return 200 OK within 2 seconds (athena hard limit)
    - Signature Verification: X-Hub-Signature (HMAC SHA256)

  Subscribed Events:
    - Claim.create: New claim submitted via athenahealth
    - Claim.update: Claim status changed (PENDING → PAID/DENIED)
    - Claim.delete: Claim voided or corrected

  Event Processing Pipeline:
    1. Receive webhook → Verify signature → Return 200 OK immediately
    2. Queue event to Celery (async processing)
    3. Parse FHIR R5 Claim resource
    4. Map to ClaimRecord model
    5. Trigger detection algorithms (DriftWatch, DenialScope, DelayGuard)
    6. Generate alerts if thresholds crossed
    7. Update dashboard in real-time (WebSocket)

  Data Mapping (FHIR R5 → Upstream):
    - claim.id → claim_id
    - claim.patient.reference → patient_id (hashed)
    - claim.insurer.display → payer
    - claim.item[].productOrService.coding[].code → cpt
    - claim.item[].modifier[] → modifiers
    - claim.diagnosis[].diagnosisCodeableConcept → diagnosis_codes
    - claim.created → submitted_date
    - claim.outcome → outcome (complete=PAID, error=DENIED, partial=PARTIAL)
    - claim.total.value → billed_amount
    - claim.payment.amount.value → paid_amount

  Idempotency:
    - Key: athena_event_id (from webhook header)
    - Storage: Redis (TTL: 24 hours)
    - Logic: If event already processed, return success without re-processing
```

---

### 1.3 Autonomous Execution Layer (Beat Adonis)

#### Feature 1.3.1: Threshold-Based Automation Framework

**Problem:** Adonis requires manual approval for most actions; Upstream should execute autonomously for low-risk actions

**Solution:** Three-tier automation framework with configurable thresholds

**Requirements:**

```yaml
Automation Tiers:

Tier 1 - Auto-Execute (No Human Approval):
  Criteria:
    - Confidence score >95%
    - Dollar value <$1,000
    - Action type in SAFE_LIST
    - No compliance flags (FCA, Stark, Anti-Kickback)

  Allowed Actions:
    - Add missing modifiers (if confidence >95%)
    - Submit routine re-authorization requests
    - Update claim status in EHR
    - Send standard follow-up inquiries to payers
    - Post payments to patient accounts

Tier 2 - Queue for Review (AI Pre-Populated):
  Criteria:
    - Confidence score 70-95%
    - Dollar value $1,000-$10,000
    - Minor documentation gaps

Tier 3 - Escalate (Human Required):
  Criteria:
    - Confidence score <70%
    - Dollar value >$10,000
    - Compliance-sensitive actions (appeals with legal certs, medical necessity)
    - Fraud/abuse indicators

  Prohibited from Automation:
    - Appeals (legal certification required)
    - Medical necessity determinations
    - Code changes affecting reimbursement >10%
    - Claims involving referrals (Stark Law compliance)
    - Any action with FCA exposure

Customer Configuration:
  AutomationSettings model:
    - auto_execute_enabled (boolean, default: true)
    - confidence_threshold_auto (integer, default: 95)
    - dollar_threshold_auto (integer, default: 1000)
    - allowed_auto_actions (array, customizable per customer)
    - escalation_contacts (array of emails by action type)
    - notification_preferences (digest vs real-time)
```

---

## Part 2: Specialty-Specific Intelligence

### 2.1 Dialysis Module

**Problem:** Dialysis centers lose $38-42K per patient annually when Medicare Advantage pays 15-20% less than Traditional Medicare

**Feature: MA Payment Variance Detection**
- Track Traditional Medicare baseline vs MA payer payments
- Alert when variance exceeds -15%
- Identify missing add-ons (TDAPA, TPNIES)

### 2.2 ABA Module

**Problem:** ABA practices have 15-30% denial rates; authorization expiration is #1 cause

**Feature: ABA Authorization Unit Tracking**
- Track by provider credentials (BCBA vs RBT)
- Monitor session length compliance
- Validate modifier requirements (HN, HO, HP)
- Alert on BCBA credential expiration

### 2.3 PT/OT Module

**Problem:** PT practices face 8-minute rule violations and KX threshold confusion

**Feature: 8-Minute Rule Compliance Validation**
- Real-time validation of time-based CPT billing
- KX modifier threshold monitoring ($2,410 for 2025)
- UnitedHealthcare MA 6-visit limitation tracking

### 2.4 Imaging Module

**Problem:** Imaging centers lose claims to missing prior authorizations from RBMs (eviCore, AIM)

**Feature: RBM Prior Authorization Requirement Database**
- Pre-submission PA requirement lookup
- Auto-submit PA via eviCore API when enabled

### 2.5 Home Health Module

**Problem:** Home health agencies face PDGM grouping errors and F2F timing violations

**Feature: PDGM Grouper Validation**
- Compare system-calculated PDGM group vs EHR-assigned
- Face-to-Face timing validation (90-day rule)
- NOA deadline tracking (5 days from episode start)

---

## Part 3: Technical Architecture

### 3.1 System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     INGESTION LAYER                             │
├─────────────────────────────────────────────────────────────────┤
│  CSV Upload ──────┐                                            │
│  athenahealth ────┼──→ Webhook Receiver (Django REST)          │
│  Epic (polling) ──┤      ↓                                     │
│  Cerner ──────────┘    Validation & Normalization             │
│                           ↓                                     │
│                    Data Quality Service                         │
│                    (PHI detection, payer normalization)         │
│                           ↓                                     │
│                    ClaimRecord creation                         │
└──────────────────────┬──────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────────┐
│                  PREVENTION LAYER                               │
├─────────────────────────────────────────────────────────────────┤
│  Authorization Monitor:                                         │
│  - 30/14/3 day expiration alerts                               │
│  - Unit exhaustion projection                                  │
│  - Re-auth deadline tracking                                   │
│                                                                  │
│  Pre-Submission Scanner:                                        │
│  - Risk score calculation (0-100)                              │
│  - Modifier validation                                         │
│  - Medical necessity check                                     │
└──────────────────────┬──────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────────┐
│                  DETECTION LAYER                                │
├─────────────────────────────────────────────────────────────────┤
│  DriftWatch: Denial rate week-over-week comparison             │
│  DenialScope: CPT-level pattern analysis                        │
│  DelayGuard: Payment timing trend detection                     │
│  Specialty Modules: Dialysis MA, ABA auth, PT 8-min, etc.     │
└──────────────────────┬──────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────────┐
│               AUTONOMOUS EXECUTION LAYER                        │
├─────────────────────────────────────────────────────────────────┤
│  Rules Engine:                                                  │
│  - Threshold classification (Tier 1/2/3)                       │
│  - Confidence scoring                                          │
│  - Action routing                                              │
│                                                                  │
│  RPA Framework (future):                                        │
│  - Payer portal automation                                      │
│  - Authorization submission                                     │
└──────────────────────┬──────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────────┐
│                    ALERT & WORKFLOW LAYER                       │
├─────────────────────────────────────────────────────────────────┤
│  Alert Generation → Notification Routing → Dashboard Updates   │
│  (Email, Webhook, SMS) → (Real-time) → (React frontend)       │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Technology Stack

**Backend (Current):**
- Python 3.12 + Django 5.2
- Django REST Framework (API)
- PostgreSQL 15 (primary database)
- Redis 7 (caching, Celery queue, idempotency)
- Celery 5.3 (async task processing)

**Frontend (Planned):**
- React 18 + TypeScript
- Tailwind CSS
- Shadcn/UI components
- Chart.js (visualizations)
- WebSocket (real-time updates)

**Infrastructure (GCP):**
- Cloud Run (Django containers)
- Cloud SQL (PostgreSQL)
- Cloud Storage (CSV, reports)
- Secret Manager (credentials)
- Cloud Build (CI/CD)

**Security:**
- TLS 1.3 (encryption in transit)
- AES-256 (encryption at rest)
- HIPAA audit logging (django-auditlog)
- OAuth 2.0 (EHR authentication)
- JWT authentication with token blacklist

### 3.3 Key Database Models

**Core Models (Implemented):**
- Customer - Multi-tenant customer accounts
- ClaimRecord - Claims with payer, CPT, outcomes
- DriftEvent - Payer behavior change alerts
- AlertEvent - All alert types with severity
- ReportRun - Generated reports

**Prevention Models (To Implement):**
- Authorization - Auth tracking with expiration
- RiskBaseline - Historical denial rates by payer+CPT

**Automation Models (To Implement):**
- AutomationRule - Threshold-based rules
- ExecutionLog - Audit trail for autonomous actions

---

## Part 4: Current Development Context

### Phase 3: Technical Debt Remediation

**Status:** Active (2/2 plans complete, final verification pending)

This phase focuses on database optimization, API improvements, and testing enhancements to achieve production-grade reliability and performance.

#### Requirements Status

**Validated (Production Capabilities):**
- ✅ Multi-tenant SaaS with customer isolation (CustomerScopedManager)
- ✅ CSV upload processing with 23 validation rules
- ✅ Payer drift detection algorithms (baseline vs current comparison)
- ✅ Alert system (email, webhook, operator feedback)
- ✅ REST API with JWT authentication and token blacklist
- ✅ Celery async task processing (drift detection, report generation)
- ✅ HIPAA-compliant audit logging and PHI encryption
- ✅ Database indexes for query optimization
- ✅ Covering indexes for aggregate queries (50-70% faster)
- ✅ CHECK constraints for data integrity (27 constraints across 7 models)

**Completed (Phase 3):**
- ✅ **DB-01**: Transaction isolation for concurrent drift detection
- ✅ **DB-02**: Unique constraints for data integrity
- ✅ **API-01**: Pagination for custom actions (feedback, dashboard)
- ✅ **API-02**: SearchFilter and DjangoFilterBackend on ViewSets
- ✅ **API-03**: Standardized error responses (RFC 7807 aligned)
- ✅ **API-04**: Complete OpenAPI/Swagger documentation
- ✅ **TEST-01**: Webhook integration tests (delivery, retry, signatures)
- ✅ **TEST-02**: Performance tests (Locust load testing)
- ✅ **TEST-03**: Deployment rollback test workflow
- ✅ **TEST-04**: RBAC cross-role tests (superuser, admin, viewer)

**Remaining:**
- [ ] **DB-03**: Additional database indexes (Phase 6)

#### Technical Debt Status

- 131 total findings identified in comprehensive audit
- 45+ issues resolved (35%+ complete)
- Phase 3 targets 10 medium-priority issues (complete)

#### Production Considerations

- Live system with real patient data (HIPAA-protected)
- Must maintain audit trail for all changes
- Zero-downtime migration strategy required
- All database changes must be backwards compatible

### Constraints

- **Production System**: Changes deployed to live environment with real PHI data
- **HIPAA Compliance**: All changes must maintain HIPAA audit trails and PHI encryption
- **Zero Downtime**: Database migrations must be backwards compatible and non-blocking
- **Tech Stack**: Django 5.2, PostgreSQL 15, Redis 7, Celery 5.3 (no major version changes)

---

## Part 5: Roadmap & Milestones

### Completed Phases

| Phase | Description | Completed |
|-------|-------------|-----------|
| 1 | Transaction Isolation & Unique Constraints | 2026-01-26 |
| 2 | API Pagination & Filtering | 2026-01-26 |
| 3 | OpenAPI Documentation & Error Standardization | 2026-02-01 |
| 4 | Webhook & RBAC Testing | 2026-01-26 |
| 5 | Performance Testing & Rollback Fix | 2026-01-26 |

### Upcoming Work

| Phase | Description | Status |
|-------|-------------|--------|
| 6 | Database Indexes | Not started |
| - | Prevention Layer (Authorization Tracking) | Planning |
| - | Real-time EHR Integration (athenahealth) | Planning |
| - | Autonomous Execution Framework | Planning |

---

## Part 6: Key Decisions

| Decision | Rationale | Status |
|----------|-----------|--------|
| Database work first | Foundation must be solid before API polish | ✅ Complete |
| All of Phase 3 scope | Systematic completion vs piecemeal | ✅ Complete |
| No major refactors | Production stability over architectural purity | ✅ Applied |
| RFC 7807 error format | Industry standard for API errors | ✅ Implemented |
| drf-spectacular for OpenAPI | Best DRF integration, active maintenance | ✅ Implemented |

---

*Last updated: 2026-02-01 after Phase 3 completion*
