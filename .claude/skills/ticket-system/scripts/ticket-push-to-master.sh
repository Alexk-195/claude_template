#!/usr/bin/env bash
# @file_purpose Publish tickets/ changes (filled content, moves to done/, closes)
#   from an agent worktree straight to origin/master, conflict-free.
#
# Ticket files are uniquely named, so merging origin/master into the branch never
# conflicts on them (distinct filenames), and pushing ONLY tickets/ to master
# cannot affect the build. This replaces the old "commit on a long-lived branch,
# let Architect merge it" path for ticket-only work, which caused merge conflicts.
#
# Refuses to push if the commits ahead of master touch anything outside tickets/,
# so it can never sneak code onto master.
#
# Usage: ticket-push-to-master.sh
#   Run from the agent worktree after editing/closing tickets. Auto-stages tickets/
#   changes (including staged ticket moves from the close script), then publishes.
set -euo pipefail

REPO="$(git rev-parse --show-toplevel)"
cd "$REPO"
branch="$(git rev-parse --abbrev-ref HEAD)"

if [ "$branch" = "master" ]; then
    echo "You are on master (main tree) — just commit and push directly." >&2
    exit 1
fi

git add -A tickets/

# Nothing outside tickets/ may be introduced by this commit.
if ! git diff --cached --quiet -- ':(exclude)tickets/'; then
    echo "Error: staged changes outside tickets/ — this path only publishes ticket files." >&2
    echo "Unstage them (git reset) and use the normal agent-branch integration for code." >&2
    exit 1
fi

if git diff --cached --quiet; then
    # Nothing newly staged; maybe there are already-committed ticket changes to push.
    if git diff --quiet origin/master...HEAD 2>/dev/null; then
        echo "No ticket changes to publish."
        exit 0
    fi
else
    git commit -q -m "tickets: update from ${branch}"
fi

attempts=5
for i in $(seq 1 "$attempts"); do
    git fetch -q origin
    if ! git merge -q --no-edit origin/master; then
        echo "Unexpected merge conflict publishing tickets — aborting." >&2
        echo "(Ticket filenames should be unique; a conflict means two tickets share a number.)" >&2
        git merge --abort 2>/dev/null || true
        exit 1
    fi
    # Guard: everything we're about to push to master must be tickets/ only.
    if ! git diff --quiet origin/master...HEAD -- ':(exclude)tickets/'; then
        echo "Error: commits ahead of master touch non-tickets/ files — refusing to push to master." >&2
        echo "Use the normal agent-branch integration (integrate-ticket.sh) for code changes." >&2
        exit 1
    fi
    if git push -q origin "HEAD:master" 2>/dev/null; then
        git fetch -q origin
        git push -q origin "HEAD:${branch}" 2>/dev/null || true   # keep branch ref in step (best-effort)
        echo "Published ticket changes to master."
        exit 0
    fi
    echo "master advanced — merging and retrying, attempt ${i}/${attempts}..." >&2
done

echo "Error: could not publish tickets to master after ${attempts} attempts." >&2
exit 1
