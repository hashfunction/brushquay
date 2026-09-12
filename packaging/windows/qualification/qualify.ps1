# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
# Disposable GitHub Windows desktop only. Public source/license approval is separate.
[CmdletBinding()]
param([string]$Python='python',[ValidateSet('','qualification','store')][string]$ReleaseMode='',[switch]$LibraryOnly)
$ErrorActionPreference='Stop';Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'display-modes.ps1')

function Invoke-QualificationCore([Collections.IDictionary]$Operations) {
    $normal=@('Preflight','PreparePackage','OwnFixtureProfile','SignAndInstall','ConsumerWorkflow','VerifyFiles','Uninstall')
    $cleanup=@('StopObserver','UninstallIfNeeded','RestoreDisplay','RemoveFixture','RemoveProfile','RemoveCertificates','RemoveSignedCopy')
    foreach($name in @($normal)+@($cleanup)){if(-not $Operations.Contains($name) -or $Operations[$name] -isnot [scriptblock]){throw "Missing operation $name"}}
    $primary=$null;$errors=[Collections.Generic.List[string]]::new()
    try{foreach($name in $normal){& $Operations[$name]|Out-Host}}
    catch{$primary=$_.Exception.Message}
    finally{foreach($name in $cleanup){try{& $Operations[$name]|Out-Host}catch{$errors.Add("${name}: $($_.Exception.Message)")}}}
    return [ordered]@{passed=(-not $primary -and $errors.Count -eq 0);primaryError=$primary;cleanupErrors=@($errors)}
}
function Write-NewJson([string]$Path,$Value){
    $stream=[IO.File]::Open($Path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try{$bytes=[Text.UTF8Encoding]::new($false).GetBytes(($Value|ConvertTo-Json -Depth 40));$stream.Write($bytes,0,$bytes.Length)}finally{$stream.Dispose()}
}
function Invoke-Native([string]$Exe,[string[]]$Arguments){& $Exe @Arguments;if($LASTEXITCODE -ne 0){throw "$Exe exited $LASTEXITCODE"}}
function New-BristluneObserverStartInfo([string]$Executable,[string[]]$Values){
    # Windows PowerShell 5.1 uses .NET Framework: ArgumentList is unavailable.
    # Quote each value using the Windows CRT backslash/quote rules. No shell is used.
    $arguments=[Collections.Generic.List[string]]::new()
    foreach($value in $Values){
        if($value.IndexOf([char]0) -ge 0){throw 'Observer arguments must not contain NUL'}
        $quoted=[Text.StringBuilder]::new();$null=$quoted.Append('"');$slashes=0
        foreach($character in $value.ToCharArray()){
            if($character -eq [char]92){$slashes++;continue}
            if($character -eq [char]34){$null=$quoted.Append([char]92,($slashes*2+1))}
            else{$null=$quoted.Append([char]92,$slashes)}
            $null=$quoted.Append($character);$slashes=0
        }
        $null=$quoted.Append([char]92,($slashes*2));$null=$quoted.Append('"')
        $arguments.Add($quoted.ToString())
    }
    $start=[Diagnostics.ProcessStartInfo]::new($Executable)
    $start.UseShellExecute=$false;$start.Arguments=[string]::Join(' ',$arguments)
    return $start
}
function Assert-NoLinks([string]$Path){
    $current=[IO.Path]::GetFullPath($Path)
    while($current){$item=Get-Item -LiteralPath $current -Force;if($item.Attributes -band [IO.FileAttributes]::ReparsePoint){throw "Reparse path refused: $current"};$current=[IO.Path]::GetDirectoryName($current)}
}
function Measure-File([string]$Path){Assert-NoLinks $Path;$file=Get-Item -LiteralPath $Path -Force;if($file.PSIsContainer){throw "Regular file required: $Path"};return [ordered]@{bytes=$file.Length;sha256=(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()}}
function Assert-File([string]$Path,$Expected){$value=Measure-File $Path;if($value.bytes -ne $Expected.bytes -or $value.sha256 -cne $Expected.sha256){throw "Exact bytes changed: $Path"}}
function Assert-NoExistingProfile {
    foreach($base in @($env:LOCALAPPDATA,$env:APPDATA)){
        Assert-NoLinks $base
        if(@(Get-ChildItem -LiteralPath $base -Force|Where-Object {$_.Name -like 'brushquay*'}).Count){throw "Existing BrushQuay profile/config/log files are preserved; fresh disposable profile required: $base"}
    }
}
function Get-QualificationIdentity([string]$Mode){
    switch -CaseSensitive ($Mode){
        'qualification' {return @{name='Trieflow.Bristlune.Qualification';publisher='CN=Bristlune-CI-Qualification';family='Trieflow.Bristlune.Qualification_kheb0ettnemtj';version='1.0.1.0';applicationId='BrushQuay'}}
        'store' {return @{name='1659hashfunction.BrushQuay';publisher='CN=B6A2631A-FD32-45CC-AE12-82466975F528';family='1659hashfunction.BrushQuay_r3hxytd7jt6c4';version='1.0.1.0';applicationId='BrushQuay'}}
        default {throw 'Unknown fixed installed identity mode'}
    }
}
function Get-ExactRegistration($State){
    $name=if($State.ContainsKey('identity')){$State.identity.name}else{'Trieflow.Bristlune.Qualification'}
    $found=@(Get-AppxPackage -Name $name)
    if($found.Count -ne 1 -or $found[0].PackageFullName -cne $State.packageFullName -or $found[0].InstallLocation -ine $State.installLocation -or $found[0].PackageFamilyName -cne $State.family){throw 'Exact owned package registration changed'}
    return $found[0]
}
function Read-StopProof($State){
    if(-not $State.activationAttempted){return $State.noActivationProof}
    $path=Join-Path $State.gui 'gui-observations.json'
    if(-not (Test-Path -LiteralPath $path)){throw 'Observer did not retain a stopped-process receipt; package/profile are retained for recovery'}
    $proof=Get-Content -LiteralPath $path -Raw|ConvertFrom-Json
    if($proof.ownedProcessesStopped -isnot [bool] -or -not $proof.ownedProcessesStopped){throw 'Product process/job stop is unproved; package/profile are retained'}
    return $path
}
function Invoke-OwnedUninstall($State,[string]$Python){
    if(-not $State.installAttempted){return}
    if(-not $State.ownedRegistration){throw 'Installation was attempted without establishing exact registration ownership; retain state for recovery'}
    if($State.uninstalled){return}
    $proof=Read-StopProof $State
    Get-ExactRegistration $State|Out-Null
    $sealed=Join-Path $State.work 'profile-sealed.json'
    if(-not (Test-Path -LiteralPath $sealed)){Invoke-Native $Python @((Join-Path $PSScriptRoot 'ownership.py'),'seal','--lease',$State.profileLease,'--proof',$proof,'--output',$sealed)}
    Invoke-Native $Python @((Join-Path $PSScriptRoot 'ownership.py'),'check','--sealed',$sealed,'--proof',$proof)
    Assert-NoExistingProfile
    Remove-AppxPackage -Package $State.packageFullName -ErrorAction Stop
    if(@(Get-AppxPackage -Name $State.identity.name).Count){throw 'Owned package registration remains after uninstall'}
    $State.uninstalled=$true
}
function Assert-InstallerHost {
    # Server 2022's Appx module requires its native Windows PowerShell host.
    # Avoid remoting proxies: ownership receipts use the original package objects.
    if([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT -or
        $PSVersionTable.PSEdition -cne 'Desktop' -or $PSVersionTable.PSVersion.Major -ne 5 -or
        $PSVersionTable.PSVersion.Minor -ne 1 -or -not [Environment]::Is64BitProcess){
        throw 'Native x64 Windows PowerShell 5.1 is required for Appx qualification.'
    }
    Import-Module Appx -ErrorAction Stop
    foreach($name in @('Get-AppxPackage','Add-AppxPackage','Remove-AppxPackage')){
        $command=Get-Command $name -CommandType Cmdlet -ErrorAction Stop
        if($command.ModuleName -cne 'Appx'){throw ('Original Appx cmdlet required: '+$name)}
    }
}
function Invoke-InstalledQualification([string]$Python,[string]$ReleaseMode=''){
    Assert-InstallerHost
    if($env:GITHUB_ACTIONS -cne 'true' -or $env:RUNNER_OS -cne 'Windows'){throw 'Only the disposable native GitHub Windows runner is supported'}
    $source=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../..'))
    $run=$env:GITHUB_RUN_ID;$attempt=$env:GITHUB_RUN_ATTEMPT
    if($run -notmatch '^[1-9][0-9]*$' -or $attempt -notmatch '^[1-9][0-9]*$'){throw 'Exact GitHub run and attempt are required'}
    $mode=if($ReleaseMode){$ReleaseMode}else{'qualification'};$identity=Get-QualificationIdentity $mode
    $tag='installed-'+$run+'-'+$attempt+'-'+[guid]::NewGuid().ToString('N')
    $workParent=Join-Path $source '.brushquay/qualification';[IO.Directory]::CreateDirectory($workParent)|Out-Null
    Assert-NoLinks $workParent;$work=Join-Path $workParent $tag;New-Item -ItemType Directory -Path $work -ErrorAction Stop|Out-Null
    $evidence=Join-Path $source ('.brushquay/evidence/'+$tag);New-Item -ItemType Directory -Path $evidence -ErrorAction Stop|Out-Null
    $gui=Join-Path $evidence 'gui';New-Item -ItemType Directory -Path $gui|Out-Null
    $state=@{work=$work;gui=$gui;evidence=$evidence;identity=$identity;family=$identity.family;packageFullName=$null;installLocation=$null;
        ownedRegistration=$false;installAttempted=$false;activationAttempted=$false;uninstalled=$false;observer=$null;
        fixtureLease=$null;profileLease=$null;certificate=$null;certificateHash=$null;trusted=$false;signedCopy=$null;signedHash=$null;unsigned=$null;unsignedHash=$null;
        displayOriginalMode=$null;displayDevice=$null;displayRestoreRequired=$false;displayEvidence=$null;displayRestoreError=$null;sdk=$null}
    $state.noActivationProof=Join-Path $work 'no-activation.json';Write-NewJson $state.noActivationProof @{ownedProcessesStopped=$true;activationAttempted=$false}
    # Callbacks run synchronously before this scope returns. Keep script-local
    # helpers visible; GetNewClosure creates a dynamic module that loses them.
    $ops=[ordered]@{}
    $ops.Preflight={
        Assert-NoExistingProfile
        if(@(Get-AppxPackage -Name 'Trieflow.Bristlune.Qualification').Count -or @(Get-AppxPackage -Name '1659hashfunction.BrushQuay').Count){throw 'Existing product registration is preserved'}
        $state.profile=Join-Path $env:LOCALAPPDATA ('Packages/'+$state.family)
        if(Test-Path -LiteralPath $state.profile){throw 'Existing package profile is preserved'}
        $state.commit=(& git -C $source rev-parse HEAD).Trim();if($LASTEXITCODE -ne 0){throw 'Cannot read committed source'}
        $sdk=Join-Path ${env:ProgramFiles(x86)} 'Windows Kits/10/bin/10.0.26100.0/x64'
        $state.sdk=[ordered]@{sdkVersion='10.0.26100.0'}; $state.sdkAuthenticode=[ordered]@{}
        foreach($name in @('makepri','makeappx','signtool')){
            $path=Join-Path $sdk ($name+'.exe');$value=Measure-File $path;$signature=Get-AuthenticodeSignature -LiteralPath $path
            if($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation'){throw "Unproved Microsoft SDK tool signature: $path"}
            $version=(Get-Item -LiteralPath $path).VersionInfo
            if($version.FileMajorPart -ne 10 -or $version.FileMinorPart -ne 0 -or $version.FileBuildPart -ne 26100 -or $version.OriginalFilename -ine ($name+'.exe')){throw "SDK version/original filename differs: $path"}
            $state.sdkAuthenticode[$name]=[ordered]@{subject=$signature.SignerCertificate.Subject;thumbprint=$signature.SignerCertificate.Thumbprint;fileVersion=$version.FileVersion}
            $record=[ordered]@{path=$path;sha256=$value.sha256;bytes=$value.bytes}
            if($name -eq 'signtool'){$state.signTool=$record}else{$state.sdk[$name]=$record}
        }
        $state.sdkLock=Join-Path $work 'sdk-tools.json';Write-NewJson $state.sdkLock $state.sdk
        $state.probe=Join-Path $work 'GuiProbe.exe'
        $csc=Join-Path $env:WINDIR 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        $refs=Join-Path ${env:ProgramFiles(x86)} 'Reference Assemblies/Microsoft/Framework/.NETFramework/v4.8'
        $arguments=@('/nologo','/target:exe','/platform:x64',('/out:'+$state.probe),'/r:System.Core.dll','/r:System.Drawing.dll','/r:System.Windows.Forms.dll','/r:System.Web.Extensions.dll')
        foreach($name in @('WindowsBase','UIAutomationClient','UIAutomationTypes')){$arguments+=('/r:'+(Join-Path $refs ($name+'.dll')))}
        foreach($name in @('GuiProbe.cs','InputGuard.cs','OwnedJob.cs','ModuleEvidence.cs')){$arguments+=(Join-Path $PSScriptRoot $name)}
        Invoke-Native $csc $arguments
        $state.probeHash=Measure-File $state.probe
    }
    $ops.PreparePackage={
        $state.stage=Join-Path $work 'package'
        if($ReleaseMode){
            Invoke-Native $Python @((Join-Path $PSScriptRoot '../msix/release_build.py'),'--source',$source,'--output',$state.stage,'--evidence',(Join-Path $evidence 'package'),'--sdk-tools',$state.sdkLock,'--commit',$state.commit,'--run',$run,'--attempt',$attempt,'--mode',$mode)
            $state.packageRecord=Join-Path $state.stage 'release-record.json';$packageName='Bristlune.msix'
        }else{
            Invoke-Native $Python @((Join-Path $PSScriptRoot 'prepare.py'),'--source',$source,'--output',$state.stage,'--evidence',(Join-Path $evidence 'package'),'--sdk-tools',$state.sdkLock,'--commit',$state.commit,'--run',$run,'--attempt',$attempt)
            $state.packageRecord=Join-Path $state.stage 'package-record.json';$packageName='Bristlune.Qualification_1.0.1.0_x64.msix'
        }
        $state.record=Get-Content -LiteralPath $state.packageRecord -Raw|ConvertFrom-Json
        if($state.record.qualificationOnly -isnot [bool] -or $state.record.qualificationOnly -ne ($mode -ceq 'qualification') -or $state.record.identity.PackageName -cne $identity.name -or $state.record.identity.Publisher -cne $identity.publisher -or $state.record.identity.Version -cne $identity.version){throw 'Selected fixed package identity differs'}
        if($ReleaseMode -and ($state.record.releaseCandidate -isnot [bool] -or -not $state.record.releaseCandidate -or $state.record.mode -cne $mode -or $state.record.signed -isnot [bool] -or $state.record.signed)){throw 'Prepared release package mode differs'}
        $state.unsigned=Join-Path $state.stage $packageName;$state.unsignedHash=$state.record.package;Assert-File $state.unsigned $state.unsignedHash
    }
    $ops.OwnFixtureProfile={
        Assert-NoExistingProfile
        $state.fixture=Join-Path $env:RUNNER_TEMP ('.bristlune-artwork-'+[guid]::NewGuid().ToString('N'));$state.fixtureLease=Join-Path $work 'fixture-lease.json'
        Invoke-Native $Python @((Join-Path $PSScriptRoot 'ownership.py'),'begin','--root',$state.fixture,'--kind','fixture','--output',$state.fixtureLease)
        $state.profileLease=Join-Path $work 'profile-lease.json'
        Invoke-Native $Python @((Join-Path $PSScriptRoot 'ownership.py'),'begin','--root',$state.profile,'--kind','profile','--output',$state.profileLease)
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
        Invoke-Native $Python @((Join-Path $PSScriptRoot 'ownership.py'),'verify','--lease',$state.profileLease)
        Assert-NoExistingProfile
        if(@(Get-AppxPackage -Name $identity.name).Count){throw 'Package appeared before owned installation'}
        $state.installAttempted=$true;Add-AppxPackage -Path $state.signedCopy -ErrorAction Stop
        $registered=@(Get-AppxPackage -Name $identity.name)
        if($registered.Count -ne 1 -or $registered[0].PackageFamilyName -cne $state.family -or $registered[0].Publisher -cne $identity.publisher -or $registered[0].Version.ToString() -cne $identity.version -or $registered[0].Architecture.ToString() -ine 'X64'){throw 'Installed identity does not match the selected fixed package'}
        $state.packageFullName=$registered[0].PackageFullName;$state.installLocation=$registered[0].InstallLocation;$state.ownedRegistration=$true
        Invoke-Native $Python @((Join-Path $PSScriptRoot 'verify_installed.py'),'--root',$state.installLocation,'--record',$state.packageRecord,'--output',(Join-Path $evidence 'installed-files.json'))
    }
    $ops.ConsumerWorkflow={
        Get-ExactRegistration $state|Out-Null;Assert-NoExistingProfile
        foreach($lease in @($state.fixtureLease,$state.profileLease)){Invoke-Native $Python @((Join-Path $PSScriptRoot 'ownership.py'),'verify','--lease',$lease)}
        Start-GuiDisplay $state
        $exe=Join-Path $state.installLocation 'Bristlune/bin/bristlune.exe';$expected=$state.record.payload.'Bristlune/bin/bristlune.exe';Assert-File $exe $expected
        Write-NewJson (Join-Path $gui 'probe-input.json') @{payload=$state.record.payload;sourceCommit=$state.commit;sourceTree=$state.record.sourceTree;run=$run;attempt=$attempt;nativeEvidence=$state.record.nativeEvidence;unsignedPackage=$state.record.package}
        Assert-File $state.probe $state.probeHash
        $start=New-BristluneObserverStartInfo $state.probe @($gui,$state.fixture,$exe,$state.packageFullName,$expected.sha256,($state.family+'!'+$identity.applicationId))
        $state.activationAttempted=$true;$state.observer=[Diagnostics.Process]::Start($start);$null=$state.observer.Handle
        if(-not $state.observer.WaitForExit(600000)){throw 'Standalone installed UI observer exceeded ten minutes'}
        $proofPath=Read-StopProof $state;$proof=Get-Content -LiteralPath $proofPath -Raw|ConvertFrom-Json
        if($state.observer.ExitCode -ne 0 -or $proof.passed -ne $true -or $proof.normalClosePassed -ne $true -or $proof.normalExitCode -ne 0){throw 'Actual installed creation/painting/export/reopen/normal-close workflow failed; see gui-observations.json'}
    }
    $ops.VerifyFiles={
        Read-StopProof $state|Out-Null;Assert-NoExistingProfile
        $lease=Get-Content -LiteralPath $state.fixtureLease -Raw|ConvertFrom-Json;$protected=Join-Path $work 'protected.json';Write-NewJson $protected $lease.protected
        Invoke-Native $Python @((Join-Path $PSScriptRoot 'workflow_files.py'),'--root',$state.fixture,'--protected',$protected,'--output',(Join-Path $evidence 'artwork-verification.json'))
        Assert-File $state.unsigned $state.unsignedHash;Assert-File $state.signedCopy $state.signedHash
        Invoke-Native $Python @((Join-Path $PSScriptRoot 'verify_installed.py'),'--root',$state.installLocation,'--record',$state.packageRecord,'--output',(Join-Path $evidence 'installed-files-after-close.json'))
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
            Invoke-Native $Python @((Join-Path $PSScriptRoot 'ownership.py'),'seal','--lease',$state.fixtureLease,'--proof',$proof,'--output',$sealed)
            Invoke-Native $Python @((Join-Path $PSScriptRoot 'ownership.py'),'clean','--sealed',$sealed,'--proof',$proof)
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
                if(-not (Test-Path -LiteralPath $sealed)){Invoke-Native $Python @((Join-Path $PSScriptRoot 'ownership.py'),'seal','--lease',$state.profileLease,'--proof',$proof,'--output',$sealed)}
                Invoke-Native $Python @((Join-Path $PSScriptRoot 'ownership.py'),'clean','--sealed',$sealed,'--proof',$proof)
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
    $result.sourceCommit=if($state.ContainsKey('commit')){$state.commit}else{$null};$result.workflowRunId=$run;$result.workflowRunAttempt=$attempt
    $result.qualificationOnly=($mode -ceq 'qualification');$result.mode=$mode;$result.releaseCandidate=[bool]$ReleaseMode
    # Installation itself never supplies the separate source/license review.
    $result.licenseReviewComplete=$false;$result.correspondingSourceComplete=$false
    $result.packageFullName=$state.packageFullName;$result.uninstalled=$state.uninstalled;$result.display=$state.displayEvidence
    $result.fixtureRemoved=if($state.ContainsKey('fixture')){-not (Test-Path -LiteralPath $state.fixture)}else{$null}
    $result.profileRemoved=if($state.ContainsKey('profile')){-not (Test-Path -LiteralPath $state.profile)}else{$null}
    $result.unsignedPackage=$state.unsignedHash;$result.signedPackage=$state.signedHash;$result.sdk=$state.sdk;$result.sdkAuthenticode=if($state.ContainsKey('sdkAuthenticode')){$state.sdkAuthenticode}else{$null}
    if($ReleaseMode){
      try{
        $result.packageFamilyName=$state.family;$result.installLocation=$state.installLocation;$result.windowsRoot=$env:WINDIR
        $result.sourceTree=if($state.ContainsKey('record')){$state.record.sourceTree}else{$null}
        $result.packageRecord=if($state.ContainsKey('packageRecord')){Measure-File $state.packageRecord}else{$null}
        $result.packageDirectory=if($state.ContainsKey('stage')){$state.stage}else{$null}
        $result.probe=if($state.ContainsKey('probeHash')){$state.probeHash}else{$null}
        $result.signTool=if($state.ContainsKey('signTool')){$state.signTool}else{$null}
        $result.certificateRemoved=if($state.certificate){-not ((Test-Path -LiteralPath ('Cert:\CurrentUser\My\'+$state.certificate.Thumbprint)) -or (Test-Path -LiteralPath ('Cert:\LocalMachine\TrustedPeople\'+$state.certificate.Thumbprint)))}else{$false}
        $result.publicCertificateRemoved=if($state.ContainsKey('cer')){-not (Test-Path -LiteralPath $state.cer)}else{$false}
        $result.signedCopyRemoved=if($state.signedCopy){-not (Test-Path -LiteralPath $state.signedCopy)}else{$false}
        $result.originalEvidence=[ordered]@{}
        foreach($name in @('installed-files.json','installed-files-after-close.json','artwork-verification.json')){
            $path=Join-Path $evidence $name;if(Test-Path -LiteralPath $path){$result.originalEvidence[$name]=Measure-File $path}
        }
        foreach($path in @(Get-ChildItem -LiteralPath $gui -File)){
            if($path.Extension -cin @('.json','.png')){$result.originalEvidence['gui/'+$path.Name]=Measure-File $path.FullName}
        }
      }catch{
        $result.passed=$false;$result.cleanupErrors+=('Release evidence retention: '+$_.Exception.Message)
      }
    }
    Write-NewJson (Join-Path $evidence 'installation-result.json') $result
    if(-not $result.passed){throw ('Bristlune installed qualification failed: '+$result.primaryError+'; '+($result.cleanupErrors -join '; '))}
}
if(-not $LibraryOnly){Invoke-InstalledQualification $Python $ReleaseMode}
