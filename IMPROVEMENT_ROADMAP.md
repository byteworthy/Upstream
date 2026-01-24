# Upstream Improvement Roadmap

**Generated:** 2026-01-24
**Status:** Brainstorming Phase
**Current Security Score:** 9.8/10 ✅

---

## Executive Summary

This document outlines potential improvements for the Upstream application across 8 key dimensions. Improvements are categorized by effort and impact to help prioritize implementation.

### Priority Matrix

| Category | Quick Wins | High Impact | Medium Impact | Nice to Have |
|----------|-----------|-------------|---------------|--------------|
| Performance | 3 items | 5 items | 4 items | 2 items |
| Features | 2 items | 4 items | 6 items | 3 items |
| Testing | 4 items | 3 items | 2 items | 1 item |
| DevEx | 5 items | 2 items | 3 items | 2 items |
| Operations | 2 items | 4 items | 3 items | 2 items |

---

## 🚀 Quick Wins (< 1 Day Each)

### QW-1: Implement TODO Comments
**Current State:** 3 TODO comments in `upstream/api/views.py`
**Effort:** 8 hours
**Impact:** Medium
**Files:** `upstream/api/views.py:248, 387, 557`

**Problem:**
- Line 248: Drift computation not triggered asynchronously
- Line 387: Trend data returns placeholder values
- Line 557: Ingestion processing not triggered

**Solution:**
```python
# Line 248 - Trigger async drift computation
from upstream.tasks import compute_drift_task
compute_drift_task.delay(report_run_id=report_run.id)

# Line 387 - Compute actual trend data
from django.db.models import Count, Avg
from datetime import timedelta

denial_trend = ClaimRecord.objects.filter(
    customer=customer,
    decided_date__gte=timezone.now().date() - timedelta(days=90)
).extra(select={'month': "DATE_TRUNC('month', decided_date)"}).values('month').annotate(
    total=Count('id'),
    denied=Count('id', filter=Q(outcome='DENIED'))
).order_by('month')

# Line 557 - Trigger async ingestion
from upstream.ingestion.tasks import process_ingestion_task
process_ingestion_task.delay(ingestion_id=ingestion.id)
```

**Benefits:**
- Real-time drift detection
- Accurate trend analytics
- Async processing prevents blocking

---

### QW-2: Add Database Indexes
**Effort:** 4 hours
**Impact:** High
**Priority:** 🔴 High

**Missing Indexes:**

```python
# upstream/models.py

class ClaimRecord(BaseModel):
    class Meta:
        indexes = [
            # Existing indexes
            models.Index(fields=['customer', 'decided_date']),
            models.Index(fields=['customer', 'payer']),

            # NEW: Add composite indexes for common queries
            models.Index(fields=['customer', 'outcome', 'decided_date']),  # For denial rate calculations
            models.Index(fields=['customer', 'payer', 'cpt_group']),  # For drift detection
            models.Index(fields=['customer', 'submitted_date', 'decided_date']),  # For lag analysis
        ]

class DriftEvent(BaseModel):
    class Meta:
        indexes = [
            # NEW: Add severity-based queries
            models.Index(fields=['customer', 'report_run', 'severity']),
            models.Index(fields=['customer', 'created_at', 'severity']),
            models.Index(fields=['payer', 'cpt_group', 'created_at']),  # For historical trends
        ]

class AlertEvent(BaseModel):
    class Meta:
        indexes = [
            # NEW: Alert dashboard queries
            models.Index(fields=['customer', 'status', 'triggered_at']),
            models.Index(fields=['customer', 'alert_rule', 'status']),
        ]
```

**Migration:**
```bash
python manage.py makemigrations --name add_performance_indexes
python manage.py migrate
```

**Expected Performance Gain:**
- 50-70% faster dashboard queries
- 40% faster drift detection
- 30% faster alert filtering

---

### QW-3: Add Request Compression
**Effort:** 2 hours
**Impact:** Medium

**Current State:** No response compression
**Solution:** Add GZip middleware

```python
# upstream/settings/base.py

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.gzip.GZipMiddleware',  # ADD THIS
    'whitenoise.middleware.WhiteNoiseMiddleware',
    # ... rest of middleware
]

# Also add in production
MIDDLEWARE.insert(1, 'django.middleware.http.ConditionalGetMiddleware')  # ETag support
```

**Benefits:**
- 60-80% reduction in response size for JSON/HTML
- Faster page loads
- Reduced bandwidth costs

---

### QW-4: Add Query Result Caching
**Effort:** 6 hours
**Impact:** High

**Current State:** Only payer/CPT mappings are cached
**Solution:** Cache expensive dashboard queries

```python
# upstream/api/views.py

from django.core.cache import cache
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator

class DashboardView(LoginRequiredMixin, APIView):
    @method_decorator(cache_page(60 * 5))  # Cache for 5 minutes
    def get(self, request):
        # ... existing code

# For function-based caching
from upstream.cache import cache_result

@cache_result('dashboard_stats_{customer_id}', ttl=300)
def get_dashboard_stats(customer):
    return {
        'total_claims': ClaimRecord.objects.filter(customer=customer).count(),
        'denial_rate': calculate_denial_rate(customer),
        'active_alerts': AlertEvent.objects.filter(
            customer=customer,
            status='active'
        ).count(),
    }
```

**What to Cache:**
- Dashboard aggregations (5 min TTL)
- Report run summaries (15 min TTL)
- Payer statistics (10 min TTL)
- Quality scorecards (5 min TTL)

**Cache Invalidation:**
```python
# When new data arrives
from django.core.cache import cache

def invalidate_dashboard_cache(customer_id):
    cache_keys = [
        f'dashboard_stats_{customer_id}',
        f'payer_summary_{customer_id}',
        f'quality_scorecard_{customer_id}',
    ]
    cache.delete_many(cache_keys)
```

---

### QW-5: Add API Rate Limiting
**Effort:** 3 hours
**Impact:** Medium
**Priority:** 🟡 Medium

**Current State:** No rate limiting
**Solution:** Add Django REST framework throttling

```python
# upstream/settings/base.py

REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
        'upload': '10/hour',  # Custom rate for uploads
    }
}
```

