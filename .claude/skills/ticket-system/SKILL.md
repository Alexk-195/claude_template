---
name: ticket-system
description: Explains how to work with tickets. Creating, reading, completing and closing.
---

# File-Based Ticketing System

Tasks tracked as markdown files under `tickets/`:
- `tickets/open/` — work in progress
- `tickets/done/` — completed

## Numbering

- Main tickets: multiples of 10, starting at 1000 (1000, 1010, 1020, ...).
- Sub-tickets: parent number + 1-9 suffix (1020 → 1021, 1022, ...). Reference them in the parent ticket.
- Gaps are fine; continuity is not required.

## Lifecycle

### 1. Create

```
python .claude/skills/ticket-system/scripts/ticket-system-create-new-ticket.py
```

Creates `NNNN_ticket.md` and `NNNN_ticket_result.md` in `tickets/open/` with prefilled templates.

### 2. Work

- Edit `NNNN_ticket.md` as you go; keep title clear and descriptive.
- Add related files using the `NNNN_ticket_` prefix (any extension).
- Break work into sub-tickets based on size:
  - Up to ~4h: don't break down.
  - Up to ~1 day: suggest break-down.
  - Multiple days: discuss and break down before starting.

### 3. Close

1. Fill in `tickets/open/NNNN_ticket_result.md` (summary, changes, testing).
2. If anything learned this session helps future work, store it via the `agent-memory` skill.
3. Run:

   ```
   python .claude/skills/ticket-system/scripts/ticket-system-close-ticket.py <NNNN> [commit message]
   ```

   The script stages all `NNNN_ticket*` files, moves them to `tickets/done/`, and commits.

   **`[commit message]` must be the description ONLY** — do *not* prefix it with
   `Closed ticket NNNN:`. The script prepends that automatically. Passing
   `"Closed ticket 1040: Migrate db_info"` produces a doubled subject
   (`Closed ticket 1040: Closed ticket 1040: Migrate db_info`). Pass just
   `"Migrate db_info"`. (The script now also strips an accidental leading
   prefix defensively, but don't rely on it — keep callers clean.)

   **`--no-commit` flag** — stage and `git mv` the ticket files to `done/` but do
   **not** commit, leaving the move staged for you to bundle into your own commit:

   ```
   python .claude/skills/ticket-system/scripts/ticket-system-close-ticket.py --no-commit <NNNN>
   ```

   Use this for **one-commit-per-ticket**: review the work, then make a single
   commit containing both the implementation and the ticket move (instead of the
   default two — a code commit plus a separate `Closed ticket` commit). The flag
   is position-independent and `[commit message]` is ignored when set.

   ⚠️ With `--no-commit` the move is left **staged but uncommitted** — commit it
   immediately. Dangling staged changes get swept into the next unrelated commit
   (e.g. a broad-`git add` committer), which is exactly what this flow is meant to
   give you control over. If you just want a clean atomic close, omit the flag.

## Listing tickets

```bash
ls tickets/open/*.md     # open
ls tickets/done/*.md     # completed
ls tickets/archive/*.md  # archived (older completed tickets)
```

## Archive

`tickets/archive/` contains older completed tickets that have been moved there manually to keep `tickets/done/` tidy. It is not part of the automated lifecycle — the close script always moves to `tickets/done/`. Archiving is a manual housekeeping step.
