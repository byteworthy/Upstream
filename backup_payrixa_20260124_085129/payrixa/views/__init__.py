from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LogoutView as DjangoLogoutView
from django.shortcuts import render, redirect
from django.views import View
from django.contrib import messages
from django.db import transaction
import csv
import io
import re
import logging
from datetime import datetime
from upstream.models import Settings, Upload, ClaimRecord, PayerMapping, CPTGroupMapping, DataQualityReport
from upstream.utils import get_current_customer
from upstream.permissions import PermissionRequiredMixin
from upstream.cache import cache_result, invalidate_cache_pattern, get_cache_key, CACHE_KEYS
from django.core.cache import cache

logger = logging.getLogger(__name__)


# =============================================================================
# CACHED DATA ACCESSORS
# =============================================================================

@cache_result(CACHE_KEYS['PAYER_MAPPINGS'], ttl=900)  # 15 minutes
def get_payer_mappings_cached(customer):
    """
    Get payer mappings for customer with caching.

    Returns:
        dict: Mapping of raw_name (lowercase) -> normalized_name
    """
    # Use all_objects to bypass CustomerScopedManager (we're filtering by customer explicitly)
    mappings = PayerMapping.all_objects.filter(customer=customer).values_list('raw_name', 'normalized_name')
    # Convert to dict with lowercase keys for case-insensitive lookup
    return {raw_name.lower(): normalized_name for raw_name, normalized_name in mappings}


@cache_result(CACHE_KEYS['CPT_MAPPINGS'], ttl=900)  # 15 minutes
def get_cpt_mappings_cached(customer):
    """
    Get CPT group mappings for customer with caching.

    Returns:
        dict: Mapping of cpt_code -> cpt_group
    """
    # Use all_objects to bypass CustomerScopedManager (we're filtering by customer explicitly)
    mappings = CPTGroupMapping.all_objects.filter(customer=customer).values_list('cpt_code', 'cpt_group')
    return dict(mappings)


# =============================================================================
# PHI VALIDATION
# =============================================================================

# Common first and last names for PHI detection (subset for validation)
COMMON_FIRST_NAMES = {
    'james', 'john', 'robert', 'michael', 'william', 'david', 'richard', 'joseph', 'thomas', 'charles',
    'mary', 'patricia', 'jennifer', 'linda', 'barbara', 'elizabeth', 'susan', 'jessica', 'sarah', 'karen',
    'christopher', 'daniel', 'matthew', 'anthony', 'mark', 'donald', 'steven', 'paul', 'andrew', 'joshua',
    'nancy', 'betty', 'margaret', 'sandra', 'ashley', 'kimberly', 'emily', 'donna', 'michelle', 'dorothy'
}

def validate_not_phi(value, field_name='payer'):
    """
    Validate that a field value doesn't look like PHI (patient name).

    Raises ValueError if the value appears to be a patient name.

    Rules:
    - Title Case with 2-3 words (e.g., "John Smith")
    - First word matches common first names
    - Only letters, spaces, hyphens (no numbers or special chars)

    Args:
        value: The value to validate
        field_name: Name of the field being validated (for error messages)

    Raises:
        ValueError: If value looks like PHI
    """
    if not value:
        return

    value_stripped = value.strip()

    # Check if it's Title Case with 2-3 words
    words = value_stripped.split()
    if 2 <= len(words) <= 3:
        # Check if all words are title case and alphabetic
        if all(word.istitle() and word.replace('-', '').isalpha() for word in words):
            # Check if first word is a common first name
            first_word = words[0].lower()
            if first_word in COMMON_FIRST_NAMES:
                # Log PHI detection attempt (value redacted for security)
                logger.warning(
                    f"PHI_DETECTION: Rejected {field_name} field containing patient-like name. "
                    f"First word: {first_word}, Word count: {len(words)}"
                )
                raise ValueError(
                    f"PRIVACY ALERT: {field_name} value '{value_stripped}' looks like a patient name. "
                    f"Please use payer organization names only (e.g., 'Blue Cross Blue Shield', 'Medicare', 'Aetna'). "
                    f"NEVER include patient names, DOB, SSN, or addresses in uploads."
                )

