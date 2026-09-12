# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
"""Actual CMake child output stays in the native build directory."""
import contextlib
import io
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import native_windows_build as native


class ConfigureOutputTests(unittest.TestCase):
    def test_real_cmake_child_output_does_not_modify_source_or_foreign_file(self):
        self.assertTrue(hasattr(native, 'configure_native'), 'Native configuration output boundary is missing')
        cmake = shutil.which('cmake')
        self.assertIsNotNone(cmake)
        with tempfile.TemporaryDirectory(prefix='bristlune-configure-') as temporary:
            root = Path(temporary).resolve()
            source = root / 'source'; source.mkdir()
            build = root / 'build output'; build.mkdir()
            project = source / 'CMakeLists.txt'
            project.write_text('cmake_minimum_required(VERSION 3.22)\nproject(OutputProbe NONE)\n'
                'execute_process(COMMAND "${PROBE_PYTHON}" -c "from pathlib import Path; Path(\'test.tif\').write_bytes(b\'probe output\')" COMMAND_ERROR_IS_FATAL ANY)\n')
            original = project.read_bytes()
            # Preserve an existing source file with the exact name observed in
            # the failed Windows run. No cleanup/reset/ignore is permitted.
            protected = source / 'test.tif'; protected.write_bytes(b'original source file')
            command = [cmake, '-S', str(source), '-B', str(build), '-DPROBE_PYTHON=' + Path(sys.executable).as_posix()]
            with contextlib.redirect_stdout(io.StringIO()):
                native.configure_native(command, root / 'configure.log', dict(os.environ), build)
            self.assertEqual((build / 'test.tif').read_bytes(), b'probe output')
            self.assertEqual(protected.read_bytes(), b'original source file')
            self.assertEqual(project.read_bytes(), original)
            self.assertEqual({p.name for p in source.iterdir()}, {'CMakeLists.txt', 'test.tif'})
            self.assertTrue((build / 'CMakeCache.txt').is_file())
            self.assertIn('Configuring done', (root / 'configure.log').read_text())


if __name__ == '__main__': unittest.main()
