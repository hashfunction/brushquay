# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
# Exercise actual capture lease/cleanup callbacks without app or trust mutations.
param([string]$Python='python')
$ErrorActionPreference='Stop';Set-StrictMode -Version Latest
$capture=$PSScriptRoot;$QualifiedSource=[IO.Path]::GetFullPath((Join-Path $capture '../../..'))
$qualifiedHelpers=Join-Path $QualifiedSource 'packaging/windows/qualification'
. (Join-Path $qualifiedHelpers 'qualify.ps1') -LibraryOnly
$tokens=$null;$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile((Join-Path $capture 'capture.ps1'),[ref]$tokens,[ref]$errors)
if($errors.Count){throw 'Capture script does not parse'}
$ops=[ordered]@{}
foreach($name in @('OwnFixtureProfile','RemoveFixture','RemoveProfile')){
    $matches=@($ast.FindAll({param($node)$node -is [Management.Automation.Language.AssignmentStatementAst] -and $node.Left.Extent.Text -ceq ('$ops.'+$name)},$true))
    if($matches.Count -ne 1){throw "Capture callback missing/ambiguous: $name"}
    $body=$matches[0].Right.Extent.Text
    if(-not ($body.StartsWith('{') -and $body.EndsWith('}'))){throw 'Expected original literal callback'}
    $ops[$name]=[scriptblock]::Create($body.Substring(1,$body.Length-2))
}
$temporary=(& $Python -c 'import pathlib,tempfile; print(pathlib.Path(tempfile.gettempdir()).resolve())').Trim()
if($LASTEXITCODE -ne 0){throw 'Cannot resolve fixture temporary directory'}
$root=Join-Path $temporary ('bristlune-capture-callbacks-'+[guid]::NewGuid().ToString('N'))
$beforeLocal=$env:LOCALAPPDATA;$beforeRoaming=$env:APPDATA
try{
    $work=Join-Path $root 'work';$null=[IO.Directory]::CreateDirectory($work)
    $env:LOCALAPPDATA=Join-Path $root 'local';$env:APPDATA=Join-Path $root 'roaming'
    foreach($path in @((Join-Path $env:LOCALAPPDATA 'Packages'),$env:APPDATA)){$null=[IO.Directory]::CreateDirectory($path)}
    $gui=Join-Path $work 'gui';$null=[IO.Directory]::CreateDirectory($gui)
    $state=@{work=$work;fixture=(Join-Path $root 'demo');profile=(Join-Path $env:LOCALAPPDATA 'Packages/owned-test-family');fixtureLease=$null;profileLease=$null;activationAttempted=$true;gui=$gui;installAttempted=$false;uninstalled=$false}
    & $ops.OwnFixtureProfile
    $art=Join-Path $state.fixture 'Moonlit Garden.ora';$original=Get-FileHash -LiteralPath $art -Algorithm SHA256
    foreach($name in @('RemoveFixture','RemoveProfile')){
        $refused=$false;try{& $ops[$name]}catch{$refused=$true}
        if(-not $refused -or -not (Test-Path -LiteralPath $state.fixture) -or -not (Test-Path -LiteralPath $state.profile)){throw 'Capture cleanup accepted missing original stop proof'}
    }
    $proof=Join-Path $gui 'gui-observations.json'
    Write-NewJson $proof @{ownedProcessesStopped=$true;normalClosePassed=$true;normalExitCode=0;passed=$true;purpose='marketing capture only';consumerAcceptance=$false}
    $foreign=Join-Path $state.fixture 'foreign.txt';[IO.File]::WriteAllText($foreign,'preserve')
    $refused=$false;try{& $ops.RemoveFixture}catch{$refused=$true}
    if(-not $refused -or [IO.File]::ReadAllText($foreign) -cne 'preserve' -or (Get-FileHash -LiteralPath $art -Algorithm SHA256).Hash -cne $original.Hash){throw 'Capture cleanup touched unexpected or original fixture bytes'}
    [IO.File]::Delete($foreign)
    foreach($name in @('Moonlit Garden.kra','Moonlit Garden.png','Moonlit Garden Reopened.kra')){[IO.File]::WriteAllText((Join-Path $state.fixture $name),'controlled file leaf')}
    $transaction=Join-Path $state.fixture '.brushquay-export-Ab12cD';$null=[IO.Directory]::CreateDirectory($transaction)
    $output=$work
    $removal=@($ast.FindAll({param($node)$node -is [Management.Automation.Language.PipelineAst] -and $node.Extent.Text.StartsWith('Invoke-Native ') -and $node.Extent.Text.Contains("'remove-empty-export'")},$true))
    if($removal.Count -ne 1){throw 'Expected exactly one actual capture empty-transaction cleanup invocation'}
    & ([scriptblock]::Create($removal[0].Extent.Text))
    if((Test-Path -LiteralPath $transaction) -or -not (Test-Path -LiteralPath (Join-Path $output 'transaction-directory-removal.json'))){throw 'Actual capture caller did not preserve empty-directory cleanup evidence'}
    & $ops.RemoveFixture
    & $ops.RemoveProfile
    if((Test-Path -LiteralPath $state.fixture) -or (Test-Path -LiteralPath $state.profile)){throw 'Actual capture callback cleanup remained incomplete'}
    Write-Output 'PASS actual capture callbacks: exclusive leases, both missing-stop refusals, foreign-file refusal, exact empty-transaction cleanup invocation/evidence, and stopped cleanup.'
}finally{
    $env:LOCALAPPDATA=$beforeLocal;$env:APPDATA=$beforeRoaming
    if(Test-Path -LiteralPath $root){[IO.Directory]::Delete($root,$true)}
}
