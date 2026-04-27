---
description: After completing a user requirement, update CHANGELOG.md and README (and Chinese README when usage changes)
alwaysApply: true
---

# Changelog and README on task completion

When a **user requirement** (feature, fix, or user-visible change) is **finished in the same session**, do **not** end without updating docs below. Skipping this is a **task failure** unless the user explicitly said to omit docs.

## CHANGELOG.md

- Follow the existing [Keep a Changelog](https://keepachangelog.com/) style in this repo.
- Add an **`## [Unreleased]`** section if missing, or append under the current **WIP** version block the maintainers use.
- Use **`### Added` / `### Changed` / `### Fixed` / `### Removed`** as appropriate; one or two concrete bullets (what changed, not internal refactors unless notable).
- If the project already shipped a version and this change is for the **next** release, keep entries under `Unreleased` until a version bump is done elsewhere.

## README.md

- **User-facing**: If behavior, install steps, keyboard shortcuts, config paths, or limitations changed, update the matching sections in `README.md` (Usage, Requirements, etc.).
- **Not user-facing** (e.g. internal test-only refactors): README update **not** required; still add a **short CHANGELOG** line.

## README.zh-TW.md

- If any **usage or product behavior** text in the English `README.md` was updated, **update the parallel section** in `README.zh-TW.md` so both stay aligned.
- If only English marketing/technical phrasing changed with **no** behavior change, optional—prefer alignment when in doubt.

## Conflicts with other rules

- Repo text remains **English** in `README.md` and `CHANGELOG.md` (see `english-only-content.mdc`). `README.zh-TW.md` stays Traditional Chinese for the localized mirror.

## Quick checklist

- [ ] `CHANGELOG.md` has a bullet for this requirement
- [ ] `README.md` updated if users would see a difference
- [ ] `README.zh-TW.md` touched if usage/behavior in Chinese doc would differ