class UploadsView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "upstream/uploads.html"
    permission_required = 'upload_claims'
    MAX_ROWS = 200000  # Maximum rows to prevent large uploads
    ALLOWED_COLUMNS = ['payer', 'cpt', 'submitted_date', 'decided_date', 'outcome', 'allowed_amount', 'denial_reason_code', 'denial_reason_text']

    def get(self, request):
        try:
            customer = get_current_customer(request)
            uploads = Upload.objects.filter(customer=customer).order_by('-uploaded_at')[:10]
            return render(request, self.template_name, {
                'customer': customer,
                'uploads': uploads
            })
        except ValueError as e:
            messages.error(request, str(e))
            return redirect('portal_root')

    def post(self, request):
        try:
            customer = get_current_customer(request)

            if 'csv_file' not in request.FILES:
                messages.error(request, "No file uploaded")
                return redirect('uploads')

            csv_file = request.FILES['csv_file']

            # Create upload record with original filename
            upload = Upload.objects.create(
                customer=customer,
                filename=csv_file.name,
                status='processing'
            )

            try:
                # Process CSV in a transaction for atomicity
                with transaction.atomic():
                    self.process_csv_upload(upload, csv_file)
                    upload.status = 'success'
                    upload.save()

                    # Show quality information if there were any rejections
                    if hasattr(upload, 'quality_report') and upload.quality_report.has_issues:
                        qr = upload.quality_report
                        quality_pct = qr.quality_score * 100
                        messages.warning(
                            request,
                            f"Uploaded {csv_file.name}: {qr.accepted_rows} of {qr.total_rows} rows accepted ({quality_pct:.1f}%). "
                            f"{qr.rejected_rows} rows were rejected. See quality report below for details."
                        )
                    else:
                        messages.success(request, f"Successfully uploaded {csv_file.name} with {upload.row_count} records")

            except Exception as e:
                upload.status = 'failed'
                upload.error_message = str(e)
                upload.save()

                # Log security event if PHI was detected
                if "PRIVACY ALERT" in str(e):
                    from upstream.core.services import create_audit_event
                    create_audit_event(
                        action='phi_detection_in_upload',
                        entity_type='Upload',
                        entity_id=upload.id,
                        customer=customer,
                        metadata={
                            'filename': csv_file.name,
                            'error': 'PHI-like data detected and rejected',
                            'user': request.user.username if request.user.is_authenticated else 'anonymous'
                        }
                    )

                messages.error(request, f"Upload failed: {str(e)}")

            return redirect('uploads')

        except ValueError as e:
            messages.error(request, str(e))
            return redirect('portal_root')

    def process_csv_upload(self, upload, csv_file):
        """
        Process CSV file and create ClaimRecord entries.

        Creates a DataQualityReport tracking accepted and rejected rows.
        Allows partial success - accepts valid rows and reports invalid ones.
        """
        # Read CSV file
        csv_data = csv_file.read().decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(csv_data))

        # Validate required columns (structural validation - must fail fast)
        required_columns = ['payer', 'cpt', 'submitted_date', 'decided_date', 'outcome']
        for col in required_columns:
            if col not in csv_reader.fieldnames:
                raise ValueError(f"Missing required column: {col}")

        # Load mappings once with caching (avoids N queries)
        payer_mappings = get_payer_mappings_cached(upload.customer)
        cpt_mappings = get_cpt_mappings_cached(upload.customer)

        logger.info(f"Loaded {len(payer_mappings)} payer mappings and {len(cpt_mappings)} CPT mappings from cache")

        # Track validation results
        claim_records = []
        dates = []
        rejection_details = {}  # {row_num: reason}
        warnings = []  # [{row: int, message: str}]

        # Error category counters
        phi_detections = 0
        missing_fields = 0
        invalid_dates = 0
        invalid_values = 0

        total_rows = 0

        for row_num, row in enumerate(csv_reader, start=2):  # start=2 because row 1 is header
            total_rows += 1

            # Check row limit
            if total_rows > self.MAX_ROWS:
                raise ValueError(f"Maximum row limit exceeded: {self.MAX_ROWS} rows")

            try:
                # Filter to only allowed columns - ignore all others
                filtered_row = {col: row[col] for col in self.ALLOWED_COLUMNS if col in row}

                # Validate required fields exist in filtered data
                for required_col in required_columns:
                    if required_col not in filtered_row or not filtered_row[required_col]:
                        rejection_details[row_num] = f"Missing required field: {required_col}"
                        missing_fields += 1
                        raise ValueError("Skip to next row")

                # Normalize data
                raw_payer = filtered_row['payer'].strip()
                cpt_code = filtered_row['cpt'].strip()

                # PHI Protection: Validate payer field doesn't contain patient names
                try:
                    validate_not_phi(raw_payer, field_name='payer')
                except ValueError as phi_error:
                    rejection_details[row_num] = f"PHI detected: {str(phi_error)[:100]}"
                    phi_detections += 1
                    raise ValueError("Skip to next row")

                # Apply payer mapping (case-insensitive lookup from cached dict)
                payer = payer_mappings.get(raw_payer.lower(), raw_payer)

                # Apply CPT group mapping (lookup from cached dict)
                cpt_group = cpt_mappings.get(cpt_code, "OTHER")

                # Normalize outcome
                outcome_raw = filtered_row['outcome'].strip().upper()
                if outcome_raw in ['PAID', 'APPROVED', 'ACCEPTED']:
                    outcome = 'PAID'
                elif outcome_raw in ['DENIED', 'REJECTED', 'DECLINED']:
                    outcome = 'DENIED'
                else:
                    outcome = 'OTHER'
                    # Add warning for unusual outcome value
                    warnings.append({
                        'row': row_num,
                        'message': f"Unusual outcome value '{outcome_raw}' mapped to OTHER"
                    })

                # Parse dates - decided_date is required for MVP
                try:
                    submitted_date = self.parse_date(filtered_row['submitted_date'], row_num, 'submitted_date')
                    decided_date = self.parse_date(filtered_row['decided_date'], row_num, 'decided_date')
                except ValueError as date_error:
                    rejection_details[row_num] = str(date_error)
                    invalid_dates += 1
                    raise ValueError("Skip to next row")

                # Create claim record
                claim_record = ClaimRecord(
                    customer=upload.customer,
                    upload=upload,
                    payer=payer,
                    cpt=cpt_code,
                    cpt_group=cpt_group,
                    submitted_date=submitted_date,
                    decided_date=decided_date,
                    outcome=outcome,
                    allowed_amount=self.parse_decimal(filtered_row.get('allowed_amount')) if filtered_row.get('allowed_amount') else None,
                    denial_reason_code=filtered_row.get('denial_reason_code') or None,
                    denial_reason_text=filtered_row.get('denial_reason_text') or None,
                )

                claim_records.append(claim_record)
                dates.extend([submitted_date, decided_date])

            except ValueError as e:
                # Skip row - already logged in rejection_details
                if str(e) != "Skip to next row":
                    # Unexpected error - log it
                    rejection_details[row_num] = str(e)[:200]
                    invalid_values += 1
                continue

        # Check if we have ANY valid rows
        if len(claim_records) == 0:
            raise ValueError(
                f"All {total_rows} rows were rejected. "
                f"PHI detected: {phi_detections}, Missing fields: {missing_fields}, "
                f"Invalid dates: {invalid_dates}, Invalid values: {invalid_values}. "
                f"Please fix the data and try again."
            )

        # Bulk create claim records
        ClaimRecord.objects.bulk_create(claim_records)

        # Update upload metadata
        upload.row_count = len(claim_records)
        if dates:
            upload.date_min = min(dates)
            upload.date_max = max(dates)

        # Create DataQualityReport
        quality_report = DataQualityReport.objects.create(
            upload=upload,
            customer=upload.customer,
            total_rows=total_rows,
            accepted_rows=len(claim_records),
            rejected_rows=len(rejection_details),
            rejection_details=rejection_details,
            warnings=warnings,
            phi_detections=phi_detections,
            missing_fields=missing_fields,
            invalid_dates=invalid_dates,
            invalid_values=invalid_values,
        )

        # Log quality report in console for operator visibility
        logger.info(
            f"Upload {upload.id} quality: {quality_report.accepted_rows}/{quality_report.total_rows} rows accepted "
            f"({quality_report.quality_score:.1%}). "
            f"Rejections - PHI: {phi_detections}, Missing: {missing_fields}, "
            f"Invalid dates: {invalid_dates}, Invalid values: {invalid_values}"
        )

    def parse_date(self, date_str, row_num, field_name):
        """Parse date from various formats."""
        if not date_str or not date_str.strip():
            raise ValueError(f"Missing {field_name} in row {row_num}")

        date_str = date_str.strip()

        # Try ISO format first (YYYY-MM-DD)
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            pass

        # Try US format (MM/DD/YYYY)
        try:
            return datetime.strptime(date_str, '%m/%d/%Y').date()
        except ValueError:
            pass

        # Try YYYY/MM/DD format
        try:
            return datetime.strptime(date_str, '%Y/%m/%d').date()
        except ValueError:
            pass

        raise ValueError(f"Invalid {field_name} format in row {row_num}: '{date_str}'. Expected formats: YYYY-MM-DD, MM/DD/YYYY, or YYYY/MM/DD")

    def parse_decimal(self, value):
        """Parse decimal value, return None if invalid."""
        if not value or not value.strip():
            return None

        try:
            return float(value.strip())
        except ValueError:
            return None

