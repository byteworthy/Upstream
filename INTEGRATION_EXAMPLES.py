"""
Integration Examples for Data Quality & Amplified Models.

This file demonstrates how to integrate the new data quality,
validation, DriftWatch, and DenialScope features into your
existing Upstream workflows.
"""

from datetime import date, timedelta
from django.db import transaction
from django.utils import timezone

# Import services
from upstream.core.data_quality_service import DataQualityService
from upstream.core.quality_reporting_service import DataQualityReportingService
from upstream.core.default_validation_rules import create_default_rules_for_customer
from upstream.products.driftwatch.services import DriftWatchSignalService
from upstream.products.denialscope.ml_services import (
    DenialClusteringService,
    CascadeDetectionService,
    PreDenialWarningService,
    AppealGenerationService,
)

# Import models
from upstream.models import Customer, Upload, ClaimRecord, ReportRun


# ============================================================================
# Example 1: Complete Upload Processing with Quality Validation
# ============================================================================


def process_upload_with_quality(customer: Customer, file_path: str, filename: str):
    """
    Complete example: Process CSV upload with data quality validation.

    This replaces your existing upload processing to include validation.
    """
    print(f"Processing upload: {filename}")

    # Step 1: Create Upload record
    upload = Upload.objects.create(
        customer=customer,
        filename=filename,
        status="processing",
        processing_started_at=timezone.now(),
        uploaded_by=None,  # Set to current user
        upload_source="web_ui",
    )

    try:
        # Step 2: Parse CSV file
        rows_data = parse_csv_file(file_path)  # Your existing parser
        upload.row_count = len(rows_data)
        upload.save()

        # Step 3: Validate data quality
        quality_service = DataQualityService(customer)
        validation_result = quality_service.validate_upload(upload, rows_data)

        # Step 4: Check validation results
        summary = validation_result["summary"]
        print(f"Validation complete:")
        print(f"  - Total rows: {summary['total_rows']}")
        print(f"  - Accepted: {summary['accepted_rows']}")
        print(f"  - Rejected: {summary['rejected_rows']}")

        # Step 5: Handle anomalies
        if validation_result["anomalies"]:
            print(f"⚠️  Detected {len(validation_result['anomalies'])} anomalies")
            for anomaly in validation_result["anomalies"]:
                if anomaly["severity"] == "critical":
                    print(f"  🚨 CRITICAL: {anomaly['description']}")
                    # Optionally halt processing or alert operator

        # Step 6: Process accepted rows only
        accepted_claims = []
        for row_idx, row_data in enumerate(rows_data):
            row_number = row_idx + 1

            # Check if this row was rejected
            if row_number in validation_result["summary"]["rejection_details"]:
                continue  # Skip rejected rows

            # Create ClaimRecord
            claim = ClaimRecord.objects.create(
                customer=customer,
                upload=upload,
                payer=row_data["payer"],
                cpt=row_data["cpt"],
                cpt_group=row_data.get("cpt_group", "OTHER"),
                submitted_date=row_data["submitted_date"],
                decided_date=row_data["decided_date"],
                outcome=row_data["outcome"],
                allowed_amount=row_data.get("allowed_amount"),
                # New amplified fields
                billed_amount=row_data.get("billed_amount"),
                paid_amount=row_data.get("paid_amount"),
                payment_date=row_data.get("payment_date"),
                authorization_required=row_data.get("auth_required", False),
                authorization_number=row_data.get("auth_number"),
                authorization_obtained=row_data.get("auth_obtained", False),
                denial_reason_code=row_data.get("denial_reason_code"),
                denial_reason_text=row_data.get("denial_reason_text"),
                # Quality tracking
                validation_passed=True,
                validation_timestamp=timezone.now(),
                source_row_number=row_number,
            )
            accepted_claims.append(claim)

        # Step 7: Finalize upload
        upload.status = "success" if summary["accepted_rows"] > 0 else "failed"
        upload.processing_completed_at = timezone.now()
        upload.processing_duration_seconds = (
            upload.processing_completed_at - upload.processing_started_at
        ).total_seconds()
        upload.save()

        # Step 8: Generate quality report
        reporting_service = DataQualityReportingService(customer)
        quality_summary = reporting_service.generate_upload_quality_summary(upload)

        print(f"\n✅ Upload complete!")
        print(f"Quality Grade: {quality_summary['quality_grade']}")
        print(f"Acceptance Rate: {quality_summary['acceptance_rate']:.1f}%")

        if quality_summary["recommendations"]:
            print(f"\n💡 Recommendations:")
            for rec in quality_summary["recommendations"]:
                print(f"  - {rec}")

        return upload, accepted_claims

    except Exception as e:
        upload.status = "failed"
        upload.error_message = str(e)
        upload.processing_completed_at = timezone.now()
        upload.save()
        raise


