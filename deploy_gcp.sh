#!/bin/bash
#
# Google Cloud Platform Deployment Script for Upstream
#
# This script sets up and deploys Upstream to GCP using:
# - Cloud Run (Django application)
# - Cloud SQL (PostgreSQL database)
# - Memorystore (Redis cache)
# - Cloud Storage (static/media files)
# - Secret Manager (credentials)
#
# Usage:
#   ./deploy_gcp.sh setup      # One-time infrastructure setup
#   ./deploy_gcp.sh deploy     # Deploy application
#   ./deploy_gcp.sh status     # Check deployment status
#   ./deploy_gcp.sh logs       # View application logs
#   ./deploy_gcp.sh rollback   # Rollback to previous version
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="upstream-staging"
DB_INSTANCE_NAME="upstream-db"
REDIS_INSTANCE_NAME="upstream-redis"
BUCKET_NAME="${PROJECT_ID}-upstream-static"

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check gcloud CLI
    if ! command -v gcloud &> /dev/null; then
        log_error "gcloud CLI not installed. Install from: https://cloud.google.com/sdk/docs/install"
        exit 1
    fi

    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker not installed. Install from: https://docs.docker.com/get-docker/"
        exit 1
    fi

    # Check PROJECT_ID
    if [ -z "$PROJECT_ID" ]; then
        log_error "GCP_PROJECT_ID not set. Export it: export GCP_PROJECT_ID=your-project-id"
        exit 1
    fi

    # Authenticate
    log_info "Current GCP project: $(gcloud config get-value project)"

    log_success "Prerequisites OK"
}

setup_infrastructure() {
    log_info "Setting up GCP infrastructure..."

    # Set project
    gcloud config set project "$PROJECT_ID"

    # Enable required APIs
    log_info "Enabling GCP APIs..."
    gcloud services enable \
        run.googleapis.com \
        sql-component.googleapis.com \
        sqladmin.googleapis.com \
        redis.googleapis.com \
        secretmanager.googleapis.com \
        cloudbuild.googleapis.com \
        artifactregistry.googleapis.com \
        storage.googleapis.com

    # Create Cloud SQL PostgreSQL instance
    log_info "Creating Cloud SQL instance (this may take 10-15 minutes)..."
    if ! gcloud sql instances describe "$DB_INSTANCE_NAME" &> /dev/null; then
        gcloud sql instances create "$DB_INSTANCE_NAME" \
            --database-version=POSTGRES_15 \
            --tier=db-f1-micro \
            --region="$REGION" \
            --network=default \
            --no-assign-ip \
            --backup-start-time=03:00

        # Create database
        gcloud sql databases create upstream \
            --instance="$DB_INSTANCE_NAME"

        # Create database user
        DB_PASSWORD=$(openssl rand -base64 32)
        gcloud sql users create upstream \
            --instance="$DB_INSTANCE_NAME" \
            --password="$DB_PASSWORD"

        log_success "Cloud SQL instance created"
        log_warning "Database password: $DB_PASSWORD (save this!)"
    else
        log_info "Cloud SQL instance already exists"
    fi

    # Create Memorystore Redis instance
    log_info "Creating Memorystore Redis instance (this may take 5-10 minutes)..."
    if ! gcloud redis instances describe "$REDIS_INSTANCE_NAME" --region="$REGION" &> /dev/null; then
        gcloud redis instances create "$REDIS_INSTANCE_NAME" \
            --region="$REGION" \
            --tier=basic \
            --size=1 \
            --redis-version=redis_6_x

        log_success "Memorystore Redis created"
    else
        log_info "Memorystore Redis already exists"
    fi

    # Get Redis connection info
    REDIS_HOST=$(gcloud redis instances describe "$REDIS_INSTANCE_NAME" \
        --region="$REGION" \
        --format="get(host)")
    REDIS_PORT=$(gcloud redis instances describe "$REDIS_INSTANCE_NAME" \
        --region="$REGION" \
        --format="get(port)")

    # Create Cloud Storage bucket for static files
    log_info "Creating Cloud Storage bucket..."
    if ! gsutil ls -b "gs://$BUCKET_NAME" &> /dev/null; then
        gsutil mb -l "$REGION" "gs://$BUCKET_NAME"
        gsutil iam ch allUsers:objectViewer "gs://$BUCKET_NAME"
        log_success "Cloud Storage bucket created"
    else
        log_info "Cloud Storage bucket already exists"
    fi

    # Create secrets in Secret Manager
    log_info "Creating secrets..."

    # Django secret key
    if ! gcloud secrets describe django-secret-key &> /dev/null; then
        echo -n "$(openssl rand -base64 64)" | \
            gcloud secrets create django-secret-key \
                --data-file=- \
                --replication-policy="automatic"
    fi

    # Database URL
    CLOUDSQL_CONNECTION_NAME="${PROJECT_ID}:${REGION}:${DB_INSTANCE_NAME}"
    DATABASE_URL="postgresql://upstream:${DB_PASSWORD:-CHANGEME}@/upstream?host=/cloudsql/${CLOUDSQL_CONNECTION_NAME}"

    if ! gcloud secrets describe database-url &> /dev/null; then
        echo -n "$DATABASE_URL" | \
            gcloud secrets create database-url \
                --data-file=- \
                --replication-policy="automatic"
    fi

    # Redis URL
    REDIS_URL="redis://${REDIS_HOST}:${REDIS_PORT}/0"
    if ! gcloud secrets describe redis-url &> /dev/null; then
        echo -n "$REDIS_URL" | \
            gcloud secrets create redis-url \
                --data-file=- \
                --replication-policy="automatic"
    fi

    log_success "Infrastructure setup complete!"
    echo ""
    echo "========================================="
    echo "GCP Infrastructure Summary"
    echo "========================================="
    echo "Project ID: $PROJECT_ID"
    echo "Region: $REGION"
    echo "Cloud SQL: $DB_INSTANCE_NAME"
    echo "Redis: $REDIS_INSTANCE_NAME"
    echo "Storage: gs://$BUCKET_NAME"
    echo "========================================="
}

