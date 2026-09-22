# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
"""Independent unsigned export from two original installed consumer lifecycles."""
import argparse,json,os,re,shutil,sys,tempfile
from datetime import datetime,timezone
from pathlib import Path,PureWindowsPath
from build_msix import canonical,manifest_bytes,load_tools,validate_audit,write_new,verify_payload,publish_directory_no_replace
from manifest_identity import identity_for_mode,family_for_mode,verify_manifest_identity
from verify_brushquay_msix import verify_msix,checked_path
from release_inputs import read_json,hashed,digest
from release_build import current_inputs,helper_inventory,reviewed_runtime,assert_release_record,CONTEXT
from runtime_stage import ROOT,measure,measure_tree,no_links

STAGES=('01-installed-ready','new-document-settings','picker-02-blank.kra','picker-03-artwork.kra','02-painted-artwork','picker-05-artwork.png','png-export-options','picker-07-artwork.png','picker-08-reopened.kra','03-reopened-export')
CAPTURE_STAGES=('01-installed-ready','new-document-settings','02-painted-artwork','png-export-options','03-reopened-export')
PACKAGE='Bristlune_1.0.1.0_x64.msix'

def require(condition,message):
 if not condition:raise ValueError(message)
def same_context(value,context):
 require(all(value.get(k)==v and type(value.get(k)) is type(v) for k,v in context.items()),'Original source/run context differs')
def require_unsigned_names(payload):
 for name in payload:
  checked_path(name)
  require(Path(name).name.lower()!='appxsignature.p7x' and Path(name).suffix.lower() not in ('.pfx','.p12','.key','.cer'), 'Signing material is forbidden in unsigned payload')
def validate_completion(record):
 for key in ('passed','uninstalled','fixtureRemoved','profileRemoved','certificateRemoved','publicCertificateRemoved','signedCopyRemoved'):
  require(record.get(key) is True,'Incomplete installed lifecycle/cleanup: '+key)
 require(record.get('primaryError') is None and record.get('cleanupErrors')==[],'Original lifecycle failed')
