# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
param(
    [string]$Python = "python",
    [int]$Jobs = 2,
    [switch]$ConfigureOnly
)
$ErrorActionPreference = "Stop"
$arguments = @((Join-Path $PSScriptRoot "native_windows_build.py"), "--jobs", "$Jobs")
if ($ConfigureOnly) { $arguments += "--configure-only" }
& $Python @arguments
if ($LASTEXITCODE -ne 0) { throw "Native Windows baseline did not complete; inspect .brushquay/evidence" }
