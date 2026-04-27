---
name: release-tag-pr-to-master
description: >-
  Prepares release documentation and version for a user-supplied v* tag, then opens
  a GitHub PR targeting master. Use when the user gives a release tag, asks to sync
  release notes or CHANGELOG for a version, or to open a merge-to-master release PR.
---

# Release tag: sync notes and PR to master

## Goal

Given a **version tag** the user provides (e.g. `v1.0.1`), align **release notes and package version** in the repo, then open a **pull request with base `master`**. After the PR merges, **push the same tag** from `master` so `.github/workflows/release.yml` can run.

## Inputs

- **Tag**: Must match `v*` (Semantic Versioning). Normalize if the user omits `v` (e.g. `1.0.1` → `v1.0.1`).
- **Release date**: Use **today’s date** from the user environment (`Today's date` in chat metadata) for the new `CHANGELOG.md` section unless the user specifies another ISO date.

## Sync release notes (CHANGELOG and version)

1. **`CHANGELOG.md`** (Keep a Changelog style, English only):
   - Add a dated section: `## [X.Y.Z] - YYYY-MM-DD` where `X.Y.Z` is the tag **without** the `v` prefix.
   - Move (or copy) all bullets from `## [Unreleased]` that belong to this release into the new section under `### Added` / `### Changed` / `### Fixed` / `### Removed` as appropriate.
   - Leave `## [Unreleased]` in place; it may be empty or keep only items **not** shipping in this release.
2. **`pyproject.toml`**: Set `version = "X.Y.Z"` to match the tag (no `v`).
3. **User-facing docs**: If `README.md` mentions the latest version or release highlights, update to match. If usage or behavior text in `README.md` changed, update the parallel section in `README.zh-TW.md` per `.cursor/rules/changelog-readme-on-completion.mdc`.
4. **Commits**: Prefer one or two clear commits (e.g. `chore(release): bump version to X.Y.Z` and changelog-only if splitting helps review).

## Branch and PR to master

1. Work on a **topic branch**, never directly on `master` or `develop` (the PR script rejects base branches).
   - Suggested name: `release/vX.Y.Z` or `chore/release-vX.Y.Z`.
2. **Conflict check** (mirror `.cursor/commands/pr-to-develop.md` intent): after `git fetch origin master`, run `git merge --no-commit --no-ff origin/master`; resolve conflicts or rebase; if only verifying, `git merge --abort`.
3. From repo root, open the PR with **`scripts/open-pr-to-develop.ps1`** and **`-Base master`**:

   ```powershell
   pwsh -NoProfile -File scripts/open-pr-to-develop.ps1 -Base master -Kind chore -Title "[chore] Release vX.Y.Z"
   ```

   Override `-Title` if a different convention is needed. Use `-WhatIf` to preview title and body. Requires **`gh`** authenticated (`gh auth login`).

## After the PR merges (tag push)

GitHub Releases for this repo are driven by **pushing `v*` tags** (`release.yml`). On the updated `master`:

```powershell
git checkout master
git pull origin master
git tag vX.Y.Z
git push origin vX.Y.Z
```

Use the **exact** tag the user requested. If that tag already exists remotely, do not overwrite; ask how to proceed.

## Do not

- Open a PR to `develop` for this workflow unless the user explicitly changes the target.
- Add non-English content to `CHANGELOG.md` or `README.md` (see `.cursor/rules/english-only-content.mdc`).
- Push the release tag before `master` contains the release commits, unless the user explicitly orders a different process.

## Quick checklist

- [ ] Tag normalized to `v*`
- [ ] `CHANGELOG.md` has `## [X.Y.Z] - date` and `Unreleased` updated
- [ ] `pyproject.toml` version matches `X.Y.Z`
- [ ] README / `README.zh-TW.md` updated if user-visible release info changed
- [ ] Topic branch; merge test against `origin/master` clean
- [ ] `open-pr-to-develop.ps1 -Base master` run; user merges PR
- [ ] Tag created on `master` and pushed to trigger release workflow
