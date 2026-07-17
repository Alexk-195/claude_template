---
name: tmux-communication
description: How AI agents running in named tmux sessions identify and message each other. Use when agents must coordinate, hand off work, or send a message to another agent.
---

# Agent-to-Agent Communication over tmux

Multiple AI agents can run side by side, each in its own **named tmux session**.
An agent's **name is its tmux session name** — e.g. an agent in session
`Architect` is the "Architect" agent. Messaging another agent means typing into
its tmux session's pane.

## The `[tmux]` suffix (reply over tmux) — safety-critical

**If your prompt ends with the suffix `[tmux]`, your feedback and questions must
go back to the tmux session that sent it — not just printed in your own
transcript.** The `[tmux]` marker means the message came from another agent over
tmux, and that agent reads its own tmux session, not yours. Reply with
`send-to-agent.sh <sender> "..."` (the sender name is in the signature, e.g.
`— Architect [tmux]`). **Anything you only print locally never reaches them.**

## Common actions — one-liners

```bash
# Send a message to another agent (handles the required 1s pause for you)
<SKILL_DIR>/scripts/send-to-agent.sh <recipient-session> <message...>

# Reset/clear a session (optionally rename, set model/effort)
<SKILL_DIR>/scripts/reset-session.sh [old_session_name] [new_session_name] [model] [effort]

# Hand a ticket to another agent (syncs their named branch to latest master,
# resets their session, sends the standard "implement this ticket" message,
# verifies delivery) — preferred for ticket work
<SKILL_DIR>/scripts/delegate-ticket.sh <recipient-session> <ticket-number> [model] [extra-instructions...]

# Each agent works in their OWN fixed worktree on their OWN permanent branch
# (Coder_Bob→coder_bob, Coder_John→coder_john, Student→student, Architect→architect on
# the main tree). We do NOT create per-ticket `ticket/<N>` branches anymore.
# After the agent pushes their branch, review + merge it into master yourself:
<SKILL_DIR>/scripts/integrate-ticket.sh <recipient-session> [--push]

# Check the shared account-wide 5h rate limit before delegating
<SKILL_DIR>/scripts/check-ratelimit.sh [threshold]
```

`<SKILL_DIR>` is `~/auto_placer/.claude/skills/tmux-communication`.

For full semantics, gotchas, and options — discovering who's running, sending
by hand, reset pause/verification rules, model-preservation, the rate-limit
rule, and general conventions — see **`reference.md`** in this skill folder.
