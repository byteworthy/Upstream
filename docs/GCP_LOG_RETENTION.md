# GCP Cloud Logging Retention Policies

**HIPAA-compliant log retention configuration for Google Cloud Logging**

This document describes the log retention policies, configuration procedures, and management practices for Upstream's Cloud Logging infrastructure on Google Cloud Platform.

---

## Table of Contents

1. [Overview](#overview)
2. [Retention Policies](#retention-policies)
3. [Log Buckets](#log-buckets)
4. [Setup Instructions](#setup-instructions)
5. [Querying Logs](#querying-logs)
6. [Cost Management](#cost-management)
7. [HIPAA Compliance](#hipaa-compliance)
8. [Troubleshooting](#troubleshooting)
9. [Related Documentation](#related-documentation)

---

## Overview

### Purpose

Google Cloud Logging provides centralized log aggregation for applications running on GCP. This document covers the configuration of log retention policies that meet HIPAA requirements while managing costs effectively.

### HIPAA Requirements

HIPAA mandates retention of audit logs for **6 years from creation or last use**. We conservatively implement **7-year retention** for audit logs to ensure compliance.

### Cost Implications

Cloud Logging pricing (as of 2024):
- **Ingestion:** $0.50/GB after 50GB/month free tier
- **Storage:** $0.01/GB/month

Different log types have different retention needs. Aligning retention policies with operational requirements reduces costs while maintaining compliance.

### Difference from Local Logs

This configuration applies to **Cloud Logging** (centralized log aggregation). It complements the local file-based logging configured in `upstream/logging_config.py`:

| Aspect | Local Logs | Cloud Logging |
|--------|------------|---------------|
| **Location** | Container filesystem | Centralized GCP service |
| **Retention** | Lost on container restart | Persistent across deployments |
| **Searchability** | Limited to grep/awk | Full-text search, filters, aggregation |
| **Access** | Requires shell access | Cloud Console, gcloud CLI, API |
| **Cost** | Free (disk space) | Ingestion + storage fees |
| **HIPAA Compliance** | Local only | Centralized audit trail |

**Best practice:** Cloud Logging is the source of truth for production. Local logs are for development/debugging.

---

## Retention Policies

### Retention Periods by Log Type

| Log Type | Retention Period | Justification | Bucket |
|----------|------------------|---------------|--------|
| **Application logs** (`upstream.*`) | 90 days | Operational troubleshooting, incident investigation | `upstream-app-logs` |
| **Audit logs** (`auditlog`) | 7 years (2555 days) | HIPAA compliance requirement | `upstream-audit-logs` |
| **Security logs** (`django.security`) | 90 days | Security incident investigation | `upstream-app-logs` |
| **Performance logs** (`upstream.performance`) | 30 days | Performance monitoring and optimization | `upstream-app-logs` |
| **Debug logs** | Excluded in production | Not needed in production (cost reduction) | N/A |

### Alignment with Local Logging

These retention periods align with the policies in `upstream/logging_config.py`:

```python
# From logging_config.py
retention_map = {
    "DEBUG": 7,       # Short retention (development only)
    "INFO": 30,       # Standard retention
    "WARNING": 90,    # Extended retention
    "ERROR": 90,      # Extended retention
    "CRITICAL": 90,   # Extended retention
}
# Audit logs: 2555 days (7 years) for HIPAA
```

**Cloud Logging extends local retention** - local logs rotate more frequently, while Cloud Logging retains logs for the full policy period.

---

## Log Buckets

### Bucket Architecture

Cloud Logging uses **log buckets** to organize and retain logs. We use two buckets:

1. **`upstream-app-logs`** - Application and operational logs (90 days)
2. **`upstream-audit-logs`** - Audit trail logs (7 years)

### 1. Application Logs Bucket

**Name:** `upstream-app-logs`
**Retention:** 90 days
**Location:** global (cross-region access)

**Contains:**
- Application logs from `upstream.*` loggers
- Security logs from `django.security`
- Performance logs from `upstream.performance`
- Error logs (WARNING, ERROR, CRITICAL)

**Log Filter:**
```
jsonPayload.logger=~"upstream.*" AND severity>=INFO
```

This captures all logs from Upstream application loggers at INFO level and above.

### 2. Audit Logs Bucket

**Name:** `upstream-audit-logs`
**Retention:** 2555 days (7 years)
**Location:** global (cross-region access)

**Contains:**
- Audit trail logs from `auditlog` logger
- All logs with `jsonPayload.audit=true` flag

**Log Filter:**
```
jsonPayload.logger="auditlog" OR jsonPayload.audit=true
```

This captures:
- User actions (login, logout, data access)
- Data modifications (create, update, delete)
- Permission changes
- Configuration changes

### Log Sinks

**Log sinks** route logs from Cloud Logging to log buckets based on filters:

| Sink Name | Destination | Filter | Purpose |
|-----------|-------------|--------|---------|
| `upstream-app-logs-sink` | `upstream-app-logs` bucket | `jsonPayload.logger=~"upstream.*" AND severity>=INFO` | Route application logs |
| `upstream-audit-logs-sink` | `upstream-audit-logs` bucket | `jsonPayload.logger="auditlog" OR jsonPayload.audit=true` | Route audit logs |

### Exclusion Filters

To reduce ingestion costs, we exclude logs that aren't needed:

| Exclusion Name | Description | Filter |
|----------------|-------------|--------|
| `exclude-debug-logs` | Exclude DEBUG logs in production | `severity=DEBUG` |
| `exclude-health-checks` | Exclude load balancer health checks | `httpRequest.requestUrl=~"/health/" AND httpRequest.userAgent=~"GoogleHC"` |
| `exclude-static-files` | Exclude static file requests (already logged by CDN) | `httpRequest.requestUrl=~"/static/"` |

**Note:** Exclusions apply before sinks, so excluded logs are not ingested (no cost).

---

## Setup Instructions

### Prerequisites

Before configuring log retention, ensure you have:

- [ ] gcloud CLI installed ([installation guide](https://cloud.google.com/sdk/docs/install))
- [ ] Authenticated to GCP (`gcloud auth login`)
- [ ] `logging.admin` IAM role on target project
- [ ] `PROJECT_ID` environment variable set

```bash
# Verify prerequisites
gcloud --version
gcloud auth list
export PROJECT_ID="your-project-id"
```

### Option 1: Automated Setup (Recommended)

Use the provided bash script to configure all log retention policies:

```bash
# Preview changes (dry-run)
export PROJECT_ID="your-project-id"
./scripts/configure_gcp_log_retention.sh --dry-run

# Apply configuration
./scripts/configure_gcp_log_retention.sh
```

**What it does:**
1. Enables Cloud Logging API
2. Creates `upstream-app-logs` bucket (90-day retention)
3. Creates `upstream-audit-logs` bucket (7-year retention)
4. Creates log sinks to route logs to buckets
5. Creates exclusion filters to reduce costs
6. Displays estimated monthly costs

**Expected output:**
```
=========================================
GCP Log Retention Configuration
=========================================
Project: your-project-id
Location: global
Mode: APPLY
=========================================

[INFO] Checking prerequisites...
[SUCCESS] Prerequisites OK
[INFO] Enabling Cloud Logging API...
[SUCCESS] Cloud Logging API enabled
[INFO] Creating log bucket: upstream-app-logs (90-day retention)...
[SUCCESS] Created bucket: upstream-app-logs
[INFO] Creating log bucket: upstream-audit-logs (2555-day retention)...
[SUCCESS] Created bucket: upstream-audit-logs
[INFO] Creating log sink: upstream-app-logs-sink...
[SUCCESS] Created sink: upstream-app-logs-sink
[INFO] Creating log sink: upstream-audit-logs-sink...
[SUCCESS] Created sink: upstream-audit-logs-sink
[INFO] Creating exclusion filter: exclude-debug-logs...
[SUCCESS] Created exclusion: exclude-debug-logs
[SUCCESS] Configuration complete!
```

### Option 2: GitHub Actions Workflow

Use the automated workflow for staging and production environments:

1. **Navigate to Actions tab** in GitHub repository
2. **Select "GCP Log Retention Setup" workflow**
3. **Click "Run workflow"**
4. **Configure inputs:**
   - Environment: staging or production
   - Dry run: true (preview) or false (apply)
5. **Review and approve** (production requires manual approval)

**Workflow benefits:**
- Consistent configuration across environments
- Built-in dry-run validation
- Configuration artifacts saved for 90 days
- GitHub Actions log retention configured automatically

### Option 3: Manual Setup

For manual configuration or custom requirements:

#### Step 1: Enable Cloud Logging API

```bash
gcloud services enable logging.googleapis.com
```

#### Step 2: Create Log Buckets

```bash
# Application logs bucket (90 days)
gcloud logging buckets create upstream-app-logs \
    --location=global \
    --retention-days=90 \
    --description="Application logs with 90-day retention"

# Audit logs bucket (7 years)
gcloud logging buckets create upstream-audit-logs \
    --location=global \
    --retention-days=2555 \
    --description="Audit logs with 7-year retention for HIPAA compliance"
```

#### Step 3: Create Log Sinks

```bash
# Application logs sink
gcloud logging sinks create upstream-app-logs-sink \
    "logging.googleapis.com/projects/$PROJECT_ID/locations/global/buckets/upstream-app-logs" \
    --log-filter='jsonPayload.logger=~"upstream.*" AND severity>=INFO'

# Audit logs sink
gcloud logging sinks create upstream-audit-logs-sink \
    "logging.googleapis.com/projects/$PROJECT_ID/locations/global/buckets/upstream-audit-logs" \
    --log-filter='jsonPayload.logger="auditlog" OR jsonPayload.audit=true'
```

#### Step 4: Create Exclusion Filters

```bash
# Exclude DEBUG logs
gcloud logging exclusions create exclude-debug-logs \
    --description="Exclude DEBUG logs to reduce costs" \
    --log-filter='severity=DEBUG'

# Exclude health checks
gcloud logging exclusions create exclude-health-checks \
    --description="Exclude load balancer health checks" \
    --log-filter='httpRequest.requestUrl=~"/health/" AND httpRequest.userAgent=~"GoogleHC"'

# Exclude static files
gcloud logging exclusions create exclude-static-files \
    --description="Exclude static file requests" \
    --log-filter='httpRequest.requestUrl=~"/static/"'
```

### Verification

Verify your configuration:

```bash
# List log buckets
gcloud logging buckets list --location=global

# List log sinks
gcloud logging sinks list

# List exclusions
gcloud logging exclusions list
```

**Expected output:**
```
BUCKET_ID                LOCATION  RETENTION_DAYS  DESCRIPTION
upstream-app-logs        global    90              Application logs with 90-day retention
upstream-audit-logs      global    2555            Audit logs with 7-year retention for HIPAA compliance

NAME                        DESTINATION                                                        FILTER
upstream-app-logs-sink      .../buckets/upstream-app-logs                                     jsonPayload.logger=~"upstream.*" AND severity>=INFO
upstream-audit-logs-sink    .../buckets/upstream-audit-logs                                   jsonPayload.logger="auditlog" OR jsonPayload.audit=true
```

### Updating Retention Periods

To update retention periods (e.g., after policy changes):

```bash
# Update application logs retention
gcloud logging buckets update upstream-app-logs \
    --location=global \
    --retention-days=120

# Update audit logs retention
gcloud logging buckets update upstream-audit-logs \
    --location=global \
    --retention-days=2920  # 8 years
```

---

## Querying Logs

### Using Cloud Console

1. **Navigate to** [Cloud Logging Console](https://console.cloud.google.com/logs)
2. **Select log bucket** from dropdown (upstream-app-logs or upstream-audit-logs)
3. **Enter query** in filter box
4. **Adjust time range** as needed

### Using gcloud CLI

#### View Recent Logs

```bash
# Last 10 application logs
gcloud logging read "jsonPayload.logger=~\"upstream.*\"" --limit=10

# Last 10 audit logs
gcloud logging read "jsonPayload.logger=\"auditlog\"" --limit=10

# Real-time tail (like tail -f)
gcloud logging tail "jsonPayload.logger=~\"upstream.*\""
```

#### Example Queries

**View all errors in last hour:**
```bash
gcloud logging read \
    "severity>=ERROR AND jsonPayload.logger=~\"upstream.*\"" \
    --limit=50 \
    --freshness=1h
```

**View audit logs for specific user:**
```bash
gcloud logging read \
    "jsonPayload.logger=\"auditlog\" AND jsonPayload.user_id=\"123\"" \
    --limit=50
```

**View logs from specific time range:**
```bash
gcloud logging read \
    "jsonPayload.logger=~\"upstream.*\"" \
    --limit=100 \
    --after="2024-01-15T00:00:00Z" \
    --before="2024-01-15T23:59:59Z"
```

**Search for specific claim ID:**
```bash
gcloud logging read \
    "jsonPayload.claim_id=\"CLM-12345\"" \
    --limit=20
```

**View security events:**
```bash
gcloud logging read \
    "jsonPayload.logger=\"django.security\" OR jsonPayload.security=true" \
    --limit=50
```

### Advanced Filtering

Cloud Logging supports rich query syntax:

| Filter Type | Example | Description |
|-------------|---------|-------------|
| **Exact match** | `jsonPayload.logger="auditlog"` | Exact string match |
| **Regex match** | `jsonPayload.logger=~"upstream.*"` | Regular expression |
| **Numeric comparison** | `jsonPayload.response_time>1000` | Greater than |
| **Boolean** | `jsonPayload.success=true` | Boolean field |
| **Severity** | `severity>=ERROR` | Log level filter |
| **HTTP** | `httpRequest.status=500` | HTTP status code |
| **Time range** | `timestamp>"2024-01-15T00:00:00Z"` | Time-based filter |

**Combine filters with AND/OR:**
```bash
gcloud logging read \
    "jsonPayload.logger=\"upstream.services\" AND severity>=WARNING AND jsonPayload.customer_id=\"456\""
```

### Exporting Logs for Analysis

#### Export to JSON

```bash
gcloud logging read \
    "jsonPayload.logger=\"auditlog\"" \
    --limit=1000 \
    --format=json > audit_logs.json
```

#### Export to CSV (via jq)

```bash
gcloud logging read \
    "jsonPayload.logger=~\"upstream.*\"" \
    --limit=1000 \
    --format=json \
    | jq -r '.[] | [.timestamp, .severity, .jsonPayload.message] | @csv' \
    > application_logs.csv
```

#### Export to BigQuery (for compliance audits)

For large-scale analysis or long-term archival:

```bash
# Create BigQuery dataset
bq mk --dataset $PROJECT_ID:upstream_logs

# Create log sink to BigQuery
gcloud logging sinks create upstream-logs-to-bigquery \
    "bigquery.googleapis.com/projects/$PROJECT_ID/datasets/upstream_logs" \
    --log-filter='jsonPayload.logger="auditlog"'
```

**Benefits:**
- SQL queries on log data
- Long-term archival beyond Cloud Logging retention
- Integration with data analysis tools
- Cost-effective for historical analysis

---

## Cost Management

### Current Pricing (2024)

| Service | Free Tier | Pricing |
|---------|-----------|---------|
| **Log ingestion** | 50GB/month | $0.50/GB |
| **Log storage** | 0GB | $0.01/GB/month |

### Monthly Cost Estimates

Based on typical usage patterns:

#### Staging Environment

| Component | Volume | Storage | Cost |
|-----------|--------|---------|------|
| Application logs (90 days) | 5GB/month | 15GB | $0.15/month storage |
| Audit logs (7 years) | 1GB/month | 85GB | $0.85/month storage |
| **Total ingestion** | 6GB/month | - | $0.00 (under free tier) |
| **Total storage** | - | 100GB | **$1.00/month** |

**Staging total: ~$1-2/month**

#### Production Environment

| Component | Volume | Storage | Cost |
|-----------|--------|---------|------|
| Application logs (90 days) | 10GB/month | 30GB | $0.30/month storage |
| Audit logs (7 years) | 2GB/month | 170GB | $1.70/month storage |
| **Total ingestion** | 12GB/month | - | $0.00 (under free tier) |
| **Total storage** | - | 200GB | **$2.00/month** |

**Production total: ~$2-5/month** (depending on traffic)

### How Exclusion Filters Reduce Costs

Our exclusion filters prevent ingestion of unnecessary logs:

| Excluded Log Type | Estimated Volume Saved | Monthly Savings |
|-------------------|------------------------|-----------------|
| DEBUG logs | 20GB/month | $0.00 (would be ingested without filter) |
| Health checks | 5GB/month | $0.00 (would be ingested without filter) |
| Static files | 10GB/month | $0.00 (would be ingested without filter) |

**Total saved:** ~35GB/month not ingested

Without exclusions, costs would be higher:
- **With exclusions:** $2/month
- **Without exclusions:** $20/month (47GB × $0.50 - $50 free tier = $0, but 47GB storage = $20)

**Exclusions reduce storage costs by 75%**

### Cost Optimization Strategies

#### 1. Adjust Retention Periods

If operational needs change, reduce retention:

```bash
# Reduce app logs to 60 days (from 90)
gcloud logging buckets update upstream-app-logs \
    --location=global \
    --retention-days=60
```

**Savings:** 33% reduction in application log storage

#### 2. Add More Exclusions

Exclude additional low-value logs:

```bash
# Exclude verbose third-party library logs
gcloud logging exclusions create exclude-verbose-libs \
    --log-filter='jsonPayload.logger=~"urllib3|boto3" AND severity<WARNING'
```

#### 3. Sample High-Volume Logs

For very high traffic, sample logs instead of capturing all:

```bash
# Sample 10% of INFO logs (keep all WARNING+)
gcloud logging exclusions create sample-info-logs \
    --log-filter='severity=INFO AND sample(insertId, 0.1)'
```

**Note:** Don't sample audit logs - HIPAA requires complete audit trail.

#### 4. Use BigQuery for Historical Analysis

For logs older than 90 days, export to BigQuery (cheaper storage):

- **Cloud Logging storage:** $0.01/GB/month
- **BigQuery storage:** $0.02/GB/month (standard), $0.01/GB/month (long-term)

BigQuery long-term storage is cost-neutral but enables SQL queries.

### Monitoring Costs

#### View Current Usage

```bash
# View log ingestion and storage in Cloud Console
# https://console.cloud.google.com/logs/usage

# Or via gcloud (requires billing API)
gcloud logging usage --project=$PROJECT_ID
```

#### Set Up Billing Alerts

```bash
# Create budget alert at $10/month
gcloud billing budgets create \
    --billing-account=YOUR_BILLING_ACCOUNT \
    --display-name="Cloud Logging Budget" \
    --budget-amount=10 \
    --threshold-rule=percent=80 \
    --threshold-rule=percent=100
```

---

## HIPAA Compliance

### Audit Log Requirements

HIPAA Security Rule §164.312(b) requires:

> "Implement hardware, software, and/or procedural mechanisms that record and examine activity in information systems that contain or use electronic protected health information."

**Our implementation:**
- ✅ **7-year retention** for audit logs (exceeds 6-year requirement)
- ✅ **Immutable logs** (Cloud Logging prevents modification)
- ✅ **Access controls** (IAM permissions for log viewing)
- ✅ **Complete audit trail** (all PHI access logged)

### What Must Be Logged

Our `auditlog` logger captures all required events:

| Event Type | Example | Logged Fields |
|------------|---------|---------------|
| **Access** | User views patient data | user_id, resource, action, timestamp |
| **Modification** | User updates claim | user_id, resource, action, before, after, timestamp |
| **Authentication** | User logs in | user_id, success, ip_address, timestamp |
| **Authorization** | Permission denied | user_id, resource, action, reason, timestamp |
| **Configuration** | Admin changes settings | user_id, setting, old_value, new_value, timestamp |

### PHI Scrubbing

All logs are automatically scrubbed of PHI before writing:

**Configured in:** `upstream/logging_config.py`

**Protected data:**
- Social Security Numbers (SSN)
- Medical Record Numbers (MRN)
- Dates of Birth
- Patient names
- Phone numbers, email addresses
- Physical addresses

**Example:**
```
Input:  "User viewed claim for patient John Doe, SSN 123-45-6789"
Output: "User viewed claim for patient [REDACTED_NAME], SSN [REDACTED_SSN]"
```

**Note:** Audit logs record *access* to PHI, not PHI itself.

### Access Controls

**Who can view logs:**

| Role | Permissions | Access |
|------|-------------|--------|
| **Developers** | `roles/logging.viewer` | Application logs only |
| **Security team** | `roles/logging.privateLogViewer` | All logs including audit |
| **Compliance auditors** | `roles/logging.privateLogViewer` | Read-only audit log access |
| **Service accounts** | `roles/logging.logWriter` | Write logs only |

**Configure IAM:**
```bash
# Grant log viewer access
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="user:developer@example.com" \
    --role="roles/logging.viewer"

# Grant audit log access
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="user:auditor@example.com" \
    --role="roles/logging.privateLogViewer"
```

### Business Associate Agreement (BAA)

**IMPORTANT:** Ensure your organization has signed a Business Associate Agreement (BAA) with Google Cloud.

- [ ] **Check BAA status:** [GCP Console > IAM & Admin > Legal](https://console.cloud.google.com/iam-admin/legal)
- [ ] **Request BAA:** Contact Google Cloud sales if not signed

**Without BAA, Cloud Logging cannot be used for PHI-related audit logs.**

### Compliance Audits

For HIPAA compliance audits, export audit logs:

```bash
# Export all audit logs for specific date range
gcloud logging read \
    "jsonPayload.logger=\"auditlog\"" \
    --format=json \
    --after="2024-01-01T00:00:00Z" \
    --before="2024-12-31T23:59:59Z" \
    > audit_logs_2024.json

# Convert to CSV for review
jq -r '.[] | [.timestamp, .jsonPayload.user_id, .jsonPayload.action, .jsonPayload.resource] | @csv' \
    audit_logs_2024.json > audit_logs_2024.csv
```

---

## Troubleshooting

### Logs Not Appearing in Cloud Logging

**Symptom:** Application is running but no logs visible in Cloud Console.

**Diagnostic steps:**

1. **Check log sinks are active:**
   ```bash
   gcloud logging sinks list
   ```

2. **Verify application is writing structured JSON logs:**
   ```bash
   # Check local container logs
   docker logs <container-id> | head -10
   ```

   Should see JSON format:
   ```json
   {"timestamp": "2024-01-15T10:30:00Z", "level": "INFO", "logger": "upstream.services", "message": "..."}
   ```

3. **Check log filters aren't excluding logs:**
   ```bash
   gcloud logging exclusions list
   ```

4. **Test with unfiltered query:**
   ```bash
   gcloud logging read "" --limit=10
   ```

**Common fixes:**

- **Structured logging not enabled:** Ensure `JSONLogFormatter` is used in production
- **Logger name mismatch:** Check logger names match filter patterns
- **Exclusion filter too broad:** Review and update exclusion filters
- **Wrong bucket selected:** Verify you're viewing correct log bucket in Console

### Retention Policy Not Taking Effect

**Symptom:** Logs older than retention period still visible.

**Explanation:** Retention policies apply to new logs. Existing logs are deleted after retention period expires.

**Timeline:**
- Day 0: Create bucket with 90-day retention
- Day 1: Logs written to bucket
- Day 91: Logs from Day 1 are deleted

**To delete old logs immediately:**

```bash
# Delete logs older than specific date
gcloud logging delete "timestamp<\"2024-01-01T00:00:00Z\"" --bucket=upstream-app-logs --location=global
```

**Warning:** This is irreversible. Ensure you don't delete logs within retention period.

### Cost Unexpectedly High

**Symptom:** Cloud Logging bill higher than expected.

**Diagnostic steps:**

1. **Check log volume:**
   ```bash
   # View usage in Cloud Console
   # https://console.cloud.google.com/logs/usage
   ```

2. **Identify high-volume loggers:**
   ```bash
   gcloud logging read "" --limit=1000 --format=json \
       | jq -r '.[] | .jsonPayload.logger' \
       | sort | uniq -c | sort -rn
   ```

3. **Check for log storms (repeated errors):**
   ```bash
   gcloud logging read "severity>=ERROR" --limit=100 \
       | grep -o "message.*" | sort | uniq -c | sort -rn
   ```

**Common causes:**

- **Debug logs in production:** Ensure DEBUG logs are excluded
- **Log storm:** Repeated error in tight loop generates millions of logs
- **Health check logs:** Load balancer health checks not excluded
- **Verbose third-party logs:** Libraries like urllib3, boto3 too verbose

**Fixes:**

- Add exclusions for high-volume low-value logs
- Fix log storms at source (catch exceptions, add rate limiting)
- Sample high-volume INFO logs

### How to Delete Old Logs Manually

**For compliance or cost reasons, delete logs before retention expires:**

```bash
# Delete application logs older than 60 days
gcloud logging delete \
    "timestamp<\"$(date -d '60 days ago' -u +%Y-%m-%dT%H:%M:%SZ)\"" \
    --bucket=upstream-app-logs \
    --location=global

# Delete audit logs older than 5 years (if policy changed)
gcloud logging delete \
    "timestamp<\"$(date -d '5 years ago' -u +%Y-%m-%dT%H:%M:%SZ)\"" \
    --bucket=upstream-audit-logs \
    --location=global
```

**CAUTION:** Ensure you're compliant with HIPAA requirements before deleting audit logs.

---

## Related Documentation

### Internal Documentation

- **[LOG_RETENTION.md](./LOG_RETENTION.md)** - Local file-based log retention policies
- **[GCP_DEPLOYMENT_GUIDE.md](../GCP_DEPLOYMENT_GUIDE.md)** - Complete GCP deployment guide
- **[upstream/logging_config.py](../upstream/logging_config.py)** - Centralized logging configuration
- **[upstream/logging_filters.py](../upstream/logging_filters.py)** - PHI scrubbing filters
- **[upstream/logging_utils.py](../upstream/logging_utils.py)** - Structured logging utilities

### Google Cloud Documentation

- **[Cloud Logging Overview](https://cloud.google.com/logging/docs/overview)** - Introduction to Cloud Logging
- **[Log Buckets](https://cloud.google.com/logging/docs/buckets)** - Managing log buckets and retention
- **[Log Sinks](https://cloud.google.com/logging/docs/export)** - Routing logs with sinks
- **[Query Language](https://cloud.google.com/logging/docs/view/logging-query-language)** - Advanced log filtering
- **[Pricing](https://cloud.google.com/stackdriver/pricing)** - Cloud Logging pricing details

### Compliance Resources

- **[HIPAA Security Rule](https://www.hhs.gov/hipaa/for-professionals/security/laws-regulations/index.html)** - HHS HIPAA regulations
- **[Google Cloud HIPAA Compliance](https://cloud.google.com/security/compliance/hipaa)** - GCP HIPAA compliance overview
- **[Business Associate Agreements](https://cloud.google.com/terms/hipaa-baa)** - GCP BAA information

---

**Document Version:** 1.0
**Last Updated:** 2026-01-26
**Maintainer:** DevOps Team
