# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
"""Independent readback of the actual Windows-installed package payload."""
import argparse
import json
from pathlib import Path
from runtime_stage import measure_tree,measure
from manifest_identity import verify_manifest_identity


def verify(root,record):
    root=Path(root);actual=measure_tree(root);expected=record['payload']
    metadata={'AppxSignature.p7x','AppxBlockMap.xml','[Content_Types].xml','AppxMetadata/CodeIntegrity.cat'}
    if set(actual)-set(expected)-metadata:raise ValueError('Unexpected installed package files')
    for name,value in expected.items():
        if actual.get(name)!=value:raise ValueError('Installed bytes differ: '+name)
    verify_manifest_identity((root/'AppxManifest.xml').read_bytes(),record['identity'])
    return {'verifiedPayloadFiles':len(expected),'installedManifest':measure(root/'AppxManifest.xml')}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path)
    p.add_argument('--record',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    result=verify(a.root,json.loads(a.record.read_text(encoding='utf-8-sig')))
    with a.output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
