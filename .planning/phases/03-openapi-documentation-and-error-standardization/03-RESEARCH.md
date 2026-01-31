# Phase 3: OpenAPI Documentation & Error Standardization - Research

**Researched:** 2026-01-31
**Domain:** OpenAPI documentation generation and error response standardization
**Confidence:** HIGH

## Summary

This phase requires implementing comprehensive OpenAPI documentation via drf-spectacular and standardizing error responses across all API endpoints. The project already has drf-spectacular 0.27.2 installed and integrated with Django REST Framework 3.15, with a custom exception handler providing basic error standardization.

The standard approach is:
1. Enhance `SPECTACULAR_SETTINGS` with detailed configuration (operation tags, components organization, security definitions)
2. Add `@extend_schema` and `@extend_schema_view` decorators to all ViewSets for complete endpoint documentation
3. Document all error response codes (400, 401, 403, 404, 429, 500) with examples using the `responses` parameter
4. Implement RFC 7807 Problem Details format for consistency with modern API standards
5. Add request/response examples to serializers and endpoints via `@extend_schema_serializer` and `OpenApiExample`
6. Define tags at the root level to control schema organization and endpoint grouping

The current custom exception handler (`upstream/api/exceptions.py`) provides a baseline error format with `error.code`, `error.message`, and `error.details` fields. Phase 3 should enhance this to document all error types in OpenAPI schema and optionally adopt RFC 7807 structure for maximum interoperability.

**Primary recommendation:** Use drf-spectacular's `@extend_schema` decorators systematically across all ViewSets, organize endpoints with well-defined tags, document all error responses with status codes and examples, and enhance the custom exception handler to align error responses with RFC 7807 Problem Details format for better API consumer experience.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| drf-spectacular | 0.27.2 | OpenAPI 3.0.3 schema generation | Industry standard for Django REST Framework; auto-detects schema from code |
| djangorestframework | 3.15.0 | REST API framework | Provides exception handling, authentication, serializers that drf-spectacular documents |
| Django | 5.2.2 | Web framework | drf-spectacular integrates deeply with Django's ORM and serialization |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| drf-standardized-errors | Latest | Standardized error response format | Optional; provides RFC 7807 integration if stricter validation error docs needed |
| drf-spectacular-sidecar | Latest | Offline UI static files | For air-gapped environments; project uses online CDN by default |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| drf-spectacular | Swagger UI hand-maintained | Manual schema maintenance; errors, outdated docs, no automation |
| drf-spectacular | swagger2 (deprecated) | Swagger 2.0 is obsolete; OpenAPI 3.0 provides better security, parameter docs |
| Custom error format | RFC 7807 Problem Details only | RFC 7807 is more verbose; current format is simpler but compatible with RFC 7807 structure |
| @extend_schema decorators | Comment-based docs | Comments don't auto-generate schema; higher maintenance; easier to become stale |

**Installation:**
```bash
pip install drf-spectacular~=0.27.0  # Already installed
# Optional for RFC 7807 integration:
pip install drf-standardized-errors  # For automatic error code documentation
```

## Architecture Patterns

### Recommended Project Structure
```
upstream/api/
├── views.py                    # ViewSets with @extend_schema decorators
├── serializers.py              # Serializers with @extend_schema_serializer and examples
├── exceptions.py               # Custom exception handler with RFC 7807-aligned format
├── permissions.py              # Existing permission classes
├── filters.py                  # FilterSet classes with descriptions
├── schema_extensions.py        # (Optional) Custom AutoSchema or OpenApiExtension classes
└── test_openapi.py             # Tests verifying schema completeness

upstream/settings/base.py
├── SPECTACULAR_SETTINGS         # Comprehensive configuration
└── REST_FRAMEWORK['EXCEPTION_HANDLER']  # Point to exceptions.custom_exception_handler
```

