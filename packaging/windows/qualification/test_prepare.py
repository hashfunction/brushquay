# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from prepare import native_evidence,EXPECTED_TESTS,pack,IDENTITY,prepare,canonical,sha
from runtime_stage import measure,measure_tree

class NativeEvidenceTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve()
  def git(*args):return subprocess.check_output(['git','-C',str(self.root),*args],text=True,stderr=subprocess.STDOUT).strip()
  self.git=git;git('init','-q');git('config','user.name','Fixture');git('config','user.email','fixture@example.invalid')
  (self.root/'.gitignore').write_text('.brushquay/\n');(self.root/'source').write_text('original');git('add','.');git('commit','-qm','fixture')
  self.head=git('rev-parse','HEAD');self.path=self.root/'.brushquay/evidence/actual/native-build.json';self.path.parent.mkdir(parents=True)
  self.record={'sourceHead':self.head,'sourceTree':git('show','-s','--format=%T','HEAD'),'workflowRunId':'42','workflowRunAttempt':'1','status':'compiled_and_installed_not_packaged','inputStageUnchanged':True,'productTests':EXPECTED_TESTS}
  self.write();self.junit()
 def write(self):self.path.write_text(json.dumps(self.record))
 def junit(self,extra=''):
  self.path.with_name('product-tests.xml').write_text('<testsuite>'+''.join('<testcase name="'+name+'" classname="'+name+'" status="run">'+(extra if i==0 else '')+'</testcase>' for i,name in enumerate(EXPECTED_TESTS))+'</testsuite>')
  self.record['productTestReport']=measure(self.path.with_name('product-tests.xml'));self.write()
 def read(self):return native_evidence(self.root,self.head,'42','1')
 def test_exact_current_native_commit_run_tree_and_six_suites(self):self.assertEqual(self.read()[1],self.record)
 def test_dirty_or_wrong_commit_refused(self):
  (self.root/'source').write_text('changed')
  with self.assertRaises(ValueError):self.read()
  self.git('checkout','--','source')
  with self.assertRaises(ValueError):native_evidence(self.root,'a'*40,'42','1')
 def test_dirty_package_boundary_retains_original_paths_and_bytes(self):
  path=self.root/'source';path.write_bytes(b'changed\r\n');output=self.path.parent/'source-before-package.json'
  with self.assertRaisesRegex(ValueError,'source'):
   native_evidence(self.root,self.head,'42','1',output)
  observed=json.loads(output.read_bytes());self.assertFalse(observed['clean']);self.assertEqual(observed['phase'],'before-package')
  row=observed['paths'][0];self.assertEqual(row['path'],'source');self.assertEqual(row['working']['crlf'],1)
  self.assertNotEqual(row['committed']['sha256'],row['working']['sha256']);self.assertEqual(path.read_bytes(),b'changed\r\n')
 def test_other_run_attempt_or_tree_cannot_qualify(self):
  for key,value in [('workflowRunId','43'),('workflowRunAttempt','2'),('sourceTree','a'*40),('inputStageUnchanged',False)]:
   with self.subTest(key=key):
    original=self.record[key];self.record[key]=value;self.write()
    with self.assertRaises(ValueError):self.read()
    self.record[key]=original;self.write()
 def test_failed_error_and_skipped_product_suite_refused(self):
  for element in ('failure','error','skipped'):
   with self.subTest(element=element):
    self.junit('<'+element+'/>')
    with self.assertRaises(ValueError):self.read()
 def test_missing_or_duplicate_suite_refused(self):
  self.record['productTests']=EXPECTED_TESTS[:-1];self.write()
  with self.assertRaises(ValueError):self.read()
  self.record['productTests']=EXPECTED_TESTS;self.write();self.path.with_name('product-tests.xml').write_text('<testsuite>'+''.join('<testcase name="'+EXPECTED_TESTS[0]+'"/>' for _ in range(6))+'</testsuite>')
  self.record['productTestReport']=measure(self.path.with_name('product-tests.xml'));self.write()
  with self.assertRaises(ValueError):self.read()
 def test_changed_report_bytes_refused(self):
  path=self.path.with_name('product-tests.xml');path.write_text(path.read_text()+'\n')
  with self.assertRaisesRegex(ValueError,'XML differs'):self.read()
 def test_ambiguous_native_receipts_refused(self):
  other=self.path.parent.with_name('other');other.mkdir();(other/'native-build.json').write_bytes(self.path.read_bytes())
  with self.assertRaises(ValueError):self.read()
 def test_incomplete_import_observation_refuses_tls_selection_before_sdk_and_preserves_inputs(self):
  install=self.root/'.brushquay/install';(install/'bin').mkdir(parents=True);(install/'plugins/platforms').mkdir(parents=True)
  for name in ('bin/bristlune.exe','bin/bristlune.dll','plugins/platforms/qwindows.dll','bin/Qt6Core.dll','bin/libc++.dll','bin/libunwind.dll','bin/libwinpthread-1.dll'):
   (install/name).write_bytes(b'original native fixture')
  locked=self.root/'.brushquay/locked';(locked/'deps/plugins/platforms').mkdir(parents=True)
  plugin=locked/'deps/plugins/platforms/qwindows.dll';plugin.write_bytes(b'original native fixture')
  staged={'deps/plugins/platforms/qwindows.dll':dict(**measure(plugin),owners=['qt'])};original=measure_tree(install)
  self.record.update(installedTree=original,lockSha256=sha(canonical({})));self.write()
  output=self.root/'.brushquay/package';evidence=self.root/'.brushquay/observations'
  with patch('prepare.sys.platform','win32'),patch('prepare.load_tools',return_value={'sdkVersion':'10.0.26100.0'}),patch('prepare.load_lock',return_value={}),patch('prepare.verify_stage',return_value={'files':staged}),patch('prepare.pack') as sdk:
   with self.assertRaisesRegex(ValueError,'^Complete current PE graph required$'):
    prepare(self.root,output,evidence,None,self.head,'42','1')
   sdk.assert_not_called()
  record=json.loads((evidence/'qualification-package.json').read_bytes());observed=json.loads((evidence/'staged-pe-imports.json').read_bytes())
  self.assertEqual(record['error'],'Complete current PE graph required');self.assertEqual(record['peImportObservation']['status'],'incomplete')
  self.assertIn('exact locked LLVM owner',observed['errors'][0]['error']);self.assertFalse(observed['releaseReady']);self.assertFalse(record['licenseReviewComplete'])
  self.assertEqual(record['peImportObservation']['file'],measure(evidence/'staged-pe-imports.json'));self.assertEqual(measure_tree(install),original)
 def test_sdk_input_mutation_cannot_be_packaged(self):
  payload=self.root/'payload';payload.mkdir();(payload/'original').write_bytes(b'keep');expected=measure_tree(payload)
  output=self.root/'output';output.mkdir();tools={'makepri':{'path':'makepri'},'makeappx':{'path':'makeappx'}}
  def mutate(*args,**kwargs):(payload/'resources.pri').write_bytes(b'pri');(payload/'original').write_bytes(b'changed')
  with patch('prepare.confirm_tools'),patch('prepare.subprocess.run',side_effect=mutate),patch('prepare.verify_msix') as verify:
   with self.assertRaisesRegex(ValueError,'payload changed'):pack(payload,expected,tools,None,output)
   verify.assert_not_called()

if __name__=='__main__':unittest.main()
