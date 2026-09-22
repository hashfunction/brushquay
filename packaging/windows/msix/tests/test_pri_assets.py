"""Manifest resource scope and a small real Windows SDK pack/unpack replay."""
import hashlib,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
import xml.etree.ElementTree as ET
import test_brushquay_msix as fixture
import build_msix as package

RUNTIME='qml/QtQuick/Controls/FluentWinUI3/light/images/pageindicatordelegate-indicator-delegate-current-pressed@3x.png'

class PriAssetsTests(unittest.TestCase):
 def fixture(self):
  f=fixture.PackageTests('test_stage_is_exact_copy_without_mutating_install');f.setUp();self.addCleanup(f.doCleanups)
  path=f.install/RUNTIME;path.parent.mkdir(parents=True);path.write_bytes((package.HERE/'pkg/Assets/StoreLogo.png').read_bytes())
  f.audit['files'].append(dict(path=RUNTIME,bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),license='BSD-3-Clause',source='https://example.invalid/fixture-source'))
  return f
 def test_config_indexes_all_manifest_logos_without_runtime_resources(self):
  f=self.fixture();expected=f.stage();config=ET.parse(package.HERE/'priconfig.xml').getroot();indexes=config.findall('index')
  self.assertEqual(len(indexes),1);index=indexes[0];self.assertEqual(index.get('root'),'\\')
  seed=f.root/'payload'/index.get('startIndexAt').strip('\\/')
  indexed={p.relative_to(f.root/'payload').as_posix() for p in seed.rglob('*') if p.is_file()}
  assets=set(json.loads((package.HERE/'assets.lock.json').read_text()))
  manifest=ET.fromstring((f.root/'payload/AppxManifest.xml').read_bytes());references=set()
  for node in manifest.iter():
   if node.tag.rsplit('}',1)[-1]=='Logo':references.add(node.text.replace('\\','/'))
   references.update(v.replace('\\','/') for k,v in node.attrib.items() if k.endswith('Logo'))
  self.assertEqual(indexed,assets);self.assertEqual(references,assets)
  self.assertIn('Bristlune/'+RUNTIME,expected);package.verify_payload(f.root/'payload',expected)
 @unittest.skipUnless(sys.platform=='win32','Real Windows SDK packaging fixture')
 def test_actual_sdk_keeps_long_runtime_file_out_of_pri_and_in_unsigned_package(self):
  f=self.fixture();sdk=Path(os.environ['ProgramFiles(x86)'])/'Windows Kits/10/bin/10.0.26100.0/x64'
  evidence=package.SOURCE/'.brushquay/evidence';evidence.mkdir(parents=True,exist_ok=True)
  root=Path(tempfile.mkdtemp(prefix='sdk-fixture-',dir=evidence)).resolve()
  print('Actual SDK fixture evidence: '+str(root),flush=True)
  # Retain the SDK's original display and numeric versions separately. SignTool's
  # original display string need not match its numeric VS_FIXEDFILEINFO version.
  script=r'''$ErrorActionPreference='Stop'; [Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
$sdk=Join-Path ${env:ProgramFiles(x86)} 'Windows Kits/10/bin/10.0.26100.0/x64'
$rows=[ordered]@{}
foreach($name in @('makepri','makeappx','signtool')) {
 $path=Join-Path $sdk ($name+'.exe');$version=(Get-Item -LiteralPath $path).VersionInfo;$signature=Get-AuthenticodeSignature -LiteralPath $path
 $rows[$name]=[ordered]@{path=$path;bytes=(Get-Item -LiteralPath $path).Length;sha256=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant();status=[string]$signature.Status;subject=$signature.SignerCertificate.Subject;thumbprint=$signature.SignerCertificate.Thumbprint;originalFilename=$version.OriginalFilename;fileVersion=$version.FileVersion;fileVersionParts=@($version.FileMajorPart,$version.FileMinorPart,$version.FileBuildPart,$version.FilePrivatePart)}
}
$rows | ConvertTo-Json -Depth 5'''
  probe=subprocess.run(['powershell.exe','-NoLogo','-NoProfile','-NonInteractive','-Command',script],capture_output=True,timeout=60)
  (root/'sdk-versions.json').write_bytes(probe.stdout);(root/'sdk-versions.log').write_bytes(probe.stderr);probe.check_returncode()
  versions=json.loads(probe.stdout.decode('utf-8-sig'));tools={'sdkVersion':'10.0.26100.0'}
  self.assertEqual(set(versions),{'makepri','makeappx','signtool'})
  for name,row in versions.items():
   path=sdk/(name+'.exe');self.assertEqual(row['status'],'Valid');self.assertIn('O=Microsoft Corporation',row['subject']);self.assertRegex(row['thumbprint'],r'^[0-9A-Fa-f]{40}$')
   self.assertEqual(row['fileVersionParts'][:3],[10,0,26100]);self.assertEqual(len(row['fileVersionParts']),4);self.assertTrue(all(type(v) is int and 0<=v<=65535 for v in row['fileVersionParts']))
   self.assertEqual(row['originalFilename'].lower(),name+'.exe');self.assertTrue(row['fileVersion']);self.assertEqual(Path(row['path']),path)
   self.assertEqual(row['bytes'],path.stat().st_size);self.assertEqual(row['sha256'],hashlib.sha256(path.read_bytes()).hexdigest())
   if name!='signtool':tools[name]={k:row[k] for k in ('path','bytes','sha256')}
  # The original SDK refused a 260-character Qt image path. Keep the actual
  # generated payload filename over that bound without changing any runtime name.
  parent=root
  while len(str(parent))<125:parent=parent/'long-native-sdk-parent'
  parent.mkdir(parents=True,exist_ok=True)
  audit=root/'audit.json';audit.write_bytes(package.canonical(f.audit))
  tool_lock=root/'sdk-tools.json';tool_lock.write_bytes(package.canonical(tools))
  output=parent/'package'
  package.build(f.install,audit,f.props,tool_lock,output)
  runtime=output/'payload/Bristlune'/RUNTIME;self.assertGreaterEqual(len(str(runtime)),260)
  record=json.loads((output/'package-record.json').read_bytes())
  self.assertIn('Bristlune/'+RUNTIME,record['payload'])
  self.assertEqual(package.inventory(f.install),package.validate_audit(f.audit))
  dump=root/'resources-dump.xml'
  with (root/'dump.log').open('xb') as log:
   subprocess.run([str(sdk/'makepri.exe'),'dump','/if',str(output/'payload/resources.pri'),'/of',str(dump),'/dt','detailed'],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
  doc=ET.parse(dump).getroot();values=[]
  for node in doc.iter():
   if node.tag.rsplit('}',1)[-1]=='Candidate' and node.get('type','').lower()=='path':
    values.extend((n.text or '').replace('\\','/') for n in node if n.tag.rsplit('}',1)[-1]=='Value')
  self.assertEqual(sorted(values),sorted(json.loads((package.HERE/'assets.lock.json').read_text())))
  result={'scope':'small actual SDK fixture, no application qualification','source':subprocess.check_output(['git','-C',str(package.SOURCE),'rev-parse','HEAD'],text=True).strip(),'sdk':tools,'runtimePathLength':len(str(runtime)),'indexedCandidates':values,'originalRuntimePreserved':True,'unsignedPackAndUnpackVerified':True}
  (root/'result.json').write_bytes(package.canonical(result))
  print('Actual SDK fixture evidence: '+str(root))

if __name__=='__main__':unittest.main()
