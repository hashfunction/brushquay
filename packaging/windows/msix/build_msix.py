#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Trieflow LLC
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build an unsigned BrushQuay MSIX from an explicitly audited install tree.

No NSIS extraction, shell extension, signing service, tool discovery or downloads.
The release owner supplies identity, source/license closure and exact SDK tools.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape
from verify_brushquay_msix import checked_path, register_path, digest_stream, verify_msix

HERE=Path(__file__).resolve().parent
SOURCE=HERE.parents[2]
sys.path.insert(0,str(SOURCE/'build-tools/ci-scripts'))
from locked_windows_deps import publish_directory_no_replace
FIELDS={'PackageName','Publisher','Version','MinWindowsVersion','MaxWindowsVersionTested'}

def canonical(value): return (json.dumps(value,sort_keys=True,indent=2)+'\n').encode()

def version(value):
    if not isinstance(value,str) or not re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)',value):
        raise ValueError('Expected four-component Windows version')
    numbers=tuple(map(int,value.split('.')))
    if any(n>65535 for n in numbers): raise ValueError('Windows version component exceeds 65535')
    return numbers

def load_identity(path):
    raw=Path(path).read_bytes()
    if len(raw)>65536 or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper(): raise ValueError('Unsafe identity XML')
    try:
        text=raw.decode('utf-8-sig')
        root=ET.fromstring(text)
    except (UnicodeDecodeError,ET.ParseError) as error: raise ValueError('Invalid identity XML') from error
    if root.tag!='Project' or root.attrib or len(root)!=1 or root[0].tag!='PropertyGroup' or root[0].attrib:
        raise ValueError('Identity must contain one PropertyGroup')
    result={}
    for node in root[0]:
        if node.tag not in FIELDS or node.tag in result or node.attrib or len(node): raise ValueError('Unknown/duplicate identity field')
        result[node.tag]=(node.text or '').strip()
    if set(result)!=FIELDS or any(not v or 'REQUIRED' in v.upper() or 'KRITA' in v.upper() or
        '03E730BB' in v.upper() or any(ord(c)<32 for c in v) for v in result.values()):
        raise ValueError('Missing, placeholder or upstream identity')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{1,48}[A-Za-z0-9]',result['PackageName']): raise ValueError('Invalid package name')
    if not result['Publisher'].startswith('CN=') or len(result['Publisher'])>8192: raise ValueError('Invalid publisher distinguished name')
    if version(result['Version'])[0]<1: raise ValueError('Package major version must be positive')
    minimum=version(result['MinWindowsVersion']);tested=version(result['MaxWindowsVersionTested'])
    if minimum<(10,0,17763,0) or tested<minimum: raise ValueError('Invalid Windows compatibility range')
    return result

def manifest_bytes(identity):
    text=(HERE/'manifest.xml.in').read_text()
    for key,value in identity.items(): text=text.replace('@'+key+'@',escape(value,{'"':'&quot;',"'":'&apos;'}))
    if re.search(r'@[A-Za-z]+@',text): raise ValueError('Unresolved manifest field')
    ET.fromstring(text)
    return text.encode('utf-8')

def validate_audit(audit):
    if not isinstance(audit,dict) or set(audit)!={'schema','sourceCommit','licenseReviewComplete','correspondingSourceComplete','files'}:
        raise ValueError('Invalid audit schema')
    if audit['schema']!=1 or not isinstance(audit['sourceCommit'],str) or not re.fullmatch('[0-9a-f]{40}',audit['sourceCommit']): raise ValueError('Missing immutable source commit')
    if audit['licenseReviewComplete'] is not True or audit['correspondingSourceComplete'] is not True:
        raise ValueError('License review and corresponding-source closure are required')
    if not isinstance(audit['files'],list) or not audit['files']: raise ValueError('Empty audited install tree')
    seen={};expected={}
    for row in audit['files']:
        if not isinstance(row,dict) or set(row)!={'path','bytes','sha256','license','source'}: raise ValueError('Invalid audited file record')
        register_path(row['path'],seen)
        if type(row['bytes']) is not int or row['bytes']<0 or not isinstance(row['sha256'],str) or not re.fullmatch('[0-9a-f]{64}',row['sha256']): raise ValueError('Invalid file hash/size')
        if any(not isinstance(row[k],str) or not row[k].strip() or re.search(r'NOASSERTION|NONE|REQUIRED',row[k],re.I) for k in ('license','source')):
            raise ValueError('Unresolved file license or source')
        expected[row['path']]={'bytes':row['bytes'],'sha256':row['sha256']}
    if 'bin/brushquay.exe' not in expected: raise ValueError('BrushQuay executable is missing')
    return expected

