# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
"""Create a capture-only observer; original native helper methods stay byte-identical."""
import argparse,hashlib,json
from pathlib import Path
WORKFLOW_SHA256='ccd7b01f140c4d1bacfa8cbb3dcf597557aedc45277db4117746811ab5888dcb'
def compose(original,workflow):
 start=b'        static void Workflow()';end=b'        public static int Main'
 if original.count(start)!=1 or original.count(end)!=1 or original.count(b'"installed consumer qualification"')!=1:
  raise ValueError('Original observer structure differs')
 first=original.index(start);last=original.index(end,first)
 if hashlib.sha256(original[first:last].replace(b'\r\n',b'\n')).hexdigest()!=WORKFLOW_SHA256:
  raise ValueError('Qualified original consumer workflow differs from reviewed capture boundary')
 if not workflow.startswith(start+b'\n') or workflow.count(start)!=1 or end in workflow:
  raise ValueError('Capture workflow replacement structure differs')
 return (original[:first]+workflow+b'\n'+original[last:]).replace(b'"installed consumer qualification"',b'"marketing capture only"')
def main():
 p=argparse.ArgumentParser();p.add_argument('--qualified-source',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
 original=a.qualified_source/'packaging/windows/qualification/GuiProbe.cs';body=Path(__file__).with_name('Workflow.capture.cs.txt')
 result=compose(original.read_bytes(),body.read_bytes())
 with a.output.open('xb') as f:f.write(result)
 print(json.dumps({'originalSha256':hashlib.sha256(original.read_bytes()).hexdigest(),'captureWorkflowSha256':hashlib.sha256(body.read_bytes()).hexdigest(),'generatedSha256':hashlib.sha256(result).hexdigest(),'changes':['Workflow body','capture purpose literal'],'productCodeChanged':False}))
if __name__=='__main__':main()