```python
# upstream/api/views.py

from rest_framework.throttling import UserRateThrottle

class UploadRateThrottle(UserRateThrottle):
    rate = '10/hour'

class UploadAPIView(APIView):
    throttle_classes = [UploadRateThrottle]
    # ... rest of view
```

**Benefits:**
- Prevents API abuse
- Protects against DoS
- Fair resource allocation

---

## ⚡ Performance Improvements

### P-1: Implement Celery Task Queue
**Effort:** 2 days
**Impact:** High
**Priority:** 🔴 High

**Current State:** Synchronous processing blocks requests
**Problem Areas:**
1. CSV upload processing (can take 30+ seconds)
2. Drift detection computation
3. Report generation (PDF/Excel)
4. Email sending

**Solution Architecture:**

```python
# upstream/celery.py (NEW FILE)
import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hello_world.settings')

app = Celery('upstream')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Periodic tasks
app.conf.beat_schedule = {
    'run-weekly-drift-detection': {
        'task': 'upstream.tasks.run_weekly_drift_detection',
        'schedule': crontab(hour=2, minute=0, day_of_week='monday'),
    },
    'cleanup-old-reports': {
        'task': 'upstream.tasks.cleanup_old_reports',
        'schedule': crontab(hour=3, minute=0),
    },
}
```

```python
# upstream/tasks.py (NEW FILE)
from celery import shared_task
from django.core.mail import send_mail
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def process_upload_async(self, upload_id):
    """Process uploaded CSV file asynchronously."""
    try:
        from upstream.models import Upload
        upload = Upload.objects.get(id=upload_id)

        # Process CSV
        from upstream.views import UploadsView
        view = UploadsView()
        view.process_csv_upload(upload, upload.csv_file)

        upload.status = 'success'
        upload.save()

        # Send notification email
        send_upload_completion_email.delay(upload_id)

    except Exception as exc:
        logger.error(f"Upload processing failed: {exc}", exc_info=True)
        upload.status = 'failed'
        upload.error_message = str(exc)
        upload.save()
        raise self.retry(exc=exc, countdown=60)

@shared_task
def compute_drift_task(report_run_id):
    """Compute drift detection for a report run."""
    from upstream.drift.services import DriftDetectionService
    service = DriftDetectionService()
    service.detect_drift(report_run_id)

@shared_task
def generate_report_async(report_run_id, format='pdf'):
    """Generate report artifact asynchronously."""
    from upstream.reporting.services import (
        generate_weekly_drift_pdf,
        generate_drift_events_csv
    )
    from upstream.models import ReportRun

    report_run = ReportRun.objects.get(id=report_run_id)

    if format == 'pdf':
        artifact = generate_weekly_drift_pdf(report_run_id)
    else:
        artifact = generate_drift_events_csv(report_run, {})

    # Notify user
    send_report_ready_email.delay(report_run.customer.id, artifact.id)

    return artifact.id

@shared_task
def send_upload_completion_email(upload_id):
    """Send email notification when upload completes."""
    from upstream.models import Upload
    upload = Upload.objects.get(id=upload_id)

    send_mail(
        subject=f'Upload Complete: {upload.filename}',
        message=f'Your upload of {upload.filename} has been processed successfully.',
        from_email='alerts@upstream.cx',
        recipient_list=[upload.customer.settings.to_email],
    )

@shared_task
def run_weekly_drift_detection():
    """Run drift detection for all active customers."""
    from upstream.models import Customer
    from upstream.drift.services import DriftDetectionService

    service = DriftDetectionService()
    for customer in Customer.objects.filter(is_active=True):
        try:
            report_run = service.create_weekly_report(customer)
            compute_drift_task.delay(report_run.id)
        except Exception as e:
            logger.error(f"Weekly drift failed for {customer.name}: {e}")

@shared_task
def cleanup_old_reports():
    """Delete report artifacts older than 90 days."""
    from datetime import timedelta
    from django.utils import timezone
    from upstream.reporting.models import ReportArtifact

    cutoff_date = timezone.now() - timedelta(days=90)
    old_artifacts = ReportArtifact.objects.filter(created_at__lt=cutoff_date)

    count = 0
    for artifact in old_artifacts:
        if artifact.file_path and os.path.exists(artifact.file_path):
            os.remove(artifact.file_path)
        artifact.delete()
        count += 1

    logger.info(f"Cleaned up {count} old report artifacts")
```

**Configuration:**

```python
# upstream/settings/base.py

# Celery Configuration
CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 minutes
```

**Benefits:**
- Non-blocking CSV uploads
- Background drift detection
- Scheduled weekly reports
- Better user experience
- Horizontal scalability

---

### P-2: Optimize N+1 Queries
**Effort:** 1 day
**Impact:** High
**Priority:** 🔴 High

**Current Issues:**

```python
# BEFORE: N+1 query problem
# upstream/api/views.py - DriftEventListView

drift_events = DriftEvent.objects.filter(customer=customer)
for event in drift_events:
    print(event.report_run.started_at)  # 1 query per event!
```

**Solution:**

```python
# AFTER: Use select_related / prefetch_related

drift_events = DriftEvent.objects.filter(
    customer=customer
).select_related(
    'customer',
    'report_run'
).prefetch_related(
    'alert_events__operator_judgments__operator'
)

# Reduces 100 queries to 3 queries!
```

**Other Hot Spots:**

```python
# upstream/api/views.py

class AlertEventListView(ListAPIView):
    def get_queryset(self):
        return AlertEvent.objects.filter(
            customer=self.request.user.profile.customer
        ).select_related(
            'alert_rule',
            'drift_event',
            'report_run'
        ).prefetch_related(
            'operator_judgments__operator',
            'operator_judgments__operator__profile'
        ).order_by('-triggered_at')

class ReportRunDetailView(RetrieveAPIView):
    def get_queryset(self):
        return ReportRun.objects.select_related(
            'customer'
        ).prefetch_related(
            'drift_events',
            'artifacts',
            'alert_events__alert_rule'
        )
```

**Monitoring:**

```python
# Add to middleware for development
# upstream/middleware/query_counter.py

from django.db import connection
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class QueryCountDebugMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.DEBUG:
            queries_before = len(connection.queries)

        response = self.get_response(request)

        if settings.DEBUG:
            queries_after = len(connection.queries)
            num_queries = queries_after - queries_before

            if num_queries > 20:
                logger.warning(
                    f"High query count: {num_queries} queries for {request.path}"
                )

        return response
```