def reject_link(path):
    info=path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400:
        raise ValueError('Symlink/reparse point refused: '+str(path))
    return info

def regular_stream(path):
    before=reject_link(path)
    if not stat.S_ISREG(before.st_mode): raise ValueError('Expected a regular file: '+str(path))
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_BINARY',0)|getattr(os,'O_NOFOLLOW',0))
    stream=os.fdopen(fd,'rb');after=os.fstat(fd)
    if (before.st_dev,before.st_ino)!=(after.st_dev,after.st_ino) or not stat.S_ISREG(after.st_mode):
        stream.close();raise ValueError('Input identity changed: '+str(path))
    return stream

def inventory(root):
    root=Path(root);reject_link(root)
    if not root.is_dir(): raise ValueError('Expected a directory')
    result={};seen={}
    def walk(directory):
        for path in sorted(directory.iterdir()):
            info=reject_link(path)
            rel=path.relative_to(root).as_posix()
            checked_path(rel)
            if stat.S_ISDIR(info.st_mode): walk(path)
            elif stat.S_ISREG(info.st_mode):
                register_path(rel,seen)
                with regular_stream(path) as stream: result[rel]=digest_stream(stream)
            else: raise ValueError('Special file refused: '+rel)
    walk(root)
    return result

def verify_payload(root,expected):
    actual=inventory(root)
    if actual!=expected:
        changed=sorted(set(actual)^set(expected) | {p for p in actual.keys()&expected.keys() if actual[p]!=expected[p]})
        raise ValueError('File inventory/hash mismatch: '+', '.join(changed[:8]))

