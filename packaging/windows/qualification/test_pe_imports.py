# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
"""Actual observer boundaries; optional locked Windows reader exercises real PE bytes."""
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from pe_imports import parse_imports, observe_imports, read_imports, retain_imports
from runtime_stage import measure

def pe_fixture():
    # A minimal x64 PE with a normal name+ordinal import and one delayed import.
    raw=bytearray(2048);raw[:2]=b'MZ';struct.pack_into('<I',raw,60,128);raw[128:132]=b'PE\0\0'
    struct.pack_into('<HHIIIHH',raw,132,0x8664,1,0,0,0,240,0x2022)
    struct.pack_into('<H',raw,152,0x20b);struct.pack_into('<Q',raw,176,0x180000000)
    struct.pack_into('<II',raw,184,4096,512);struct.pack_into('<II',raw,208,8192,512)
    struct.pack_into('<H',raw,220,3);struct.pack_into('<I',raw,260,16)
    struct.pack_into('<II',raw,272,0x1000,40);struct.pack_into('<II',raw,368,0x1100,64)
    raw[392:400]=b'.rdata\0\0';struct.pack_into('<IIII',raw,400,1536,4096,1536,512)
    struct.pack_into('<I',raw,428,0x40000040)
    struct.pack_into('<IIIII',raw,512,0x1080,0,0,0x1040,0x1080)
    raw[576:589]=b'KERNEL32.dll\0';struct.pack_into('<QQQ',raw,640,0x10a0,0x800000000000000c,0)
    raw[674:688]=b'GetLastError\0\0';struct.pack_into('<IIIIIIII',raw,768,1,0x1140,0,0x1180,0x1180,0,0,0)
    raw[832:843]=b'USER32.dll\0';struct.pack_into('<QQ',raw,896,0x11b0,0);raw[946:960]=b'GetFocus\0\0\0\0\0\0'
    return bytes(raw)

def transcript(path):
    return ('\nFile: '+str(path)+'\nFormat: COFF-x86-64\nArch: x86_64\nAddressSize: 64bit\n'
            'Import {\n  Name: KERNEL32.dll\n  ImportLookupTableRVA: 0x1080\n  ImportAddressTableRVA: 0x1080\n'
            '  Symbol: GetLastError (0)\n  Symbol:  (12)\n}\n'
            'DelayImport {\n  Name: USER32.dll\n  Attributes: 0x1\n  ModuleHandle: 0x0\n'
            '  ImportAddressTable: 0x1180\n  ImportNameTable: 0x1180\n  BoundDelayImportTable: 0x0\n'
            '  UnloadDelayImportTable: 0x0\n  Import {\n    Symbol: GetFocus (0)\n    Address: 0x11B0\n  }\n}\n')

class ImportObservationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve()
        self.payload=self.root/'payload';(self.payload/'bin').mkdir(parents=True)
        self.dll=self.payload/'bin/app.dll';self.dll.write_bytes(pe_fixture())
        self.tool=self.root/'reader.exe';self.tool.write_bytes(b'locked reader')
        self.selected={'bin/app.dll':dict(**measure(self.dll),inputs=[{'tree':'application','path':'bin/app.dll'}])}
        self.context={'sourceCommit':'a'*40,'sourceTree':'b'*40,'workflowRunId':'42','workflowRunAttempt':'1',
                      'nativeEvidence':{'bytes':5,'sha256':'c'*64},'lockSha256':'d'*64}
        self.tool_record=dict(**measure(self.tool),owners=['llvm-mingw'])
    def collect(self,reader=None):
        return observe_imports(self.payload,self.selected,self.tool,self.tool_record,self.context,reader=reader or (lambda t,p:parse_imports(transcript(p),p)))
    def test_normal_and_delayed_named_and_ordinal_imports_remain_distinct(self):
        result=parse_imports(transcript(self.dll),self.dll)
        self.assertEqual(result['normalImports'],[{'library':'KERNEL32.dll','symbols':[{'name':'GetLastError','hint':0},{'ordinal':12}]}])
        self.assertEqual(result['delayImports'],[{'library':'USER32.dll','symbols':[{'name':'GetFocus','hint':0}]}])
    def test_unknown_format_path_truncation_descriptor_or_symbol_refused(self):
        original=transcript(self.dll)
        for raw in [original.replace('COFF-x86-64','ELF64-x86-64'),original.replace(str(self.dll),'foreign.dll'),original[:-3],
                    original.replace('Name: KERNEL32.dll','Name: ../foreign.dll'),original.replace('Symbol: GetLastError (0)','Unexpected: false'),
                    original.replace('Symbol:  (12)','Symbol:  (999999)'),original+'File: other.dll\n']:
            with self.subTest(raw=raw[-70:]),self.assertRaises(ValueError):parse_imports(raw,self.dll)
    def test_complete_staged_hash_owner_and_current_context_binding(self):
        result=self.collect();self.assertEqual(result['status'],'observed');self.assertFalse(result['releaseReady'])
        self.assertEqual(result['sourceCommit'],self.context['sourceCommit']);self.assertEqual(result['workflowRunId'],'42')
        self.assertEqual(result['files'][0]['inputs'],self.selected['bin/app.dll']['inputs']);self.assertEqual(result['files'][0]['sha256'],measure(self.dll)['sha256'])
        self.assertEqual(result['reader']['sha256'],measure(self.tool)['sha256']);self.assertEqual(result['errors'],[])
    def test_input_or_reader_mutation_is_retained_as_incomplete_not_source_approval(self):
        for name in ['input','tool']:
            def changed(t,p):
                (p if name=='input' else t).write_bytes(b'changed');return parse_imports(transcript(p),p)
            with self.subTest(name=name):
                self.dll.write_bytes(pe_fixture());self.tool.write_bytes(b'locked reader')
                result=self.collect(changed);self.assertEqual(result['status'],'incomplete');self.assertTrue(result['errors']);self.assertFalse(result['releaseReady'])
    def test_missing_tool_wrong_owner_context_and_input_are_never_observed(self):
        for key in ['tool','owner','source','attempt','input']:
            with self.subTest(key=key):
                if key=='tool':self.tool.unlink()
                if key=='owner':self.tool_record['owners']=['foreign']
                if key=='source':self.context['sourceCommit']='stale'
                if key=='attempt':self.context['workflowRunAttempt']='0'
                if key=='input':self.dll.write_bytes(b'changed')
                result=self.collect();self.assertEqual(result['status'],'incomplete');self.assertTrue(result['errors'])
                self.tool.write_bytes(b'locked reader');self.tool_record['owners']=['llvm-mingw'];self.context['sourceCommit']='a'*40;self.context['workflowRunAttempt']='1';self.dll.write_bytes(pe_fixture())
    def test_reader_failure_preserves_partial_observations_and_original_bytes(self):
        def fail(t,p):raise TimeoutError('original reader timeout')
        result=self.collect(fail);self.assertEqual(result['status'],'incomplete');self.assertIn('original reader timeout',result['errors'][0]['error']);self.assertEqual(self.dll.read_bytes(),pe_fixture())
    def test_com_launcher_is_included_data_is_not(self):
        (self.payload/'bin/app.com').write_bytes(pe_fixture());self.selected['bin/app.com']=dict(**measure(self.payload/'bin/app.com'),inputs=[{'tree':'application','path':'bin/app.com'}])
        (self.payload/'data.txt').write_bytes(b'data');self.selected['data.txt']=dict(**measure(self.payload/'data.txt'),inputs=[{'tree':'application','path':'data.txt'}])
        self.assertEqual([x['path'] for x in self.collect()['files']],['bin/app.com','bin/app.dll'])
    def test_retained_observation_is_exclusive_and_write_failure_is_secondary(self):
        path=self.root/'observation.json'
        kwargs={'reader':lambda t,p:parse_imports(transcript(p),p)}
        first=retain_imports(path,self.payload,self.selected,self.tool,self.tool_record,self.context,**kwargs)
        self.assertEqual(first['status'],'observed');self.assertEqual(first['file'],measure(path))
        before=path.read_bytes();second=retain_imports(path,self.payload,self.selected,self.tool,self.tool_record,self.context,**kwargs)
        self.assertEqual(second['status'],'incomplete');self.assertIn('FileExistsError',second['error']);self.assertEqual(before,path.read_bytes())
    def test_record_budget_and_unsafe_selected_path_do_not_read_unbounded_or_foreign_inputs(self):
        with patch('pe_imports.MAX_RECORD',20):
            result=self.collect();self.assertEqual(result['status'],'incomplete');self.assertEqual(result['files'],[])
        self.selected['../foreign.dll']=self.selected.pop('bin/app.dll')
        with patch('pe_imports.measure',wraps=measure) as hashed:
            result=self.collect();self.assertEqual(result['status'],'incomplete')
            self.assertTrue(all(Path(c.args[0])==self.tool for c in hashed.call_args_list))
    def test_real_reader_process_overflow_timeout_exit_and_invalid_output_are_bounded(self):
        popen=subprocess.Popen
        scripts=[('import sys;sys.stdout.write("x"*256)', 'exceeds bound', 64, 2),
                 ('import time;time.sleep(10)', 'twenty seconds', 1024, 0.05),
                 ('import sys;sys.stdout.write("original read error");sys.exit(7)', 'original read error',1024,2),
                 ('import sys;sys.stdout.buffer.write(bytes([255]))', 'not UTF-8',1024,2)]
        for script,message,limit,seconds in scripts:
            def launch(command,**kwargs):return popen([sys.executable,'-c',script],**kwargs)
            with self.subTest(message=message),patch('pe_imports.subprocess.Popen',side_effect=launch),patch('pe_imports.MAX_OUTPUT',limit),patch('pe_imports.READER_TIMEOUT',seconds):
                with self.assertRaisesRegex((ValueError,TimeoutError),message):read_imports(self.tool,self.dll)
    @unittest.skipUnless(os.environ.get('BRISTLUNE_TEST_PE_READER'),'Requires exact locked Windows LLVM reader after fetch')
    def test_actual_locked_llvm_reads_real_normal_and_delay_pe(self):
        tool=Path(os.environ['BRISTLUNE_TEST_PE_READER'])
        # Measured directly from exact llvm-mingw20251118 locked ZIP d14a2022... .
        self.assertEqual(measure(tool),{'bytes':1545216,'sha256':'2911b6a130c7d88e74a894368d493e5fa80a0baae3bc6ed35e06b543e360fd4e'})
        result=read_imports(tool,self.dll)
        self.assertEqual(result,parse_imports(transcript(self.dll),self.dll))
        self.dll.write_bytes(b'not a PE')
        with self.assertRaises(ValueError):read_imports(Path(os.environ['BRISTLUNE_TEST_PE_READER']),self.dll)

if __name__=='__main__':unittest.main()
