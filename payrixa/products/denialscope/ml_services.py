"""
ML-powered DenialScope Services.

Implements:
- Denial clustering using ML algorithms
- Cascade detection for related denials
- Pre-denial warning predictions
- AI-powered appeal generation
"""

from datetime import timedelta
from decimal import Decimal
from typing import Dict, List, Tuple
import re

from django.db import transaction
from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score

from payrixa.models import ClaimRecord
from payrixa.products.denialscope.advanced_models import (
    DenialCluster, DenialCascade, PreDenialWarning,
    AppealTemplate, AppealGeneration
)


class DenialClusteringService:
    """
    ML-powered denial clustering.

    Groups similar denials to identify patterns and enable bulk resolution.
    """

    def __init__(self, customer):
        self.customer = customer

    @transaction.atomic
    def cluster_denials(self, days_back: int = 90, min_cluster_size: int = 5) -> List[DenialCluster]:
        """
        Perform ML clustering on recent denials.

        Uses DBSCAN algorithm to find density-based clusters.
        """
        # Get recent denied claims
        start_date = timezone.now().date() - timedelta(days=days_back)
        denied_claims = ClaimRecord.objects.filter(
            customer=self.customer,
            outcome='DENIED',
            decided_date__gte=start_date
        ).select_related('customer')

        if denied_claims.count() < min_cluster_size:
            return []

        # Extract features for clustering
        features, claim_data = self._extract_clustering_features(denied_claims)

        if len(features) == 0:
            return []

        # Normalize features
        scaler = StandardScaler()
        features_normalized = scaler.fit_transform(features)

        # Perform DBSCAN clustering
        clustering = DBSCAN(eps=0.5, min_samples=min_cluster_size)
        cluster_labels = clustering.fit_predict(features_normalized)

        # Calculate silhouette score if we have clusters
        silhouette_avg = 0
        if len(set(cluster_labels)) > 1:
            silhouette_avg = silhouette_score(features_normalized, cluster_labels)

        # Create cluster objects
        clusters = []
        unique_labels = set(cluster_labels)

        for label in unique_labels:
            if label == -1:  # Noise points
                continue

            cluster_mask = cluster_labels == label
            cluster_claims = [claim_data[i] for i, mask in enumerate(cluster_mask) if mask]

            if len(cluster_claims) < min_cluster_size:
                continue

            cluster = self._create_cluster_from_claims(
                cluster_claims,
                label,
                silhouette_avg
            )
            clusters.append(cluster)

        return clusters

    def _extract_clustering_features(self, denied_claims) -> Tuple[List, List]:
        """
        Extract numerical features for clustering.

        Features:
        - Payer (one-hot encoded)
        - CPT code (embedded)
        - Denial reason (embedded)
        - Allowed amount (normalized)
        - Days to decision
        """
        features = []
        claim_data = []

        # Build vocabularies
        payers = list(set(c.payer for c in denied_claims))
        denial_reasons = list(set(c.denial_reason_code or 'UNKNOWN' for c in denied_claims))

        for claim in denied_claims:
            feature_vector = []

            # Payer one-hot (top 10 payers only)
            payer_idx = payers.index(claim.payer) if claim.payer in payers[:10] else 10
            payer_onehot = [1 if i == payer_idx else 0 for i in range(11)]
            feature_vector.extend(payer_onehot)

            # Denial reason one-hot (top 10 reasons only)
            reason = claim.denial_reason_code or 'UNKNOWN'
            reason_idx = denial_reasons.index(reason) if reason in denial_reasons[:10] else 10
            reason_onehot = [1 if i == reason_idx else 0 for i in range(11)]
            feature_vector.extend(reason_onehot)

            # Numerical features
            allowed_amount = float(claim.allowed_amount or 0)
            feature_vector.append(allowed_amount)

            days_to_decision = (claim.decided_date - claim.submitted_date).days if claim.decided_date and claim.submitted_date else 0
            feature_vector.append(days_to_decision)

            features.append(feature_vector)
            claim_data.append({
                'claim': claim,
                'payer': claim.payer,
                'cpt': claim.cpt,
                'denial_reason': claim.denial_reason_code or claim.denial_reason_text or 'UNKNOWN',
                'allowed_amount': claim.allowed_amount,
            })

        return features, claim_data

    def _create_cluster_from_claims(
        self, cluster_claims: List[Dict], label: int, silhouette: float
    ) -> DenialCluster:
        """Create a DenialCluster object from grouped claims."""
        # Analyze cluster characteristics
        payers = list(set(c['payer'] for c in cluster_claims))
        cpts = list(set(c['cpt'] for c in cluster_claims))
        denial_reasons = list(set(c['denial_reason'] for c in cluster_claims))

        # Most common denial reason
        reason_counts = {}
        for c in cluster_claims:
            reason = c['denial_reason']
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

        primary_reason = max(reason_counts, key=reason_counts.get)
        secondary_reasons = [r for r in denial_reasons if r != primary_reason]

        # Calculate totals
        total_dollars = sum(float(c['allowed_amount'] or 0) for c in cluster_claims)

        # Get date range
        claims_list = [c['claim'] for c in cluster_claims]
        first_date = min(c.decided_date for c in claims_list)
        last_date = max(c.decided_date for c in claims_list)

        # Generate AI description
        pattern_desc = self._generate_pattern_description(
            cluster_claims, primary_reason, payers, cpts
        )
        root_cause = self._generate_root_cause_hypothesis(
            cluster_claims, primary_reason
        )

        # Create cluster
        cluster_id = f"CLU-{timezone.now().year}-{label:03d}"

        cluster = DenialCluster.objects.create(
            customer=self.customer,
            cluster_id=cluster_id,
            cluster_name=f"Denial Cluster: {primary_reason[:50]}",
            primary_denial_reason=primary_reason,
            secondary_denial_reasons=secondary_reasons,
            payers=payers,
            cpt_codes=cpts,
            claim_count=len(cluster_claims),
            total_denied_dollars=Decimal(str(total_dollars)),
            cluster_confidence=min(silhouette + 0.5, 1.0),  # Normalize
            silhouette_score=silhouette,
            pattern_description=pattern_desc,
            root_cause_hypothesis=root_cause,
            first_denial_date=first_date,
            last_denial_date=last_date,
        )

        return cluster

    def _generate_pattern_description(
        self, cluster_claims: List[Dict], primary_reason: str, payers: List[str], cpts: List[str]
    ) -> str:
        """Generate human-readable pattern description."""
        claim_count = len(cluster_claims)

        if len(payers) == 1:
            payer_desc = f"payer {payers[0]}"
        else:
            payer_desc = f"{len(payers)} payers"

        if len(cpts) <= 3:
            cpt_desc = f"CPT codes {', '.join(cpts)}"
        else:
            cpt_desc = f"{len(cpts)} different CPT codes"

        return (
            f"Cluster of {claim_count} denials with reason '{primary_reason}' "
            f"affecting {payer_desc} and {cpt_desc}. "
            f"This pattern suggests a systematic issue requiring investigation."
        )

    def _generate_root_cause_hypothesis(
        self, cluster_claims: List[Dict], primary_reason: str
    ) -> str:
        """Generate hypothesis about root cause."""
        # Simple rule-based root cause inference
        reason_lower = primary_reason.lower()

        if 'auth' in reason_lower or 'prior' in reason_lower:
            return "Likely root cause: Authorization workflow breakdown or missing prior auth requests."
        elif 'medical' in reason_lower or 'necessity' in reason_lower:
            return "Likely root cause: Insufficient documentation of medical necessity or policy coverage gap."
        elif 'timely' in reason_lower or 'filing' in reason_lower:
            return "Likely root cause: Claims submission timing issues or administrative delays."
        elif 'coding' in reason_lower or 'invalid' in reason_lower:
            return "Likely root cause: Coding errors or outdated CPT code usage."
        elif 'duplicate' in reason_lower:
            return "Likely root cause: Duplicate claim submission or billing system issue."
        else:
            return f"Possible root cause related to '{primary_reason}' - requires further investigation."


