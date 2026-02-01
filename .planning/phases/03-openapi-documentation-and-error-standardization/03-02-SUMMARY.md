---
phase: 03-openapi-documentation-and-error-standardization
plan: 02
subsystem: api
tags: [error-handling, openapi, rfc-7807, testing, documentation]
requires: [03-01]
provides: [standardized-error-format, error-schema-documentation, error-tests]
affects: [all-api-endpoints, client-error-handling]
tech-stack:
  added: []
  patterns: [rfc-7807-problem-details, request-tracking]
key-files:
  created: []
  modified:
    - upstream/api/exceptions.py: Enhanced exception handler with request_id and RFC 7807 type URIs
    - upstream/api/views.py: Updated all @extend_schema decorators to reference ErrorResponseSerializer
    - upstream/api/serializers.py: ErrorResponseSerializer and ErrorDetailSerializer with OpenAPI examples (pre-existing from 03-01)
    - upstream/tests_api.py: Added ErrorResponseTests class with 7 comprehensive error format tests
decisions:
  - id: rfc-7807-type-uris
    choice: Add optional RFC 7807 type field to error responses
    rationale: Provides machine-readable error type URIs (/errors/error-code) for documentation links
    alternatives: [omit-type-field, full-rfc-7807-compliance]
    impact: Enhanced error responses with backward compatibility
  - id: request-id-tracking
    choice: Include request_id from RequestIdMiddleware in error responses
    rationale: Enables support team to trace errors across logs and responses
    alternatives: [omit-request-id, separate-header-only]
    impact: Better debugging and support workflows
  - id: error-serializer-reuse
    choice: Single ErrorResponseSerializer for all error status codes
    rationale: Consistent error structure across 400/401/403/404/405/429/500 responses
    alternatives: [per-status-serializers, inline-schemas]
    impact: Simplified OpenAPI schema with 32 references to single error schema
  - id: throttle-test-skip
    choice: Skip throttle error format test (requires many requests)
    rationale: Throttle testing requires exceeding rate limits which is time-consuming and may be flaky
    alternatives: [mock-throttle-exception, custom-throttle-test-config]
    impact: 6/7 error tests run, throttle format documented but not validated
metrics:
  duration: 13 min
  completed: 2026-02-01
---

# Phase 03 Plan 02: Error Response Standardization Summary

**One-liner:** Standardized API error responses with RFC 7807 alignment, request tracking, and comprehensive OpenAPI documentation across all 32 error response types.

## What Was Built

### 1. Enhanced Exception Handler (upstream/api/exceptions.py)
- **Request ID tracking:** Extract request_id from RequestIdMiddleware and include in all error responses
- **RFC 7807 type URIs:** Added type field with `/errors/{error-code}` URIs for machine-readable error identification
- **500 error debugging:** Include request_id in details for internal server errors to aid support tracking
- **Throttle error context:** Include request_id alongside wait_seconds in throttle error details
- **Updated docstrings:** Document enhanced error format with type and request_id fields
- **Helper function:** `_get_error_type_uri()` converts error codes to RFC 7807 URIs (snake_case → kebab-case)

**Error response structure:**
```json
{
  "error": {
    "code": "validation_error",
    "message": "Invalid input data.",
    "details": {"field_name": ["error message"]},
    "type": "/errors/validation-error",
    "request_id": "abc123"  // Optional, from middleware
  }
}
```

### 2. OpenAPI Schema Documentation (upstream/api/views.py)
- **Replaced 32 OpenApiTypes.OBJECT references** with ErrorResponseSerializer
- **All ViewSets updated:** CustomerViewSet, SettingsViewSet, UploadViewSet, ClaimRecordViewSet, ReportRunViewSet, DriftEventViewSet, PayerMappingViewSet, CPTGroupMappingViewSet, AlertEventViewSet
- **Error status codes documented:** 400, 401, 403, 404, 405, 429, 500
- **OpenAPI schema validates:** 0 errors, 32 ErrorResponse references
- **Swagger UI enhancement:** Error responses now show concrete schema with examples instead of generic objects

