# tmux-communication reference

Detailed procedures for the `tmux-communication` skill. Start from `SKILL.md`
for the core model, the `[tmux]` rule, and the one-liners; come here when you
need the full semantics, gotchas, or options for any of them.

## Discovering who is running

Run the project's context generator from the repo root:

```bash
./context.py
```

Under `--- tmux agents ---` it prints (to the console, never into the context
files):

- **This agent** — the current tmux session name (your own name).
- **Other agents** — the other tmux sessions you can talk to.

Equivalent raw tmux commands:

```bash
tmux display-message -p '#S'      # this agent's name (current session)
tmux list-sessions -F '#S'        # all agents (sessions)
```

If `$TMUX` is unset you are not inside tmux and have no agent name — there is no
one to message.

## Sending a message to another agent

**Standard case — use the helper script.** It checks the recipient session
exists, refuses to message yourself, appends your sender signature, and applies
the required 1s pause for you:

```bash
<SKILL_DIR>/scripts/send-to-agent.sh <recipient-session> <message...>
# e.g.
~/auto_placer/.claude/skills/tmux-communication/scripts/send-to-agent.sh \
    Coder_Bob "Please start ticket 1010 (db.py)."
```

It signs the message with your own session name automatically, so you don't need
to add "— YourName" yourself.

### Doing it by hand

If you need to send manually, a message is delivered by typing it into the
target session and then sending a separate `Enter` keystroke to submit it.

**IMPORTANT — the 1-second pause:** there must be a pause of **at least 1 second
between posting the message text and sending the final `Enter`**. Sending the
text and the `Enter` together (or back-to-back) is unreliable — the receiving
agent's input box may not have registered the pasted text before the submit
fires, so the message gets lost or truncated. Always split it into two
`send-keys` calls with a `sleep 1` in between:

```bash
# 1. Type the message into the target agent's session (no Enter yet)
tmux send-keys -t <SESSION> "your message here"

# 2. Wait at least 1 second so the text settles in the input box
sleep 1

# 3. Send Enter on its own to submit it
tmux send-keys -t <SESSION> Enter
```

Example — Architect asking the Coder_Bob agent to start a ticket:

```bash
tmux send-keys -t Coder_Bob "Please start ticket 1010 (db.py). — Architect"
sleep 1
tmux send-keys -t Coder_Bob Enter
```

## Resetting / clearing a session

To clear an agent's conversation and reconfigure it, use the reset helper. It
verifies the session exists, optionally renames it, then issues `/new`,
`/model`, and `/effort` as slash commands with a 2s pause after each so the TUI
keeps up:

```bash
<SKILL_DIR>/scripts/reset-session.sh [old_session_name] [new_session_name] [model] [effort]
# rename Architect -> Coder_Bob, clear, set model + effort:
~/auto_placer/.claude/skills/tmux-communication/scripts/reset-session.sh \
    Architect Coder_Bob claude-opus-4-8 medium
# clear the CURRENT session in place (omit the name — defaults to your session):
~/auto_placer/.claude/skills/tmux-communication/scripts/reset-session.sh
```

All arguments are optional. The first defaults to the **current** session when
omitted or empty. Pass an empty string `""` to skip an optional step (e.g. keep
the name but set effort: `reset-session.sh "" "" "" medium`). Often used on your
**own** session to start fresh — note that `/new` clears the conversation, so
run it when you no longer need the current context.

**Pause after a reset before sending the next message.** The reset issues its
last slash command (e.g. `/rc`) and the TUI is still settling when the script
returns. If you `send-to-agent.sh` a task message immediately, it can collide
with that trailing command and be **dropped — the target stays idle at 0%
context**. Wait a few seconds (≈3–5s) after `reset-session.sh` before sending.

**Verify by reading the pane transcript, not the status bar.** After sending,
wait ~8–10s, then capture a chunk of the pane (`tmux capture-pane -p -t
<SESSION> | tail -30`) and confirm **your message text actually appears in the
conversation**. Don't judge by the context-bar percentage alone — it lags and
can show `0%` for several seconds during a render gap even though the message
landed. Only re-send if your text is genuinely absent from the transcript after
that wait; re-sending on a slow render produces a **duplicate prompt** the agent
will process twice.

**Keep the model as it was.** Unless you are deliberately switching models, the
reset must preserve the session's current model. Don't guess it — read it off
the target's status line, which lives in the **bottom 3 lines** of the pane
(e.g. `[Opus 4.8]`):

```bash
tmux capture-pane -p -t <SESSION> | tail -3
```

Map that label to the model id and pass it through (`[Opus 4.8]` →
`claude-opus-4-8`, `[Sonnet 4.6]` → `claude-sonnet-4-6`, `[Haiku 4.5]` →
`claude-haiku-4-5-20251001`, `[Fable 5]` → `claude-fable-5`). So a
context-clearing reset that must NOT change the model looks like:

```bash
model="claude-opus-4-8"   # read from the status line above
reset-session.sh <SESSION> "" "$model" ""
```

> Note: `reset-session.sh` no longer issues `/rc` (remote control stays
> connected across resets). Issue `/rc` explicitly only if a session needs it.

## Delegating a ticket (the umbrella script)

