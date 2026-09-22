# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
"""Portable readback of an exact successful original export; never a new qualification."""
import argparse,hashlib,json,os,re,stat,subprocess,sys
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parents[3]
PACKAGE='Bristlune_1.0.1.0_x64.msix';REPOSITORY='hashfunction/brushquay'
def require(value,message):
 if not value:raise ValueError(message)
def load(path):
 require(Path(path).stat().st_size<=32*1024*1024,'JSON exceeds bound')
 def pairs(rows):
  result={}
  for k,v in rows:
   require(k not in result,'Duplicate JSON key');result[k]=v
  return result
 return json.loads(Path(path).read_text(encoding='utf-8-sig'),object_pairs_hook=pairs)
def no_links(path):
 p=Path(path).absolute()
 for item in (p,*p.parents):
  if os.path.lexists(item):
   value=item.lstat();require(not stat.S_ISLNK(value.st_mode) and not getattr(value,'st_file_attributes',0)&0x400,'Linked/reparse capture input refused')
def digest(path):
 no_links(path)
 h=hashlib.sha256();size=0
 with Path(path).open('rb') as f:
  for block in iter(lambda:f.read(1048576),b''):h.update(block);size+=len(block)
 return {'bytes':size,'sha256':h.hexdigest()}
def relative(name):
 require(isinstance(name,str) and name and '\\' not in name and ':' not in name and not name.startswith('/') and all(p not in ('','.','..') for p in name.split('/')) and str(PurePosixPath(name))==name,'Unsafe relative path');return name
def binding(value=None):
 value=load(Path(__file__).with_name('binding.json')) if value is None else value
 require(value.get('schema')==1 and value.get('product')=='Bristlune' and isinstance(value.get('qualified'),dict),'Capture requires reviewed exact successful Store package')
 b=value['qualified'];require(set(b)=={'source_commit','run_id','run_attempt','package','export_receipt','artifacts'},'Exact capture binding fields required')
 require(re.fullmatch('[0-9a-f]{40}',b['source_commit']) and all(isinstance(b[n],str) and re.fullmatch('[1-9][0-9]*',b[n]) for n in ('run_id','run_attempt')),'Exact source/run/attempt required')
 for name in ('package','export_receipt'):
  row=b[name];require(set(row)=={'bytes','sha256'} and type(row['bytes']) is int and row['bytes']>0 and re.fullmatch('[0-9a-f]{64}',row['sha256']),'Exact bytes required')
 require(set(b['artifacts'])=={'store','metadata'} and all(type(v) is int and v>0 for v in b['artifacts'].values()),'Exact artifact IDs required');return b
def checkout(root,commit):
 def git(*args):return subprocess.check_output(['git','-C',str(root),*args],timeout=30).decode().strip()
 require(git('rev-parse','HEAD')==commit and not git('status','--porcelain=v1','--untracked-files=all'),'Exact clean source checkout required')
def validate_run(run,b):
 require(run.get('id')==int(b['run_id']) and run.get('run_attempt')==int(b['run_attempt']) and run.get('head_sha')==b['source_commit'] and run.get('conclusion')=='success' and run.get('repository',{}).get('full_name')==REPOSITORY and run.get('path')=='.github/workflows/windows.yml','Original successful native run differs')
