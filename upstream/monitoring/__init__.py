"""
Monitoring module for platform health alerts.

This module provides platform-level monitoring and alerting for:
- High error rates (5xx responses)
- Slow response times (latency spikes)
- Database connection pool exhaustion
- Failed Celery background tasks

Different from business alerts (upstream.services.alert_processing):
- Business alerts: Notify customers about drift/delays in their data
- Platform alerts: Notify operators about system health and infrastructure
"""
