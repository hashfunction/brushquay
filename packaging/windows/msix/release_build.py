# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
"""Opt-in reviewed runtime staging around the existing audited MSIX builder."""
import argparse,json,os,re,sys
from pathlib import Path
import xml.etree.ElementTree as ET
from build_msix import build,canonical,write_new,validate_audit,load_tools,verify_payload
from manifest_identity import identity_for_mode,require_mode,family_for_mode
from release_inputs import read_json,validate_reviewed,apply_exclusions,digest,hashed
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'qualification'))
from prepare import native_evidence,QT_CONF
from runtime_stage import ROOT,measure,measure_tree,select_runtime,materialize,no_links
from pe_imports import retain_imports
from locked_windows_deps import load_lock,verify_stage,sha,canonical as lock_canonical

CONTEXT=('sourceCommit','sourceTree','workflowRunId','workflowRunAttempt','nativeEvidence','lockSha256')

def helper_inventory(source):
 paths=[]
 for folder in ('packaging/windows/msix','packaging/windows/qualification'):
  paths.extend(p for p in (Path(source)/folder).rglob('*') if p.is_file() and p.suffix in ('.py','.ps1','.cs','.xml','.json'))
 paths.extend(Path(source)/n for n in ('build-tools/ci-scripts/locked_windows_deps.py','build-tools/ci-scripts/source_state.py','.github/workflows/windows.yml'))
 return {p.relative_to(source).as_posix():measure(p) for p in sorted(paths)}

def identity_xml(mode):
 root=ET.Element('Project');group=ET.SubElement(root,'PropertyGroup')
 for key,value in identity_for_mode(mode).items():ET.SubElement(group,key).text=value
 return ET.tostring(root,encoding='utf-8',xml_declaration=True)

def assert_release_record(record,mode):
 require_mode(record.get('identity'),mode)
 if record.get('mode')!=mode:raise ValueError('Selected release mode differs')
 expected={'qualificationOnly':mode=='qualification','releaseCandidate':True,'signed':False,'licenseReviewComplete':True,'correspondingSourceComplete':True,'publicBinaryDistributionAuthorizedByThisReceipt':False}
 for key,value in expected.items():
  if record.get(key) is not value:raise ValueError('Typed release package flag differs: '+key)
 if record.get('applicationId')!='BrushQuay' or record.get('executable')!='Bristlune/bin/bristlune.exe' or record.get('status')!='audited_package_verified_not_installed':raise ValueError('Prepared release package contract differs')
 for key in ('sourceCommit','sourceTree','workflowRunId','workflowRunAttempt'):
  if not isinstance(record.get(key),str) or not re.fullmatch('[0-9a-f]{40}' if key in ('sourceCommit','sourceTree') else '[1-9][0-9]*',record[key]):raise ValueError('Exact release source/run context required')

def assert_run_environment(commit,run,attempt,environment=None):
 environment=os.environ if environment is None else environment
 expected=dict(GITHUB_ACTIONS='true',RUNNER_OS='Windows',GITHUB_REPOSITORY='hashfunction/brushquay',GITHUB_SHA=commit,GITHUB_RUN_ID=run,GITHUB_RUN_ATTEMPT=attempt)
 if any(environment.get(k)!=v for k,v in expected.items()):raise ValueError('Exact current native GitHub source/run/attempt required')


def current_inputs(source,commit,run,attempt):
 assert_run_environment(commit,run,attempt)
 source=Path(source);path,native=native_evidence(source,commit,run,attempt)
 lock=load_lock(source/'build-tools/ci-scripts/brushquay-dependency-lock.json')
 if native['lockSha256']!=sha(lock_canonical(lock)):raise ValueError('Current native lock differs')
 manifest=verify_stage(lock,source/'.brushquay/cache',source/'.brushquay/locked')
 if not native.get('installedTree') or measure_tree(source/'.brushquay/install')!=native['installedTree']:raise ValueError('Current native installed bytes differ')
 selected=select_runtime(native['installedTree'],manifest['files'])
 context=dict(sourceCommit=commit,sourceTree=native['sourceTree'],workflowRunId=run,workflowRunAttempt=attempt,nativeEvidence=measure(path),lockSha256=native['lockSha256'])
 return context,selected,manifest

