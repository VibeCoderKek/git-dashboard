#!/usr/bin/env python3
"""
Patch script — adds option 30 (Setup GitHub remote) to dashboard.py.
Run from the git-dashboard directory:
    python patch_remote.py dashboard.py
"""

import sys

def patch(path):
    with open(path) as f:
        src = f.read()

    # ── 1. Add getpass import ─────────────────────────────────────────────────
    OLD_IMPORTS = "import json\nimport py_compile\nimport tempfile"
    NEW_IMPORTS = "import json\nimport py_compile\nimport tempfile\nimport getpass"
    assert OLD_IMPORTS in src, "Import anchor not found"
    src = src.replace(OLD_IMPORTS, NEW_IMPORTS, 1)

    # ── 2. Add action_setup_remote method (before run_loop) ───────────────────
    OLD_LOOP = "    def run_loop(self):"
    NEW_METHOD = '''    def action_setup_remote(self):
        """30 — Configure GitHub HTTPS remote + store PAT credentials."""
        if not self.require_repo():
            return

        # Check if origin already exists
        existing = git("remote", "get-url", "origin")
        if existing.ok:
            print(f"{C.YELLOW}\\u26a0\\ufe0f  Remote 'origin' is already set:{C.RESET}")
            print(f"   {existing.out}")
            if not confirm("Replace it?"):
                pause()
                return
            git("remote", "remove", "origin")

        # GitHub username
        username = input(f"{C.BLUE}GitHub username:{C.RESET} ").strip()
        if not username:
            print(f"{C.RED}\\u274c Username cannot be empty.{C.RESET}")
            pause()
            return

        # Repo name — default to current directory name
        cwd_name = os.path.basename(os.getcwd())
        repo_input = input(f"{C.BLUE}Repo name{C.RESET} (Enter for '{cwd_name}'): ").strip()
        repo = repo_input if repo_input else cwd_name

        # PAT — masked input
        print(f"{C.GRAY_DIM}  Generate at: https://github.com/settings/tokens{C.RESET}")
        print(f"{C.GRAY_DIM}  Scopes needed: repo (full){C.RESET}")
        pat = getpass.getpass(f"{C.BLUE}Personal Access Token (hidden): {C.RESET}")
        if not pat:
            print(f"{C.RED}\\u274c PAT cannot be empty.{C.RESET}")
            pause()
            return

        remote_url = f"https://github.com/{username}/{repo}.git"

        # Add remote
        res = git("remote", "add", "origin", remote_url)
        if not res.ok:
            print(f"{C.RED}\\u274c Failed to add remote: {res.err}{C.RESET}")
            pause()
            return
        print(f"{C.GREEN}\\u2705 Remote set to {remote_url}{C.RESET}")

        # Enable credential store globally
        run(["git", "config", "--global", "credential.helper", "store"])

        # Write directly to ~/.git-credentials
        cred_file = os.path.expanduser("~/.git-credentials")
        cred_line = f"https://{username}:{pat}@github.com"
        try:
            existing_creds = ""
            if os.path.isfile(cred_file):
                with open(cred_file) as f:
                    existing_creds = f.read()
            if cred_line not in existing_creds:
                with open(cred_file, "a") as f:
                    f.write(cred_line + "\\n")
            os.chmod(cred_file, 0o600)
            print(f"{C.GREEN}\\u2705 Credentials stored in ~/.git-credentials{C.RESET}")
        except OSError as e:
            print(f"{C.YELLOW}\\u26a0\\ufe0f  Could not write credentials file: {e}{C.RESET}")

        # Save to dashboard config
        self.config.set("github_username", username)
        self.config.set("github_repo", repo)

        toast(f"Remote configured: github.com/{username}/{repo}", icon="\\U0001f517")

        # Offer immediate push
        if confirm("\\n\\u2b06\\ufe0f  Push current branch to origin now?"):
            self.action_push()
            return

        pause()

    def run_loop(self):'''

    assert OLD_LOOP in src, "run_loop anchor not found"
    src = src.replace(OLD_LOOP, NEW_METHOD, 1)

    # ── 3. Add option 30 to dispatch dict ────────────────────────────────────
    OLD_DISPATCH = '            "29": self.action_fix_detached_head,\n        }'
    NEW_DISPATCH = '            "29": self.action_fix_detached_head,\n            "30": self.action_setup_remote,\n        }'
    assert OLD_DISPATCH in src, "Dispatch anchor not found"
    src = src.replace(OLD_DISPATCH, NEW_DISPATCH, 1)

    # ── 4. Add option 30 to print_menu ───────────────────────────────────────
    OLD_MENU = '        print(f"{C.GRAY}\u2502{C.RESET}  {C.BLUE}29.{C.RESET} \U0001f3e5 Fix detached HEAD \u2192 create branch")\n        print(f"{C.GRAY}\u2502{C.RESET}")\n        print(f"{C.GRAY}\u2502{C.RESET}  {C.BLUE}21.{C.RESET} {C.RED}\U0001f6aa Exit{C.RESET}")'
    NEW_MENU = '        print(f"{C.GRAY}\u2502{C.RESET}  {C.BLUE}29.{C.RESET} \U0001f3e5 Fix detached HEAD \u2192 create branch")\n        print(f"{C.GRAY}\u2502{C.RESET}  {C.BLUE}30.{C.RESET} \U0001f517 Setup GitHub remote + credentials")\n        print(f"{C.GRAY}\u2502{C.RESET}")\n        print(f"{C.GRAY}\u2502{C.RESET}  {C.BLUE}21.{C.RESET} {C.RED}\U0001f6aa Exit{C.RESET}")'
    assert OLD_MENU in src, "Menu anchor not found"
    src = src.replace(OLD_MENU, NEW_MENU, 1)

    with open(path, "w") as f:
        f.write(src)

    print(f"Patched {path} — option 30 added.")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "dashboard.py"
    patch(target)
