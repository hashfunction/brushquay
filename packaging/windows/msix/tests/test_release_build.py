import importlib.util,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
class ReleaseBuildTests(unittest.TestCase):
 def test_package_contract_rejects_mode_context_payload_confusion(self):
  self.assertIsNotNone(importlib.util.find_spec('release_build'),'release preparation interface is missing')
  import release_build as r
  from manifest_identity import identity_for_mode
  base={'mode':'store','identity':identity_for_mode('store'),'qualificationOnly':False,'releaseCandidate':True,'signed':False,'licenseReviewComplete':True,'correspondingSourceComplete':True,'publicBinaryDistributionAuthorizedByThisReceipt':False,'applicationId':'BrushQuay','executable':'Bristlune/bin/bristlune.exe','status':'audited_package_verified_not_installed','sourceCommit':'a'*40,'sourceTree':'b'*40,'workflowRunId':'1','workflowRunAttempt':'1'}
  r.assert_release_record(base,'store')
  for key,value in [('mode','qualification'),('qualificationOnly',True),('signed',True),('releaseCandidate',1),('workflowRunAttempt',1),('applicationId','Bristlune'),('publicBinaryDistributionAuthorizedByThisReceipt',True)]:
   with self.subTest(key=key),self.assertRaises(ValueError):r.assert_release_record(dict(base,**{key:value}),'store')
 def test_current_workflow_environment_is_independent_of_supplied_context(self):
  import release_build as r
  self.assertTrue(callable(getattr(r,'assert_run_environment',None)),'current native workflow binding is missing')
  good={'GITHUB_ACTIONS':'true','RUNNER_OS':'Windows','GITHUB_REPOSITORY':'hashfunction/brushquay','GITHUB_SHA':'a'*40,'GITHUB_RUN_ID':'42','GITHUB_RUN_ATTEMPT':'1'}
  r.assert_run_environment('a'*40,'42','1',good)
  for key in good:
   bad=dict(good);bad[key]='foreign'
   with self.subTest(key=key),self.assertRaises(ValueError):r.assert_run_environment('a'*40,'42','1',bad)
 def test_fixed_identity_xml_matches_independent_parser(self):
  self.assertIsNotNone(importlib.util.find_spec('release_build'),'release preparation interface is missing')
  import release_build as r
  from build_msix import load_identity
  from manifest_identity import identity_for_mode
  with tempfile.TemporaryDirectory() as t:
   path=Path(t)/'identity.props'
   for mode in ('store','qualification'):
    path.write_bytes(r.identity_xml(mode));self.assertEqual(load_identity(path),identity_for_mode(mode))
if __name__=='__main__':unittest.main()
