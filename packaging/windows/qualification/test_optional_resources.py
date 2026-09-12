# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
import copy
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import prepare
import release_inputs
from runtime_stage import measure, measure_tree


class OptionalResourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.selected = {}
        for name in (*release_inputs.OPTIONAL_TLS, 'plugins/tls/qschannelbackend.dll',
                     'python/libcrypto-3.dll', 'python/libssl-3.dll', 'bin/bristlune.exe'):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(('fixture:' + name).encode())
            self.selected[name] = dict(measure(path), inputs=[{'tree': 'locked', 'path': 'deps/' + name, 'owners': ['fixture']}])
        self.group = {name: measure(self.root / name) for name in release_inputs.OPTIONAL_TLS}
        self.context = dict(sourceCommit='a'*40, sourceTree='b'*40, workflowRunId='1',
                            workflowRunAttempt='1', nativeEvidence={'bytes': 1, 'sha256': 'c'*64}, lockSha256='d'*64)
        rows = [dict(value, path=name, normalImports=[], delayImports=[]) for name, value in self.selected.items()]
        self.graph = dict(self.context, status='observed', errors=[], selectedPeFiles=len(rows), files=rows)

    def omit(self, graph=None):
        # Only fixture byte pins differ; the real three-name group and production guard are used.
        with patch.object(prepare, 'OPTIONAL_TLS', self.group), patch.object(release_inputs, 'OPTIONAL_TLS', self.group):
            return prepare.omit_optional_tls(self.root, self.selected, graph or self.graph, self.context)

    def test_only_reviewed_three_files_removed_after_complete_graph(self):
        before = copy.deepcopy(self.selected)
        retained = self.omit()
        self.assertEqual(retained, {k: v for k, v in before.items() if k not in self.group})
        self.assertEqual(measure_tree(self.root), {k: {f: v[f] for f in ('bytes', 'sha256')} for k, v in retained.items()})
        self.assertEqual(self.selected, before)
        self.assertIn('plugins/tls/qschannelbackend.dll', retained)
        self.assertIn('python/libcrypto-3.dll', retained)
        self.assertIn('python/libssl-3.dll', retained)

    def test_edge_delay_stale_missing_and_failed_graph_preserve_owned_files(self):
        before = measure_tree(self.root)
        for kind in ('normalImports', 'delayImports', 'stale', 'missing', 'failed'):
            bad = copy.deepcopy(self.graph)
            if kind.endswith('Imports'):
                bad['files'][-1][kind] = [{'library': 'libssl-1_1-x64.dll'}]
            elif kind == 'stale': bad['workflowRunAttempt'] = '2'
            elif kind == 'missing': bad['files'].pop()
            else: bad['status'] = 'incomplete'
            with self.subTest(kind=kind), self.assertRaises(ValueError): self.omit(bad)
            self.assertEqual(measure_tree(self.root), before)

    def test_changed_or_extra_file_prevents_any_removal(self):
        for name in (next(iter(self.group)), 'foreign.txt'):
            path = self.root / name
            original = path.read_bytes() if path.exists() else None
            path.write_bytes(b'changed')
            before = measure_tree(self.root)
            with self.subTest(name=name), self.assertRaises(ValueError): self.omit()
            self.assertEqual(measure_tree(self.root), before)
            if original is None: path.unlink()
            else: path.write_bytes(original)

    def test_actual_bundle_cmake_install_preserves_only_other_original_bundles(self):
        source = prepare.ROOT / 'krita/data/bundles'
        project = self.root / 'project'
        project.mkdir()
        (project / 'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.16)\nproject(BundleInstall NONE)\nset(KDE_INSTALL_DATADIR share)\nadd_subdirectory("' + str(source) + '" bundles)\n')
        build = self.root / 'build'
        output = self.root / 'installed'
        subprocess.run(['cmake', '-S', str(project), '-B', str(build)], check=True, capture_output=True)
        subprocess.run(['cmake', '--install', str(build), '--prefix', str(output)], check=True, capture_output=True)
        names = {'README', 'Krita_3_Default_Resources.bundle', 'Krita_4_Default_Resources.bundle', 'RGBA_brushes.bundle'}
        observed = measure_tree(output)
        self.assertEqual(observed, {'share/krita/bundles/' + name: measure(source / name) for name in names})
        self.assertEqual(hashlib.sha256((source / 'Krita_Artists_SeExpr_examples.bundle').read_bytes()).hexdigest(),
                         '5e0a5a97fb31ab1b8840e3df03c64bb410d61166e5824d8b46d168bdc109a15c')


if __name__ == '__main__': unittest.main()
