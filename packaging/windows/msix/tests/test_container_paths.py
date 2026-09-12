# SPDX-FileCopyrightText: 2026 Trieflow LLC
# SPDX-License-Identifier: GPL-3.0-or-later
"""Real ZIP boundary regressions for SDK part names; no native install claim."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from build_msix import manifest_bytes
from verify_brushquay_msix import verify_msix


class ContainerPathTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.archive = Path(self.temp.name) / 'fixture.msix'
        self.identity = dict(PackageName='Trieflow.Bristlune.Qualification',
                             Publisher='CN=Bristlune-CI-Qualification', Version='1.0.1.0',
                             MinWindowsVersion='10.0.19041.0', MaxWindowsVersionTested='10.0.26100.0')
        self.manifest = manifest_bytes(self.identity)

    def verify(self, payload, entries):
        expected = dict(payload, **{'AppxManifest.xml': self.manifest})
        expected = {name: {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
                    for name, data in expected.items()}
        with zipfile.ZipFile(self.archive, 'w') as archive:
            archive.writestr('AppxManifest.xml', self.manifest)
            archive.writestr('[Content_Types].xml', '<Types/>')
            archive.writestr('AppxBlockMap.xml', '<BlockMap/>')
            for name, data in entries:
                archive.writestr(name, data)
        return verify_msix(self.archive, expected, self.identity)

    def test_actual_sdk_failure_name_with_original_5711_byte_brush(self):
        name = 'c)_Pencil_1_Sketch_(mypaint).myb'
        # The actual Windows checkout has CRLF; recreate and pin its observed bytes.
        data = (HERE.parents[2] / 'plugins/paintops/mypaint/brushes' / name).read_bytes()
        data = data.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
        self.assertEqual(len(data), 5711)
        self.assertEqual(hashlib.sha256(data).hexdigest(),
                         '67e84826b573159d2ff99446b721851b25318b12b01e067a284fdde4392c360c')
        prefix = 'Bristlune/share/krita/paintoppresets/'
        result = self.verify({prefix + name: data}, [
            (prefix + 'c%29_Pencil_1_Sketch_%28mypaint%29.myb', data)])
        self.assertEqual(result['verifiedPayloadFiles'], 2)

    def test_sdk_punctuation_unicode_and_literal_percent_are_decoded_once(self):
        vectors = [('folder/hello.txt', 'folder/hello.txt'),
                   ('folder/a ()+[]!#$%&\',;=@^`{}.txt',
                    'folder/a%20%28%29%2B%5B%5D%21%23%24%25%26%27%2C%3B%3D%40%5E%60%7B%7D.txt'),
                   ('café/雪.txt', 'caf%C3%A9/%E9%9B%AA.txt'),
                   ('literal%28.txt', 'literal%2528.txt')]
        for name, encoded in vectors:
            with self.subTest(name=name):
                self.assertEqual(self.verify({name: b'original'}, [(encoded, b'original')])['verifiedPayloadFiles'], 2)

    def test_bad_encodings_traversal_and_unexpected_files_refused(self):
        names = ['x%', 'x%2', 'x%GG', '%41.txt', 'a%2bb.txt', 'a%2Fb.txt',
                 'a%5Cb.txt', '%2E%2E/x.txt', 'a%00.txt', 'a%3Astream.txt',
                 'a%20.txt', '%C0%AF.txt', '%ED%A0%80.txt', '%FF.txt',
                 'a%2528.txt', 'a(%20b.txt', 'AppxSignature.p7x',
                 '%5BContent_Types%5D.xml']
        for name in names:
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.verify({'a(b.txt': b'original'}, [(name, b'original')])

    def test_encoded_payload_still_requires_exact_hash_and_complete_tree(self):
        for entries in [[('a%28b.txt', b'mutated!')], []]:
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                self.verify({'a(b.txt': b'original'}, entries)

    def test_noncanonical_alias_refused_even_with_matching_expected_bytes(self):
        for name, encoded in [('A.txt', '%41.txt'), ('a+b.txt', 'a%2bb.txt'),
                              ('dir/a.txt', 'dir%2Fa.txt'), ('a( b.txt', 'a(%20b.txt')]:
            with self.subTest(encoded=encoded), self.assertRaisesRegex(ValueError, '[Nn]oncanonical'):
                self.verify({name: b'original'}, [(encoded, b'original')])

    def test_plain_encoded_case_and_unicode_aliases_refused(self):
        for name, first, second in [('a(b.txt', 'a(b.txt', 'a%28b.txt'),
                                    ('café.txt', 'caf%C3%A9.txt', 'café.txt'),
                                    ('dir name/file.txt', 'dir%20name/file.txt', 'DIR%20name/file.txt'),
                                    ('café.txt', 'caf%C3%A9.txt', 'cafe%CC%81.txt')]:
            with self.subTest(names=(first, second)), self.assertRaises(ValueError):
                self.verify({name: b'original'}, [(first, b'original'), (second, b'original')])

    def test_encoded_directory_is_owned_and_cannot_alias(self):
        payload = {'dir name/a.txt': b'original'}
        self.assertEqual(self.verify(payload, [('dir%20name/', b''),
                         ('dir%20name/a.txt', b'original')])['verifiedPayloadFiles'], 2)
        for entries in [[('dir name/', b''), ('dir%20name/', b''), ('dir%20name/a.txt', b'original')],
                        [('dir%20name', b''), ('dir%20name/a.txt', b'original')],
                        [('foreign%20dir/', b''), ('dir%20name/a.txt', b'original')]]:
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                self.verify(payload, entries)


if __name__ == '__main__':
    unittest.main()
