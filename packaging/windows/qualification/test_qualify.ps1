# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
$ErrorActionPreference='Stop';Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'qualify.ps1') -LibraryOnly
$normal=@('Preflight','PreparePackage','OwnFixtureProfile','SignAndInstall','ConsumerWorkflow','VerifyFiles','Uninstall')
$cleanup=@('StopObserver','UninstallIfNeeded','RestoreDisplay','RemoveFixture','RemoveProfile','RemoveCertificates','RemoveSignedCopy')
foreach($failure in @('')+$normal+$cleanup){
 $calls=[Collections.Generic.List[string]]::new();$ops=[ordered]@{}
 foreach($name in @($normal)+@($cleanup)){$step=$name;$ops[$name]={ $calls.Add($step);if($step -ceq $failure){throw ('failure '+$step)} }.GetNewClosure()}
 $result=Invoke-QualificationCore $ops
 if($failure -eq ''){if(-not $result.passed){throw 'Complete normal/cleanup sequence failed'}}elseif($result.passed){throw "Failure was accepted: $failure"}
 if(($calls.GetRange($calls.Count-$cleanup.Count,$cleanup.Count) -join ',') -cne ($cleanup -join ',')){throw "Cleanup order/integrity changed after $failure"}
 if($normal -contains $failure -and $result.primaryError -cne ('failure '+$failure)){throw 'Primary error lost'}
 if($cleanup -contains $failure -and $result.cleanupErrors.Count -ne 1){throw 'Cleanup failure lost'}
}
$temp=Join-Path ([IO.Path]::GetTempPath()) ('bristlune-ps-'+[guid]::NewGuid().ToString('N'));[IO.Directory]::CreateDirectory($temp)|Out-Null
try{
 $original=Join-Path $temp 'original.json';Write-NewJson $original @{value='keep'};$hash=(Get-FileHash -LiteralPath $original).Hash
 $rejected=$false;try{Write-NewJson $original @{value='overwrite'}}catch{$rejected=$true}
 if(-not $rejected -or (Get-FileHash -LiteralPath $original).Hash -cne $hash){throw 'Exclusive JSON output overwrote original bytes'}
 $state=@{activationAttempted=$true;gui=$temp};$rejected=$false;try{Read-StopProof $state}catch{$rejected=$true};if(-not $rejected){throw 'Absent process receipt accepted'}
 Write-NewJson (Join-Path $temp 'gui-observations.json') @{ownedProcessesStopped=$false}
 $rejected=$false;try{Read-StopProof $state}catch{$rejected=$true};if(-not $rejected){throw 'Live/unproved process accepted'}
}finally{Remove-Item -LiteralPath $temp -Recurse -Force}
Write-Output 'PASS actual lifecycle: normal path, 14 phase/cleanup failures, exclusive metadata, missing/false stop proof.'
