# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
"""Actual Git/filesystem source-state diagnostics, never a native success fixture."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

MODULE=Path(__file__).resolve().parents[1]/'source_state.py'

class SourceStateTests(unittest.TestCase):
 def setUp(self):
  self.assertTrue(MODULE.is_file(),'Required original per-phase Git observation is missing')
  spec=importlib.util.spec_from_file_location('bristlune_source_state',MODULE);self.api=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.api)
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve()
  self.git('init','-q');self.git('config','user.name','Fixture');self.git('config','user.email','fixture@example.invalid');self.git('config','core.autocrlf','false')
  (self.root/'.gitignore').write_text('.brushquay/\n');(self.root/'tracked.txt').write_bytes(b'original\nsecond\n')
  self.git('add','.');self.git('commit','-qm','fixture');self.head=self.git('rev-parse','HEAD').decode().strip()
  self.output=self.root/'.brushquay/evidence/state.json';self.output.parent.mkdir(parents=True)
 def git(self,*args):return subprocess.check_output(['git','-C',str(self.root),*args],stderr=subprocess.STDOUT)
 def observe(self):return self.api.require_clean_source(self.root,self.head,self.output,'after-configure')
 def test_real_clean_checkout_retains_exact_head_tree_and_empty_status(self):
  got=self.observe();self.assertEqual(got['head'],self.head);self.assertTrue(got['clean']);self.assertEqual(got['statusPorcelainV1Base64'],'')
  self.assertEqual(json.loads(self.output.read_bytes()),got);self.assertEqual(self.git('status','--porcelain'),b'')
 def test_original_content_and_crlf_bytes_are_observed_without_reset(self):
  changed=b'original\r\nsecond\r\n';(self.root/'tracked.txt').write_bytes(changed)
  with self.assertRaisesRegex(ValueError,'tracked.txt'):self.observe()
  got=json.loads(self.output.read_bytes());row=got['paths'][0]
  self.assertFalse(got['clean']);self.assertEqual(row['committed']['lf'],2);self.assertEqual(row['committed']['crlf'],0)
  self.assertEqual(row['working']['crlf'],2);self.assertNotEqual(row['working']['sha256'],row['committed']['sha256'])
  self.assertEqual((self.root/'tracked.txt').read_bytes(),changed);self.assertTrue(got['diffNumstatBase64']);self.assertTrue(got['indexEolBase64'])
 def test_untracked_generated_and_deleted_source_are_distinguished(self):
  (self.root/'generated file.txt').write_bytes(b'generated');(self.root/'tracked.txt').unlink()
  with self.assertRaises(ValueError):self.observe()
  rows={r['path']:r for r in json.loads(self.output.read_bytes())['paths']}
  self.assertIsNone(rows['generated file.txt']['committed']);self.assertEqual(rows['generated file.txt']['working']['bytes'],9)
  self.assertIsNone(rows['tracked.txt']['working']);self.assertIsNotNone(rows['tracked.txt']['committed'])
 def test_wrong_commit_and_existing_evidence_refuse(self):
  with self.assertRaisesRegex(ValueError,'commit'):self.api.require_clean_source(self.root,'a'*40,self.output,'before-package')
  original=self.output.read_bytes()
  with self.assertRaises(FileExistsError):self.observe()
  self.assertEqual(self.output.read_bytes(),original)
 def test_returned_symlink_never_reads_its_foreign_target(self):
  target=self.root.parent/(self.root.name+'-foreign');target.write_bytes(b'foreign protected');self.addCleanup(target.unlink)
  (self.root/'alias').symlink_to(target)
  with self.assertRaises(ValueError):self.observe()
  row=next(r for r in json.loads(self.output.read_bytes())['paths'] if r['path']=='alias')
  self.assertEqual(row['working']['kind'],'link');self.assertNotIn('sha256',row['working']);self.assertEqual(target.read_bytes(),b'foreign protected')
 def test_index_mode_and_rename_metadata_preserve_original_blob_identity(self):
  self.git('update-index','--chmod=+x','tracked.txt')
  with self.assertRaises(ValueError):self.observe()
  row=json.loads(self.output.read_bytes())['paths'][0];self.assertEqual(row['working']['sha256'],row['committed']['sha256'])
  self.assertEqual(row['committed']['mode'],'100644');self.output.unlink()
  self.git('mv','tracked.txt','new name.txt')
  with self.assertRaises(ValueError):self.observe()
  got=json.loads(self.output.read_bytes());self.assertEqual(got['statusEntries'][0]['originalPath'],'tracked.txt')
  rows={r['path']:r for r in got['paths']};self.assertEqual(rows['new name.txt']['working']['sha256'],rows['tracked.txt']['committed']['sha256'])

if __name__=='__main__':unittest.main()
