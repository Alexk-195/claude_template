---
name: orientation
description: Use this skill on following trigger words: orient yourself, get whole picture, get overview of the project, understand project structure, on-boarding
---

# Project Context

Run from the repo root:

```bash
./context.py
```

This regenerates three docs (exits non-zero on error):

- `context.md` — entry doc: git branch, important files, and pointers to the two below.
- `context_sources.md` — all source folders/files and their purpose.
- `context_tickets.md` — open and done tickets.

Read `context.md` first; open the others only if you need them.

Implementation: `build_context.py` (class `Context`) next to this file.
