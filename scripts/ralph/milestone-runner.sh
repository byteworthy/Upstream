#!/bin/bash
# Milestone Runner - Orchestrate Ralph execution across product milestones
# Usage: ./milestone-runner.sh [options] <milestone-number>
#
# Options:
#   --status      Show completion status for all milestones
#   --dry-run     Validate PRD without executing
#   --resume      Resume from last incomplete story (default behavior)
#   <milestone>   1-5 (which milestone to run)
#   <iterations>  Max iterations (default: 50)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MILESTONES_DIR="$PROJECT_ROOT/milestones"
PROGRESS_DIR="$MILESTONES_DIR/progress"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

usage() {
    echo "Usage: $0 [options] <milestone-number> [max-iterations]"
    echo ""
    echo "Options:"
    echo "  --status      Show completion status for all milestones"
    echo "  --dry-run     Validate PRD without executing"
    echo "  --help        Show this help message"
    echo ""
    echo "Arguments:"
    echo "  milestone     1-5 (Core Scoring, Specialty, Frontend, EHR, Launch)"
    echo "  iterations    Max iterations per session (default: 50)"
    echo ""
    echo "Examples:"
    echo "  $0 --status                    # Check all milestone progress"
    echo "  $0 1                           # Run Milestone 1 with 50 iterations"
    echo "  $0 2 100                       # Run Milestone 2 with 100 iterations"
    echo ""
}

check_status() {
    echo -e "${BLUE}=== Milestone Completion Status ===${NC}"
    echo ""

    for prd in "$MILESTONES_DIR"/milestone-*.json; do
        if [ ! -f "$prd" ]; then
            echo -e "${YELLOW}No milestone PRDs found in $MILESTONES_DIR${NC}"
            return
        fi

        NAME=$(basename "$prd" .json)
        TOTAL=$(jq '.userStories | length' "$prd" 2>/dev/null || echo 0)
        COMPLETE=$(jq '[.userStories[] | select(.passes == true)] | length' "$prd" 2>/dev/null || echo 0)

        if [ "$TOTAL" -eq 0 ]; then
            PERCENT=0
        else
            PERCENT=$((COMPLETE * 100 / TOTAL))
        fi

        # Color based on completion
        if [ "$PERCENT" -eq 100 ]; then
            COLOR=$GREEN
            STATUS="COMPLETE"
        elif [ "$PERCENT" -gt 0 ]; then
            COLOR=$YELLOW
            STATUS="IN PROGRESS"
        else
            COLOR=$RED
            STATUS="NOT STARTED"
        fi

        printf "${COLOR}%-40s %3d/%3d (%3d%%) - %s${NC}\n" "$NAME" "$COMPLETE" "$TOTAL" "$PERCENT" "$STATUS"
    done
    echo ""
}

validate_prd() {
    local prd_file=$1
    echo -e "${BLUE}Validating PRD: $prd_file${NC}"

    # Check JSON validity
    if ! jq . "$prd_file" > /dev/null 2>&1; then
        echo -e "${RED}ERROR: Invalid JSON in $prd_file${NC}"
        return 1
    fi

    # Check required fields
    if ! jq -e '.branchName' "$prd_file" > /dev/null 2>&1; then
        echo -e "${RED}ERROR: Missing branchName${NC}"
        return 1
    fi

    if ! jq -e '.userStories | length > 0' "$prd_file" > /dev/null 2>&1; then
        echo -e "${RED}ERROR: No user stories defined${NC}"
        return 1
    fi

    # Check each story has required fields
    STORY_COUNT=$(jq '.userStories | length' "$prd_file")
    for i in $(seq 0 $((STORY_COUNT - 1))); do
        if ! jq -e ".userStories[$i].id" "$prd_file" > /dev/null 2>&1; then
            echo -e "${RED}ERROR: Story $i missing id${NC}"
            return 1
        fi
        if ! jq -e ".userStories[$i].title" "$prd_file" > /dev/null 2>&1; then
            echo -e "${RED}ERROR: Story $i missing title${NC}"
            return 1
        fi
    done

    echo -e "${GREEN}PRD validation passed${NC}"
    echo "  Branch: $(jq -r '.branchName' "$prd_file")"
    echo "  Stories: $STORY_COUNT"
    echo "  Remaining: $(jq '[.userStories[] | select(.passes == false)] | length' "$prd_file")"
    return 0
}

