# Upstream

**Early-Warning Payer Risk Intelligence Platform**

Upstream helps healthcare organizations detect payer behavior changes **30-60 days earlier** than traditional monthly reporting—before revenue loss compounds.

---

## What Upstream Does

Healthcare billing teams typically discover payer issues (denial spikes, policy changes, payment delays) **30-60 days too late**. By then, the damage has compounded.

Upstream provides **early warning** so you can act while there's still time:

- **Detect** denial rate changes within days, not months
- **Predict** which claims are at risk before submission
- **Track** authorization expirations proactively
- **Execute** pre-approved fixes automatically

> "You see the problem coming. You have time to act."

---

## Key Features

### Detection Engines
- **DriftWatch** — Week-over-week denial rate monitoring
- **DenialScope** — Dollar-weighted denial tracking
- **DelayGuard** — Payment timing trend detection
- **Authorization Tracking** — Expiration and exhaustion alerts
- **Pre-Submission Scoring** — Risk assessment before claims go out

### Specialty Intelligence
Purpose-built modules for healthcare verticals:
- Dialysis Centers
- ABA Therapy Providers
- Imaging Centers
- Home Health Agencies

### Autonomous Execution
Define rules once, let Upstream execute:
- Automatic reauthorization requests
- Appeal generation for known patterns
- High-risk claim holds for review

---

## Who It's For

**Target Users**: Owner-operated healthcare businesses with 1-25 locations who need early visibility into payer behavior changes.

**Primary Roles**:
- Revenue Cycle Directors
- Billing Managers
- RCM Analysts

**Time to Value**:
- Setup: 30 minutes
- First insight: ~5 days
- Daily check: 5 minutes

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python, Django |
| API | Django REST Framework |
| Database | PostgreSQL |
| Frontend | React, TypeScript, Tailwind CSS |
| Testing | pytest, Vitest, Playwright |

---

## Getting Started

### Prerequisites
- Python 3.12+
- Node.js 20+
- PostgreSQL

### Installation

```bash
# Clone the repository
git clone https://github.com/byteworthy/upstream.git
cd upstream

# Backend setup
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver

# Frontend setup (separate terminal)
cd frontend
npm install
npm run dev
```

### Running Tests

```bash
# Backend
python manage.py test upstream -v 2

# Frontend
cd frontend && npm run test
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [OPERATOR_GUIDE.md](OPERATOR_GUIDE.md) | User guide for operators |
| [OPERATOR_WORKFLOWS.md](OPERATOR_WORKFLOWS.md) | Daily/weekly workflows |
| [AUTHENTICATION_GUIDE.md](AUTHENTICATION_GUIDE.md) | Authentication setup |

---

## Project Status

Upstream is in active development. Core detection engines, specialty modules, and the frontend MVP are complete.

---

## Contact

**Byteworthy** — [scale@getbyteworthy.com](mailto:scale@getbyteworthy.com)

---

## License

Proprietary © 2026 Byteworthy. All rights reserved.

This software is proprietary and confidential. Unauthorized copying, distribution, or use is strictly prohibited.