# ============================================================================
# Example 2: Weekly Drift Detection & Alert Generation
# ============================================================================


def run_weekly_drift_detection(customer: Customer):
    """
    Run comprehensive drift detection weekly.

    This should be scheduled as a cron job or Celery task.
    """
    print(f"Running weekly drift detection for {customer.name}")

    # Step 1: Create report run
    report_run = ReportRun.objects.create(
        customer=customer,
        run_type="weekly",
        status="running",
        started_at=timezone.now(),
    )

    try:
        # Step 2: Run DriftWatch analysis
        drift_service = DriftWatchSignalService(customer)
        drift_results = drift_service.compute_all_signals(report_run)

        print(f"\n📊 DriftWatch Results:")
        print(f"  Total signals: {drift_results['signals_created']}")
        print(f"  By type:")
        for signal_type, count in drift_results["by_type"].items():
            print(f"    - {signal_type}: {count}")

        # Step 3: Check for high-value underpayment signals
        from upstream.models import DriftEvent

        underpayments = DriftEvent.objects.filter(
            customer=customer,
            report_run=report_run,
            drift_type="PAYMENT_AMOUNT",
            severity__gte=0.7,
        )

        if underpayments.exists():
            print(f"\n💰 HIGH-VALUE UNDERPAYMENT OPPORTUNITIES:")
            for signal in underpayments:
                print(f"  - {signal.payer} / {signal.cpt_group}")
                print(f"    Impact: ${signal.estimated_revenue_impact:,.2f}")
                print(f"    Variance: {signal.delta_percentage:.1f}%")
                # Send alert to revenue recovery team
                send_underpayment_alert(customer, signal)

        # Step 4: Finalize report
        report_run.status = "success"
        report_run.finished_at = timezone.now()
        report_run.summary_json = {
            "drift_signals": drift_results["signals_created"],
            "by_type": drift_results["by_type"],
        }
        report_run.save()

        print(f"\n✅ Drift detection complete")
        return report_run

    except Exception as e:
        report_run.status = "failed"
        report_run.finished_at = timezone.now()
        report_run.save()
        raise


# ============================================================================
# Example 3: Monthly Denial Analysis with ML
# ============================================================================


def run_monthly_denial_analysis(customer: Customer):
    """
    Run comprehensive denial analysis monthly.

    Uses ML clustering and cascade detection.
    """
    print(f"Running monthly denial analysis for {customer.name}")

    # Step 1: Run denial clustering
    clustering_service = DenialClusteringService(customer)
    clusters = clustering_service.cluster_denials(days_back=90, min_cluster_size=10)

    print(f"\n🔍 Denial Clustering Results:")
    print(f"  Found {len(clusters)} denial clusters")

    for cluster in clusters:
        print(f"\n  Cluster: {cluster.cluster_name}")
        print(f"  Claims: {cluster.claim_count}")
        print(f"  Dollars: ${cluster.total_denied_dollars:,.2f}")
        print(f"  Pattern: {cluster.pattern_description}")
        print(f"  Root Cause: {cluster.root_cause_hypothesis}")

        # Assign to analyst for investigation
        if cluster.claim_count >= 50:
            assign_cluster_to_analyst(customer, cluster)

    # Step 2: Detect cascades
    cascade_service = CascadeDetectionService(customer)
    cascades = cascade_service.detect_cascades(days_back=60)

    print(f"\n🔗 Cascade Detection Results:")
    print(f"  Found {len(cascades)} denial cascades")

    for cascade in cascades:
        print(f"\n  Cascade: {cascade.cascade_type}")
        print(f"  Claims: {cascade.claim_count}")
        print(f"  Pattern: {cascade.pattern_summary}")

        if cascade.cascade_type == "payer_systemic":
            # Alert management about systematic payer issue
            send_payer_systemic_alert(customer, cascade)

    return {"clusters": clusters, "cascades": cascades}


