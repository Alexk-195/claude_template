# @file_purpose Launch script for the Coder_Bob agent (Claude Sonnet via Anthropic, medium effort) in its tmux session.

# Setup coder_bob branch and worktree
WORKTREE_PATH="../auto_placer-worktrees/Coder_Bob"

# Ensure coder_bob branch exists (create from master if needed)
if ! git show-ref --verify --quiet refs/heads/coder_bob; then
    git branch coder_bob origin/master
fi

# Check if worktree exists
if [ ! -d "$WORKTREE_PATH" ]; then
    # Create worktree for coder_bob branch
    git worktree add "$WORKTREE_PATH" coder_bob
    echo "Created worktree at $WORKTREE_PATH"
fi

# Change to worktree directory
cd "$WORKTREE_PATH" || exit 1

claude --dangerously-skip-permissions --effort medium --model Sonnet
# --settings ~/.claude/settings_zai.json


