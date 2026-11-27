"""Read-only verification of the revised HMI/TFT against firmware de053ec6."""
import hashlib,struct,sys
from pathlib import Path
import build_figma_fix_hmi as b

root=Path(__file__).resolve().parents[1]
project=root/'project'
name='RoastSense_NX4827T043_011_WAVEFORM_RF30_V5'
source=project/'RoastSense_NX4827T043_011_COMPILE_READY.HMI'
hmi=project/(name+'.HMI')
tft=root/'build'/(name+'.tft')
if len(sys.argv)>1:tft=Path(sys.argv[1])
raw=hmi.read_bytes();old=source.read_bytes();binary=tft.read_bytes()
expected=['pSplash','pHome','pTake','pDataRun','pDataDone','pTest','pTestRun','pResult','pCal','pSettings','pHistory','pAlert']
def attr(r,k):return int.from_bytes(b.attr_bytes(r,k),'little')
def names(p):return [b.component_name(r) for *_,r in b.component_records(p)]
def res(r,n):
    _,_,_,s,l,_,_=b.find_entry(r,n);return r[s:s+l]
n=struct.unpack_from('<I',raw)[0];end=4+n*b.ENTRY_SIZE
assert raw[:end+4]==raw[b.BACKUP_DIR_OFFSET:b.BACKUP_DIR_OFFSET+end+4]
assert struct.unpack_from('<I',raw,end)[0]==b.directory_checksum(raw[:end])
index=res(raw,'main.HMI');assert index[16:20]==struct.pack('<I',b.EXPECTED_MODEL_CRC)
indexed=[index[i+8:i+16].split(b'\0')[0].decode() for i in range(96,len(index),16) if index[i:i+2]==b'pa']
assert indexed==[f'{i}.pa' for i in range(12)],indexed
for i,name in enumerate(expected):
    p=b.get_page(raw,i);assert p[24:40].split(b'\0')[0].decode()==name
    assert struct.unpack_from('<I',p)[0]==b.page_crc(p)
    if i not in (1,3,6,7):
        assert p==b.get_page(old,i)
        for suffix in ('.i','.is'):assert res(raw,str(i)+suffix)==res(old,str(i)+suffix)
assert set(names(b.get_page(raw,1)))=={'pHome','mTest','mData','mSet','mHist','mCal'}
assert set(names(b.get_page(raw,7)))=={'pResult','tRoast','mSave','mHome'}
for i,values in [(3,(11,0,4,242,81,216,79)),(6,(10,0,4,28,72,425,46))]:
    r=b.find_component(b.get_page(raw,i),'s0')[-1]
    assert tuple(attr(r,k) for k in ('id','type','ch','x','y','w','h'))==values
    print('WAVEFORM_PASS',expected[i],values)
assert attr(b.find_component(b.get_page(raw,7),'tRoast')[-1],'font')==2
assert res(raw,'4.zi')[7]==48
# Compare the model field and dimensions against the known Basic TFT header.
old_tft=(root/'build/RoastSense_NX4827T043_011_COMPILE_READY.tft').read_bytes()
assert binary[46:50]==old_tft[46:50]==struct.pack('<I',b.EXPECTED_MODEL_CRC)
assert binary[12:20]==old_tft[12:20]
assert struct.unpack_from('<H',binary,56)[0]==12
assert struct.unpack_from('<I',binary,60)[0]==len(binary)
for p,data in [(hmi,raw),(tft,binary)]:print(p.name,len(data),hashlib.sha256(data).hexdigest())
print('WAVEFORM_RF30_HMI_TFT_STATIC_PASS; not a hardware or simulator test')
