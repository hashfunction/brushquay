#!/usr/bin/env python3
# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
"""Verify proposed release materials against retained original native evidence.

No native binaries are downloaded/built. This cannot approve the active binding.
"""
import argparse,json
from pathlib import Path
from release_inputs import read_json,source_file,hashed,apply_exclusions,validate_candidate
from release_build import CONTEXT
from runtime_stage import measure

ROOT=Path(__file__).resolve().parents[3]

def validate_store_terms(source,basis,selected,original_catalog,catalog,additional):
 """Bind the proposed downstream terms to shipped bytes and original grants."""
 text_path=source_file(source,basis['licenseText']);text=text_path.read_bytes()
 notice=basis['packagedNotice'];rows={r['path']:r for r in catalog['files']}
 notice_root=Path(source)/'distribution/native-source/original-notices'
 if notice not in rows or hashed(rows[notice])!=measure(text_path) or measure(notice_root/notice)!=measure(text_path) or additional.get('licenses/Bristlune/'+notice)!=text:
  raise ValueError('Store terms differ from the exact packaged notice')
 microsoft_names={'dbgcore.dll','dbghelp.dll','symsrv.dll','vcruntime140.dll','vcruntime140_1.dll'}
 actual={n:hashed(v) for n,v in selected.items() if Path(n).name.lower() in microsoft_names}
 required={'bin/dbgcore.dll','bin/dbghelp.dll','bin/symsrv.dll','bin/vcruntime140.dll','bin/vcruntime140_1.dll','python/vcruntime140.dll','python/vcruntime140_1.dll'}
 if set(actual)!=required or actual!=basis['standaloneMicrosoftFiles']:
  raise ValueError('Store terms Microsoft runtime scope differs')
 ids={'microsoft-sdk18362','microsoft-vc-runtime','microsoft-vc-distribution','python-windows-conditions'}
 associations=[r for r in original_catalog['associations'] if r['id'] in ids]
 names={n for r in associations for n in r['files']}
 originals={r['path']:r for r in original_catalog['files']}
 if len(associations)!=len(ids) or len(names)!=10 or names!=set(basis['originalNotices']):
  raise ValueError('Store terms original Microsoft grant scope differs')
 for name,value in basis['originalNotices'].items():
  if name not in rows or name not in originals or hashed(rows[name])!=value or hashed(originals[name])!=value or measure(notice_root/name)!=value:
   raise ValueError('Store terms original Microsoft grant bytes differ: '+name)
 return {'licenseText':basis['licenseText'],'standaloneMicrosoftFiles':len(actual),'originalMicrosoftNotices':len(names)}

def check(source,record_path,graph_path):
 source=Path(source)
 folder=source/'packaging/windows/msix/release-data'
 proof=read_json(folder/'candidate-provenance.json')
 if measure(record_path)!=proof['originalRuntimeRecord'] or measure(graph_path)!=proof['originalPeGraph']:
  raise ValueError('Original native evidence bytes differ')
 record=read_json(record_path);graph=read_json(graph_path)
 context={k:record[k] for k in CONTEXT}
 if context!=proof['nativeContext']:raise ValueError('Original source/run context differs')
 binding=read_json(folder/'review-candidate.json');proposed=binding['candidate']
 if proposed['excludedRuntime']!=proof['excludedRuntime']:raise ValueError('Proposed TLS omission differs')
 selected=apply_exclusions(record['runtimeInputs'],proposed['excludedRuntime'],graph,context,proposed['optionalTlsRemovalReviewed'])
 omitted=proof['omittedSourceInstalledBundle'];name=omitted['path']
 if name not in selected or hashed(selected[name])!=hashed(omitted) or selected[name]['inputs']!=[{'tree':'application','path':name}]:
  raise ValueError('Original omitted example bundle differs')
 selected.pop(name)
 application=sum(any(i['tree']=='application' for i in row['inputs']) for row in selected.values())
 if (len(record['runtimeInputs']),graph['selectedPeFiles'],len(selected),application,len(selected)-application)!=(
  proof['originalSelectedFiles'],proof['originalPeFiles'],proof['projectedRetainedFiles'],proof['projectedApplicationFiles'],proof['projectedDependencyFiles']):
  raise ValueError('Projected native selection counts differ')
 original_catalog=read_json(source_file(source,proof['originalCatalog']))
 combined_catalog=read_json(source_file(source,proposed['catalog']))
 if combined_catalog['archives']!=original_catalog['archives'] or combined_catalog['files'][:len(original_catalog['files'])]!=original_catalog['files']:
  raise ValueError('Original dependency catalog was rewritten')
 result=validate_candidate(source,binding,selected,context['sourceCommit'])
 store_terms=validate_store_terms(source,read_json(folder/'store-license-basis.json'),selected,original_catalog,combined_catalog,result['additionalFiles'])
 if read_json(source/'packaging/windows/msix/release-inputs.json')!={'schema':1,'reviewed':None}:
  raise ValueError('This candidate check requires the active binding to remain unapproved')
 return {'schema':1,'candidateMaterialsVerified':True,'reviewed':False,
  'licenseReviewComplete':result['audit']['licenseReviewComplete'],
  'correspondingSourceComplete':result['audit']['correspondingSourceComplete'],
  'nativeContext':context,'originalSelectedFiles':len(record['runtimeInputs']),
  'projectedRetainedFiles':len(selected),'projectedApplicationFiles':application,
  'owners':len(proposed['owners']),'originalNoticeFiles':len(combined_catalog['files']),
  'storeTerms':store_terms,
  'candidate':measure(folder/'review-candidate.json'),
  'note':'Historical native bytes establish projected path ownership only. Fresh source-built runtime, both installed lifecycles and independent export remain required.'}

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--source',type=Path,default=ROOT)
 p.add_argument('--runtime-record',required=True,type=Path)
 p.add_argument('--pe-graph',required=True,type=Path)
 a=p.parse_args();print(json.dumps(check(a.source,a.runtime_record,a.pe_graph),indent=2))
