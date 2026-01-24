# Data Quality & Model Amplification Setup Guide

Complete setup guide for the new data quality, validation, and amplified model features.

---

## 📋 Prerequisites

- Python 3.12+
- Django 5.x
- PostgreSQL database
- Existing Upstream installation

---

## 🚀 Installation Steps

### Step 1: Install Dependencies

```bash
# Install required Python packages
pip install scipy scikit-learn numpy

# Update requirements.txt
cat >> requirements.txt <<EOF
scipy>=1.11.0
scikit-learn>=1.3.0
numpy>=1.24.0
EOF
```

### Step 2: Run Migrations

```bash
# Create and run migrations for new models
python manage.py makemigrations
python manage.py migrate
```

This will create:
- 10 new database tables
- 35+ new fields on existing tables
- 30+ new indexes

### Step 3: Add URL Patterns

Add the data quality URLs to your main `urls.py`:

```python
# hello_world/urls.py
from django.urls import path, include

urlpatterns = [
    # ... existing patterns ...

    # Data Quality URLs
    path('', include('upstream.urls_data_quality')),
]
```

### Step 4: Initialize Data Quality for Customers

Run the initialization command to create default validation rules:

```bash
# For all customers
python manage.py init_data_quality --all

# Or for specific customer
python manage.py init_data_quality --customer "Acme Corp"
```

This creates 15 default validation rules for each customer.

### Step 5: Load Template Tags

Ensure template tags are loaded. Add to `settings.py` if not already present:

```python
# In TEMPLATES configuration
'OPTIONS': {
    'context_processors': [
        # ... existing processors ...
    ],
    'libraries': {
        'quality_filters': 'upstream.templatetags.quality_filters',
    }
}
```

---

## 🎨 Feature Access

### Data Quality Dashboard
```
URL: /quality/
```

Access the main data quality dashboard showing:
- Overall health score
- Quality metrics
- Recent uploads with quality scores
- Open anomalies

### Upload Quality Detail
```
URL: /quality/upload/<upload_id>/
```

View detailed quality report for a specific upload:
- Quality grade and score
- Validation failures
- Detected anomalies
- Recommendations

### Validation Rules
```
URL: /quality/rules/
```

Manage validation rules:
- View all rules
- Rule statistics
- Recent failures

### Quality Trends
```
URL: /quality/trends/?days=30
```

View quality trends over time:
- Quality score trends
- Metrics by type
- Validation failure trends

### Anomaly Dashboard
```
URL: /quality/anomalies/
```

Monitor data anomalies:
- Unacknowledged anomalies
- Anomalies by type/severity
- Acknowledgment workflow

---

## 🔧 Configuration

### Enable Data Quality Validation

In your upload processing code, add validation:

```python
from upstream.core.data_quality_service import DataQualityService

# During upload processing
service = DataQualityService(customer)

# Validate uploaded rows
validation_result = service.validate_upload(upload, rows_data)

# Check results
if validation_result['summary']['accepted_rows'] > 0:
    # Process accepted rows
    pass

if validation_result['anomalies']:
    # Handle detected anomalies
    pass
```

### Calculate Quality Metrics

Schedule periodic quality metric calculation:

```python
from upstream.core.data_quality_service import DataQualityService
from datetime import date, timedelta

service = DataQualityService(customer)

# Calculate metrics for last 7 days
start_date = date.today() - timedelta(days=7)
end_date = date.today()

metrics = service.calculate_quality_metrics(start_date, end_date)
```

### Generate Quality Reports

```python
from upstream.core.quality_reporting_service import DataQualityReportingService

reporting = DataQualityReportingService(customer)

# Generate scorecard
scorecard = reporting.generate_quality_scorecard()

# Generate trend report
trends = reporting.generate_quality_trend_report(days=30)

# Generate upload quality summary
summary = reporting.generate_upload_quality_summary(upload)
```

---

## 📊 DriftWatch Signals

### Enable Advanced Drift Detection

```python
from upstream.products.driftwatch.services import DriftWatchSignalService
from upstream.models import ReportRun

# Create report run
report_run = ReportRun.objects.create(
    customer=customer,
    run_type='weekly',
    status='running'
)

# Run drift detection
service = DriftWatchSignalService(customer)
results = service.compute_all_signals(report_run)

# Results contain:
# - Denial rate drift
# - Underpayment variance (revenue recovery)
# - Payment delays
# - Auth failure spikes
# - Approval rate changes
# - Processing time drift

print(f"Created {results['signals_created']} drift signals")
print(f"By type: {results['by_type']}")
```

---

## 🤖 DenialScope ML Features

### Run Denial Clustering

```python
from upstream.products.denialscope.ml_services import DenialClusteringService

service = DenialClusteringService(customer)

# Cluster recent denials
clusters = service.cluster_denials(days_back=90, min_cluster_size=5)

for cluster in clusters:
    print(f"Cluster: {cluster.cluster_name}")
    print(f"Claims: {cluster.claim_count}")
    print(f"Pattern: {cluster.pattern_description}")
    print(f"Root cause: {cluster.root_cause_hypothesis}")
```

### Detect Denial Cascades

```python
from upstream.products.denialscope.ml_services import CascadeDetectionService

service = CascadeDetectionService(customer)

# Detect cascades
cascades = service.detect_cascades(days_back=60)

for cascade in cascades:
    print(f"Cascade: {cascade.cascade_type}")
    print(f"Claims affected: {cascade.claim_count}")
    print(f"Total impact: ${cascade.total_denied_dollars}")
```

