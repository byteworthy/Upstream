# Celery Monitoring & Health Checks

Comprehensive monitoring and health checking for Celery background tasks in Upstream.

## Features

### 1. Automatic Task Monitoring

All Celery tasks are automatically instrumented with Prometheus metrics:

- **Task starts**: Counter of tasks started
- **Task completions**: Counter of successful task completions
- **Task failures**: Counter of failed tasks (with error type labels)
- **Task duration**: Histogram of task execution time

### 2. Worker Health Checks

Health check endpoints provide real-time information about:

- Worker status (active/inactive)
- Queue depth
- Running tasks
- Scheduled tasks

### 3. Management Commands

Command-line tools for checking Celery health:

```bash
# Basic health check
python manage.py celery_health

# Verbose output with task details
python manage.py celery_health --verbose
```

## Implementation

### MonitoredTask Base Class

All tasks use the `MonitoredTask` base class which automatically tracks:

```python
from celery import shared_task
from upstream.celery_monitoring import MonitoredTask

@shared_task(base=MonitoredTask)
def my_task(customer_id, arg1, arg2):
    # Task logic here
    pass
```

**Automatic tracking includes:**
- Task start time
- Task completion time
- Task duration
- Success/failure status
- Error types on failure
- Customer ID (extracted from args/kwargs)

### Monitoring Decorator

Alternatively, use the `@monitor_task` decorator:

```python
from celery import shared_task
from upstream.celery_monitoring import monitor_task

@shared_task
@monitor_task
def my_task(customer_id, arg1, arg2):
    # Task logic here
    pass
```

## API Endpoints

### GET /api/celery/health/

Health check endpoint for monitoring tools (Kubernetes, Docker, load balancers).

**Response (healthy):**
```json
{
  "status": "healthy",
  "workers": {
    "healthy": true,
    "active_workers": ["worker1@hostname"],
    "worker_count": 1
  },
  "queues": {
    "celery": 5
  },
  "recommendations": []
}
```

**Response (unhealthy):**
```json
{
  "status": "unhealthy",
  "workers": {
    "healthy": false,
    "active_workers": [],
    "error": "No active Celery workers found"
  },
  "queues": {
    "celery": -1
  },
  "recommendations": [
    "Start Celery workers: celery -A upstream worker --loglevel=info"
  ]
}
```

**HTTP Status Codes:**
- `200 OK`: Celery is healthy or degraded (but operational)
- `503 Service Unavailable`: Celery is unhealthy (workers not running)

### GET /api/celery/tasks/

Get information about currently running and scheduled tasks.

**Response:**
```json
{
  "running": [
    {
      "worker": "worker1@hostname",
      "task_name": "upstream.tasks.run_drift_detection",
      "task_id": "abc-123-def-456",
      "time_start": 1234567890
    }
  ],
  "scheduled": [
    {
      "worker": "worker1@hostname",
      "task_name": "upstream.tasks.send_scheduled_report",
      "task_id": "def-456-ghi-789",
      "eta": "2024-01-28T10:30:00"
    }
  ],
  "running_count": 1
}
```

### GET /api/celery/stats/

Get statistics about task execution.

**Response:**
```json
{
  "total_running": 3,
  "total_scheduled": 1,
  "by_task_name": {
    "upstream.tasks.run_drift_detection": {
      "running": 2,
      "scheduled": 0
    },
    "upstream.tasks.send_alert": {
      "running": 1,
      "scheduled": 1
    }
  }
}
```

## Prometheus Metrics

All metrics are exposed at `/metrics` endpoint:

```prometheus
# Task starts
upstream_background_job_started_total{task_name="upstream.tasks.run_drift_detection",customer_id="123"} 42

# Task completions
upstream_background_job_completed_total{task_name="upstream.tasks.run_drift_detection",customer_id="123"} 40

# Task failures
upstream_background_job_failed_total{task_name="upstream.tasks.run_drift_detection",error_type="DatabaseError",customer_id="123"} 2

# Task duration (histogram)
upstream_background_job_duration_seconds_bucket{task_name="upstream.tasks.run_drift_detection",le="5.0"} 35
upstream_background_job_duration_seconds_bucket{task_name="upstream.tasks.run_drift_detection",le="10.0"} 40
upstream_background_job_duration_seconds_sum{task_name="upstream.tasks.run_drift_detection"} 234.5
upstream_background_job_duration_seconds_count{task_name="upstream.tasks.run_drift_detection"} 40
```

## Health Check Status

### Healthy

Celery is fully operational:
- ✓ Workers are running
- ✓ Queue depth is manageable (<1000 tasks)
- ✓ Tasks are being processed

### Degraded

Celery is operational but performance may be impacted:
- ✓ Workers are running
- ⚠ Queue depth is high (>1000 tasks)

**Actions:**
- Add more workers
- Investigate slow tasks
- Check task timeouts

### Unhealthy

Celery is not operational:
- ✗ No workers running
- ✗ Tasks cannot be processed

**Actions:**
- Start Celery workers: `celery -A upstream worker --loglevel=info`
- Check broker connectivity (Redis/RabbitMQ)
- Check worker logs for errors

## Monitored Tasks

The following tasks are automatically monitored:

