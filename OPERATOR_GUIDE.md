# Upstream Operator Guide

**For**: Revenue Cycle Directors, Billing Managers, RCM Analysts
**Purpose**: Understand what Upstream watches, why it matters, and how to respond

---

## What Upstream Is

Upstream is an **Early-Warning Payer Risk Intelligence Platform with Autonomous Execution**. It detects when payers change their behavior—denying more claims, changing policies, slowing payments—30-60 days before traditional monthly reporting would catch it. Then it can execute fixes autonomously.

> "You see the problem coming. You have time to act. The system acts for you."

---

## What Upstream Watches

Upstream monitors **six detection engines** that indicate when your revenue is at risk:

### 1. DriftWatch (Denial Rate Detection)

**What it is**: Week-over-week changes in how often payers deny your claims.

**Why it matters**:

- A payer quietly tightening their rules can cost you 5-10% in revenue before you notice
- Most practices discover denial rate changes 30-60 days too late
- Uses chi-square significance testing (p-value < 0.05 AND rate change > 10%)

**Example**:

> "Blue Cross was approving 92% of your E&M codes. This week they're at 78%. That's a 14-point drop worth investigating today, not next month."

### 2. DenialScope (Dollar Spike Detection)

**What it is**: Sudden increases in total denial dollars from a specific payer or reason code.

**Why it matters**:

- Large dollar shifts signal contract changes, coding issues, or payer policy updates
- Threshold: >$50K spike in weekly denial dollars
- Consolidates by payer and denial reason

**Example**:

> "UnitedHealthcare denial dollars jumped from $12K to $68K this week. Primary reason: 'Medical necessity not established.' This is new behavior."

### 3. DelayGuard (Payment Timing Detection)

**What it is**: Tracks median payment time and detects worsening trends.

**Why it matters**:

- Payment delays directly impact cash flow
- Uses 4-week rolling window for trend detection
- Calculates cash flow impact of payment slowdowns

**Example**:

> "Aetna's median payment time increased from 21 days to 34 days over the past month."

### 4. Authorization Tracking (Calendar-Based Prevention)

**What it is**: Proactive monitoring of authorization expirations and unit consumption.

**Why it matters**:

- 30/14/3 day advance warning for auth expirations
- Visit exhaustion projection (when units will run out)
- Credential expiration tracking (BCBA for ABA, etc.)

### 5. Pre-Submission Risk Scoring

**What it is**: Scores claims before submission to predict denial risk.

**Scoring weights**:

- Historical denial rate by CPT + payer combo (40%)
- Missing required modifiers (20%)
- Recent denial streak (20%)
- Diagnosis-CPT mismatch (10%)
- Authorization status (10%)

### 6. Behavioral Prediction Engine

**What it is**: Day-over-day denial rate comparison detecting emerging patterns.

**Why it matters**:

- Compares last 3 days vs previous 14 days
- Aggregates patterns across customers (network intelligence)
- Infers policy changes before official announcements

---

## Specialty Modules

Upstream includes specialty-specific intelligence for four verticals:

**Dialysis Intelligence**: MA Payment Variance, ESRD PPS Drift, TDAPA/TPNIES Add-on Tracking

**ABA Therapy Intelligence**: Authorization Cycle Tracking, Visit Exhaustion Projection, BCBA Credential Tracking

**Imaging Center Intelligence**: RBM Requirement Tracking, AUC Compliance, Medical Necessity Scoring

**Home Health Intelligence**: PDGM Grouper Validation, Face-to-Face Timing, NOA Deadline Tracking

---

## What Upstream Doesn't Do

Upstream is **not** a claims clearinghouse, a billing system, or a collections tool.

**It does NOT**:

- Submit claims for you (unless autonomous execution is enabled)
- Replace your PM/EHR system
- Track individual patient balances
- Manage your revenue cycle end-to-end

**What it IS**:

- An early warning system
- A pattern detector
- A lens into payer behavior changes
- An autonomous execution engine for approved workflows

---

## Autonomous Execution

Unlike traditional alert systems, Upstream can execute fixes autonomously when enabled.

**Pre-Approved Rule Types**:

- Reauthorization Request: Auto-submit reauth before expiration
- Appeal Generation: Generate appeals for specific denial patterns
- High Risk Hold: Flag high-risk claims for review before submission

**How It Works**: You define trigger conditions (payer, CPT, threshold). Upstream monitors for matching events. When triggered, action executes automatically. You receive notification after execution. Full audit trail logged (HIPAA-compliant).

---

## Why Early Detection Matters

### The 30-Day Problem

Most practices discover payer behavior changes **30-60 days after they start**:

- Monthly reports show the damage after it's done
- By the time you see it, you've already lost revenue
- Appeals have shorter windows than you think

### The Upstream Advantage

Upstream detects shifts **within 3-7 days**:

- DriftWatch: Weekly analysis catches changes in the first cycle
- Behavioral Prediction: Day-over-day comparison catches patterns in 72 hours
- Authorization Tracking: Calendar-based alerts before anything happens

### Real Cost Example

**Scenario**: Payer denial rate increases from 8% to 15%

- Weekly volume: 500 claims @ $200 avg = $100K submitted
- Additional denials: 35 claims = $7K/week
- **If detected in Week 1**: $7K loss
- **If detected in Week 4**: $28K loss
- **If detected in Week 8**: $56K loss

Early detection matters.

---

## Decision Framework: What Do I Do With This Alert?

