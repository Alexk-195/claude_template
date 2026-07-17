#!/bin/bash
# @file_purpose Print compact status for an agent's branch (branch, ahead count, last commit, diffstat).
set -euo pipefail

# Get the repo root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)"
[ -n "$REPO" ] || REPO="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <agent-or-branch>" >&2
    echo "  agent-or-branch  the agent whose status to show (Coder_Bob, Coder_John, Student, Architect) or a raw branch name" >&2
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

# Print status
echo "branch: $branch"
echo "ahead of master: $(git -C "$REPO" rev-list --count master.."$branch") commit(s)"
echo "last commit: $(git -C "$REPO" log -1 --format='%h %s' "$branch")"
echo "code diff (excl tickets):"
git -C "$REPO" diff --stat master..."$branch" -- . ':(exclude)tickets/'
