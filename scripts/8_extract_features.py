"""
8_extract_features.py - Statistical Analysis & Feature Extraction -- E-NOSE Kopi

Tujuan:
  - Baca seluruh RAW CSV terstandarisasi dari folder data/
  - Hanya gunakan fase 'collecting' untuk ekstraksi fitur
  - Hitung 12 statistik per sensor per RUN
  - Output:
      processed/run_statistics.csv   <- statistik per run per sensor (format panjang)
      processed/feature_dataset.csv  <- dataset siap analisis (1 baris = 1 RUN)

Fitur per sensor (12):
  mean, median, min, max, range, std, var,
  initial, final, delta, slope, auc

TIDAK ADA Machine Learning / Random Forest / Training.
RAW CSV TIDAK DIUBAH.
"""

import os, sys, glob, warnings
import numpy as np
import pandas as pd
from scipy import stats as sp_stats

warnings.filterwarnings('ignore')

BASE_DIR      = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR      = os.path.join(BASE_DIR, 'data')
PROCESSED_DIR = os.path.join(BASE_DIR, 'processed')

ADC_COLS = [
    'adc_tgs822', 'adc_mq135',  'adc_mq9',    'adc_tgs2611',
    'adc_tgs2620','adc_tgs2600','adc_tgs2602', 'adc_mq8',
    'adc_tgs813', 'adc_tgs816',
]

SENSOR_LABEL = {
    'adc_tgs822':'TGS822','adc_mq135':'MQ135','adc_mq9':'MQ9',
    'adc_tgs2611':'TGS2611','adc_tgs2620':'TGS2620','adc_tgs2600':'TGS2600',
    'adc_tgs2602':'TGS2602','adc_mq8':'MQ8','adc_tgs813':'TGS813','adc_tgs816':'TGS816',
}

METADATA_COLS    = ['sample_id','roast_level','origin','batch_id','run_id']
FEATURE_SUFFIXES = ['mean','median','min','max','range','std','var',
                    'initial','final','delta','slope','auc']


def extract_run_features(run_df, sensor_col):
    vals = run_df[sensor_col].dropna().values
    if len(vals) == 0:
        return {s: np.nan for s in FEATURE_SUFFIXES}
    n = len(vals)
    t = np.arange(n, dtype=float)
    v_mean   = float(np.mean(vals))
    v_median = float(np.median(vals))
    v_min    = float(np.min(vals))
    v_max    = float(np.max(vals))
    v_range  = v_max - v_min
    v_std    = float(np.std(vals, ddof=1)) if n > 1 else 0.0
    v_var    = float(np.var(vals, ddof=1)) if n > 1 else 0.0
    v_init   = float(vals[0])
    v_final  = float(vals[-1])
    v_delta  = v_final - v_init
    v_slope  = float(sp_stats.linregress(t, vals)[0]) if n > 1 else 0.0
    v_auc    = float(np.trapezoid(vals, t))
    return {'mean':v_mean,'median':v_median,'min':v_min,'max':v_max,'range':v_range,
            'std':v_std,'var':v_var,'initial':v_init,'final':v_final,
            'delta':v_delta,'slope':v_slope,'auc':v_auc}