### Pattern 1: Complete ViewSet Documentation with @extend_schema_view
**What:** Apply decorators to ViewSets to document all actions (list, retrieve, create, update, custom actions) with summaries, descriptions, parameters, and error responses
**When to use:** For all ViewSets with endpoints that users call
**Example:**
```python
# Source: https://drf-spectacular.readthedocs.io/en/latest/customization.html
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiExample, OpenApiParameter
from rest_framework import viewsets

@extend_schema_view(
    list=extend_schema(
        summary="List claim records",
        description="Retrieve paginated claim records filtered by status, date range, or payer",
        tags=["Claims"],
        parameters=[
            OpenApiParameter(
                name="status",
                description="Filter by claim status (denied, approved, pending)",
                required=False,
            ),
            OpenApiParameter(
                name="min_amount",
                description="Filter by minimum allowed amount",
                required=False,
            ),
        ],
        responses={
            200: ClaimRecordSerializer(many=True),
            400: OpenApiTypes.OBJECT,  # Validation error
            401: OpenApiTypes.OBJECT,  # Authentication required
            403: OpenApiTypes.OBJECT,  # Permission denied
        }
    ),
    retrieve=extend_schema(
        summary="Get claim record details",
        description="Retrieve a single claim record by ID with all associated metadata",
        tags=["Claims"],
        responses={
            200: ClaimRecordSerializer(),
            404: OpenApiTypes.OBJECT,  # Not found
        }
    ),
    create=extend_schema(
        summary="Create claim record",
        description="Create a new claim record (admin only)",
        tags=["Claims"],
        request=ClaimRecordCreateSerializer,
        responses={
            201: ClaimRecordSerializer(),
            400: OpenApiTypes.OBJECT,  # Validation error
            403: OpenApiTypes.OBJECT,  # Permission denied
        }
    ),
)
class ClaimRecordViewSet(viewsets.ModelViewSet):
    queryset = ClaimRecord.objects.all()
    serializer_class = ClaimRecordSerializer
```

### Pattern 2: Document Custom Actions with Error Responses
**What:** Apply `@extend_schema` decorator to custom `@action` methods, documenting all possible error codes
**When to use:** For any custom `@action` method that's user-facing
**Example:**
```python
# Source: https://drf-spectacular.readthedocs.io/en/latest/customization.html
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema

@extend_schema(
    summary="Get operator feedback",
    description="Retrieve paginated operator feedback for alerts in this customer",
    tags=["Alerts"],
    responses={
        200: OperatorFeedbackSerializer(many=True),
        401: OpenApiTypes.OBJECT,  # Not authenticated
        403: OpenApiTypes.OBJECT,  # Not a customer member
    }
)
@action(detail=False, methods=['get'])
def feedback(self, request):
    """List operator feedback with pagination."""
    # Implementation here
    pass
```

### Pattern 3: Add Examples to Serializers
**What:** Document request/response examples using `@extend_schema_serializer` and `OpenApiExample`
**When to use:** For all serializers that appear in POST/PUT/PATCH requests or in response examples
**Example:**
```python
# Source: https://drf-spectacular.readthedocs.io/en/latest/customization.html
from drf_spectacular.utils import extend_schema_serializer, OpenApiExample

@extend_schema_serializer(
    examples=[
        OpenApiExample(
            name="Valid claim record",
            description="Example of a typical approved claim",
            value={
                "id": 123,
                "claim_number": "CLM-2026-00001",
                "payer": "Aetna",
                "status": "approved",
                "allowed_amount": 500.00,
                "decided_date": "2026-01-31",
            }
        ),
        OpenApiExample(
            name="Denied claim",
            description="Example of a denied claim",
            value={
                "id": 124,
                "claim_number": "CLM-2026-00002",
                "payer": "United",
                "status": "denied",
                "allowed_amount": 0.00,
                "decided_date": "2026-01-30",
            }
        ),
    ]
)
class ClaimRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClaimRecord
        fields = ['id', 'claim_number', 'payer', 'status', 'allowed_amount', 'decided_date']
```

