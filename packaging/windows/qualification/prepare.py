# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
"""Build only a disposable, source-bound native qualification MSIX."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from runtime_stage import ROOT, measure, measure_tree, no_links, select_runtime, materialize
sys.path.insert(0,str(ROOT/'build-tools/ci-scripts'))
from locked_windows_deps import canonical, load_lock, sha, verify_stage
from source_state import require_clean_source
from build_msix import manifest_bytes, load_tools, confirm_tools, write_new
from verify_brushquay_msix import verify_msix
from manifest_identity import verify_manifest_identity

IDENTITY={'PackageName':'Trieflow.Bristlune.Qualification','Publisher':'CN=Bristlune-CI-Qualification',
          'Version':'1.0.1.0','MinWindowsVersion':'10.0.19041.0','MaxWindowsVersionTested':'10.0.26100.0'}
PACKAGE='Bristlune.Qualification_1.0.1.0_x64.msix'
EXPECTED_TESTS=sorted('libs-ui-'+name for name in ('KisBrushQuayIdentityTest','KisBrushQuayWorkspaceTest',
    'KisClipboardNullTest','KisExportFileTransactionTest','KisExportPresetIntegrationTest','KisExportPresetStoreTest'))
QT_CONF=b'[Paths]\nPrefix=..\nPlugins=plugins\nLibraries=bin\nTranslations=translations\nQmlImports=qml\n'


def native_evidence(source,commit,run,attempt,source_observation=None):
    if not re.fullmatch('[0-9a-f]{40}',commit or '') or not all(re.fullmatch('[1-9][0-9]*',v or '') for v in (run,attempt)):
        raise ValueError('Exact source/run/attempt required')
    def git(*args):return subprocess.check_output(['git','-C',str(source),*args],text=True).strip()
    require_clean_source(source,commit,source_observation,'before-package')
    found=[]
    for path in (source/'.brushquay/evidence').glob('*/native-build.json'):
        if path.stat().st_size>16*1024*1024:raise ValueError('Native evidence exceeds bound')
        data=json.loads(path.read_text(encoding='utf-8'))
        if data.get('sourceHead')==commit and data.get('workflowRunId')==run and data.get('workflowRunAttempt')==attempt:
            found.append((path,data))
    if len(found)!=1:raise ValueError('Exactly one native receipt for this source/run/attempt is required')
    path,data=found[0]
    if data.get('sourceTree')!=git('show','-s','--format=%T','HEAD') or data.get('status')!='compiled_and_installed_not_packaged' or data.get('inputStageUnchanged') is not True or data.get('productTests')!=EXPECTED_TESTS:
        raise ValueError('Full native build, all six suites and unchanged input stage required')
    report=path.with_name('product-tests.xml')
    if measure(report)!=data.get('productTestReport') or report.stat().st_size>16*1024*1024:
        raise ValueError('Product suite XML differs from the native run receipt')
    tests=ET.parse(report).getroot()
    cases=tests.findall('.//testcase')
    if len(cases)!=6 or sorted(c.get('name') for c in cases)!=EXPECTED_TESTS or any(c.get('status')!='run' or c.get('classname')!=c.get('name') or c.find('failure') is not None or c.find('error') is not None or c.find('skipped') is not None for c in cases):
        raise ValueError('Native test report does not prove all six required product suites')
    return path,data


def pack(payload,expected,tools,tool_lock,output):
    commands=[[tools['makepri']['path'],'new','/pr',str(payload),'/mn',str(payload/'AppxManifest.xml'),
               '/cf',str(ROOT/'packaging/windows/msix/priconfig.xml'),'/of',str(payload/'resources.pri')],
              [tools['makeappx']['path'],'pack','/d',str(payload),'/p',str(output/PACKAGE),'/no','/v','/h','SHA256'],
              [tools['makeappx']['path'],'unpack','/p',str(output/PACKAGE),'/d',str(output/'unpacked'),'/no','/v']]
    for index,command in enumerate(commands):
        confirm_tools(tool_lock,tools)
        with (output/('sdk-'+str(index+1)+'.log')).open('xb') as log:
            subprocess.run(command,check=True,stdout=log,stderr=subprocess.STDOUT,timeout=600,shell=False)
        if index==0:
            expected['resources.pri']=measure(payload/'resources.pri')
            if expected['resources.pri']['bytes']==0:raise ValueError('Empty generated resource index')
        if measure_tree(payload)!=expected:raise ValueError('SDK input payload changed')
    verified=verify_msix(output/PACKAGE,expected,IDENTITY)
    unpacked=measure_tree(output/'unpacked')
    for name in ('[Content_Types].xml','AppxBlockMap.xml'):unpacked.pop(name,None)
    if unpacked!=expected:raise ValueError('SDK-unpacked payload differs from exact selected inputs')
    verify_manifest_identity((output/'unpacked/AppxManifest.xml').read_bytes(),IDENTITY)
    confirm_tools(tool_lock,tools)
    return verified


def prepare(source,output,evidence,tool_lock,commit,run,attempt):
    if sys.platform!='win32':raise ValueError('Disposable MSIX preparation requires native Windows')
    source=Path(source).absolute();output=Path(output).absolute();evidence=Path(evidence).absolute()
    no_links(source);no_links(output.parent);no_links(evidence.parent)
    if os.path.lexists(output) or os.path.lexists(evidence):raise ValueError('Qualification output already exists')
    path,native=native_evidence(source,commit,run,attempt,evidence.parent/'source-before-package.json');native_digest=measure(path)
    tools=load_tools(tool_lock)
    if tools['sdkVersion']!='10.0.26100.0':raise ValueError('Only the reviewed SDK version is accepted')
    lock=load_lock(source/'build-tools/ci-scripts/brushquay-dependency-lock.json')
    if native['lockSha256']!=sha(canonical(lock)):raise ValueError('Native dependency lock differs')
    locked=source/'.brushquay/locked';install=source/'.brushquay/install'
    manifest=verify_stage(lock,source/'.brushquay/cache',locked)
    if not native.get('installedTree') or measure_tree(install)!=native['installedTree']:
        raise ValueError('Complete CMake install tree differs from the native build')
    selected=select_runtime(native['installedTree'],manifest['files'])
    for name in ('bin/bristlune.exe','bin/bristlune.dll','plugins/platforms/qwindows.dll','bin/Qt6Core.dll','bin/libc++.dll','bin/libunwind.dll','bin/libwinpthread-1.dll'):
        if name not in selected:raise ValueError('Required deployed runtime missing: '+name)
    output.mkdir();evidence.mkdir()
    record={'schema':1,'qualificationOnly':True,'sourceCommit':commit,'workflowRunId':run,'workflowRunAttempt':attempt,
            'sourceTree':native['sourceTree'],'nativeEvidence':native_digest,'lockSha256':native['lockSha256'],
            'identity':IDENTITY,'applicationId':'BrushQuay','executable':'Bristlune/bin/bristlune.exe',
            'licenseReviewComplete':False,'correspondingSourceComplete':False,'publicBinaryDistributionAuthorizedByThisReceipt':False,
            'runtimeInputs':selected,'sdk':tools,'status':'preparing','signed':False}
    try:
        payload=output/'payload';payload.mkdir()
        materialize(install,locked,selected,payload/'Bristlune')
        conf=payload/'Bristlune/bin/qt.conf';write_new(conf,QT_CONF)
        record['runtimeGeneratedFiles']={'Bristlune/bin/qt.conf':measure(conf)}
        asset_root=ROOT/'packaging/windows/msix';assets=json.loads((asset_root/'assets.lock.json').read_text())
        for relative,digest in assets.items():
            if measure(asset_root/'pkg'/relative)!=digest:raise ValueError('Original package artwork changed')
            write_new(payload/relative,(asset_root/'pkg'/relative).read_bytes())
        write_new(payload/'AppxManifest.xml',manifest_bytes(IDENTITY))
        expected=measure_tree(payload)
        record['verification']=pack(payload,expected,tools,tool_lock,output)
        if measure(path)!=native_digest or measure_tree(install)!=native['installedTree']:
            raise ValueError('Native inputs changed during qualification staging')
        verify_stage(lock,source/'.brushquay/cache',locked)
        record.update(status='disposable_package_verified_not_installed',payload=expected,package=measure(output/PACKAGE))
        write_new(output/'package-record.json',canonical(record)+b'\n')
        return record
    except Exception as error:
        record['error']=str(error)
        raise
    finally:
        write_new(evidence/'qualification-package.json',canonical(record)+b'\n')
        for path in output.glob('sdk-*.log'):shutil.copyfile(path,evidence/path.name)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','output','evidence','sdk-tools'):p.add_argument('--'+name,required=True,type=Path)
    p.add_argument('--commit',required=True);p.add_argument('--run',required=True);p.add_argument('--attempt',required=True)
    args=p.parse_args()
    prepare(args.source,args.output,args.evidence,args.sdk_tools,args.commit,args.run,args.attempt)
