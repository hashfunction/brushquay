import copy,json,tempfile,unittest,zipfile,sys,struct,zlib,binascii
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import capture_checks as c,capture_files as files,prepare_capture as prepare
class CaptureBoundaryTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve()
 def test_unbound_changed_run_and_incomplete_normal_stop_refused(self):
  with self.assertRaises(ValueError):c.binding({'schema':1,'product':'Bristlune','qualified':None})
  b={'source_commit':'a'*40,'run_id':'12','run_attempt':'1','package':{'bytes':12,'sha256':'b'*64},'export_receipt':{'bytes':13,'sha256':'c'*64},'artifacts':{'store':14,'metadata':15}}
  self.assertEqual(c.binding({'schema':1,'product':'Bristlune','qualified':b}),b)
  run={'id':12,'run_attempt':1,'head_sha':'a'*40,'conclusion':'success','repository':{'full_name':c.REPOSITORY},'path':'.github/workflows/windows.yml'}
  c.validate_run(run,b)
  for key,val in [('run_attempt',2),('head_sha','f'*40),('conclusion','failure')]:
   with self.subTest(key=key),self.assertRaises(ValueError):c.validate_run(dict(run,**{key:val}),b)
  proof={'passed':True,'normalClosePassed':True,'ownedProcessesStopped':True,'normalExitCode':0,'purpose':'marketing capture only','consumerAcceptance':False}
  files.stopped(proof)
  for key,val in [('normalClosePassed',False),('ownedProcessesStopped',False),('normalExitCode',1),('forcedStop',True),('consumerAcceptance',True)]:
   with self.subTest(key=key),self.assertRaises(ValueError):files.stopped(dict(proof,**{key:val}))
 def test_actual_archive_inventory_refuses_alias_extra_and_traversal(self):
  for i,names in enumerate([['a.txt'],['a.txt','A.txt'],['../outside.txt'],['a.txt','extra.txt']]):
   archive=self.root/(str(i)+'.zip');out=self.root/('out'+str(i))
   with zipfile.ZipFile(archive,'w') as z:
    for n in names:z.writestr(n,b'original')
   if i==0:
    prepare.extract(archive,out,128,['a.txt']);self.assertEqual((out/'a.txt').read_bytes(),b'original')
   else:
    with self.assertRaises(ValueError):prepare.extract(archive,out,128,['a.txt'])
    self.assertFalse(out.exists())
 def test_actual_original_lease_rejects_changed_artwork_foreign_file_and_unproved_stop(self):
  source=Path(__file__).resolve().parents[3];root=self.root/'demo';lease=files.begin(root,source);own,_=files.helpers(source)
  original=(root/'Moonlit Garden.ora').read_bytes();(root/'Moonlit Garden.ora').write_bytes(b'changed')
  with self.assertRaises(ValueError):own.seal(lease,{'ownedProcessesStopped':True})
  (root/'Moonlit Garden.ora').write_bytes(original);(root/'foreign.txt').write_bytes(b'preserve')
  with self.assertRaises(ValueError):own.seal(lease,{'ownedProcessesStopped':True})
  self.assertEqual((root/'foreign.txt').read_bytes(),b'preserve');(root/'foreign.txt').unlink()
  with self.assertRaises(ValueError):own.seal(lease,{'ownedProcessesStopped':False})
  sealed=own.seal(lease,{'ownedProcessesStopped':True});own.clean(sealed,{'ownedProcessesStopped':True});self.assertFalse(root.exists())
 def test_independent_artwork_recipe_and_raw_capture_readback(self):
  # File-oracle fixture only. These bytes are never published as UI evidence.
  source=Path(__file__).resolve().parents[3];lease=files.begin(self.root/'demo',source);own,_=files.helpers(source)
  profile=own.begin(self.root/'profile','profile');gui=self.root/'gui';gui.mkdir()
  fixture=Path(__file__).parent/'fixtures';manifest=c.load(fixture/'artwork.json');png=(fixture/'artwork-preview.png').read_bytes()
  root=Path(lease['root']);(root/'Moonlit Garden.png').write_bytes(png)
  xml='<DOC><IMAGE width="512" height="384"><layers>'+''.join('<layer name="'+n+'"/>' for n in manifest['layerNames'])+'</layers></IMAGE></DOC>'
  for name in ('Moonlit Garden.kra','Moonlit Garden Reopened.kra'):
   with zipfile.ZipFile(root/name,'w') as z:
    z.writestr('mimetype',b'application/x-krita');z.writestr('maindoc.xml',xml);z.writestr('mergedimage.png',png)
  store=Path(profile['root'])/'LocalState/brushquay/export-presets-v1.json';store.parent.mkdir(parents=True)
  preset={'schema':1,'name':'Moonlit Garden - PNG','mimeType':'image/png','extension':'png','properties':{'alpha':{'type':'bool','value':True}}}
  store.write_text(json.dumps({'schema':1,'presets':[preset]}))
  proof={'passed':True,'normalClosePassed':True,'ownedProcessesStopped':True,'normalExitCode':0,'purpose':'marketing capture only','consumerAcceptance':False,'activatedPid':72,'processStartUtc':'2026-09-12T00:00:00Z','executableSha256':'a'*64}
  def chunk(kind,body):return struct.pack('>I',len(body))+kind+body+struct.pack('>I',binascii.crc32(kind+body)&0xffffffff)
  raw=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1366,768,8,2,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+b'\xff'*(1366*3))*768))+chunk(b'IEND',b'')
  for scene in files.SCENES:
   path=gui/(scene+'.png');path.write_bytes(raw)
   meta={'unedited':True,'purpose':'marketing capture only','processId':72,'processStartUtc':proof['processStartUtc'],'executableSha256':'a'*64,'sha256':c.digest(path)['sha256'],'bounds':[0,0,1366,768]}
   (gui/(scene+'-capture.json')).write_text(json.dumps(meta))
  result=files.verify(lease,profile,proof,gui,source)
  self.assertEqual(set(result['captures']),{n+'.png' for n in files.SCENES});self.assertEqual(sorted(result['layerNames']),sorted(manifest['layerNames']))
  with self.assertRaisesRegex(ValueError,'Normal owned capture stop'):files.verify(lease,profile,dict(proof,normalClosePassed=False),gui,source)
  store.write_text(json.dumps({'schema':1,'presets':[dict(preset,name='wrong')]}))
  with self.assertRaisesRegex(ValueError,'Actual named PNG preset'):files.verify(lease,profile,proof,gui,source)
  store.write_text(json.dumps({'schema':1,'presets':[preset]}))
  path=gui/(files.SCENES[0]+'.png');path.write_bytes(raw+b'changed')
  with self.assertRaisesRegex(ValueError,'Raw marketing capture/process'):files.verify(lease,profile,proof,gui,source)
  path.write_bytes(raw)
  (root/'Moonlit Garden.png').write_bytes(b'changed exported image')
  with self.assertRaisesRegex(ValueError,'Expected a bounded PNG'):files.verify(lease,profile,proof,gui,source)
 def test_only_source_defined_empty_transaction_directory_is_removed_after_stop(self):
  source=Path(__file__).resolve().parents[3]
  for mutation in ('none','live','content','foreign-name','multiple','link','marker','protected'):
   with self.subTest(mutation=mutation):
    parent=self.root/mutation;parent.mkdir();lease=files.begin(parent/'demo',source);root=Path(lease['root'])
    for name in files.NAMES-{'Moonlit Garden.ora'}:(root/name).write_bytes(b'controlled output file')
    transaction=root/'.brushquay-export-Ab12cD';transaction.mkdir();gui=parent/'gui';gui.mkdir()
    proof={'passed':True,'normalClosePassed':True,'ownedProcessesStopped':True,'normalExitCode':0,'purpose':'marketing capture only','consumerAcceptance':False}
    if mutation=='live':proof['normalClosePassed']=False
    elif mutation=='content':(transaction/'unexpected').write_bytes(b'keep')
    elif mutation=='foreign-name':transaction.rename(root/'other')
    elif mutation=='multiple':(root/'.brushquay-export-Xy34zA').mkdir()
    elif mutation=='link':
     transaction.rmdir();outside=parent/'outside';outside.mkdir()
     try:transaction.symlink_to(outside,target_is_directory=True)
     except OSError:continue # Native Windows runner may not permit test symlinks.
    elif mutation=='marker':(root/'.bristlune-qualification-owner.json').write_bytes(b'changed marker')
    elif mutation=='protected':(root/'protected.txt').write_bytes(b'changed original')
    if mutation=='none':
     result=files.remove_empty_export(lease,proof,gui,source)
     self.assertTrue(result['removed']);self.assertFalse(transaction.exists());self.assertTrue((gui/'transaction-directory-observation.json').is_file())
    else:
     with self.assertRaises((ValueError,OSError)):files.remove_empty_export(lease,proof,gui,source)
     self.assertFalse((gui/'transaction-directory-observation.json').exists())
if __name__=='__main__':unittest.main()
