# Monitoring and Observability Guide

This document describes the monitoring and observability stack for Upstream.

## Overview

Upstream uses **Prometheus** for metrics collection and **Grafana** for visualization. The `django-prometheus` library automatically instruments Django to expose metrics.

## Architecture

```
┌─────────────┐     scrapes     ┌────────────┐     queries     ┌─────────┐
│   Django    │ ──────────────> │ Prometheus │ ◄────────────── │ Grafana │
│   /metrics  │                 │   :9090    │                 │  :3000  │
└─────────────┘                 └────────────┘                 └─────────┘
```

## Quick Start

### Running with Docker Compose

```bash
# Start all services including monitoring
docker-compose up -d

# Access services:
# - Application: http://localhost:8000
# - Prometheus: http://localhost:9090
# - Grafana: http://localhost:3000 (admin/admin)
```

### Accessing Metrics

The metrics endpoint is available at: `http://localhost:8000/metrics`

This endpoint exposes Prometheus-format metrics including:
- HTTP request counts and latencies
- Database query counts and durations
- Python interpreter statistics
- Cache hit/miss ratios

## Metrics Available

### HTTP Metrics
- `django_http_requests_total_by_method_total` - Total requests by HTTP method
- `django_http_requests_latency_seconds_by_view_method` - Request latency histogram
- `django_http_responses_total_by_status_total` - Response counts by status code

### Database Metrics
- `django_db_query_total` - Total database queries
- `django_db_query_duration_seconds` - Query duration histogram

### Model Metrics
- `django_model_inserts_total` - Model insert operations
- `django_model_updates_total` - Model update operations
- `django_model_deletes_total` - Model delete operations

### Cache Metrics
- `django_cache_get_total` - Cache get operations
- `django_cache_hits_total` - Cache hits
- `django_cache_misses_total` - Cache misses

## Grafana Dashboards

Pre-configured dashboards are available in `monitoring/grafana/dashboards/`:

1. **Upstream Application Monitoring** - Main dashboard showing:
   - HTTP request rate
   - Request latency (p95)
   - Error rates (4xx, 5xx)
   - Database query counts

### Importing Dashboards

1. Log in to Grafana at http://localhost:3000
2. Navigate to **Dashboards** → **Import**
3. Upload the JSON file from `monitoring/grafana/dashboards/upstream-dashboard.json`
4. Select **Prometheus** as the data source

## Configuration

### Prometheus

Configuration is in `monitoring/prometheus/prometheus.yml`:

- **Scrape interval**: 15 seconds
- **Targets**: Django web application at `web:8000`

### Grafana

- Default credentials: `admin/admin` (change in production)
- Data source: Prometheus at `http://prometheus:9090`

## Production Considerations

### Security

1. **Protect the metrics endpoint**: Add authentication
   ```python
   # In settings.py
   PROMETHEUS_EXPORT_MIGRATIONS = False  # Don't expose migration info
   ```

2. **Secure Grafana**: Change default password via environment variable:
   ```bash
   GRAFANA_PASSWORD=your-secure-password
   ```

3. **PHI Compliance**: The metrics do NOT contain PHI data - only aggregate counts and durations

### Alerting

Configure Prometheus alerting rules in `monitoring/prometheus/alerts.yml`:

```yaml
groups:
  - name: upstream_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(django_http_responses_total_by_status_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        annotations:
          summary: "High 5xx error rate detected"
```

### Retention

Prometheus default retention is 15 days. Adjust in docker-compose.yml:

```yaml
command:
  - '--storage.tsdb.retention.time=30d'
```

## Monitoring Celery Workers

For Celery worker monitoring, install celery-prometheus-exporter:

```bash
pip install celery-prometheus-exporter
```

Run the exporter alongside celery workers:

```bash
celery-prometheus-exporter --broker=redis://localhost:6379/0
```

## Troubleshooting

### Metrics endpoint returns 404

Ensure `django_prometheus` is in `INSTALLED_APPS` and URLs are configured:

```python
# hello_world/urls.py
path("", include("django_prometheus.urls")),
```

### Prometheus can't scrape Django

Check that:
1. Django is running and accessible at the configured port
2. Firewall rules allow traffic between containers
3. The `/metrics` endpoint is accessible: `curl http://localhost:8000/metrics`

### Grafana shows "No Data"

1. Verify Prometheus data source is configured correctly
2. Check Prometheus is scraping Django: Go to Prometheus → Status → Targets
3. Verify queries in dashboard panels match your metric names

## Best Practices

1. **Don't expose PHI**: Never log or expose patient identifiable information in metrics
2. **Use labels wisely**: Don't create high-cardinality labels (e.g., user IDs)
3. **Monitor what matters**: Focus on business metrics (drift detection rate, alert delivery success)
4. **Set up alerts**: Don't just collect metrics - alert on anomalies
5. **Regular review**: Review dashboards monthly and adjust as needs evolve

## Additional Resources

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [django-prometheus Documentation](https://github.com/korfuri/django-prometheus)
