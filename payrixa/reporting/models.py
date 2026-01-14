from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from payrixa.core.models import BaseModel
from payrixa.models import ReportRun

class ReportTemplate(BaseModel):
    """Report templates for generation."""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    template_type = models.CharField(max_length=50, choices=[('pdf', 'PDF Report'), ('csv', 'CSV Export'), ('excel', 'Excel Spreadsheet'), ('html', 'HTML Report')])
    template_file = models.FileField(upload_to='report_templates/')
    output_format = models.CharField(max_length=20, choices=[('pdf', 'PDF'), ('csv', 'CSV'), ('xlsx', 'Excel'), ('html', 'HTML')])
    is_active = models.BooleanField(default=True)
    class Meta:
        verbose_name = 'Report Template'
        verbose_name_plural = 'Report Templates'
    def __str__(self):
        return self.name

class ScheduledReport(BaseModel):
    """Scheduled report generation jobs."""
    template = models.ForeignKey(ReportTemplate, on_delete=models.CASCADE)
    schedule_type = models.CharField(max_length=20, choices=[('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly'), ('quarterly', 'Quarterly'), ('one_time', 'One Time')])
    next_run_date = models.DateTimeField()
    last_run_date = models.DateTimeField(null=True, blank=True)
    last_run_status = models.CharField(max_length=20, choices=[('success', 'Success'), ('failed', 'Failed'), ('pending', 'Pending')], null=True, blank=True)
    recipients = models.JSONField(default=list)
    parameters = models.JSONField(default=dict)
    class Meta:
        verbose_name = 'Scheduled Report'
        verbose_name_plural = 'Scheduled Reports'

class ReportArtifact(BaseModel):
    """Artifacts generated from report runs (CSV exports, etc.)."""
    customer = models.ForeignKey('payrixa.Customer', on_delete=models.CASCADE, related_name='report_artifacts')
    report_run = models.ForeignKey(ReportRun, on_delete=models.CASCADE, related_name='artifacts')
    format = models.CharField(max_length=10, choices=[('csv', 'CSV'), ('pdf', 'PDF'), ('xlsx', 'Excel'), ('json', 'JSON')])
    status = models.CharField(max_length=20, choices=[('pending', 'Pending'), ('processing', 'Processing'), ('completed', 'Completed'), ('failed', 'Failed')], default='pending')
    file_path = models.CharField(max_length=512, blank=True, null=True)
    params = models.JSONField(default=dict, blank=True)
    class Meta:
        verbose_name = 'Report Artifact'
        verbose_name_plural = 'Report Artifacts'
    def __str__(self):
        return f"Artifact {self.id} - {self.format} ({self.status})"
