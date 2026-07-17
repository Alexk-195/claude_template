#!/usr/bin/env bash
# @file_purpose Atomically create a new ticket (template) directly on origin/master
#   from an agent worktree, so ticket NUMBERS can never collide and there is no
#   branch merge for ticket drafts.
#
# Why: ticket files are additive markdown. The old flow numbered a ticket against
# a possibly-stale local/branch view and then merged a long-lived branch, which
# produced duplicate numbers (two agents pick the same N) and same-path merge
# conflicts. This claims the number by pushing the template straight to master:
# if someone else pushed first, the push fails non-fast-forward and we re-number
# against the fresh master and retry — so the number is authoritative and unique.
# Pushing ONLY tickets/ to master cannot affect the build.
#
# Usage: ticket-new-on-master.sh
#   Run it from the agent's worktree (on the agent's branch). Prints the claimed
#   number and file paths. Then edit the ticket and publish with
#   ticket-push-to-master.sh.
set -euo pipefail

REPO="$(git rev-parse --show-toplevel)"
cd "$REPO"
branch="$(git rev-parse --abbrev-ref HEAD)"

if [ "$branch" = "master" ]; then
    echo "You are on master (main tree) — just use ticket-system-create-new-ticket.py, commit, and push." >&2
    exit 1
fi

# Safety: reset --hard below would destroy uncommitted work.
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "Error: worktree has uncommitted changes — commit or stash them first (this flow resets to origin/master)." >&2
    exit 1
fi

CREATE="$REPO/.claude/skills/ticket-system/scripts/ticket-system-create-new-ticket.py"
attempts=5
for i in $(seq 1 "$attempts"); do
    git fetch -q origin
    git reset --hard origin/master >/dev/null

    out="$(python3 "$CREATE")"
    num="$(printf '%s\n' "$out" | sed -n 's/^Next available ticket number: //p')"
    if [ -z "$num" ]; then
        echo "Error: create script did not return a number:" >&2
        printf '%s\n' "$out" >&2
        exit 1
    fi

    git add "tickets/open/${num}_ticket.md" "tickets/open/${num}_ticket_result.md"
    git commit -q -m "tickets: create ticket ${num} (draft template)"

    if git push -q origin "HEAD:master" 2>/dev/null; then
        git fetch -q origin
        git push -q origin "HEAD:${branch}" 2>/dev/null || true   # keep branch ref in step (best-effort)
        echo "Claimed ticket ${num} on master (unique, no branch merge)."
        echo "  tickets/open/${num}_ticket.md"
        echo "  tickets/open/${num}_ticket_result.md"
        echo "Edit the ticket, then run: ticket-push-to-master.sh"
        exit 0
    fi
    echo "master advanced (another ticket landed first) — re-numbering, attempt ${i}/${attempts}..." >&2
done

echo "Error: could not claim a ticket on master after ${attempts} attempts (master moving too fast?)." >&2
exit 1