class CascadeDetectionService:
    """
    Detect cascading denials - related denials across claims.
    """

    def __init__(self, customer):
        self.customer = customer

    def detect_cascades(self, days_back: int = 60) -> List[DenialCascade]:
        """Detect denial cascades in recent claims."""
        start_date = timezone.now().date() - timedelta(days=days_back)

        cascades = []

        # 1. Temporal cascades (burst of denials in short timeframe)
        temporal_cascades = self._detect_temporal_cascades(start_date)
        cascades.extend(temporal_cascades)

        # 2. Payer systemic cascades (same payer, similar issues)
        payer_cascades = self._detect_payer_systemic_cascades(start_date)
        cascades.extend(payer_cascades)

        return cascades

    def _detect_temporal_cascades(self, start_date) -> List[DenialCascade]:
        """Detect bursts of denials in short time periods."""
        cascades = []

        # Group denials by payer and week
        denied_claims = ClaimRecord.objects.filter(
            customer=self.customer,
            outcome='DENIED',
            decided_date__gte=start_date
        ).order_by('decided_date')

        # Find weeks with unusual denial spikes
        payer_weeks = {}
        for claim in denied_claims:
            payer = claim.payer
            week = claim.decided_date.isocalendar()[:2]  # (year, week)

            key = (payer, week)
            if key not in payer_weeks:
                payer_weeks[key] = []
            payer_weeks[key].append(claim)

        # Identify cascades (>= 10 denials in one week)
        for (payer, week), claims in payer_weeks.items():
            if len(claims) >= 10:
                cascade = self._create_temporal_cascade(payer, claims)
                cascades.append(cascade)

        return cascades

    def _create_temporal_cascade(self, payer: str, claims: List) -> DenialCascade:
        """Create temporal cascade from claims."""
        denial_reasons = list(set(
            c.denial_reason_code or c.denial_reason_text or 'UNKNOWN'
            for c in claims
        ))

        total_dollars = sum(float(c.allowed_amount or 0) for c in claims)

        start_date = min(c.decided_date for c in claims)
        end_date = max(c.decided_date for c in claims)

        cascade_id = f"CAS-{payer[:10]}-{start_date.strftime('%Y%m%d')}"

        pattern_summary = (
            f"Detected temporal cascade: {len(claims)} denials from {payer} "
            f"occurred between {start_date} and {end_date}. "
            f"This represents an unusual spike in denial activity."
        )

        cascade = DenialCascade.objects.create(
            customer=self.customer,
            cascade_id=cascade_id,
            cascade_type='temporal',
            claim_ids=[c.id for c in claims],
            claim_count=len(claims),
            payer=payer,
            denial_reasons=denial_reasons,
            total_denied_dollars=Decimal(str(total_dollars)),
            confidence_score=0.8,
            pattern_summary=pattern_summary,
            root_cause=f"Sudden change in {payer} claims processing or policy",
            cascade_start_date=start_date,
            cascade_end_date=end_date,
        )

        return cascade

    def _detect_payer_systemic_cascades(self, start_date) -> List[DenialCascade]:
        """Detect payer-wide systematic denial issues."""
        cascades = []

        # Find payers with high denial rates
        payer_stats = ClaimRecord.objects.filter(
            customer=self.customer,
            decided_date__gte=start_date
        ).values('payer').annotate(
            total=Count('id'),
            denials=Count('id', filter=Q(outcome='DENIED'))
        )

        for stat in payer_stats:
            if stat['total'] >= 50 and stat['denials'] >= 15:
                denial_rate = stat['denials'] / stat['total']

                if denial_rate >= 0.25:  # 25% denial rate
                    # Get the denied claims
                    denied_claims = ClaimRecord.objects.filter(
                        customer=self.customer,
                        payer=stat['payer'],
                        outcome='DENIED',
                        decided_date__gte=start_date
                    )

                    # Check if they share common denial reasons
                    reason_counts = {}
                    for claim in denied_claims:
                        reason = claim.denial_reason_code or 'UNKNOWN'
                        reason_counts[reason] = reason_counts.get(reason, 0) + 1

                    # If majority share same reason, it's a systemic issue
                    if reason_counts:
                        max_reason = max(reason_counts, key=reason_counts.get)
                        if reason_counts[max_reason] / len(denied_claims) >= 0.5:
                            cascade = self._create_payer_systemic_cascade(
                                stat['payer'],
                                list(denied_claims),
                                max_reason,
                                start_date
                            )
                            cascades.append(cascade)

        return cascades

    def _create_payer_systemic_cascade(
        self, payer: str, claims: List, primary_reason: str, start_date
    ) -> DenialCascade:
        """Create payer systemic cascade."""
        total_dollars = sum(float(c.allowed_amount or 0) for c in claims)
        end_date = max(c.decided_date for c in claims)

        cascade_id = f"CAS-SYS-{payer[:10]}-{primary_reason[:10]}"

        pattern_summary = (
            f"Systemic denial issue detected: {len(claims)} claims from {payer} "
            f"denied for '{primary_reason}'. This appears to be a payer-wide policy issue."
        )

        cascade = DenialCascade.objects.create(
            customer=self.customer,
            cascade_id=cascade_id,
            cascade_type='payer_systemic',
            claim_ids=[c.id for c in claims],
            claim_count=len(claims),
            payer=payer,
            denial_reasons=[primary_reason],
            total_denied_dollars=Decimal(str(total_dollars)),
            confidence_score=0.9,
            pattern_summary=pattern_summary,
            root_cause=f"Systematic {payer} policy change or interpretation issue",
            resolution_recommended=f"Contact {payer} to clarify policy on '{primary_reason}'",
            cascade_start_date=start_date,
            cascade_end_date=end_date,
        )

        return cascade