class SettingsView(LoginRequiredMixin, View):
    template_name = "upstream/settings.html"

    def get(self, request):
        try:
            customer = get_current_customer(request)

            # Get or create settings for the customer
            settings, created = Settings.objects.get_or_create(customer=customer)

            return render(request, self.template_name, {
                'settings': settings,
                'customer': customer
            })

        except ValueError as e:
            messages.error(request, str(e))
            return redirect('portal_root')

    def post(self, request):
        try:
            customer = get_current_customer(request)

            # Get or create settings for the customer
            settings, created = Settings.objects.get_or_create(customer=customer)

            # Update settings from form data
            settings.to_email = request.POST.get('to_email', '')
            settings.cc_email = request.POST.get('cc_email', '') or None
            settings.attach_pdf = 'attach_pdf' in request.POST

            settings.save()

            messages.success(request, "Settings saved successfully!")
            return redirect('settings')

        except ValueError as e:
            messages.error(request, str(e))
            return redirect('portal_root')

class DriftFeedView(LoginRequiredMixin, TemplateView):
    template_name = "upstream/drift_feed.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            customer = get_current_customer(self.request)
            context['customer'] = customer
        except ValueError as e:
            messages.error(self.request, str(e))
        return context

class ReportsView(LoginRequiredMixin, TemplateView):
    template_name = "upstream/reports.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            customer = get_current_customer(self.request)
            context['customer'] = customer
            # Get report runs for this customer, newest first
            context['report_runs'] = customer.report_runs.order_by('-started_at')
        except ValueError as e:
            messages.error(self.request, str(e))
        return context


