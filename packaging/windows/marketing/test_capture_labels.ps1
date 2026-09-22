# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
# Compile the actual expected-label expression with Windows filename inputs.
$ErrorActionPreference='Stop';Set-StrictMode -Version Latest
$body=Get-Content (Join-Path $PSScriptRoot 'Workflow.capture.cs.txt') -Raw
$match=[regex]::Matches($body,'Find\(outcome, e => e.Current.Name == (.+), "exact successful export destination"\);')
if($match.Count -ne 1){throw 'Exact captured export-result predicate missing'}
$code='using System; using System.IO; public static class CaptureLabelReplay { public static bool Match(string fixture,string actual) {return actual == '+$match[0].Groups[1].Value+';} }'
Add-Type -TypeDefinition $code
$expected='Export created: C:/Bristlune Demo/Moonlit Garden.png'
if(-not [CaptureLabelReplay]::Match('C:\Bristlune Demo',$expected)){throw 'Actual capture predicate does not match the source-defined Qt Windows output path'}
foreach($bad in @('Export created: C:\Bristlune Demo\Moonlit Garden.png','Export created: C:/Other/Moonlit Garden.png','Export created: C:/Bristlune Demo/other.png',($expected+"`nwarning"),'Export failed: C:/Bristlune Demo/Moonlit Garden.png')){
    if([CaptureLabelReplay]::Match('C:\Bristlune Demo',$bad)){throw 'Foreign output text accepted'}
}
Write-Output 'PASS actual capture output predicate: exact Qt Windows path and five foreign/native-spelling/error mutations.'
