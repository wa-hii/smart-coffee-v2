"""READ-ONLY page, component, and stale-page-reference audit for HMI variants."""
from pathlib import Path
import importlib.util
import hashlib
import struct

HERE=Path(__file__).resolve()
root=HERE.parents[1]
spec=importlib.util.spec_from_file_location('hh',root/'tools/build_figma_fix_hmi.py')
h=importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)

def analyze(path:Path):
    print('\nFILE',path.name)
    try:
        raw=path.read_bytes()
    except OSError as e:
        print('UNREADABLE',str(e));return
    print('BYTES',len(raw),'SHA',hashlib.sha256(raw).hexdigest())
    n=struct.unpack_from('<I',raw,0)[0];end=4+n*h.ENTRY_SIZE
    print('DIR_COUNT',n,'CHECKSUM',struct.unpack_from('<I',raw,end)[0]==h.directory_checksum(raw[:end]))
    pages=[]
    for entry in h.entries(raw):
        _,_,name,start,size,deleted,_=entry
        if not name.endswith('.pa') or deleted:
            continue
        p=raw[start:start+size]
        nm=p[24:40].split(b'\0',1)[0].decode('latin1','replace') if len(p)>40 else '?'
        crc_ok=len(p)>56 and struct.unpack_from('<I',p,0)[0]==h.page_crc(p)
        matches=[]
        if crc_ok:
            for _,_,_,_,_,r in h.component_records(p):
                cname=h.component_name(r)
                refs=[(s, r.count(s.encode())) for s in ('pDataRun','pDataDone','pTake','page ') if s.encode() in r]
                if refs:matches.append((cname,refs))
        components= [h.component_name(r) for *_,r in h.component_records(p)] if crc_ok else []
        print('PAGE',name,'actual',nm,'size',size,'crc',crc_ok,'components',components)
        if matches: print('REFS',matches)
        pages.append((name,nm))
    print('ACTIVE_PAGE_COUNT',len(pages),'RAW_PDATARUN_OCCURRENCES',raw.count(b'pDataRun'))
    print('ACTIVE_PAGE_NAMES',pages)

for basename in ('RoastSense_NX4827T043_011.HMI','RoastSense_UI_FIX_QA.HMI','RoastSense_NX4827T043_011_COMPILE_READY.HMI'):
    analyze(root/'project'/basename)