1. **upstream.tasks.run_drift_detection** - Drift event detection
2. **upstream.tasks.send_alert** - Alert notification sending
3. **upstream.tasks.send_webhook** - Webhook delivery
4. **upstream.tasks.generate_report_artifact** - Report artifact generation (PDF/CSV)
5. **upstream.tasks.send_scheduled_report** - Scheduled report generation
6. **upstream.tasks.compute_report_drift** - Report-specific drift computation
7. **upstream.tasks.process_ingestion** - Data ingestion processing

## Integration with Kubernetes

### Liveness Probe

Use the health check endpoint for Kubernetes liveness probes:

```yaml
livenessProbe:
  httpGet:
    path: /api/celery/health/
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3
```

### Readiness Probe

```yaml
readinessProbe:
  httpGet:
    path: /api/celery/health/
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 2
```

## Integration with Prometheus

### Scrape Configuration

Add to `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'upstream-celery'
    static_configs:
      - targets: ['upstream:8000']
    metrics_path: '/metrics'
    scrape_interval: 15s
```

### Grafana Dashboard

Key metrics to monitor:

1. **Task Throughput**:
   - Rate of tasks started: `rate(upstream_background_job_started_total[5m])`
   - Rate of tasks completed: `rate(upstream_background_job_completed_total[5m])`

2. **Task Success Rate**:
   - Success rate: `rate(upstream_background_job_completed_total[5m]) / rate(upstream_background_job_started_total[5m])`
   - Failure rate: `rate(upstream_background_job_failed_total[5m]) / rate(upstream_background_job_started_total[5m])`

3. **Task Duration**:
   - P50 latency: `histogram_quantile(0.5, rate(upstream_background_job_duration_seconds_bucket[5m]))`
   - P95 latency: `histogram_quantile(0.95, rate(upstream_background_job_duration_seconds_bucket[5m]))`
   - P99 latency: `histogram_quantile(0.99, rate(upstream_background_job_duration_seconds_bucket[5m]))`

4. **Queue Depth** (manual check via API):
   - Monitor `/api/celery/stats/` for queue depth trends

## Alerting

### Prometheus Alerting Rules

```yaml
groups:
  - name: celery
    rules:
      # No workers running
      - alert: CeleryWorkersDown
        expr: up{job="upstream-celery"} == 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Celery workers are down"
          description: "No Celery workers have been detected for 5 minutes"

      # High task failure rate
      - alert: CeleryHighFailureRate
        expr: |
          rate(upstream_background_job_failed_total[5m]) /
          rate(upstream_background_job_started_total[5m]) > 0.1
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High Celery task failure rate"
          description: "More than 10% of tasks are failing"

      # Slow task execution
      - alert: CelerySlowTasks
        expr: |
          histogram_quantile(0.95,
            rate(upstream_background_job_duration_seconds_bucket[5m])
          ) > 300
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "Celery tasks are running slowly"
          description: "P95 task duration is over 5 minutes"

      # High queue depth
      - alert: CeleryHighQueueDepth
        expr: celery_queue_length > 1000
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Celery queue depth is high"
          description: "Queue has over 1000 pending tasks"
```

## Troubleshooting

### Workers Not Starting

**Symptoms:**
- `/api/celery/health/` returns 503
- `python manage.py celery_health` shows "UNHEALTHY"
- No workers in active_workers list

**Solutions:**
1. Check Redis/broker connectivity:
   ```bash
   redis-cli ping
   ```

2. Start workers manually:
   ```bash
   celery -A upstream worker --loglevel=info
   ```

3. Check worker logs for errors:
   ```bash
   celery -A upstream worker --loglevel=debug
   ```

### High Queue Depth

**Symptoms:**
- Queue depth > 1000
- Tasks taking long time to start
- `/api/celery/health/` returns "degraded"

**Solutions:**
1. Add more workers:
   ```bash
   # Start multiple worker instances
   celery -A upstream worker --loglevel=info --concurrency=4 -n worker1
   celery -A upstream worker --loglevel=info --concurrency=4 -n worker2
   ```

2. Investigate slow tasks:
   ```bash
   # Check task duration metrics
   curl http://localhost:8000/api/celery/stats/
   ```

3. Increase task timeout if appropriate:
   ```python
   # In settings.py
   CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
   ```

### Task Failures

**Symptoms:**
- High failure rate in metrics
- Errors in worker logs
- Tasks marked as failed in result backend

**Solutions:**
1. Check error types in Prometheus:
   ```promql
   upstream_background_job_failed_total
   ```

2. Review worker logs:
   ```bash
   celery -A upstream worker --loglevel=info
   ```

3. Add retry logic to tasks:
   ```python
   @shared_task(base=MonitoredTask, bind=True, max_retries=3)
   def my_task(self, arg1):
       try:
           # Task logic
           pass
       except Exception as exc:
           raise self.retry(exc=exc, countdown=60)
   ```

## Best Practices

1. **Always use MonitoredTask base class** for new tasks
2. **Set appropriate task timeouts** based on expected duration
3. **Implement retry logic** for transient failures
4. **Monitor queue depth** and scale workers accordingly
5. **Set up alerting** for critical metrics (workers down, high failure rate)
6. **Use task priorities** for important vs. background work
7. **Implement idempotency** for tasks that may be retried
8. **Log task progress** for long-running operations

## Related Documentation

- [Celery Configuration](../upstream/celery.py)
- [Task Definitions](../upstream/tasks.py)
- [Metrics Documentation](./METRICS.md)
- [Prometheus Integration](./PROMETHEUS.md)