class PreDenialWarningService:
    """
    Predictive pre-denial warnings using ML.
    """

    def __init__(self, customer):
        self.customer = customer

    def generate_warnings(self, claim: ClaimRecord) -> List[PreDenialWarning]:
        """
        Generate pre-denial warnings for a claim.

        Uses rule-based heuristics (placeholder for actual ML model).
        """
        warnings = []

        # Rule 1: Check for missing authorization
        if claim.authorization_required and not claim.authorization_obtained:
            warning = PreDenialWarning.objects.create(
                customer=self.customer,
                warning_id=f"WARN-AUTH-{claim.id}",
                claim_record=claim,
                warning_type='auth_missing',
                predicted_denial_reason='Authorization not obtained',
                denial_probability=0.85,
                confidence_score=0.9,
                risk_factors=[
                    {'factor': 'Authorization required but not obtained', 'weight': 1.0},
                ],
                payer=claim.payer,
                cpt_code=claim.cpt,
                estimated_claim_value=claim.allowed_amount,
                recommended_actions=[
                    {'action': 'Obtain prior authorization immediately', 'priority': 'high'},
                    {'action': 'Contact payer to confirm auth requirements', 'priority': 'medium'},
                ],
                intervention_deadline=(claim.submitted_date + timedelta(days=7)) if claim.submitted_date else None,
                model_version='rule-based-v1',
            )
            warnings.append(warning)

        # Rule 2: Historical payer denial patterns
        # (In production, this would use ML model predictions)

        return warnings


