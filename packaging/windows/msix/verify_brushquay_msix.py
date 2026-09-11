#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Trieflow LLC
# SPDX-License-Identifier: GPL-3.0-or-later
"""Independently compare every unsigned MSIX payload entry with its audited hashes."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import unicodedata
import zipfile
from manifest_identity import MAX_MANIFEST_BYTES, validate_identity_values, verify_manifest_identity

METADATA = {'[Content_Types].xml', 'AppxBlockMap.xml'}

def checked_path(value):
    if not isinstance(value,str) or not value or '\\' in value or ':' in value:
        raise ValueError('Non-canonical package path: '+repr(value))
    parts=value.split('/')
    if any(not p or p in ('.','..') or p.endswith(('.', ' ')) or
           re.search(r'[<>"|?*\x00-\x1f\x7f]',p) or
           re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?',p,re.I) for p in parts):
        raise ValueError('Unsafe Windows package path: '+value)
    return value

def register_path(value,seen):
    checked_path(value)
    parts=value.split('/')
    for count in range(1,len(parts)+1):
        prefix='/'.join(parts[:count]);key=unicodedata.normalize('NFC',prefix).casefold()
        if ('file',key) in seen: raise ValueError('Duplicate/file-directory package collision: '+value)
        prior=seen.get(('component',key))
        if prior is not None and prior!=prefix: raise ValueError('Case/Unicode directory alias: '+value)
        if count==len(parts) and ('directory',key) in seen: raise ValueError('File-directory package collision: '+value)
        seen[('component',key)]=prefix
        seen[('file' if count==len(parts) else 'directory',key)]=prefix


def digest_stream(stream):
    sha=hashlib.sha256();size=0
    while data:=stream.read(1024*1024): sha.update(data);size+=len(data)
    return {'sha256':sha.hexdigest(),'bytes':size}

def verify_msix(path,expected,identity):
    validate_identity_values(identity)
    if 'AppxManifest.xml' not in expected: raise ValueError('Approved manifest is required')
    if not expected or any(name in METADATA for name in expected): raise ValueError('Invalid expected payload')
    expected_seen={}
    for name in expected: register_path(name,expected_seen)
    seen={};actual={};metadata=set();directories=set();manifest_identity=None
    allowed_directories={str(parent) for name in expected for parent in PurePosixPath(name).parents if str(parent)!="."}
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            mode=info.external_attr>>16
            if info.flag_bits&1: raise ValueError('Encrypted container entry: '+info.filename)
            if info.is_dir():
                name=checked_path(info.filename[:-1])
                if stat.S_IFMT(mode) not in (0,stat.S_IFDIR) or name not in allowed_directories or name in directories:
                    raise ValueError('Unexpected/special directory entry: '+info.filename)
                directories.add(name)
                continue
            register_path(info.filename,seen)
            if stat.S_IFMT(mode) not in (0,stat.S_IFREG):
                raise ValueError('Special container entry: '+info.filename)
            if info.filename in METADATA:
                if info.file_size>16*1024*1024: raise ValueError('Oversized package metadata')
                metadata.add(info.filename)
                continue
            record=expected.get(info.filename)
            if not record or info.file_size!=record['bytes']:
                raise ValueError('Unexpected package entry or size: '+info.filename)
            with archive.open(info) as stream:
                if info.filename=='AppxManifest.xml':
                    if info.file_size>MAX_MANIFEST_BYTES: raise ValueError('Oversized package manifest')
                    data=stream.read(MAX_MANIFEST_BYTES+1)
                    measured={'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
                    manifest_identity=verify_manifest_identity(data,identity)
                else: measured=digest_stream(stream)
            if measured!=record: raise ValueError('Package payload hash mismatch: '+info.filename)
            actual[info.filename]=measured
    if set(actual)!=set(expected) or metadata!=METADATA: raise ValueError('Missing package payload or required metadata')
    with Path(path).open('rb') as stream: package=digest_stream(stream)
    return {'verifiedPayloadFiles':len(actual),'package':package,'manifest':manifest_identity}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',required=True,type=Path)
    parser.add_argument('--record',required=True,type=Path)
    args=parser.parse_args()
    record=json.loads(args.record.read_text())
    print(json.dumps(verify_msix(args.package,record['payload'],record['identity']),indent=2))

if __name__=='__main__': main()
