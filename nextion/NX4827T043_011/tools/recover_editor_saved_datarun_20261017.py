"""Repair the Page 3 corruption introduced after Nextion Editor save.

Output is a NEW HMI. The source file is never modified. Replaces only the
CRC-invalid pDataRun page with a CRC-valid, matching component snapshot from
the independent compile-ready HMI; all other saved pages/assets are preserved.
"""
from __future__ import annotations

from pathlib import Path
import importlib.util
import hashlib
import struct

HERE=Path(__file__).resolve().parent
DISPLAY=HERE.parent
ROOT=DISPLAY.parents[1]
SOURCE=DISPLAY/'project/RoastSense_RECOVERED_12P_34ac89d.HMI'
GOOD=DISPLAY/'project/RoastSense_NX4827T043_011_COMPILE_READY.HMI'
OUTPUT=DISPLAY/'project/RoastSense_12P_EDITOR_REPAIRED_SAFE_20261017.HMI'
SOURCE_HASH='85076d236ea72af317aa2c731227abf51f74e926a6ce39394a349657c590dc5e'
GOOD_HASH='b02e7c495c915c8a706dc50bb30fe575874d3b8c4fcfa9c3f8f10e86ec3bd4b2'
EXPECTED=('pSplash','pHome','pTake','pDataRun','pDataDone','pTest',
          'pTestRun','pResult','pCal','pSettings','pHistory','pAlert')


def hmi_helper():
    spec=importlib.util.spec_from_file_location('nextion_helper',HERE/'build_figma_fix_hmi.py')
    assert spec and spec.loader
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate(raw,helper):
    n=struct.unpack_from('<I',raw,0)[0]
    end=4+n*helper.ENTRY_SIZE
    checksum=helper.directory_checksum(raw[:end])
    assert checksum==struct.unpack_from('<I',raw,end)[0]
    assert checksum==struct.unpack_from('<I',raw,helper.BACKUP_DIR_OFFSET+end)[0]
    assert raw[:end]==raw[helper.BACKUP_DIR_OFFSET:helper.BACKUP_DIR_OFFSET+end]
    for i,name in enumerate(EXPECTED):
        page=helper.get_page(raw,i)
        assert page[24:40].split(b'\0',1)[0]==name.encode(),(i,name)
        assert struct.unpack_from('<I',page,0)[0]==helper.page_crc(page),(i,name,'CRC')
        comps={helper.component_name(record) for *_,record in helper.component_records(page)}
        assert helper.REQUIRED_COMPONENTS.get(i,set()).issubset(comps),(i,name,'components')
    run=helper.get_page(raw,3)
    assert helper.attr_bytes(helper.find_component(run,'jCycle')[-1],'type')==b'j'
    assert b'EVT:DATA_PAUSE' in run and b'EVT:DATA_CANCEL' in run


def main():
    helper=hmi_helper()
    before=SOURCE.read_bytes()
    good=GOOD.read_bytes()
    assert hashlib.sha256(before).hexdigest()==SOURCE_HASH, 'User HMI changed; do not overwrite'
    assert hashlib.sha256(good).hexdigest()==GOOD_HASH, 'Verified reference changed'
    broken=helper.get_page(before,3)
    assert struct.unpack_from('<I',broken,0)[0]!=helper.page_crc(broken),'Page 3 already valid'
    repair=helper.get_page(good,3)
    assert len(repair)==len(broken)
    assert struct.unpack_from('<I',repair,0)[0]==helper.page_crc(repair)
    # Page 3's stale *active* pointer can point INTO a picture resource.
    # Never overwrite that location, even if the size happens to match.
    # Append a fresh page blob, and ONLY rewrite both directory entries.
    fixed=bytearray(before)
    new_offset=len(fixed)
    fixed.extend(repair)
    _, entry_off, _, _, _, deleted, tail=helper.find_entry(before,'3.pa')
    assert deleted==0
    rec=struct.pack(helper.ENTRY_FMT,b'3.pa'.ljust(16,b'\0'),
                    new_offset,len(repair),0,*tail)
    for base in (0,helper.BACKUP_DIR_OFFSET):
        fixed[base+entry_off:base+entry_off+helper.ENTRY_SIZE]=rec
    n=struct.unpack_from('<I',before,0)[0]
    dir_end=4+n*helper.ENTRY_SIZE
    crc=helper.directory_checksum(bytes(fixed[:dir_end]))
    for base in (0,helper.BACKUP_DIR_OFFSET):
        struct.pack_into('<I',fixed,base+dir_end,crc)
    fixed=bytes(fixed)
    validate(fixed,helper)
    assert len(fixed)==len(before)+len(repair)
    for i in range(12):
        if i!=3:
            assert helper.get_page(before,i)==helper.get_page(fixed,i),('Unexpected visual/page change',i)
    # The original 15+ MB payload must be entirely byte-identical outside
    # of the two directory headers; this proves all assets were preserved.
    end=dir_end+4
    allowed=((0,end),(helper.BACKUP_DIR_OFFSET,helper.BACKUP_DIR_OFFSET+end))
    diff=[i for i,(a,b) in enumerate(zip(before,fixed[:len(before)])) if a!=b]
    assert diff and all(any(lo<=i<hi for lo,hi in allowed) for i in diff)
    with OUTPUT.open('xb') as f:
        f.write(fixed)
    assert OUTPUT.read_bytes()==fixed
    print('RESTORED_EDITOR_SAVED_12_PAGES_PASS',
          'output=',OUTPUT.relative_to(ROOT),'sha256=',hashlib.sha256(fixed).hexdigest(),
          'bytes=',len(fixed),'diff_bytes=',len(diff),
          'all_other_11_pages_and_picture_font_resources_identical=true')


if __name__=='__main__':
    main()
