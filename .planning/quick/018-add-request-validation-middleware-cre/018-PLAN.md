---
phase: quick-018
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - upstream/middleware.py
  - upstream/tests_middleware_validation.py
  - upstream/settings/base.py
autonomous: true

must_haves:
  truths:
    - "Invalid JSON payloads return 400 with error details"
    - "Missing required fields return 400 with field names"
    - "Requests with valid JSON pass through unchanged"
    - "Middleware only validates POST/PUT/PATCH requests"
  artifacts:
    - path: "upstream/middleware.py"
      provides: "RequestValidationMiddleware class with JSON schema validation"
      min_lines: 50
      contains: "class RequestValidationMiddleware"
    - path: "upstream/tests_middleware_validation.py"
      provides: "Test coverage for validation middleware"
      min_lines: 100
  key_links:
    - from: "upstream/settings/base.py"
      to: "upstream.middleware.RequestValidationMiddleware"
      via: "MIDDLEWARE list"
      pattern: "RequestValidationMiddleware"
    - from: "RequestValidationMiddleware.process_view"
      to: "json.loads(request.body)"
      via: "JSON parsing and validation"
      pattern: "json\\.loads"
---

<objective>
Add request validation middleware to provide centralized JSON schema validation for API endpoints with standardized 400 error responses.

Purpose: Prevent invalid data from reaching view layer, reduce boilerplate validation code, and provide consistent error responses across the API.

Output: RequestValidationMiddleware class in upstream/middleware.py with comprehensive test coverage and middleware configuration.
</objective>

<execution_context>
@/home/codespace/.claude/get-shit-done/workflows/execute-plan.md
@/home/codespace/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@/workspaces/codespaces-django/.planning/STATE.md
@/workspaces/codespaces-django/upstream/middleware.py
@/workspaces/codespaces-django/upstream/settings/base.py

## Existing Patterns

The codebase has established middleware patterns:
- MiddlewareMixin base class for backward compatibility
- process_request for pre-processing, process_response for post-processing
- Early return of HttpResponse to short-circuit request flow
- JsonResponse for structured error responses
- Thread-safe implementations (no shared mutable state)

Existing middleware examples:
- HealthCheckMiddleware: Early return pattern for /health/ endpoint
- RequestIdMiddleware: Request/response processing with header injection
- ApiVersionMiddleware: Response header modification
- SecurityHeadersMiddleware: Response header security additions

DRF serializers already handle validation, but middleware provides:
- Request-level validation before routing
- Protection against malformed payloads
- Consistent error format across all endpoints
- Defense against common API attacks (oversized payloads, malformed JSON)
</context>

<tasks>

<task type="auto">
  <name>Create RequestValidationMiddleware with JSON validation</name>
  <files>upstream/middleware.py</files>
  <action>
Add RequestValidationMiddleware class to upstream/middleware.py:

