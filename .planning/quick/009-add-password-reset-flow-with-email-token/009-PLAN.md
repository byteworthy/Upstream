---
phase: quick-009
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - upstream/urls.py
  - upstream/templates/registration/password_reset_form.html
  - upstream/templates/registration/password_reset_done.html
  - upstream/templates/registration/password_reset_confirm.html
  - upstream/templates/registration/password_reset_complete.html
  - upstream/templates/registration/password_reset_email.html
  - upstream/templates/registration/password_reset_subject.txt
  - upstream/settings/base.py
autonomous: true

must_haves:
  truths:
    - "User can request password reset via email"
    - "User receives email with secure token link"
    - "User can set new password via token link"
    - "Token expires after reasonable time period"
    - "Reset flow matches existing UI styling"
  artifacts:
    - path: "upstream/urls.py"
      provides: "Password reset URL patterns"
      contains: "password_reset"
    - path: "upstream/templates/registration/password_reset_form.html"
      provides: "Password reset request form"
      min_lines: 20
    - path: "upstream/templates/registration/password_reset_email.html"
      provides: "Email template with reset link"
      contains: "{{ protocol }}://{{ domain }}"
    - path: "upstream/settings/base.py"
      provides: "Password reset timeout configuration"
      contains: "PASSWORD_RESET_TIMEOUT"
  key_links:
    - from: "upstream/urls.py"
      to: "django.contrib.auth.views.PasswordResetView"
      via: "URL pattern registration"
      pattern: "auth_views\\.PasswordReset"
    - from: "upstream/templates/registration/password_reset_email.html"
      to: "password_reset_confirm URL"
      via: "{% url 'password_reset_confirm' %}"
      pattern: "\\{%\\s*url\\s*['\"]password_reset_confirm"
---

<objective>
Implement Django's built-in password reset flow with secure email token-based verification.

Purpose: Enable users to securely reset forgotten passwords via email link, following Django security best practices with token expiration and one-time use links.

Output: Complete password reset flow with 4 screens (request, confirmation, reset form, complete) and styled email template matching existing brand.
</objective>

<execution_context>
@/home/codespace/.claude/get-shit-done/workflows/execute-plan.md
@/home/codespace/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@/workspaces/codespaces-django/.planning/STATE.md
@/workspaces/codespaces-django/upstream/settings/base.py
@/workspaces/codespaces-django/upstream/settings/dev.py
@/workspaces/codespaces-django/upstream/urls.py
@/workspaces/codespaces-django/upstream/templates/upstream/login.html
@/workspaces/codespaces-django/upstream/templates/email/alert_email_body.html
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add password reset URL patterns to upstream/urls.py</name>
  <files>upstream/urls.py</files>
  <action>
Add Django's built-in password reset URL patterns to upstream/urls.py after the existing login/logout patterns.

Add these 4 URL patterns using Django's auth_views:
1. password_reset/ - PasswordResetView (user enters email)
2. password_reset/done/ - PasswordResetDoneView (confirmation email sent)
3. reset/&lt;uidb64&gt;/&lt;token&gt;/ - PasswordResetConfirmView (user enters new password)
4. reset/done/ - PasswordResetCompleteView (success message)

Use template_name parameter to point to upstream/registration/ templates.
Set email_template_name to 'registration/password_reset_email.html'.
Set subject_template_name to 'registration/password_reset_subject.txt'.

Import: from django.contrib.auth import views as auth_views
  </action>
  <verify>
grep -A 4 "password_reset" upstream/urls.py confirms 4 URL patterns exist.
python manage.py show_urls | grep password_reset shows patterns registered.
  </verify>
  <done>
URL patterns for password_reset, password_reset_done, password_reset_confirm, and password_reset_complete are registered in upstream/urls.py with correct template paths.
  </done>
</task>

<task type="auto">
  <name>Task 2: Create password reset email templates</name>
  <files>
    upstream/templates/registration/password_reset_email.html
    upstream/templates/registration/password_reset_subject.txt
  </files>
  <action>
Create upstream/templates/registration/ directory if it doesn't exist.

Create password_reset_subject.txt:
- Single line: "Password Reset Request for Upstream"
- No HTML, plain text only

