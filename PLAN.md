# Implementation Plan: Closing True Feature Gaps

## Executive Summary

After thorough codebase exploration, the gap analysis had several inaccuracies. Many features claimed as "missing" are actually implemented. This plan focuses on the **true remaining gaps**.

---

## Gap Analysis Corrections

| Feature | Gap Analysis Said | Actual Status |
|---------|------------------|---------------|
| PT/OT 8-Minute Rule | "Completely Missing" | ✅ FULLY IMPLEMENTED |
| Underpayment Detection | "Missing" | ✅ IMPLEMENTED (5% threshold) |
| Appeal Generation | "Missing" | ✅ MODELS EXIST |
| Network Intelligence | "Partial" | ✅ FULLY IMPLEMENTED |
| PDGM Grouper | "Missing" | ✅ FULLY IMPLEMENTED (432+ combos) |
| RBM Requirements | "Partial" | ✅ FULLY IMPLEMENTED (6 RBM providers) |

---

## True Remaining Gaps (Priority Order)

### Gap 1: PT/OT G-Code Validators & Database Models
**Status:** Service layer exists, models missing
**Location:** `upstream/products/ptot/`

**What exists:**
- `services.py` - 8-minute rule validator (complete)
- `constants.py` - 45+ CPT codes, time thresholds
- `tests.py` - Comprehensive unit tests

**What's missing:**
- Database models for PT/OT claims
- G-code/functional limitation validators
- Progress report tracking (every 10 visits)

### Gap 2: Payer Portal RPA (Selenium)
**Status:** Scaffolded, not implemented
**Location:** `upstream/automation/rules_engine.py`

**What exists:**
- RulesEngine with event evaluation
- ExecutionLog audit trail
- IntegrationConnection model for credentials

**What's missing:**
- Selenium WebDriver integration
- Payer-specific portal handlers
- Form filling and submission logic

### Gap 3: Home Health Certification Cycle Tracking
**Status:** Not implemented
**Location:** `upstream/products/homehealth/`

**What exists:**
- HomeHealthPDGMGroup (432+ combinations)
- HomeHealthEpisode model
- F2F timing validation

**What's missing:**
- CertificationCycle model
- 60-day recert deadline tracking
- 45/30/21/14-day alert generation

### Gap 4: Appeal Submission to Payers
**Status:** Models exist, submission doesn't
**Location:** `upstream/products/denialscope/`

**What exists:**
- AppealTemplate model (AI-generated)
- AppealGeneration model (status tracking)
- PreDenialWarning model

**What's missing:**
- Actual portal/fax submission
- Confirmation number capture
- Outcome tracking automation

### Gap 5: Payer Rule Change Detection
**Status:** Not implemented
**What's missing:**
- Web scraping for payer bulletins
- NLP for policy change extraction
- Affected CPT code mapping

### Gap 6: Marketing Content Auto-Generation
**Status:** Not implemented
**What's missing:**
- Blog post generation from patterns
- Webinar topic suggestions
- Case study automation

---

## Implementation Plan

### Phase 1: PT/OT Completion (Sprint 1)

#### Task 1.1: Create PT/OT Database Models
**File:** `upstream/products/ptot/models.py`

