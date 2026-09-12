# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
"""Review attestations tied to exact current runtime, original notices and public sources."""
import hashlib,json,re,sys
from pathlib import Path
from urllib.parse import urlparse
from build_msix import canonical,validate_audit
from verify_brushquay_msix import checked_path,register_path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'qualification'))
from runtime_stage import measure,no_links
from pe_imports import PE_SUFFIXES

OPTIONAL_TLS={
 'plugins/tls/qopensslbackend.dll':{'bytes':1545216,'sha256':'bbcdd80bd27c8eec236f7f9410bf4edbed7155ffd1a8e9a5bbafc7c9e7845bac'},
 'bin/libssl-1_1-x64.dll':{'bytes':550984,'sha256':'98d9bb9eccc5d2846fe2cd51d4f91f7b368bbe755ab307f2b49c232a5fb59f8b'},
 'bin/libcrypto-1_1-x64.dll':{'bytes':2819656,'sha256':'bd3cf8a3342bd22a06234fd54eb93f6f4c98596f72f1df314505f325f9773e99'}}

# This one BSD DLL has version-qualified notices but no identified meson-2
# producer revision. Do not turn an upstream reference into an archive claim.
LIBVPX_REFERENCE={
 'key':'upstream-reference:libvpx-1.13.1',
 'url':'https://github.com/webmproject/libvpx/tree/v1.13.1',
 'license':'BSD-3-Clause','producerRevision':None,'exactSourceArchiveClaimed':False,
 'scope':'Upstream 1.13.1 LICENSE/PATENTS reference for the exact selected permissive DLL; original meson-2 producer revision is unidentified. No exact source or binary reproduction claim.',
 'notices':{
  'supplements/libvpx-1.13.1-reference/LICENSE':{'bytes':1537,'sha256':'8267348d5af1262c11d1a08de2f5afc77457755f1ac658627dd9acf71011d615'},
  'supplements/libvpx-1.13.1-reference/PATENTS':{'bytes':1436,'sha256':'cc3273e0694ea5896145e0677699b53471b03ea43021ddc50e7923fbb9f5023c'}},
 'runtime':{'bin/libvpx-8.dll':{'bytes':10112000,'sha256':'1c0d685e79e4d670f789ac72e06a2ec1e0166624e4833fe0d579846fff1f4141',
  'inputs':[{'tree':'locked','path':'deps/bin/libvpx-8.dll','owners':['ext_vpx']}]}}}

def vpx_reference(owner,rule,selected,notices):
 policy=LIBVPX_REFERENCE
 actual={n:v for n,v in selected.items() if any('ext_vpx' in i.get('owners',[]) for i in v['inputs'])}
 if owner!='ext_vpx' or rule['license']!=policy['license'] or rule['sources']!=[policy['key']] or sorted(rule['notices'])!=sorted(policy['notices']) or actual!=policy['runtime'] or any(notices.get(n)!=v for n,v in policy['notices'].items()):
  raise ValueError('Only the exact reviewed permissive libvpx reference is allowed')
 return {k:v for k,v in policy.items() if k!='key'}