def reviewed_runtime(source,binding,selected,graph,context):
 review=binding.get('reviewed')
 if not isinstance(review,dict):raise ValueError('Reviewed release-input binding is absent')
 retained=apply_exclusions(selected,review.get('excludedRuntime'),graph,context,review.get('optionalTlsRemovalReviewed'))
 result=validate_reviewed(source,binding,retained,context['sourceCommit'])
 generated={'bin/qt.conf':QT_CONF}
 for name,data in generated.items():
  if name in retained:raise ValueError('Generated runtime input unexpectedly already exists')
  result['audit']['files'].append(dict(path=name,**digest(data),license='GPL-3.0-or-later',source='https://github.com/hashfunction/brushquay/archive/'+context['sourceCommit']+'.tar.gz'))
 result['additionalFiles'].update(generated)
 validate_audit(result['audit'])
 return retained,result

def prepare_release(source,output,evidence,tools_path,commit,run,attempt,mode):
 identity_for_mode(mode)
 if sys.platform!='win32':raise ValueError('Release package preparation requires actual native Windows')
 source=Path(source).absolute();output=Path(output).absolute();evidence=Path(evidence).absolute()
 no_links(source);no_links(output.parent);no_links(evidence.parent)
 if output.exists() or evidence.exists():raise ValueError('Existing release output is preserved')
 binding_path=source/'packaging/windows/msix/release-inputs.json';binding=read_json(binding_path)
 if not isinstance(binding.get('reviewed'),dict):raise ValueError('Reviewed release-input binding is absent')
 context,selected,manifest=current_inputs(source,commit,run,attempt);helpers=helper_inventory(source)
 sdk=load_tools(tools_path)
 if sdk['sdkVersion']!='10.0.26100.0':raise ValueError('Only the reviewed SDK version is accepted')
 evidence.mkdir();raw=output.with_name(output.name+'-full-runtime')
 materialize(source/'.brushquay/install',source/'.brushquay/locked',selected,raw)
 reader_name='tools/llvm/bin/llvm-readobj.exe';graph_path=evidence/'staged-pe-imports.json'
 summary=retain_imports(graph_path,raw,selected,source/'.brushquay/locked'/reader_name,manifest['files'].get(reader_name,{}),context)
 if summary.get('status')!='observed':raise ValueError('Complete current full runtime PE graph required; original observation retained')
 graph=read_json(graph_path);retained,reviewed=reviewed_runtime(source,binding,selected,graph,context)
 runtime=output.with_name(output.name+'-audited-runtime');materialize(source/'.brushquay/install',source/'.brushquay/locked',retained,runtime)
 for name,data in reviewed['additionalFiles'].items():write_new(runtime/name,data)
 audit_path=evidence/'runtime-audit.json';write_new(audit_path,canonical(reviewed['audit']))
 identity_path=evidence/'identity.props';write_new(identity_path,identity_xml(mode))
 build(runtime,audit_path,identity_path,tools_path,output)
 original=read_json(output/'package-record.json');require_mode(original['identity'],mode)
 record=dict(context,schema=2,mode=mode,qualificationOnly=mode=='qualification',releaseCandidate=True,
  identity=identity_for_mode(mode),family=family_for_mode(mode),applicationId='BrushQuay',executable='Bristlune/bin/bristlune.exe',
  licenseReviewComplete=reviewed['audit']['licenseReviewComplete'],correspondingSourceComplete=reviewed['audit']['correspondingSourceComplete'],publicBinaryDistributionAuthorizedByThisReceipt=False,signed=False,
  status='audited_package_verified_not_installed',runtimeInputs=retained,fullRuntimeInputs=selected,
  runtimeGeneratedFiles={name:digest(data) for name,data in reviewed['additionalFiles'].items()},
  releaseBinding=measure(binding_path),helpers=helpers,sourceReferences={'catalog':reviewed['catalog'],'publications':reviewed['publications']},
  peImportObservation=summary,audit=reviewed['audit'],builderRecord=measure(output/'package-record.json'),sdk=sdk,
  payload=original['payload'],verification=original['verification'],package=measure(output/'Bristlune.msix'))
 assert_release_record(record,mode)
 if current_inputs(source,commit,run,attempt)[:2]!=(context,selected) or helper_inventory(source)!=helpers:raise ValueError('Current release inputs changed during packaging')
 verify_payload(runtime,validate_audit(reviewed['audit']))
 write_new(output/'release-record.json',canonical(record));write_new(evidence/'qualification-package.json',canonical(record))
 return record

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('source','output','evidence','sdk-tools'):p.add_argument('--'+name,required=True,type=Path)
 for name in ('commit','run','attempt'):p.add_argument('--'+name,required=True)
 p.add_argument('--mode',choices=('qualification','store'),required=True);a=p.parse_args()
 prepare_release(a.source,a.output,a.evidence,a.sdk_tools,a.commit,a.run,a.attempt,a.mode)
