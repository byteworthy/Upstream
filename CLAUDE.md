# CLAUDE.md - Upstream Project Intelligence

## What is Upstream?

**Upstream is an Early-Warning Payer Risk Intelligence Platform with Autonomous Execution.**

It detects when payers change their behavior—denying more claims, changing policies, slowing payments—30-60 days before traditional monthly reporting would catch it. Then executes fixes autonomously.

### Core Philosophy

> "You see the problem coming. You have time to act. The system acts for you."

Think of Upstream as a **smoke detector + autonomous firefighter** for healthcare revenue. It doesn't just alert—it detects early AND executes fixes without manual approval bottlenecks.

---

## Competitive Positioning

| Capability | Upstream | Adonis | Waystar | Rivet |
|------------|----------|--------|---------|-------|
| Detection Speed | Day 3 | Day 14 | Day 30+ | Day 30+ |
| Execution Model | Autonomous (execute first, notify after) | Manual approval | Manual | Manual |
| Intelligence Type | Behavioral prediction | Post-denial analysis | Claims workflows | Contract benchmarking |
| Specialty Focus | Dialysis, ABA, Imaging, Home Health | Generic | Generic | Generic |

### Key Differentiators

1. **TIME ADVANTAGE**: 30-60 day early warning vs competitors' 1-2 weeks
2. **AUTONOMOUS EXECUTION**: Execute first, notify after (vs Adonis "alert, review, approve, execute")
3. **PREVENTION vs RECOVERY**: Stop denials before submission (not just faster appeals)
4. **SPECIALTY-FIRST**: Built for dialysis/ABA/imaging/home health (not adapted from generic RCM)

---

## Architecture Overview

### Three-Layer System

```
┌─────────────────────────────────────────────────────────────┐
│                    DETECTION LAYER                          │
│  Real-time EHR webhooks (1-2 day alerts)                   │
│  Calendar-based prevention (30-day auth expiration)         │
│  Behavioral prediction (day 3 detection)                    │
│  Payment timing trends (cash flow stress)                   │
└─────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   INTELLIGENCE LAYER                        │
│  Pre-submission risk scoring                                │
│  Specialty-specific baselines (Dialysis, ABA, Imaging, HH)  │
│  Network effects (cross-customer intelligence)              │
└─────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    EXECUTION LAYER                          │
│  Pre-approved rules engine (threshold-based)                │
│  Payer portal automation (RPA)                              │
│  Zero-touch workflows (execute first, notify after)         │
│  Audit trail (log every action for compliance)              │
└─────────────────────────────────────────────────────────────┘
```

---

## Detection Engines

### 1. DriftWatch (Denial Rate Detection)
- Statistical threshold monitoring with chi-square significance testing
- Baseline: Previous 13 weeks, Current: Last 7 days
- Alert trigger: p-value < 0.05 AND rate change > 10%

### 2. DenialScope (Dollar Spike Detection)
- Dollar-weighted denial tracking
- Threshold: >$50K spike in weekly denial dollars
- Consolidation by payer and denial reason

### 3. DelayGuard (Payment Timing Detection)
- Median payment time tracking
- Worsening trend detection (4-week rolling window)
- Cash flow impact calculation

### 4. Authorization Tracking (Calendar-Based Prevention)
- 30/14/3 day advance warning for auth expirations
- Visit exhaustion projection
- Credential expiration tracking (BCBA for ABA)

### 5. Pre-Submission Risk Scoring
- Historical denial rate by CPT + payer combo (40% weight)
- Missing required modifiers (20% weight)
- Recent denial streak (20% weight)
- Diagnosis-CPT mismatch (10% weight)
- Authorization status (10% weight)

### 6. Behavioral Prediction Engine
- Day-over-day denial rate comparison (last 3 days vs previous 14 days)
- Cross-customer pattern aggregation
- Policy change inference

---

## Specialty Modules

### Dialysis Intelligence
- **MA Payment Variance**: Detects when Medicare Advantage pays <85% of Traditional Medicare
- **ESRD PPS Drift**: Bundle payment rate changes
- **TDAPA/TPNIES Add-on Tracking**: Detects missing add-ons

### ABA Therapy Intelligence
- **Authorization Cycle Tracking**: 30/14/3 day expiration alerts
- **Visit Exhaustion Projection**: Predicts when units will run out
- **BCBA Credential Tracking**: Supervisor credential expiration

### Imaging Center Intelligence
- **RBM Requirement Tracking**: Prior auth requirements by RBM (eviCore, AIM)
- **AUC Compliance**: CMS Appropriate Use Criteria validation
- **Medical Necessity Scoring**: Documentation completeness

