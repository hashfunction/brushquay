# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
"""Exclusive fixture/package-profile leases; deletion requires stopped-process proof."""
import argparse
import json
import os
from pathlib import Path
import secrets
from runtime_stage import measure, measure_tree, no_links

MARKER='.bristlune-qualification-owner.json'
FIXTURE_FILES={MARKER,'protected.txt','blank.kra','artwork.kra','artwork.png','reopened.kra'}
PROFILE_TREES={'AC','AppData','LocalCache','LocalState','RoamingState','Settings','SystemAppData','TempState'}


def write(path,data):
    with Path(path).open('x',encoding='utf-8') as f:json.dump(data,f,sort_keys=True,indent=2)


def begin(root,kind):
    root=Path(root).absolute();no_links(root.parent)
    if kind not in ('fixture','profile') or os.path.lexists(root):raise ValueError('An absent, exact owned root is required')
    root.mkdir()
    marker={'purpose':'Bristlune disposable '+kind,'token':secrets.token_hex(32)}
    write(root/MARKER,marker)
    if kind=='fixture':
        with (root/'protected.txt').open('xb') as f:f.write(b'Original protected bytes: Bristlune\r\n\x00\xff\n')
    return {'root':str(root),'kind':kind,'identity':[root.stat().st_dev,root.stat().st_ino],
            'marker':measure(root/MARKER),'protected':measure_tree(root)}


def require_stopped(proof):
    if proof.get('ownedProcessesStopped') is not True:
        raise ValueError('All retained product processes must be proven stopped')


def inspect(lease):
    root=Path(lease['root']);no_links(root)
    if [root.stat().st_dev,root.stat().st_ino]!=lease['identity'] or measure(root/MARKER)!=lease['marker']:
        raise ValueError('Owned root or exclusive marker changed')
    tree=measure_tree(root)
    if len(tree)>50000 or sum(row['bytes'] for row in tree.values())>1024*1024*1024:
        raise ValueError('Owned profile/fixture exceeds inspection bound')
    for name in tree:
        if lease['kind']=='fixture' and name not in FIXTURE_FILES:raise ValueError('Unexpected fixture file: '+name)
        if lease['kind']=='profile' and name!=MARKER and name.split('/')[0] not in PROFILE_TREES:
            raise ValueError('Unexpected package profile file: '+name)
    # Empty/unexpected directories also block cleanup.
    for path in root.rglob('*'):
        if path.is_dir():
            rel=path.relative_to(root).as_posix()
            if lease['kind']=='fixture' or rel.split('/')[0] not in PROFILE_TREES:
                raise ValueError('Unexpected owned directory: '+rel)
    for name,value in lease['protected'].items():
        if tree.get(name)!=value:raise ValueError('Protected original changed: '+name)
    return tree


def seal(lease,proof):
    require_stopped(proof)
    tree=inspect(lease)
    return {'lease':lease,'tree':tree,'directories':sorted(p.relative_to(Path(lease['root'])).as_posix() for p in Path(lease['root']).rglob('*') if p.is_dir())}


def clean(sealed,proof):
    require_stopped(proof);lease=sealed['lease'];root=Path(lease['root'])
    current=seal(lease,proof)
    if current!=sealed:raise ValueError('Owned contents changed after the stopped-process snapshot')
    # Files are checked again immediately before removal; marker stays until last.
    names=sorted(n for n in sealed['tree'] if n!=MARKER)
    for name in names:
        if measure(root/name)!=sealed['tree'][name]:raise ValueError('Cleanup input changed: '+name)
        (root/name).unlink()
    for path in sorted((p for p in root.rglob('*') if p.name!=MARKER),key=lambda p:len(p.parts),reverse=True):
        no_links(path)
        if not path.is_dir():raise ValueError('Unexpected file appeared during cleanup')
        path.rmdir()
    if sorted(p.name for p in root.iterdir())!=[MARKER] or measure(root/MARKER)!=lease['marker']:
        raise ValueError('Owned directory changed before final marker removal')
    (root/MARKER).unlink();root.rmdir()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('begin','verify','seal','check','clean'))
    p.add_argument('--root',type=Path);p.add_argument('--kind',choices=('fixture','profile'))
    p.add_argument('--lease',type=Path);p.add_argument('--sealed',type=Path);p.add_argument('--proof',type=Path);p.add_argument('--output',type=Path)
    a=p.parse_args();read=lambda path:json.loads(path.read_text(encoding='utf-8-sig'))
    if a.action=='begin':write(a.output,begin(a.root,a.kind))
    elif a.action=='verify':inspect(read(a.lease))
    elif a.action=='seal':write(a.output,seal(read(a.lease),read(a.proof)))
    elif a.action=='check':
        frozen=read(a.sealed);require_stopped(read(a.proof))
        if seal(frozen['lease'],read(a.proof))!=frozen:raise ValueError('Owned contents changed before uninstall')
    else:clean(read(a.sealed),read(a.proof))