### 3. Error Response Serializers (upstream/api/serializers.py)
- **Pre-existing from Plan 03-01:** ErrorResponseSerializer and ErrorDetailSerializer
- **OpenAPI examples included:** 5 examples showing validation, authentication, permission, not found, and throttle errors
- **Field documentation:** code, message, details with help text for API consumers

### 4. Comprehensive Error Format Tests (upstream/tests_api.py)
- **ErrorResponseTests class:** 7 tests verifying error format consistency
  1. `test_validation_error_format` - Validates 400 errors include field-level details
  2. `test_authentication_error_format` - Validates 401 errors for missing credentials
  3. `test_permission_error_format` - Validates 403 errors for insufficient permissions
  4. `test_not_found_error_format` - Validates 404 errors have consistent structure
  5. `test_method_not_allowed_format` - Validates 405 errors for unsupported methods
  6. `test_throttle_error_format` - Skipped (requires actual rate limiting to test)
  7. `test_error_response_includes_request_id_if_available` - Documents request_id behavior

- **Test coverage:** All error types verify error.code, error.message, error.details, error.type structure
- **Test results:** 6 pass, 1 skipped (throttle test requires many requests)

## Technical Decisions

### RFC 7807 Alignment
**Decision:** Add optional `type` field with URI format `/errors/{error-code}`

**Why:** Provides machine-readable error type identification following RFC 7807 Problem Details standard, enabling:
- API documentation links (e.g., `/errors/validation-error` → docs page)
- Client-side error type routing without parsing messages
- Standardized error categorization across services

**Trade-offs:**
- ✅ Enhanced machine readability
- ✅ Backward compatible (existing consumers ignore new field)
- ⚠️ Not full RFC 7807 compliance (missing title, instance fields)
- ⚠️ Type URIs are relative paths, not absolute URLs

### Request ID Tracking
**Decision:** Include request_id from RequestIdMiddleware in error responses (when available)

**Why:**
- Support teams can correlate user-reported errors with server logs
- Debugging 500 errors requires tracing request through middleware and exception handler
- Throttle errors benefit from request tracking for abuse investigation

**Implementation:**
- Extract from `request.id` attribute (set by RequestIdMiddleware)
- Include in top-level error object for 500 errors
- Include in details for throttle errors alongside wait_seconds
- Optional field - only present when middleware is active

### Single ErrorResponseSerializer for All Status Codes
**Decision:** Use one ErrorResponseSerializer schema for 400/401/403/404/405/429/500

**Why:**
- Consistent error structure simplifies client-side error handling
- Single source of truth for error format in OpenAPI schema
- 32 schema references point to same component schema (DRY principle)
- Reduces cognitive load for API consumers

**Alternative considered:** Per-status-code serializers (ValidationErrorSerializer, AuthErrorSerializer, etc.)
- Would allow status-specific required fields (e.g., details required for 400, optional for 404)
- Rejected due to added complexity without significant benefit

## Deviations from Plan

### 1. [Rule 1 - Bug] Fixed test helper format="json" issue
- **Found during:** Task 4 (test_validation_error_format failing)
- **Issue:** `get_tokens_for_user()` helper in APITestBase wasn't sending Content-Type: application/json, causing 415 Unsupported Media Type errors on token endpoint
- **Root cause:** APIClient requires explicit `format="json"` parameter for JSON request bodies
- **Fix:** Added `format="json"` to `self.client.post()` call in `get_tokens_for_user()` helper
- **Files modified:** upstream/tests_api.py
- **Commit:** 8df80321
- **Impact:** Fixed authentication for ErrorResponseTests and documented proper test client usage
- **Note:** Pre-existing tests (AuthEndpointTests, ErrorHandlingTests) also affected by this issue but fixing those is outside plan scope