def validate_artwork(value):
 require(set(value)=={'dimensions','changed_pixels','export_matches_saved_artwork','reopened_pixels_match','protected_files_unchanged','pixel_sha256','files'},'Original complete pixel oracle required')
 require(value['dimensions']==[512,384] and all(type(v) is int for v in value['dimensions']),'Actual artwork dimensions differ')
 require(type(value['changed_pixels']) is int and 50<=value['changed_pixels']<512*384//2,'Actual bounded brush stroke is unproved')
 for key in ('export_matches_saved_artwork','reopened_pixels_match','protected_files_unchanged'):require(value[key] is True,'Actual artwork oracle did not pass')
 require(isinstance(value['pixel_sha256'],str) and re.fullmatch('[0-9a-f]{64}',value['pixel_sha256']),'Missing original pixel digest')
 require(isinstance(value['files'],dict) and set(value['files'])=={'blank.kra','artwork.kra','artwork.png','reopened.kra'},'Original artwork snapshots incomplete')
 for row in value['files'].values():require(0<hashed(row)['bytes']<=32*1024*1024,'Unbounded original artwork snapshot')
def original_snapshots(root,records):
 require(isinstance(records,dict) and 0<len(records)<=64,'Original evidence snapshot set missing/unbounded')
 for name,record in records.items():
  checked_path(name);require(measure(Path(root)/name)==hashed(record),'Original evidence bytes differ: '+name)
 return records

def window_path(value):
 require(isinstance(value,str) and PureWindowsPath(value).is_absolute(),'Absolute native Windows path required')
 return str(PureWindowsPath(value)).casefold()
def beneath(value,root):return window_path(value).startswith(window_path(root).rstrip('\\')+'\\')

def validate_modules(root,gui,package,context,pid,started,full_name,installation):
 summaries=gui.get('moduleObservations');require(isinstance(summaries,list) and len(summaries)==2,'Both original module snapshots required')
 require([v.get('phase') for v in summaries]==['startup','workflow-complete'],'Original module sequence differs')
 for summary in summaries:
  phase=summary['phase'];path=root/'gui'/('module-observation-'+phase+'.json')
  require(summary.get('status')=='observed' and summary.get('errors')==[] and summary.get('file')==measure(path),'Incomplete original module snapshot')
  require(window_path(summary['path'])==window_path(str(path)),'Foreign module snapshot path')
  value=read_json(path)
  same_context(value,dict(sourceCommit=context['sourceCommit'],sourceTree=context['sourceTree'],run=context['workflowRunId'],attempt=context['workflowRunAttempt'],nativeEvidence=context['nativeEvidence'],unsignedPackage=package['package']))
  require(value.get('status')=='observed' and value.get('errors')==[] and value.get('processId')==pid and type(value.get('processId')) is int and value.get('processStartUtc')==started and value.get('packageFullName')==full_name,'Foreign/incomplete process module evidence')
  require(value.get('executableSha256')==package['payload']['Bristlune/bin/bristlune.exe']['sha256'] and window_path(value['executable'])==window_path(installation+'/Bristlune/bin/bristlune.exe'),'Foreign module executable')
  require(value.get('probeInput')==measure(root/'gui/probe-input.json'),'Module input snapshot differs')
  require(type(value.get('elapsedMilliseconds')) is int and 0<=value['elapsedMilliseconds']<=15000,'Module observation exceeded original budget')
  rows=value.get('modules');require(isinstance(rows,list) and 0<len(rows)<=1024,'Missing original modules')
  seen=set();packaged=set()
  for row in rows:
   actual=window_path(row['path']);require(actual not in seen,'Duplicate module path');seen.add(actual);hashed(row)
   if row.get('kind')=='package':
    relative=row.get('payloadPath');require(relative in package['payload'] and hashed(row)==package['payload'][relative],'Module is absent from exact package')
    require(actual==window_path(installation+'/'+relative),'Module package path differs');packaged.add(relative.lower())
   else:require(row.get('kind')=='windows' and beneath(row['path'],package['windowsRoot']),'Foreign loaded module boundary')
  if phase=='workflow-complete':require({'bristlune/bin/qt6core.dll','bristlune/plugins/platforms/qwindows.dll'}<=packaged,'Actual Qt core/platform modules missing')
 rows=gui.get('modules');require(isinstance(rows,list) and rows,'Original enforcing module gate missing')
 seen=set()
 for row in rows:
  name=row.get('path');require(name in package['payload'] and row.get('sha256')==package['payload'][name]['sha256'] and name not in seen,'Original enforcing module gate differs');seen.add(name)
 require({'Bristlune/bin/Qt6Core.dll','Bristlune/plugins/platforms/qwindows.dll'}<=seen,'Enforcing Qt module gate incomplete')

def validate_gui(root,record,package,context):
 gui=read_json(root/'gui/gui-observations.json')
 for key in ('passed','normalClosePassed','ownedProcessesStopped','jobAssigned'):require(gui.get(key) is True,'Actual GUI lifecycle is incomplete: '+key)
 require(type(gui.get('normalExitCode')) is int and gui['normalExitCode']==0,'Normal application exit failed')
 require(not any(k in gui for k in ('error','cleanupError','diagnosticError','forcedStop')),'GUI failure or forced stop cannot qualify')
 pid=gui.get('activatedPid');started=gui.get('processStartUtc');require(type(pid) is int and pid>0 and isinstance(started,str),'Original retained process identity missing')
 datetime.fromisoformat(started.replace('Z','+00:00'))
 exe=package['payload']['Bristlune/bin/bristlune.exe'];require(gui.get('executableSha256')==exe['sha256'],'GUI executable differs')
 probe=read_json(root/'gui/probe-input.json')
 expected=dict(payload=package['payload'],sourceCommit=context['sourceCommit'],sourceTree=context['sourceTree'],run=context['workflowRunId'],attempt=context['workflowRunAttempt'],nativeEvidence=context['nativeEvidence'],unsignedPackage=package['package'])
 require(probe==expected,'Original observer input differs from current package')
 steps=gui.get('steps');require(isinstance(steps,list) and [v.get('stage') for v in steps]==list(STAGES),'Complete original ordered consumer observations required')
 full_name=record['packageFullName'];previous=None
 for step in steps:
  stage=step['stage'];original=read_json(root/'gui'/(stage+'-observation.json'))
  require(original=={k:v for k,v in step.items() if k!='capture'},'Original window snapshot differs from embedded workflow')
  require(type(step.get('processId')) is int and step['processId']==pid and step.get('processStartUtc')==started and step.get('packageFullName')==full_name and step.get('executableSha256')==exe['sha256'],'Foreign workflow window identity')
  require(type(step.get('handle')) is int and step['handle']>0 and isinstance(step.get('nodes'),list) and len(step['nodes'])<=3000,'Original window snapshot incomplete')
  time=datetime.fromisoformat(step['timeUtc'].replace('Z','+00:00'));require(previous is None or time>=previous,'Workflow observation order differs');previous=time
  require(0<=(time-datetime.fromisoformat(started.replace('Z','+00:00'))).total_seconds()<=600,'Original consumer workflow exceeded ten-minute observer bound')
  if stage not in CAPTURE_STAGES:
   require('capture' not in step,'Picker observation unexpectedly claims a screenshot')
   continue
  capture=read_json(root/'gui'/(stage+'-capture.json'));require(capture==step.get('capture'),'Original capture differs from workflow')
  require(capture.get('unedited') is True and capture.get('purpose')=='installed consumer qualification' and capture.get('processId')==pid and capture.get('handle')==step['handle'] and capture.get('executableSha256')==exe['sha256'],'Foreign or edited capture')
  png=root/'gui'/(stage+'.png');require(window_path(capture['path'])==window_path(str(png)) and capture.get('sha256')==measure(png)['sha256'],'Original raw screenshot differs')
  bounds=capture.get('bounds');require(isinstance(bounds,list) and len(bounds)==4 and all(type(v) in (int,float) for v in bounds) and bounds[2]>0 and bounds[3]>0,'Original owned capture bounds missing')
 validate_modules(root,gui,dict(package,windowsRoot=record['windowsRoot']),context,pid,started,full_name,record['installLocation'])
 return {'processId':pid,'processStartUtc':started,'originalGui':measure(root/'gui/gui-observations.json')}

def expected_payload(source,audit,mode,pri):
 expected={'Bristlune/'+n:v for n,v in validate_audit(audit).items()}
 assets=read_json(Path(source)/'packaging/windows/msix/assets.lock.json')
 for name,row in assets.items():require(measure(Path(source)/'packaging/windows/msix/pkg'/name)==row,'Original package artwork changed')
 expected.update(assets);expected['AppxManifest.xml']=digest(manifest_bytes(identity_for_mode(mode)))
 require(hashed(pri)['bytes']>0,'Generated SDK resource index missing');expected['resources.pri']=hashed(pri)
 require_unsigned_names(expected)
 return expected

def verify_lifecycle(source,root,mode,context,selected,helpers,binding):
 root=Path(root);record=read_json(root/'installation-result.json');validate_completion(record)
 same_context(record,{k:context[k] for k in ('sourceCommit','sourceTree','workflowRunId','workflowRunAttempt')})
 require(record.get('releaseCandidate') is True and record.get('mode')==mode and record.get('qualificationOnly') is (mode=='qualification'),'Foundation/foreign installation cannot qualify release')
 require(window_path(record.get('windowsRoot'))==window_path(os.environ.get('WINDIR')),'Original Windows module root differs from current native host')
 family=family_for_mode(mode);identity=identity_for_mode(mode)
 full_name=identity['PackageName']+'_1.0.1.0_x64__'+family.rsplit('_',1)[1]
 require(record.get('packageFamilyName')==family and record.get('packageFullName')==full_name,'Installed fixed identity differs')
 directory=Path(record['packageDirectory']);no_links(directory)
 require(directory.name=='package' and directory.parent.parent==Path(source)/'.brushquay/qualification','Foreign prepared package location')
 package=read_json(directory/'release-record.json');assert_release_record(package,mode);same_context(package,context)
 require(record.get('packageRecord')==measure(directory/'release-record.json') and read_json(root/'package/qualification-package.json')==package,'Original prepared package snapshot differs')
 require(package.get('helpers')==helpers and package.get('releaseBinding')==measure(Path(source)/'packaging/windows/msix/release-inputs.json'),'Stale helper or review binding')
 graph_path=root/'package/staged-pe-imports.json';require(package['peImportObservation'].get('file')==measure(graph_path),'Original full PE graph changed')
 graph=read_json(graph_path);reader=Path(source)/'.brushquay/locked/tools/llvm/bin/llvm-readobj.exe'
 require(graph.get('reader')==dict(path=str(reader),**measure(reader),owners=['llvm-mingw'],arguments=['--coff-imports']),'Original exact locked PE reader differs')
 retained,reviewed=reviewed_runtime(source,binding,selected,graph,context)
 require(package.get('fullRuntimeInputs')==selected and package.get('runtimeInputs')==retained and package.get('audit')==reviewed['audit'],'Current exact audited runtime differs')
 require(package.get('runtimeGeneratedFiles')=={n:digest(v) for n,v in reviewed['additionalFiles'].items()} and package.get('sourceReferences')=={'catalog':reviewed['catalog'],'publications':reviewed['publications']},'Current source/notice material differs')
 sdk_path=directory.parent/'sdk-tools.json';sdk=load_tools(sdk_path)
 require(sdk.get('sdkVersion')=='10.0.26100.0' and package.get('sdk')==sdk and record.get('sdk')==sdk,'Current SDK tools differ')
 for name in ('makepri','makeappx','signtool'):
  auth=record.get('sdkAuthenticode',{}).get(name,{})
  parts=auth.get('fileVersionParts')
  numeric=isinstance(parts,list) and len(parts)==4 and all(type(v) is int for v in parts) and parts[:3]==[10,0,26100] and 0<=parts[3]<=65535
  require(isinstance(auth.get('subject'),str) and 'O=Microsoft Corporation' in auth['subject'] and re.fullmatch('[0-9A-Fa-f]{40}',auth.get('thumbprint','')) and isinstance(auth.get('fileVersion'),str) and bool(auth['fileVersion'].strip()) and numeric,'Original SDK signature/version evidence incomplete')
 sign_tool=record.get('signTool');require(isinstance(sign_tool,dict) and hashed(sign_tool)==measure(sign_tool['path']) and Path(sign_tool['path']).name.lower()=='signtool.exe' and Path(sign_tool['path']).parent==Path(sdk['makeappx']['path']).parent,'Current SDK signing tool differs')
 require(record.get('probe')==measure(directory.parent/'GuiProbe.exe'),'Retained compiled observer bytes differ')
 expected=expected_payload(source,reviewed['audit'],mode,package['payload']['resources.pri'])
 require(package['payload']==expected,'Package includes unexpected or stale payload')
 unsigned=directory/'Bristlune.msix';verified=verify_msix(unsigned,expected,identity)
 require(package.get('verification')==verified and package.get('package')==verified['package'] and record.get('unsignedPackage')==verified['package'],'Unsigned package binding differs')
 require(hashed(record.get('signedPackage'))!=verified['package'],'Installed signed copy was not distinct')
 original=read_json(directory/'package-record.json')
 require(package.get('builderRecord')==measure(directory/'package-record.json') and original.get('audit')==reviewed['audit'] and original.get('payload')==expected and original.get('identity')==identity and original.get('sdk')==sdk and original.get('signed') is False and original.get('verification')==verified,'Original audited builder record differs')
 unpacked=measure_tree(directory/'unpacked')
 for name in ('[Content_Types].xml','AppxBlockMap.xml'):unpacked.pop(name,None)
 require(unpacked==expected and original.get('unpackedManifest')==verify_manifest_identity((directory/'unpacked/AppxManifest.xml').read_bytes(),identity),'SDK unpacked original differs')
 verify_payload(directory/'payload',expected)
 snapshots=original_snapshots(root,record.get('originalEvidence'))
 required={'installed-files.json','installed-files-after-close.json','artwork-verification.json','gui/probe-input.json','gui/gui-observations.json','gui/module-observation-startup.json','gui/module-observation-workflow-complete.json'}
 for stage in STAGES:required.add('gui/'+stage+'-observation.json')
 for stage in CAPTURE_STAGES:required.update('gui/'+stage+suffix for suffix in ('-capture.json','.png'))
 require(set(snapshots)==required,'Complete exact original evidence file set differs')
 actual={p.relative_to(root).as_posix() for p in (root/'gui').iterdir() if p.is_file() and p.suffix in ('.json','.png')}
 require(actual=={n for n in required if n.startswith('gui/')},'Extra unbound GUI evidence')
 for name in ('installed-files.json','installed-files-after-close.json'):
  installed=read_json(root/name);require(type(installed.get('verifiedPayloadFiles')) is int and installed=={'verifiedPayloadFiles':len(expected),'installedManifest':expected['AppxManifest.xml']},'Original independent installed file oracle differs')
 artwork=read_json(root/'artwork-verification.json');validate_artwork(artwork)
 display=record.get('display');require(isinstance(display,dict) and display.get('restore_verified') is True and display.get('restored')==display.get('before'),'Original display restoration unproved')
 for key in ('registry_updated','unsafe_modes_enabled','dpi_changed','renderer_emulation_used'):require(display.get(key) is False,'Native display policy differs')
 gui=validate_gui(root,record,package,context)
 return {'mode':mode,'installation':measure(root/'installation-result.json'),'originalEvidence':snapshots,'package':verified['package'],'packageRecord':measure(directory/'release-record.json'),'artworkOracle':measure(root/'artwork-verification.json'),'gui':gui,'unsignedPath':unsigned,'payload':expected,'sdk':sdk,'sourceReferences':package['sourceReferences']}

def export(source,output,commit,run,attempt):
 require(sys.platform=='win32','Final export requires the actual native Windows run')
 source=Path(source).absolute();output=Path(output).absolute();no_links(output.parent);require(not output.exists(),'Existing Store export is preserved')
 binding=read_json(source/'packaging/windows/msix/release-inputs.json')
 require(isinstance(binding.get('reviewed'),dict),'Reviewed release-input binding is absent')
 context,selected,_=current_inputs(source,commit,run,attempt);helpers=helper_inventory(source);found={}
 for path in (source/'.brushquay/evidence').glob('installed-*/installation-result.json'):
  record=read_json(path)
  if record.get('sourceCommit')==commit and record.get('workflowRunId')==run and record.get('workflowRunAttempt')==attempt and record.get('releaseCandidate') is True:
   mode=record.get('mode');require(mode in ('qualification','store') and mode not in found,'Ambiguous original release lifecycle');found[mode]=path.parent
 require(set(found)=={'qualification','store'},'Both original installed release lifecycles are required')
 proofs={mode:verify_lifecycle(source,found[mode],mode,context,selected,helpers,binding) for mode in ('qualification','store')}
 require(proofs['store']['sdk']==proofs['qualification']['sdk'],'Both identities must use the same SDK')
 left=dict(proofs['qualification']['payload']);right=dict(proofs['store']['payload'])
 for name in ('AppxManifest.xml','resources.pri'):left.pop(name);right.pop(name)
 require(left==right,'Both installed packages must contain the same final application/runtime/notices')
 require(proofs['qualification']['gui']['processId']!=proofs['store']['gui']['processId'] or proofs['qualification']['gui']['processStartUtc']!=proofs['store']['gui']['processStartUtc'],'Both lifecycles reused one process identity')
 if current_inputs(source,commit,run,attempt)[:2]!=(context,selected) or helper_inventory(source)!=helpers:raise ValueError('Release inputs changed during independent export')
 temporary=Path(tempfile.mkdtemp(prefix='.bristlune-store-export-',dir=output.parent));target=temporary/PACKAGE
 with proofs['store']['unsignedPath'].open('rb') as source_file,target.open('xb') as destination:shutil.copyfileobj(source_file,destination,1024*1024)
 require(measure(target)==proofs['store']['package'],'Unsigned export changed during copy')
 verify_msix(target,proofs['store']['payload'],identity_for_mode('store'))
 for proof in proofs.values():proof.pop('unsignedPath');proof.pop('payload')
 receipt=dict(context,schema=1,kind='independently-qualified-unsigned-store-export',verifiedAtUtc=datetime.now(timezone.utc).isoformat(),signed=False,
  identity=identity_for_mode('store'),applicationId='BrushQuay',family=family_for_mode('store'),package=measure(target),fileName=PACKAGE,
  releaseBinding=measure(source/'packaging/windows/msix/release-inputs.json'),helpers=helpers,installedLifecycles=proofs,
  licenseReviewComplete=binding['reviewed']['licenseReviewComplete'],correspondingSourceComplete=binding['reviewed']['correspondingSourceComplete'],qualificationComplete=True)
 write_new(temporary/'store-export.json',canonical(receipt))
 require({p.name for p in temporary.iterdir()}=={PACKAGE,'store-export.json'},'Unexpected export artifact files')
 publish_directory_no_replace(temporary,output)
 return receipt

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--source',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
 for name in ('commit','run','attempt'):p.add_argument('--'+name,required=True)
 a=p.parse_args();export(a.source,a.output,a.commit,a.run,a.attempt)
