# Upstream Demo Story

**Duration**: 10-15 minutes  
**Audience**: Revenue Cycle Director, Billing Manager, Potential Customer  
**Goal**: Show value discovery in a realistic scenario

---

## The Persona: Sam, Revenue Cycle Director

**Name**: Sam Martinez  
**Title**: Revenue Cycle Director at Midwest Family Practice  
**Practice Size**: 12 providers, ~$8M annual collections  
**Current Challenge**: Denial rates have been creeping up but Sam doesn't know which payers are causing it or why

**Sam's Day**: 
- Spends 2 hours/week in monthly reports looking for problems
- Usually discovers issues 30-45 days after they start
- Gets surprised by AR aging spikes that could have been caught earlier
- Wants a way to catch problems in Week 1, not Month 2

---

## The Setup

### Demo Environment
```bash
# Generate demo data for a realistic scenario
python manage.py generate_driftwatch_demo --customer 1
python manage.py generate_denialscope_test_data --customer 1
python manage.py compute_denialscope --customer 1
```

### Scenario
It's Monday morning. Sam logs into Upstream for their weekly check. Unknown to Sam, Blue Cross started denying more E&M claims last week due to a policy change. This is Sam's first alert.

---

## Part 1: The Morning Check (2 min)

### Talking Points
> "Let's walk through Sam's Monday morning. She opens Upstream to check if there's anything urgent—this should take about 5 minutes."

### Steps
1. **Open the Portal** → Navigate to `/portal/`
   
2. **Show the Dashboard** → Note the "What is This?" section at top
   > "Notice Upstream explains what you're looking at right here. It watches denial rates and dollar spikes—the two things that matter for catching payer behavior changes."

3. **Point to High-Severity Signal**
   > "See this red badge? That's a High severity signal. It says 'Investigate Today'—that means something changed enough to warrant attention."

---

## Part 2: Understanding the Signal (3 min)

### Talking Points
> "Let's click into this signal and see what Sam is dealing with."

### Steps
1. **Review DriftWatch Dashboard**
   - Show the "Recent Drift Events" table
   - Point to the Blue Cross row (or Demo-Payer-1)
   
   > "Here's what happened: Blue Cross's denial rate jumped from 8% to 16%. That's an 8-point increase in one week. Normal variance for this payer is 2-3 points."

2. **Explain the Numbers**
   - **Baseline**: 0.08 (8%) — average over last 4 weeks
   - **Current**: 0.16 (16%) — this week
   - **Delta**: +0.08 (+8 points) — the change
   - **Severity**: 0.75 (High) — outside normal patterns

   > "Upstream doesn't just show you data—it tells you if it matters. Severity 0.75 means this is statistically significant. It's not noise."

3. **Show the Evidence Section**
   > "And here's the evidence: specific claims, specific CPT groups, specific time range. Sam doesn't have to dig—it's all here."

---

## Part 3: The "So What?" (3 min)

### Talking Points
> "Now here's where it gets interesting. What does this actually cost Sam if she doesn't catch it?"

### The Math
- Blue Cross volume: ~200 claims/week at $150 avg = $30,000/week submitted
- Normal denial rate: 8% = $2,400/week denied
- New denial rate: 16% = $4,800/week denied
- **Weekly impact: $2,400 additional denials**

> "If Sam catches this in Week 1, she loses $2,400. If she catches it in her monthly report (Week 4), she's lost $9,600. If it takes 8 weeks to notice, that's $19,200."

### The Value
> "Upstream caught this in Week 1. Sam has 3 weeks of runway to investigate, appeal, or adjust—instead of discovering it after the damage is done."

---

## Part 4: What Sam Does Next (3 min)

### Talking Points
> "So Sam sees the alert. What does she actually do about it?"

### Steps
1. **Read the Alert Email** (if demo includes email)
   - Show "What This Means" section
   - Show "Recommended Action" with specific steps
   
   > "Upstream doesn't just say 'something changed'—it says what to do about it."

2. **Pull Sample Claims**
   > "Sam pulls 5 claims from the evidence table. She sees they're all E&M codes (99213, 99214) getting denied for 'Medical necessity not established.'"

