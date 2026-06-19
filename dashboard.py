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
from collections import defaultdict


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


class Dashboard:
    def __init__(self):
        self.branch = "unknown"
        self.dirty = False
        self.ahead = 0
        self.behind = 0
        self.in_repo = False

    def refresh(self):
        check = run(["git", "rev-parse", "--is-inside-work-tree"])
        self.in_repo = check.ok and check.out == "true"
        if not self.in_repo:
            self.branch = "unknown"
            self.dirty = False
            self.ahead = self.behind = 0
            return

        b = git("branch", "--show-current")
        self.branch = b.out if b.ok and b.out else "(detached)"

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

    def require_repo(self):
        if not self.in_repo:
            print(f"{C.RED}❌ Error: Not inside a git repository.{C.RESET}")
            pause()
            return False
        return True

    def print_header(self):
        self.refresh()

        if self.branch == "main":
            b_color, b_icon = C.GREEN, "🌳"
        elif self.branch == "dev":
            b_color, b_icon = C.YELLOW, "🛠️"
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

        sync = ""
        if self.ahead or self.behind:
            sync = f" │ {C.CYAN}↑{self.ahead} ↓{self.behind}{C.RESET}"
        info = f" {b_icon} Branch: {b_color}{self.branch}{C.RESET} │ {status_text}{sync}"
        print(f"{C.GRAY_DIM}{info}{C.RESET}\n")

    def print_menu(self):
        print(f"{C.GRAY}┌{DASHES}┐{C.RESET}")
        print(f"{C.GRAY}│{C.RESET} {C.GOLD}📋 WORKFLOW{C.RESET}")
        print(f"{C.GRAY}│{C.RESET}  {C.BLUE} 1.{C.RESET} 👀 Status")
        print(f"{C.GRAY}│{C.RESET}  {C.BLUE} 2.{C.RESET} 🔍 Verify changes (git diff HEAD)")
        print(f"{C.GRAY}│{C.RESET}  {C.BLUE} 3.{C.RESET} 💾 Commit to feature branch")
        print(f"{C.GRAY}│{C.RESET}  {C.BLUE} 4.{C.RESET} 🔀 Merge feature to dev (--no-ff)")
        print(f"{C.GRAY}│{C.RESET}  {C.BLUE} 5.{C.RESET} 🏆 Milestone: Merge dev to main")
        print(f"{C.GRAY}│{C.RESET}")
        print(f"{C.GRAY}│{C.RESET} {C.GREEN}🌿 BRANCHING{C.RESET}")
        print(f"{C.GRAY}│{C.RESET}  {C.BLUE} 6.{C.RESET} 🌱 Feature branch (off dev)")
        print(f"{C.GRAY}│{C.RESET}  {C.BLUE} 7.{C.RESET} 🔁 Switch branch")
        print(f"{C.GRAY}│{C.RESET}  {C.BLUE} 8.{C.RESET} 🧹 Cleanup merged branches")
        print(f"{C.GRAY}│{C.RESET}  {C.BLUE} 9.{C.RESET} 🗑️  Delete branch (manual)")
        print(f"{C.GRAY}│{C.RESET}")
        print(f"{C.GRAY}│{C.RESET} {C.GOLD}✏️  EDITING & RECOVERY{C.RESET}")
        print(f"{C.GRAY}│{C.RESET}  {C.BLUE}10.{C.RESET} 📝 Edit file")
        print(f"{C.GRAY}│{C.RESET}  {C.BLUE}11.{C.RESET} 📦 Stash changes")
        print(f"{C.GRAY}│{C.RESET}  {C.BLUE}12.{C.RESET} 📤 Pop stash")
        print(f"{C.GRAY}│{C.RESET}  {C.BLUE}13.{C.RESET} 🩹 Resolve conflicts")
        print(f"{C.GRAY}│{C.RESET}")
        print(f"{C.GRAY}│{C.RESET} {C.PINK}⚙️  ADVANCED{C.RESET}")
        print(f"{C.GRAY}│{C.RESET}  {C.BLUE}14.{C.RESET} 🪓 Squash commits (soft reset)")
        print(f"{C.GRAY}│{C.RESET}  {C.BLUE}15.{C.RESET} 📜 Generate changelog")
        print(f"{C.GRAY}│{C.RESET}  {C.BLUE}16.{C.RESET} 🌐 View commit graph")
        print(f"{C.GRAY}│{C.RESET}  {C.BLUE}17.{C.RESET} ⬆️  Push to remote")
        print(f"{C.GRAY}│{C.RESET}  {C.BLUE}18.{C.RESET} ⬇️  Pull from remote")
        print(f"{C.GRAY}│{C.RESET}  {C.BLUE}19.{C.RESET} 🔄 Fetch + prune remote-tracking")
        print(f"{C.GRAY}│{C.RESET}  {C.BLUE}20.{C.RESET} ⚡ Quick WIP commit")
        print(f"{C.GRAY}│{C.RESET}")
        print(f"{C.GRAY}│{C.RESET}  {C.BLUE}21.{C.RESET} {C.RED}🚪 Exit{C.RESET}")
        print(f"{C.GRAY}└{DASHES}┘{C.RESET}")

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
                print(diff.out)
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
            print(diff.out)
        if untracked.out:
            print(f"{C.YELLOW}📄 Untracked files (will be added):{C.RESET}")
            print(untracked.out)

        if is_merging:
            print(f"{C.BLUE}🔀 Merge in progress detected. Finalizing merge...{C.RESET}")

        ctype = self._prompt_conventional_type()
        scope = input("Scope (e.g., dashboard): ").strip()
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
        git("checkout", "dev")
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
        git("checkout", "main")
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
        status = git("status", "-s")
        if status.out:
            print(f"{C.RED}⚠️  Warning: Working tree is dirty. Stash or commit changes first.{C.RESET}")
            pause()
            return
        git("checkout", "dev")
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
        res = git("checkout", "-b", sanitized)
        print(res.out or res.err)
        pause()

    def action_switch_branch(self):
        if not self.require_repo():
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
        git("checkout", "dev")
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
            merged = git("branch", "--merged", "dev", "--list", b)
            tag = f"{C.GREEN}(merged to dev){C.RESET}" if merged.out else f"{C.ORANGE}(unmerged){C.RESET}"
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

        merged = git("branch", "--merged", "dev", "--list", name)
        if not merged.out:
            if not confirm(f"⚠️  '{name}' is NOT merged into dev. Force delete anyway?"):
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

    def run_loop(self):
        dispatch = {
            "1": self.action_status,
            "2": self.action_diff,
            "3": self.action_commit,
            "4": self.action_merge_to_dev,
            "5": self.action_milestone_merge,
            "6": self.action_new_feature_branch,
            "7": self.action_switch_branch,
            "8": self.action_cleanup_branches,
            "9": self.action_delete_branch,
            "10": self.action_edit_file,
            "11": self.action_stash,
            "12": self.action_stash_pop,
            "13": self.action_resolve_conflicts,
            "14": self.action_squash,
            "15": self.action_changelog,
            "16": self.action_graph,
            "17": self.action_push,
            "18": self.action_pull,
            "19": self.action_fetch_prune,
            "20": self.action_quick_wip,
        }

        while True:
            self.print_header()
            self.print_menu()
            choice = input(f"\n{C.GREEN}❯{C.RESET} ").strip()

            if choice == "21":
                print(f"{C.PURPLE}👋 Catch you later.{C.RESET}")
                break
            action = dispatch.get(choice)
            if action:
                action()
            else:
                print(f"{C.RED}❌ Invalid choice{C.RESET}")


def main():
    dashboard = Dashboard()
    try:
        dashboard.run_loop()
    except KeyboardInterrupt:
        print(f"\n{C.GRAY_DIM}👋 Exiting.{C.RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()
