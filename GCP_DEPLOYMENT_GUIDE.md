# Google Cloud Platform Deployment Guide

**Complete guide to deploying Payrixa on Google Cloud Platform**

## Overview

This guide walks you through deploying Payrixa to GCP using:

- **Cloud Run** - Containerized Django application
- **Cloud SQL** - PostgreSQL database (managed)
- **Memorystore** - Redis cache (managed)
- **Cloud Storage** - Static and media files
- **Secret Manager** - Secure credential storage
- **Cloud Build** - Automated CI/CD

**Estimated Setup Time:** 30-45 minutes (first time)
**Estimated Monthly Cost:** ~$50-100 (staging environment)

---

## Prerequisites

### 1. Google Cloud Account

- [ ] GCP account created: https://console.cloud.google.com
- [ ] Billing enabled
- [ ] New project created (or existing project selected)

### 2. Local Tools

```bash
# Install Google Cloud SDK
# macOS:
brew install google-cloud-sdk

# Linux:
curl https://sdk.cloud.google.com | bash

# Windows:
# Download from: https://cloud.google.com/sdk/docs/install

# Verify installation
gcloud --version
```

### 3. Docker

```bash
# Install Docker Desktop
# macOS/Windows: https://www.docker.com/products/docker-desktop
# Linux: https://docs.docker.com/engine/install/

# Verify installation
docker --version
```

### 4. Project Configuration

```bash
# Set your GCP project ID
export GCP_PROJECT_ID="your-project-id"

# Optional: Set region (default: us-central1)
export GCP_REGION="us-central1"

# Authenticate with GCP
gcloud auth login

# Set project
gcloud config set project $GCP_PROJECT_ID
```

---

## Quick Start (TL;DR)

```bash
# 1. Set project ID
export GCP_PROJECT_ID="your-project-id"

# 2. Setup infrastructure (one-time, ~15 minutes)
./deploy_gcp.sh setup

# 3. Deploy application (~5-10 minutes)
./deploy_gcp.sh deploy

# 4. Check status
./deploy_gcp.sh status

# 5. Run smoke tests
SERVICE_URL=$(gcloud run services describe payrixa-staging \
    --region=us-central1 \
    --format="get(status.url)")
python smoke_tests.py --url $SERVICE_URL --critical-only
```

---

## Detailed Setup Instructions

### Step 1: Infrastructure Setup (One-Time)

The `deploy_gcp.sh setup` command creates:

1. **Cloud SQL PostgreSQL Instance**
   - Database: `payrixa`
   - User: `payrixa`
   - Version: PostgreSQL 15
   - Tier: db-f1-micro (1 vCPU, 0.6GB RAM)
   - Region: us-central1
   - Private IP only (security)
   - Automated backups (3AM daily)

2. **Memorystore Redis Instance**
   - Name: `payrixa-redis`
   - Version: Redis 6.x
   - Tier: Basic (1GB)
   - Region: us-central1

3. **Cloud Storage Bucket**
   - Name: `{project-id}-payrixa-static`
   - Location: us-central1
   - Public read access (for static files)

4. **Secret Manager Secrets**
   - `django-secret-key` - Django SECRET_KEY
   - `database-url` - PostgreSQL connection string
   - `redis-url` - Redis connection string

**Run Setup:**

```bash
chmod +x deploy_gcp.sh
./deploy_gcp.sh setup
```

**Expected Output:**

```
[INFO] Checking prerequisites...
[SUCCESS] Prerequisites OK
[INFO] Setting up GCP infrastructure...
[INFO] Enabling GCP APIs...
[INFO] Creating Cloud SQL instance (this may take 10-15 minutes)...
[SUCCESS] Cloud SQL instance created
[INFO] Creating Memorystore Redis instance (this may take 5-10 minutes)...
[SUCCESS] Memorystore Redis created
[INFO] Creating Cloud Storage bucket...
[SUCCESS] Cloud Storage bucket created
[INFO] Creating secrets...
[SUCCESS] Infrastructure setup complete!

=========================================
GCP Infrastructure Summary
=========================================
Project ID: your-project-id
Region: us-central1
Cloud SQL: payrixa-db
Redis: payrixa-redis
Storage: gs://your-project-id-payrixa-static
=========================================
```