# ============================================================================
# Example 4: Pre-Denial Warning for New Claims
# ============================================================================


def check_claim_for_denial_risk(claim: ClaimRecord):
    """
    Check if a claim is at risk of denial BEFORE submission.

    Use this during claim creation/review.
    """
    customer = claim.customer

    # Generate pre-denial warnings
    warning_service = PreDenialWarningService(customer)
    warnings = warning_service.generate_warnings(claim)

    if warnings:
        print(f"⚠️  Claim at risk of denial:")
        for warning in warnings:
            print(f"\n  Type: {warning.warning_type}")
            print(f"  Probability: {warning.denial_probability:.0%}")
            print(f"  Confidence: {warning.confidence_score:.0%}")
            print(f"  Risk Factors:")
            for factor in warning.risk_factors:
                print(f"    - {factor['factor']}: {factor['weight']:.0%}")
            print(f"  Recommended Actions:")
            for action in warning.recommended_actions:
                print(f"    - [{action['priority']}] {action['action']}")

            # Show warning to operator
            show_warning_to_operator(claim, warning)

    return warnings


# ============================================================================
# Example 5: Auto-Generate Appeals for Denied Claims
# ============================================================================


def generate_appeals_for_denials(customer: Customer, days_back: int = 30):
    """
    Automatically generate appeals for recently denied claims.

    Run this daily or weekly.
    """
    print(f"Generating appeals for denials in last {days_back} days")

    # Get recently denied claims without appeals
    cutoff_date = date.today() - timedelta(days=days_back)
    denied_claims = ClaimRecord.objects.filter(
        customer=customer, outcome="DENIED", decided_date__gte=cutoff_date
    ).exclude(appeals__isnull=False)

    print(f"Found {denied_claims.count()} denied claims without appeals")

    appeal_service = AppealGenerationService(customer)
    generated_appeals = []

    for claim in denied_claims:
        try:
            # Generate appeal
            appeal = appeal_service.generate_appeal(claim)

            print(f"\n✅ Generated appeal for claim {claim.id}")
            print(f"  Appeal ID: {appeal.appeal_id}")
            print(
                f"  Template: {appeal.template_used.template_name if appeal.template_used else 'Generic'}"
            )
            print(f"  Confidence: {appeal.generation_confidence:.0%}")

            generated_appeals.append(appeal)

            # Notify operator for review
            notify_operator_new_appeal(appeal)

        except Exception as e:
            print(f"❌ Failed to generate appeal for claim {claim.id}: {e}")

    return generated_appeals


# ============================================================================
# Example 6: Quality Scorecard for Executive Dashboard
# ============================================================================


def get_executive_quality_dashboard(customer: Customer):
    """
    Generate executive-level quality dashboard.

    Use this for monthly reports or leadership dashboards.
    """
    reporting_service = DataQualityReportingService(customer)

    # Generate comprehensive scorecard
    scorecard = reporting_service.generate_quality_scorecard()

    print(f"\n📊 Executive Quality Dashboard")
    print(f"=" * 50)
    print(
        f"Overall Health Score: {scorecard['overall_health_score']}/100 ({scorecard['overall_health_grade']})"
    )
    print(f"Status: {scorecard['status'].upper()}")
    print(f"\nKey Metrics:")
    print(f"  - Average Quality: {scorecard['average_acceptance_rate']:.1f}%")
    print(f"  - Uploads Processed: {scorecard['uploads_count']}")
    print(f"  - Total Rows: {scorecard['total_rows_processed']:,}")
    print(f"\nQuality Dimensions:")
    for metric_type, metric_data in scorecard["quality_metrics"].items():
        print(
            f"  - {metric_type.title()}: {metric_data['grade']} ({metric_data['score']:.2f})"
        )

    print(f"\nOpen Issues:")
    print(f"  - Critical: {scorecard['open_issues']['critical']}")
    print(f"  - High: {scorecard['open_issues']['high']}")
    print(f"  - Medium: {scorecard['open_issues']['medium']}")

    return scorecard


