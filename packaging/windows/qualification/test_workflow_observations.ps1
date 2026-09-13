# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
# Execute the original Workflow/Picker/SaveAs/Observe/Save methods with controlled
# UI leaves. This tests sequencing and exclusive evidence writes, not native UI.
$ErrorActionPreference='Stop';Set-StrictMode -Version Latest
$source=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'GuiProbe.cs') -Raw
$methods=[Collections.Generic.List[string]]::new()
foreach($name in @('D','Hash','Save','Button','Picker','SaveAs','Observe','Workflow')){
    $pattern='(?ms)^        static [^\r\n]+ '+$name+'\([^\r\n]*\)\r?\n        \{.*?^        \}'
    $found=[regex]::Matches($source,$pattern)
    if($found.Count -ne 1){throw "Expected one original method: $name"}
    $methods.Add($found[0].Value)
}
$fixture=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'fixtures/WorkflowObservationReplay.cs.txt') -Raw
if(@([regex]::Matches($fixture,'/\* ORIGINAL_METHODS \*/')).Count -ne 1){throw 'Replay insertion marker differs'}
Add-Type -TypeDefinition $fixture.Replace('/* ORIGINAL_METHODS */',($methods -join "`n"))
$root=Join-Path ([IO.Path]::GetTempPath()) ('bristlune-observation-replay-'+[guid]::NewGuid().ToString('N'))
$null=[IO.Directory]::CreateDirectory($root)
try{
    $expected=@('01-installed-ready','new-document-settings','picker-02-blank.kra','picker-03-artwork.kra','02-painted-artwork','picker-05-artwork.png','png-export-options','picker-07-artwork.png','picker-08-reopened.kra','03-reopened-export')
    $captures=@('01-installed-ready','new-document-settings','02-painted-artwork','png-export-options','03-reopened-export')
    $normal=Join-Path $root 'normal'
    [ObservationReplay]::Run($normal,$true,$true,$null)
    $actual=@([ObservationReplay]::Stages())
    if(($actual -join '|') -cne ($expected -join '|')){throw 'Actual original workflow observation sequence differs'}
    if((@([ObservationReplay]::Captures()) -join '|') -cne ($captures -join '|')){throw 'Actual original five captures differ'}
    $files=@(Get-ChildItem -LiteralPath (Join-Path $normal 'output') -File)
    if($files.Count -ne 20){throw 'Expected ten exclusive observations and five capture/PNG pairs'}
    if([ObservationReplay]::FilenameInputs -ne 5 -or [ObservationReplay]::PointerInputs -ne 30 -or [ObservationReplay]::CloseInputs -ne 1 -or -not [ObservationReplay]::NormalClose()){throw 'Original input/normal-close flow differs'}
    foreach($case in @(@('exit',$false,$true),@('child',$true,$false))){
        $refused=$false
        try{[ObservationReplay]::Run((Join-Path $root $case[0]),$case[1],$case[2],$null)}catch{$refused=$true}
        if(-not $refused -or [ObservationReplay]::NormalClose()){throw 'Failed original close was accepted'}
    }
    $collision=Join-Path $root 'collision';$refused=$false
    try{[ObservationReplay]::Run($collision,$true,$true,'picker-02-blank.kra-observation.json')}catch{$refused=$true}
    if(-not $refused -or [ObservationReplay]::FilenameInputs -ne 0 -or [IO.File]::ReadAllText((Join-Path $collision 'output/picker-02-blank.kra-observation.json')) -cne 'protected original'){throw 'Existing observation was replaced or input was replayed after exclusive-write failure'}
    Write-Output 'PASS actual C# workflow: ten ordered observations, five captures, repeated image pathname, both close refusals, and exclusive-write refusal before filename input.'
}finally{[IO.Directory]::Delete($root,$true)}
