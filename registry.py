"""
registry.py — Multi-repo switcher for Git Control Dashboard

Maintains a global registry of known project paths at:
    ~/.git-dashboard/registry.json

Responsibilities:
  - First-run auto-scan of ~ (top-level only) and ~/projects/ (top-level only)
    for directories containing a .git folder
  - Manual add/remove of arbitrary paths
  - Live git status hydration (branch, dirty flag, ahead/behind, last commit)
    on every render — never cached in the registry file
  - Rendering the "SELECT PROJECT" screen and handling its input loop

The registry file only stores paths + a `scanned` flag. All status data
(branch, dirty, ahead/behind, last commit) is computed fresh each time
the screen is shown, since that's the whole point — it has to be current.
"""

import json
import os
import subprocess
from pathlib import Path

REGISTRY_DIR = Path.home() / ".git-dashboard"
REGISTRY_FILE = REGISTRY_DIR / "registry.json"

# Colors (ANSI) — adjust/remove if dashboard.py already has its own palette
GREEN = "\033[92m"
RED = "\033[91m"
DIM = "\033[2m"
BOLD = "\033[1m"
CYAN = "\033[96m"
RESET = "\033[0m"


# ---------------------------------------------------------------------------
# Registry persistence
# ---------------------------------------------------------------------------

def _ensure_registry_dir():
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)


def load_registry():
    """Load registry.json. Returns dict with 'paths' (list[str]) and 'scanned' (bool)."""
    _ensure_registry_dir()
    if not REGISTRY_FILE.exists():
        return {"paths": [], "scanned": False}
    try:
        with open(REGISTRY_FILE, "r") as f:
            data = json.load(f)
        data.setdefault("paths", [])
        data.setdefault("scanned", False)
        return data
    except (json.JSONDecodeError, OSError):
        # Corrupt or unreadable — start fresh rather than crash the dashboard
        return {"paths": [], "scanned": False}


