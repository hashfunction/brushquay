"""Bounded integrity checks for the source-owned original notice catalog."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import unittest
import tempfile
import subprocess
import shutil
import struct

ROOT = Path(__file__).resolve().parent / 'original-notices'


def validate(root, catalog):
    declared = set()
    for row in catalog['files']:
        name = row['path']
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or name in declared:
            raise ValueError('Unsafe or duplicate notice path')
        declared.add(name)
        target = root / name
        if target.is_symlink():
            raise ValueError('Notice may not be a symbolic link')
        content = target.read_bytes()
        if len(content) != row['bytes'] or hashlib.sha256(content).hexdigest() != row['sha256']:
            raise ValueError('Original notice byte mismatch: ' + name)
        if content[:2] == b'MZ' or name.lower().endswith(('.dll', '.exe', '.msi', '.cab', '.tar', '.gz', '.7z')):
            raise ValueError('Executable or source archive is not a notice')
        if not row['origins'] or not row['owners']:
            raise ValueError('Missing original provenance or component owner')
    for row in catalog['files']:
        for origin in row['origins']:
            for ref in origin.get('sourceReferences', []):
                if ref['file'] not in declared:
                    raise ValueError('Missing exact excerpt source')
                content = (root / ref['file']).read_bytes()
                if content[ref['byteOffset']:ref['byteOffset'] + ref['byteLength']] != (root / row['path']).read_bytes():
                    raise ValueError('Original excerpt offset mismatch')
    allowed = declared | {'catalog.json', 'THIRD-PARTY-NOTICES.md'}
    actual = {str(p.relative_to(root)).replace('\\', '/') for p in root.rglob('*') if p.is_file()}
    if actual != allowed:
        raise ValueError('Unrecorded or missing notice file')
    for component in catalog['components']:
        if component['selection'] not in ('selected', 'tool-only', 'unknown'):
            raise ValueError('Unknown component selection')
        if not set(component['files']) <= declared:
            raise ValueError('Component points outside catalog')
        for grant in component.get('primaryRuntimeGrants', []):
            if not grant['expression'] or not grant['scope'] or not grant['evidence']:
                raise ValueError('Incomplete primary runtime grant')
            if not set(grant['files']) <= set(component['files']):
                raise ValueError('Primary grant points outside component')
            if not grant['runtimeFiles'] or not set(grant['runtimeFiles']) <= set(component['selectedRuntimeFiles']):
                raise ValueError('Primary grant points outside selected runtime')
            for proof in grant['evidence']:
                if proof['file'] not in grant['files'] or not proof['contains']:
                    raise ValueError('Primary grant lacks original proof')
                content = (root / proof['file']).read_text(errors='replace')
                if any(literal not in content for literal in proof['contains']):
                    raise ValueError('Primary grant original proof mismatch')
    for group in catalog['associations']:
        if group['selection'] not in ('selected', 'conditional', 'tool-only', 'not-selected', 'separate-owner', 'unknown'):
            raise ValueError('Unknown notice association')
        if not set(group['files']) <= declared:
            raise ValueError('Association points outside catalog')
    serialized = json.dumps(catalog)
    for forbidden in ('/private/tmp/', '/Users/', 'licenseReviewComplete', 'correspondingSourceComplete', 'finalReleaseReady', 'X-Amz-', 'sig='):
        if forbidden in serialized:
            raise ValueError('Private location or approval assertion in catalog')


class OriginalNoticeIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads((ROOT / 'catalog.json').read_text())

    def test_original_bytes_and_references(self):
        validate(ROOT, self.catalog)

    def test_existing_original_collection_is_complete(self):
        original = [r for r in self.catalog['files'] if 'original-918-collection' in r['roles']]
        self.assertEqual(len(original), 918)
        self.assertEqual(sum(r['bytes'] for r in original), 6445405)
        blocks = [r for r in self.catalog['files'] if 'original-drmingw-notice-block' in r['roles']]
        self.assertEqual(len(blocks), 116)
        self.assertEqual(sum(r['bytes'] for r in blocks), 114929)

    def test_rejects_byte_count_and_hash_tampering(self):
        for field, replacement in [('bytes', -1), ('sha256', '0' * 64)]:
            bad = json.loads(json.dumps(self.catalog))
            bad['files'][0][field] = replacement
            with self.assertRaisesRegex(ValueError, 'byte mismatch'):
                validate(ROOT, bad)

    def test_rejects_unsafe_or_duplicate_paths(self):
        for replacement in ('../escape', '/absolute', self.catalog['files'][1]['path']):
            bad = json.loads(json.dumps(self.catalog))
            bad['files'][0]['path'] = replacement
            with self.assertRaises(ValueError):
                validate(ROOT, bad)

    def test_real_git_checkout_preserves_original_bytes(self):
        source_root = ROOT.parents[2]
        samples = []
        for suffix in ('.txt', '.docx', '.rtf', '.cpp'):
            samples.append(next(r['path'] for r in self.catalog['files'] if r['path'].endswith(suffix)))
        samples.append(next(r['path'] for r in self.catalog['files'] if b'\r\n' in (ROOT / r['path']).read_bytes()))
        with tempfile.TemporaryDirectory(prefix='brist-notice-checkout-') as temp:
            repo = Path(temp) / 'repo'
            checkout = Path(temp) / 'checkout'
            repo.mkdir()
            checkout.mkdir()
            shutil.copyfile(source_root / '.gitattributes', repo / '.gitattributes')
            for name in samples:
                target = repo / 'distribution/native-source/original-notices' / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, target)
            def git(*args):
                subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True)
            git('init', '-q')
            git('config', 'core.autocrlf', 'true')
            git('add', '.')
            git('checkout-index', '--all', '--prefix=' + str(checkout) + '/')
            for name in samples:
                self.assertEqual((ROOT / name).read_bytes(), (checkout / 'distribution/native-source/original-notices' / name).read_bytes())

    def test_primary_runtime_grants_are_distinct_and_source_bound(self):
        components = {r['id']: r for r in self.catalog['components']}
        expected = {
            'ext_lame': 'LGPL-2.0-or-later', 'ext_libde265': 'LGPL-3.0-or-later',
            'ext_libx265': 'GPL-2.0-or-later', 'ext_openssl': 'OpenSSL',
            'ext_png': 'libpng-2.0', 'ext_sdl2': 'Zlib', 'ext_zlib': 'Zlib',
            'llvm-mingw': 'Apache-2.0 WITH LLVM-exception',
            'ext_python': 'PSF-2.0', 'ext_jpeg': 'IJG AND BSD-3-Clause AND Zlib',
            'ext_gettext': 'LGPL-2.1-or-later', 'ext_icu': 'Unicode-DFS-2016 AND ICU',
            'ext_ffmpeg': 'LGPL-2.1-or-later',
        }
        index = (ROOT / 'THIRD-PARTY-NOTICES.md').read_text()
        for owner, expression in expected.items():
            with self.subTest(owner=owner):
                component = components[owner]
                grants = component.get('primaryRuntimeGrants', [])
                self.assertIn(expression, [g['expression'] for g in grants])
                for grant in grants:
                    self.assertTrue(grant['scope'])
                    self.assertTrue(grant['runtimeFiles'])
                    self.assertLessEqual(set(grant['runtimeFiles']), set(component['selectedRuntimeFiles']))
                    self.assertLessEqual(set(grant['files']), set(component['files']))
                    self.assertTrue(grant['evidence'])
                    for proof in grant['evidence']:
                        self.assertIn(proof['file'], grant['files'])
                        content = (ROOT / proof['file']).read_text(errors='replace')
                        for literal in proof['contains']:
                            self.assertIn(literal, content)
                section = index.split('## ' + owner + '\n', 1)[1].split('\n## ', 1)[0]
                self.assertLess(section.index('Primary runtime grants'), section.index('Other source-file grants'))
        llvm = components['llvm-mingw']['primaryRuntimeGrants']
        self.assertEqual(next(g for g in llvm if 'LLVM-exception' in g['expression'])['runtimeFiles'],
                         ['bin/libc++.dll', 'bin/libomp.dll', 'bin/libunwind.dll'])
        self.assertEqual(next(g for g in llvm if 'bin/libwinpthread-1.dll' in g['runtimeFiles'])['expression'],
                         'MIT AND BSD-3-Clause')
        intl = components['ext_gettext']['primaryRuntimeGrants'][0]
        self.assertEqual(intl['runtimeFiles'], ['bin/intl.dll'])
        self.assertIn('not selected', components['ext_gettext']['primaryGrantNotes'])
        ffmpeg = components['ext_ffmpeg']['producerLicenseConfiguration']
        self.assertEqual(ffmpeg['mesonOptions'], {'gpl': 'disabled', 'version3': 'disabled', 'nonfree': 'disabled'})
        self.assertNotEqual(ffmpeg['evidenceKind'], 'license-template-only')

    def test_primary_grant_refuses_wrong_scope_or_proof(self):
        for field, value in [('files', ['catalog.json']), ('runtimeFiles', ['bin/not-selected.dll']),
                             ('evidence', [{'file': 'catalog.json', 'contains': ['wrong']}])]:
            bad = json.loads(json.dumps(self.catalog))
            component = next(c for c in bad['components'] if c['id'] == 'ext_lame')
            component['primaryRuntimeGrants'][0][field] = value
            with self.assertRaisesRegex(ValueError, 'Primary grant'):
                validate(ROOT, bad)

    def test_ffmpeg_observation_is_exactly_bound_to_selected_dlls(self):
        component = next(c for c in self.catalog['components'] if c['id'] == 'ext_ffmpeg')
        config = component['producerLicenseConfiguration']
        receipt = json.loads((ROOT / config['binaryObservationFile']).read_text())
        self.assertEqual(receipt['archive']['sha256'], component['binaryInput']['binarySha256'])
        self.assertEqual(config['recipeSha256'], component['binaryInput']['recipeFile']['sha256'])
        self.assertEqual(config['retainedPatchCount'], 13)
        self.assertEqual({f['member'] for f in receipt['files']}, set(component['selectedRuntimeFiles']))
        configurations = set()
        for row in receipt['files']:
            selected = component['selectedRuntimeFiles'][row['member']]
            self.assertEqual((row['bytes'], row['sha256']), (selected['bytes'], selected['sha256']))
            prefix = row['member'].split('/lib')[1].split('-')[0]
            self.assertEqual(set(row['exports']), {prefix + '_license', prefix + '_configuration'})
            for name, proof in row['exports'].items():
                instructions = bytes.fromhex(proof['instructionBytes'])
                self.assertEqual((instructions[:3], instructions[7:]), (b'\x48\x8d\x05', b'\xc3'))
                self.assertEqual(proof['returnedStringRva'], proof['functionRva'] + 7 + struct.unpack('<i', instructions[3:7])[0])
                if name.endswith('_license'):
                    self.assertEqual(proof['value'], 'LGPL version 2.1 or later')
                else:
                    configurations.add(proof['value'])
                    for option in ('gpl', 'version3', 'nonfree'):
                        self.assertNotIn('-D' + option + '=', proof['value'])
                    self.assertIn('-Ddefault_library=shared', proof['value'])
        self.assertEqual(len(configurations), 1)

    def test_scoped_qt_and_microsoft_records(self):
        by_id = {r['id']: r for r in self.catalog['associations']}
        self.assertEqual(by_id['qt-grayraster']['selection'], 'selected')
        self.assertEqual(by_id['qt-qtsciicodec']['selection'], 'selected')
        self.assertEqual(by_id['qt-libwebp']['selection'], 'conditional')
        self.assertEqual(by_id['qt-georama-font']['selection'], 'not-selected')
        self.assertIn('end-user', by_id['microsoft-vc-runtime']['basis'])
        self.assertIn('downstream', by_id['microsoft-vc-distribution']['basis'])
        self.assertEqual(len(by_id['microsoft-sdk18362']['runtimeFiles']), 3)
        components = {r['id']: r for r in self.catalog['components']}
        self.assertEqual(components['ext_immer']['selection'], 'unknown')
        self.assertTrue(all(c['identifiedSourceGrants'] for c in components.values() if c['selection'] == 'selected'))


if __name__ == '__main__':
    unittest.main()
