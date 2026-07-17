#!/bin/bash
# @file_purpose Print low-noise review payload for an agent's branch (code diff + result file).
set -euo pipefail

# Get the repo root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)"
[ -n "$REPO" ] || REPO="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <agent-or-branch>" >&2
    echo "  agent-or-branch  the agent whose work to review (Coder_Bob, Coder_John, Student, Architect) or a raw branch name" >&2
    exit 2
fi

# Map an agent name to its permanent branch; accept a raw branch name too.
case "$1" in
    Architect|architect) branch="architect" ;;
    Coder_Bob|coder_bob)   branch="coder_bob"  ;;
    Coder_John|coder_john) branch="coder_john" ;;
    Student|student)     branch="student"    ;;
    *)                   branch="$1"         ;;
esac

# Fetch quietly
git -C "$REPO" fetch -q origin 2>/dev/null || true

# Check if the branch exists
if ! git -C "$REPO" show-ref --verify --quiet "refs/heads/$branch" && ! git -C "$REPO" show-ref --verify --quiet "refs/remotes/origin/$branch"; then
    echo "no such branch: $branch" >&2
    exit 1
fi

# Use origin branch if local doesn't exist but remote does
if ! git -C "$REPO" show-ref --verify --quiet "refs/heads/$branch"; then
    branch="origin/$branch"
fi

echo "===== CODE DIFF (excl tickets) ====="
git -C "$REPO" diff master..."$branch" -- . ':(exclude)tickets/'

# Find newly-added result files in tickets/done/
result_files="$(git -C "$REPO" diff --name-only --diff-filter=A master..."$branch" -- 'tickets/done/*_ticket_result.md' || true)"

if [ -n "$result_files" ]; then
    echo ""
    echo "===== RESULT FILE ====="
    for result_file in $result_files; do
        echo "--- $result_file ---"
        git -C "$REPO" show "$branch:$result_file"
    done
fi
