#!/usr/bin/env python3
# @file_purpose Print plan usage for the agent accounts: Anthropic (Claude) 5h/7-day from local ratelimit files, plus z.ai (GLM) usage for the shared Coder_Bob/Coder_John/Student account.
"""
Prints two sections:
  - Anthropic (Claude) 5-hour and 7-day usage, read from the local
    ~/.claude/ratelimits/*.json files (same source as the tmux-communication
    check-ratelimit.sh helper).
  - z.ai (GLM) plan usage — a Python port of the glm-plan-usage
    `query-usage.mjs` skill (zai-org/zai-coding-plugins): the z.ai monitor API's
    5-hour + weekly token limits and the monthly MCP limit.

Auth/config comes from the same environment the Claude agents use:
  - ANTHROPIC_AUTH_TOKEN  (required)  the z.ai API key, sent as the Authorization header
  - ANTHROPIC_BASE_URL    (optional)  defaults to https://api.z.ai/api/anthropic;
                                      only its scheme://host is used to build the
                                      monitor endpoints.

Stdlib only (urllib) — no third-party dependencies.

Usage:
    ANTHROPIC_AUTH_TOKEN=<key> ./usage.py [--json]

    --json   print the raw parsed API response instead of the formatted summary.
"""

import glob
import json
import os
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

DEFAULT_BASE_URL = "https://api.z.ai/api/anthropic"
QUOTA_PATH = "/api/monitor/usage/quota/limit"

# type -> human label for the metric kind
TYPE_LABELS = {
    "TOKENS_LIMIT": "Token usage",
    "TIME_LIMIT": "MCP usage",
}

# (unit, number) -> the rolling window that limit resets over. The API encodes
# the window as a `unit` code + `number` count; the values below are what the
# z.ai plan returns (confirmed against each entry's nextResetTime):
#   unit 3 = hour, unit 6 = week, unit 5 = month.
WINDOW_LABELS = {
    (3, 5): "5-hour",
    (6, 1): "weekly",
    (5, 1): "monthly",
}
UNIT_NAMES = {3: "hour", 5: "month", 6: "week"}


def base_domain(base_url: str) -> str:
    """scheme://host from ANTHROPIC_BASE_URL, stripping any path."""
    parsed = urlparse(base_url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"ANTHROPIC_BASE_URL is not a valid URL: {base_url!r}")
    return f"{parsed.scheme}://{parsed.netloc}"


def get_json(url: str, token: str) -> dict:
    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Authorization": token,
            "Accept-Language": "en-US,en",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            body = res.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace") if e.fp else ""
        raise SystemExit(f"[quota/limit] HTTP {e.code}\n{detail}")
    except urllib.error.URLError as e:
        raise SystemExit(f"Request failed: {e.reason}")
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        raise SystemExit(f"Could not parse response as JSON:\n{body}")


def extract_limits(data) -> list:
    """json.data may be {'limits': [...]} or a bare list; normalize to a list."""
    if isinstance(data, dict):
        limits = data.get("limits")
        if isinstance(limits, list):
            return limits
        # some responses may nest the entries directly under data
        return [data]
    if isinstance(data, list):
        return data
    return []


def window_label(entry: dict) -> str:
    """Human name for the limit's rolling window (e.g. '5-hour', 'weekly')."""
    unit = entry.get("unit")
    number = entry.get("number")
    if (unit, number) in WINDOW_LABELS:
        return WINDOW_LABELS[(unit, number)]
    if unit in UNIT_NAMES and number is not None:
        return f"{number}-{UNIT_NAMES[unit]}"
    return ""


def humanize_reset(next_reset_ms) -> str:
    """'resets in ~4h' / '~6 days' from an epoch-millis reset timestamp."""
    if not isinstance(next_reset_ms, (int, float)):
        return ""
    secs = next_reset_ms / 1000.0 - time.time()
    if secs <= 0:
        return "resets now"
    hours = secs / 3600.0
    if hours < 48:
        return f"resets in ~{hours:.0f}h"
    return f"resets in ~{hours / 24:.0f} days"


