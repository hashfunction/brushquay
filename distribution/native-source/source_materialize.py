# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
"""Fetch pinned source materials and compare Git archives with immutable objects.

Downloads are data only. Prebuilt archives and unresolved Git branches are not
source requests. An archive hash or Git match does not grant release clearance.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import gzip
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile
from urllib.parse import quote, urlsplit, urlunsplit

import native_source as source


def archive_requests(inventory):
    requests = {}
    for package in inventory['packages']:
        for item in package.get('windowsInputs', []):
            if 'URL' not in item or item['inputKind'] == 'prebuilt-input-not-corresponding-source': continue
            if 'URL_HASH' in item:
                algorithm, digest = item['URL_HASH'].lower().split('=', 1)
            elif 'URL_MD5' in item:
                algorithm, digest = 'md5', item['URL_MD5'].lower()
            else: raise ValueError('Unpinned source archive: ' + item['URL'])
            record = {'url': item['URL'], 'algorithm': algorithm, 'digest': digest,
                      'owners': [package['name']]}
            check_request(record)
            if item['URL'] in requests:
                old = requests[item['URL']]
                if (old['algorithm'], old['digest']) != (algorithm, digest):
                    raise ValueError('Conflicting source pins for one URL')
                old['owners'] = sorted(set(old['owners'] + record['owners']))
            else: requests[item['URL']] = record
    return [requests[url] for url in sorted(requests)]


def check_request(request):
    url = urlsplit(request['url'])
    if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password or url.fragment:
        raise ValueError('Invalid source URL')
    length = {'sha256': 64, 'sha1': 40, 'md5': 32}.get(request['algorithm'])
    if length is None or not re.fullmatch('[a-f0-9]{' + str(length) + '}', request['digest']):
        raise ValueError('Invalid source digest')
    if not request['owners'] or request['owners'] != sorted(set(request['owners'])):
        raise ValueError('Explicit unique source owners required')


def transport_url(url):
    parsed = urlsplit(url)
    return urlunsplit(('https', parsed.netloc, parsed.path, parsed.query, ''))


def curl_download(url, output):
    subprocess.run(['curl', '--fail', '--silent', '--show-error', '--location',
                    '--proto', '=https', '--proto-redir', '=https', '--connect-timeout', '25',
                    '--max-time', '180', '--max-filesize', str(512*1024*1024),
                    url, '--output', str(output)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def measure_original(path, algorithm):
    before = source.measure(path)
    checksum = hashlib.new(algorithm)
    with Path(path).open('rb') as stream:
        while data := stream.read(1024*1024): checksum.update(data)
    if source.measure(path) != before: raise ValueError('Source archive changed during original hash check')
    return before, checksum.hexdigest()


def fetch_archive(request, cache, download=curl_download):
    check_request(request)
    cache = Path(cache); source.no_links(cache)
    name = request['algorithm'] + '-' + request['digest'] + '.source'
    destination = cache / name
    url = transport_url(request['url'])
    if not os.path.lexists(destination):
        fd, temporary = tempfile.mkstemp(prefix='.source-download-', dir=cache)
        os.close(fd); temporary = Path(temporary)
        try:
            download(url, temporary)
            measured, checksum = measure_original(temporary, request['algorithm'])
            if checksum != request['digest']: raise ValueError('Downloaded source does not match its original recipe digest')
            try: os.link(temporary, destination)
            except FileExistsError: pass  # Verify the competing owner's exact bytes below.
        finally: temporary.unlink(missing_ok=True)
    measured, checksum = measure_original(destination, request['algorithm'])
    if checksum != request['digest']: raise ValueError('Existing source cache owner has different bytes')
    return {**measured, 'file': name, 'url': request['url'], 'transportUrl': url,
            'owners': request['owners'], 'recipeHashAlgorithm': request['algorithm'],
            'recipeHash': request['digest'], 'strongOriginalSourceHash': request['algorithm'] == 'sha256',
            'correspondingSourceComplete': False}


def git_entries(repo, commit):
    if not re.fullmatch('[a-f0-9]{40}', commit): raise ValueError('Full immutable Git commit required')
    try:
        if source.git(repo, 'cat-file', '-t', commit).strip() != b'commit': raise ValueError('Git object is not a commit')
        tree = source.git(repo, 'show', '-s', '--format=%T', commit).decode().strip()
        listing = source.git(repo, 'ls-tree', '-rz', '--full-tree', commit)
    except subprocess.CalledProcessError as error:
        raise ValueError('Pinned Git source object is unavailable') from error
    entries = {}
    for row in listing.split(b'\0'):
        if not row: continue
        meta, name = row.split(b'\t', 1); mode, kind, oid = meta.decode().split()
        path = name.decode('utf-8'); archive_path(path)
        if path in entries or mode not in ('100644', '100755', '120000', '160000'):
            raise ValueError('Unsupported/duplicate Git source entry')
        entries[path] = {'mode': mode, 'kind': kind, 'oid': oid}
    return tree, entries


def archive_path(name):
    if (not name or name.startswith(('/', '\\')) or '\x00' in name
            or any(part in ('', '.', '..') for part in name.rstrip('/').split('/'))):
        raise ValueError('Unsafe source archive path: ' + repr(name))


def blob_hash(stream, size):
    checksum = hashlib.sha1(b'blob ' + str(size).encode() + b'\0'); count = 0
    while data := stream.read(1024*1024): checksum.update(data); count += len(data)
    if count != size: raise ValueError('Truncated Git source archive member')
    return checksum.hexdigest()


def verify_git_archive(path, repo, commit):
    """Read-only proof of every tracked Git blob; report unexpanded gitlinks.

    Does not extract or follow archive symlinks. Gitlinks are explicitly listed,
    never silently represented as delivered submodule source. Export-ignored or
    substituted files fail their independent Git object comparison.
    """
    measured = source.measure(path)
    tree, entries = git_entries(repo, commit)
    expected = {p: r for p, r in entries.items() if r['mode'] != '160000'}
    gitlinks = {p: r['oid'] for p, r in entries.items() if r['mode'] == '160000'}
    seen = set(); wrapper = None
    try:
        with tarfile.open(path, 'r:*') as archive:
            for member in archive:
                archive_path(member.name)
                parts = member.name.rstrip('/').split('/')
                if wrapper is None: wrapper = parts[0]
                if parts[0] != wrapper: raise ValueError('Source archive has multiple root prefixes')
                if len(parts) == 1:
                    if not member.isdir(): raise ValueError('Source archive has no root prefix')
                    continue
                relative = '/'.join(parts[1:])
                if member.isdir(): continue
                if relative in seen or relative not in expected: raise ValueError('Unexpected/duplicate Git source member: ' + relative)
                record = expected[relative]; mode = record['mode']
                if mode == '120000':
                    if not member.issym(): raise ValueError('Git source link type differs')
                    data = member.linkname.encode('utf-8')
                    value = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
                else:
                    if (not member.isfile() or bool(member.mode & 0o111) != (mode == '100755')
                            or member.mode & 0o7000): raise ValueError('Git source file type/mode differs')
                    value = blob_hash(archive.extractfile(member), member.size)
                if value != record['oid']: raise ValueError('Git source blob differs: ' + relative)
                seen.add(relative)
    except (tarfile.TarError, EOFError) as error: raise ValueError('Invalid Git source archive') from error
    missing = set(expected) - seen
    if missing: raise ValueError('Missing Git source files: ' + ', '.join(sorted(missing)[:12]))
    if source.measure(path) != measured: raise ValueError('Git source archive changed during verification')
    return {**measured, 'commit': commit, 'tree': tree, 'matchedFiles': len(seen),
            'unexpandedGitlinks': gitlinks, 'correspondingSourceComplete': False}


def restore_git_archive(path, repo, commit, output, read_blob=None):
    """Restore export-ignored/substituted/EOL-converted files to raw Git bytes.

    Keep the original download untouched. A callback may fetch raw source bytes
    from an immutable URL; every returned blob must match the independently read
    Git object ID. Gitlinks stay explicit and require separate module archives.
    No archive is extracted, symlink followed or downloaded program executed.
    """
    path, output = Path(path), Path(output)
    source.no_links(output.parent)
    if os.path.lexists(output): raise FileExistsError('Existing source archive owner is preserved')
    original = source.measure(path)
    tree, entries = git_entries(repo, commit)
    expected = {p:r for p,r in entries.items() if r['mode'] != '160000'}
    if read_blob is None: read_blob = lambda p,r: source.git(repo, 'cat-file', 'blob', r['oid'])
    seen = set(); restored = []; wrapper = None
    fd, temporary = tempfile.mkstemp(prefix='.git-source-', dir=output.parent)
    os.close(fd); temporary = Path(temporary)
    def add(destination, relative, data, reason=None):
        record = expected[relative]
        if data is None or hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest() != record['oid']:
            reason = reason or 'archive blob differs from immutable Git object'
            data = read_blob(relative, record)
            if hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest() != record['oid']:
                raise ValueError('Immutable Git blob differs: '+relative)
        info = tarfile.TarInfo('source/'+relative)
        if record['mode'] == '120000':
            info.type = tarfile.SYMTYPE; info.linkname = data.decode('utf-8'); info.mode = 0o777
            destination.addfile(info)
        else:
            info.mode = 0o755 if record['mode'] == '100755' else 0o644; info.size = len(data)
            destination.addfile(info, io.BytesIO(data))
        if reason: restored.append({'path': relative, 'gitBlob': record['oid'], 'reason': reason})
    try:
        with temporary.open('wb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode='w|', format=tarfile.PAX_FORMAT) as destination:
                with tarfile.open(path, 'r|*') as archive:
                    for member in archive:
                        archive_path(member.name); parts = member.name.rstrip('/').split('/')
                        if wrapper is None: wrapper = parts[0]
                        if parts[0] != wrapper: raise ValueError('Source archive has multiple root prefixes')
                        if len(parts)==1:
                            if not member.isdir(): raise ValueError('Source archive has no root prefix')
                            continue
                        relative = '/'.join(parts[1:])
                        if member.isdir(): continue
                        if relative in seen or relative not in expected: raise ValueError('Unexpected/duplicate Git source member: '+relative)
                        if member.issym() and expected[relative]['mode']=='120000': data=member.linkname.encode('utf-8')
                        elif member.isfile() and expected[relative]['mode']!='120000': data=archive.extractfile(member).read()
                        else: raise ValueError('Unsupported Git source member type')
                        add(destination, relative, data); seen.add(relative)
                for relative in sorted(set(expected)-seen): add(destination, relative, None, 'tracked file omitted by source host archive')
        proof = verify_git_archive(temporary, repo, commit)
        if source.measure(path) != original: raise ValueError('Original Git download changed during restoration')
        os.link(temporary, output)
        return {**proof, 'originalArchive': original, 'restoredFiles': restored,
                'file': output.name, 'licenseReviewComplete': False}
    finally: temporary.unlink(missing_ok=True)


def remote_blob_reader(repository, commit):
    """Fetch raw data only; restore_git_archive independently authenticates it."""
    parsed = urlsplit(repository)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or not re.fullmatch('[a-f0-9]{40}', commit)):
        raise ValueError('Immutable HTTPS source repository required')
    project = parsed.path.removesuffix('.git').strip('/')
    archive_path(project)
    if parsed.hostname == 'github.com': prefix = 'https://raw.githubusercontent.com/'+project+'/'+commit+'/'
    elif parsed.hostname in ('gitlab.freedesktop.org', 'gitlab.xiph.org', 'invent.kde.org'):
        prefix = 'https://'+parsed.netloc+'/'+project+'/-/raw/'+commit+'/'
    else: raise ValueError('Unsupported raw-source host; use local Git blobs')
    def read(path, record):
        archive_path(path)
        return subprocess.check_output(['curl','--fail','--silent','--show-error','--location',
            '--proto','=https','--proto-redir','=https','--connect-timeout','25','--max-time','90',
            '--max-filesize',str(64*1024*1024),prefix+quote(path)], stderr=subprocess.PIPE)
    return read


def materialized_plan(receipt, cache, inventory, inventory_sha256):
    """Verify a separately reviewed receipt and prepare the existing tar gate.

    This is byte/owner verification against that receipt, not independent proof
    that its provenance claims establish the original producer's complete source.
    Extra cache files are never selected into the source-only collection.
    """
    if (receipt.get('schema') != 1 or receipt.get('correspondingSourceComplete') is not False
            or receipt.get('licenseReviewComplete') is not False
            or receipt.get('inventorySha256') != inventory_sha256):
        raise ValueError('Materialization receipt/inventory binding or clearance differs')
    known = {p['name'] for p in inventory['packages']}
    records = {}; material = {}; cases = {}
    for entry in receipt['materials']:
        path = entry['path']; source.safe_path(path, cases)
        if path in records: raise ValueError('Duplicate materialized source path')
        if (entry['kind'] not in ('upstream-source-archive','git-source-archive')
                or not entry['owners'] or entry['owners'] != sorted(set(entry['owners']))
                or not set(entry['owners']) <= known):
            raise ValueError('Invalid materialized source kind/owner')
        if entry['kind']=='git-source-archive' and (
                not re.fullmatch('[a-f0-9]{40}', entry['commit'])
                or not re.fullmatch('[a-f0-9]{40}', entry['tree'])):
            raise ValueError('Immutable materialized Git binding required')
        actual = Path(cache)/path
        if source.measure(actual) != {k:entry[k] for k in ('bytes','sha256')}:
            raise ValueError('Materialized source bytes differ: '+path)
        records[path] = {k:entry[k] for k in ('bytes','sha256')}; records[path]['mode'] = 0o644
        material[path] = actual
    plan = source.new_plan({'materializationReceiptSha256':source.digest(source.canonical(receipt)),
        'inventorySha256':inventory_sha256,
        'scope':'Reviewed available source materials only; unresolved producer inputs remain outside this collection'}, records)
    return plan, material


def collection_main():
    parser = argparse.ArgumentParser(description='Verify reviewed materialized sources; optionally collect using the strict tar gate')
    parser.add_argument('operation', choices=['collection-check','collection-create'])
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--inventory', type=Path, default=Path(__file__).with_name('inventory.json'))
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--output', type=Path)
    args=parser.parse_args()
    if args.operation=='collection-create' and (not args.plan or not args.output): parser.error('Creation requires new plan and output paths')
    if args.operation=='collection-check' and (args.plan or args.output): parser.error('Read-only check does not create files')
    for p in [args.plan,args.output]:
        if p and os.path.lexists(p): raise FileExistsError('Existing collection owner is preserved')
    receipt=source.read_json(args.receipt)
    plan,material=materialized_plan(receipt,args.cache,source.read_json(args.inventory),source.measure(args.inventory)['sha256'])
    if args.operation=='collection-create':
        result=source.collect(plan,material,args.output)
        with args.plan.open('xb') as stream:stream.write(source.canonical(plan)+b'\n')
    else: result={'verifiedFiles':len(material),'bytes':sum(v['bytes'] for v in plan['files'].values()),
                  'correspondingSourceComplete':False,'licenseReviewComplete':False}
    print(json.dumps(result,indent=2))


def git_main():
    parser = argparse.ArgumentParser(description='Verify raw Git source; optionally restore host archive transformations')
    parser.add_argument('operation', choices=['git-verify','git-restore'])
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--raw-repository', help='Fetch changed/missing blobs from this source host; Git OIDs are still required')
    args = parser.parse_args()
    if args.operation == 'git-verify':
        if args.output or args.raw_repository: parser.error('Verification does not create output or fetch raw URLs')
        result = verify_git_archive(args.archive, args.repo, args.commit)
    else:
        if not args.output: parser.error('Restoration requires a new output path')
        reader = remote_blob_reader(args.raw_repository, args.commit) if args.raw_repository else None
        result = restore_git_archive(args.archive, args.repo, args.commit, args.output, reader)
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, default=Path(__file__).with_name('inventory.json'))
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    if os.path.lexists(args.receipt): raise FileExistsError('Existing materialization receipt is preserved')
    args.cache.mkdir(parents=True, exist_ok=True); source.no_links(args.cache)
    requests = archive_requests(source.read_json(args.inventory))
    def run(request):
        try:
            result = fetch_archive(request, args.cache)
            print(json.dumps({'owners': request['owners'], 'bytes': result['bytes'], 'status': 'verified'}), flush=True)
            return {'status': 'verified', **result}
        except Exception as error:
            result = {'status': 'failed', 'request': request, 'error': str(error)}
            print(json.dumps({'owners': request['owners'], 'status': 'failed', 'error': str(error)}), flush=True)
            return result
    with ThreadPoolExecutor(max_workers=5) as pool: results = list(pool.map(run, requests))
    receipt = {'schema': 1, 'inventorySha256': source.measure(args.inventory)['sha256'],
               'correspondingSourceComplete': False, 'licenseReviewComplete': False, 'results': results}
    with args.receipt.open('xb') as output: output.write(source.canonical(receipt) + b'\n')
    print(json.dumps({'verified': sum(r['status'] == 'verified' for r in results), 'requested': len(results)}))
    if any(r['status'] != 'verified' for r in results): raise SystemExit(1)


if __name__ == '__main__':
    if len(sys.argv)>1 and sys.argv[1].startswith('git-'): git_main()
    elif len(sys.argv)>1 and sys.argv[1].startswith('collection-'): collection_main()
    else: main()
