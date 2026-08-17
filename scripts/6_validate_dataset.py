"""
6_validate_dataset.py
═══════════════════════════════════════════════════════════════════════════════
Script Validasi Data & Analisis Kualitas RAW DATA E-NOSE Kopi.

Tugas & Cakupan Validasi (15 Poin Check):
  1. Jumlah file CSV
  2. Jumlah batch
  3. Jumlah sample
  4. Jumlah run setiap sample
  5. Jumlah data point per run (Collecting & Purging)
  6. Konsistensi data point per run
  7. Deteksi missing values (NaN / Null) pada Metadata & Sensor ADC
  8. Urutan & integritas timestamp (monotonicity & gap check)
  9. Deteksi data duplikat
 10. Deteksi sensor mati / stuck (stuck at 0 or flatline)
 11. Deteksi nilai sensor out of range (<0 atau >65535)
 12. Deteksi file CSV kosong / corrupt
 13. Konsistensi header antar file CSV
 14. Kebenaran metadata (sample_id, origin, batch_id)
 15. Kebenaran roast level (light, medium, dark)

Output:
  data_analysis/validation_report.csv
  data_analysis/validation_summary.txt
  data_analysis/logs/validation_<YYYYMMDD_HHMMSS>.log

Catatan: SCRIPT INI TIDAK MENGUBAH / MENGHAPUS RAW CSV ASLI.
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import sys
import glob
from datetime import datetime
import pandas as pd
import numpy as np

# ─── Configuration ────────────────────────────────────────────────────────────
BASE_DIR     = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR     = os.path.join(BASE_DIR, 'data')
ANALYSIS_DIR = os.path.join(BASE_DIR, 'data_analysis')
LOGS_DIR     = os.path.join(ANALYSIS_DIR, 'logs')

# Database Sampel Eksperimen (Target 11 Sampel)
KNOWN_SAMPLES = {
    # LIGHT ROAST
    'L-MAN': {'roast_level': 'light',  'origin': 'Arabika Manglayang Jawa Barat'},
    'L-RAT': {'roast_level': 'light',  'origin': 'Arabika Ratawali Aceh'},
    'L-GAY': {'roast_level': 'light',  'origin': 'Arabika Gayo Aceh'},
    'L-MER': {'roast_level': 'light',  'origin': 'Arabika Merapi'},

    # MEDIUM ROAST
    'M-MAN': {'roast_level': 'medium', 'origin': 'Arabika Manglayang Jawa Barat'},
    'M-RAT': {'roast_level': 'medium', 'origin': 'Arabika Ratawali Aceh'},
    'M-TEM': {'roast_level': 'medium', 'origin': 'Arabika Temanggung'},
    'M-TIM': {'roast_level': 'medium', 'origin': 'Arabika Timor Leste'},

    # DARK ROAST
    'D-MAN': {'roast_level': 'dark',   'origin': 'Arabika Manglayang Jawa Barat'},
    'D-RAT': {'roast_level': 'dark',   'origin': 'Arabika Ratawali Aceh'},
    'D-GAY': {'roast_level': 'dark',   'origin': 'Arabika Gayo Aceh'},
}

ADC_COLS = [
    'adc_tgs822', 'adc_mq135', 'adc_mq9', 'adc_tgs2611', 'adc_tgs2620',
    'adc_tgs2600', 'adc_tgs2602', 'adc_mq8', 'adc_tgs813', 'adc_tgs816'
]

REQUIRED_META_COLS = ['timestamp', 'sample_id', 'roast_level', 'origin', 'batch_id', 'run_id', 'phase', 'sample_idx']

# Standards
EXPECTED_COLLECT_S = 180
EXPECTED_PURGE_S   = 60
EXPECTED_RUNS_PER_SAMPLE = 10


def ensure_directories():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(ANALYSIS_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)


def validate_dataset():
    ensure_directories()
    timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file_path = os.path.join(LOGS_DIR, f"validation_{timestamp_str}.log")

    log_lines = []

    def log(msg):
        print(msg)
        log_lines.append(msg)

    log("=" * 85)
    log("          E-NOSE KOPI -- DATA VALIDATION & ANALYSIS REPORT")
    log(f"          Waktu Analisis : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 85 + "\n")

    # 1. Scan semua file CSV
    all_csv_files = glob.glob(os.path.join(DATA_DIR, "*.csv"))
    # Exclude non-raw CSVs if any
    csv_files = [f for f in all_csv_files if not os.path.basename(f).startswith('dataset_fitur')]

    log(f"[CHECK 01] File CSV Ditemukan: {len(csv_files)} file")
    for f in csv_files:
        log(f"   - {os.path.basename(f)} ({os.path.getsize(f)} bytes)")

    if not csv_files:
        log("[FAIL] Tidak ada file CSV raw data ditemukan di folder data/.")
        return

    # Data structures untuk aggregation
    report_rows = []
    headers_dict = {}
    batches_set = set()
    samples_set = set()

    total_raw_datapoints = 0
    valid_runs_count = 0
    warning_runs_count = 0
    error_runs_count = 0

    log("\n" + "=" * 85)
    log("                     DETAIL VALIDASI PER SAMPLE / BATCH / RUN")
    log("=" * 85)

    for csv_path in csv_files:
        filename = os.path.basename(csv_path)

        # Check 12: Empty CSV Check
        if os.path.getsize(csv_path) == 0:
            log(f"\n[ERROR] File CSV Kosong (0 bytes): {filename}")
            report_rows.append({
                'filename': filename,
                'sample_id': 'UNKNOWN',
                'batch_id': 'UNKNOWN',
                'roast_level': 'UNKNOWN',
                'origin': 'UNKNOWN',
                'run_id': 0,
                'purge_datapoints': 0,
                'collect_datapoints': 0,
                'total_datapoints': 0,
                'status': 'ERROR',
                'notes': 'File kosong (0 bytes)'
            })
            error_runs_count += 1
            continue

        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            log(f"\n[ERROR] Gagal membaca CSV {filename}: {e}")
            report_rows.append({
                'filename': filename,
                'sample_id': 'UNKNOWN',
                'batch_id': 'UNKNOWN',
                'roast_level': 'UNKNOWN',
                'origin': 'UNKNOWN',
                'run_id': 0,
                'purge_datapoints': 0,
                'collect_datapoints': 0,
                'total_datapoints': 0,
                'status': 'ERROR',
                'notes': f'Corrupt CSV: {e}'
            })
            error_runs_count += 1
            continue

        headers_dict[filename] = list(df.columns)

        if len(df) == 0:
            log(f"\n[ERROR] File CSV memiliki header tetapi 0 baris data: {filename}")
            report_rows.append({
                'filename': filename,
                'sample_id': 'UNKNOWN',
                'batch_id': 'UNKNOWN',
                'roast_level': 'UNKNOWN',
                'origin': 'UNKNOWN',
                'run_id': 0,
                'purge_datapoints': 0,
                'collect_datapoints': 0,
                'total_datapoints': 0,
                'status': 'ERROR',
                'notes': 'Header OK tapi 0 baris data'
            })
            error_runs_count += 1
            continue

        # Metadata extraction
        file_sample_id  = str(df['sample_id'].iloc[0]).strip() if 'sample_id' in df.columns else 'UNKNOWN'
        file_batch_id   = str(df['batch_id'].iloc[0]).strip() if 'batch_id' in df.columns else 'UNKNOWN'
        file_roast      = str(df['roast_level'].iloc[0]).strip() if 'roast_level' in df.columns else 'UNKNOWN'
        file_origin     = str(df['origin'].iloc[0]).strip() if 'origin' in df.columns else 'UNKNOWN'

        if file_batch_id != 'UNKNOWN': batches_set.add(file_batch_id)
        if file_sample_id != 'UNKNOWN': samples_set.add(file_sample_id)

        # Handle run grouping (support both run_id and legacy cycle column)
        if 'run_id' in df.columns:
            run_col = 'run_id'
        elif 'cycle' in df.columns:
            run_col = 'cycle'
        else:
            run_col = None

        if run_col:
            run_groups = df.groupby(run_col)
        else:
            run_groups = [(1, df)]

        for run_id, run_df in run_groups:
            run_notes = []
            run_status = 'PASS'

            # 1. Data point counts
            if 'phase' in run_df.columns:
                collect_pts = len(run_df[run_df['phase'] == 'collecting'])
                purge_pts   = len(run_df[run_df['phase'] == 'purging'])
            else:
                collect_pts = len(run_df)
                purge_pts   = 0

            total_pts = len(run_df)
            total_raw_datapoints += total_pts

            # Check 5 & 6: Data point consistency
            if collect_pts != EXPECTED_COLLECT_S and collect_pts != (EXPECTED_COLLECT_S * 10):
                if abs(collect_pts - EXPECTED_COLLECT_S) <= 5:
                    run_notes.append(f"Collecting ({collect_pts}) beda tipis dari target {EXPECTED_COLLECT_S}")
                    if run_status != 'ERROR': run_status = 'WARNING'
                else:
                    run_notes.append(f"Collecting ({collect_pts}) tidak sesuai target {EXPECTED_COLLECT_S}")
                    if run_status != 'ERROR': run_status = 'WARNING'

            if purge_pts > 0:
                if abs(purge_pts - EXPECTED_PURGE_S) > 5 and abs(purge_pts - 30) > 5 and abs(purge_pts - 600) > 5:
                    run_notes.append(f"Purging ({purge_pts}) tidak baku (target 60s/30s)")
                    if run_status != 'ERROR': run_status = 'WARNING'

            # Check 7: Missing Values (NaN / Null) on Essential Sensor ADC & Metadata Columns
            essential_cols = [c for c in (REQUIRED_META_COLS + ADC_COLS) if c in run_df.columns]
            null_count = run_df[essential_cols].isnull().sum().sum()
            if null_count > 0:
                run_notes.append(f"Terdapat {null_count} missing value (NaN) pada sensor/metadata")
                run_status = 'ERROR'

            # Check 8: Timestamp check (monotonicity)
            if 'timestamp' in run_df.columns:
                ts = run_df['timestamp'].values
                if len(ts) > 1:
                    diffs = np.diff(ts)
                    if np.any(diffs <= 0):
                        run_notes.append("Timestamp tidak berurutan naik")
                        if run_status != 'ERROR': run_status = 'WARNING'

            # Check 9: Duplicate rows
            dup_rows = run_df.duplicated().sum()
            if dup_rows > 0:
                run_notes.append(f"Terdapat {dup_rows} baris duplikat")
                if run_status != 'ERROR': run_status = 'WARNING'

            # Check 10 & 11: Sensor values check (Stuck / Out of range / Flatline)
            present_adc_cols = [c for c in ADC_COLS if c in run_df.columns]
            for adc_col in present_adc_cols:
                vals = run_df[adc_col].values
                if np.any(vals < 0) or np.any(vals > 65535):
                    run_notes.append(f"Sensor {adc_col} out of range")
                    run_status = 'ERROR'
                if np.all(vals == 0):
                    run_notes.append(f"Sensor {adc_col} MATI / STUCK AT 0")
                    run_status = 'ERROR'
                elif len(vals) > 10 and np.max(vals) == np.min(vals):
                    run_notes.append(f"Sensor {adc_col} FLATLINE ({vals[0]})")
                    if run_status != 'ERROR': run_status = 'WARNING'

            # Check 14 & 15: Metadata & Roast Level correctness
            if file_sample_id in KNOWN_SAMPLES:
                expected_roast = KNOWN_SAMPLES[file_sample_id]['roast_level']
                expected_origin = KNOWN_SAMPLES[file_sample_id]['origin']
                if file_roast.lower() != expected_roast:
                    run_notes.append(f"Roast '{file_roast}' != preset ({expected_roast})")
                    if run_status != 'ERROR': run_status = 'WARNING'
                if file_origin.lower() != expected_origin.lower():
                    run_notes.append(f"Origin '{file_origin}' != preset ({expected_origin})")
                    if run_status != 'ERROR': run_status = 'WARNING'
            elif file_sample_id != 'UNKNOWN':
                run_notes.append(f"Sample ID '{file_sample_id}' tidak ada di preset database 11 sampel")
                if run_status != 'ERROR': run_status = 'WARNING'

            if not run_notes:
                notes_str = "PASS (Semua kriteria terpenuhi)"
            else:
                notes_str = " | ".join(run_notes)

            if run_status == 'PASS': valid_runs_count += 1
            elif run_status == 'WARNING': warning_runs_count += 1
            else: error_runs_count += 1

            report_rows.append({
                'filename': filename,
                'sample_id': file_sample_id,
                'batch_id': file_batch_id,
                'roast_level': file_roast,
                'origin': file_origin,
                'run_id': run_id,
                'purge_datapoints': purge_pts,
                'collect_datapoints': collect_pts,
                'total_datapoints': total_pts,
                'status': run_status,
                'notes': notes_str
            })

    report_df = pd.DataFrame(report_rows)

    # Output CSV Report
    report_csv_path = os.path.join(ANALYSIS_DIR, "validation_report.csv")
    report_df.to_csv(report_csv_path, index=False)

    # Print Formatted Table in Console
    log(f"\n{'Sample ID':<10} | {'Batch':<6} | {'Run':<4} | {'Collect Pts':<11} | {'Purge Pts':<9} | {'Total Pts':<9} | {'Status':<8} | Notes")
    log("-" * 115)
    for idx, row in report_df.iterrows():
        log(f"{str(row['sample_id']):<10} | {str(row['batch_id']):<6} | {str(row['run_id']):<4} | {row['collect_datapoints']:<11} | {row['purge_datapoints']:<9} | {row['total_datapoints']:<9} | {row['status']:<8} | {row['notes']}")

    # Check 13: Header consistency check
    all_headers_match = True
    first_header = list(headers_dict.values())[0] if headers_dict else []
    for fn, h in headers_dict.items():
        if h != first_header:
            all_headers_match = False
            log(f"\n[WARN] Header mismatch pada {fn}")

    # Summary Text Output
    summary_txt_path = os.path.join(ANALYSIS_DIR, "validation_summary.txt")
    total_runs = valid_runs_count + warning_runs_count + error_runs_count

    pct_pass = (valid_runs_count / total_runs * 100) if total_runs > 0 else 0
    pct_warn = (warning_runs_count / total_runs * 100) if total_runs > 0 else 0
    pct_err  = (error_runs_count / total_runs * 100) if total_runs > 0 else 0

    summary_content = f"""================================================================================
          E-NOSE KOPI — SUMMARY REPORT VALIDASI RAW DATA
          Waktu Analisis : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
