# Instructions for AI Agents

**IMPORTANT**: If you need overview over the project for better understanding the whole picture run `./context.py` and read its output. Make sure it returns 0 as error code.
Use skill "orientation" to get the whole picture.

The team members are: Architect, Coder_Bob, Coder_John, Student, TicketWriter.
Task of Architect is to create tickets, delegate them, review results, discuss with CEO (human). He reports issues and blockers to CEO.
Coders and Student receive tickets and implement them. They report issues and blockers to Architect.
Student only receives very simple tasks. Architect ALWAYS reviews his work.
All team members are running Claude in tmux sessions with corresponding names.
You can find out who you are if you run ./context.py.

## Per-Agent Worktree Workflow

Each agent runs in its own **fixed git worktree** to isolate work and prevent conflicts:

- **Architect**: Main tree `/home/mint/auto_placer` (branch: `architect`)
- **Coder_Bob**: `/home/mint/auto_placer-worktrees/Coder_Bob` (branch: `coder_bob`)
- **Coder_John**: `/home/mint/auto_placer-worktrees/Coder_John` (branch: `coder_john`)
- **Student**: `/home/mint/auto_placer-worktrees/Student` (branch: `student`)
- **TicketWriter**: `/home/mint/auto_placer-worktrees/TicketWriter` (branch: `ticketwriter`)

### Ticket Delegation Workflow

When Architect delegates a ticket:

1. Architect ensures agent's branch is up-to-date with latest master
2. Agent works in their isolated worktree on their named branch (coder_bob, student, etc.)
3. Agent commits and pushes to their branch when done
4. Architect reviews and merges agent's branch to master

This ensures:
- No conflicts between agents working on different tickets
- Clean integration (Architect controls master merges)

### Ticket drafting goes straight to master (no branch merge)

**Ticket files are additive markdown — never route them through a long-lived branch.**
Numbering a ticket against a stale branch, then merging that branch, can cause duplicate
ticket numbers and same-path merge conflicts. Instead, TicketWriter (and any agent
creating/closing tickets) publishes ticket files **directly to master**, which cannot
affect the build:

- **Create a ticket:** run `.claude/skills/ticket-system/scripts/ticket-new-on-master.sh`
  from the agent worktree. It resets to `origin/master`, numbers against the authoritative
  latest master, and claims the number by pushing the template to master — if another
  ticket landed first the push fails and it **re-numbers and retries**, so numbers can
  never collide.
- **Fill / close a ticket:** edit the ticket (and run the normal close script for a close),
  then run `.claude/skills/ticket-system/scripts/ticket-push-to-master.sh`. It merges
  `origin/master` (conflict-free — ticket filenames are unique) and pushes. Both scripts
  **refuse to push anything outside `tickets/`**, so no code can reach master this way.
- The Architect still **reviews ticket content** (premise-check TicketWriter's tickets
  against the code before delegating) — only the *mechanics* of numbering/merging changed.
- **Code work is unchanged:** the per-agent branch + `integrate-ticket.sh` flow above still
  governs anything that touches source. The master-direct path is for `tickets/**` only.

### Launch Scripts

Each agent's `team/*.sh` script creates/uses its fixed worktree:

```bash
# Architect uses main tree
./team/Architect.sh

# Coder_Bob, Coder_John, Student, TicketWriter use their worktrees
./team/Coder_Bob.sh
./team/Coder_John.sh
./team/Student.sh
./team/TicketWriter.sh
```

Scripts automatically create worktrees if missing and ensure agents run in the correct location.

## Architect Context Management & Self-Restart

The Architect must watch his own context fill state and restart his session before it
degrades. Check the context fill after all major work — **after every ticket**.

- **From 40%**: plan a session restart in the near future. The Architect may still take on
  a few more tickets to reach a clean topic break — a natural boundary means less handoff
  document to write.
- **From 60%**: no new work. Finish the handoff once the other team members have completed
  their in-flight jobs, then restart.

### Restart procedure

1. Write the handoff session document (see `team/Architect_restart.sh` and the paths it
   references — `ARCHITECT_HANDOFF.md` in the repo root, gitignored).
2. Send a tmux message to a team member asking them to run the restart. A Haiku-model agent
   is enough for this, so **Student or TicketWriter** are fine choices.
3. That team member runs the restart per `team/Architect_restart.sh`.

### TicketWriter watches the restart

The TicketWriter should observe the restart process. If it hangs, TicketWriter performs the
restart himself according to the restart script. **Retry up to 3 times.**

### After an autonomous restart

An automatic restart will probably happen in the absence of the supervisor (CEO). The
Architect therefore continues his work autonomously: check the backlog and delegate tickets
to team members.
