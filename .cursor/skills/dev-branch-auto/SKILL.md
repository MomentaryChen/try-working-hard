---
name: dev-branch-auto
description: Provisions a local git development branch from the default remote base with consistent naming, fetch, and safety checks. Use when the user asks to create a dev branch, feature branch, topic branch, or automatically set up a branch for parallel work in this repository.
---

# Dev branch auto-setup (this project)

## When to use

- User wants a **new development / feature / fix branch** from the default line.
- User says **create a dev branch**, **open a feature branch**, **branch off from main**, etc.
- Do **not** use this for full **git worktree** + copy `.env` + install deps; that is a heavier workflow (see the user’s separate worktree skill if present).

## Conventions (defaults)

| Item | Default |
|------|---------|
| Base branch | Resolve with `git symbolic-ref refs/remotes/origin/HEAD` or try `main`, then `master` |
| Local branch prefix | `dev/` for generic work, `feature/` for user-facing features, `fix/` for bugfix |
| Name body | kebab-case, short; include issue id if user gives one, e.g. `dev/JIRA-123-slider-interval` → prefer `dev/jira-123-slider-interval` (ASCII, lowercase) |

If the user provides an exact branch name, use it (after basic sanity: no spaces; replace spaces with `-`).

## Steps (run in repo root)

1. **Status**

   - `git status -sb`
   - If there are uncommitted changes and the user did not ask to commit: **stop** and say they must commit, stash, or discard, unless they confirm stash.

2. **Update refs**

   - `git fetch origin` (or the user’s `remote` name from `git remote`).

3. **Resolve default base** (one of):

   - `git rev-parse --verify origin/main 2>/dev/null` → use `main`
   - else `git rev-parse --verify origin/master` → use `master`
   - else first remote head: `git remote show origin` / `git branch -r` and ask if ambiguous.

4. **Create branch**

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

## Windows / PowerShell

- Same `git` commands; avoid bash-only `$( )` in **single-line** copy-paste for users—agent may run multiline in project shell.
- Path for repo: use this workspace’s root (`git rev-parse --show-toplevel`).

## Optional: after branch exists

- If this project uses `pip install` / `hatch` / `pytest`, only run install or tests if the user asked or a task requires it (keep scope to branching unless expanded).

## Anti-patterns

- Do not force-push or reset `--hard` without explicit user request.
- Do not delete the remote or default branch.
- Do not create `main` / `master` as a new topic branch name.