**IMPORTANT:** Save the database password shown during setup!

---

### Step 2: Deploy Application

The deployment process:

1. Builds Docker image
2. Pushes to Google Container Registry
3. Runs database migrations
4. Deploys to Cloud Run
5. Configures secrets and environment variables

**Run Deployment:**

```bash
./deploy_gcp.sh deploy
```

**What Happens:**

```
[INFO] Deploying application to Cloud Run...

Cloud Build Steps:
✓ Step 1/5: Build Docker image
✓ Step 2/5: Push to Container Registry
✓ Step 3/5: Push latest tag
✓ Step 4/5: Run database migrations
✓ Step 5/5: Deploy to Cloud Run

[SUCCESS] Deployment complete!

=========================================
Service URL: https://payrixa-staging-xxxxx-uc.a.run.app
=========================================

Next steps:
  1. Visit: https://payrixa-staging-xxxxx-uc.a.run.app/health/
  2. Run smoke tests: python smoke_tests.py --url https://...
  3. Check logs: ./deploy_gcp.sh logs
```

---

### Step 3: Verify Deployment

#### Check Service Status:

```bash
./deploy_gcp.sh status
```

**Output:**

```
URL                                              LATEST REVISION              READY
https://payrixa-staging-xxxxx-uc.a.run.app      payrixa-staging-00001-abc   True

Recent revisions:
NAME                        ACTIVE  SERVICE           DEPLOYED
payrixa-staging-00001-abc   yes     payrixa-staging   2026-01-24T08:30:00Z
```

#### Test Health Endpoint:

```bash
SERVICE_URL=$(gcloud run services describe payrixa-staging \
    --region=us-central1 \
    --format="get(status.url)")

curl $SERVICE_URL/health/
```

**Expected:**

```json
{
  "status": "healthy",
  "timestamp": 1706086800.123
}
```

#### Run Smoke Tests:

```bash
python smoke_tests.py --url $SERVICE_URL --critical-only
```

**Expected:**

```
🔥 SMOKE TESTS - https://payrixa-staging-xxxxx-uc.a.run.app
Started: 2026-01-24 08:30:00
======================================================================

[TEST] Health endpoint...
  ✅ PASS: Health endpoint OK

[TEST] Database connection...
  ✅ PASS: Database connected (postgresql)

[TEST] Redis cache connection...
  ✅ PASS: Redis cache operational

[TEST] Home page...
  ✅ PASS: Home page loads

[TEST] Login page...
  ✅ PASS: Login page loads with form

======================================================================
SMOKE TEST SUMMARY
======================================================================
Total Tests: 5
  ✅ Passed:   5
  ❌ Failed:   0
  ⚠️  Warnings: 0

🎉 All critical tests passed! Deployment looks good.
======================================================================
```

---

### Step 4: Manual Testing

#### Access the Application:

```bash
# Get service URL
echo $SERVICE_URL

# Visit in browser:
# https://payrixa-staging-xxxxx-uc.a.run.app
```

#### Create Superuser:

```bash
# Run Django command via Cloud Run
gcloud run services update payrixa-staging \
    --region=us-central1 \
    --execute-command=/bin/bash

# In the container shell:
python manage.py createsuperuser
```

**Or use Cloud SQL proxy:**

```bash
# Install Cloud SQL proxy
curl -o cloud_sql_proxy https://dl.google.com/cloudsql/cloud_sql_proxy.darwin.amd64
chmod +x cloud_sql_proxy

# Start proxy
./cloud_sql_proxy -instances=your-project-id:us-central1:payrixa-db=tcp:5432

# In another terminal, connect
psql "host=127.0.0.1 port=5432 dbname=payrixa user=payrixa"
```

#### Test DelayGuard:

```bash
# Run DelayGuard computation
gcloud run jobs create compute-delayguard \
    --image gcr.io/$GCP_PROJECT_ID/payrixa:latest \
    --region $GCP_REGION \
    --set-cloudsql-instances $GCP_PROJECT_ID:$GCP_REGION:payrixa-db \
    --set-secrets DATABASE_URL=database-url:latest \
    --execute-now \
    --args="python,manage.py,compute_delayguard,--all"
```

---

## Configuration

### Environment Variables

Cloud Run automatically injects these:

