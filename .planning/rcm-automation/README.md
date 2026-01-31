# RCM Automation Strategic Framework

**From Alerts to Autonomous Execution: Implementation Guide for Upstream Healthcare**

## Quick Start

This directory contains the complete strategic framework for building autonomous revenue cycle management automation that competes with Adonis Intelligence, AKASA, and Waystar while maintaining compliance-first design.

### Documents Overview

| Document | Purpose | Audience |
|----------|---------|----------|
| [RCM_AUTOMATION_ROADMAP.md](./RCM_AUTOMATION_ROADMAP.md) | Strategic overview, competitive analysis, technical architecture, implementation phases | Product, Engineering, Leadership |
| [COMPLIANCE_REQUIREMENTS.md](./COMPLIANCE_REQUIREMENTS.md) | Legal requirements, HIPAA audit trails, state AI laws, red-line actions | Compliance, Legal, Engineering |
| [UX_TRUST_PATTERNS.md](./UX_TRUST_PATTERNS.md) | Trust calibration, notification system, undo patterns, dashboard design | Product Design, Frontend Engineering |

### Code Implementation

| File | Purpose |
|------|---------|
| [upstream/automation/models.py](../../upstream/automation/models.py) | ClaimScore, CustomerAutomationProfile, ShadowModeResult models |

---

## Core Concepts

### Three-Tier Automation Model

**Tier 1: Auto-Execute (High Confidence)**
- Confidence: >95%
- Dollar: <$1,000
- Actions: Auto-submit, auto-post, auto-adjudicate
- Example: Routine office visits with complete documentation

**Tier 2: Queue for Review (Medium Confidence)**
- Confidence: 70-95%
- Dollar: $1,000-$10,000
- Actions: Queue with AI pre-fill, human one-click approval
- Example: Complex coding scenarios, minor documentation gaps

**Tier 3: Escalate (Low Confidence / High Risk)**
- Confidence: <70%
- Dollar: >$10,000
- Actions: Route to senior adjuster, medical director, compliance
- Example: Medical necessity questions, fraud indicators

### Trust Calibration Framework (4 Stages)

1. **Observe (Weeks 1-2):** AI recommends, human takes all actions
2. **Suggest (Weeks 3-4):** AI pre-fills, human confirms with one click
3. **Act + Notify (Weeks 5-8):** AI executes, human notified with undo
4. **Full Autonomy (Week 9+):** AI executes silently, summary reports only

**Progression Criteria:**
- Shadow mode accuracy >95%
- Customer satisfaction score >4/5
- Zero compliance violations
- <5% undo rate

### Compliance Red Lines (Cannot Automate)

**Legally Required Human Review:**
1. Medical necessity determinations (CA SB 1120, FL SB 794)
2. Code changes affecting reimbursement (FCA liability)
3. Denial appeals (legal certifications)
4. Stark Law referrals (anti-kickback exposure)
5. 60-day overpayment determinations (FCA trigger)
6. Fraud investigations (SIU required)

**Implementation:**
```python
if claim_score.requires_human_review:
    escalate_to_human(claim, reason=claim_score.red_line_reason)
```

---

## Competitive Positioning

### Market Landscape

| Vendor | Autonomous Execution | Verified Accuracy | Appeals Automation | Voice AI |
|--------|---------------------|-------------------|--------------------| ---------|
| **Adonis** | ✅ (unverified) | ❌ No KLAS | ❌ Human review | ✅ Claimed |
| **AKASA** | ✅ Cleveland Clinic | ✅ 99.5% | ❌ Limited | ❌ |
| **Waystar** | ✅ Prior auth | ✅ 85% auto-approve | ❌ Draft only | ❌ |
| **Infinx** | ✅ RPA hybrid | ⚠️ 50% cost reduction | ❌ Templates | ❌ |
| **Experian** | ❌ Alerts only | ✅ 4% denial rate | ❌ | ❌ |
| **Upstream** | 🎯 **Target** | 🎯 **>95%** | 🎯 **LLM + RAG** | 🎯 **Planned** |

### Differentiation Opportunities

1. **Appeals Automation** (No competitor fully auto-submits)
   - LLM + RAG for clinical justification
   - Always require human approval (but save 90% of time)
   - Success pattern matching from historical data

2. **Voice AI** (Adonis claims, not validated)
   - Twilio/Vapi.ai for outbound payer calls
   - IVR navigation with ASR
   - Live agent conversation (NLU)
   - Structured outcome logging

3. **Explainable AI by Default** (Most competitors black-box)
   - Feature importance in every decision
   - Human-readable reasoning
   - Confidence score breakdowns

4. **Compliance-First Design** (Competitors add compliance later)
   - Audit trails exceeding HIPAA minimums
   - State AI law compliance (CA, FL, CT)
   - Configurable human oversight