### Home Health Intelligence
- **PDGM Grouper Validation**: 432+ grouping combinations
- **Face-to-Face Timing**: Within 90 days validation
- **NOA Deadline Tracking**: Submission window monitoring

---

## Data Models (Key)

```python
# Core
Customer           # Multi-tenant customer
ClaimRecord        # Individual claim with outcome
Authorization      # Prior auth with expiration tracking
RiskBaseline       # Historical denial rates by payer+CPT
AlertEvent         # Generated alerts with severity

# Automation
AutomationRule     # Pre-approved execution rules
ExecutionLog       # Audit trail of autonomous actions
PreSubmissionClaim # Claims scored before submission

# Specialty
DialysisMABaseline       # Traditional Medicare payment baselines
ABAAuthorizationTracker  # Unit consumption tracking
ImagingPARequirement     # PA requirements by payer+CPT
HomeHealthPDGMGroup      # PDGM grouper mapping
```

---

## API Endpoints

```
# Authentication
POST /api/v1/auth/token/     # Get JWT token

# Claims
GET  /api/v1/claims/         # List claims
POST /api/v1/claims/         # Create claim
POST /api/v1/uploads/        # CSV upload

# Alerts
GET  /api/v1/alerts/         # List alerts
PATCH /api/v1/alerts/{id}/   # Update status

# Webhooks
POST /api/v1/webhooks/ehr/{provider}/  # EHR webhook receiver

# Specialty
GET /api/v1/specialty/dialysis/baselines/
GET /api/v1/specialty/aba/authorizations/
GET /api/v1/specialty/imaging/pa-requirements/
POST /api/v1/specialty/validate/
```

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.12, Django 5.x |
| API | Django REST Framework, JWT auth |
| Database | PostgreSQL (prod), SQLite (dev) |
| Task Queue | Celery + Redis |
| Frontend | React 19, Vite 7, Tailwind CSS v4 |
| Testing | pytest (backend), Vitest + Playwright (frontend) |

---

## Development Commands

```bash
# Backend
python manage.py runserver                    # Dev server
python manage.py test upstream -v 2           # Run tests
python manage.py run_weekly_payer_drift       # Run drift detection

# Frontend
cd frontend && npm run dev                    # Dev server
cd frontend && npm run test                   # Unit tests
cd frontend && npm run test:e2e               # E2E tests
cd frontend && npm run build                  # Production build

# Quality
cd frontend && npm run lint                   # ESLint
cd frontend && npm run format                 # Prettier
```

---

## Alert Severity Levels

| Level | Color | Response Time | Example |
|-------|-------|---------------|---------|
| INFO | Gray | N/A | Baseline updated |
| MEDIUM | Yellow | 24-48 hours | 30-day auth expiration |
| HIGH | Orange | 4-8 hours | Denial rate spike |
| CRITICAL | Red | 1-2 hours | 3-day auth expiration, compliance violation |

---

## Target Users

**Primary**: Owner-operated healthcare businesses with 1-25 locations, thin margins, and high sensitivity to cash flow disruption.

**Specialties**: Dialysis centers, ABA therapy providers, imaging centers, home health agencies.

**Roles**:
- Revenue Cycle Directors (early visibility)
- Billing Managers (denial trend tracking)
- RCM Analysts (root cause investigation)

---

## Business Value

1. **TIME ADVANTAGE**: See payer changes 30-60 days early
2. **PREVENTION**: Stop denials before submission
3. **AUTONOMY**: Fixes execute without manual approval
4. **SPECIALTY INTELLIGENCE**: Built for your vertical

---

## File Structure

```
upstream/
├── models.py              # Core data models
├── api/                   # REST API
├── services/
│   ├── payer_drift.py     # DriftWatch engine
│   ├── scoring.py         # Risk scoring
│   └── detection/         # Detection engines
├── products/              # Specialty modules
│   ├── dialysis/
│   ├── aba/
│   ├── imaging/
│   └── homehealth/
└── management/commands/   # Celery tasks

frontend/
├── src/
│   ├── components/        # React components
│   ├── pages/             # Route pages
│   ├── hooks/             # Custom hooks
│   └── services/          # API clients
├── e2e/                   # Playwright tests
└── vitest.config.ts       # Test config
```

---

## Milestones

| # | Name | Status |
|---|------|--------|
| 01 | Core Scoring Engine | Complete |
| 02 | Specialty Modules | Complete |
| 03 | Frontend MVP | Complete |
| 04 | EHR Integrations | Complete |
| 05 | Launch Prep | Complete |
