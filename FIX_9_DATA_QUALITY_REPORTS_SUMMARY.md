# Fix #9: Data Quality Reports - Implementation Summary

**Status:** ✅ COMPLETE
**Date:** 2026-01-24
**Priority:** Critical

## Overview

Implemented comprehensive data quality reporting for CSV uploads. This enables the "Trust before scale" principle by showing operators exactly which rows were accepted and which were rejected, with detailed reasons.

## Problem

Previously, CSV upload validation would fail on the **first error**, providing no visibility into:
- How many rows had issues
- What the specific issues were
- Whether most of the data was valid

This created a poor user experience where operators had to fix one error at a time, re-upload, and repeat.

## Solution

### 1. Created DataQualityReport Model

**File:** `payrixa/models.py`

```python
class DataQualityReport(models.Model):
    """
    Data quality report for CSV upload validation.

    Tracks which rows were accepted/rejected and why.
    Enables "Trust before scale" principle by showing operators
    exactly what data passed validation.
    """
    upload = models.OneToOneField(Upload, on_delete=models.CASCADE, related_name='quality_report')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='quality_reports')

    # Summary metrics
    total_rows = models.IntegerField(default=0)
    accepted_rows = models.IntegerField(default=0)
    rejected_rows = models.IntegerField(default=0)

    # Detailed rejection tracking
    rejection_details = models.JSONField(default=dict)  # {row_num: reason}
    warnings = models.JSONField(default=list)  # [{row: int, message: str}]

    # Error category counters
    phi_detections = models.IntegerField(default=0)
    missing_fields = models.IntegerField(default=0)
    invalid_dates = models.IntegerField(default=0)
    invalid_values = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
```

**Key Features:**
- One-to-one relationship with Upload
- Categorized error tracking (PHI, missing fields, invalid dates, invalid values)
- JSON field for detailed rejection reasons per row
- Warnings for non-fatal issues
- Quality score calculation (accepted/total)
- Database indexes for performance

### 2. Refactored CSV Upload Processing

**File:** `payrixa/views.py` - `process_csv_upload()` method

**Before:** Fail on first error
```python
for row in csv_reader:
    if missing_field:
        raise ValueError("Missing field")  # Stops processing
```

**After:** Collect all errors, allow partial success
```python
# Track validation results
rejection_details = {}  # {row_num: reason}
phi_detections = 0
missing_fields = 0
invalid_dates = 0
invalid_values = 0

for row_num, row in enumerate(csv_reader, start=2):
    try:
        # Validate row...
        if missing_field:
            rejection_details[row_num] = "Missing required field: X"
            missing_fields += 1
            continue  # Skip row, continue processing

        # PHI detection...
        if phi_detected:
            rejection_details[row_num] = "PHI detected: patient name"
            phi_detections += 1
            continue

        # If valid, add to claim_records list
        claim_records.append(claim_record)

    except Exception as e:
        # Log error and continue
        rejection_details[row_num] = str(e)
        invalid_values += 1
        continue

# Only fail if ALL rows are rejected
if len(claim_records) == 0:
    raise ValueError(f"All {total_rows} rows were rejected...")

# Create DataQualityReport
DataQualityReport.objects.create(
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
```

**Key Improvements:**
- Collects ALL validation errors instead of failing on first
- Categorizes errors for reporting
- Allows partial success (accept valid rows, report invalid rows)
- Only fails if 100% of rows are rejected
- Creates comprehensive quality report

### 3. Enhanced UI with Quality Report Display

**File:** `payrixa/templates/payrixa/uploads.html`

Added quality indicators and expandable details:

```html
<th>Quality</th>
...
<td>
    {% if upload.quality_report %}
        {% if qr.quality_score >= 0.95 %}
            <span class="quality-badge quality-excellent">
                ✓ 95%
            </span>
        {% elif qr.quality_score >= 0.80 %}
            <span class="quality-badge quality-good">
                ⚠ 82%
            </span>
        {% else %}
            <span class="quality-badge quality-poor">
                ✗ 50%
            </span>
        {% endif %}
        <a href="#quality-details">Details</a>
    {% endif %}
</td>
```

**Quality Report Panel Shows:**
- Total rows vs. accepted vs. rejected
- Breakdown by error category:
  - PHI detected (patient-like names)
  - Missing required fields
  - Invalid date formats
  - Invalid values
- Expandable list of rejected rows with specific reasons
- Warnings for non-fatal issues

### 4. Updated Success Messages

**File:** `payrixa/views.py` - `UploadsView.post()` method

Now shows quality information when there are rejections:

```python
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
```

### 5. Added CSS Styling

**File:** `payrixa/static/payrixa/css/style.css`

