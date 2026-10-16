"""Forensic, read-only QA of the latest operator-edited Nextion HMI nav fix."""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import struct

ROOT=Path(__file__).resolve().parents[3]
DISPLAY=Path(__file__).resolve().parents[1]
HMI=DISPLAY/'project/RoastSense_NX4827T043_011.HMI'
BACKUP=ROOT/'results/hmi-repair-backup-20261016/ROOT_HMI_BEFORE_11PAGE_NAV_FIX_9729ea962129.HMI'

spec=importlib.util.spec_from_file_location('helper',DISPLAY/'tools/build_figma_fix_hmi.py')
h=importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(h)


def run():
    before=BACKUP.read_bytes();after=HMI.read_bytes()
    assert hashlib.sha256(before).hexdigest()=='9729ea9621299fc89915eeabc26660f78c1e6c3edb9e3eb1555ae6cd267a4967'
    assert hashlib.sha256(after).hexdigest()=='86d809e8eb90a74a9b9e6115ae16e310f060f8972aa73a23c918bb49605b3bd5'
    assert len(before)==len(after)
    count=struct.unpack_from('<I',after,0)[0]
    boundary=4+count*h.ENTRY_SIZE
    check=h.directory_checksum(after[:boundary])
    assert check==struct.unpack_from('<I',after,boundary)[0]
    assert check==struct.unpack_from('<I',after,h.BACKUP_DIR_OFFSET+boundary)[0]
    assert after[:boundary]==after[h.BACKUP_DIR_OFFSET:h.BACKUP_DIR_OFFSET+boundary]

    page=h.get_page(after,2)
    assert page[24:40].split(b'\0',1)[0]==b'pTake'
    assert struct.unpack_from('<I',page,0)[0]==h.page_crc(page)
    _,_,_,_,_,button=h.find_component(page,'mStart')
    assert button.count(b'EVT:DATA_START')==1
    assert button.count(b'printh 0D 0A')==1
    assert b'doevents     ' in button
    assert b'page pDataRun' not in after

    old_data=before[15220268:15220268+8115]
    assert struct.unpack_from('<I',old_data,0)[0]==h.page_crc(old_data)
    assert len(old_data)==len(page)
    for (_,_,_,_,_,a),(_,_,_,_,_,b) in zip(h.component_records(old_data),h.component_records(page)):
        assert h.component_name(a)==h.component_name(b)
        if h.component_name(a)!='mStart':
            assert a==b
    # All image, font and non-page resources and all other bytes identical.
    changed=[i for i,(a,b) in enumerate(zip(before,after)) if a!=b]
    allowed=((0,boundary+4),
             (h.BACKUP_DIR_OFFSET,h.BACKUP_DIR_OFFSET+boundary+4),
             (15220268,15220268+8115))
    assert len(changed)==34
    assert all(any(lo<=i<hi for lo,hi in allowed) for i in changed)
    print('LAST_EDITED_HMI_START_NAV_QA_PASS',
          'page=pTake', 'event=EVT:DATA_START',
          'stale_pDataRun_nav_removed=true',
          'unchanged_components=true',
          'original_resources_and_colors_preserved=true',
          'changed_bytes=34')


if __name__=='__main__':run()