Create password_reset_email.html:
- Use existing alert_email_body.html as reference for styling (Upstream brand colors)
- Include greeting with {{ user.get_username }}
- Explain password reset was requested
- Provide reset link: {{ protocol }}://{{ domain }}{% url 'password_reset_confirm' uidb64=uid token=token %}
- Note link expires in 24 hours
- Include security note: "If you didn't request this, ignore this email"
- Professional email signature
- Use HTML table layout for email client compatibility
- Match existing email template structure with inline CSS
  </action>
  <verify>
ls upstream/templates/registration/ confirms both files exist.
cat upstream/templates/registration/password_reset_subject.txt shows subject line.
grep "password_reset_confirm" upstream/templates/registration/password_reset_email.html confirms URL tag present.
  </verify>
  <done>
Email templates exist in registration/ directory with proper Django template variables ({{ protocol }}, {{ domain }}, {{ uid }}, {{ token }}), branded styling, and security messaging.
  </done>
</task>

<task type="auto">
  <name>Task 3: Create password reset form templates and configure timeout</name>
  <files>
    upstream/templates/registration/password_reset_form.html
    upstream/templates/registration/password_reset_done.html
    upstream/templates/registration/password_reset_confirm.html
    upstream/templates/registration/password_reset_complete.html
    upstream/settings/base.py
  </files>
  <action>
Create 4 HTML templates extending upstream/templates/upstream/base.html (if exists, otherwise create minimal base).

password_reset_form.html:
- Form with email input field
- Submit button "Send Password Reset Email"
- CSRF token ({% csrf_token %})
- Display form errors with {{ form.errors }}
- Link back to login page
- Match styling from login.html (use as reference)

password_reset_done.html:
- Success message: "Password reset email sent"
- Instructions: "Check your email for reset link"
- Link back to login

password_reset_confirm.html:
- If validlink: form with password1 and password2 fields
- If not validlink: error message "Reset link expired or invalid"
- CSRF token, form errors
- Submit button "Reset Password"
- Password requirements reminder (12+ chars)

password_reset_complete.html:
- Success message: "Password successfully reset"
- Link to login page with "Log in now" button

Add to upstream/settings/base.py (after AUTH_PASSWORD_VALIDATORS section):
- PASSWORD_RESET_TIMEOUT = 86400  # 24 hours in seconds
- Add comment: "# Password reset link expires after 24 hours"
  </action>
  <verify>
ls upstream/templates/registration/ | wc -l shows 6 files (4 HTML + 2 email templates).
grep "PASSWORD_RESET_TIMEOUT" upstream/settings/base.py confirms setting exists.
grep "csrf_token" upstream/templates/registration/password_reset_form.html confirms CSRF protection.
  </verify>
  <done>
All 4 password reset form templates exist with proper Django form syntax, CSRF protection, error handling, consistent styling with login page, and PASSWORD_RESET_TIMEOUT configured to 24 hours in base settings.
  </done>
</task>

</tasks>

<verification>
Manual verification steps:

1. Start dev server: python manage.py runserver
2. Navigate to http://localhost:8000/portal/password_reset/
3. Enter valid email address (check console for email output in dev mode)
4. Verify email contains reset link
5. Click reset link (or manually visit the URL)
6. Enter new password (must meet 12+ char requirement)
7. Confirm password reset success
8. Log in with new password

Automated checks:
- python manage.py check confirms no configuration errors
- grep -r "password_reset" upstream/urls.py confirms URL patterns
- ls upstream/templates/registration/ confirms 6 files
</verification>

<success_criteria>
- [ ] 4 password reset URL patterns registered in upstream/urls.py
- [ ] 6 template files exist in upstream/templates/registration/
- [ ] Email templates include all required Django variables (protocol, domain, uid, token)
- [ ] Form templates include CSRF tokens and error handling
- [ ] PASSWORD_RESET_TIMEOUT set to 86400 seconds (24 hours)
- [ ] Templates match existing UI styling from login.html
- [ ] python manage.py check passes with no errors
- [ ] Manual test flow completes successfully (request -> email -> reset -> login)
</success_criteria>

<output>
After completion, create `.planning/quick/009-add-password-reset-flow-with-email-token/009-SUMMARY.md`
</output>
