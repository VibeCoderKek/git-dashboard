# 🔮 Git Control Dashboard

A Termux-native interactive git workflow tool built for mobile developers who live in the terminal. No GUI, no browser — just a fast, keyboard-driven dashboard that enforces GitFlow discipline and keeps your repository clean from your phone.

---

## What It Is

Git Control Dashboard (`dashboard.py`) is a Python TUI that wraps your entire git workflow behind a numbered menu. It was built specifically for **Termux on Android** — where context-switching between a terminal and a browser git client is slow, and where muscle memory for raw git commands is easy to lose mid-flow.

It enforces a strict **GitFlow branching model**:

```
main        ← stable releases only, tagged milestones
 └── dev    ← integration branch, always deployable
      └── feat/your-feature   ← all work happens here
```

Every guardrail, every warning, and every default in the dashboard is designed around this model. You cannot accidentally commit to `main` or `dev`. You cannot push without a lint check. You cannot abandon a branch silently.

The dashboard also spans **multiple projects** (Option 27) and can now **bootstrap a brand-new repo from zero** (Option 31) and **sign in to GitHub with saved credentials** (Option 30) — so the whole lifecycle, from empty folder to pushed milestone, stays inside one tool.

---

## Requirements

- **Termux** (Android) — [f-droid.org/packages/com.termux](https://f-droid.org/packages/com.termux)
- Python 3.10+
- Git
- Optional but recommended: `termux-api` package (enables clipboard + toast notifications)
- Optional: `nvim` or `nano` for in-dashboard file editing

```bash
pkg install python git termux-api
```

---

## Installation

```bash
# Clone the repo
git clone https://github.com/VibeCoderKek/git-dashboard.git
cd git-dashboard

# Make executable
chmod +x dashboard.py

# Optional: add alias to ~/.bashrc or ~/.zshrc
echo 'alias git-dash="python ~/git-dashboard/dashboard.py"' >> ~/.bashrc
source ~/.bashrc
```

Run it from inside any git repository:

```bash
cd ~/your-project
git-dash
```

Starting a brand-new project? You don't need an existing repo first — `cd` into the (possibly empty) folder and run `git-dash`. It'll detect there's no repo yet and Option 31 will set one up for you.

---

## Menu Reference

### 🔐 Setup & Init

| Option | Action |
|--------|--------|
| `30` | GitHub sign-in — set/update `origin`, store credentials so future pushes don't prompt |
| `31` | Git init with `main` + `dev` branches, ready for GitFlow |

### 📋 Workflow

| Option | Action |
|--------|--------|
| `1` | Git status |
| `2` | Full diff against HEAD (colorized) |
| `2s` | Compact diff --stat summary |
| `3` | Commit to feature branch (conventional commits enforced) |
| `4` | Merge feature → dev (`--no-ff`) |
| `5` | Milestone merge: dev → main + optional release tag |

### 🌿 Branching

| Option | Action |
|--------|--------|
| `6` | Create new feature branch off dev |
| `7` | Switch branch |
| `8` | Cleanup merged branches |
| `9` | Delete branch (manual, with merge-status warning) |
| `27` | Switch project — jump to another registered repo without leaving the dashboard |
| `28` | Branch age / staleness report (flags >30 day branches) |

### ✏️ Editing & Recovery

| Option | Action |
|--------|--------|
| `10` | Edit a tracked file in nvim/nano |
| `11` | Stash changes |
| `12` | Pop stash |
| `13` | Resolve merge conflicts (opens each conflicted file) |
| `25` | Quick-add pattern to `.gitignore` |

### ⚙️ Advanced

| Option | Action |
|--------|--------|
| `14` | Squash commits via soft reset |
| `15` | Generate `CHANGELOG.md` from conventional commits |
| `16` | View commit graph (all branches) |
| `17` | Push to remote (runs py_compile lint first) |
| `18` | Pull from remote |
| `19` | Fetch + prune remote-tracking branches |
| `20` | Quick WIP snapshot commit |
| `22` | Interactive rebase onto dev |
| `23` | Cherry-pick a commit from another branch |
| `24` | Add a git worktree |
| `26` | Search commits by keyword (`log --grep`) |
| `29` | Fix detached HEAD — create branch from current position |

---

## How to Use It

### Bootstrapping a brand-new project

```
Option 31 →  git init -b main, ensures an initial commit, branches dev off it
Option 30 →  sign in to GitHub, connect origin, save credentials
Option 6  →  create your first feature branch off dev
```

### Starting a new feature

```
Option 6  →  name your branch (auto-sanitized to kebab-case)
Option 3  →  commit (prompted for type, scope, description)
Option 4  →  merge to dev when done
Option 17 →  push
```

### Conventional commit format

Every commit through option 3 is enforced as:

```
type(scope): description
```

Supported types: `feat`, `fix`, `chore`, `docs`, `refactor`, `style`, `test`, `perf`

The scope is remembered between commits — press Enter to reuse the last one.

### Milestone release

```
Option 5  →  merges dev into main with --no-ff, prompts for version tag (e.g. v1.0.0)
Option 17 →  push main + tags
```

### Recovering from detached HEAD

```
Option 29  →  shows current SHA, offers to create a branch from it
```

### Jumping between projects

If you work across several repos from one phone (e.g. Vector, AuraSpace, git-dashboard itself), Option 27 opens a project picker backed by a registry of known repos. Selecting one `cd`s the dashboard's working directory into that project and reloads its branch/status/config context — no need to exit and re-run `git-dash` from a different folder.

### GitHub sign-in

```
Option 30  →  enter GitHub username, repo name, and a Personal Access Token
```

The token is entered with hidden input (never echoed or logged). The dashboard:

- Sets or updates `origin` to `https://github.com/<username>/<repo>.git`
- Sets `credential.helper store` globally
- Writes the credential line into `~/.git-credentials` (mode `600`), replacing any stale entry for that username on github.com
- Remembers your username and repo name per-project so the prompts pre-fill next time

After this, Option 17 (push) and Option 18 (pull) won't prompt for credentials again.

> Use a fine-scoped Personal Access Token (repo access only), not your account password — GitHub requires PATs for HTTPS git operations anyway.

---

## Guardrails Built In

- **GitFlow protection** — options 3 and 20 refuse to commit directly to `main` or `dev`
- **Scope mismatch warning** — if your commit scope is `dashboard` but you touched `Vector/` files, you get a confirmation gate before proceeding
- **Detached HEAD banner** — red bordered warning in the header with SHA and recovery instructions
- **Empty branch detection** — on exit, if your feature branch has zero commits ahead of dev, you're offered to delete it before leaving
- **Stash safety** — options 6 and 7 detect a dirty tree and offer to stash inline instead of hard-aborting
- **Pre-push lint** — option 17 runs `py_compile` over all tracked `.py` files before pushing, with a "push anyway?" escape hatch
- **Protected branches** — `main` and `dev` cannot be deleted via option 9
- **No double-init** — option 31 refuses to run if you're already inside a git repository

---

## Incorporating Into Your GitFlow

The dashboard is designed to be run **from inside your project directory**, not from its own directory. The recommended setup:

```bash
# In ~/.bashrc or ~/.zshrc
alias git-dash="python ~/git-dashboard/dashboard.py"
```

Then your daily workflow becomes:

```bash
cd ~/Vector          # or ~/AuraSpace, ~/proj, etc.
git-dash             # dashboard opens in context of that repo
```

The dashboard reads `.git/dashboard_config.json` inside whichever repo you're in — so last-used commit scope and GitHub username/repo are per-project. Once you're in, Option 27 lets you hop to any other registered project without quitting and re-`cd`ing manually.

### Worktrees (multi-project parallel work)

If you're juggling Vector and another project simultaneously, use option 24 to add a worktree:

```
Option 24  →  path: ../vector-hotfix  →  branch: fix/urgent-crash
```

This lets you have two branches checked out at once in separate directories — no stash juggling.

---

## Configuration

The dashboard stores per-repo config in `.git/dashboard_config.json` (excluded from version control by default). Current keys:

| Key | Description |
|-----|-------------|
| `last_scope` | Last commit scope used (pre-fills the scope prompt) |
| `github_username` | Set by option 30 — pre-fills the username prompt next time |
| `github_repo` | Set by option 30 — pre-fills the repo name prompt next time |

Global git config set by the dashboard:

```
credential.helper = store   ← set by option 30, persists PAT across sessions
```

Project registry data for Option 27 (known repo paths) is managed separately by `registry.py` rather than the per-repo dashboard config.

---

## Vision / Roadmap

### Near-term
- **Stash list viewer** — browse named stashes, preview diffs, pop or drop by number
- **Tag manager** — list, create, and delete tags with annotation support
- **Conflict diff viewer** — show `ours` vs `theirs` side-by-side before opening editor

### Medium-term
- **Project profiles** — per-project config for lint command, default branch names, scope suggestions
- **JS/TS lint integration** — run `eslint` or `tsc --noEmit` as pre-push check for React Native / Expo projects alongside `py_compile`
- **Commit template library** — save and recall frequently used commit message patterns
- **Remote branch manager** — list remote branches, fetch individual ones, set upstream tracking

### Long-term
- **GitHub CLI integration** — create PRs, view open issues, and merge PRs directly from the dashboard without leaving Termux
- **Interactive diff staging** — stage individual hunks (like `git add -p`) via a guided menu instead of raw terminal
- **Plugin system** — drop a `dashboard_hooks.py` into any project to register custom menu options and pre/post hooks
- **Offline change log** — track what you did across sessions even without commits (useful during long refactors)

---

## License

MIT — do whatever you want with it.

---

*Built in Termux on a Samsung Galaxy S25. Designed for developers who ship from their phone.*