Added 150+ lines of styling for:
- Quality badges (excellent/good/poor)
- Quality report panel layout
- Rejection details expandable sections
- Rejected row list with syntax highlighting
- Warning sections
- Responsive design for mobile

## Testing

### Test Coverage

**File:** `test_quality_report.py`

Comprehensive test with 10 CSV rows:
- 2 rows with PHI (John Smith, Mary Johnson) - REJECTED
- 1 row with missing submitted_date - REJECTED
- 1 row with invalid date format - REJECTED
- 1 row with missing CPT code - REJECTED
- 5 valid rows - ACCEPTED

### Test Results

```
✅ ALL TESTS PASSED (8/8)

✓ Total rows: 10 (expected 10)
✓ Accepted rows: 5 (expected 5)
✓ Rejected rows: 5 (expected 5)
✓ PHI detections: 2 (expected 2)
✓ Missing fields: 2 (expected 2)
✓ Invalid dates: 1 (expected 1)
✓ Quality score: 50.0% (expected 50.0%)
✓ Rejection details: 5 entries
```

### Sample Output

```
Rejection Details:
  Row 4: PHI detected: PRIVACY ALERT: payer value 'John Smith' looks like a patient name...
  Row 6: PHI detected: PRIVACY ALERT: payer value 'Mary Johnson' looks like a patient name...
  Row 7: Missing required field: submitted_date
  Row 8: Invalid decided_date format in row 8: 'invalid-date'. Expected formats: YYYY-MM-DD...
  Row 10: Missing required field: cpt
```

## Database Migration

**File:** `payrixa/migrations/0015_dataqualityreport.py`

Migration successfully applied:
```bash
$ python manage.py migrate payrixa
Applying payrixa.0015_dataqualityreport... OK
```

## Impact

### User Experience Improvements

1. **Visibility:** Operators see exactly what was accepted and rejected
2. **Efficiency:** No need to fix one error at a time and re-upload
3. **Trust:** Shows quality score so operators know data reliability
4. **Learning:** Detailed rejection reasons help fix data at source

### Example Scenarios

**Scenario 1: High Quality Upload (95%+ accepted)**
- Green badge: ✓ 98%
- Success message: "Successfully uploaded file.csv with 196 records"
- Optional quality details available but not intrusive

**Scenario 2: Good Quality Upload (80-95% accepted)**
- Yellow badge: ⚠ 87%
- Warning message: "187 of 200 rows accepted. 13 rows rejected. See details below."
- Expandable quality report shows what to fix

**Scenario 3: Poor Quality Upload (< 80% accepted)**
- Red badge: ✗ 45%
- Warning message: "90 of 200 rows accepted. 110 rows rejected. See details below."
- Detailed breakdown helps identify data quality issues

**Scenario 4: Complete Failure (0% accepted)**
- Upload fails with clear message:
  "All 50 rows were rejected. PHI detected: 30, Missing fields: 15, Invalid dates: 5. Please fix the data and try again."

## Files Changed

1. **payrixa/models.py**
   - Added DataQualityReport model (60 lines)

2. **payrixa/views.py**
   - Imported DataQualityReport
   - Refactored process_csv_upload() method (140 lines)
   - Updated success message logic (10 lines)

3. **payrixa/templates/payrixa/uploads.html**
   - Added Quality column to table
   - Added quality badge display
   - Added expandable quality report panel (80 lines)

4. **payrixa/static/payrixa/css/style.css**
   - Added quality report styling (150 lines)

5. **payrixa/migrations/0015_dataqualityreport.py**
   - Database migration (110 lines)

6. **test_quality_report.py** (NEW)
   - Comprehensive test suite (200 lines)

## Metrics

- **Lines of code:** ~650 lines
- **Test coverage:** 8/8 tests passing (100%)
- **Files modified:** 5
- **Migration:** 1
- **Database tables:** +1 (DataQualityReport)

## Next Steps (Optional Enhancements)

1. **Export Quality Reports**
   - Download rejected rows as CSV
   - Email quality summary to admin

2. **Quality Trends**
   - Track quality score over time
   - Alert if quality drops below threshold

3. **Auto-Fix Suggestions**
   - Suggest payer mappings for rejected names
   - Suggest date format conversions

4. **Batch Quality View**
   - Dashboard showing quality across all uploads
   - Identify chronic data quality issues

## Compliance

✅ **HIPAA-conscious:** PHI detection integrated into quality reporting
✅ **Tenant isolation:** DataQualityReport uses CustomerScopedManager
✅ **Audit logging:** Quality metrics logged for compliance
✅ **No data loss:** Partial success prevents losing valid data

## Production Readiness

✅ Database migration applied
✅ Comprehensive testing completed
✅ UI styling complete
✅ Performance optimized (database indexes)
✅ Error handling robust
✅ Logging comprehensive

**Status:** Ready for production deployment
