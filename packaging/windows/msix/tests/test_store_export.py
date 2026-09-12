import copy,importlib.util,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
class ExportTests(unittest.TestCase):
 def setUp(self):
  self.assertIsNotNone(importlib.util.find_spec('store_export'),'independent original lifecycle verifier is missing')
  import store_export
  self.api=store_export
 def test_complete_typed_original_pixel_oracle_and_mutations(self):
  good={'dimensions':[512,384],'changed_pixels':1200,'export_matches_saved_artwork':True,'reopened_pixels_match':True,'protected_files_unchanged':True,'pixel_sha256':'a'*64,'files':{n:{'bytes':12,'sha256':str(i)*64} for i,n in enumerate(('blank.kra','artwork.kra','artwork.png','reopened.kra'),1)}}
  self.api.validate_artwork(good)
  for key,value in [('dimensions',[384,512]),('changed_pixels',True),('changed_pixels',49),('changed_pixels',512*384//2),('reopened_pixels_match',1),('export_matches_saved_artwork',False),('pixel_sha256',''),('files',{})]:
   with self.subTest(key=key),self.assertRaises(ValueError):self.api.validate_artwork(dict(good,**{key:value}))
 def test_lifecycle_flags_cannot_accept_partial_forced_or_failed_cleanup(self):
  good={'passed':True,'primaryError':None,'cleanupErrors':[],'uninstalled':True,'fixtureRemoved':True,'profileRemoved':True,'certificateRemoved':True,'publicCertificateRemoved':True,'signedCopyRemoved':True}
  self.api.validate_completion(good)
  for key,value in [('passed',1),('primaryError','failed'),('cleanupErrors',['failed']),('uninstalled',False),('profileRemoved',None),('certificateRemoved',False),('signedCopyRemoved',False)]:
   with self.subTest(key=key),self.assertRaises(ValueError):self.api.validate_completion(dict(good,**{key:value}))
 def test_original_snapshot_missing_stale_and_extra_file_refused(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t).resolve();(root/'gui').mkdir();path=root/'gui/observed.json';path.write_text('{"original":true}')
   from runtime_stage import measure
   original={'gui/observed.json':measure(path)}
   self.api.original_snapshots(root,original)
   path.write_text('{"original":false}')
   with self.assertRaises(ValueError):self.api.original_snapshots(root,original)
   path.unlink()
   with self.assertRaises((ValueError,OSError)):self.api.original_snapshots(root,original)
 def test_unsigned_output_allowlist_rejects_signing_inputs(self):
  for member in ('AppxSignature.p7x','private.pfx','private.p12','ephemeral-public.cer','Bristlune/private.key'):
   with self.subTest(member=member),self.assertRaises(ValueError):self.api.require_unsigned_names({'AppxManifest.xml':{},member:{}})
if __name__=='__main__':unittest.main()