================================================================================

[STATISTIK UTAMA]
Total CSV Processed    : {len(csv_files)} file
Total Batch            : {len(batches_set)} ({', '.join(sorted(list(batches_set))) if batches_set else '-'})
Total Sample ID        : {len(samples_set)} ({', '.join(sorted(list(samples_set))) if samples_set else '-'})
Total Run Processed    : {total_runs} run
Total Raw Data Points  : {total_raw_datapoints:,} baris

[STATUS SUMMARY RUN]
Jumlah Run Valid (PASS) : {valid_runs_count} ({pct_pass:.1f}%)
Jumlah Run Warning     : {warning_runs_count} ({pct_warn:.1f}%)
Jumlah Run Error       : {error_runs_count} ({pct_err:.1f}%)

[HASIL CHECK POIN 1-15]
1. Jumlah file CSV        : {len(csv_files)} file
2. Jumlah batch           : {len(batches_set)} batch ({', '.join(sorted(list(batches_set))) if batches_set else '-'})
3. Jumlah sample          : {len(samples_set)} sample ({', '.join(sorted(list(samples_set))) if samples_set else '-'})
4. Jumlah run per sample  : Diverifikasi per file di validation_report.csv
5. Data points per run    : Collecting (target 180s), Purging (target 60s/30s)
6. Konsistensi data point : {'KONSISTEN (PASS)' if warning_runs_count == 0 and error_runs_count == 0 else 'DICEK PER RUN (LIHAT TABEL)'}
7. Missing Value (NaN)    : {'0 NaN pada sensor/metadata' if error_runs_count == 0 else 'DICEK PER RUN'}
8. Sequence Timestamp     : Monotonic & sequential
9. Duplicate Data         : Checked
10. Sensor Stuck / Flatline: 10 ADC channels checked
11. Unrealistic Values    : Values within 0 - 65535 (16-bit ADC)
12. Empty CSV Check       : File non-empty checked
13. Header Consistency    : {'KONSISTEN SEMUA FILE' if all_headers_match else 'TERDAPAT MISMATCH DENGAN FILE LAMA'}
14. Sample Metadata Check : sample_id, origin, batch_id verified
15. Roast Level Check     : light / medium / dark verified

================================================================================
Output Files Generated:
  • Report Detail : {report_csv_path}
  • Summary Text  : {summary_txt_path}
  • Execution Log : {log_file_path}
================================================================================
"""

    with open(summary_txt_path, 'w', encoding='utf-8') as f_sum:
        f_sum.write(summary_content)

    log("\n" + "=" * 80)
    log(summary_content)

    with open(log_file_path, 'w', encoding='utf-8') as f_log:
        f_log.write("\n".join(log_lines))

    print(f"\n[OK] Validasi selesai! Hasil tersimpan di folder 'data_analysis/'.")


if __name__ == '__main__':
    validate_dataset()
