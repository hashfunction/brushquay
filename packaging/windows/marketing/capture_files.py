# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
"""Exclusive demo fixtures and independent readback after proven normal app stop."""
import argparse,hashlib,json,re,shutil,sys,zipfile,xml.etree.ElementTree as ET
from pathlib import Path
import capture_checks as c
NAMES={'Moonlit Garden.ora','Moonlit Garden.kra','Moonlit Garden.png','Moonlit Garden Reopened.kra'}
SCENES=('01-painting-workspace','02-export-preset','03-exported-illustration')
def helpers(source):
 sys.path.insert(0,str(Path(source)/'packaging/windows/msix'));sys.path.insert(0,str(Path(source)/'packaging/windows/qualification'))
 import ownership,workflow_files
 # Capture-specific fixture names only; unchanged lease, link, snapshot and
 # deletion implementation. Product/profile state is never configured here.
 ownership.FIXTURE_FILES={ownership.MARKER,'protected.txt'}|NAMES
 return ownership,workflow_files
def stopped(proof):
 c.require(all(proof.get(k) is True for k in ('passed','normalClosePassed','ownedProcessesStopped')) and proof.get('purpose')=='marketing capture only' and proof.get('consumerAcceptance') is False and type(proof.get('normalExitCode')) is int and proof['normalExitCode']==0 and not any(k in proof for k in ('error','cleanupError','forcedStop')),'Normal owned capture stop is unproved')
def begin(root,source):
 own,_=helpers(source)
 asset=Path(__file__).parent/'fixtures/Moonlit Garden.ora';manifest=c.load(asset.with_name('artwork.json'))
 c.require(c.digest(asset)==manifest['archive'],'Original demo artwork changed')
 lease=own.begin(root,'fixture')
 with asset.open('rb') as src,(Path(root)/asset.name).open('xb') as out:shutil.copyfileobj(src,out)
 lease['protected'][asset.name]=c.digest(asset);own.inspect(lease);return lease
def remove_empty_export(lease,proof,gui,source):
 stopped(proof);own,_=helpers(source);root=Path(lease['root']);c.no_links(root)
 c.require(lease['kind']=='fixture' and [root.stat().st_dev,root.stat().st_ino]==lease['identity'] and c.digest(root/own.MARKER)==lease['marker'],'Original exclusive fixture identity/marker changed')
 tree=own.measure_tree(root)
 c.require(set(tree)==own.FIXTURE_FILES and all(tree.get(n)==v for n,v in lease['protected'].items()),'Original protected or exact capture fixture files differ')
 directories=[]
 for path in root.iterdir():
  c.no_links(path)
  if path.is_dir():directories.append(path)
 c.require(len(directories)==1 and re.fullmatch(r'\.brushquay-export-[A-Za-z0-9]{6}',directories[0].name),'Exact single source-defined transaction directory required')
 directory=directories[0];identity=[directory.stat().st_dev,directory.stat().st_ino]
 c.require(not list(directory.iterdir()),'Transaction directory contains unexpected files; preserve it')
 observation={'purpose':'marketing capture only','path':str(directory),'identity':identity,'empty':True,'normalCloseVerified':True,'state':'observed-before-removal'}
 with (Path(gui)/'transaction-directory-observation.json').open('x') as f:json.dump(observation,f,indent=2)
 c.no_links(directory)
 c.require([root.stat().st_dev,root.stat().st_ino]==lease['identity'] and c.digest(root/own.MARKER)==lease['marker'] and own.measure_tree(root)==tree and [p.name for p in root.iterdir() if p.is_dir()]==[directory.name] and [directory.stat().st_dev,directory.stat().st_ino]==identity and not list(directory.iterdir()),'Owned transaction directory or original fixture changed before removal')
 # rmdir cannot remove unexpected contents. Original strict fixture inspection
 # resumes immediately after removing this one documented empty product output.
 directory.rmdir();own.inspect(lease)
 return dict(observation,removed=True,state='removed-empty-directory')
