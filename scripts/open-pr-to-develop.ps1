# Push the current branch, then open a PR to develop with title and body filled from this branch vs the base.
# Title: bracket tag + a short "main purpose" line (first sentence of the most important commit, heuristically chosen).
# Body: Summary (main change + extra sentences), full commit list, and diff stat.
# Requires: Git, gh (https://cli.github.com/), gh auth login
# Usage (from repo root): .\scripts\open-pr-to-develop.ps1 [-Kind feature] [-Title "..."] [-TitleCoreMax 100] [-Draft] [-WhatIf]

param(
    [ValidateSet("feature", "bug", "docs", "chore", "perf", "refactor", "test")]
    [string] $Kind,
    [string] $Title,
    [string] $Base = "develop",
    [int] $TitleMaxLength = 0,
    [int] $TitleCoreMax = 100,
    [switch] $Draft,
    [switch] $WhatIf
)

function Get-ConventionalParts {
    param([string] $Subject)
    $m = [regex]::Match(
        $Subject,
        '^(?<type>feat|fix|docs|style|refactor|perf|test|build|ci|chore)(\([^)]+\))?(?<brk>!)?:\s*(?<desc>.+)$'
    )
    if (-not $m.Success) {
        return @{ Type = $null; Description = $Subject.Trim() }
    }
    return @{
        Type        = $m.Groups["type"].Value
        Description = $m.Groups["desc"].Value.Trim()
    }
}

function Map-TypeToLabel {
    param([string] $Type)
    if (-not $Type) { return $null }
    switch ($Type.ToLower()) {
        "feat" { return "feature" }
        "fix" { return "bug" }
        "docs" { return "docs" }
        { $_ -in "chore", "build", "ci", "style" } { return "chore" }
        "perf" { return "perf" }
        "refactor" { return "refactor" }
        "test" { return "test" }
        Default { return $null }
    }
}

function Get-LabelFromBranchPrefix {
    param([string] $Branch)
    if ($Branch -notmatch '/') { return $null }
    $prefix = ($Branch -split '/')[0].ToLowerInvariant()
    switch ($prefix) {
        { $_ -in "fix", "bugfix", "hotfix" } { return "bug" }
        { $_ -in "feat", "feature" } { return "feature" }
        "docs" { return "docs" }
        { $_ -in "chore", "build", "ci", "release" } { return "chore" }
        "perf" { return "perf" }
        "refactor" { return "refactor" }
        { $_ -in "test", "tests" } { return "test" }
        "dev" { return "feature" }
        Default { return $null }
    }
}

function Limit-TitleLength {
    param([string] $Text, [int] $Max)
    if ($Max -le 0 -or $Text.Length -le $Max) { return $Text }
    if ($Max -le 3) { return $Text.Substring(0, $Max) }
    return $Text.Substring(0, $Max - 3).TrimEnd() + "..."
}

function Limit-TitleCoreShort {
    param([string] $Text, [int] $Max)
    $t = $Text.Trim()
    if ($Max -le 0 -or $t.Length -le $Max) { return $t }
    $cut = $t.Substring(0, $Max)
    $sp = $cut.LastIndexOf(' ')
    $minWordBreak = [Math]::Min(40, [Math]::Max(20, $Max / 2))
    if ($sp -ge $minWordBreak) {
        return $cut.Substring(0, $sp)
    }
    return $cut
}

function Build-TaggedTitle {
    param([string] $Label, [string] $Core, [int] $MaxTotal)
    $prefix = "[$Label] "
    if ($MaxTotal -le 0) {
        return "$prefix$Core"
    }
    $room = $MaxTotal - $prefix.Length
    if ($room -lt 12) { $room = 12 }
    $short = Limit-TitleLength $Core $room
    return "$prefix$short"
}

function Split-Sentences {
    param([string] $Text)
    $t = $Text.Trim()
    if (-not $t) { return @() }
    $parts = [regex]::Split($t, '(?<=[.!?])\s+')
    return @($parts | ForEach-Object { $_.Trim() } | Where-Object { $_.Length -gt 0 })
}

function Select-MainCommitEntry {
    param([array] $Entries)
    if ($Entries.Count -eq 1) { return $Entries[0] }
    $bestIdx = 0
    $bestScore = [long]::MinValue
    for ($i = 0; $i -lt $Entries.Count; $i++) {
        $subj = $Entries[$i].Subject
        $d = (Get-ConventionalParts $subj).Description
        $d = ($d -replace "\s+", " ").Trim()
        if (-not $d) { $d = $subj.Trim() }

        $score = [Math]::Min($d.Length, 800)
        if ($subj -match '^(Merge branch|Merge pull request|Merge remote)') {
            $score -= 300
        }
        if ($d -match '^(Add|Introduce|Implement|Enhance|Support|Enable)\b') {
            $score += 140
        } elseif ($d -match '^(Fix|Repair|Correct)\b') {
            $score += 100
        } elseif ($d -match '^(Update|Change|Adjust)\b') {
            $score += 50
        }
        if ($score -ge $bestScore) {
            $bestScore = $score
            $bestIdx = $i
        }
    }
    return $Entries[$bestIdx]
}

$ErrorActionPreference = "Stop"
Set-Location (git rev-parse --show-toplevel)

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Error "GitHub CLI (gh) is not installed or on PATH. Install from https://cli.github.com/ then run: gh auth login"
    exit 1
}

