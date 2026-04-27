# Open PR to develop

Opens a GitHub pull request targeting **develop** for the current branch. The PR **title** is **`[tag]` + one short “main purpose” line**: the script picks the **most important commit** in the range (heuristic: de-prioritizes `Merge …`, boosts `Add` / `Introduce` / `Fix`, prefers longer substantive messages, tie → later commit), then uses its **first sentence**, trimmed to **`-TitleCoreMax`** (default **100** chars, word boundary). The **body** starts with **Summary** (**Main change** + any **following sentences** from that commit), then **Commits** (full subjects) and **Files changed** (`git diff --stat`). Tag order: **`-Kind`**, **branch prefix**, **main commit’s** `feat:`/`fix:`/…, else **tip commit**, else **`[chore]`**. Optional **`-TitleMaxLength`** caps the **entire** title line (`0` = no extra cap).

## Before you submit

Confirm your branch will not conflict with the target base (default **`develop`**) so the PR is mergeable and you avoid surprise failures in CI or review.

1. Update remote refs: `git fetch origin develop`
2. Try a **local merge test** (does not require pushing):
   - `git merge --no-commit --no-ff origin/develop`
   - If Git reports **conflicts**, stop: resolve them (for example by merging or rebasing onto `origin/develop`) before you run the script, or run `git merge --abort` and fix on a clean plan.
   - If the merge **completes without conflicts** and you only needed a check, run `git merge --abort` to drop the test merge. If you intend to **merge `develop` into your branch** before the PR, complete the merge with a commit instead of aborting.

## Run (repository root)

```powershell
pwsh -NoProfile -File scripts/open-pr-to-develop.ps1
```

## Options

- `-Kind feature|bug|docs|chore|perf|refactor|test` — force the bracket label
- `-Title "Override"` — custom subject line; a tag is prepended unless the text already starts with `[tag] `
- `-TitleCoreMax 100` — max length for the short “main purpose” fragment (first sentence, word boundary)
- `-TitleMaxLength` — optional cap on the **full** title including `[tag]` (`0` = no cap)
- `-Draft` — open as draft PR
- `-Base branch` — override base (default `develop`)
- `-WhatIf` — print title and body only; no push or PR

## Requirements

- Commits on the current branch that are **not** already in `origin/develop`
- `gh` installed and `gh auth login` completed
- Not on `develop`, `master`, or `main`

Uncommitted changes are warned and are **not** included until you commit and run again.
