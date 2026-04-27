---
name: open-pr-to-develop
description: >-
  Push the current branch and open a GitHub PR to develop. Title is concise with
  a bracket tag plus a short main-purpose title (from the best-scoring commit’s first
  sentence), with Summary + full commits + diff stat in the body. Use when the user
  asks to open a PR to develop or run pr-to-develop.
---

# Open PR to develop (this repo)

## Goal

Create a **GitHub PR** with **base `develop`**, after **pushing** the current branch. The **title** is **`[tag]`** plus a **brief main-change line** derived from all commits in the range (pick the “main” commit by heuristic, then **first sentence**, **`-TitleCoreMax`**). The **body** has **Summary** (main change + remaining sentences), **Commits** (full list), and **`git diff --stat`**. Tag from **`-Kind`**, branch prefix, main/tip conventional type, or **`chore`**. Optional **`-TitleMaxLength`** caps the whole title.

## Preconditions

- Current branch is **not** `develop`, `master`, or `main`.
- At least **one commit** exists that is **not** in `origin/develop` (agent should suggest `git fetch origin develop` if needed).
- **`gh`** is installed and authenticated (`gh auth login`).
- Prefer a **clean** working tree for the PR to match “this change”; if there are uncommitted files, the script warns—the user should commit first if they want everything included.

## Steps

1. From the repo root (`git rev-parse --show-toplevel`), run:

   ```powershell
   pwsh -NoProfile -File scripts/open-pr-to-develop.ps1
   ```

2. Optional flags: `-Kind`, `-Title`, `-TitleMaxLength`, `-Draft`, `-WhatIf` (preview only).

3. If the script errors on “no commits ahead”, tell the user to **commit** (and push is done by the script).

## Do not

- Create or rely on GitHub Actions for opening the PR (user preference: local `git` + `gh` only).
- Force-push or rewrite history unless the user explicitly asks.