```python
class PTOTClaim(models.Model):
    """PT/OT specific claim tracking."""
    customer = ForeignKey(Customer, on_delete=CASCADE)
    claim = OneToOneField(ClaimRecord, on_delete=CASCADE)

    # Time-based billing
    documented_minutes = IntegerField()
    units_billed = IntegerField()
    expected_units = IntegerField()

    # 8-minute rule compliance
    billing_status = CharField(choices=[
        ('compliant', 'Compliant'),
        ('over_billed', 'Over-Billed'),
        ('under_billed', 'Under-Billed'),
    ])

    # Modifiers
    kx_modifier_required = BooleanField(default=False)
    kx_modifier_present = BooleanField(default=False)
    therapy_cap_amount = DecimalField(null=True)

class PTOTGCodeReport(models.Model):
    """G-code functional limitation reporting."""
    customer = ForeignKey(Customer, on_delete=CASCADE)
    patient_id = CharField(max_length=100)

    # Reporting point
    report_type = CharField(choices=[
        ('evaluation', 'Initial Evaluation'),
        ('progress', 'Progress Report'),
        ('discharge', 'Discharge'),
    ])

    # G-codes
    functional_limitation_category = CharField(choices=[
        ('mobility', 'Mobility'),
        ('self_care', 'Self Care'),
        ('changing_positions', 'Changing Positions'),
        ('carrying', 'Carrying/Moving'),
        ('other_pt', 'Other PT'),
        ('swallowing', 'Swallowing'),
        ('motor_speech', 'Motor Speech'),
        ('attention', 'Attention'),
        ('memory', 'Memory'),
        ('voice', 'Voice'),
        ('fluency', 'Fluency'),
        ('language', 'Language'),
        ('other_slp', 'Other SLP'),
        ('other_ot', 'Other OT'),
    ])

    current_gcode = CharField(max_length=20)
    current_severity = CharField(max_length=5)  # CH-CN scale
    goal_gcode = CharField(max_length=20)
    goal_severity = CharField(max_length=5)

    visit_number = IntegerField()
    report_date = DateField()
    next_report_due = DateField()  # Every 10 visits

class PTOTVisitTracker(models.Model):
    """Track visits for progress report timing."""
    customer = ForeignKey(Customer, on_delete=CASCADE)
    patient_id = CharField(max_length=100)
    episode_start = DateField()

    total_visits = IntegerField(default=0)
    last_progress_report_visit = IntegerField(default=0)
    next_progress_report_due = IntegerField()  # Visit number

    # Alerts
    progress_report_overdue = BooleanField(default=False)
```

#### Task 1.2: Add G-Code Validator Service
**File:** `upstream/products/ptot/services.py` (extend existing)

```python
class PTOTGCodeValidator:
    """Validate G-code functional limitation reporting."""

    REQUIRED_REPORTING_POINTS = ['evaluation', 'discharge']
    PROGRESS_REPORT_INTERVAL = 10  # Every 10 visits

    def validate_gcode_requirements(self, claim: ClaimRecord) -> ValidationResult:
        """Check if G-codes present when required."""
        service_type = self._classify_service(claim.cpt)

        if service_type in self.REQUIRED_REPORTING_POINTS:
            gcodes = self._extract_gcodes(claim)
            if not gcodes:
                return ValidationResult(
                    valid=False,
                    issue='gcode_missing',
                    severity='high',
                    message=f"{service_type} requires functional limitation G-codes",
                    denial_probability=0.95
                )

        return ValidationResult(valid=True)

    def check_progress_report_due(self, patient_id: str) -> Optional[Alert]:
        """Alert when 10th visit approaching without G-codes."""
        tracker = PTOTVisitTracker.objects.get(patient_id=patient_id)

        visits_since_report = tracker.total_visits - tracker.last_progress_report_visit

        if visits_since_report >= 8:  # 2 visits before due
            return Alert(
                alert_type='ptot_progress_report_due',
                severity='medium' if visits_since_report == 8 else 'high',
                message=f"Progress report due at visit {tracker.next_progress_report_due}"
            )

        return None
```

#### Task 1.3: Add PT/OT Alerts
**Alerts to generate:**
- `ptot_8_minute_violation` - Over-billing detected
- `ptot_revenue_leakage` - Under-billing detected
- `ptot_gcode_missing` - Required G-code absent
- `ptot_progress_report_due` - 10th visit approaching
- `ptot_kx_modifier_required` - Threshold exceeded, KX needed

---

### Phase 2: Home Health Certification Cycles (Sprint 2)