# ============================================================================
# Example 7: Quality Trend Analysis
# ============================================================================


def analyze_quality_trends(customer: Customer, days: int = 90):
    """
    Analyze quality trends over time.

    Use this for identifying quality improvements or degradations.
    """
    reporting_service = DataQualityReportingService(customer)

    # Get trend report
    trend_report = reporting_service.generate_quality_trend_report(days=days)

    print(f"\n📈 Quality Trend Analysis ({days} days)")
    print(f"=" * 50)

    # Overall trend
    if trend_report.get("trends"):
        trends = trend_report["trends"]
        print(f"Trend: {trends['description']}")
        print(f"Direction: {trends['trend'].upper()}")
        print(f"Change: {trends['change_percentage']:+.1f}%")

        if trends["trend"] == "degrading":
            print(f"\n⚠️  ALERT: Data quality is degrading")
            # Send alert to operations team
            send_quality_degradation_alert(customer, trends)

    # Top failures
    failure_report = reporting_service.generate_validation_failure_report(days=days)

    print(f"\nTop Validation Failures:")
    for failure in failure_report["top_failing_rules"][:5]:
        print(
            f"  - {failure['validation_rule__code']}: {failure['failure_count']} failures"
        )

    return trend_report


# ============================================================================
# Helper Functions (implement these based on your notification system)
# ============================================================================


def parse_csv_file(file_path: str):
    """Parse CSV file - implement based on your format."""
    # Your existing CSV parsing logic
    pass


def send_underpayment_alert(customer, signal):
    """Send alert for underpayment opportunity."""
    # Send email/Slack/webhook
    pass


def send_payer_systemic_alert(customer, cascade):
    """Send alert for systematic payer issue."""
    # Send email/Slack/webhook
    pass


def assign_cluster_to_analyst(customer, cluster):
    """Assign denial cluster to analyst for investigation."""
    # Create task in your task management system
    pass


def show_warning_to_operator(claim, warning):
    """Show pre-denial warning to operator in UI."""
    # Display warning in claim review screen
    pass


def notify_operator_new_appeal(appeal):
    """Notify operator of new auto-generated appeal."""
    # Send notification
    pass


def send_quality_degradation_alert(customer, trends):
    """Send alert when quality is degrading."""
    # Send email/Slack/webhook
    pass


# ============================================================================
# Main Integration Example
# ============================================================================

if __name__ == "__main__":
    """
    Example workflow integrating all features.
    """
    # Get customer
    customer = Customer.objects.get(name="Demo Customer")

    print("=" * 70)
    print("UPSTREAM DATA QUALITY & AMPLIFICATION - INTEGRATION DEMO")
    print("=" * 70)

    # 1. Initialize data quality (run once)
    print("\n1. Initializing data quality...")
    create_default_rules_for_customer(customer)

    # 2. Process upload with validation
    print("\n2. Processing upload with validation...")
    # upload, claims = process_upload_with_quality(
    #     customer, '/path/to/file.csv', 'claims_2024.csv'
    # )

    # 3. Run drift detection
    print("\n3. Running drift detection...")
    # report_run = run_weekly_drift_detection(customer)

    # 4. Run denial analysis
    print("\n4. Running denial analysis...")
    # analysis = run_monthly_denial_analysis(customer)

    # 5. Generate quality scorecard
    print("\n5. Generating quality scorecard...")
    # scorecard = get_executive_quality_dashboard(customer)

    # 6. Analyze trends
    print("\n6. Analyzing quality trends...")
    # trends = analyze_quality_trends(customer, days=90)

    print("\n" + "=" * 70)
    print("✅ Integration demo complete!")
    print("=" * 70)
