#!/bin/bash
# Ralph Wave Runner - 4 parallel tracks with dependency waves
# Usage: ./ralph-waves.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_DIR="$PROJECT_ROOT/.ralph-logs"
LOCK_DIR="$PROJECT_ROOT/.ralph-locks"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

mkdir -p "$LOG_DIR" "$LOCK_DIR"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     Ralph Wave Runner - 4 Parallel Tracks                      ║${NC}"
echo -e "${BLUE}╠════════════════════════════════════════════════════════════════╣${NC}"
echo -e "${BLUE}║${NC} Track A: Behavioral Prediction (2→3→14,17)                     ${BLUE}║${NC}"
echo -e "${BLUE}║${NC} Track B: DenialScope Dollar Spike (4→5→6)                      ${BLUE}║${NC}"
echo -e "${BLUE}║${NC} Track C: Network Intelligence (7→8→9,15,16)                    ${BLUE}║${NC}"
echo -e "${BLUE}║${NC} Track D: HomeHealth Models (10,11→12→13)                       ${BLUE}║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Function to run agent on specific stories
run_agent() {
    local TRACK=$1
    local STORIES=$2
    local LOG_FILE="$LOG_DIR/track-${TRACK}.log"

    echo -e "${CYAN}[Track $TRACK]${NC} Starting stories: $STORIES"

    cd "$PROJECT_ROOT"
    claude --dangerously-skip-permissions --print -p "$(cat <<EOF
You are Ralph Track $TRACK agent implementing PRD gap features.

## YOUR ASSIGNED STORIES
You are responsible for stories: $STORIES (in order)

## Workflow for EACH story:

1. Read prd.json - check if story is already passes: true, skip if so
2. Implement the story:
   - Story 2: Create upstream/services/behavioral_prediction.py with compute_behavioral_prediction()
   - Story 3: Create upstream/tests/test_behavioral_prediction.py
   - Story 4: Add DENIAL_DOLLARS_SPIKE_THRESHOLD=50000 to upstream/constants.py
   - Story 5: Update upstream/products/denialscope/services.py with dollar spike detection
   - Story 6: Add dollar spike tests to upstream/products/denialscope/tests.py
   - Story 7: Add NetworkAlert model to upstream/models.py
   - Story 8: Create upstream/services/network_intelligence.py
   - Story 9: Create upstream/tests/test_network_intelligence.py
   - Story 10: Create upstream/products/homehealth/models.py with HomeHealthPDGMGroup
   - Story 11: Add HomeHealthEpisode model
   - Story 12: Update upstream/products/homehealth/services.py
   - Story 13: Add HomeHealth model tests
   - Story 14: Add run_daily_behavioral_prediction to upstream/tasks.py
   - Story 15: Add run_network_intelligence to upstream/tasks.py
   - Story 16: Add NetworkAlertViewSet to upstream/api/views.py
   - Story 17: Update DashboardView with behavioral prediction counts

3. Run tests: pytest upstream/ -v --tb=short -x
4. Git commit: git add -A && git commit -m "feat(track-$TRACK): implement story #X"
5. Git push: git push origin HEAD
6. Update prd.json: mark story passes: true
7. Move to next story in your list

## Git Conflict Resolution
If push fails: git pull --rebase origin main && git push origin HEAD

## Key Patterns
- Follow upstream/services/payer_drift.py for detection logic
- Use DriftEvent for behavioral prediction (drift_type='BEHAVIORAL_PREDICTION')
- Use DenialSignal for denialscope signals
- NetworkAlert is platform-level (no customer FK)

## Completion
When ALL your stories ($STORIES) are passes: true, output:
<promise>COMPLETE</promise>

Start now with your first story.
EOF
)" > "$LOG_FILE" 2>&1 &

    echo $!
}

# Wave 1: Independent stories (no dependencies)
echo -e "\n${MAGENTA}═══ WAVE 1: Independent Stories (4 parallel) ═══${NC}"
echo -e "Track A: Story 2 (Behavioral prediction engine)"
echo -e "Track B: Story 4 (Dollar spike constant)"
echo -e "Track C: Story 7 (NetworkAlert model)"
echo -e "Track D: Stories 10,11 (HomeHealth models)"
echo ""

PID_A=$(run_agent "A" "2")
sleep 3
PID_B=$(run_agent "B" "4")
sleep 3
PID_C=$(run_agent "C" "7")
sleep 3
PID_D=$(run_agent "D" "10,11")

echo ""
echo -e "${GREEN}Wave 1 launched:${NC}"
echo -e "  Track A (PID $PID_A): Story 2"
echo -e "  Track B (PID $PID_B): Story 4"
echo -e "  Track C (PID $PID_C): Story 7"
echo -e "  Track D (PID $PID_D): Stories 10,11"
echo ""
echo -e "${YELLOW}Waiting for Wave 1 to complete...${NC}"
echo "  Monitor: tail -f $LOG_DIR/track-*.log"
echo "  Status:  cat prd.json | jq '[.userStories[] | select(.passes==true)] | length'"

# Wait for Wave 1
wait $PID_A $PID_B $PID_C $PID_D 2>/dev/null || true

# Check Wave 1 completion
WAVE1_DONE=$(jq '[.userStories[] | select(.id == 2 or .id == 4 or .id == 7 or .id == 10 or .id == 11) | select(.passes == true)] | length' "$PROJECT_ROOT/prd.json")
echo -e "\n${GREEN}Wave 1 complete: $WAVE1_DONE/5 stories${NC}"

# Wave 2: Dependent on Wave 1
echo -e "\n${MAGENTA}═══ WAVE 2: Dependent Stories ═══${NC}"

PID_A=$(run_agent "A" "3")
sleep 3
PID_B=$(run_agent "B" "5")
sleep 3
PID_C=$(run_agent "C" "8")
sleep 3
PID_D=$(run_agent "D" "12")

echo -e "${GREEN}Wave 2 launched${NC}"
wait $PID_A $PID_B $PID_C $PID_D 2>/dev/null || true

# Wave 3
echo -e "\n${MAGENTA}═══ WAVE 3: Tests & Tasks ═══${NC}"

PID_A=$(run_agent "A" "14,17")
sleep 3
PID_B=$(run_agent "B" "6")
sleep 3
PID_C=$(run_agent "C" "9,15,16")
sleep 3
PID_D=$(run_agent "D" "13")

echo -e "${GREEN}Wave 3 launched${NC}"
wait $PID_A $PID_B $PID_C $PID_D 2>/dev/null || true

# Wave 4: Final integration
echo -e "\n${MAGENTA}═══ WAVE 4: Final Integration ═══${NC}"

cd "$PROJECT_ROOT"
claude --dangerously-skip-permissions --print -p "$(cat <<EOF
You are the final integration agent.

Run these commands and fix any issues:
1. python manage.py makemigrations
2. python manage.py migrate
3. python manage.py test upstream -v 2

If tests fail, fix the issues.
Then mark story 18 as passes: true in prd.json.

Output <promise>COMPLETE</promise> when done.
EOF
)" > "$LOG_DIR/track-final.log" 2>&1

# Final status
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
COMPLETED=$(jq '[.userStories[] | select(.passes == true)] | length' "$PROJECT_ROOT/prd.json")
TOTAL=$(jq '.userStories | length' "$PROJECT_ROOT/prd.json")
echo -e "${GREEN}FINAL STATUS: $COMPLETED/$TOTAL stories complete${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
