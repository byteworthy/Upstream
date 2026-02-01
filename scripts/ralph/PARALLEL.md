# Ralph Parallel Execution Strategies

Two approaches for running multiple Ralph agents without duplicate work.

## Strategy 1: Track Assignment (Recommended for Known Workloads)

Use `ralph-parallel.sh` when you know the story dependencies upfront.

```bash
./scripts/ralph/ralph-parallel.sh 20
```

**How it works:**
- Splits stories into 3 non-overlapping tracks
- Each agent only works on its assigned stories
- No lock contention, maximum parallelism

**Current Track Assignment:**
| Agent | Stories | Track |
|-------|---------|-------|
| 1 | 13, 22, 23 | PT/OT tests + Integration |
| 2 | 14, 15, 16, 17 | Imaging (model → service → docs → tests) |
| 3 | 18, 19, 20, 21 | Home Health (constants → service → F2F → tests) |

**To customize tracks**, edit `ralph-parallel.sh`:
```bash
AGENT1_STORIES="13,22,23"
AGENT2_STORIES="14,15,16,17"
AGENT3_STORIES="18,19,20,21"
```

## Strategy 2: Dynamic Claiming (Recommended for Unknown Workloads)

Use `ralph-claim.sh` when agents should dynamically pick up available work.

```bash
# Terminal 1
./scripts/ralph/ralph-claim.sh alpha 20

# Terminal 2
./scripts/ralph/ralph-claim.sh beta 20

# Terminal 3
./scripts/ralph/ralph-claim.sh gamma 20
```

**How it works:**
- Each agent claims ONE story at a time using atomic file locks
- When story completes, agent releases claim and picks next
- Handles failures gracefully - unclaimed stories get picked up

**Lock files:**
```
.ralph-claims/
├── story-13/
│   ├── owner      # "alpha"
│   └── claimed_at # timestamp
├── story-14/
│   └── ...
```

## Choosing a Strategy

| Scenario | Use |
|----------|-----|
| Stories have clear tracks (specialty modules) | Track Assignment |
| Stories are independent (all can run in parallel) | Dynamic Claiming |
| Unknown dependencies | Dynamic Claiming |
| Maximum throughput, known workload | Track Assignment |

## Monitoring Parallel Runs

```bash
# Check story status
cat prd.json | jq '.userStories[] | select(.passes==false) | {id,title}'

# Check active claims
ls -la .ralph-claims/

# Watch logs (track assignment)
tail -f .ralph-logs/agent-*.log

# Check progress
tail -30 progress.txt
```

## Important: Git Conflict Handling

With parallel agents, git conflicts WILL happen. Both scripts instruct agents to:

1. Always commit with `--no-verify` (skip slow hooks)
2. Always push immediately after commit
3. If push fails: `git pull --rebase origin main` then retry push

## Cleanup

```bash
# Remove claim locks
rm -rf .ralph-claims/

# Remove logs
rm -rf .ralph-logs/

# Kill all Ralph agents
pkill -f "claude.*Ralph"
```
