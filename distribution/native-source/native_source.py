# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
"""Offline source materials: exact Git bytes, deterministic tar, independent verification.

No dependency instructions are executed, no downloads occur, and collection
integrity never changes a license or corresponding-source clearance decision.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'build-tools/ci-scripts'))
from locked_windows_deps import canonical, relative_name, register_case, LockError
sys.path.insert(0, str(ROOT / 'packaging/windows/qualification'))
from runtime_stage import measure, no_links

MANIFEST = 'SOURCE-MATERIALS.json'
HEX40 = re.compile(r'[0-9a-f]{40}\Z')
HEX64 = re.compile(r'[0-9a-f]{64}\Z')
PLAN_KEYS = {'schema', 'kind', 'correspondingSourceComplete', 'licenseReviewComplete',
             'provenance', 'files'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError('Duplicate source JSON key: ' + key)
            result[key] = value
        return result
    def invalid(value): raise ValueError('Non-finite source JSON value: ' + value)
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=pairs, parse_constant=invalid)


def safe_path(name, cases):
    try:
        relative_name(name)
        register_case(name, cases)
    except (LockError, TypeError) as error:
        raise ValueError(str(error)) from error


def new_plan(provenance, files):
    plan = {'schema': 1, 'kind': 'source-materials-only',
            'correspondingSourceComplete': False, 'licenseReviewComplete': False,
            'provenance': provenance, 'files': dict(sorted(files.items()))}
    validate_plan(plan)
    return plan


def validate_plan(plan):
    if (set(plan) != PLAN_KEYS or type(plan['schema']) is not int or plan['schema'] != 1
            or plan['kind'] != 'source-materials-only'
            or plan['correspondingSourceComplete'] is not False
            or plan['licenseReviewComplete'] is not False
            or not isinstance(plan['provenance'], dict) or not plan['provenance']
            or not isinstance(plan['files'], dict) or not plan['files']):
        raise ValueError('Invalid source material plan; clearance is a separate review')
    cases = {}
    safe_path(MANIFEST, cases)
    for name, record in plan['files'].items():
        safe_path(name, cases)
        if name == MANIFEST or set(record) != {'bytes', 'sha256', 'mode'}:
            raise ValueError('Invalid source member record')
        if (type(record['bytes']) is not int or record['bytes'] < 0
                or type(record['mode']) is not int or record['mode'] not in (0o644, 0o755)
                or not isinstance(record['sha256'], str) or not HEX64.fullmatch(record['sha256'])):
            raise ValueError('Invalid source member size/hash/mode')
    # Reject file/directory conflicts, even where the names differ only by case.
    keys = set(cases)
    for name in plan['files']:
        normalized = name.casefold()
        if any(k.startswith(normalized + '/') for k in keys):
            raise ValueError('Source file/directory conflict')


def git(repo, *arguments):
    return subprocess.check_output(['git', '-C', str(repo), *arguments], stderr=subprocess.PIPE)


def git_material(repo, commit, tree, prefix):
    """Read objects, not a mutable checkout or git-archive export substitutions.

    Intentionally refuses gitlinks and symbolic links: a superproject alone must
    not be described as a materialized recursive source tree. Use the audited
    per-repository materials for submodules and retain their linkage separately.
    """
    if not HEX40.fullmatch(commit) or not HEX40.fullmatch(tree):
        raise ValueError('Full immutable Git commit/tree required')
    safe_path(prefix, {})
    if (git(repo, 'cat-file', '-t', commit).strip() != b'commit'
            or git(repo, 'show', '-s', '--format=%T', commit).decode().strip() != tree):
        raise ValueError('Git commit does not match required tree')
    records, material, cases = {}, {}, {}
    listing = git(repo, 'ls-tree', '-rz', '--full-tree', commit)
    for row in listing.split(b'\0'):
        if not row: continue
        metadata, path = row.split(b'\t', 1)
        mode, kind, oid = metadata.decode().split()
        name = prefix + '/' + path.decode('utf-8')
        safe_path(name, cases)
        if mode == '160000': raise ValueError('Unmaterialized Git submodule: ' + name)
        if kind != 'blob' or mode not in ('100644', '100755'):
            raise ValueError('Unsupported source mode: ' + name)
        data = git(repo, 'cat-file', 'blob', oid)
        records[name] = {'bytes': len(data), 'sha256': digest(data),
                         'mode': 0o755 if mode == '100755' else 0o644}
        material[name] = data
    return new_plan({'git': {'commit': commit, 'tree': tree, 'prefix': prefix}}, records), material


def record_material(value, mode=0o644):
    result = {'bytes': len(value), 'sha256': digest(value)} if isinstance(value, bytes) else measure(value)
    return {**result, 'mode': mode}


def open_material(value):
    if isinstance(value, bytes): return io.BytesIO(value)
    no_links(Path(value))
    return Path(value).open('rb')


def info(name, record):
    member = tarfile.TarInfo(name)
    member.size = record['bytes']
    member.mode = record['mode']
    member.mtime = 0
    member.uid = member.gid = 0
    member.uname = member.gname = ''
    return member


def collect(plan, material, output):
    """Write a verified private file and publish through an exclusive hard link."""
    validate_plan(plan)
    output = Path(output)
    no_links(output.parent)
    if os.path.lexists(output): raise FileExistsError('Existing source output is preserved')
    if set(material) != set(plan['files']): raise ValueError('Source material file set differs')
    for name, value in material.items():
        if record_material(value, plan['files'][name]['mode']) != plan['files'][name]:
            raise ValueError('Source material hash/size differs: ' + name)
    fd, temporary = tempfile.mkstemp(prefix='.bristlune-source-', dir=output.parent)
    temporary = Path(temporary)
    try:
        with os.fdopen(fd, 'wb') as stream, tarfile.open(fileobj=stream, mode='w', format=tarfile.PAX_FORMAT) as archive:
            data = canonical(plan) + b'\n'
            archive.addfile(info(MANIFEST, record_material(data)), io.BytesIO(data))
            for name, record in sorted(plan['files'].items()):
                with open_material(material[name]) as source:
                    archive.addfile(info(name, record), source)
        result = verify_collection(temporary, plan)
        # A source changed during collection cannot be silently accepted, even if
        # another input supplied identical output bytes earlier in the operation.
        for name, value in material.items():
            if record_material(value, plan['files'][name]['mode']) != plan['files'][name]:
                raise ValueError('Source material changed during collection: ' + name)
        os.link(temporary, output)  # Never overwrite or unlink a concurrent owner.
        return result
    finally:
        temporary.unlink(missing_ok=True)


class HashOutput:
    def __init__(self): self.sha = hashlib.sha256(); self.position = 0
    def write(self, data): self.sha.update(data); self.position += len(data); return len(data)
    def tell(self): return self.position
    def flush(self): pass


class HashInput:
    def __init__(self, stream): self.stream = stream; self.sha = hashlib.sha256(); self.count = 0
    def read(self, count=-1):
        data = self.stream.read(count); self.sha.update(data); self.count += len(data); return data


def verify_collection(path, plan):
    """Verify against a separately supplied plan, including canonical tar bytes.

    Re-encoding to a hash sink also rejects ignored trailing payload, alternate
    headers, extra PAX data and noncanonical padding without extracting files.
    """
    validate_plan(plan)
    original = measure(path)
    expected_manifest = canonical(plan) + b'\n'
    expected = {MANIFEST: record_material(expected_manifest), **dict(sorted(plan['files'].items()))}
    output = HashOutput()
    try:
        with tarfile.open(path, 'r:') as archive, tarfile.open(fileobj=output, mode='w', format=tarfile.PAX_FORMAT) as canonical_archive:
            for name, record in expected.items():
                member = archive.next()
                if (member is None or member.name != name or not member.isfile()
                        or member.size != record['bytes'] or member.mode != record['mode']
                        or member.uid or member.gid or member.mtime or member.uname or member.gname):
                    raise ValueError('Source archive member set/order/type/metadata differs: ' + name)
                payload = HashInput(archive.extractfile(member))
                canonical_archive.addfile(info(name, record), payload)
                if payload.count != record['bytes'] or payload.sha.hexdigest() != record['sha256']:
                    raise ValueError('Source archive member hash/size differs: ' + name)
            if archive.next() is not None: raise ValueError('Unexpected source archive member')
    except (tarfile.TarError, EOFError) as error:
        raise ValueError('Invalid source archive: ' + str(error)) from error
    if output.position != original['bytes'] or output.sha.hexdigest() != original['sha256']:
        raise ValueError('Source archive is not canonical or contains trailing data')
    if measure(path) != original: raise ValueError('Source archive changed during verification')
    return {**original, 'memberCount': len(plan['files']), 'sourcePlanSha256': digest(expected_manifest),
            'correspondingSourceComplete': False, 'licenseReviewComplete': False}


def recipe_calls(text):
    """Lex selected CMake declarations without evaluating CMake or its conditions.

    The source lock explicitly selects Windows call numbers. This scanner is not
    a CMake interpreter; variables remain literal until individually reviewed.
    """
    # Remove comments while retaining line positions and literal quoted strings.
    chars = list(text); quote = False; i = 0
    while i < len(chars):
        if chars[i] == '\\': i += 2; continue
        if chars[i] == '"': quote = not quote
        elif chars[i] == '#' and not quote:
            end = text.find('\n', i)
            if end < 0: end = len(text)
            chars[i:end] = ' ' * (end - i); i = end; continue
        i += 1
    clean = ''.join(chars)
    pattern = re.compile(r'(?im)^[ \t]*(ExternalProject_Add|kis_ExternalProject_Add_with_separate_builds_apple)\s*\(')
    result = []
    for match in pattern.finditer(clean):
        start = match.end(); i = start; depth = 1; quote = False
        while i < len(clean) and depth:
            char = clean[i]
            if char == '\\': i += 2; continue
            if char == '"': quote = not quote
            elif not quote:
                if char == '(': depth += 1
                elif char == ')': depth -= 1
            i += 1
        if depth or quote: raise ValueError('Unterminated dependency declaration')
        body = clean[start:i-1]
        tokens = re.findall(r'"(?:\\.|[^"\\])*"|[^\s]+', body)
        if not tokens: raise ValueError('Empty dependency declaration')
        record = {'target': tokens[0], 'line': clean[:match.start()].count('\n') + 1,
                  'declarationSha256': digest(text[match.start():i].encode()),
                  'declaration': text[match.start():i]}
        for key in ('URL', 'URL_HASH', 'URL_MD5', 'GIT_REPOSITORY', 'GIT_TAG', 'DOWNLOAD_NAME'):
            positions = [n for n, token in enumerate(tokens) if token == key]
            if len(positions) > 1: raise ValueError('Duplicate dependency source field: ' + key)
            if positions:
                n = positions[0]
                if n + 1 == len(tokens): raise ValueError('Missing dependency source value: ' + key)
                record[key] = tokens[n+1].strip('"')
        result.append(record)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    create = sub.add_parser('git-collect')
    for option in ('repo', 'commit', 'tree', 'prefix', 'output', 'plan'): create.add_argument('--' + option, required=True)
    verify = sub.add_parser('verify')
    verify.add_argument('--archive', required=True); verify.add_argument('--plan', required=True)
    files = sub.add_parser('collect')
    files.add_argument('--plan', required=True); files.add_argument('--materials', required=True)
    files.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.action == 'git-collect':
        no_links(Path(args.plan).parent)
        if os.path.lexists(args.plan): raise FileExistsError('Existing source plan is preserved')
        plan, material = git_material(args.repo, args.commit, args.tree, args.prefix)
        result = collect(plan, material, args.output)
        with open(args.plan, 'xb') as output: output.write(canonical(plan) + b'\n')
    elif args.action == 'collect':
        plan = read_json(args.plan)
        validate_plan(plan)
        root = Path(args.materials)
        no_links(root)
        # Reject undeclared files and links in a collection staging directory.
        from runtime_stage import measure_tree
        if set(measure_tree(root)) != set(plan['files']): raise ValueError('Material directory file set differs')
        result = collect(plan, {name: root / name for name in plan['files']}, args.output)
    else:
        plan = read_json(args.plan)
        result = verify_collection(args.archive, plan)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__': main()