### Step 1: Assess Urgency

Look at the **severity** and **delta**:

| Severity     | Delta       | Urgency Label       | Action           |
|--------------|-------------|---------------------|------------------|
| **Critical** | >15 points  | Investigate Now     | Drop everything  |
| **High**     | >10 points  | Investigate Today   | Address same day |
| **Medium**   | 5-10 points | Review This Week    | Schedule time    |
| **Low**      | <5 points   | Monitor for Trend   | Note and watch   |

### Step 2: Check Historical Context

Is this:

- **First time**: New behavior, highest priority
- **Recurring**: Known issue, may need escalation
- **Trending**: Getting worse over time, needs attention

### Step 3: Determine Next Move

**If it's URGENT (High + First Time)**:

1. Pull sample claims from the evidence list
2. Review denial reasons and payer correspondence
3. Check if contract terms or payer policies changed
4. Brief your billing team on what to watch
5. Consider immediate outreach to payer rep

**If it's A TREND (Medium + Recurring)**:

1. Compare to previous alerts for this payer
2. Calculate cumulative revenue impact
3. Determine if this is the "new normal" or fixable
4. Schedule review with billing leadership
5. Document for contract renegotiation leverage

**If it's NOISE (Low + Isolated)**:

1. Mark as reviewed
2. Watch for recurrence next week
3. No immediate action needed

### Step 4: Close the Loop

After investigating:

- Update the alert status (Reviewed, Actionable, Noise)
- Document your findings in the resolution form
- Update your team on what you learned
- Watch for recurrence in next week's report

---

## Trust Building: How to Know Upstream Is Right

### Week 1: Calibration

- You'll see alerts
- Some will feel obvious ("Yeah, I knew that")
- Some will feel surprising ("Really? Let me check")
- **This is normal**

### Week 2-4: Pattern Recognition

- You'll start seeing which payers are consistent vs volatile
- You'll recognize your "usual suspects"
- You'll catch 1-2 issues you wouldn't have seen otherwise
- **This is when trust starts**

### Month 2+: Early Certainty

- Alerts will feel predictive, not reactive
- You'll trust the signals enough to act without full investigation
- You'll catch issues before your monthly reports show them
- **This is when it becomes part of your workflow**

---

## Common Questions

### "How do I know this isn't just normal variance?"

Upstream uses statistical thresholds based on your historical data. A "high severity" alert means the change is **outside normal variance** for your practice.

### "What if I don't have time to investigate every alert?"

Focus on **High severity + First time** signals first. Low severity alerts are informational and can be reviewed weekly.

### "Will this replace my monthly reporting?"

No. Upstream is **early detection**, not **comprehensive reporting**. Use it alongside your monthly reports, not instead of them.

### "What if I investigate and find nothing?"

That's okay. False positives teach Upstream what "normal" looks like for you. Over time, the signal-to-noise ratio improves. Mark it as "Noise" so the system learns.

### "What about autonomous execution - is it safe?"

Autonomous execution only runs pre-approved rules you define. Every action is logged with full audit trail. You can disable any rule or all automation with one click.

### "How do I explain this to my team?"

> "Upstream watches for when payers change how they treat our claims. It's like a smoke detector—it tells us early when something's wrong, so we can fix it before it becomes a fire. And if we enable automation, it can call the fire department for us."

---

## Getting Started

### Your First Week

1. Log in and review your current dashboard
2. Read through any active alerts
3. Pick one "High" severity alert to investigate
4. Document what you find using the resolution form
5. Share with your team

### Your First Month

1. Check the dashboard every Monday morning (5 min)
2. Investigate any new "High" alerts within 48 hours
3. Review "Medium" alerts during your weekly billing meeting
4. Track outcomes: What did you find? What action did you take?
5. Consider enabling one automation rule for a low-risk workflow

### Building the Habit

- **Daily check** (5 min): Any new high-priority alerts?
- **Weekly review** (20 min): Investigate active signals, review trends
- **Monthly sanity check** (30 min): Is Upstream catching things you'd miss? What's the ROI?

---

## Success Looks Like

### Short Term (Month 1-2)

- You catch 1-2 denial rate changes before they show up in monthly reports
- Your team knows what Upstream is and checks it regularly
- You have evidence to bring to payer conversations

### Medium Term (Month 3-6)

- Upstream is part of your Monday morning routine
- You trust the High severity alerts enough to act without full investigation
- You've prevented at least one 5-figure revenue leak
- You've enabled at least one automation rule

### Long Term (6+ months)

- You're catching payer behavior changes in Week 1, not Month 2
- Your appeal success rate improves because you have early evidence
- Your contract negotiations are stronger because you have data on payer behavior shifts
- Autonomous execution handles routine tasks, freeing your team

---

## Need Help?

- **Technical issues**: Check `SETTINGS_GUIDE.md` and `GCP_DEPLOYMENT_GUIDE.md`
- **Workflow questions**: See `OPERATOR_WORKFLOWS.md`
- **Demo walkthrough**: See `DEMO_STORY.md`
- **Architecture details**: See `ARCHITECTURE_PRODUCT_LINE.md`
- **Authentication & Roles**: See `AUTHENTICATION_GUIDE.md`
- **Testing**: See `docs/TESTING.md`

---

**Remember**: Upstream doesn't make decisions for you. It gives you **early certainty** so you can make better decisions faster—and optionally executes approved actions so you don't have to.
