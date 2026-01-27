# Task 022 Completion Instructions

## Current Status

All code has been written and is ready for migration creation and testing.

### Files Created/Modified:

**Models (upstream/models.py):**
- ✅ ExecutionLog model added (lines 1109-1166)
- ✅ Authorization model added (lines 1168-1263)
- ✅ ClaimRecord.submitted_via field added (lines 442-451)
- ✅ Composite index for analytics added (lines 574-578)

**Webhook (upstream/views/webhooks.py):**
- ✅ ehr_webhook() endpoint created (98 lines)

**Rules Engine (upstream/automation/):**
- ✅ __init__.py package created
- ✅ rules_engine.py with RulesEngine, Event, Action, ExecutionResult (262 lines)

**Celery Task (upstream/tasks.py):**
- ✅ process_claim_with_automation task added (81 lines)

**Scripts:**
- ✅ complete_task_022.sh created for automated migration and verification

**Documentation:**
- ✅ 022-SUMMARY.md created with comprehensive documentation

## Next Steps to Complete

### 1. Create Migrations

Run the following commands to create the three required migrations:

```bash
cd /workspaces/codespaces-django

# Create ExecutionLog migration
python manage.py makemigrations upstream -n add_execution_log --no-input

# Create Authorization migration
python manage.py makemigrations upstream -n add_authorization --no-input

# Create submitted_via field migration
python manage.py makemigrations upstream -n add_claim_submitted_via --no-input
```

**Expected Output:**
- Creates `upstream/migrations/0023_add_execution_log.py`
- Creates `upstream/migrations/0024_add_authorization.py`
- Creates `upstream/migrations/0025_add_claim_submitted_via.py`

### 2. Review Migration Plan

```bash
python manage.py migrate --plan
```

This shows what will be applied without actually applying it.

### 3. Apply Migrations

```bash
python manage.py migrate
```

**Expected Output:**
```
Running migrations:
  Applying upstream.0023_add_execution_log... OK
  Applying upstream.0024_add_authorization... OK
  Applying upstream.0025_add_claim_submitted_via... OK
```

### 4. Verify Models

```bash
# Test model imports
python manage.py shell -c "
from upstream.models import AutomationRule, ExecutionLog, Authorization, ClaimRecord
print('✓ All models imported successfully')
print('ExecutionLog:', ExecutionLog._meta.db_table)
print('Authorization:', Authorization._meta.db_table)
"

# Test submitted_via field
python manage.py shell -c "
from upstream.models import ClaimRecord
field = ClaimRecord._meta.get_field('submitted_via')
print('✓ ClaimRecord.submitted_via field exists')
print('Choices:', field.choices)
print('Default:', field.default)
"
```

### 5. Verify Rules Engine

```bash
# Test rules engine imports
python -c "
from upstream.automation.rules_engine import RulesEngine, Event, Action, ExecutionResult
print('✓ Rules engine imports successful')
"

# Test instantiation
python manage.py shell -c "
from upstream.models import Customer
from upstream.automation.rules_engine import RulesEngine
customer = Customer.objects.first()
engine = RulesEngine(customer)
print('✓ RulesEngine instantiated successfully')
"
```

### 6. Verify Webhook

```bash
# Check webhook endpoint exists
grep -c "def ehr_webhook" upstream/views/webhooks.py
# Should output: 1

# Check CSRF exemption
grep -c "@csrf_exempt" upstream/views/webhooks.py
# Should output: 1

# Check async task call
grep -c "process_claim_with_automation.delay" upstream/views/webhooks.py
# Should output: 1
```

### 7. Verify Celery Task

```bash
python manage.py shell -c "
from upstream.tasks import process_claim_with_automation
print('✓ Task registered:', process_claim_with_automation.name)
print('Expected: upstream.tasks.process_claim_with_automation')
"
```

### 8. Check Database Tables

```bash
# Using Django ORM
python manage.py shell -c "
from django.db import connection
cursor = connection.cursor()

# Check tables exist
tables = [
    'upstream_execution_log',
    'upstream_authorization'
]

for table in tables:
    cursor.execute(f'SELECT COUNT(*) FROM {table}')
    count = cursor.fetchone()[0]
    print(f'✓ {table}: {count} rows')
"
```

### 9. Run Tests (if any exist)

```bash
# Run upstream app tests
python manage.py test upstream --settings=upstream.settings.test

# Run specific test modules if they exist
python manage.py test upstream.tests.test_automation --settings=upstream.settings.test
```

### 10. Add URL Route for Webhook

Create or update `upstream/urls.py` to add the webhook endpoint:

```python
from django.urls import path
from upstream.views.webhooks import ehr_webhook

urlpatterns = [
    # ... existing routes ...
    path('webhooks/ehr', ehr_webhook, name='ehr_webhook'),
]
```

Or if there's a main `urls.py`, include it there:

