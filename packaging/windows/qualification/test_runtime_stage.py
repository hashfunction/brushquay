# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
from pathlib import Path
import tempfile
import unittest
from runtime_stage import select_runtime, materialize, measure_tree


def row(data, owners=None):
    result={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    if owners is not None: result['owners']=owners
    return result

class RuntimeStageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.install=self.root/'install';self.locked=self.root/'locked'
        self.app={'bin/bristlune.exe':row(b'app'),'bin/bristlune.dll':row(b'impl'),
                  'lib/kritaplugins/png.dll':row(b'png'),'share/krita/data.txt':row(b'resource')}
        self.dep={'deps/bin/Qt6Core.dll':row(b'qt',['qt']),
                  'deps/plugins/platforms/qwindows.dll':row(b'platform',['qt']),
                  'tools/llvm/x86_64-w64-mingw32/bin/libc++.dll':row(b'c++',['llvm']),
                  'deps/bin/qmake.exe':row(b'tool',['qt']),
                  'deps/lib/site-packages/pyqtbuild/tool.py':row(b'buildtool',['builder'])}
        contents={**{('app',k):v for k,v in {'bin/bristlune.exe':b'app','bin/bristlune.dll':b'impl','lib/kritaplugins/png.dll':b'png','share/krita/data.txt':b'resource'}.items()},
                  **{('locked',k):v for k,v in {'deps/bin/Qt6Core.dll':b'qt','deps/plugins/platforms/qwindows.dll':b'platform','tools/llvm/x86_64-w64-mingw32/bin/libc++.dll':b'c++','deps/bin/qmake.exe':b'tool','deps/lib/site-packages/pyqtbuild/tool.py':b'buildtool'}.items()}}
        for (tree,rel),data in contents.items():
            p=(self.install if tree=='app' else self.locked)/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    def test_exact_runtime_inputs_and_owners_exclude_build_tools(self):
        selected=select_runtime(self.app,self.dep)
        self.assertEqual(set(selected),{'bin/bristlune.exe','bin/bristlune.dll','lib/kritaplugins/png.dll','share/krita/data.txt','bin/Qt6Core.dll','plugins/platforms/qwindows.dll','bin/libc++.dll'})
        self.assertEqual(selected['bin/libc++.dll']['inputs'],[{'tree':'locked','path':'tools/llvm/x86_64-w64-mingw32/bin/libc++.dll','owners':['llvm']}])
        materialize(self.install,self.locked,selected,self.root/'output')
        self.assertEqual(measure_tree(self.root/'output'),{k:{f:v[f] for f in ('bytes','sha256')} for k,v in selected.items()})
        self.assertEqual((self.locked/'deps/bin/qmake.exe').read_bytes(),b'tool')
    def test_application_qml_module_is_copied_from_the_native_install(self):
        relative='qml/org/krita/Module/qmldir';data=b'module org.krita.Module\n'
        path=self.install/relative;path.parent.mkdir(parents=True);path.write_bytes(data)
        self.app[relative]=row(data);selected=select_runtime(self.app,self.dep)
        materialize(self.install,self.locked,selected,self.root/'output')
        self.assertEqual((self.root/'output'/relative).read_bytes(),data)
        self.assertEqual(selected[relative]['inputs'],[{'tree':'application','path':relative}])
    def test_conflicting_dependency_never_replaces_application(self):
        self.dep['deps/bin/bristlune.dll']=row(b'foreign',['foreign'])
        with self.assertRaises(ValueError): select_runtime(self.app,self.dep)
    def test_equal_shared_bytes_retain_both_exact_owners(self):
        self.dep['deps/bin/bristlune.dll']=row(b'impl',['dependency'])
        selected=select_runtime(self.app,self.dep)
        self.assertEqual(len(selected['bin/bristlune.dll']['inputs']),2)
    def test_case_alias_and_escaping_runtime_input_refused(self):
        for name in ('bin/BRISTLUNE.exe','bin/../bristlune.exe'):
            with self.subTest(name=name),self.assertRaises(ValueError): select_runtime({**self.app,name:row(b'changed')},self.dep)
    def test_changed_source_and_existing_output_refused(self):
        selected=select_runtime(self.app,self.dep)
        (self.install/'bin/bristlune.exe').write_bytes(b'changed')
        with self.assertRaises(ValueError): materialize(self.install,self.locked,selected,self.root/'output')
        other=self.root/'foreign';other.mkdir();(other/'keep').write_bytes(b'preserve')
        with self.assertRaises(ValueError): materialize(self.install,self.locked,selected,other)
        self.assertEqual((other/'keep').read_bytes(),b'preserve')
    def test_linked_source_is_never_copied(self):
        selected=select_runtime(self.app,self.dep);p=self.install/'bin/bristlune.exe';p.unlink();p.symlink_to(self.locked/'deps/bin/Qt6Core.dll')
        with self.assertRaises(ValueError): materialize(self.install,self.locked,selected,self.root/'output')

if __name__=='__main__':unittest.main()
