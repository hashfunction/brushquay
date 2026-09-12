# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
import binascii
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile
import zlib
from workflow_files import verify_artwork, png_pixels
from runtime_stage import measure


def png(pixels,width=512,height=384):
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',binascii.crc32(kind+data)&0xffffffff)
    rows=b''.join(b'\0'+pixels[y*width*4:(y+1)*width*4] for y in range(height))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b'')


def kra(path,pixels):
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('mimetype','application/x-krita')
        z.writestr('maindoc.xml','<DOC><IMAGE width="512" height="384"/></DOC>')
        z.writestr('mergedimage.png',png(pixels))


class WorkflowFileTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        self.blank=b'\xff'*512*384*4
        self.art=bytearray(self.blank)
        for y in range(180,190):
            for x in range(100,400):self.art[(y*512+x)*4:(y*512+x+1)*4]=b'\x20\x30\x40\xff'
        kra(self.root/'blank.kra',self.blank);kra(self.root/'artwork.kra',self.art);kra(self.root/'reopened.kra',self.art)
        (self.root/'artwork.png').write_bytes(png(self.art))
        (self.root/'protected.txt').write_bytes(b'untouched foreign target')
        self.protected={'protected.txt':measure(self.root/'protected.txt'),'blank.kra':measure(self.root/'blank.kra')}
    def test_independent_decoding_matches_painted_export_and_reopened_document(self):
        result=verify_artwork(self.root,self.protected)
        self.assertEqual(result['dimensions'],[512,384]);self.assertEqual(result['changed_pixels'],3000)
        self.assertTrue(result['export_matches_saved_artwork'] and result['reopened_pixels_match'])
    def test_no_stroke_cannot_qualify(self):
        kra(self.root/'artwork.kra',self.blank)
        with self.assertRaises(ValueError):verify_artwork(self.root,self.protected)
    def test_export_and_reopen_must_match_independently(self):
        for target in ('artwork.png','reopened.kra'):
            original=(self.root/target).read_bytes()
            if target.endswith('.png'):(self.root/target).write_bytes(png(self.blank))
            else:kra(self.root/target,self.blank)
            with self.subTest(target=target),self.assertRaises(ValueError):verify_artwork(self.root,self.protected)
            (self.root/target).write_bytes(original)
    def test_protected_bytes_and_source_artwork_never_change(self):
        for target in self.protected:
            original=(self.root/target).read_bytes();(self.root/target).write_bytes(b'changed')
            with self.subTest(target=target),self.assertRaises(ValueError):verify_artwork(self.root,self.protected)
            (self.root/target).write_bytes(original)
    def test_wrong_dimensions_corrupt_crc_and_trailing_data_refused(self):
        original=png(self.art)
        corrupt=bytearray(original);corrupt[-5]^=1
        for data in (png(b'\xff'*4,1,1),bytes(corrupt),original+b'trailing'):
            with self.subTest(size=len(data)),self.assertRaises(ValueError):png_pixels(data)
    def test_document_zip_aliases_and_links_refused(self):
        path=self.root/'artwork.kra'
        with zipfile.ZipFile(path,'a') as z:z.writestr('../foreign',b'foreign')
        with self.assertRaises(ValueError):verify_artwork(self.root,self.protected)
    def test_foreign_link_target_is_preserved(self):
        foreign=self.root/'foreign.png';foreign.write_bytes(png(self.art))
        (self.root/'artwork.png').unlink();(self.root/'artwork.png').symlink_to(foreign)
        with self.assertRaises(ValueError):verify_artwork(self.root,self.protected)
        self.assertEqual(foreign.read_bytes(),png(self.art))

if __name__=='__main__':unittest.main()
