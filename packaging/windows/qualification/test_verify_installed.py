# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import tempfile
import unittest
from prepare import IDENTITY,manifest_bytes
from runtime_stage import measure_tree
from verify_installed import verify

class InstalledReadbackTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve()
  (self.root/'AppxManifest.xml').write_bytes(manifest_bytes(IDENTITY));(self.root/'Bristlune').mkdir();(self.root/'Bristlune/app.dll').write_bytes(b'compiled input')
  self.record={'identity':IDENTITY,'payload':measure_tree(self.root)}
 def test_exact_installed_bytes_allow_only_os_footprint_metadata(self):
  (self.root/'AppxSignature.p7x').write_bytes(b'signature')
  self.assertEqual(verify(self.root,self.record)['verifiedPayloadFiles'],2)
 def test_release_mode_is_independent_of_supplied_manifest_and_record(self):
  self.record.update(releaseCandidate=True,mode='store')
  with self.assertRaises(ValueError):verify(self.root,self.record)
 def test_changed_missing_and_extra_runtime_files_are_refused(self):
  path=self.root/'Bristlune/app.dll';path.write_bytes(b'foreign')
  with self.assertRaises(ValueError):verify(self.root,self.record)
  path.unlink()
  with self.assertRaises(ValueError):verify(self.root,self.record)
  path.write_bytes(b'compiled input');(self.root/'foreign.dll').write_bytes(b'keep')
  with self.assertRaises(ValueError):verify(self.root,self.record)
  self.assertEqual((self.root/'foreign.dll').read_bytes(),b'keep')

if __name__=='__main__':unittest.main()
