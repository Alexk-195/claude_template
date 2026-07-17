# @file_purpose Launch script for the TicketWriter agent (Claude Haiku, medium effort, remote-control) in its own worktree.

# Setup ticketwriter branch and worktree
WORKTREE_PATH="../auto_placer-worktrees/TicketWriter"

# Ensure ticketwriter branch exists (create from master if needed)
if ! git show-ref --verify --quiet refs/heads/ticketwriter; then
    git branch ticketwriter origin/master
fi

# Check if worktree exists
if [ ! -d "$WORKTREE_PATH" ]; then
    # Create worktree for ticketwriter branch
    git worktree add "$WORKTREE_PATH" ticketwriter
    echo "Created worktree at $WORKTREE_PATH"
fi

# Change to worktree directory
cd "$WORKTREE_PATH" || exit 1

# IMPORTANT: publish ticket files STRAIGHT TO MASTER — do not use the branch
# for tickets (branch numbering/merging caused duplicate ticket numbers and
# merge conflicts). See CLAUDE.md "Ticket drafting goes straight to master":
#   - Create:      .claude/skills/ticket-system/scripts/ticket-new-on-master.sh
#   - Fill/close:  .claude/skills/ticket-system/scripts/ticket-push-to-master.sh
# Both refuse to push anything outside tickets/. The Architect still reviews the
# ticket CONTENT before it is delegated.

# Remote control is activated automatically by the --remote-control flag, which
# also names the tmux/session as "TicketWriter".
claude --dangerously-skip-permissions --effort medium --model Haiku --remote-control TicketWriter 
# For GLM/z.ai Haiku instead of Anthropic Haiku, append: --settings ~/.claude/settings_zai.json
