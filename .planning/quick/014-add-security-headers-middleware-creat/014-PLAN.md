---
phase: quick-014
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - upstream/middleware.py
  - upstream/settings/base.py
autonomous: true

must_haves:
  truths:
    - "All HTTP responses include security headers"
    - "X-Frame-Options header prevents clickjacking"
    - "X-Content-Type-Options header prevents MIME sniffing"
    - "X-XSS-Protection header enables browser XSS filters"
    - "Strict-Transport-Security header enforces HTTPS"
  artifacts:
    - path: "upstream/middleware.py"
      provides: "SecurityHeadersMiddleware class"
      min_lines: 30
      contains: "class SecurityHeadersMiddleware"
    - path: "upstream/settings/base.py"
      provides: "SecurityHeadersMiddleware in MIDDLEWARE list"
      contains: "upstream.middleware.SecurityHeadersMiddleware"
  key_links:
    - from: "upstream/settings/base.py"
      to: "upstream.middleware.SecurityHeadersMiddleware"
      via: "MIDDLEWARE list registration"
      pattern: "upstream\\.middleware\\.SecurityHeadersMiddleware"
---

<objective>
Add security headers middleware to protect against common web vulnerabilities (clickjacking, MIME sniffing, XSS, insecure connections).

Purpose: Improve application security posture with industry-standard HTTP security headers following OWASP best practices.
Output: SecurityHeadersMiddleware class that automatically adds security headers to all responses.
</objective>

<execution_context>
@/home/codespace/.claude/get-shit-done/workflows/execute-plan.md
@/home/codespace/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@upstream/middleware.py
@upstream/settings/base.py

## Codebase Pattern

The project has multiple existing middleware classes in `upstream/middleware.py`:
- RequestIdMiddleware (MiddlewareMixin pattern)
- ApiVersionMiddleware (MiddlewareMixin pattern for response headers)
- HealthCheckMiddleware (early return pattern)

Follow the established pattern of using `MiddlewareMixin` for response header manipulation.

## Current Security Configuration

Settings already has:
- `X_FRAME_OPTIONS = "DENY"` (line 69) - but this is Django's setting, not a custom header
- `django.middleware.clickjacking.XFrameOptionsMiddleware` in MIDDLEWARE list

The new middleware will add additional security headers beyond Django's built-in X-Frame-Options.
</context>

<tasks>

<task type="auto">
  <name>Create SecurityHeadersMiddleware class</name>
  <files>upstream/middleware.py</files>
  <action>
Add SecurityHeadersMiddleware class to `upstream/middleware.py` following the existing MiddlewareMixin pattern used by ApiVersionMiddleware.

Implementation requirements:
- Inherit from `MiddlewareMixin` (already imported)
- Implement `process_response(request, response)` method
- Add the following security headers to every response:
  - `X-Content-Type-Options: nosniff` - Prevents MIME type sniffing
  - `X-XSS-Protection: 1; mode=block` - Enables browser XSS filters (legacy browsers)
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains` - Enforces HTTPS for 1 year
  - Note: X-Frame-Options already handled by Django's XFrameOptionsMiddleware
- Add docstring explaining the security headers and their purpose
- Place class after ApiVersionMiddleware (end of file, around line 506)

Why these specific headers:
- X-Content-Type-Options: Prevents browsers from MIME-sniffing responses, forcing declared content-type
- X-XSS-Protection: Defense-in-depth for older browsers (modern browsers use CSP)
- Strict-Transport-Security: Prevents protocol downgrade attacks and cookie hijacking
- Skip X-Frame-Options: Already configured via Django's built-in middleware and X_FRAME_OPTIONS setting

IMPORTANT: Do NOT add Content-Security-Policy header - CSP requires careful configuration with asset URLs and inline scripts. Leave CSP for future dedicated task.
  </action>
  <verify>
```bash
# Verify middleware class exists
grep -A 20 "class SecurityHeadersMiddleware" upstream/middleware.py

