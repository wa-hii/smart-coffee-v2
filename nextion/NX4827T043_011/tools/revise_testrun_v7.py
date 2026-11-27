"""V7: restore upper outline and render rounded Pi badge with cropped text.
Build deterministically from the physically verified V5, not an open Editor file.
"""
import hashlib, io, struct, sys
from pathlib import Path
from PIL import Image, ImageDraw
import build_figma_fix_hmi as b

DISPLAY=Path(__file__).resolve().parents[1]
ROOT=DISPLAY.parents[1]
STEM='RoastSense_NX4827T043_011_WAVEFORM_RF30_V'
BASE=ROOT/'fix/nextion'/(STEM+'5.HMI')
if not BASE.exists():BASE=ROOT/'archieve/verified_v5_rollback'/(STEM+'5.HMI')
OUT=DISPLAY/'project'/(STEM+'7.HMI')
SHA='5268b934b50977d88ce3ef28ad426768c485d4247353bc82340a44f50a0fe7af'
GEOM={'tTestId':(30,53,320,16),'tPi':(377,55,62,12),**{f'tStep{i+1}':(375,132+15*i,76,12) for i in range(4)}}
def resource(raw,name):
    _,_,_,start,size,_,_=b.find_entry(raw,name)
    return raw[start:start+size]
def attr(r,k):return int.from_bytes(b.attr_bytes(r,k),'little')
def background(raw):return Image.open(io.BytesIO(resource(raw,'6.is')[27:])).convert('RGB')
def verify(raw,old):
    assert hashlib.sha256(old).hexdigest()==SHA
    assert [e[2] for e in b.entries(raw)]==[e[2] for e in b.entries(old)]
    for e in b.entries(old):
        if e[5] or e[2] in ('6.pa','6.i','6.is'):continue
        assert resource(raw,e[2])==resource(old,e[2]),e[2]
    p=b.get_page(raw,6);a=b.get_page(old,6)
    assert struct.unpack_from('<I',p)[0]==b.page_crc(p)
    for *_,r in b.component_records(a):
        n=b.component_name(r);new=b.find_component(p,n)[-1]
        if n not in GEOM:assert r==new,n;continue
        assert tuple(attr(new,k) for k in ('x','y','w','h'))==GEOM[n]
        assert all(attr(new,k)==attr(r,k) for k in ('id','font','txt_maxl'))
        assert attr(new,'sta')==0 and attr(new,'picc')==6
        assert attr(new,'pco')==attr(r,'pco')
    im=background(raw);prev=background(old)
    assert all(im.getpixel((x,48))==(0,0,0) for x in range(28,453))
    assert im.getpixel((368,52))==(0,200,179) and im.getpixel((408,61))==(222,255,230)
    assert im.crop((0,72,480,130)).tobytes()==prev.crop((0,72,480,130)).tobytes()
    assert im.crop((0,191,480,272)).tobytes()==prev.crop((0,191,480,272)).tobytes()
    for i in range(4):
        y=132+15*i
        assert set(im.crop((375,y,451,y+12)).getdata())=={(255,255,255)}
        assert im.getpixel((400,y-1))==im.getpixel((400,y+12))==(0,0,0)
    count=struct.unpack_from('<I',raw)[0];end=4+count*b.ENTRY_SIZE
    assert raw[:end+4]==raw[b.BACKUP_DIR_OFFSET:b.BACKUP_DIR_OFFSET+end+4]
    assert struct.unpack_from('<I',raw,end)[0]==b.directory_checksum(raw[:end])
    print('V7_STATIC_PASS: restored border, rounded badge, crop image, unchanged IDs and other resources')

def main():
    old=BASE.read_bytes();assert hashlib.sha256(old).hexdigest()==SHA
    p=b.get_page(old,6)
    for n,(x,y,w,h) in GEOM.items():
        p=b.replace_component(p,n,x=x,y=y,w=w,h=h,sta=0)
        _,_,size,_,pos,rec=b.find_component(p,n)
        r=bytearray(rec);assert b._put_attr(r,'picc',6)
        assert b._put_attr(r,'txt','TEST' if n=='tTestId' else 'PI RF' if n=='tPi' else 'WAIT')
        pp=bytearray(p);pp[pos:pos+size]=r;struct.pack_into('<I',pp,0,b.page_crc(pp));p=bytes(pp)
    original=background(old);im=original.copy();d=ImageDraw.Draw(im)
    # V5 background erased this original top outline (x28..377, y48).
    d.line((28,48,377,48),fill='black',width=1)
    # Remove old square badge only; draw approved pill inside the teal panel.
    d.rectangle((368,51,449,70),fill=(0,200,179))
    d.rounded_rectangle((368,52,447,69),radius=9,fill=(222,255,230),outline=(54,133,74),width=1)
    # V6 status rows: 12px text inside 14px black outline, gap 1px.
    d.rectangle((20,130,459,190),fill=(217,217,217))
    for i in range(4):
        y=131+15*i;prev=133+14*i
        d.rounded_rectangle((22,y,457,y+13),radius=5,fill='white',outline='black',width=1)
        im.paste(original.crop((32,prev+1,240,prev+11)),(32,y+2))
    raw=b.rewrite_page(old,6,p)
    preview=ROOT/'private/testrun_v7_background.png';im.save(preview)
    raw=b.replace_picture(raw,6,preview);verify(raw,old)
    with OUT.open('xb') as f:f.write(raw)
    print(OUT.name,len(raw),hashlib.sha256(raw).hexdigest())
if __name__=='__main__':
    if '--verify' in sys.argv:verify(OUT.read_bytes(),BASE.read_bytes())
    else:main()
