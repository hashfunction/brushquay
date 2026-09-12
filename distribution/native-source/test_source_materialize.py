# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

import source_materialize as subject


class MaterializationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def test_requests_merge_shared_source_owners_and_exclude_prebuilt_archives(self):
        def item(name, kind='upstream-source-or-source-overlay'):
            return {'name': name, 'windowsInputs': [{'URL': 'https://example.invalid/source.tar',
                    'URL_HASH': 'SHA256=' + 'a'*64, 'inputKind': kind, 'target': name}]}
        result = subject.archive_requests({'packages': [item('x265'), item('x265-10'), item('binary', 'prebuilt-input-not-corresponding-source')]})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['owners'], ['x265', 'x265-10'])
        bad = item('mismatch'); bad['windowsInputs'][0]['URL_HASH'] = 'SHA256=' + 'b'*64
        with self.assertRaises(ValueError): subject.archive_requests({'packages': [item('a'), bad]})

    def test_download_verifies_original_hash_and_preserves_existing_cache_owner(self):
        payload = b'source archive bytes'
        request = {'url': 'https://example.invalid/source.tar', 'algorithm': 'sha256',
                   'digest': hashlib.sha256(payload).hexdigest(), 'owners': ['component']}
        def download(url, output): output.write_bytes(payload)
        receipt = subject.fetch_archive(request, self.root, download)
        self.assertEqual(receipt['sha256'], request['digest'])
        self.assertEqual(receipt['bytes'], len(payload))
        self.assertEqual(receipt['owners'], ['component'])
        path = self.root / receipt['file']; path.write_bytes(b'other owner')
        with self.assertRaises(ValueError): subject.fetch_archive(request, self.root, download)
        self.assertEqual(path.read_bytes(), b'other owner')

    def test_failed_download_is_not_published_and_md5_is_not_relabeled_sha256_pin(self):
        request = {'url': 'https://example.invalid/source.tar', 'algorithm': 'md5',
                   'digest': hashlib.md5(b'original').hexdigest(), 'owners': ['legacy']}
        with self.assertRaises(ValueError):
            subject.fetch_archive(request, self.root, lambda url, output: output.write_bytes(b'wrong'))
        self.assertEqual(list(self.root.iterdir()), [])
        receipt = subject.fetch_archive(request, self.root, lambda url, output: output.write_bytes(b'original'))
        self.assertEqual(receipt['recipeHashAlgorithm'], 'md5')
        self.assertEqual(receipt['sha256'], hashlib.sha256(b'original').hexdigest())
        self.assertFalse(receipt['strongOriginalSourceHash'])

    def test_git_archive_is_checked_against_real_immutable_git_objects(self):
        repo = self.root / 'repo'; repo.mkdir()
        def git(*args): return subprocess.check_output(['git','-C',str(repo),*args]).strip()
        git('init','-q'); git('config','user.email','source@example.invalid'); git('config','user.name','Source')
        (repo/'LICENSE').write_bytes(b'license\n'); (repo/'code.c').write_bytes(b'int main() {}\n')
        (repo/'link').symlink_to('code.c')
        git('add','.'); git('commit','-qm','source')
        commit = git('rev-parse','HEAD').decode(); tree = git('show','-s','--format=%T','HEAD').decode()
        archive = self.root/'source.tar'
        subprocess.run(['git','-C',str(repo),'archive','--format=tar','--prefix=source/','-o',str(archive),commit],check=True)
        result = subject.verify_git_archive(archive, repo, commit)
        self.assertEqual(result['tree'], tree)
        self.assertEqual(result['matchedFiles'], 3)
        for mutation in ['payload','missing','extra','traversal','wrong-commit']:
            with self.subTest(mutation=mutation):
                with tarfile.open(archive) as t:
                    members=[(m,t.extractfile(m).read() if m.isfile() else None) for m in t]
                if mutation=='payload':
                    m,data=next((m,d) for m,d in members if m.name.endswith('code.c')); data=b'X'*len(data)
                    members=[(x,data if x is m else d) for x,d in members]
                if mutation=='missing': members=[(m,d) for m,d in members if not m.name.endswith('LICENSE')]
                if mutation in ['extra','traversal']:
                    m=tarfile.TarInfo('source/extra' if mutation=='extra' else '../escape');m.size=1;members.append((m,b'x'))
                changed=self.root/(mutation+'.tar')
                with tarfile.open(changed,'w') as t:
                    for m,data in members:t.addfile(m,io.BytesIO(data) if data is not None else None)
                with self.assertRaises(ValueError):
                    subject.verify_git_archive(changed,repo,'0'*40 if mutation=='wrong-commit' else commit)

    def test_git_export_ignore_is_reported_as_missing_source(self):
        repo=self.root/'repo';repo.mkdir()
        def git(*args):return subprocess.check_output(['git','-C',str(repo),*args]).strip()
        git('init','-q');git('config','user.email','source@example.invalid');git('config','user.name','Source')
        (repo/'LICENSE').write_bytes(b'license');(repo/'.gitattributes').write_text('LICENSE export-ignore\n')
        git('add','.');git('commit','-qm','source');commit=git('rev-parse','HEAD').decode()
        archive=self.root/'source.tar';subprocess.run(['git','-C',str(repo),'archive','--prefix=src/','-o',str(archive),commit],check=True)
        with self.assertRaisesRegex(ValueError,'Missing Git source'):
            subject.verify_git_archive(archive,repo,commit)

    def test_restores_export_attributes_from_verified_git_blobs_without_overwriting_owner(self):
        repo=self.root/'repo';repo.mkdir()
        def git(*args):return subprocess.check_output(['git','-C',str(repo),*args]).strip()
        git('init','-q');git('config','user.email','source@example.invalid');git('config','user.name','Source')
        (repo/'LICENSE').write_bytes(b'license');(repo/'.tag').write_text('$Format:%H$\n')
        (repo/'windows.txt').write_bytes(b'line\n')
        (repo/'.gitattributes').write_text('LICENSE export-ignore\n.tag export-subst\nwindows.txt eol=crlf\n')
        git('add','.');git('commit','-qm','source');commit=git('rev-parse','HEAD').decode()
        archive=self.root/'source.tar';subprocess.run(['git','-C',str(repo),'archive','--prefix=src/','-o',str(archive),commit],check=True)
        output=self.root/'restored.tar.gz'
        with self.assertRaisesRegex(ValueError,'Immutable Git blob differs'):
            subject.restore_git_archive(archive,repo,commit,output,lambda p,r:b'incorrect')
        self.assertFalse(output.exists())
        result=subject.restore_git_archive(archive,repo,commit,output)
        self.assertEqual(result['matchedFiles'],4)
        self.assertEqual({x['path'] for x in result['restoredFiles']},{'LICENSE','.tag','windows.txt'})
        self.assertFalse(result['correspondingSourceComplete'])
        second=self.root/'second.tar.gz'
        self.assertEqual(subject.restore_git_archive(archive,repo,commit,second)['sha256'],result['sha256'])
        output.write_bytes(b'existing owner')
        with self.assertRaises(FileExistsError):subject.restore_git_archive(archive,repo,commit,output)
        self.assertEqual(output.read_bytes(),b'existing owner')

    def test_reviewed_materialization_receipt_rejects_changed_bytes_owners_and_clearance(self):
        import copy
        payload=b'archive';(self.root/'source.tar').write_bytes(payload)
        receipt={'schema':1,'inventorySha256':'a'*64,'correspondingSourceComplete':False,
                 'licenseReviewComplete':False,'materials':[{'path':'source.tar','kind':'upstream-source-archive',
                 'owners':['component'],'bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest()}]}
        inventory={'packages':[{'name':'component'}]}
        plan,material=subject.materialized_plan(receipt,self.root,inventory,"a"*64)
        self.assertEqual(set(material),{'source.tar'});self.assertFalse(plan['correspondingSourceComplete'])
        for mutation in ['bytes','owner','clearance','duplicate','path','inventory']:
            changed=copy.deepcopy(receipt)
            if mutation=='bytes':changed['materials'][0]['sha256']='0'*64
            if mutation=='owner':changed['materials'][0]['owners']=['unknown']
            if mutation=='clearance':changed['licenseReviewComplete']=True
            if mutation=='duplicate':changed['materials']*=2
            if mutation=='path':changed['materials'][0]['path']='../source.tar'
            if mutation=='inventory':changed['inventorySha256']='b'*64
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):subject.materialized_plan(changed,self.root,inventory,"a"*64)

    def test_retained_materials_cover_pinned_owners_and_keep_producer_gaps_explicit(self):
        root=Path(__file__).parent
        receipt=json.loads((root/'materialized-inputs.json').read_text())
        inventory=json.loads((root/'inventory.json').read_text())
        self.assertEqual(receipt['inventorySha256'],hashlib.sha256((root/'inventory.json').read_bytes()).hexdigest())
        self.assertEqual(len(receipt['materials']),117)
        known={p['name'] for p in inventory['packages']}
        for r in receipt['materials']:self.assertLessEqual(set(r['owners']),known)
        by_name={r['name']:r for r in receipt['materials'] if r['kind']=='git-source-archive'}
        self.assertEqual(len(by_name),34)
        resolved=json.loads((root/'resolved-inputs.json').read_text())
        for module in resolved['qtSubmodules']:
            self.assertEqual(by_name[module['path']]['commit'],module['commit'])
            self.assertGreater(by_name[module['path']]['matchedFiles'],0)
        for r in receipt['materials']:
            if r.get('recipeHashAlgorithm')=='md5':self.assertFalse(r['strongOriginalSourceHash'])
        research=json.loads((root/'producer-research.json').read_text())
        self.assertEqual({x['package'] for x in research['movingBranches']},{'ext_vpx','ext_gperf'})
        self.assertTrue(all(x['actualProducerCommit'] is None for x in research['movingBranches']))
        producer=json.loads((root/research['openssl']['producerEvidence']).read_text())
        self.assertEqual(research['openssl']['actualProducerCommit'],producer['producer']['commit'])
        self.assertFalse(receipt['licenseReviewComplete']);self.assertFalse(receipt['correspondingSourceComplete'])

    def test_python_producer_sbom_binds_original_embed_and_materialized_external_sources(self):
        root=Path(__file__).parent
        sbom=json.loads((root/'evidence/python-3.13.5-embed-amd64.zip.spdx.json').read_text())
        producer=json.loads((root/'producer-provenance.json').read_text())
        binary=next(r for r in producer['results'] if r['owners']==['ext_python'])
        python=next(p for p in sbom['packages'] if p['name']=='CPython')
        self.assertEqual(binary['sha256'],python['checksums'][0]['checksumValue'])
        materials=json.loads((root/'materialized-inputs.json').read_text())['materials']
        for package in sbom['packages']:
            if package['name'] in ['CPython','tcl-core','tk']:continue
            matches=[m for m in materials if m.get('url')==package['downloadLocation']]
            self.assertEqual(len(matches),1)
            self.assertEqual(matches[0]['sha256'],package['checksums'][0]['checksumValue'])
            self.assertIn('ext_python',matches[0]['owners'])


if __name__=='__main__':unittest.main()