---

### P-3: Add Database Connection Pooling
**Effort:** 4 hours
**Impact:** Medium

**Current State:** Default Django connection handling
**Solution:** Use pgbouncer or django-db-geventpool

```python
# upstream/settings/prod.py

DATABASES = {
    'default': {
        'ENGINE': 'django_db_geventpool.backends.postgresql_psycopg2',
        'OPTIONS': {
            'MAX_CONNS': 20,
            'REUSE_CONNS': 10,
        },
        # ... other settings
    }
}
```

**Or use PgBouncer:**

```ini
# pgbouncer.ini
[databases]
upstream = host=localhost port=5432 dbname=upstream

[pgbouncer]
listen_port = 6432
listen_addr = 127.0.0.1
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = transaction
max_client_conn = 100
default_pool_size = 20
```

```python
# .env.production
DATABASE_URL=postgres://user:pass@localhost:6432/upstream
```

**Benefits:**
- Reduced connection overhead
- Better resource utilization
- Handles connection spikes

---

### P-4: Implement Read Replicas
**Effort:** 2 days
**Impact:** High (for scale)

**Solution:**

```python
# upstream/settings/prod.py

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'upstream',
        'USER': 'upstream_user',
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST_PRIMARY'),
        'PORT': '5432',
    },
    'replica': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'upstream',
        'USER': 'upstream_readonly',
        'PASSWORD': os.getenv('DB_PASSWORD_READONLY'),
        'HOST': os.getenv('DB_HOST_REPLICA'),
        'PORT': '5432',
    }
}

# Database router
class UpstreamDBRouter:
    """Route reads to replica, writes to primary."""

    def db_for_read(self, model, **hints):
        """Send reads to replica."""
        if model._meta.app_label == 'upstream':
            return 'replica'
        return 'default'

    def db_for_write(self, model, **hints):
        """Send writes to primary."""
        return 'default'

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Only migrate on primary."""
        return db == 'default'

DATABASE_ROUTERS = ['upstream.routers.UpstreamDBRouter']
```

**Usage:**

```python
# Explicit database selection
ClaimRecord.objects.using('replica').filter(customer=customer)

# Force write database for consistency
with transaction.atomic(using='default'):
    claim = ClaimRecord.objects.create(...)
```

---

### P-5: Add Redis Caching Layer
**Effort:** 1 day
**Impact:** High

**Current State:** In-memory cache only
**Solution:** Redis for distributed caching

```python
# upstream/settings/prod.py

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'PARSER_CLASS': 'redis.connection.HiredisParser',
            'CONNECTION_POOL_KWARGS': {'max_connections': 50},
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
            'IGNORE_EXCEPTIONS': True,  # Graceful degradation
        }
    },
    'sessions': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/2'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Use Redis for sessions
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'sessions'
```

**Cache Warming:**

```python
# upstream/management/commands/warm_cache.py

from django.core.management.base import BaseCommand
from django.core.cache import cache
from upstream.models import Customer

class Command(BaseCommand):
    help = 'Warm cache with frequently accessed data'

    def handle(self, *args, **options):
        for customer in Customer.objects.all():
            # Warm payer mappings
            from upstream.views import get_payer_mappings_cached
            get_payer_mappings_cached(customer)

            # Warm CPT mappings
            from upstream.views import get_cpt_mappings_cached
            get_cpt_mappings_cached(customer)

            self.stdout.write(f'Warmed cache for {customer.name}')
```

---

## 🎨 Feature Enhancements

### F-1: Real-Time Notifications with WebSockets
**Effort:** 3 days
**Impact:** High
**Priority:** 🟠 Medium

**Current State:** User must refresh to see new alerts
**Solution:** Django Channels + WebSocket notifications

```python
# requirements.txt
channels==4.0.0
channels-redis==4.1.0
daphne==4.0.0

# hello_world/asgi.py
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hello_world.settings')

django_asgi_app = get_asgi_application()

from upstream.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        )
    ),
})
```

```python
# upstream/consumers.py (NEW FILE)
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async

class NotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        if not self.user.is_authenticated:
            await self.close()
            return

        # Join customer notification group
        self.customer_id = await self.get_customer_id()
        self.group_name = f'notifications_{self.customer_id}'

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def notification_message(self, event):
        """Send notification to WebSocket."""
        await self.send_json(event['data'])

    @database_sync_to_async
    def get_customer_id(self):
        return self.user.profile.customer.id
```

```python
# upstream/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

@receiver(post_save, sender=AlertEvent)
def notify_new_alert(sender, instance, created, **kwargs):
    """Send real-time notification when alert is created."""
    if created:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'notifications_{instance.customer.id}',
            {
                'type': 'notification_message',
                'data': {
                    'type': 'new_alert',
                    'alert_id': instance.id,
                    'severity': instance.payload.get('severity'),
                    'payer': instance.payload.get('payer'),
                    'message': f'New alert detected for {instance.payload.get("payer")}'
                }
            }
        )
```

**Frontend:**

```javascript
// upstream/templates/upstream/base.html

const ws = new WebSocket(
    'ws://' + window.location.host + '/ws/notifications/'
);

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);

    if (data.type === 'new_alert') {
        showNotificationToast(data.message);
        updateAlertBadge();
    } else if (data.type === 'upload_complete') {
        showNotificationToast('Upload completed successfully');
        refreshUploadList();
    }
};

function showNotificationToast(message) {
    // Show browser notification
    if (Notification.permission === 'granted') {
        new Notification('Upstream Alert', {
            body: message,
            icon: '/static/img/logo.png'
        });
    }
}
```

**Benefits:**
- Real-time alert notifications
- Upload progress updates
- Live dashboard updates
- Better user experience

---

### F-2: Advanced Data Export Options
**Effort:** 2 days
**Impact:** Medium

**Current State:** Basic CSV/PDF exports
**Enhancements:**

