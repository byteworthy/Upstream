---
task_id: "004"
type: quick
wave: 1
depends_on: []
files_modified:
  - scripts/configure_gcp_log_retention.sh
  - .github/workflows/gcp-setup.yml
  - docs/GCP_LOG_RETENTION.md
autonomous: true

must_haves:
  truths:
    - "Cloud Logging retention policies configured for HIPAA compliance"
    - "Application logs retained for 90 days"
    - "Audit logs retained for 7 years"
    - "GitHub workflow logs retained for 90 days"
  artifacts:
    - path: "scripts/configure_gcp_log_retention.sh"
      provides: "Automated GCP log bucket retention configuration"
      min_lines: 80
    - path: ".github/workflows/gcp-setup.yml"
      provides: "CI workflow for log retention setup"
      min_lines: 40
    - path: "docs/GCP_LOG_RETENTION.md"
      provides: "Documentation for log retention policies"
      min_lines: 100
  key_links:
    - from: ".github/workflows/gcp-setup.yml"
      to: "scripts/configure_gcp_log_retention.sh"
      via: "workflow executes script"
      pattern: "scripts/configure_gcp_log_retention\\.sh"
---

<objective>
Configure HIPAA-compliant log retention policies for Google Cloud Logging and GitHub Actions workflows. Ensure application logs are retained for 90 days and audit logs for 7 years to meet regulatory requirements.

Purpose: Comply with HIPAA audit trail retention requirements while managing cloud logging costs through appropriate retention periods for different log types.

Output: Automated configuration script, GitHub Actions workflow, and documentation for GCP log retention policies.
</objective>

<execution_context>
@/home/codespace/.claude/get-shit-done/workflows/execute-plan.md
@/home/codespace/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/PROJECT.md
@upstream/logging_config.py
@docs/LOG_RETENTION.md
@deploy_gcp.sh
@GCP_DEPLOYMENT_GUIDE.md

**Current State:**
- Local log retention: 90 days (app logs), 7 years (audit logs)
- JSON structured logging configured for production
- GCP deployment infrastructure exists (Cloud Run, Cloud SQL)
- No Cloud Logging retention policies configured yet
- GitHub Actions workflows have default 90-day log retention

**HIPAA Requirements:**
- Audit logs: 6 years minimum (using 7 years conservatively)
- Application logs: 90 days for operational troubleshooting
- Security logs: 90 days for incident investigation

**Cost Considerations:**
- Cloud Logging pricing: $0.50/GB ingested after 50GB/month
- Long-term retention via log buckets: $0.01/GB/month
- Need balance between compliance and cost
</context>

<tasks>

<task type="auto">
  <name>Create GCP log retention configuration script</name>
  <files>scripts/configure_gcp_log_retention.sh</files>
  <action>
Create automated bash script to configure GCP log bucket retention policies using gcloud logging commands.

**Script structure:**
1. Prerequisites check (gcloud CLI, authentication, project ID)
2. Enable Cloud Logging API
3. Create log buckets with retention policies:
   - `upstream-app-logs` bucket: 90-day retention for INFO/WARNING/ERROR logs
   - `upstream-audit-logs` bucket: 2555-day (7-year) retention for audit trails
4. Create log sinks to route logs to appropriate buckets:
   - Route `jsonPayload.logger=~"upstream.*"` AND `severity>=INFO` to app-logs bucket
   - Route `jsonPayload.logger="auditlog"` OR `jsonPayload.audit=true` to audit-logs bucket
5. Set up log exclusion filters to reduce costs:
   - Exclude verbose DEBUG logs (only in production)
   - Exclude health check pings from load balancer
   - Exclude static file requests (already captured by CDN)
6. Verify configuration with gcloud logging buckets list
7. Display estimated monthly cost based on configured retention

**Important:**
- Use `gcloud logging buckets create` not `gsutil` (different from Cloud Storage)
- Set `--location=global` for cross-region access
- Use `--restricted-fields` to prevent accidental PHI exposure in logs
- Include `--locked=false` to allow future retention updates
- Test in staging environment first (use `--project` flag to target specific project)

**Error handling:**
- Check if buckets already exist before creating
- Validate PROJECT_ID environment variable
- Confirm user has `logging.admin` IAM role
- Provide clear error messages with remediation steps
  </action>
  <verify>
```bash
# Dry-run mode to preview changes
bash scripts/configure_gcp_log_retention.sh --dry-run

# Verify script is executable and has no syntax errors
bash -n scripts/configure_gcp_log_retention.sh
```
  </verify>
  <done>
- Script exists at scripts/configure_gcp_log_retention.sh
- Script is executable (chmod +x)
- Script includes dry-run mode for safe testing
- Script validates prerequisites before making changes
- Script creates two log buckets with correct retention periods
- Script creates log sinks with proper filters
- Script includes cost estimation output
  </done>
</task>

<task type="auto">
  <name>Create GitHub Actions workflow for log retention setup</name>
  <files>.github/workflows/gcp-setup.yml</files>
  <action>
Create GitHub Actions workflow to automate GCP log retention configuration during infrastructure setup.

**Workflow structure:**
1. Trigger: workflow_dispatch (manual) with environment input (staging/production)
2. Job: `configure-log-retention`
   - Runs on: ubuntu-latest
   - Environment: ${{ github.event.inputs.environment }}
3. Steps:
   - Checkout code
   - Authenticate to GCP using workload identity federation
     - Use `google-github-actions/auth@v2` action
     - Set `workload_identity_provider` and `service_account` from secrets
   - Set up gcloud CLI
   - Run log retention script with appropriate PROJECT_ID
   - Upload results as workflow artifact (JSON summary of created buckets)
