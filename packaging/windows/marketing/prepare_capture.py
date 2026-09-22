# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
"""Fetch exact final artifacts only; no application build or source mutation."""
import argparse,json,os,shutil,stat,subprocess,zipfile
from pathlib import Path
import capture_checks as c
NAMES={'store':'Bristlune-Store-1.0.1.0-x64','metadata':'Bristlune-Windows-foundation-qualification'}
def gh(endpoint):
 r=subprocess.run(['gh','api',endpoint],check=True,capture_output=True,timeout=30);c.require(len(r.stdout)<=1024*1024,'GitHub metadata exceeds bound');return json.loads(r.stdout)
def extract(archive,output,maximum,exact=None):
 c.no_links(output);c.require(not os.path.lexists(output),'Existing artifact destination preserved')
 with zipfile.ZipFile(archive) as z:
  items=z.infolist();names=[c.relative(i.filename) for i in items]
  c.require(len(names)<=1500 and len(set(n.casefold() for n in names))==len(names) and sum(i.file_size for i in items)<=maximum and all(not i.is_dir() and not i.flag_bits&1 and not stat.S_ISLNK(i.external_attr>>16) for i in items),'Unsafe or oversized artifact inventory')
  if exact is not None:c.require(set(names)==set(exact),'Unexpected Store artifact member')
  output.mkdir()
  for i in items:
   target=output/i.filename;target.parent.mkdir(parents=True,exist_ok=True)
   with z.open(i) as src,target.open('xb') as dst:shutil.copyfileobj(src,dst,1048576)
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--qualified-source',required=True,type=Path);a=p.parse_args();b=c.binding()
 c.require(os.name=='nt' and os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('GITHUB_REPOSITORY')==c.REPOSITORY,'Only isolated native Windows capture is supported')
 c.checkout(c.ROOT,os.environ.get('GITHUB_SHA'));c.checkout(a.qualified_source,b['source_commit']);c.no_links(a.output);a.output.mkdir()
 run=gh(f"repos/{c.REPOSITORY}/actions/runs/{b['run_id']}");c.validate_run(run,b);artifacts={}
 for key in ('store','metadata'):
  number=b['artifacts'][key];endpoint=f'repos/{c.REPOSITORY}/actions/artifacts/{number}';info=gh(endpoint);maximum=3*1024**3 if key=='store' else 192*1024**2
  c.require(info['id']==number and info['name']==NAMES[key] and info['expired'] is False and info['workflow_run']['id']==int(b['run_id']) and info['workflow_run']['head_sha']==b['source_commit'] and 0<info['size_in_bytes']<=maximum and str(info.get('digest','')).startswith('sha256:'),'Pinned artifact provenance differs')
  archive=a.output/(key+'.zip')
  with archive.open('xb') as f:subprocess.run(['gh','api',endpoint+'/zip'],stdout=f,check=True,timeout=300)
  c.require(c.digest(archive)=={'bytes':info['size_in_bytes'],'sha256':info['digest'][7:]},'Artifact transport body differs')
  extract(archive,a.output/key,maximum,[c.PACKAGE,'store-export.json'] if key=='store' else None);archive.unlink();artifacts[key]=info
 record=c.verify_inputs(a.output,a.qualified_source,b,run)
 for name,value in [('qualified-run.json',run),('verified-package.json',record),('capture-inputs.json',{'purpose':'marketing capture only','consumerAcceptance':False,'qualified':b,'artifacts':artifacts})]:
  with (a.output/name).open('x') as f:json.dump(value,f,indent=2)
if __name__=='__main__':main()