class MappingsView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "upstream/mappings.html"
    permission_required = 'manage_mappings'

    def get(self, request):
        try:
            customer = get_current_customer(request)
            payer_mappings = PayerMapping.objects.filter(customer=customer).order_by('raw_name')
            cpt_mappings = CPTGroupMapping.objects.filter(customer=customer).order_by('cpt_code')
            return render(request, self.template_name, {
                'customer': customer,
                'payer_mappings': payer_mappings,
                'cpt_mappings': cpt_mappings
            })
        except ValueError as e:
            messages.error(request, str(e))
            return redirect('portal_root')

    def post(self, request):
        try:
            customer = get_current_customer(request)
            action = request.POST.get('action')

            if action == 'add_payer':
                return self.add_payer_mapping(request, customer)
            elif action == 'delete_payer':
                return self.delete_payer_mapping(request, customer)
            elif action == 'add_cpt':
                return self.add_cpt_mapping(request, customer)
            elif action == 'delete_cpt':
                return self.delete_cpt_mapping(request, customer)

            return redirect('mappings')

        except ValueError as e:
            messages.error(request, str(e))
            return redirect('portal_root')

    def add_payer_mapping(self, request, customer):
        raw_name = request.POST.get('raw_name', '').strip()
        normalized_name = request.POST.get('normalized_name', '').strip()

        if not raw_name or not normalized_name:
            messages.error(request, "Both raw name and normalized name are required")
            return redirect('mappings')

        # Check if mapping already exists
        if PayerMapping.objects.filter(customer=customer, raw_name__iexact=raw_name).exists():
            messages.error(request, f"Mapping for '{raw_name}' already exists")
            return redirect('mappings')

        PayerMapping.objects.create(
            customer=customer,
            raw_name=raw_name,
            normalized_name=normalized_name
        )

        # Invalidate cache for this customer's payer mappings
        cache_key = get_cache_key(CACHE_KEYS['PAYER_MAPPINGS'], customer)
        cache.delete(cache_key)
        logger.info(f"Cache invalidated for payer mappings: customer {customer.id}")

        messages.success(request, "Payer mapping added successfully")
        return redirect('mappings')

    def delete_payer_mapping(self, request, customer):
        mapping_id = request.POST.get('mapping_id')
        if mapping_id:
            try:
                mapping = PayerMapping.objects.get(id=mapping_id, customer=customer)
                mapping.delete()

                # Invalidate cache for this customer's payer mappings
                cache_key = get_cache_key(CACHE_KEYS['PAYER_MAPPINGS'], customer)
                cache.delete(cache_key)
                logger.info(f"Cache invalidated for payer mappings: customer {customer.id}")

                messages.success(request, "Payer mapping deleted successfully")
            except PayerMapping.DoesNotExist:
                messages.error(request, "Payer mapping not found")
        return redirect('mappings')

    def add_cpt_mapping(self, request, customer):
        cpt_code = request.POST.get('cpt_code', '').strip()
        cpt_group = request.POST.get('cpt_group', '').strip()

        if not cpt_code or not cpt_group:
            messages.error(request, "Both CPT code and CPT group are required")
            return redirect('mappings')

        # Check if mapping already exists
        if CPTGroupMapping.objects.filter(customer=customer, cpt_code__iexact=cpt_code).exists():
            messages.error(request, f"Mapping for CPT code '{cpt_code}' already exists")
            return redirect('mappings')

        CPTGroupMapping.objects.create(
            customer=customer,
            cpt_code=cpt_code,
            cpt_group=cpt_group
        )

        # Invalidate cache for this customer's CPT mappings
        cache_key = get_cache_key(CACHE_KEYS['CPT_MAPPINGS'], customer)
        cache.delete(cache_key)
        logger.info(f"Cache invalidated for CPT mappings: customer {customer.id}")

        messages.success(request, "CPT group mapping added successfully")
        return redirect('mappings')

    def delete_cpt_mapping(self, request, customer):
        mapping_id = request.POST.get('mapping_id')
        if mapping_id:
            try:
                mapping = CPTGroupMapping.objects.get(id=mapping_id, customer=customer)
                mapping.delete()

                # Invalidate cache for this customer's CPT mappings
                cache_key = get_cache_key(CACHE_KEYS['CPT_MAPPINGS'], customer)
                cache.delete(cache_key)
                logger.info(f"Cache invalidated for CPT mappings: customer {customer.id}")

                messages.success(request, "CPT group mapping deleted successfully")
            except CPTGroupMapping.DoesNotExist:
                messages.error(request, "CPT group mapping not found")
        return redirect('mappings')


