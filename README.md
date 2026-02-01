# Upstream

**Early-Warning Payer Risk Intelligence Platform with Autonomous Execution**

## What Upstream Does

Upstream detects when payers change their behavior—denying more claims, changing policies, slowing payments—**30-60 days before traditional monthly reporting would catch it**. Then executes fixes autonomously.

### The Core Problem

Healthcare operators are **BLIND** to payer changes until denials spike. By then, damage has compounded. Traditional RCM tools are REACTIVE (fix denials after they happen). Upstream is PROACTIVE (prevent denials before submission).

### The Business Value

| Advantage | Description |
|-----------|-------------|
| **TIME ADVANTAGE** | See payer changes 30-60 days early (vs competitors' 1-2 weeks) |
| **PREVENTION** | Stop denials before submission (vs appealing after denial) |
| **AUTONOMY** | Fixes execute without manual approval (vs "review and approve" workflows) |
| **SPECIALTY INTELLIGENCE** | Built for your vertical (vs generic RCM platforms) |

### Core Philosophy

> "You see the problem coming. You have time to act. The system acts for you."

---

## How It Works

### 1. Detection Layer (Faster than Competitors)

- **Real-time EHR webhooks**: 1-2 day alerts for submitted claims
- **Calendar-based prevention**: 30-day authorization expiration alerts
- **Behavioral prediction**: Day 3 detection vs competitors' day 14
- **Payment timing trends**: Detect cash flow stress before denials spike

### 2. Intelligence Layer (Smarter than Competitors)

- **Pre-submission risk scoring**: Flag high-risk claims BEFORE sending
- **Specialty-specific baselines**:
  - **Dialysis**: MA payment variance (when MA pays <85% of traditional Medicare)
  - **ABA**: Authorization exhaustion projection (30-day reauth alerts)
  - **Imaging**: RBM requirement tracking (eviCore/AIM PA rules by payer)
  - **Home Health**: PDGM grouper validation + F2F/NOA deadline tracking
- **Network effects**: Cross-customer intelligence ("8 practices affected by UHC rule change")

### 3. Execution Layer (More Autonomous than Competitors)

- **Pre-approved rules engine**: Execute first, notify after
- **Payer portal automation**: RPA for form submission, reauth requests, appeals
- **Zero-touch workflows**: No manual approval bottlenecks
- **Audit trail**: Log every autonomous action for compliance

---

## Detection Engines

| Engine | Purpose | Alert Trigger |
|--------|---------|---------------|
| **DriftWatch** | Denial rate detection | Week-over-week change >10%, p-value <0.05 |
| **DenialScope** | Dollar spike detection | >$50K weekly denial spike |
| **DelayGuard** | Payment timing detection | 4-week worsening trend |
| **Authorization Tracking** | Calendar-based prevention | 30/14/3 days before expiration |
| **Pre-Submission Scoring** | Risk scoring | Risk score >70 (HIGH) |
| **Behavioral Prediction** | Early pattern detection | Day 3 detection of anomalies |

---

## Specialty Modules

### Dialysis Intelligence
- MA Payment Variance Tracking (Traditional Medicare vs MA)
- ESRD PPS Drift Alerts
- TDAPA/TPNIES Add-on Detection

### ABA Therapy Intelligence
- Authorization Cycle Tracking (30/14/3 day alerts)
- Visit Exhaustion Projection
- BCBA Credential Expiration

### Imaging Center Intelligence
- RBM Requirement Tracking (eviCore, AIM)
- AUC Compliance Validation
- Medical Necessity Scoring

### Home Health Intelligence
- PDGM Grouper Validation (432+ combinations)
- Face-to-Face Timing Validation
- NOA Deadline Tracking

---

## Who Should Use Upstream

**Target Users**: Owner-operated healthcare businesses (dialysis centers, ABA therapy providers, imaging centers, home health agencies) with 1-25 locations, thin margins, and high sensitivity to cash flow disruption.

**Primary Roles**:
- Revenue Cycle Directors who need early visibility into payer behavior changes
- Billing Managers tracking denial trends and payer policy shifts
- RCM Analysts investigating root causes of revenue variance

**Time to Value**:
- Setup: 30 minutes (upload claims, configure alerts)
- First insight: After first weekly run (~5 days)
- Routine use: 5-minute daily check, 20-minute weekly review

---

## Competitive Positioning

| Capability | Upstream | Adonis | Waystar | Rivet |
|------------|----------|--------|---------|-------|
| Detection Speed | **Day 3** | Day 14 | Day 30+ | Day 30+ |
| Execution | **Autonomous** | Manual approval | Manual | Manual |
| Intelligence | Behavioral prediction | Post-denial | Claims workflow | Contract benchmarking |
| Specialty Focus | **Built-in** | Generic | Generic | Generic |

---

## Tech Stack

| Layer | Technology | Why |
|-------|------------|-----|
| **Backend** | Python 3.12, Django 5.x | Rapid iteration, batteries included |
| **API** | Django REST Framework | Industry standard, JWT auth ready |
| **Database** | PostgreSQL (prod), SQLite (dev) | Simple dev, scalable prod |
| **Task Queue** | Celery + Redis | Async processing, scheduled tasks |
| **Frontend** | React 19, Vite 7, Tailwind CSS v4 | Modern, performant SPA |
| **Testing** | pytest, Vitest, Playwright | Full stack coverage |
| **Security** | django-auditlog, encrypted fields | PHI compliance ready |

---

## Getting Started

### Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Apply database migrations
python manage.py migrate

# Load demo data (optional - creates sample practice)
python manage.py loaddata demo_data

# Create a superuser
python manage.py createsuperuser

# Run the development server
python manage.py runserver
```

Visit `http://localhost:8000` to access the application.

### Frontend Development

```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:5173` for the React frontend.

### Running Detection Engines

```bash
# Run weekly payer drift detection for all customers
python manage.py run_weekly_payer_drift

# Check expiring authorizations
python manage.py check_expiring_authorizations
```

### API Access

```bash
# Get JWT token
curl -X POST http://localhost:8000/api/v1/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "your-user", "password": "your-pass"}'

# View API documentation
open http://localhost:8000/api/v1/docs/
```

---

## Project Structure

```
upstream/
├── models.py              # Customer, ClaimRecord, AlertEvent, etc.
├── views.py               # Web portal views
├── api/
│   ├── serializers.py     # DRF serializers
│   ├── views.py           # API viewsets
│   ├── permissions.py     # Multi-tenant access control
│   └── urls.py            # API routes
├── services/
│   ├── payer_drift.py     # DriftWatch detection algorithm
│   ├── scoring.py         # Pre-submission risk scoring
│   └── detection/         # Detection engines
├── products/              # Specialty modules
│   ├── dialysis/          # MA variance, ESRD PPS
│   ├── aba/               # Authorization tracking
│   ├── imaging/           # PA requirements
│   └── homehealth/        # PDGM validation
├── management/commands/   # CLI commands for scheduled tasks
├── fixtures/              # Demo data for onboarding
└── templates/             # Django HTML templates

frontend/
├── src/
│   ├── components/        # React components
│   │   ├── common/        # Shared UI components
│   │   ├── layout/        # Navigation, sidebar, header
│   │   ├── dashboard/     # Dashboard widgets
│   │   ├── claims/        # Claims scoring views
│   │   ├── alerts/        # Alert management
│   │   ├── execution/     # Execution log timeline
│   │   └── settings/      # Automation settings
│   ├── pages/             # Route pages
│   ├── hooks/             # Custom hooks (useDarkMode, etc.)
│   └── services/          # API client
├── e2e/                   # Playwright E2E tests
└── vitest.config.ts       # Test configuration
```

---

## Alert Types (40+)

### Detection Alerts
- `denial_rate_drift` - Denial rate spike detected
- `denial_dollar_spike` - Significant denial dollars increase
- `payment_timing_slowdown` - Payment timing increased
- `payer_behavior_shift_day_3` - Early detection of denial rate change

### Authorization Alerts
- `authorization_expiring_30_days` - Reauth deadline approaching (MEDIUM)
- `authorization_expiring_14_days` - Urgent reauth needed (HIGH)
- `authorization_expiring_3_days` - Critical reauth deadline (CRITICAL)
- `authorization_units_exhausting` - Will exhaust visits before reauth

### Specialty Alerts
- `dialysis_ma_payment_variance` - MA underpaying vs baseline
- `aba_modifier_missing` - Required modifier not present
- `rbm_pa_required_missing` - PA required but not requested
- `pdgm_grouping_mismatch` - Assigned group != calculated group

### Pre-Submission Alerts
- `high_risk_claim` - Claim flagged for review
- `missing_required_modifier` - Required modifier not present
- `diagnosis_mismatch` - Diagnosis doesn't support CPT

---

## Autonomous Actions

| Action | Description |
|--------|-------------|
| `submit_reauth_request` | Auto-submit reauthorization to payer portal |
| `generate_and_submit_appeal` | Create + submit appeal letter |
| `hold_for_review` | Flag claim for human review |
| `auto_add_modifier` | Add missing required modifier |
| `request_prior_authorization` | Submit PA request to RBM |
| `escalate_to_human` | Send to manual review queue |

---

## Milestones

| # | Name | Status | Stories |
|---|------|--------|---------|
| 01 | Core Scoring Engine | Complete | 18/18 |
| 02 | Specialty Modules | Complete | 23/23 |
| 03 | Frontend MVP | Complete | 18/18 |
| 04 | EHR Integrations | Complete | 14/14 |
| 05 | Launch Prep | Complete | 17/17 |

**Total**: 90/90 stories (100%)

---

## Documentation

- [CLAUDE.md](CLAUDE.md) - Project intelligence for AI assistants
- [OPERATOR_GUIDE.md](OPERATOR_GUIDE.md) - Detailed operator workflows
- [AUTHENTICATION_GUIDE.md](AUTHENTICATION_GUIDE.md) - Auth setup
- [GCP_DEPLOYMENT_GUIDE.md](GCP_DEPLOYMENT_GUIDE.md) - Production deployment
- [ARCHITECTURE_PRODUCT_LINE.md](ARCHITECTURE_PRODUCT_LINE.md) - System architecture

---

## Contributing

This project is in active development. See [CHANGELOG.md](CHANGELOG.md) for recent updates.

**Questions?** Contact the team at [scale@getbyteworthy.com](mailto:scale@getbyteworthy.com)

---

## License

Proprietary - 2026 Byteworthy. All rights reserved.