---

## Implementation Roadmap

### Week 1 Foundation ✅ COMPLETE

**Deliverables:**
- ✅ Authorization model (multi-vertical)
- ✅ ExecutionLog (HIPAA audit trails)
- ✅ AutomationRule framework
- ✅ RulesEngine foundation
- ✅ EHR webhook integration

**Commits:**
- `348f1b57`: Week 1 foundation
- `1a4960ad`: Multi-vertical Authorization support
- `42407690`: RCM automation strategic framework

### Phase 1: Confidence Scoring (Weeks 2-4)

**Deliverables:**
- [ ] Add ClaimScore model to migrations
- [ ] Train ML models (Random Forest, Gradient Boosting)
- [ ] Implement confidence threshold routing
- [ ] Build CustomerAutomationProfile UI
- [ ] Enable shadow mode tracking

**Success Criteria:**
- AUC score >0.85
- Shadow mode accuracy >95%
- Zero false positive escalations to compliance

### Phase 2: Three-Tier Automation (Weeks 5-8)

**Deliverables:**
- [ ] Expand AutomationRule with tier-specific logic
- [ ] Build exception queue UI
- [ ] Implement one-click approval (Stage 2)
- [ ] Add post-action notifications (Stage 3)
- [ ] Create automation dashboard

**Success Criteria:**
- 60%+ claims auto-executed (Tier 1)
- <5 minutes average review time (Tier 2)
- 100% red-line compliance (Tier 3)

### Phase 3: Portal RPA (Weeks 9-12)

**Deliverables:**
- [ ] UiPath/Playwright integration
- [ ] Payer portal credential vault
- [ ] 2FA automation (TOTP)
- [ ] Status check automation
- [ ] Clearinghouse integration

**Success Criteria:**
- 80%+ portal login success rate
- <2 minute average status check time
- Zero credential leaks

### Phase 4: Appeal Generation (Weeks 13-16)

**Deliverables:**
- [ ] LLM integration (OpenAI/Claude)
- [ ] RAG system for clinical guidelines
- [ ] Success pattern matching
- [ ] Human review workflow
- [ ] Multi-channel submission (portal/fax/EDI)

**Success Criteria:**
- 90% time savings (draft appeals)
- 70%+ appeal success rate
- 100% human review compliance

### Phase 5: Voice AI (Weeks 17-20)

**Deliverables:**
- [ ] Twilio/Vapi.ai integration
- [ ] IVR navigation
- [ ] Live agent conversation (NLU)
- [ ] Structured outcome logging
- [ ] Call recording compliance

**Success Criteria:**
- 80%+ IVR navigation success
- 60%+ live agent info extraction
- Zero HIPAA violations

---

## Key Metrics & KPIs

### Technical Metrics

| Metric | Target | Benchmark |
|--------|--------|-----------|
| AUC Score | >0.85 | Industry: 0.83-0.88 |
| Automation Rate | 60-90% | AKASA: ~80% |
| Accuracy | >95% | Human coders: 95% |
| Denial Reduction | 25-50% | Waystar: 85% auto-approve |
| False Positive Rate | <2% | N/A |

### Business Metrics

| Metric | Target | Industry Avg |
|--------|--------|--------------|
| Time to Resolution | 50%+ reduction | 18 hours |
| Cost per Claim | 30-50% reduction | $5-10 |
| Days in AR | 15-25% improvement | 40-50 days |
| Clean Claim Rate | >95% | 85% |

### Compliance Metrics

| Metric | Target | Requirement |
|--------|--------|-------------|
| Audit Trail Completeness | 100% | HIPAA 45 CFR 164.312 |
| Human Review Compliance | 100% | State laws (CA, FL, CT) |
| FCA Violations | 0 | $13K-$27K per claim |
| Shadow Mode Accuracy | >95% | Before live deployment |

### Customer Trust Metrics

| Metric | Target | Rationale |
|--------|--------|-----------|
| Stage 3 Advancement Rate | 80% within 6 months | Trust calibration success |
| Undo Action Rate | <5% | Confidence in AI decisions |
| Customer Satisfaction (NPS) | >50 | Industry benchmark |
| Shadow Mode Opt-In Rate | >90% | Willingness to validate |

---

## Quick Reference

### When to Auto-Execute (Tier 1)

```python
def can_auto_execute(claim: ClaimRecord) -> bool:
    score = claim.score
    profile = claim.customer.automation_profile

    return (
        score.overall_confidence >= profile.auto_execute_confidence and
        claim.allowed_amount <= profile.auto_execute_max_amount and
        not score.requires_human_review and
        not profile.shadow_mode_enabled and
        profile.automation_stage in ['act_notify', 'full_autonomy']
    )
```

### When to Escalate (Tier 3)