#### Task 2.1: Create CertificationCycle Model
**File:** `upstream/products/homehealth/models.py` (extend existing)

```python
class CertificationCycle(models.Model):
    """Track 60-day home health certification cycles."""
    customer = ForeignKey(Customer, on_delete=CASCADE)
    episode = ForeignKey(HomeHealthEpisode, on_delete=CASCADE)

    # Cycle info
    cycle_number = IntegerField()  # 1, 2, 3...
    cycle_start = DateField()
    cycle_end = DateField()  # 60 days from start

    # Certification requirements
    cert_due_date = DateField(db_index=True)
    physician_order_signed = BooleanField(default=False)
    physician_order_date = DateField(null=True)
    face_to_face_completed = BooleanField(default=False)
    face_to_face_date = DateField(null=True)
    oasis_completed = BooleanField(default=False)
    oasis_date = DateField(null=True)

    # NOA tracking
    noa_required = BooleanField(default=True)
    noa_submitted = BooleanField(default=False)
    noa_submission_date = DateField(null=True)
    noa_deadline = DateField()  # 5 days from SOC

    # Status
    status = CharField(choices=[
        ('active', 'Active'),
        ('pending_recert', 'Pending Recertification'),
        ('recertified', 'Recertified'),
        ('discharged', 'Discharged'),
    ])
```

#### Task 2.2: Certification Deadline Monitor Service
**File:** `upstream/products/homehealth/services.py` (extend existing)

```python
class CertificationCycleMonitor:
    """Monitor 60-day cycles and generate deadline alerts."""

    ALERT_DAYS = [45, 30, 21, 14, 7, 3]  # Days before deadline

    def check_certification_deadlines(self, customer: Customer) -> List[Alert]:
        """Generate alerts for approaching cert deadlines."""
        alerts = []
        today = date.today()

        cycles = CertificationCycle.objects.filter(
            customer=customer,
            status='active',
            cert_due_date__gte=today
        )

        for cycle in cycles:
            days_until = (cycle.cert_due_date - today).days

            if days_until in self.ALERT_DAYS:
                severity = self._get_severity(days_until)
                alerts.append(Alert(
                    alert_type='homehealth_recert_deadline',
                    severity=severity,
                    message=f"Recertification due in {days_until} days",
                    evidence={
                        'episode_id': cycle.episode_id,
                        'cert_due_date': cycle.cert_due_date,
                        'f2f_completed': cycle.face_to_face_completed,
                        'oasis_completed': cycle.oasis_completed,
                    }
                ))

        return alerts

    def check_noa_deadlines(self, customer: Customer) -> List[Alert]:
        """Alert on NOA submission deadlines (5 days from SOC)."""
        ...
```

---

### Phase 3: Payer Portal RPA Foundation (Sprint 3)

#### Task 3.1: RPA Abstraction Layer
**File:** `upstream/automation/rpa/__init__.py`

```python
class PayerPortalClient(ABC):
    """Abstract base for payer portal automation."""

    @abstractmethod
    def login(self) -> Session: ...

    @abstractmethod
    def submit_prior_auth(self, request: PARequest) -> PAResult: ...

    @abstractmethod
    def submit_reauth(self, request: ReauthRequest) -> ReauthResult: ...

    @abstractmethod
    def check_claim_status(self, claim_id: str) -> ClaimStatus: ...

    @abstractmethod
    def submit_appeal(self, appeal: Appeal) -> AppealResult: ...

class MockPayerPortal(PayerPortalClient):
    """Mock implementation for testing and shadow mode."""

    def login(self) -> Session:
        return MockSession(authenticated=True)

    def submit_prior_auth(self, request: PARequest) -> PAResult:
        # Simulate realistic delays and responses
        time.sleep(random.uniform(1.0, 3.0))
        return PAResult(
            success=True,
            confirmation_number=f"PA-{uuid4().hex[:8].upper()}",
            estimated_decision_date=date.today() + timedelta(days=3)
        )
```