def get_anthropic_usage() -> dict:
    """Read Anthropic usage from ~/.claude/ratelimits/*.json files.

    Returns dict with keys: five_hour and seven_day (each with used, resets_at,
    session, age), or None if unavailable.
    """
    now = int(time.time())
    FRESH = 900  # seconds; ignore files older than this (stale local views)

    best_five_hour = None  # (used, resets_at, session, age)
    best_seven_day = None  # (used, resets_at, session, age)
    ratelimit_dir = os.path.expanduser("~/.claude/ratelimits")

    if not os.path.exists(ratelimit_dir):
        return None

    for f in glob.glob(os.path.join(ratelimit_dir, "*.json")):
        try:
            with open(f) as fp:
                d = json.load(fp)
        except Exception:
            continue

        age = now - int(d.get("written_at", 0))
        if age > FRESH:
            continue

        session = d.get("session")

        # Check five_hour
        fh = d.get("five_hour") or {}
        used_5h = fh.get("used_percentage")
        if used_5h is not None:
            if best_five_hour is None or used_5h > best_five_hour[0]:
                best_five_hour = (used_5h, fh.get("resets_at"), session, age)

        # Check seven_day
        sd = d.get("seven_day") or {}
        used_7d = sd.get("used_percentage")
        if used_7d is not None:
            if best_seven_day is None or used_7d > best_seven_day[0]:
                best_seven_day = (used_7d, sd.get("resets_at"), session, age)

    if best_five_hour is None and best_seven_day is None:
        return None

    result = {}
    if best_five_hour is not None:
        result["five_hour"] = {
            "used": best_five_hour[0],
            "resets_at": best_five_hour[1],
            "session": best_five_hour[2],
            "age": best_five_hour[3],
        }
    if best_seven_day is not None:
        result["seven_day"] = {
            "used": best_seven_day[0],
            "resets_at": best_seven_day[1],
            "session": best_seven_day[2],
            "age": best_seven_day[3],
        }
    return result


def format_anthropic_usage(info: dict) -> str:
    """Format Anthropic usage info for display."""
    lines = []

    for period in ("five_hour", "seven_day"):
        data = info.get(period)
        if not data:
            continue

        label = "5h" if period == "five_hour" else "7-day"
        used = data["used"]
        resets = data["resets_at"]
        sess = data["session"]
        age = data["age"]

        if resets:
            remain = int(resets) - int(time.time())
            when = time.strftime("%H:%M", time.localtime(resets))
            if remain > 0:
                reset_str = f"{when} (in {remain//3600}h {remain%3600//60}m)"
            else:
                reset_str = f"{when} (passed)"
        else:
            reset_str = "unknown"

        lines.append(f"  Account {label}: {used}% (shared; freshest from {sess}, {age}s ago) | resets at {reset_str}")

    return "\n".join(lines)


def fmt_entry(entry: dict) -> str:
    raw_type = entry.get("type", "")
    kind = TYPE_LABELS.get(raw_type, raw_type or "unknown")
    window = window_label(entry)
    label = f"{kind} ({window})" if window else kind
    pct = entry.get("percentage")

    line = f"  {label}:"
    line += f" {pct}%" if pct is not None else " n/a"
    reset = humanize_reset(entry.get("nextResetTime"))
    if reset:
        line += f"  [{reset}]"
    details = entry.get("usageDetails")
    if details:
        line += f"\n    details: {json.dumps(details, ensure_ascii=False)}"
    return line


def main() -> int:
    want_json = "--json" in sys.argv[1:]

    # --- Anthropic (Claude) usage from local ratelimit files ---
    anthropic_info = get_anthropic_usage()
    if anthropic_info and not want_json:
        print("Anthropic (Claude) plan usage:")
        print(format_anthropic_usage(anthropic_info))
        print()  # blank line between sections
    elif not anthropic_info and not want_json:
        print("Anthropic (Claude) plan usage:")
        print("  No fresh rate-limit data available")
        print()

    # --- GLM (z.ai) usage from API ---
    token = os.environ.get("ANTHROPIC_AUTH_TOKEN")
    if not token:
        print("Error: ANTHROPIC_AUTH_TOKEN is not set", file=sys.stderr)
        return 1

    base_url = os.environ.get("ANTHROPIC_BASE_URL", DEFAULT_BASE_URL)
    url = base_domain(base_url) + QUOTA_PATH

    payload = get_json(url, token)
    data = payload.get("data", payload)

    if want_json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0

    limits = extract_limits(data)
    if not limits:
        print("GLM plan usage:")
        print("No usage limits returned. Raw response:")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    print("GLM plan usage:")
    for entry in limits:
        print(fmt_entry(entry))
    return 0


if __name__ == "__main__":
    sys.exit(main())
