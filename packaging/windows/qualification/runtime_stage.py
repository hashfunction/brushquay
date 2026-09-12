# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
"""Select and copy exact runtime inputs for disposable qualification only."""
import hashlib
import os
from pathlib import Path
import shutil
import stat
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'packaging/windows/msix'))
from verify_brushquay_msix import checked_path, register_path

APP_TREES=('lib/kritaplugins/','lib/krita-python-libs/','share/color/','share/color-schemes/',
           'share/icons/','qml/','share/krita/','share/kritaplugins/','share/locale/')
DEP_TREES=('plugins/','qml/','translations/','etc/fonts/','share/kf6/','share/mime/',
           'share/mlt/','lib/mlt/','lib/krita-python-libs/','lib/site-packages/PyQt6/')
LLVM_RUNTIME={'libc++.dll','libomp.dll','libunwind.dll','libwinpthread-1.dll','libssp-0.dll'}


def no_links(path):
    for item in (Path(path).absolute(),*Path(path).absolute().parents):
        value=item.lstat()
        if stat.S_ISLNK(value.st_mode) or getattr(value,'st_file_attributes',0)&0x400:
            raise ValueError('Linked/reparse runtime path: '+str(item))


def measure(path):
    path=Path(path);no_links(path)
    before=path.stat()
    if not stat.S_ISREG(before.st_mode):raise ValueError('Runtime input is not a regular file')
    with path.open('rb') as stream:
        current=os.fstat(stream.fileno())
        if (before.st_dev,before.st_ino)!=(current.st_dev,current.st_ino):raise ValueError('Input identity changed')
        digest=hashlib.sha256();count=0
        while chunk:=stream.read(1024*1024):digest.update(chunk);count+=len(chunk)
    after=path.stat()
    fields=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')
    if any(getattr(after,k)!=getattr(before,k) for k in fields):raise ValueError('Runtime input changed while hashing')
    return {'bytes':count,'sha256':digest.hexdigest()}


def measure_tree(root):
    root=Path(root);no_links(root)
    result={};names={}
    for directory,folders,files in os.walk(root,followlinks=False):
        for name in folders:no_links(Path(directory)/name)
        for name in files:
            path=Path(directory)/name;relative=path.relative_to(root).as_posix()
            register_path(relative,names)
            result[relative]=measure(path)
    return result


def select_runtime(application,locked):
    result={};aliases={}
    for inventory in (application,locked):
        seen={}
        for path in inventory:register_path(path,seen)
    def add(target,record,tree,relative):
        checked_path(target);checked_path(relative)
        checked={k:record[k] for k in ('bytes','sha256')}
        if type(checked['bytes']) is not int or checked['bytes']<0 or len(checked['sha256'])!=64:
            raise ValueError('Invalid runtime input hash/size')
        origin={'tree':tree,'path':relative}
        if tree=='locked':
            if not record.get('owners'):raise ValueError('Runtime dependency has no locked owner')
            origin['owners']=record['owners']
        if target in result:
            if any(result[target][k]!=checked[k] for k in checked):raise ValueError('Conflicting runtime input: '+target)
            result[target]['inputs'].append(origin)
        else:
            register_path(target,aliases)
            result[target]={**checked,'inputs':[origin]}
    for relative,record in sorted(application.items()):
        checked_path(relative)
        p=Path(relative)
        if relative.startswith(APP_TREES) or (p.parent.as_posix()=='bin' and
            (p.suffix.lower()=='.dll' or p.name in ('bristlune.exe','bristlune.com'))):
            add(relative,record,'application',relative)
    for relative,record in sorted(locked.items()):
        checked_path(relative)
        if relative.startswith('tools/llvm/x86_64-w64-mingw32/bin/') and Path(relative).name in LLVM_RUNTIME:
            add('bin/'+Path(relative).name,record,'locked',relative)
        if not relative.startswith('deps/'):continue
        name=relative[5:];p=Path(name)
        if p.parent.as_posix() in ('bin','lib') and p.suffix.lower()=='.dll':
            add('bin/'+p.name,record,'locked',relative)
        elif name.startswith('lib/plugins/'):
            add(name[4:],record,'locked',relative)
        elif name.startswith(DEP_TREES):add(name,record,'locked',relative)
        elif name.startswith('share/locale/'):add('bin/locale/'+name[len('share/locale/'):],record,'locked',relative)
        elif name.startswith('python/') and p.suffix.lower() not in ('.exe','.cat'):
            add(name,record,'locked',relative)
        elif name=='lib/site-packages/sitecustomize.py' or name.startswith(('lib/site-packages/pyqt6-','lib/site-packages/pyqt6_sip-')):
            add(name,record,'locked',relative)
        elif name=='bin/symsrv.yes':add(name,record,'locked',relative)
    if 'bin/bristlune.exe' not in result or 'bin/bristlune.dll' not in result:
        raise ValueError('Renamed application executable/implementation is missing')
    return result


def materialize(install,locked,selected,destination):
    destination=Path(destination)
    if os.path.lexists(destination):raise ValueError('Existing runtime output is preserved')
    no_links(destination.parent)
    roots={'application':Path(install),'locked':Path(locked)}
    # Check all origins before creating output; equal bytes still need their own provenance.
    for value in selected.values():
        for origin in value['inputs']:
            if measure(roots[origin['tree']]/origin['path'])!={k:value[k] for k in ('bytes','sha256')}:
                raise ValueError('Runtime source differs from measured native/locked input')
    destination.mkdir()
    for relative,value in selected.items():
        checked_path(relative);origin=value['inputs'][0]
        source=roots[origin['tree']]/origin['path'];target=destination/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        no_links(source)
        with source.open('rb') as input_stream,target.open('xb') as output:
            shutil.copyfileobj(input_stream,output,1024*1024)
        if measure(target)!={k:value[k] for k in ('bytes','sha256')}:
            raise ValueError('Runtime source changed during copying')
    if measure_tree(destination)!={k:{field:v[field] for field in ('bytes','sha256')} for k,v in selected.items()}:
        raise ValueError('Copied runtime differs from its source inventory')
