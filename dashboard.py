#!/usr/bin/env python3
"""
Git Control Dashboard
A Termux-native interactive git workflow tool.
"""

import subprocess
import sys
import os
import re
import shutil
import shlex
import json
import getpass
import py_compile
import tempfile
import difflib
from collections import defaultdict
from datetime import datetime, timezone

import registry


class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    PURPLE = "\033[38;5;141m"
    GRAY = "\033[38;5;102m"
    GRAY_DIM = "\033[38;5;243m"
    GRAY_FAINT = "\033[38;5;241m"
    GREEN = "\033[38;5;118m"
    YELLOW = "\033[38;5;226m"
    GOLD = "\033[38;5;220m"
    BLUE = "\033[38;5;81m"
    RED = "\033[38;5;196m"
    PINK = "\033[38;5;171m"
    CYAN = "\033[38;5;51m"
    ORANGE = "\033[38;5;208m"


class CmdResult:
    __slots__ = ("out", "err", "code")

    def __init__(self, out, err, code):
        self.out = out
        self.err = err
        self.code = code

    @property
    def ok(self):
        return self.code == 0

    def __bool__(self):
        return self.ok


def run(args, input_text=None):
    try:
        res = subprocess.run(
            args,
            capture_output=True,
            text=True,
            input=input_text,
        )
        return CmdResult(res.stdout.strip(), res.stderr.strip(), res.returncode)
    except FileNotFoundError as e:
        return CmdResult("", str(e), 127)


def git(*args, input_text=None):
    return run(["git", *args], input_text=input_text)


CONVENTIONAL_TYPES = ["feat", "fix", "chore", "docs", "refactor", "style", "test", "perf"]

TYPE_TITLES = {
    "feat": "✨ Features",
    "fix": "🐛 Bug Fixes",
    "chore": "🧹 Chores",
    "docs": "📝 Documentation",
    "refactor": "♻️  Refactoring",
    "style": "💅 Styling",
    "test": "🧪 Tests",
    "perf": "⚡ Performance",
    "other": "🔧 Other",
}

ACTION_LABELS = {
    "1": "👀 Status", "2": "🔍 Diff (full)", "2s": "📊 Diff stat summary",
    "3": "💾 Commit", "3a": "✏️  Amend last commit", "3b": "⏪ Undo last commit", "20": "⚡ Quick WIP commit",
    "4": "🔀 Merge feature → dev", "5": "🏆 Milestone merge → main",
    "6": "🌱 New feature branch", "7": "🔁 Switch branch",
    "8": "🧹 Cleanup merged branches", "9": "🗑️  Delete branch",
    "28": "📅 Branch staleness report", "27": "🔮 Switch project",
    "34": "🔬 Show commit", "35": "👁️  Blame file", "37": "📄 File history",
    "26": "🔎 Commit search", "16": "🌐 Commit graph", "15": "📜 Generate changelog",
    "32": "🏷️  Tag management", "17": "⬆️  Push to remote", "18": "⬇️  Pull from remote",
    "19": "🔄 Fetch + prune", "36": "🌐 Remote management",
    "11": "📦 Stash changes", "38": "🔍 Stash list/inspect/drop", "12": "📤 Pop stash",
    "33": "🧹 Restore file", "13": "🩹 Resolve conflicts", "13a": "🛑 Abort operation", "25": "📄 .gitignore quick-add", "25a": "🙈 Untrack file",
    "14": "🪓 Squash commits", "22": "🔃 Interactive rebase", "23": "🍒 Cherry-pick",
    "24": "🌲 Worktree add", "10": "📝 Edit file", "10a": "🩹 Apply text patch",
    "30": "🔑 GitHub sign-in", "31": "🆕 Git init", "29": "🏥 Fix detached HEAD",
}

CATEGORIES = {
    "W": ("📋 WORKFLOW", C.GOLD, ["1", "2", "2s", "3", "3a", "3b", "20", "4", "5"]),
    "B": ("🌿 BRANCHING", C.GREEN, ["6", "7", "8", "9", "28", "27"]),
    "I": ("🔬 INSPECT", C.CYAN, ["34", "35", "37", "26", "16", "15"]),
    "T": ("🏷️  TAGS & REMOTE", C.GOLD, ["32", "17", "18", "19", "36"]),
    "S": ("📦 STASH & RECOVERY", C.PINK, ["11", "38", "12", "33", "13", "13a", "25", "25a"]),
    "A": ("⚙️  ADVANCED", C.PINK, ["14", "22", "23", "24", "10", "10a"]),
    "U": ("🔐 SETUP", C.PINK, ["30", "31", "29"]),
}

BANNER_LINES = [
    "██████╗  ██╗ ███████╗",
    "██╔════╝ ██║ ╚══██╔══╝",
    "██║  ██████╗    ██║   ",
    "██║   ██║██║    ██║   ",
    "╚██████╔╝██║    ██║   ",
    " ╚═════╝ ╚═╝    ╚═╝   ",
]

BOX_WIDTH = 44
DASHES = "─" * (BOX_WIDTH - 2)

CONFIG_PATH = os.path.join(".git", "dashboard_config.json")


# ── Config persistence ────────────────────────────────────────────────────────

class DashboardConfig:
    def __init__(self):
        self.data = {}
        self._load()

    def _load(self):
        try:
            with open(CONFIG_PATH) as f:
                self.data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.data = {}

    def _save(self):
        try:
            with open(CONFIG_PATH, "w") as f:
                json.dump(self.data, f, indent=2)
        except OSError:
            pass  # silently skip if .git doesn't exist yet

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        self._save()


# ── Helpers ───────────────────────────────────────────────────────────────────

def sanitize_branch_name(name):
    name = name.strip().lower()
    name = re.sub(r"\s+", "-", name)
    name = re.sub(r"[^a-z0-9-]", "", name)
    name = re.sub(r"-+", "-", name)
    return name.strip("-")


def is_valid_branch_name(name):
    if not name:
        return False
    res = run(["git", "check-ref-format", "--branch", name])
    return res.ok


def copy_to_clipboard(text):
    if shutil.which("termux-clipboard-set"):
        run(["termux-clipboard-set"], input_text=text)
        return True
    return False


def toast(message, color=C.GREEN, icon="✅"):
    if shutil.which("termux-toast"):
        run(["termux-toast", "-s", message])
    print(f"{color}{icon} {message}{C.RESET}")


def pause():
    input(f"\n{C.GRAY_FAINT}[ ⏎ Press Enter to return to dashboard ]{C.RESET}")


def confirm(prompt):
    return input(f"{prompt} (y/n): ").strip().lower() == "y"


def offer_clipboard(text, label="output"):
    if not text:
        return
    if copy_to_clipboard(text):
        print(f"{C.GRAY_DIM}📋 ({label} copied to clipboard){C.RESET}")


def colorize_diff(diff_text):
    """Re-colorize diff output line by line (git strips color under capture_output)."""
    lines = []
    for line in diff_text.split("\n"):
        if line.startswith("+") and not line.startswith("+++"):
            lines.append(f"{C.GREEN}{line}{C.RESET}")
        elif line.startswith("-") and not line.startswith("---"):
            lines.append(f"{C.RED}{line}{C.RESET}")
        elif line.startswith("@@"):
            lines.append(f"{C.CYAN}{line}{C.RESET}")
        elif line.startswith("diff ") or line.startswith("index ") or line.startswith("---") or line.startswith("+++"):
            lines.append(f"{C.GRAY_DIM}{line}{C.RESET}")
        else:
            lines.append(line)
    return "\n".join(lines)


def _path_matches_scope(filepath, scope):
    """
    Return True if filepath contains scope as a substring (case-insensitive).
    Tries full path first; if the full path has no directory component,
    falls back to matching against just the dirname.
    """
    filepath_lower = filepath.lower()
    scope_lower = scope.lower()
    if scope_lower in filepath_lower:
        return True
    dirname = os.path.dirname(filepath_lower)
    if dirname and scope_lower in dirname:
        return True
    return False


def _check_scope_mismatch(scope, threshold=0.5):
    """
    Compare scope string against staged+unstaged changed file paths.
    Returns (mismatched_files, total_files) — both lists of strings.
    If scope is empty, skip the check entirely (return None, None).
    """
    if not scope:
        return None, None

    diff_names = git("diff", "--name-only", "HEAD")
    untracked = git("ls-files", "--others", "--exclude-standard")

    all_files = []
    if diff_names.out:
        all_files += [f for f in diff_names.out.split("\n") if f]
    if untracked.out:
        all_files += [f for f in untracked.out.split("\n") if f]

    if not all_files:
        return None, None

    mismatched = [f for f in all_files if not _path_matches_scope(f, scope)]
    return mismatched, all_files


