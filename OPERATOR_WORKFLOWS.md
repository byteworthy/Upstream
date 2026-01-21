# Payrixa Operator Workflows

**For**: Revenue Cycle Directors, Billing Managers, RCM Analysts  
**Purpose**: Step-by-step workflows for daily, weekly, and monthly use of Payrixa

---

## Daily Routine: Morning Check (5 minutes)

### When
Every workday, ideally first thing in the morning or after your coffee.

### Goal
Know if there are any urgent issues that need attention today.

### Steps

1. **Open Payrixa Portal**
   - Navigate to your dashboard (bookmark it)
   - You should land on the Axis hub page or your default product dashboard

2. **Check for High-Severity Alerts**
   - Look at any new signals marked "High" severity
   - These appear with a red badge and urgency label "Investigate Today"
   - If none exist, you're done for the day

3. **Review New DriftWatch Events** (if any High alerts)
   - Open DriftWatch dashboard
   - Check the "Recent Drift Events" table
   - Focus on: Delta > 10 points OR Severity > 0.7

4. **Quick Decision**
   - **If urgent**: Note the payer and signal for investigation later today
   - **If nothing urgent**: Close and proceed with your day
   - **If unsure**: Flag for your weekly review

### Time Check
If this takes more than 5 minutes, you're digging too deep for a daily check. Save deeper investigation for weekly review.

---

## Weekly Review: Monday Morning (20 minutes)

### When
Every Monday morning, after your daily check. Block 20-30 minutes on your calendar.

### Goal
Review all signals from the past week, investigate medium-priority items, identify patterns.

### Steps

#### Part 1: Dashboard Review (5 min)
1. **Open DriftWatch Dashboard**
   - Note the "Total Drift Events" count
   - Review "Top Payers by Drift Frequency" table
   - Any payer with 3+ events this week deserves attention

2. **Open DenialScope Dashboard**
   - Note "Total Denials" count vs last week (trend up or down?)
   - Check "Top Payer" and "Top Denial Reason"
   - Any new denial reasons appearing?

#### Part 2: Medium-Priority Investigation (10 min)
1. **List all medium-severity signals** from the past week
   - These are signals with severity 0.4-0.7 or delta 5-10 points
   
2. **For each medium signal, ask**:
   - Is this a payer we've seen before? (recurring)
   - Is the delta getting larger over time? (trending)
   - Does this match something we already know about?
   
3. **Triage**:
   - **Known issue**: Note it, no action
   - **New pattern**: Schedule deeper investigation
   - **Getting worse**: Escalate to high priority

#### Part 3: Pattern Recognition (5 min)
1. **Look for themes**:
   - Same payer showing up in multiple signals?
   - Same denial reason across multiple payers?
   - Same CPT group consistently flagged?

2. **Document patterns**:
   - Note any recurring patterns in your weekly meeting notes
   - These become talking points for monthly review

### Output
At the end of weekly review, you should have:
- List of issues to investigate this week (0-3 items typically)
- Notes on any emerging patterns
- Decision on which low-priority signals to watch vs ignore

---

## Monthly Sanity Check (30 minutes)

### When
First Monday of each month, or during your monthly billing operations review.

### Goal
Validate that Payrixa is catching real issues, calibrate your expectations, identify systemic patterns.

### Steps

#### Part 1: Look Back at Alerts (10 min)
1. **Pull up last month's alerts** (from email archive or portal history)
2. **For each alert, answer**:
   - Did we investigate this?
   - Was it a real issue or false positive?
   - What action did we take?
   - What was the outcome?

3. **Tally**:
   - How many alerts total?
   - How many were actionable?
   - How many were noise?

#### Part 2: ROI Check (10 min)
1. **Identify wins**:
   - Any issues caught early that saved money?
   - Any payer behavior changes caught before they escalated?
   - Any successful appeals based on early detection?

2. **Estimate value**:
   - If you caught a 10% denial rate increase on $100K weekly volume, that's $10K/week in at-risk revenue
   - Early detection means faster resolution means less compounding loss

3. **Note for leadership**:
   - Document specific examples for your monthly or quarterly reporting

#### Part 3: Calibration (10 min)
1. **Adjust expectations**:
   - Are you getting too many alerts? Consider raising thresholds
   - Are you missing things? Consider lowering thresholds
   - Is a specific payer always noisy? Consider adding to "known variance" list

2. **Review patterns**:
   - Any systemic issues that need operational changes?
   - Any payer relationships that need contract discussion?
   - Any coding patterns that need staff training?

3. **Update your team**:
   - Share insights in your monthly billing meeting
   - Update onboarding docs if needed
   - Refine your response playbooks

### Output
At the end of monthly review, you should have:
- Clear ROI story (or honest "nothing actionable yet")
- List of calibration adjustments to make
- 1-2 systemic insights for leadership

---

## Alert Response Workflow

### High Severity Alert ("Investigate Today")

