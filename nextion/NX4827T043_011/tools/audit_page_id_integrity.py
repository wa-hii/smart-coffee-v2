"""Read-only audit of page IDs and page directory in an Editor-managed HMI.

Compares current locally edited file with Git HEAD without changing either.
"""
from __future__ import annotations

import importlib.util
import hashlib
from pathlib import Path
import struct
import subprocess

HERE=Path(__file__).resolve()
DISPLAY=HERE.parents[1]
REPO=HERE.parents[3]
FILENAME="nextion/NX4827T043_011/project/RoastSense_NX4827T043_011_COMPILE_READY.HMI"

spec=importlib.util.spec_from_file_location("nextion_helper",DISPLAY/"tools/build_figma_fix_hmi.py")
helper=importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(helper)

NAMES=("pSplash","pHome","pTake","pDataRun","pDataDone","pTest",
       "pTestRun","pResult","pCal","pSettings","pHistory","pAlert")


def audit(data:bytes,title:str):
    print("\n========",title,"bytes",len(data),"SHA256",hashlib.sha256(data).hexdigest(),"========")
    count=struct.unpack_from("<I",data,0)[0]
    end=4+count*helper.ENTRY_SIZE
    stored=struct.unpack_from("<I",data,end)[0]
    backup=struct.unpack_from("<I",data,helper.BACKUP_DIR_OFFSET+end)[0]
    correct=helper.directory_checksum(data[:end])
    print("DIRECTORY",count,"primary_checksum",hex(stored),"backup_checksum",hex(backup),
          "computed",hex(correct),"checksum_ok",stored==correct==backup,
          "primary_eq_backup",data[:end]==data[helper.BACKUP_DIR_OFFSET:helper.BACKUP_DIR_OFFSET+end])
    print('DIRECTORY_NEXT_64_AFTER_CRC',data[end+4:end+68].hex(' '),
          'BACKUP_NEXT_64_AFTER_CRC',data[helper.BACKUP_DIR_OFFSET+end+4:helper.BACKUP_DIR_OFFSET+end+68].hex(' '))
    for _idx,_off,name,start,size,deleted,_tail in helper.entries(data):
        if name.endswith('.pa') or name in ('main.HMI','3.pa'):
            print('ENTRY',repr(name),'start',start,'length',size,'deleted',deleted)
    needle=b'pDataRun'
    found=[]
    seek=0
    while True:
        pos=data.find(needle,seek)
        if pos<0:
            break
        seek=pos+1
        start=pos-24
        if start>=0 and start+56<=len(data):
            length=struct.unpack_from('<I',data,start+4)[0]
            if 56<length<100000 and start+length<=len(data):
                blob=data[start:start+length]
                ok=struct.unpack_from('<I',blob,0)[0]==helper.page_crc(blob)
                names=[helper.component_name(rec) for *_,rec in helper.component_records(blob)] if ok else []
                progress_info=[]
                if ok:
                    for *_,rec in helper.component_records(blob):
                        if helper.component_name(rec) in ('jCycle','tSample','mPause'):
                            progress_info.append((helper.component_name(rec),
                                                  {x: (helper.attr_bytes(rec,x).hex() if helper.attr_bytes(rec,x) is not None else None)
                                                   for x in ('type','id','x','y','w','h','bco','pco','val','maxval','sta','picc','pic','pco2')}))
                found.append((start,length,ok,blob[24:40].split(b'\0',1)[0].decode('latin1','replace'),names,
                              'PAUSE' if b'EVT:DATA_PAUSE' in blob else 'NO_PAUSE_EVENT',progress_info))
    print('PDataRun_CANDIDATES',found[-20:])
    for i,expected in enumerate(NAMES):
        label=f"{i}.pa"
        try:
            _,off,_,start,size,deleted,_=helper.find_entry(data,label)
            page=data[start:start+size]
            crc=struct.unpack_from("<I",page,0)[0] if len(page)>=4 else None
            crc_ok=crc==helper.page_crc(page) if len(page)>=56 else False
            count_comp=struct.unpack_from("<I",page,12)[0] if len(page)>=16 else None
            internal_name=page[24:40].split(b"\x00",1)[0].decode("latin1","replace")
            print("PAGE",i,"wanted",expected,"actual",repr(internal_name),
                  "offset",start,"size",size,"component_count",count_comp,
                  "CRC_OK",crc_ok,"name_ok",internal_name==expected)
            if len(page)>=56 and 0 < count_comp < 256 and crc_ok:
                comps=[helper.component_name(rec) for *_,rec in helper.component_records(page)]
                print("  COMPONENTS",comps[:30])
            if not crc_ok or internal_name!=expected:
                print("  FIRST_64_BYTES",page[:64].hex(" "))
        except Exception as exc:
            print("PAGE",i,"ERROR",type(exc).__name__,str(exc))

def main():
    path=REPO/FILENAME
    audit(path.read_bytes(),"LOCAL_EDITED_HMI")
    old=subprocess.run(["git","show",f"HEAD:{FILENAME}"],cwd=REPO,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True).stdout
    audit(old,"GIT_HEAD_HMI")

if __name__=="__main__":
    main()