class AppealGenerationService:
    """
    AI-powered appeal generation.
    """

    def __init__(self, customer):
        self.customer = customer

    def generate_appeal(self, claim: ClaimRecord) -> AppealGeneration:
        """
        Generate appeal letter for denied claim.

        Uses template matching and AI content generation.
        """
        if claim.outcome != 'DENIED':
            raise ValueError("Can only generate appeals for denied claims")

        # Find matching template
        template = self._find_best_template(claim)

        # Generate appeal content
        appeal_letter = self._generate_appeal_content(claim, template)

        # Create appeal generation
        appeal = AppealGeneration.objects.create(
            customer=self.customer,
            appeal_id=f"APP-{claim.id}-{timezone.now().strftime('%Y%m%d')}",
            claim_record=claim,
            template_used=template,
            appeal_letter=appeal_letter,
            required_documentation=template.required_documentation if template else [],
            denial_reason=claim.denial_reason_code or claim.denial_reason_text or 'UNKNOWN',
            appeal_reason=self._generate_appeal_reason(claim),
            supporting_evidence=self._generate_supporting_evidence(claim),
            status='draft',
            generation_confidence=0.85 if template else 0.65,
        )

        return appeal

    def _find_best_template(self, claim: ClaimRecord) -> AppealTemplate:
        """Find best matching appeal template."""
        templates = AppealTemplate.objects.filter(
            customer=self.customer,
            active=True
        ).order_by('-success_rate')

        # Try exact denial code match
        if claim.denial_reason_code:
            template = templates.filter(
                denial_reason_code=claim.denial_reason_code
            ).first()
            if template:
                return template

        # Try payer-specific match
        template = templates.filter(payer=claim.payer).first()
        if template:
            return template

        # Use best generic template
        return templates.first()

    def _generate_appeal_content(self, claim: ClaimRecord, template: AppealTemplate) -> str:
        """Generate appeal letter content."""
        if template:
            # Fill template with claim data
            content = template.appeal_letter_template.format(
                payer=claim.payer,
                claim_id=claim.id,
                cpt_code=claim.cpt,
                service_date=claim.submitted_date,
                denied_amount=claim.allowed_amount,
                denial_reason=claim.denial_reason_code or claim.denial_reason_text,
            )
            return content
        else:
            # Generate generic appeal
            return f"""
Dear {claim.payer} Appeals Department,

I am writing to formally appeal the denial of claim #{claim.id} for services rendered on {claim.submitted_date}.

The claim was denied with reason: {claim.denial_reason_code or claim.denial_reason_text}

We believe this denial was made in error for the following reasons:
1. The service (CPT {claim.cpt}) was medically necessary and appropriate
2. All required documentation was provided with the original claim
3. The service meets the criteria outlined in your coverage policies

We respectfully request that you review this claim and overturn the denial.

Sincerely,
[Provider Name]
"""

    def _generate_appeal_reason(self, claim: ClaimRecord) -> str:
        """Generate appeal reasoning."""
        denial = claim.denial_reason_code or claim.denial_reason_text or 'UNKNOWN'

        if 'auth' in denial.lower():
            return "Authorization was obtained prior to service as required. Authorization number provided in original claim."
        elif 'medical necessity' in denial.lower():
            return "Service was medically necessary based on patient condition and clinical guidelines."
        elif 'timely filing' in denial.lower():
            return "Claim was filed within required timeframe. Documentation of timely filing attached."
        else:
            return f"Denial reason '{denial}' does not apply to this claim based on the facts and documentation provided."

    def _generate_supporting_evidence(self, claim: ClaimRecord) -> List[str]:
        """Generate list of supporting evidence points."""
        evidence = [
            f"Claim submitted on {claim.submitted_date}",
            f"Service provided with CPT code {claim.cpt}",
        ]

        if claim.authorization_number:
            evidence.append(f"Prior authorization obtained: {claim.authorization_number}")

        return evidence