For the common "hand ticket N to an agent" case, use `delegate-ticket.sh`. Pass
the recipient and the ticket number; it does everything: checks the ticket file
exists, **brings the agent's named branch up to date with latest master** in
their fixed worktree, resets the recipient's session (clearing context; sets the
model if you give one, otherwise preserves it), waits the post-reset pause, sends
the standard "implement this ticket, follow the criteria, commit+push your code,
ask over tmux" message, and **verifies delivery by reading the pane transcript**
(re-sends once if it didn't land).

```bash
<SKILL_DIR>/scripts/delegate-ticket.sh <recipient-session> <ticket-number> [model] [extra-instructions...]
# e.g. hand ticket 2004 to Coder_Bob on Sonnet:
~/auto_placer/.claude/skills/tmux-communication/scripts/delegate-ticket.sh Coder_Bob 2004 claude-sonnet-4-6
# keep the recipient's current model (omit it), add a one-line extra note:
~/auto_placer/.claude/skills/tmux-communication/scripts/delegate-ticket.sh Student 2005 "" "Tests can be written against the documented signatures first (TDD)."
```

This is the preferred path — prefer it over manually chaining `reset-session.sh`
+ `send-to-agent.sh` for ticket work.

### Per-agent fixed worktrees + named branches

Each agent has its **own permanent worktree on its own permanent branch**, so
agents never share a working tree and their commits never collide — no per-ticket
branches are created:

| Agent      | Worktree                                    | Branch       |
|------------|---------------------------------------------|--------------|
| Architect  | `~/auto_placer` (main tree)                   | `architect`  |
| Coder_Bob  | `~/auto_placer-worktrees/Coder_Bob`           | `coder_bob`  |
| Coder_John | `~/auto_placer-worktrees/Coder_John`          | `coder_john` |
| Student    | `~/auto_placer-worktrees/Student`             | `student`    |
| Release    | `~/auto_placer-worktrees/release`             | `release`    |

`delegate-ticket.sh` fetches origin and fast-forwards the recipient's named
branch to `origin/master` before delegating (so they start each ticket from a
clean, current base), then tells the agent to implement in **their** worktree,
commit to **their** branch, and push it — never merging into master or touching
another tree. Agents are long-lived Claude sessions with a fixed launch dir, so
the reset does not change their cwd; they already run in the right worktree.

Integration is the **orchestrator's** job (review gate). After the agent pushes
their branch, review it and merge with `integrate-ticket.sh <agent>`:

```bash
# inspect first (e.g. Coder_Bob's branch):
git -C ~/auto_placer log --oneline master..coder_bob
git -C ~/auto_placer diff master..coder_bob
# then merge the agent's named branch (--no-ff) into master:
<SKILL_DIR>/scripts/integrate-ticket.sh Coder_Bob [--push]
```

`integrate-ticket.sh` refuses to run unless `master` is checked out and clean in
the main tree, and aborts on merge conflicts (resolve in the main repo, commit,
then re-run). It **does not delete** the agent's named branch — those are
permanent; instead it fast-forwards the branch back to master after a successful
merge so it's clean for the next ticket. Use `--push` to also push `master`
afterwards.

### Rate-limit rule — the 5h limit is ACCOUNT-WIDE (shared by all agents)

**All agents run under one account, so the rolling 5-hour usage limit is shared
across every session — there is NO per-agent headroom.** You cannot "route the
ticket to whichever agent shows a lower %"; they all draw from the same budget.

Critically, each session's status-bar `5h:NN%` is a **stale local view** — it
only updates when *that* session repaints. An idle agent can show an old, low
value while the real (shared) usage is much higher. (This bit us once: an agent
showing "77%" was picked and then stalled mid-ticket — its bar was outdated; the
account was already near the cap.)

**Rule: gate on the account-wide usage, and when it's near the cap (≥ ~90-95%)
don't delegate to ANY agent** until the window resets. `delegate-ticket.sh`
enforces this via `check-ratelimit.sh`, which reads the **freshest** figure
available — the currently-active orchestrator's own bar, which repaints
constantly and therefore reflects true account usage.

```bash
<SKILL_DIR>/scripts/check-ratelimit.sh [threshold]   # default 95; exit 0 = ok, 3 = wait
# -> "Account 5h=90% (shared) | resets at 02:20 (in 2h 41m)"
```

**If the limit trips mid-task the agent stalls and resume does NOT reliably
work** — you must wait for the reset, then re-run/re-delegate the ticket.

**When blocked, wake once at the reset.** The reset epoch comes from
`rate_limits.five_hour.resets_at` in the status-line payload (persisted to
`~/.claude/ratelimits/<session>.json`). Schedule a single wake-up at that time
(`send_later`/`ScheduleWakeup`) rather than busy-polling.

## Reviewing an agent's branch (low-noise)

When reviewing an agent's branch, avoid token-heavy operations that dump
irrelevant context.

**Use three-dot diffs and `git log`, not two-dot `diff --stat`.** The two-dot
form `git diff --stat master..<branch>` shows every master-side commit the
agent's branch lacks as a spurious "deletion" — huge noise when the orchestrator
has committed many things since the agent branched. Prefer:

- `git log --oneline master..<branch>` — only the agent's own commits.
- `git diff --stat master...<branch>` — THREE dots = merge-base diff, hides
  master-side additions.
- Exclude ticket markdown from code review: `-- . ':(exclude)tickets/'`.

**Use the #1711 helper scripts:** `team/agent_status.sh <agent>` for a compact
status block and `team/review.sh <agent>` for a low-noise review payload (code
diff excl tickets + the result file). Prefer these over ad-hoc multi-command
greps.

**Filter pane captures, never dump raw.** Always `tmux capture-pane -p -t
<session> | grep -E '<filter>' | tail -N` rather than dumping the whole pane —
call logs and big diffstats are token-heavy.

## Conventions

- **Sign your messages** with your own agent name (from `tmux display-message -p
  '#S'`) so the recipient knows who is asking.
- **Address the right session.** Confirm the target name with `./context.py` or
  `tmux list-sessions -F '#S'` before sending — a typo sends keystrokes nowhere
  (or to the wrong agent).
- **One message, one submit.** Don't bundle multiple `Enter`s; send the text,
  pause ≥1s, then a single `Enter`.
- **Don't message yourself.** Skip the current session when iterating over the
  session list.
