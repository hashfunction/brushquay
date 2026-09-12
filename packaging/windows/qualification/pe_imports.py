# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only staged PE observations; never runtime selection or release approval."""
from pathlib import Path, PureWindowsPath, PurePosixPath
import json
import re
import subprocess
import threading
import time
from runtime_stage import measure

MAX_OUTPUT=8*1024*1024
MAX_FILES=1024
MAX_RECORD=16*1024*1024
READER_TIMEOUT=20
TOTAL_TIMEOUT=300
PE_SUFFIXES={'.dll','.exe','.pyd','.com'}

def parse_imports(text,path):
    """LLVM COFFDumper::printCOFFImports at locked a832a5222e489... ."""
    if not isinstance(text,str) or len(text.encode('utf-8'))>MAX_OUTPUT:raise ValueError('PE reader output exceeds bound')
    header={};result={'normalImports':[],'delayImports':[]};group=None;delay=False;nested=False
    numeric={'ImportLookupTableRVA','ImportAddressTableRVA','Attributes','ModuleHandle','ImportAddressTable',
             'ImportNameTable','BoundDelayImportTable','UnloadDelayImportTable','Address'}
    for line in text.splitlines():
        if len(line)>4096:raise ValueError('PE reader line exceeds bound')
        value=line.strip()
        if not value:continue
        if group is None:
            if value in ('Import {','DelayImport {'):
                if set(header)!={'File','Format','Arch','AddressSize'}:raise ValueError('PE reader header is incomplete')
                delay=value=='DelayImport {';group={'library':None,'symbols':[]};continue
            match=re.fullmatch('(File|Format|Arch|AddressSize): (.+)',value)
            if not match or match[1] in header:raise ValueError('Unexpected PE reader header')
            header[match[1]]=match[2];continue
        if value=='Import {' and delay and not nested:nested=True;continue
        if value=='}':
            if nested:nested=False;continue
            if group['library'] is None or not group['symbols']:raise ValueError('PE import descriptor is incomplete')
            result['delayImports' if delay else 'normalImports'].append(group);group=None;continue
        if value.startswith('Name: ') and not nested:
            name=value[6:]
            if group['library'] is not None or len(name)>255 or not name.isascii() or any(ord(c)<33 for c in name) or PureWindowsPath(name).name!=name or any(c in name for c in ':\\/'):
                raise ValueError('Invalid PE import library name')
            group['library']=name;continue
        match=re.fullmatch(r'Symbol: (.*)\(([0-9]+)\)',value)
        if match and (nested if delay else not nested):
            name=match[1].rstrip();ordinal=int(match[2])
            if ordinal>65535 or len(name)>2048 or not name.isascii() or any(ord(c)<32 for c in name):raise ValueError('Invalid PE import symbol')
            group['symbols'].append({'name':name,'hint':ordinal} if name else {'ordinal':ordinal});continue
        match=re.fullmatch(r'([A-Za-z]+): 0x[0-9A-Fa-f]+',value)
        if match and match[1] in numeric:continue
        raise ValueError('Unrecognized PE import record')
    if group is not None or nested or set(header)!={'File','Format','Arch','AddressSize'}:raise ValueError('Truncated PE reader output')
    if header!={'File':str(path),'Format':'COFF-x86-64','Arch':'x86_64','AddressSize':'64bit'}:
        raise ValueError('PE reader file or x64 format differs')
    return result

def read_imports(tool,path):
    # No shell, DLL loading or input execution. The retained locked tool reads PE data.
    command=[str(tool),'--coff-imports',str(path)]
    process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,shell=False)
    buffer=bytearray();failure=[]
    def drain():
        try:
            while True:
                part=process.stdout.read(65536)
                if not part:break
                room=MAX_OUTPUT+1-len(buffer);buffer.extend(part[:room])
                if len(buffer)>MAX_OUTPUT:
                    process.kill();break
        except Exception as error:failure.append(error)
    thread=threading.Thread(target=drain,daemon=True);thread.start()
    try:
        try:code=process.wait(timeout=READER_TIMEOUT)
        except subprocess.TimeoutExpired as error:
            process.kill();process.wait(timeout=5);raise TimeoutError('PE reader exceeded twenty seconds') from error
        thread.join(timeout=5)
        if thread.is_alive() or failure:raise ValueError('PE reader output did not complete')
        if len(buffer)>MAX_OUTPUT:raise ValueError('PE reader output exceeds bound')
        if code!=0:raise ValueError('PE reader failed with exit '+str(code)+': '+bytes(buffer[:2048]).decode('utf-8','replace'))
        try:text=bytes(buffer).decode('utf-8',errors='strict')
        except UnicodeError as error:raise ValueError('PE reader output is not UTF-8') from error
        return parse_imports(text,path)
    finally:
        if process.poll() is None:process.kill();process.wait(timeout=5)
        thread.join(timeout=5);process.stdout.close()

