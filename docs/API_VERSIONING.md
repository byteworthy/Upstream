# API Versioning Strategy

## Overview

The Upstream API uses **header-based versioning** to communicate the API version to clients. Every HTTP response includes an `API-Version` header that indicates which version of the API processed the request.

**Current version:** 1.0.0

**Versioning scheme:** Semantic Versioning (MAJOR.MINOR.PATCH)

This approach enables backward-compatible evolution of the API while giving clients visibility into version changes and future deprecations.

## Versioning Policy

The API version follows semantic versioning with the following semantics:

### MAJOR version (X.0.0)

Breaking changes that require client updates:

- Removed endpoints or parameters
- Changed response structure (removed fields, changed types)
- Changed authentication mechanism
- Changed error response format
- Breaking changes to request/response contracts

**Example:** Removing the `/v1/claims` endpoint or changing `status` field from string to enum

### MINOR version (1.X.0)

Backward-compatible additions:

- New endpoints
- New optional request parameters
- New fields in responses (additive)
- New query filters or search capabilities
- Performance improvements with no contract changes

**Example:** Adding a new `/v1/reports` endpoint or adding an optional `include_details` parameter

### PATCH version (1.0.X)

Bug fixes and internal changes:

- Bug fixes that restore documented behavior
- Internal refactoring with no API contract changes
- Documentation improvements
- Performance optimizations that don't affect behavior

**Example:** Fixing a bug where pagination returned incorrect results

### Default behavior

When clients make requests without specifying a version preference (future feature), they receive the **latest stable version**. The version that processed the request is always returned in the `API-Version` response header.

## Client Integration

### Reading the API version

Clients should read and log the `API-Version` header from responses to track which version they're interacting with.

**Example with curl:**

```bash
curl -I https://api.upstream.example.com/v1/claims | grep API-Version
# Output: API-Version: 1.0.0
```

**Example with Python requests:**

```python
import requests

response = requests.get('https://api.upstream.example.com/v1/claims')
api_version = response.headers.get('API-Version')
print(f"API Version: {api_version}")  # Output: API Version: 1.0.0
```

**Example with JavaScript fetch:**

```javascript
fetch('https://api.upstream.example.com/v1/claims')
  .then(response => {
    console.log('API Version:', response.headers.get('API-Version'));
    // Output: API Version: 1.0.0
    return response.json();
  });
```

### Monitoring recommendations

Clients should:

1. **Log the API version** on every request or periodically sample
2. **Alert on version changes** - especially MAJOR version changes
3. **Test against new versions** before they become default
4. **Monitor deprecation warnings** (see below)

## Deprecation Process

To maintain stability and give clients time to migrate, we follow a structured deprecation process:

### Timeline

- **Minimum 6 months notice** before removing endpoints or making breaking changes
- **3 months recommended** for migrating to new major versions
- **30 days minimum** for minor changes that affect behavior (even if backward-compatible)

### Deprecation warnings

When an endpoint or feature is deprecated, the API will include an `X-API-Deprecation-Notice` header:

```
X-API-Deprecation-Notice: The /v1/legacy-claims endpoint is deprecated and will be removed in version 2.0.0 (2027-06-01). Use /v1/claims instead.
```

Clients should monitor for this header and take action when detected.

### Migration guides

Before any major version bump (e.g., 1.x.x → 2.0.0), we will provide:

1. **Migration guide** documenting all breaking changes
2. **Code examples** showing before/after patterns
3. **Testing endpoint** to validate client compatibility
4. **Sunset schedule** with specific dates

## Implementation Details

### Middleware

The `API-Version` header is added by `ApiVersionMiddleware` in `upstream/middleware.py`.

**Class:** `upstream.middleware.ApiVersionMiddleware`

**Location in middleware stack:** Near the end, before Prometheus metrics collection

**Process flow:**

1. Request enters Django
2. All middleware process the request
3. View executes and returns response
4. `ApiVersionMiddleware.process_response()` adds `API-Version` header
5. Response sent to client

### Configuration

The middleware is registered in `MIDDLEWARE` in `upstream/settings/base.py`:

```python
MIDDLEWARE = [
    # ... other middleware ...
    "upstream.middleware.ApiVersionMiddleware",
    "django_prometheus.middleware.PrometheusAfterMiddleware",
]
```

### Version constant

The current version is defined as a class constant in the middleware:

```python
class ApiVersionMiddleware(MiddlewareMixin):
    VERSION = "1.0.0"
```

### How to update the version

To update the API version:

1. **Update the VERSION constant** in `upstream/middleware.py`:
   ```python
   class ApiVersionMiddleware(MiddlewareMixin):
       VERSION = "1.1.0"  # Changed from 1.0.0
   ```

2. **Update this documentation** with:
   - New current version
   - Changelog of what changed
   - Migration notes (if breaking changes)

3. **Notify clients** if MAJOR or significant MINOR changes:
   - Email announcement
   - Dashboard notification
   - Deprecation headers (if applicable)

4. **Deploy changes** following standard deployment process

## Future Enhancements

The following features are planned for future iterations:

### Client-requested version negotiation

Allow clients to request a specific API version via `Accept-Version` request header:

```
GET /v1/claims
Accept-Version: 1.0.0
```

The server would respond with the requested version (if supported) or return 406 Not Acceptable.

### Per-endpoint version overrides

Enable gradual rollout of new API versions by supporting version overrides on specific endpoints:

```python
# New version only for /v1/claims endpoint
if request.path == '/v1/claims' and request.headers.get('Accept-Version') == '2.0.0':
    response['API-Version'] = '2.0.0'
```

### Multi-version support

Support multiple API versions simultaneously (e.g., 1.x and 2.x) with automatic routing based on requested version. This would enable:

- Zero-downtime migrations for clients
- A/B testing of new API designs
- Gradual deprecation of old versions

### Version metrics

Track API version usage in Prometheus metrics to understand adoption:

- Requests by version
- Unique clients by version
- Deprecation warning triggers
- Version negotiation failures

---

**Document version:** 1.0
**Last updated:** 2026-01-26
**Owner:** API Platform Team
