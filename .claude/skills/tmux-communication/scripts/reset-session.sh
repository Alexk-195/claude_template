#!/bin/bash
# @file_purpose Reset/clear an agent's tmux session: optional rename, then /new, /model, /effort.
# Usage: reset-session.sh [old_session_name] [new_session_name] [model] [effort]
#   old_session_name  session to operate on; pass "" or omit for the current one
#   new_session_name  rename target; pass "" to keep the current name
#   model             value for /model (e.g. claude-opus-4-8); pass "" to skip
#   effort            value for /effort (e.g. medium); pass "" to skip
# Each operation is followed by a 2s pause so the TUI can process it.
set -euo pipefail

PAUSE=2

old="${1:-}"
new="${2:-}"
model="${3:-}"
effort="${4:-}"

# Default old to the current session when not provided.
if [ -z "$old" ]; then
    if [ -z "${TMUX:-}" ]; then
        echo "Error: no session name given and not inside tmux." >&2
        exit 1
    fi
    old="$(tmux display-message -p '#S')"
fi

# old session must exist.
if ! tmux has-session -t "=$old" 2>/dev/null; then
    echo "Error: no tmux session named '$old'. Running sessions:" >&2
    tmux list-sessions -F '  - #S' >&2
    exit 1
fi

# Issue a slash command into the target session and wait.
issue() {
    local target="$1" cmd="$2"
    tmux send-keys -t "$target" "$cmd"
    sleep 1                      # let the text settle before submitting
    tmux send-keys -t "$target" Enter
    sleep "$PAUSE"
}

target="$old"

# 1. Clear the conversation.
issue "$target" "/new"
echo "Issued /new"

# 2. Rename the Claude session (if a new name was provided and differs).
if [ -n "$new" ] && [ "$new" != "$old" ]; then
    issue "$target" "/rename $new"
    echo "Issued /rename $new"
fi

# 3. Set the model (if provided).
if [ -n "$model" ]; then
    issue "$target" "/model $model"
    echo "Issued /model $model"
fi

# 4. Set the effort (if provided).
if [ -n "$effort" ]; then
    issue "$target" "/effort $effort"
    echo "Issued /effort $effort"
fi

# Note: /rc (remote control) is intentionally NOT issued here — it stays
# connected across resets. Issue it explicitly only if a session needs it.

echo "Done resetting session '$target'."
