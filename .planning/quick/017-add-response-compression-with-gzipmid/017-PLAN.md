---
phase: quick-017
plan: 017
type: execute
wave: 1
depends_on: []
files_modified:
  - upstream/middleware.py
  - upstream/settings/base.py
  - upstream/tests/test_middleware.py
autonomous: true

must_haves:
  truths:
    - "Responses larger than 500 bytes are compressed with gzip"
    - "Responses smaller than 500 bytes are not compressed (overhead)"
    - "Compression works for all content types (HTML, JSON, CSS, JS)"
  artifacts:
    - path: "upstream/middleware.py"
      provides: "Custom GZipMiddleware with min_length=500 configuration"
      contains: "class ConfigurableGZipMiddleware"
    - path: "upstream/settings/base.py"
      provides: "GZipMiddleware configuration in MIDDLEWARE list"
      contains: "ConfigurableGZipMiddleware"
    - path: "upstream/tests/test_middleware.py"
      provides: "Compression behavior tests"
      contains: "test_gzip"
  key_links:
    - from: "upstream/settings/base.py"
      to: "upstream.middleware.ConfigurableGZipMiddleware"
      via: "MIDDLEWARE list"
      pattern: "upstream\\.middleware\\.ConfigurableGZipMiddleware"
---

<objective>
Configure response compression with custom min_length=500 to optimize bandwidth while avoiding compression overhead on small responses.

Purpose: Reduce bandwidth usage by 60-80% for large API responses while skipping compression for small responses where the overhead exceeds the benefit.

Output: Configurable GZipMiddleware with min_length=500 setting, integrated into middleware stack with test coverage.
</objective>

<execution_context>
@/home/codespace/.claude/get-shit-done/workflows/execute-plan.md
@/home/codespace/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@upstream/settings/base.py
@upstream/middleware.py
</context>

<tasks>

<task type="auto">
  <name>Create configurable GZipMiddleware with min_length=500</name>
  <files>upstream/middleware.py</files>
  <action>
Add ConfigurableGZipMiddleware class to upstream/middleware.py:

1. Import Django's GZipMiddleware at the top
2. Create ConfigurableGZipMiddleware that subclasses Django's GZipMiddleware
3. Override __init__ to accept min_length and compresslevel parameters
4. Set self.min_length from parameter (default 500)
5. Set self.compresslevel from parameter (default 6 for balanced compression)
6. Add docstring explaining configuration and rationale for min_length=500

Rationale for 500 bytes:
- Django's default is 200 bytes (too aggressive)
- Gzip overhead is ~10-20 bytes of headers
- For responses < 500 bytes, compression savings are minimal and CPU cost isn't worth it
- For responses > 500 bytes (typical API JSON), compression saves 60-80%

Implementation note: Django's GZipMiddleware hardcodes min_length=200, so we need to override __init__ and set instance attribute before calling super().__init__().
  </action>
  <verify>
grep -A 5 "class ConfigurableGZipMiddleware" upstream/middleware.py
grep "min_length" upstream/middleware.py
  </verify>
  <done>
ConfigurableGZipMiddleware exists in upstream/middleware.py with configurable min_length parameter set to 500 by default.
  </done>
</task>

<task type="auto">
  <name>Update MIDDLEWARE to use ConfigurableGZipMiddleware</name>
  <files>upstream/settings/base.py</files>
  <action>
Update upstream/settings/base.py MIDDLEWARE list:

1. Replace "django.middleware.gzip.GZipMiddleware" (line 53)
2. With "upstream.middleware.ConfigurableGZipMiddleware"
3. Position remains same (after SecurityMiddleware, before CorsMiddleware)
4. Update comment to reflect min_length=500 configuration
5. Keep comment about 60-80% size reduction

The middleware will use the default min_length=500 defined in the class. No additional settings needed.
  </action>
  <verify>
grep "ConfigurableGZipMiddleware" upstream/settings/base.py
grep -B 1 "ConfigurableGZipMiddleware" upstream/settings/base.py | grep "QW-3"
  </verify>
  <done>
MIDDLEWARE list uses upstream.middleware.ConfigurableGZipMiddleware instead of django.middleware.gzip.GZipMiddleware, with updated comment.
  </done>
</task>

<task type="auto">
  <name>Add compression tests for min_length=500 behavior</name>
  <files>upstream/tests/test_middleware.py</files>
  <action>
Add compression tests to upstream/tests/test_middleware.py:

1. Add test_gzip_compression_large_response:
   - Create response with 1000 bytes of content
   - Set Accept-Encoding: gzip header
   - Assert response has Content-Encoding: gzip
   - Assert compressed content is smaller than original

2. Add test_gzip_no_compression_small_response:
   - Create response with 300 bytes of content (< 500)
   - Set Accept-Encoding: gzip header
   - Assert response does NOT have Content-Encoding: gzip
   - Assert content is unchanged

3. Add test_gzip_compression_json_api:
   - Make API request to /api/v1/health/ (returns JSON)
   - Set Accept-Encoding: gzip header
   - Assert response has Content-Encoding: gzip
   - Assert valid JSON after decompression

Use Django's RequestFactory for request creation, TestCase for test structure.
  </action>
  <verify>
pytest upstream/tests/test_middleware.py::test_gzip_compression_large_response -v
pytest upstream/tests/test_middleware.py::test_gzip_no_compression_small_response -v
pytest upstream/tests/test_middleware.py::test_gzip_compression_json_api -v
  </verify>
  <done>
Three compression tests pass: large responses are compressed, small responses (< 500 bytes) are not compressed, API JSON responses are compressed.
  </done>
</task>

</tasks>

<verification>
Manual verification:
1. Start dev server: `python manage.py runserver`
2. Test large response: `curl -H "Accept-Encoding: gzip" http://localhost:8000/api/v1/claims/ -v | grep "Content-Encoding: gzip"`
3. Test small response: `curl -H "Accept-Encoding: gzip" http://localhost:8000/api/v1/health/ -v | grep -c "Content-Encoding: gzip"` (should be 0 if health response < 500 bytes)
4. Check compression ratio: Compare Content-Length with and without gzip
</verification>

<success_criteria>
- [ ] ConfigurableGZipMiddleware class exists with min_length=500 default
- [ ] MIDDLEWARE list uses ConfigurableGZipMiddleware
- [ ] Three compression tests pass (large, small, JSON API)
- [ ] All existing middleware tests still pass
- [ ] pytest upstream/tests/test_middleware.py passes
- [ ] Responses > 500 bytes are compressed, responses < 500 bytes are not
</success_criteria>

<output>
After completion, create `.planning/quick/017-add-response-compression-with-gzipmid/017-SUMMARY.md`
</output>
