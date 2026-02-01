#!/bin/bash
# Ralph: Autonomous AI Agent Loop for Upstream Healthcare Platform
# Usage: ./scripts/ralph/ralph.sh [--tool amp|claude] [max_iterations]

set -e

# Configuration
MAX_ITERATIONS=${2:-50}  # Default 50 iterations
TOOL="claude"  # Default to Claude Code
PRD_FILE="prd.json"
PROGRESS_FILE="progress.txt"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --tool)
            TOOL="$2"
            shift 2
            ;;
        *)
            if [[ $1 =~ ^[0-9]+$ ]]; then
                MAX_ITERATIONS=$1
            fi
            shift
            ;;
    esac
done

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Ralph: Upstream Gaps Implementation   ${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "Tool: ${GREEN}$TOOL${NC}"
echo -e "Max Iterations: ${GREEN}$MAX_ITERATIONS${NC}"
echo -e "PRD File: ${GREEN}$PRD_FILE${NC}"
echo ""

# Verify prd.json exists
if [ ! -f "$PRD_FILE" ]; then
    echo -e "${RED}Error: $PRD_FILE not found${NC}"
    echo "Create prd.json with user stories first."
    exit 1
fi

# Initialize progress.txt if not exists
if [ ! -f "$PROGRESS_FILE" ]; then
    echo "# Ralph Progress Log - $(date)" > "$PROGRESS_FILE"
    echo "# Upstream Gaps Implementation" >> "$PROGRESS_FILE"
    echo "" >> "$PROGRESS_FILE"
fi

# Get branch name from prd.json
BRANCH_NAME=$(cat "$PRD_FILE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('branchName', 'ralph/feature'))")

# Create or checkout branch
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" != "$BRANCH_NAME" ]; then
    echo -e "${YELLOW}Switching to branch: $BRANCH_NAME${NC}"
    git checkout -B "$BRANCH_NAME" 2>/dev/null || git checkout "$BRANCH_NAME"
fi

# Function to count incomplete stories
count_incomplete() {
    cat "$PRD_FILE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
incomplete = [s for s in data.get('userStories', []) if not s.get('passes', False)]
print(len(incomplete))
"
}

# Function to get next story
get_next_story() {
    cat "$PRD_FILE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for story in data.get('userStories', []):
    if not story.get('passes', False):
        print(f\"Story {story['id']}: {story['title']}\")
        break
"
}

# Main loop
iteration=1
while [ $iteration -le $MAX_ITERATIONS ]; do
    INCOMPLETE=$(count_incomplete)

    if [ "$INCOMPLETE" -eq 0 ]; then
        echo -e "${GREEN}========================================${NC}"
        echo -e "${GREEN}  ALL STORIES COMPLETE!                 ${NC}"
        echo -e "${GREEN}========================================${NC}"
        echo "<promise>COMPLETE</promise>"
        exit 0
    fi

    NEXT_STORY=$(get_next_story)

    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  Iteration $iteration of $MAX_ITERATIONS${NC}"
    echo -e "${BLUE}  Remaining stories: $INCOMPLETE${NC}"
    echo -e "${BLUE}  $NEXT_STORY${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    # Log iteration start
    echo "--- Iteration $iteration - $(date) ---" >> "$PROGRESS_FILE"
    echo "Working on: $NEXT_STORY" >> "$PROGRESS_FILE"

    # Run the AI tool
    if [ "$TOOL" = "claude" ]; then
        # Claude Code execution
        claude --dangerously-skip-permissions --print "$(cat scripts/ralph/CLAUDE.md)"
        EXIT_CODE=$?
    else
        # Amp execution
        amp --prompt "$(cat scripts/ralph/prompt.md)"
        EXIT_CODE=$?
    fi

    if [ $EXIT_CODE -ne 0 ]; then
        echo -e "${RED}AI tool exited with error code $EXIT_CODE${NC}"
        echo "Error: AI tool failed with code $EXIT_CODE" >> "$PROGRESS_FILE"
    fi

    # Check if story completed
    NEW_INCOMPLETE=$(count_incomplete)
    if [ "$NEW_INCOMPLETE" -lt "$INCOMPLETE" ]; then
        echo -e "${GREEN}Story completed successfully!${NC}"
        echo "Result: Story completed" >> "$PROGRESS_FILE"
    else
        echo -e "${YELLOW}Story not yet complete, will retry${NC}"
        echo "Result: Story not complete, retrying" >> "$PROGRESS_FILE"
    fi

    echo "" >> "$PROGRESS_FILE"

    ((iteration++))

    # Brief pause between iterations
    sleep 2
done

echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}  Max iterations reached ($MAX_ITERATIONS)${NC}"
echo -e "${YELLOW}  $(count_incomplete) stories remaining${NC}"
echo -e "${YELLOW}========================================${NC}"
echo "Max iterations reached" >> "$PROGRESS_FILE"
