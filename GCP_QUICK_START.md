# GCP Quick Start - Payrixa Deployment

**⚡ Get Payrixa running on Google Cloud in 20 minutes**

## Prerequisites (5 minutes)

```bash
# 1. Install Google Cloud SDK
brew install google-cloud-sdk    # macOS
# OR download: https://cloud.google.com/sdk/docs/install

# 2. Login to GCP
gcloud auth login

# 3. Set your project ID
export GCP_PROJECT_ID="your-project-id"
gcloud config set project $GCP_PROJECT_ID
```

---

## Deploy to GCP (15 minutes)

### Step 1: Setup Infrastructure (One-Time, ~10 minutes)

```bash
./deploy_gcp.sh setup
```

**This creates:**
- ✅ Cloud SQL PostgreSQL database
- ✅ Memorystore Redis cache
- ✅ Cloud Storage bucket
- ✅ Secret Manager secrets

**⚠️ SAVE THE DATABASE PASSWORD shown during setup!**

---

### Step 2: Deploy Application (~5 minutes)

```bash
./deploy_gcp.sh deploy
```

**This does:**
- ✅ Builds Docker image
- ✅ Runs database migrations
- ✅ Deploys to Cloud Run
- ✅ Configures environment

---

### Step 3: Verify Deployment (1 minute)

```bash
# Check status
./deploy_gcp.sh status

# Get service URL
SERVICE_URL=$(gcloud run services describe payrixa-staging \
    --region=us-central1 \
    --format="get(status.url)")

echo "Service URL: $SERVICE_URL"

# Test health endpoint
curl $SERVICE_URL/health/

# Run smoke tests
python smoke_tests.py --url $SERVICE_URL --critical-only
```

---

## Common Commands

```bash
# View logs
./deploy_gcp.sh logs

# Rollback deployment
./deploy_gcp.sh rollback

# Update application (after code changes)
git push origin main
./deploy_gcp.sh deploy

# SSH into database
gcloud sql connect payrixa-db --user=payrixa
```

---

## Costs

**Staging Environment:** ~$75/month
- Cloud Run: ~$30
- Cloud SQL: ~$15
- Redis: ~$30

**Production Environment:** ~$500/month

---

## Troubleshooting

### Deployment fails?
```bash
gcloud builds list
gcloud builds log <BUILD_ID>
```

### Can't connect to database?
```bash
gcloud sql instances describe payrixa-db
gcloud sql connect payrixa-db --user=payrixa
```

### Service not responding?
```bash
./deploy_gcp.sh logs
gcloud run services describe payrixa-staging --region=us-central1
```

---

## Next Steps

1. ✅ Configure custom domain
2. ✅ Set up monitoring alerts
3. ✅ Create production environment
4. ✅ Configure CI/CD pipeline

**Full Documentation:** See `GCP_DEPLOYMENT_GUIDE.md`

---

**Need Help?**
- GCP Console: https://console.cloud.google.com
- Cloud Run Docs: https://cloud.google.com/run/docs
- Support: https://cloud.google.com/support
