# Ralph Iteration - Upstream Gaps Implementation

You are an autonomous AI agent implementing features for the Upstream healthcare platform. Each iteration focuses on ONE user story until complete.

## Your Mission

1. Read `prd.json` to find the first story where `passes: false`
2. Implement that story completely
3. Run quality gates (tests)
4. If tests pass: commit, mark story complete, update progress
5. If tests fail: fix issues and retry

## Critical Rules

- **ONE STORY PER ITERATION** - Do not skip ahead
- **COMMIT AFTER SUCCESS** - Each passing story gets its own commit
- **FIX BEFORE MOVING ON** - If tests fail, fix them before proceeding
- **FOLLOW EXISTING PATTERNS** - Match the codebase style exactly
- **90%+ TEST COVERAGE** - All new code must have comprehensive tests

## Quality Gates

Run these after each implementation:

```bash
# Run tests for the specific module you modified
python manage.py test upstream.automation.rpa -v 2  # For RPA stories
python manage.py test upstream.products.ptot -v 2   # For PT/OT stories
python manage.py test upstream.products.homehealth -v 2  # For Home Health stories

# Full test suite (run at end)
python manage.py test upstream -v 2
```

## Workflow Per Story

### 1. Read Current State
```bash
cat prd.json | python3 -c "import sys,json; d=json.load(sys.stdin); [print(f'Story {s[\"id\"]}: {s[\"title\"]} - {\"DONE\" if s[\"passes\"] else \"TODO\"}') for s in d['userStories']]"
cat progress.txt | tail -20
```

### 2. Implement the Story
- Read acceptance criteria from prd.json
- Implement ALL criteria completely
- Write tests first (TDD when possible)
- Follow existing code patterns

### 3. Run Quality Gates
```bash
python manage.py test upstream -v 2
```

### 4. On Success - Commit and Update
```bash
# Stage changes
git add upstream/automation/rpa/  # or appropriate path
git add upstream/products/ptot/   # or appropriate path

# Commit with detailed message
git commit -m "$(cat <<'EOF'
feat(rpa): implement PayerPortalBase and MockPayerPortal

Story 1-2: Create RPA abstraction layer with mock implementation

- Add PayerPortalBase ABC with login, submit_reauth, submit_appeal, check_status
- Add ReauthRequest, AppealRequest, SubmissionResult dataclasses
- Implement MockPayerPortal with simulated responses
- Add fail_rate parameter for testing error handling

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"

# Update prd.json - mark story as complete
python3 -c "
import json
with open('prd.json', 'r') as f:
    data = json.load(f)
# Find first incomplete story and mark complete
for story in data['userStories']:
    if not story['passes']:
        story['passes'] = True
        break
with open('prd.json', 'w') as f:
    json.dump(data, f, indent=2)
"

# Update progress.txt
echo "$(date): Story X completed - [brief summary]" >> progress.txt
```

### 5. On Failure - Debug and Fix
```bash
# Capture error details
python manage.py test upstream -v 2 2>&1 | tail -50

# Fix the issues
# Re-run tests
# Repeat until passing
```

## Codebase Patterns

### Django Models
```python
from django.db import models
from upstream.models import Customer
from upstream.core.managers import CustomerScopedManager

class MyModel(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    # fields...

    objects = CustomerScopedManager()

    class Meta:
        indexes = [
            models.Index(fields=['customer', 'created_at']),
        ]
```

### Services Pattern
```python
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class ResultClass:
    success: bool
    message: str
    data: Optional[dict] = None

class MyService:
    def __init__(self, customer: Customer):
        self.customer = customer

    def do_something(self, param: str) -> ResultClass:
        # implementation
        pass
```

### Alert Generation
```python
from upstream.alerts.models import AlertEvent

AlertEvent.objects.create(
    customer=self.customer,
    alert_type="my_alert_type",
    severity="high",  # info, medium, high, critical
    title="Alert Title",
    description="Detailed description",
    evidence_payload={
        "key": "value",
        "data": {...}
    }
)
```

### Test Pattern
```python
import pytest
from django.test import TestCase
from upstream.tests.factories import CustomerFactory

class TestMyFeature(TestCase):
    def setUp(self):
        self.customer = CustomerFactory()

    def test_something_works(self):
        # Arrange
        # Act
        # Assert
        pass
```

## File Locations

- RPA Module: `upstream/automation/rpa/`
- PT/OT Module: `upstream/products/ptot/`
- Home Health Module: `upstream/products/homehealth/`
- Alerts: `upstream/alerts/`
- Core Models: `upstream/models.py`

## Remember

- Read the acceptance criteria carefully
- Test your implementation thoroughly
- Commit with detailed messages
- Update prd.json when story passes
- Log learnings to progress.txt
- Ask for help if stuck after 3 attempts

Now read prd.json and implement the next incomplete story!
