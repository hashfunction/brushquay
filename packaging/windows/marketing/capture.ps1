# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
# Separate exact-product marketing capture; does not qualify or rebuild the product.
param([Parameter(Mandatory)][string]$Inputs,[Parameter(Mandatory)][string]$QualifiedSource,[Parameter(Mandatory)][string]$Output)
$ErrorActionPreference='Stop';Set-StrictMode -Version Latest
$qualifiedHelpers=Join-Path ([IO.Path]::GetFullPath($QualifiedSource)) 'packaging/windows/qualification'
. (Join-Path $qualifiedHelpers 'qualify.ps1') -LibraryOnly
Assert-InstallerHost
if($env:GITHUB_ACTIONS -cne 'true' -or $env:RUNNER_OS -cne 'Windows' -or $env:GITHUB_REPOSITORY -cne 'hashfunction/brushquay' -or $env:GITHUB_EVENT_NAME -cne 'workflow_dispatch'){throw 'Only separate manual isolated Windows marketing capture is supported'}
$Python='python';$capture=$PSScriptRoot
Invoke-Native $Python @((Join-Path $capture 'capture_checks.py'),'--inputs',$Inputs,'--qualified-source',$QualifiedSource)
$bound=(Get-Content (Join-Path $capture 'binding.json') -Raw|ConvertFrom-Json).qualified
$record=Get-Content (Join-Path $Inputs 'verified-package.json') -Raw|ConvertFrom-Json
$identity=Get-QualificationIdentity store
$output=[IO.Path]::GetFullPath($Output)
if(Test-Path -LiteralPath $output){throw 'Existing screenshot output is preserved'}
Assert-NoLinks ([IO.Path]::GetDirectoryName($output));New-Item -ItemType Directory -Path $output|Out-Null
$gui=Join-Path $output 'gui';New-Item -ItemType Directory -Path $gui|Out-Null
$tag='bristlune-marketing-'+[guid]::NewGuid().ToString('N');$work=Join-Path $env:RUNNER_TEMP $tag
Assert-NoLinks $env:RUNNER_TEMP;New-Item -ItemType Directory -Path $work|Out-Null
$state=@{work=$work;gui=$gui;evidence=$output;identity=$identity;family=$identity.family;record=$record;
    packageFullName=$null;installLocation=$null;ownedRegistration=$false;installAttempted=$false;activationAttempted=$false;uninstalled=$false;observer=$null;
    fixtureLease=$null;profileLease=$null;certificate=$null;certificateHash=$null;trusted=$false;signedCopy=$null;signedHash=$null;unsigned=$null;unsignedHash=$null;
    displayOriginalMode=$null;displayDevice=$null;displayRestoreRequired=$false;displayEvidence=$null;displayRestoreError=$null;
    probeHash=$null;profile=(Join-Path $env:LOCALAPPDATA ('Packages/'+$identity.family));fixture='C:\Bristlune Demo';normalClose=$false;filesVerified=$false}
