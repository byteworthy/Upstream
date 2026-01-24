# Upstream Operator Guide

**For**: Revenue Cycle Directors, Billing Managers, RCM Analysts  
**Purpose**: Understand what Upstream watches, why it matters, and how to respond

---

## What Upstream Watches

Upstream monitors **two critical signals** that indicate when your revenue is at risk:

### 1. Denial Rate Drift (DriftWatch)
**What it is**: Week-over-week changes in how often payers deny your claims.

**Why it matters**: 
- A payer quietly tightening their rules can cost you 5-10% in revenue before you notice
- Most practices discover denial rate changes 30-60 days too late
- Early detection = early intervention

**Example**: 
> "Blue Cross was approving 92% of your E&M codes. This week they're at 78%. That's a 14-point drop worth investigating today, not next month."

### 2. Denial Dollar Spike (DenialScope)
**What it is**: Sudden increases in total denial dollars from a specific payer or reason code.

**Why it matters**:
- Large dollar shifts signal contract changes, coding issues, or payer policy updates
- A $50K spike in one payer's denials is not "normal variance"
- These are revenue leaks you can plug if you catch them early

**Example**:
> "UnitedHealthcare denial dollars jumped from $12K to $68K this week. Primary reason: 'Medical necessity not established.' This is new behavior."

---

## What Upstream Doesn't Watch

Upstream is **not** a claims clearinghouse, a billing system, or a collections tool.

**It does NOT**:
- Submit claims for you
- Auto-appeal denials
- Replace your PM/EHR system
- Make decisions for you
- Track individual patient balances
- Manage your revenue cycle end-to-end

**What it IS**:
- An early warning system
- A pattern detector
- A signal above the noise
- A lens into payer behavior changes

---

## Why Early Detection Matters

### The 30-Day Problem
Most practices discover payer behavior changes **30-60 days after they start**:
- Monthly reports show the damage after it's done
- By the time you see it, you've already lost revenue
- Appeals have shorter windows than you think

### The Upstream Advantage
Upstream detects shifts **within 7 days**:
- Weekly analysis catches changes in the first cycle
- Alerts arrive when you can still act
- Historical context shows if this is new or recurring

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

| Severity | Delta | Action |
|----------|-------|--------|
| **High** | >10 points | Investigate today |
| **Medium** | 5-10 points | Review this week |
| **Low** | <5 points | Monitor for trend |

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
- Mark the alert as "Reviewed" (future feature)
- Document your findings
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
That's okay. False positives teach Upstream what "normal" looks like for you. Over time, the signal-to-noise ratio improves.

### "How do I explain this to my team?"
> "Upstream watches for when payers change how they treat our claims. It's like a smoke detector—it tells us early when something's wrong, so we can fix it before it becomes a fire."

---

## Getting Started

### Your First Week
1. Log in and review your current dashboard
2. Read through any active alerts
3. Pick one "High" severity alert to investigate
4. Document what you find
5. Share with your team

### Your First Month
1. Check the dashboard every Monday morning (5 min)
2. Investigate any new "High" alerts within 48 hours
3. Review "Medium" alerts during your weekly billing meeting
4. Track outcomes: What did you find? What action did you take?

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

### Long Term (6+ months)
- You're catching payer behavior changes in Week 1, not Month 2
- Your appeal success rate improves because you have early evidence
- Your contract negotiations are stronger because you have data on payer behavior shifts

---

## Need Help?

- **Technical issues**: Check `SETTINGS_GUIDE.md` and `DEPLOYMENT.md`
- **Workflow questions**: See `OPERATOR_WORKFLOWS.md`
- **Demo walkthrough**: See `DEMO_STORY.md`
- **Architecture details**: See `ARCHITECTURE_PRODUCT_LINE.md`

---

**Remember**: Upstream doesn't make decisions for you. It gives you **early certainty** so you can make better decisions faster.
