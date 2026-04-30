---
name: release-tag-pr-to-master
description: >-
  Prepares release documentation and version for a user-supplied v* tag, then opens
  GitHub PRs targeting master (production merge + tag) and develop (integration
  sync). Use when the user gives a release tag, asks to sync release notes or
  CHANGELOG for a version, or to open merge-to-master and merge-to-develop release PRs.
---

# Release tag: sync notes, PR to master, and PR to develop

## Goal

Given a **version tag** the user provides (e.g. `v1.0.1`), align **release notes and package version** in the repo, then open:

1. A **pull request with base `master`** so production can advance and you can tag from `master` after merge.
2. A **pull request with base `develop`** from the **same topic branch** so `develop` receives the same `CHANGELOG` / `pyproject.toml` / README release commits (integration branch stays aligned with the release line).

After the **master** PR merges, **push the same tag** from `master` so `.github/workflows/release.yml` can run.

## Inputs

- **Tag**: Must match `v*` (Semantic Versioning). Normalize if the user omits `v` (e.g. `1.0.1` → `v1.0.1`).
- **Release date**: Use **today’s date** from the user environment (`Today's date` in chat metadata) for the new `CHANGELOG.md` section unless the user specifies another ISO date.

## Sync release notes (CHANGELOG and version)

1. **`CHANGELOG.md`** (Keep a Changelog style, English only):
   - Add a dated section: `## [X.Y.Z] - YYYY-MM-DD` where `X.Y.Z` is the tag **without** the `v` prefix.
   - Move (or copy) all bullets from `## [Unreleased]` that belong to this release into the new section under `### Added` / `### Changed` / `### Fixed` / `### Removed` as appropriate.
   - Leave `## [Unreleased]` in place; it may be empty or keep only items **not** shipping in this release.
2. **`pyproject.toml`**: Set `version = "X.Y.Z"` to match the tag (no `v`).

   **Why this is mandatory for artifacts:** The `[project] version` field is the **source of truth** for PEP 621 metadata. Build backends (`hatchling`, `setuptools`, etc.) and commands such as `python -m build` or `uv build` name outputs from this value only. If it stays at an old number, **`dist/` will still contain** sdist and wheel files like `try_working_hard-1.0.0.tar.gz` even when the human intent, tag, or `CHANGELOG` say `v1.1.0`—the archive filename does not infer the tag; it comes only from `pyproject.toml`.

   If the package exposes a **fallback** `__version__` when `importlib.metadata` fails (e.g. uninstalled `editable` or script runs), keep that string in sync with `X.Y.Z` on release so dev-only runs are not stuck on a stale number.

3. **User-facing docs**: If `README.md` mentions the latest version or release highlights, update to match. If usage or behavior text in `README.md` changed, update the parallel section in `README.zh-TW.md` per `.cursor/rules/update-changelog-and-readme-complement.md`.
4. **Commits**: Prefer one or two clear commits (e.g. `chore(release): bump version to X.Y.Z` and changelog-only if splitting helps review).

## Branch and PRs (master and develop)

1. Work on a **topic branch**, never directly on `master` or `develop` (the PR script rejects base branches).
   - Suggested name: `release/vX.Y.Z` or `chore/release-vX.Y.Z`.
2. **Optional conflict check** before the PRs: after `git fetch origin master`, run `git merge --no-commit --no-ff origin/master`; resolve conflicts or rebase; if only verifying, `git merge --abort`. If `master` has diverged and a normal merge would duplicate or conflict heavily, consider `git merge -s ours origin/master` **once** on the release branch to record `master` in history while keeping the tree from `develop` (then **master** can fast-forward when merging the release PR—verify with a local test merge).
3. **Push** the topic branch: `git push -u origin <branch>`.
4. From repo root, open **both** PRs with **`scripts/open-pr-to-develop.ps1`** (run twice; same branch, different `-Base`):

   **Production (required for tagging):**

   ```powershell
   pwsh -NoProfile -File scripts/open-pr-to-develop.ps1 -Base master -Kind chore -Title "[chore] Release vX.Y.Z"
   ```

   **Integration sync (keep `develop` aligned with the release commits):**

   ```powershell
   pwsh -NoProfile -File scripts/open-pr-to-develop.ps1 -Base develop -Kind chore -Title "[chore] Sync release vX.Y.Z to develop"
   ```

   Override `-Title` if a different convention is needed. Use `-WhatIf` to preview title and body. Requires **`gh`** authenticated (`gh auth login`).

   Merge order is flexible unless the team mandates one: often **master** first (then tag), then **develop**; merging **develop** first is acceptable if it only adds the synced version/changelog and does not block the **master** release PR.

## After the master PR merges (tag push)

GitHub Releases for this repo are driven by **pushing `v*` tags** (`release.yml`). On the updated `master`:

```powershell
git checkout master
git pull origin master
git tag vX.Y.Z
git push origin vX.Y.Z
```

Use the **exact** tag the user requested. If that tag already exists remotely, do not overwrite; ask how to proceed.

## Do not

- Skip the **develop** PR unless the user explicitly asks for a master-only release (default workflow opens both).
- Add non-English content to `CHANGELOG.md` or `README.md` (see `.cursor/rules/english-only-content.mdc`).
- Push the release tag before `master` contains the release commits, unless the user explicitly orders a different process.

## Quick checklist

- [ ] Tag normalized to `v*`
- [ ] `CHANGELOG.md` has `## [X.Y.Z] - date` and `Unreleased` updated
- [ ] `pyproject.toml` version matches `X.Y.Z` (so `dist/*.tar.gz` / `*.whl` names match the release; bump any `__version__` fallback in code if present)
- [ ] README / `README.zh-TW.md` updated if user-visible release info changed
- [ ] Topic branch; merge test against `origin/master` clean (or resolved with documented strategy)
- [ ] `open-pr-to-develop.ps1 -Base master` run; user merges PR to **master**
- [ ] `open-pr-to-develop.ps1 -Base develop` run; user merges PR to **develop**
- [ ] Tag created on `master` and pushed to trigger release workflow
