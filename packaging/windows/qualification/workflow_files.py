# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
"""Independent bounded KRA/PNG readback; no application code or image writer."""
import argparse
import binascii
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import struct
import xml.etree.ElementTree as ET
import zipfile
import zlib
from runtime_stage import measure, no_links
from verify_brushquay_msix import checked_path, register_path

WIDTH,HEIGHT=512,384
MAX_FILE=32*1024*1024


def png_pixels(data):
    if len(data)>MAX_FILE or data[:8]!=b'\x89PNG\r\n\x1a\n':raise ValueError('Expected a bounded PNG')
    position=8;header=None;compressed=bytearray();ended=False;seen_data=False
    while position<len(data):
        if len(data)-position<12:raise ValueError('Truncated PNG chunk')
        size=struct.unpack_from('>I',data,position)[0];kind=data[position+4:position+8]
        end=position+12+size
        if end>len(data):raise ValueError('Truncated PNG payload')
        value=data[position+8:position+8+size]
        crc=struct.unpack_from('>I',data,position+8+size)[0]
        if (binascii.crc32(kind+value)&0xffffffff)!=crc:raise ValueError('PNG CRC differs')
        if header is None and kind!=b'IHDR':raise ValueError('PNG header is not first')
        if kind==b'IHDR':
            if header is not None or size!=13:raise ValueError('Duplicate/invalid PNG header')
            header=struct.unpack('>IIBBBBB',value)
        elif kind==b'IDAT':compressed.extend(value);seen_data=True
        elif kind==b'IEND':
            if size or not seen_data or end!=len(data):raise ValueError('PNG end/trailing data differs')
            ended=True;break
        elif not kind[0]&32 and kind!=b'PLTE':raise ValueError('Unsupported critical PNG chunk')
        position=end
    if not ended or header is None:raise ValueError('Incomplete PNG')
    width,height,depth,color,compression,filter_method,interlace=header
    if (width,height)!=(WIDTH,HEIGHT) or depth!=8 or color not in (2,6) or any((compression,filter_method,interlace)):
        raise ValueError('Expected exact 512x384 8-bit non-interlaced RGB/RGBA image')
    channels=3 if color==2 else 4;stride=width*channels;expected=(stride+1)*height
    decoder=zlib.decompressobj();raw=decoder.decompress(compressed,expected+1)
    if len(raw)!=expected or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise ValueError('PNG scanline length/compressed stream differs')
    pixels=bytearray();previous=bytearray(stride)
    def paeth(a,b,c):
        p=a+b-c;dist=(abs(p-a),abs(p-b),abs(p-c))
        return (a,b,c)[dist.index(min(dist))]
    for y in range(height):
        start=y*(stride+1);method=raw[start];scan=bytearray(raw[start+1:start+1+stride])
        if method>4:raise ValueError('Unknown PNG filter')
        for i in range(stride):
            left=scan[i-channels] if i>=channels else 0;up=previous[i];corner=previous[i-channels] if i>=channels else 0
            predictor=(0,left,up,(left+up)//2,paeth(left,up,corner))[method]
            scan[i]=(scan[i]+predictor)&255
        for x in range(width):
            offset=x*channels;pixels.extend(scan[offset:offset+3]);pixels.append(scan[offset+3] if channels==4 else 255)
        previous=scan
    return bytes(pixels)


def image_file(path):
    before=measure(path)
    if not 0<before['bytes']<=MAX_FILE:raise ValueError('Image file exceeds bound')
    pixels=png_pixels(Path(path).read_bytes())
    if measure(path)!=before:raise ValueError('Image changed while decoding')
    return pixels,before


def kra_image(path):
    before=measure(path)
    if not 0<before['bytes']<=MAX_FILE:raise ValueError('KRA exceeds bound')
    with zipfile.ZipFile(path) as archive:
        names={};seen={};directories=[];total=0
        for item in archive.infolist():
            if item.is_dir():directories.append(checked_path(item.filename[:-1]));continue
            register_path(item.filename,seen);names[item.filename]=item
            if stat.S_ISLNK(item.external_attr>>16) or item.flag_bits&1:raise ValueError('Linked/encrypted KRA entry')
            total+=item.file_size
            if item.file_size>MAX_FILE or total>MAX_FILE or len(names)>256:raise ValueError('KRA content exceeds bound')
        parents={str(p) for name in names for p in PurePosixPath(name).parents}
        if len(directories)!=len(set(directories)) or any(name not in parents for name in directories):raise ValueError('Unexpected KRA directory')
        if archive.read('mimetype')!=b'application/x-krita':raise ValueError('Not a Krita-format document')
        xml=archive.read('maindoc.xml')
        if len(xml)>1024*1024 or b'<!ENTITY' in xml.upper():raise ValueError('Unbounded/entity document XML')
        document=ET.fromstring(xml)
        images=[node for node in document.iter() if node.tag.rsplit('}',1)[-1]=='IMAGE']
        if len(images)!=1 or images[0].get('width')!='512' or images[0].get('height')!='384':raise ValueError('KRA document dimensions differ')
        pixels=png_pixels(archive.read('mergedimage.png'))
    if measure(path)!=before:raise ValueError('KRA changed while decoding')
    return pixels,before


def verify_artwork(root,protected):
    root=Path(root);no_links(root)
    for name,expected in protected.items():
        checked_path(name)
        if measure(root/name)!=expected:raise ValueError('Protected fixture changed: '+name)
    blank,blank_record=kra_image(root/'blank.kra')
    art,art_record=kra_image(root/'artwork.kra')
    exported,export_record=image_file(root/'artwork.png')
    reopened,reopen_record=kra_image(root/'reopened.kra')
    if blank!=b'\xff'*(WIDTH*HEIGHT*4):raise ValueError('Initial real UI document is not opaque white')
    changed=sum(art[i:i+4]!=blank[i:i+4] for i in range(0,len(art),4))
    if not 50<=changed<WIDTH*HEIGHT//2:raise ValueError('Real brush stroke did not change a bounded part of the blank image')
    if art!=exported:raise ValueError('PNG pixels differ from the saved artwork')
    if reopened!=exported:raise ValueError('Reopened/saved pixels differ from the exported PNG')
    return {'dimensions':[WIDTH,HEIGHT],'changed_pixels':changed,
            'export_matches_saved_artwork':True,'reopened_pixels_match':True,'protected_files_unchanged':True,
            'pixel_sha256':hashlib.sha256(art).hexdigest(),'files':{'blank.kra':blank_record,'artwork.kra':art_record,'artwork.png':export_record,'reopened.kra':reopen_record}}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True,type=Path);parser.add_argument('--protected',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
    result=verify_artwork(args.root,json.loads(args.protected.read_text(encoding='utf-8-sig')))
    with args.output.open('x',encoding='utf-8') as output:json.dump(result,output,indent=2)
