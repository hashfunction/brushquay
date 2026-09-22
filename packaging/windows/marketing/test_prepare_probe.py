import importlib.util,tempfile,unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
class ProbeTests(unittest.TestCase):
 def test_only_workflow_and_purpose_change_in_actual_qualified_helper(self):
  import prepare_probe as p
  root=Path(__file__).resolve().parents[3];original=(root/'packaging/windows/qualification/GuiProbe.cs').read_bytes()
  body=(Path(__file__).parent/'Workflow.capture.cs.txt').read_bytes()
  result=p.compose(original,body)
  first=original.index(b'        static void Workflow()');last=original.index(b'        public static int Main',first)
  prefix=original[:first].replace(b'"installed consumer qualification"',b'"marketing capture only"')
  self.assertEqual(result[:len(prefix)],prefix)
  self.assertEqual(result[len(prefix):len(prefix)+len(body)+1],body+b'\n')
  self.assertEqual(result[len(prefix)+len(body)+1:],original[last:])
  for bad in (original.replace(b'        static void Workflow()',b'        static void OtherWorkflow()'),original[:first]+original[first:last].replace(b'512',b'513')+original[last:]):
   with self.assertRaises(ValueError):p.compose(bad,body)
  windows=original.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')
  result=p.compose(windows,body)
  first=windows.index(b'        static void Workflow()');last=windows.index(b'        public static int Main',first)
  self.assertEqual(result,windows[:first].replace(b'"installed consumer qualification"',b'"marketing capture only"')+body+b'\n'+windows[last:])
if __name__=='__main__':unittest.main()