```python
from django.urls import path, include
from upstream.views.webhooks import ehr_webhook

urlpatterns = [
    # ... existing routes ...
    path('api/webhooks/ehr', ehr_webhook, name='ehr_webhook'),
]
```

### 11. Test Webhook Endpoint (Optional - if server is running)

```bash
# Start development server in one terminal
python manage.py runserver

# In another terminal, test the webhook
curl -X POST http://localhost:8000/webhooks/ehr \
  -H "Content-Type: application/json" \
  -d '{
    "resourceType": "Claim",
    "patient": {"reference": "Patient/123"},
    "insurance": [{"coverage": {"display": "Blue Cross"}}],
    "item": [{"productOrService": {"coding": [{"code": "97153"}]}}]
  }'
```

**Expected Response:**
```json
{
  "status": "accepted",
  "task_id": "<celery-task-id>",
  "message": "Claim queued for processing"
}
```

### 12. Commit Changes

```bash
# Stage all changes
git add upstream/models.py
git add upstream/views/webhooks.py
git add upstream/automation/__init__.py
git add upstream/automation/rules_engine.py
git add upstream/tasks.py
git add upstream/migrations/0023_add_execution_log.py
git add upstream/migrations/0024_add_authorization.py
git add upstream/migrations/0025_add_claim_submitted_via.py
git add .planning/quick/022-complete-week-1-tasks-2-7-for-autonomous/022-SUMMARY.md

# Commit
git commit -m "feat(quick-022): complete Week 1 autonomous execution foundation

Tasks completed:
- Add ExecutionLog model for HIPAA audit trail
- Add Authorization model with expiration tracking
- Add ClaimRecord.submitted_via field for multi-source ingestion
- Create EHR webhook receiver for FHIR R4 claims
- Implement rules engine framework with condition evaluation
- Add Celery task for async claim processing with automation

Models: ExecutionLog, Authorization, ClaimRecord enhancement
Files: upstream/views/webhooks.py, upstream/automation/rules_engine.py
Task: upstream/tasks.py::process_claim_with_automation

SUMMARY: .planning/quick/022-complete-week-1-tasks-2-7-for-autonomous/022-SUMMARY.md

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

### 13. Update STATE.md

Add entry to Quick Tasks Completed section:

```markdown
| 022 | Complete Week 1 Tasks 2-7 for autonomous execution platform | 2026-01-27 | <commit-hash> | [022-complete-week-1-tasks-2-7-for-autonomous](./quick/022-complete-week-1-tasks-2-7-for-autonomous/) |
```

## Automated Completion (Alternative)

Instead of running commands manually, you can use the completion script:

```bash
cd /workspaces/codespaces-django
bash upstream/automation/complete_task_022.sh
```

This script will:
1. Create all three migrations
2. Show migration plan
3. Apply migrations
4. Verify model imports
5. Verify rules engine imports
6. Verify webhook endpoint
7. Verify Celery task
8. Check database tables exist
9. Show completion summary with timing

## Known Issues / TODOs

1. **URL Wiring:** Webhook endpoint needs to be added to urls.py
2. **API Authentication:** Currently uses Customer.objects.first() - needs proper API key auth
3. **FHIR Parsing:** Simplified parsing for Week 1 - needs fhir.resources library
4. **Risk Scoring:** Placeholder (risk_score=0) - needs Week 2 implementation
5. **Action Execution:** Stub implementation - needs Week 2-4 payer portal automation

## Troubleshooting

### If makemigrations fails with "No changes detected":

This means Django doesn't see the model changes. Check:
1. Models are in `upstream/models.py` (not a sub-module)
2. Models have proper imports at top of file
3. Try `python manage.py makemigrations upstream --dry-run --verbosity 3` for details

### If migration applies but models don't import:

Check for:
1. Syntax errors in models.py
2. Missing imports (CustomerScopedManager, MinValueValidator)
3. Circular import issues

### If Celery task doesn't register:

1. Check CELERY_ENABLED setting
2. Verify task has @shared_task decorator
3. Verify base=MonitoredTask is correct
4. Restart Celery worker if running

### If webhook returns 404:

1. Verify URL routing is configured
2. Check urls.py includes the webhook path
3. Run `python manage.py show_urls` if django-extensions is installed

## Success Indicators

When complete, you should see:

✅ Three new migration files created (0023, 0024, 0025)
✅ Migrations applied successfully (no errors)
✅ Models import without errors
✅ Rules engine imports without errors
✅ Webhook function exists with CSRF exemption
✅ Celery task registered with correct name
✅ Database tables exist and are empty (0 rows initially)
✅ All files committed to git
✅ STATE.md updated with task completion

## Next Phase

After completion, ready to proceed with:
- Week 2: Risk scoring algorithm implementation
- Week 2-4: Payer portal RPA automation
- FHIR parsing library integration
- API key authentication for webhooks
- Comprehensive testing suite
