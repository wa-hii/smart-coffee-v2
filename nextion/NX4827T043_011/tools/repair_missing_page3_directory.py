"""Minimally restore a missing HMI 3.pa directory entry with existing page bytes.

The only changed byte ranges are primary and backup directory tables. ALL
resource images, fonts, edited page blobs, IDs, and event scripts stay intact.
Back up the byte-identical original before touching the canonical HMI.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import struct
import subprocess


ROOT = Path(__file__).resolve().parents[3]
DISPLAY = Path(__file__).resolve().parents[1]
CANONICAL_REL = 'nextion/NX4827T043_011/project/RoastSense_NX4827T043_011_COMPILE_READY.HMI'
CANONICAL = ROOT / CANONICAL_REL
EXPECTED_ORIGINAL_SHA256 = '3c771322159b73cc3dcec60894f40de3d508b61910176580fb8ce6f5bdd37bdd'
BACKUP_DIR = ROOT/'results/hmi-repair-backup-20261016'
PAGE_NAMES = ('pSplash','pHome','pTake','pDataRun','pDataDone','pTest',
              'pTestRun','pResult','pCal','pSettings','pHistory','pAlert')


def load_helper():
    spec = importlib.util.spec_from_file_location('nex_helper',DISPLAY/'tools/build_figma_fix_hmi.py')
    assert spec is not None and spec.loader is not None
    h = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(h)
    return h


def page_candidates(raw: bytes, helper):
    candidates=[]
    offset=0
    while True:
        i=raw.find(b'pDataRun',offset)
        if i<0:
            break
        offset=i+1
        start=i-24
        if start<0 or start+56>len(raw):
            continue
        length=struct.unpack_from('<I',raw,start+4)[0]
        if not 56<length<100000 or start+length>len(raw):
            continue
        page=raw[start:start+length]
        if struct.unpack_from('<I',page,0)[0]!=helper.page_crc(page):
            continue
        if page[24:40].split(b'\0',1)[0]!=b'pDataRun':
            continue
        names={helper.component_name(component) for *_,component in helper.component_records(page)}
        required={'pDataRun','tSample','tCycle','jCycle','tPhase','tRemain',
                  'tTemp','tHum','tSensors','mPause','mCancel'}
        if not required.issubset(names):
            continue
        if not (b'EVT:DATA_PAUSE' in page and b'EVT:DATA_CANCEL' in page):
            continue
        candidates.append((start,length,page))
    return sorted(candidates)


def validate(raw:bytes,helper,expected_page:bytes) -> None:
    n=struct.unpack_from('<I',raw,0)[0]
    end=4+n*helper.ENTRY_SIZE
    expected_crc=helper.directory_checksum(raw[:end])
    assert raw[:end]==raw[helper.BACKUP_DIR_OFFSET:helper.BACKUP_DIR_OFFSET+end]
    assert struct.unpack_from('<I',raw,end)[0]==expected_crc
    assert struct.unpack_from('<I',raw,helper.BACKUP_DIR_OFFSET+end)[0]==expected_crc
    for pid,name in enumerate(PAGE_NAMES):
        page=helper.get_page(raw,pid)
        assert page[24:40].split(b'\0',1)[0]==name.encode(),(pid,name)
        assert struct.unpack_from('<I',page,0)[0]==helper.page_crc(page),(pid,'crc')
        if pid==3:
            assert page==expected_page


def main():
    helper=load_helper()
    raw=CANONICAL.read_bytes()
    sha=hashlib.sha256(raw).hexdigest()
    if sha!=EXPECTED_ORIGINAL_SHA256:
        raise RuntimeError(f'Edited HMI changed since audit ({sha}); refusing to overwrite')
    try:
        helper.find_entry(raw,'3.pa')
    except KeyError:
        pass
    else:
        raise RuntimeError('3.pa already exists, refusing to patch')

    entries_count=struct.unpack_from('<I',raw,0)[0]
    old_end=4+entries_count*helper.ENTRY_SIZE
    crc=helper.directory_checksum(raw[:old_end])
    assert raw[:old_end]==raw[helper.BACKUP_DIR_OFFSET:helper.BACKUP_DIR_OFFSET+old_end]
    assert struct.unpack_from('<I',raw,old_end)[0]==crc
    assert struct.unpack_from('<I',raw,helper.BACKUP_DIR_OFFSET+old_end)[0]==crc
    space=helper.ENTRY_SIZE+4
    for offset in (old_end,helper.BACKUP_DIR_OFFSET+old_end):
        assert raw[offset+4:offset+space]==b'\0'*(space-4), 'Directory extension not empty'

    candidates=page_candidates(raw,helper)
    assert len(candidates)>=1, 'No valid pDataRun with Pause/Cancel was found'
    start,length,selected=candidates[-1]
    # Reuse the canonical 3.pa directory metadata tail fields from HEAD.
    historical=subprocess.run(['git','show','HEAD:'+CANONICAL_REL],cwd=ROOT,
                              check=True,capture_output=True).stdout
    _,_,_,_,_,_,tail=helper.find_entry(historical,'3.pa')
    record=struct.pack(helper.ENTRY_FMT,b'3.pa'.ljust(16,b'\0'),
                       start,length,0,*tail)
    assert len(record)==helper.ENTRY_SIZE
    fixed=bytearray(raw)
    for base in (0,helper.BACKUP_DIR_OFFSET):
        struct.pack_into('<I',fixed,base,entries_count+1)
        fixed[base+old_end:base+old_end+helper.ENTRY_SIZE]=record
    new_end=old_end+helper.ENTRY_SIZE
    checksum=helper.directory_checksum(bytes(fixed[:new_end]))
    for base in (0,helper.BACKUP_DIR_OFFSET):
        struct.pack_into('<I',fixed,base+new_end,checksum)
    repaired=bytes(fixed)
    validate(repaired,helper,selected)
    assert len(repaired)==len(raw)
    for pid in range(12):
        if pid!=3:
            assert helper.get_page(repaired,pid)==helper.get_page(raw,pid),('page_changed',pid)
    boundaries=((0,new_end+4),(helper.BACKUP_DIR_OFFSET,helper.BACKUP_DIR_OFFSET+new_end+4))
    for i,(before,after) in enumerate(zip(raw,repaired)):
        if before!=after:
            assert any(lo<=i<hi for lo,hi in boundaries),('unexpected_change',i)

    BACKUP_DIR.mkdir(parents=True,exist_ok=True)
    backup=BACKUP_DIR/f'ORIGINAL_{sha[:12]}.HMI'
    if backup.exists():
        raise FileExistsError(f'Original backup already exists, refusing to overwrite: {backup}')
    backup.write_bytes(raw)
    assert hashlib.sha256(backup.read_bytes()).hexdigest()==sha

    temp=CANONICAL.with_suffix('.HMI.tmp')
    if temp.exists():
        raise FileExistsError(f'Temporary file exists: {temp}')
    try:
        temp.write_bytes(repaired)
        validate(temp.read_bytes(),helper,selected)
        os.replace(temp,CANONICAL)
    finally:
        if temp.exists():
            temp.unlink()
    after=CANONICAL.read_bytes()
    assert after==repaired
    print('PAGE3_MINIMAL_REPAIR_PASS original_SHA256=',sha,
          'repaired_SHA256=',hashlib.sha256(after).hexdigest(),
          'old_files=',entries_count,'new_files=',entries_count+1,
          'selected_existing_page_offset=',start,'page_size=',length,
          'backup=',backup.relative_to(ROOT),
          'all_other_11_pages_and_resources_unchanged=true')


if __name__=='__main__':
    main()
