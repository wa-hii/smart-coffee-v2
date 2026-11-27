"""Promote simulator-verified V7 only; preserve physical V5 rollback, no UART."""
from pathlib import Path
import hashlib,json,shutil,sys,struct
ROOT=Path(__file__).resolve().parents[1]
FIX=ROOT/'fix'; ARCH=ROOT/'archieve/verified_v5_rollback'; DISPLAY=ROOT/'nextion/NX4827T043_011'
STEM='RoastSense_NX4827T043_011_WAVEFORM_RF30_V'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    qa=json.loads((ROOT/'private/v7_simqa.json').read_text());cancel=json.loads((ROOT/'private/v7_cancel_qa.json').read_text());compile_log=json.loads((ROOT/'private/v7_compile.json').read_text())
    assert compile_log['compiled'] and compile_log['exported'] and compile_log['tft_bytes']==3586744
    assert qa['completed'] and len(qa['cases'])==25 and all(x['ok'] for x in qa['cases'] if x['name']!='cancel')
    assert sum(x['name'].startswith('nav') and x['ok'] for x in qa['cases'])==12
    assert cancel['length_ok'] and cancel['bytes']=='T:27'
    mpath=FIX/'manifest.json';m=json.loads(mpath.read_text(encoding='utf8'));assert m['release']=='waveform_rf30_v5_20261127'
    h=DISPLAY/'project'/(STEM+'7.HMI');t=DISPLAY/'build'/(STEM+'7.tft')
    assert sha(h)=='709cde6dce86b0d425c0072490d66abe29b8c61e3270bc522f7d81ab7b687e7e'
    assert sha(t)=='75589f599893c5300fbedcd1e6f9e2395d004934d846d54c5bd4efb2b4b2e64e'
    sys.path.insert(0,str(DISPLAY/'tools'));import revise_testrun_v7 as v
    v.verify(h.read_bytes(),v.BASE.read_bytes())
    assert not ARCH.exists();ARCH.mkdir(parents=True)
    shutil.copy2(mpath,ARCH/'manifest_v5.json')
    for ext in ('.HMI','.tft'):
        old=FIX/'nextion'/(STEM+'5'+ext);dst=ARCH/old.name;key=old.relative_to(ROOT).as_posix()
        assert sha(old)==m['files_sha256'][key]
        shutil.move(str(old),str(dst));m['files_sha256'][dst.relative_to(ROOT).as_posix()]=m['files_sha256'].pop(key)
    for p in (h,t):
        dst=FIX/'nextion'/p.name;assert not dst.exists();shutil.copy2(p,dst);assert sha(dst)==sha(p);m['files_sha256'][dst.relative_to(ROOT).as_posix()]=sha(dst)
    m['files_sha256'][(ARCH/'manifest_v5.json').relative_to(ROOT).as_posix()]=sha(ARCH/'manifest_v5.json')
    for p in (FIX/'README.md',ROOT/'archieve/README.md'):
        m['files_sha256'][p.relative_to(ROOT).as_posix()]=sha(p)
    m.update(release='waveform_rf30_v7_ui_20261127',scope='firmware_and_transport_physically_verified_with_v5_v7_ui_compile_simulator_verified_model_accuracy_failed',hmi_baseline_commit=m.pop('hmi_commit'),preferred_nextion='V7',nextion_v7_physical_test='PENDING',nextion_v5_rollback='archieve/verified_v5_rollback/')
    mpath.write_text(json.dumps(m,indent=2)+'\n',encoding='utf8',newline='\n')
    print('V7_PROMOTED',len(m['files_sha256']),'manifest files')
if __name__=='__main__':main()
