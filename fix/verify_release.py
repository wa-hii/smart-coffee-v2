"""Verify frozen artifact hashes. No device or serial access."""
from pathlib import Path
import argparse,hashlib,json,sys,zipfile

ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--require-local',action='store_true');args=ap.parse_args()
    manifest=json.loads((ROOT/'fix/manifest.json').read_text(encoding='utf8'))
    failed=[];skipped=[];n=0
    for rel,expected in manifest['files_sha256'].items():
        p=ROOT/rel
        if not p.is_file() and not args.require_local and any(rel.startswith(x) for x in manifest['local_only_prefixes']):
            skipped.append(rel);continue
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:failed.append(rel)
        else:n+=1
    for p in (ROOT/'fix/atmega2560').glob('*.zip'):
        with zipfile.ZipFile(p) as z:
            if z.testzip() or not {'platformio.ini','src/main.cpp','src/nextion_waveform.h'}<=set(z.namelist()):failed.append(p.name)
    print(json.dumps({'status':'PASS' if not failed else 'FAIL','verified_files':n,'missing_optional_local':skipped,'failed':failed,'locked_originals_not_archived':manifest['local_locked_not_copied']},indent=2))
    return int(bool(failed))
if __name__=='__main__':sys.exit(main())
