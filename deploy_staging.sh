#!/bin/bash
#
# Staging Deployment Script for Upstream
#
# This script deploys Phase 2 + DelayGuard to staging environment
# with comprehensive safety checks and rollback capability.
#
# Usage:
#   ./deploy_staging.sh
#   ./deploy_staging.sh --dry-run
#   ./deploy_staging.sh --rollback
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT="staging"
APP_NAME="upstream"
BACKUP_DIR="./backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Parse arguments
DRY_RUN=false
ROLLBACK=false

for arg in "$@"; do
    case $arg in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --rollback)
            ROLLBACK=true
            shift
            ;;
        *)
            ;;
    esac
done

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check if git is available
    if ! command -v git &> /dev/null; then
        log_error "git is not installed"
        exit 1
    fi

    # Check if Python is available
    if ! command -v python &> /dev/null; then
        log_error "python is not installed"
        exit 1
    fi

    # Check if we're on the correct branch
    CURRENT_BRANCH=$(git branch --show-current)
    if [ "$CURRENT_BRANCH" != "main" ]; then
        log_warning "Not on main branch (currently on $CURRENT_BRANCH)"
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi

    # Check for uncommitted changes
    if ! git diff-index --quiet HEAD --; then
        log_error "Uncommitted changes detected. Commit or stash them first."
        git status --short
        exit 1
    fi

    log_success "Prerequisites check passed"
}

backup_database() {
    log_info "Creating database backup..."

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would create database backup"
        return
    fi

    mkdir -p "$BACKUP_DIR"

    # PostgreSQL backup (adjust credentials as needed)
    if command -v pg_dump &> /dev/null; then
        BACKUP_FILE="$BACKUP_DIR/db_backup_${TIMESTAMP}.sql"
        log_info "Backing up database to $BACKUP_FILE"

        # Uncomment and configure for your environment:
        # pg_dump -U $DB_USER -h $DB_HOST $DB_NAME > "$BACKUP_FILE"

        log_warning "Database backup command needs configuration"
    else
        log_warning "pg_dump not found, skipping database backup"
    fi
}

pull_latest_code() {
    log_info "Pulling latest code from remote..."

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would pull from origin/main"
        return
    fi

    git fetch origin
    git pull origin main

    log_success "Code updated to latest version"
}

install_dependencies() {
    log_info "Installing Python dependencies..."

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would run pip install -r requirements.txt"
        return
    fi

    pip install -r requirements.txt --quiet

    log_success "Dependencies installed"
}

run_migrations() {
    log_info "Running database migrations..."

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would run migrations"
        python manage.py showmigrations --list
        return
    fi

    # Show pending migrations
    log_info "Pending migrations:"
    python manage.py showmigrations --plan | grep '\[ \]' || log_info "None"

    # Apply migrations
    python manage.py migrate --no-input

    log_success "Migrations applied"
}

collect_static_files() {
    log_info "Collecting static files..."

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would collect static files"
        return
    fi

    python manage.py collectstatic --no-input --clear

    log_success "Static files collected"
}

run_deployment_checks() {
    log_info "Running deployment checks..."

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would run deployment checks"
        return
    fi

    # Django system checks
    python manage.py check --deploy

    # Custom security checks
    log_info "Verifying security settings..."
    python -c "
from django.conf import settings
import sys

# Check critical security settings
checks = {
    'DEBUG': settings.DEBUG == False,
    'SECRET_KEY': len(getattr(settings, 'SECRET_KEY', '')) > 20,
    'ALLOWED_HOSTS': len(settings.ALLOWED_HOSTS) > 0,
    'SESSION_COOKIE_HTTPONLY': getattr(settings, 'SESSION_COOKIE_HTTPONLY', False),
    'CSRF_COOKIE_HTTPONLY': getattr(settings, 'CSRF_COOKIE_HTTPONLY', False),
}

all_passed = all(checks.values())
for check, passed in checks.items():
    status = '✓' if passed else '✗'
    print(f'  {status} {check}: {passed}')

sys.exit(0 if all_passed else 1)
"

    log_success "Deployment checks passed"
}

restart_services() {
    log_info "Restarting application services..."

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY_RUN] Would restart services"
        return
    fi

    # Adjust based on your deployment setup:
    # - systemctl restart gunicorn
    # - supervisorctl restart upstream
    # - docker-compose restart web
    # - kubectl rollout restart deployment/upstream

    log_warning "Service restart command needs configuration"
}

run_smoke_tests() {
    log_info "Running smoke tests..."

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY_RUN] Would run smoke tests"
        return
    fi

    # Run smoke tests
    python smoke_tests.py --env staging --critical-only

    if [ $? -eq 0 ]; then
        log_success "Smoke tests passed"
    else
        log_error "Smoke tests failed!"
        exit 1
    fi
}

perform_rollback() {
    log_error "Rolling back deployment..."

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY_RUN] Would rollback deployment"
        return
    fi

    # Get previous commit
    PREVIOUS_COMMIT=$(git rev-parse HEAD^)
    log_info "Rolling back to commit: $PREVIOUS_COMMIT"

    git reset --hard "$PREVIOUS_COMMIT"
    python manage.py migrate
    restart_services

    log_success "Rollback complete"
}

# Main deployment flow
main() {
    echo "========================================="
    echo "   Upstream Staging Deployment"
    echo "========================================="
    echo ""

    if [ "$DRY_RUN" = true ]; then
        log_warning "DRY RUN MODE - No changes will be made"
        echo ""
    fi

    if [ "$ROLLBACK" = true ]; then
        perform_rollback
        exit 0
    fi

    # Pre-deployment checks
    check_prerequisites

    # Deployment steps
    backup_database
    pull_latest_code
    install_dependencies
    run_migrations
    collect_static_files
    run_deployment_checks
    restart_services
    run_smoke_tests

    echo ""
    echo "========================================="
    log_success "Deployment complete!"
    echo "========================================="
    echo ""
    echo "Deployed at: $(date)"
    echo "Commit: $(git rev-parse --short HEAD)"
    echo "Branch: $(git branch --show-current)"
    echo ""
    echo "Next steps:"
    echo "  1. Monitor application logs"
    echo "  2. Test critical user flows"
    echo "  3. Notify stakeholders"
    echo ""
}

# Handle errors
trap 'log_error "Deployment failed at line $LINENO"; exit 1' ERR

# Run main
main