class AxisHubView(LoginRequiredMixin, TemplateView):
    """Axis Hub - Landing page for Hub v1 products (DenialScope + DriftWatch)."""
    template_name = "upstream/products/axis.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            customer = get_current_customer(self.request)
            context['customer'] = customer
        except ValueError as e:
            messages.error(self.request, str(e))
        return context


class InsightsFeedView(LoginRequiredMixin, TemplateView):
    """Shared insight feed showing SystemEvent activity across all products."""
    template_name = "upstream/insights_feed.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            customer = get_current_customer(self.request)
            context['customer'] = customer

            # Import SystemEvent from ingestion models
            from upstream.ingestion.models import SystemEvent

            # Get recent system events for this customer
            events = SystemEvent.objects.filter(customer=customer).order_by('-created_at')[:50]
            context['events'] = events
            context['has_events'] = events.exists()
        except ValueError as e:
            messages.error(self.request, str(e))
        return context


class CustomLogoutView(DjangoLogoutView):
    """Custom logout view that shows which account was logged out."""
    template_name = "upstream/logged_out.html"

    def dispatch(self, request, *args, **kwargs):
        # Capture user context before logging out
        if request.user.is_authenticated:
            context = {}
            if request.user.is_superuser:
                context['was_operator'] = True
                context['username'] = request.user.username
            elif hasattr(request.user, 'profile') and request.user.profile:
                context['was_operator'] = False
                context['customer_name'] = request.user.profile.customer.name
                context['role'] = request.user.profile.get_role_display()
                context['username'] = request.user.username

            # Store in session before logout
            request.session['logout_context'] = context

        return super().dispatch(request, *args, **kwargs)


