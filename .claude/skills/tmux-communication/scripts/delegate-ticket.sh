#!/bin/bash
# @file_purpose One-shot ticket delegation to an agent: sync the agent's fixed
#               named branch to latest master, reset its session, send the
#               standard "implement this ticket" message, and verify it landed.
# Usage: delegate-ticket.sh <recipient-session> <ticket-number> [model] [extra-instructions...]
#   recipient-session  tmux session / agent to delegate to (Coder_Bob, Coder_John, Student, Architect)
#   ticket-number      ticket id, e.g. 2003 (file tickets/open/<N>_ticket.md must exist)
#   model              optional model id (e.g. claude-sonnet-4-6); empty preserves current
#   extra-instructions optional extra sentence appended to the standard message
#
# Each agent works in its OWN fixed worktree on its OWN permanent branch
# (Coder_Bob->coder_bob, Coder_John->coder_john, Student->student, Architect->architect
# on the main tree). We do NOT create per-ticket `ticket/<N>` branches. This
# script fast-forwards the agent's named branch to origin/master before
# delegating (so they start each ticket from a clean, current base), then tells
# the agent to implement in their worktree, commit to their branch, and push it.
# Integrate later with: integrate-ticket.sh <agent> [--push].
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)"
[ -n "$REPO" ] || REPO="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

if [ "$#" -lt 2 ]; then
    echo "Usage: $0 <recipient-session> <ticket-number> [model] [extra-instructions...]" >&2
    exit 2
fi

recipient="$1"; ticket="$2"; model="${3:-}"
shift 2; [ "$#" -gt 0 ] && shift || true   # drop model arg if present
extra="$*"

ticket_rel="tickets/open/${ticket}_ticket.md"
if [ ! -f "$REPO/$ticket_rel" ]; then
    echo "Error: ticket file '$ticket_rel' not found under $REPO." >&2
    echo "Open tickets:" >&2
    ls "$REPO"/tickets/open/*_ticket.md 2>/dev/null | sed 's#.*/#  - #' >&2 || true
    exit 1
fi

if ! tmux has-session -t "=$recipient" 2>/dev/null; then
    echo "Error: no tmux session named '$recipient'. Running agents:" >&2
    tmux list-sessions -F '  - #S' >&2
    exit 1
fi

# Map recipient -> (fixed worktree path, permanent named branch).
wt_parent="$(dirname "$REPO")/$(basename "$REPO")-worktrees"
case "$recipient" in
    Architect)  wt_path="$REPO";                 branch="architect"  ;;
    Coder_Bob)  wt_path="$wt_parent/Coder_Bob";   branch="coder_bob"  ;;
    Coder_John) wt_path="$wt_parent/Coder_John";  branch="coder_john" ;;
    Student)    wt_path="$wt_parent/Student";     branch="student"    ;;
    *)
        echo "Error: unknown recipient '$recipient' (expected Coder_Bob, Coder_John, Student, or Architect)." >&2
        exit 1
        ;;
esac

# 0. Rate-limit guard: the 5h limit is ACCOUNT-WIDE (shared by all agents), so
# gate on the account usage — not this one target's (possibly stale) bar.
if "$SCRIPT_DIR/check-ratelimit.sh" 95; then
    :  # below threshold (or unknown-but-allowed): proceed
else
    rc=$?
    if [ "$rc" -eq 3 ]; then
        echo "Refusing to delegate: the account 5h limit is (near) maxed (see reset time above)." >&2
        echo "It's shared across all agents — wait for the reset, then delegate again." >&2
        exit 3
    fi
    # rc=2 (no fresh data) is non-fatal — proceed but the warning was printed.
fi

# 0b. Sync the agent's named branch to latest master so they start clean.
# Architect's tree is the orchestrator's own working tree — never auto-sync it
# from under a running session; only the agent worktrees are reset here.
if [ "$recipient" != "Architect" ]; then
    if [ ! -d "$wt_path" ]; then
        echo "Error: worktree '$wt_path' for '$recipient' does not exist. Launch team/${recipient}.sh first." >&2
        exit 1
    fi
    echo "Syncing $recipient's branch '$branch' to origin/master in $wt_path ..."
    git -C "$wt_path" fetch origin
    if ! git -C "$wt_path" diff --quiet || ! git -C "$wt_path" diff --cached --quiet; then
        echo "Warning: $wt_path has uncommitted changes — leaving branch '$branch' as-is (not syncing)." >&2
    else
        git -C "$wt_path" checkout "$branch" 2>/dev/null || git -C "$wt_path" checkout -B "$branch" origin/master
        # After integrate-ticket.sh's back-merge re-sync, '$branch' CONTAINS
        # origin/master (plus a merge commit) rather than equalling it — in
        # that case `merge --ff-only origin/master` has nothing to do and
        # fails with "not possible to fast-forward" even though the branch is
        # perfectly up to date. Treat "already an ancestor" as success first.
        if git -C "$wt_path" merge-base --is-ancestor origin/master HEAD 2>/dev/null; then
            echo "Branch '$branch' already contains origin/master (up to date)."
        elif git -C "$wt_path" merge --ff-only origin/master; then
            echo "Branch '$branch' fast-forwarded to origin/master."
        else
            echo "Warning: '$branch' could not fast-forward to origin/master (diverged?) — sync it manually." >&2
        fi
    fi
fi

# 1. Reset the recipient (clear context; set model if given, else preserve current).
"$SCRIPT_DIR/reset-session.sh" "$recipient" "" "$model" ""

# 2. Post-reset settle pause (the reset's trailing command needs to clear).
sleep 4

# 3. Standard delegation message (+ any extra instruction).
msg="Please implement ticket ${ticket_rel}. You are in your own worktree on branch '${branch}'. Do ALL edits, tests and git commits HERE on '${branch}', never in another agent's worktree or the main tree. Read the ticket in full, follow its acceptance criteria, fill in the result file, close the ticket, then git add+commit your code and push your branch (git push origin '${branch}'). Do NOT merge into master — I (Architect) will review and merge."
[ -n "$extra" ] && msg="$msg $extra"
msg="$msg Ask me over tmux if anything is unclear."

send() { "$SCRIPT_DIR/send-to-agent.sh" "$recipient" "$msg"; }
send

# 4. Verify by transcript (the status bar % lags; check the text actually appears).
sleep 9
confirm() { tmux capture-pane -p -t "$recipient" | grep -q "${ticket}_ticket.md"; }
report_ok() {
    echo "Delegated ticket $ticket to $recipient on branch '$branch' ($1)."
    echo "Integrate when done with: $SCRIPT_DIR/integrate-ticket.sh $recipient --push"
}
if confirm; then
    report_ok "confirmed in pane"
    exit 0
fi

echo "Warning: ticket $ticket not visible in $recipient's pane yet — re-sending once." >&2
send
sleep 9
if confirm; then
    report_ok "confirmed after re-send"
else
    echo "Warning: still not confirmed in $recipient's pane. Check it manually:" >&2
    echo "  tmux capture-pane -p -t $recipient | tail -30" >&2
    exit 1
fi
