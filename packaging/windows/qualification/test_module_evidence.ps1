# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
$ErrorActionPreference='Stop';Set-StrictMode -Version Latest
Add-Type -Path (Join-Path $PSScriptRoot 'ModuleEvidence.cs')
$root=Join-Path ([IO.Path]::GetTempPath()) ('bristlune-modules-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $root|Out-Null
$root=(Get-Item -LiteralPath $root).FullName
try {
    $package=Join-Path $root 'Bristlune';$windows=Join-Path $root 'Windows';$foreign=Join-Path $root 'Windows-other'
    foreach($path in @($package,$windows,$foreign)){New-Item -ItemType Directory -Path $path|Out-Null}
    $dll=Join-Path $package 'owned.dll';$os=Join-Path $windows 'system.dll';$other=Join-Path $foreign 'foreign.dll'
    foreach($path in @($dll,$os,$other)){[IO.File]::WriteAllBytes($path,[byte[]]@(1,2,3))}
    $payload=[Collections.Generic.Dictionary[string,object]]::new();$payload.Add('Bristlune/owned.dll',[BristluneQualification.ModuleEvidence]::Measure($dll))
    $calls=@{count=0};$alive=[Action]{$calls.count++}
    $paths=[Func[string[]]]{return [string[]]@($dll,$os)}
    $observation=[BristluneQualification.ModuleEvidence]::Capture($package,$windows,$payload,$alive,$paths)
    if($observation['status'] -cne 'observed' -or $observation['releaseReady'] -ne $false -or $observation['modules'].Count -ne 2 -or $calls.count -lt 2){throw 'Exact owned module observation failed'}
    $rows=$observation['modules'];if($rows[0]['kind'] -cne 'package' -or $rows[0]['path'] -cne $dll -or $rows[0]['payloadPath'] -cne 'Bristlune/owned.dll' -or $rows[0]['sha256'] -cne $payload['Bristlune/owned.dll']['sha256'] -or $rows[1]['kind'] -cne 'windows' -or $rows[1]['bytes'] -ne 3){throw 'Actual bytes/path/classification changed'}
    $before=(Get-FileHash -LiteralPath $dll).Hash
    $scenarios=@('outside','missing','changed','ownership-before','ownership-after','enumeration','duplicate')
    foreach($scenario in $scenarios){
        $calls.count=0;$check=$alive;$query=$paths
        switch($scenario){
            'outside'{$query=[Func[string[]]]{return [string[]]@($dll,$other)}}
            'missing'{$payload.Clear()}
            'changed'{[IO.File]::WriteAllBytes($dll,[byte[]]@(4,5,6))}
            'ownership-before'{$check=[Action]{throw 'original owner-before error'}}
            'ownership-after'{$check=[Action]{$calls.count++;if($calls.count -gt 1){throw 'original owner-after error'}}}
            'enumeration'{$query=[Func[string[]]]{throw 'original enumeration error'}}
            'duplicate'{$query=[Func[string[]]]{return [string[]]@($dll,$dll)}}
        }
        $result=[BristluneQualification.ModuleEvidence]::Capture($package,$windows,$payload,$check,$query)
        if($result['status'] -cne 'incomplete' -or $result['releaseReady'] -ne $false -or $result['errors'].Count -ne 1){throw ('Unsafe module observation accepted: '+$scenario)}
        if($scenario -like 'ownership-*' -or $scenario -eq 'enumeration'){if($result['errors'][0] -notlike '*original*error*'){throw 'Original diagnostic exception lost'}}
        [IO.File]::WriteAllBytes($dll,[byte[]]@(1,2,3));$payload['Bristlune/owned.dll']=[BristluneQualification.ModuleEvidence]::Measure($dll)
    }
    if((Get-FileHash -LiteralPath $dll).Hash -cne $before){throw 'Original owned input changed'}
    Write-Output 'PASS actual module observer: stable file bytes, package/Windows paths, seven ownership/hash/query/refusal scenarios; no release approval.'
}finally{Remove-Item -LiteralPath $root -Recurse -Force}