$branch = git rev-parse --abbrev-ref HEAD
if ($branch -in @("develop", "master", "main")) {
    Write-Error "Current branch is '$branch'. Switch to a topic branch first."
    exit 1
}

git fetch origin $Base 2>$null

$compare = $null
if (git rev-parse --verify "origin/$Base" 2>$null) {
    $compare = "origin/$Base"
} elseif (git rev-parse --verify $Base 2>$null) {
    $compare = $Base
} else {
    Write-Error "Cannot resolve base as '$Base' or 'origin/$Base'. Fetch or create the base branch first."
    exit 1
}

$ahead = [int](git rev-list --count "$compare..HEAD" 2>$null)
if ($ahead -eq 0) {
    if (git status --porcelain) {
        Write-Error "No commits ahead of $compare. Commit your changes, then run this script again."
    } else {
        Write-Error "No commits ahead of $compare. Nothing to publish as a PR."
    }
    exit 1
}

if (git status --porcelain) {
    Write-Warning "Working tree has uncommitted changes; the PR will only include already-committed work until you commit and push again."
}

$commitLogLines = @(git log "$compare..HEAD" --reverse --pretty=format:"%h`t%s" 2>$null)
$entries = foreach ($line in $commitLogLines) {
    if ([string]::IsNullOrWhiteSpace($line)) { continue }
    $parts = $line -split "`t", 2
    if ($parts.Count -lt 2) { continue }
    [pscustomobject]@{ Hash = $parts[0]; Subject = $parts[1] }
}
if ($entries.Count -eq 0) {
    Write-Error "Could not read commits for $compare..HEAD."
    exit 1
}

$commitLines = foreach ($e in $entries) { "- $($e.Subject) ($($e.Hash))" }
$commitsBlock = ($commitLines -join "`n")

$statLines = @(git diff "$compare...HEAD" --stat 2>$null)
$stat = if ($statLines.Count -gt 0) {
    ($statLines -join "`n").TrimEnd()
} else {
    "(no diff stat)"
}

$mdFence = '```'

$mainEntry = Select-MainCommitEntry $entries
$tipEntry = $entries[-1]
$mainConv = Get-ConventionalParts $mainEntry.Subject
$tipConv = Get-ConventionalParts $tipEntry.Subject

$fullMainText = ($mainConv.Description -replace "\s+", " ").Trim()
if (-not $fullMainText) {
    $fullMainText = $mainEntry.Subject.Trim()
}

$sentenceParts = @(Split-Sentences $fullMainText)
if ($sentenceParts.Count -eq 0) {
    $sentenceParts = @($fullMainText)
}

$firstSentenceFull = $sentenceParts[0]
if (-not $firstSentenceFull) {
    $firstSentenceFull = $fullMainText
}

# Short line for GitHub title (word-boundary cap). Body Summary uses the full first sentence.
$titleCore = Limit-TitleCoreShort $firstSentenceFull $TitleCoreMax
if (-not $titleCore) {
    $titleCore = Limit-TitleCoreShort $fullMainText $TitleCoreMax
}
if (-not $titleCore) {
    $titleCore = $branch
}

$detailParagraph = ""
if ($sentenceParts.Count -gt 1) {
    $detailParagraph = ($sentenceParts[1..($sentenceParts.Count - 1)] -join " ").Trim()
}

$label = $null
if ($Kind) {
    $label = $Kind.ToLowerInvariant()
} else {
    $label = Get-LabelFromBranchPrefix $branch
    if (-not $label) {
        $label = Map-TypeToLabel $mainConv.Type
    }
    if (-not $label) {
        $label = Map-TypeToLabel $tipConv.Type
    }
    if (-not $label) {
        $label = "chore"
    }
}

if (-not $Title) {
    $Title = Build-TaggedTitle $label $titleCore $TitleMaxLength
} else {
    $Title = $Title.Trim()
    if ($Title -notmatch '^\[[^\]]+\]\s') {
        $Title = Build-TaggedTitle $label $Title $TitleMaxLength
    } else {
        $Title = Limit-TitleLength $Title $TitleMaxLength
    }
}

$summarySection = "## Summary`n`n**Main change:** $firstSentenceFull`n"
if ($detailParagraph) {
    $summarySection += "`n$detailParagraph`n"
}

$body = @"
$summarySection
## Commits
$commitsBlock

## Files changed
$mdFence
$stat
$mdFence
"@

if ($WhatIf) {
    Write-Host "Title: $Title"
    Write-Host ""
    Write-Host $body
    exit 0
}

$tmp = [System.IO.Path]::GetTempFileName()
try {
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($tmp, $body, $utf8NoBom)

    $expectedUpstream = "origin/$branch"
    $hasUpstream = git rev-parse --abbrev-ref "@{u}" 2>$null
    if (-not $hasUpstream -or ($hasUpstream -ne $expectedUpstream)) {
        if ($hasUpstream -and $hasUpstream -ne $expectedUpstream) {
            Write-Warning "Upstream is '$hasUpstream' but this branch is '$branch'. Pushing to $expectedUpstream and setting upstream."
        }
        git push -u origin HEAD
    } else {
        git push
    }

    $ghArgs = @(
        "pr", "create",
        "--base", $Base,
        "--title", $Title,
        "--body-file", $tmp
    )
    if ($Draft) {
        $ghArgs += "--draft"
    }
    gh @ghArgs
} finally {
    Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
}