```python
# upstream/api/views.py

class ExportAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Export data in various formats."""
        export_type = request.data.get('type')  # 'drift_events', 'claims', 'alerts'
        format = request.data.get('format')  # 'csv', 'excel', 'json', 'pdf'
        filters = request.data.get('filters', {})

        # Queue export job
        from upstream.tasks import generate_export_async
        task = generate_export_async.delay(
            customer_id=request.user.profile.customer.id,
            export_type=export_type,
            format=format,
            filters=filters,
            user_email=request.user.email
        )

        return Response({
            'task_id': task.id,
            'status': 'queued',
            'message': 'Export queued. You will receive an email when ready.'
        })

    def get(self, request):
        """Check export status."""
        task_id = request.query_params.get('task_id')
        result = AsyncResult(task_id)

        return Response({
            'task_id': task_id,
            'status': result.state,
            'result': result.result if result.ready() else None
        })
```

**Excel Export with Formatting:**

```python
# upstream/exports/excel_service.py

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.chart import BarChart, Reference

class ExcelExportService:
    def export_drift_analysis(self, report_run):
        """Create Excel workbook with multiple sheets and charts."""
        wb = Workbook()

        # Sheet 1: Executive Summary
        ws_summary = wb.active
        ws_summary.title = 'Executive Summary'
        self._create_summary_sheet(ws_summary, report_run)

        # Sheet 2: Detailed Drift Events
        ws_details = wb.create_sheet('Drift Events')
        self._create_details_sheet(ws_details, report_run)

        # Sheet 3: Payer Analysis
        ws_payers = wb.create_sheet('Payer Analysis')
        self._create_payer_analysis(ws_payers, report_run)

        # Sheet 4: Charts
        ws_charts = wb.create_sheet('Visualizations')
        self._add_charts(ws_charts, report_run)

        return wb

    def _add_charts(self, ws, report_run):
        """Add charts to worksheet."""
        # Bar chart of drift events by payer
        chart = BarChart()
        chart.title = 'Drift Events by Payer'
        chart.x_axis.title = 'Payer'
        chart.y_axis.title = 'Number of Events'

        # Add data
        data = Reference(ws, min_col=2, min_row=1, max_row=20)
        cats = Reference(ws, min_col=1, min_row=2, max_row=20)
        chart.add_data(data, titles_from_data=True)
        chart.set_categories(cats)

        ws.add_chart(chart, 'E5')
```

---

### F-3: Interactive Dashboard Widgets
**Effort:** 3 days
**Impact:** High

**Current State:** Static dashboard
**Solution:** Draggable, customizable widgets

```javascript
// Use Grid.js or similar
// upstream/static/js/dashboard-widgets.js

class DashboardManager {
    constructor() {
        this.grid = GridStack.init({
            cellHeight: 80,
            acceptWidgets: true,
            removable: true
        });

        this.loadLayout();
    }

    loadLayout() {
        // Load user's saved layout
        fetch('/api/v1/dashboard/layout/')
            .then(r => r.json())
            .then(layout => {
                this.grid.load(layout.widgets || this.getDefaultLayout());
            });
    }

    saveLayout() {
        const layout = this.grid.save();
        fetch('/api/v1/dashboard/layout/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({ widgets: layout })
        });
    }

    getDefaultLayout() {
        return [
            { x: 0, y: 0, w: 6, h: 2, content: '<div class="widget" data-widget="alert-summary"></div>' },
            { x: 6, y: 0, w: 6, h: 2, content: '<div class="widget" data-widget="denial-rate"></div>' },
            { x: 0, y: 2, w: 12, h: 4, content: '<div class="widget" data-widget="drift-timeline"></div>' },
        ];
    }
}
```

**Widget Types:**
1. Alert Summary Card
2. Denial Rate Trend
3. Drift Timeline
4. Top Payers Table
5. Quality Score Gauge
6. Recent Activity Feed
7. Quick Actions Panel

---

### F-4: Smart Alert Deduplication
**Effort:** 2 days
**Impact:** Medium

**Problem:** Multiple alerts for same issue
**Solution:** Intelligent grouping

```python
# upstream/alerts/deduplication.py

from datetime import timedelta
from django.utils import timezone
from upstream.alerts.models import AlertEvent

class AlertDeduplicationService:
    def __init__(self, customer):
        self.customer = customer

    def should_create_alert(self, drift_event, alert_rule):
        """
        Check if we should create a new alert or group with existing.

        Grouping criteria:
        - Same payer + CPT group
        - Within 24 hours
        - Similar severity (within 0.1)
        - Same alert rule
        """
        cutoff = timezone.now() - timedelta(hours=24)

        similar_alerts = AlertEvent.objects.filter(
            customer=self.customer,
            alert_rule=alert_rule,
            drift_event__payer=drift_event.payer,
            drift_event__cpt_group=drift_event.cpt_group,
            triggered_at__gte=cutoff,
            status__in=['active', 'acknowledged']
        ).exists()

        if similar_alerts:
            self._increment_alert_count(drift_event, alert_rule)
            return False

        return True

    def _increment_alert_count(self, drift_event, alert_rule):
        """Update existing alert with new occurrence."""
        alert = AlertEvent.objects.filter(
            customer=self.customer,
            alert_rule=alert_rule,
            drift_event__payer=drift_event.payer,
            drift_event__cpt_group=drift_event.cpt_group,
        ).order_by('-triggered_at').first()

        if alert:
            metadata = alert.payload.get('metadata', {})
            metadata['occurrence_count'] = metadata.get('occurrence_count', 1) + 1
            metadata['last_seen'] = timezone.now().isoformat()
            alert.payload['metadata'] = metadata
            alert.save()
```

---

### F-5: Predictive Analytics Dashboard
**Effort:** 1 week
**Impact:** High
**Priority:** 🟢 Low (Future)

**Concept:** Use ML to predict denial rates and drift

```python
# upstream/ml/predictor.py

from sklearn.ensemble import RandomForestRegressor
import numpy as np

class DenialRatePredictor:
    def __init__(self, customer):
        self.customer = customer
        self.model = None

    def train(self):
        """Train model on historical data."""
        # Get training data
        claims = ClaimRecord.objects.filter(
            customer=self.customer,
            decided_date__isnull=False
        ).values('payer', 'cpt_group', 'submitted_date', 'outcome')

        # Feature engineering
        X, y = self._prepare_features(claims)

        # Train model
        self.model = RandomForestRegressor(n_estimators=100)
        self.model.fit(X, y)

    def predict_next_month(self, payer, cpt_group):
        """Predict denial rate for next month."""
        features = self._extract_features(payer, cpt_group)
        return self.model.predict([features])[0]

    def _prepare_features(self, claims):
        """Convert claims to feature vectors."""
        # Features: payer_id, cpt_group_id, month, day_of_week,
        #           historical_denial_rate, claim_volume
        pass
```

