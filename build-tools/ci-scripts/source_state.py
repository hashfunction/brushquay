# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only, bounded original Git and byte evidence for a strict clean-source gate."""
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess

MAX_STATUS=2*1024*1024
MAX_PATHS=256
MAX_FILE=64*1024*1024


def encoded(data):return base64.b64encode(data).decode('ascii')


def git(source,*args):
    result=subprocess.run(['git','-C',str(source),'--literal-pathspecs',*args],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
    if result.returncode:raise ValueError('Git observation failed: '+str(result.returncode)+': '+result.stderr[:4096].decode('utf-8','backslashreplace'))
    if len(result.stdout)>MAX_STATUS:raise ValueError('Git observation exceeds 2 MiB bound')
    return result.stdout


def digest_stream(stream):
    h=hashlib.sha256();count=lf=cr=crlf=0;last=b''
    while block:=stream.read(1024*1024):
        count+=len(block)
        if count>MAX_FILE:raise ValueError('Source path exceeds hash byte bound')
        h.update(block);lf+=block.count(b'\n');cr+=block.count(b'\r');crlf+=block.count(b'\r\n')+int(last==b'\r' and block.startswith(b'\n'));last=block[-1:]
    return dict(bytes=count,sha256=h.hexdigest(),lf=lf,cr=cr,crlf=crlf)


def status_paths(raw):
    parts=raw.split(b'\0');rows=[];i=0
    while i<len(parts)-1:
        part=parts[i];i+=1
        if len(part)<4 or part[2:3]!=b' ':raise ValueError('Malformed Git porcelain record')
        row=dict(status=part[:2].decode('ascii'),path=part[3:].decode('utf-8','surrogateescape'))
        if b'R' in part[:2] or b'C' in part[:2]:
            if i>=len(parts)-1:raise ValueError('Missing original rename path')
            row['originalPath']=parts[i].decode('utf-8','surrogateescape');i+=1
        rows.append(row)
    return rows


def safe_path(source,relative):
    parsed=PurePosixPath(relative)
    if parsed.is_absolute() or not relative or '\\' in relative or ':' in relative or any(p in ('','..','.') for p in relative.split('/')):
        raise ValueError('Unsafe Git-returned source path')
    path=source.joinpath(*parsed.parts)
    for parent in path.parents:
        if parent==source:break
        try:info=parent.lstat()
        except FileNotFoundError:continue
        if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400:raise ValueError('Git-returned path has a link ancestor')
    return path


def observe_path(source,head,relative):
    path=safe_path(source,relative);row=dict(path=relative,committed=None,working=None)
    tree=git(source,'ls-tree','-z',head,'--',relative)
    if tree:
        if tree.count(b'\0')!=1:raise ValueError('Ambiguous committed path')
        header,name=tree[:-1].split(b'\t',1);mode,kind,oid=header.decode('ascii').split()
        if name.decode('utf-8','surrogateescape')!=relative or not re.fullmatch('[0-9a-f]{40,64}',oid):raise ValueError('Committed path identity differs')
        row['committed']=dict(mode=mode,kind=kind,gitObject=oid)
        if kind=='blob':
            size=int(git(source,'cat-file','-s',oid))
            if size>MAX_FILE:row['committed'].update(bytes=size,hashOmitted='64 MiB bound')
            else:
                process=subprocess.Popen(['git','-C',str(source),'cat-file','blob',oid],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                try:row['committed'].update(digest_stream(process.stdout))
                finally:
                    process.stdout.close();error=process.stderr.read(4096);process.stderr.close();code=process.wait(timeout=30)
                if code or row['committed']['bytes']!=size:raise ValueError('Committed blob read failed: '+error.decode('utf-8','backslashreplace'))
    try:before=path.lstat()
    except FileNotFoundError:return row
    row['working']=dict(mode=oct(stat.S_IMODE(before.st_mode)))
    if stat.S_ISLNK(before.st_mode) or getattr(before,'st_file_attributes',0)&0x400:
        row['working'].update(kind='link');return row
    if not stat.S_ISREG(before.st_mode):row['working'].update(kind='nonregular');return row
    row['working'].update(kind='file')
    if before.st_size>MAX_FILE:row['working'].update(bytes=before.st_size,hashOmitted='64 MiB bound');return row
    with path.open('rb') as stream:
        opened=os.fstat(stream.fileno())
        if (opened.st_dev,opened.st_ino)!=(before.st_dev,before.st_ino):raise ValueError('Source path changed before hash read')
        row['working'].update(digest_stream(stream))
    after=path.lstat()
    if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_mode)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_mode):raise ValueError('Source path changed while hashing')
    return row


def require_clean_source(source,expected_commit,output,phase):
    source=Path(source).resolve(strict=True)
    record=dict(schema=1,phase=phase,expectedCommit=expected_commit,observedUtc=datetime.now(timezone.utc).isoformat(),
        head=None,tree=None,clean=False,stable=False,statusPorcelainV1Base64=None,statusEntries=[],paths=[],observationErrors=[])
    # Reserve only the caller's exclusive metadata output, never a source path.
    stream=Path(output).open('x',encoding='utf-8') if output is not None else None
    try:
        head=git(source,'rev-parse','HEAD').decode('ascii').strip();record['head']=head
        record['tree']=git(source,'show','-s','--format=%T','HEAD').decode('ascii').strip()
        raw=git(source,'status','--porcelain=v1','-z','--untracked-files=all');record['statusPorcelainV1Base64']=encoded(raw)
        entries=status_paths(raw);record['statusEntries']=entries
        returned=sorted({entry[key] for entry in entries for key in ('path','originalPath') if key in entry})
        record['pathCount']=len(returned);record['pathMetadataTruncated']=len(returned)>MAX_PATHS
        for relative in returned[:MAX_PATHS]:
            try:record['paths'].append(observe_path(source,head,relative))
            except (OSError,ValueError,subprocess.SubprocessError) as error:record['observationErrors'].append(dict(path=relative,error=str(error)))
        # No source content diff is exported; these record original modes,
        # object IDs, line counts and index/working-tree line-ending metadata.
        for field,args in [('diffRawBase64',('diff','--no-ext-diff','--no-textconv','--raw','--no-abbrev','--no-renames','-z',head)),
                           ('diffNumstatBase64',('diff','--no-ext-diff','--no-textconv','--numstat','--no-renames','-z',head)),
                           ('indexEolBase64',('ls-files','--eol','-z'))]:
            record[field]=encoded(git(source,*args,'--',*returned[:MAX_PATHS])) if returned else ''
        record['stable']=git(source,'rev-parse','HEAD').decode('ascii').strip()==head and git(source,'status','--porcelain=v1','-z','--untracked-files=all')==raw
        record['clean']=bool(re.fullmatch('[0-9a-f]{40}',expected_commit or '') and head==expected_commit and not raw and record['stable'] and not record['observationErrors'])
    except (OSError,ValueError,subprocess.SubprocessError) as error:
        record['observationErrors'].append(dict(error=str(error)))
    finally:
        if stream:
            json.dump(record,stream,ensure_ascii=True,sort_keys=True,indent=2);stream.write('\n');stream.close()
    if not record['clean']:
        paths=', '.join(entry['path'] for entry in record['statusEntries'][:12])
        raise ValueError('Qualification requires the exact clean committed source; phase='+phase+'; expected commit='+str(expected_commit)+
                         '; observed commit='+str(record['head'])+'; dirty paths='+paths+'; original metadata='+str(output))
    return record
