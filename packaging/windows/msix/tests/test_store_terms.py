import copy,json,shutil,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import check_release_candidate as api

class StoreTermsTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve()
  source=Path(__file__).resolve().parents[4];self.data='packaging/windows/msix/release-data/'
  self.basis=json.loads((source/self.data/'store-license-basis.json').read_text())
  self.original=json.loads((source/'distribution/native-source/original-notices/catalog.json').read_text())
  combined=json.loads((source/'distribution/native-source/original-notices/release-catalog.json').read_text())
  needed=set(self.basis['originalNotices'])|{self.basis['packagedNotice']}
  self.catalog=dict(combined,files=[r for r in combined['files'] if r['path'] in needed])
  paths=[self.basis['licenseText']['path']]+['distribution/native-source/original-notices/'+n for n in needed]
  for name in paths:
   target=self.root/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source/name,target)
  self.selected=copy.deepcopy(self.basis['standaloneMicrosoftFiles'])
  self.additional={'licenses/Bristlune/'+self.basis['packagedNotice']:(self.root/self.basis['licenseText']['path']).read_bytes()}
 def check(self):return api.validate_store_terms(self.root,self.basis,self.selected,self.original,self.catalog,self.additional)
 def test_identical_packaged_terms_bind_original_grants_and_selected_dlls(self):
  result=self.check()
  self.assertEqual(result['standaloneMicrosoftFiles'],7)
  self.assertEqual(result['originalMicrosoftNotices'],10)
  self.assertEqual(result['licenseText'],self.basis['licenseText'])
 def test_changed_text_packaged_bytes_runtime_and_original_notice_are_refused(self):
  for mutation in ('source-text','packaged-text','packaged-output','missing-dll','extra-dll','changed-dll','missing-notice','changed-notice','rewritten-original'):
   with self.subTest(mutation=mutation):
    # Each fresh instance exercises the actual validator and file bytes.
    other=StoreTermsTests();other.setUp()
    try:
     if mutation=='source-text':(other.root/other.basis['licenseText']['path']).write_bytes(b'changed terms')
     if mutation=='packaged-text':(other.root/'distribution/native-source/original-notices'/other.basis['packagedNotice']).write_bytes(b'changed terms')
     if mutation=='packaged-output':other.additional['licenses/Bristlune/'+other.basis['packagedNotice']]=b'changed output'
     if mutation=='missing-dll':other.selected.pop('bin/dbghelp.dll')
     if mutation=='extra-dll':other.selected['extra/dbghelp.dll']=other.selected['bin/dbghelp.dll']
     if mutation=='changed-dll':other.selected['bin/dbghelp.dll']['sha256']='f'*64
     if mutation=='missing-notice':other.basis['originalNotices'].pop(next(iter(other.basis['originalNotices'])))
     if mutation=='changed-notice':(other.root/'distribution/native-source/original-notices'/next(iter(other.basis['originalNotices']))).write_bytes(b'changed original')
     if mutation=='rewritten-original':
      next(r for r in other.original['files'] if r['path'] in other.basis['originalNotices'])['sha256']='e'*64
     with other.assertRaises(ValueError):other.check()
    finally:other.doCleanups()
if __name__=='__main__':unittest.main()
