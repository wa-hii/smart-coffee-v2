"""Preserve selected origin/irfan-pria-solo CSV files byte-for-byte."""
from pathlib import Path
import subprocess, hashlib, json, csv, io

ROOT=Path(__file__).resolve().parents[1]
BRANCH='origin/irfan-pria-solo'
NAMES=[f'BASELINE_B{x}.csv' for x in range(36,41)]+[f'{r}-MING_B40.csv' for r in 'DLM']
DEST=ROOT/'data/raw/irfan_baseline_B36_B40'
MANIFEST=ROOT/'data/analysis/irfan_baseline_B36_B40_manifest.csv'
REPORT=ROOT/'data/analysis/irfan_baseline_B36_B40_summary.json'

def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def sha(b):return hashlib.sha256(b).hexdigest()

def main():
    commit=git('rev-parse',BRANCH).decode().strip()
    paths=set(git('ls-tree','-r','--name-only',BRANCH,'--','data').decode().splitlines())
    missing=[n for n in NAMES if f'data/{n}' not in paths]
    selected=[n for n in NAMES if n not in missing]
    if DEST.exists() or MANIFEST.exists() or REPORT.exists():
        raise FileExistsError('Import exists: refuse overwrite')
    records=[]; payloads=[]
    for name in selected:
        source=f'data/{name}'
        data=git('show',f'{commit}:{source}')
        parsed=list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))))
        if not parsed:raise ValueError('Empty CSV '+name)
        header=list(parsed[0])
        required={'timestamp','sample_id','roast_level','origin','batch_id','run_id',
                  'phase','sample_idx','adc_tgs822','adc_mq135','adc_mq3',
                  'adc_tgs2611','adc_tgs2620','adc_tgs2600','adc_tgs2602',
                  'adc_mq8','adc_tgs813','adc_tgs816','temperature','humidity'}
        if not required.issubset(header) or set(header)-required-{'datetime'}:
            raise ValueError('Unrecognized CSV schema '+name)
        local=ROOT/'data/raw'/name
        records.append(dict(source_branch=BRANCH,source_commit=commit,source_path=source,
                            imported_path=f'data/raw/irfan_baseline_B36_B40/{name}',
                            sha256=sha(data),bytes=len(data),rows=len(parsed),
                            has_datetime='datetime' in header,
                            existing_root_collision=local.exists(),
                            existing_root_sha256=sha(local.read_bytes()) if local.exists() else '',
                            ml_status='HOLD_SEPARATE_PROTOCOL_NOT_BLIND'))
        payloads.append((name,data))
    DEST.mkdir(parents=True)
    for name,data in payloads:
        (DEST/name).write_bytes(data)
        assert sha((DEST/name).read_bytes())==sha(data)
    with MANIFEST.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    result=dict(status='IMPORT_COMPLETE_NOT_MODEL_APPROVED',source_branch=BRANCH,
                source_commit=commit,requested=len(NAMES),imported=len(selected),
                missing=missing,root_collisions_preserved=sum(r['existing_root_collision'] for r in records),
                paths=[r['imported_path'] for r in records],sha_verified=True,
                blind_evaluation_approved=False)
    REPORT.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
