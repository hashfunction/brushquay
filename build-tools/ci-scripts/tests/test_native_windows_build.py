# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path, PureWindowsPath
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import native_windows_build as build


class NativeWindowsBuildTest(unittest.TestCase):
    def test_configuration_uses_exact_isolated_toolchain_and_offline_sources(self):
        stage = Path.cwd() / 'locked inputs 水彩'
        command, environment = build.configuration(stage, Path('/source'), Path('/build'), Path('/install'), {'SystemRoot': 'C:\\Windows', 'PATH': 'unverified-tools', 'PYTHONPATH': 'unverified-python'})
        self.assertEqual(Path(command[0]), stage / 'tools/cmake/bin/cmake.exe')
        self.assertIn('-DCMAKE_C_COMPILER=' + str(stage / 'tools/llvm/bin/x86_64-w64-mingw32-clang.exe'), command)
        self.assertIn('-DCMAKE_CXX_COMPILER=' + str(stage / 'tools/llvm/bin/x86_64-w64-mingw32-clang++.exe'), command)
        self.assertIn('-DCMAKE_MAKE_PROGRAM=' + str(stage / 'tools/ninja/ninja.exe'), command)
        self.assertIn('-DPython_EXECUTABLE=' + str(stage / 'tools/python-sdk/tools/python.exe'), command)
        self.assertIn('-DPKG_CONFIG_EXECUTABLE=' + str(stage / 'deps/bin/pkgconf.exe'), command)
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
        self.assertIn('-DPython_EXECUTABLE=' + str(stage / 'tools/python-sdk/tools/python.exe'), command)
        self.assertIn(str(stage / 'deps/bin'), environment['PATH'].split(';'))
        self.assertIn('C:\\Windows\\System32', environment['PATH'].split(';'))

    def test_system_environment_cannot_override_compiler_flags(self):
        _, environment = build.configuration(Path('/locked'), Path('/source'), Path('/build'), Path('/install'), {'SystemRoot': 'C:\\Windows', 'CC': 'foreign', 'CXXFLAGS': '-injected', 'CMAKE_PREFIX_PATH': '/foreign', 'PKG_CONFIG_PATH': '/foreign'})
        self.assertNotIn('CC', environment)
        self.assertNotIn('CXXFLAGS', environment)
        self.assertNotIn('CMAKE_PREFIX_PATH', environment)
        self.assertNotIn('/foreign', environment['PKG_CONFIG_PATH'])


if __name__ == '__main__':
    unittest.main()