deploy_application() {
    log_info "Deploying application to Cloud Run..."

    # Build and deploy using Cloud Build
    gcloud builds submit \
        --config cloudbuild.yaml \
        --substitutions=_REGION="$REGION"

    # Get service URL
    SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
        --region="$REGION" \
        --format="get(status.url)")

    log_success "Deployment complete!"
    echo ""
    echo "========================================="
    echo "Service URL: $SERVICE_URL"
    echo "========================================="
    echo ""
    echo "Next steps:"
    echo "  1. Visit: $SERVICE_URL/health/"
    echo "  2. Run smoke tests: python smoke_tests.py --url $SERVICE_URL"
    echo "  3. Check logs: ./deploy_gcp.sh logs"
}

show_status() {
    log_info "Checking deployment status..."

    # Cloud Run service
    gcloud run services describe "$SERVICE_NAME" \
        --region="$REGION" \
        --format="table(status.url,status.latestReadyRevisionName,status.conditions[0].status)"

    # Recent deployments
    log_info "Recent revisions:"
    gcloud run revisions list \
        --service="$SERVICE_NAME" \
        --region="$REGION" \
        --limit=5
}

show_logs() {
    log_info "Fetching application logs..."

    gcloud logging read \
        "resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME" \
        --limit=50 \
        --format=json \
        | jq -r '.[] | "\(.timestamp) [\(.severity)] \(.textPayload // .jsonPayload.message)"'
}

rollback_deployment() {
    log_warning "Rolling back to previous version..."

    # Get previous revision
    PREVIOUS_REVISION=$(gcloud run revisions list \
        --service="$SERVICE_NAME" \
        --region="$REGION" \
        --limit=2 \
        --format="get(metadata.name)" \
        | tail -n 1)

    if [ -z "$PREVIOUS_REVISION" ]; then
        log_error "No previous revision found"
        exit 1
    fi

    log_info "Rolling back to: $PREVIOUS_REVISION"

    # Update traffic to previous revision
    gcloud run services update-traffic "$SERVICE_NAME" \
        --region="$REGION" \
        --to-revisions="$PREVIOUS_REVISION=100"

    log_success "Rollback complete"
}

# Main
case "${1:-}" in
    setup)
        check_prerequisites
        setup_infrastructure
        ;;
    deploy)
        check_prerequisites
        deploy_application
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    rollback)
        rollback_deployment
        ;;
    *)
        echo "Usage: $0 {setup|deploy|status|logs|rollback}"
        echo ""
        echo "Commands:"
        echo "  setup     - One-time infrastructure setup (Cloud SQL, Redis, etc.)"
        echo "  deploy    - Build and deploy application to Cloud Run"
        echo "  status    - Check deployment status"
        echo "  logs      - View application logs"
        echo "  rollback  - Rollback to previous version"
        echo ""
        echo "Environment variables:"
        echo "  GCP_PROJECT_ID - Your GCP project ID (required)"
        echo "  GCP_REGION     - GCP region (default: us-central1)"
        exit 1
        ;;
esac
