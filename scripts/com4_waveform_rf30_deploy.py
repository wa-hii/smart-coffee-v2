"""Guarded COM4 Waveform RF30 deployment; fresh full backup before any write."""
import argparse, hashlib, json, re, sys, time
from datetime import datetime
from pathlib import Path
from intelhex import IntelHex
from com4_rf30_verified_deploy import check_preflight
from com4_rf30_release_from_verified_backup import avr
from svm30_b6_verify_readback import parse_intel_hex

ROOT=Path(__file__).resolve().parents[1]
HEX=ROOT/'.pio/build/mega2560_waveform_rf30/firmware.hex'
SHA='ae5b34eca58e68837f318308a8d8f7ab5db37380cd233a7e1b61361593216621'
APPROVAL='I_APPROVE_COM4_WAVEFORM_RF30_AFTER_BACKUP'
def sha(data):return hashlib.sha256(data).hexdigest()
def preflight():
    check_preflight(uploading=True)
    assert sha(HEX.read_bytes())==SHA,'candidate hash changed'
    assert IntelHex(str(HEX)).segments()==[(0,36392)],'candidate range changed'
def run(approval):
    assert approval==APPROVAL,'explicit approval required'
    preflight()
    out=ROOT/'private/com4_waveform_rf30_deploy'/datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    out.mkdir(parents=True,exist_ok=False)
    m={'port':'COM4','ftdi':'A10KMZQJA','candidate_sha256':SHA,'state':'PREFLIGHT','flash_write_attempted':False,'eeprom_write_requested':False}
    def save(state):
        m['state']=state;(out/'manifest.json').write_text(json.dumps(m,indent=2),encoding='utf8');print(state,str(out),flush=True)
    def call(label,args,timeout=180):
        valid,log=avr(out,label,args,timeout)
        if not valid:raise RuntimeError(label+' failed; see log')
        return log
    try:
        save('PREFLIGHT');call('01_signature',['-n','-v'],25);save('SIGNATURE_PASS')
        call('02_backup',['-n','-U','flash:r:original_flash.hex:i','-U','eeprom:r:original_eeprom.hex:i'])
        flash=parse_intel_hex(out/'original_flash.hex',262144,allow_trimmed_erased_suffix=True)
        ee=parse_intel_hex(out/'original_eeprom.hex',4096)
        start=flash['address_coverage_bytes'];remain=262144-start
        assert 0<=remain<=4096,'unexpected flash coverage'
        if remain:
            # Independently verify all omitted erased suffix bytes via terminal.
            import subprocess
            from com11_rf30_verified_deploy import AVRDUDE,CONFIG
            p=subprocess.run([str(AVRDUDE),'-C',str(CONFIG),'-p','m2560','-c','wiring','-P','COM4','-b','115200','-n','-t'],cwd=out,input=f'dump flash 0x{start:x} {remain}\nquit\n',capture_output=True,text=True,errors='replace',timeout=45)
            log=p.stdout+'\n'+p.stderr;(out/'03_suffix.log').write_text(log,encoding='utf8')
            assert p.returncode==0 and 'device signature = 0x1e9801' in log.lower()
            seen=bytearray()
            for line in log.splitlines():
                match=re.match(r'^([0-9a-fA-F]{5,6})\s+(.+?)\s*\|',line.strip())
                if match:
                    assert int(match[1],16)==start+len(seen)
                    seen.extend(bytes.fromhex(match[2]))
            assert len(seen)==remain and all(v==255 for v in seen),'suffix not verified'
        fb=bytes(IntelHex(str(out/'original_flash.hex')).tobinarray(start=0,size=262144,pad=255))
        eb=bytes(IntelHex(str(out/'original_eeprom.hex')).tobinarray(start=0,size=4096,pad=255))
        assert sha(fb)==flash['data_sha256'] and sha(eb)==ee['data_sha256']
        (out/'original_flash_full.bin').write_bytes(fb);(out/'original_eeprom_full.bin').write_bytes(eb)
        call('04_backup_verify',['-n','-U','flash:v:original_flash_full.bin:r','-U','eeprom:v:original_eeprom_full.bin:r'])
        m.update(flash_backup_sha256=sha(fb),eeprom_backup_sha256=sha(eb),suffix_verified=remain,backup_verified=True)
        save('BACKUP_VERIFIED');preflight()
        m['flash_write_attempted']=True;save('WRITE_STARTED')
        call('05_upload',['-D','-U',f'flash:w:{HEX}:i'])
        save('UPLOAD_PASS');call('06_independent_verify',['-n','-U',f'flash:v:{HEX}:i'])
        m['application_verified']=True;save('APPLICATION_VERIFIED')
        call('07_eeprom_verify',['-n','-U','eeprom:v:original_eeprom_full.bin:r'])
        m['eeprom_verified_unchanged']=True;save('FLASH_AND_EEPROM_VERIFIED')
        return 0
    except Exception as e:
        m['error']=repr(e);save('STOP_WRITE_MAY_HAVE_OCCURRED' if m['flash_write_attempted'] else 'STOP_NO_WRITE');return 2
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--approval',required=True);a=p.parse_args();sys.exit(run(a.approval))
