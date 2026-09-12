# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

import native_source as subject
import inventory_native_sources as inventory


class SourceCollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'user.name', 'Source fixture')
        (self.repo / 'LICENSE').write_text('Original license\n')
        (self.repo / 'build.sh').write_text('#!/bin/sh\nprintf rebuilt\n')
        (self.repo / 'build.sh').chmod(0o755)
        # Export attributes must not silently remove corresponding source.
        (self.repo / '.gitattributes').write_text('LICENSE export-ignore\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'source fixture')
        self.commit = self.git('rev-parse', 'HEAD')
        self.tree = self.git('show', '-s', '--format=%T', 'HEAD')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], text=True).strip()

    def test_deterministic_git_collection_and_independent_verification(self):
        plan, material = subject.git_material(self.repo, self.commit, self.tree, 'recipes')
        self.assertEqual(plan['files']['recipes/build.sh']['mode'], 0o755)
        self.assertIn('recipes/LICENSE', plan['files'])
        one, two = self.root / 'one.tar', self.root / 'two.tar'
        subject.collect(plan, material, one)
        (self.repo / 'LICENSE').write_text('Working copy must not alter immutable source\n')
        plan2, material2 = subject.git_material(self.repo, self.commit, self.tree, 'recipes')
        subject.collect(plan2, material2, two)
        self.assertEqual(one.read_bytes(), two.read_bytes())
        result = subject.verify_collection(one, plan)
        self.assertEqual(result['memberCount'], 3)
        self.assertFalse(result['correspondingSourceComplete'])

    def test_wrong_git_binding_and_unresolved_submodule_are_rejected(self):
        for commit, tree in [('HEAD', self.tree), (self.commit, '0' * 40)]:
            with self.subTest(commit=commit, tree=tree), self.assertRaises(ValueError):
                subject.git_material(self.repo, commit, tree, 'recipes')
        self.git('update-index', '--add', '--cacheinfo', '160000', self.commit, 'nested')
        self.git('commit', '-qm', 'unmaterialized submodule')
        with self.assertRaisesRegex(ValueError, 'submodule'):
            subject.git_material(self.repo, self.git('rev-parse', 'HEAD'),
                                 self.git('show', '-s', '--format=%T', 'HEAD'), 'recipes')

    def test_output_preserved_and_changed_or_extra_material_rejected(self):
        plan, material = subject.git_material(self.repo, self.commit, self.tree, 'recipes')
        output = self.root / 'existing.tar'
        output.write_bytes(b'other owner')
        with self.assertRaises(FileExistsError):
            subject.collect(plan, material, output)
        self.assertEqual(output.read_bytes(), b'other owner')
        bad = dict(material)
        bad['recipes/LICENSE'] = b'changed'
        with self.assertRaisesRegex(ValueError, 'hash/size'):
            subject.collect(plan, bad, self.root / 'changed.tar')
        self.assertFalse((self.root / 'changed.tar').exists())
        for changed in [dict(material, extra=b'unlisted'),
                        {k: v for k, v in material.items() if k != 'recipes/LICENSE'}]:
            with self.assertRaisesRegex(ValueError, 'file set'):
                subject.collect(plan, changed, self.root / 'extra.tar')

    def test_archive_mutations_rejected(self):
        plan, material = subject.git_material(self.repo, self.commit, self.tree, 'recipes')
        original = self.root / 'good.tar'
        subject.collect(plan, material, original)
        with tarfile.open(original) as archive:
            members = [(m, archive.extractfile(m).read()) for m in archive]
        for mutation in ['extra', 'missing', 'duplicate', 'path', 'symlink', 'mode',
                         'time', 'payload', 'manifest', 'trailing']:
            with self.subTest(mutation=mutation):
                mutated = [(copy.copy(m), data) for m, data in members]
                if mutation == 'extra':
                    info = tarfile.TarInfo('extra'); info.size = 1
                    mutated.append((info, b'x'))
                if mutation == 'missing': mutated.pop()
                if mutation == 'duplicate': mutated.append(mutated[-1])
                if mutation == 'path': mutated[-1][0].name = '../escape'
                if mutation == 'symlink':
                    mutated[-1][0].type = tarfile.SYMTYPE
                    mutated[-1][0].linkname = '/foreign'
                    mutated[-1][0].size = 0
                if mutation == 'mode': mutated[-1][0].mode = 0o777
                if mutation == 'time': mutated[-1][0].mtime = 1
                if mutation == 'payload':
                    m, data = mutated[-1]; mutated[-1] = (m, b'X' * len(data))
                if mutation == 'manifest':
                    m, data = mutated[0]; data = data.replace(b'false', b'true ')
                    mutated[0] = (m, data)
                path = self.root / (mutation + '.tar')
                with tarfile.open(path, 'w', format=tarfile.PAX_FORMAT) as archive:
                    for m, data in mutated: archive.addfile(m, io.BytesIO(data))
                if mutation == 'trailing':
                    with path.open('ab') as output: output.write(b'not a source member')
                with self.assertRaises(ValueError): subject.verify_collection(path, plan)

    def test_manifest_cannot_assert_completeness_or_alias_paths(self):
        plan, _ = subject.git_material(self.repo, self.commit, self.tree, 'recipes')
        for change in ['clearance', 'case', 'unicode', 'bool-size', 'unknown']:
            bad = copy.deepcopy(plan)
            if change == 'clearance': bad['correspondingSourceComplete'] = True
            if change == 'case': bad['files']['Recipes/license'] = bad['files']['recipes/LICENSE']
            if change == 'unicode':
                bad['files']['recipes/é'] = bad['files']['recipes/LICENSE']
                bad['files']['recipes/e\u0301'] = bad['files']['recipes/LICENSE']
            if change == 'bool-size': bad['files']['recipes/LICENSE']['bytes'] = True
            if change == 'unknown': bad['unreviewed'] = True
            with self.subTest(change=change), self.assertRaises(ValueError): subject.validate_plan(bad)

    def test_recipe_parser_does_not_execute_cmake_and_keeps_exact_declarations(self):
        text = '''# ExternalProject_Add(fake URL https://wrong.invalid)
set(PIN "abc")
execute_process(COMMAND unexpected-do-not-run)
ExternalProject_Add(real
 URL https://example.invalid/source.tar.gz # ignored ) comment
 URL_HASH SHA256=0123
 PATCH_COMMAND tool "literal (quoted) value"
)
ExternalProject_Add_Step(real download COMMAND unused)
'''
        calls = subject.recipe_calls(text)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['target'], 'real')
        self.assertEqual(calls[0]['line'], 4)
        self.assertEqual(calls[0]['URL'], 'https://example.invalid/source.tar.gz')
        self.assertEqual(calls[0]['URL_HASH'], 'SHA256=0123')
        with self.assertRaises(ValueError): subject.recipe_calls('ExternalProject_Add(broken')

    def test_source_path_links_are_refused_and_output_owner_is_preserved(self):
        payload = self.root / 'payload'; payload.write_bytes(b'source')
        link = self.root / 'linked'; link.symlink_to(payload)
        plan = subject.new_plan({'fixture': 'linked source'},
                                {'sources/input.tar': subject.record_material(b'source')})
        with self.assertRaises(ValueError):
            subject.collect(plan, {'sources/input.tar': link}, self.root / 'refused.tar')
        self.assertFalse((self.root / 'refused.tar').exists())
        parent = self.root / 'parent'; parent.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            subject.collect(plan, {'sources/input.tar': b'source'}, parent / 'out.tar')

    def test_reviewed_windows_selection_and_variables_fail_closed(self):
        text = '''set(PIN "012345")
if(WIN32)
 ExternalProject_Add(windows URL https://example.invalid/win.zip URL_HASH SHA256=${PIN})
else()
 ExternalProject_Add(unix URL https://example.invalid/source.tar)
endif()
'''
        decision = {'callCount': 2, 'fileSha256': subject.digest(text.encode()),
                    'windowsCalls': [0], 'prebuiltCalls': {'0': 'prebuilt-input-not-corresponding-source'}}
        result = inventory.selected_declarations(text, decision)
        self.assertEqual(result[0]['target'], 'windows')
        self.assertEqual(result[0]['URL_HASH'], 'SHA256=012345')
        self.assertEqual(result[0]['inputKind'], 'prebuilt-input-not-corresponding-source')
        for mutation in ['changed', 'count', 'duplicate', 'out-of-range']:
            bad = copy.deepcopy(decision); changed = text
            if mutation == 'changed': changed += '\n# changed recipes\n'
            if mutation == 'count': bad['callCount'] = 1
            if mutation == 'duplicate': bad['windowsCalls'] = [0, 0]
            if mutation == 'out-of-range': bad['windowsCalls'] = [2]
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                inventory.selected_declarations(changed, bad)
        with self.assertRaisesRegex(ValueError, 'Unresolved'):
            inventory.resolve('${MOVING}', {})

    def test_dependency_selection_never_outputs_sentinel_application_files(self):
        files = {'deps/bin/library.dll': {'bytes': 123, 'sha256': '1' * 64, 'owners': ['example']},
                 'deps/lib/libcompiled-in.a': {'bytes': 321, 'sha256': '2' * 64, 'owners': ['static-library']}}
        selected = inventory.dependency_runtime(files)
        self.assertEqual(set(selected), {'bin/library.dll'})
        self.assertEqual(selected['bin/library.dll']['inputs'][0]['owners'], ['example'])
        self.assertEqual(set(files), {'deps/bin/library.dll', 'deps/lib/libcompiled-in.a'})
        self.assertFalse(inventory.notice_candidate('tools/llvm/lib/liboemlicense.a'))
        self.assertFalse(inventory.notice_candidate('deps/lib/QtSbomLicenseHelpers.cmake'))
        self.assertTrue(inventory.notice_candidate('deps/doc/LICENSE-zlib.txt'))

    def test_file_directory_conflicts_and_archive_missing_inputs_fail(self):
        plan = subject.new_plan({'fixture': 'source bytes'}, {'sources/license': subject.record_material(b'L')})
        bad = copy.deepcopy(plan); bad['files']['sources'] = subject.record_material(b'conflict')
        with self.assertRaises(ValueError): subject.validate_plan(bad)
        with self.assertRaisesRegex(ValueError, 'file set'):
            subject.collect(plan, {}, self.root / 'missing.tar')

    def test_duplicate_and_nonfinite_source_json_refused(self):
        path = self.root / 'plan.json'
        for payload in ['{"files": {}, "files": {"hidden": 1}}', '{"bytes": NaN}']:
            path.write_text(payload)
            with self.subTest(payload=payload), self.assertRaises(ValueError): subject.read_json(path)


