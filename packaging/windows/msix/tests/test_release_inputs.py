import copy,hashlib,importlib.util,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

class ReleaseInputTests(unittest.TestCase):
 def setUp(self):
  spec=importlib.util.find_spec('release_inputs')
  self.assertIsNotNone(spec,'reviewed release input validator is missing')
  import release_inputs
  self.api=release_inputs
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve()
  def write(path,value):
   p=self.root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(value if isinstance(value,bytes) else json.dumps(value).encode());return dict(path=path,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
  self.write=write
  notice=write('notices/license.txt',b'original license')
  self.catalog={'schema':1,'archives':{'a'*64:{'bytes':10,'sha256':'a'*64}},'files':[dict(notice,path='license.txt')]}
  cat=write('notices/catalog.json',self.catalog)
  pub={'schemaVersion':1,'repository':'hashfunction/brushquay','anonymous':True,'authorizationHeadersSent':False,'cookiesUsed':False,'tlsCertificateValidation':True,'tlsHostnameValidation':True,'allAssetsVerified':True,'failedAssetCount':0,'remainingAssetCount':0,'verifiedAssetCount':1,'expectedAssetCount':1,'verifiedAssetBytes':10,'expectedAssetBytes':10,'assets':[{'url':'https://github.com/hashfunction/brushquay/releases/download/source/a.tar','name':'a.tar','status':'verified','httpStatus':200,'tlsCertificateVerified':True,'error':None,'expected':{'bytes':10,'sha256':'a'*64},'bytes':10,'sha256':'a'*64}]}
  self.pub=pub;public=write('public.json',pub)
  self.selected={'bin/bristlune.exe':{'bytes':3,'sha256':'b'*64,'inputs':[{'tree':'application','path':'bin/bristlune.exe'}]}}
  self.binding={'schema':1,'reviewed':{'licenseReviewComplete':True,'correspondingSourceComplete':True,'catalog':cat,'publications':[public],'runtimeOwners':{'bin/bristlune.exe':['application']},'owners':{'application':{'license':'GPL-3.0-or-later','sources':['current-application'],'notices':['license.txt']}},'excludedRuntime':{},'optionalTlsRemovalReviewed':False}}
 def test_reviewed_inputs_and_original_notice(self):
  result=self.api.validate_reviewed(self.root,self.binding,self.selected,'c'*40)
  self.assertIn('licenses/Bristlune/license.txt',result['additionalFiles'])
  self.assertEqual(result['audit']['files'][0]['source'],'https://github.com/hashfunction/brushquay/archive/'+'c'*40+'.tar.gz')
 def test_null_and_false_review_refused(self):
  for value in ({'schema':1,'reviewed':None},{'schema':1,'reviewed':dict(self.binding['reviewed'],licenseReviewComplete=False)}):
   with self.assertRaises(ValueError):self.api.validate_reviewed(self.root,value,self.selected,'c'*40)
 def test_missing_foreign_source_owner_notice_and_extra_mapping_refused(self):
  for field,value in [('sources',['d'*64]),('notices',[])]:
   bad=copy.deepcopy(self.binding);bad['reviewed']['owners']['application'][field]=value
   with self.assertRaises(ValueError):self.api.validate_reviewed(self.root,bad,self.selected,'c'*40)
  bad=copy.deepcopy(self.binding);bad['reviewed']['runtimeOwners']['extra.dll']=['application']
  with self.assertRaises(ValueError):self.api.validate_reviewed(self.root,bad,self.selected,'c'*40)
  (self.root/'notices/license.txt').write_text('changed')
  with self.assertRaises(ValueError):self.api.validate_reviewed(self.root,self.binding,self.selected,'c'*40)
 def test_public_partial_or_fabricated_counts_refused(self):
  for key,value in [('allAssetsVerified',False),('verifiedAssetCount',2),('authorizationHeadersSent',True)]:
   bad=copy.deepcopy(self.pub);bad[key]=value;binding=copy.deepcopy(self.binding);binding['reviewed']['publications']=[self.write('bad-public.json',bad)]
   with self.assertRaises(ValueError):self.api.validate_reviewed(self.root,binding,self.selected,'c'*40)
 def test_permissive_vpx_reference_is_exact_and_never_an_archive_claim(self):
  policy=self.api.LIBVPX_REFERENCE
  source=Path(__file__).resolve().parents[4]
  for name,value in policy['notices'].items():
   data=(source/'distribution/native-source/original-notices'/name).read_bytes()
   self.assertEqual(self.api.digest(data),value)
   self.write('notices/'+name,data);self.catalog['files'].append(dict(value,path=name))
  self.binding['reviewed']['catalog']=self.write('notices/catalog.json',self.catalog)
  self.selected.update(copy.deepcopy(policy['runtime']))
  self.binding['reviewed']['runtimeOwners']['bin/libvpx-8.dll']=['ext_vpx']
  self.binding['reviewed']['owners']['ext_vpx']={'license':'BSD-3-Clause','sources':[policy['key']],'notices':list(policy['notices'])}
  result=self.api.validate_reviewed(self.root,self.binding,self.selected,'c'*40)
  index=json.loads(result['additionalFiles']['licenses/Bristlune/source-references.json'])
  self.assertIsNone(index['referenceSources']['ext_vpx']['producerRevision'])
  self.assertFalse(index['referenceSources']['ext_vpx']['exactSourceArchiveClaimed'])
  self.assertEqual(len(index['publicSources']),1)
  for mutation in ('license','source','notice','binary','extra-file'):
   binding=copy.deepcopy(self.binding);selected=copy.deepcopy(self.selected)
   if mutation=='license':binding['reviewed']['owners']['ext_vpx']['license']='GPL-3.0-or-later'
   if mutation=='source':binding['reviewed']['owners']['ext_vpx']['sources']=['upstream-reference:libvpx-1.13.2']
   if mutation=='notice':binding['reviewed']['owners']['ext_vpx']['notices'].pop()
   if mutation=='binary':selected['bin/libvpx-8.dll']['sha256']='f'*64
   if mutation=='extra-file':
    selected['bin/extra-vpx.dll']=copy.deepcopy(selected['bin/libvpx-8.dll']);binding['reviewed']['runtimeOwners']['bin/extra-vpx.dll']=['ext_vpx']
   with self.subTest(mutation=mutation),self.assertRaises(ValueError):self.api.validate_reviewed(self.root,binding,selected,'c'*40)
 def test_candidate_checks_materials_without_creating_review_attestations(self):
  proposed=copy.deepcopy(self.binding['reviewed'])
  proposed['licenseReviewComplete']=proposed['correspondingSourceComplete']=False
  candidate={'schema':1,'reviewed':None,'candidate':proposed}
  result=self.api.validate_candidate(self.root,candidate,self.selected,'c'*40)
  self.assertFalse(result['audit']['licenseReviewComplete'])
  self.assertFalse(result['audit']['correspondingSourceComplete'])
  with self.assertRaises(ValueError):self.api.validate_reviewed(self.root,candidate,self.selected,'c'*40)
  from build_msix import validate_audit
  with self.assertRaises(ValueError):validate_audit(result['audit'])
  candidate['candidate']['licenseReviewComplete']=True
  with self.assertRaises(ValueError):self.api.validate_candidate(self.root,candidate,self.selected,'c'*40)
 def test_tls_group_requires_complete_current_graph_and_no_external_edges(self):
  group=self.api.OPTIONAL_TLS
  selected=dict(self.selected,**{n:dict(v,inputs=[{'tree':'locked','path':'deps/'+n,'owners':['ext_openssl']}]) for n,v in group.items()})
  context={'sourceCommit':'c'*40,'sourceTree':'d'*40,'workflowRunId':'1','workflowRunAttempt':'1','nativeEvidence':{'bytes':2,'sha256':'e'*64},'lockSha256':'f'*64}
  rows=[dict(v,path=n,normalImports=[],delayImports=[]) for n,v in selected.items()]
  graph=dict(context,status='observed',errors=[],selectedPeFiles=len(rows),files=rows)
  result=self.api.apply_exclusions(selected,group,graph,context,True)
  self.assertEqual(result,self.selected)
  for mutation in ('edge','delay','missing','stale','unreviewed'):
   bad=copy.deepcopy(graph)
   if mutation in ('edge','delay'):bad['files'][0]['delayImports' if mutation=='delay' else 'normalImports']=[{'library':'libssl-1_1-x64.dll','symbols':[]}]
   if mutation=='missing':bad['files'].pop()
   if mutation=='stale':bad['workflowRunAttempt']='2'
   with self.assertRaises(ValueError):self.api.apply_exclusions(selected,group,bad,context,mutation!='unreviewed')
if __name__=='__main__':unittest.main()