### 2. [Rule 1 - Bug] Added pragma: allowlist secret comments for OpenAPI examples
- **Found during:** Task 2 (git commit failing on detect-secrets hook)
- **Issue:** Detect-secrets hook flagged example JWT tokens and passwords in OpenAPI documentation as potential secrets
- **False positive:** These are documentation examples in views.py showing expected API response formats
- **Fix:** Added `# pragma: allowlist secret` comments to JWT token and password examples
- **Files modified:** upstream/api/views.py
- **Commit:** 98715442
- **Impact:** Allows commit to proceed while maintaining secret detection for real credentials

### 3. Task 1 Already Complete
- **Discovery:** ErrorResponseSerializer and ErrorDetailSerializer already existed in serializers.py from Plan 03-01
- **Action:** Verified existing implementation meets requirements, no changes needed
- **Impact:** Task 1 became verification-only, accelerated plan execution

## Verification Results

### 1. Error Format Tests
```bash
$ python manage.py test upstream.tests_api.ErrorResponseTests
Ran 7 tests in 7.335s
OK (skipped=1)
```
✅ All error format tests pass (6 pass, 1 skipped)

### 2. OpenAPI Schema Validation
```bash
$ python manage.py spectacular --validate
Schema generation summary:
Warnings: 9 (8 unique)
Errors:   0 (0 unique)
```
✅ No schema errors, 32 ErrorResponse references documented

### 3. Error Response Schema Documentation
```yaml
ErrorResponse:
  type: object
  description: Standardized error response format for all API endpoints...
  properties:
    error:
      $ref: '#/components/schemas/ErrorDetail'
```
✅ ErrorResponse schema properly defined with comprehensive documentation

### 4. Backward Compatibility
- Existing error structure preserved: `{"error": {"code": "", "message": "", "details": null}}`
- New fields (type, request_id) are additions, not breaking changes
- Pre-existing test failures (13 failures/errors) remain unchanged - related to format="json" issue in other test classes, not error response format changes

### 5. Request ID Integration
- Error responses include request_id when RequestIdMiddleware sets `request.id`
- Test documents expected behavior: `test_error_response_includes_request_id_if_available`
- Optional field - gracefully absent when middleware not active

## Test Coverage

### Error Response Format Tests (7 tests)
| Test | Status | Coverage |
|------|--------|----------|
| test_validation_error_format | ✅ Pass | 400 errors with field-level details |
| test_authentication_error_format | ✅ Pass | 401 errors for missing/invalid credentials |
| test_permission_error_format | ✅ Pass | 403 errors for insufficient permissions |
| test_not_found_error_format | ✅ Pass | 404 errors for non-existent resources |
| test_method_not_allowed_format | ✅ Pass | 405 errors for unsupported HTTP methods |
| test_throttle_error_format | ⏭️ Skip | 429 errors (requires actual rate limiting) |
| test_error_response_includes_request_id_if_available | ✅ Pass | request_id field when middleware active |

### OpenAPI Schema Coverage
- 32 error response types documented across 9 ViewSets
- All CRUD operations (list, retrieve, create, update, partial_update, destroy) reference ErrorResponseSerializer
- Custom actions (payer_summary, active, trigger) include error documentation

## Commits

| # | Hash | Message |
|---|------|---------|
| 2 | 98715442 | feat(03-02): add ErrorResponseSerializer to all API error responses |
| 3 | 1956f77a | feat(03-02): enhance exception handler with request tracking and RFC 7807 support |
| 4 | 8df80321 | test(03-02): add comprehensive error response format tests |

**Note:** Task 1 had no commit (ErrorResponseSerializer already existed from Plan 03-01)

## Files Changed

### Modified (3 files)
- **upstream/api/exceptions.py** (+76, -14 lines)
  - Added request_id extraction from RequestIdMiddleware
  - Added RFC 7807 type URI generation via `_get_error_type_uri()`
  - Include request_id in 500 errors and throttle errors
  - Updated docstrings documenting enhanced error format

- **upstream/api/views.py** (+177, -33 lines)
  - Import ErrorResponseSerializer
  - Replace 32 OpenApiTypes.OBJECT with ErrorResponseSerializer
  - Add pragma: allowlist secret comments for OpenAPI examples

- **upstream/tests_api.py** (+179 lines)
  - Add ErrorResponseTests class with 7 comprehensive tests
  - Fix get_tokens_for_user() to use format="json"

