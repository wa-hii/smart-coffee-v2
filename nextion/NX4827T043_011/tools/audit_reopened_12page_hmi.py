"""Read-only diagnostic of HMI file after Nextion Editor Save/Compile/reopen."""
from pathlib import Path
from datetime import datetime
import hashlib, importlib.util, struct

HERE=Path(__file__).resolve()
ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('h',HERE.parent/'build_figma_fix_hmi.py')
h=importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(h)
expected=('pSplash','pHome','pTake','pDataRun','pDataDone','pTest',
          'pTestRun','pResult','pCal','pSettings','pHistory','pAlert')

def inspect(path):
    raw=path.read_bytes()
    print('\nFILE',path.name,'bytes',len(raw),'mtime',datetime.fromtimestamp(path.stat().st_mtime),
          'SHA',hashlib.sha256(raw).hexdigest())
    count=struct.unpack_from('<I',raw,0)[0]
    end=4+count*h.ENTRY_SIZE
    checksum=struct.unpack_from('<I',raw,end)[0]
    print('DIR_COUNT',count,'PRIMARY_CHECKSUM',checksum==h.directory_checksum(raw[:end]),
          'BACKUP_DIR_MATCH',raw[:end]==raw[h.BACKUP_DIR_OFFSET:h.BACKUP_DIR_OFFSET+end])
    count_named=0;count_crc=0
    for i,name in enumerate(expected):
        try:
            blob=h.get_page(raw,i)
            actual=blob[24:40].split(b'\0',1)[0].decode('ascii','replace')
            crc=struct.unpack_from('<I',blob,0)[0]==h.page_crc(blob)
            comps={h.component_name(rec) for *_,rec in h.component_records(blob)} if crc else set()
            missing=h.REQUIRED_COMPONENTS.get(i,set())-comps
            print('PAGE',i,actual,'EXPECTED',name,'CRC',crc,
                  'COMPONENTS',len(comps),'MISSING',sorted(missing),
                  'SIZE',len(blob))
            count_named+=int(actual==name)
            count_crc+=int(crc)
        except Exception as exc:
            print('PAGE',i,'MISSING',type(exc).__name__,str(exc))
    print('ACTIVE_MATCHING_PAGE_IDS',count_named,'CRC_PASS',count_crc)
    candidates=[]
    cursor=0
    while True:
        i=raw.find(b'pDataRun',cursor)
        if i<0:break
        cursor=i+1
        start=i-24
        if start<0 or start+56>len(raw):continue
        size=struct.unpack_from('<I',raw,start+4)[0]
        if not 56<size<30000 or start+size>len(raw):continue
        blob=raw[start:start+size]
        if blob[24:40].split(b'\0',1)[0]!=b'pDataRun':continue
        crc=struct.unpack_from('<I',blob,0)[0]==h.page_crc(blob)
        comps={h.component_name(rec) for *_,rec in h.component_records(blob)} if crc else set()
        required=h.REQUIRED_COMPONENTS[3]
        if crc and required.issubset(comps):
            jcycle=h.attr_bytes(h.find_component(blob,'jCycle')[-1],'type')
            candidates.append((start,size,crc,jcycle,hashlib.sha256(blob).hexdigest()[:16]))
    print('VALID_EMBEDDED_PDATARUN_CANDIDATES',candidates)
    return count_named

def main():
    base=ROOT/'project'
    for name in ('RoastSense_RECOVERED_12P_34ac89d.HMI',
                 'RoastSense_NX4827T043_011.HMI',
                 'RoastSense_NX4827T043_011_COMPILE_READY.HMI'):
        inspect(base/name)

if __name__=='__main__':main()