---

## 🧪 Testing & Quality Improvements

### T-1: Implement Automated Testing Pipeline
**Effort:** 3 days
**Impact:** High
**Priority:** 🔴 High

**Current State:** Limited test coverage
**Solution:** Comprehensive test suite

```bash
# .github/workflows/test.yml

name: Test Suite

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:14
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-django pytest-cov

      - name: Run tests
        env:
          DATABASE_URL: postgres://postgres:postgres@localhost:5432/test_db
          REDIS_URL: redis://localhost:6379/0
        run: |
          pytest --cov=upstream --cov-report=xml --cov-report=html

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

**Test Structure:**

```python
# upstream/tests/test_views.py

import pytest
from django.test import Client
from upstream.models import Customer, ClaimRecord

@pytest.mark.django_db
class TestUploadView:
    def test_upload_valid_csv(self, client, authenticated_user, sample_csv):
        """Test successful CSV upload."""
        response = client.post('/uploads/', {
            'csv_file': sample_csv
        })
        assert response.status_code == 302
        assert Upload.objects.count() == 1

    def test_upload_exceeds_size_limit(self, client, authenticated_user, large_csv):
        """Test file size validation."""
        response = client.post('/uploads/', {
            'csv_file': large_csv
        })
        assert response.status_code == 302
        assert 'File too large' in response.messages

    def test_upload_wrong_extension(self, client, authenticated_user):
        """Test file extension validation."""
        response = client.post('/uploads/', {
            'csv_file': SimpleUploadedFile('test.txt', b'content')
        })
        assert 'Only CSV files' in response.messages

# upstream/tests/test_api.py

@pytest.mark.django_db
class TestDriftEventAPI:
    def test_list_drift_events(self, api_client, sample_drift_events):
        """Test drift event listing."""
        response = api_client.get('/api/v1/drift-events/')
        assert response.status_code == 200
        assert len(response.json()['results']) == 5

    def test_drift_event_filtering(self, api_client, sample_drift_events):
        """Test severity filtering."""
        response = api_client.get('/api/v1/drift-events/?min_severity=0.7')
        assert all(e['severity'] >= 0.7 for e in response.json()['results'])

# upstream/tests/fixtures.py

@pytest.fixture
def sample_csv():
    """Create sample CSV file for testing."""
    content = b"""payer,cpt,submitted_date,decided_date,outcome,allowed_amount
Medicare,99213,2024-01-01,2024-01-15,PAID,75.00
Aetna,99214,2024-01-02,2024-01-16,DENIED,0.00"""
    return SimpleUploadedFile('test.csv', content, content_type='text/csv')

@pytest.fixture
def authenticated_user(db):
    """Create authenticated user with customer."""
    customer = Customer.objects.create(name='Test Customer')
    user = User.objects.create_user('test@example.com', password='test')
    UserProfile.objects.create(user=user, customer=customer)
    return user
```

**Test Coverage Goals:**
- Unit tests: 80%+ coverage
- Integration tests: Key workflows
- API tests: All endpoints
- Security tests: Injection attempts

---

### T-2: Add Performance Testing
**Effort:** 2 days
**Impact:** Medium

```python
# locustfile.py

from locust import HttpUser, task, between

class UpstreamUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        """Login before testing."""
        self.client.post('/login/', {
            'username': 'test@example.com',
            'password': 'test123'
        })

    @task(3)
    def view_dashboard(self):
        """View dashboard (most common)."""
        self.client.get('/dashboard/')

    @task(2)
    def view_drift_events(self):
        """View drift events."""
        self.client.get('/api/v1/drift-events/')

    @task(1)
    def upload_csv(self):
        """Upload CSV file."""
        with open('test_data.csv', 'rb') as f:
            self.client.post('/uploads/', {
                'csv_file': f
            })

    @task(2)
    def view_alerts(self):
        """View alerts."""
        self.client.get('/api/v1/alerts/')
```

**Run Load Tests:**

```bash
# Install locust
pip install locust

# Run test
locust -f locustfile.py --host=http://localhost:8000

# Or headless
locust -f locustfile.py --host=http://localhost:8000 \
    --users 100 --spawn-rate 10 --run-time 5m --headless
```

---

### T-3: Add E2E Testing with Playwright
**Effort:** 3 days
**Impact:** Medium

```javascript
// tests/e2e/upload.spec.js

const { test, expect } = require('@playwright/test');

test.describe('CSV Upload Flow', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto('http://localhost:8000/login/');
        await page.fill('input[name="username"]', 'test@example.com');
        await page.fill('input[name="password"]', 'test123');
        await page.click('button[type="submit"]');
    });

    test('should upload CSV successfully', async ({ page }) => {
        await page.goto('/uploads/');

        // Upload file
        const fileInput = page.locator('input[type="file"]');
        await fileInput.setInputFiles('test_data.csv');
        await page.click('button:has-text("Upload")');

        // Wait for success message
        await expect(page.locator('.alert-success')).toBeVisible();
        await expect(page.locator('.alert-success')).toContainText('Successfully uploaded');

        // Verify upload appears in list
        await expect(page.locator('table tbody tr').first()).toContainText('test_data.csv');
    });

    test('should show error for large file', async ({ page }) => {
        await page.goto('/uploads/');

        const fileInput = page.locator('input[type="file"]');
        await fileInput.setInputFiles('large_file.csv');  // 200MB file
        await page.click('button:has-text("Upload")');

        await expect(page.locator('.alert-error')).toContainText('File too large');
    });
});

test.describe('Dashboard', () => {
    test('should display drift events', async ({ page }) => {
        await page.goto('/dashboard/');

        // Check for alert cards
        await expect(page.locator('.alert-card')).toHaveCount(3);

        // Check chart is loaded
        await expect(page.locator('canvas#drift-chart')).toBeVisible();

        // Check table has data
        const rows = page.locator('table tbody tr');
        await expect(rows).toHaveCountGreaterThan(0);
    });
});
```

---

### T-4: Add Security Scanning
**Effort:** 1 day
**Impact:** High

```yaml
# .github/workflows/security.yml