1. Create class inheriting from MiddlewareMixin
2. Implement process_view method (runs after routing, before view execution):
   - Only validate POST/PUT/PATCH requests (GET/DELETE don't have bodies)
   - Skip validation for admin paths (/admin/)
   - Check Content-Type header is application/json
   - Parse request.body with json.loads
   - Catch JSONDecodeError and return 400 with {"error": "Invalid JSON", "detail": error message}
   - On success, attach parsed data to request.validated_data for view access
3. Add docstring explaining:
   - Purpose: Centralized JSON validation before view layer
   - When it runs: After routing, before view execution (process_view)
   - What it validates: JSON parsing only (schema validation left to serializers)
   - Error format: {"error": "message", "detail": "specifics"}
4. Return None for successful validation (allows request to continue)
5. Return JsonResponse with status=400 for validation failures

Why process_view not process_request: process_view has access to view_func and view_args, allowing view-specific validation rules in future. process_request runs before routing, so we can't determine which endpoint is being called.

Edge cases to handle:
- Empty body (valid for some endpoints, let view decide)
- Non-JSON Content-Type (return 415 Unsupported Media Type)
- Request.body already consumed (cache parsed data)
  </action>
  <verify>
Run: grep -n "class RequestValidationMiddleware" upstream/middleware.py
Should show new middleware class with process_view method
  </verify>
  <done>RequestValidationMiddleware exists in upstream/middleware.py with JSON parsing, error handling, and 400 responses for invalid JSON</done>
</task>

<task type="auto">
  <name>Add comprehensive test suite for validation middleware</name>
  <files>upstream/tests_middleware_validation.py</files>
  <action>
Create upstream/tests_middleware_validation.py with Django TestCase:

1. Import necessary modules: TestCase, RequestFactory, JsonResponse, json
2. Create RequestValidationMiddlewareTests class
3. Add setUp method:
   - Initialize RequestFactory
   - Create middleware instance
   - Create mock get_response function
4. Test cases to implement:
   - test_valid_json_post: Valid POST with JSON body passes through
   - test_valid_json_put: Valid PUT with JSON body passes through
   - test_valid_json_patch: Valid PATCH with JSON body passes through
   - test_invalid_json_returns_400: Malformed JSON returns 400 with error
   - test_empty_json_object: {} is valid JSON
   - test_json_array: [] is valid JSON
   - test_missing_content_type: Non-JSON Content-Type returns 415
   - test_get_request_skipped: GET requests bypass validation
   - test_delete_request_skipped: DELETE requests bypass validation
   - test_admin_path_skipped: /admin/ paths bypass validation
   - test_validated_data_attached: Successful validation adds request.validated_data
5. Each test should:
   - Create request with RequestFactory
   - Set appropriate headers (Content-Type)
   - Call middleware.process_view(request, view_func, view_args, view_kwargs)
   - Assert response status code or None return
   - Assert error message format for failures

Use existing test patterns from upstream/tests_api.py for consistency.
  </action>
  <verify>
Run: python manage.py test upstream.tests_middleware_validation -v 2
All tests should pass (10+ test cases)
  </verify>
  <done>Comprehensive test suite exists with 10+ passing tests covering valid/invalid JSON, different HTTP methods, Content-Type handling, and path skipping</done>
</task>

<task type="auto">
  <name>Configure middleware in Django settings</name>
  <files>upstream/settings/base.py</files>
  <action>
Add RequestValidationMiddleware to MIDDLEWARE list in upstream/settings/base.py:

1. Insert after ApiVersionMiddleware (line ~68) and before PrometheusAfterMiddleware
2. Position rationale:
   - After authentication (needs user context for potential future role-based validation)
   - After RequestIdMiddleware (validation errors should include request ID)
   - Before PrometheusAfterMiddleware (failed validations should be tracked in metrics)
3. Add inline comment explaining purpose:
   # Request validation middleware - validates JSON payloads before view execution

Final MIDDLEWARE order around insertion point:
```python
"upstream.middleware.ApiVersionMiddleware",
"upstream.middleware.RequestValidationMiddleware",  # NEW
"django_prometheus.middleware.PrometheusAfterMiddleware",
```

DO NOT add to test.py or dev.py settings (base.py applies to all environments).
  </action>
  <verify>
Run: grep -n "RequestValidationMiddleware" upstream/settings/base.py
Should show middleware added to MIDDLEWARE list with comment
  </verify>
  <done>RequestValidationMiddleware configured in MIDDLEWARE list in upstream/settings/base.py with proper positioning and inline comment</done>
</task>

</tasks>

<verification>
Run full validation:
1. python manage.py test upstream.tests_middleware_validation
2. python manage.py check (no system errors)
3. curl -X POST http://localhost:8000/api/v1/uploads/ -H "Content-Type: application/json" -d "invalid json"
   Should return 400 with error message
4. curl -X POST http://localhost:8000/api/v1/uploads/ -H "Content-Type: application/json" -d '{"valid": "json"}'
   Should pass validation (may fail auth, but validation passes)
</verification>

<success_criteria>
- RequestValidationMiddleware class exists in upstream/middleware.py
- Middleware validates JSON for POST/PUT/PATCH requests only
- Invalid JSON returns 400 with {"error": ..., "detail": ...}
- Valid JSON attaches request.validated_data
- Non-JSON Content-Type returns 415
- GET/DELETE requests skip validation
- Admin paths skip validation
- 10+ passing tests in upstream/tests_middleware_validation.py
- Middleware configured in MIDDLEWARE list
- python manage.py check passes with no warnings
</success_criteria>

<output>
After completion, create `.planning/quick/018-add-request-validation-middleware-cre/018-SUMMARY.md`
</output>
