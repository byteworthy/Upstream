---
phase: quick-007
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - upstream/middleware.py
  - upstream/settings/base.py
  - docs/API_VERSIONING.md
autonomous: true

must_haves:
  truths:
    - "All API responses include API-Version header"
    - "Versioning strategy is documented for maintainers"
    - "Middleware is registered in MIDDLEWARE stack"
  artifacts:
    - path: "upstream/middleware.py"
      provides: "ApiVersionMiddleware class"
      min_lines: 30
    - path: "upstream/settings/base.py"
      provides: "ApiVersionMiddleware in MIDDLEWARE list"
      contains: "upstream.middleware.ApiVersionMiddleware"
    - path: "docs/API_VERSIONING.md"
      provides: "API versioning strategy documentation"
      min_lines: 50
  key_links:
    - from: "upstream/settings/base.py"
      to: "upstream.middleware.ApiVersionMiddleware"
      via: "MIDDLEWARE configuration"
      pattern: "upstream\\.middleware\\.ApiVersionMiddleware"
---

<objective>
Add API versioning headers to all responses via Django middleware.

Purpose: Establish API versioning infrastructure for future backward-compatible changes and client version tracking.
Output: ApiVersionMiddleware class, MIDDLEWARE configuration, and versioning strategy documentation.
</objective>

<execution_context>
@/home/codespace/.claude/get-shit-done/workflows/execute-plan.md
@/home/codespace/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@upstream/middleware.py
@upstream/settings/base.py
@.planning/codebase/CONVENTIONS.md

**Current Setup:**
- Django 5.2.2 with Django REST Framework 3.15.0
- Existing custom middleware (RequestIdMiddleware, RequestTimingMiddleware, etc.)
- MIDDLEWARE list in upstream/settings/base.py (lines 46-67)
- MiddlewareMixin pattern used for compatibility with both old and new-style middleware
- drf-spectacular configured for OpenAPI schema generation (SPECTACULAR_SETTINGS lines 183-191)

**Pattern:**
- Middleware classes follow Django's MiddlewareMixin pattern
- process_response() method adds response headers
- Type hints used: HttpRequest, HttpResponse
- Logger instantiated: logger = logging.getLogger(__name__)
- Classes documented with docstrings explaining purpose and configuration
</context>

<tasks>

<task type="auto">
  <name>Create ApiVersionMiddleware and configure in settings</name>
  <files>upstream/middleware.py, upstream/settings/base.py</files>
  <action>
1. Add ApiVersionMiddleware class to upstream/middleware.py:
   - Import typing annotations at top if not present
   - Create class inheriting from MiddlewareMixin
   - Implement process_response() to add API-Version header with value "1.0.0"
   - Add docstring explaining purpose: "Middleware to add API version header to all responses for client version tracking and future backward compatibility"
   - Keep version as a class constant: VERSION = "1.0.0" for easy updates
   - Use type hints: def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse
   - Return response object after adding header: response['API-Version'] = self.VERSION

2. Register middleware in upstream/settings/base.py MIDDLEWARE list (lines 46-67):
   - Add "upstream.middleware.ApiVersionMiddleware" near the end of the list
   - Place AFTER django_browser_reload.middleware.BrowserReloadMiddleware (line 65)
   - Place BEFORE django_prometheus.middleware.PrometheusAfterMiddleware (line 66)
   - This ensures version header is added after all processing but captured by Prometheus metrics

Pattern follows existing middleware like RequestIdMiddleware (lines 31-59 in middleware.py) which adds X-Request-Id header in process_response().
  </action>
  <verify>
1. Verify middleware exists: grep -A 15 "class ApiVersionMiddleware" upstream/middleware.py
2. Verify MIDDLEWARE registration: grep "ApiVersionMiddleware" upstream/settings/base.py
3. Test middleware: python manage.py shell -c "from django.test import Client; c = Client(); r = c.get('/health/'); print('API-Version' in r.headers and r['API-Version'] == '1.0.0')"
  </verify>
  <done>
