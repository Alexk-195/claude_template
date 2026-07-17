#!/usr/bin/env python3
# @file_purpose Close a ticket: stage and move all NNNN_ticket* files from open/ to done/, then commit (unless --no-commit).

import os
import re
import sys
import subprocess


def git_mv(src_path, dst_path):
    """Move a tracked or staged file using `git mv` to preserve history."""
    rc = subprocess.run(['git', 'mv', src_path, dst_path]).returncode
    if rc == 0:
        print(f"Moved {src_path} -> {dst_path}")
    else:
        print(f"Error: `git mv {src_path} {dst_path}` failed (exit {rc}).")
    return rc


def format_commit_message(ticket_number, custom_message=None):
    message_text = f"Closed ticket {ticket_number}"
    if custom_message:
        # Be idempotent: callers sometimes pass a message that already starts
        # with one or more "Closed ticket <N>:" prefixes (the script adds its
        # own). Strip any such leading prefixes so we never double them up.
        prefix_re = re.compile(rf"^\s*Closed ticket {re.escape(ticket_number)}\s*:\s*", re.IGNORECASE)
        while prefix_re.match(custom_message):
            custom_message = prefix_re.sub("", custom_message, count=1)
        custom_message = custom_message.strip()
        if custom_message:
            message_text += f": {custom_message}"
    return message_text


def has_staged_changes():
    """True if anything is staged for commit."""
    return subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode != 0


def uncommitted_non_ticket_changes(ticket_number):
    """Working-tree changes (staged/modified/untracked) to files that are NOT this
    ticket's own NNNN_ticket* files. These are almost always an agent's code edits
    that it forgot to commit -- the close-commit below would silently omit them,
    orphaning the work (bug behind #1713/#1714 false completions). Returned so the
    caller can refuse to close until they're committed."""
    out = subprocess.run(["git", "status", "--porcelain"],
                         capture_output=True, text=True).stdout
    tick_re = re.compile(rf"tickets/(open|done)/{re.escape(ticket_number)}_ticket[._]")
    offenders = []
    for line in out.splitlines():
        if not line.strip():
            continue
        path = line[3:]
        if " -> " in path:            # rename: "old -> new"
            path = path.split(" -> ", 1)[1]
        path = path.strip().strip('"')
        if tick_re.search(path):
            continue                  # this ticket's own files are expected
        offenders.append(line.rstrip())
    return offenders


def main():
    args = sys.argv[1:]

    # --no-commit: stage + `git mv` the ticket files to done/ but do NOT commit,
    # leaving the move staged so the caller can bundle it into their own commit
    # (e.g. one commit per ticket: impl + close together).
    no_commit = False
    if "--no-commit" in args:
        no_commit = True
        args = [a for a in args if a != "--no-commit"]

    # --force: close even if there are uncommitted non-ticket changes (normally
    # refused, to stop an agent's code edits being orphaned -- see #1714).
    force = "--force" in args
    if force:
        args = [a for a in args if a != "--force"]

    if not args:
        print("Usage: ticket-system-close-ticket.py [--no-commit] <ticket_number> [commit_message]")
        return 1

    ticket_number = args[0]
    if not re.fullmatch(r"\d+", ticket_number):
        print(f"Error: Ticket number must be all digits, got '{ticket_number}'.")
        return 1

    custom_message = ' '.join(args[1:]) if len(args) > 1 else None
    open_ticket_path = os.path.join("tickets", "open")
    done_ticket_path = os.path.join("tickets", "done")

    if not os.path.isdir(open_ticket_path):
        print(f"Error: Folder {open_ticket_path} does not exist.")
        return 2

    # Result file lives in open/ until this script moves it.
    result_file_name = f"{ticket_number}_ticket_result.md"
    result_file_path = os.path.join(open_ticket_path, result_file_name)
    if not os.path.isfile(result_file_path):
        print(f"Error: Result file '{result_file_path}' is missing. Fill it in before closing.")
        return 2

    # Guard (#1714): refuse to close if the agent has uncommitted code — the
    # close-commit only stages this ticket's own files, so any other modified/
    # untracked file would be silently left behind (the bug behind the #1713/#1714
    # false completions). --no-commit is exempt (it deliberately leaves work for a
    # bundled commit); --force overrides.
    if not no_commit and not force:
        offenders = uncommitted_non_ticket_changes(ticket_number)
        if offenders:
            print("Error: refusing to close — you have uncommitted changes that this "
                  "close would NOT commit (your code would be left behind):")
            for o in offenders:
                print("  " + o)
            print("Commit your code first:  git add <files> && git commit -m '...'")
            print("then re-run close. (Pass --force to close anyway.)")
            return 4

    os.makedirs(done_ticket_path, exist_ok=True)

    # Match NNNN_ticket.<ext> or NNNN_ticket_<anything>.<ext>; the [._] anchor
    # prevents prefix collisions (e.g. ticket "100" matching "1000_ticket*").
    prefix_re = re.compile(rf"^{re.escape(ticket_number)}_ticket[._]")
    matching = sorted(f for f in os.listdir(open_ticket_path) if prefix_re.match(f))

    if not matching:
        print(f"Error: No files matching '{ticket_number}_ticket*' in {open_ticket_path}.")
        return 2

    for filename in matching:
        src = os.path.join(open_ticket_path, filename)
        dst = os.path.join(done_ticket_path, filename)
        # `git mv` needs the source tracked or staged; stage first so freshly
        # created files (e.g. the result file) move cleanly.
        subprocess.run(['git', 'add', src], check=False)
        if git_mv(src, dst) != 0:
            return 3

    if no_commit:
        print(f"--no-commit: moved {ticket_number}_ticket* to done/ and staged the move; "
              "commit it yourself (bundle with the related code changes if desired).")
        print(f"Ticket {ticket_number} has been closed (move staged, not committed).")
        return 0

    if has_staged_changes():
        commit_message = format_commit_message(ticket_number, custom_message)
        if subprocess.run(['git', 'commit', '-m', commit_message]).returncode != 0:
            print("Error: Failed to commit changes. Please fix and repeat.")
            return 3
    else:
        print("Warning: Nothing was staged; skipping commit.")

    print(f"Ticket {ticket_number} has been successfully closed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