run_milestone() {
    local MILESTONE=$1
    local MAX_ITERATIONS=${2:-50}

    # Find PRD file for this milestone
    local PRD_PATTERN="$MILESTONES_DIR/milestone-0${MILESTONE}-*.json"
    local PRD_FILE=$(ls $PRD_PATTERN 2>/dev/null | head -1)

    if [ -z "$PRD_FILE" ] || [ ! -f "$PRD_FILE" ]; then
        echo -e "${RED}ERROR: No PRD found for milestone $MILESTONE${NC}"
        echo "Expected pattern: $PRD_PATTERN"
        exit 1
    fi

    echo -e "${BLUE}=== Running Milestone $MILESTONE ===${NC}"
    echo "PRD: $PRD_FILE"
    echo "Max Iterations: $MAX_ITERATIONS"
    echo ""

    # Validate PRD first
    if ! validate_prd "$PRD_FILE"; then
        exit 1
    fi

    # Create progress directory if needed
    mkdir -p "$PROGRESS_DIR"

    # Initialize progress file if needed
    local PROGRESS_FILE="$PROGRESS_DIR/milestone-0${MILESTONE}-progress.txt"
    if [ ! -f "$PROGRESS_FILE" ]; then
        echo "# Milestone $MILESTONE Progress Log" > "$PROGRESS_FILE"
        echo "Started: $(date)" >> "$PROGRESS_FILE"
        echo "PRD: $(basename "$PRD_FILE")" >> "$PROGRESS_FILE"
        echo "---" >> "$PROGRESS_FILE"
    fi

    # Symlink PRD and progress to project root for Ralph
    ln -sf "$PRD_FILE" "$PROJECT_ROOT/prd.json"
    ln -sf "$PROGRESS_FILE" "$PROJECT_ROOT/progress.txt"

    echo -e "${GREEN}Symlinks created:${NC}"
    echo "  prd.json -> $PRD_FILE"
    echo "  progress.txt -> $PROGRESS_FILE"
    echo ""

    # Check remaining stories
    local REMAINING=$(jq '[.userStories[] | select(.passes == false)] | length' "$PRD_FILE")
    if [ "$REMAINING" -eq 0 ]; then
        echo -e "${GREEN}All stories in Milestone $MILESTONE are complete!${NC}"
        exit 0
    fi

    echo -e "${YELLOW}Stories remaining: $REMAINING${NC}"
    echo ""

    # Run Ralph
    echo -e "${BLUE}Starting Ralph...${NC}"
    "$SCRIPT_DIR/ralph.sh" --tool claude $MAX_ITERATIONS
}

# Parse arguments
DRY_RUN=false
SHOW_STATUS=false
MILESTONE=""
MAX_ITERATIONS=50

while [[ $# -gt 0 ]]; do
    case $1 in
        --status)
            SHOW_STATUS=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            if [[ "$1" =~ ^[1-5]$ ]]; then
                MILESTONE="$1"
            elif [[ "$1" =~ ^[0-9]+$ ]]; then
                MAX_ITERATIONS="$1"
            else
                echo -e "${RED}Unknown argument: $1${NC}"
                usage
                exit 1
            fi
            shift
            ;;
    esac
done

# Execute based on mode
if [ "$SHOW_STATUS" = true ]; then
    check_status
    exit 0
fi

if [ -z "$MILESTONE" ]; then
    echo -e "${RED}ERROR: Milestone number required (1-5)${NC}"
    usage
    exit 1
fi

if [ "$DRY_RUN" = true ]; then
    PRD_PATTERN="$MILESTONES_DIR/milestone-0${MILESTONE}-*.json"
    PRD_FILE=$(ls $PRD_PATTERN 2>/dev/null | head -1)
    if [ -z "$PRD_FILE" ]; then
        echo -e "${RED}ERROR: No PRD found for milestone $MILESTONE${NC}"
        exit 1
    fi
    validate_prd "$PRD_FILE"
    exit $?
fi

run_milestone "$MILESTONE" "$MAX_ITERATIONS"