def save_registry(data):
    _ensure_registry_dir()
    with open(REGISTRY_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------

def _is_git_repo(path: Path) -> bool:
    return (path / ".git").exists()


def scan_for_repos():
    """
    Non-recursive scan of:
      - ~ (top-level directories only)
      - ~/projects/ (top-level directories only, if it exists)

    Returns a sorted list of absolute path strings to directories containing .git
    """
    found = set()
    home = Path.home()

    def scan_dir(base: Path):
        if not base.exists() or not base.is_dir():
            return
        try:
            for entry in base.iterdir():
                if entry.is_dir() and not entry.name.startswith("."):
                    if _is_git_repo(entry):
                        found.add(str(entry.resolve()))
        except PermissionError:
            pass

    scan_dir(home)
    scan_dir(home / "projects")

    return sorted(found)


def run_first_scan_if_needed():
    """Call once at dashboard startup. Populates registry on first-ever run only."""
    data = load_registry()
    if not data["scanned"]:
        found = scan_for_repos()
        existing = set(data["paths"])
        data["paths"] = sorted(existing | set(found))
        data["scanned"] = True
        save_registry(data)
    return data


def manual_rescan():
    """Triggered by 'r' in the picker. Re-scans and merges new repos in."""
    data = load_registry()
    found = scan_for_repos()
    existing = set(data["paths"])
    data["paths"] = sorted(existing | set(found))
    save_registry(data)
    return data


def add_path(raw_path: str):
    """Triggered by 'a' in the picker. Validates and adds a manual path."""
    path = Path(raw_path).expanduser().resolve()
    if not path.exists() or not path.is_dir():
        return None, f"Path does not exist: {path}"
    if not _is_git_repo(path):
        return None, f"Not a git repository: {path}"
    data = load_registry()
    path_str = str(path)
    if path_str not in data["paths"]:
        data["paths"].append(path_str)
        data["paths"].sort()
        save_registry(data)
    return path_str, None


def remove_path(path_str: str):
    """Triggered by 'd' in the picker."""
    data = load_registry()
    if path_str in data["paths"]:
        data["paths"].remove(path_str)
        save_registry(data)
        return True
    return False


# ---------------------------------------------------------------------------
# Live git status hydration
# ---------------------------------------------------------------------------

def _git(path, args):
    try:
        result = subprocess.run(
            ["git", "-C", str(path)] + args,
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def get_repo_status(path_str: str):
    """
    Returns dict:
      name, path, branch, dirty (bool), ahead (int), behind (int),
      last_commit (str), valid (bool)
    If the path is missing or no longer a git repo, valid=False.
    """
    path = Path(path_str)
    name = path.name

    if not path.exists() or not _is_git_repo(path):
        return {
            "name": name, "path": path_str, "valid": False,
            "branch": "?", "dirty": False, "ahead": 0, "behind": 0,
            "last_commit": "(missing or not a git repo)"
        }

    branch = _git(path, ["rev-parse", "--abbrev-ref", "HEAD"]) or "?"

    status_output = _git(path, ["status", "--porcelain"])
    dirty = bool(status_output)

    ahead, behind = 0, 0
    upstream = _git(path, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    if upstream:
        counts = _git(path, ["rev-list", "--left-right", "--count", f"{upstream}...HEAD"])
        if counts:
            parts = counts.split()
            if len(parts) == 2:
                behind, ahead = int(parts[0]), int(parts[1])

    last_commit = _git(path, ["log", "-1", "--pretty=%s"]) or "(no commits)"

    return {
        "name": name, "path": path_str, "valid": True,
        "branch": branch, "dirty": dirty,
        "ahead": ahead, "behind": behind,
        "last_commit": last_commit
    }


# ---------------------------------------------------------------------------
# Rendering + interactive loop
# ---------------------------------------------------------------------------

def _truncate(s, width):
    return s if len(s) <= width else s[: width - 1] + "…"


def render_picker(statuses):
    print(f"\n{BOLD}{CYAN}🔮 SELECT PROJECT{RESET}\n")
    for i, s in enumerate(statuses, start=1):
        dot = f"{GREEN}🟢{RESET}" if not s["dirty"] else f"{RED}🔴{RESET}"
        ab = f"↑{s['ahead']} ↓{s['behind']}"
        name = _truncate(s["name"], 16).ljust(16)
        branch = _truncate(s["branch"], 12).ljust(12)
        commit = _truncate(s["last_commit"], 40)
        marker = f"{DIM}(missing){RESET} " if not s["valid"] else ""
        print(f"  {i:<3} {name} {branch} {dot}  {ab:<8} {marker}{commit}")
    print(f"\n  {DIM}r. Rescan   a. Add path   d. Remove   q. Quit{RESET}\n")


def run_repo_switcher():
    """
    Main entry point — call this from dashboard.py's menu handler.
    Returns the selected repo path (str) to chdir into, or None if the
    user quit without selecting.
    """
    run_first_scan_if_needed()

    while True:
        data = load_registry()
        if not data["paths"]:
            print(f"\n{DIM}No projects registered yet. Press 'a' to add one, or 'r' to rescan.{RESET}")
            statuses = []
        else:
            statuses = [get_repo_status(p) for p in data["paths"]]

        render_picker(statuses)
        choice = input("  > ").strip().lower()

        if choice == "q":
            return None

        elif choice == "r":
            manual_rescan()
            print(f"{GREEN}Rescanned.{RESET}")
            continue

        elif choice == "a":
            raw = input("  Path to add: ").strip()
            if not raw:
                continue
            added, err = add_path(raw)
            if err:
                print(f"{RED}{err}{RESET}")
            else:
                print(f"{GREEN}Added: {added}{RESET}")
            continue

        elif choice == "d":
            idx_raw = input("  Number to remove: ").strip()
            if not idx_raw.isdigit():
                continue
            idx = int(idx_raw) - 1
            if 0 <= idx < len(statuses):
                remove_path(statuses[idx]["path"])
                print(f"{GREEN}Removed {statuses[idx]['name']}.{RESET}")
            continue

        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(statuses):
                selected = statuses[idx]
                if not selected["valid"]:
                    print(f"{RED}That path no longer exists or isn't a git repo.{RESET}")
                    continue
                return selected["path"]
            continue

        # unrecognized input — just redraw
        continue