name: Security Scan

on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM
  push:
    branches: [main]

jobs:
  security:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Run Bandit (Python security)
        run: |
          pip install bandit
          bandit -r upstream/ -f json -o bandit-report.json

      - name: Run Safety (dependency check)
        run: |
          pip install safety
          safety check --json > safety-report.json

      - name: Run npm audit
        run: |
          npm audit --json > npm-audit.json

      - name: Upload reports
        uses: actions/upload-artifact@v3
        with:
          name: security-reports
          path: |
            bandit-report.json
            safety-report.json
            npm-audit.json
```

---

## 👨‍💻 Developer Experience Improvements

### DX-1: Add Pre-commit Hooks
**Effort:** 2 hours
**Impact:** High

```yaml
# .pre-commit-config.yaml

repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: check-json
      - id: check-merge-conflict

  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
        language_version: python3.11

  - repo: https://github.com/PyCQA/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
        args: ['--max-line-length=120', '--extend-ignore=E203,W503']

  - repo: https://github.com/PyCQA/isort
    rev: 5.12.0
    hooks:
      - id: isort
        args: ['--profile', 'black']

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.3.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
```

**Install:**

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

---

### DX-2: Add Development Docker Compose
**Effort:** 4 hours
**Impact:** High

```yaml
# docker-compose.dev.yml

version: '3.8'

services:
  db:
    image: postgres:14
    environment:
      POSTGRES_DB: upstream
      POSTGRES_USER: upstream
      POSTGRES_PASSWORD: upstream
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7
    ports:
      - "6379:6379"

  web:
    build: .
    command: python manage.py runserver 0.0.0.0:8000
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    env_file:
      - .env
    depends_on:
      - db
      - redis

  celery:
    build: .
    command: celery -A hello_world worker --loglevel=info
    volumes:
      - .:/app
    env_file:
      - .env
    depends_on:
      - db
      - redis

  celery-beat:
    build: .
    command: celery -A hello_world beat --loglevel=info
    volumes:
      - .:/app
    env_file:
      - .env
    depends_on:
      - db
      - redis

volumes:
  postgres_data:
```

**Usage:**

```bash
docker-compose -f docker-compose.dev.yml up
docker-compose -f docker-compose.dev.yml run web python manage.py migrate
docker-compose -f docker-compose.dev.yml run web python manage.py createsuperuser
```

---

### DX-3: Add API Documentation with Swagger UI
**Effort:** 4 hours
**Impact:** Medium

**Current State:** drf-spectacular installed but not fully configured

```python
# upstream/settings/base.py

SPECTACULAR_SETTINGS = {
    'TITLE': 'Upstream API',
    'DESCRIPTION': 'Healthcare claims drift detection and analytics API',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SCHEMA_PATH_PREFIX': r'/api/v[0-9]',
    'SERVE_AUTHENTICATION': ['rest_framework.authentication.SessionAuthentication'],
    'SERVE_PERMISSIONS': ['rest_framework.permissions.IsAuthenticated'],
    'PREPROCESSING_HOOKS': [
        'drf_spectacular.hooks.preprocess_exclude_path_format',
    ],
    'POSTPROCESSING_HOOKS': [
        'drf_spectacular.contrib.djangorestframework_camel_case.camelize_serializer_fields',
    ],
    'TAGS': [
        {'name': 'Drift Events', 'description': 'Drift detection and analysis'},
        {'name': 'Alerts', 'description': 'Alert management and feedback'},
        {'name': 'Uploads', 'description': 'CSV file uploads'},
        {'name': 'Reports', 'description': 'Report generation and retrieval'},
        {'name': 'Quality', 'description': 'Data quality metrics'},
    ],
}

# hello_world/urls.py

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    # ... other patterns
]
```

**Access:**
- Swagger UI: `http://localhost:8000/api/docs/`
- ReDoc: `http://localhost:8000/api/redoc/`
- Schema: `http://localhost:8000/api/schema/`

---

### DX-4: Add Database Seeding for Development
**Effort:** 1 day
**Impact:** Medium

```python
# upstream/management/commands/seed_data.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import random

class Command(BaseCommand):
    help = 'Seed database with test data for development'

    def add_arguments(self, parser):
        parser.add_argument('--customers', type=int, default=2)
        parser.add_argument('--claims', type=int, default=1000)
        parser.add_argument('--drift-events', type=int, default=50)

    def handle(self, *args, **options):
        from upstream.models import (
            Customer, Upload, ClaimRecord,
            DriftEvent, ReportRun
        )

        # Create customers
        customers = []
        for i in range(options['customers']):
            customer = Customer.objects.create(
                name=f'Test Hospital {i+1}'
            )
            customers.append(customer)
            self.stdout.write(f'Created customer: {customer.name}')

        # Create uploads and claims
        for customer in customers:
            upload = Upload.objects.create(
                customer=customer,
                filename='seed_data.csv',
                status='success',
                row_count=options['claims']
            )

            # Create claims
            payers = ['Medicare', 'Medicaid', 'Blue Cross', 'Aetna', 'UnitedHealth']
            cpts = ['99213', '99214', '99215', '99203', '99204']
            outcomes = ['PAID', 'DENIED', 'OTHER']

            for i in range(options['claims']):
                decided_date = timezone.now().date() - timedelta(days=random.randint(1, 365))

                ClaimRecord.objects.create(
                    customer=customer,
                    upload=upload,
                    payer=random.choice(payers),
                    cpt=random.choice(cpts),
                    cpt_group='E&M',
                    submitted_date=decided_date - timedelta(days=random.randint(7, 30)),
                    decided_date=decided_date,
                    outcome=random.choice(outcomes),
                    allowed_amount=random.uniform(50, 200) if random.random() > 0.3 else 0
                )

            self.stdout.write(f'Created {options["claims"]} claims for {customer.name}')

            # Create report run
            report_run = ReportRun.objects.create(
                customer=customer,
                run_type='weekly',
                status='completed',
                started_at=timezone.now() - timedelta(hours=1),
                finished_at=timezone.now(),
                summary_json={
                    'baseline_start': '2024-01-01',
                    'baseline_end': '2024-01-31',
                    'current_start': '2024-02-01',
                    'current_end': '2024-02-28',
                }
            )

            # Create drift events
            for i in range(options['drift_events']):
                DriftEvent.objects.create(
                    customer=customer,
                    report_run=report_run,
                    payer=random.choice(payers),
                    cpt_group='E&M',
                    drift_type='denial_rate',
                    baseline_value=random.uniform(0.1, 0.3),
                    current_value=random.uniform(0.2, 0.5),
                    delta_value=random.uniform(0.1, 0.2),
                    severity=random.uniform(0.3, 0.9),
                    confidence=random.uniform(0.7, 0.95),
                    baseline_start=timezone.now().date() - timedelta(days=60),
                    baseline_end=timezone.now().date() - timedelta(days=30),
                    current_start=timezone.now().date() - timedelta(days=30),
                    current_end=timezone.now().date()
                )

            self.stdout.write(f'Created {options["drift_events"]} drift events for {customer.name}')

        self.stdout.write(self.style.SUCCESS('Database seeded successfully!'))
```

