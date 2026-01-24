"""
Upstream API Views

RESTful API endpoints for the Upstream platform.
All views enforce multi-tenant access control.
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Avg, Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter

from ..models import (
    Customer, Settings, Upload, ClaimRecord,
    ReportRun, DriftEvent, PayerMapping, CPTGroupMapping
)
from upstream.alerts.models import AlertEvent, OperatorJudgment
from upstream.ingestion.models import IngestionToken
from upstream.ingestion import IngestionService
from .serializers import (
    CustomerSerializer, SettingsSerializer, UploadSerializer, UploadSummarySerializer,
    ClaimRecordSerializer, ClaimRecordSummarySerializer,
    ReportRunSerializer, ReportRunSummarySerializer, DriftEventSerializer,
    PayerMappingSerializer, CPTGroupMappingSerializer,
    PayerSummarySerializer, DashboardSerializer,
    AlertEventSerializer, OperatorJudgmentSerializer, OperatorFeedbackSerializer
)
from .permissions import IsCustomerMember, get_user_customer


class CustomerFilterMixin:
    """
    Mixin to automatically filter querysets to the user's customer.
    """
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        # Superusers see all data
        if user.is_superuser:
            return queryset
        
        # Regular users only see their customer's data
        customer = get_user_customer(user)
        if customer is None:
            return queryset.none()
        
        # Filter by customer field
        if hasattr(queryset.model, 'customer'):
            return queryset.filter(customer=customer)
        
        return queryset


class CustomerViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing customer information.
    Users can only see their own customer.
    """
    
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated, IsCustomerMember]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Customer.objects.all()
        
        customer = get_user_customer(user)
        if customer:
            return Customer.objects.filter(id=customer.id)
        return Customer.objects.none()


class SettingsViewSet(CustomerFilterMixin, viewsets.ModelViewSet):
    """
    API endpoint for managing customer settings.
    """
    
    queryset = Settings.objects.all()
    serializer_class = SettingsSerializer
    permission_classes = [IsAuthenticated, IsCustomerMember]
    
    def get_object(self):
        """Get or create settings for the user's customer."""
        customer = get_user_customer(self.request.user)
        if customer:
            settings, _ = Settings.objects.get_or_create(customer=customer)
            return settings
        return super().get_object()