def digest(data):return {'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
def hashed(value):
 if not isinstance(value,dict) or type(value.get('bytes')) is not int or value['bytes']<0 or not re.fullmatch('[0-9a-f]{64}',value.get('sha256','')):raise ValueError('Invalid exact file digest')
 return {k:value[k] for k in ('bytes','sha256')}
def read_json(path):
 before=measure(path)
 if before['bytes']>32*1024*1024:raise ValueError('Release JSON exceeds bound')
 def pairs(items):
  result={}
  for k,v in items:
   if k in result:raise ValueError('Duplicate JSON key')
   result[k]=v
  return result
 data=json.loads(Path(path).read_text(encoding='utf-8-sig'),object_pairs_hook=pairs)
 if measure(path)!=before:raise ValueError('Release JSON changed while reading')
 return data

def source_file(root,reference):
 if set(reference)!={'path','bytes','sha256'}:raise ValueError('Invalid source reference')
 checked_path(reference['path']);path=Path(root)/reference['path']
 if measure(path)!=hashed(reference):raise ValueError('Bound source reference changed: '+reference['path'])
 return path

def public_assets(record):
 if record.get('schemaVersion')!=1 or record.get('repository')!='hashfunction/brushquay':raise ValueError('Foreign publication receipt')
 for k in ('anonymous','tlsCertificateValidation','tlsHostnameValidation','allAssetsVerified'):
  if record.get(k) is not True:raise ValueError('Incomplete anonymous HTTPS source readback')
 for k in ('authorizationHeadersSent','cookiesUsed'):
  if record.get(k) is not False:raise ValueError('Authenticated source readback is not public proof')
 rows=record.get('assets');result={};urls=set()
 if not isinstance(rows,list) or not rows:raise ValueError('Missing original public assets')
 for row in rows:
  expected=hashed(row.get('expected'));url=row.get('url','');parsed=urlparse(url)
  if parsed.scheme!='https' or parsed.netloc!='github.com' or not parsed.path.startswith('/hashfunction/brushquay/releases/download/') or parsed.query or parsed.fragment:raise ValueError('Foreign public source URL')
  if row.get('status')!='verified' or type(row.get('httpStatus')) is not int or row['httpStatus']!=200 or row.get('tlsCertificateVerified') is not True or row.get('error') is not None or hashed(row)!=expected or url in urls:raise ValueError('Incomplete/duplicate original public body')
  urls.add(url);key=expected['sha256']
  if key in result:raise ValueError('Ambiguous public source bytes')
  result[key]=dict(expected,url=url)
 for key,value in {'verifiedAssetCount':len(rows),'expectedAssetCount':len(rows),'verifiedAssetBytes':sum(v['bytes'] for v in result.values()),'expectedAssetBytes':sum(v['bytes'] for v in result.values()),'failedAssetCount':0,'remainingAssetCount':0}.items():
  if type(record.get(key)) is not int or record[key]!=value:raise ValueError('Public readback counts disagree with original bodies')
 return result

def apply_exclusions(selected,excluded,graph,context,reviewed):
 if not isinstance(excluded,dict):raise ValueError('Invalid excluded runtime map')
 if excluded and (excluded!=OPTIONAL_TLS or reviewed is not True):raise ValueError('Only the exact separately reviewed optional TLS group may be excluded')
 if not excluded and reviewed is not False:raise ValueError('Unexpected optional TLS removal attestation')
 if graph.get('status')!='observed' or graph.get('errors')!=[] or any(graph.get(k)!=v for k,v in context.items()):raise ValueError('Complete current PE graph required')
 names={n for n in selected if Path(n).suffix.lower() in PE_SUFFIXES};rows=graph.get('files')
 if not isinstance(rows,list) or len(rows)!=len(names) or type(graph.get('selectedPeFiles')) is not int or graph['selectedPeFiles']!=len(names) or {r.get('path') for r in rows}!=names:raise ValueError('Complete selected PE graph differs')
 removed={Path(n).name.lower() for n in excluded}
 for row in rows:
  name=row['path']
  if hashed(row)!=hashed(selected[name]) or row.get('inputs')!=selected[name]['inputs']:raise ValueError('PE graph source bytes/origins changed')
  if name in excluded and hashed(row)!=excluded[name]:raise ValueError('Optional TLS bytes changed')
  for kind in ('normalImports','delayImports'):
   if not isinstance(row.get(kind),list):raise ValueError('Missing PE import class')
   for dependency in row[kind]:
    library=dependency.get('library')
    if not isinstance(library,str) or not library:raise ValueError('Invalid PE import library')
    if name not in excluded and library.lower() in removed:raise ValueError('Retained PE imports excluded TLS runtime: '+name+' -> '+library)
 if not set(excluded)<=set(selected):raise ValueError('Optional TLS group is not present in full selected tree')
 return {n:v for n,v in selected.items() if n not in excluded}

def review_object(binding,candidate):
 if not isinstance(binding,dict) or set(binding)!=({'schema','reviewed','candidate'} if candidate else {'schema','reviewed'}) or type(binding['schema']) is not int or binding['schema']!=1:
  raise ValueError('Invalid release-input binding schema')
 if candidate and binding['reviewed'] is not None:raise ValueError('Candidate may not claim review approval')
 review=binding.get('candidate' if candidate else 'reviewed')
 if not isinstance(review,dict):raise ValueError('Reviewed release-input binding is absent')
 if set(review)!={'licenseReviewComplete','correspondingSourceComplete','catalog','publications','runtimeOwners','owners','excludedRuntime','optionalTlsRemovalReviewed'} or any(review[k] is not (not candidate) for k in ('licenseReviewComplete','correspondingSourceComplete')):
  raise ValueError('Candidate must remain unapproved' if candidate else 'Complete explicit source/license review required')
 return review

def validate_reviewed(root,binding,selected,commit):
 return validate_materials(root,review_object(binding,False),selected,commit,True)

def validate_candidate(root,binding,selected,commit):
 """Check the proposed bytes/map with false attestations; never buildable output."""
 return validate_materials(root,review_object(binding,True),selected,commit,False)

def validate_materials(root,review,selected,commit,approved):
 if not re.fullmatch('[0-9a-f]{40}',commit or ''):raise ValueError('Exact current application source commit required')
 catalog_path=source_file(root,review['catalog']);catalog=read_json(catalog_path)
 if catalog.get('schema')!=1 or not isinstance(catalog.get('files'),list) or not isinstance(catalog.get('archives'),dict):raise ValueError('Invalid original notice catalog')
 assets={}
 if not isinstance(review['publications'],list) or not review['publications']:raise ValueError('Missing original public readback')
 for reference in review['publications']:
  for key,row in public_assets(read_json(source_file(root,reference))).items():
   if key in assets and assets[key]!=row:raise ValueError('Ambiguous source publication')
   assets[key]=row
 notices={};additional={};seen={}
 for row in catalog['files']:
  name=row['path'];register_path(name,seen)
  path=catalog_path.parent/name
  if measure(path)!=hashed(row):raise ValueError('Original packaged notice differs: '+name)
  notices[name]=hashed(row);additional['licenses/Bristlune/'+name]=path
 additional['licenses/Bristlune/catalog.json']=catalog_path
 owners=review['owners'];mapping=review['runtimeOwners']
 if not isinstance(owners,dict) or not owners or not isinstance(mapping,dict) or set(mapping)!=set(selected):raise ValueError('Exact selected runtime/owner mapping required')
 references={};reference_sources={};used=set();files=[]
 for name,value in selected.items():
  checked_path(name);actual=set()
  for origin in value['inputs']:
   if origin['tree']=='application':actual.add('application')
   elif origin['tree']=='locked':actual.update(origin['owners'])
   else:raise ValueError('Foreign runtime input tree')
  decision=mapping[name]
  if not isinstance(decision,list) or len(decision)!=len(set(decision)) or set(decision)!=actual:raise ValueError('Reviewed runtime owners differ: '+name)
  licenses=[];sources=[]
  for owner in decision:
   used.add(owner);rule=owners.get(owner)
   if not isinstance(rule,dict) or set(rule)!={'license','sources','notices'} or not isinstance(rule['license'],str) or not rule['license'].strip():raise ValueError('Missing reviewed owner license')
   if not isinstance(rule['notices'],list) or not rule['notices'] or any(n not in notices for n in rule['notices']):raise ValueError('Missing applicable original notices')
   if not isinstance(rule['sources'],list) or not rule['sources']:raise ValueError('Missing corresponding source')
   for key in rule['sources']:
    if key=='current-application':
     if owner!='application':raise ValueError('Dependency cannot use application source as its corresponding source')
     url='https://github.com/hashfunction/brushquay/archive/'+commit+'.tar.gz'
    elif key==LIBVPX_REFERENCE['key']:
     reference_sources[owner]=vpx_reference(owner,rule,selected,notices)
     url=LIBVPX_REFERENCE['url']+' (upstream version reference; producer revision unidentified)'
    else:
     if key not in assets or key not in catalog['archives'] or hashed(catalog['archives'][key])!=hashed(assets[key]):raise ValueError('Source is not exact catalog/public original')
     url=assets[key]['url']
    sources.append(url)
   licenses.append('('+rule['license']+')');references[owner]=rule
  files.append(dict(path=name,**hashed(value),license=' AND '.join(licenses),source=' '.join(sorted(set(sources)))))
 if used!=set(owners):raise ValueError('Unused or missing reviewed owner decisions')
 # Catalog/index are original/derived source metadata with each original notice retaining its own terms.
 index=canonical({'schema':1,'applicationSource':'https://github.com/hashfunction/brushquay/archive/'+commit+'.tar.gz','owners':references,'publicSources':assets,'referenceSources':reference_sources,'catalog':review['catalog']})
 extra_bytes={n:Path(p).read_bytes() for n,p in additional.items()}
 extra_bytes['licenses/Bristlune/source-references.json']=index
 for name,data in extra_bytes.items():files.append(dict(path=name,**digest(data),license='LicenseRef-Original-Notices',source='See licenses/Bristlune/source-references.json'))
 audit=dict(schema=1,sourceCommit=commit,licenseReviewComplete=review['licenseReviewComplete'],correspondingSourceComplete=review['correspondingSourceComplete'],files=files)
 if approved:validate_audit(audit)
 return {'audit':audit,'additionalFiles':extra_bytes,'catalog':review['catalog'],'publications':review['publications']}