def process_all_files():
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    csv_files = sorted(glob.glob(os.path.join(DATA_DIR, '*_B*.csv')))
    if not csv_files:
        print("[ERROR] Tidak ada file CSV terstandarisasi di folder data/.")
        sys.exit(1)

    print(f"[INFO] Ditemukan {len(csv_files)} file CSV.")
    print(f"[INFO] Sensor: {len(ADC_COLS)} channel | Fitur: {len(FEATURE_SUFFIXES)} per sensor")
    print(f"[INFO] Total fitur numerik: {len(ADC_COLS)*len(FEATURE_SUFFIXES)}\n")

    all_rows, stat_rows, skipped, total_runs = [], [], [], 0

    for csv_path in csv_files:
        fname = os.path.basename(csv_path)
        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            print(f"  [SKIP] {fname}: {e}")
            continue

        missing = [c for c in METADATA_COLS+['phase'] if c not in df.columns]
        if missing:
            print(f"  [SKIP] {fname} -- kolom hilang: {missing}")
            continue

        df_col = df[df['phase']=='collecting'].copy()
        if len(df_col) == 0:
            print(f"  [SKIP] {fname} -- tidak ada fase collecting")
            continue

        s_id    = str(df['sample_id'].iloc[0]).strip()
        s_roast = str(df['roast_level'].iloc[0]).strip()
        s_orig  = str(df['origin'].iloc[0]).strip()
        s_batch = str(df['batch_id'].iloc[0]).strip()

        run_groups = df_col.groupby('run_id', sort=True)
        print(f"  {fname:<22}  {s_id:<6} {s_roast:<7} {s_batch}  {len(run_groups)} runs")

        for run_id, rdf in run_groups:
            n_pts = len(rdf)
            if n_pts < 10:
                skipped.append({'file':fname,'run_id':run_id,'reason':f'{n_pts} pts'})
                continue

            row = {'sample_id':s_id,'roast_level':s_roast,'origin':s_orig,
                   'batch_id':s_batch,'run_id':int(run_id),'n_collect_pts':n_pts}

            for adc in ADC_COLS:
                lbl = SENSOR_LABEL[adc]
                if adc not in rdf.columns:
                    for sf in FEATURE_SUFFIXES: row[f'{lbl}_{sf}'] = np.nan
                else:
                    for sf, v in extract_run_features(rdf, adc).items():
                        row[f'{lbl}_{sf}'] = v

            all_rows.append(row)

            for adc in ADC_COLS:
                lbl = SENSOR_LABEL[adc]
                if adc not in rdf.columns: continue
                sr = {'filename':fname,'sample_id':s_id,'roast_level':s_roast,
                      'origin':s_orig,'batch_id':s_batch,'run_id':int(run_id),
                      'sensor':lbl,'n_pts':n_pts}
                sr.update(extract_run_features(rdf, adc))
                stat_rows.append(sr)

            total_runs += 1

    print()

    feature_df = pd.DataFrame(all_rows)
    meta = ['sample_id','roast_level','origin','batch_id','run_id','n_collect_pts']
    feat_cols = [c for c in feature_df.columns if c not in meta]
    feature_df = feature_df[meta + feat_cols]
    feature_df.to_csv(os.path.join(PROCESSED_DIR,'feature_dataset.csv'), index=False)

    stat_df = pd.DataFrame(stat_rows)
    stat_df.to_csv(os.path.join(PROCESSED_DIR,'run_statistics.csv'), index=False)

    print("="*72)
    print("  VALIDASI FEATURE DATASET")
    print("="*72)

    only_feat = feature_df[feat_cols]

    v1_ok = len(feature_df) == total_runs
    print(f"\n[V1] Baris feature_dataset: {len(feature_df)} | RUN diproses: {total_runs} | {'PASS' if v1_ok else 'FAIL'}")

    print(f"\n[V2] Distribusi roast_level:")
    for r, c in sorted(feature_df['roast_level'].value_counts().items()): print(f"     {r:<10}: {c} baris")

    print(f"\n[V3] Distribusi sample_id:")
    for sid in sorted(feature_df['sample_id'].unique()):
        cnt = len(feature_df[feature_df['sample_id']==sid])
        rt  = feature_df[feature_df['sample_id']==sid]['roast_level'].iloc[0]
        print(f"     {sid:<10} ({rt:<7}): {cnt} baris")

    nan_counts = only_feat.isnull().sum()
    nan_cols   = nan_counts[nan_counts>0]
    print(f"\n[V4] Missing Values: {'PASS - tidak ada NaN' if len(nan_cols)==0 else str(len(nan_cols))+' kolom dengan NaN'}")
    for col, cnt in nan_cols.items(): print(f"     WARNING {col}: {cnt} NaN")

    print(f"\n[V5] Fitur variance sangat kecil (std < 1e-3):")
    low_var = [(c, only_feat[c].std()) for c in feat_cols
               if pd.notna(only_feat[c].std()) and only_feat[c].std() < 1e-3]
    if not low_var: print("     Tidak ada. PASS")
    else:
        for col, sv in low_var[:15]: print(f"     WARNING {col}: std={sv:.2e}")

    print(f"\n[V6] Fitur dengan nilai ekstrem (|z| > 5):")
    extremes = []
    for col in feat_cols:
        cv = only_feat[col].dropna()
        if len(cv) > 3 and cv.std() > 0:
            z = np.abs(sp_stats.zscore(cv))
            if np.any(z > 5): extremes.append((col, int(np.sum(z>5))))
    if not extremes: print("     Tidak ada. PASS")
    else:
        for col, cnt in extremes[:10]: print(f"     NOTE {col}: {cnt} nilai |z|>5")

    print(f"\n[V7] Kehadiran semua sensor:")
    all_ok = all(f'{SENSOR_LABEL[a]}_mean' in feature_df.columns for a in ADC_COLS)
    print(f"     {'Semua 10 sensor hadir. PASS' if all_ok else 'FAIL -- sensor hilang'}")

    print(f"\n[V8] Skipped runs: {len(skipped)}")
    for s in skipped: print(f"     {s['file']} run={s['run_id']}: {s['reason']}")
    if not skipped: print("     Tidak ada. PASS")

    leak = [c for c in feature_df.columns if c in ['timestamp','phase','sample_idx']]
    print(f"\n[V9] Data leakage: {'PASS - tidak ada kolom raw' if not leak else 'WARNING: '+str(leak)}")

    print()
    print("="*72)
    print("  RINGKASAN")
    print("="*72)
    print(f"  Total RUN diproses         : {total_runs}")
    print(f"  Total baris feature_dataset: {len(feature_df)}")
    print(f"  Total fitur numerik        : {len(feat_cols)} ({len(ADC_COLS)} sensor x {len(FEATURE_SUFFIXES)} statistik)")
    print(f"  Missing value              : {'0 PASS' if len(nan_cols)==0 else str(len(nan_cols))+' WARNING'}")
    print(f"  Outlier potensial          : {len(extremes)} fitur")
    print()
    print(f"  processed/feature_dataset.csv")
    print(f"  processed/run_statistics.csv")
    print()
    print("[DONE] Feature extraction selesai. RAW CSV tidak diubah.")


if __name__ == '__main__':
    process_all_files()
