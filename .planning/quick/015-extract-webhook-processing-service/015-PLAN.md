---
phase: quick-015
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - upstream/services/webhook_processor.py
  - upstream/integrations/services.py
  - upstream/tasks.py
  - upstream/management/commands/send_webhooks.py
  - upstream/tests_webhooks.py
  - upstream/tests_delivery.py
autonomous: true

must_haves:
  truths:
    - Webhook delivery logic extracted to services/webhook_processor.py
    - All webhook imports updated to use new service module
    - Existing tests pass without modification
  artifacts:
    - path: upstream/services/webhook_processor.py
      provides: Webhook delivery and retry logic
      exports: ["deliver_webhook", "process_pending_deliveries", "dispatch_event", "create_webhook_delivery"]
      min_lines: 140
    - path: upstream/integrations/services.py
      provides: Signature generation utilities only
      exports: ["generate_signature", "verify_signature"]
      max_lines: 30
  key_links:
    - from: upstream/tasks.py
      to: upstream.services.webhook_processor
      via: "import deliver_webhook"
      pattern: "from upstream\\.services\\.webhook_processor import deliver_webhook"
    - from: upstream/management/commands/send_webhooks.py
      to: upstream.services.webhook_processor
      via: "import process_pending_deliveries"
      pattern: "from upstream\\.services\\.webhook_processor import process_pending_deliveries"
---

<objective>
Extract webhook processing service to follow established codebase pattern of placing business logic in services/ directory.

Purpose: Improve code organization by moving webhook delivery and retry logic from integrations/services.py to services/webhook_processor.py, aligning with existing services like payer_drift.py, alert_processing.py, and report_generation.py.

Output: Dedicated webhook_processor.py service module with all delivery, retry, and dispatching logic.
</objective>

<execution_context>
@/home/codespace/.claude/get-shit-done/workflows/execute-plan.md
@/home/codespace/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md

## Current Code Structure

**upstream/integrations/services.py** contains:
- Signature utilities (generate_signature, verify_signature)
- Webhook delivery logic (deliver_webhook, create_webhook_delivery)
- Event dispatching (dispatch_event)
- Retry processing (process_pending_deliveries)

**Desired State:**
- **upstream/services/webhook_processor.py**: Delivery, retry, and dispatch logic
- **upstream/integrations/services.py**: Only signature utilities (generate_signature, verify_signature)

**Import References:**
- upstream/tasks.py: `from upstream.integrations.services import deliver_webhook`
- upstream/management/commands/send_webhooks.py: `from upstream.integrations.services import process_pending_deliveries`
- upstream/tests_webhooks.py: Multiple imports from integrations.services
- upstream/tests_delivery.py: `from upstream.integrations.services import generate_signature, deliver_webhook, process_pending_deliveries`

## Established Pattern

Services directory contains business logic modules:
- services/payer_drift.py (drift detection logic)
- services/alert_processing.py (alert handling)
- services/report_generation.py (report creation)
- services/evidence_payload.py (payload generation)
- services/data_quality.py (data validation)

Each service imports models, utilities, and other services as needed.
</context>

<tasks>

<task type="auto">
  <name>Extract webhook processor service</name>
  <files>
    upstream/services/webhook_processor.py
    upstream/integrations/services.py
  </files>
  <action>
Create upstream/services/webhook_processor.py by extracting the following from upstream/integrations/services.py:
- deliver_webhook(delivery: WebhookDelivery) -> bool
- create_webhook_delivery(endpoint: WebhookEndpoint, event_type: str, payload: Dict) -> Optional[WebhookDelivery]
- dispatch_event(customer: Customer, event_type: str, payload: Dict) -> List[WebhookDelivery]
- process_pending_deliveries() -> Dict[str, int]

**Implementation details:**
- Import signature utilities from integrations.services: `from upstream.integrations.services import generate_signature`
- Import models: WebhookEndpoint, WebhookDelivery from upstream.integrations.models
- Import Customer from upstream.models
- Import timezone, uuid, json, logging, requests, Dict, List, Optional, Any
- Preserve all existing logic exactly (audit event creation, request_id handling, retry scheduling)
- Use same logger pattern: `logger = logging.getLogger(__name__)`

**Leave in upstream/integrations/services.py:**
- generate_signature() function
- verify_signature() function
- All imports needed for these functions (hashlib, hmac, json, Union, Dict, Any)
- Module docstring: """Webhook signature utilities."""

