#!/bin/bash
#
# Upstream Model Amplification - Automated Setup Script
#
# This script automates the setup of data quality, validation,
# DriftWatch, and DenialScope amplified features.
#
# Usage:
#   bash setup_amplification.sh
#

set -e  # Exit on error

echo "=========================================="
echo "Upstream Model Amplification Setup"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in the right directory
if [ ! -f "manage.py" ]; then
    print_error "manage.py not found. Please run this script from the project root directory."
    exit 1
fi

# Step 1: Install dependencies
echo ""
print_status "Step 1: Installing Python dependencies..."
pip install scipy scikit-learn numpy --quiet

if [ $? -eq 0 ]; then
    print_success "Dependencies installed successfully"
else
    print_error "Failed to install dependencies"
    exit 1
fi

# Step 2: Check for existing migrations
echo ""
print_status "Step 2: Checking for pending migrations..."

if python manage.py showmigrations upstream | grep -q "\[ \]"; then
    print_warning "Pending migrations found"
fi

# Step 3: Create migrations
echo ""
print_status "Step 3: Creating new migrations..."
python manage.py makemigrations --noinput

if [ $? -eq 0 ]; then
    print_success "Migrations created successfully"
else
    print_error "Failed to create migrations"
    exit 1
fi

# Step 4: Run migrations
echo ""
print_status "Step 4: Running migrations..."
python manage.py migrate --noinput

if [ $? -eq 0 ]; then
    print_success "Migrations applied successfully"
else
    print_error "Failed to apply migrations"
    exit 1
fi

# Step 5: Initialize data quality
echo ""
print_status "Step 5: Initializing data quality for customers..."

# Check if customers exist
CUSTOMER_COUNT=$(python manage.py shell -c "from upstream.models import Customer; print(Customer.objects.count())")

if [ "$CUSTOMER_COUNT" -gt 0 ]; then
    print_status "Found $CUSTOMER_COUNT customers"
    python manage.py init_data_quality --all

    if [ $? -eq 0 ]; then
        print_success "Data quality initialized for all customers"
    else
        print_warning "Data quality initialization completed with warnings"
    fi
else
    print_warning "No customers found. Run 'python manage.py init_data_quality --customer <name>' after creating customers."
fi

# Step 6: Collect static files (if needed)
echo ""
print_status "Step 6: Collecting static files..."
python manage.py collectstatic --noinput --clear 2>/dev/null || print_warning "Static files collection skipped (may not be needed in development)"

# Step 7: Verify installation
echo ""
print_status "Step 7: Verifying installation..."

# Check if models are accessible
python manage.py shell -c "
from upstream.core.validation_models import ValidationRule, DataQualityMetric
from upstream.products.denialscope.advanced_models import DenialCluster
print('✓ All models accessible')
" 2>/dev/null

if [ $? -eq 0 ]; then
    print_success "Model verification passed"
else
    print_error "Model verification failed"
    exit 1
fi

# Summary
echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
print_success "Upstream Model Amplification is ready to use!"
echo ""
echo "Next steps:"
echo "  1. Add URL patterns to hello_world/urls.py:"
echo "     path('', include('upstream.urls_data_quality')),"
echo ""
echo "  2. Start development server:"
echo "     python manage.py runserver"
echo ""
echo "  3. Access dashboards:"
echo "     - Quality Dashboard: http://localhost:8000/quality/"
echo "     - Validation Rules:  http://localhost:8000/quality/rules/"
echo "     - Quality Trends:    http://localhost:8000/quality/trends/"
echo "     - Anomaly Dashboard: http://localhost:8000/quality/anomalies/"
echo ""
echo "Documentation:"
echo "  - Setup Guide:     DATA_QUALITY_SETUP_GUIDE.md"
echo "  - Technical Docs:  MODEL_AMPLIFICATION_SUMMARY.md"
echo "  - Code Examples:   INTEGRATION_EXAMPLES.py"
echo "  - Quick Reference: AMPLIFICATION_README.md"
echo ""
print_success "Happy amplifying! 🚀"
echo ""
