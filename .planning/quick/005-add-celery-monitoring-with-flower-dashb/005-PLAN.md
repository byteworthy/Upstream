---
phase: quick-005
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - requirements.txt
  - docker-compose.yml
  - upstream/settings/base.py
autonomous: false

must_haves:
  truths:
    - "Flower dashboard is accessible on port 5555"
    - "Flower shows real-time Celery worker status"
    - "Flower displays task history and statistics"
    - "Flower is protected with basic authentication"
  artifacts:
    - path: "requirements.txt"
      provides: "Flower dependency"
      contains: "flower"
    - path: "docker-compose.yml"
      provides: "Flower service container"
      contains: "flower"
    - path: "upstream/settings/base.py"
      provides: "Flower authentication configuration"
      contains: "FLOWER"
  key_links:
    - from: "docker-compose.yml"
      to: "redis:6379"
      via: "CELERY_BROKER_URL environment variable"
      pattern: "redis://redis:6379"
---

<objective>
Add Flower dashboard for visual monitoring of Celery workers, tasks, and queue status with basic authentication.

Purpose: Provide real-time visual monitoring for webhook delivery and drift detection background jobs, complementing existing Prometheus metrics with an interactive web UI for operational insight.

Output: Working Flower dashboard accessible at http://localhost:5555 with basic auth protection, showing task history, worker status, and queue statistics.
</objective>

<execution_context>
@/home/codespace/.claude/get-shit-done/workflows/execute-plan.md
@/home/codespace/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@upstream/celery.py
@docker-compose.yml
@requirements.txt
@upstream/settings/base.py
</context>

<tasks>

<task type="auto">
  <name>Install Flower and add to docker-compose</name>
  <files>requirements.txt, docker-compose.yml</files>
  <action>
1. Add Flower to requirements.txt with version constraint:
   - Add `flower~=2.0.1` after the celery line in the "Background Tasks & Async Processing" section
   - This is a standard Celery monitoring tool, battle-tested and maintained by the Celery team

2. Add Flower service to docker-compose.yml after celery_beat service:
   ```yaml
   # Flower (Celery Monitoring Dashboard)
   flower:
     build:
       context: .
       target: development
     command: celery -A upstream --broker=redis://redis:6379/0 flower --port=5555 --basic_auth=admin:${FLOWER_PASSWORD:-flower_dev_pass}
     volumes:
       - .:/app
     environment:
       - DEBUG=${DEBUG:-True}
       - SECRET_KEY=${SECRET_KEY:-django-insecure-docker-dev-key}
       - DB_NAME=${DB_NAME:-upstream}
       - DB_USER=${DB_USER:-upstream}
       - DB_PASSWORD=${DB_PASSWORD:-upstream_dev_password}
       - DB_HOST=db
       - DB_PORT=5432
       - CELERY_BROKER_URL=redis://redis:6379/0
       - CELERY_RESULT_BACKEND=redis://redis:6379/0
       - CELERY_ENABLED=True
     ports:
       - "5555:5555"
     depends_on:
       redis:
         condition: service_healthy
     restart: unless-stopped
   ```

3. Key configuration notes:
   - Using --basic_auth for simple protection (not for production with sensitive data, but adequate for dev/staging)
   - Port 5555 is the standard Flower port
   - Depends on redis only (not db) since Flower connects to broker, not database
   - Uses same broker URL as celery_worker and celery_beat for consistency
  </action>
  <verify>
grep -q "flower~=" requirements.txt && grep -q "flower:" docker-compose.yml
  </verify>
  <done>
- Flower dependency added to requirements.txt with version constraint
- Flower service defined in docker-compose.yml with basic auth and port 5555
- Service depends on Redis and uses correct broker URL
  </done>
</task>

<task type="auto">
  <name>Add Flower environment configuration</name>
  <files>upstream/settings/base.py, .env.production.example</files>
  <action>