$state.noActivationProof=Join-Path $work 'no-activation.json';Write-NewJson $state.noActivationProof @{ownedProcessesStopped=$true;activationAttempted=$false}
$ops=[ordered]@{}
$ops.Preflight={
    Assert-NoExistingProfile
    if(@(Get-AppxPackage -Name 'Trieflow.Bristlune.Qualification').Count -or @(Get-AppxPackage -Name '1659hashfunction.BrushQuay').Count -or (Test-Path -LiteralPath $state.profile) -or (Test-Path -LiteralPath $state.fixture)){throw 'Existing product registration, profile or demo folder preserved'}
    $sdk=Join-Path ${env:ProgramFiles(x86)} 'Windows Kits/10/bin/10.0.26100.0/x64'
    $tool=Join-Path $sdk 'signtool.exe';$signature=Get-AuthenticodeSignature -LiteralPath $tool
    if($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation'){throw 'Unproved original Microsoft signing tool'}
    $version=(Get-Item -LiteralPath $tool).VersionInfo
    if($version.FileMajorPart -ne 10 -or $version.FileMinorPart -ne 0 -or $version.FileBuildPart -ne 26100 -or $version.OriginalFilename -ine 'signtool.exe'){throw 'SDK signing tool version differs'}
    $storeInstallation=@(Get-ChildItem (Join-Path $Inputs 'metadata') -Recurse -File -Filter installation-result.json|ForEach-Object {Get-Content $_.FullName -Raw|ConvertFrom-Json}|Where-Object {$_.releaseCandidate -and $_.mode -ceq 'store'})
    if($storeInstallation.Count -ne 1){throw 'Exact original Store installation receipt missing'}
    Assert-File $tool $storeInstallation[0].signTool
    $state.signTool=@{path=$tool;bytes=$storeInstallation[0].signTool.bytes;sha256=$storeInstallation[0].signTool.sha256}
    $generated=Join-Path $work 'GuiProbe.cs'
    & $Python (Join-Path $capture 'prepare_probe.py') --qualified-source $QualifiedSource --output $generated > (Join-Path $output 'probe-generation.json')
    if($LASTEXITCODE -ne 0){throw 'Strict capture-only observer preparation failed'}
    $state.probe=Join-Path $work 'GuiProbe.exe';$csc=Join-Path $env:WINDIR 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    $refs=Join-Path ${env:ProgramFiles(x86)} 'Reference Assemblies/Microsoft/Framework/.NETFramework/v4.8'
    $arguments=@('/nologo','/target:exe','/platform:x64',('/out:'+$state.probe),'/r:System.Core.dll','/r:System.Drawing.dll','/r:System.Windows.Forms.dll','/r:System.Web.Extensions.dll')
    foreach($name in @('WindowsBase','UIAutomationClient','UIAutomationTypes')){$arguments+=('/r:'+(Join-Path $refs ($name+'.dll')))}
    $arguments+=$generated;foreach($name in @('InputGuard.cs','OwnedJob.cs','ModuleEvidence.cs')){$arguments+=(Join-Path $qualifiedHelpers $name)}
    Invoke-Native $csc $arguments;$state.probeHash=Measure-File $state.probe
}
$ops.PreparePackage={
    $state.unsigned=Join-Path $Inputs 'store/Bristlune_1.0.1.0_x64.msix';$state.unsignedHash=$bound.package
    $state.packageRecord=Join-Path $Inputs 'verified-package.json';Assert-File $state.unsigned $state.unsignedHash
    if($state.record.identity.PackageName -cne $identity.name -or $state.record.identity.Publisher -cne $identity.publisher -or $state.record.mode -cne 'store' -or $state.record.signed -ne $false){throw 'Exact fixed unsigned Store record differs'}
}
$ops.OwnFixtureProfile={
    Assert-NoExistingProfile
    $state.fixtureLease=Join-Path $work 'fixture-lease.json';$state.profileLease=Join-Path $work 'profile-lease.json'
    Invoke-Native $Python @((Join-Path $capture 'capture_files.py'),'begin','--source',$QualifiedSource,'--root',$state.fixture,'--output',$state.fixtureLease)
    Invoke-Native $Python @((Join-Path $qualifiedHelpers 'ownership.py'),'begin','--root',$state.profile,'--kind','profile','--output',$state.profileLease)
}
    $ops.SignAndInstall={
        $state.signedCopy=Join-Path $work 'Bristlune.Qualification.signed.msix';[IO.File]::Copy($state.unsigned,$state.signedCopy,$false)
        $state.certificate=New-SelfSignedCertificate -Type Custom -KeyUsage DigitalSignature -KeyExportPolicy NonExportable -KeySpec Signature -CertStoreLocation 'Cert:\CurrentUser\My' -TextExtension @('2.5.29.37={text}1.3.6.1.5.5.7.3.3','2.5.29.19={text}') -Subject $identity.publisher -FriendlyName ('Bristlune disposable '+$tag) -NotAfter (Get-Date).AddHours(12)
        $state.certificateHash=[Convert]::ToBase64String($state.certificate.RawData)
        $state.cer=Join-Path $work 'ephemeral-public.cer';Export-Certificate -Cert $state.certificate -FilePath $state.cer|Out-Null;$state.cerHash=Measure-File $state.cer
        $trustPath='Cert:\LocalMachine\TrustedPeople\'+$state.certificate.Thumbprint
        if(Test-Path -LiteralPath $trustPath){throw 'Ephemeral certificate unexpectedly already trusted'}
        $state.trusted=$true;Import-Certificate -FilePath $state.cer -CertStoreLocation 'Cert:\LocalMachine\TrustedPeople'|Out-Null
        foreach($toolArguments in @(@('sign','/fd','SHA256','/sha1',$state.certificate.Thumbprint,'/s','My',$state.signedCopy),@('verify','/pa','/all','/v',$state.signedCopy))){Assert-File $state.signTool.path $state.signTool;Invoke-Native $state.signTool.path $toolArguments}
        Assert-File $state.signTool.path $state.signTool
        $signature=Get-AuthenticodeSignature -LiteralPath $state.signedCopy
        if($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Thumbprint -cne $state.certificate.Thumbprint){throw 'Signed copy does not have the exact ephemeral signature'}
        $state.signedHash=Measure-File $state.signedCopy;Assert-File $state.unsigned $state.unsignedHash
        Invoke-Native $Python @((Join-Path $qualifiedHelpers 'ownership.py'),'verify','--lease',$state.profileLease)
        Assert-NoExistingProfile
        if(@(Get-AppxPackage -Name $identity.name).Count){throw 'Package appeared before owned installation'}
        $state.installAttempted=$true;Add-AppxPackage -Path $state.signedCopy -ErrorAction Stop
        $registered=@(Get-AppxPackage -Name $identity.name)
        if($registered.Count -ne 1 -or $registered[0].PackageFamilyName -cne $state.family -or $registered[0].Publisher -cne $identity.publisher -or $registered[0].Version.ToString() -cne $identity.version -or $registered[0].Architecture.ToString() -ine 'X64'){throw 'Installed identity does not match the selected fixed package'}
        $state.packageFullName=$registered[0].PackageFullName;$state.installLocation=$registered[0].InstallLocation;$state.ownedRegistration=$true
        Invoke-Native $Python @((Join-Path $qualifiedHelpers 'verify_installed.py'),'--root',$state.installLocation,'--record',$state.packageRecord,'--output',(Join-Path $output 'installed-files.json'))
    }
$ops.ConsumerWorkflow={
    Get-ExactRegistration $state|Out-Null;Assert-NoExistingProfile
    Invoke-Native $Python @((Join-Path $capture 'capture_files.py'),'inspect','--source',$QualifiedSource,'--lease',$state.fixtureLease)
    Invoke-Native $Python @((Join-Path $qualifiedHelpers 'ownership.py'),'verify','--lease',$state.profileLease)
    Start-GuiDisplay $state
    $exe=Join-Path $state.installLocation 'Bristlune/bin/bristlune.exe';$expected=$state.record.payload.'Bristlune/bin/bristlune.exe';Assert-File $exe $expected
    Write-NewJson (Join-Path $gui 'probe-input.json') @{payload=$state.record.payload;sourceCommit=$bound.source_commit;sourceTree=$state.record.sourceTree;run=$bound.run_id;attempt=$bound.run_attempt;nativeEvidence=$state.record.nativeEvidence;unsignedPackage=$state.record.package}
    Assert-File $state.probe $state.probeHash
    $start=New-BristluneObserverStartInfo $state.probe @($gui,$state.fixture,$exe,$state.packageFullName,$expected.sha256,($state.family+'!'+$identity.applicationId))
    $state.activationAttempted=$true;$state.observer=[Diagnostics.Process]::Start($start);$null=$state.observer.Handle
    if(-not $state.observer.WaitForExit(600000)){throw 'Capture observer exceeded ten minutes'}
    $proof=Get-Content (Read-StopProof $state) -Raw|ConvertFrom-Json
    if($state.observer.ExitCode -ne 0 -or $proof.passed -ne $true -or $proof.normalClosePassed -ne $true -or $proof.normalExitCode -ne 0 -or $proof.purpose -cne 'marketing capture only' -or $proof.consumerAcceptance -ne $false){throw 'Actual marketing UI workflow/normal close failed'}
    $state.normalClose=$true
}
$ops.VerifyFiles={
    $proof=Read-StopProof $state;Assert-NoExistingProfile
    Invoke-Native $Python @((Join-Path $capture 'capture_files.py'),'remove-empty-export','--source',$QualifiedSource,'--lease',$state.fixtureLease,'--proof',$proof,'--gui',$gui,'--output',(Join-Path $output 'transaction-directory-removal.json'))
    Invoke-Native $Python @((Join-Path $capture 'capture_files.py'),'verify','--source',$QualifiedSource,'--lease',$state.fixtureLease,'--profile',$state.profileLease,'--proof',$proof,'--gui',$gui,'--output',(Join-Path $output 'artwork-verification.json'))
    Assert-File $state.unsigned $state.unsignedHash;Assert-File $state.signedCopy $state.signedHash
    Invoke-Native $Python @((Join-Path $qualifiedHelpers 'verify_installed.py'),'--root',$state.installLocation,'--record',$state.packageRecord,'--output',(Join-Path $output 'installed-files-after-close.json'))
    $state.filesVerified=$true
}
    $ops.Uninstall={Invoke-OwnedUninstall $state $Python}
    $ops.StopObserver={
        if($state.observer){if(-not $state.observer.HasExited){$state.observer.Kill();if(-not $state.observer.WaitForExit(15000)){throw 'Retained observer did not stop'}};$state.observer.Dispose();$state.observer=$null}
    }
    $ops.UninstallIfNeeded={Invoke-OwnedUninstall $state $Python}
    $ops.RestoreDisplay={Restore-GuiDisplay $state}
$ops.RemoveFixture={
    if($state.fixtureLease -and (Test-Path -LiteralPath $state.fixtureLease)){
        $proof=Read-StopProof $state;$sealed=Join-Path $work 'fixture-sealed.json'
        Invoke-Native $Python @((Join-Path $capture 'capture_files.py'),'seal','--source',$QualifiedSource,'--lease',$state.fixtureLease,'--proof',$proof,'--output',$sealed)
        Invoke-Native $Python @((Join-Path $capture 'capture_files.py'),'clean','--source',$QualifiedSource,'--sealed',$sealed,'--proof',$proof)
    }
}
    $ops.RemoveProfile={
        if($state.profileLease -and (Test-Path -LiteralPath $state.profileLease)){
            $proof=Read-StopProof $state
            if($state.installAttempted -and -not $state.uninstalled){throw 'Profile cleanup requires exact package uninstall'}
            if(Test-Path -LiteralPath $state.profile){
                # Uninstall may remove the entire private state tree. Any residue
                # must still have the exact marker and stopped snapshot bytes.
                $sealed=Join-Path $work 'profile-sealed.json'
                if(-not (Test-Path -LiteralPath $sealed)){Invoke-Native $Python @((Join-Path $qualifiedHelpers 'ownership.py'),'seal','--lease',$state.profileLease,'--proof',$proof,'--output',$sealed)}
                Invoke-Native $Python @((Join-Path $qualifiedHelpers 'ownership.py'),'clean','--sealed',$sealed,'--proof',$proof)
            }
            if(Test-Path -LiteralPath $state.profile){throw 'Owned private package profile remains'}
        }
    }
    $ops.RemoveCertificates={
        if($state.certificate){
            foreach($store in @('Cert:\LocalMachine\TrustedPeople\','Cert:\CurrentUser\My\')){
                if($store -like '*TrustedPeople*' -and -not $state.trusted){continue}
                $path=$store+$state.certificate.Thumbprint
                if(Test-Path -LiteralPath $path){$cert=Get-Item -LiteralPath $path;if([Convert]::ToBase64String($cert.RawData) -cne $state.certificateHash){throw 'Certificate bytes changed; refuse removal'};Remove-Item -LiteralPath $path -ErrorAction Stop}
                if(Test-Path -LiteralPath $path){throw 'Ephemeral certificate remains'}
            }
            if($state.ContainsKey('cerHash') -and (Test-Path -LiteralPath $state.cer)){Assert-File $state.cer $state.cerHash;[IO.File]::Delete($state.cer)}
        }
    }
    $ops.RemoveSignedCopy={
        if($state.unsigned){Assert-File $state.unsigned $state.unsignedHash}
        if($state.signedCopy -and (Test-Path -LiteralPath $state.signedCopy)){
            if(-not $state.signedHash){throw 'Signing did not establish final signed bytes; retain temporary copy for recovery'}
            Assert-File $state.signedCopy $state.signedHash;[IO.File]::Delete($state.signedCopy)
        }
    }
$result=Invoke-QualificationCore $ops
$unchanged=$false
try{Invoke-Native $Python @((Join-Path $capture 'capture_checks.py'),'--inputs',$Inputs,'--qualified-source',$QualifiedSource);$unchanged=$true}catch{$result.cleanupErrors+=@('Original input readback: '+$_.Exception.Message);$result.passed=$false}
$trustRemoved=if($state.certificate){-not ((Test-Path -LiteralPath ('Cert:\CurrentUser\My\'+$state.certificate.Thumbprint)) -or (Test-Path -LiteralPath ('Cert:\LocalMachine\TrustedPeople\'+$state.certificate.Thumbprint)))}else{$false}
$complete=($result.passed -and $state.normalClose -and $state.filesVerified -and $state.uninstalled -and -not (Test-Path -LiteralPath $state.fixture) -and -not (Test-Path -LiteralPath $state.profile) -and $trustRemoved -and $state.displayEvidence.restore_verified -and $unchanged)
Write-NewJson (Join-Path $output 'capture-result.json') @{schema=1;purpose='marketing capture only';consumerAcceptance=$false;qualificationClaimed=$false;captured=$complete;
    captureSource=$env:GITHUB_SHA;captureRun=$env:GITHUB_RUN_ID;captureAttempt=$env:GITHUB_RUN_ATTEMPT;qualified=$bound;packageFullName=$state.packageFullName;
    originalInputsUnchanged=$unchanged;probe=$state.probeHash;normalCloseVerified=$state.normalClose;filesVerified=$state.filesVerified;uninstalled=$state.uninstalled;
    fixtureRemoved=(-not (Test-Path -LiteralPath $state.fixture));profileRemoved=(-not (Test-Path -LiteralPath $state.profile));certificateRemoved=$trustRemoved;display=$state.displayEvidence;outcome=$result}
if(-not $complete){throw 'Marketing capture incomplete; original failure and cleanup evidence retained'}
Write-Output 'Three raw real Bristlune scenes and actual named-preset export verified; original product qualification remains separate.'
