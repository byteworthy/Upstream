# Upstream Hub v1 Project Status

## Hub v1 Definition (LOCKED)

- **One vertical**: Revenue cycle healthcare analytics
- **One ingest path**: Webhook/CSV upload via existing ingestion
- **Two products in hub**: DenialScope, DriftWatch
- **One signal per product**:
  - DenialScope: `denial_dollars_spike`
  - DriftWatch: `DENIAL_RATE`
- **One alert route**: Email only (Slack/webhooks disabled by default)
- **Two dashboards** + **one hub landing page** (Axis)
- **One shared evidence payload schema** and **one artifact format**

## Products

| Product     | Signal Type           | Dashboard Route             | Status |
|-------------|----------------------|----------------------------|--------|
| DenialScope | denial_dollars_spike | /portal/products/denialscope/ | ✅ Live |
| DriftWatch  | DENIAL_RATE          | /portal/products/driftwatch/  | ✅ Live |

## Routes

| Route              | Description              |
|--------------------|--------------------------|
| /portal/axis/      | Hub landing page (Axis)  |
| /portal/products/  | Redirect to /portal/axis/|

## Demo Commands

### DenialScope Demo
```bash
python manage.py generate_denialscope_test_data --customer 1
python manage.py compute_denialscope --customer 1
```

**Expected output:**
- At least 1 `DenialSignal` with `signal_type=denial_dollars_spike`
- Dashboard `/portal/products/denialscope/` shows Total Denials, Top Payer, Top Reason

### DriftWatch Demo
```bash
python manage.py generate_driftwatch_demo --customer 1
```

**Expected output:**
- At least 3 `DriftEvent` rows with `drift_type=DENIAL_RATE` and payers starting with `Demo-`
- Dashboard `/portal/products/driftwatch/` shows events in table and top payers

### Verify Demo Data
```bash
python manage.py shell -c "from upstream.models import DriftEvent; from upstream.products.denialscope.models import DenialSignal; print('DriftEvents:', DriftEvent.objects.filter(drift_type='DENIAL_RATE').count()); print('DenialSignals:', DenialSignal.objects.filter(signal_type='denial_dollars_spike').count())"
```

## Email Alert Artifact

- Subject: `[{product_name} Alert] {customer} - {severity} Severity`
- Body includes: one-sentence explanation, evidence table
- Suppression: 4-hour cooldown per (customer, product, signal, entity)

## Non-Negotiable Rules

1. No third product
2. No new data models or migrations
3. No second ingest path
4. Slack/webhooks disabled by default
5. DriftWatch v1: DENIAL_RATE only
6. DenialScope v1: denial_dollars_spike only
7. Smallest change possible
8. All tests green
9. No secrets in code/logs/git
10. Ask before violating rules