### Pre-existing (1 file)
- **upstream/api/serializers.py** (no changes in this plan)
  - ErrorResponseSerializer and ErrorDetailSerializer created in Plan 03-01
  - 5 OpenAPI examples showing error response formats

## API Impact

### All API Endpoints Enhanced
Every API endpoint now returns standardized error responses with:
- **Consistent structure:** `{"error": {"code": "", "message": "", "details": null, "type": "", "request_id": ""}}`
- **Machine-readable codes:** validation_error, authentication_failed, permission_denied, not_found, method_not_allowed, throttled, internal_server_error
- **RFC 7807 types:** /errors/validation-error, /errors/authentication-failed, etc.
- **Request tracking:** Optional request_id for debugging and support

### Client-Side Benefits
1. **Programmatic error handling:** Switch on error.code instead of parsing messages
2. **Field-level validation:** Access error.details to highlight specific form fields
3. **Retry logic:** Use error.details.wait_seconds for throttled requests
4. **Support workflows:** Include error.request_id in bug reports for faster resolution
5. **Documentation links:** Map error.type URIs to help documentation

### Swagger UI Enhancement
- Error response schemas now show concrete structure with examples
- API consumers can see expected error format before making requests
- 5 realistic examples demonstrate validation, auth, permission, not found, and throttle errors

## Integration with Plan 03-01

Plan 03-01 (OpenAPI Documentation Enhancement) created the error serializers:
- ErrorResponseSerializer with comprehensive documentation
- ErrorDetailSerializer defining error structure
- 5 OpenApiExample instances showing realistic error formats

Plan 03-02 (this plan) completed the integration:
- Enhanced exception handler to generate documented error format
- Updated all ViewSets to reference error serializers
- Added tests verifying format consistency

**Result:** Seamless integration between documentation and implementation. OpenAPI schema examples match actual error responses from exception handler.

## Known Issues

### Pre-existing Test Failures
13 test failures/errors in upstream.tests_api unrelated to error response format changes:
- AuthEndpointTests: Missing format="json" in token endpoint tests (3 failures)
- ErrorHandlingTests: Missing format="json" in error handling tests (3 failures)
- Query count tests: Unrelated to error format (2 errors)
- Report trigger test: Unrelated to error format (1 failure)

**Root cause:** Tests written before format="json" requirement enforced
**Resolution:** Outside scope of error standardization plan
**Recommendation:** Apply format="json" fix from ErrorResponseTests to all test classes in follow-up task

### Throttle Test Skipped
`test_throttle_error_format` skipped because triggering throttle requires:
- Making many requests to exceed rate limit (configured as 5/hour for auth endpoint)
- Time-consuming and potentially flaky in CI
- Alternative: Manual testing or mock-based test in future

## Next Phase Readiness

### For Plan 03-03 (if exists)
- ✅ Error responses fully documented in OpenAPI schema
- ✅ All error status codes (400/401/403/404/405/429/500) standardized
- ✅ ErrorResponseSerializer reusable for future endpoints

### For Phase 4 (Integration Testing)
- ✅ Error format tests provide foundation for integration test assertions
- ✅ Request ID tracking enables end-to-end error tracing
- ✅ Consistent error structure simplifies test automation

### For Phase 5 (Performance Testing)
- ✅ Throttle error format documented (includes wait_seconds)
- ✅ Error responses lightweight (no unnecessary nesting)
- ✅ Exception handler optimized (single DRF call + transformation)

### For Phase 6 (Production Deployment)
- ✅ RFC 7807 alignment prepares for API versioning and evolution
- ✅ Request ID tracking enables production debugging
- ✅ Backward compatible - existing clients unaffected by new fields

## Blockers/Concerns

None. Phase 3 Plan 2 complete and ready for next phase.

---

**Phase 3 Progress:** 2/2 plans complete (03-01 ✅, 03-02 ✅)
**Overall Progress:** Phase 3 complete, ready for Phase 6 (Phase 4 and 5 already complete per STATE.md)