# Verify headers are set
grep "X-Content-Type-Options" upstream/middleware.py
grep "X-XSS-Protection" upstream/middleware.py
grep "Strict-Transport-Security" upstream/middleware.py
```
  </verify>
  <done>
SecurityHeadersMiddleware class exists in upstream/middleware.py with process_response method that sets X-Content-Type-Options, X-XSS-Protection, and Strict-Transport-Security headers.
  </done>
</task>

<task type="auto">
  <name>Register SecurityHeadersMiddleware in settings</name>
  <files>upstream/settings/base.py</files>
  <action>
Add SecurityHeadersMiddleware to the MIDDLEWARE list in `upstream/settings/base.py`.

Placement strategy:
- Add AFTER `django.middleware.security.SecurityMiddleware` (line 48)
- Add BEFORE `django.middleware.gzip.GZipMiddleware` (line 50)
- This ensures security headers are set early but after Django's built-in security

Update the MIDDLEWARE list at line 45-67 to include:
```python
"django.middleware.security.SecurityMiddleware",
"upstream.middleware.SecurityHeadersMiddleware",  # Custom security headers
"django.middleware.gzip.GZipMiddleware",
```

Rationale: Security headers should be set early in the middleware chain, but after Django's SecurityMiddleware which handles HTTPS redirects and other foundational security. Placing before GZip ensures headers are set before compression.
  </action>
  <verify>
```bash
# Verify middleware is registered
grep "SecurityHeadersMiddleware" upstream/settings/base.py

# Verify placement in MIDDLEWARE list
sed -n '45,70p' upstream/settings/base.py | grep -A 2 -B 2 "SecurityHeadersMiddleware"
```
  </verify>
  <done>
SecurityHeadersMiddleware is registered in MIDDLEWARE list in upstream/settings/base.py, positioned after SecurityMiddleware and before GZipMiddleware.
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <what-built>
SecurityHeadersMiddleware automatically adds security headers (X-Content-Type-Options, X-XSS-Protection, Strict-Transport-Security) to all HTTP responses.
  </what-built>
  <how-to-verify>
1. Start the development server:
   ```bash
   cd /workspaces/codespaces-django
   python manage.py runserver
   ```

2. Test security headers are present:
   ```bash
   # Test API endpoint
   curl -I http://localhost:8000/api/v1/uploads/ 2>&1 | grep -E "X-Content-Type-Options|X-XSS-Protection|Strict-Transport-Security"

   # Test health endpoint
   curl -I http://localhost:8000/health/ 2>&1 | grep -E "X-Content-Type-Options|X-XSS-Protection|Strict-Transport-Security"
   ```

3. Expected headers in response:
   ```
   X-Content-Type-Options: nosniff
   X-XSS-Protection: 1; mode=block
   Strict-Transport-Security: max-age=31536000; includeSubDomains
   ```

4. Verify existing X-Frame-Options still present (from Django's middleware):
   ```bash
   curl -I http://localhost:8000/api/v1/uploads/ 2>&1 | grep "X-Frame-Options"
   ```
   Expected: `X-Frame-Options: DENY`

5. All four security headers should be present on every response.
  </how-to-verify>
  <resume-signal>Type "approved" if all headers present, or describe issues</resume-signal>
</task>

</tasks>

<verification>
## Overall Checks

1. SecurityHeadersMiddleware class exists in upstream/middleware.py
2. Middleware is registered in upstream/settings/base.py MIDDLEWARE list
3. All responses include X-Content-Type-Options, X-XSS-Protection, Strict-Transport-Security headers
4. Existing X-Frame-Options header still present (from Django's built-in middleware)
5. No errors when starting development server
6. Headers present on both API and non-API endpoints
</verification>

<success_criteria>
- [ ] SecurityHeadersMiddleware class created in upstream/middleware.py with MiddlewareMixin pattern
- [ ] process_response method sets three security headers: X-Content-Type-Options, X-XSS-Protection, Strict-Transport-Security
- [ ] Middleware registered in MIDDLEWARE list after SecurityMiddleware
- [ ] All HTTP responses include the security headers
- [ ] Existing X-Frame-Options header still works (from Django's XFrameOptionsMiddleware)
- [ ] Development server starts without errors
- [ ] Manual curl tests confirm headers present
</success_criteria>

<output>
After completion, create `.planning/quick/014-add-security-headers-middleware-creat/014-SUMMARY.md`
</output>
