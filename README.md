# 📡 Payrixa

**Early-warning intelligence for healthcare revenue operations.**

## What Payrixa Does

Payrixa is an **early-warning intelligence system** for healthcare revenue operations. It detects when payers change their behavior—denying more claims, changing policies, or creating new revenue risks—usually 30-60 days before traditional monthly reporting would catch it.

**For Operators**: Think of Payrixa as a smoke detector for your revenue cycle. It doesn't fight the fire for you, but it tells you early when something's wrong so you can act before it becomes expensive.

### Core Features

- 📊 **DriftWatch (Denial Rate Detection)** — Detects week-over-week changes in payer denial rates. Catches when a payer who normally denies 8% suddenly denies 15%.
- 💰 **DenialScope (Dollar Spike Detection)** — Flags sudden increases in denial dollars by payer or reason code. Identifies $50K+ revenue leaks before they compound.
- 📁 **Claim Upload & Normalization** — CSV upload with automatic payer name and CPT code mapping. Works with your existing data.
- ⚠️ **Smart Alerting** — Statistical thresholds flag significant changes, not noise. Email alerts with evidence and context.
- 📈 **Weekly Analysis** — Runs automatically. You get early signals, not month-end surprises.

### Who Should Use Payrixa

**Primary Users**:
- Revenue Cycle Directors who need early visibility into payer behavior changes
- Billing Managers tracking denial trends and payer policy shifts
- RCM Analysts investigating root causes of revenue variance

**What You'll See**:
- Alerts when payers change denial behavior outside normal variance
- Evidence tables showing which claims, payers, and codes are affected
- Historical context to distinguish new issues from recurring patterns
- Actionable signals, not raw data dumps

**Time to Value**: 
- Setup: 30 minutes (upload claims, configure alerts)
- First insight: After first weekly run (~5 days)
- Routine use: 5-minute daily check, 20-minute weekly review

**Read more**: See `OPERATOR_GUIDE.md` for detailed workflows and decision frameworks.

## Tech Stack

| Layer | Technology | Why |
|-------|------------|-----|
| **Backend** | Python 3.12, Django 5.x | Rapid iteration, batteries included |
| **API** | Django REST Framework | Industry standard, JWT auth ready |
| **Database** | SQLite (dev), PostgreSQL (prod) | Simple dev, scalable prod |
| **Security** | django-auditlog, encrypted fields | PHI compliance ready |
| **Frontend** | Django Templates → React (planned) | Server-first, SPA later |

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

### Running Payer Drift Analysis

```bash
# Run weekly payer drift detection for all customers
python manage.py run_weekly_payer_drift
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
payrixa/
├── models.py              # Customer, ClaimRecord, DriftEvent, etc.
├── views.py               # Web portal views
├── api/
│   ├── serializers.py     # DRF serializers
│   ├── views.py           # API viewsets
│   ├── permissions.py     # Multi-tenant access control
│   └── urls.py            # API routes
├── services/
│   └── payer_drift.py     # Core drift detection algorithm
├── management/commands/   # CLI commands for scheduled tasks
├── fixtures/              # Demo data for onboarding
└── templates/             # Django HTML templates
```

---

## Roadmap

### Phase 1: Core Platform ✅
Multi-tenant architecture, CSV uploads, payer drift detection, API layer

### Phase 2: Enhanced Analytics
Trend visualization, custom date ranges, CPT group-level drift, payer benchmarking

### Phase 3: Enterprise
SSO/SAML, role-based access, webhook integrations, audit logging dashboard

---

## Contributing

This project is in active development. See [CHANGELOG.md](CHANGELOG.md) for recent updates.

**Questions?** Contact the team at [scale@getbyteworthy.com](mailto:scale@getbyteworthy.com)

---

## License

Proprietary — © 2026 Byteworthy. All rights reserved.