**Usage:**

```bash
python manage.py seed_data --customers 3 --claims 5000 --drift-events 100
```

---

### DX-5: Add Makefile for Common Commands
**Effort:** 1 hour
**Impact:** Medium

```makefile
# Makefile

.PHONY: help install migrate test run clean seed docker-up docker-down

help:
	@echo "Available commands:"
	@echo "  make install      - Install dependencies"
	@echo "  make migrate      - Run database migrations"
	@echo "  make test         - Run test suite"
	@echo "  make run          - Start development server"
	@echo "  make clean        - Clean Python cache files"
	@echo "  make seed         - Seed database with test data"
	@echo "  make docker-up    - Start Docker containers"
	@echo "  make docker-down  - Stop Docker containers"
	@echo "  make format       - Format code with black"
	@echo "  make lint         - Run linters"

install:
	pip install -r requirements.txt
	pre-commit install

migrate:
	python manage.py migrate

test:
	pytest --cov=upstream --cov-report=html

run:
	python manage.py runserver

clean:
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -delete
	find . -type d -name '*.egg-info' -exec rm -rf {} +
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .pytest_cache/

seed:
	python manage.py seed_data --customers 3 --claims 1000 --drift-events 50

docker-up:
	docker-compose -f docker-compose.dev.yml up -d

docker-down:
	docker-compose -f docker-compose.dev.yml down

format:
	black upstream/
	isort upstream/

lint:
	flake8 upstream/
	mypy upstream/
	bandit -r upstream/

shell:
	python manage.py shell_plus

db-reset:
	python manage.py reset_db --noinput
	python manage.py migrate
	python manage.py seed_data
```

---

## 📊 Operations & Monitoring

### O-1: Add Application Performance Monitoring (APM)
**Effort:** 1 day
**Impact:** High

**Solution:** Integrate Sentry + New Relic/DataDog

```python
# requirements.txt
sentry-sdk==1.40.0
newrelic==9.4.0

# upstream/settings/prod.py

import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.redis import RedisIntegration

sentry_sdk.init(
    dsn=os.getenv('SENTRY_DSN'),
    integrations=[
        DjangoIntegration(),
        CeleryIntegration(),
        RedisIntegration(),
    ],
    traces_sample_rate=0.1,  # 10% of transactions
    profiles_sample_rate=0.1,
    send_default_pii=False,
    environment=os.getenv('ENVIRONMENT', 'production'),
    release=os.getenv('GIT_COMMIT_SHA'),
    before_send=filter_sensitive_data,
)

def filter_sensitive_data(event, hint):
    """Remove sensitive data before sending to Sentry."""
    if 'request' in event:
        # Remove authorization headers
        if 'headers' in event['request']:
            event['request']['headers'].pop('Authorization', None)
            event['request']['headers'].pop('Cookie', None)

    return event
```

**Custom Metrics:**

```python
# upstream/monitoring.py

from sentry_sdk import set_tag, set_context, capture_message
from functools import wraps
import time

def monitor_performance(func):
    """Decorator to monitor function performance."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()

        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time

            if duration > 1.0:  # Slow query threshold
                capture_message(
                    f'Slow operation: {func.__name__} took {duration:.2f}s',
                    level='warning'
                )

            return result
        except Exception as e:
            set_tag('function', func.__name__)
            raise

    return wrapper

# Usage
@monitor_performance
def expensive_query():
    return ClaimRecord.objects.all().count()
```

---

### O-2: Add Health Check Endpoints
**Effort:** 4 hours
**Impact:** High

**Enhanced Health Checks:**

```python
# upstream/health.py

from django.db import connection
from django.core.cache import cache
from django.http import JsonResponse
import redis

class HealthCheckService:
    @staticmethod
    def check_database():
        """Check database connectivity."""
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
            return {'status': 'healthy', 'latency_ms': 0}
        except Exception as e:
            return {'status': 'unhealthy', 'error': str(e)}

    @staticmethod
    def check_redis():
        """Check Redis connectivity."""
        try:
            cache.set('health_check', 'ok', timeout=10)
            value = cache.get('health_check')
            if value == 'ok':
                return {'status': 'healthy'}
            return {'status': 'unhealthy', 'error': 'Cache read failed'}
        except Exception as e:
            return {'status': 'unhealthy', 'error': str(e)}

    @staticmethod
    def check_celery():
        """Check Celery workers."""
        try:
            from celery import current_app
            inspect = current_app.control.inspect()
            active_workers = inspect.active()

            if active_workers:
                return {
                    'status': 'healthy',
                    'workers': len(active_workers)
                }
            return {'status': 'unhealthy', 'error': 'No active workers'}
        except Exception as e:
            return {'status': 'unhealthy', 'error': str(e)}

    @staticmethod
    def check_disk_space():
        """Check available disk space."""
        import shutil
        stat = shutil.disk_usage('/')
        free_gb = stat.free / (1024**3)

        if free_gb < 1:
            return {'status': 'critical', 'free_gb': free_gb}
        elif free_gb < 5:
            return {'status': 'warning', 'free_gb': free_gb}
        return {'status': 'healthy', 'free_gb': free_gb}

# upstream/api/views.py

class DetailedHealthCheckView(APIView):
    permission_classes = []

    def get(self, request):
        """Detailed health check with component status."""
        health_service = HealthCheckService()

        checks = {
            'database': health_service.check_database(),
            'redis': health_service.check_redis(),
            'celery': health_service.check_celery(),
            'disk': health_service.check_disk_space(),
        }

        # Overall status
        statuses = [c['status'] for c in checks.values()]
        if 'critical' in statuses:
            overall_status = 'critical'
            status_code = 503
        elif 'unhealthy' in statuses:
            overall_status = 'degraded'
            status_code = 503
        elif 'warning' in statuses:
            overall_status = 'warning'
            status_code = 200
        else:
            overall_status = 'healthy'
            status_code = 200

        return Response({
            'status': overall_status,
            'timestamp': timezone.now().isoformat(),
            'version': '1.0.0',
            'checks': checks
        }, status=status_code)
```