3. **Check for Root Cause**
   > "She checks her payer portal and finds Blue Cross issued a policy update last week: new documentation requirements for E&M visits."

4. **Take Action**
   > "Sam sends a quick note to her billing team: 'Heads up—Blue Cross has new E&M documentation requirements. Make sure providers are including X, Y, Z.' She schedules a training for Thursday."

### The Outcome
> "Problem identified in Week 1. Training happens in Week 1. By Week 2, denial rate is back to normal. Total exposure: one week. Without Upstream? Could have been 6-8 weeks."

---

## Part 5: The Routine (2 min)

### Talking Points
> "Let's zoom out. How does Upstream fit into Sam's week?"

### Daily Check (5 min)
> "Every morning, Sam opens the dashboard, checks for red badges, and moves on. Most days: nothing urgent. Takes 5 minutes."

### Weekly Review (20 min)
> "Monday morning, she spends 20 minutes reviewing the week's signals, investigating any medium-priority items, looking for patterns."

### Monthly Check (30 min)
> "First Monday of the month, she reviews last month's alerts, calculates rough ROI, and shares insights with her team."

### The Rhythm
> "Upstream becomes part of the routine—not a burden. It's the smoke detector that runs in the background, alerting when something's wrong."

---

## Closing: The Value Prop (1 min)

### Summary
> "Upstream doesn't replace Sam's judgment. It gives her early certainty."

> "Without Upstream: Sam discovers problems 30-60 days late, after the damage is done."

> "With Upstream: Sam catches problems in Week 1, when there's still time to act."

### The One-Liner
> "Upstream is like a smoke detector for your revenue cycle. It doesn't fight the fire—it tells you early, so you can."

---

## Demo Variations

### For Technical Audience
- Show the CLI commands for running analysis
- Explain the drift detection algorithm briefly
- Show the API endpoints

### For Executive Audience
- Focus on the ROI math
- Skip the dashboard details
- Emphasize the "early detection = early action" message

### For Hands-On Demo
- Let them click through the dashboard
- Generate demo data live
- Show an email alert coming through

---

## Objection Handling

### "We already have reports"
> "Reports tell you what happened. Upstream tells you what's changing—early enough to do something about it. It's not a replacement for reports; it's early warning before reports show the problem."

### "How accurate is it?"
> "Upstream uses statistical thresholds based on your historical data. It flags changes that are outside your normal variance. Early on, you might get a few false positives as it learns your patterns. Within a month, the signal-to-noise ratio improves."

### "We don't have time for another tool"
> "Daily check: 5 minutes. Weekly review: 20 minutes. That's less than an hour a week. Compare that to the hours spent investigating problems you catch too late."

### "What if we investigate and find nothing?"
> "That happens occasionally—and it's okay. A false positive costs you 30 minutes. A missed issue can cost you tens of thousands. We'd rather you check something that turns out to be fine than miss something that costs you."

---

## Demo Checklist

Before the demo:
- [ ] Fresh demo data generated
- [ ] At least one High severity signal present
- [ ] DriftWatch dashboard loads correctly
- [ ] DenialScope dashboard loads correctly
- [ ] "What is This?" sections visible
- [ ] Email template tested (if showing alerts)

During the demo:
- [ ] Start with the persona (Sam)
- [ ] Show the signal discovery
- [ ] Explain the "so what" (cost math)
- [ ] Walk through the response workflow
- [ ] End with the routine (daily/weekly/monthly)

After the demo:
- [ ] Ask for questions
- [ ] Offer to set up a trial with their data
- [ ] Share OPERATOR_GUIDE.md for self-service onboarding

---

## Quick Reference: Demo URLs

| Page | URL | Purpose |
|------|-----|---------|
| Portal Home | `/portal/` | Landing page |
| DriftWatch | `/portal/products/driftwatch/` | Denial rate drift |
| DenialScope | `/portal/products/denialscope/` | Denial dollar spikes |
| Reports | `/portal/reports/` | Historical analysis |

---

**Remember**: The goal of the demo is not to show features. It's to show **value discovery**—the moment Sam realizes Upstream caught something she would have missed.
