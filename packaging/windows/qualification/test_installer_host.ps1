# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
# Real host/module check; no package or profile mutation.
$ErrorActionPreference='Stop';Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'qualify.ps1') -LibraryOnly
if([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT -or $PSVersionTable.PSEdition -cne 'Desktop'){
    $failure=$null
    try{Assert-InstallerHost}catch{$failure=$_.Exception.Message}
    if($failure -cne 'Native x64 Windows PowerShell 5.1 is required for Appx qualification.'){
        throw ('Unsupported host was not refused at the explicit host boundary: '+$failure)
    }
    Write-Output 'PASS actual unsupported installer host refusal; Windows module execution pending.'
}else{
    Assert-InstallerHost
    foreach($name in @('Trieflow.Bristlune.Qualification','1659hashfunction.BrushQuay')){
        if(@(Get-AppxPackage -Name $name -ErrorAction Stop).Count){throw 'Fresh runner required; existing registration preserved.'}
    }
    Write-Output 'PASS native Windows PowerShell host, original Appx commands and actual package queries.'
}