**Kubernetes Probes:**

```yaml
# deployment.yaml

apiVersion: apps/v1
kind: Deployment
metadata:
  name: upstream-web
spec:
  template:
    spec:
      containers:
      - name: web
        livenessProbe:
          httpGet:
            path: /health/
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10

        readinessProbe:
          httpGet:
            path: /health/ready/
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
```

---

### O-3: Add Logging and Audit Trail
**Effort:** 2 days
**Impact:** High

```python
# upstream/logging_config.py

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(name)s %(levelname)s %(message)s %(pathname)s %(lineno)d'
        },
        'verbose': {
            'format': '[{levelname}] {asctime} {name} {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'add_request_id': {
            '()': 'upstream.logging.RequestIDFilter',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json',
            'filters': ['add_request_id'],
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/upstream/app.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 10,
            'formatter': 'json',
            'filters': ['add_request_id'],
        },
        'sentry': {
            'level': 'ERROR',
            'class': 'sentry_sdk.integrations.logging.EventHandler',
            'filters': ['require_debug_false'],
        },
    },
    'loggers': {
        'upstream': {
            'handlers': ['console', 'file', 'sentry'],
            'level': 'INFO',
            'propagate': False,
        },
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
        },
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'WARNING',  # Only log slow queries
            'propagate': False,
        },
    },
}
```

**Request ID Middleware:**

```python
# upstream/middleware/request_id.py

import uuid
import logging

class RequestIDMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.id = str(uuid.uuid4())
        response = self.get_response(request)
        response['X-Request-ID'] = request.id
        return response

# upstream/logging.py

class RequestIDFilter(logging.Filter):
    def filter(self, record):
        from threading import local
        _thread_locals = local()
        request_id = getattr(_thread_locals, 'request_id', None)
        record.request_id = request_id or 'N/A'
        return True
```

**Audit Log Model:**

```python
# upstream/models.py

class AuditLog(BaseModel):
    """Comprehensive audit trail for all significant actions."""

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    action = models.CharField(max_length=100)
    entity_type = models.CharField(max_length=50)
    entity_id = models.CharField(max_length=100)
    changes = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True)
    user_agent = models.TextField(blank=True)
    request_id = models.UUIDField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['customer', 'created_at']),
            models.Index(fields=['user', 'action', 'created_at']),
            models.Index(fields=['entity_type', 'entity_id']),
        ]

    def __str__(self):
        return f"{self.user} - {self.action} - {self.entity_type}"

# Usage in views
def log_action(request, action, entity_type, entity_id, changes=None):
    AuditLog.objects.create(
        user=request.user if request.user.is_authenticated else None,
        customer=request.user.profile.customer,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        changes=changes or {},
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        request_id=request.id
    )
```

---

### O-4: Add Metrics Dashboard
**Effort:** 3 days
**Impact:** Medium

**Prometheus + Grafana Integration:**

```python
# requirements.txt
django-prometheus==2.3.1

# upstream/settings/prod.py

INSTALLED_APPS += ['django_prometheus']

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    # ... your middleware
    'django_prometheus.middleware.PrometheusAfterMiddleware',
]

# Custom metrics
from prometheus_client import Counter, Histogram

# Define custom metrics
upload_counter = Counter(
    'upstream_uploads_total',
    'Total number of CSV uploads',
    ['customer', 'status']
)

upload_processing_time = Histogram(
    'upstream_upload_processing_seconds',
    'Time to process CSV upload',
    ['customer']
)

drift_events_gauge = Gauge(
    'upstream_drift_events_active',
    'Number of active drift events',
    ['customer', 'severity']
)

# Use in code
def process_upload(upload):
    with upload_processing_time.labels(customer=upload.customer.name).time():
        # Process upload
        result = do_processing()

    upload_counter.labels(
        customer=upload.customer.name,
        status='success' if result else 'failed'
    ).inc()
```

**Grafana Dashboard JSON:**

```json
{
  "dashboard": {
    "title": "Upstream Metrics",
    "panels": [
      {
        "title": "Upload Rate",
        "targets": [
          {
            "expr": "rate(upstream_uploads_total[5m])"
          }
        ]
      },
      {
        "title": "Upload Processing Time",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, upstream_upload_processing_seconds)"
          }
        ]
      }
    ]
  }
}
```

---

## 🎯 Priority Recommendations

Based on impact vs effort analysis:

### Immediate (This Sprint)
1. ✅ **Quick Wins** - All QW items (< 2 days total)
2. ✅ **P-2: Optimize N+1 Queries** - High impact, 1 day
3. ✅ **T-1: Automated Testing** - Foundation for quality
4. ✅ **DX-1: Pre-commit Hooks** - Prevent issues early

### Next Sprint
5. **P-1: Celery Task Queue** - Critical for scale
6. **F-1: Real-Time Notifications** - User experience win
7. **O-1: APM Integration** - Visibility into production
8. **DX-2: Docker Compose** - Developer productivity

### Future Quarters
9. **F-5: Predictive Analytics** - Advanced feature
10. **P-4: Read Replicas** - When load requires it

---

## 📝 Next Steps

1. **Review this document** with the team
2. **Prioritize improvements** based on current business needs
3. **Create JIRA/GitHub issues** for selected items
4. **Assign ownership** for each improvement
5. **Set milestones** and track progress

---

**Document Version:** 1.0
**Last Updated:** 2026-01-24
**Contributors:** Development Team
