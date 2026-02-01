# Upstream Product Milestones

Ralph-powered autonomous execution of the complete Upstream product build (Months 2-7).

## Milestones Overview

| # | Milestone | Scope | Stories | Est. Duration |
|---|-----------|-------|---------|---------------|
| 1 | Core Scoring Engine | ClaimScore integration, three-tier routing, pre-submission API | 18 | 2 weeks |
| 2 | Specialty Modules | Dialysis MA, ABA units, PT/OT 8-min rule, Imaging PA, Home Health PDGM | 23 | 2-3 weeks |
| 3 | Frontend MVP | React scaffold, dashboards, work queues, alerts UI | 18 | 2 weeks |
| 4 | EHR Integrations | Epic FHIR polling, Cerner, athenahealth connectors | 13 | 1-2 weeks |
| 5 | Launch Prep | Stripe billing, signup flow, HIPAA docs, marketing site | 18 | 2 weeks |

**Total: ~90 stories, 9-12 weeks of autonomous execution**

## Quick Start

```bash
# Check status of all milestones
./scripts/ralph/milestone-runner.sh --status

# Run Milestone 1 (Core Scoring Engine)
./scripts/ralph/milestone-runner.sh 1

# Run with custom iteration limit
./scripts/ralph/milestone-runner.sh 2 100

# Validate PRD without running
./scripts/ralph/milestone-runner.sh --dry-run 3
```

## Execution Order

Milestones must be executed in order due to dependencies:

```
Milestone 1 (Core Scoring)
    ↓
Milestone 2 (Specialty Modules) - depends on scoring infrastructure
    ↓
Milestone 3 (Frontend MVP) - depends on API endpoints
    ↓
Milestone 4 (EHR Integrations) - depends on claim processing
    ↓
Milestone 5 (Launch Prep) - depends on all features
```

## Monitoring Progress

```bash
# Overall status
./scripts/ralph/milestone-runner.sh --status

# Detailed story status for milestone
cat milestones/milestone-01-core-scoring-engine.json | jq '.userStories[] | {id, title, passes}'

# Count remaining stories
cat prd.json | jq '[.userStories[] | select(.passes == false)] | length'

# View progress log
tail -50 progress.txt

# Recent git commits
git log --oneline -20
```

## Resuming After Failure

Ralph is stateless - just run again:

```bash
# Ralph reads prd.json and finds first story with passes: false
./scripts/ralph/milestone-runner.sh 1
```

Check `progress.txt` for context on what failed in previous iterations.

## Quality Gates

Each milestone has specific quality gates that must pass:

| Milestone | Primary Gates |
|-----------|---------------|
| 1 Core Scoring | `pytest upstream/automation/ -v`, `python manage.py spectacular --validate` |
| 2 Specialty | `pytest upstream/products/ -v`, coverage > 70% |
| 3 Frontend | `npm run lint && npm run test`, `npm run build` |
| 4 EHR | `pytest upstream/integrations/ -v`, mock FHIR tests |
| 5 Launch | `pytest upstream/billing/ -v`, E2E signup tests |

## File Structure

```
milestones/
├── README.md                               # This file
├── milestone-01-core-scoring-engine.json   # Milestone 1 PRD
├── milestone-02-specialty-modules.json     # Milestone 2 PRD
├── milestone-03-frontend-mvp.json          # Milestone 3 PRD
├── milestone-04-ehr-integrations.json      # Milestone 4 PRD
├── milestone-05-launch-prep.json           # Milestone 5 PRD
└── progress/
    ├── milestone-01-progress.txt           # Progress log for M1
    ├── milestone-02-progress.txt           # Progress log for M2
    └── ...
```

## PRD Format

Each PRD follows the Ralph JSON format:

```json
{
  "branchName": "milestone-01-core-scoring-engine",
  "context": {
    "milestone": "01",
    "milestoneName": "Core Scoring Engine",
    "milestoneGoal": "...",
    "dependsOn": [...],
    "successCriteria": [...],
    "qualityGates": [...]
  },
  "userStories": [
    {
      "id": 1,
      "title": "...",
      "description": "...",
      "acceptanceCriteria": [...],
      "files": [...],
      "passes": false
    }
  ]
}
```

## Success Criteria

A milestone is complete when:
1. All stories have `"passes": true`
2. All quality gates pass
3. Git branch has clean commits
4. Progress log documents learnings

## After All Milestones Complete

1. Merge milestone branches to main
2. Run full test suite: `python manage.py test upstream -v 2`
3. Update documentation
4. Deploy to staging for validation