def verify_inputs(inputs,source,b,run):
 inputs=Path(inputs);source=Path(source);checkout(source,b['source_commit']);validate_run(run,b)
 sys.path.insert(0,str(source/'packaging/windows/msix'));sys.path.insert(0,str(source/'packaging/windows/qualification'))
 import store_export as exporter
 from release_inputs import validate_reviewed,apply_exclusions
 from release_build import helper_inventory,CONTEXT,assert_release_record
 from verify_brushquay_msix import verify_msix
 from manifest_identity import identity_for_mode
 ready=load(inputs/'store/store-export.json');package=inputs/'store'/PACKAGE
 require(digest(package)==b['package'] and digest(inputs/'store/store-export.json')==b['export_receipt'],'Original package/export receipt changed')
 require(ready.get('kind')=='independently-qualified-unsigned-store-export' and ready.get('schema')==1 and ready.get('signed') is False and ready.get('qualificationComplete') is True and ready.get('licenseReviewComplete') is True and ready.get('correspondingSourceComplete') is True,'Original final release gates incomplete')
 require(ready['sourceCommit']==b['source_commit'] and ready['workflowRunId']==b['run_id'] and ready['workflowRunAttempt']==b['run_attempt'] and ready['package']==b['package'] and ready['identity']==identity_for_mode('store') and ready['fileName']==PACKAGE,'Final original context differs')
 helpers=helper_inventory(source);require(ready['helpers']==helpers,'Qualified source/helper inventory differs')
 review=load(source/'packaging/windows/msix/release-inputs.json');require(ready['releaseBinding']==digest(source/'packaging/windows/msix/release-inputs.json'),'Original source approval binding changed')
 context={k:ready[k] for k in CONTEXT};found={}
 for p in (inputs/'metadata').rglob('installation-result.json'):
  value=load(p)
  if value.get('releaseCandidate') is True:
   mode=value.get('mode');require(mode in ('qualification','store') and mode not in found,'Ambiguous original installed lifecycle');found[mode]=(p,value)
 require(set(found)=={'qualification','store'} and set(ready['installedLifecycles'])==set(found),'Both original installed lifecycles required')
 payloads={};records={}
 for mode,(path,record) in found.items():
  proof=ready['installedLifecycles'][mode];folder=path.parent
  exporter.validate_completion(record);exporter.same_context(record,{k:context[k] for k in ('sourceCommit','sourceTree','workflowRunId','workflowRunAttempt')})
  require(digest(path)==proof['installation'] and record['originalEvidence']==proof['originalEvidence'],'Original lifecycle body/snapshot binding differs')
  exporter.original_snapshots(folder,proof['originalEvidence'])
  prepared=load(folder/'package/qualification-package.json');assert_release_record(prepared,mode);exporter.same_context(prepared,context)
  require(digest(folder/'package/qualification-package.json')==proof['packageRecord'] and prepared['helpers']==helpers and prepared['package']==proof['package'],'Original prepared package/source differs')
  graph=load(folder/'package/staged-pe-imports.json');require(digest(folder/'package/staged-pe-imports.json')==prepared['peImportObservation']['file'],'Original complete PE graph changed')
  retained=apply_exclusions(prepared['fullRuntimeInputs'],review['reviewed']['excludedRuntime'],graph,context,review['reviewed']['optionalTlsRemovalReviewed'])
  materials=validate_reviewed(source,review,retained,b['source_commit'])
  require(retained==prepared['runtimeInputs'] and prepared['sourceReferences']=={'catalog':materials['catalog'],'publications':materials['publications']},'Original runtime/source owner selection differs')
  # The final signed-off receipt binds the original full GUI/module/path-sensitive
  # validator run. Portable checks retain every original body rather than rewrite
  # original Windows locations to this download directory.
  gui=load(folder/'gui/gui-observations.json')
  require(all(gui.get(k) is True for k in ('passed','normalClosePassed','ownedProcessesStopped','jobAssigned')) and type(gui.get('normalExitCode')) is int and gui['normalExitCode']==0 and not any(k in gui for k in ('error','cleanupError','diagnosticError','forcedStop')),'Original complete GUI/normal-close evidence differs')
  require([s['stage'] for s in gui['steps']]==list(exporter.STAGES) and proof['gui']=={'processId':gui['activatedPid'],'processStartUtc':gui['processStartUtc'],'originalGui':digest(folder/'gui/gui-observations.json')},'Original complete ordered process binding differs')
  exporter.validate_artwork(load(folder/'artwork-verification.json'))
  for n in ('installed-files.json','installed-files-after-close.json'):
   require(load(folder/n)=={'verifiedPayloadFiles':len(prepared['payload']),'installedManifest':prepared['payload']['AppxManifest.xml']},'Original installed payload readback differs')
  require(record['display']['restore_verified'] is True and record['display']['restored']==record['display']['before'],'Original display restoration missing')
  payloads[mode]=prepared['payload'];records[mode]=prepared
 left=dict(payloads['qualification']);right=dict(payloads['store'])
 for n in ('AppxManifest.xml','resources.pri'):left.pop(n);right.pop(n)
 require(left==right,'Both original installed runtime payloads differ')
 require(verify_msix(package,payloads['store'],identity_for_mode('store'))==records['store']['verification'],'Exact original unsigned MSIX container differs')
 return records['store']
def main():
 p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path);p.add_argument('--qualified-source',type=Path);p.add_argument('--binding-output',type=Path);a=p.parse_args();b=binding()
 if a.binding_output:
  with a.binding_output.open('a') as f:f.write('qualified_source='+b['source_commit']+'\n')
 else:
  checkout(ROOT,os.environ.get('GITHUB_SHA'));record=verify_inputs(a.inputs,a.qualified_source,b,load(a.inputs/'qualified-run.json'))
  target=a.inputs/'verified-package.json'
  if target.exists():require(load(target)==record,'Prepared verified record changed')
  else:
   with target.open('x') as f:json.dump(record,f)
  print('Original exact Store payload, sources and both complete installed lifecycle bodies verified for capture only.')
if __name__=='__main__':main()
