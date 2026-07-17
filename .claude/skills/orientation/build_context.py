#!/usr/bin/env python3
# @file_purpose Basic functionality for building context. Classes Context and FileDirInfo
import os
import glob
import subprocess
import sys

# Recursive structure for collecting folders and files into
class FileDirInfo:
    def __init__(self):
        self.purpose = "" # put a string here if needed
        self.source_path = "" # path of source file or directory relative to parent
        self.children = [] # Children of type FileDirInfo
        self.type = "folder" # currently only "file" or "folder"
        self.parent = None # Parent instance of FileDirInfo
        self.frontmatter = None # If any, this will be dict of keywords and values
    
    def lines(self):
        r = []
        p=self.purpose
        if p is None:
            p = ""
        r.append(self.type+":"+self.source_path + ":" + p)
        return r
    
    def print(self):
        ll = self.lines()
        for l in ll:
            print(l)


class Context:
    """Generic context utilities for AI coding agents."""

    def __init__(self):
        """Initialize Context with configuration constants."""
        # File sampling configuration
        self.default_sample_size = 2048
        
        # ASCII text detection thresholds
        self.ascii_tab_range = (9, 13)  # Tab, newline, etc.
        self.ascii_printable_range = (32, 126)  # Printable ASCII range
        self.ascii_printable_threshold = 0.90  # 95% threshold for printable bytes
        
        # File purpose search configuration
        self.max_lines_to_search = 50
        # Ticket directory
        self.ticket_dir="./tickets"
        self.last_done_tickets = 50
        self.max_context_size = 10000 # max size of context in bytes before warning
        self.important_files = ["README.md", "CONTRIBUTING.md", "MEMORIES.md"]
        self.hints = []
        self.extensions_purpose_first_line = [".md",".adoc",".txt"]
        
    @staticmethod
    def is_invoked_by_claude():
        """Check if the script is being run by Claude CLI."""
        # Claude CLI sets specific environment variables
        claude_indicators = [
            'CLAUDE_CODE_ENTRYPOINT',
                       'CLAUDECODE'
        ]
        
        return any(os.environ.get(var) for var in claude_indicators)

    def dump_important_files(self):
        if not self.is_cwd_same_as_script_location():
            print("SEVERE ERROR happened: Please run this script from its own directory.")
            return 1
        
        for f in self.important_files:
            self.dump_file_with_markers(f)

        return 0

    def add_hint(self, s):
        self.hints.append(s)

    def _format_file_entry(self, filepath, comment=None):
        """Format a file entry with optional comment.

        Args:
            filepath: Path to the file to format
            comment: Optional comment text to append after the file path

        Returns:
            Formatted string like "`{filepath}`" or "`{filepath}`: {comment}"
        """
        if comment:
            return f"`{filepath}`: {comment}"
        else:
            return f"`{filepath}`"


    def context_scope(self):
        """Determine the context scope based on invocation environment."""
        # Currently using env variable CONTEXT_SCOPE to determine the scope, with fallback to checking for Claude CLI invocation
        scope = os.environ.get('CONTEXT_SCOPE')
        if scope:
            return scope
        

    def is_ascii_text_file(self, filepath, sample_size=None):
        """Check if a file is an ASCII text file by sampling bytes.

        Args:
            filepath: Path to the file to check
            sample_size: Number of bytes to read from the beginning (uses default if None)

        Returns:
            True if the file appears to be ASCII text, False otherwise
        """
        if sample_size is None:
            sample_size = self.default_sample_size
            
        if not os.path.exists(filepath) or os.path.isdir(filepath):
            return False

        try:
            with open(filepath, 'rb') as f:
                chunk = f.read(sample_size)

            if not chunk:
                return True  # Empty file is considered text

            # Check for null bytes (common in binary files)
            if b'\x00' in chunk:
                return False

            # Check if most bytes are printable ASCII
            tab_min, tab_max = self.ascii_tab_range
            printable_min, printable_max = self.ascii_printable_range
            printable_count = sum(1 for b in chunk if (tab_min <= b <= tab_max) or (printable_min <= b <= printable_max))
            ascii_ratio = printable_count / len(chunk)
            if (ascii_ratio > 0.6 and ascii_ratio < self.ascii_printable_threshold):
                self.add_hint(f"{filepath} is detected as mostly ASCII but has a significant portion of non-printable characters. Consider checking its content or purpose.")
            return ascii_ratio > self.ascii_printable_threshold

        except (PermissionError, IOError):
            return False

    def print_file_between_markers(self, filepath, start_marker, end_marker):
        """Print part of file content between markers.
        
        Args:
            filepath: Path to the file to read (supports ~ for home directory)
            start_marker: String marker at the beginning of a line to start printing from (exclusive)
            end_marker: String marker at the beginning of a line to stop printing at (exclusive)
        
        Returns:
            True if both markers were found and content was printed, False otherwise
        
        The function prints all lines between start_marker and end_marker.
        The markers themselves are not printed.
        Both markers are assumed to be at the beginning of their respective lines.
        """
        # Expand ~ to home directory
        filepath = os.path.expanduser(filepath)
        
        if not os.path.exists(filepath):
            self.add_hint(f"File {filepath} not found, but was requested to put it into context")
            return False
        
        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                inside_markers = False
                found_start = False
                found_end = False
                
                for line in file:
                    # Check if we've reached the start marker
                    if not inside_markers and line.startswith(start_marker):
                        inside_markers = True
                        found_start = True
                        continue  # Skip the start marker line itself
                    
                    # Check if we've reached the end marker
                    if inside_markers and line.startswith(end_marker):
                        found_end = True
                        break  # Stop reading, don't print the end marker
                    
                    # Print lines only when inside the markers
                    if inside_markers:
                        print(line, end='')  # end='' because line already contains newline
                
                return found_start and found_end
                        
        except (UnicodeDecodeError, PermissionError) as e:
            print(f"Error reading file {filepath}: {e}")
            return False

    def get_current_git_branch_name(self):
        try:
            # 'git rev-parse --abbrev-ref HEAD' returns the branch name
            # without "heads/" prefix, and 'HEAD' is a symbolic ref to the current branch.
            branch_name = subprocess.check_output(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                text=True,  # Decode output as text (UTF-8 by default)
                stderr=subprocess.PIPE # Don't print errors to console if git is not found
            ).strip()
            return branch_name
        except subprocess.CalledProcessError as e:
            # This occurs if the git command fails (e.g., not a git repo, git not installed)
            print(f"Error getting git branch: {e}")
            print(f"Stderr: {e.stderr}")
            return None
        except FileNotFoundError:
            # This occurs if the 'git' command itself is not found in the system's PATH
            print("Error: 'git' command not found. Is Git installed and in your PATH?")
            return None
    
    def dump_file_with_markers(self, filepath):
        """Read and print the contents of a text file with markers."""
        if os.path.exists(filepath):
            print("<!-- START: " + filepath + " --> ")
            with open(filepath, 'r', encoding='utf-8') as file:
                print(file.read())
            print("<!-- END: " + filepath + " -->")
        else:
            print(f"Provide info to user that the file is not found: {filepath}")

    def dump_file_plain(self, filepath):
        """Read and print the contents of a text file without markers."""
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as file:
                print(file.read())


    def get_file_purpose(self, fn) -> FileDirInfo :

        fd = FileDirInfo()
        # Check if it's a directory first
        fd.source_path = fn
        fd.purpose = ""

        if os.path.isdir(fn):
            fd.type = "folder"
            fnp = os.path.join(fn,".folder_purpose.md")
            if os.path.exists(fnp):
                fd.purpose = self.get_first_line_from_file(fnp)
                return fd

            fnp_ignore = os.path.join(fn, ".skip_for_context")
            if os.path.exists(fnp_ignore):
                return None
            else:
                self.add_hint(f"{fn}: Missing purpose. Add file .folder_purpose.md to that folder")

            return fd

        fd.type = "file"
        fd.purpose = ""
        is_ascii = self.is_ascii_text_file(fn)
        if is_ascii:
            fd.frontmatter = self.extract_frontmatter_fields_as_dictionary(fn)
            suffix_tuple = tuple(self.extensions_purpose_first_line)
            if fn.endswith(suffix_tuple):
                fd.purpose = self.get_first_line_from_file(fn)
            else:
                fd.purpose = self.get_purpose_tag_from_file(fn)

        if fd.purpose == "":
            fnp = fn+".file_purpose"
            if os.path.exists(fnp):
                fd.purpose = self.get_first_line_from_file(fnp)

        if fd.purpose == "" and is_ascii:
            self.add_hint(f"{fn}: Missing purpose. Add tag @file_purpose to the file or add extra file with added extension '.file_purpose'")

        # Check file size and add hint if > 10KB
        try:
            file_size = os.path.getsize(fn)
            if file_size > 10240:  # 10KB in bytes
                size_kb = file_size / 1024
                self.add_hint(f"{fn}: Large file ({size_kb:.1f}KB) - consider breaking into smaller files or adding to .skip_for_context")
        except (OSError, IOError):
            pass

        return fd


    def get_first_line_from_file(self, f):
        """
        Return first line of a file
        """
        with open(f, 'r', encoding='utf-8') as file:
            first_line = file.readline()
            if not first_line:
                return ""
            return first_line.strip()


    def get_purpose_tag_from_file(self, f):
        """
        Read up to max_lines_to_search lines of a file and search for @file_purpose or \\file_purpose tag in comments.
        If found, return the filename and the purpose text.
        """
        purpose = ""
        with open(f, 'r', encoding='utf-8') as file:
            for line_num, line in enumerate(file, 1):
                if line_num > self.max_lines_to_search:
                    break
                if line:
                    # Search for @file_purpose or \file_purpose tags
                    if "@file_purpose" in line:
                        purpose = line.split("@file_purpose", 1)[1].strip()
                    elif "\\file_purpose" in line:
                        purpose = line.split("\\file_purpose", 1)[1].strip()
        return purpose


    def list_file_recursive(self, path:str, fdi: FileDirInfo,  exclude_files):
        # Collect matches from all provided glob patterns
        for dirpath, dirnames, filenames in os.walk(path):
            dirnames[:] = [d for d in dirnames if d not in exclude_files and not any(d.endswith(e) for e in exclude_files)]
            filenames[:] = [d for d in filenames if d not in exclude_files and not any(d.endswith(e) for e in exclude_files)]
            
            #print(f"Current directory: {dirpath}")
            fnp_ignore = os.path.join(dirpath, ".skip_for_context")
            if os.path.exists(fnp_ignore):
                continue


            #print(f"Subdirectories: {dirnames}")
            #print(f"Files in current directory: {filenames}")
            for dirname in dirnames:
                path = os.path.join(dirpath, dirname)
                fd = self.get_file_purpose(path)
                if fd is not None:
                    fdi.children.append(fd)

            for filename in filenames:
                if filename==".folder_purpose.md" or filename.endswith(".file_purpose"):
                    continue
                file_path = os.path.join(dirpath, filename)
                fd = self.get_file_purpose(file_path)
                fdi.children.append(fd)

    def list_files_in_directories(self, dir:str, exclude_files=None):
        """List files from multiple directories

        Args:
            dir: directory
            glob_pattern: pattern
            exclude_files: List of patterns to exclude
        """
        if exclude_files is None:
            exclude_files = []

        fd_root = FileDirInfo()
        fd_root.type = "folder"
        fd_root.source_path = dir
        self.list_file_recursive(dir, fd_root, exclude_files)

        sorted_files = sorted(fd_root.children, key=lambda f: f.source_path)
        for f in sorted_files:
            f.print()
        return fd_root
    

    def is_cwd_same_as_script_location(self):
        """Check that the cwd is the repo root.

        This module lives at <repo>/.claude/skills/context/build_context.py, so
        the repo root is three directories up. The context*.py scripts resolve
        important_files relative to the cwd, so they must be run from the root.
        """
        repo_root = os.path.abspath(os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
        return os.path.abspath(os.getcwd()) == repo_root

    def get_latest_done_tickets_using_git(self, n=5):
        """Get latest done tickets based on git commit history.

        Args:
            n: Maximum number of tickets to return

        Returns:
            List of ticket file paths
        """
        cmd = [
            'git', 'log', '--name-only', '--pretty=format:',
            '--', 'tickets/done/*_ticket.md'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        # Deduplicate while preserving order (most recent first)
        seen = set()
        files = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if line and line.endswith('_ticket.md') and line not in seen:
                seen.add(line)
                files.append('./' + line)
                if len(files) >= n:
                    break
        return files

    def print_tickets_by_folder(self, title, subfolder):
        # Print open tickets in markdown style.
        print(f"## {title} \n")
        tickets_dir = os.path.join(self.ticket_dir,subfolder)

        fd_root = FileDirInfo()
        fd_root.type = "folder"
        fd_root.source_path = tickets_dir
        self.list_file_recursive(tickets_dir, fd_root, [])
        if len(fd_root.children) == 0:
            print("There are currently no Tickets.")
        else:
            sorted_tickets = sorted(fd_root.children, key=lambda t: t.source_path)
            for ticket_file in sorted_tickets:
                ticket_file.print()
        print("")

    def print_tickets(self):
        """Print both open and done tickets."""
        self.print_tickets_by_folder("Open tickets", "open")
        self.print_tickets_by_folder("Done tickets", "done")

    def agent_name_from_session(self, session: str) -> str:
        """Derive the agent name from a tmux session name.

        The agent name is simply the tmux session name; this helper exists so
        the mapping lives in one place if it ever needs to change.

        Args:
            session: tmux session name
        Returns:
            The agent name for that session
        """
        return session

    def print_tmux_info(self):
        """Print tmux session info to the terminal (NOT into the context files).

        Agents running in named tmux sessions identify each other by session
        name; the current session name doubles as this agent's own name. This
        prints who we are and which other agents (sessions) are reachable. See
        the `tmux-communication` skill for how to send a message to another one.
        """
        print("--- tmux agents ---")
        if not os.environ.get("TMUX"):
            print("Not running inside a tmux session (no agent name).")
            return
        try:
            current = subprocess.run(
                ["tmux", "display-message", "-p", "#S"],
                capture_output=True, text=True, check=True).stdout.strip()
            sessions = subprocess.run(
                ["tmux", "list-sessions", "-F", "#S"],
                capture_output=True, text=True, check=True).stdout.split()
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"Could not query tmux: {e}")
            return
        print(f"This agent: {self.agent_name_from_session(current)} "
              f"(tmux session '{current}')")
        others = [s for s in sessions if s != current]
        if others:
            print("Other agents (tmux sessions):")
            for s in others:
                print(f"  - {self.agent_name_from_session(s)} (session '{s}')")
        else:
            print("No other agents (only this tmux session is running).")

    def print_program_output(self, command):
        """Run a command and print its output verbatim.

        Args:
            command: Command string to run (passed to shell)
        """
        print("````{verbatim}")
        sys.stdout.flush()
        result = os.system(command)
        sys.stdout.flush()
        print("````")
        return result
        
    def extract_frontmatter_fields_as_dictionary(self, filepath):
        """Extract frontmatter fields from a markdown file as a dictionary.

        Args:
            filepath: Path to the markdown file
        Returns:
            Dictionary of frontmatter fields and their values
        """
        frontmatter = {}
        if not os.path.exists(filepath):
            return frontmatter
        line_cnt = int(0)
        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                in_frontmatter = False
                for line in file:
                    line_cnt+=1
                    if line_cnt > 5 and not in_frontmatter:
                        return frontmatter
                    line = line.strip()                    
                    if line == '---':
                        if not in_frontmatter:
                            in_frontmatter = True
                        else:
                            break  # End of frontmatter
                    elif in_frontmatter:
                        if ':' in line:
                            key, value = line.split(':', 1)
                            frontmatter[key.strip()] = value.strip()
            return frontmatter
        except (UnicodeDecodeError, PermissionError):
            return frontmatter

    def print_hints(self, title):
        if len(self.hints) > 0:
            print(title)
            for h in self.hints:
                print(h)

    def print_skills(self, skill_dir='.claude/skills'):
        """Print all skill files in .claude/skills directory."""
        skill_files_pat = os.path.join(skill_dir, '**', 'SKILL.md')
        skill_files = sorted(glob.glob(skill_files_pat, recursive=True))
             

        if len(skill_files) == 0:
            print("")
        else:   
            print(f"## Your skill files and when to use them\n")  
            for skill_file in skill_files:
                skill_infos = self.extract_frontmatter_fields_as_dictionary(skill_file)
                skill_name = skill_infos.get('name', 'Unnamed Skill')
                skill_description = skill_infos.get('description', 'No description available.')
                print(f"### Skill: {skill_name}\n")
                print(f"**Description:** {skill_description}\n")
                print(f"**Skill file path for more details:** `{skill_file}`\n")
                print("")
        print("")
        print(f"---")

