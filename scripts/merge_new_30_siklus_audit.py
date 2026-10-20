"""Audit new 30-cycle data and merge provenance-safe with October 19 archive.

Read-only source folders. Create an entirely new merged archive with validated
old + accepted new CSV, segregated rejected records, and exact/semantic
duplicates. Original manifests and source CSVs must remain byte-identical.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from audit_dataset_30_siklus import ROOT, audit_one, categorize, FOLDERS

NEW = ROOT / 'data/raw/new'
OLD = ROOT / 'data/raw/data 30 siklus/HASIL_AUDIT_30_SIKLUS_20261019'
OUTPUT = OLD / 'HASIL_GABUNGAN_20261021'
SAMPLE_COLUMNS = [
    'timestamp','run_id','phase','sample_idx',
    'adc_tgs822','adc_mq135','adc_mq3','adc_tgs2611','adc_tgs2620',
    'adc_tgs2600','adc_tgs2602','adc_mq8','adc_tgs813','adc_tgs816',
    'temperature','humidity',
]
TARGET_CLASSES = [(o,level) for o in ('GAW','GRB','TEM','CAT','MING','TOR')
                  for level in ('light','medium','dark')]
TARGET_CLASSES += [('RAT','dark'),('MUK','medium'),('GAY','light')]


def checksum(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda:handle.read(1<<20),b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def signal_fingerprint(path: Path) -> str:
    """Ignores naming labels but checks original time+phase+ADC sequence."""
    hasher = hashlib.sha256()
    try:
        with path.open('r',newline='',encoding='utf-8-sig') as handle:
            reader=csv.DictReader(handle)
            if not set(SAMPLE_COLUMNS).issubset(set(reader.fieldnames or [])):
                return ''
            for record in reader:
                hasher.update('\x1f'.join(record[col] for col in SAMPLE_COLUMNS).encode('utf-8'))
                hasher.update(b'\n')
    except (OSError,UnicodeError,csv.Error,KeyError):
        return ''
    return hasher.hexdigest()


def old_records(old_dir: Path)->list[dict]:
    manifest=json.loads((old_dir/'audit_manifest.json').read_text(encoding='utf-8'))
    if manifest['total_csv']!=len(manifest['files']):
        raise RuntimeError('Old manifest file count disagrees')
    rows=[]
    for entry in manifest['files']:
        source=old_dir/FOLDERS[entry['category']]/entry['filename']
        if not source.is_file() or checksum(source)!=entry['sha256']:
            raise RuntimeError('Old archive corrupted: '+str(source))
        rows.append({
            'filename':entry['filename'],'path':source,'sha256':entry['sha256'],
            'signal_sha256':signal_fingerprint(source),
            'category':entry['category'],'sample_id':entry['sample_ids'],
            'batch_id':entry['batch_ids'],'roast_level':entry['roast_levels'],
            'rows':entry['rows'],'issues':entry['anomalies'],
            'origin':'old',
        })
    return rows


def scan_new(new_dir:Path)->list[dict]:
    files=sorted(new_dir.glob('*.csv'))
    if not files:
        raise ValueError('Folder new tidak berisi CSV')
    non_csv=[p for p in new_dir.iterdir() if p.is_file() and p.suffix.lower()!='.csv']
    if non_csv:
        raise ValueError('Terdapat berkas bukan CSV yang belum ditangani: '+', '.join(p.name for p in non_csv))
    rows=[]
    for source in files:
        sha=checksum(source)
        audit, _=audit_one(source,sha)
        category=categorize(audit)
        if '_INCOMPLETE' in source.stem.upper() and category=='VALID':
            category='INCOMPLETE'
            audit['anomalies'].append('FILE_BERTANDA_INCOMPLETE_PERLU_VERIFIKASI')
        rows.append({
            'filename':source.name,'path':source,'sha256':sha,
            'signal_sha256':signal_fingerprint(source),'category':category,
            'sample_id':audit['sample_ids'],'batch_id':audit['batch_ids'],
            'roast_level':audit['roast_levels'],'rows':audit['rows'],
            'cycles':audit['cycles_detected'],'purging_rows':audit['purging_rows'],
            'collecting_rows':audit['collecting_rows'],
            'duration_s':audit['span_estimate_seconds'],
            'issues':audit['anomalies'],'origin':'new',
        })
    return rows


def categorize_new(rows_old:list[dict],rows_new:list[dict])->list[dict]:
    """Deduplicate valid against accepted valid; preserve corrected labels.

    An old *invalid* mislabeled copy must not block a new *valid* copy of
    the identical measurement. Same-source duplicate sensors under
    conflicting coffee labels are quarantined, not relabeled automatically.
    """
    seen_all=defaultdict(list)
    seen_good=defaultdict(list)
    for item in rows_old:
        seen_all[item['sha256']].append(item)
        if item['signal_sha256']:
            seen_all['signal:'+item['signal_sha256']].append(item)
        if item['category']=='VALID':
            seen_good[item['sha256']].append(item)
            if item['signal_sha256']:
                seen_good['signal:'+item['signal_sha256']].append(item)

    for item in rows_new:
        keys=[item['sha256']]
        if item['signal_sha256']:
            keys.append('signal:'+item['signal_sha256'])
        matches=[]
        for key in keys:
            matches.extend(seen_all[key]);
        # Identity by path, as a signal and byte fingerprint can both match.
        unique={str(x['path']):x for x in matches}
        references=list(unique.values())
        item['matches_existing']=[{'origin':r['origin'],'filename':r['filename'],
                                    'category':r['category'],'same_bytes':r['sha256']==item['sha256']}
                                   for r in references]
        good_refs={str(r['path']):r for key in keys for r in seen_good[key]}
        if item['category']=='VALID':
            if good_refs:
                item['merge_action']='SKIP_DUPLICATE_VALID'
                item['merge_reason']='DATA_SUDAH_ADA_PADA_VALID_ARSIP'
            else:
                # Can be a corrected copy of a previous invalid filename.
                item['merge_action']='ADD_VALID'
                item['merge_reason']='VALID_UNIK_ATAU_KOREKSI_ARSIP_INVALID'
                for key in keys:
                    seen_good[key].append(item)
        elif references:
            item['merge_action']='SKIP_DUPLICATE_INVALID'
            item['merge_reason']='INCOMPLETE_ATAU_ANOMALI_SUDAH_ADA'
        else:
            item['merge_action']='ADD_INCOMPLETE'
            item['merge_reason']='BELUM_LOLOS_AUDIT_30_SIKLUS'
        # Every raw record is registered even if rejected, to avoid recounting
        # repeated failures with differing filenames.
        for key in keys:
            seen_all[key].append(item)
    return rows_new


def copy_verified(source:Path,target:Path,sha256:str):
    if checksum(source)!=sha256:
        raise RuntimeError('SOURCE_CHANGED_DURING_AUDIT: '+str(source))
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():
        raise FileExistsError('Target already exists: '+str(target))
    shutil.copy2(source,target)
    if checksum(target)!=sha256:
        raise RuntimeError('COPY_DIGEST_MISMATCH: '+str(target))


def save_table(path:Path,rows:list[dict],fields:list[str]):
    with path.open('w',newline='',encoding='utf-8-sig') as handle:
        writer=csv.DictWriter(handle,fieldnames=fields,extrasaction='ignore')
        writer.writeheader()
        for row in rows:
            cleaned={k:(json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v)
                     for k,v in row.items()}
            writer.writerow(cleaned)


def merge(new_dir:Path=NEW,old_dir:Path=OLD,out:Path=OUTPUT)->dict:
    if out.exists():
        raise FileExistsError('Refusing to overwrite merged output: '+str(out))
    old=old_records(old_dir)
    new=scan_new(new_dir)
    categorize_new(old,new)
    originals=old+new
    original_provenance={str(r['path']):r['sha256'] for r in originals}
    with TemporaryDirectory(prefix='.merge_30c_temp_',dir=old_dir) as tmp:
        stage=Path(tmp)/'result'
        stage.mkdir()
        # All old accepted rows are copied intact; old failed QA is retained
        # under a separate anomaly folder, never silently promoted.
        for item in old:
            if item['category']=='VALID':
                target=stage/'01_VALID_GABUNGAN'/item['filename']
                item['merge_action']='KEEP_OLD_VALID'
            else:
                target=stage/'02_INCOMPLETE_DAN_ANOMALI'/'OLD'/item['category']/item['filename']
                item['merge_action']='KEEP_OLD_INVALID'
            copy_verified(item['path'],target,item['sha256'])
            item['merged_relative_path']=target.relative_to(stage).as_posix()

        collisions=[]
        for item in new:
            action=item['merge_action']
            if action=='ADD_VALID':
                folder=stage/'01_VALID_GABUNGAN'
                filename=item['filename']
                if (folder/filename).exists():
                    # Preserve sample_batch prefix, suffix source and digest;
                    # human provenance sees both without overwriting.
                    filename=f'{Path(filename).stem}__NEW_{item["sha256"][:10]}.csv'
                    collisions.append({'new_file':item['filename'],
                                       'resolved_name':filename,
                                       'reason':'SAME_FILENAME_DIFFERENT_VALID_CONTENT'})
                target=folder/filename
            elif action=='ADD_INCOMPLETE':
                target=stage/'02_INCOMPLETE_DAN_ANOMALI'/'NEW'/item['filename']
            else:
                target=stage/'03_DUPLIKAT_BARU_TIDAK_DIGABUNG'/item['filename']
            copy_verified(item['path'],target,item['sha256'])
            item['merged_relative_path']=target.relative_to(stage).as_posix()

        merged_valid=[x for x in originals if x['merge_action'] in ('KEEP_OLD_VALID','ADD_VALID')]
        counts=Counter(x['merge_action'] for x in originals)
        status_by_class=defaultdict(list)
        for item in merged_valid:
            key=(item['sample_id'].split('-')[-1],item['roast_level'].lower())
            status_by_class[key].append(item)
        deficits=[]
        for origin,level in TARGET_CLASSES:
            records=status_by_class[origin,level]
            batches=sorted(set(item['batch_id'] for item in records))
            deficits.append({'origin':origin,'roast_level':level,
                             'valid_recordings':len(records),'unique_batch_ids':len(batches),
                             'batch_ids':' | '.join(batches),
                             'missing_for_5_recordings':max(0,5-len(records)),
                             'missing_for_5_unique_batch_ids':max(0,5-len(batches))})
        summary={
            'created_at':datetime.now().isoformat(timespec='seconds'),
            'source_new':str(new_dir.resolve()), 'source_old_audit':str(old_dir.resolve()),
            'old_audit_csv':len(old), 'new_csv_audited':len(new),
            'new_structural_pass':sum(x['category']=='VALID' for x in new),
            'new_structural_fail':sum(x['category']!='VALID' for x in new),
            'new_unique_valid_added':counts['ADD_VALID'],
            'new_unique_incomplete_added':counts['ADD_INCOMPLETE'],
            'new_duplicates_quarantined':sum(x['merge_action'].startswith('SKIP_DUPLICATE') for x in new),
            'merged_valid_unique_recordings':len(merged_valid),
            'merged_invalid_quarantined':counts['KEEP_OLD_INVALID']+counts['ADD_INCOMPLETE'],
            'merge_actions':dict(counts),
            'filename_collisions_resolved':collisions,
            'full_run_contract':'30 cycles, 25 purging + 5 collecting samples per cycle, 900 genuine sensor frames and ~900 s',
            'independence_note':'Different CSV with same coffee/batch may be repeated runs; independence of sample preparation/physical devices requires external evidence.',
            'sources_modified':False,
        }
        readme=[
            '# Audit dan merge data 30 siklus — 21 Oktober 2026', '',
            'Sumber asli **tetap utuh**; folder audit sebelumnya juga tidak diubah.',
            '',
            f'- CSV arsip lama: **{len(old)}**',
            f'- CSV baru diperiksa: **{len(new)}**',
            f'- Baru lolos struktur: **{summary["new_structural_pass"]}**',
            f'- Baru gagal struktur: **{summary["new_structural_fail"]}**',
            f'- Baru valid unik masuk pool: **{counts["ADD_VALID"]}**',
            f'- Baru incomplete unik: **{counts["ADD_INCOMPLETE"]}**',
            f'- Baru duplikat disisihkan: **{summary["new_duplicates_quarantined"]}**',
            f'- **Total dataset valid unik gabungan: {len(merged_valid)}**',
            f'- **Total data incomplete/anomali unik: {summary["merged_invalid_quarantined"]}**',
            '', '## Struktur',
            '- `01_VALID_GABUNGAN/`: data old valid dan new valid unik (tidak overwrite).',
            '- `02_INCOMPLETE_DAN_ANOMALI/OLD/`: data lama yang gagal audit, dikelompokkan berdasarkan kategori.',
            '- `02_INCOMPLETE_DAN_ANOMALI/NEW/`: data baru gagal audit yang belum ada sebelumnya.',
            '- `03_DUPLIKAT_BARU_TIDAK_DIGABUNG/`: seluruh CSV baru identik dengan sumber lain, tidak dihitung dua kali.',
            '- `AUDIT_NEW_PER_FILE.csv`: semua 83 CSV baru, alasan per file dan tindakan merge.',
            '- `INCOMPLETE_KETIDAKSESUAIAN.csv`: daftar seluruh data tidak valid baru dan lama, termasuk duplikat yang dikeluarkan.',
            '- `AUDIT_PEMENUHAN_5X_PER_KOPI.csv`: progres target pengambilan valid per kombinasi.',
            '- `MANIFEST_GABUNGAN.json`: catatan lengkap referensi source, hash, serta duplikasi.',
            '', '## Kaidah data',
            '- Tepat 900 baris valid, indeks urut 1..25 purging dan 1..5 collecting untuk setiap siklus.',
            '- 30 siklus lengkap, timestamp naik dan sekitar 1 Hz; tidak ada ADC hilang/out of range.',
            '- Nama file mesti sesuai `sample_id`, `batch_id` serta roast. File berlabel incomplete tidak pernah otomatis diloloskan.',
            '- Duplikasi tidak dibedakan hanya dari nama; isi berkas SHA256 dan fingerprint 16 kolom sensor-waktu diperiksa.',
            '- File yang sama dengan arsip invalid karena nama batch salah boleh masuk sebagai *versi metadata valid*, sedangkan arsip invalid tetap dikarantina.',
            '- Semua data original dan arsip audit 19 Oktober tetap di lokasi sebelumnya.',
            '- Data identik tidak diulang dalam folder valid, dan bentrok nama dengan isi berbeda diberi sufiks `__NEW_hash`.',
            '', '## Bentrokan nama berbeda isi',
        ]
        if collisions:
            for c in collisions:
                readme.append(f'- `{c["new_file"]}` -> `{c["resolved_name"]}`')
        else:
            readme.append('- Tidak ada.')
        (stage/'README_HASIL_GABUNGAN.md').write_text('\n'.join(readme)+'\n',encoding='utf-8')
        fields=['filename','category','merge_action','merge_reason','rows','cycles',
                'purging_rows','collecting_rows','duration_s','sample_id','batch_id',
                'roast_level','issues','matches_existing','sha256',
                'signal_sha256','merged_relative_path','path']
        save_table(stage/'AUDIT_NEW_PER_FILE.csv',new,fields)
        flagged=[x for x in originals if x['merge_action'] not in ('KEEP_OLD_VALID','ADD_VALID')]
        save_table(stage/'INCOMPLETE_KETIDAKSESUAIAN.csv',flagged,fields)
        save_table(stage/'AUDIT_PEMENUHAN_5X_PER_KOPI.csv',deficits,
                   ['origin','roast_level','valid_recordings','unique_batch_ids',
                    'batch_ids','missing_for_5_recordings','missing_for_5_unique_batch_ids'])
        data={**summary,'input_old':[{k:v for k,v in x.items() if k!='path'} | {'source_path':str(x['path'].resolve())} for x in old],
              'input_new':[{k:v for k,v in x.items() if k!='path'} | {'source_path':str(x['path'].resolve())} for x in new]}
        (stage/'MANIFEST_GABUNGAN.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        if (len(list((stage/'01_VALID_GABUNGAN').glob('*.csv')))!=len(merged_valid)
                or len(list((stage/'03_DUPLIKAT_BARU_TIDAK_DIGABUNG').glob('*.csv')))!=summary['new_duplicates_quarantined']):
            raise RuntimeError('Output count mismatch')
        for item in originals:
            written=stage/item['merged_relative_path']
            if checksum(written)!=item['sha256']:
                raise RuntimeError('Checksum verify failed: '+str(written))
        if any(checksum(Path(src))!=sha for src,sha in original_provenance.items()):
            raise RuntimeError('Source file changed while building merger')
        stage.rename(out)
    return summary


def main():
    summary=merge()
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    print('SAVED_TO',OUTPUT)


if __name__=='__main__':
    main()
