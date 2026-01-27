---
phase: quick-011
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - upstream/api/serializers.py
  - upstream/api/tests.py
autonomous: true

must_haves:
  truths:
    - "API responses include _links field with self URL"
    - "List responses include collection and pagination links"
    - "Detail responses include related resource links"
    - "Links are absolute URLs with proper protocol and domain"
  artifacts:
    - path: "upstream/api/serializers.py"
      provides: "HATEOASMixin for link generation"
      min_lines: 50
    - path: "upstream/api/tests.py"
      provides: "HATEOAS link validation tests"
      min_lines: 30
  key_links:
    - from: "upstream/api/serializers.py"
      to: "request.build_absolute_uri"
      via: "URL generation helper"
      pattern: "build_absolute_uri.*reverse"
---

<objective>
Add HATEOAS (Hypermedia as the Engine of Application State) links to all API responses to improve API discoverability and enable client-driven navigation.

Purpose: Enables API consumers to discover available actions and related resources without hardcoding URLs, following REST best practices and improving developer experience.

Output: All API responses include a `_links` field with `self`, `collection`, and related resource URLs.
</objective>

<execution_context>
@/home/codespace/.claude/get-shit-done/workflows/execute-plan.md
@/home/codespace/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@upstream/api/serializers.py
@upstream/api/views.py
@upstream/settings/base.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create HATEOAS link generation infrastructure</name>
  <files>upstream/api/serializers.py</files>
  <action>
Add HATEOAS link generation to all serializers using a reusable mixin pattern.

1. Create HATEOASMixin class at the top of serializers.py (after imports):
   - Add _links field using SerializerMethodField
   - Implement get__links(self, obj) method that:
     - Gets request from context: self.context.get('request')
     - Generates self URL using reverse(viewname, kwargs={'pk': obj.pk})
     - Builds absolute URI with request.build_absolute_uri()
     - Returns dict with 'self' key containing absolute URL

2. Add collection link support:
   - Detect list vs detail view from request.parser_context['view']
   - For list views: add 'collection' link (current URL without pk)
   - For detail views: add 'collection' link pointing to list endpoint

3. Add pagination link support:
   - Check if response has next/previous pagination
   - Add 'next' and 'previous' links if available from view.paginator

4. Add related resource links for each serializer:
   - UploadSerializer: add 'claims' link -> /api/v1/claims/?upload={id}
   - ClaimRecordSerializer: add 'upload' link -> /api/v1/uploads/{upload_id}/
   - DriftEventSerializer: add 'report' link -> /api/v1/reports/{report_run}/
   - ReportRunSerializer: add 'drift-events' link -> /api/v1/drift-events/?report_run={id}
   - AlertEventSerializer: add 'drift-event' link if drift_event_id exists

5. Update all ModelSerializer classes to inherit from HATEOASMixin:
   - CustomerSerializer(HATEOASMixin, serializers.ModelSerializer)
   - SettingsSerializer(HATEOASMixin, serializers.ModelSerializer)
   - UploadSerializer(HATEOASMixin, serializers.ModelSerializer)
   - ClaimRecordSerializer(HATEOASMixin, serializers.ModelSerializer)
   - DriftEventSerializer(HATEOASMixin, serializers.ModelSerializer)
   - ReportRunSerializer(HATEOASMixin, serializers.ModelSerializer)
   - AlertEventSerializer(HATEOASMixin, serializers.ModelSerializer)
   - PayerMappingSerializer(HATEOASMixin, serializers.ModelSerializer)
   - CPTGroupMappingSerializer(HATEOASMixin, serializers.ModelSerializer)

6. Add Meta.fields update for each serializer:
   - Append "_links" to fields list in Meta class

Why this approach:
- Mixin pattern: DRY principle, single implementation reused across all serializers
- Request context: Required for build_absolute_uri to generate proper protocol/domain
- Related resource links: Provides navigability between related entities
- Pagination links: Enables client-side pagination without URL construction

Do NOT use hardcoded URLs or relative paths - all links must be absolute URLs.
Do NOT add links to summary serializers (UploadSummarySerializer, ClaimRecordSummarySerializer) - they're for lightweight listings only.
  </action>
  <verify>
python manage.py shell -c "from upstream.api.serializers import UploadSerializer; from upstream.models import Upload; from rest_framework.request import Request; from django.test import RequestFactory; factory = RequestFactory(); request = Request(factory.get('/api/v1/uploads/1/')); u = Upload.objects.first(); s = UploadSerializer(u, context={'request': request}); print('_links' in s.data); print(s.data.get('_links', {}).get('self', '').startswith('http'))"

Both outputs should be True, confirming:
1. _links field exists in serialized data
2. self link is an absolute URL starting with http
  </verify>
  <done>
All serializers include _links field with absolute URLs. HATEOASMixin implements self, collection, pagination, and related resource link generation. Request context properly passes through serializer initialization.
  </done>
</task>

<task type="auto">
  <name>Task 2: Add comprehensive HATEOAS tests</name>
  <files>upstream/api/tests.py</files>
  <action>
Add test suite validating HATEOAS link generation across all ViewSets.

1. Create test class TestHATEOASLinks(APITestCase) at end of tests.py:

2. Add setUp method:
   - Create test customer, user with customer_admin role
   - Authenticate client with JWT token
   - Create test fixtures (upload, claim, report, drift event)