def write_new(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as stream: stream.write(data);stream.flush();os.fsync(stream.fileno())

def stage_payload(install,audit,destination,identity):
    expected=validate_audit(audit);install=Path(install);destination=Path(destination)
    verify_payload(install,expected)
    if os.path.lexists(destination): raise ValueError('Existing payload is never replaced')
    destination.mkdir()
    for rel,record in expected.items():
        target=destination/'BrushQuay'/rel;target.parent.mkdir(parents=True,exist_ok=True)
        with regular_stream(install/rel) as source, target.open('xb') as output:
            shutil.copyfileobj(source,output,1024*1024)
        with regular_stream(target) as stream:
            if digest_stream(stream)!=record: raise ValueError('Input changed during copy: '+rel)
    verify_payload(install,expected)
    asset_lock=json.loads((HERE/'assets.lock.json').read_text())
    if set(asset_lock)!={'Assets/StoreLogo.png','Assets/Square150x150Logo.png','Assets/Square44x44Logo.png'}:
        raise ValueError('Only the three reviewed original package assets are allowed')
    for rel,record in asset_lock.items():
        checked_path(rel)
        with regular_stream(HERE/'pkg'/rel) as stream:
            data=stream.read()
        if {'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}!=record: raise ValueError('Original artwork hash mismatch: '+rel)
        write_new(destination/rel,data)
    write_new(destination/'AppxManifest.xml',manifest_bytes(identity))
    payload={'BrushQuay/'+rel:record for rel,record in expected.items()}
    payload.update(asset_lock)
    manifest=(destination/'AppxManifest.xml').read_bytes()
    payload['AppxManifest.xml']={'bytes':len(manifest),'sha256':hashlib.sha256(manifest).hexdigest()}
    verify_payload(destination,payload)
    return payload

def load_tools(path):
    data=json.loads(Path(path).read_text())
    if set(data)!={'sdkVersion','makepri','makeappx'} or not re.fullmatch(r'10\.0\.\d+\.0',data['sdkVersion']): raise ValueError('Explicit Windows SDK version/tools are required')
    for name in ('makepri','makeappx'):
        record=data[name]
        if set(record)!={'path','sha256','bytes'}: raise ValueError('Tool path/hash/size required')
        tool=Path(record['path'])
        if not tool.is_absolute() or tool.name.lower()!=name+'.exe': raise ValueError('Absolute SDK executable path required')
        with regular_stream(tool) as stream:
            if digest_stream(stream)!={k:record[k] for k in ('sha256','bytes')}: raise ValueError('SDK tool hash/size mismatch')
    return data

def require_windows():
    if sys.platform!='win32': raise ValueError('Actual MSIX packaging requires Windows; no platform emulation is used')

def confirm_tools(path,frozen):
    if load_tools(path)!=frozen: raise ValueError('SDK lock changed during packaging')

def build(install,audit_path,identity_path,tools_path,output):
    require_windows()
    audit=json.loads(Path(audit_path).read_text());identity=load_identity(identity_path);sdk=load_tools(tools_path)
    output=Path(output).absolute()
    if os.path.lexists(output): raise ValueError('Existing output is never replaced')
    output.parent.mkdir(parents=True,exist_ok=True)
    temporary=Path(tempfile.mkdtemp(prefix='.brushquay-msix-',dir=output.parent))
    try:
        payload=temporary/'payload';expected=stage_payload(install,audit,payload,identity)
        commands=[[sdk['makepri']['path'],'new','/pr',str(payload),'/mn',str(payload/'AppxManifest.xml'),'/cf',str(HERE/'priconfig.xml'),'/of',str(payload/'resources.pri')],
                  [sdk['makeappx']['path'],'pack','/d',str(payload),'/p',str(temporary/'BrushQuay.msix'),'/no','/v','/h','SHA256'],
                  [sdk['makeappx']['path'],'unpack','/p',str(temporary/'BrushQuay.msix'),'/d',str(temporary/'unpacked'),'/no','/v']]
        for number,command in enumerate(commands):
            confirm_tools(tools_path,sdk) # Recheck against the original immutable tool snapshot.
            with (temporary/f'sdk-{number+1}.log').open('xb') as log:
                subprocess.run(command,check=True,stdout=log,stderr=subprocess.STDOUT,timeout=600,shell=False)
            if number==0:
                with regular_stream(payload/'resources.pri') as stream: expected['resources.pri']=digest_stream(stream)
                if expected['resources.pri']['bytes']==0: raise ValueError('Empty resources.pri')
            verify_payload(payload,expected)
        container=verify_msix(temporary/'BrushQuay.msix',expected)
        # SDK-unpacked content must also agree; only container metadata may be extra.
        unpacked=inventory(temporary/'unpacked')
        for extra in ('[Content_Types].xml','AppxBlockMap.xml'): unpacked.pop(extra,None)
        if unpacked!=expected: raise ValueError('SDK-unpacked bytes differ from audited payload')
        verify_payload(install,validate_audit(audit));confirm_tools(tools_path,sdk)
        record={'schema':1,'identity':identity,'audit':audit,'sdk':sdk,'payload':expected,'verification':container,'signed':False}
        write_new(temporary/'package-record.json',canonical(record))
        publish_directory_no_replace(temporary,output)
        return output
    except Exception as error:
        raise ValueError(f'Packaging failed; inputs were not modified. Recovery/evidence retained at {temporary}: {error}') from error

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('install','audit','identity','sdk-tools','output'): parser.add_argument('--'+name,required=True,type=Path)
    args=parser.parse_args()
    try: print(build(args.install,args.audit,args.identity,args.sdk_tools,args.output))
    except (ValueError,OSError) as error: parser.exit(1,str(error)+'\n')

if __name__=='__main__': main()