### Generate Pre-Denial Warnings

```python
from upstream.products.denialscope.ml_services import PreDenialWarningService

service = PreDenialWarningService(customer)

# Check claim for denial risk
warnings = service.generate_warnings(claim)

for warning in warnings:
    print(f"Warning: {warning.warning_type}")
    print(f"Probability: {warning.denial_probability:.0%}")
    print(f"Actions: {warning.recommended_actions}")
```

### Auto-Generate Appeals

```python
from upstream.products.denialscope.ml_services import AppealGenerationService

service = AppealGenerationService(customer)

# Generate appeal for denied claim
appeal = service.generate_appeal(denied_claim)

print(f"Appeal ID: {appeal.appeal_id}")
print(f"Letter:\n{appeal.appeal_letter}")
print(f"Required docs: {appeal.required_documentation}")
```

---

## 🔍 Custom Validation Rules

### Create Custom Rule

```python
from upstream.core.validation_models import ValidationRule

rule = ValidationRule.objects.create(
    customer=customer,
    name='Custom Rule',
    code='CUSTOM_001',
    rule_type='business_rule',
    severity='error',
    enabled=True,
    error_message_template='Custom validation failed',
    validation_logic={
        'rule_name': 'custom_business_logic',
        'parameters': {
            'threshold': 100
        }
    },
    execution_order=100
)
```

---

## 📈 Monitoring & Alerts

### Monitor Data Quality

Create alerts based on quality scores:

```python
from upstream.core.validation_models import DataQualityMetric

# Check recent quality
recent_metrics = DataQualityMetric.objects.filter(
    customer=customer,
    metric_type='completeness',
    measurement_date__gte=date.today() - timedelta(days=1)
).order_by('-measurement_date').first()

if recent_metrics and recent_metrics.score < 0.90:
    # Send alert
    print(f"⚠️ Data quality degraded: {recent_metrics.score:.1%}")
```

### Monitor Anomalies

```python
from upstream.core.validation_models import DataAnomalyDetection

# Check unacknowledged critical anomalies
critical = DataAnomalyDetection.objects.filter(
    customer=customer,
    severity='critical',
    acknowledged=False
).count()

if critical > 0:
    print(f"🚨 {critical} critical anomalies require attention")
```

---

## 🧪 Testing

### Run Tests

```bash
# Test data quality service
python manage.py test payrixa.tests_data_quality

# Test validation rules
python manage.py test payrixa.tests_validation

# Test ML services
python manage.py test payrixa.products.denialscope.tests_ml
```

---

## 📚 API Endpoints

### Quality Metrics API

```bash
# Get quality metrics chart data
GET /api/quality/metrics/chart-data/?metric_type=completeness&days=30

# Get validation failures chart data
GET /api/quality/validation/chart-data/?days=30

# Acknowledge anomaly
POST /api/quality/anomaly/<id>/acknowledge/
Content-Type: application/json
{
    "notes": "Acknowledged and investigated"
}
```

---

## 🎯 Quick Start Example

Complete example from upload to quality reporting:

```python
from upstream.core.data_quality_service import DataQualityService
from upstream.core.quality_reporting_service import DataQualityReportingService

# 1. Validate upload
quality_service = DataQualityService(customer)
validation_result = quality_service.validate_upload(upload, rows_data)

# 2. Check quality
if validation_result['summary']['rejected_rows'] > 0:
    print(f"Rejected {validation_result['summary']['rejected_rows']} rows")

# 3. Handle anomalies
for anomaly in validation_result['anomalies']:
    if anomaly['severity'] == 'critical':
        # Alert operator
        print(f"Critical anomaly: {anomaly['description']}")

# 4. Generate report
reporting_service = DataQualityReportingService(customer)
summary = reporting_service.generate_upload_quality_summary(upload)

print(f"Quality Grade: {summary['quality_grade']}")
print(f"Acceptance Rate: {summary['acceptance_rate']:.1f}%")
print(f"Recommendations: {summary['recommendations']}")
```

---

## 🐛 Troubleshooting

### Issue: Migrations fail

```bash
# Reset migrations (DEV ONLY)
python manage.py migrate upstream zero
python manage.py migrate upstream

# Or manually create
python manage.py makemigrations upstream --name amplified_models
python manage.py migrate
```

### Issue: scipy not found

```bash
pip install --upgrade scipy scikit-learn numpy
```

### Issue: Template tags not loaded

Add to templates in HTML files:
```django
{% load quality_filters %}
```

### Issue: No validation rules

```bash
python manage.py init_data_quality --all
```

---

## 📞 Support

For issues or questions:
- Check MODEL_AMPLIFICATION_SUMMARY.md
- Review test files in upstream/tests_*
- Check Django admin for model data

---

## ✅ Verification Checklist

After setup, verify:

- [ ] Migrations applied successfully
- [ ] Default validation rules created
- [ ] Quality dashboard accessible at /quality/
- [ ] Upload validation works
- [ ] Anomaly detection runs
- [ ] DriftWatch signals generate
- [ ] DenialScope clustering works
- [ ] Template tags load correctly
- [ ] Charts render properly

---

**Setup Time:** ~15-30 minutes
**Last Updated:** January 24, 2026
