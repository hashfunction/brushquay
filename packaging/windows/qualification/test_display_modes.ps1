$ErrorActionPreference='Stop';Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'display-modes.ps1')
function Check($Condition,[string]$Message){if(-not $Condition){throw $Message}}
Add-GuiDisplayTypes
Check ([Runtime.InteropServices.Marshal]::SizeOf([BristluneGui.Mode]::new()) -eq 220 -and
    [Runtime.InteropServices.Marshal]::OffsetOf([BristluneGui.Mode],'dmPelsWidth').ToInt32() -eq 172 -and
    [Runtime.InteropServices.Marshal]::SizeOf([BristluneGui.DisplayDevice]::new()) -eq 840) 'Native Unicode display structure layout differs.'
foreach($flag in @(1,0x100,0x200,0x10000000)){
    $failed=$false;try{$null=[BristluneGui.DisplayModes]::Change('not-a-device',[BristluneGui.Mode]::new(),$flag)}catch{$failed=$_.Exception.Message -match 'Only native test and dynamic change'}
    Check $failed 'Persistent, unsafe or other unapproved native change flags reached the OS.'
}
function Mode($Width,$Height,$Bits=32){[pscustomobject]@{dmPositionX=0;dmPositionY=0;dmDisplayFixedOutput=0;dmPelsWidth=$Width;dmPelsHeight=$Height;dmBitsPerPel=$Bits;dmDisplayFrequency=60;dmDisplayOrientation=0;dmDisplayFlags=0;dmDriverExtra=0}}
$original=Mode 1024 768;$desired=Mode 1920 1080
Check ((Get-GuiModeChoice @((Mode 1280 720),$desired,(Mode 2560 1440))).dmPelsWidth -eq 1920) 'A supported 1080p mode was not selected.'
foreach($modes in @(@((Mode 1024 768)),@((Mode 1920 1080 16)),@((Mode 4000 3000)))){
    $failed=$false;try{$null=Get-GuiModeChoice $modes}catch{$failed=$true};Check $failed 'Absent/unsafe/oversized supported mode was accepted.'
}
$script:current=$original;$script:calls=[Collections.Generic.List[int]]::new();$script:rejectTest=$false;$script:partialApplyFailure=$false;$script:rejectRestore=$false
function Get-GuiDisplayState([string]$Device){@{device='fixture-primary';current=$script:current;modes=@($original,$desired)}}
function Set-GuiDisplayMode([string]$Device,$Mode,[int]$Flags){$script:calls.Add($Flags);if($Flags -eq 2){if($script:rejectTest){return -2};return 0};if($script:rejectRestore -and $Mode.dmPelsWidth -eq 1024){return -1};$script:current=$Mode;if($script:partialApplyFailure -and $Mode.dmPelsWidth -eq 1920){return -1};return 0}
$state=@{displayOriginalMode=$null;displayDevice=$null;displayRestoreRequired=$false;displayEvidence=$null}
Start-GuiDisplay $state
Check ($script:current.dmPelsWidth -eq 1920 -and $script:calls.Count -eq 2 -and $script:calls[0] -eq 2 -and $script:calls[1] -eq 0) 'Production display change skipped native test or used persistent/unsafe flags.'
Restore-GuiDisplay $state
Check ($script:current.dmPelsWidth -eq 1024 -and $state.displayEvidence.restore_verified -eq $true) 'Production restore did not restore the retained original mode.'
$script:calls.Clear();$script:rejectTest=$true
$state=@{displayOriginalMode=$null;displayDevice=$null;displayRestoreRequired=$false;displayEvidence=$null}
$failed=$false;try{Start-GuiDisplay $state}catch{$failed=$true}
Check ($failed -and $script:calls.Count -eq 1 -and $script:current.dmPelsWidth -eq 1024 -and -not $state.displayRestoreRequired) 'Failed CDS_TEST changed the actual mode.'
$script:calls.Clear();$script:rejectTest=$false;$script:partialApplyFailure=$true
$state=@{displayOriginalMode=$null;displayDevice=$null;displayRestoreRequired=$false;displayEvidence=$null}
$failed=$false;try{Start-GuiDisplay $state}catch{$failed=$true}
Check ($failed -and $state.displayRestoreRequired -and $script:current.dmPelsWidth -eq 1920) 'Partial native apply failure lost required restoration state.'
Restore-GuiDisplay $state
Check ($script:current.dmPelsWidth -eq 1024 -and $state.displayEvidence.restore_verified -eq $true -and $script:calls[2] -eq 0) 'Partial apply failure did not restore the retained original mode dynamically.'
Write-Output 'PASS: native structure/flag boundary, enumerated safe selection, test-before-apply, flags 0, original-mode restoration, failed-test preservation and partial-apply recovery.'

$script:calls.Clear();$script:partialApplyFailure=$false;$script:current=$original;$saved=$false
$state=@{displayOriginalMode=$null;displayDevice=$null;displayRestoreRequired=$false;displayEvidence=$null;displayRestoreError=$null}
$failure=$null
try{Invoke-GuiDisplayScope $state {throw 'controlled helper timeout'} {$script:saved=$true}}catch{$failure=$_.Exception.Message}
Check ($failure -match 'controlled helper timeout' -and $script:current.dmPelsWidth -eq 1024 -and $state.displayEvidence.restore_verified -and $script:saved) 'Helper failure did not restore display and preserve evidence.'
$script:saved=$false;$script:partialApplyFailure=$true
$state=@{displayOriginalMode=$null;displayDevice=$null;displayRestoreRequired=$false;displayEvidence=$null;displayRestoreError=$null}
$failure=$null
try{Invoke-GuiDisplayScope $state {throw 'must not run'} {$script:saved=$true}}catch{$failure=$_.Exception.Message}
Check ($failure -match 'Native dynamic display change failed' -and $script:current.dmPelsWidth -eq 1024 -and $state.displayEvidence.restore_verified -and $script:saved) 'Partial display apply failure lost outer restoration.'
Write-Output 'PASS actual display scope restores on helper failure and partial apply, and always preserves evidence.'

$script:partialApplyFailure=$false;$script:rejectRestore=$true;$script:saved=$false
$state=@{displayOriginalMode=$null;displayDevice=$null;displayRestoreRequired=$false;displayEvidence=$null;displayRestoreError=$null}
$failure=$null
try{Invoke-GuiDisplayScope $state {} {$script:saved=$true}}catch{$failure=$_.Exception.Message}
Check ($failure -match 'Native display restoration failed' -and $state.displayRestoreError -match 'restoration failed' -and -not $state.displayEvidence.restore_verified -and $script:saved) 'Display restore failure did not fail qualification and preserve evidence.'
$script:rejectRestore=$false;$script:current=$desired;$script:calls.Clear()
$state=@{displayOriginalMode=$null;displayDevice=$null;displayRestoreRequired=$false;displayEvidence=$null;displayRestoreError=$null}
Invoke-GuiDisplayScope $state {} {}
Check ($script:calls.Count -eq 0 -and $state.displayEvidence.restore_verified) 'Adequate unchanged native desktop was mutated.'
Write-Output 'PASS restoration failure remains fatal with evidence; adequate original display stays unchanged.'
