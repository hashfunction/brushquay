"""Source-owned workflow release switch and exact public artifact boundary."""
from pathlib import Path
import subprocess,unittest
class WorkflowTests(unittest.TestCase):
 def test_public_upload_is_success_only_exact_two_files_and_explicit_switch(self):
  root=Path(__file__).resolve().parents[4]
  text=(root/'.github/workflows/windows.yml').read_text()
  block=text.split('      - name: Upload independently qualified unsigned Store submission\n',1)[1].split('      - name:',1)[0]
  self.assertIn("if: success() && github.event_name == 'workflow_dispatch' && inputs.release == true",block)
  paths=block.split('          path: |\n',1)[1].split('          include-hidden-files:',1)[0]
  self.assertEqual([v.strip() for v in paths.splitlines()],['.brushquay/store-output/Bristlune_1.0.1.0_x64.msix','.brushquay/store-output/store-export.json'])
  self.assertIn('default: false',text)
  self.assertIn("if: github.event_name != 'workflow_dispatch' || inputs.release != true",text)
  self.assertLess(text.index('Refuse unreviewed release inputs'),text.index('Compile and test the native'))
if __name__=='__main__':unittest.main()