class RetainedEvidenceTests(unittest.TestCase):
    def test_inventory_covers_all_locked_inputs_including_compiled_in_libraries(self):
        report = subject.read_json(inventory.HERE / 'inventory.json')
        lock = subject.read_json(inventory.LOCK)
        self.assertEqual(report['lockSha256'], subject.digest(subject.canonical(lock)))
        self.assertEqual({p['name']: p['binarySha256'] for p in report['packages']},
                         {p['name']: p['sha256'] for p in lock['packages']})
        self.assertEqual(report['packageCount'], 90)
        self.assertFalse(report['correspondingSourceComplete'])
        self.assertFalse(report['licenseReviewComplete'])
        for name in ('ext_libaom', 'ext_highway', 'ext_libx265_10bit', 'ext_libx265_12bit'):
            record = next(p for p in report['packages'] if p['name'] == name)
            self.assertEqual(record['runtimeSelectedFileCount'], 0)
            self.assertTrue(record['windowsInputs'])
            self.assertFalse(record['sourceAndLicenseReviewComplete'])

    def test_qt_module_resolution_matches_both_original_build_and_git_tree(self):
        resolved = subject.read_json(inventory.HERE / 'resolved-inputs.json')
        tree = subject.read_json(inventory.HERE / 'evidence/qt-super-tree')
        self.assertEqual(len(resolved['qtSubmodules']), 8)
        for module in resolved['qtSubmodules']:
            entry = next(x for x in tree['tree'] if x['path'] == module['path'])
            self.assertEqual(entry['mode'], '160000')
            self.assertEqual(entry['sha'], module['commit'])
            self.assertEqual(module['buildEvent']['text'],
                             "Submodule path '" + module['path'] + "': checked out '" + module['commit'] + "'")
        unresolved = {r['package'] for r in resolved['gitInputs'] if r['fullCommit'] is None}
        self.assertEqual(unresolved, {'ext_vpx', 'ext_gperf'})
        self.assertFalse(resolved['correspondingSourceComplete'])

    def test_retained_source_evidence_bytes_and_no_environment_records(self):
        provenance = subject.read_json(inventory.HERE / 'evidence-provenance.json')
        for item in provenance['files']:
            path = inventory.HERE / item['path']
            self.assertEqual(subject.record_material(path),
                             {'bytes': item['bytes'], 'sha256': item['sha256'], 'mode': 0o644})
        events = subject.read_json(inventory.HERE / 'evidence/original-windows-source-events.json')
        for item in events['records']:
            self.assertNotIn('CI_JOB_TOKEN', item['text'])
            self.assertNotIn('PASSWORD=', item['text'])
            self.assertNotIn('SECRET=', item['text'])


if __name__ == '__main__':
    unittest.main()
