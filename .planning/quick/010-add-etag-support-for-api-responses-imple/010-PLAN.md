---
phase: quick-010
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - upstream/api/views.py
  - upstream/tests_api.py
autonomous: true

must_haves:
  truths:
    - "API responses include ETag headers for cacheable content"
    - "Clients can send If-None-Match headers to avoid re-downloading unchanged data"
    - "Server returns 304 Not Modified when content hasn't changed"
  artifacts:
    - path: "upstream/api/views.py"
      provides: "ETag mixin for API ViewSets"
      min_lines: 20
    - path: "upstream/tests_api.py"
      provides: "ETag validation tests"
      min_lines: 30
  key_links:
    - from: "upstream.api.views ViewSets"
      to: "ETagMixin"
      via: "inheritance"
      pattern: "class.*ViewSet.*ETagMixin"
    - from: "django.middleware.http.ConditionalGetMiddleware"
      to: "response headers"
      via: "automatic ETag injection"
      pattern: "ETag.*response"
---

<objective>
Add ETag support to API responses to enable HTTP caching and reduce bandwidth usage.

Purpose: Implement ETag headers and If-None-Match validation so clients can cache API responses and avoid re-downloading unchanged data, improving performance and reducing server load.

Output: ETag mixin applied to API ViewSets with test coverage validating 304 Not Modified responses.
</objective>

<execution_context>
@/home/codespace/.claude/get-shit-done/workflows/execute-plan.md
@/home/codespace/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md

Django's ConditionalGetMiddleware is already enabled in settings:
- Line 54 of upstream/settings/base.py: "django.middleware.http.ConditionalGetMiddleware"
- Automatically handles ETag generation and If-None-Match validation
- Uses MD5 hash of response content to generate ETags

Existing middleware pattern in upstream/middleware.py shows the project structure.
API ViewSets are in upstream/api/views.py with DRF ModelViewSet patterns.
Tests are in upstream/tests_api.py following Django TestCase patterns.
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add ETag mixin and apply to API ViewSets</name>
  <files>upstream/api/views.py</files>
  <action>
Create an ETagMixin class that configures Cache-Control headers for ETag support on API responses. Apply it to existing ViewSets (UploadViewSet, ClaimRecordViewSet, ReportRunViewSet, DriftEventViewSet, PayerMappingViewSet, AlertEventViewSet, OperatorJudgmentViewSet).

Implementation details:
- Import: `from django.utils.cache import patch_cache_control`
- Create ETagMixin with finalize_response() method that:
  - Calls super().finalize_response() to get DRF response
  - For GET requests with 200 status: `patch_cache_control(response, max_age=60, must_revalidate=True)`
  - For other methods (POST/PUT/DELETE): `patch_cache_control(response, no_cache=True, no_store=True, must_revalidate=True)`
  - Returns response
- Add ETagMixin as first base class to all ViewSets (order matters: ETagMixin, CustomerFilterMixin, viewsets.ModelViewSet)
- ConditionalGetMiddleware will automatically generate ETag headers and handle If-None-Match validation

Why this approach:
- Django's ConditionalGetMiddleware (already enabled) handles ETag generation automatically
- Only need to set Cache-Control headers via patch_cache_control()
- max_age=60 allows 1-minute client-side caching with must-revalidate for stale checks
- GET requests are cacheable, mutations (POST/PUT/DELETE) are not
- Mixin pattern allows consistent application across all ViewSets
  </action>
  <verify>
Run grep to confirm ETagMixin is applied:
```bash
grep -n "class.*ViewSet.*ETagMixin" upstream/api/views.py
```

Check imports are present:
```bash
grep "from django.utils.cache import patch_cache_control" upstream/api/views.py
```
  </verify>
  <done>
- ETagMixin class exists with finalize_response() method
- All 7 ViewSets inherit from ETagMixin as first base class
- GET responses have Cache-Control: max-age=60, must-revalidate
- Non-GET responses have Cache-Control: no-cache, no-store, must-revalidate
  </done>
</task>

<task type="auto">
  <name>Task 2: Add ETag validation tests</name>
  <files>upstream/tests_api.py</files>
  <action>
Add test class ETagCachingTests to validate ETag behavior using Django TestCase and APIClient.

Test cases to implement:
1. `test_get_response_includes_etag` - Verify GET request returns ETag header
2. `test_if_none_match_returns_304` - Verify If-None-Match with matching ETag returns 304 Not Modified
3. `test_if_none_match_mismatch_returns_200` - Verify If-None-Match with non-matching ETag returns 200 with full response
4. `test_post_request_has_no_cache` - Verify POST response has Cache-Control: no-cache, no-store
5. `test_etag_changes_when_content_changes` - Verify ETag changes after PUT update

