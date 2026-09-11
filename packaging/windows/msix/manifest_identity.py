# SPDX-FileCopyrightText: 2026 Trieflow LLC
# SPDX-License-Identifier: GPL-3.0-or-later
"""Validate the approved identity and compare owned manifest semantics exactly."""
import re
import xml.etree.ElementTree as ET

IDENTITY_FIELDS={'PackageName','Publisher','Version','MinWindowsVersion','MaxWindowsVersionTested'}
FOUNDATION='{http://schemas.microsoft.com/appx/manifest/foundation/windows10}'
UAP='{http://schemas.microsoft.com/appx/manifest/uap/windows10}'
RESTRICTED='{http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities}'
TEMPLATE_MARKER=re.compile(r'@[^@]*@')
MAX_MANIFEST_BYTES=1024*1024

def version(value):
    if not isinstance(value,str) or not re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)',value):
        raise ValueError('Expected four-component Windows version')
    numbers=tuple(map(int,value.split('.')))
    if any(n>65535 for n in numbers): raise ValueError('Windows version component exceeds 65535')
    return numbers

def validate_identity_values(identity):
    if not isinstance(identity,dict) or set(identity)!=IDENTITY_FIELDS:
        raise ValueError('Exactly the five approved identity fields are required')
    for value in identity.values():
        if not isinstance(value,str) or not value or value!=value.strip() or any(ord(c)<32 for c in value):
            raise ValueError('Invalid approved identity value')
        if TEMPLATE_MARKER.search(value): raise ValueError('Template markers are forbidden in identity values')
        if 'REQUIRED' in value.upper() or 'KRITA' in value.upper() or '03E730BB' in value.upper():
            raise ValueError('Placeholder or upstream identity')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{1,48}[A-Za-z0-9]',identity['PackageName']): raise ValueError('Invalid package name')
    if not identity['Publisher'].startswith('CN=') or len(identity['Publisher'])>8192: raise ValueError('Invalid publisher distinguished name')
    if version(identity['Version'])[0]<1: raise ValueError('Package major version must be positive')
    minimum=version(identity['MinWindowsVersion']);tested=version(identity['MaxWindowsVersionTested'])
    if minimum<(10,0,17763,0) or tested<minimum: raise ValueError('Invalid Windows compatibility range')

def verify_manifest_identity(data,identity):
    """Return parsed fields only after they exactly match the approved contract.

    Namespace-aware cardinality checks reject duplicate/surplus identity,
    dependency, application, capability and extension nodes. XML escaping is
    decoded by the parser; no string substitution is performed during checking.
    """
    validate_identity_values(identity)
    if not isinstance(data,bytes) or len(data)>MAX_MANIFEST_BYTES:
        raise ValueError('Manifest must be bounded UTF-8 XML')
    try: text=data.decode('utf-8-sig')
    except UnicodeDecodeError as error: raise ValueError('Manifest must be UTF-8') from error
    if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper(): raise ValueError('Manifest declarations are forbidden')
    try: root=ET.fromstring(text)
    except ET.ParseError as error: raise ValueError('Invalid manifest XML') from error
    sections={'Identity','Properties','Resources','Dependencies','Applications','Capabilities'}
    if root.tag!=FOUNDATION+'Package' or len(root)!=len(sections) or {n.tag for n in root}!={FOUNDATION+s for s in sections}:
        raise ValueError('Manifest identity structure has duplicate, missing or unexpected sections')
    nodes={n.tag:n for n in root}
    def attributes(node,expected,label):
        if node.attrib!=expected: raise ValueError('Manifest '+label+' differs from approved identity')
    def child(section,tag):
        parent=nodes[FOUNDATION+section]
        if parent.attrib or len(parent)!=1 or parent[0].tag!=tag:
            raise ValueError('Manifest '+section+' must contain exactly the approved entry')
        return parent[0]
    package=nodes[FOUNDATION+'Identity']
    attributes(package,{'Name':identity['PackageName'],'Publisher':identity['Publisher'],
        'Version':identity['Version'],'ProcessorArchitecture':'x64'},'package identity')
    target=child('Dependencies',FOUNDATION+'TargetDeviceFamily')
    attributes(target,{'Name':'Windows.Desktop','MinVersion':identity['MinWindowsVersion'],
        'MaxVersionTested':identity['MaxWindowsVersionTested']},'target device family')
    application=child('Applications',FOUNDATION+'Application')
    attributes(application,{'Id':'BrushQuay','Executable':r'BrushQuay\bin\brushquay.exe',
        'EntryPoint':'Windows.FullTrustApplication'},'application identity')
    if len(application)!=1 or application[0].tag!=UAP+'VisualElements' or len(application[0]):
        raise ValueError('Manifest application may contain only its approved visual elements; extensions are forbidden')
    capability=child('Capabilities',RESTRICTED+'Capability')
    attributes(capability,{'Name':'runFullTrust'},'capabilities')
    if any(len(node) for node in (package,target,capability)):
        raise ValueError('Unexpected child in manifest identity fields')
    return {'package':dict(package.attrib),'application':dict(application.attrib),
            'capabilities':['runFullTrust'],'targetDeviceFamily':dict(target.attrib)}
