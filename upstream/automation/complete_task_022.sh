#!/bin/bash
# Completion script for quick task 022
# This script creates migrations, applies them, and runs verification

set -e  # Exit on error

echo "=========================================="
echo "Quick Task 022: Complete Week 1 Tasks 2-7"
echo "=========================================="
echo ""

# Record start time
START_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "Start time: $START_TIME"
echo ""

# Step 1: Create migrations
echo "Step 1: Creating migrations..."
echo "-------------------------------"

echo "Creating ExecutionLog migration..."
python manage.py makemigrations upstream -n add_execution_log --no-input

echo "Creating Authorization migration..."
python manage.py makemigrations upstream -n add_authorization --no-input

echo "Creating submitted_via field migration..."
python manage.py makemigrations upstream -n add_claim_submitted_via --no-input

echo ""
echo "Migrations created successfully!"
echo ""

# Step 2: Show migration plan
echo "Step 2: Reviewing migration plan..."
echo "-----------------------------------"
python manage.py migrate --plan

echo ""

# Step 3: Apply migrations
echo "Step 3: Applying migrations..."
echo "------------------------------"
python manage.py migrate

echo ""
echo "Migrations applied successfully!"
echo ""

# Step 4: Verify models can be imported
echo "Step 4: Verifying model imports..."
echo "----------------------------------"

python manage.py shell -c "from upstream.models import AutomationRule, ExecutionLog, Authorization, ClaimRecord; print('✓ All models imported successfully')"

python manage.py shell -c "from upstream.models import ClaimRecord; field = ClaimRecord._meta.get_field('submitted_via'); print(f'✓ ClaimRecord.submitted_via field: {field}')"

echo ""

# Step 5: Verify rules engine imports
echo "Step 5: Verifying rules engine imports..."
echo "-----------------------------------------"

python -c "from upstream.automation.rules_engine import RulesEngine, Event, Action, ExecutionResult; print('✓ Rules engine imports successful')"

echo ""

# Step 6: Verify webhook endpoint
echo "Step 6: Verifying webhook endpoint..."
echo "-------------------------------------"

grep -q "def ehr_webhook" upstream/views/webhooks.py && echo "✓ EHR webhook endpoint exists"
grep -q "@csrf_exempt" upstream/views/webhooks.py && echo "✓ CSRF exemption present"
grep -q "process_claim_with_automation.delay" upstream/views/webhooks.py && echo "✓ Async task invocation present"

echo ""

# Step 7: Verify Celery task
echo "Step 7: Verifying Celery task..."
echo "--------------------------------"

python manage.py shell -c "from upstream.tasks import process_claim_with_automation; print(f'✓ Task registered: {process_claim_with_automation.name}')"

echo ""

# Step 8: Check database tables exist
echo "Step 8: Verifying database tables..."
echo "------------------------------------"

python manage.py dbshell <<SQL
SELECT 'upstream_automation_rule' as table_name, COUNT(*) as rows FROM upstream_automation_rule
UNION ALL
SELECT 'upstream_execution_log', COUNT(*) FROM upstream_execution_log
UNION ALL
SELECT 'upstream_authorization', COUNT(*) FROM upstream_authorization;
SQL

echo ""
echo "✓ All database tables verified!"
echo ""

# Step 9: Show completion summary
END_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "=========================================="
echo "Task 022 Completion Summary"
echo "=========================================="
echo ""
echo "Start time: $START_TIME"
echo "End time:   $END_TIME"
echo ""
echo "Deliverables:"
echo "  ✓ ExecutionLog model and migration"
echo "  ✓ Authorization model and migration"
echo "  ✓ ClaimRecord.submitted_via field and migration"
echo "  ✓ EHR webhook endpoint (upstream/views/webhooks.py)"
echo "  ✓ Rules engine framework (upstream/automation/rules_engine.py)"
echo "  ✓ Celery task process_claim_with_automation"
echo ""
echo "Next steps:"
echo "  1. Wire URL route for /webhooks/ehr endpoint"
echo "  2. Implement API key authentication for webhooks"
echo "  3. Add FHIR parsing library (fhir.resources)"
echo "  4. Implement actual risk scoring (Week 2)"
echo "  5. Implement payer portal automation (Week 2-4)"
echo ""
echo "=========================================="
echo "Task 022 Complete!"
echo "=========================================="
