"""Synthetic original-file replay through the production final lifecycle verifier.

No native UI/SDK success is simulated or claimed. Only native path comparison is
adapted to the temporary host filesystem; all record/hash/payload checks are real.
"""
import copy,json,os,sys,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import test_release_inputs as input_fixture
import store_export as export
from release_build import reviewed_runtime
from release_inputs import digest
from manifest_identity import identity_for_mode,family_for_mode,verify_manifest_identity
from build_msix import manifest_bytes,canonical
from runtime_stage import measure,measure_tree

# Independent expected sequence from the original C# Workflow/Picker calls.
WORKFLOW_STAGES=('01-installed-ready','new-document-settings','picker-02-blank.kra','picker-03-artwork.kra','02-painted-artwork','picker-05-artwork.png','png-export-options','picker-07-artwork.png','picker-08-reopened.kra','03-reopened-export')
CAPTURE_STAGES=('01-installed-ready','new-document-settings','02-painted-artwork','png-export-options','03-reopened-export')

class OriginalLifecycleReplay(unittest.TestCase):
 def setUp(self):
  f=input_fixture.ReleaseInputTests('test_reviewed_inputs_and_original_notice');f.setUp();self.addCleanup(f.doCleanups)
  self.source=f.root;self.binding=f.binding;self.context=dict(sourceCommit='c'*40,sourceTree='d'*40,workflowRunId='42',workflowRunAttempt='1',nativeEvidence={'bytes':2,'sha256':'e'*64},lockSha256='f'*64)
  self.selected={n:dict(digest(n.encode()),inputs=[dict(tree='application',path=n)]) for n in ('bin/bristlune.exe','bin/Qt6Core.dll','plugins/platforms/qwindows.dll')}
  self.binding['reviewed']['runtimeOwners']={n:['application'] for n in self.selected}
  self.write(self.source/'packaging/windows/msix/release-inputs.json',self.binding)
  (self.source/'packaging/windows/msix/pkg/Assets').mkdir(parents=True)
  asset=self.source/'packaging/windows/msix/pkg/Assets/Logo.png';asset.write_bytes(b'original asset')
  self.write(self.source/'packaging/windows/msix/assets.lock.json',{'Assets/Logo.png':measure(asset)})
  self.graph=dict(self.context,status='observed',errors=[],selectedPeFiles=len(self.selected),files=[dict(v,path=n,normalImports=[],delayImports=[]) for n,v in self.selected.items()])
  self.retained,self.reviewed=reviewed_runtime(self.source,self.binding,self.selected,self.graph,self.context)
  self.original=[]
 def write(self,path,value):
  path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(value if isinstance(value,bytes) else canonical(value));return measure(path)
 def construct(self,mode):
  root=self.source/'.brushquay/evidence'/('installed-'+mode);root.mkdir(parents=True);self.root=root
  work=self.source/'.brushquay/qualification'/('owned-'+mode);directory=work/'package';(directory/'payload').mkdir(parents=True);(directory/'unpacked').mkdir()
  identity=identity_for_mode(mode);family=family_for_mode(mode);full=identity['PackageName']+'_1.0.1.0_x64__'+family.rsplit('_',1)[1];installation='C:\\Program Files\\WindowsApps\\'+full
  for n in self.selected:self.write(directory/'payload/Bristlune'/n,n.encode())
  for n,data in self.reviewed['additionalFiles'].items():self.write(directory/'payload/Bristlune'/n,data)
  self.write(directory/'payload/Assets/Logo.png',b'original asset');self.write(directory/'payload/AppxManifest.xml',manifest_bytes(identity));self.write(directory/'payload/resources.pri',b'original index')
  payload=measure_tree(directory/'payload');package=directory/'Bristlune.msix'
  with zipfile.ZipFile(package,'w') as z:
   for n in payload:z.write(directory/'payload'/n,n);self.write(directory/'unpacked'/n,(directory/'payload'/n).read_bytes())
   z.writestr('[Content_Types].xml','<Types/>');z.writestr('AppxBlockMap.xml','<BlockMap/>')
  sdk={'sdkVersion':'10.0.26100.0'}
  for n in ('makepri','makeappx','signtool'):
   path=work/'sdk'/(n+'.exe');self.write(path,('tool-'+n).encode());row=dict(path=str(path),**measure(path))
   if n=='signtool':sign=row
   else:sdk[n]=row
  self.write(work/'sdk-tools.json',sdk);self.write(work/'GuiProbe.exe',b'fixture compiled observer')
  verification=export.verify_msix(package,payload,identity)
  original=dict(schema=1,identity=identity,audit=self.reviewed['audit'],sdk=sdk,payload=payload,verification=verification,unpackedManifest=verify_manifest_identity((directory/'unpacked/AppxManifest.xml').read_bytes(),identity),signed=False)
  original_hash=self.write(directory/'package-record.json',original)
  reader=self.source/'.brushquay/locked/tools/llvm/bin/llvm-readobj.exe';self.write(reader,b'exact locked reader')
  self.graph['reader']=dict(path=str(reader),**measure(reader),owners=['llvm-mingw'],arguments=['--coff-imports'])
  graphhash=self.write(root/'package/staged-pe-imports.json',self.graph)
  rec=dict(self.context,schema=2,mode=mode,identity=identity,qualificationOnly=mode=='qualification',releaseCandidate=True,signed=False,licenseReviewComplete=True,correspondingSourceComplete=True,publicBinaryDistributionAuthorizedByThisReceipt=False,applicationId='BrushQuay',executable='Bristlune/bin/bristlune.exe',status='audited_package_verified_not_installed',helpers={},releaseBinding=measure(self.source/'packaging/windows/msix/release-inputs.json'),sourceReferences={k:self.reviewed[k] for k in ('catalog','publications')},fullRuntimeInputs=self.selected,runtimeInputs=self.retained,audit=self.reviewed['audit'],runtimeGeneratedFiles={n:digest(v) for n,v in self.reviewed['additionalFiles'].items()},builderRecord=original_hash,sdk=sdk,payload=payload,verification=verification,package=measure(package),peImportObservation={'file':graphhash})
  self.write(directory/'release-record.json',rec);self.write(root/'package/qualification-package.json',rec)
  proof=dict(passed=True,primaryError=None,cleanupErrors=[],uninstalled=True,fixtureRemoved=True,profileRemoved=True,certificateRemoved=True,publicCertificateRemoved=True,signedCopyRemoved=True,
   **{k:self.context[k] for k in ('sourceCommit','sourceTree','workflowRunId','workflowRunAttempt')},releaseCandidate=True,mode=mode,qualificationOnly=mode=='qualification',packageFamilyName=family,packageFullName=full,packageDirectory=str(directory),installLocation=installation,windowsRoot='C:\\Windows',packageRecord=measure(directory/'release-record.json'),sdk=sdk,
   sdkAuthenticode={n:dict(subject='CN=Microsoft Windows, O=Microsoft Corporation',thumbprint='a'*40,fileVersion=('4.00 (WinBuild.160101.0800)' if n=='signtool' else '10.0.26100.7705 (WinBuild.160101.0800)'),fileVersionParts=[10,0,26100,7705]) for n in ('makepri','makeappx','signtool')},signTool=sign,probe=measure(work/'GuiProbe.exe'),unsignedPackage=measure(package),signedPackage=digest(b'original signed copy'),display=dict(restore_verified=True,restored={'width':1024},before={'width':1024},registry_updated=False,unsafe_modes_enabled=False,dpi_changed=False,renderer_emulation_used=False))
  for n in ('installed-files.json','installed-files-after-close.json'):self.write(root/n,dict(verifiedPayloadFiles=len(payload),installedManifest=payload['AppxManifest.xml']))
  artwork={'dimensions':[512,384],'changed_pixels':1000,'export_matches_saved_artwork':True,'reopened_pixels_match':True,'protected_files_unchanged':True,'pixel_sha256':'a'*64,'files':{n:digest(n.encode()) for n in ('blank.kra','artwork.kra','artwork.png','reopened.kra')}}
  self.write(root/'artwork-verification.json',artwork)
  inp=dict(payload=payload,sourceCommit='c'*40,sourceTree='d'*40,run='42',attempt='1',nativeEvidence=self.context['nativeEvidence'],unsignedPackage=measure(package));self.write(root/'gui/probe-input.json',inp)
  pid=100 if mode=='qualification' else 200;started='2026-09-12T20:00:00+00:00';exe=payload['Bristlune/bin/bristlune.exe']['sha256'];steps=[]
  for i,stage in enumerate(WORKFLOW_STAGES,1):
   item=dict(stage=stage,timeUtc=f'2026-09-12T20:00:{i:02d}+00:00',processId=pid,processStartUtc=started,packageFullName=full,executableSha256=exe,handle=123,nodes=[])
   self.write(root/'gui'/(stage+'-observation.json'),item)
   if stage in CAPTURE_STAGES:
    png=root/'gui'/(stage+'.png');self.write(png,b'fixture screenshot bytes')
    capture=dict(path=str(png),sha256=measure(png)['sha256'],bounds=[0,0,1472,1080],unedited=True,purpose='installed consumer qualification',processId=pid,handle=123,executableSha256=exe)
    self.write(root/'gui'/(stage+'-capture.json'),capture);item['capture']=capture
   steps.append(item)
  modules=[dict(path=installation+'/'+n,kind='package',payloadPath=n,**row) for n,row in payload.items() if n in ('Bristlune/bin/Qt6Core.dll','Bristlune/plugins/platforms/qwindows.dll')]
  summaries=[]
  for phase in ('startup','workflow-complete'):
   path=root/'gui'/('module-observation-'+phase+'.json')
   value=dict(schema=1,status='observed',errors=[],processId=pid,processStartUtc=started,packageFullName=full,executableSha256=exe,executable=installation+'/Bristlune/bin/bristlune.exe',probeInput=measure(root/'gui/probe-input.json'),elapsedMilliseconds=10,modules=modules,**{k:v for k,v in inp.items() if k!='payload'})
   file=self.write(path,value);summaries.append(dict(phase=phase,path=str(path),status='observed',errors=[],file=file))
  gui=dict(passed=True,normalClosePassed=True,ownedProcessesStopped=True,jobAssigned=True,normalExitCode=0,activatedPid=pid,processStartUtc=started,executableSha256=exe,steps=steps,moduleObservations=summaries,modules=[dict(path=r['payloadPath'],sha256=r['sha256']) for r in modules])
  self.write(root/'gui/gui-observations.json',gui)
  proof['originalEvidence']={p.relative_to(root).as_posix():measure(p) for p in (root/'gui').iterdir()}
  for n in ('installed-files.json','installed-files-after-close.json','artwork-verification.json'):proof['originalEvidence'][n]=measure(root/n)
  self.write(root/'installation-result.json',proof)
  self.original=[(p,p.read_bytes()) for p in root.rglob('*') if p.is_file()]
  return root
 def verify(self,mode):
  # Only filesystem path spelling differs on the fixture host. Native identity,
  # hashes, manifests, ZIP, all original snapshots and typed gates run unchanged.
  with patch.dict(os.environ,{'WINDIR':'C:\\Windows'}),patch.object(export,'window_path',side_effect=lambda p:str(p).replace('/','\\').casefold()):
   return export.verify_lifecycle(self.source,self.root,mode,self.context,self.selected,{},self.binding)
 def restore(self):
  for p,data in self.original:p.write_bytes(data)
 def test_both_complete_original_lifecycles(self):
  for mode in ('qualification','store'):
   self.construct(mode);self.assertEqual(self.verify(mode)['mode'],mode)
 def test_picker_order_presence_identity_and_capture_policy_remain_exact(self):
  self.construct('store')
  for mutation in ('omit-picker','duplicate-picker','reorder-picker','foreign-picker','picker-capture','missing-capture'):
   with self.subTest(mutation=mutation):
    self.restore();path=self.root/'gui/gui-observations.json';gui=json.loads(path.read_bytes());steps=gui['steps']
    if mutation=='omit-picker':steps.pop(2)
    elif mutation=='duplicate-picker':steps.insert(3,copy.deepcopy(steps[2]))
    elif mutation=='reorder-picker':steps[2],steps[3]=steps[3],steps[2]
    elif mutation=='foreign-picker':
     steps[2]['processId']=999
     self.write(self.root/'gui'/(steps[2]['stage']+'-observation.json'),steps[2])
    elif mutation=='picker-capture':steps[2]['capture']=copy.deepcopy(steps[0]['capture'])
    else:steps[0].pop('capture')
    self.write(path,gui)
    receipt=json.loads((self.root/'installation-result.json').read_bytes())
    for name in receipt['originalEvidence']:receipt['originalEvidence'][name]=measure(self.root/name)
    self.write(self.root/'installation-result.json',receipt)
    with self.assertRaises(ValueError):self.verify('store')
 def test_numeric_sdk_version_signature_and_original_display_are_required(self):
  self.construct('store')
  for field,value in [('fileVersionParts',None),('fileVersionParts',[10,0,26101,7705]),('fileVersionParts',[10,0,26100]),('fileVersionParts',[10,0,26100,True]),('fileVersionParts',[10,0,26100,65536]),('fileVersionParts',[10,0,26100,-1]),('fileVersion',''),('subject','CN=Foreign publisher'),('thumbprint','not-a-thumbprint')]:
   with self.subTest(field=field,value=value):
    self.restore();path=self.root/'installation-result.json';proof=json.loads(path.read_bytes());proof['sdkAuthenticode']['signtool'][field]=value;self.write(path,proof)
    with self.assertRaisesRegex(ValueError,'Original SDK signature/version evidence incomplete'):self.verify('store')
 def test_current_sdk_payload_and_unsigned_container_mutations_refused(self):
  self.construct('store')
  proof=json.loads((self.root/'installation-result.json').read_bytes());directory=Path(proof['packageDirectory'])
  tool=Path(proof['sdk']['makeappx']['path']);original=tool.read_bytes();tool.write_bytes(b'foreign tool')
  with self.assertRaises(ValueError):self.verify('store')
  tool.write_bytes(original)
  extra=directory/'payload/private.pfx';extra.write_bytes(b'private signing material')
  with self.assertRaises(ValueError):self.verify('store')
  extra.unlink()
  with zipfile.ZipFile(directory/'Bristlune.msix','a') as archive:archive.writestr('AppxSignature.p7x',b'forbidden signed submission')
  with self.assertRaises(ValueError):self.verify('store')
 def test_stale_partial_fabricated_oracle_snapshot_and_workflow_refused(self):
  self.construct('store')
  for file,key,value in [('installation-result.json','workflowRunAttempt','2'),('installation-result.json','signedCopyRemoved',False),('gui/gui-observations.json','forcedStop',True),('gui/gui-observations.json','steps',[]),('artwork-verification.json','reopened_pixels_match',False),('gui/probe-input.json','payload',{}),('gui/module-observation-startup.json','status','incomplete'),('package/staged-pe-imports.json','reader',{})]:
   with self.subTest(file=file,key=key):
    self.restore();p=self.root/file;data=json.loads(p.read_bytes());data[key]=value;self.write(p,data)
    # Updating the outer snapshot alone cannot manufacture successful inner evidence.
    receipt=json.loads((self.root/'installation-result.json').read_bytes())
    if file in receipt['originalEvidence']:receipt['originalEvidence'][file]=measure(p);self.write(self.root/'installation-result.json',receipt)
    with self.assertRaises((ValueError,KeyError)):self.verify('store')
  self.restore();(self.root/'gui/new-document-settings-observation.json').unlink()
  with self.assertRaises((ValueError,OSError)):self.verify('store')
if __name__=='__main__':unittest.main()
