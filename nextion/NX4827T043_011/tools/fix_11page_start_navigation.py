"""Fix stale `page pDataRun` in *user-edited* 11-page Nextion HMI.

Backup original bytes; modify only the valid pTake.mStart event, associated
page CRC, and if needed the 2.pa directory entry. Preserve all colors/assets.
Never activate the Nextion hardware or modify unrelated HMI versions.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import struct

HERE=Path(__file__).resolve()
ROOT=HERE.parents[3]
DISPLAY=HERE.parents[1]
HMI=DISPLAY/'project/RoastSense_NX4827T043_011.HMI'
BACKUP=ROOT/'results/hmi-repair-backup-20261016'
EXPECTED_SHA='9729ea9621299fc89915eeabc26660f78c1e6c3edb9e3eb1555ae6cd267a4967'
BAD=b'page pDataRun'
GOOD=b'doevents     '  # valid Nextion command, padded to exactly 13 bytes
assert len(BAD)==len(GOOD)


def load_helper():
    spec=importlib.util.spec_from_file_location('nx',DISPLAY/'tools/build_figma_fix_hmi.py')
    assert spec is not None and spec.loader is not None
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def find_valid_take(raw:bytes,h):
    candidates=[]
    offset=0
    while (pos:=raw.find(b'pTake',offset))!=-1:
        offset=pos+1
        start=pos-24
        if start<0 or start+56>len(raw): continue
        size=struct.unpack_from('<I',raw,start+4)[0]
        if size<56 or size>30000 or start+size>len(raw):continue
        blob=raw[start:start+size]
        if blob[24:40].split(b'\0',1)[0]!=b'pTake':continue
        if struct.unpack_from('<I',blob,0)[0]!=h.page_crc(blob):continue
        try:
            _,_,_,_,_,start_record=h.find_component(blob,'mStart')
            assert b'EVT:DATA_START' in start_record
        except (KeyError,AssertionError):
            continue
        if BAD in start_record:
            candidates.append((start,size,blob,start_record))
    assert candidates,'No CRC-valid pTake.mStart with stale navigation'
    return candidates[-1]


def main():
    raw=HMI.read_bytes()
    sha=hashlib.sha256(raw).hexdigest()
    if sha!=EXPECTED_SHA:
        raise RuntimeError('HMI changed since audit, refusing to overwrite: '+sha)
    helper=load_helper()
    count=struct.unpack_from('<I',raw,0)[0]
    end=4+count*helper.ENTRY_SIZE
    assert helper.directory_checksum(raw[:end])==struct.unpack_from('<I',raw,end)[0]
    assert raw[:end]==raw[helper.BACKUP_DIR_OFFSET:helper.BACKUP_DIR_OFFSET+end]
    start,size,original_page,original_start=find_valid_take(raw,helper)
    assert original_start.count(BAD)==1
    assert raw.count(BAD)==1, 'Unexpected additional stale references need review'
    fixed_page=bytearray(original_page)
    _,_,_,_,record_at,rec=helper.find_component(original_page,'mStart')
    event_at=rec.index(BAD)
    fixed_page[record_at+event_at:record_at+event_at+len(BAD)]=GOOD
    struct.pack_into('<I',fixed_page,0,helper.page_crc(bytes(fixed_page)))
    fixed_page=bytes(fixed_page)
    assert struct.unpack_from('<I',fixed_page,0)[0]==helper.page_crc(fixed_page)
    assert BAD not in fixed_page
    new_start_record=helper.find_component(fixed_page,'mStart')[-1]
    assert b'EVT:DATA_START' in new_start_record
    assert GOOD in new_start_record
    assert len(original_page)==len(fixed_page)
    # Directory 2.pa was found referencing a stale/CRC-invalid blob in this
    # manual-save file. Redirect it to the existing validated page at `start`.
    fixed=bytearray(raw)
    fixed[start:start+size]=fixed_page
    idx,entry_off,name,old_start,old_size,deleted,tail=helper.find_entry(raw,'2.pa')
    assert deleted==0
    new_entry=struct.pack(helper.ENTRY_FMT,b'2.pa'.ljust(16,b'\0'),start,size,0,*tail)
    for base in (0,helper.BACKUP_DIR_OFFSET):
        fixed[base+entry_off:base+entry_off+helper.ENTRY_SIZE]=new_entry
    new_crc=helper.directory_checksum(bytes(fixed[:end]))
    for base in (0,helper.BACKUP_DIR_OFFSET):
        struct.pack_into('<I',fixed,base+end,new_crc)
    fixed=bytes(fixed)
    assert BAD not in fixed
    assert helper.get_page(fixed,2)==fixed_page
    assert len(fixed)==len(raw)
    # Only the directory and the chosen pTake page blob may differ. The rest,
    # including picture resources and other page blobs, is byte-for-byte same.
    diff=[i for i,(a,b) in enumerate(zip(raw,fixed)) if a!=b]
    assert diff and all(i<end+4 or
                        helper.BACKUP_DIR_OFFSET<=i<helper.BACKUP_DIR_OFFSET+end+4 or
                        start<=i<start+size for i in diff)
    BACKUP.mkdir(parents=True,exist_ok=True)
    backup=BACKUP/('ROOT_HMI_BEFORE_11PAGE_NAV_FIX_'+sha[:12]+'.HMI')
    if backup.exists():raise FileExistsError(backup)
    backup.write_bytes(raw)
    assert hashlib.sha256(backup.read_bytes()).hexdigest()==sha
    tmp=HMI.with_suffix('.HMI.pending')
    if tmp.exists():raise FileExistsError(tmp)
    try:
        tmp.write_bytes(fixed)
        assert helper.get_page(tmp.read_bytes(),2)==fixed_page
        os.replace(tmp,HMI)
    finally:
        if tmp.exists():tmp.unlink()
    assert HMI.read_bytes()==fixed
    print('11PAGE_PTAKE_NAVIGATION_REPAIR_PASS',
          'before=',sha,'after=',hashlib.sha256(fixed).hexdigest(),
          'page2_offset=',start,'page2_size=',size,
          'changed_bytes=',len(diff),
          'event_start_retained=true',
          'picture_fonts_unchanged=true',
          'backup=',backup.relative_to(ROOT))


if __name__=='__main__':main()