def verify(lease,profile,proof,gui,source):
 stopped(proof);own,images=helpers(source);own.inspect(lease);own.inspect(profile);root=Path(lease['root'])
 manifest=c.load(Path(__file__).parent/'fixtures/artwork.json')
 with zipfile.ZipFile(root/'Moonlit Garden.ora') as original:
  c.require(set(original.namelist())==set(manifest['members']),'Original artwork member set differs')
  for n,v in manifest['members'].items():c.require({'bytes':len(original.read(n)),'sha256':hashlib.sha256(original.read(n)).hexdigest()}==v,'Original artwork member changed')
 art,art_record=images.kra_image(root/'Moonlit Garden.kra');png,png_record=images.image_file(root/'Moonlit Garden.png');reopened,reopen_record=images.kra_image(root/'Moonlit Garden Reopened.kra')
 c.require(art==png==reopened,'Actual saved, preset-exported and reopened pixels differ')
 with zipfile.ZipFile(root/'Moonlit Garden.kra') as document:
  tree=ET.fromstring(document.read('maindoc.xml'))
  names=[n.get('name') for n in tree.iter() if n.tag.rsplit('}',1)[-1]=='layer']
 c.require(sorted(names)==sorted(manifest['layerNames']),'Actual editable document did not preserve the three original layers')
 c.require(len(set(tuple(art[i:i+4]) for i in range(0,len(art),4)))>100,'Composed illustration is missing')
 presets=[Path(profile['root'])/n for n in own.inspect(profile) if n.endswith('/export-presets-v1.json')]
 c.require(len(presets)==1 and presets[0].stat().st_size<=2*1024*1024,'Exact owned saved preset store missing or ambiguous')
 store=c.load(presets[0]);c.require(store.get('schema')==1 and len(store.get('presets',[]))==1,'Unexpected preset store content')
 preset=store['presets'][0]
 c.require(preset.get('schema')==1 and preset.get('name')=='Moonlit Garden - PNG' and preset.get('mimeType')=='image/png' and preset.get('extension')=='png' and isinstance(preset.get('properties'),dict) and preset['properties'],'Actual named PNG preset was not persisted')
 captures={}
 for name in SCENES:
  meta=c.load(Path(gui)/(name+'-capture.json'));path=Path(gui)/(name+'.png');raw=path.read_bytes()
  c.require(meta.get('unedited') is True and meta.get('purpose')=='marketing capture only' and meta.get('processId')==proof['activatedPid'] and meta.get('processStartUtc')==proof['processStartUtc'] and meta.get('executableSha256')==proof['executableSha256'] and meta.get('sha256')==hashlib.sha256(raw).hexdigest(),'Raw marketing capture/process binding differs')
  import struct
  c.require(raw[:8]==b'\x89PNG\r\n\x1a\n' and list(struct.unpack('>II',raw[16:24]))==meta['bounds'][2:] and meta['bounds'][2]>=1366 and meta['bounds'][3]>=768,'Raw full-window capture dimensions differ')
  captures[name+'.png']=c.digest(path)
 return {'purpose':'marketing capture only','consumerAcceptance':False,'dimensions':[512,384],'layerNames':names,'pixelSha256':hashlib.sha256(art).hexdigest(),'savedPreset':{'name':preset['name'],'mimeType':preset['mimeType'],'store':c.digest(presets[0])},'files':{'Moonlit Garden.kra':art_record,'Moonlit Garden.png':png_record,'Moonlit Garden Reopened.kra':reopen_record},'captures':captures,'sourceArtwork':manifest['archive']}
def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=('begin','inspect','remove-empty-export','verify','seal','clean'));p.add_argument('--source',required=True,type=Path);p.add_argument('--root',type=Path);p.add_argument('--lease',type=Path);p.add_argument('--profile',type=Path);p.add_argument('--proof',type=Path);p.add_argument('--gui',type=Path);p.add_argument('--sealed',type=Path);p.add_argument('--output',type=Path);a=p.parse_args();own,_=helpers(a.source)
 if a.action=='begin':result=begin(a.root,a.source)
 elif a.action=='inspect':result=own.inspect(c.load(a.lease))
 elif a.action=='remove-empty-export':result=remove_empty_export(c.load(a.lease),c.load(a.proof),a.gui,a.source)
 elif a.action=='verify':result=verify(c.load(a.lease),c.load(a.profile),c.load(a.proof),a.gui,a.source)
 elif a.action=='seal':result=own.seal(c.load(a.lease),c.load(a.proof))
 else:own.clean(c.load(a.sealed),c.load(a.proof));return
 if a.output:
  with a.output.open('x') as f:json.dump(result,f,indent=2)
if __name__=='__main__':main()
