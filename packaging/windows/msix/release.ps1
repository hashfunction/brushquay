# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
[CmdletBinding()]
param([string]$Python='python',[switch]$PreflightOnly)
$ErrorActionPreference='Stop';Set-StrictMode -Version Latest
$source=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../..'))
$binding=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'release-inputs.json') -Raw|ConvertFrom-Json
if($binding.schema -ne 1 -or $null -eq $binding.reviewed){throw 'Reviewed release-input binding is absent; release mode remains disabled.'}
if($binding.reviewed.licenseReviewComplete -isnot [bool] -or -not $binding.reviewed.licenseReviewComplete -or $binding.reviewed.correspondingSourceComplete -isnot [bool] -or -not $binding.reviewed.correspondingSourceComplete){throw 'Separate source/license review is incomplete.'}
if($PreflightOnly){return}
# A fresh native host for each installed lifecycle; no leaked script/module state.
$hostExe=Join-Path $env:WINDIR 'System32/WindowsPowerShell/v1.0/powershell.exe'
foreach($mode in @('qualification','store')){
    & $hostExe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot '../qualification/qualify.ps1') -Python $Python -ReleaseMode $mode
    if($LASTEXITCODE -ne 0){throw ('Original installed '+$mode+' lifecycle failed.')}
}
$commit=(& git -C $source rev-parse HEAD).Trim();if($LASTEXITCODE -ne 0){throw 'Cannot read current committed source'}
& $Python (Join-Path $PSScriptRoot 'store_export.py') --source $source --output (Join-Path $source '.brushquay/store-output') --commit $commit --run $env:GITHUB_RUN_ID --attempt $env:GITHUB_RUN_ATTEMPT
if($LASTEXITCODE -ne 0){throw 'Independent unsigned Store export failed.'}
