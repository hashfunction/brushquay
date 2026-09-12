# SPDX-FileCopyrightText: 2026 Trieflow LLC
# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build_msix as package
from verify_brushquay_msix import verify_msix

class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.install = self.root/'install'
        (self.install/'bin').mkdir(parents=True)
        (self.install/'bin/bristlune.exe').write_bytes(b'fixture executable; not a native binary')
        (self.install/'share/licenses').mkdir(parents=True)
        (self.install/'share/licenses/source.txt').write_text('Fixture license and source location')
        self.audit = {'schema':1, 'sourceCommit':'a'*40, 'licenseReviewComplete':True,
                      'correspondingSourceComplete':True, 'files':[]}
        for p in sorted(self.install.rglob('*')):
            if p.is_file(): self.audit['files'].append({'path':p.relative_to(self.install).as_posix(),
                'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
                'license':'GPL-3.0-or-later','source':'https://example.invalid/fixture-source'})
        self.props=self.root/'identity.props'
        self.props.write_text('''<Project><PropertyGroup>
<PackageName>Fixture.Bristlune</PackageName><Publisher>CN=Fixture Only</Publisher>
<Version>1.0.0.0</Version><MinWindowsVersion>10.0.17763.0</MinWindowsVersion>
<MaxWindowsVersionTested>10.0.26100.0</MaxWindowsVersionTested>
</PropertyGroup></Project>''')
        self.identity=package.load_identity(self.props)
    def stage(self):
        return package.stage_payload(self.install,self.audit,self.root/'payload',self.identity)
    def zip(self, expected, extra=None):
        path=self.root/'fixture.msix'
        with zipfile.ZipFile(path,'w') as archive:
            for rel in expected: archive.write(self.root/'payload'/rel,rel)
            archive.writestr('[Content_Types].xml','<Types/>')
            archive.writestr('AppxBlockMap.xml','<BlockMap/>')
            for name,data in (extra or {}).items(): archive.writestr(name,data)
        return path
    def test_owned_manifest_has_only_explicit_fulltrust_capability(self):
        doc=ET.fromstring(package.manifest_bytes(self.identity))
        names=[node.attrib.get('Name') for node in doc.iter() if node.tag.endswith('Capability')]
        self.assertEqual(names,['runFullTrust'])
        applications=[n for n in doc.iter() if n.tag.endswith('Application')]
        self.assertEqual(applications[0].attrib['Executable'],'Bristlune\\bin\\bristlune.exe')
        self.assertFalse(any('Extension' in n.tag for n in doc.iter()))
    def test_renamed_manifest_preserves_application_id_and_rejects_old_display_name(self):
        data=package.manifest_bytes(self.identity)
        self.assertIn(b'Id="BrushQuay"',data)
        self.assertIn(b'<DisplayName>Bristlune</DisplayName>',data)
        self.assertIn(b'<PublisherDisplayName>hashfunction</PublisherDisplayName>',data)
        for before,after in ((b'<DisplayName>Bristlune',b'<DisplayName>BrushQuay'),
                             (b'DisplayName="Bristlune"',b'DisplayName="BrushQuay"'),
                             (b'<PublisherDisplayName>hashfunction',b'<PublisherDisplayName>foreign')):
            with self.subTest(before=before),self.assertRaises(ValueError):
                package.verify_manifest_identity(data.replace(before,after),self.identity)
    def test_missing_placeholder_or_upstream_identity_rejected(self):
        original=self.props.read_text()
        for value in ('49800KritaProject.Krita','REQUIRED_FROM_PARTNER_CENTER','bad/name',''):
            self.props.write_text(original.replace('Fixture.Bristlune',value))
            with self.assertRaises(ValueError): package.load_identity(self.props)
        self.props.write_text(original.replace('CN=Fixture Only','CN=03E730BB-6849-4762-9BDB-10CD7FFDB2C1'))
        with self.assertRaises(ValueError): package.load_identity(self.props)
    def test_unknown_identity_fields_and_entities_rejected(self):
        self.props.write_text(self.props.read_text().replace('</PropertyGroup>','<ShellExtension>yes</ShellExtension></PropertyGroup>'))
        with self.assertRaises(ValueError): package.load_identity(self.props)
        self.props.write_text('<!DOCTYPE x [<!ENTITY x "bad">]><Project/>')
        with self.assertRaises(ValueError): package.load_identity(self.props)
    def test_invalid_windows_and_package_versions_rejected(self):
        original=self.props.read_text()
        for a,b in [('1.0.0.0','1.0.65536.0'),('10.0.17763.0','6.1.0.0'),('10.0.26100.0','10.0.10000.0')]:
            self.props.write_text(original.replace(a,b))
            with self.assertRaises(ValueError): package.load_identity(self.props)
    def write_identity_fields(self,fields):
        root=ET.Element('Project');group=ET.SubElement(root,'PropertyGroup')
        for key,value in fields: ET.SubElement(group,key).text=value
        self.props.write_bytes(ET.tostring(root,encoding='utf-8'))
    def test_template_markers_rejected_in_every_identity_field_and_order(self):
        for publisher_first in (True,False):
            keys=['Publisher','PackageName','Version','MinWindowsVersion','MaxWindowsVersionTested']
            if not publisher_first: keys.reverse()
            for field in keys:
                for token in ('@PackageName@','@UNKNOWN_123@','@@','@ spaced marker @'):
                    with self.subTest(publisher_first=publisher_first,field=field,token=token):
                        values=dict(self.identity);values[field]=('CN=' if field=='Publisher' else '')+token
                        self.write_identity_fields([(key,values[key]) for key in keys])
                        with self.assertRaises(ValueError): package.load_identity(self.props)
    def test_reordered_xml_metacharacters_round_trip_without_substitution(self):
        publisher='CN="Brush & Quay <Tools>", O=Trieflow LLC, L=Montréal, E=owner@example.invalid, OU=Artist\'s Desk'
        for keys in (list(self.identity),list(reversed(self.identity))):
            with self.subTest(order=keys):
                values=dict(self.identity,Publisher=publisher)
                self.write_identity_fields([(key,values[key]) for key in keys])
                approved=package.load_identity(self.props)
                node=ET.fromstring(package.manifest_bytes(approved)).find('{http://schemas.microsoft.com/appx/manifest/foundation/windows10}Identity')
                self.assertEqual(node.attrib['Publisher'],publisher)
                self.assertEqual(node.attrib['Name'],'Fixture.Bristlune')
                self.assertEqual(node.attrib['Version'],'1.0.0.0')
                self.assertEqual(node.attrib['ProcessorArchitecture'],'x64')
    def test_generation_rejects_template_identity_drift(self):
        template=self.root/'templates';template.mkdir()
        original=(ROOT/'manifest.xml.in').read_text()
        for before,after in (('Publisher="@Publisher@"','Publisher="CN=Different"'),
                             ('ProcessorArchitecture="x64"','ProcessorArchitecture="arm64"'),
                             ('Name="runFullTrust"','Name="internetClient"')):
            with self.subTest(attribute=before):
                (template/'manifest.xml.in').write_text(original.replace(before,after))
                with patch.object(package,'HERE',template):
                    with self.assertRaises(ValueError): package.manifest_bytes(self.identity)
    def test_cli_rejects_identity_mismatch_even_when_payload_hashes_agree(self):
        expected=self.stage();manifest=self.root/'payload/AppxManifest.xml';original=manifest.read_bytes()
        foundation='{http://schemas.microsoft.com/appx/manifest/foundation/windows10}'
        restricted='{http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities}'
        changes=[('Identity','Name','Different.Bristlune'),('Identity','Publisher','CN=Different'),
                 ('Identity','Version','2.0.0.0'),('Identity','ProcessorArchitecture','arm64'),
                 ('Applications/Application','Executable','Bristlune\\bin\\other.exe'),
                 ('Applications/Application','Id','Different'),
                 ('Applications/Application','EntryPoint','Other.EntryPoint'),
                 ('Dependencies/TargetDeviceFamily','Name','Windows.Universal'),
                 ('Dependencies/TargetDeviceFamily','MinVersion','10.0.19041.0'),
                 ('Dependencies/TargetDeviceFamily','MaxVersionTested','10.0.99999.0'),
                 ('Capabilities/Capability','Name','internetClient')]
        for path,attribute,value in changes:
            with self.subTest(path=path,attribute=attribute):
                doc=ET.fromstring(original)
                qualified='/'.join((restricted if part=='Capability' else foundation)+part for part in path.split('/'))
                doc.find(qualified).set(attribute,value)
                changed=ET.tostring(doc,encoding='utf-8');manifest.write_bytes(changed)
                coherent=dict(expected);coherent['AppxManifest.xml']={'bytes':len(changed),'sha256':hashlib.sha256(changed).hexdigest()}
                archive=self.zip(coherent);record=self.root/'record.json'
                record.write_text(json.dumps({'payload':coherent,'identity':self.identity}))
                result=subprocess.run([sys.executable,str(ROOT/'verify_brushquay_msix.py'),'--package',str(archive),'--record',str(record)],capture_output=True,text=True)
                self.assertNotEqual(result.returncode,0,'Verifier accepted coherent hashes with unapproved manifest '+path+'/'+attribute)
    def test_cli_rejects_duplicate_or_extended_manifest_identity(self):
        expected=self.stage();manifest=self.root/'payload/AppxManifest.xml';original=manifest.read_bytes()
        ns='{http://schemas.microsoft.com/appx/manifest/foundation/windows10}'
        for duplicate in ('Identity','Capabilities','Dependencies','Applications','application extension'):
            with self.subTest(duplicate=duplicate):
                doc=ET.fromstring(original)
                if duplicate=='application extension': ET.SubElement(doc.find(ns+'Applications/'+ns+'Application'),ns+'Extensions')
                else: doc.append(ET.fromstring(ET.tostring(doc.find(ns+duplicate))))
                changed=ET.tostring(doc,encoding='utf-8');manifest.write_bytes(changed)
                coherent=dict(expected);coherent['AppxManifest.xml']={'bytes':len(changed),'sha256':hashlib.sha256(changed).hexdigest()}
                archive=self.zip(coherent);record=self.root/'record.json';record.write_text(json.dumps({'payload':coherent,'identity':self.identity}))
                result=subprocess.run([sys.executable,str(ROOT/'verify_brushquay_msix.py'),'--package',str(archive),'--record',str(record)],capture_output=True,text=True)
                self.assertNotEqual(result.returncode,0,'Verifier accepted duplicate '+duplicate)

    def test_audit_gates_and_unresolved_licenses_rejected(self):
        for key in ('licenseReviewComplete','correspondingSourceComplete'):
            bad=json.loads(json.dumps(self.audit));bad[key]=False
            with self.assertRaises(ValueError): package.validate_audit(bad)
        for license in ('NOASSERTION','NONE',''):
            bad=json.loads(json.dumps(self.audit));bad['files'][0]['license']=license
            with self.assertRaises(ValueError): package.validate_audit(bad)
    def test_paths_case_alias_and_unaudited_file_rejected(self):
        for name in ('../escape','bin/CON.exe','bin/thing:stream','bin/a.','bin\\bad'):
            bad=json.loads(json.dumps(self.audit));bad['files'][0]['path']=name
            with self.assertRaises(ValueError): package.validate_audit(bad)
        bad=json.loads(json.dumps(self.audit));bad['files'].append(dict(bad['files'][0],path='BIN/bristlune.exe'))
        with self.assertRaises(ValueError): package.validate_audit(bad)
        (self.install/'extra.dll').write_bytes(b'unreviewed')
        with self.assertRaises(ValueError): self.stage()
    def test_source_bytes_changed_and_symlink_rejected(self):
        path=self.install/'bin/bristlune.exe';path.write_bytes(b'changed')
        with self.assertRaises(ValueError): self.stage()
    def test_directory_symlink_rejected(self):
        linked=self.root/'linked'
        try: linked.symlink_to(self.install,target_is_directory=True)
        except OSError: self.skipTest('This Windows account cannot create symlinks; native junction probe remains required')
        with self.assertRaises(ValueError): package.stage_payload(linked,self.audit,self.root/'payload',self.identity)
    def test_stage_is_exact_copy_without_mutating_install(self):
        original={p.relative_to(self.install).as_posix():p.read_bytes() for p in self.install.rglob('*') if p.is_file()}
        expected=self.stage()
        package.verify_payload(self.root/'payload',expected)
        self.assertTrue('Bristlune/bin/bristlune.exe' in expected)
        self.assertTrue('Assets/StoreLogo.png' in expected)
        self.assertEqual(original,{p.relative_to(self.install).as_posix():p.read_bytes() for p in self.install.rglob('*') if p.is_file()})
    def test_existing_stage_refused(self):
        (self.root/'payload').mkdir();(self.root/'payload/owner').write_text('owner')
        with self.assertRaises(ValueError): self.stage()
        self.assertEqual((self.root/'payload/owner').read_text(),'owner')
    def test_payload_tamper_after_stage_detected(self):
        expected=self.stage();(self.root/'payload/Bristlune/bin/bristlune.exe').write_bytes(b'changed')
        with self.assertRaises(ValueError): package.verify_payload(self.root/'payload',expected)
    def test_container_exact_hash_verification(self):
        expected=self.stage();result=verify_msix(self.zip(expected),expected,self.identity)
        self.assertEqual(result['verifiedPayloadFiles'],len(expected))
    def test_container_extra_alias_or_escape_rejected(self):
        expected=self.stage()
        for name in ('extra.dll','brushquay/bin/bristlune.exe','../escape'):
            with self.assertRaises(ValueError): verify_msix(self.zip(expected,{name:b'bad'}),expected,self.identity)
    def test_container_changed_manifest_rejected(self):
        expected=self.stage();(self.root/'payload/AppxManifest.xml').write_bytes(b'<changed/>')
        with self.assertRaises(ValueError): verify_msix(self.zip(expected),expected,self.identity)
    def test_container_symlink_rejected(self):
        expected=self.stage();path=self.zip(expected)
        with zipfile.ZipFile(path,'a') as archive:
            info=zipfile.ZipInfo('link');info.external_attr=0o120777<<16;archive.writestr(info,'target')
        with self.assertRaises(ValueError): verify_msix(path,expected,self.identity)

    def test_container_unknown_or_symlink_directory_rejected(self):
        expected=self.stage()
        for name,mode in [('extra/',0o40755),('Assets/',0o120777),('assets/',0o40755)]:
            path=self.zip(expected)
            with zipfile.ZipFile(path,'a') as archive:
                info=zipfile.ZipInfo(name);info.external_attr=mode<<16;archive.writestr(info,'')
            with self.assertRaises(ValueError): verify_msix(path,expected,self.identity)
    def test_audit_file_directory_alias_rejected(self):
        bad=json.loads(json.dumps(self.audit))
        bad['files'].append(dict(bad['files'][0],path='bin'))
        with self.assertRaises(ValueError): package.validate_audit(bad)

    def sdk_fixture(self):
        audit_path=self.root/'audit.json';audit_path.write_text(json.dumps(self.audit))
        tools={'sdkVersion':'10.0.26100.0'}
        for name in ('makepri','makeappx'):
            exe=self.root/(name+'.exe');exe.write_bytes(b'SDK command fixture, not a native executable')
            tools[name]={'path':str(exe),'bytes':exe.stat().st_size,'sha256':hashlib.sha256(exe.read_bytes()).hexdigest()}
        sdk_path=self.root/'sdk.json';sdk_path.write_text(json.dumps(tools))
        return audit_path,sdk_path
    def fake_sdk(self,command,**kwargs):
        args=command[1:]
        def value(flag): return Path(args[args.index(flag)+1])
        if args[0]=='new': value('/of').write_bytes(b'PRI fixture, not native PRI output')
        elif args[0]=='pack':
            with zipfile.ZipFile(value('/p'),'w') as archive:
                for path in value('/d').rglob('*'):
                    if path.is_file(): archive.write(path,path.relative_to(value('/d')).as_posix())
                for metadata in ('[Content_Types].xml','AppxBlockMap.xml'): archive.writestr(metadata,'<fixture/>')
        elif args[0]=='unpack':
            with zipfile.ZipFile(value('/p')) as archive: archive.extractall(value('/d'))
    def test_driver_retains_complete_verified_evidence(self):
        audit,sdk=self.sdk_fixture();output=self.root/'release'
        with patch.object(package,'require_windows'),patch.object(package.subprocess,'run',side_effect=self.fake_sdk):
            result=package.build(self.install,audit,self.props,sdk,output)
        self.assertEqual(result,output)
        record=json.loads((output/'package-record.json').read_text())
        self.assertFalse(record['signed'])
        self.assertEqual(record['audit']['sourceCommit'],'a'*40)
        for parsed in (record['unpackedManifest'],record['verification']['manifest']):
            self.assertEqual(parsed['package'],{'Name':'Fixture.Bristlune','Publisher':'CN=Fixture Only','Version':'1.0.0.0','ProcessorArchitecture':'x64'})
            self.assertEqual(parsed['application']['Executable'],r'Bristlune\bin\bristlune.exe')
            self.assertEqual(parsed['capabilities'],['runFullTrust'])
        verify_msix(output/'Bristlune.msix',record['payload'],record['identity'])
    def test_driver_late_output_owner_is_not_replaced(self):
        audit,sdk=self.sdk_fixture();output=self.root/'release'
        def collision(command,**kwargs):
            self.fake_sdk(command,**kwargs)
            if command[1]=='unpack': output.mkdir();(output/'owner').write_text('late owner')
        with patch.object(package,'require_windows'),patch.object(package.subprocess,'run',side_effect=collision):
            with self.assertRaisesRegex(ValueError,'Recovery/evidence retained'):
                package.build(self.install,audit,self.props,sdk,output)
        self.assertEqual((output/'owner').read_text(),'late owner')
        self.assertEqual(len(list(self.root.glob('.brushquay-msix-*'))),1)
    def test_driver_tool_lock_change_cannot_authorize_new_bytes(self):
        audit,sdk=self.sdk_fixture()
        def mutate(command,**kwargs):
            self.fake_sdk(command,**kwargs)
            if command[1]=='new':
                lock=json.loads(sdk.read_text());lock['sdkVersion']='10.0.99999.0';sdk.write_text(json.dumps(lock))
        with patch.object(package,'require_windows'),patch.object(package.subprocess,'run',side_effect=mutate):
            with self.assertRaisesRegex(ValueError,'SDK lock changed'):
                package.build(self.install,audit,self.props,sdk,self.root/'release')
        self.assertFalse((self.root/'release').exists())
    def test_driver_sdk_failure_retains_recovery_without_publication(self):
        audit,sdk=self.sdk_fixture()
        with patch.object(package,'require_windows'),patch.object(package.subprocess,'run',side_effect=OSError('fixture SDK failure')):
            with self.assertRaisesRegex(ValueError,'fixture SDK failure'):
                package.build(self.install,audit,self.props,sdk,self.root/'release')
        self.assertFalse((self.root/'release').exists())
        self.assertEqual(len(list(self.root.glob('.brushquay-msix-*'))),1)

if __name__=='__main__': unittest.main()
