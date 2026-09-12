$ErrorActionPreference='Stop';Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'qualify.ps1') -LibraryOnly
if(-not (Get-Command Get-QualificationIdentity -ErrorAction SilentlyContinue)){throw 'Fixed installed identity resolver is missing'}
foreach($mode in @('qualification','store')){
 $value=Get-QualificationIdentity $mode
 if($value.applicationId -cne 'BrushQuay' -or $value.version -cne '1.0.1.0'){throw 'Immutable identity/version differs'}
 if($mode -eq 'store' -and ($value.name -cne '1659hashfunction.BrushQuay' -or $value.publisher -cne 'CN=B6A2631A-FD32-45CC-AE12-82466975F528' -or $value.family -cne '1659hashfunction.BrushQuay_r3hxytd7jt6c4')){throw 'Assigned Store identity differs'}
 $script:registration=@([pscustomobject]@{PackageFullName='owned';InstallLocation='C:\owned';PackageFamilyName=$value.family})
 function Get-AppxPackage {param($Name);if($Name -cne $value.name){throw 'Wrong registration lookup name'};return $script:registration}
 $state=@{identity=$value;packageFullName='owned';installLocation='C:\owned';family=$value.family}
 Get-ExactRegistration $state|Out-Null
 foreach($field in @('PackageFullName','InstallLocation','PackageFamilyName')){
  $old=$script:registration[0].$field;$script:registration[0].$field='foreign';$failed=$false
  try{Get-ExactRegistration $state|Out-Null}catch{$failed=$true}
  if(-not $failed){throw "Foreign registration accepted: $field"};$script:registration[0].$field=$old
 }
 $script:registration=@();$failed=$false;try{Get-ExactRegistration $state|Out-Null}catch{$failed=$true};if(-not $failed){throw 'Absent registration accepted'}
}
foreach($bad in @('Store','foreign','')){$failed=$false;try{Get-QualificationIdentity $bad|Out-Null}catch{$failed=$true};if(-not $failed){throw 'Unknown mode accepted'}}
Write-Output 'PASS: both fixed identities, eight registration mutations, three unknown modes.'
