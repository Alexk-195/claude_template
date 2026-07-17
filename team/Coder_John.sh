# @file_purpose Launch script for the Coder_John agent (Claude Sonnet via Anthropic, medium effort) in its tmux session.

# Setup coder_john branch and worktree
WORKTREE_PATH="../auto_placer-worktrees/Coder_John"

# Ensure coder_john branch exists (create from master if needed)
if ! git show-ref --verify --quiet refs/heads/coder_john; then
    git branch coder_john origin/master
fi

# Check if worktree exists
if [ ! -d "$WORKTREE_PATH" ]; then
    # Create worktree for coder_john branch
    git worktree add "$WORKTREE_PATH" coder_john
    echo "Created worktree at $WORKTREE_PATH"
fi

# Change to worktree directory
cd "$WORKTREE_PATH" || exit 1

claude --dangerously-skip-permissions --effort medium --model Sonnet
# --settings ~/.claude/settings_zai.json
