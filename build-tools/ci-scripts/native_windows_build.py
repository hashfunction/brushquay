# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
"""Compile the native baseline using verified inputs. Never package, sign or publish."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import uuid

from locked_windows_deps import LockError, canonical, load_lock, sha, verify_stage


def configuration(stage, source, build, install, host):
    stage, source, build, install = map(Path, (stage, source, build, install))
    deps, tools = stage / 'deps', stage / 'tools'
    llvm, cmake, ninja = tools / 'llvm/bin', tools / 'cmake/bin', tools / 'ninja'
    python = tools / 'python-sdk/tools'
    # Cache values are embedded into generated CMake code; backslashes are escapes there.
    # Only CMake cache paths use forward slashes. Executables and environment stay native.
    command = [str(cmake / 'cmake.exe'), '-S', str(source), '-B', str(build), '-G', 'Ninja',
               '-DCMAKE_BUILD_TYPE=RelWithDebInfo', '-DBUILD_TESTING=ON',
               '-DBUILD_WITH_QT6=ON', '-DALLOW_UNSTABLE=QT6',
               '-DENABLE_UPDATERS=OFF', '-DFOUNDATION_BUILD=OFF',
               '-DUSE_EXTERNAL_RAQM=OFF', '-DFETCHCONTENT_FULLY_DISCONNECTED=ON',
               '-DFETCHCONTENT_UPDATES_DISCONNECTED=ON', '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON',
               '-DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF', '-DCMAKE_FIND_USE_SYSTEM_PACKAGE_REGISTRY=OFF',
               '-DCMAKE_FIND_USE_CMAKE_ENVIRONMENT_PATH=OFF', '-DCMAKE_FIND_USE_SYSTEM_ENVIRONMENT_PATH=OFF',
               '-DCMAKE_FIND_USE_CMAKE_SYSTEM_PATH=OFF',
               '-DCMAKE_FIND_ROOT_PATH_MODE_PACKAGE=ONLY', '-DCMAKE_FIND_ROOT_PATH_MODE_LIBRARY=ONLY',
               '-DCMAKE_FIND_ROOT_PATH_MODE_INCLUDE=ONLY', '-DCMAKE_FIND_ROOT_PATH_MODE_PROGRAM=NEVER',
               '-DCMAKE_FIND_ROOT_PATH=' + ';'.join(p.as_posix() for p in (deps, python, tools / 'llvm/x86_64-w64-mingw32', tools / 'cmake', source)),
               '-DCMAKE_PROGRAM_PATH=' + ';'.join(p.as_posix() for p in (cmake, ninja, llvm, deps / 'bin', python, python / 'Scripts')),
               '-DCMAKE_C_COMPILER=' + (llvm / 'x86_64-w64-mingw32-clang.exe').as_posix(),
               '-DCMAKE_CXX_COMPILER=' + (llvm / 'x86_64-w64-mingw32-clang++.exe').as_posix(),
               '-DCMAKE_RC_COMPILER=' + (llvm / 'x86_64-w64-mingw32-windres.exe').as_posix(),
               '-DCMAKE_MAKE_PROGRAM=' + (ninja / 'ninja.exe').as_posix(),
               '-DCMAKE_PREFIX_PATH=' + (deps).as_posix(),
               '-DCMAKE_INSTALL_PREFIX=' + (install).as_posix(),
               '-DPython_ROOT_DIR=' + (python).as_posix(),
               '-DPython_EXECUTABLE=' + (python / 'python.exe').as_posix(),
               '-DPython_INCLUDE_DIR=' + (python / 'include').as_posix(),
               '-DPython_LIBRARY=' + (python / 'libs/python313.lib').as_posix(),
               '-DPython_FIND_REGISTRY=NEVER', '-DPython_FIND_STRATEGY=LOCATION',
               '-DPKG_CONFIG_EXECUTABLE=' + (deps / 'bin/pkgconf.exe').as_posix()]
    # Deliberately do not inherit compiler flags, Python packages or a foreign compiler PATH.
    keep = ('SystemRoot', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'TEMP', 'TMP', 'USERPROFILE',
            'NUMBER_OF_PROCESSORS', 'PROCESSOR_ARCHITECTURE', 'PATHEXT', 'LANG')
    environment = {name: host[name] for name in keep if name in host}
    system = Path(host.get('SystemRoot', host.get('SYSTEMROOT', 'C:\\Windows')))
    environment.update({
        'PATH': ';'.join(map(str, (cmake, ninja, llvm, tools / 'llvm/x86_64-w64-mingw32/bin',
                                  deps / 'bin', python, python / 'Scripts', system / 'System32', system))),
        'PYTHONPATH': ';'.join(map(str, (deps / 'lib/site-packages', deps / 'lib/python3.13/site-packages',
                                        deps / 'lib/krita-python-libs'))),
        'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONNOUSERSITE': '1', 'PYTHONUTF8': '1',
        'PKG_CONFIG_PATH': ';'.join(map(str, (deps / 'lib/pkgconfig', deps / 'share/pkgconfig'))),
        'PKG_CONFIG_LIBDIR': ';'.join(map(str, (deps / 'lib/pkgconfig', deps / 'share/pkgconfig'))),
        'APPDATA': str(build / 'test-profile/roaming'),
        'LOCALAPPDATA': str(build / 'test-profile/local'),
    })
    return command, environment


def run(command, log, environment, cwd):
    print('Running:', subprocess.list2cmdline(list(map(str, command))), flush=True)
    with log.open('x', encoding='utf-8') as output:
        process = subprocess.Popen(command, env=environment, cwd=cwd, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
        for line in process.stdout:
            output.write(line)
            output.flush()
            print(line, end='', flush=True)
        code = process.wait()
    if code:
        raise LockError('Native command exited ' + str(code) + '; log: ' + str(log))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lock', type=Path, default=Path(__file__).with_name('brushquay-dependency-lock.json'))
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--cache', type=Path, default=Path('.brushquay/cache'))
    parser.add_argument('--stage', type=Path, default=Path('.brushquay/locked'))
    parser.add_argument('--build', type=Path, default=Path('.brushquay/build'))
    parser.add_argument('--install', type=Path, default=Path('.brushquay/install'))
    parser.add_argument('--evidence', type=Path, default=Path('.brushquay/evidence'))
    parser.add_argument('--jobs', type=int, default=2)
    parser.add_argument('--configure-only', action='store_true')
    args = parser.parse_args()
    if sys.platform != 'win32' or platform.machine().lower() not in ('amd64', 'x86_64'):
        parser.exit(1, 'Native baseline compilation requires Windows x64. No cross-platform success is claimed.\n')
    if args.jobs < 1 or args.jobs > 32:
        parser.error('--jobs must be between 1 and 32')
    source, cache, stage, build, install = [p.resolve() for p in (args.source, args.cache, args.stage, args.build, args.install)]
    lock = load_lock(args.lock)
    evidence = args.evidence.resolve() / (time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex)
    evidence.mkdir(parents=True)
    record = {'schema': 1, 'status': 'not_built', 'lockSha256': sha(canonical(lock)),
              'licenseAuditComplete': False, 'windows': platform.platform(),
              'bootstrapPython': sys.version, 'bootstrapExecutable': sys.executable,
              'bootstrapExecutableSha256': hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
              'sourceBaselineCommit': lock['applicationSourceCommit']}
    try:
        manifest = verify_stage(lock, cache, stage)
        record['verifiedInputFiles'] = len(manifest['files'])
        record['sourceHead'] = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
        record['sourceTree'] = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD^{tree}'], text=True).strip()
        dirty = subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain', '--untracked-files=all'], text=True)
        if dirty:
            raise LockError('Source checkout is dirty; commit the reviewed inputs before native qualification')
        command, environment = configuration(stage, source, build, install, os.environ)
        record['configuration'] = command
        build.mkdir(parents=True, exist_ok=True)
        Path(environment['APPDATA']).mkdir(parents=True, exist_ok=True)
        Path(environment['LOCALAPPDATA']).mkdir(parents=True, exist_ok=True)
        tools = {
            'compiler': (stage / 'tools/llvm/bin/x86_64-w64-mingw32-clang.exe', ['--version'], '21.1.6'),
            'cmake': (stage / 'tools/cmake/bin/cmake.exe', ['--version'], '3.31.8'),
            'ninja': (stage / 'tools/ninja/ninja.exe', ['--version'], '1.13.2'),
            'python-sdk': (stage / 'tools/python-sdk/tools/python.exe', ['--version'], '3.13.5'),
            'qt': (stage / 'deps/bin/qmake.exe', ['-query', 'QT_VERSION'], '6.11.0'),
        }
        record['tools'] = {}
        for name, (executable, arguments, version) in tools.items():
            result = subprocess.check_output([str(executable), *arguments], env=environment, cwd=build,
                                             stderr=subprocess.STDOUT, text=True, encoding='utf-8')
            if version not in result:
                raise LockError('Unexpected locked tool version: ' + name + ': ' + result)
            record['tools'][name] = {'versionOutput': result.strip(), 'path': str(executable),
                                      'sha256': hashlib.sha256(executable.read_bytes()).hexdigest()}
        run(command, evidence / 'configure.log', environment, source)
        record['status'] = 'configured'
        if not args.configure_only:
            run([command[0], '--build', str(build), '--parallel', str(args.jobs)], evidence / 'build.log', environment, source)
            record['status'] = 'compiled'
            run([command[0], '--install', str(build)], evidence / 'install.log', environment, source)
            record['status'] = 'compiled_and_installed_not_packaged'
        verify_stage(lock, cache, stage)
        record['inputStageUnchanged'] = True
    except Exception as error:
        record['error'] = str(error)
        raise
    finally:
        (evidence / 'native-build.json').write_bytes(canonical(record) + b'\n')
        print('Metadata/log evidence:', evidence, flush=True)


if __name__ == '__main__':
    main()
