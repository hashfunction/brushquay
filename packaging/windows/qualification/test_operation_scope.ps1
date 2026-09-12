# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
# Run as a file, like the production workflow: helpers must remain script-local.
$ErrorActionPreference='Stop';Set-StrictMode -Version Latest
& {
. (Join-Path $PSScriptRoot 'qualify.ps1') -LibraryOnly
$tokens=$null;$parseErrors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot 'qualify.ps1'),[ref]$tokens,[ref]$parseErrors)
if($parseErrors.Count){throw 'Production qualification does not parse'}
$normal=@('Preflight','PreparePackage','OwnFixtureProfile','SignAndInstall','ConsumerWorkflow','VerifyFiles','Uninstall')
$cleanup=@('StopObserver','UninstallIfNeeded','RestoreDisplay','RemoveFixture','RemoveProfile','RemoveCertificates','RemoveSignedCopy')
$temp=Join-Path ([IO.Path]::GetTempPath()) ('bristlune-scope-'+[guid]::NewGuid().ToString('N'))
[IO.Directory]::CreateDirectory($temp)|Out-Null
$sentinel=Join-Path $temp 'brushquay-existing-profile';[IO.File]::WriteAllText($sentinel,'preserve')
$oldLocal=$env:LOCALAPPDATA;$oldRoaming=$env:APPDATA
try {
    $env:LOCALAPPDATA=$temp;$env:APPDATA=$temp
    # Construct the actual production callbacks while the declaring scope is
    # alive, exactly as Invoke-InstalledQualification calls its lifecycle core.
    & {
        $state=@{installAttempted=$false;observer=$null;displayOriginalMode=$null;
            fixtureLease=$null;profileLease=$null;certificate=$null;unsigned=$null;signedCopy=$null}
        $ops=[ordered]@{}
        foreach($name in $normal){$ops[$name]={throw 'A mutation phase ran after the preflight refusal'}}
        foreach($name in @('Preflight')+$cleanup){
            $left='$ops.'+$name
            $matches=@($ast.FindAll({param($node)
                $node -is [Management.Automation.Language.AssignmentStatementAst] -and $node.Left.Extent.Text -ceq $left
            },$true))
            if($matches.Count -ne 1){throw "Expected one actual production callback: $left"}
            . ([scriptblock]::Create($left+'='+$matches[0].Right.Extent.Text))
        }
        $result=Invoke-QualificationCore $ops
        $expected="Existing BrushQuay profile/config/log files are preserved; fresh disposable profile required: $temp"
        if($result.passed -or $result.primaryError -cne $expected){throw ("Actual preflight helper was not reached: "+$result.primaryError)}
        if($result.cleanupErrors.Count){throw ('Actual cleanup helper resolution failed: '+($result.cleanupErrors -join '; '))}
    }
    if([IO.File]::ReadAllText($sentinel) -cne 'preserve'){throw 'Pre-existing profile sentinel was changed'}
} finally {
    $env:LOCALAPPDATA=$oldLocal;$env:APPDATA=$oldRoaming
    Remove-Item -LiteralPath $temp -Recurse -Force
}
Write-Output 'PASS actual production callbacks in script scope: profile refusal, unchanged sentinel, all cleanup helpers.'
}
