"""Non-destructive merge of audited 30-cycle CSV and B70..B75.

The input CSV and receiver quality metadata are never modified. Valid captures
are SHA256-verified copies in a new merged folder. Rejected captures are
recorded separately and never included in model training. Existing valid
same-batch runs are kept in the archive but only one is eligible per batch.
"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import shutil

import pandas as pd

from audit_dataset_30_siklus import audit_one,categorize
from merge_new_30_siklus_audit import checksum,signal_fingerprint

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'data/raw/data 30 siklus/HASIL_AUDIT_30_SIKLUS_20261019/HASIL_GABUNGAN_20261021/01_VALID_GABUNGAN'
RAW=ROOT/'data/raw'
OUT=ROOT/'results/combined_30cycle_B70_B75_20261031'
VALID=OUT/'01_VALID_GABUNGAN'


def merge():
    if OUT.exists():
        raise FileExistsError(f'Refusing overwrite: {OUT}')
    old=sorted(OLD.glob('*.csv'))
    new=[p for b in range(70,76) for p in sorted((RAW/f'B{b}').glob('*.csv'))]
    assert len(old)==112 and len(new)==126,(len(old),len(new))
    entries=[];accepted=[];rejected=[];hash_seen={};signal_seen={}
    for kind,path in [('previous_audit',p) for p in old]+[('B70_B75',p) for p in new]:
        sha=checksum(path)
        a,_=audit_one(path,sha)
        cat=categorize(a)
        signal=signal_fingerprint(path)
        quality_path=path.with_suffix('.quality.json') if kind=='B70_B75' else None
        quality=json.loads(quality_path.read_text(encoding='utf8')) if quality_path and quality_path.exists() else {}
        label=a['sample_ids'];batch=a['batch_ids'];roast=a['roast_levels']
        reasons=list(a['anomalies'])
        if kind=='B70_B75':
            if not quality:
                reasons.append('MISSING_RECEIVER_QUALITY_JSON')
            if quality.get('trainable_as_complete_30_cycle_dataset') is not True or quality.get('quality_status')!='validated_complete':
                reasons.append('RECEIVER_FLAG_INCOMPLETE')
            if quality.get('sample_id')!=label or quality.get('batch_id')!=batch:
                reasons.append('RECEIVER_METADATA_MISMATCH')
            if quality.get('device_id') not in {'ALAT_1','ALAT_2','ALAT_3'}:
                reasons.append('DEVICE_UNKNOWN')
            if path.parent.name!=batch:
                reasons.append('DIRECTORY_BATCH_MISMATCH')
        duplicate=hash_seen.get(sha) or signal_seen.get(signal)
        if duplicate:
            reasons.append('DUPLICATE_SIGNAL_OR_BYTES:'+duplicate)
        eligible=(cat=='VALID' and not reasons and not duplicate and '_INCOMPLETE' not in path.stem.upper())
        row={'source_type':kind,'filename':path.name,'source_path':str(path.resolve()),
             'quality_json_path':str(quality_path.resolve()) if quality_path else '',
             'sample_id':label,'origin':label.partition('-')[2],
             'roast_level':roast,'batch_id':batch,
             'device_id':quality.get('device_id','UNKNOWN'),
             'quality_status':quality.get('quality_status','OLDER_AUDITED'),
             'rows':a['rows'],'cycles':a['cycles_detected'],
             'sha256':sha,'signal_sha256':signal,'audit_category':cat,
             'merge_status':'ACCEPTED' if eligible else 'QUARANTINED',
             'reasons':' | '.join(reasons)}
        entries.append(row)
        if eligible:
            if path.name in {x['filename'] for x in accepted}:
                raise RuntimeError('Filename collision in merged archive: '+path.name)
            hash_seen[sha]=path.name
            signal_seen[signal]=path.name
            accepted.append(row)
        else:
            rejected.append(row)
    if not accepted:
        raise RuntimeError('No accepted CSVs')
    # Stage metadata and copied CSV. A crash never corrupts source.
    VALID.mkdir(parents=True)
    for row in accepted:
        src=Path(row['source_path']);dst=VALID/row['filename']
        shutil.copy2(src,dst)
        if checksum(dst)!=row['sha256']:
            raise RuntimeError('SHA mismatch after copy '+dst.name)
    # Do not silently multiply independent samples for reused batch IDs.
    unique={}
    for row in accepted:
        key=(row['origin'],row['roast_level'],row['batch_id'])
        if key in unique:
            row['primary_independent_batch']=False
            row['primary_filename']=unique[key]
        else:
            unique[key]=row['filename']
            row['primary_independent_batch']=True
            row['primary_filename']=row['filename']
    for row in rejected:
        row['primary_independent_batch']=False
        row['primary_filename']=''
    pd.DataFrame(entries).to_csv(OUT/'all_input_manifest.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(accepted).to_csv(OUT/'accepted_provenance.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(rejected).to_csv(OUT/'quarantined_records.csv',index=False,encoding='utf-8-sig')
    counts={'old_inputs':len(old),'new_inputs':len(new),'total_inputs':len(entries),
            'old_accepted':sum(r['source_type']=='previous_audit' for r in accepted),
            'new_accepted':sum(r['source_type']=='B70_B75' for r in accepted),
            'new_quarantined':sum(r['source_type']=='B70_B75' for r in rejected),
            'merged_valid_csv':len(accepted),
            'independent_origin_roast_batch_unique':sum(x['primary_independent_batch'] for x in accepted),
            'same_batch_extras':sum(not x['primary_independent_batch'] for x in accepted),
            'by_origin_roast_source':dict(sorted(Counter(f"{r['source_type']}:{r['origin']}:{r['roast_level']}" for r in accepted).items())),
            'by_device_new':dict(sorted(Counter(r['device_id'] for r in accepted if r['source_type']=='B70_B75').items())),
            'rejected_files':[{'filename':r['filename'],'reason':r['reasons'],
                                'rows':r['rows'],'device':r['device_id']} for r in rejected],
            'no_source_changes':True}
    (OUT/'summary.json').write_text(json.dumps(counts,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    (OUT/'README.md').write_text(
        '# Penggabungan data 30 siklus: arsip lama + B70 sampai B75\n\n'
        f"Audit ulang {len(entries)} berkas; {len(accepted)} valid disalin ke `01_VALID_GABUNGAN`, "
        f"{len(rejected)} dikarantina melalui manifest (tidak disalin untuk AI).\n\n"
        'Semua input lama dan baru bersifat read-only, divalidasi ketat terhadap 900 sampel, '
        '30 siklus × (25s purging + 5s collecting), timing, metadata, receiver quality JSON, '
        'SHA256 dan fingerprint sinyal. File incomplete **tidak diinterpolasi** agar dapat '
        'dianggap sebagai sampel utuh. Detail ada di `quarantined_records.csv`.\n\n'
        'Karena dua pasangan rekaman lama menggunakan origin+roast+batch yang sama, '
        'hanya satu per grup dihitung independen saat training. Data yang tidak '
        'memiliki device_id (arsip lama) diberi `UNKNOWN`, tidak diimputasi dari kelas.\n',encoding='utf8')
    print('MERGE_30CYCLE_PASS',json.dumps({k:v for k,v in counts.items() if k!='by_origin_roast_source'},ensure_ascii=True),flush=True)
    return counts


if __name__=='__main__':merge()
