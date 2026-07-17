#!/usr/bin/env python3
# @file_purpose Script to get the next available ticket number from a ticket system and create new ticket files

import os
import re
import subprocess


ticket_template = """

[Detailed description of the task, issue, or feature]

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

## Notes
[Any additional context, references, or implementation notes]

## Related Tickets
- Blocks: #NNNN
- Blocked by: #NNNN
- Related: #NNNN
"""


ticket_result_template = """

[Brief summary of what was accomplished]

## Changes Made
- Change 1
- Change 2
...

## Testing
[How the changes were tested]

## Notes

"""


TICKET_NUMBER_RE = re.compile(r"(?:^|/)(\d+)_ticket")


def run_git(args, timeout=15):
    """Run a read-only git command, returning stdout (or "" on any failure)."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except Exception:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout


def fetch_origin_best_effort():
    # Best-effort refresh of remote-tracking branches so the global scan below
    # sees other agents' worktrees/branches. Network failures are tolerated.
    try:
        subprocess.run(
            ["git", "fetch", "-q", "origin"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:
        pass


def local_ticket_numbers(ticket_file_path):
    numbers = []
    for subdir in ["open", "done", "archive"]:
        dir_path = os.path.join(ticket_file_path, subdir)
        if os.path.isdir(dir_path):
            for filename in os.listdir(dir_path):
                match = re.match(r"^(\d+)_ticket", filename)
                if match:
                    numbers.append(int(match.group(1)))
    return numbers


def remote_ticket_numbers():
    """Scan tickets/ across every origin/* branch for ticket numbers."""
    numbers = []
    refs_output = run_git(["for-each-ref", "--format=%(refname)", "refs/remotes/origin"])
    for ref in refs_output.splitlines():
        ref = ref.strip()
        if not ref or ref.endswith("/HEAD"):
            continue
        listing = run_git(["ls-tree", "-r", "--name-only", ref, "--", "tickets"])
        for line in listing.splitlines():
            match = TICKET_NUMBER_RE.search(line)
            if match:
                numbers.append(int(match.group(1)))
    return numbers


def main():
    ticket_file_path = "tickets"

    # check if ticket file path exists
    if not os.path.isdir(ticket_file_path):
        print(f"Error: Ticket file path '{ticket_file_path}' does not exist.")
        return

    fetch_origin_best_effort()

    # Global max across local tickets/{open,done,archive} and every origin/*
    # branch's tickets/ dir, so agents in separate worktrees (and TicketWriter
    # with uncommitted files) don't pick the same number.
    all_numbers = local_ticket_numbers(ticket_file_path) + remote_ticket_numbers()

    # Find the next available main ticket number (increments of 10), based on
    # the global max (including sub-ticket numbers) rounded down to a
    # multiple of 10. Start from 1000 if no tickets exist anywhere.
    if all_numbers:
        next_ticket = (max(all_numbers) // 10) * 10 + 10
    else:
        next_ticket = 1000

    ticket_header_string = f"# Ticket {next_ticket}: [Title]"
    ticket_result_header_string = f"# Ticket {next_ticket} Result"

    open_dir = os.path.join(ticket_file_path, "open")
    os.makedirs(open_dir, exist_ok=True)

    ticket_path = os.path.join(open_dir, f"{next_ticket:04d}_ticket.md")
    ticket_result_path = os.path.join(open_dir, f"{next_ticket:04d}_ticket_result.md")

    if os.path.exists(ticket_path):
        print(f"Error: Ticket file '{ticket_path}' already exists. Aborting.")
        return
    if os.path.exists(ticket_result_path):
        print(f"Error: Ticket result file '{ticket_result_path}' already exists. Aborting.")
        return

    with open(ticket_path, "w") as f:
        f.write(ticket_header_string + ticket_template)

    with open(ticket_result_path, "w") as f:
        f.write(ticket_result_header_string + ticket_result_template)

    print(f"Next available ticket number: {next_ticket}")
    print(f"Prepared ticket file: {ticket_path}")
    print(f"Prepared ticket result file: {ticket_result_path}")


if __name__ == "__main__":
    main()
