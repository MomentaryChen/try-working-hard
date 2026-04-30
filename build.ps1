#Requires -Version 5.1
<#
.SYNOPSIS
  Build the Windows one-file executable with PyInstaller (uv + packaging/try-working-hard.spec).

.EXAMPLE
  pwsh -File .\build.ps1
.EXAMPLE
  pwsh -File .\build.ps1 -Clean
#>
param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
if (-not $Root) { $Root = Split-Path -Parent $MyInvocation.MyCommand.Path }
Set-Location -LiteralPath $Root

Write-Host "Project root: $Root" -ForegroundColor Cyan

function Get-ProjectVersion {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PyProjectPath
    )

    if (-not (Test-Path -LiteralPath $PyProjectPath)) {
        throw "pyproject.toml not found: $PyProjectPath"
    }

    $content = Get-Content -LiteralPath $PyProjectPath -Raw
    $match = [regex]::Match($content, '(?m)^\s*version\s*=\s*"([^"]+)"\s*$')
    if (-not $match.Success) {
        throw "Could not find project version in $PyProjectPath"
    }

    return $match.Groups[1].Value.Trim()
}

function Convert-VersionToQuad {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Version
    )

    $clean = [regex]::Match($Version, '^\d+(?:\.\d+){0,3}')
    if (-not $clean.Success) {
        throw "Version '$Version' does not start with a numeric format."
    }

    $parts = $clean.Value.Split(".")
    while ($parts.Count -lt 4) { $parts += "0" }
    if ($parts.Count -gt 4) { $parts = $parts[0..3] }
    return ($parts -join ", ")
}

function New-PyInstallerVersionFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Version,
        [Parameter(Mandatory = $true)]
        [string]$OutputPath
    )

    $quad = Convert-VersionToQuad -Version $Version
    $content = @"
# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=($quad),
    prodvers=($quad),
    mask=0x3f,
    flags=0x0,
    OS=0x4,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
    ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        '040904B0',
        [StringStruct('CompanyName', 'MomentaryChen'),
        StringStruct('FileDescription', 'try-working-hard'),
        StringStruct('FileVersion', '$Version'),
        StringStruct('InternalName', 'try-working-hard'),
        StringStruct('OriginalFilename', 'try-working-hard.exe'),
        StringStruct('ProductName', 'try-working-hard'),
        StringStruct('ProductVersion', '$Version')])
      ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"@

    Set-Content -LiteralPath $OutputPath -Value $content -Encoding utf8
}

if ($Clean) {
    Write-Host "Removing build/ and dist/ ..." -ForegroundColor Yellow
    @("build", "dist") | ForEach-Object {
        $p = Join-Path $Root $_
        if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Recurse -Force }
    }
}

Write-Host "uv sync --group dev --extra build" -ForegroundColor Cyan
& uv sync --group dev --extra build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$pyprojectPath = Join-Path $Root "pyproject.toml"
$projectVersion = Get-ProjectVersion -PyProjectPath $pyprojectPath
$versionFilePath = Join-Path $Root "build\pyinstaller-version-info.txt"

New-Item -ItemType Directory -Path (Split-Path -Parent $versionFilePath) -Force | Out-Null
New-PyInstallerVersionFile -Version $projectVersion -OutputPath $versionFilePath

Write-Host "Using project version from pyproject.toml: $projectVersion" -ForegroundColor Cyan
Write-Host "pyinstaller packaging/try-working-hard.spec (version file via env)" -ForegroundColor Cyan

$previousVersionFileEnv = $env:TWH_PYI_VERSION_FILE
$env:TWH_PYI_VERSION_FILE = $versionFilePath
try {
    & uv run pyinstaller (Join-Path $Root "packaging\try-working-hard.spec") -y
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    if ($null -eq $previousVersionFileEnv) {
        Remove-Item Env:TWH_PYI_VERSION_FILE -ErrorAction SilentlyContinue
    } else {
        $env:TWH_PYI_VERSION_FILE = $previousVersionFileEnv
    }
}

$exe = Join-Path $Root "dist\try-working-hard.exe"
if (Test-Path -LiteralPath $exe) {
    Write-Host "OK: $exe" -ForegroundColor Green
} else {
    Write-Warning "Expected output not found: $exe"
    exit 1
}