**Timeline**: Respond same day, ideally within 4 hours of receiving alert.

**Steps**:
1. **Read the alert email** completely
   - Note: payer, signal type, delta, evidence rows
   - Read the "What This Means" and "Recommended Action" sections

2. **Pull sample claims** (15 min)
   - From the evidence table, pick 5-10 claims
   - Pull them in your PM/EHR system
   - Review: denial reason, date, service type

3. **Check for known causes** (10 min)
   - Any recent contract changes with this payer?
   - Any recent payer policy bulletins?
   - Any recent coding or billing changes on your end?

4. **Brief your team** (5 min)
   - Send quick Slack/email to billing lead
   - "Heads up: [Payer] denial rate spiked. Watch for [specific issue]. Investigating."

5. **Document and escalate if needed** (5 min)
   - Note findings in your tracking system
   - If no clear cause found, schedule follow-up
   - If clear cause found, initiate resolution (appeal, payer call, etc.)

**Total time**: 30-40 minutes

---

### Medium Severity Alert ("Review This Week")

**Timeline**: Respond within 3 business days.

**Steps**:
1. **Read the alert** during your weekly review (not immediately)

2. **Compare to history**:
   - Have we seen this payer/signal before?
   - Is this getting better or worse?

3. **Quick investigation** (15 min):
   - Pull 3-5 sample claims
   - Look for obvious patterns
   - Check if it matches a known issue

4. **Decide**:
   - **Actionable**: Schedule investigation or escalate
   - **Known issue**: Note and monitor
   - **Noise**: Mark as reviewed, watch for recurrence

**Total time**: 20-30 minutes

---

### Low Severity Alert ("Monitor for Trend")

**Timeline**: Review during weekly check, no immediate action.

**Steps**:
1. **Acknowledge** during weekly review
2. **Note the signal** (payer, type, delta)
3. **Watch for recurrence**:
   - If same signal appears 2-3 weeks in a row, escalate to medium
   - If it doesn't recur, ignore

**Total time**: 2-3 minutes

---

## Workflow Cheat Sheet

### Daily (5 min)
```
☐ Open portal
☐ Check for High severity alerts
☐ Note any urgent items
☐ Close
```

### Weekly (20 min)
```
☐ Review DriftWatch totals
☐ Review DenialScope totals
☐ Investigate medium-priority signals
☐ Look for patterns
☐ Document findings
```

### Monthly (30 min)
```
☐ Review last month's alerts
☐ Calculate ROI / wins
☐ Calibrate thresholds if needed
☐ Identify systemic patterns
☐ Share insights with team
```

### Alert Response
```
High:    Respond same day (30-40 min)
Medium:  Respond within 3 days (20-30 min)
Low:     Note and watch (2-3 min)
```

---

## Integration with Your Existing Processes

### Billing Team Huddle
- Share any High alerts from the morning check
- Assign investigation ownership
- Brief on emerging patterns

### Weekly Billing Meeting
- Review week's signals as an agenda item
- Discuss patterns and trends
- Assign follow-ups

### Monthly Operations Review
- Include Payrixa ROI summary
- Present systemic patterns
- Propose operational changes

### Payer Contract Discussions
- Use historical drift data as evidence
- Show patterns over time
- Document behavior changes for negotiation leverage

### Staff Training
- If certain denial reasons keep appearing, train staff
- If certain CPT groups are problematic, review coding practices

---

## Troubleshooting

### "I'm getting too many alerts"
- Raise your alert thresholds (contact admin or adjust AlertRule settings)
- Focus only on High severity until alert volume is manageable
- Consider which payers are "known noisy" and adjust expectations

### "I'm not getting any alerts"
- Check that alert rules are enabled
- Verify email delivery (check spam)
- Ensure data is being ingested regularly
- Consider lowering thresholds if everything seems normal

### "I investigated but found nothing"
- This is normal occasionally—false positives happen
- Note it as "no action needed" and move on
- If it happens frequently, recalibrate thresholds

### "I don't have time for weekly review"
- Compress to 10 minutes focusing only on High + new patterns
- Delegate medium investigation to a team member
- Consider bi-weekly instead of weekly

---

## Success Metrics

### After 1 Month
- [ ] Daily check takes < 5 minutes
- [ ] You've investigated at least one alert end-to-end
- [ ] You understand the difference between High/Medium/Low

### After 3 Months
- [ ] Weekly review is a habit
- [ ] You've caught at least one issue before it escalated
- [ ] You have a documented pattern or two

### After 6 Months
- [ ] Payrixa is part of your operational rhythm
- [ ] You can articulate ROI to leadership
- [ ] You're calibrating thresholds based on experience
- [ ] Your team knows how to respond to alerts

---

**Related Documentation**:
- `OPERATOR_GUIDE.md` - Mental model and decision frameworks
- `DEMO_STORY.md` - Example walkthrough
- `README.md` - Technical overview