4. Add job to configure GitHub Actions log retention:
   - Use `actions/github-script@v7` to call GitHub API
   - Set workflow log retention to 90 days (default is 90, but explicitly set)
   - Set artifact retention to 30 days (reduce storage costs)

**GitHub Actions log retention:**
- Workflow logs: 90 days (matches application logs)
- Artifacts: 30 days (shorter for temporary test outputs)
- Use GitHub API: `PUT /repos/{owner}/{repo}/actions/cache/usage-policy`

**Important:**
- Require approval for production environment (use `environment` protection rules)
- Include dry-run step before actual execution
- Add output summary showing configured retention periods
- Store GCP credentials as repository secrets (not in workflow file)
  </action>
  <verify>
```bash
# Validate workflow syntax
cat .github/workflows/gcp-setup.yml | grep -E "(name:|on:|jobs:)" | head -5

# Test workflow locally with act (if available)
act workflow_dispatch --dryrun 2>/dev/null || echo "Install act for local testing"
```
  </verify>
  <done>
- Workflow file exists at .github/workflows/gcp-setup.yml
- Workflow has manual trigger with environment selection
- Workflow authenticates to GCP securely
- Workflow executes log retention script
- Workflow configures GitHub Actions log retention
- Workflow includes dry-run validation step
- Workflow requires approval for production changes
  </done>
</task>

<task type="auto">
  <name>Document GCP log retention configuration</name>
  <files>docs/GCP_LOG_RETENTION.md</files>
  <action>
Create comprehensive documentation for GCP Cloud Logging retention policies and management.

**Documentation structure:**

1. **Overview**
   - HIPAA compliance requirements for log retention
   - Cost implications of different retention periods
   - Difference between local log files and Cloud Logging

2. **Retention Policies**
   - Table showing log types, retention periods, and justification:
     - Application logs (upstream.*): 90 days
     - Audit logs (auditlog): 7 years (2555 days)
     - Security logs (django.security): 90 days
     - Performance logs: 30 days
     - Debug logs: Excluded in production
   - Alignment with local logging_config.py retention periods

3. **Log Buckets**
   - upstream-app-logs bucket configuration
   - upstream-audit-logs bucket configuration
   - How log sinks route logs to buckets
   - Log exclusion filters for cost optimization

4. **Setup Instructions**
   - Prerequisites (gcloud CLI, IAM permissions)
   - Manual setup: `./scripts/configure_gcp_log_retention.sh`
   - Automated setup: GitHub Actions workflow
   - How to verify configuration: `gcloud logging buckets list`
   - How to update retention periods: `gcloud logging buckets update`

5. **Querying Logs**
   - Using Cloud Logging Explorer
   - Example queries:
     - View audit logs: `logName:"audit-logs" AND jsonPayload.logger="auditlog"`
     - View errors: `severity>=ERROR AND jsonPayload.logger=~"upstream.*"`
     - Search by user: `jsonPayload.user_id="123"`
   - Exporting logs for compliance audits

6. **Cost Management**
   - Current pricing: $0.50/GB ingested, $0.01/GB/month storage
   - Monthly cost estimates based on typical usage:
     - Staging: ~$10-20/month
     - Production: ~$50-100/month (depends on traffic)
   - How exclusion filters reduce costs
   - When to consider BigQuery export for analysis

7. **HIPAA Compliance**
   - Audit log requirements (7-year retention)
   - PHI scrubbing (already handled by logging_config.py)
   - Access controls (IAM permissions for log viewing)
   - Business Associate Agreement (BAA) with Google Cloud

8. **Troubleshooting**
   - Logs not appearing in Cloud Logging
   - Retention policy not taking effect
   - Cost unexpectedly high
   - How to delete old logs manually

9. **Related Documentation**
   - Link to LOG_RETENTION.md (local logs)
   - Link to GCP_DEPLOYMENT_GUIDE.md
   - Link to Google Cloud Logging docs
  </action>
  <verify>
```bash
# Check documentation exists and has proper structure
test -f docs/GCP_LOG_RETENTION.md && echo "✓ Documentation created"

# Verify markdown formatting
grep -E "^#{1,3} " docs/GCP_LOG_RETENTION.md | head -10
```
  </verify>
  <done>
- Documentation exists at docs/GCP_LOG_RETENTION.md
- Documentation covers all 9 sections listed above
- Documentation includes retention policy table
- Documentation provides setup and query examples
- Documentation explains HIPAA compliance requirements
- Documentation includes cost management guidance
- Documentation links to related documentation
  </done>
</task>

</tasks>

<verification>
1. Retention configuration script passes syntax check
2. Script includes dry-run mode for safe testing
3. GitHub Actions workflow has valid YAML syntax
4. Documentation covers setup, usage, and troubleshooting
5. All retention periods align with HIPAA requirements
6. Cost optimization filters included in script
</verification>

<success_criteria>
- [x] Script creates GCP log buckets with correct retention (90 days app, 7 years audit)
- [x] Script creates log sinks routing logs to appropriate buckets
- [x] Script includes cost-reducing exclusion filters
- [x] GitHub Actions workflow automates log retention setup
- [x] GitHub Actions workflow configures GitHub log retention (90 days)
- [x] Documentation explains retention policies and HIPAA compliance
- [x] All artifacts use HIPAA-compliant retention periods
- [x] Configuration can be applied to staging and production separately
</success_criteria>

<output>
After completion, create `.planning/quick/004-configure-log-retention-policy-for-hipa/004-SUMMARY.md`
</output>
