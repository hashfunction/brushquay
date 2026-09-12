# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
import tempfile
import unittest
from pathlib import Path
from ownership import begin,seal,clean,MARKER

class OwnershipTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve()/'owned';self.proof={'ownedProcessesStopped':True}
 def test_owned_fixture_can_be_sealed_and_removed_after_stop(self):
  lease=begin(self.root,'fixture');(self.root/'artwork.kra').write_bytes(b'real output')
  frozen=seal(lease,self.proof);clean(frozen,self.proof);self.assertFalse(self.root.exists())
 def test_foreign_root_is_never_replaced(self):
  self.root.mkdir();(self.root/'original').write_bytes(b'keep')
  with self.assertRaises(ValueError):begin(self.root,'fixture')
  self.assertEqual((self.root/'original').read_bytes(),b'keep')
 def test_marker_and_protected_bytes_cannot_be_changed(self):
  for name in (MARKER,'protected.txt'):
   with self.subTest(name=name),tempfile.TemporaryDirectory() as temp:
    root=Path(temp).resolve()/'owned';lease=begin(root,'fixture');(root/name).write_bytes(b'changed')
    with self.assertRaises(ValueError):seal(lease,self.proof)
    self.assertTrue(root.exists())
 def test_unproved_stop_cannot_seal_or_clean(self):
  lease=begin(self.root,'fixture')
  with self.assertRaises(ValueError):seal(lease,{'ownedProcessesStopped':False})
  frozen=seal(lease,self.proof)
  with self.assertRaises(ValueError):clean(frozen,{})
  self.assertTrue((self.root/MARKER).exists())
 def test_changed_or_unexpected_file_prevents_any_removal(self):
  lease=begin(self.root,'fixture');frozen=seal(lease,self.proof)
  (self.root/'artwork.png').write_bytes(b'late output')
  with self.assertRaises(ValueError):clean(frozen,self.proof)
  (self.root/'foreign').write_bytes(b'keep')
  with self.assertRaises(ValueError):seal(lease,self.proof)
  self.assertEqual((self.root/'foreign').read_bytes(),b'keep')
  self.assertTrue((self.root/'protected.txt').exists())
 def test_empty_foreign_directory_and_link_block_cleanup(self):
  lease=begin(self.root,'fixture');(self.root/'unexpected').mkdir()
  with self.assertRaises(ValueError):seal(lease,self.proof)
  (self.root/'unexpected').rmdir();foreign=Path(self.temp.name).resolve()/'foreign';foreign.write_bytes(b'keep');(self.root/'artwork.png').symlink_to(foreign)
  with self.assertRaises(ValueError):seal(lease,self.proof)
  self.assertEqual(foreign.read_bytes(),b'keep')
 def test_profile_directory_added_after_stop_snapshot_is_preserved(self):
  lease=begin(self.root,'profile');frozen=seal(lease,self.proof);(self.root/'LocalState').mkdir()
  with self.assertRaises(ValueError):clean(frozen,self.proof)
  self.assertTrue((self.root/MARKER).exists())
 def test_package_profile_only_allows_owned_state_roots(self):
  lease=begin(self.root,'profile');(self.root/'LocalCache').mkdir();(self.root/'LocalCache'/'app').write_bytes(b'state')
  frozen=seal(lease,self.proof);(self.root/'foreign').write_bytes(b'keep')
  with self.assertRaises(ValueError):clean(frozen,self.proof)
  self.assertEqual((self.root/'foreign').read_bytes(),b'keep')

if __name__=='__main__':unittest.main()
