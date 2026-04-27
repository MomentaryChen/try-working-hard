---
name: dev-branch-auto
description: Provisions a local git development branch from origin/develop with consistent naming, fetch, and safety checks. Always creates the branch via a Git worktree under D:\projects\worktree (parallel checkout); the main clone stays on its current branch. After adding the worktree, continue implementation from that directory. Use when the user asks to create a dev branch, feature branch, topic branch, worktree, or automatically set up a branch for parallel work in this repository.
---

# Dev branch auto-setup (this project)

## When to use

- User wants a **new development / feature / fix branch** from the default line.
- User says **create a dev branch**, **open a feature branch**, **branch off from develop**, etc.
- **Worktree is mandatory for this skill:** the new branch is always created in a **second directory** under `D:\projects\worktree` so the **current workspace folder does not switch branches**. After the worktree exists, the agent **must** treat that directory as the **active repo root** for the rest of the task (shell `working_directory`, file paths, tests).

## Conventions (defaults)

| Item | Default |
|------|---------|
| Base branch | **`origin/develop`** — always use `develop` as `<base>` when this skill runs (after fetch and verify; see step 3) |
| Local branch prefix | `dev/` for generic work, `feature/` for user-facing features, `fix/` for bugfix |
| Name body | kebab-case, short; include issue id if user gives one, e.g. `dev/JIRA-123-slider-interval` → prefer `dev/jira-123-slider-interval` (ASCII, lowercase) |
| Worktree parent (this project) | `D:\projects\worktree` (**required** — do not skip) |

If the user provides an exact branch name, use it (after basic sanity: no spaces; replace spaces with `-`).

## Steps (run from this repository’s Git root)

Run these from whichever checkout is the user’s **current workspace** (main clone or an existing worktree); `git worktree` commands use the shared repo metadata.

1. **Status**

   - `git status -sb`
   - If there are uncommitted changes and the user did not ask to commit: **stop** and say they must commit, stash, or discard, unless they confirm stash.

2. **Update refs**

   - `git fetch origin` (or the user’s `remote` name from `git remote`).

3. **Resolve default base** (required for this skill)

   - After fetch, run `git rev-parse --verify origin/develop`. On success, set `<base>` to **`develop`** (branch from **`origin/develop`**).
   - If `origin/develop` is missing, **stop** and tell the user to fetch, create `develop` on the remote, or name another base explicitly; do **not** silently fall back to `main` / `master` unless the user overrides in the same message.
   - If the user **explicitly** asks for a different base (e.g. `main`, a release branch), use that name instead of `develop` for this run only.

4. **Choose branch name `<name>`**

   - Ensure the branch is not already checked out in another worktree: `git worktree list` (if `<name>` is in use elsewhere, **stop** or pick another name).
   - If `git show-ref --verify refs/heads/<name>` succeeds and the branch already exists **only** as a local branch, you will **link** a new worktree to it (step 5b) instead of creating it with `-b`.

5. **Create worktree under `D:\projects\worktree` (required)**

   Path rules:

   - **Folder name**: `<repo-basename>-<branch-for-filesystem>`, where `<repo-basename>` is the last segment of `git rev-parse --show-toplevel` and `<branch-for-filesystem>` is `<name>` with `/` replaced by `-` (e.g. `dev/foo` → `dev-foo`).
   - **Full path**: `D:\projects\worktree\<folder-name>`
   - The target path must not already exist; if it does, **stop** or remove the old worktree first (`git worktree remove`).

   Create the worktree parent if needed (PowerShell):

   ```powershell
   New-Item -ItemType Directory -Force -Path 'D:\projects\worktree' | Out-Null
   ```

   **5a. New branch** (branch does not exist yet — **preferred**; leaves the current checkout’s HEAD unchanged):

   ```powershell
   $wtRoot = 'D:\projects\worktree'
   $base = '<base>'   # default: develop (this skill)
   $name = '<name>'   # full branch name, e.g. feature/my-task
   $repoBase = Split-Path (git rev-parse --show-toplevel) -Leaf
   $safe = $name -replace '/', '-'
   $path = Join-Path $wtRoot ($repoBase + '-' + $safe)
   git worktree add -b $name $path "origin/$base"
   ```

   **5b. Existing local branch** (branch already exists; only add a linked folder):

   ```powershell
   $wtRoot = 'D:\projects\worktree'
   $name = '<name>'
   $repoBase = Split-Path (git rev-parse --show-toplevel) -Leaf
   $safe = $name -replace '/', '-'
   $path = Join-Path $wtRoot ($repoBase + '-' + $safe)
   git worktree add $path $name
   ```

   **Do not** use `git checkout -b` / `git checkout -B` in the **current** workspace as a substitute for this step — the branch must appear in the new worktree path.

6. **Confirm**

   - `git worktree list`, `git status -sb` and `git log -1 --oneline` **from `$path`** (the new worktree directory).
   - Report: branch name, full path `$path`, and base tip if useful.

7. **Continue in the new worktree (agent)**

   - Treat **`$path`** as the **only** active repo root for implementation: shell `working_directory` / `cd`, file reads, edits, searches, and tests.
   - Tell the user to **open that folder in the editor** (e.g. Cursor **File → Open Folder** → `$path`) if their workspace is still the main clone.
   - Proceed with commits and tooling **from `$path`** unless the user explicitly asks to switch back.

### Remove a worktree later

```powershell
git worktree remove <path>
# If Git refuses (locked files), after closing editors:
# git worktree remove --force <path>
```

### Notes

- This workflow does not copy `.env` or install dependencies; do that only if the user asks or the task needs it, matching **Optional: after branch exists** below.
- Default integration line is **`origin/develop`**; the worktree snippet uses `<base>` from step 3 (normally `develop`).

## Windows / PowerShell

- Same `git` commands; avoid bash-only `$( )` in **single-line** copy-paste for users—agent may run multiline in project shell.
- After step 5, “repo root” for implementation means **`$path`** under `D:\projects\worktree`, not necessarily the folder where the user first opened Cursor.

## Optional: after branch exists

- If this project uses `pip install` / `hatch` / `pytest`, only run install or tests if the user asked or a task requires it (keep scope to branching unless expanded).

## Anti-patterns

- Do not skip the worktree step or create the topic branch only in the main clone when this skill applies.
- Do not force-push or reset `--hard` without explicit user request.
- Do not delete the remote or default branch.
- Do not create `main` / `master` as a new topic branch name.
