# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest import mock
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import locked_windows_deps as deps


def digest(data):
    return hashlib.sha256(data).hexdigest()


class LockedWindowsDepsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='brushquay-lock-test-')
        self.root = Path(self.tmp.name)
        self.cache = self.root / 'cache'
        self.cache.mkdir()
        self.stage = self.root / 'stage'
        self.responses = {}
        self.lock = {'schema': 1, 'applicationSourceCommit': 'a' * 40,
                     'licenseAuditComplete': False, 'packages': [], 'sourceRepositories': []}

    def tearDown(self):
        self.tmp.cleanup()

    def package(self, name, files, links=None, archive_type='tar', prefix='deps', strip=''):
        data = io.BytesIO()
        if archive_type == 'tar':
            with tarfile.open(fileobj=data, mode='w') as archive:
                for path, payload in files.items():
                    member = tarfile.TarInfo(path)
                    member.size = len(payload)
                    archive.addfile(member, io.BytesIO(payload))
                for path, (kind, target) in (links or {}).items():
                    member = tarfile.TarInfo(path)
                    member.type, member.linkname = kind, target
                    archive.addfile(member)
        else:
            with zipfile.ZipFile(data, 'w') as archive:
                for path, payload in files.items():
                    archive.writestr(path, payload)
        payload = data.getvalue()
        package = {'name': name, 'url': 'https://fixtures.invalid/' + name,
                   'sha256': digest(payload), 'bytes': len(payload), 'archive': archive_type,
                   'stagePrefix': prefix, 'stripPrefix': strip,
                   'sourceCommit': 'b' * 40, 'version': 'exact-1', 'dependencies': [],
                   'licenseClearance': False, 'sourceDeliveryComplete': False}
        self.lock['packages'].append(package)
        self.responses[package['url']] = payload
        return package

    def freeze(self):
        path = self.root / 'lock.json'
        path.write_text(json.dumps(self.lock), encoding='utf-8')
        return deps.load_lock(path)

    def fetch(self, lock):
        def opener(request, **kwargs):
            return io.BytesIO(self.responses[request.full_url])
        deps.fetch_all(lock, self.cache, opener=opener)

    def test_exact_archives_create_verifiable_stage_with_shared_owners(self):
        self.package('one', {'bin/app.dll': b'native', 'share/common': b'same'})
        self.package('two', {'share/common': b'same', 'include/header.h': b'header'})
        lock = self.freeze()
        self.fetch(lock)
        manifest = deps.stage_all(lock, self.cache, self.stage)
        self.assertEqual((self.stage / 'deps/bin/app.dll').read_bytes(), b'native')
        self.assertEqual(manifest['files']['deps/share/common']['owners'], ['one', 'two'])
        self.assertEqual(deps.verify_stage(lock, self.cache, self.stage), manifest)

    def test_hash_mismatch_never_enters_cache_or_stage(self):
        package = self.package('one', {'bin/app.dll': b'native'})
        self.responses[package['url']] = b'corrupt'
        with self.assertRaises(deps.LockError):
            self.fetch(self.freeze())
        self.assertEqual(list(self.cache.iterdir()), [])
        self.assertFalse(self.stage.exists())

    def test_does_not_replace_corrupt_cache_entry(self):
        package = self.package('one', {'bin/app.dll': b'native'})
        cache_file = self.cache / package['sha256']
        cache_file.write_bytes(b'unapproved existing data')
        with self.assertRaises(deps.LockError):
            self.fetch(self.freeze())
        self.assertEqual(cache_file.read_bytes(), b'unapproved existing data')

    def test_unknown_cache_entry_is_rejected(self):
        self.package('one', {'file': b'contents'})
        (self.cache / 'unlocked-package').write_bytes(b'unknown')
        with self.assertRaises(deps.LockError):
            self.fetch(self.freeze())

    def test_safe_same_archive_hardlinks_are_materialized(self):
        self.package('qt', {'bin/qmake.exe': b'executable'}, {'bin/qmake6.exe': (tarfile.LNKTYPE, 'bin/qmake.exe')})
        lock = self.freeze()
        self.fetch(lock)
        deps.stage_all(lock, self.cache, self.stage)
        self.assertEqual((self.stage / 'deps/bin/qmake6.exe').read_bytes(), b'executable')

    def test_traversal_windows_devices_ads_and_aliases_fail_closed(self):
        for path in ['../escaped', '/absolute', 'C:/drive', 'file:stream', 'bin/CON.dll', 'bin/file.', 'bin/file ', 'bin\\escape']:
            with self.subTest(path=path):
                self.lock['packages'] = []
                self.package('bad', {path: b'untrusted'})
                lock = self.freeze()
                cache = self.root / ('cache-' + digest(path.encode()))
                cache.mkdir()
                for package in lock['packages']:
                    (cache / package['sha256']).write_bytes(self.responses[package['url']])
                with self.assertRaises(deps.LockError):
                    deps.stage_all(lock, cache, self.stage)
                self.assertFalse(self.stage.exists())
        self.assertFalse((self.root / 'escaped').exists())

    def test_symlinks_and_escaping_hardlinks_are_rejected(self):
        for kind, target in [(tarfile.SYMTYPE, 'safe'), (tarfile.LNKTYPE, '../outside')]:
            with self.subTest(kind=kind):
                self.lock['packages'] = []
                self.package('bad', {'safe': b'data'}, {'link': (kind, target)})
                lock = self.freeze()
                cache = self.root / ('cache-' + kind.decode())
                cache.mkdir()
                for package in lock['packages']:
                    (cache / package['sha256']).write_bytes(self.responses[package['url']])
                with self.assertRaises(deps.LockError):
                    deps.stage_all(lock, cache, self.stage)
                self.assertFalse(self.stage.exists())

    def test_package_conflict_rejected_without_override(self):
        self.package('one', {'bin/library.dll': b'old'})
        self.package('two', {'bin/library.dll': b'different'})
        lock = self.freeze()
        self.fetch(lock)
        with self.assertRaises(deps.LockError):
            deps.stage_all(lock, self.cache, self.stage)
        self.assertFalse(self.stage.exists())

    def test_case_alias_is_rejected_even_when_bytes_match(self):
        self.package('one', {'bin/A.dll': b'same', 'bin/a.dll': b'same'})
        lock = self.freeze()
        self.fetch(lock)
        with self.assertRaises(deps.LockError):
            deps.stage_all(lock, self.cache, self.stage)

    def test_existing_stage_is_never_replaced(self):
        self.package('one', {'file': b'data'})
        lock = self.freeze()
        self.fetch(lock)
        self.stage.mkdir()
        (self.stage / 'owner').write_bytes(b'original')
        with self.assertRaises(deps.LockError):
            deps.stage_all(lock, self.cache, self.stage)
        self.assertEqual((self.stage / 'owner').read_bytes(), b'original')

    def test_late_stage_owner_is_not_replaced_at_publication(self):
        self.package('one', {'file': b'data'})
        lock = self.freeze()
        self.fetch(lock)
        original = deps.publish_directory_no_replace
        def compete(source, destination):
            destination.mkdir()
            (destination / 'owner').write_bytes(b'late owner')
            return original(source, destination)
        with mock.patch.object(deps, 'publish_directory_no_replace', side_effect=compete):
            with self.assertRaises(deps.LockError):
                deps.stage_all(lock, self.cache, self.stage)
        self.assertEqual((self.stage / 'owner').read_bytes(), b'late owner')

    def test_stage_verification_does_not_trust_modified_receipt(self):
        self.package('one', {'file': b'data'})
        lock = self.freeze()
        self.fetch(lock)
        deps.stage_all(lock, self.cache, self.stage)
        (self.stage / 'deps/file').write_bytes(b'changed')
        receipt = self.stage / deps.MANIFEST
        contents = json.loads(receipt.read_text())
        contents['files']['deps/file']['sha256'] = digest(b'changed')
        contents['files']['deps/file']['bytes'] = 7
        receipt.write_text(json.dumps(contents))
        with self.assertRaises(deps.LockError):
            deps.verify_stage(lock, self.cache, self.stage)

    def test_extra_file_in_stage_is_rejected(self):
        self.package('one', {'file': b'data'})
        lock = self.freeze()
        self.fetch(lock)
        deps.stage_all(lock, self.cache, self.stage)
        (self.stage / 'unlocked.dll').write_bytes(b'not in archive')
        with self.assertRaises(deps.LockError):
            deps.verify_stage(lock, self.cache, self.stage)

    def test_zip_toolchain_prefix_is_exact_and_not_executed(self):
        self.package('compiler', {'compiler/bin/clang.exe': b'not executed'}, archive_type='zip', prefix='tools/llvm', strip='compiler')
        lock = self.freeze()
        self.fetch(lock)
        deps.stage_all(lock, self.cache, self.stage)
        self.assertEqual((self.stage / 'tools/llvm/bin/clang.exe').read_bytes(), b'not executed')

    def test_native_publication_preserves_even_an_empty_competing_directory(self):
        original = self.root / 'original'
        original.mkdir()
        (original / 'payload').write_bytes(b'staged')
        self.stage.mkdir()
        identity = self.stage.stat().st_ino
        with self.assertRaises(deps.LockError):
            deps.publish_directory_no_replace(original, self.stage)
        self.assertEqual(self.stage.stat().st_ino, identity)
        self.assertEqual(list(self.stage.iterdir()), [])
        self.assertEqual((original / 'payload').read_bytes(), b'staged')

    def test_cache_symlink_is_not_followed_or_modified(self):
        package = self.package('one', {'file': b'data'})
        victim = self.root / 'victim'
        victim.write_bytes(b'owner bytes')
        (self.cache / package['sha256']).symlink_to(victim)
        with self.assertRaises(deps.LockError):
            self.fetch(self.freeze())
        self.assertEqual(victim.read_bytes(), b'owner bytes')

    def test_metadata_hash_and_contents_are_both_checked(self):
        package = self.package('one', {'file': b'data'})
        metadata = {'identifier': 'one', 'version': 'wrong-version', 'gitRevision': package['sourceCommit'],
                    'sha256sum': package['sha256'], 'dependencies': {}, 'runtime-dependencies': {}}
        payload = json.dumps(metadata).encode()
        package['metadata'] = {'url': 'https://fixtures.invalid/metadata', 'sha256': digest(payload)}
        self.responses[package['metadata']['url']] = payload
        with self.assertRaises(deps.LockError):
            self.fetch(self.freeze())
        self.assertFalse(self.stage.exists())

    def test_cache_mutation_invalidates_prior_stage_receipt(self):
        package = self.package('one', {'file': b'data'})
        lock = self.freeze()
        self.fetch(lock)
        deps.stage_all(lock, self.cache, self.stage)
        (self.cache / package['sha256']).write_bytes(b'changed archive')
        with self.assertRaises(deps.LockError):
            deps.verify_stage(lock, self.cache, self.stage)

    def test_float_source_or_missing_dependency_or_url_scheme_is_rejected(self):
        package = self.package('one', {'file': b'data'})
        original = copy.deepcopy(package)
        for mutation in [{'sourceCommit': 'master'}, {'dependencies': ['missing']}, {'url': 'file:///secret'}, {'sha256': 'bad'}]:
            with self.subTest(mutation=mutation):
                package.clear()
                package.update(original)
                package.update(mutation)
                with self.assertRaises(deps.LockError):
                    self.freeze()


if __name__ == '__main__':
    unittest.main()
