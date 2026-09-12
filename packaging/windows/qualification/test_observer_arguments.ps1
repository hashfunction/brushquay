# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
# Actual ProcessStartInfo child round-trip; runs under both pwsh and Windows PS5.1.
$ErrorActionPreference='Stop';Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'qualify.ps1') -LibraryOnly
$root=Join-Path ([IO.Path]::GetTempPath()) ('bristlune-arguments-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $root|Out-Null
try {
    $child=Join-Path $root 'argument reader.ps1';$resultPath=Join-Path $root 'actual arguments.json'
    [IO.File]::WriteAllText($child,@'
$ErrorActionPreference='Stop'
$output=$args[0]
$values=@($args|Select-Object -Skip 1)
[IO.File]::WriteAllText($output,(ConvertTo-Json -InputObject $values -Compress),[Text.UTF8Encoding]::new($false))
'@,[Text.UTF8Encoding]::new($false))
    $hostExecutable=(Get-Process -Id $PID).Path;$prefix=@('-NoProfile','-File',$child)
    $unicodePath='C:\Owned Folder\r'+[char]0x00e9+'sum'+[char]0x00e9+' '+[char]0x539f+[char]0x7a3f
    if([Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT){
        # Exercise the actual .NET Framework executable argument parser, without
        # introducing PowerShell.exe's separate -File parameter parsing layer.
        $readerSource=Join-Path $root 'argument reader.cs'
        [IO.File]::WriteAllText($readerSource,@'
using System.IO; using System.Linq; using System.Text; using System.Web.Script.Serialization;
class ArgumentReader { static void Main(string[] args) {
    File.WriteAllText(args[0], new JavaScriptSerializer().Serialize(args.Skip(1).ToArray()),new UTF8Encoding(false));
} }
'@,[Text.UTF8Encoding]::new($false))
        $hostExecutable=Join-Path $root ('argument reader '+[char]0x539f+'.exe');$prefix=@()
        $compiler=Join-Path $env:WINDIR 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        & $compiler /nologo /target:exe ('/out:'+$hostExecutable) /reference:System.Web.Extensions.dll $readerSource
        if($LASTEXITCODE -ne 0){throw 'Actual Framework argument reader failed to compile'}
    }
    $values=@('plain',$unicodePath,'one"quote','two\\"quote','C:\trailing slash\','',('line one'+"`n"+'line two'),'package!BrushQuay')
    $start=New-BristluneObserverStartInfo $hostExecutable (@($prefix)+@($resultPath)+$values)
    if($start -isnot [Diagnostics.ProcessStartInfo] -or $start.UseShellExecute -or $start.FileName -cne $hostExecutable){throw 'Actual process launch configuration changed'}
    # This is the .NET Framework-compatible member, with every argument quoted.
    if(-not $start.Arguments -or $start.Arguments[0] -ne '"'){throw 'Compatible Arguments string was not constructed'}
    $process=[Diagnostics.Process]::Start($start)
    try {if(-not $process.WaitForExit(15000) -or $process.ExitCode -ne 0){throw 'Actual argument reader child failed'}}finally{if(-not $process.HasExited){$process.Kill();$process.WaitForExit()};$process.Dispose()}
    # Windows PowerShell 5.1 emits the JSON array as one pipeline object.
    # Assign its parsed value directly; @(...pipeline...) would wrap it again.
    $actual=Get-Content -LiteralPath $resultPath -Raw|ConvertFrom-Json
    if($actual -isnot [array]){throw 'Actual child argument result must be a JSON array'}
    if($actual.Count -ne $values.Count){throw "Argument count differs: $($actual.Count) versus $($values.Count)"}
    for($i=0;$i -lt $values.Count;$i++){if($actual[$i] -cne $values[$i]){throw "Native argument $i did not round-trip"}}
    $before=(Get-FileHash -LiteralPath $resultPath).Hash
    $rejected=$false;try{New-BristluneObserverStartInfo $hostExecutable @('bad'+[char]0+'value')|Out-Null}catch{$rejected=$true}
    if(-not $rejected){throw 'NUL argument was accepted'}
    # A real Process.Start failure remains the primary error through the original
    # lifecycle core, and later cleanup failures remain separately recorded.
    $calls=[Collections.Generic.List[string]]::new();$ops=[ordered]@{};$failure=@{message=$null}
    foreach($name in @('Preflight','PreparePackage','OwnFixtureProfile','SignAndInstall','ConsumerWorkflow','VerifyFiles','Uninstall','StopObserver','UninstallIfNeeded','RestoreDisplay','RemoveFixture','RemoveProfile','RemoveCertificates','RemoveSignedCopy')){$label=$name;$ops[$name]={ $calls.Add($label) }.GetNewClosure()}
    $ops.ConsumerWorkflow={
        try{[Diagnostics.Process]::Start((New-BristluneObserverStartInfo (Join-Path $root 'absent observer.exe') @('original value')))|Out-Null}
        catch{$failure.message=$_.Exception.Message;throw}
    }
    $ops.RemoveSignedCopy={throw 'separate cleanup error'}
    $result=Invoke-QualificationCore $ops
    if($result.passed -or -not $failure.message -or $result.primaryError -cne $failure.message -or $result.cleanupErrors.Count -ne 1 -or $result.cleanupErrors[0] -cne 'RemoveSignedCopy: separate cleanup error'){throw 'Original launch/cleanup errors were not preserved'}
    if($calls -contains 'VerifyFiles' -or $calls -contains 'Uninstall' -or $calls -notcontains 'RemoveCertificates'){throw 'Original lifecycle order changed after launch failure'}
    if((Get-FileHash -LiteralPath $resultPath).Hash -cne $before){throw 'Existing round-trip evidence changed'}
    Write-Output 'PASS actual ProcessStartInfo: eight exact arguments, empty/Unicode/quote/backslash/newline cases, NUL refusal, real launch failure and original cleanup preservation.'
}finally{Remove-Item -LiteralPath $root -Recurse -Force}