Why keep signatures in integrations: These are cryptographic utilities used by both webhook delivery AND webhook verification (receivers), so they belong in integrations layer.
  </action>
  <verify>
Run: `python -c "from upstream.services.webhook_processor import deliver_webhook, process_pending_deliveries, dispatch_event, create_webhook_delivery; from upstream.integrations.services import generate_signature, verify_signature; print('Imports successful')"`
  </verify>
  <done>
- upstream/services/webhook_processor.py exists with 4 exported functions
- upstream/integrations/services.py contains only signature utilities (~28 lines)
- Both modules import without errors
  </done>
</task>

<task type="auto">
  <name>Update all import references</name>
  <files>
    upstream/tasks.py
    upstream/management/commands/send_webhooks.py
    upstream/tests_webhooks.py
    upstream/tests_delivery.py
  </files>
  <action>
Update imports in 4 files to reference new module location:

**upstream/tasks.py (line 97):**
- Change: `from upstream.integrations.services import deliver_webhook`
- To: `from upstream.services.webhook_processor import deliver_webhook`

**upstream/management/commands/send_webhooks.py (line 8):**
- Change: `from upstream.integrations.services import process_pending_deliveries`
- To: `from upstream.services.webhook_processor import process_pending_deliveries`

**upstream/tests_webhooks.py (line 14):**
- Change: `from upstream.integrations.services import (deliver_webhook, dispatch_event, create_webhook_delivery, generate_signature, verify_signature)`
- To: `from upstream.services.webhook_processor import deliver_webhook, dispatch_event, create_webhook_delivery`
- Add: `from upstream.integrations.services import generate_signature, verify_signature`

**upstream/tests_delivery.py (line 17):**
- Change: `from upstream.integrations.services import generate_signature, deliver_webhook, process_pending_deliveries`
- To: `from upstream.services.webhook_processor import deliver_webhook, process_pending_deliveries`
- Add: `from upstream.integrations.services import generate_signature`

Keep verify_signature imports from integrations.services (not moved, remains there).
  </action>
  <verify>
Run test suite to verify no import errors: `cd /workspaces/codespaces-django && python manage.py test upstream.tests_webhooks upstream.tests_delivery --settings=upstream.settings.test --keepdb`
  </verify>
  <done>
- All imports updated to reference new module paths
- Test suite runs without import errors
- Webhook tests pass (delivery, retry, signature validation)
  </done>
</task>

<task type="auto">
  <name>Verify extraction completeness</name>
  <files>N/A (verification only)</files>
  <action>
Run comprehensive verification:

1. Check no remaining references to moved functions in old location:
```bash
grep -n "from upstream.integrations.services import.*deliver_webhook" /workspaces/codespaces-django/upstream/**/*.py 2>/dev/null || echo "✓ No stale deliver_webhook imports"
grep -n "from upstream.integrations.services import.*dispatch_event" /workspaces/codespaces-django/upstream/**/*.py 2>/dev/null || echo "✓ No stale dispatch_event imports"
```

2. Verify new module is importable:
```bash
python -c "from upstream.services.webhook_processor import deliver_webhook, process_pending_deliveries, dispatch_event, create_webhook_delivery; print('✓ All webhook processor functions import successfully')"
```

3. Run webhook-related tests:
```bash
python manage.py test upstream.tests_webhooks upstream.tests_delivery --settings=upstream.settings.test --keepdb
```

4. Verify services/__init__.py doesn't need updates (it doesn't export specific functions, just provides namespace).
  </action>
  <verify>
All grep commands return no results (or "✓" messages), imports succeed, tests pass.
  </verify>
  <done>
- No stale imports remain
- New module fully functional
- Existing test coverage validates extraction
- Code organization improved following established pattern
  </done>
</task>

</tasks>

<verification>
1. upstream/services/webhook_processor.py exists with 140+ lines
2. upstream/integrations/services.py reduced to ~28 lines (signatures only)
3. All imports updated (tasks.py, send_webhooks.py, tests)
4. `python manage.py test upstream.tests_webhooks upstream.tests_delivery` passes
5. No references to old import paths remain
</verification>

<success_criteria>
- Webhook processing logic extracted to services/webhook_processor.py
- Signature utilities remain in integrations/services.py
- All 4 import references updated correctly
- Test suite passes without modification (tests unchanged, only imports updated)
- Code organization aligns with established services/ pattern
</success_criteria>

<output>
After completion, create `.planning/quick/015-extract-webhook-processing-service/015-SUMMARY.md`
</output>
