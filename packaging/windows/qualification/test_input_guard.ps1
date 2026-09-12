# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
$ErrorActionPreference='Stop';Set-StrictMode -Version Latest
Add-Type -Path (Join-Path $PSScriptRoot 'InputGuard.cs')
function Snapshot {
 $s=[BristluneQualification.InputSnapshot]::new()
 $s.pid=72;$s.nativePid=72;$s.foregroundPid=72;$s.targetPid=72;$s.hitPid=72
 $s.window=200;$s.foreground=200;$s.main=100;$s.ownerRoot=100;$s.hitRoot=200
 $s.title='Saving As';$s.targetName='Save';$s.targetId='1';$s.targetClass='Button';$s.enabled=$true
 $s.windowBounds=@(200,100,600,500);$s.targetBounds=@(650,540,80,30);$s.desktop=@(0,0,1920,1080)
 return $s
}
$before=Snapshot
[BristluneQualification.InputGuard]::Stable($before,(Snapshot),72,100,$true)
$mutations=@{
 'foreign target'={param($s)$s.targetPid=99};'foreign native window'={param($s)$s.nativePid=99}
 'foreign foreground'={param($s)$s.foregroundPid=99};'same process other foreground'={param($s)$s.foreground=201}
 'wrong owner chain'={param($s)$s.ownerRoot=200};'foreign pointer target'={param($s)$s.hitPid=99}
 'same process wrong pointer root'={param($s)$s.hitRoot=201};'replaced window'={param($s)$s.window=201;$s.foreground=201;$s.hitRoot=201}
 'disabled'={param($s)$s.enabled=$false};'offscreen'={param($s)$s.offscreen=$true}
 'changed dialog title'={param($s)$s.title='Foreign'};'changed target id'={param($s)$s.targetId='2'}
 'moved target'={param($s)$s.targetBounds=@(650,541,80,30)};'resized window'={param($s)$s.windowBounds=@(200,100,601,500)}
 'outside desktop'={param($s)$s.desktop=@(0,0,700,500)};'desktop mutation'={param($s)$s.desktop=@(0,0,2048,1080)}
 'nonfinite'={param($s)$s.targetBounds[0]=[double]::NaN};'outside target window'={param($s)$s.targetBounds=@(850,540,80,30)}
}
foreach($name in $mutations.Keys){$s=Snapshot;& $mutations[$name] $s;$rejected=$false;try{[BristluneQualification.InputGuard]::Stable($before,$s,72,100,$true)}catch{$rejected=$true};if(-not $rejected){throw "Unsafe owned input accepted: $name"}}
$negative=Snapshot;$negative.desktop=@(-1920,0,1920,1080);$negative.windowBounds=@(-1000,100,600,500);$negative.targetBounds=@(-550,540,80,30)
[BristluneQualification.InputGuard]::Stable($negative,$negative,72,100,$true)
Write-Output 'PASS actual input guard: owned native picker, negative desktop, and 18 ownership/geometry mutations.'

# Offscreen UIA rectangles may be infinite; metadata uses null, input still refuses them.
if($null -ne [BristluneQualification.InputGuard]::DiagnosticBounds(@([double]::PositiveInfinity,0,10,10))){throw 'Nonfinite diagnostic bounds were serialized'}
if($null -eq [BristluneQualification.InputGuard]::DiagnosticBounds(@(0,0,10,10))){throw 'Finite diagnostic bounds were lost'}
