# Git Control Dashboard

A Termux-native, interactive git workflow tool that enforces strict GitFlow
for solo development entirely from a phone — no laptop, no GUI client.

## What it is

`dashboard.py` is a menu-driven CLI wrapper around git, built for working
across multiple personal projects from Termux on Android. It exists to make
GitFlow hard to get wrong when you're typing on a phone keyboard: branch
protection, conventional commits, scope checks, pre-push linting, and
recovery tools for the situations a phone-only workflow tends to produce
(detached HEAD, abandoned branches, merge conflicts).

## Why it exists

Working solo, on a phone, across several repos, raw git commands are easy
to fat-finger and easy to run on the wrong branch. This tool is the single
entry point for git operations on supported repos — guardrails like scope
mismatch warnings, lint-before-push, and empty-branch cleanup only work
because the dashboard is the only way in.

## Branch model

```
main  <- stable releases only, tagged milestones
  dev  <- integration branch, always deployable
    feature/xyz  <- all work happens here
```

- Never commit directly to `main` or `dev` — the dashboard blocks this
  (merge commits are the one exception, to finalize an in-progress merge).
- All work happens on a feature branch off `dev` (Option 6, under Branching).
- Feature branches merge to `dev` with `--no-ff` (Option 4), then get deleted.
- `dev` to `main` only at milestones (Option 5), with an optional release tag.

## Commit convention

```
type(scope): description
```

Types: feat, fix, chore, docs, refactor, style, test, perf.
Always created via Option 3 (Commit) or Option 20 (Quick WIP), never a raw
`git commit`. The scope should match the paths actually changed — Option 3
warns (case-insensitively) when it doesn't, and remembers your last scope
as a default for next time.

## Menu structure

The dashboard opens to a category list. Pick a letter to open that category,
then a number to run the action, or `b` to go back. Your most-used actions
also surface in a Favorites row at the top automatically.

| Key | Category | Actions |
|-----|----------|---------|
| W | Workflow | 1 Status, 2 Diff (full), 2s Diff stat summary, 3 Commit, 3a Amend last commit, 3b Undo last commit, 20 Quick WIP commit, 4 Merge feature to dev, 5 Milestone merge to main |
| B | Branching | 6 New feature branch, 7 Switch branch, 8 Cleanup merged branches, 9 Delete branch, 28 Branch staleness report, 27 Switch project |
| I | Inspect | 34 Show commit, 35 Blame file, 37 File history, 26 Commit search, 16 Commit graph, 15 Generate changelog |
| T | Tags & Remote | 32 Tag management, 17 Push to remote, 18 Pull from remote, 19 Fetch + prune, 36 Remote management |
| S | Stash & Recovery | 11 Stash changes, 38 Stash list/inspect/drop, 12 Pop stash, 33 Restore file, 13 Resolve conflicts, 13a Abort operation, 25 .gitignore quick-add, 25a Untrack file |
| A | Advanced | 14 Squash commits, 22 Interactive rebase, 23 Cherry-pick, 24 Worktree add, 10 Edit file, 10a Apply patch (batch) |
| U | Setup | 30 GitHub sign-in, 31 Git init, 29 Fix detached HEAD |

## Notable behaviors

- Scope mismatch check — warns at commit time if the entered scope doesn't
  match the files actually changed (case-insensitive substring match), and
  lets you proceed anyway or abort to fix it.
- Branch deletion safety — checks merge status against both `dev` and
  `main` before warning a branch looks unmerged; force-delete requires
  explicit confirmation.
- Pre-push lint — runs `py_compile` over tracked .py files before pushing;
  you can override and push anyway if needed.
- Default .gitignore on init — Option 31 writes a sane Python/Node/Expo/
  editor/env .gitignore on fresh repos, only if one doesn't already exist,
  and offers to register the project with the multi-repo switcher.
- Detached HEAD recovery — Option 29 (and an automatic banner on the main
  screen) offers to branch off the current commit before you lose work.
- Empty branch cleanup — on exit, offers to delete a feature branch that
  never got any commits ahead of dev.
- Branch staleness report — Option 28 lists branches by last-commit age
  and flags anything 30+ days old as stale.
- Paginated pickers — cherry-pick, show-commit, and apply-patch's file
  picker page through results 10 at a time, or accept a raw SHA/path
  typed directly.
- Quick WIP commits — Option 20 snapshots all changes with a fixed
  `chore(wip): snapshot` message, blocked on `main`/`dev` like Option 3.
- Amend / undo — Option 3a amends the last commit (optionally restaging
  current changes first); Option 3b soft-resets the last commit back to
  staging. Both are blocked on `main`/`dev`.
- Untrack file — Option 25a removes a file from git tracking with
  `git rm --cached` while keeping the local copy, and auto-appends it to
  `.gitignore` if it isn't already there.
- Tag management — Option 32 lists, creates (annotated or lightweight),
  pushes, and deletes tags (locally and on remote).
- Remote management — Option 36 adds, updates, or removes remotes beyond
  just `origin`.
- Stash inspect/drop — Option 38 lists stashes, shows the diff for a
  specific one, and offers to drop it.
- Abort operation — Option 13a detects an in-progress merge, cherry-pick,
  or rebase and aborts it after confirmation.
- GitHub sign-in — Option 30 sets the `origin` remote from a username/repo
  and stores a PAT via git's credential store so later pushes/pulls
  (Options 17/18) don't prompt for credentials.
- Favorites — the 4 most-used menu actions surface at the top automatically.

## Workflow rules for anyone (human or AI) touching this codebase

- Never run raw git commands directly — everything routes through the
  dashboard menu so its guardrails actually apply.
- No `sed` for code edits — Python heredoc patch scripts (PYEOF) or full
  file rewrites only, except bare JSX text-node replacements.
- No rebase, push --force, or history rewriting on `main`/`dev`.
- Never suggest a milestone merge to `main` unless explicitly asked.

## Requirements

- Termux on Android
- Python 3
- git
- Optional: `termux-clipboard-set`, `termux-toast` (Termux:API) for
  clipboard and toast support