class UploadViewSet(CustomerFilterMixin, viewsets.ModelViewSet):
    """
    API endpoint for managing file uploads.
    """
    
    queryset = Upload.objects.all().order_by('-uploaded_at')
    serializer_class = UploadSerializer
    permission_classes = [IsAuthenticated, IsCustomerMember]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['uploaded_at', 'status', 'row_count']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return UploadSummarySerializer
        return UploadSerializer
    
    @extend_schema(
        summary="Get upload statistics",
        responses={200: dict}
    )
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get upload statistics for the customer."""
        queryset = self.get_queryset()
        stats = {
            'total': queryset.count(),
            'success': queryset.filter(status='success').count(),
            'failed': queryset.filter(status='failed').count(),
            'processing': queryset.filter(status='processing').count(),
            'total_rows': queryset.aggregate(
                total=Count('claim_records')
            )['total'] or 0
        }
        return Response(stats)


class ClaimRecordViewSet(CustomerFilterMixin, viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing claim records.
    Supports filtering by payer, outcome, and date range.
    """
    
    queryset = ClaimRecord.objects.all().order_by('-decided_date')
    serializer_class = ClaimRecordSerializer
    permission_classes = [IsAuthenticated, IsCustomerMember]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['decided_date', 'submitted_date', 'payer', 'outcome']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ClaimRecordSummarySerializer
        return ClaimRecordSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by payer
        payer = self.request.query_params.get('payer')
        if payer:
            queryset = queryset.filter(payer__iexact=payer)
        
        # Filter by outcome
        outcome = self.request.query_params.get('outcome')
        if outcome:
            queryset = queryset.filter(outcome=outcome.upper())
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(decided_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(decided_date__lte=end_date)
        
        return queryset
    
    @extend_schema(
        summary="Get payer summary statistics",
        responses={200: PayerSummarySerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def payer_summary(self, request):
        """Get aggregated statistics by payer."""
        queryset = self.get_queryset()
        
        payers = queryset.values('payer').annotate(
            total_claims=Count('id'),
            paid_count=Count('id', filter=Q(outcome='PAID')),
            denied_count=Count('id', filter=Q(outcome='DENIED')),
            other_count=Count('id', filter=Q(outcome='OTHER')),
            avg_allowed_amount=Avg('allowed_amount')
        ).order_by('-total_claims')
        
        # Calculate denial rate
        results = []
        for p in payers:
            denial_rate = 0
            if p['total_claims'] > 0:
                denial_rate = (p['denied_count'] / p['total_claims']) * 100
            
            results.append({
                'payer': p['payer'],
                'total_claims': p['total_claims'],
                'paid_count': p['paid_count'],
                'denied_count': p['denied_count'],
                'other_count': p['other_count'],
                'denial_rate': round(denial_rate, 2),
                'avg_allowed_amount': p['avg_allowed_amount']
            })
        
        serializer = PayerSummarySerializer(results, many=True)
        return Response(serializer.data)


class ReportRunViewSet(CustomerFilterMixin, viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing report runs and their results.
    """
    
    queryset = ReportRun.objects.all().order_by('-started_at')
    serializer_class = ReportRunSerializer
    permission_classes = [IsAuthenticated, IsCustomerMember]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ReportRunSummarySerializer
        return ReportRunSerializer
    
    @extend_schema(
        summary="Trigger a new report run",
        responses={202: ReportRunSerializer}
    )
    @action(detail=False, methods=['post'])
    def trigger(self, request):
        """Trigger a new payer drift report run."""
        customer = get_user_customer(request.user)
        if not customer:
            return Response(
                {'error': 'No customer associated with user'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create a new report run
        report_run = ReportRun.objects.create(
            customer=customer,
            run_type='weekly',
            status='running'
        )
        
        # TODO: Trigger async task to compute drift
        # For now, mark as success placeholder
        # from ..services.payer_drift import compute_weekly_payer_drift
        # compute_weekly_payer_drift(customer, report_run)
        
        serializer = ReportRunSerializer(report_run)
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)


class DriftEventViewSet(CustomerFilterMixin, viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing drift events.
    """
    
    queryset = DriftEvent.objects.all().order_by('-created_at')
    serializer_class = DriftEventSerializer
    permission_classes = [IsAuthenticated, IsCustomerMember]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by severity
        min_severity = self.request.query_params.get('min_severity')
        if min_severity:
            queryset = queryset.filter(severity__gte=float(min_severity))
        
        # Filter by payer
        payer = self.request.query_params.get('payer')
        if payer:
            queryset = queryset.filter(payer__iexact=payer)
        
        # Filter by drift type
        drift_type = self.request.query_params.get('drift_type')
        if drift_type:
            queryset = queryset.filter(drift_type=drift_type.upper())
        
        return queryset
    
    @extend_schema(
        summary="Get active (recent) drift events",
        responses={200: DriftEventSerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get drift events from the most recent report run."""
        queryset = self.get_queryset()
        
        # Get the most recent report run
        latest_report = ReportRun.objects.filter(
            customer=get_user_customer(request.user),
            status='success'
        ).order_by('-finished_at').first()
        
        if latest_report:
            queryset = queryset.filter(report_run=latest_report)
        else:
            queryset = queryset.none()
        
        serializer = DriftEventSerializer(queryset, many=True)
        return Response(serializer.data)


class PayerMappingViewSet(CustomerFilterMixin, viewsets.ModelViewSet):
    """
    API endpoint for managing payer name mappings.
    """
    
    queryset = PayerMapping.objects.all().order_by('raw_name')
    serializer_class = PayerMappingSerializer
    permission_classes = [IsAuthenticated, IsCustomerMember]
    
    def perform_create(self, serializer):
        customer = get_user_customer(self.request.user)
        serializer.save(customer=customer)


class CPTGroupMappingViewSet(CustomerFilterMixin, viewsets.ModelViewSet):
    """
    API endpoint for managing CPT code to group mappings.
    """
    
    queryset = CPTGroupMapping.objects.all().order_by('cpt_code')
    serializer_class = CPTGroupMappingSerializer
    permission_classes = [IsAuthenticated, IsCustomerMember]
    
    def perform_create(self, serializer):
        customer = get_user_customer(self.request.user)
        serializer.save(customer=customer)


class DashboardView(APIView):
    """
    API endpoint for dashboard overview data.
    """

    permission_classes = [IsAuthenticated, IsCustomerMember]

    @extend_schema(
        summary="Get dashboard overview",
        responses={200: DashboardSerializer}
    )
    def get(self, request):
        customer = get_user_customer(request.user)
        if not customer:
            return Response(
                {'error': 'No customer associated with user'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get counts
        total_claims = ClaimRecord.objects.filter(customer=customer).count()
        total_uploads = Upload.objects.filter(customer=customer, status='success').count()

        # Get latest report
        latest_report = ReportRun.objects.filter(
            customer=customer,
            status='success'
        ).order_by('-finished_at').first()

        active_drift_events = 0
        if latest_report:
            active_drift_events = latest_report.drift_events.count()

        # Get top drift payers from latest report
        top_drift_payers = []
        if latest_report:
            top_events = latest_report.drift_events.order_by('-severity')[:5]
            for event in top_events:
                top_drift_payers.append({
                    'payer': event.payer,
                    'severity': event.severity,
                    'delta_value': event.delta_value
                })

        data = {
            'total_claims': total_claims,
            'total_uploads': total_uploads,
            'active_drift_events': active_drift_events,
            'last_report_date': latest_report.finished_at if latest_report else None,
            'denial_rate_trend': [],  # TODO: Compute trend data
            'top_drift_payers': top_drift_payers
        }

        serializer = DashboardSerializer(data)
        return Response(serializer.data)


class AlertEventViewSet(CustomerFilterMixin, viewsets.ModelViewSet):
    """
    API endpoint for managing alert events with operator feedback.
    """

    queryset = AlertEvent.objects.all().select_related('alert_rule', 'drift_event').prefetch_related('operator_judgments')
    serializer_class = AlertEventSerializer
    permission_classes = [IsAuthenticated, IsCustomerMember]
    ordering = ['-triggered_at']

    @action(detail=True, methods=['post'], url_path='feedback')
    @extend_schema(
        summary="Submit operator feedback on an alert",
        request=OperatorFeedbackSerializer,
        responses={201: OperatorJudgmentSerializer, 400: dict}
    )
    def feedback(self, request, pk=None):
        """
        Submit operator feedback/judgment on an alert event.
        Creates or updates an OperatorJudgment record.
        """
        from upstream.ingestion.models import SystemEvent

        alert_event = self.get_object()
        customer = get_user_customer(request.user)

        if not customer:
            return Response(
                {'error': 'No customer associated with user'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate input
        feedback_serializer = OperatorFeedbackSerializer(data=request.data)
        if not feedback_serializer.is_valid():
            return Response(feedback_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated_data = feedback_serializer.validated_data

        # Create or update operator judgment
        judgment, created = OperatorJudgment.objects.update_or_create(
            alert_event=alert_event,
            operator=request.user,
            defaults={
                'customer': customer,
                'verdict': validated_data['verdict'],
                'reason_codes_json': validated_data.get('reason_codes', []),
                'recovered_amount': validated_data.get('recovered_amount'),
                'recovered_date': validated_data.get('recovered_date'),
                'notes': validated_data.get('notes', ''),
            }
        )

        # Update alert event status based on verdict
        old_status = alert_event.status
        if validated_data['verdict'] == 'noise':
            alert_event.status = 'resolved'
        elif validated_data['verdict'] == 'real':
            alert_event.status = 'acknowledged'
        elif validated_data['verdict'] == 'needs_followup':
            alert_event.status = 'pending'

        alert_event.save(update_fields=['status'])

        # Log operator feedback action (audit trail)
        SystemEvent.objects.create(
            customer=customer,
            event_type='operator_feedback_submitted',
            payload={
                'alert_id': alert_event.id,
                'verdict': validated_data['verdict'],
                'previous_status': old_status,
                'new_status': alert_event.status,
                'recovered_amount': str(validated_data.get('recovered_amount')) if validated_data.get('recovered_amount') else None,
                'action': 'created' if created else 'updated',
                'drift_event_id': alert_event.drift_event.id if alert_event.drift_event else None,
                'operator_username': request.user.username,
            },
            related_alert=alert_event
        )

        serializer = OperatorJudgmentSerializer(judgment)
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class WebhookIngestionView(APIView):
    """
    Webhook ingestion endpoint.
    
    Accepts JSON payloads authenticated with ingestion tokens.
    Creates durable ingestion records for async processing.
    """
    
    permission_classes = []  # Uses token auth instead
    
    @extend_schema(
        summary="Ingest data via webhook",
        request={'application/json': dict},
        responses={202: dict, 401: dict, 400: dict}
    )
    def post(self, request):
        """Accept webhook payload and create ingestion record."""
        # Extract token from header
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer '):
            return Response(
                {'error': 'Missing or invalid authorization header'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        token_value = auth_header[7:]  # Remove 'Bearer '
        
        # Validate token
        try:
            token = IngestionToken.objects.get(token=token_value, is_active=True)
            
            # Check expiration
            if token.expires_at and token.expires_at < timezone.now():
                return Response(
                    {'error': 'Token expired'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Update last used
            token.last_used_at = timezone.now()
            token.save(update_fields=['last_used_at'])
            
        except IngestionToken.DoesNotExist:
            return Response(
                {'error': 'Invalid token'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Extract payload
        payload = request.data
        if not payload:
            return Response(
                {'error': 'Empty payload'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Extract optional idempotency key
        idempotency_key = request.META.get('HTTP_X_IDEMPOTENCY_KEY')
        
        # Create ingestion record
        try:
            service = IngestionService(
                customer=token.customer,
                source_type='webhook',
                created_by=None
            )
            
            record = service.create_record(
                payload_metadata={
                    'source': 'webhook',
                    'token_name': token.name,
                    'payload_keys': list(payload.keys()) if isinstance(payload, dict) else []
                },
                idempotency_key=idempotency_key,
                record_count=len(payload) if isinstance(payload, list) else 1
            )
            
            # TODO: Trigger async processing task
            # from upstream.tasks import process_ingestion
            # process_ingestion.delay(record.id)
            
            return Response({
                'status': 'accepted',
                'ingestion_id': record.id,
                'message': 'Payload received and queued for processing'
            }, status=status.HTTP_202_ACCEPTED)
            
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class HealthCheckView(APIView):
    """
    API health check endpoint (no auth required).
    """
    
    permission_classes = []
    
    def get(self, request):
        return Response({
            'status': 'healthy',
            'version': '1.0.0',
            'timestamp': timezone.now().isoformat()
        })