1. Add Flower configuration section to upstream/settings/base.py after CELERY configuration block (around line 150-200):
   ```python
   # Flower Configuration
   # Dashboard for monitoring Celery workers, tasks, and queues
   FLOWER_BASIC_AUTH_USERNAME = config('FLOWER_BASIC_AUTH_USERNAME', default='admin')
   FLOWER_BASIC_AUTH_PASSWORD = config('FLOWER_BASIC_AUTH_PASSWORD', default='flower_dev_pass')
   FLOWER_PORT = config('FLOWER_PORT', default='5555', cast=int)
   # Note: In production, use strong password and consider additional security (VPN, firewall rules, OAuth)
   ```

2. Add Flower credentials to .env.production.example (if file exists) after CELERY section:
   ```
   # Flower Dashboard (Celery Monitoring)
   FLOWER_BASIC_AUTH_USERNAME=admin
   FLOWER_BASIC_AUTH_PASSWORD=<change-in-production>
   FLOWER_PORT=5555
   ```

3. Documentation note: While basic auth is configured in settings, the actual enforcement happens via command-line flag in docker-compose.yml for simplicity. Settings provide centralized credential management for future use.
  </action>
  <verify>
grep -q "FLOWER_BASIC_AUTH_USERNAME" upstream/settings/base.py
  </verify>
  <done>
- Flower configuration added to Django settings with environment variable support
- Credentials documented in .env.production.example (if exists)
- Configuration follows existing patterns (decouple, defaults for dev)
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <what-built>Flower dashboard service with basic auth on port 5555, integrated with existing Celery setup</what-built>
  <how-to-verify>
1. Start the services:
   ```bash
   docker-compose up -d flower
   ```

2. Wait 10-15 seconds for Flower to start, then visit:
   http://localhost:5555

3. Login with credentials:
   - Username: admin
   - Password: flower_dev_pass (or value of FLOWER_PASSWORD env var)

4. Verify Flower dashboard shows:
   - "Workers" tab: Active celery_worker instances (should see at least 1)
   - "Tasks" tab: Any completed tasks from prior work (drift detection, webhooks)
   - "Broker" tab: Redis connection status (should be connected)
   - "Monitor" tab: Real-time task execution graphs

5. Optional: Trigger a test task to see it in Flower:
   ```bash
   docker-compose exec web python manage.py shell
   >>> from upstream.celery import debug_task
   >>> debug_task.delay()
   >>> exit()
   ```
   Refresh Flower to see the debug_task appear in task history.

6. Check logs for any errors:
   ```bash
   docker-compose logs flower
   ```

Expected behavior:
- Flower UI loads successfully with authentication
- Workers are visible and marked as "Online"
- Tasks show execution history with timing data
- Redis broker shows as connected
  </how-to-verify>
  <resume-signal>Type "approved" if Flower dashboard is accessible and showing Celery workers/tasks correctly, or describe any issues encountered</resume-signal>
</task>

</tasks>

<verification>
- [ ] requirements.txt contains flower~=2.0.1
- [ ] docker-compose.yml has flower service on port 5555
- [ ] Flower service uses basic_auth with credentials
- [ ] Flower connects to redis://redis:6379/0 broker
- [ ] upstream/settings/base.py has FLOWER configuration
- [ ] Flower dashboard accessible at http://localhost:5555
- [ ] Authentication prompt appears before dashboard access
- [ ] Workers tab shows active celery_worker instances
- [ ] Tasks tab displays task history and statistics
- [ ] Broker tab confirms Redis connection
</verification>

<success_criteria>
- Flower package added to requirements.txt
- docker-compose.yml has flower service configured with basic auth
- Flower environment variables defined in settings
- Dashboard loads at http://localhost:5555 with auth prompt
- Flower displays real-time Celery worker status
- Task history visible with execution times
- Redis broker connection confirmed
- All existing Celery functionality still works (worker, beat)
</success_criteria>

<output>
After completion, create `.planning/quick/005-add-celery-monitoring-with-flower-dashb/005-SUMMARY.md`
</output>
