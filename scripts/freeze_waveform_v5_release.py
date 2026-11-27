"""Freeze verified hardware/transport release, without modifying active devices."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess

ROOT=Path(__file__).resolve().parents[1]
FIX=ROOT/'fix'; ARCH=ROOT/'archieve'
HOST='enose-v3@enose-pi5'; BASE='smart-coffee-stage7/rf30_staging'
WORK=BASE+'/com4_integration_20261117/always_on'
def run(*args):return subprocess.check_output(args,cwd=ROOT)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def copy(src,dst,expected=None):
    dst.parent.mkdir(parents=True,exist_ok=True)
    assert not dst.exists(),dst
    shutil.copy2(src,dst)
    assert sha(src)==sha(dst) and (expected is None or sha(dst)==expected),dst
def fetch(remote,dst,expected=None):
    dst.parent.mkdir(parents=True,exist_ok=True)
    assert not dst.exists(),dst
    actual=run('ssh','-o','BatchMode=yes',HOST,'sha256sum',remote).decode().split()[0]
    assert expected is None or actual==expected,(remote,actual)
    run('scp','-o','BatchMode=yes',f'{HOST}:{remote}',str(dst))
    assert sha(dst)==actual,dst
    print('REMOTE_MATCH',dst.relative_to(ROOT),actual,flush=True)

def main():
    assert not (FIX/'atmega2560').exists() and not (ARCH/'legacy_source').exists()
    assert not run('git','status','--porcelain','--','src','include','lib','platformio.ini').strip(),'active source dirty'
    fw=FIX/'atmega2560'; fw.mkdir(parents=True)
    copy(ROOT/'.pio/build/mega2560_waveform_rf30/firmware.hex',fw/'firmware.hex','ae5b34eca58e68837f318308a8d8f7ab5db37380cd233a7e1b61361593216621')
    run('git','archive','--format=zip','-o',str(fw/'source_de053ec6.zip'),'de053ec6','src','include','lib','platformio.ini')
    n=ROOT/'nextion/NX4827T043_011'; name='RoastSense_NX4827T043_011_WAVEFORM_RF30_V5'
    copy(n/'project'/f'{name}.HMI',FIX/'nextion'/f'{name}.HMI','5268b934b50977d88ce3ef28ad426768c485d4247353bc82340a44f50a0fe7af')
    copy(n/'build'/f'{name}.tft',FIX/'nextion'/f'{name}.tft','6c5ca75cb8e25596db483eef46925b3eebae3d40abb93cf20e73c1130c4c51d7')
    runtime=FIX/'raspberry_pi5/runtime'; snapshot=FIX/'raspberry_pi5/deployed_enose_pi5'
    for name in ('roast_rf30_pi_inference.py','roast_rf30_pi_stream_replay.py'):
        fetch(BASE+'/'+name,runtime/name)
    for name in ('rf500_pi_persistent_listener.py','rf30_pi_result_bridge.py','pi_labeled_take_data.py'):
        fetch(WORK+'/'+name,runtime/name)
    for name in ('rf500_pi_boot_supervisor.sh','rf500_pi_install_autostart.py','rf500_pi_verify_staged_bridge.py'):
        fetch(WORK+'/'+name,snapshot/name)
    ref=ARCH/'rf500_reference_not_validated'
    fetch(BASE+'/final_model.joblib',ref/'final_model.joblib','b2b6e8d8ff03e92c695c1b0b55a8c06ea9d4178249c9ce012203e602ff1bcf5d')
    fetch(BASE+'/final_model_info.json',ref/'final_model_info.json','ebe354ea40bf8b8b5c689780ec0e332c0675d5a7b5e6410d1e181a726a22061d')
    old=ARCH/'legacy_source';old.mkdir(parents=True)
    for commit in ('629f4c15','e8d367e9'):
        run('git','archive','--format=zip','-o',str(old/f'firmware_{commit}.zip'),commit,'src','include','lib','platformio.ini')
    # Git snapshots of older host code; no user dirty files staged.
    run('git','archive','--format=zip','-o',str(old/'listener_pre_waveform_629f4c15.zip'),'629f4c15','scripts')
    fetch(WORK+'/rf500_pi_boot_supervisor.sh.bak_20261127_161019',old/'supervisor_A10KN6X9.sh')
    copy(ROOT/'private/rf30_second_pcb_candidate/20261112_rf30_bootguard_v1/rf30_pi_return_candidate.hex',old/'rf30_pre_waveform.hex','26833b3cda23d65bae6b33b796331efa0f803071aa283e592ab6fffabeafebb6')
    finish()

def finish():
    assert not (FIX/'nextion/RoastSense_NX4827T043_011_WAVEFORM_RF30_V7.HMI').exists(), 'V7 promoted; do not regenerate historical V5 manifest'
    # Preserve previous local HMI/TFT (including unsaved-to-Git user edits)
    # in an ignored archive. Never move/overwrite files open in Nextion Editor.
    n=ROOT/'nextion/NX4827T043_011'
    old=ARCH/'legacy_source'
    old_hmi=old/'tracked_nextion_pre_v5.zip'
    if not old_hmi.exists():
        run('git','archive','--format=zip','-o',str(old_hmi),'629f4c15','nextion/NX4827T043_011/project')
    locked=[]
    for folder,pattern in [('project','*.HMI'),('build','*.tft')]:
        for p in sorted((n/folder).glob(pattern)):
            if p.name==f'RoastSense_NX4827T043_011_WAVEFORM_RF30_V5{p.suffix}':continue
            dst=ARCH/'local_nextion_versions'/folder/p.name
            try:
                if dst.exists():assert sha(p)==sha(dst),p
                else:copy(p,dst)
            except PermissionError:
                locked.append(p.relative_to(ROOT).as_posix())
                print('LOCAL_LOCKED_ORIGINAL_PRESERVED',p.name,flush=True)
    files={p.relative_to(ROOT).as_posix():sha(p) for d in (FIX,ARCH) for p in d.rglob('*') if p.is_file() and p.name not in ('manifest.json','.gitignore') and '__pycache__' not in p.parts}
    (FIX/'manifest.json').write_text(json.dumps({'release':'waveform_rf30_v5_20261127','scope':'hardware_and_transport_verified_model_accuracy_failed','firmware_commit':'de053ec6','hmi_commit':'2c16aa44','deployment_evidence':'bdc31cac','g3_g4_evidence':'95b23846','local_locked_not_copied':locked,'local_only_prefixes':['archieve/local_nextion_versions/','archieve/rf500_reference_not_validated/final_model.joblib'],'files_sha256':files},indent=2)+'\n',encoding='utf8',newline='\n')
    print('SNAPSHOT_PASS',len(files),'files',flush=True)
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--finish-existing',action='store_true');args=ap.parse_args()
    if args.finish_existing:
        assert (FIX/'atmega2560/firmware.hex').is_file() and (ARCH/'legacy_source/rf30_pre_waveform.hex').is_file()
        finish()
    else:main()
