# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
param(
    [string]$Python = "python",
    [string]$Cache = ".brushquay/cache",
    [string]$Stage = ".brushquay/locked"
)
$ErrorActionPreference = "Stop"
$script = Join-Path $PSScriptRoot "locked_windows_deps.py"
& $Python $script fetch --cache $Cache --stage $Stage
if ($LASTEXITCODE -ne 0) { throw "Locked download/verification failed" }
if (Test-Path -LiteralPath $Stage) {
    & $Python $script verify --cache $Cache --stage $Stage
} else {
    & $Python $script stage --cache $Cache --stage $Stage
}
if ($LASTEXITCODE -ne 0) { throw "Locked stage validation failed" }
