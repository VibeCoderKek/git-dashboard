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

- Never commit directly to `main` or `dev` — the dashboard blocks this.
- All work happens on a feature branch off `dev` (Option 6, under Branching).
- Feature branches merge to `dev` with `--no-ff` (Option 4), then get deleted.
- `dev` to `main` only at milestones (Option 5), with an optional release tag.

## Commit convention

```
type(scope): description
```

Types: feat, fix, chore, docs, refactor, style, test, perf.
Always created via Option 3 (Commit), never a raw `git commit`. The scope
should match the paths actually changed — Option 3 warns (case-insensitively)
when it doesn't.

## Menu structure

The dashboard opens to a category list. Pick a letter to open that category,
then a number to run the action, or `b` to go back. Your most-used actions
also surface in a Favorites row at the top automatically.

| Key | Category |
|-----|----------|
| W | Workflow - status, diff, commit, merge, milestone |
| B | Branching - new/switch/delete branch, cleanup, staleness, switch project |
| I | Inspect - show commit, blame, file history, search, graph, changelog |
| T | Tags & Remote - tag management, push/pull/fetch, remote management |
| S | Stash & Recovery - stash, restore file, resolve conflicts, .gitignore |
| A | Advanced - squash, rebase, cherry-pick, worktree, edit file |
| U | Setup - GitHub sign-in, git init, detached HEAD recovery |

## Notable behaviors

- Scope mismatch check — warns at commit time if the entered scope doesn't
  match the files actually changed (case-insensitive substring match).
- Branch deletion safety — checks merge status against both `dev` and
  `main` before warning a branch looks unmerged.
- Pre-push lint — runs `py_compile` over tracked .py files before pushing;
  you can override and push anyway if needed.
- Default .gitignore on init — Option 31 writes a sane Python/Node/Expo/
  editor/env .gitignore on fresh repos, only if one doesn't already exist.
- Detached HEAD recovery — Option 29 (and an automatic banner) offers to
  branch off the current commit before you lose work.
- Empty branch cleanup — on exit, offers to delete a feature branch that
  never got any commits ahead of dev.
- Branch staleness report — Option 28 lists branches by last-commit age
  and flags anything over 30 days old.
- Paginated commit pickers — cherry-pick and show-commit page through
  history 10 at a time, or accept a raw SHA directly.
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