def observe_imports(payload,selected,tool,tool_record,context,reader=read_imports):
    record=dict(context,schema=1,observationOnly=True,releaseReady=False,status='incomplete',files=[],errors=[])
    start=time.monotonic();tool_before=None;record_bytes=0
    def failure(path,error):
        record['errors'].append({'path':path,'error':(type(error).__name__+': '+str(error))[:4096]})
    try:
        if not all(re.fullmatch('[0-9a-f]{40}',context.get(k,'')) for k in ('sourceCommit','sourceTree')) or not all(re.fullmatch('[1-9][0-9]*',context.get(k,'')) for k in ('workflowRunId','workflowRunAttempt')):
            raise ValueError('Exact current source/tree/run/attempt required')
        if tool_record.get('owners')!=['llvm-mingw']:raise ValueError('PE reader has no exact locked LLVM owner')
        tool_before=measure(tool)
        if tool_before!={k:tool_record[k] for k in ('bytes','sha256')}:raise ValueError('Locked PE reader bytes differ')
        record['reader']=dict(path=str(tool),**tool_before,owners=tool_record['owners'],arguments=['--coff-imports'])
        if any(not isinstance(n,str) or not n or '\\' in n or ':' in n or PurePosixPath(n).is_absolute() or '..' in PurePosixPath(n).parts for n in selected):
            raise ValueError('Unsafe selected runtime path')
        names=sorted(n for n in selected if Path(n).suffix.lower() in PE_SUFFIXES)
        if not names or len(names)>MAX_FILES:raise ValueError('Selected PE count is empty or exceeds bound')
        record['selectedPeFiles']=len(names)
        for name in names:
            if len(record['errors'])>=8 or time.monotonic()-start>TOTAL_TIMEOUT:raise ValueError('PE observation error/time bound reached')
            try:
                expected={k:selected[name][k] for k in ('bytes','sha256')};path=Path(payload)/name
                if measure(path)!=expected:raise ValueError('Selected PE bytes differ before inspection')
                imports=reader(Path(tool),path)
                if measure(path)!=expected:raise ValueError('Selected PE changed during inspection')
                row=dict(path=name,**expected,inputs=selected[name]['inputs'],**imports)
                record_bytes+=len(json.dumps(row,sort_keys=True,separators=(',',':')).encode('utf-8'))
                if record_bytes>MAX_RECORD:raise ValueError('PE observation metadata exceeds byte bound')
                record['files'].append(row)
            except Exception as error:failure(name,error)
        if not record['errors'] and len(record['files'])==len(names):record['status']='observed'
    except Exception as error:failure(None,error)
    finally:
        if tool_before is not None:
            try:
                if measure(tool)!=tool_before:raise ValueError('Locked PE reader changed during observation')
            except Exception as error:failure(None,error)
        if record['errors']:record['status']='incomplete'
    return record


def retain_imports(destination,payload,selected,tool,tool_record,context,reader=read_imports):
    """Metadata failure remains secondary to the original package/GUI workflow."""
    summary={'observationOnly':True,'releaseReady':False,'status':'incomplete'}
    try:
        record=observe_imports(payload,selected,tool,tool_record,context,reader)
        raw=(json.dumps(record,sort_keys=True,separators=(',',':'))+'\n').encode('utf-8')
        if len(raw)>MAX_RECORD+65536:raise ValueError('PE observation metadata exceeds total bound')
        with Path(destination).open('xb') as output:output.write(raw)
        summary.update(status=record['status'],path=str(destination),file=measure(destination),
                       observedFiles=len(record['files']),errors=record['errors'])
    except Exception as error:summary['error']=(type(error).__name__+': '+str(error))[:4096]
    return summary