def _is_branch_merged(branch_name):
    """
    Return True if branch_name is merged into dev OR main.
    Checks both protected branches so hotfix-style branches merged
    only into main aren't incorrectly flagged as unmerged.
    """
    merged_dev = git("branch", "--merged", "dev", "--list", branch_name)
    if merged_dev.out:
        return True
    merged_main = git("branch", "--merged", "main", "--list", branch_name)
    return bool(merged_main.out)


def _lint_python_files():
    """
    Run py_compile over every tracked .py file.
    Returns list of (filepath, error_string) for failures.
    """
    tracked = git("ls-files", "--cached", "--others", "--exclude-standard")
    py_files = [f for f in tracked.out.split("\n") if f.endswith(".py") and os.path.isfile(f)]
    errors = []
    for fpath in py_files:
        try:
            py_compile.compile(fpath, doraise=True)
        except py_compile.PyCompileError as e:
            errors.append((fpath, str(e)))
    return errors


# ── Dashboard ─────────────────────────────────────────────────────────────────

class Dashboard:
    def __init__(self):
        self.branch = "unknown"
        self.dirty = False
        self.ahead = 0
        self.behind = 0
        self.in_repo = False
        self.detached = False
        self.empty_branch = False   # feature branch with 0 commits ahead of dev
        self.recent_commits = []    # list of strings, last 3 one-liners
        self.config = DashboardConfig()

    def refresh(self):
        check = run(["git", "rev-parse", "--is-inside-work-tree"])
        self.in_repo = check.ok and check.out == "true"
        if not self.in_repo:
            self.branch = "unknown"
            self.dirty = False
            self.ahead = self.behind = 0
            self.detached = False
            self.empty_branch = False
            self.recent_commits = []
            return

        b = git("branch", "--show-current")
        if b.ok and b.out:
            self.branch = b.out
            self.detached = False
        else:
            self.branch = "(detached)"
            self.detached = True

        status = git("status", "-s")
        self.dirty = bool(status.out)

        self.ahead, self.behind = 0, 0
        upstream = git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
        if upstream.ok:
            counts = git("rev-list", "--left-right", "--count", "@{u}...HEAD")
            if counts.ok:
                parts = counts.out.split()
                if len(parts) == 2:
                    self.behind, self.ahead = int(parts[0]), int(parts[1])

        # Empty branch detection (feature branch, 0 commits ahead of dev)
        self.empty_branch = False
        if self.branch not in ("main", "dev", "unknown", "(detached)"):
            ahead_dev = git("rev-list", "--count", "dev..HEAD")
            if ahead_dev.ok:
                try:
                    self.empty_branch = int(ahead_dev.out) == 0
                except ValueError:
                    pass

        # Recent commits mini-view (last 3)
        log = git("log", "--oneline", "-3")
        if log.ok and log.out:
            self.recent_commits = log.out.split("\n")
        else:
            self.recent_commits = []

    def require_repo(self):
        if not self.in_repo:
            print(f"{C.RED}❌ Error: Not inside a git repository.{C.RESET}")
            pause()
            return False
        return True

    def _offer_detached_head_branch(self):
        """Prompt to create a new branch from detached HEAD position."""
        print(f"\n{C.YELLOW}Would you like to create a branch here to save your work?{C.RESET}")
        if confirm("Create branch from current detached HEAD?"):
            name = input("New branch name: ").strip()
            sanitized = sanitize_branch_name(name)
            if sanitized and is_valid_branch_name(sanitized):
                res = git("switch", "-c", sanitized)
                print(res.out or res.err)
                if res.ok:
                    toast(f"Created and switched to '{sanitized}'", icon="🌿")
            else:
                print(f"{C.RED}❌ Invalid branch name.{C.RESET}")

    def _offer_stash_and_continue(self):
        """
        Offer to stash dirty changes inline. Returns True if stash succeeded
        (caller can continue), False if user declined or stash failed.
        """
        print(f"{C.YELLOW}⚠️  Working tree is dirty.{C.RESET}")
        if confirm("Stash changes now and continue?"):
            res = git("stash", "push", "-m", "dashboard-auto-stash")
            if res.ok:
                toast("Stashed! Continuing…", icon="📦")
                self.dirty = False
                return True
            else:
                print(f"{C.RED}❌ Stash failed: {res.err}{C.RESET}")
                return False
        return False

    def print_header(self):
        print('\033c', end='')
        self.refresh()

        if self.branch == "main":
            b_color, b_icon = C.GREEN, "🌳"
        elif self.branch == "dev":
            b_color, b_icon = C.YELLOW, "🛠️"
        elif self.branch == "(detached)":
            b_color, b_icon = C.RED, "⚠️ "
        else:
            b_color, b_icon = C.BLUE, "🌿"

        status_text = f"{C.RED}🔴 DIRTY{C.RESET}" if self.dirty else f"{C.GREEN}🟢 CLEAN{C.RESET}"

        print()
        for line in BANNER_LINES:
            print(f"  {C.BOLD}{C.PURPLE}{line}{C.RESET}")
        print(f"  {C.GRAY}{'─' * 23}{C.RESET}")
        print(f"  {C.DIM}{C.PURPLE}🔮 C O N T R O L   D A S H B O A R D{C.RESET}")
        print()

        if not self.in_repo:
            print(f"{C.GRAY_DIM} ⚠️  Not inside a git repository{C.RESET}\n")
            return

        # ── Detached HEAD banner ──────────────────────────────────────────────
        if self.detached:
            sha = git("rev-parse", "--short", "HEAD")
            sha_str = sha.out if sha.ok else "unknown"
            print(f"{C.RED}{C.BOLD}  ╔══════════════════════════════════════╗{C.RESET}")
            print(f"{C.RED}{C.BOLD}  ║  ⚠️  DETACHED HEAD  @ {sha_str:<16} ║{C.RESET}")
            print(f"{C.RED}{C.BOLD}  ║  You are not on any branch!          ║{C.RESET}")
            print(f"{C.RED}{C.BOLD}  ║  Use option 29 to create a branch.   ║{C.RESET}")
            print(f"{C.RED}{C.BOLD}  ╚══════════════════════════════════════╝{C.RESET}")
            print()

        sync = ""
        if self.ahead or self.behind:
            sync = f" │ {C.CYAN}↑{self.ahead} ↓{self.behind}{C.RESET}"
        info = f" {b_icon} Branch: {b_color}{self.branch}{C.RESET} │ {status_text}{sync}"
        print(f"{C.GRAY_DIM}{info}{C.RESET}")

        # ── Empty branch hint ─────────────────────────────────────────────────
        if self.empty_branch:
            print(f"{C.GRAY_DIM}  💤 No commits ahead of dev — branch is empty{C.RESET}")

        # ── Recent commits mini-view ──────────────────────────────────────────
        if self.recent_commits:
            print(f"{C.GRAY_DIM}  {'─' * 40}{C.RESET}")
            for commit in self.recent_commits:
                # sha in dim gold, message in gray
                parts = commit.split(" ", 1)
                sha_part = parts[0] if parts else ""
                msg_part = parts[1] if len(parts) > 1 else ""
                print(f"{C.GRAY_DIM}  {C.GOLD}{sha_part}{C.RESET} {C.GRAY_FAINT}{msg_part}{C.RESET}")
        print()

    def print_menu(self):
        usage = self.config.get("action_usage", {})
        top = sorted(usage.items(), key=lambda kv: kv[1], reverse=True)[:4]
        print(f"{C.GRAY}┌{DASHES}┐{C.RESET}")
        if top:
            print(f"{C.GRAY}│{C.RESET} {C.GOLD}⭐ FAVORITES{C.RESET}")
            for choice, _ in top:
                label = ACTION_LABELS.get(choice, choice)
                print(f"{C.GRAY}│{C.RESET}  {C.BLUE}{choice:>3}.{C.RESET} {label}")
            print(f"{C.GRAY}│{C.RESET}")
        print(f"{C.GRAY}│{C.RESET} {C.GOLD}CATEGORIES{C.RESET}")
        for key, (title, color, _) in CATEGORIES.items():
            print(f"{C.GRAY}│{C.RESET}  {C.BLUE}{key}.{C.RESET}  {color}{title}{C.RESET}")
        print(f"{C.GRAY}│{C.RESET}")
        print(f"{C.GRAY}│{C.RESET}  {C.BLUE}21.{C.RESET} {C.RED}🚪 Exit{C.RESET}")
        print(f"{C.GRAY}└{DASHES}┘{C.RESET}")

    def print_submenu(self, key):
        title, color, numbers = CATEGORIES[key]
        print(f"{C.GRAY}┌{DASHES}┐{C.RESET}")
        print(f"{C.GRAY}│{C.RESET} {color}{title}{C.RESET}")
        for num in numbers:
            label = ACTION_LABELS.get(num, num)
            print(f"{C.GRAY}│{C.RESET}  {C.BLUE}{num:>3}.{C.RESET} {label}")
        print(f"{C.GRAY}│{C.RESET}")
        print(f"{C.GRAY}│{C.RESET}  {C.BLUE}b.{C.RESET}  {C.GRAY_DIM}← Back{C.RESET}")
        print(f"{C.GRAY}└{DASHES}┘{C.RESET}")

    # ── Existing actions (unchanged) ──────────────────────────────────────────

    def action_status(self):
        print(git("status").out)
        pause()

    def action_diff(self):
        diff = git("diff", "HEAD")
        untracked = git("ls-files", "--others", "--exclude-standard")
        if not diff.out and not untracked.out:
            print(f"{C.GREEN}✅ No changes detected against HEAD.{C.RESET}")
        else:
            if diff.out:
                print(colorize_diff(diff.out))
            if untracked.out:
                print(f"{C.YELLOW}📄 Untracked files:{C.RESET}")
                print(untracked.out)
        pause()

    def _prompt_conventional_type(self):
        while True:
            ctype = input(f"Type ({'/'.join(CONVENTIONAL_TYPES)}): ").strip().lower()
            if ctype in CONVENTIONAL_TYPES:
                return ctype
            print(f"{C.RED}❌ Invalid type. Choose one of: {', '.join(CONVENTIONAL_TYPES)}{C.RESET}")

    def action_commit(self):
        if not self.require_repo():
            return
        is_merging = os.path.exists(os.path.join(".git", "MERGE_HEAD"))

        if self.branch in ("main", "dev") and not is_merging:
            print(f"{C.RED}❌ Error: GitFlow violation. Cannot commit directly to {self.branch}.{C.RESET}")
            print("Use Option 11 to stash, then Option 6 to create a feature branch.")
            pause()
            return

        print(f"\n{C.YELLOW}🔍 --- Auto-verifying changes before commit ---{C.RESET}")
        diff = git("diff", "HEAD")
        untracked = git("ls-files", "--others", "--exclude-standard")

        if not diff.out and not untracked.out and not is_merging:
            print(f"{C.RED}❌ No changes detected against HEAD. Nothing to commit.{C.RESET}")
            pause()
            return

        if diff.out:
            print(colorize_diff(diff.out))
        if untracked.out:
            print(f"{C.YELLOW}📄 Untracked files (will be added):{C.RESET}")
            print(untracked.out)

        if is_merging:
            print(f"{C.BLUE}🔀 Merge in progress detected. Finalizing merge...{C.RESET}")

        ctype = self._prompt_conventional_type()

        last_scope = self.config.get("last_scope", "")
        scope_prompt = f"Scope (e.g., {last_scope}): " if last_scope else "Scope (e.g., dashboard): "
        scope_input = input(scope_prompt).strip()
        scope = scope_input if scope_input else last_scope

        # ── Scope mismatch check ──────────────────────────────────────────────
        if scope and not is_merging:
            mismatched, all_files = _check_scope_mismatch(scope)
            if mismatched and all_files:
                mismatch_ratio = len(mismatched) / len(all_files)
                print(f"\n{C.ORANGE}⚠️  Scope mismatch warning!{C.RESET}")
                print(f"{C.ORANGE}   Scope entered: '{scope}'{C.RESET}")
                print(f"{C.ORANGE}   {len(mismatched)}/{len(all_files)} files don't match this scope:{C.RESET}")
                for f in mismatched:
                    print(f"{C.ORANGE}     - {f}{C.RESET}")
                if not confirm("Scope looks right anyway — continue?"):
                    print(f"{C.GRAY_DIM}Commit aborted. Fix scope or use a broader one.{C.RESET}")
                    pause()
                    return

        desc = input("Description: ").strip()
        if not desc:
            print(f"{C.RED}❌ Description cannot be empty. Aborting commit.{C.RESET}")
            pause()
            return

        msg = f"{ctype}({scope}): {desc}" if scope else f"{ctype}: {desc}"

        print(f"\n{C.GRAY_DIM}❯ git add . && git commit -m {shlex.quote(msg)}{C.RESET}")
        git("add", ".")
        res = git("commit", "-m", msg)
        print(res.out or res.err)
        if res.ok:
            if scope:
                self.config.set("last_scope", scope)
            toast("Commit created.", icon="💾")
        pause()

    def action_quick_wip(self):
        if not self.require_repo():
            return
        if self.branch in ("main", "dev"):
            print(f"{C.RED}❌ Error: Refusing quick WIP commit on {self.branch}.{C.RESET}")
            pause()
            return
        diff = git("diff", "HEAD")
        untracked = git("ls-files", "--others", "--exclude-standard")
        if not diff.out and not untracked.out:
            print(f"{C.RED}❌ No changes to commit.{C.RESET}")
            pause()
            return
        msg = "chore(wip): snapshot"
        git("add", ".")
        res = git("commit", "-m", msg)
        print(res.out or res.err)
        if res.ok:
            toast("WIP snapshot committed.", icon="⚡")
        pause()

    def action_merge_to_dev(self):
        if not self.require_repo():
            return
        if self.branch in ("main", "dev"):
            print(f"{C.RED}❌ Error: Must be on a feature branch to merge to dev.{C.RESET}")
            pause()
            return
        feature = self.branch
        git("switch", "dev")
        res = git("merge", "--no-ff", feature)
        print(res.out or res.err)
        if "CONFLICT" in (res.out + res.err):
            print(f"{C.RED}💥 Merge conflict detected! Use Option 13 to resolve.{C.RESET}")
            pause()
            return
        elif res.ok:
            toast(f"Merged {feature} into dev.", icon="🔀")
            pause()
            if confirm(f"\n🗑️  Delete feature branch '{feature}' now that it's merged?"):
                del_res = git("branch", "-d", feature)
                if del_res.ok:
                    print(f"{C.GREEN}🗑️  Deleted {feature}{C.RESET}")
                else:
                    print(f"{C.RED}❌ Failed to delete {feature}: {del_res.err}{C.RESET}")
                pause()
            return
        pause()

    def action_milestone_merge(self):
        if not self.require_repo():
            return
        git("switch", "main")
        res = git("merge", "--no-ff", "dev")
        print(res.out or res.err)
        if res.ok:
            tag = input("\n🏷️  Create a release tag for this milestone? (e.g., v1.0.0, blank to skip): ").strip()
            if tag:
                if run(["git", "check-ref-format", "refs/tags/" + tag]).ok:
                    git("tag", "-a", tag, "-m", f"Release {tag}")
                    toast(f"Tagged release: {tag}", icon="🏷️")
                else:
                    print(f"{C.RED}❌ Invalid tag name, skipping.{C.RESET}")
        pause()

    def action_new_feature_branch(self):
        if not self.require_repo():
            return
        # ── Stash safety ──────────────────────────────────────────────────────
        if self.dirty:
            if not self._offer_stash_and_continue():
                pause()
                return
        git("switch", "dev")
        name = input("🌱 Feature branch name: ").strip()
        sanitized = sanitize_branch_name(name)
        if not sanitized or not is_valid_branch_name(sanitized):
            print(f"{C.RED}❌ Error: Invalid branch name.{C.RESET}")
            pause()
            return
        existing = git("branch", "--list", sanitized)
        if existing.out:
            print(f"{C.RED}❌ Error: Branch '{sanitized}' already exists.{C.RESET}")
            pause()
            return
        print(f"Creating branch: {C.BLUE}{sanitized}{C.RESET}")
        res = git("switch", "-c", sanitized)
        print(res.out or res.err)
        pause()

    def action_switch_branch(self):
        if not self.require_repo():
            return
        # ── Stash safety ──────────────────────────────────────────────────────
        if self.dirty:
            if not self._offer_stash_and_continue():
                pause()
                return
        branches = git("branch")
        print(f"{C.YELLOW}🌿 Available branches:{C.RESET}")
        print(branches.out)
        name = input("Switch to branch: ").strip()
        if name:
            res = git("switch", name)
            print(res.out or res.err)
        pause()

    def action_cleanup_branches(self):
        if not self.require_repo():
            return
        git("switch", "dev")
        merged = git("branch", "--merged")
        branches = [b.strip().lstrip("* ") for b in merged.out.split("\n") if b.strip()]
        safe = [b for b in branches if b not in ("main", "dev", "")]

        if not safe:
            print(f"{C.GREEN}✅ No merged feature branches found to clean up.{C.RESET}")
        else:
            print(f"{C.YELLOW}🧹 Merged branches found:{C.RESET}")
            for b in safe:
                print(f" - {b}")
            if confirm("\nDelete these branches?"):
                for b in safe:
                    res = git("branch", "-d", b)
                    if res.ok:
                        print(f"{C.GREEN}🗑️  Deleted {b}{C.RESET}")
                    else:
                        print(f"{C.RED}❌ Failed to delete {b}: {res.err}{C.RESET}")
        pause()

    def action_delete_branch(self):
        if not self.require_repo():
            return
        branches_res = git("branch")
        all_branches = [b.strip().lstrip("* ") for b in branches_res.out.split("\n") if b.strip()]
        deletable = [b for b in all_branches if b not in ("main", "dev")]

        if not deletable:
            print(f"{C.GREEN}No deletable branches (main/dev are protected).{C.RESET}")
            pause()
            return

        print(f"{C.YELLOW}🌿 Branches:{C.RESET}")
        for b in deletable:
            tag = f"{C.GREEN}(merged){C.RESET}" if _is_branch_merged(b) else f"{C.ORANGE}(unmerged){C.RESET}"
            print(f" - {b} {tag}")

        name = input("\nBranch to delete (blank to cancel): ").strip()
        if not name:
            pause()
            return
        if name not in deletable:
            print(f"{C.RED}❌ '{name}' is not a deletable branch (must exist and not be main/dev).{C.RESET}")
            pause()
            return
        if name == self.branch:
            print(f"{C.RED}❌ Cannot delete the branch you're currently on. Switch first (Option 7).{C.RESET}")
            pause()
            return

        if not _is_branch_merged(name):
            if not confirm(f"⚠️  '{name}' is NOT merged into dev or main. Force delete anyway?"):
                pause()
                return
            res = git("branch", "-D", name)
        else:
            if not confirm(f"🗑️  Delete branch '{name}'?"):
                pause()
                return
            res = git("branch", "-d", name)

        if res.ok:
            print(f"{C.GREEN}🗑️  Deleted {name}{C.RESET}")
        else:
            print(f"{C.RED}❌ Failed to delete {name}: {res.err}{C.RESET}")
        pause()

    def action_edit_file(self):
        if not self.require_repo():
            return
        tracked = git("ls-files")
        print(f"{C.YELLOW}📄 Tracked files:{C.RESET}")
        print(tracked.out)
        fname = input("File to edit (or new file name): ").strip()
        if fname:
            editor = "nvim" if shutil.which("nvim") else ("nano" if shutil.which("nano") else "vi")
            subprocess.call([editor, fname])
        pause()

    def action_apply_patch(self):
        if not self.require_repo():
            return
        if self.branch in ("main", "dev", "unknown"):
            print(f"{C.RED}❌ Error: Must be on a feature branch to apply a patch.{C.RESET}")
            pause()
            return

        path = input("File path to patch: ").strip()
        mode = input("Mode — [t]argeted replace or [f]ull rewrite? ").strip().lower()
        if mode not in ("t", "f"):
            print(f"{C.RED}❌ Invalid mode.{C.RESET}")
            pause()
            return

        sentinel = input("Sentinel to end each paste (default EOF): ").strip() or "EOF"

        def read_block(label):
            print(f"{C.GRAY_DIM}Paste {label}, then a line with only '{sentinel}':{C.RESET}")
            lines = []
            while True:
                try:
                    line = input()
                except EOFError:
                    break
                if line.strip() == sentinel:
                    break
                lines.append(line)
            return "\n".join(lines)

        if mode == "t":
            if not os.path.isfile(path):
                print(f"{C.RED}❌ File not found: {path}{C.RESET}")
                pause()
                return
            with open(path, "r") as f:
                original = f.read()

            old = read_block("OLD text block")
            new = read_block("NEW text block")

            count = original.count(old)
            if count == 0:
                print(f"{C.RED}❌ WARNING: anchor not found in {path}. No changes made.{C.RESET}")
                pause()
                return
            if count > 1:
                print(f"{C.YELLOW}⚠️  Anchor appears {count} times — ambiguous. Aborting.{C.RESET}")
                pause()
                return

            patched = original.replace(old, new, 1)
        else:
            original = open(path, "r").read() if os.path.isfile(path) else ""
            patched = read_block("FULL new file content")

        diff_lines = list(difflib.unified_diff(
            original.splitlines(keepends=True),
            patched.splitlines(keepends=True),
            fromfile=path, tofile=path,
        ))
        if not diff_lines:
            print(f"{C.YELLOW}⚠️  No changes detected.{C.RESET}")
            pause()
            return

        print(f"{C.YELLOW}--- Preview ---{C.RESET}")
        for line in diff_lines:
            if line.startswith("+") and not line.startswith("+++"):
                print(f"{C.GREEN}{line.rstrip()}{C.RESET}")
            elif line.startswith("-") and not line.startswith("---"):
                print(f"{C.RED}{line.rstrip()}{C.RESET}")
            else:
                print(line.rstrip())

        if not confirm(f"Write {len(patched.splitlines())} line(s) to {path}?"):
            pause()
            return

        with open(path, "w") as f:
            f.write(patched)

        if path.endswith(".py"):
            try:
                py_compile.compile(path, doraise=True)
                print(f"{C.GREEN}✅ Syntax check passed.{C.RESET}")
            except py_compile.PyCompileError as e:
                print(f"{C.RED}❌ Syntax error after patch: {e}{C.RESET}")
                if confirm("Revert file to pre-patch content?"):
                    with open(path, "w") as f:
                        f.write(original)
                    print(f"{C.YELLOW}↩️  Reverted {path}.{C.RESET}")
                    pause()
                    return

        print(f"{C.GREEN}✅ Patched {path}.{C.RESET}")
        toast(f"Patched {path}", icon="🩹")
        pause()

    def action_stash(self):
        if not self.require_repo():
            return
        res = git("stash", "push", "-m", "dashboard-auto-stash")
        print(res.out or res.err)
        pause()

    def action_stash_pop(self):
        if not self.require_repo():
            return
        res = git("stash", "pop")
        print(res.out or res.err)
        pause()

    def action_abort_operation(self):
        if not self.require_repo():
            return
        git_dir = ".git"
        merge_head = os.path.join(git_dir, "MERGE_HEAD")
        cherry_pick_head = os.path.join(git_dir, "CHERRY_PICK_HEAD")
        rebase_merge = os.path.join(git_dir, "rebase-merge")
        rebase_apply = os.path.join(git_dir, "rebase-apply")

        if os.path.exists(merge_head):
            op_name, abort_args = "merge", ("merge", "--abort")
        elif os.path.exists(cherry_pick_head):
            op_name, abort_args = "cherry-pick", ("cherry-pick", "--abort")
        elif os.path.exists(rebase_merge) or os.path.exists(rebase_apply):
            op_name, abort_args = "rebase", ("rebase", "--abort")
        else:
            print(f"{C.GREEN}✅ No in-progress merge, cherry-pick, or rebase detected.{C.RESET}")
            pause()
            return

        print(f"{C.YELLOW}⚠️  In-progress {op_name} detected.{C.RESET}")
        if not confirm(f"Abort the {op_name}? This discards all in-progress changes from it."):
            pause()
            return

        result = git(*abort_args)
        if result.ok:
            print(f"{C.GREEN}✅ {op_name.capitalize()} aborted. Working tree restored.{C.RESET}")
            toast(f"{op_name.capitalize()} aborted.", icon="🛑")
        else:
            print(f"{C.RED}❌ Abort failed: {result.err}{C.RESET}")
        pause()

    def action_resolve_conflicts(self):
        if not self.require_repo():
            return
        status = git("status", "--porcelain")
        conflicts = []
        for line in status.out.split("\n"):
            if not line:
                continue
            code = line[:2]
            if "U" in code or code in ("AA", "DD"):
                conflicts.append(line[3:])

        if not conflicts:
            print(f"{C.GREEN}✅ No merge conflicts detected.{C.RESET}")
            pause()
            return

        print(f"{C.YELLOW}🩹 Found {len(conflicts)} conflicted file(s).{C.RESET}")
        for f in conflicts:
            print(f" - {f}")
        input("Press Enter to start editing...")

        editor = "nvim" if shutil.which("nvim") else ("nano" if shutil.which("nano") else "vi")
        for f in conflicts:
            print(f"{C.GRAY_DIM}✏️  Editing {f}...{C.RESET}")
            subprocess.call([editor, f])

        print(f"{C.YELLOW}📦 All files edited. Staging changes...{C.RESET}")
        git("add", ".")
        print(f"{C.GREEN}✅ Changes staged! Use Option 3 to finalize the merge commit.{C.RESET}")
        toast("Conflicts staged.", icon="🩹")
        pause()

    def action_undo_commit(self):
        if not self.require_repo():
            return
        if self.branch in ("main", "dev", "unknown"):
            print(f"{C.RED}❌ Error: Must be on a feature branch to undo a commit.{C.RESET}")
            pause()
            return
        log_res = git("log", "-1", "--oneline")
        last_commit = log_res.out if log_res.ok and log_res.out else "(unknown)"
        print(f"{C.YELLOW}⏪ Last commit: {last_commit}{C.RESET}")
        if not confirm("Soft reset HEAD~1? Changes will return to the staging area."):
            pause()
            return
        result = git("reset", "--soft", "HEAD~1")
        if result.ok:
            print(f"{C.GREEN}✅ Last commit undone. Changes are staged.{C.RESET}")
        else:
            print(f"{C.RED}❌ Undo failed: {result.err}{C.RESET}")
        pause()

    def action_squash(self):
        if not self.require_repo():
            return
        if self.branch in ("main", "dev", "unknown"):
            print(f"{C.RED}❌ Error: Must be on a feature branch to squash commits.{C.RESET}")
            pause()
            return
        count_res = git("rev-list", "--count", "dev..HEAD")
        try:
            count = int(count_res.out)
        except ValueError:
            count = 0
        if count <= 1:
            print(f"{C.YELLOW}⚠️  Only {count} commit(s) found. Nothing to squash.{C.RESET}")
            pause()
            return

        print(f"{C.YELLOW}🪓 Found {count} commits to squash into one.{C.RESET}")
        if not confirm("Proceed with soft reset?"):
            pause()
            return

        git("reset", "--soft", "dev")
        print(f"{C.GREEN}✅ Commits squashed to staging area.{C.RESET}")
        ctype = self._prompt_conventional_type()
        scope = input("New scope (e.g., dashboard): ").strip()
        desc = input("New description: ").strip()
        msg = f"{ctype}({scope}): {desc}" if scope else f"{ctype}: {desc}"
        res = git("commit", "-m", msg)
        print(res.out or res.err)
        pause()

    def action_changelog(self):
        log = git("log", "--pretty=format:%H\x01%s")
        if not log.out:
            print(f"{C.RED}❌ No commits found to generate changelog.{C.RESET}")
            pause()
            return

        changelog = "# Changelog\n\nAll notable changes to this project will be documented in this file.\n\n"
        by_type = defaultdict(list)

        for line in log.out.split("\n"):
            if "\x01" not in line:
                continue
            _, msg = line.split("\x01", 1)
            m = re.match(r"(feat|fix|chore|docs|refactor|style|test|perf)(\((.*?)\))?:\s*(.*)", msg)
            if m:
                ctype, _, scope, desc = m.groups()
                scope = scope or "general"
                by_type[ctype].append(f"- **{scope}**: {desc}")
            else:
                by_type["other"].append(f"- {msg}")

        for t in [*CONVENTIONAL_TYPES, "other"]:
            if t in by_type:
                changelog += f"## {TYPE_TITLES.get(t, t.title())}\n\n"
                changelog += "\n".join(by_type[t]) + "\n\n"

        with open("CHANGELOG.md", "w") as f:
            f.write(changelog)
        toast("CHANGELOG.md generated successfully!", icon="📜")
        pause()

    def action_graph(self):
        graph = git("log", "--graph", "--oneline", "--decorate", "--all")
        print(graph.out)
        offer_clipboard(graph.out, "commit graph")
        pause()

    def action_push(self):
        if not self.require_repo():
            return
        if self.branch == "unknown":
            print(f"{C.RED}❌ Error: Not in a git repository.{C.RESET}")
            pause()
            return

        # ── Pre-push lint check ───────────────────────────────────────────────
        print(f"{C.YELLOW}🔍 Running pre-push lint (py_compile)…{C.RESET}")
        lint_errors = _lint_python_files()
        if lint_errors:
            print(f"{C.RED}❌ Lint errors found:{C.RESET}")
            for fpath, err in lint_errors:
                print(f"{C.RED}  {fpath}: {err}{C.RESET}")
            if not confirm("Push anyway despite lint errors?"):
                print(f"{C.GRAY_DIM}Push aborted.{C.RESET}")
                pause()
                return
        else:
            print(f"{C.GREEN}✅ Lint passed.{C.RESET}")

        print(f"{C.YELLOW}⬆️  Pushing {self.branch} to origin...{C.RESET}")
        res = git("push", "-u", "origin", self.branch)
        if not res.ok:
            print(f"{C.RED}❌ Push failed: {res.err}{C.RESET}")
        else:
            print(f"{C.GREEN}✅ Successfully pushed {self.branch}.{C.RESET}")
            if res.out:
                print(res.out)
            toast("Push complete.", icon="⬆️")
        pause()

    def action_pull(self):
        if not self.require_repo():
            return
        print(f"{C.YELLOW}⬇️  Pulling {self.branch} from origin...{C.RESET}")
        res = git("pull", "origin", self.branch)
        if not res.ok:
            print(f"{C.RED}❌ Pull failed: {res.err}{C.RESET}")
        else:
            print(f"{C.GREEN}✅ Successfully pulled {self.branch}.{C.RESET}")
            if res.out:
                print(res.out)
            toast("Pull complete.", icon="⬇️")
        pause()

    def action_fetch_prune(self):
        if not self.require_repo():
            return
        print(f"{C.YELLOW}🔄 Fetching and pruning stale remote-tracking branches...{C.RESET}")
        res = git("fetch", "--prune", "origin")
        print(res.out or res.err or f"{C.GREEN}✅ Already up to date.{C.RESET}")
        if res.ok:
            toast("Fetch + prune complete.", icon="🔄")
        pause()

    # ── New actions ───────────────────────────────────────────────────────────

    def action_diff_stat(self):
        """2s — compact diff --stat view."""
        if not self.require_repo():
            return
        stat = git("diff", "--stat", "HEAD")
        if not stat.out:
            print(f"{C.GREEN}✅ No changes against HEAD.{C.RESET}")
        else:
            # Colorize: lines with | get file in blue, bar + count in gold
            for line in stat.out.split("\n"):
                if "|" in line:
                    fname, rest = line.split("|", 1)
                    # Highlight + and - within the bar
                    rest_colored = rest.replace("+", f"{C.GREEN}+{C.RESET}").replace("-", f"{C.RED}-{C.RESET}")
                    print(f"{C.BLUE}{fname}{C.RESET}|{C.GOLD}{rest_colored}{C.RESET}")
                else:
                    print(f"{C.GRAY_DIM}{line}{C.RESET}")
        pause()

    def action_interactive_rebase(self):
        """22 — git rebase -i dev via the user's $EDITOR."""
        if not self.require_repo():
            return
        if self.branch in ("main", "dev", "unknown", "(detached)"):
            print(f"{C.RED}❌ Must be on a feature branch to rebase onto dev.{C.RESET}")
            pause()
            return
        count_res = git("rev-list", "--count", "dev..HEAD")
        try:
            count = int(count_res.out)
        except ValueError:
            count = 0
        if count == 0:
            print(f"{C.YELLOW}⚠️  No commits ahead of dev — nothing to rebase.{C.RESET}")
            pause()
            return
        print(f"{C.YELLOW}🔃 Starting interactive rebase of {count} commit(s) onto dev…{C.RESET}")
        print(f"{C.GRAY_DIM}   Your editor will open. Save and close to continue.{C.RESET}")
        editor = os.environ.get("EDITOR", "nano")
        env = {**os.environ, "GIT_SEQUENCE_EDITOR": editor}
        subprocess.call(["git", "rebase", "-i", "dev"], env=env)
        pause()

    def _paginated_commit_picker(self, ref=None, page_size=10):
        """
        Page through commits (optionally on a given ref/branch) and let the
        user pick one by number, type 'm' for more, or type a raw SHA/partial
        SHA directly even if it's outside the currently shown page.
        Returns the chosen SHA string, or None if cancelled.
        """
        skip = 0
        shown = []
        while True:
            args = ["log", "--oneline", f"--skip={skip}", f"-{page_size}"]
            if ref:
                args.append(ref)
            page = git(*args)
            if not page.out:
                if not shown:
                    print(f"{C.RED}❌ No commits found.{C.RESET}")
                    return None
                print(f"{C.GRAY_DIM}(no more commits){C.RESET}")
            else:
                new_lines = page.out.split("\n")
                shown.extend(new_lines)
                start_idx = len(shown) - len(new_lines) + 1
                for i, c in enumerate(new_lines, start_idx):
                    sha = c.split(" ", 1)[0]
                    msg = c.split(" ", 1)[1] if " " in c else ""
                    print(f"  {C.BLUE}{i}.{C.RESET} {C.GOLD}{sha}{C.RESET} {msg}")

            choice = input(
                f"\nNumber to select, {C.GRAY_DIM}'m'{C.RESET} for more, "
                f"or paste a SHA directly (blank to cancel): "
            ).strip()

            if not choice:
                return None
            if choice.lower() == "m":
                skip += page_size
                continue
            try:
                idx = int(choice)
                if 1 <= idx <= len(shown):
                    return shown[idx - 1].split(" ", 1)[0]
                print(f"{C.RED}❌ Number out of range.{C.RESET}")
                continue
            except ValueError:
                pass

            # Treat as a raw SHA/partial SHA — verify it resolves
            verify = git("rev-parse", "--verify", "--quiet", choice)
            if verify.ok:
                return choice
            print(f"{C.RED}❌ '{choice}' is not a valid commit reference.{C.RESET}")

    def action_cherry_pick(self):
        """23 — list commits from another branch, pick one by number."""
        if not self.require_repo():
            return
        branches_res = git("branch")
        all_branches = [b.strip().lstrip("* ") for b in branches_res.out.split("\n") if b.strip()]
        other = [b for b in all_branches if b != self.branch]
        if not other:
            print(f"{C.RED}❌ No other branches available to pick from.{C.RESET}")
            pause()
            return

        print(f"{C.YELLOW}🍒 Cherry-pick from which branch?{C.RESET}")
        for i, b in enumerate(other, 1):
            print(f"  {C.BLUE}{i}.{C.RESET} {b}")
        choice = input("Branch number: ").strip()
        try:
            src_branch = other[int(choice) - 1]
        except (ValueError, IndexError):
            print(f"{C.RED}❌ Invalid selection.{C.RESET}")
            pause()
            return

        print(f"\n{C.YELLOW}Commits on {src_branch}:{C.RESET}")
        target = self._paginated_commit_picker(ref=src_branch)
        if not target:
            print(f"{C.GRAY_DIM}Cancelled.{C.RESET}")
            pause()
            return

        print(f"{C.YELLOW}🍒 Cherry-picking {target}…{C.RESET}")
        res = git("cherry-pick", target)
        print(res.out or res.err)
        if res.ok:
            toast(f"Cherry-picked {target}", icon="🍒")
        pause()

    def action_worktree_add(self):
        """24 — git worktree add wrapper."""
        if not self.require_repo():
            return
        path = input("Worktree path (e.g., ../vector-fix): ").strip()
        if not path:
            pause()
            return
        branch = input("Branch for worktree (blank = detached at HEAD): ").strip()
        if branch:
            sanitized = sanitize_branch_name(branch)
            existing = git("branch", "--list", sanitized)
            if existing.out:
                res = git("worktree", "add", path, sanitized)
            else:
                res = git("worktree", "add", "-b", sanitized, path)
        else:
            res = git("worktree", "add", path)
        print(res.out or res.err)
        if res.ok:
            toast(f"Worktree created at {path}", icon="🌲")
        pause()

    def action_gitignore_add(self):
        """25 — append pattern to .gitignore."""
        if not self.require_repo():
            return
        untracked = git("ls-files", "--others", "--exclude-standard")
        if untracked.out:
            print(f"{C.YELLOW}📄 Untracked files:{C.RESET}")
            print(untracked.out)
        pattern = input("\nPattern to add to .gitignore: ").strip()
        if not pattern:
            pause()
            return
        gitignore_path = ".gitignore"
        # Check if pattern already present
        if os.path.isfile(gitignore_path):
            with open(gitignore_path) as f:
                existing = f.read()
            if pattern in existing.split("\n"):
                print(f"{C.YELLOW}⚠️  Pattern already in .gitignore.{C.RESET}")
                pause()
                return
        with open(gitignore_path, "a") as f:
            f.write(f"\n{pattern}\n")
        print(f"{C.GREEN}✅ Added '{pattern}' to .gitignore{C.RESET}")
        toast(f"Added '{pattern}' to .gitignore", icon="📄")
        pause()

    def action_untrack_file(self):
        """25a — git rm --cached + auto-append to .gitignore, local copy kept."""
        if not self.require_repo():
            return
        tracked = git("ls-files")
        print(f"{C.YELLOW}📄 Tracked files:{C.RESET}")
        print(tracked.out)
        fname = input("\nFile to untrack (keep local copy): ").strip()
        if not fname:
            pause()
            return
        if fname not in tracked.out.split("\n"):
            print(f"{C.RED}❌ '{fname}' is not a tracked file.{C.RESET}")
            pause()
            return

        if not confirm(f"Untrack '{fname}'? It stays on disk but is removed from git tracking."):
            pause()
            return

        result = git("rm", "--cached", fname)
        if not result.ok:
            print(f"{C.RED}❌ Untrack failed: {result.err}{C.RESET}")
            pause()
            return
        print(f"{C.GREEN}✅ Untracked '{fname}' (local copy kept).{C.RESET}")

        gitignore_path = ".gitignore"
        already_ignored = False
        if os.path.isfile(gitignore_path):
            with open(gitignore_path) as f:
                existing = f.read()
            already_ignored = fname in existing.split("\n")

        if already_ignored:
            print(f"{C.YELLOW}⚠️  '{fname}' already in .gitignore.{C.RESET}")
        else:
            with open(gitignore_path, "a") as f:
                f.write(f"\n{fname}\n")
            print(f"{C.GREEN}✅ Added '{fname}' to .gitignore{C.RESET}")

        toast(f"Untracked '{fname}'", icon="🙈")
        pause()

    def action_commit_search(self):
        """26 — git log --grep wrapper."""
        if not self.require_repo():
            return
        keyword = input("Search commits for keyword: ").strip()
        if not keyword:
            pause()
            return
        log = git("log", "--oneline", "--all", f"--grep={keyword}")
        if not log.out:
            print(f"{C.YELLOW}No commits matched '{keyword}'.{C.RESET}")
        else:
            print(f"{C.YELLOW}🔎 Commits matching '{keyword}':{C.RESET}")
            for line in log.out.split("\n"):
                sha = line.split(" ", 1)[0]
                msg = line.split(" ", 1)[1] if " " in line else ""
                print(f"  {C.GOLD}{sha}{C.RESET} {msg}")
        offer_clipboard(log.out, "search results")
        pause()

    def action_switch_project(self):
        """27 — multi-repo switcher. Lets you jump to another registered project."""
        target = registry.run_repo_switcher()
        if not target:
            return
        try:
            os.chdir(target)
        except OSError as e:
            print(f"{C.RED}❌ Failed to switch to {target}: {e}{C.RESET}")
            pause()
            return
        toast(f"Switched to {os.path.basename(target)}", icon="🔮")
        self.config = DashboardConfig()
        self.refresh()
        pause()

    def action_branch_age_report(self):
        """28 — list branches sorted by last-commit date, flag stale ones."""
        if not self.require_repo():
            return
        branches_res = git("branch", "--format=%(refname:short)")
        if not branches_res.out:
            print(f"{C.RED}❌ No branches found.{C.RESET}")
            pause()
            return

        now = datetime.now(timezone.utc)
        STALE_DAYS = 30
        entries = []

        for b in branches_res.out.split("\n"):
            b = b.strip()
            if not b:
                continue
            ts_res = git("log", "-1", "--format=%ct", b)
            try:
                ts = int(ts_res.out)
                dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                age_days = (now - dt).days
            except (ValueError, OSError):
                age_days = -1
                dt = None
            entries.append((b, age_days, dt))

        # Sort oldest first
        entries.sort(key=lambda x: x[1], reverse=True)

        print(f"{C.YELLOW}📅 Branch age report (oldest first):{C.RESET}")
        print(f"{C.GRAY_DIM}  {'Branch':<30} {'Age':>6}  {'Last commit'}{C.RESET}")
        print(f"{C.GRAY_DIM}  {'─'*30} {'─'*6}  {'─'*20}{C.RESET}")

        stale = []
        for b, age_days, dt in entries:
            date_str = dt.strftime("%Y-%m-%d") if dt else "unknown"
            is_stale = age_days >= STALE_DAYS
            if is_stale:
                stale.append(b)
            age_color = C.RED if is_stale else (C.YELLOW if age_days >= 14 else C.GREEN)
            stale_flag = f" {C.RED}← STALE{C.RESET}" if is_stale else ""
            print(f"  {C.BLUE}{b:<30}{C.RESET} {age_color}{age_days:>5}d{C.RESET}  {C.GRAY_DIM}{date_str}{C.RESET}{stale_flag}")

        if stale:
            print(f"\n{C.ORANGE}⚠️  {len(stale)} stale branch(es) (>{STALE_DAYS} days). Use Option 9 to delete.{C.RESET}")

        pause()

    def action_fix_detached_head(self):
        """29 — surface detached HEAD recovery, offer to branch from current SHA."""
        if not self.require_repo():
            return
        if not self.detached:
            print(f"{C.GREEN}✅ Not in detached HEAD state — you're on branch '{self.branch}'.{C.RESET}")
            pause()
            return
        sha = git("rev-parse", "--short", "HEAD")
        sha_str = sha.out if sha.ok else "unknown"
        print(f"\n{C.RED}⚠️  You are in detached HEAD state at {sha_str}.{C.RESET}")
        print(f"{C.GRAY_DIM}   Commits made here will be lost if you switch branches without saving.{C.RESET}")
        self._offer_detached_head_branch()
        pause()

    def action_setup_github(self):
        """30 — GitHub sign-in: configure origin + persist credentials so pushes don't prompt."""
        if not self.require_repo():
            return

        print(f"\n{C.YELLOW}🔑 GitHub sign-in{C.RESET}")
        default_user = self.config.get("github_username", "")
        user_prompt = f"GitHub username [{default_user}]: " if default_user else "GitHub username: "
        username = input(user_prompt).strip() or default_user

        default_repo = self.config.get("github_repo", "")
        repo_prompt = f"Repository name [{default_repo}]: " if default_repo else "Repository name (e.g., git-dashboard): "
        repo_name = input(repo_prompt).strip() or default_repo

        if not username or not repo_name:
            print(f"{C.RED}❌ Username and repo name are required. Aborting.{C.RESET}")
            pause()
            return

        pat = getpass.getpass("Personal Access Token (input hidden): ").strip()
        if not pat:
            print(f"{C.RED}❌ No token entered. Aborting.{C.RESET}")
            pause()
            return

        remote_url = f"https://github.com/{username}/{repo_name}.git"

        existing_origin = git("remote", "get-url", "origin")
        if existing_origin.ok and existing_origin.out:
            if not confirm(f"Origin already set to '{existing_origin.out}'. Overwrite with '{remote_url}'?"):
                print(f"{C.GRAY_DIM}Keeping existing origin.{C.RESET}")
            else:
                res = git("remote", "set-url", "origin", remote_url)
                print(res.out or res.err)
        else:
            res = git("remote", "add", "origin", remote_url)
            print(res.out or res.err)

        # Persist credential storage so pushes/pulls don't re-prompt.
        git("config", "--global", "credential.helper", "store")
        cred_line = f"https://{username}:{pat}@github.com\n"
        cred_path = os.path.expanduser("~/.git-credentials")
        try:
            existing_lines = []
            if os.path.isfile(cred_path):
                with open(cred_path) as f:
                    existing_lines = [l for l in f.readlines() if username not in l or "github.com" not in l]
            with open(cred_path, "w") as f:
                f.writelines(existing_lines)
                f.write(cred_line)
            os.chmod(cred_path, 0o600)
        except OSError as e:
            print(f"{C.RED}❌ Failed to store credentials: {e}{C.RESET}")
            pause()
            return

        self.config.set("github_username", username)
        self.config.set("github_repo", repo_name)
        toast(f"Signed in as {username} for {repo_name}", icon="🔑")
        print(f"{C.GRAY_DIM}   Origin set to {remote_url} — pushes via Option 17 won't prompt for credentials.{C.RESET}")
        pause()

    def action_git_init(self):
        """31 — git init with main + dev branches, ready for GitFlow."""
        check = run(["git", "rev-parse", "--is-inside-work-tree"])
        if check.ok and check.out == "true":
            print(f"{C.RED}❌ Already inside a git repository — refusing to re-init.{C.RESET}")
            pause()
            return

        cwd = os.getcwd()
        print(f"\n{C.YELLOW}🆕 Initialize a new repo in:{C.RESET} {C.BLUE}{cwd}{C.RESET}")
        if not confirm("Proceed with git init (main + dev)?"):
            pause()
            return

        res = git("init", "-b", "main")
        print(res.out or res.err)
        if not res.ok:
            print(f"{C.RED}❌ git init failed.{C.RESET}")
            pause()
            return

        if not os.path.exists(".gitignore"):
            default_gitignore = (
                "# Python\n"
                "__pycache__/\n"
                "*.pyc\n"
                ".venv/\n"
                "venv/\n"
                "\n"
                "# Node / Expo / React Native\n"
                "node_modules/\n"
                ".expo/\n"
                ".expo-shared/\n"
                "dist/\n"
                "build/\n"
                "*.log\n"
                "npm-debug.log*\n"
                "\n"
                "# OS / editor\n"
                ".DS_Store\n"
                ".vscode/\n"
                "*.swp\n"
                "\n"
                "# Env\n"
                ".env\n"
                ".env.local\n"
            )
            with open(".gitignore", "w") as f:
                f.write(default_gitignore)
            print(f"{C.GRAY_DIM}📄 Created default .gitignore (Python/Node/Expo/editor patterns).{C.RESET}")

        # Ensure there's at least one commit on main before branching dev off it.
        has_commit = run(["git", "rev-parse", "HEAD"])
        if not has_commit.ok:
            if not os.path.exists("README.md"):
                with open("README.md", "w") as f:
                    f.write(f"# {os.path.basename(cwd)}\n")
                git("add", "README.md")
                commit_res = git("commit", "-m", "chore: initial commit")
            else:
                git("add", ".")
                commit_res = git("commit", "-m", "chore: initial commit")
                if not commit_res.ok:
                    commit_res = git("commit", "--allow-empty", "-m", "chore: initial commit")
            print(commit_res.out or commit_res.err)

        dev_res = git("switch", "-c", "dev")
        print(dev_res.out or dev_res.err)

        if dev_res.ok:
            toast("Repo initialized with main + dev", icon="🆕")
            print(f"{C.GRAY_DIM}   You're now on 'dev'. Use Option 6 to start a feature branch,{C.RESET}")
            print(f"{C.GRAY_DIM}   or Option 30 to connect a GitHub remote.{C.RESET}")
            self.refresh()

            register_fn = getattr(registry, "register_project", None)
            if callable(register_fn):
                if confirm("Register this project for Option 27 (switch project)?"):
                    try:
                        register_fn(os.getcwd())
                        print(f"{C.GREEN}✅ Registered with project switcher.{C.RESET}")
                    except Exception as e:
                        print(f"{C.RED}❌ Registration failed: {e}{C.RESET}")
            else:
                print(f"{C.GRAY_DIM}ℹ️  registry.py has no register_project() function — add this project to the switcher manually.{C.RESET}")
        pause()

    def _check_empty_branch_on_exit(self):
        """On exit, if current branch has zero commits ahead of dev, offer to delete it."""
        if not self.in_repo:
            return
        if self.branch in ("main", "dev", "unknown", "(detached)"):
            return
        if not self.empty_branch:
            return
        print(f"\n{C.YELLOW}💤 Branch '{self.branch}' has no commits ahead of dev.{C.RESET}")
        if confirm(f"Delete abandoned branch '{self.branch}' before exiting?"):
            git("switch", "dev")
            res = git("branch", "-d", self.branch)
            if res.ok:
                print(f"{C.GREEN}🗑️  Deleted '{self.branch}'.{C.RESET}")
            else:
                print(f"{C.RED}❌ Failed: {res.err}{C.RESET}")


    def action_amend_commit(self):
        """3a — Amend the most recent commit."""
        if not self.require_repo():
            return
        if self.branch in ("main", "dev"):
            print(f"{C.RED}❌ Error: GitFlow violation. Cannot amend on {self.branch}.{C.RESET}")
            pause()
            return
        last_log = git("log", "-1", "--pretty=format:%h %s")
        if not last_log.ok or not last_log.out:
            print(f"{C.RED}❌ No commits found to amend.{C.RESET}")
            pause()
            return
        print(f"{C.YELLOW}✏️  Last commit:{C.RESET} {last_log.out}")
        diff = git("diff", "HEAD")
        untracked = git("ls-files", "--others", "--exclude-standard")
        if diff.out:
            print(colorize_diff(diff.out))
        if untracked.out:
            print(f"{C.YELLOW}📄 Untracked files:{C.RESET}")
            print(untracked.out)
        if diff.out or untracked.out:
            if confirm("Stage current changes into this commit?"):
                git("add", ".")
        new_msg = input("New commit message (blank = keep existing): ").strip()
        if new_msg:
            res = git("commit", "--amend", "-m", new_msg)
        else:
            res = git("commit", "--amend", "--no-edit")
        print(res.out or res.err)
        if res.ok:
            toast("Commit amended.", icon="✏️")
        pause()

    def action_tag_management(self):
        """32 — List, create, push, or delete tags."""
        if not self.require_repo():
            return
        print(f"{C.GOLD}🏷️  Tag management{C.RESET}")
        print("  1. List tags")
        print("  2. Create tag")
        print("  3. Push tag(s)")
        print("  4. Delete tag")
        choice = input("Choice: ").strip()

        if choice == "1":
            tags = git("tag", "-n")
            print(tags.out or f"{C.GRAY_DIM}No tags found.{C.RESET}")

        elif choice == "2":
            name = input("Tag name (e.g., v1.2.0): ").strip()
            if not name or not run(["git", "check-ref-format", "refs/tags/" + name]).ok:
                print(f"{C.RED}❌ Invalid tag name.{C.RESET}")
                pause()
                return
            msg = input("Tag message (blank = lightweight tag): ").strip()
            res = git("tag", "-a", name, "-m", msg) if msg else git("tag", name)
            print(res.out or res.err)
            if res.ok:
                toast(f"Tagged {name}", icon="🏷️")

        elif choice == "3":
            tags = git("tag")
            if not tags.out:
                print(f"{C.GRAY_DIM}No tags to push.{C.RESET}")
            else:
                print(tags.out)
                name = input("Tag to push (blank = push all): ").strip()
                res = git("push", "origin", name) if name else git("push", "origin", "--tags")
                print(res.out or res.err)
                if res.ok:
                    toast("Tag(s) pushed.", icon="⬆️")

        elif choice == "4":
            tags = git("tag")
            if not tags.out:
                print(f"{C.GRAY_DIM}No tags found.{C.RESET}")
                pause()
                return
            print(tags.out)
            name = input("Tag to delete: ").strip()
            if name and confirm(f"Delete tag '{name}' locally?"):
                res = git("tag", "-d", name)
                print(res.out or res.err)
                if confirm("Also delete from remote?"):
                    res2 = git("push", "origin", f":refs/tags/{name}")
                    print(res2.out or res2.err)
        else:
            print(f"{C.RED}❌ Invalid choice.{C.RESET}")
        pause()

    def action_restore_file(self):
        """33 — Discard local changes to a single file."""
        if not self.require_repo():
            return
        status = git("status", "-s")
        if not status.out:
            print(f"{C.GREEN}✅ Working tree clean — nothing to restore.{C.RESET}")
            pause()
            return
        print(f"{C.YELLOW}🧹 Changed files:{C.RESET}")
        print(status.out)
        fname = input("\nFile to restore (discard changes), blank to cancel: ").strip()
        if not fname:
            pause()
            return
        if not confirm(f"⚠️  Discard ALL changes to '{fname}'? This cannot be undone."):
            pause()
            return
        res = git("checkout", "--", fname)
        print(res.out or res.err)
        if res.ok:
            toast(f"Restored {fname}", icon="🧹")
        pause()

    def action_show_commit(self):
        """34 — Show full diff/details for a commit."""
        if not self.require_repo():
            return
        print(f"{C.YELLOW}Recent commits:{C.RESET}")
        sha = self._paginated_commit_picker()
        if not sha:
            sha = "HEAD"
        res = git("show", sha)
        print(colorize_diff(res.out) if res.ok else res.err)
        offer_clipboard(res.out, "commit details")
        pause()

    def action_blame_file(self):
        """35 — git blame on a tracked file."""
        if not self.require_repo():
            return
        tracked = git("ls-files")
        print(f"{C.YELLOW}📄 Tracked files:{C.RESET}")
        print(tracked.out)
        fname = input("\nFile to blame: ").strip()
        if not fname:
            pause()
            return
        res = git("blame", fname)
        print(res.out or res.err)
        pause()

    def action_remote_management(self):
        """36 — Add, update, or remove remotes."""
        if not self.require_repo():
            return
        print(f"{C.CYAN}🌐 Remote management{C.RESET}")
        remotes = git("remote", "-v")
        print(remotes.out or f"{C.GRAY_DIM}No remotes configured.{C.RESET}")
        print("\n  1. Add remote")
        print("  2. Change remote URL")
        print("  3. Remove remote")
        choice = input("Choice (blank to cancel): ").strip()

        if choice == "1":
            name = input("Remote name (e.g., origin): ").strip()
            url = input("Remote URL: ").strip()
            if name and url:
                res = git("remote", "add", name, url)
                print(res.out or res.err)
                if res.ok:
                    toast(f"Added remote {name}", icon="🌐")
        elif choice == "2":
            name = input("Remote name to update: ").strip()
            url = input("New URL: ").strip()
            if name and url:
                res = git("remote", "set-url", name, url)
                print(res.out or res.err)
                if res.ok:
                    toast(f"Updated {name}", icon="🌐")
        elif choice == "3":
            name = input("Remote name to remove: ").strip()
            if name and confirm(f"Remove remote '{name}'?"):
                res = git("remote", "remove", name)
                print(res.out or res.err)
        pause()

    def action_file_history(self):
        """37 — log --follow for a single file."""
        if not self.require_repo():
            return
        tracked = git("ls-files")
        print(f"{C.YELLOW}📄 Tracked files:{C.RESET}")
        print(tracked.out)
        fname = input("\nFile to view history for: ").strip()
        if not fname:
            pause()
            return
        res = git("log", "--oneline", "--follow", "--", fname)
        print(res.out or f"{C.GRAY_DIM}No history found.{C.RESET}")
        offer_clipboard(res.out, "file history")
        pause()

    def action_stash_inspect(self):
        """38 — List stashes, inspect contents, optionally drop."""
        if not self.require_repo():
            return
        stashes = git("stash", "list")
        if not stashes.out:
            print(f"{C.GREEN}✅ No stashes found.{C.RESET}")
            pause()
            return
        print(f"{C.PINK}🔍 Stash list:{C.RESET}")
        print(stashes.out)
        ref = input("\nStash to inspect (e.g., stash@{0}), blank to cancel: ").strip()
        if not ref:
            pause()
            return
        if not re.match(r"^stash@\{\d+\}$", ref):
            print(f"{C.RED}❌ Invalid stash reference. Expected format: stash@{{N}} (e.g., stash@{{0}}).{C.RESET}")
            pause()
            return
        show = git("stash", "show", "-p", ref)
        print(colorize_diff(show.out) if show.ok else show.err)
        if confirm(f"\nDrop {ref}?"):
            res = git("stash", "drop", ref)
            print(res.out or res.err)
            if res.ok:
                toast(f"Dropped {ref}", icon="🗑️")
        pause()

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run_loop(self):
        dispatch = {
            "1":  self.action_status,
            "2":  self.action_diff,
            "2s": self.action_diff_stat,
            "3":  self.action_commit,
            "4":  self.action_merge_to_dev,
            "5":  self.action_milestone_merge,
            "6":  self.action_new_feature_branch,
            "7":  self.action_switch_branch,
            "8":  self.action_cleanup_branches,
            "9":  self.action_delete_branch,
            "10": self.action_edit_file,
            "10a": self.action_apply_patch,
            "11": self.action_stash,
            "12": self.action_stash_pop,
            "13": self.action_resolve_conflicts,
            "13a": self.action_abort_operation,
            "14": self.action_squash,
            "15": self.action_changelog,
            "16": self.action_graph,
            "17": self.action_push,
            "18": self.action_pull,
            "19": self.action_fetch_prune,
            "20": self.action_quick_wip,
            "22": self.action_interactive_rebase,
            "23": self.action_cherry_pick,
            "24": self.action_worktree_add,
            "25": self.action_gitignore_add,
            "25a": self.action_untrack_file,
            "26": self.action_commit_search,
            "27": self.action_switch_project,
            "28": self.action_branch_age_report,
            "29": self.action_fix_detached_head,
            "30": self.action_setup_github,
            "31": self.action_git_init,
            "3a": self.action_amend_commit,
            "3b": self.action_undo_commit,
            "32": self.action_tag_management,
            "33": self.action_restore_file,
            "34": self.action_show_commit,
            "35": self.action_blame_file,
            "36": self.action_remote_management,
            "37": self.action_file_history,
            "38": self.action_stash_inspect,
        }

        def run_action(choice):
            action = dispatch.get(choice)
            if action:
                action()
                usage = self.config.get("action_usage", {})
                usage[choice] = usage.get(choice, 0) + 1
                self.config.set("action_usage", usage)
                return True
            print(f"{C.RED}❌ Invalid choice{C.RESET}")
            return False

        while True:
            self.print_header()
            self.print_menu()
            choice = input(f"\n{C.GREEN}❯{C.RESET} ").strip()

            if choice == "21":
                self._check_empty_branch_on_exit()
                print(f"{C.PURPLE}👋 Catch you later.{C.RESET}")
                break

            cat_key = choice.upper()
            if cat_key in CATEGORIES:
                while True:
                    self.print_submenu(cat_key)
                    sub_choice = input(f"\n{C.GREEN}❯{C.RESET} ").strip()
                    if sub_choice.lower() == "b" or not sub_choice:
                        break
                    if sub_choice in CATEGORIES[cat_key][2]:
                        run_action(sub_choice)
                        break
                    print(f"{C.RED}❌ Invalid choice for this category{C.RESET}")
                continue

            run_action(choice)


def main():
    dashboard = Dashboard()
    try:
        dashboard.run_loop()
    except KeyboardInterrupt:
        print(f"\n{C.GRAY_DIM}👋 Exiting.{C.RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()
