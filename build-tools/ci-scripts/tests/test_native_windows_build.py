# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path, PureWindowsPath
import sys
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import native_windows_build as build


class NativeWindowsBuildTest(unittest.TestCase):
    def test_focused_targets_build_before_the_complete_native_tree(self):
        with patch.object(build, 'run') as native:
            build.compile_targets('cmake', Path('/build'), 2, Path('/evidence'), {}, Path('/source'))
        self.assertEqual(native.call_count, 2)
        focused, complete = [call.args[0] for call in native.call_args_list]
        self.assertEqual(focused[focused.index('--target') + 1:focused.index('--parallel')],
                         ['KisBrushQuayIdentityTest', 'KisExportFileTransactionTest', 'KisExportPresetStoreTest'])
        self.assertEqual(complete, ['cmake', '--build', str(Path('/build')), '--parallel', '2'])

    def test_focused_failure_prevents_the_expensive_full_build(self):
        with patch.object(build, 'run', side_effect=build.LockError('focused compile failed')) as native:
            with self.assertRaisesRegex(build.LockError, 'focused compile failed'):
                build.compile_targets('cmake', Path('/build'), 2, Path('/evidence'), {}, Path('/source'))
        self.assertEqual(native.call_count, 1)

    def test_source_violation_after_focused_compile_stops_full_build(self):
        phases=[]
        def refuse(phase):phases.append(phase);raise ValueError('Original source violation')
        with patch.object(build,'run') as native:
            with self.assertRaisesRegex(ValueError,'Original source violation'):
                build.compile_targets('cmake',Path('/build'),2,Path('/evidence'),{},Path('/source'),refuse)
        self.assertEqual(native.call_count,1);self.assertEqual(phases,['after-focused-compile'])

    def test_configuration_uses_exact_isolated_toolchain_and_offline_sources(self):
        stage = Path.cwd() / 'locked inputs 水彩'
        command, environment = build.configuration(stage, Path('/source'), Path('/build'), Path('/install'), {'SystemRoot': 'C:\\Windows', 'PATH': 'unverified-tools', 'PYTHONPATH': 'unverified-python'})
        self.assertEqual(Path(command[0]), stage / 'tools/cmake/bin/cmake.exe')
        self.assertIn('-DCMAKE_C_COMPILER=' + (stage / 'tools/llvm/bin/x86_64-w64-mingw32-clang.exe').as_posix(), command)
        self.assertIn('-DCMAKE_CXX_COMPILER=' + (stage / 'tools/llvm/bin/x86_64-w64-mingw32-clang++.exe').as_posix(), command)
        self.assertIn('-DCMAKE_MAKE_PROGRAM=' + (stage / 'tools/ninja/ninja.exe').as_posix(), command)
        self.assertIn('-DPython_EXECUTABLE=' + (stage / 'tools/python-sdk/tools/python.exe').as_posix(), command)
        self.assertIn('-DPKG_CONFIG_EXECUTABLE=' + (stage / 'deps/bin/pkgconf.exe').as_posix(), command)
        self.assertIn('-DBUILD_WITH_QT6=ON', command)
        self.assertIn('-DALLOW_UNSTABLE=QT6', command)
        self.assertIn('-DFETCHCONTENT_FULLY_DISCONNECTED=ON', command)
        self.assertIn('-DCMAKE_FIND_ROOT_PATH_MODE_PACKAGE=ONLY', command)
        self.assertIn('-DCMAKE_FIND_ROOT_PATH_MODE_LIBRARY=ONLY', command)
        self.assertIn('-DCMAKE_FIND_ROOT_PATH_MODE_INCLUDE=ONLY', command)
        self.assertIn('-DCMAKE_FIND_USE_SYSTEM_ENVIRONMENT_PATH=OFF', command)
        self.assertIn('-DUSE_EXTERNAL_RAQM=OFF', command)
        self.assertIn('-DENABLE_UPDATERS=OFF', command)
        self.assertNotIn('unverified-tools', environment['PATH'])
        self.assertNotIn('unverified-python', environment['PYTHONPATH'])
        self.assertEqual(environment['PYTHONDONTWRITEBYTECODE'], '1')

    def test_windows_drive_space_and_unicode_path_arguments(self):
        # Exercise Windows path semantics on every test host, with real pathlib objects.
        stage = PureWindowsPath('D:/BrushQuay inputs/水彩')
        with patch.object(build, 'Path', PureWindowsPath):
            command, environment = build.configuration(stage, 'D:/source', 'D:/build', 'D:/install', {'SystemRoot': 'C:/Windows'})
        self.assertEqual(command[0], str(stage / 'tools/cmake/bin/cmake.exe'))
        self.assertIn('-DPython_EXECUTABLE=' + (stage / 'tools/python-sdk/tools/python.exe').as_posix(), command)
        self.assertIn(str(stage / 'deps/bin'), environment['PATH'].split(';'))
        self.assertIn('C:\\Windows\\System32', environment['PATH'].split(';'))

    def test_cmake_can_parse_generated_compiler_and_cache_paths(self):
        # CMakeRCCompiler.cmake.in writes a quoted set() without escaping its path.
        # Parse the real command values in CMake, including the GitHub runner's \a segment.
        with patch.object(build, 'Path', PureWindowsPath):
            command, environment = build.configuration('D:/a/brushquay/locked inputs/水彩', 'D:/a/source', 'D:/a/build', 'D:/a/install', {'SystemRoot': 'C:/Windows'})
        cmake = shutil.which('cmake')
        self.assertIsNotNone(cmake, 'The configuration-parser regression requires a host CMake executable.')
        lines = ['cmake_minimum_required(VERSION 3.22)']
        for argument in command:
            if argument.startswith('-D'):
                key, value = argument[2:].split('=', 1)
                lines.append('set(' + key + ' "' + value + '")')
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / 'generated-compiler.cmake'
            script.write_text('\n'.join(lines) + '\n', encoding='utf-8')
            result = subprocess.run([cmake, '-P', str(script)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        cache_values = [argument.split('=', 1)[1] for argument in command if argument.startswith('-D')]
        self.assertTrue(all('\\' not in value for value in cache_values))
        self.assertIn('D:\\a\\brushquay\\locked inputs\\水彩\\deps\\bin', environment['PATH'].split(';'))

    def test_system_environment_cannot_override_compiler_flags(self):
        _, environment = build.configuration(Path('/locked'), Path('/source'), Path('/build'), Path('/install'), {'SystemRoot': 'C:\\Windows', 'CC': 'foreign', 'CXXFLAGS': '-injected', 'CMAKE_PREFIX_PATH': '/foreign', 'PKG_CONFIG_PATH': '/foreign'})
        self.assertNotIn('CC', environment)
        self.assertNotIn('CXXFLAGS', environment)
        self.assertNotIn('CMAKE_PREFIX_PATH', environment)
        self.assertNotIn('/foreign', environment['PKG_CONFIG_PATH'])


if __name__ == '__main__':
    unittest.main()
