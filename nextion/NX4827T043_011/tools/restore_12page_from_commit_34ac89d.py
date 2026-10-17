"""Restore an exact, read-only Git snapshot as a NEW Nextion HMI file.

Never overwrites an existing project HMI or changes connected equipment.
"""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import struct
import subprocess


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
REL = 'nextion/NX4827T043_011/project/RoastSense_NX4827T043_011_COMPILE_READY.HMI'
DEST = ROOT / 'nextion/NX4827T043_011/project/RoastSense_RECOVERED_12P_34ac89d.HMI'
REV = '34ac89d93b4772dadd2fe5008c8d00bac8e138e9'
SOURCE_SHA256 = 'b481a5ae498badedcc8395908f1c75132442a3e134a67bd43043c3ed6c505188'
EXPECTED_NAMES = ('pSplash','pHome','pTake','pDataRun','pDataDone','pTest',
                  'pTestRun','pResult','pCal','pSettings','pHistory','pAlert')


def helper():
    spec = importlib.util.spec_from_file_location('nx_hmi_helper', HERE/'build_figma_fix_hmi.py')
    assert spec is not None and spec.loader is not None
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def verify(raw:bytes) -> dict:
    h = helper()
    assert hashlib.sha256(raw).hexdigest()==SOURCE_SHA256, 'HMI differs from 34ac89d source'
    count = struct.unpack_from('<I',raw,0)[0]
    end = 4 + count*h.ENTRY_SIZE
    checksum = h.directory_checksum(raw[:end])
    assert struct.unpack_from('<I',raw,end)[0] == checksum
    assert struct.unpack_from('<I',raw,h.BACKUP_DIR_OFFSET+end)[0] == checksum
    assert raw[:end] == raw[h.BACKUP_DIR_OFFSET:h.BACKUP_DIR_OFFSET+end]
    for i,name in enumerate(EXPECTED_NAMES):
        page = h.get_page(raw,i)
        assert page[24:40].split(b'\0',1)[0] == name.encode(), (i,name)
        assert struct.unpack_from('<I',page,0)[0] == h.page_crc(page), (i,name,'CRC')
        components = {h.component_name(rec) for *_,rec in h.component_records(page)}
        assert h.REQUIRED_COMPONENTS.get(i,set()).issubset(components), (i,name,'components')
    run = h.get_page(raw,3)
    assert h.attr_bytes(h.find_component(run,'jCycle')[-1],'type') == b'j'
    assert h.attr_bytes(h.find_component(run,'tTemp')[-1],'type') == b't'
    assert h.attr_bytes(h.find_component(run,'tHum')[-1],'type') == b't'
    take = h.get_page(raw,2)
    assert b'EVT:DATA_START' in h.find_component(take,'mStart')[-1]
    assert b'page pDataRun' in h.find_component(take,'mStart')[-1]
    return {'sha256':hashlib.sha256(raw).hexdigest(), 'page_count':len(EXPECTED_NAMES),
            'bytes':len(raw), 'valid_components':True,
            'source':REV+':'+REL}


def main():
    raw = subprocess.check_output(['git','show',f'{REV}:{REL}'],cwd=ROOT)
    check = verify(raw)
    # A distinct filename is intentional: no manual color/layout edits lost.
    with DEST.open('xb') as fd:
        fd.write(raw)
    assert DEST.read_bytes()==raw
    print('RECOVERED_HMI12_QA_PASS',check,'file=',DEST.relative_to(ROOT))


if __name__=='__main__':
    main()