```bash
# Managed by Cloud Run
PORT=8080
K_SERVICE=payrixa-staging
K_REVISION=payrixa-staging-00001
K_CONFIGURATION=payrixa-staging

# Set in cloudbuild.yaml
DJANGO_SETTINGS_MODULE=payrixa.settings.prod

# From Secret Manager
SECRET_KEY=<from secret>
DATABASE_URL=<from secret>
REDIS_URL=<from secret>
```

### Update Secrets:

```bash
# Update Django secret key
echo -n "new-secret-key" | gcloud secrets versions add django-secret-key --data-file=-

# Update database URL
echo -n "postgresql://..." | gcloud secrets versions add database-url --data-file=-

# Update Redis URL
echo -n "redis://..." | gcloud secrets versions add redis-url --data-file=-
```

### Scale Configuration:

Edit `cloudbuild.yaml`:

```yaml
--memory: '2Gi'          # RAM per instance (512Mi, 1Gi, 2Gi, 4Gi, 8Gi)
--cpu: '2'               # vCPUs (1, 2, 4, 8)
--min-instances: '1'     # Always running (0 = scale to zero)
--max-instances: '10'    # Max autoscale
--timeout: '300'         # Request timeout (seconds)
```

---

## Monitoring & Logs

### View Application Logs:

```bash
# Real-time logs
./deploy_gcp.sh logs

# Or using gcloud directly
gcloud logging tail "resource.type=cloud_run_revision AND resource.labels.service_name=payrixa-staging"

# Last 100 logs
gcloud logging read \
    "resource.type=cloud_run_revision AND resource.labels.service_name=payrixa-staging" \
    --limit=100 \
    --format=json
```

### Cloud Console:

1. Visit: https://console.cloud.google.com/run
2. Click `payrixa-staging`
3. Click "LOGS" tab

### Metrics:

```bash
# Request count, latency, error rate
gcloud monitoring dashboards list

# Or visit Cloud Console:
# https://console.cloud.google.com/monitoring
```

### Alerts (Optional):

```bash
# Create alert for error rate
gcloud alpha monitoring policies create \
    --notification-channels=YOUR_CHANNEL \
    --display-name="Payrixa High Error Rate" \
    --condition-display-name="Error rate > 5%" \
    --condition-threshold-value=5 \
    --condition-threshold-duration=60s
```

---

## Troubleshooting

### Issue: Deployment Fails

**Check Cloud Build logs:**

```bash
gcloud builds list --limit=5

# Get build ID from output, then:
gcloud builds log BUILD_ID
```

**Common fixes:**

```bash
# Enable required APIs
gcloud services enable cloudbuild.googleapis.com run.googleapis.com

# Grant Cloud Build permissions
PROJECT_NUMBER=$(gcloud projects describe $GCP_PROJECT_ID --format="value(projectNumber)")
gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
    --member=serviceAccount:$PROJECT_NUMBER@cloudbuild.gserviceaccount.com \
    --role=roles/run.admin
```

### Issue: Database Connection Fails

**Check Cloud SQL status:**

```bash
gcloud sql instances describe payrixa-db
```

**Test connection:**

```bash
gcloud sql connect payrixa-db --user=payrixa
# Enter password when prompted
```

**Check database URL secret:**

```bash
gcloud secrets versions access latest --secret=database-url
```

### Issue: Redis Connection Fails

**Check Memorystore status:**

```bash
gcloud redis instances describe payrixa-redis --region=us-central1
```

**Get connection info:**

```bash
gcloud redis instances describe payrixa-redis \
    --region=us-central1 \
    --format="get(host,port)"
```

### Issue: Static Files Not Loading

**Upload static files to Cloud Storage:**

```bash
# Collect static files locally
python manage.py collectstatic --no-input

# Upload to GCS
gsutil -m rsync -r staticfiles/ gs://$GCP_PROJECT_ID-payrixa-static/static/

# Make public
gsutil -m acl ch -r -u AllUsers:R gs://$GCP_PROJECT_ID-payrixa-static/static/
```

**Update Django settings:**

```python
# payrixa/settings/prod.py
STATIC_URL = f'https://storage.googleapis.com/{PROJECT_ID}-payrixa-static/static/'
```

### Issue: Service Timeout

**Increase timeout in cloudbuild.yaml:**

