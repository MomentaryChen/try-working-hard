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

Write-Host "pyinstaller packaging/try-working-hard.spec" -ForegroundColor Cyan
& uv run pyinstaller (Join-Path $Root "packaging\try-working-hard.spec") -y
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$exe = Join-Path $Root "dist\try-working-hard.exe"
if (Test-Path -LiteralPath $exe) {
    Write-Host "OK: $exe" -ForegroundColor Green
} else {
    Write-Warning "Expected output not found: $exe"
    exit 1
}