- ApiVersionMiddleware class exists in upstream/middleware.py with VERSION constant and process_response() method
- Middleware registered in MIDDLEWARE list in base.py between browser reload and Prometheus
- Test confirms /health/ endpoint returns API-Version: 1.0.0 header
  </done>
</task>

<task type="auto">
  <name>Document API versioning strategy</name>
  <files>docs/API_VERSIONING.md</files>
  <action>
Create docs/API_VERSIONING.md documenting the versioning strategy:

1. Overview section:
   - Explain header-based versioning approach (API-Version header)
   - Current version: 1.0.0
   - Semantic versioning scheme (MAJOR.MINOR.PATCH)

2. Versioning Policy section:
   - MAJOR: Breaking changes requiring client updates (e.g., removed endpoints, changed response structure)
   - MINOR: Backward-compatible additions (new endpoints, new optional fields)
   - PATCH: Bug fixes and internal changes (no API contract changes)
   - Default version: Latest stable version when no version requested

3. Client Integration section:
   - How to read API-Version from response headers
   - Example: curl -I https://api.example.com/v1/claims | grep API-Version
   - Clients should log/monitor this header to detect version changes

4. Deprecation Process section:
   - Minimum 6 months notice for breaking changes
   - Deprecation warnings in response headers (X-API-Deprecation-Notice)
   - Migration guide provided before major version bumps

5. Implementation Details section:
   - Middleware: ApiVersionMiddleware in upstream/middleware.py
   - Configuration: MIDDLEWARE in upstream/settings/base.py
   - Version constant: ApiVersionMiddleware.VERSION
   - To update: Change VERSION constant and update this doc

6. Future Enhancements section:
   - Accept-Version request header for client-requested versions
   - Per-endpoint version overrides for gradual rollout
   - Version negotiation for multi-version support

Use Markdown with code blocks for examples. Keep tone technical and concise (maintenance doc, not marketing).
  </action>
  <verify>
1. File exists: ls -la docs/API_VERSIONING.md
2. Contains key sections: grep -E "^## " docs/API_VERSIONING.md
3. Contains version reference: grep "1.0.0" docs/API_VERSIONING.md
4. Line count check: wc -l docs/API_VERSIONING.md (should be 50+ lines)
  </verify>
  <done>
- docs/API_VERSIONING.md exists with 6 sections (Overview, Policy, Client Integration, Deprecation, Implementation, Future)
- Documents current version 1.0.0 and semantic versioning scheme
- Includes implementation details (middleware class, configuration location, how to update)
- Provides client integration guidance and deprecation process
  </done>
</task>

</tasks>

<verification>
1. All API responses include API-Version header:
   - curl -I http://localhost:8000/health/ | grep "API-Version: 1.0.0"
   - python manage.py shell -c "from django.test import Client; c = Client(); print(c.get('/api/').headers.get('API-Version'))"

2. Middleware is registered and positioned correctly:
   - grep -n "ApiVersionMiddleware" upstream/settings/base.py (should appear in MIDDLEWARE list)

3. Documentation is comprehensive:
   - docs/API_VERSIONING.md exists and covers all 6 sections
   - grep "ApiVersionMiddleware.VERSION" docs/API_VERSIONING.md (implementation details present)
</verification>

<success_criteria>
- [ ] ApiVersionMiddleware class exists in upstream/middleware.py
- [ ] Middleware registered in MIDDLEWARE list in base.py
- [ ] /health/ endpoint returns API-Version: 1.0.0 header
- [ ] docs/API_VERSIONING.md exists with versioning strategy
- [ ] Documentation includes current version, semantic versioning policy, client integration, deprecation process, implementation details, and future enhancements
- [ ] Plan completes within ~30% context usage (2 simple configuration tasks)
</success_criteria>

<output>
After completion, create `.planning/quick/007-add-api-versioning-headers-via-middlewar/007-SUMMARY.md`
</output>
