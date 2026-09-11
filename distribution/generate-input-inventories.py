# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
"""Record candidate source/resources without asserting distribution clearance."""
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

source = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(source / 'build-tools/ci-scripts'))
from locked_windows_deps import canonical, load_lock, sha

lock = load_lock(source / 'build-tools/ci-scripts/brushquay-dependency-lock.json')
lock_hash = sha(canonical(lock))
spdx = {'spdxVersion': 'SPDX-2.3', 'dataLicense': 'CC0-1.0', 'SPDXID': 'SPDXRef-DOCUMENT',
        'name': 'BrushQuay candidate native build inputs',
        'documentNamespace': 'https://brushquay.trieflow.com/spdx/build-inputs/' + lock_hash,
        'creationInfo': {'created': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                         'creators': ['Organization: Trieflow LLC', 'Tool: BrushQuay locked input inventory 1']},
        'documentComment': 'Candidate inventory only. License conclusions and complete corresponding-source closure remain unverified. ext_* sourceCommit values identify dependency build recipes, not every upstream library source.',
        'packages': [], 'relationships': []}
for package in lock['packages']:
    identifier = 'SPDXRef-Package-' + package['name'].replace('_', '-')
    spdx['packages'].append({'SPDXID': identifier, 'name': package['name'], 'versionInfo': package['version'],
                            'downloadLocation': package['url'], 'filesAnalyzed': False,
                            'checksums': [{'algorithm': 'SHA256', 'checksumValue': package['sha256']}],
                            'licenseConcluded': 'NOASSERTION', 'licenseDeclared': 'NOASSERTION',
                            'copyrightText': 'NOASSERTION',
                            'comment': 'Candidate input. Recorded build/source revision: ' + package['sourceCommit'] +
                                       '. Complete upstream source inventory, patches, license/notice and redistribution decision are pending.'})
    spdx['relationships'].append({'spdxElementId': 'SPDXRef-DOCUMENT', 'relationshipType': 'DESCRIBES', 'relatedSpdxElement': identifier})
    for dependency in package['dependencies']:
        spdx['relationships'].append({'spdxElementId': identifier, 'relationshipType': 'DEPENDS_ON',
                                      'relatedSpdxElement': 'SPDXRef-Package-' + dependency.replace('_', '-')})
(source / 'distribution/dependencies.spdx.json').write_text(json.dumps(spdx, indent=2) + '\n', encoding='utf-8')
files = subprocess.check_output(['git', '-C', str(source), 'ls-files', '-z', 'krita/data'], text=True).split('\0')
with (source / 'distribution/resources.csv').open('w', newline='', encoding='utf-8') as output:
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(['path', 'sha256', 'bytes', 'source_commit', 'author', 'license', 'modification', 'release_inclusion'])
    for name in sorted(filter(None, files)):
        path = source / name
        if not path.is_file():
            continue
        data = path.read_bytes()
        writer.writerow([name, hashlib.sha256(data).hexdigest(), len(data), lock['applicationSourceCommit'],
                         'NOASSERTION', 'NOASSERTION', 'unchanged upstream baseline', 'not release-cleared'])
print('Recorded', len(spdx['packages']), 'candidate package inputs and', len(list(filter(None, files))), 'source data paths; no licensing clearance asserted.')
