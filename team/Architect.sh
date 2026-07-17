# @file_purpose Launch script for the Architect agent (Claude Opus, medium effort, remote-control) in its tmux session.

# Ensure architect branch exists (create from master if needed)
if ! git show-ref --verify --quiet refs/heads/architect; then
    git branch architect origin/master
fi

# Switch to architect branch (stays in main tree)
git checkout architect

claude --dangerously-skip-permissions --effort medium --model Opus --remote-control Architect
