"""Restore jCycle's Progress type while retaining manually edited HMI UI.

Uses a known-good Progress record only for jCycle, but preserves its current
position, size, current background/foreground color, all other components,
pages, pictures and fonts. Produces backup and atomic file replacement.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import struct
import subprocess

ROOT=Path(__file__).resolve().parents[3]
DISPLAY=Path(__file__).resolve().parents[1]
REL='nextion/NX4827T043_011/project/RoastSense_NX4827T043_011_COMPILE_READY.HMI'
CANONICAL=ROOT/REL
BACKUP_DIR=ROOT/'results/hmi-repair-backup-20261016'
EXPECTED_INPUT_SHA256='625eab48f2aa3ad194684c78bd6be453ff28603af2c62be25f782c2f4d1feb30'


def helper_module():
    spec=importlib.util.spec_from_file_location('nextion_pagehelper',DISPLAY/'tools/build_figma_fix_hmi.py')
    assert spec is not None and spec.loader is not None
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def rebuild_with_progress(page:bytes,legacy_page:bytes,h):
    assert struct.unpack_from('<I',page,0)[0]==h.page_crc(page)
    _,_,_,_,_,rec_edited=h.find_component(page,'jCycle')
    _,_,_,_,_,rec_source=h.find_component(legacy_page,'jCycle')
    assert h.attr_bytes(rec_edited,'type')==b't'
    assert h.attr_bytes(rec_source,'type')==b'j'
    attrs=('id','objname','x','y','w','h')
    assert all(h.attr_bytes(rec_edited,x)==h.attr_bytes(rec_source,x) for x in attrs)
    bco=h.attr_bytes(rec_edited,'bco')
    pco=h.attr_bytes(rec_edited,'pco')
    assert bco is not None and len(bco)==2 and pco is not None and len(pco)==2
    new_progress=h.patch_record(rec_source,
                                bco=int.from_bytes(bco,'little'),
                                pco=int.from_bytes(pco,'little'))
    assert h.attr_bytes(new_progress,'type')==b'j'
    assert h.attr_bytes(new_progress,'val') is not None
    assert h.attr_bytes(new_progress,'bco')==bco
    assert h.attr_bytes(new_progress,'pco')==pco
    n=struct.unpack_from('<I',page,12)[0]
    assert n==11
    header=bytearray(page[:h.PCH_BASE]);pchs=bytearray();data=bytearray()
    for idx,_,_,third,_,rec in h.component_records(page):
        name=h.component_name(rec)
        if name=='jCycle':
            rec=new_progress
        rel_start=n*h.PCH_SIZE+len(data)
        pchs.extend(struct.pack('<III',rel_start,len(rec),third))
        data.extend(rec)
    result=bytearray(header+pchs+data)
    struct.pack_into('<I',result,4,len(result))
    struct.pack_into('<I',result,0,h.page_crc(bytes(result)))
    restored=bytes(result)
    assert struct.unpack_from('<I',restored,0)[0]==h.page_crc(restored)
    for (_,_,_,_,_,before),(_,_,_,_,_,after) in zip(h.component_records(page),h.component_records(restored)):
        if h.component_name(before)!='jCycle':
            assert before==after,'Unexpected change to other component'
    return restored


def main():
    h=helper_module()
    raw=CANONICAL.read_bytes()
    sha=hashlib.sha256(raw).hexdigest()
    if sha!=EXPECTED_INPUT_SHA256:
        raise RuntimeError(f'HMI was modified since ID repair, refusing write: {sha}')
    old_page=h.get_page(raw,3)
    git=subprocess.run(['git','show','HEAD:'+REL],cwd=ROOT,capture_output=True,check=True).stdout
    legacy_page=h.get_page(git,3)
    new_page=rebuild_with_progress(old_page,legacy_page,h)
    fixed=h.rewrite_page(raw,3,new_page)
    assert h.get_page(fixed,3)==new_page
    assert len(fixed)>len(raw)
    for idx in range(12):
        page=h.get_page(fixed,idx)
        assert struct.unpack_from('<I',page,0)[0]==h.page_crc(page)
        if idx!=3:
            assert page==h.get_page(raw,idx),('other_page_changed',idx)
    # Existing binary data remains byte-identical except directory updates.
    count=struct.unpack_from('<I',raw,0)[0]
    directory_end=4+count*h.ENTRY_SIZE+4
    zones=((0,directory_end),
           (h.BACKUP_DIR_OFFSET,h.BACKUP_DIR_OFFSET+directory_end))
    for idx,(a,b) in enumerate(zip(raw,fixed)):
        if a!=b:
            assert any(lo<=idx<hi for lo,hi in zones),('unexpected_old_binary_change',idx)
    BACKUP_DIR.mkdir(parents=True,exist_ok=True)
    backup=BACKUP_DIR/f'PAGE3_RESTORED_{sha[:12]}.HMI'
    if backup.exists():
        raise FileExistsError(backup)
    backup.write_bytes(raw)
    assert hashlib.sha256(backup.read_bytes()).hexdigest()==sha
    tmp=CANONICAL.with_suffix('.HMI.tmp')
    if tmp.exists():
        raise FileExistsError(tmp)
    try:
        tmp.write_bytes(fixed)
        assert h.get_page(tmp.read_bytes(),3)==new_page
        os.replace(tmp,CANONICAL)
    finally:
        if tmp.exists():
            tmp.unlink()
    assert CANONICAL.read_bytes()==fixed
    assert h.attr_bytes(h.find_component(h.get_page(fixed,3),'jCycle')[-1],'type')==b'j'
    print('JCYCLE_PROGRESS_RESTORED_PASS',
          'new_hmi_sha256=',hashlib.sha256(fixed).hexdigest(),
          'old_hmi_sha256=',sha,
          'page3_old_size=',len(old_page),
          'page3_new_size=',len(new_page),
          'backup=',backup.relative_to(ROOT),
          'other_11_pages_unchanged=true',
          'jCycle_geometry_and_edited_bco_pco_preserved=true')


if __name__=='__main__':
    main()
