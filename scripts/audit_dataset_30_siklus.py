"""Audit & non-destructive classification of E-Nose 30-cycle CSV captures.

Default is read-only/dry-run. --copy-classified copies every input CSV into a
clearly separated category folder and writes detailed per-file and per-cycle
reports. It NEVER alters/deletes/renames an input CSV. Uses files directly
inside the selected directory (not recursive) to avoid stale mixed archives.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
from datetime import datetime

import pandas as pd

from acquisition_schema import ADC_COLS, CSV_COLUMNS

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DEFAULT = ROOT / 'data' / 'raw' / 'data 30 siklus'
EXPECTED_PHASE_COUNTS = {'purging': 25, 'collecting': 5}
EXPECTED_CYCLES = 30
EXPECTED_ROWS = 900
PHASE_START_TOLERANCE_MS = 1250
SAMPLE_INTERVAL_MIN_MS = 750
SAMPLE_INTERVAL_MAX_MS = 1250
FULL_RUN_TOLERANCE_MS = 1500
FILENAME_RE = re.compile(r'^(?P<sample>[LMD]-[A-Z0-9]+)_B(?P<batch>\d+)(?:_.*)?\.csv$', re.I)

FOLDERS = {
    'VALID': '01_VALID_30_SIKLUS',
    'INCOMPLETE': '02_KURANG_ATAU_LEBIH_900_SAMPEL',
    'PHASE_OR_TIMING': '03_ANOMALI_SIKLUS_FASE_TIMESTAMP',
    'BASELINE_OR_UNKNOWN': '04_BASELINE_ATAU_NON_SAMPEL_KOPI',
    'METADATA': '05_NAMA_FILE_ATAU_METADATA_TIDAK_COCOK',
    'DUPLICATE': '06_DUPLIKAT_IDENTIK_LINTAS_FILE',
    'SENSOR_VALUES': '07_NILAI_SENSOR_INVALID',
    'UNREADABLE': '08_CSV_TIDAK_TERBACA',
}


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors='coerce')


def _unique_strings(series: pd.Series) -> list[str]:
    return sorted({str(x).strip() for x in series.dropna() if str(x).strip()})


def audit_one(path: Path, digest: str) -> tuple[dict, list[dict]]:
    result = {
        'filename': path.name, 'source_path': str(path.resolve()),
        'sha256': digest, 'bytes': path.stat().st_size,
        'rows': 0, 'cycles_detected': 0,
        'purging_rows': 0, 'collecting_rows': 0,
        'sensor_empty_rows': 0, 'duplicate_phase_indices': 0,
        'duplicate_timestamps': 0, 'timestamp_nonmonotonic': 0,
        'sample_intervals_outside_750_1250ms': 0,
        'phase_start_deviation_count': 0,
        'span_estimate_seconds': None,
        'time_interval_median_ms': None, 'time_interval_max_ms': None,
        'sample_ids': '', 'batch_ids': '', 'roast_levels': '',
        'filename_metadata_match': None,
        'strict_30_cycle_timing_pass': False,
        'anomalies': [],
    }
    cycle_rows: list[dict] = []
    issues = result['anomalies']
    try:
        df = pd.read_csv(path, low_memory=False)
    except Exception as exc:
        issues.append('UNREADABLE:' + type(exc).__name__ + ':' + str(exc)[:180])
        return result, cycle_rows

    result['rows'] = len(df)
    if list(df.columns) != CSV_COLUMNS:
        issues.append('SCHEMA_TIDAK_SESUAI')
    mandatory = {'timestamp', 'sample_id', 'batch_id', 'roast_level', 'run_id', 'phase', 'sample_idx'}
    if not mandatory.issubset(df.columns):
        issues.append('KOLOM_PENTING_HILANG')
        return result, cycle_rows

    if len(df) != EXPECTED_ROWS:
        issues.append('JUMLAH_SAMPEL_BUKAN_900')
    if not len(df):
        issues.append('CSV_KOSONG')
        return result, cycle_rows

    samples = _unique_strings(df['sample_id'])
    batches = _unique_strings(df['batch_id'])
    roasts = _unique_strings(df['roast_level'])
    result.update(sample_ids=';'.join(samples), batch_ids=';'.join(batches),
                  roast_levels=';'.join(roasts))
    if len(samples) != 1 or len(batches) != 1 or len(roasts) != 1:
        issues.append('METADATA_KOSONG_ATAU_BERUBAH_DALAM_FILE')
    if df['origin'].isna().any() or len(_unique_strings(df['origin'])) != 1:
        issues.append('ORIGIN_KOSONG_ATAU_BERUBAH')

    fname = FILENAME_RE.match(path.name)
    if not fname:
        issues.append('NAMA_FILE_TIDAK_STANDAR_LMD')
        result['filename_metadata_match'] = False
    else:
        filename_sample = fname.group('sample').upper()
        filename_batch = 'B' + str(int(fname.group('batch')))
        match = samples == [filename_sample] and batches == [filename_batch]
        result['filename_metadata_match'] = match
        if not match:
            issues.append('NAMA_FILE_TIDAK_SESUAI_SAMPLE_BATCH_ASLI')
        roast_map = {'L': 'light', 'M': 'medium', 'D': 'dark'}
        if roasts != [roast_map[filename_sample[0]]]:
            issues.append('ROAST_LEVEL_TIDAK_SESUAI_NAMA')

    cycles = numeric(df['run_id'])
    valid_cycles = cycles.notna() & (cycles % 1 == 0) & cycles.between(1, 30)
    seen_cycles = sorted(set(cycles.loc[valid_cycles].astype(int)))
    result['cycles_detected'] = len(seen_cycles)
    if (seen_cycles != list(range(1, 31))) or not valid_cycles.all():
        issues.append('SIKLUS_TIDAK_LENGKAP_1_SAMPAI_30')

    phases = df['phase'].astype('string').str.strip().str.lower()
    result['purging_rows'] = int((phases == 'purging').sum())
    result['collecting_rows'] = int((phases == 'collecting').sum())
    if not phases.isin(['purging', 'collecting']).all():
        issues.append('FASE_DI_LUAR_PURGING_COLLECTING')
    sample_idx = numeric(df['sample_idx'])
    ts = numeric(df['timestamp'])
    if sample_idx.isna().any() or (sample_idx % 1 != 0).any():
        issues.append('SAMPLE_IDX_INVALID')
    if ts.isna().any():
        issues.append('TIMESTAMP_KOSONG_ATAU_INVALID')
    else:
        delta = ts.diff().dropna()
        result['timestamp_nonmonotonic'] = int((delta <= 0).sum())
        result['duplicate_timestamps'] = int(ts.duplicated().sum())
        result['sample_intervals_outside_750_1250ms'] = int(
            ((delta < SAMPLE_INTERVAL_MIN_MS) | (delta > SAMPLE_INTERVAL_MAX_MS)).sum()
        )
        result['time_interval_median_ms'] = round(float(delta.median()), 3) if len(delta) else None
        result['time_interval_max_ms'] = round(float(delta.max()), 3) if len(delta) else None
        result['span_estimate_seconds'] = round((float(ts.iloc[-1])-float(ts.iloc[0])+1000)/1000, 3)
        if result['timestamp_nonmonotonic']:
            issues.append('TIMESTAMP_TIDAK_MENINGKAT')
        if result['sample_intervals_outside_750_1250ms']:
            issues.append('INTERVAL_SENSOR_TIDAK_SEKITAR_1_DETIK')
        if abs((ts.iloc[-1] - ts.iloc[0] + 1000) - 900000) > FULL_RUN_TOLERANCE_MS:
            issues.append('TOTAL_DURASI_TIDAK_SEKITAR_900_DETIK')

    if valid_cycles.all() and phases.isin(['purging','collecting']).all() and sample_idx.notna().all():
        keys = pd.DataFrame({'cycle': cycles.astype(int), 'phase': phases,
                             'sample_idx': sample_idx.astype(int)})
        result['duplicate_phase_indices'] = int(keys.duplicated().sum())
        if result['duplicate_phase_indices']:
            issues.append('DUPLIKAT_INDEX_SAMPEL_DALAM_FILE')
        expected_order = [(cy, ph, i)
                          for cy in range(1,31)
                          for ph, n in EXPECTED_PHASE_COUNTS.items()
                          for i in range(1,n+1)]
        observed_order = list(keys.itertuples(index=False,name=None))
        if observed_order != expected_order:
            issues.append('URUTAN_SIKLUS_FASE_SAMPLE_IDX_TIDAK_SESUAI')
        group_starts: list[tuple[int,str,float]] = []
        for cy in range(1,31):
            for phase, target in EXPECTED_PHASE_COUNTS.items():
                condition = (keys['cycle'] == cy) & (keys['phase'] == phase)
                block = keys.loc[condition]
                indices = block['sample_idx'].tolist()
                expected_indices = list(range(1,target+1))
                duration = None
                part_ts = ts.loc[condition]
                if len(part_ts) and part_ts.notna().all():
                    duration = round((float(part_ts.iloc[-1]) - float(part_ts.iloc[0]) + 1000) / 1000, 3)
                    group_starts.append((cy,phase,float(part_ts.iloc[0])))
                cycle_rows.append({
                    'filename': path.name, 'cycle': cy, 'phase': phase,
                    'expected_rows': target, 'actual_rows': len(indices),
                    'indices_contiguous': indices == expected_indices,
                    'estimated_phase_seconds': duration,
                })
                if indices != expected_indices:
                    issues.append('JUMLAH_ATAU_INDEKS_PER_FASE_TIDAK_25_5')
        # First sample to next phase start should be 25s (purging), 5s
        # (collecting). Last collecting phase lacks next-start: estimate via
        # last sample + 1 second separately in the per-cycle report.
        for (cy, phase, start), (_, _, next_start) in zip(group_starts, group_starts[1:]):
            target_ms = EXPECTED_PHASE_COUNTS[phase] * 1000
            if abs((next_start - start) - target_ms) > PHASE_START_TOLERANCE_MS:
                result['phase_start_deviation_count'] += 1
        if result['phase_start_deviation_count']:
            issues.append('TRANSISI_FASE_TIDAK_25_5_DETIK')

    missing_adc = [c for c in ADC_COLS if c not in df]
    if missing_adc:
        issues.append('KOLOM_ADC_TIDAK_LENGKAP')
    else:
        adc = df[ADC_COLS].apply(pd.to_numeric, errors='coerce')
        invalid = adc.isna() | (adc < 0) | (adc > 32767) | (adc % 1 != 0)
        result['sensor_empty_rows'] = int(invalid.any(axis=1).sum())
        if result['sensor_empty_rows']:
            issues.append('SENSOR_ADC_HILANG_ATAU_NILAI_TIDAK_VALID')

    if 'temperature' in df and 'humidity' in df:
        temp = numeric(df['temperature']); hum = numeric(df['humidity'])
        if ((temp.notna()) & (~temp.between(-40,125))).any() or ((hum.notna()) & (~hum.between(0,100))).any():
            issues.append('SUHU_KELEMBAPAN_DI_LUAR_RENTANG')

    result['anomalies'] = sorted(set(issues))
    result['strict_30_cycle_timing_pass'] = not any(x in result['anomalies'] for x in (
        'JUMLAH_SAMPEL_BUKAN_900', 'SIKLUS_TIDAK_LENGKAP_1_SAMPAI_30',
        'FASE_DI_LUAR_PURGING_COLLECTING', 'SAMPLE_IDX_INVALID',
        'URUTAN_SIKLUS_FASE_SAMPLE_IDX_TIDAK_SESUAI',
        'JUMLAH_ATAU_INDEKS_PER_FASE_TIDAK_25_5',
        'INTERVAL_SENSOR_TIDAK_SEKITAR_1_DETIK',
        'TRANSISI_FASE_TIDAK_25_5_DETIK',
        'TOTAL_DURASI_TIDAK_SEKITAR_900_DETIK',
        'TIMESTAMP_TIDAK_MENINGKAT', 'TIMESTAMP_KOSONG_ATAU_INVALID',
        'DUPLIKAT_INDEX_SAMPEL_DALAM_FILE',
    ))
    return result, cycle_rows


def categorize(result: dict) -> str:
    issues = set(result['anomalies'])
    if any(x.startswith('UNREADABLE:') or x in ('SCHEMA_TIDAK_SESUAI','KOLOM_PENTING_HILANG','CSV_KOSONG') for x in issues):
        return 'UNREADABLE'
    if result.get('is_exact_duplicate_later_copy'):
        return 'DUPLICATE'
    # Incomplete capture is the primary operational issue even when the
    # filename says BASELINE (e.g. BASELINE_B64 contains only 597 rows).
    if 'JUMLAH_SAMPEL_BUKAN_900' in issues:
        return 'INCOMPLETE'
    if result['filename'].upper().startswith('BASELINE_') and (not result['sample_ids'] or
            result['sample_ids'].upper() == 'BASELINE'):
        return 'BASELINE_OR_UNKNOWN'
    if not result['strict_30_cycle_timing_pass']:
        return 'PHASE_OR_TIMING'
    if result['filename_metadata_match'] is not True or any(
        x in issues for x in ('METADATA_KOSONG_ATAU_BERUBAH_DALAM_FILE',
                              'ORIGIN_KOSONG_ATAU_BERUBAH',
                              'ROAST_LEVEL_TIDAK_SESUAI_NAMA')):
        return 'METADATA'
    if 'SENSOR_ADC_HILANG_ATAU_NILAI_TIDAK_VALID' in issues or 'SUHU_KELEMBAPAN_DI_LUAR_RENTANG' in issues:
        return 'SENSOR_VALUES'
    return 'VALID'


def save_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def do_audit(source: Path, destination: Path | None, copy_classified: bool) -> dict:
    files = sorted(p for p in source.glob('*.csv') if p.is_file())
    if not files:
        raise RuntimeError('Folder tidak memiliki CSV langsung: '+str(source))
    observed: list[dict] = []
    per_cycle: list[dict] = []
    digests: dict[str,list[dict]] = defaultdict(list)
    for path in files:
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        row, group = audit_one(path, sha)
        observed.append(row)
        per_cycle.extend(group)
        digests[sha].append(row)
    duplicates = []
    for sha, group in digests.items():
        if len(group) <= 1:
            continue
        # Keep first name in alphabetic ordering as reference, mark rest.
        for idx, result in enumerate(group):
            result['exact_duplicate_group'] = group[0]['filename']
            if idx:
                result['is_exact_duplicate_later_copy'] = True
                result['anomalies'] = sorted(set(result['anomalies'] + ['KONTEN_IDENTIK_FILE_LAIN']))
        duplicates.append({'sha256':sha,'identical_files':[x['filename'] for x in group]})
    for result in observed:
        result['category'] = categorize(result)
    counts = Counter(item['category'] for item in observed)
    anomalies = Counter(issue for item in observed for issue in item['anomalies'])
    manifest = {
        'source': str(source.resolve()), 'analysis_date': datetime.now().isoformat(timespec='seconds'),
        'total_csv': len(files), 'categories': dict(counts),
        'anomaly_frequency_overlapping': dict(anomalies),
        'exact_duplicate_groups': duplicates,
        'files': observed,
        'rules': {
            'cycles':30, 'rows_per_cycle':30, 'purging_rows':25,
            'collecting_rows':5, 'expected_rows':900,
            'sample_interval_ms_range':[SAMPLE_INTERVAL_MIN_MS,SAMPLE_INTERVAL_MAX_MS],
            'phase_start_tolerance_ms':PHASE_START_TOLERANCE_MS,
            'whole_run_tolerance_ms':FULL_RUN_TOLERANCE_MS,
            'timestamp_note':'900 seconds estimated by (last-first+1000) ms for 1 Hz samples',
            'handling':'input CSV never moved/overwritten; category CSVs are verified copies',
        },
    }
    if not copy_classified:
        return manifest
    if destination is None:
        raise ValueError('Need destination when writing reports')
    if destination.resolve() == source.resolve():
        raise ValueError('Output must be a subfolder, not the input directory itself')
    destination.mkdir(parents=True, exist_ok=True)
    for result in observed:
        src = source/result['filename']
        target_folder = destination/FOLDERS[result['category']]
        target_folder.mkdir(parents=True, exist_ok=True)
        dst = target_folder/src.name
        if dst.exists():
            if hashlib.sha256(dst.read_bytes()).hexdigest() != result['sha256']:
                raise FileExistsError('Refuse overwrite of changed classified copy: '+str(dst))
        else:
            if hashlib.sha256(src.read_bytes()).hexdigest() != result['sha256']:
                raise RuntimeError('Input changed during audit: '+str(src))
            shutil.copy2(src, dst)
        if hashlib.sha256(dst.read_bytes()).hexdigest() != result['sha256']:
            raise RuntimeError('Copy checksum failed: '+str(dst))
        result['classified_copy_path'] = str(dst.resolve())

    manifest['output_folder'] = str(destination.resolve())
    with (destination/'audit_manifest.json').open('w',encoding='utf-8') as f:
        json.dump(manifest,f,ensure_ascii=False,indent=2)
    ordered_fields = ['filename','category','rows','cycles_detected',
                      'purging_rows','collecting_rows','span_estimate_seconds',
                      'time_interval_median_ms','time_interval_max_ms',
                      'sample_intervals_outside_750_1250ms','phase_start_deviation_count',
                      'duplicate_phase_indices','duplicate_timestamps',
                      'timestamp_nonmonotonic','sensor_empty_rows','sample_ids',
                      'batch_ids','roast_levels','filename_metadata_match',
                      'strict_30_cycle_timing_pass','anomalies','sha256',
                      'source_path','classified_copy_path']
    report_rows = [dict(x, anomalies=';'.join(x['anomalies'])) for x in observed]
    save_csv(destination/'AUDIT_REKAP_PER_FILE.csv',report_rows,ordered_fields)
    save_csv(destination/'AUDIT_DETAIL_PER_SIKLUS.csv',per_cycle,
             ['filename','cycle','phase','expected_rows','actual_rows',
              'indices_contiguous','estimated_phase_seconds'])
    dup_rows = [{'sha256':entry['sha256'],
                 'identical_files':' | '.join(entry['identical_files'])}
                for entry in duplicates]
    save_csv(destination/'AUDIT_DUPLIKAT_IDENTIK.csv',dup_rows,
             ['sha256','identical_files'])
    lines = [
        '# Hasil audit CSV E-Nose — 30 siklus', '',
        f'- Folder sumber: `{source.resolve()}`',
        f'- Jumlah CSV: **{len(files)}**',
        '- Ketentuan: 30 siklus × (25 baris purging + 5 baris collecting), 1 Hz, sekitar 900 detik.',
        '- Setiap fase dicek urutan indeks 1..25 / 1..5, selisih waktu dan label metadata.',
        '- Kategori berdasarkan **prioritas satu folder per CSV**; sebuah CSV bisa memiliki **lebih dari satu jenis anomali** di rekap.',
        '- **Folder sumber tidak diubah.** Semua klasifikasi berupa salinan dengan SHA256 identik.',
        '- File bertanda `INCOMPLETE` atau baseline tidak otomatis buruk sebagai bahan investigasi, tetapi bukan dataset kopi 30 siklus siap ML.',
        '', '## Kategori hasil', '',
        '| Folder | Jumlah file |','|---|---:|',
    ]
    for category, folder in FOLDERS.items():
        lines.append(f'| `{folder}` | {counts.get(category,0)} |')
    lines += ['', '## Peringatan penting',
              '',
              '- `strict_30_cycle_timing_pass` menguji struktur durasi/fase saja; untuk data training kopi tetap harus memeriksa metadata dan keunikan sampel.',
              '- Nama file tidak sama dengan metadata sampel/batch **tidak diperbaiki otomatis**.',
              '- Data identik yang dinamai berbeda tidak boleh otomatis diperlakukan sebagai pengulangan independen.',
              '- Rekap lengkap: `AUDIT_REKAP_PER_FILE.csv`; detail per fase: `AUDIT_DETAIL_PER_SIKLUS.csv`.',
              '', '## Daftar file per kategori', '']
    for category, folder in FOLDERS.items():
        group = [f for f in observed if f['category'] == category]
        if not group:
            continue
        lines += [f'### {folder} ({len(group)})', '']
        for f in group:
            why = ', '.join(f['anomalies'][:5]) or 'LULUS seluruh audit'
            lines.append(f'- `{f["filename"]}` — {f["rows"]} baris, {f["cycles_detected"]} siklus; {why}')
        lines.append('')
    lines += ['## Kelompok konten identik', '']
    for dup in duplicates:
        lines.append('- '+', '.join('`'+x+'`' for x in dup['identical_files']))
    lines.append('')
    (destination/'README_HASIL_AUDIT.md').write_text('\n'.join(lines),encoding='utf-8')
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=SOURCE_DEFAULT)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--copy-classified', action='store_true',
                        help='Create category copy folders + reports (originals unchanged)')
    args = parser.parse_args()
    source = args.source.resolve()
    if not source.is_dir():
        parser.error(f'Folder tidak ditemukan: {source}')
    dest = args.out or source/'HASIL_AUDIT_30_SIKLUS_20261019'
    manifest = do_audit(source, dest, args.copy_classified)
    print('CSV TOTAL',manifest['total_csv'])
    print('CATEGORIES',json.dumps(manifest['categories'],ensure_ascii=False))
    print('EXACT_DUPLICATE_GROUPS',json.dumps(manifest['exact_duplicate_groups'],ensure_ascii=False))
    if args.copy_classified:
        print('OUTPUT',dest.resolve())
    else:
        print('DRY-RUN ONLY (use --copy-classified for folders/reports)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