### Pattern 4: Define Error Response Schema
**What:** Create reusable error response schemas that are referenced by all error responses
**When to use:** For consistent documentation of all error responses
**Example:**
```python
# Source: RFC 7807 - https://datatracker.ietf.org/doc/html/rfc7807
# In serializers.py or a new schema_responses.py file:

from rest_framework import serializers

class ErrorDetailSerializer(serializers.Serializer):
    """Error response in RFC 7807 Problem Details format"""
    type = serializers.URLField(
        required=False,
        help_text="A URI reference identifying the problem type"
    )
    title = serializers.CharField(
        required=False,
        help_text="A short, human-readable summary of the problem type"
    )
    status = serializers.IntegerField(
        help_text="The HTTP status code"
    )
    detail = serializers.CharField(
        help_text="A human-readable explanation of the problem"
    )
    instance = serializers.URLField(
        required=False,
        help_text="A URI reference identifying this specific occurrence"
    )

# Then reference in @extend_schema:
@extend_schema(
    responses={
        400: ErrorDetailSerializer(),
        401: ErrorDetailSerializer(),
        403: ErrorDetailSerializer(),
    }
)
```

### Pattern 5: Configure SPECTACULAR_SETTINGS Comprehensively
**What:** Set up SPECTACULAR_SETTINGS with tags, server URLs, security definitions, and schema customization
**When to use:** Once, during setup; affects all generated schemas
**Example:**
```python
# Source: https://drf-spectacular.readthedocs.io/en/latest/customization.html
# In upstream/settings/base.py:

SPECTACULAR_SETTINGS = {
    # Metadata
    "TITLE": "Upstream API",
    "DESCRIPTION": "Early-warning intelligence for healthcare revenue operations",
    "VERSION": "1.0.0",

    # Servers
    "SERVERS": [
        {"url": "https://api.upstream.example.com", "description": "Production"},
        {"url": "http://localhost:8000", "description": "Development"},
    ],

    # Tags (operation grouping)
    "TAGS": [
        {"name": "Customers", "description": "Customer management endpoints"},
        {"name": "Claims", "description": "Claim record operations"},
        {"name": "Alerts", "description": "Alert event management"},
        {"name": "Reports", "description": "Report generation and retrieval"},
    ],

    # Security schemes
    "SECURITY": [
        {"Bearer": []}
    ],

    # Schema postprocessing
    "POSTPROCESSING_HOOKS": [
        "upstream.api.schema_extensions.fix_error_responses"
    ],

    # Component naming for enums with conflicts
    "ENUM_ADD_EXPLICIT_BLANK_NULL_CHOICE": False,

    # UI and rendering
    "SERVE_INCLUDE_SCHEMA": False,  # Don't serve /schema/ endpoint
    "SERVE_PERMISSIONS": ["rest_framework.permissions.IsAdminUser"],
}
```

