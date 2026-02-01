---
phase: quick-008
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - .github/workflows/deploy.yml
autonomous: false
user_setup:
  - service: slack
    why: "Deployment notifications"
    env_vars:
      - name: SLACK_WEBHOOK_URL
        source: "Slack App -> Incoming Webhooks -> Add New Webhook to Workspace"
    dashboard_config:
      - task: "Create incoming webhook"
        location: "Slack App settings -> Incoming Webhooks"
  - service: discord
    why: "Deployment notifications (alternative to Slack)"
    env_vars:
      - name: DISCORD_WEBHOOK_URL
        source: "Discord Server Settings -> Integrations -> Webhooks -> New Webhook"
    dashboard_config:
      - task: "Create webhook for channel"
        location: "Discord Server Settings -> Integrations -> Webhooks"

must_haves:
  truths:
    - "Deployment start notifications sent to configured channels"
    - "Deployment success notifications include commit info and deployment URL"
    - "Deployment failure notifications include error context"
    - "Notifications work with either Slack or Discord webhooks"
  artifacts:
    - path: ".github/workflows/deploy.yml"
      provides: "Deployment workflow with notification steps"
      min_lines: 120
      contains: "notification"
  key_links:
    - from: ".github/workflows/deploy.yml"
      to: "Slack/Discord API"
      via: "curl webhook POST"
      pattern: "curl.*webhook"
---

<objective>
Add deployment notifications to the GitHub Actions deploy workflow to alert teams of deployment events via Slack or Discord webhooks.

Purpose: Enable real-time visibility into deployment status, including success/failure notifications with commit details and deployment URLs.

Output: Updated deploy.yml workflow with notification steps for deployment start, success, and failure events.
</objective>

<execution_context>
@/home/codespace/.claude/get-shit-done/workflows/execute-plan.md
@/home/codespace/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@.github/workflows/deploy.yml
</context>

<tasks>

<task type="auto">
  <name>Add notification steps to deploy workflow</name>
  <files>.github/workflows/deploy.yml</files>
  <action>
Add deployment notification steps to the existing deploy.yml workflow:

1. **Deployment start notification** (after checkout, before tests):
   - POST to SLACK_WEBHOOK_URL or DISCORD_WEBHOOK_URL if configured
   - Include: environment, commit SHA (short), commit message, triggered by user
   - Use conditional: `if: secrets.SLACK_WEBHOOK_URL != '' || secrets.DISCORD_WEBHOOK_URL != ''`
   - Format for Slack: JSON with `text` field
   - Format for Discord: JSON with `content` field

2. **Deployment success notification** (after smoke tests pass):
   - Include: environment, commit SHA, deployment URL (from vars.DEPLOYMENT_URL)
   - Include: duration (use job start time)
   - Success emoji and color coding (green for Slack attachments)
   - Use conditional: `if: success() && (secrets.SLACK_WEBHOOK_URL != '' || secrets.DISCORD_WEBHOOK_URL != '')`

3. **Deployment failure notification** (on any step failure):
   - Include: environment, commit SHA, failed step name
   - Include: link to workflow run
   - Failure emoji and color coding (red for Slack attachments)
   - Use conditional: `if: failure() && (secrets.SLACK_WEBHOOK_URL != '' || secrets.DISCORD_WEBHOOK_URL != '')`

Implementation notes:
- Use `curl -X POST` with `-H "Content-Type: application/json"` for webhook calls
- Extract commit message: `git log -1 --pretty=%B`
- Workflow run URL: `${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}`
- Keep notification logic simple - no external actions, just curl
- Use `continue-on-error: true` for notification steps so deployment isn't blocked by notification failures
  </action>
  <verify>
1. Validate workflow syntax: `cat .github/workflows/deploy.yml | grep -A5 "notification"`
2. Check for proper conditionals on all notification steps
3. Verify webhook URL references use secrets.SLACK_WEBHOOK_URL and secrets.DISCORD_WEBHOOK_URL
4. Confirm all notification steps have continue-on-error: true
  </verify>
  <done>
- Deployment start notification step added after checkout
- Success notification step added after smoke tests with deployment details
- Failure notification step added with proper if: failure() condition
- All notifications support both Slack and Discord webhook formats
- Notifications use continue-on-error: true to prevent deployment blocking
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <what-built>Deployment notification integration in GitHub Actions workflow</what-built>
  <how-to-verify>
**Without configured webhooks (workflow syntax validation):**
1. Review the updated .github/workflows/deploy.yml file
2. Verify notification steps are present:
   - Deployment start (early in workflow)
   - Success notification (after smoke tests)
   - Failure notification (with if: failure() condition)
3. Check that conditionals properly check for webhook URL existence
4. Confirm continue-on-error: true is set on all notification steps

**With configured webhooks (actual notification test):**
1. Add SLACK_WEBHOOK_URL or DISCORD_WEBHOOK_URL to repository secrets:
   - GitHub repo -> Settings -> Secrets and variables -> Actions -> New repository secret
2. Trigger a test deployment:
   - Push a tag: `git tag v0.0.1-test && git push origin v0.0.1-test`
   - Or use workflow_dispatch from Actions tab
3. Check Slack/Discord channel for notifications:
   - Start notification appears immediately
   - Success/failure notification appears after workflow completes
   - Notifications include commit info, environment, and relevant links
4. Verify workflow still succeeds even if webhook fails (continue-on-error working)

**Expected notification format:**
- Start: "🚀 Deployment started: {environment} | Commit: {sha} | By: {user}"
- Success: "✅ Deployment succeeded: {environment} | Commit: {sha} | URL: {deployment_url}"
- Failure: "❌ Deployment failed: {environment} | Commit: {sha} | View logs: {run_url}"
  </how-to-verify>
  <resume-signal>Type "approved" if notifications are working correctly or describe any issues</resume-signal>
</task>

</tasks>

<verification>
1. Workflow syntax is valid (no YAML errors)
2. All notification steps have proper conditionals
3. Webhook URLs are referenced as secrets
4. Notifications don't block deployment (continue-on-error: true)
5. Both Slack and Discord formats are supported
6. Commit info and deployment URLs are included in notifications
</verification>

<success_criteria>
- Deployment workflow includes notification steps for start, success, and failure
- Notifications support both Slack and Discord webhook formats
- Webhook URLs are configured as GitHub secrets
- Notifications include commit SHA, message, environment, and deployment URL
- Workflow continues even if notifications fail
- Human verification confirms notifications appear in configured channels
</success_criteria>

<output>
After completion, create `.planning/quick/008-add-deployment-notifications-via-github-/008-SUMMARY.md`
</output>
