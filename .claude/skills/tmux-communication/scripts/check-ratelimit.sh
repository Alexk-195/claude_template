#!/bin/bash
# @file_purpose Gate delegation on the ACCOUNT-WIDE 5h usage limit (shared by all
#               agents). Exit 3 if usage >= threshold (default 95), else 0.
# Usage: check-ratelimit.sh [threshold_pct]
#
# The 5h limit is shared across every agent session, so there is no per-agent
# headroom. Each session's status bar is a stale local view; the true account
# usage is the FRESHEST reading available. status_line.py writes every session's
# rate_limits (with resets_at) to ~/.claude/ratelimits/<session>.json on each
# repaint. We take the max used_percentage among *recently written* files (the
# active orchestrator's is always fresh), which approximates current account use.
set -euo pipefail

threshold="${1:-95}"

python3 - "$threshold" <<'PY'
import glob, json, os, sys, time
threshold = float(sys.argv[1])
now = int(time.time())
FRESH = 900  # seconds; ignore files older than this (stale local views)

best = None  # (used, resets_at, session, age)
for f in glob.glob(os.path.expanduser("~/.claude/ratelimits/*.json")):
    try:
        d = json.load(open(f))
    except Exception:
        continue
    fh = d.get("five_hour") or {}
    used = fh.get("used_percentage")
    if used is None:
        continue
    age = now - int(d.get("written_at", 0))
    if age > FRESH:
        continue
    if best is None or used > best[0]:
        best = (used, fh.get("resets_at"), d.get("session"), age)

if best is None:
    sys.stderr.write("account rate: no fresh rate-limit data (no session repainted recently).\n")
    sys.exit(2)

used, resets, sess, age = best
if resets:
    remain = int(resets) - now
    when = time.strftime("%H:%M", time.localtime(resets))
    reset_str = f"{when} " + (f"(in {remain//3600}h {remain%3600//60}m)" if remain > 0 else "(passed)")
else:
    reset_str = "unknown"

print(f"Account 5h={used}% (shared; freshest from {sess}, {age}s ago) | resets at {reset_str}")
if used >= threshold:
    sys.stderr.write(f"  -> account 5h usage {used}% >= {threshold:.0f}%: DO NOT delegate until reset.\n")
    sys.exit(3)
sys.exit(0)
PY