#### Task 3.2: Selenium Portal Handler (Template)
**File:** `upstream/automation/rpa/selenium_base.py`

```python
class SeleniumPortalHandler(PayerPortalClient):
    """Base Selenium handler for payer portals."""

    def __init__(self, payer: str, credentials: EncryptedCredentials):
        self.payer = payer
        self.credentials = credentials
        self.driver = None

    def _init_driver(self) -> WebDriver:
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        return webdriver.Chrome(options=options)

    def login(self) -> Session:
        self.driver = self._init_driver()
        # Payer-specific login logic in subclasses
        raise NotImplementedError

    def _wait_for_element(self, selector: str, timeout: int = 10):
        return WebDriverWait(self.driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )

    def _capture_screenshot(self, name: str):
        """Capture screenshot for audit trail."""
        path = f"/tmp/rpa_screenshots/{self.payer}/{name}_{datetime.now().isoformat()}.png"
        self.driver.save_screenshot(path)
        return path
```

---

## Decision Points

### Decision 1: PT/OT Priority
- **Option A:** Equal priority - implement full G-code validators
- **Option B:** Lower priority - 8-minute rule sufficient for now
- **Option C:** Higher priority - PT/OT is key launch vertical

**Recommendation:** Option A - The 8-minute rule is already complete. Adding G-codes is incremental work that completes the module.

### Decision 2: RPA Approach
- **Option A:** Mock layer first - build abstraction, integrate later
- **Option B:** Real integration - need test credentials
- **Option C:** Skip for now - defer to future sprint

**Recommendation:** Option A - The rules engine is scaffolded. Building a mock layer validates the architecture without payer credentials.

### Decision 3: Home Health Cert Cycles
- **Option A:** Full implementation with 45/30/21/14/7/3-day alerts
- **Option B:** Basic implementation with 30/14/3-day alerts only

**Recommendation:** Option A - Calendar-based alerts are a core differentiator.

---

## File Changes Summary

| File | Action | Description |
|------|--------|-------------|
| `upstream/products/ptot/models.py` | CREATE | PTOTClaim, PTOTGCodeReport, PTOTVisitTracker |
| `upstream/products/ptot/services.py` | EXTEND | Add PTOTGCodeValidator |
| `upstream/products/ptot/admin.py` | CREATE | Django admin for PT/OT models |
| `upstream/products/homehealth/models.py` | EXTEND | Add CertificationCycle |
| `upstream/products/homehealth/services.py` | EXTEND | Add CertificationCycleMonitor |
| `upstream/automation/rpa/__init__.py` | CREATE | PayerPortalClient ABC |
| `upstream/automation/rpa/mock_portal.py` | CREATE | MockPayerPortal |
| `upstream/automation/rpa/selenium_base.py` | CREATE | SeleniumPortalHandler base |
| `upstream/api/serializers.py` | EXTEND | Add serializers for new models |
| `upstream/api/views.py` | EXTEND | Add viewsets for new models |

---

## Testing Strategy

### Unit Tests
- PT/OT G-code validation logic
- Certification cycle deadline calculations
- RPA mock responses

### Integration Tests
- Alert generation from PT/OT claims
- Cert cycle to alert pipeline
- RPA execution logging

### E2E Tests
- Full claim → validation → alert flow
- Cert cycle dashboard rendering

---

## Estimated Scope

| Phase | Tasks | Complexity |
|-------|-------|------------|
| Phase 1: PT/OT | 3 models, 1 service extension, tests | Medium |
| Phase 2: Home Health | 1 model, 1 service, deadline logic | Medium |
| Phase 3: RPA Foundation | Abstraction layer, mock implementation | Medium-High |

---

## Next Steps

1. Confirm priority decisions above
2. Begin Phase 1 (PT/OT completion)
3. Run existing test suite to ensure no regressions
4. Create migrations for new models
5. Extend API for new endpoints
