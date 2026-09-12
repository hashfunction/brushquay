# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
"""Compile and test the native product using verified inputs. Never package, sign or publish."""
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
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'packaging/windows/qualification'))
from runtime_stage import measure, measure_tree
from source_state import require_clean_source


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


def configure_native(command, log, environment, build):
    # CheckLibTIFFPSDSupport executes a probe that writes relative test.tif.
    # CMake and its probe must inherit the output directory, never source.
    run(command, log, environment, build)


def compile_targets(cmake, build, jobs, evidence, environment, source, observe_source=None):
    # These targets link only the small preset library and Qt Core/Test/Xml.
    # Catch their source-boundary errors before compiling the entire product.
    focused = ['KisBrushQuayIdentityTest', 'KisExportFileTransactionTest', 'KisExportPresetStoreTest']
    run([cmake, '--build', str(build), '--target', *focused, '--parallel', str(jobs)],
        evidence / 'focused-build.log', environment, source)
    if observe_source:observe_source('after-focused-compile')
    run([cmake, '--build', str(build), '--parallel', str(jobs)],
        evidence / 'build.log', environment, source)
    if observe_source:observe_source('after-compile')


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
              'workflowRunId': os.environ.get('GITHUB_RUN_ID'),
              'workflowRunAttempt': os.environ.get('GITHUB_RUN_ATTEMPT'),
              'licenseAuditComplete': False, 'windows': platform.platform(),
              'bootstrapPython': sys.version, 'bootstrapExecutable': sys.executable,
              'bootstrapExecutableSha256': hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
              'sourceBaselineCommit': lock['applicationSourceCommit'], 'sourceObservations': {}}
    def observe_source(phase):
        output=evidence/('source-'+phase+'.json')
        try:return require_clean_source(source,record['sourceHead'],output,phase)
        finally:
            if output.is_file():record['sourceObservations'][phase]={'file':output.name,**measure(output)}
    try:
        manifest = verify_stage(lock, cache, stage)
        record['verifiedInputFiles'] = len(manifest['files'])
        record['sourceHead'] = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
        record['sourceTree'] = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD^{tree}'], text=True).strip()
        observe_source('before-configure')
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
        configure_native(command, evidence / 'configure.log', environment, build)
        record['status'] = 'configured'
        observe_source('after-configure')
        if not args.configure_only:
            compile_targets(command[0], build, args.jobs, evidence, environment, source, observe_source)
            record['status'] = 'compiled'
            expected_tests = {'libs-ui-' + name for name in (
                'KisBrushQuayIdentityTest', 'KisBrushQuayWorkspaceTest', 'KisExportPresetIntegrationTest',
                'KisExportFileTransactionTest', 'KisExportPresetStoreTest', 'KisClipboardNullTest')}
            test_pattern = '^(' + '|'.join(sorted(expected_tests)) + ')$'
            ctest = stage / 'tools/cmake/bin/ctest.exe'
            test_environment = dict(environment)
            test_environment['PATH'] = str(build / 'bin') + ';' + environment['PATH']
            test_environment['QT_QPA_PLATFORM'] = 'offscreen'
            test_environment['BRUSHQUAY_WORKSPACE_OUTPUT'] = str(evidence / 'workspaces')
            test_environment['BRUSHQUAY_WORKSPACE_SOURCE_COMMIT'] = record['sourceHead']
            discovery = subprocess.check_output([str(ctest), '--test-dir', str(build), '-N',
                '--show-only=json-v1', '-R', test_pattern], env=test_environment, text=True, encoding='utf-8')
            (evidence / 'product-test-discovery.json').write_text(discovery, encoding='utf-8')
            discovered = json.loads(discovery)['tests']
            if len(discovered) != len(expected_tests) or {test['name'] for test in discovered} != expected_tests:
                raise LockError('The native build did not register every required product test')
            run([str(ctest), '--test-dir', str(build), '-R', test_pattern, '--no-tests=error',
                 '--timeout', '180', '--output-on-failure', '--output-junit', str(evidence / 'product-tests.xml')],
                evidence / 'product-tests.log', test_environment, source)
            record['productTests'] = sorted(expected_tests)
            record['productTestReport'] = measure(evidence / 'product-tests.xml')
            record['status'] = 'compiled_and_product_tests_passed'
            observe_source('after-tests')
            run([command[0], '--install', str(build)], evidence / 'install.log', environment, source)
            observe_source('after-install')
            record['installedApplicationFiles'] = []
            for relative in ('bin/bristlune.exe', 'bin/bristlune.com', 'bin/bristlune.dll'):
                installed_file = install / relative
                if not installed_file.is_file() or installed_file.stat().st_size == 0:
                    raise LockError('Missing installed product binary: ' + relative)
                record['installedApplicationFiles'].append({'path': relative, 'bytes': installed_file.stat().st_size,
                    'sha256': hashlib.sha256(installed_file.read_bytes()).hexdigest()})
            record['status'] = 'compiled_and_installed_not_packaged'
            record['installedTree'] = measure_tree(install)
        verify_stage(lock, cache, stage)
        record['inputStageUnchanged'] = True
    except Exception as error:
        record['error'] = str(error)
        raise
    finally:
        # A failed native command keeps its primary error. Preserve a separate
        # final read even when it could not reach the next successful phase.
        if 'error' in record and 'sourceHead' in record:
            try:observe_source('failure-final')
            except Exception as error:record['finalSourceObservationError']=str(error)
        (evidence / 'native-build.json').write_bytes(canonical(record) + b'\n')
        print('Metadata/log evidence:', evidence, flush=True)


if __name__ == '__main__':
    main()
