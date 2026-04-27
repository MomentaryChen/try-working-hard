---
name: dev-branch-auto
description: Provisions a local git development branch from origin/develop with consistent naming, fetch, and safety checks. Optional Git worktree under D:\projects\worktree for parallel checkouts; after creating a worktree, continue implementation from that directory. Use when the user asks to create a dev branch, feature branch, topic branch, worktree, or automatically set up a branch for parallel work in this repository.
---

# Dev branch auto-setup (this project)

## When to use

- User wants a **new development / feature / fix branch** from the default line.
- User says **create a dev branch**, **open a feature branch**, **branch off from develop**, etc.
- User wants a **separate working directory** for the same repo (**git worktree**) so they can keep another branch checked out in the main folder—use **Optional: Worktree (parallel directory)**. After adding the worktree, the agent **switches context to that directory** for ongoing implementation in the same task.

## Conventions (defaults)

| Item | Default |
|------|---------|
| Base branch | **`origin/develop`** — always use `develop` as `<base>` when this skill runs (after fetch and verify; see step 3) |
| Local branch prefix | `dev/` for generic work, `feature/` for user-facing features, `fix/` for bugfix |
| Name body | kebab-case, short; include issue id if user gives one, e.g. `dev/JIRA-123-slider-interval` → prefer `dev/jira-123-slider-interval` (ASCII, lowercase) |
| Worktree parent (this project) | `D:\projects\worktree` |

If the user provides an exact branch name, use it (after basic sanity: no spaces; replace spaces with `-`).

## Steps (run in repo root)

1. **Status**

   - `git status -sb`
   - If there are uncommitted changes and the user did not ask to commit: **stop** and say they must commit, stash, or discard, unless they confirm stash.

2. **Update refs**

   - `git fetch origin` (or the user’s `remote` name from `git remote`).

3. **Resolve default base** (required for this skill)

   - After fetch, run `git rev-parse --verify origin/develop`. On success, set `<base>` to **`develop`** (branch from **`origin/develop`**).
   - If `origin/develop` is missing, **stop** and tell the user to fetch, create `develop` on the remote, or name another base explicitly; do **not** silently fall back to `main` / `master` unless the user overrides in the same message.
   - If the user **explicitly** asks for a different base (e.g. `main`, a release branch), use that name instead of `develop` for this run only.

4. **Create branch** (in the current worktree)

   - Ensure not already on a branch with the same name: `git show-ref --verify refs/heads/<name>` → if exists, suggest checkout or new name.
   - Preferred (tracks base explicitly):

   ```bash
   git checkout -B <name> origin/<base>
   ```

   Or, if the user is already on `<base>` and it is up to date:

   ```bash
   git pull --ff-only origin <base>
   git checkout -b <name>
   ```

5. **Confirm**

   - `git status -sb` and `git log -1 --oneline`
   - Report: new branch name, base SHA or tag if useful.

## Optional: Worktree (parallel directory)

Use this when the user wants the new (or existing) branch in a **second checkout** without switching the current folder. The parent directory for extra worktrees in this project is:

`D:\projects\worktree`

### Path for the new worktree

- **Folder name**: `<repo-basename>-<branch-for-filesystem>`, where `<repo-basename>` is the last segment of `git rev-parse --show-toplevel` and `<branch-for-filesystem>` is the branch name with `/` replaced by `-` (e.g. `feature-foo` → `feature-foo`, `dev/foo` → `dev-foo`).
- **Full path**: `D:\projects\worktree\<folder-name>`

### Preconditions

- The branch name must not already be checked out in another worktree (`git worktree list`).
- The target path must not already exist as a worktree (pick another folder name or remove the old worktree first).

### Steps (after steps 1–3 above: status, fetch, resolve base)

1. Create the worktree parent if it does not exist (PowerShell):

   ```powershell
   New-Item -ItemType Directory -Force -Path 'D:\projects\worktree' | Out-Null
   ```

2. **New branch** (create branch only in the new directory; leave current worktree’s HEAD unchanged):

   ```powershell
   $wtRoot = 'D:\projects\worktree'
   $base = '<base>'   # default: develop (this skill)
   $name = '<name>'   # full branch name, e.g. feature/my-task
   $repoBase = Split-Path (git rev-parse --show-toplevel) -Leaf
   $safe = $name -replace '/', '-'
   $path = Join-Path $wtRoot ($repoBase + '-' + $safe)
   git worktree add -b $name $path "origin/$base"
   ```

3. **Existing local branch** (branch was already created; user only wants a linked folder). Reuse `$wtRoot`, `$repoBase`, and `$safe` from step 2, then:

   ```powershell
   $path = Join-Path $wtRoot ($repoBase + '-' + $safe)
   git worktree add $path $name
   ```

4. Confirm: `git worktree list`, branch name, and the new directory path.

5. **Continue in the new worktree (agent)** — After the worktree is created, **do not** keep using the original repo root for implementation in the same task.

   - Treat **`$path`** (the full worktree directory from step 2 or 3) as the **active repo root** for the rest of the session: run shell commands with `working_directory` / `cd` set to `$path`, and use paths under `$path` for file reads, edits, searches, and tests.
   - Run `git status -sb` and `git log -1 --oneline` from `$path` to confirm HEAD.
   - Tell the user to **open that folder in the editor** (e.g. Cursor **File → Open Folder** → `$path`) if their workspace is still the main clone, so the UI matches where the agent is working.
   - Proceed with the user’s implementation work (install, code changes, commits) **from `$path`** unless they ask to switch back.

### Remove a worktree later

```powershell
git worktree remove <path>
# If Git refuses (locked files), after closing editors:
# git worktree remove --force <path>
```

### Notes

- This workflow does not copy `.env` or install dependencies; do that only if the user asks or the task needs it, matching the same rules as **Optional: after branch exists** below.
- Default integration line for this skill is **`origin/develop`**; the worktree snippet uses the same `<base>` from step 3 (normally `develop`).

## Windows / PowerShell

- Same `git` commands; avoid bash-only `$( )` in **single-line** copy-paste for users—agent may run multiline in project shell.
- Path for repo: use this workspace’s root (`git rev-parse --show-toplevel`).

## Optional: after branch exists

- If this project uses `pip install` / `hatch` / `pytest`, only run install or tests if the user asked or a task requires it (keep scope to branching unless expanded).

## Anti-patterns

- Do not force-push or reset `--hard` without explicit user request.
- Do not delete the remote or default branch.
- Do not create `main` / `master` as a new topic branch name.
