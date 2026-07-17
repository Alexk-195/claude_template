#!/bin/bash
# @file_purpose Send a one-line message to another agent's tmux session (the standard "send text to" case).
# Usage: send-to-agent.sh <recipient-session> <message...>
# Handles the existence check, the sender signature, the required 1s pause
# between posting the text and the final Enter, and appends the "[tmux]" suffix
# that tells the recipient to send feedback/questions back over tmux.
set -euo pipefail

if [ "$#" -lt 2 ]; then
    echo "Usage: $0 <recipient-session> <message...>" >&2
    exit 2
fi

recipient="$1"
shift
message="$*"

# Must be inside tmux to have a sender name.
if [ -z "${TMUX:-}" ]; then
    echo "Error: not inside a tmux session — no sender agent name." >&2
    exit 1
fi
sender="$(tmux display-message -p '#S')"

# Don't message yourself.
if [ "$recipient" = "$sender" ]; then
    echo "Error: recipient '$recipient' is the current session (can't message yourself)." >&2
    exit 1
fi

# Recipient session must exist.
if ! tmux has-session -t "=$recipient" 2>/dev/null; then
    echo "Error: no tmux session named '$recipient'. Running agents:" >&2
    tmux list-sessions -F '  - #S' >&2
    exit 1
fi

# Append the sender signature and the [tmux] suffix (signals the recipient to
# reply over tmux, not just print its answer).
text="$message — $sender [tmux]"

# Post the text, wait >=1s so it settles in the input box, then submit.
tmux send-keys -t "$recipient" "$text"
sleep 1
tmux send-keys -t "$recipient" Enter

echo "Sent to $recipient: $text"
