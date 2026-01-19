# 📡 Payrixa

**Early-warning intelligence for healthcare revenue operations.**

## What Payrixa Does

Payrixa is a web-based system that detects payer behavior drift and operational variance using claims data.
It surfaces signals and alerts for review without automating decisions.

### Core Features

- 📊 **Payer Drift Detection** — Week-over-week analysis identifies when payer denial rates shift beyond normal variance
- 📁 **Claim Upload & Normalization** — CSV upload with automatic payer name and CPT code mapping
- ⚠️ **Threshold-Based Alerts** — Customizable sensitivity to flag statistically significant changes
- 📈 **Weekly Report Runs** — Scheduled analysis with historical tracking

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