3. Add test_upload_detail_links:
   - GET /api/v1/uploads/{id}/
   - Assert response contains _links field
   - Assert _links.self matches /api/v1/uploads/{id}/
   - Assert _links.collection matches /api/v1/uploads/
   - Assert _links.claims matches /api/v1/claims/?upload={id}
   - Assert all URLs are absolute (start with http:// or https://)

4. Add test_upload_list_links:
   - GET /api/v1/uploads/
   - Assert each result contains _links field
   - Assert _links.self is unique per object
   - Assert response contains next/previous links if paginated

5. Add test_claim_detail_links:
   - GET /api/v1/claims/{id}/
   - Assert _links.self matches /api/v1/claims/{id}/
   - Assert _links.upload matches /api/v1/uploads/{upload_id}/
   - Verify upload link points to correct related upload

6. Add test_drift_event_detail_links:
   - GET /api/v1/drift-events/{id}/
   - Assert _links.report matches /api/v1/reports/{report_run}/
   - Verify report link points to correct related report

7. Add test_report_detail_links:
   - GET /api/v1/reports/{id}/
   - Assert _links.drift-events matches /api/v1/drift-events/?report_run={id}

8. Add test_pagination_links:
   - Create 60 uploads (exceeds PAGE_SIZE of 50)
   - GET /api/v1/uploads/?page=1
   - Assert response._links.next exists
   - GET /api/v1/uploads/?page=2
   - Assert response._links.previous exists
   - Assert both are absolute URLs

9. Add test_links_respect_tenant_isolation:
   - Create uploads for two different customers
   - Authenticate as customer1 user
   - GET /api/v1/uploads/
   - Assert all _links.self point to customer1's uploads only
   - Verify no leakage of customer2 URLs

Test with: pytest upstream/api/tests.py::TestHATEOASLinks -v

Expected output: 9 tests pass, confirming HATEOAS links work across all ViewSets with proper absolute URLs and tenant isolation.
  </action>
  <verify>
pytest upstream/api/tests.py::TestHATEOASLinks -v --tb=short

All 9 tests should pass with output showing:
- test_upload_detail_links PASSED
- test_upload_list_links PASSED
- test_claim_detail_links PASSED
- test_drift_event_detail_links PASSED
- test_report_detail_links PASSED
- test_pagination_links PASSED
- test_links_respect_tenant_isolation PASSED
  </verify>
  <done>
Test suite validates HATEOAS link generation with 9 passing tests covering detail views, list views, related resources, pagination, and tenant isolation. All links are absolute URLs with proper protocol and domain.
  </done>
</task>

<task type="auto">
  <name>Task 3: Verify OpenAPI schema includes link documentation</name>
  <files>upstream/api/serializers.py</files>
  <action>
Add OpenAPI documentation for _links field so it appears in Swagger UI.

1. Add drf_spectacular imports at top of serializers.py:
   from drf_spectacular.utils import extend_schema_field, extend_schema_serializer
   from drf_spectacular.types import OpenApiTypes

2. Decorate HATEOASMixin.get__links method with OpenAPI schema:
   @extend_schema_field({
       'type': 'object',
       'properties': {
           'self': {'type': 'string', 'format': 'uri', 'example': 'http://localhost:8000/api/v1/uploads/123/'},
           'collection': {'type': 'string', 'format': 'uri', 'example': 'http://localhost:8000/api/v1/uploads/'},
           'next': {'type': 'string', 'format': 'uri', 'example': 'http://localhost:8000/api/v1/uploads/?page=2'},
           'previous': {'type': 'string', 'format': 'uri', 'example': 'http://localhost:8000/api/v1/uploads/?page=1'},
       },
       'description': 'HATEOAS links for resource navigation and discoverability'
   })
   def get__links(self, obj):
       ...

3. Test OpenAPI schema generation:
   python manage.py spectacular --color --file schema.yml --validate

4. Verify _links appears in schema:
   grep -A 10 "_links" schema.yml

Expected output: _links field documented as object with self, collection, next, previous properties, all typed as URI format strings.

Why this matters:
- API documentation auto-generates link structure
- Swagger UI shows available navigation options
- Client SDK generators include link types
- Developers see HATEOAS pattern in docs

Do NOT commit schema.yml (it's just for verification).
  </action>
  <verify>
python manage.py spectacular --color --validate 2>&1 | grep -i "error"

Should output nothing (no errors), confirming OpenAPI schema validates successfully with _links field properly documented.

python manage.py spectacular --file /tmp/schema-test.yml && grep -c "_links" /tmp/schema-test.yml

Should output a number > 0, confirming _links field appears in generated schema.
  </verify>
  <done>
OpenAPI schema includes _links field documentation with proper type annotations (object with URI-formatted properties). Schema validation passes without errors. Swagger UI will display HATEOAS links in API responses.
  </done>
</task>

</tasks>

<verification>
Run full test suite to ensure HATEOAS doesn't break existing functionality:

```bash
pytest upstream/api/tests.py -v --tb=short
```

Spot check API responses in shell:

```bash
python manage.py runserver
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/v1/uploads/ | jq '.results[0]._links'
```

Expected output:
```json
{
  "self": "http://localhost:8000/api/v1/uploads/123/",
  "collection": "http://localhost:8000/api/v1/uploads/",
  "claims": "http://localhost:8000/api/v1/claims/?upload=123"
}
```
</verification>

<success_criteria>
- All ModelSerializers include _links field in Meta.fields
- HATEOASMixin generates self, collection, and related resource links
- All links are absolute URLs with proper protocol and domain
- List views include pagination links (next/previous) when applicable
- Related resource links connect entities (upload->claims, claim->upload, etc)
- 9 new HATEOAS tests pass validating link generation
- OpenAPI schema documents _links field structure
- Existing tests continue passing (no regressions)
- API responses follow HATEOAS principles for improved discoverability
</success_criteria>

<output>
After completion, create `.planning/quick/011-add-hateoas-links-to-api-responses-for/011-SUMMARY.md`
</output>