Test setup:
- Use UploadViewSet endpoint (/api/v1/uploads/) as test target
- Create fixtures in setUp(): Customer, UserProfile, User with JWT token
- Use self.client.get() with HTTP_IF_NONE_MATCH header for conditional requests
- Assert response status codes (200, 304) and header presence (ETag, Cache-Control)
- Follow existing test patterns in tests_api.py for authentication and fixtures

Implementation notes:
- Place after existing RBACAPIEndpointTests class (around line 800+)
- Import: `from rest_framework.test import APIClient`
- JWT auth required: Use force_authenticate() or create proper JWT token in setUp()
- Test database isolation: Each test runs with fresh database state
  </action>
  <verify>
Run the new tests:
```bash
python manage.py test upstream.tests_api.ETagCachingTests -v 2
```

Expected output: 5 tests pass with status codes validated.
  </verify>
  <done>
- ETagCachingTests class with 5 test methods exists
- All tests pass validating 200, 304 status codes, ETag headers, and Cache-Control headers
- Tests confirm ConditionalGetMiddleware generates ETags and handles If-None-Match
- Tests confirm ETag changes when content is updated
  </done>
</task>

<task type="auto">
  <name>Task 3: Run full test suite to verify no regressions</name>
  <files></files>
  <action>
Run complete test suite to ensure ETag implementation doesn't break existing functionality.

Commands to run:
```bash
python manage.py test upstream.tests_api -v 2
```

Expected behavior:
- All existing tests pass (including new ETagCachingTests)
- No test failures or errors related to response headers
- Performance should be identical (ConditionalGetMiddleware was already enabled)
- ETag headers appear on GET responses for all API endpoints

If any failures occur:
1. Check that ETagMixin is first in inheritance order (must come before CustomerFilterMixin)
2. Verify Cache-Control headers don't conflict with existing middleware
3. Ensure test fixtures create proper authentication tokens
  </action>
  <verify>
```bash
python manage.py test upstream.tests_api -v 2
```

All tests should pass with output showing "Ran X tests in Y.YYs OK"
  </verify>
  <done>
- Full upstream.tests_api suite passes without regressions
- New ETag tests integrate cleanly with existing test infrastructure
- API responses include ETag headers on GET requests
- If-None-Match validation works correctly via ConditionalGetMiddleware
  </done>
</task>

</tasks>

<verification>
Manual verification steps:

1. Start development server: `python manage.py runserver`

2. Test ETag generation:
```bash
# Get initial response with ETag
curl -i http://localhost:8000/api/v1/uploads/ \
  -H "Authorization: Bearer <token>"

# Response should include:
# ETag: "3858f62230ac3c915f300c664312c63f"
# Cache-Control: max-age=60, must-revalidate
```

3. Test conditional request:
```bash
# Use ETag from previous response
curl -i http://localhost:8000/api/v1/uploads/ \
  -H "Authorization: Bearer <token>" \
  -H "If-None-Match: \"3858f62230ac3c915f300c664312c63f\""

# Should return: 304 Not Modified (no body)
```

4. Test after content change:
```bash
# Create new upload via POST
curl -X POST http://localhost:8000/api/v1/uploads/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"filename": "test.txt"}'

# GET again with old ETag
curl -i http://localhost:8000/api/v1/uploads/ \
  -H "Authorization: Bearer <token>" \
  -H "If-None-Match: \"3858f62230ac3c915f300c664312c63f\""

# Should return: 200 OK with new ETag (content changed)
```

All tests should demonstrate proper ETag generation and 304 Not Modified responses.
</verification>

<success_criteria>
- [ ] ETagMixin class created and applied to all 7 API ViewSets
- [ ] GET responses include ETag header (MD5 hash of content)
- [ ] GET responses include Cache-Control: max-age=60, must-revalidate
- [ ] POST/PUT/DELETE responses include Cache-Control: no-cache, no-store
- [ ] If-None-Match with matching ETag returns 304 Not Modified
- [ ] If-None-Match with stale ETag returns 200 OK with new content
- [ ] 5 new tests in ETagCachingTests all pass
- [ ] Full test suite passes without regressions
- [ ] Manual curl tests demonstrate bandwidth savings via 304 responses
</success_criteria>

<output>
After completion, create `.planning/quick/010-add-etag-support-for-api-responses-imple/010-SUMMARY.md` documenting:
- ETag implementation approach (ConditionalGetMiddleware + Cache-Control headers)
- Performance benefits (304 responses save bandwidth)
- Test coverage added (5 tests validating ETag behavior)
- Files modified and line counts
</output>
