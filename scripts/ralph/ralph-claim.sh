#!/bin/bash
# Ralph with Story Claiming - Multiple agents can run, each claims stories atomically
# Usage: ./ralph-claim.sh [agent_name] [max_iterations]
#
# Each agent claims ONE story at a time using file locks.
# This prevents duplicate work when running multiple agents.

set -e

AGENT_NAME=${1:-"agent-$$"}
MAX_ITERATIONS=${2:-10}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOCK_DIR="$PROJECT_ROOT/.ralph-claims"
PRD_FILE="$PROJECT_ROOT/prd.json"

mkdir -p "$LOCK_DIR"

echo "[$AGENT_NAME] Starting Ralph with story claiming"
echo "[$AGENT_NAME] Lock directory: $LOCK_DIR"

# Function to claim a story (atomic via mkdir)
claim_story() {
    local STORY_ID=$1
    local CLAIM_DIR="$LOCK_DIR/story-$STORY_ID"

    # mkdir is atomic - if it succeeds, we have the claim
    if mkdir "$CLAIM_DIR" 2>/dev/null; then
        echo "$AGENT_NAME" > "$CLAIM_DIR/owner"
        echo "$(date)" > "$CLAIM_DIR/claimed_at"
        return 0
    fi
    return 1
}

# Function to release a story claim
release_story() {
    local STORY_ID=$1
    rm -rf "$LOCK_DIR/story-$STORY_ID"
}

# Function to find and claim next available story
find_and_claim_story() {
    # Get all incomplete story IDs
    local INCOMPLETE=$(jq -r '.userStories[] | select(.passes == false) | .id' "$PRD_FILE")

    for STORY_ID in $INCOMPLETE; do
        if claim_story "$STORY_ID"; then
            echo "$STORY_ID"
            return 0
        fi
    done

    echo ""
    return 1
}

for i in $(seq 1 $MAX_ITERATIONS); do
    echo ""
    echo "[$AGENT_NAME] ════════════════════════════════════════"
    echo "[$AGENT_NAME] Iteration $i of $MAX_ITERATIONS"
    echo "[$AGENT_NAME] ════════════════════════════════════════"

    # Try to claim a story
    CLAIMED_STORY=$(find_and_claim_story)

    if [ -z "$CLAIMED_STORY" ]; then
        # Check if all stories are complete or all claimed by others
        REMAINING=$(jq '[.userStories[] | select(.passes == false)] | length' "$PRD_FILE")
        if [ "$REMAINING" -eq 0 ]; then
            echo "[$AGENT_NAME] All stories complete!"
            exit 0
        else
            echo "[$AGENT_NAME] All remaining stories claimed by other agents. Waiting..."
            sleep 10
            continue
        fi
    fi

    # Get story details
    STORY_TITLE=$(jq -r ".userStories[] | select(.id == $CLAIMED_STORY) | .title" "$PRD_FILE")
    echo "[$AGENT_NAME] Claimed story #$CLAIMED_STORY: $STORY_TITLE"

    # Run Claude to implement this specific story
    cd "$PROJECT_ROOT"
    OUTPUT=$(claude --dangerously-skip-permissions --print -p "$(cat <<EOF
You are Ralph ($AGENT_NAME). Implement ONLY story #$CLAIMED_STORY.

## Your ONE Task
Story #$CLAIMED_STORY: $STORY_TITLE

Read prd.json for full acceptance criteria, then:
1. Implement the story
2. Run: pytest && python manage.py check
3. Commit: git add <files> && git commit --no-verify -m "feat: implement story #$CLAIMED_STORY - $STORY_TITLE"
4. Push: git push origin main (pull --rebase if conflicts)
5. Update prd.json: mark story #$CLAIMED_STORY as passes: true
6. Append to progress.txt with [$AGENT_NAME] prefix

If complete, output: STORY_COMPLETE
If blocked, output: STORY_BLOCKED: <reason>
EOF
)" 2>&1) || true

    echo "$OUTPUT" | tail -20

    # Release the claim
    release_story "$CLAIMED_STORY"

    # Check if story was completed
    STORY_STATUS=$(jq -r ".userStories[] | select(.id == $CLAIMED_STORY) | .passes" "$PRD_FILE")
    if [ "$STORY_STATUS" == "true" ]; then
        echo "[$AGENT_NAME] ✓ Story #$CLAIMED_STORY completed successfully"
    else
        echo "[$AGENT_NAME] ✗ Story #$CLAIMED_STORY not completed, will retry later"
    fi

    sleep 2
done

echo "[$AGENT_NAME] Reached max iterations"
