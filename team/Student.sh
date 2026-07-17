# @file_purpose Launch script for the Student agent (Claude Haiku via z.ai/GLM settings, low effort) in its tmux session.

# Setup student branch and worktree
WORKTREE_PATH="../auto_placer-worktrees/Student"

# Ensure student branch exists (create from master if needed)
if ! git show-ref --verify --quiet refs/heads/student; then
    git branch student origin/master
fi

# Check if worktree exists
if [ ! -d "$WORKTREE_PATH" ]; then
    # Create worktree for student branch
    git worktree add "$WORKTREE_PATH" student
    echo "Created worktree at $WORKTREE_PATH"
fi

# Change to worktree directory
cd "$WORKTREE_PATH" || exit 1

claude --dangerously-skip-permissions --effort low --model Haiku 
# --settings ~/.claude/settings_zai.json
# --ax-screen-reader

