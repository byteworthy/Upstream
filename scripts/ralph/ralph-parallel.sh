#!/bin/bash
# Ralph Parallel Runner - Runs 3 agents on different story tracks
# Usage: ./ralph-parallel.sh [max_iterations]
#
# Each agent works on a specific specialty track to avoid conflicts:
#   Agent 1: PT/OT tests (13) + Integration (22-23)
#   Agent 2: Imaging track (14-17)
#   Agent 3: Home Health track (18-21)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MAX_ITERATIONS=${1:-20}
LOCK_DIR="$PROJECT_ROOT/.ralph-locks"
LOG_DIR="$PROJECT_ROOT/.ralph-logs"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Create directories
mkdir -p "$LOCK_DIR" "$LOG_DIR"

# Define story assignments for each agent
# These MUST NOT overlap
AGENT1_STORIES="22,23"  # Integration track
AGENT2_STORIES="18,19"  # Home Health constants + service
AGENT3_STORIES="20,21"  # Home Health F2F + tests

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     Ralph Parallel Runner - 3 Agent Configuration          ║${NC}"
echo -e "${BLUE}╠════════════════════════════════════════════════════════════╣${NC}"
echo -e "${BLUE}║${NC} Agent 1: Stories $AGENT1_STORIES (PT/OT tests + Integration)     ${BLUE}║${NC}"
echo -e "${BLUE}║${NC} Agent 2: Stories $AGENT2_STORIES (Imaging track)              ${BLUE}║${NC}"
echo -e "${BLUE}║${NC} Agent 3: Stories $AGENT3_STORIES (Home Health track)          ${BLUE}║${NC}"
echo -e "${BLUE}║${NC} Max iterations per agent: $MAX_ITERATIONS                          ${BLUE}║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check remaining stories
REMAINING=$(jq '[.userStories[] | select(.passes == false)] | length' "$PROJECT_ROOT/prd.json")
echo -e "${YELLOW}Stories remaining: $REMAINING${NC}"

if [ "$REMAINING" -eq 0 ]; then
    echo -e "${GREEN}All stories complete! Nothing to do.${NC}"
    exit 0
fi

# Function to run a single agent
run_agent() {
    local AGENT_NUM=$1
    local STORIES=$2
    local LOG_FILE="$LOG_DIR/agent-${AGENT_NUM}.log"
    local LOCK_FILE="$LOCK_DIR/agent-${AGENT_NUM}.lock"

    # Create lock file
    echo "$$" > "$LOCK_FILE"

    echo -e "${CYAN}[Agent $AGENT_NUM]${NC} Starting on stories: $STORIES"
    echo -e "${CYAN}[Agent $AGENT_NUM]${NC} Log: $LOG_FILE"

    # Run Claude with story-specific prompt
    cd "$PROJECT_ROOT"
    RALPH_AGENT_NUM=$AGENT_NUM \
    RALPH_ASSIGNED_STORIES=$STORIES \
    claude --dangerously-skip-permissions --print -p "$(cat <<EOF
You are Ralph Agent $AGENT_NUM, part of a 3-agent parallel team.

## YOUR ASSIGNED STORIES ONLY
You are ONLY responsible for stories: $STORIES
DO NOT work on any other stories - other agents handle those.

## Your Workflow

1. Read prd.json - find YOUR first incomplete story from: $STORIES
2. If all YOUR stories are complete, output: <promise>COMPLETE</promise>
3. Implement the story following Django REST Framework patterns
4. Run quality gates: pytest, python manage.py check
5. Commit with: git add <files> && git commit --no-verify -m "feat: ..."
6. Push to GitHub: git push origin main
7. Update prd.json to mark story passes: true
8. Append learnings to progress.txt with [Agent $AGENT_NUM] prefix
9. Repeat for next story in YOUR list

## Critical Rules
- ONLY work on stories $STORIES
- Always push after commit
- Use [Agent $AGENT_NUM] prefix in progress.txt entries
- If git push fails due to conflicts, pull --rebase first
- Skip stories that are already passes: true

## Quality Gates
\`\`\`bash
pytest upstream/products/ -v --tb=short
python manage.py check
\`\`\`

Start now: Read prd.json and find your first incomplete story.
EOF
)" > "$LOG_FILE" 2>&1 &

    echo $!
}

# Launch all 3 agents in parallel
echo ""
echo -e "${GREEN}Launching agents...${NC}"

PID1=$(run_agent 1 "$AGENT1_STORIES")
sleep 2
PID2=$(run_agent 2 "$AGENT2_STORIES")
sleep 2
PID3=$(run_agent 3 "$AGENT3_STORIES")

echo ""
echo -e "${BLUE}Agents launched:${NC}"
echo -e "  Agent 1 (PID $PID1): Stories $AGENT1_STORIES"
echo -e "  Agent 2 (PID $PID2): Stories $AGENT2_STORIES"
echo -e "  Agent 3 (PID $PID3): Stories $AGENT3_STORIES"
echo ""
echo -e "${YELLOW}Monitoring progress...${NC}"
echo "  Logs: $LOG_DIR/"
echo "  PRD:  cat prd.json | jq '.userStories[] | select(.passes==false) | {id,title}'"
echo ""

# Wait for all agents
wait $PID1 $PID2 $PID3 2>/dev/null || true

# Cleanup
rm -f "$LOCK_DIR"/*.lock

# Final status
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
COMPLETED=$(jq '[.userStories[] | select(.passes == true)] | length' "$PROJECT_ROOT/prd.json")
TOTAL=$(jq '.userStories | length' "$PROJECT_ROOT/prd.json")
echo -e "${GREEN}Final Status: $COMPLETED/$TOTAL stories complete${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