```python
def should_escalate(claim: ClaimRecord) -> bool:
    score = claim.score
    profile = claim.customer.automation_profile

    return (
        score.requires_human_review or  # Legal requirement
        score.overall_confidence < profile.queue_review_min_confidence or
        claim.allowed_amount >= profile.escalate_min_amount or
        score.fraud_risk_score > 0.7 or
        score.compliance_risk_score > 0.7
    )
```

### Notification Severity Matrix

| Action | Severity | Delivery | Undo Window |
|--------|----------|----------|-------------|
| Claim denied | High | Modal + Push + Email | N/A (cannot undo) |
| Claim submitted | Medium | Toast | 2-24 hours |
| Status check | Low | Daily digest | Immediate |
| Large dollar (>$10K) | High | Modal + Push + Email | Time-windowed |
| Compliance escalation | High | Modal + Push + Email | N/A (requires review) |
| Appeal generated | Medium | Toast | 30 days (soft delete) |

---

## Getting Started

### For Product Managers
1. Read [RCM_AUTOMATION_ROADMAP.md](./RCM_AUTOMATION_ROADMAP.md) for strategic overview
2. Review competitive analysis and differentiation opportunities
3. Prioritize implementation phases with engineering

### For Engineers
1. Review [upstream/automation/models.py](../../upstream/automation/models.py) for data models
2. Read [COMPLIANCE_REQUIREMENTS.md](./COMPLIANCE_REQUIREMENTS.md) for red-line detection
3. Implement ClaimScore model and confidence scoring pipeline

### For Designers
1. Read [UX_TRUST_PATTERNS.md](./UX_TRUST_PATTERNS.md) for UI patterns
2. Design Stage 1-4 trust calibration flows
3. Create dashboard mockups with three-status hierarchy

### For Compliance
1. Read [COMPLIANCE_REQUIREMENTS.md](./COMPLIANCE_REQUIREMENTS.md) thoroughly
2. Review red-line actions requiring human review
3. Validate audit trail fields meet HIPAA requirements
4. Sign off on BAA AI-specific clauses

---

## Frequently Asked Questions

**Q: Can we auto-submit appeals?**
A: No. Appeals contain legal certifications requiring clinical judgment. AI can draft appeals (saving 90% of time), but human sign-off is always required.

**Q: What confidence threshold should we use?**
A: Start conservative (98%), then lower to 95% after shadow mode validates accuracy. Customers can configure their own thresholds based on risk tolerance.

**Q: How long should shadow mode run?**
A: Minimum 4 weeks, target 6-8 weeks. Require >95% accuracy and compliance officer sign-off before enabling live automation.

**Q: What if a customer wants <70% confidence threshold?**
A: Allow configuration but warn about increased false positive rate. Recommend starting higher and lowering gradually based on performance data.

**Q: Do we need human review for all $10K+ claims?**
A: Not legally required, but recommended for risk mitigation. Customers can configure their own dollar thresholds.

**Q: What happens if we violate a state AI law?**
A: Customer bears liability (not vendor). Implement red-line detection for CA, FL, CT requirements. Get legal sign-off before deploying in new states.

**Q: Can we train ML models on customer PHI?**
A: Only with explicit written authorization in BAA. De-identify per HIPAA Safe Harbor. Customer owns derivative models trained on their data.

**Q: How do we compete with Adonis's 90% claim rate?**
A: Focus on validated accuracy (>95% with KLAS rating) vs. marketing claims. Build trust through transparency and compliance-first design.

---

## Resources

### External Documentation
- [HIPAA Security Rule 45 CFR 164.312](https://www.hhs.gov/hipaa/for-professionals/security/laws-regulations/index.html)
- [False Claims Act 31 U.S.C. § 3729](https://www.justice.gov/civil/false-claims-act)
- [California SB 1120 (AI in Healthcare)](https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=202320240SB1120)
- [CMS Prior Auth API Rule (CMS-0057-F)](https://www.cms.gov/newsroom/fact-sheets/cms-interoperability-and-prior-authorization-final-rule-cms-0057-f)

### Competitor Research
- [Adonis Intelligence Case Study](https://www.adonishealth.com/) (ApolloMD 90% autonomous rate)
- [AKASA Human-in-the-Loop](https://akasa.com/) (99.5% accuracy)
- [Waystar Prior Auth](https://www.waystar.com/) (85% auto-approval)
- [KLAS Research RCM Reports](https://klasresearch.com/)

### Technical Resources
- [UiPath Healthcare Automation](https://www.uipath.com/solutions/industry/healthcare)
- [FHIR R4 Specification](https://hl7.org/fhir/)
- [SMART on FHIR](https://smarthealthit.org/)

---

**Document Version:** 1.0
**Last Updated:** 2026-01-31
**Maintainer:** Product Team
**Status:** Active Development