class AlertDeepDiveView(LoginRequiredMixin, TemplateView):
    """Deep dive view for alert evidence and details."""
    template_name = "upstream/alert_deep_dive.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        alert_id = self.kwargs.get('alert_id')

        from upstream.alerts.models import AlertEvent
        from upstream.services.evidence_payload import build_driftwatch_evidence_payload, get_alert_interpretation
        from upstream.ingestion.models import SystemEvent

        try:
            customer = get_current_customer(self.request)
            context['customer'] = customer

            # Get alert event with tenant isolation
            try:
                alert_event = AlertEvent.objects.select_related(
                    'alert_rule', 'drift_event', 'report_run'
                ).prefetch_related('operator_judgments__operator').get(
                    id=alert_id,
                    customer=customer
                )
                context['alert_event'] = alert_event

                # Log access to deep dive
                SystemEvent.objects.create(
                    customer=customer,
                    event_type='alert_deep_dive_viewed',
                    payload={
                        'alert_id': alert_id,
                        'alert_status': alert_event.status,
                        'username': self.request.user.username,
                    },
                    related_alert=alert_event
                )

            except AlertEvent.DoesNotExist:
                messages.error(self.request, f'Alert {alert_id} not found or you do not have access to it.')
                context['alert_event'] = None
                return context

            # Get operator judgments
            judgments = alert_event.operator_judgments.order_by('-created_at')
            context['judgments'] = judgments
            context['latest_judgment'] = judgments.first() if judgments.exists() else None

            # Build evidence payload safely
            if alert_event.drift_event:
                try:
                    drift_event = alert_event.drift_event
                    # Get related drift events for context
                    related_events = drift_event.customer.drift_events.filter(
                        report_run=drift_event.report_run
                    ).order_by('-severity')[:10]

                    evidence_payload = build_driftwatch_evidence_payload(
                        drift_event,
                        related_events
                    )
                    context['evidence_payload'] = evidence_payload

                    # Get interpretation
                    interpretation = get_alert_interpretation(evidence_payload)
                    context['interpretation'] = interpretation

                except Exception as e:
                    messages.warning(self.request, 'Could not load evidence payload. Showing basic alert information.')
                    context['evidence_payload'] = None
                    context['interpretation'] = None

                # Get sample claims if available
                try:
                    from upstream.models import ClaimRecord
                    sample_claims = ClaimRecord.objects.filter(
                        customer=customer,
                        payer_name__icontains=drift_event.payer
                    ).order_by('-service_date')[:20]
                    context['sample_claims'] = sample_claims
                except Exception as e:
                    messages.warning(self.request, 'Could not load sample claims.')
                    context['sample_claims'] = []
            else:
                messages.info(self.request, 'No drift event associated with this alert.')

        except ValueError as e:
            messages.error(self.request, str(e))
            context['alert_event'] = None
        except Exception as e:
            messages.error(self.request, f'An unexpected error occurred: {str(e)}')
            context['alert_event'] = None

        return context
