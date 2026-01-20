from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect
from django.views import View
from django.contrib import messages
from django.db import transaction
import csv
import io
from datetime import datetime
from .models import Settings, Upload, ClaimRecord, PayerMapping, CPTGroupMapping
from .utils import get_current_customer
from .permissions import PermissionRequiredMixin

class UploadsView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = "payrixa/uploads.html"
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
                    messages.success(request, f"Successfully uploaded {csv_file.name} with {upload.row_count} records")

            except Exception as e:
                upload.status = 'failed'
                upload.error_message = str(e)
                upload.save()
                messages.error(request, f"Upload failed: {str(e)}")

            return redirect('uploads')

        except ValueError as e:
            messages.error(request, str(e))
            return redirect('portal_root')

    def process_csv_upload(self, upload, csv_file):
        """Process CSV file and create ClaimRecord entries."""
        # Read CSV file
        csv_data = csv_file.read().decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(csv_data))

        # Validate required columns
        required_columns = ['payer', 'cpt', 'submitted_date', 'decided_date', 'outcome']
        for col in required_columns:
            if col not in csv_reader.fieldnames:
                raise ValueError(f"Missing required column: {col}")

        # Check for row limit
        row_count = 0
        claim_records = []
        dates = []

        for row_num, row in enumerate(csv_reader, start=2):  # start=2 because row 1 is header
            # Check row limit
            if row_count >= self.MAX_ROWS:
                raise ValueError(f"Maximum row limit exceeded: {self.MAX_ROWS} rows")

            try:
                # Filter to only allowed columns - ignore all others
                filtered_row = {col: row[col] for col in self.ALLOWED_COLUMNS if col in row}

                # Validate required fields exist in filtered data
                for required_col in required_columns:
                    if required_col not in filtered_row or not filtered_row[required_col]:
                        raise ValueError(f"Missing required field '{required_col}' in row {row_num}")

                # Normalize data
                raw_payer = filtered_row['payer'].strip()
                cpt_code = filtered_row['cpt'].strip()

                # Apply payer mapping (case-insensitive exact match)
                payer_mapping = PayerMapping.objects.filter(
                    customer=upload.customer,
                    raw_name__iexact=raw_payer
                ).first()
                payer = payer_mapping.normalized_name if payer_mapping else raw_payer

                # Apply CPT group mapping
                cpt_mapping = CPTGroupMapping.objects.filter(
                    customer=upload.customer,
                    cpt_code=cpt_code
                ).first()
                cpt_group = cpt_mapping.cpt_group if cpt_mapping else "OTHER"

                # Normalize outcome
                outcome_raw = filtered_row['outcome'].strip().upper()
                if outcome_raw in ['PAID', 'APPROVED', 'ACCEPTED']:
                    outcome = 'PAID'
                elif outcome_raw in ['DENIED', 'REJECTED', 'DECLINED']:
                    outcome = 'DENIED'
                else:
                    outcome = 'OTHER'

                # Parse dates - decided_date is required for MVP
                submitted_date = self.parse_date(filtered_row['submitted_date'], row_num, 'submitted_date')
                decided_date = self.parse_date(filtered_row['decided_date'], row_num, 'decided_date')

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
                row_count += 1

            except Exception as e:
                raise ValueError(f"Error processing row {row_num}: {str(e)}")

        # Bulk create claim records
        ClaimRecord.objects.bulk_create(claim_records)

        # Update upload metadata
        upload.row_count = len(claim_records)
        if dates:
            upload.date_min = min(dates)
            upload.date_max = max(dates)

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
    template_name = "payrixa/settings.html"

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
    template_name = "payrixa/drift_feed.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            customer = get_current_customer(self.request)
            context['customer'] = customer
        except ValueError as e:
            messages.error(self.request, str(e))
        return context

class ReportsView(LoginRequiredMixin, TemplateView):
    template_name = "payrixa/reports.html"

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
    template_name = "payrixa/mappings.html"
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
        messages.success(request, "Payer mapping added successfully")
        return redirect('mappings')

    def delete_payer_mapping(self, request, customer):
        mapping_id = request.POST.get('mapping_id')
        if mapping_id:
            try:
                mapping = PayerMapping.objects.get(id=mapping_id, customer=customer)
                mapping.delete()
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
        messages.success(request, "CPT group mapping added successfully")
        return redirect('mappings')

    def delete_cpt_mapping(self, request, customer):
        mapping_id = request.POST.get('mapping_id')
        if mapping_id:
            try:
                mapping = CPTGroupMapping.objects.get(id=mapping_id, customer=customer)
                mapping.delete()
                messages.success(request, "CPT group mapping deleted successfully")
            except CPTGroupMapping.DoesNotExist:
                messages.error(request, "CPT group mapping not found")
        return redirect('mappings')


class InsightsFeedView(LoginRequiredMixin, TemplateView):
    """Shared insight feed showing SystemEvent activity across all products."""
    template_name = "payrixa/insights_feed.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            customer = get_current_customer(self.request)
            context['customer'] = customer
            
            # Import SystemEvent from ingestion models
            from payrixa.ingestion.models import SystemEvent
            
            # Get recent system events for this customer
            events = SystemEvent.objects.filter(customer=customer).order_by('-created_at')[:50]
            context['events'] = events
            context['has_events'] = events.exists()
        except ValueError as e:
            messages.error(self.request, str(e))
        return context