```yaml
--timeout: '600'  # 10 minutes
```

**Check slow queries:**

```bash
# Enable Cloud SQL query insights
gcloud sql instances patch payrixa-db \
    --database-flags=cloudsql.enable_query_insights=on
```

---

## Rollback

### Automatic Rollback:

```bash
./deploy_gcp.sh rollback
```

### Manual Rollback:

```bash
# List revisions
gcloud run revisions list --service=payrixa-staging --region=us-central1

# Rollback to specific revision
gcloud run services update-traffic payrixa-staging \
    --region=us-central1 \
    --to-revisions=payrixa-staging-00001-abc=100
```

### Database Rollback:

```bash
# List backups
gcloud sql backups list --instance=payrixa-db

# Restore from backup
gcloud sql backups restore BACKUP_ID \
    --backup-instance=payrixa-db \
    --backup-instance=payrixa-db
```

---

## Cost Optimization

### Estimated Monthly Costs (Staging):

| Service | Configuration | Cost/Month |
|---------|--------------|------------|
| Cloud Run | 2 vCPU, 2GB RAM, 1 min instance | ~$30 |
| Cloud SQL | db-f1-micro | ~$15 |
| Memorystore | Basic 1GB | ~$30 |
| Cloud Storage | 10GB | ~$0.20 |
| **Total** | | **~$75** |

### Cost Savings:

```bash
# Scale to zero when not in use
# Edit cloudbuild.yaml:
--min-instances: '0'  # Scale to zero

# Use smaller database tier
gcloud sql instances patch payrixa-db \
    --tier=db-g1-small

# Use smaller Redis
gcloud redis instances update payrixa-redis \
    --size=1 \
    --region=us-central1
```

### Production Cost (Estimated):

| Service | Configuration | Cost/Month |
|---------|--------------|------------|
| Cloud Run | 4 vCPU, 8GB RAM, 2 min instances | ~$200 |
| Cloud SQL | db-n1-standard-2 | ~$100 |
| Memorystore | Standard 5GB | ~$200 |
| Cloud Storage | 100GB | ~$2 |
| **Total** | | **~$500** |

---

## Production Deployment

### Production Checklist:

- [ ] Separate GCP project for production
- [ ] Larger Cloud SQL instance (db-n1-standard-2)
- [ ] Redis Standard tier (high availability)
- [ ] Cloud CDN for static files
- [ ] Cloud Armor for DDoS protection
- [ ] Uptime monitoring configured
- [ ] Error alerting configured
- [ ] Database backups automated
- [ ] Disaster recovery plan documented

### Deploy to Production:

```bash
# Set production project
export GCP_PROJECT_ID="payrixa-production"

# Setup infrastructure
./deploy_gcp.sh setup

# Deploy
./deploy_gcp.sh deploy

# Verify
./deploy_gcp.sh status
python smoke_tests.py --url $SERVICE_URL
```

---

## Continuous Deployment

### Setup Cloud Build Trigger:

```bash
# Create trigger that deploys on push to main
gcloud builds triggers create github \
    --repo-name=Payrixa \
    --repo-owner=byteworthy \
    --branch-pattern=^main$ \
    --build-config=cloudbuild.yaml \
    --substitutions=_REGION=us-central1
```

Now every push to `main` branch automatically deploys to Cloud Run!

---

## Next Steps

1. ✅ Infrastructure setup complete
2. ✅ Application deployed
3. ✅ Smoke tests passed
4. ⏭️ Configure custom domain
5. ⏭️ Set up monitoring alerts
6. ⏭️ Configure Cloud CDN
7. ⏭️ Plan production deployment

---

## Support & Resources

**GCP Documentation:**
- Cloud Run: https://cloud.google.com/run/docs
- Cloud SQL: https://cloud.google.com/sql/docs
- Memorystore: https://cloud.google.com/memorystore/docs

**Payrixa Documentation:**
- Deployment Runbook: `DEPLOYMENT_RUNBOOK.md`
- Code Review: `CODE_REVIEW_REPORT.md`
- Phase 2 Report: `PHASE_2_COMPLETION_REPORT.md`

**Troubleshooting:**
- GCP Status: https://status.cloud.google.com
- Community: https://stackoverflow.com/questions/tagged/google-cloud-platform

---

**End of GCP Deployment Guide**
