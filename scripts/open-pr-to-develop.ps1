# Push the current branch with git, then open a PR to develop via GitHub CLI (no GitHub Actions).
# Requires: Git, gh (https://cli.github.com/), gh auth login
# Usage (from repo root): .\scripts\open-pr-to-develop.ps1 [-Title "optional title"] [-Draft]

param(
    [string] $Title,
    [switch] $Draft
)

$ErrorActionPreference = "Stop"
Set-Location (git rev-parse --show-toplevel)

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Error "GitHub CLI (gh) is not installed or not on PATH. Install from https://cli.github.com/ then run: gh auth login"
    exit 1
}

$branch = git rev-parse --abbrev-ref HEAD
if ($branch -in @("develop", "master", "main")) {
    Write-Error "Current branch is '$branch'. Switch to a topic branch first."
    exit 1
}

$hasUpstream = git rev-parse --abbrev-ref "@{u}" 2>$null
if (-not $hasUpstream) {
    git push -u origin HEAD
} else {
    git push
}

$ghArgs = @("pr", "create", "--base", "develop")
if ($Title) {
    $ghArgs += @("--title", $Title)
} else {
    $ghArgs += "--fill"
}
if ($Draft) {
    $ghArgs += "--draft"
}

gh @ghArgs
