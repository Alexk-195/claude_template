#!/bin/bash
# @file_purpose Merge an agent's fixed named branch into master, then re-sync
#               that branch back to master so it's clean for the next ticket.
# Usage: integrate-ticket.sh <agent-or-branch> [--push]
#   agent-or-branch  the agent whose work to merge (Coder_Bob, Coder_John,
#                    Student, Architect) or a raw branch name (coder_bob, student, ...)
#   --push           also push master (and the re-synced agent branch) to origin
#
# We do NOT use per-ticket `ticket/<N>` branches — each agent has ONE permanent
# named branch (Coder_Bob->coder_bob, Coder_John->coder_john, Student->student,
# Architect->architect). Review is the orchestrator's job and happens BEFORE
# running this: inspect the branch (git -C <repo> log/diff master..<branch>) and
# the agent's worktree, then run this to merge <branch> into master with --no-ff.
# The named branch is NOT deleted (it's permanent); after a clean merge it is
# fast-forwarded back to master in the agent's worktree so the next ticket starts
# from a current base. Aborts cleanly on merge conflicts or a dirty main tree.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)"
[ -n "$REPO" ] || REPO="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

# Integration branch: honor an explicit override, else prefer master (this
# project), else main, else default to master.
MAIN="${INTEGRATE_MAIN_BRANCH:-}"
if [ -z "$MAIN" ]; then
    if git -C "$REPO" show-ref --verify --quiet refs/heads/master; then
        MAIN=master
    elif git -C "$REPO" show-ref --verify --quiet refs/heads/main; then
        MAIN=main
    else
        MAIN=master
    fi
fi

push=0
args=()
for a in "$@"; do
    case "$a" in
        --push) push=1 ;;
        *) args+=("$a") ;;
    esac
done
set -- "${args[@]}"

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <agent-or-branch> [--push]" >&2
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

if [ "$branch" = "$MAIN" ]; then
    echo "Error: refusing to integrate '$branch' into itself." >&2
    exit 1
fi

# The branch must exist.
if ! git -C "$REPO" show-ref --verify --quiet "refs/heads/$branch"; then
    echo "Error: branch '$branch' not found. Nothing to integrate." >&2
    exit 1
fi

# The integration branch must be checked out and clean in the main tree.
cur="$(git -C "$REPO" symbolic-ref --short HEAD 2>/dev/null || echo DETACHED)"
if [ "$cur" != "$MAIN" ]; then
    echo "Error: $REPO is on '$cur', not '$MAIN'. Switch to $MAIN before integrating." >&2
    exit 1
fi
if ! git -C "$REPO" diff --quiet || ! git -C "$REPO" diff --cached --quiet; then
    echo "Error: $MAIN working tree at $REPO has uncommitted changes. Commit/stash them first." >&2
    exit 1
fi

pre_merge_sha="$(git -C "$REPO" rev-parse HEAD)"

echo "Merging $branch into $MAIN ..."
if ! git -C "$REPO" merge --no-ff "$branch" -m "Merge $branch into $MAIN"; then
    echo "Merge conflict — resolve it in $REPO, commit, then re-run to clean up." >&2
    echo "(Or 'git -C $REPO merge --abort' to back out.)" >&2
    exit 1
fi
echo "Merged $branch into $MAIN."

# Everything below only matters when we're about to push (i.e. actually land on
# origin/master). A no-push dry-run merge stops here, same as before.
if [ "$push" -eq 1 ]; then
    abort_merge() {
        git -C "$REPO" reset --hard "$pre_merge_sha" >/dev/null 2>&1
        echo "Reverted the local merge in $REPO (unpushed, so this is safe) — fix it on '$branch' and re-run integrate-ticket.sh." >&2
    }

    echo "Running test gate (pytest)..."
    if ! ( cd "$REPO" && python -m pytest -q ); then
        echo "Error: 'pytest' failed." >&2
        abort_merge
        exit 1
    fi
    echo "Test gate passed."

    git -C "$REPO" push origin "$MAIN"
    echo "Pushed $MAIN to origin."
fi

# Re-sync the agent's permanent branch with master via a lossless back-merge
# (never discards un-integrated commits, never force-pushes) so its next
# ticket starts from a base that includes master. Done in the branch's own
# worktree if it has one; skipped for the architect branch (the main tree is
# already on master here) and skipped entirely on a no-push dry run, since
# there is no fresh origin/master to sync against yet.
if [ "$push" -eq 1 ]; then
    wt_parent="$(dirname "$REPO")/$(basename "$REPO")-worktrees"
    case "$branch" in
        coder_bob)  wt_path="$wt_parent/Coder_Bob"  ;;
        coder_john) wt_path="$wt_parent/Coder_John" ;;
        student)    wt_path="$wt_parent/Student"    ;;
        *)          wt_path=""                       ;;
    esac
    if [ -n "$wt_path" ] && [ -d "$wt_path" ]; then
        if git -C "$wt_path" diff --quiet && git -C "$wt_path" diff --cached --quiet; then
            git -C "$wt_path" fetch origin
            if git -C "$wt_path" merge origin/master -m "Merge $MAIN into $branch (post-integration re-sync)"; then
                echo "Re-synced branch '$branch' with $MAIN in $wt_path (back-merge)."
                if git -C "$wt_path" push origin "$branch"; then
                    echo "Pushed '$branch' to origin."
                else
                    echo "Error: back-merge succeeded locally but pushing '$branch' failed — push it manually from $wt_path." >&2
                    exit 1
                fi
            else
                git -C "$wt_path" merge --abort 2>/dev/null || true
                echo "Error: back-merging $MAIN into '$branch' conflicted in $wt_path." >&2
                echo "Merge aborted (git merge --abort) — resolve manually: cd $wt_path && git merge origin/master" >&2
                exit 1
            fi
        else
            echo "Note: $wt_path has uncommitted changes — leaving '$branch' as-is." >&2
        fi
    fi
fi

echo "Ticket integration for '$branch' complete."