### Pattern 6: Document Error Responses Comprehensively
**What:** Define all possible error codes and status codes for each endpoint
**When to use:** For every endpoint that can return errors
**Standard status codes:**
- 400: Validation error (malformed input, invalid field values)
- 401: Authentication failed (missing or invalid token)
- 403: Permission denied (authenticated but lacks authorization)
- 404: Not found (resource doesn't exist)
- 429: Too many requests (rate limited)
- 500: Server error (unhandled exception)

**Example:**
```python
from drf_spectacular.types import OpenApiTypes

@extend_schema(
    summary="Update claim record",
    description="Update an existing claim record",
    tags=["Claims"],
    request=ClaimRecordUpdateSerializer,
    responses={
        200: ClaimRecordSerializer(),
        400: OpenApiTypes.OBJECT,  # Invalid field values
        401: OpenApiTypes.OBJECT,  # Missing authentication
        403: OpenApiTypes.OBJECT,  # Not authorized to update
        404: OpenApiTypes.OBJECT,  # Record not found
        429: OpenApiTypes.OBJECT,  # Too many requests
    }
)
@action(detail=True, methods=['patch'])
def partial_update(self, request, pk=None):
    """Update specific fields of a claim record."""
    pass
```

### Anti-Patterns to Avoid
- **Omitting error responses:** Every endpoint should document all possible errors (400, 401, 403, 404, 429)
- **Using generic "Object" for all errors:** Create specific error schemas so consumers can parse responses
- **Forgetting to add tags:** Endpoints without tags are harder to navigate in documentation
- **Not documenting custom actions:** Custom @action methods need @extend_schema decorators like standard list/retrieve
- **Inconsistent error format:** All endpoints should return errors in the same structure
- **Missing examples:** Endpoints without examples are harder for consumers to understand

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Generate OpenAPI schema from views | Custom schema generator or manual YAML | drf-spectacular with @extend_schema | Automatic detection from DRF code; stays in sync as code changes; comprehensive |
| Document all error responses | Manual error code list or comments | @extend_schema with responses parameter | Auto-validates against actual exception handler; prevents outdated docs; type-safe |
| Add request/response examples | Hard-code JSON in docstrings | @extend_schema_serializer with OpenApiExample | Maintainable, reusable, can be validated against serializers |
| Organize endpoints in documentation | Manual grouping or alphabetical | drf-spectacular tags with SPECTACULAR_SETTINGS | Automatic grouping; affects code organization; consistent with API semantics |
| Validate error response format | Manual testing or integration tests | Custom exception handler + @extend_schema | Enforces consistent format; documents expectations; catchable at schema generation time |
| Document field constraints | Docstrings or comments | Serializer help_text + max_length, validators | Serializer knows constraints; auto-documents in schema; validated at request time |

**Key insight:** drf-spectacular is purpose-built to keep documentation synchronized with implementation. Manual approaches diverge over time; automated approaches stay in sync.

## Common Pitfalls

### Pitfall 1: Incomplete Error Response Documentation
**What goes wrong:** OpenAPI schema doesn't document all error codes (400, 401, 403, 404, 429); consumers can't handle errors properly
**Why it happens:** Developers only document happy path (200 response); error cases are afterthought or considered "obvious"
**How to avoid:** For every endpoint, explicitly list all possible status codes in @extend_schema responses parameter, including 400, 401, 403, 404, 429
**Warning signs:** API documentation missing error codes; support tickets asking "what should I do if I get a 403?"; API client code has no error handling

### Pitfall 2: Custom Actions Not Documented
**What goes wrong:** Custom @action methods have no @extend_schema decorator; OpenAPI schema is incomplete; developers don't know endpoints exist
**Why it happens:** Developers focus on list/retrieve/create/update/delete (automatically documented); forget that custom actions also need documentation
**How to avoid:** Apply @extend_schema decorator to every @action method with summary, description, and responses
**Warning signs:** schema.yaml missing endpoints that exist in code; developers discover endpoints by reading code instead of documentation

### Pitfall 3: Error Response Format Mismatch
**What goes wrong:** Custom exception handler returns one format; @extend_schema documents a different format; real errors don't match documentation
**Why it happens:** Exception handler and schema documentation written at different times; no validation that they match
**How to avoid:** Update exception handler to match documented error format; add tests verifying actual error responses match schema
**Warning signs:** Swagger UI shows one error format; actual API returns different format; API client parsing breaks

### Pitfall 4: Inconsistent Tag Usage
**What goes wrong:** Some endpoints use tag "Alerts", others use "alerts", "alert-events"; schema tools can't group endpoints consistently
**Why it happens:** Developers add tags ad-hoc without checking what other endpoints use
**How to avoid:** Define all tags in SPECTACULAR_SETTINGS["TAGS"] once; use exact same strings in @extend_schema decorators
**Warning signs:** Swagger UI shows duplicate sections (e.g., "Alerts" and "alerts" as separate groups); tag counts in schema don't match defined tags

### Pitfall 5: Missing Examples in Schema
**What goes wrong:** Endpoints have no examples; documentation tool can't show request/response samples; developers resort to trial-and-error
**Why it happens:** Adding examples requires extra work; seems optional if schema is clear
**How to avoid:** Add @extend_schema_serializer with OpenApiExample to all serializers; add examples parameter to @extend_schema
**Warning signs:** Documentation lacks "Try it out" examples; API client generators produce incomplete code; support requests ask "how do I format this?"

### Pitfall 6: Not Using @extend_schema_field for Custom Fields
**What goes wrong:** Custom serializer fields (computed, custom validators) aren't documented in schema; type appears as generic object
**Why it happens:** drf-spectacular can introspect built-in fields but needs hints for custom ones
**How to avoid:** For custom serializer fields, apply @extend_schema_field decorator specifying OpenApiTypes
**Warning signs:** Schema shows custom fields as generic objects instead of strings/numbers/booleans; API client doesn't generate proper code for custom fields

### Pitfall 7: Over-Decorating Simple Endpoints
**What goes wrong:** Developers add extensive @extend_schema to simple list() endpoints; schema decorators become maintenance burden
**Why it happens:** Misunderstanding of when decoration is necessary; treating all endpoints the same
**How to avoid:** Use decorators judiciously; only override auto-detected behavior when needed; omit decorator if defaults are correct
**Warning signs:** Decorators repeat what code already shows; diff diffs are large but documentation barely changes; "DRY" violations in schema code

### Pitfall 8: Throttle Status Code (429) Not Documented
**What goes wrong:** API has throttling (rate limits) but endpoints don't document 429 status code; client doesn't know to retry
**Why it happens:** Throttling is configured globally; developers don't think to document it per-endpoint
**How to avoid:** Add 429 to responses in ALL user-facing endpoints since throttling is applied globally
**Warning signs:** Throttling exists but no 429 in schema; clients get 429 responses but no error handler

## Code Examples

Verified patterns from official sources:

### Minimal Viable Phase 3 Setup
```python
# Source: https://drf-spectacular.readthedocs.io/en/latest/customization.html

# Step 1: Update settings/base.py
SPECTACULAR_SETTINGS = {
    "TITLE": "Upstream API",
    "DESCRIPTION": "Early-warning intelligence for healthcare revenue operations",
    "VERSION": "1.0.0",
    "TAGS": [
        {"name": "Customers", "description": "Customer management"},
        {"name": "Claims", "description": "Claim records"},
        {"name": "Alerts", "description": "Alert events"},
        {"name": "Reports", "description": "Report generation"},
    ],
}

# Step 2: Decorate ViewSet
from drf_spectacular.utils import extend_schema, extend_schema_view
from drf_spectacular.types import OpenApiTypes

@extend_schema_view(
    list=extend_schema(
        summary="List claims",
        tags=["Claims"],
        responses={200: ClaimRecordSerializer(many=True), 401: OpenApiTypes.OBJECT}
    ),
    retrieve=extend_schema(
        summary="Get claim",
        tags=["Claims"],
        responses={200: ClaimRecordSerializer(), 404: OpenApiTypes.OBJECT}
    ),
)
class ClaimRecordViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ClaimRecord.objects.all()
    serializer_class = ClaimRecordSerializer
```

### Document All Error Codes Systematically
```python
# Source: RFC 7807 + drf-spectacular docs
from drf_spectacular.types import OpenApiTypes

def error_responses():
    """Standard error responses for all endpoints"""
    return {
        400: OpenApiTypes.OBJECT,  # Validation error
        401: OpenApiTypes.OBJECT,  # Authentication failed
        403: OpenApiTypes.OBJECT,  # Permission denied
        404: OpenApiTypes.OBJECT,  # Not found
        429: OpenApiTypes.OBJECT,  # Throttled
    }

@extend_schema(
    summary="Create claim",
    tags=["Claims"],
    request=ClaimRecordCreateSerializer,
    responses={201: ClaimRecordSerializer(), **error_responses()}
)
def create(self, request):
    pass
```

### Add Examples to Serializers
```python
# Source: https://drf-spectacular.readthedocs.io/en/latest/customization.html
from drf_spectacular.utils import extend_schema_serializer, OpenApiExample

@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "approved_claim",
            summary="Approved claim",
            value={
                "id": 1,
                "claim_number": "CLM-2026-001",
                "status": "approved",
                "allowed_amount": 500.00,
            }
        ),
    ]
)
class ClaimRecordSerializer(serializers.ModelSerializer):
    pass
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Swagger 2.0 (manual YAML) | OpenAPI 3.0 via drf-spectacular | 2017 | Better security, parameter docs, reusable components |
| Stateless error responses | Error codes with retry hints (429 with Retry-After) | 2020s | Clients can implement intelligent retry logic |
| No error examples | Examples + error schemas in OpenAPI | drf-spectacular 0.20+ (2021) | Clients generate better error handling code |
| Generic error format | Structured errors (code, message, details) | 2010s onwards | Easier parsing; clients can show specific error messages |
| No tag organization | Tags in SPECTACULAR_SETTINGS | drf-spectacular 0.15+ (2020) | Better documentation organization |
| Comments for docs | @extend_schema decorators | drf-spectacular 0.1+ (2019) | Stays in sync; validated by tools |

**Deprecated/outdated:**
- **swagger2 library**: Generates Swagger 2.0; OpenAPI 3.0 is standard now
- **Manual YAML/JSON schemas**: drf-spectacular auto-generation is standard in Django ecosystem
- **Generic "error" response format**: RFC 7807 Problem Details is emerging standard
- **Unstructured error messages**: Field-level errors with codes are standard in modern APIs

## Open Questions

Things that couldn't be fully resolved:

1. **Error response schema documentation in OpenAPI**
   - What we know: @extend_schema responses can reference serializers; drf-spectacular auto-documents structure
   - What's unclear: Whether to document error responses with custom error serializers or generic object
   - Recommendation: Create error response schema (RFC 7807-like) and reference it in all endpoints; easier to maintain and test than per-endpoint error docs

2. **RFC 7807 vs custom error format**
   - What we know: Current exception handler uses `{"error": {"code": "", "message": "", "details": null}}` format; RFC 7807 uses `{"type": "", "title": "", "status": "", "detail": "", "instance": ""}`
   - What's unclear: Whether to migrate to RFC 7807 completely or keep current format with optional RFC 7807 support
   - Recommendation: Keep current format (simpler, already working) but document it as RFC 7807-compatible by mapping fields

3. **How deeply to document internal vs user-facing errors**
   - What we know: Validation errors should include field names; 500 errors shouldn't leak internals
   - What's unclear: How much detail in 500 error responses vs generic "unexpected error" message
   - Recommendation: In development show stack traces; in production show generic message + request ID for support tracking

4. **Testing schema completeness**
   - What we know: drf-spectacular generates schema; @extend_schema decorators control what's in it
   - What's unclear: How to test that all endpoints are documented and error codes match actual handlers
   - Recommendation: Write schema validation tests; verify all ViewSet methods have tags; compare schema operations with actual routes

## Sources

### Primary (HIGH confidence)
- [drf-spectacular Documentation](https://drf-spectacular.readthedocs.io/en/latest/) - Official docs, verified 2026-01-31
- [drf-spectacular Customization Guide](https://drf-spectacular.readthedocs.io/en/latest/customization.html) - Official patterns, verified 2026-01-31
- [Django REST Framework Exceptions](https://www.django-rest-framework.org/api-guide/exceptions/) - Official DRF docs, verified 2026-01-31
- [RFC 7807 - Problem Details for HTTP APIs](https://datatracker.ietf.org/doc/html/rfc7807) - IETF standard specification
- [OpenAPI 3.0 Specification](https://spec.openapis.org/oas/v3.0.3) - Official OpenAPI spec, verified 2026-01-31

### Secondary (MEDIUM confidence)
- [drf-standardized-errors OpenAPI Integration](https://drf-standardized-errors.readthedocs.io/en/latest/openapi.html) - Optional error standardization package
- [OpenAPI Best Practices - Speakeasy](https://www.speakeasy.com/blog/tags-best-practices-in-openapi) - Industry best practices guide, verified 2026-01-31
- [OpenAPI 3.0 Best Practices](https://learn.openapis.org/best-practices.html) - Official OpenAPI learning materials

### Tertiary (LOW confidence)
- [WebSearch: drf-spectacular extend_schema custom actions] - Community patterns for custom action documentation
- [WebSearch: OpenAPI error response patterns 2026] - Industry discussions on error standardization

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - drf-spectacular 0.27.2 verified installed; Django REST Framework 3.15 verified; no compatibility gaps
- Architecture: HIGH - Patterns from official drf-spectacular documentation, verified with source code examination
- Pitfalls: HIGH - Common pitfalls documented in official drf-spectacular issues and Django REST Framework best practices
- Error standardization: MEDIUM-HIGH - Current exception handler verified in codebase; RFC 7807 is IETF standard; optional enhancement (not breaking change)

**Research date:** 2026-01-31
**Valid until:** 2026-03-02 (30 days - stable domain; drf-spectacular major changes rare)

**Specific version confirmations:**
- drf-spectacular: 0.27.2 (installed via requirements.txt constraint ~=0.27.0)
- Django REST Framework: 3.15.0 (constraint ~=3.15.0)
- Django: 5.2.2 (constraint ~=5.2.2)
- django-filter: 25.1 (constraint ~=25.1)
