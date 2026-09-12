# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
"""Regenerate the source trace from immutable recipes and reverified binary inputs."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys

import native_source as source
from locked_windows_deps import load_lock, canonical, sha, verify_stage
from runtime_stage import select_runtime

HERE = Path(__file__).resolve().parent
LOCK = source.ROOT / 'build-tools/ci-scripts/brushquay-dependency-lock.json'
RECIPE_COMMIT = '993af62fdf291eaec05a1824d9b420782717fc44'
RECIPE_TREE = 'c7c208f011a7123df1b99d6fe7f59276b5025e84'


def scalar_variables(text):
    values = {}
    for name, value in re.findall(r'(?im)^\s*set\s*\(\s*([A-Z_0-9]+)\s+("[^"\n]*"|[^\s()]+)\s*\)', text):
        values.setdefault(name, set()).add(value.strip('"'))
    return {name: next(iter(items)) for name, items in values.items() if len(items) == 1}


def resolve(value, variables):
    result = re.sub(r'\$\{([^}]+)\}', lambda m: variables.get(m[1], m[0]), value)
    if '${' in result: raise ValueError('Unresolved source input variable: ' + result)
    return result


def selected_declarations(text, decision):
    calls = source.recipe_calls(text)
    if len(calls) != decision['callCount'] or source.digest(text.encode()) != decision['fileSha256']:
        raise ValueError('Reviewed recipe declaration set changed')
    choices = decision['windowsCalls']
    if (not choices or choices != sorted(set(choices))
            or any(type(n) is not int or n < 0 or n >= len(calls) for n in choices)):
        raise ValueError('Invalid reviewed Windows selection')
    variables = scalar_variables(text)
    result = []
    for n in choices:
        record = {k: v for k, v in calls[n].items() if k != 'declaration'}
        record['callIndex'] = n
        for key in ('URL', 'URL_HASH', 'URL_MD5', 'GIT_REPOSITORY', 'GIT_TAG', 'DOWNLOAD_NAME'):
            if key in record: record[key] = resolve(record[key], variables)
        record['inputKind'] = decision.get('prebuiltCalls', {}).get(str(n), 'upstream-source-or-source-overlay')
        result.append(record)
    return result


def dependency_runtime(files):
    # The selector insists on two application members. These in-memory sentinels
    # only exercise its dependency branch and are removed immediately. They are
    # never recorded, packaged or used as native/consumer qualification evidence.
    placeholders = {name: {'bytes': 0, 'sha256': '0' * 64}
                    for name in ('bin/bristlune.exe', 'bin/bristlune.dll')}
    selected = select_runtime(placeholders, files)
    return {name: value for name, value in selected.items()
            if all(origin['tree'] == 'locked' for origin in value['inputs'])}


def notice_candidate(name):
    # Candidate discovery, never a license conclusion. Exclude binaries and
    # similarly named CMake helpers; retain the original paths and owner hashes.
    base = Path(name).name.lower()
    return (re.match(r'^(license|copying|copyright|notice)(?:[._-]|$)', base) is not None
            or base.endswith(('-license.txt', '.license'))) and Path(name).suffix.lower() not in ('.a', '.dll', '.exe', '.cmake')


def build_inventory(lock, recipes, stage, review):
    if review['recipeCommit'] != RECIPE_COMMIT or review['recipeTree'] != RECIPE_TREE:
        raise ValueError('Unexpected reviewed recipe repository')
    if stage['lockSha256'] != sha(canonical(lock)) or review['lockSha256'] != stage['lockSha256']:
        raise ValueError('Dependency/source review lock mismatch')
    plan, contents = source.git_material(recipes, RECIPE_COMMIT, RECIPE_TREE, 'recipes')
    packages = lock['packages']
    recipe_names = {p['name'] for p in packages if p['name'].startswith('ext_')}
    if set(review['packages']) != recipe_names: raise ValueError('Reviewed package set differs from binary lock')
    selected = dependency_runtime(stage['files'])
    counts = Counter()
    for item in selected.values():
        for origin in item['inputs']: counts.update(origin['owners'])
    notices = {n: r for n, r in stage['files'].items() if notice_candidate(n)}
    package_records = []
    for package in packages:
        name = package['name']
        record = {'name': name, 'binarySha256': package['sha256'],
                  'binaryVersion': package['version'], 'runtimeSelectedFileCount': counts[name],
                  'noticeCandidates': [n for n, r in notices.items() if name in r['owners']]}
        if name in recipe_names:
            if package['sourceCommit'] != RECIPE_COMMIT: raise ValueError('Package recipe revision differs')
            path = 'recipes/' + name + '/CMakeLists.txt'
            record['recipeFile'] = {**plan['files'][path], 'path': path}
            record['windowsInputs'] = selected_declarations(contents[path].decode(), review['packages'][name])
        else:
            record['toolSourceCommit'] = package['sourceCommit']
            record['sourceStatus'] = 'tool-source-and-bundled-runtime-review-required'
        # Zero runtime files is deliberately not a build-only classification:
        # libaom, x265 variants, Highway and header libraries are compiled in.
        record['sourceAndLicenseReviewComplete'] = False
        package_records.append(record)
    result = {'schema': 1, 'kind': 'bristlune-native-source-trace',
              'correspondingSourceComplete': False, 'licenseReviewComplete': False,
              'lockSha256': stage['lockSha256'],
              'recipeRepository': {'commit': RECIPE_COMMIT, 'tree': RECIPE_TREE,
                                   'url': 'https://invent.kde.org/packaging/krita-deps-management.git'},
              'recipesSourcePlanSha256': source.digest(canonical(plan) + b'\n'),
              'recipeFileCount': len(plan['files']),
              'lockedFileCount': len(stage['files']), 'packageCount': len(packages),
              'dependencyRuntime': {'scope': 'Dependency selection only; final application/native installed tree is separate.',
                                    'selectorSha256': source.measure(source.ROOT / 'packaging/windows/qualification/runtime_stage.py')['sha256'],
                                    'fileCount': len(selected), 'bytes': sum(r['bytes'] for r in selected.values()),
                                    'inventorySha256': source.digest(canonical(selected) + b'\n')},
              'noticeDiscovery': {'scope': 'Filename candidates only; missing notices and nested licenses remain open.',
                                  'candidateCount': len(notices),
                                  'inventorySha256': source.digest(canonical(notices) + b'\n')},
              'packages': package_records}
    return result, selected, notices, plan, contents


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recipes', type=Path, required=True)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--check', action='store_true', help='Require regeneration to equal the committed inventory')
    args = parser.parse_args()
    if args.output.exists(): raise FileExistsError('Existing audit output is preserved')
    lock = load_lock(LOCK)
    stage = verify_stage(lock, args.cache, args.stage)
    review = source.read_json(HERE / 'windows-selection.json')
    report, runtime, notices, plan, contents = build_inventory(lock, args.recipes, stage, review)
    if args.check and report != source.read_json(HERE / 'inventory.json'):
        raise ValueError('Regenerated source inventory differs from committed review')
    args.output.mkdir()
    for name, value in [('inventory.json', report), ('dependency-runtime-files.json', runtime),
                        ('notice-candidates.json', notices), ('recipes-source-plan.json', plan)]:
        with (args.output / name).open('xb') as output: output.write(canonical(value) + b'\n')
    receipt = source.collect(plan, contents, args.output / 'Bristlune-native-recipes.tar')
    with (args.output / 'recipes-collection-receipt.json').open('xb') as output:
        output.write(canonical(receipt) + b'\n')
    notice_plan = source.new_plan({'lockSha256': report['lockSha256'],
                                   'noticeCandidatesSha256': report['noticeDiscovery']['inventorySha256'],
                                   'scope': 'Unreviewed notice candidates with original paths and owners.'},
                                  {'notices/' + name: {**{k: r[k] for k in ('bytes', 'sha256')}, 'mode': 0o644}
                                   for name, r in notices.items()})
    notice_receipt = source.collect(notice_plan, {'notices/' + n: args.stage / n for n in notices},
                                    args.output / 'Bristlune-native-notice-candidates.tar')
    for name, value in [('notices-source-plan.json', notice_plan),
                        ('notices-collection-receipt.json', notice_receipt)]:
        with (args.output / name).open('xb') as output: output.write(canonical(value) + b'\n')
    print(json.dumps({'packages': report['packageCount'], 'runtimeFiles': len(runtime),
                      'noticeCandidates': len(notices), 'recipes': receipt,
                      'notices': notice_receipt,
                      'correspondingSourceComplete': False}, sort_keys=True))


if __name__ == '__main__': main()
