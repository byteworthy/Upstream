from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.conf import settings

class Customer(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name

class Settings(models.Model):
    customer = models.OneToOneField(Customer, on_delete=models.CASCADE, related_name='settings')
    to_email = models.EmailField()
    cc_email = models.EmailField(blank=True, null=True)
    attach_pdf = models.BooleanField(default=True)

    def __str__(self):
        return f"Settings for {self.customer.name}"

class Upload(models.Model):
    STATUS_CHOICES = [
        ('processing', 'Processing'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='uploads')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    filename = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='processing')
    error_message = models.TextField(blank=True, null=True)
    row_count = models.IntegerField(blank=True, null=True)
    date_min = models.DateField(blank=True, null=True)
    date_max = models.DateField(blank=True, null=True)

    def __str__(self):
        return f"{self.filename} ({self.status})"

class ClaimRecord(models.Model):
    OUTCOME_CHOICES = [
        ('PAID', 'Paid'),
        ('DENIED', 'Denied'),
        ('OTHER', 'Other'),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='claim_records')
    upload = models.ForeignKey(Upload, on_delete=models.CASCADE, related_name='claim_records')
    payer = models.TextField()
    cpt = models.TextField()
    cpt_group = models.TextField(default="OTHER")
    submitted_date = models.DateField()
    decided_date = models.DateField()
    outcome = models.CharField(max_length=20, choices=OUTCOME_CHOICES)
    allowed_amount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    def __str__(self):
        return f"Claim {self.id} - {self.payer} - {self.outcome}"

class ReportRun(models.Model):
    REPORT_TYPE_CHOICES = [
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('custom', 'Custom'),
    ]

    STATUS_CHOICES = [
        ('running', 'Running'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='report_runs')
    run_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES, default='weekly')
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='running')
    summary_json = models.JSONField(blank=True, null=True)

    def __str__(self):
        return f"Report {self.id} - {self.run_type} ({self.status})"

class DriftEvent(models.Model):
    DRIFT_TYPE_CHOICES = [
        ('DENIAL_RATE', 'Denial Rate'),
        ('DECISION_TIME', 'Decision Time'),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='drift_events')
    report_run = models.ForeignKey(ReportRun, on_delete=models.CASCADE, related_name='drift_events')
    payer = models.TextField()
    cpt_group = models.TextField()
    drift_type = models.CharField(max_length=20, choices=DRIFT_TYPE_CHOICES)
    baseline_value = models.FloatField()
    current_value = models.FloatField()
    delta_value = models.FloatField()
    severity = models.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    confidence = models.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    baseline_start = models.DateField()
    baseline_end = models.DateField()
    current_start = models.DateField()
    current_end = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Drift Event {self.id} - {self.drift_type} - {self.payer}"

class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='user_profiles')

    def __str__(self):
        return f"Profile for {self.user.username} -> {self.customer.name}"

class PayerMapping(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='payer_mappings')
    raw_name = models.CharField(max_length=255)
    normalized_name = models.CharField(max_length=255)

    class Meta:
        unique_together = ('customer', 'raw_name')

    def __str__(self):
        return f"{self.raw_name} -> {self.normalized_name}"

class CPTGroupMapping(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='cpt_group_mappings')
    cpt_code = models.CharField(max_length=10)
    cpt_group = models.CharField(max_length=50)

    class Meta:
        unique_together = ('customer', 'cpt_code')

    def __str__(self):
        return f"{self.cpt_code} -> {self.cpt_group}"
