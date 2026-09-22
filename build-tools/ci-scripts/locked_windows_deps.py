# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
"""Locked, non-publishing Windows dependency preparation. Python standard library only.

Archives are immutable inputs, never commands. Existing cache/stage files are not
replaced. Verification derives file hashes from the locked archives again instead
of trusting the mutable installed receipt. This is not a hostile-filesystem CAS.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tarfile
import tempfile
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zipfile

MANIFEST = '.brushquay-inputs.json'
HEX40 = re.compile(r'[0-9a-f]{40}\Z')
HEX64 = re.compile(r'[0-9a-f]{64}\Z')
NAME = re.compile(r'[a-zA-Z0-9_.-]+\Z')
DEVICE = re.compile(r'(con|prn|aux|nul|com[0-9¹²³]|lpt[0-9¹²³])(?:\..*)?\Z', re.IGNORECASE)
CHUNK = 1024 * 1024


class LockError(RuntimeError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def relative_name(name):
    if not isinstance(name, str) or not name or '\\' in name or ':' in name or '\x00' in name:
        raise LockError('Invalid Windows archive path: ' + repr(name))
    parts = name.split('/')
    for part in parts:
        if part in ('', '.', '..') or part.endswith(('.', ' ')) or DEVICE.fullmatch(part):
            raise LockError('Unsafe Windows archive path: ' + repr(name))
        if any(ord(c) < 32 or c in '<>"|?*' for c in part):
            raise LockError('Invalid Windows filename: ' + repr(name))
    return '/'.join(parts)


def checked_url(url):
    value = urllib.parse.urlsplit(url)
    if value.scheme != 'https' or not value.hostname or value.username or value.password or value.fragment:
        raise LockError('Only explicit credential-free HTTPS archive URLs are accepted')


def load_lock(path):
    try:
        lock = json.loads(Path(path).read_text(encoding='utf-8'))
        if lock['schema'] != 1 or not HEX40.fullmatch(lock['applicationSourceCommit']):
            raise LockError('Unsupported lock schema or unpinned application source')
        packages = lock['packages']
        if not packages or not isinstance(packages, list):
            raise LockError('A nonempty package lock is required')
        names = set()
        for package in packages:
            name = package['name']
            if not NAME.fullmatch(name) or name in names:
                raise LockError('Duplicate or invalid package name: ' + name)
            names.add(name)
            if not HEX64.fullmatch(package['sha256']) or not HEX40.fullmatch(package['sourceCommit']):
                raise LockError('Package must pin full SHA-256 and source commit: ' + name)
            if type(package['bytes']) is not int or package['bytes'] <= 0:
                raise LockError('Package size must be a positive integer: ' + name)
            if package['archive'] not in ('tar', 'zip') or not package['version']:
                raise LockError('Explicit package archive type/version required: ' + name)
            checked_url(package['url'])
            relative_name(package['stagePrefix'])
            if package['stagePrefix'] != 'deps' and not package['stagePrefix'].startswith('tools/'):
                raise LockError('Packages must be separated into deps or tools prefixes')
            if package.get('stripPrefix'):
                relative_name(package['stripPrefix'])
            if 'metadata' in package:
                checked_url(package['metadata']['url'])
                if not HEX64.fullmatch(package['metadata']['sha256']):
                    raise LockError('Package metadata must be hashed')
        for package in packages:
            if not isinstance(package['dependencies'], list) or set(package['dependencies']) - names:
                raise LockError('Dependency closure is incomplete: ' + package['name'])
        for repository in lock.get('sourceRepositories', []):
            if not HEX40.fullmatch(repository['commit']) or not HEX40.fullmatch(repository['tree']):
                raise LockError('Source repositories must pin full commit and tree IDs')
            checked_url(repository['url'])
        return lock
    except (KeyError, TypeError, ValueError) as error:
        raise LockError('Malformed dependency lock: ' + str(error)) from error


def input_artifacts(lock):
    result = {}
    for package in lock['packages']:
        result[package['sha256']] = package
        if 'metadata' in package:
            metadata = dict(package['metadata'])
            metadata['bytes'] = None
            result[metadata['sha256']] = metadata
    return result


def check_cache_entries(lock, cache):
    if cache.is_symlink() or not cache.is_dir():
        raise LockError('Cache must be a real directory')
    allowed = set(input_artifacts(lock))
    extra = {p.name for p in cache.iterdir()} - allowed
    if extra:
        raise LockError('Cache contains unlocked entries: ' + ', '.join(sorted(extra)))


def open_regular(path):
    try:
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode):
            raise LockError('Input must be a regular file: ' + str(path))
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0))
        stream = os.fdopen(fd, 'rb')
        after = os.fstat(stream.fileno())
        if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
            stream.close()
            raise LockError('Input identity changed while opening: ' + str(path))
        return stream
    except OSError as error:
        raise LockError('Cannot read input: ' + str(path) + ': ' + str(error)) from error


def hash_stream(stream):
    checksum, count = hashlib.sha256(), 0
    while chunk := stream.read(CHUNK):
        checksum.update(chunk)
        count += len(chunk)
    return checksum.hexdigest(), count


def verify_artifact(path, artifact):
    with open_regular(path) as stream:
        digest, size = hash_stream(stream)
    if digest != artifact['sha256'] or (artifact.get('bytes') is not None and size != artifact['bytes']):
        raise LockError('Locked hash/size mismatch: ' + str(path))


def fetch_one(artifact, cache, opener):
    destination = cache / artifact['sha256']
    if os.path.lexists(destination):
        verify_artifact(destination, artifact)
        return
    fd, temporary = tempfile.mkstemp(prefix='.download-', dir=cache)
    temporary = Path(temporary)
    try:
        checksum, count = hashlib.sha256(), 0
        limit = artifact.get('bytes') or 16 * 1024 * 1024
        request = urllib.request.Request(artifact['url'], headers={'User-Agent': 'BrushQuay-locked-build/1'})
        with os.fdopen(fd, 'wb') as output, opener(request, timeout=60) as response:
            while chunk := response.read(CHUNK):
                count += len(chunk)
                if count > limit:
                    raise LockError('Download exceeded its locked size: ' + artifact['url'])
                checksum.update(chunk)
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        if checksum.hexdigest() != artifact['sha256'] or (artifact.get('bytes') is not None and count != artifact['bytes']):
            raise LockError('Download hash/size did not match lock: ' + artifact['url'])
        try:
            os.link(temporary, destination)
        except FileExistsError:
            # A competing cache writer may only supply these same pinned bytes.
            verify_artifact(destination, artifact)
    except urllib.error.URLError as error:
        raise LockError('Download failed for ' + artifact['url'] + ' (SHA256 ' + artifact['sha256'] + '): ' + str(error)) from error
    finally:
        temporary.unlink(missing_ok=True)


def check_metadata(package, cache):
    if 'metadata' not in package:
        return
    artifact = package['metadata']
    verify_artifact(cache / artifact['sha256'], artifact)
    with open_regular(cache / artifact['sha256']) as stream:
        metadata = json.load(stream)
    checks = {'identifier': package['name'], 'version': package['version'],
              'gitRevision': package['sourceCommit'], 'sha256sum': package['sha256']}
    if any(metadata.get(key) != value for key, value in checks.items()):
        raise LockError('Frozen registry metadata contradicts package lock: ' + package['name'])
    actual_dependencies = set(metadata.get('dependencies', {})) | set(metadata.get('runtime-dependencies', {}))
    if actual_dependencies != set(package['dependencies']):
        raise LockError('Registry dependency closure contradicts package lock: ' + package['name'])


def fetch_all(lock, cache, opener=urllib.request.urlopen):
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    check_cache_entries(lock, cache)
    for artifact in input_artifacts(lock).values():
        fetch_one(artifact, cache, opener)
    for package in lock['packages']:
        check_metadata(package, cache)


def destination_name(package, name):
    name = relative_name(name)
    strip = package.get('stripPrefix', '')
    if strip:
        if not name.startswith(strip + '/'):
            raise LockError('Archive path is outside its locked prefix: ' + name)
        name = name[len(strip) + 1:]
    return relative_name(package['stagePrefix'] + '/' + name)


def archive_files(package, cache):
    """Yield safe regular members plus resolved same-archive hardlinks, never extractall."""
    with open_regular(cache / package['sha256']) as stream:
        digest, size = hash_stream(stream)
        if digest != package['sha256'] or size != package['bytes']:
            raise LockError('Archive changed or is corrupt: ' + package['name'])
        stream.seek(0)
        if package['archive'] == 'tar':
            with tarfile.open(fileobj=stream, mode='r:*') as archive:
                members = {}
                for member in archive.getmembers():
                    if member.isdir():
                        continue
                    relative_name(member.name)
                    if member.name in members:
                        raise LockError('Duplicate archive member: ' + member.name)
                    if not member.isfile() and not member.islnk():
                        raise LockError('Symlink/special archive member refused: ' + member.name)
                    members[member.name] = member
                for member in members.values():
                    target, visited = member, set()
                    while target.islnk():
                        link = relative_name(target.linkname)
                        if link in visited or link not in members:
                            raise LockError('Hardlink is cyclic or outside its archive: ' + member.name)
                        visited.add(link)
                        target = members[link]
                    if target.size > package['bytes'] * 20:
                        raise LockError('Expanded member exceeds safety limit')
                    with archive.extractfile(target) as payload:
                        yield destination_name(package, member.name), target.size, payload
        else:
            with zipfile.ZipFile(stream) as archive:
                seen = set()
                for member in archive.infolist():
                    if member.is_dir():
                        continue
                    mode = member.external_attr >> 16
                    if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFREG)):
                        raise LockError('Special ZIP member refused: ' + member.filename)
                    if member.filename in seen or member.flag_bits & 1:
                        raise LockError('Duplicate/encrypted ZIP member refused: ' + member.filename)
                    seen.add(member.filename)
                    if member.file_size > package['bytes'] * 20:
                        raise LockError('Expanded member exceeds safety limit')
                    with archive.open(member) as payload:
                        yield destination_name(package, member.filename), member.file_size, payload
        stream.seek(0)
        if hash_stream(stream) != (package['sha256'], package['bytes']):
            raise LockError('Archive changed during staging: ' + package['name'])


def register_case(path, cases):
    parts = path.split('/')
    for i in range(1, len(parts) + 1):
        value = '/'.join(parts[:i])
        key = unicodedata.normalize('NFC', value).casefold()
        if key in cases and cases[key] != value:
            raise LockError('Windows case/Unicode path alias: ' + value + ' and ' + cases[key])
        cases[key] = value


def inventory(lock, cache, root, write):
    files, cases = {}, {}
    for package in lock['packages']:
        check_metadata(package, cache)
        for name, expected_size, payload in archive_files(package, cache):
            register_case(name, cases)
            target = root / name
            checksum, count = hashlib.sha256(), 0
            output = None
            try:
                if write and name not in files:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    output = target.open('xb')
                while chunk := payload.read(CHUNK):
                    checksum.update(chunk)
                    count += len(chunk)
                    if count > expected_size:
                        raise LockError('Archive member exceeds header size: ' + name)
                    if output:
                        output.write(chunk)
            finally:
                if output:
                    output.close()
            if count != expected_size:
                raise LockError('Truncated archive member: ' + name)
            record = {'sha256': checksum.hexdigest(), 'bytes': count, 'owners': [package['name']]}
            if name in files:
                previous = files[name]
                if previous['sha256'] != record['sha256'] or previous['bytes'] != count or package['name'] in previous['owners']:
                    raise LockError('Package file conflict; no override is allowed: ' + name)
                previous['owners'].append(package['name'])
            else:
                files[name] = record
            if not write:
                verify_artifact(target, record)
    for record in files.values():
        record['owners'].sort()
    return {'schema': 1, 'lockSha256': sha(canonical(lock)), 'licenseAuditComplete': False,
            'files': dict(sorted(files.items()))}


def publish_directory_no_replace(source, destination):
    try:
        if sys.platform == 'win32':
            os.rename(source, destination)  # Windows rename refuses an existing destination.
        elif sys.platform == 'darwin':
            library = ctypes.CDLL(None, use_errno=True)
            rename = library.renamex_np
            rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
            if rename(os.fsencode(source), os.fsencode(destination), 4):  # RENAME_EXCL
                raise OSError(ctypes.get_errno(), 'No-replace directory rename failed')
        elif sys.platform.startswith('linux'):
            library = ctypes.CDLL(None, use_errno=True)
            rename = library.renameat2
            rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
            if rename(-100, os.fsencode(source), -100, os.fsencode(destination), 1):
                raise OSError(ctypes.get_errno(), 'No-replace directory rename failed')
        else:
            raise LockError('Native no-replace directory publication unavailable')
    except (OSError, AttributeError) as error:
        raise LockError(str(error)) from error


def stage_all(lock, cache, stage):
    cache, stage = Path(cache), Path(stage)
    check_cache_entries(lock, cache)
    if os.path.lexists(stage):
        raise LockError('Existing stage is never replaced: ' + str(stage))
    stage.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.brushquay-stage-', dir=stage.parent))
    try:
        manifest = inventory(lock, cache, temporary, True)
        (temporary / MANIFEST).write_bytes(canonical(manifest) + b'\n')
        publish_directory_no_replace(temporary, stage)
        return manifest
    except Exception as error:
        raise LockError('Stage was not published; partial files retained at ' + str(temporary) + ': ' + str(error)) from error


def verify_stage(lock, cache, stage):
    cache, stage = Path(cache), Path(stage)
    check_cache_entries(lock, cache)
    if stage.is_symlink() or not stage.is_dir():
        raise LockError('Stage must be a real directory')
    actual = set()
    for parent, directories, files in os.walk(stage, followlinks=False):
        for name in directories + files:
            if (Path(parent) / name).is_symlink():
                raise LockError('Stage contains a symbolic link')
        actual.update((Path(parent) / name).relative_to(stage).as_posix() for name in files)
    expected = inventory(lock, cache, stage, False)
    if actual != set(expected['files']) | {MANIFEST}:
        raise LockError('Installed file set differs from the locked archive set')
    with open_regular(stage / MANIFEST) as stream:
        stored = json.load(stream)
    if stored != expected:
        raise LockError('Installed receipt differs from locked archive inventory')
    return expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('fetch', 'stage', 'verify'))
    parser.add_argument('--lock', type=Path, default=Path(__file__).with_name('brushquay-dependency-lock.json'))
    parser.add_argument('--cache', type=Path, default=Path('.brushquay/cache'))
    parser.add_argument('--stage', type=Path, default=Path('.brushquay/locked'))
    args = parser.parse_args()
    try:
        lock = load_lock(args.lock)
        if args.action == 'fetch':
            fetch_all(lock, args.cache)
            print('Verified all locked archives and metadata; no package was executed or published.')
        elif args.action == 'stage':
            result = stage_all(lock, args.cache, args.stage)
            print('Staged', len(result['files']), 'verified files at', args.stage)
        else:
            result = verify_stage(lock, args.cache, args.stage)
            print('Verified', len(result['files']), 'files against the exact locked archives.')
    except (LockError, OSError, ValueError) as error:
        parser.exit(1, 'BrushQuay dependency preparation failed: ' + str(error) + '\n')


if __name__ == '__main__':
    main()
