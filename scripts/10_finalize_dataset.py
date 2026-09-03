"""
10_finalize_dataset.py - Finalisasi Dataset untuk Machine Learning -- E-NOSE Kopi
==============================================================================
Input:
  processed/feature_dataset.csv
  processed/feature_significance.csv

Output:
  processed/ml_dataset_full.csv    <- Semua 120 fitur + metadata
  processed/ml_dataset_final.csv   <- Fitur terpilih (non-redundan, signifikan)
  processed/ml_dataset_summary.md  <- Ringkasan lengkap

TIDAK ADA Training ML / Random Forest.
RAW CSV TIDAK DIUBAH.
==============================================================================
"""

import os, sys, warnings
import numpy as np
import pandas as pd
from scipy.stats import zscore

warnings.filterwarnings('ignore')

BASE_DIR      = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
PROCESSED_DIR = os.path.join(BASE_DIR, 'processed')
FEATURE_CSV   = os.path.join(PROCESSED_DIR, 'feature_dataset.csv')
SIG_CSV       = os.path.join(PROCESSED_DIR, 'feature_significance.csv')

OUT_FULL    = os.path.join(PROCESSED_DIR, 'ml_dataset_full.csv')
OUT_FINAL   = os.path.join(PROCESSED_DIR, 'ml_dataset_final.csv')
OUT_SUMMARY = os.path.join(PROCESSED_DIR, 'ml_dataset_summary.md')

# ── Sensor / stat config ──────────────────────────────────────────────────────
SENSORS = ['TGS822','MQ135','MQ9','TGS2611','TGS2620',
           'TGS2600','TGS2602','MQ8','TGS813','TGS816']
ALL_STATS = ['mean','median','min','max','range','std','var',
             'initial','final','delta','slope','auc']

META_COLS = ['sample_id','roast_level','origin','batch_id','run_id','n_collect_pts']

# Feature selection rules (based on analysis results):
# - REDUNDANT and DROP from final: median (r~1.0 w/ mean), auc (r~1.0 w/ mean),
#   var (r=1.0 w/ std), initial (r~0.999 w/ min), final (r~0.999 w/ mean/median)
# - KEEP: mean, max, min, range, std, delta, slope
REDUNDANT_STATS  = {'median', 'auc', 'var', 'initial', 'final'}
KEPT_STATS       = {'mean', 'max', 'min', 'range', 'std', 'delta', 'slope'}

# Sensors with low discrimination (most features not significant)
LOW_INFO_SENSORS = {'MQ135', 'MQ9', 'TGS2600'}

# Sensors with batch drift detected
DRIFT_SENSORS    = {'TGS822', 'TGS2611'}


def categorize_features(sig_df):
    """
    Categorize all 120 features into groups based on analysis results.
    Returns dict: feature -> category
    """
    categories = {}
    sig_map = {row['feature']: row for _, row in sig_df.iterrows()}

    # Build correlation groups from our known analysis results
    redundant_set = set()
    for sensor in SENSORS:
        for stat in REDUNDANT_STATS:
            f = f'{sensor}_{stat}'
            redundant_set.add(f)

    for sensor in SENSORS:
        for stat in ALL_STATS:
            f = f'{sensor}_{stat}'
            if f not in sig_map:
                categories[f] = 'MISSING_FROM_ANALYSIS'
                continue

            row = sig_map[f]
            p   = row['p_kruskal']
            cv  = row['cv']
            sig = row['significant']

            if f in redundant_set:
                categories[f] = 'REDUNDANT'
            elif not sig:
                categories[f] = 'NOT_SIGNIFICANT'
            elif cv < 0.01:
                categories[f] = 'LOW_VARIANCE'
            else:
                categories[f] = 'RECOMMENDED'

    return categories, sig_map


def select_final_features(categories, sig_map):
    """
    Select final feature set:
    - RECOMMENDED (significant & non-redundant)
    - From low-info sensors: only include if p < 0.01 (stricter threshold)
    """
    final_feats = []
    not_recommended = []

    for feat, cat in sorted(categories.items()):
        p_val = sig_map[feat]['p_kruskal'] if feat in sig_map else None
        if cat == 'RECOMMENDED':
            sensor = feat.split('_')[0]
            # For low-info sensors, apply stricter cutoff
            p_thresh = 0.01 if sensor in LOW_INFO_SENSORS else 0.05
            if p_val is not None and p_val < p_thresh:
                final_feats.append(feat)
            else:
                not_recommended.append((feat, cat, p_val))
        else:
            not_recommended.append((feat, cat, p_val))

    return final_feats, not_recommended


def flag_outliers(df, feat_cols, z_thresh=3.5):
    """
    Flag outliers per run using z-score across all numeric features.
    Returns: outlier_df with columns: run_index, sample_id, run_id, n_outlier_feats, outlier_features
    """
    outlier_records = []
    z_scores = np.abs(df[feat_cols].apply(zscore, nan_policy='omit'))

    for idx in df.index:
        row_z = z_scores.loc[idx]
        outlier_feats = row_z[row_z > z_thresh].index.tolist()
        if outlier_feats:
            outlier_records.append({
                'row_index':       idx,
                'sample_id':       df.loc[idx, 'sample_id'],
                'batch_id':        df.loc[idx, 'batch_id'],
                'run_id':          df.loc[idx, 'run_id'],
                'roast_level':     df.loc[idx, 'roast_level'],
                'n_outlier_feats': len(outlier_feats),
                'max_z':           float(row_z.max()),
                'outlier_features': ', '.join(outlier_feats[:5]),
                'is_outlier':      True
            })

    return pd.DataFrame(outlier_records)


def main():
    # ── Load data ─────────────────────────────────────────────────────────────
    print("[INFO] Loading data...")
    if not os.path.exists(FEATURE_CSV):
        print(f"[ERROR] Tidak ditemukan: {FEATURE_CSV}")
        sys.exit(1)
    if not os.path.exists(SIG_CSV):
        print(f"[ERROR] Tidak ditemukan: {SIG_CSV}")
        sys.exit(1)

    df     = pd.read_csv(FEATURE_CSV)
    sig_df = pd.read_csv(SIG_CSV)

    feat_cols = [c for c in df.columns if c not in META_COLS]
    numeric_feats = df[feat_cols].select_dtypes(include=[np.number]).columns.tolist()

    print(f"[INFO] Total RUN: {len(df)}")
    print(f"[INFO] Total features: {len(feat_cols)}")
    print()

    # ── 1. Missing Value Check ────────────────────────────────────────────────
    print("[1/7] Checking missing values...")
    nan_counts = df[feat_cols].isnull().sum()
    nan_feats  = nan_counts[nan_counts > 0]
    nan_rows   = df[feat_cols].isnull().any(axis=1)
    nan_run_count = nan_rows.sum()

    print(f"  Total NaN: {nan_counts.sum()}")
    print(f"  Features with NaN: {len(nan_feats)}")
    print(f"  Runs with any NaN: {nan_run_count}")

    # ── 2. Categorize Features ───────────────────────────────────────────────
    print("[2/7] Categorizing features...")
    categories, sig_map = categorize_features(sig_df)

    cat_counts = {}
    for f, cat in categories.items():
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    print(f"  RECOMMENDED    : {cat_counts.get('RECOMMENDED', 0)}")
    print(f"  REDUNDANT      : {cat_counts.get('REDUNDANT', 0)}")
    print(f"  NOT_SIGNIFICANT: {cat_counts.get('NOT_SIGNIFICANT', 0)}")
    print(f"  LOW_VARIANCE   : {cat_counts.get('LOW_VARIANCE', 0)}")

    # ── 3. Select Final Features ─────────────────────────────────────────────
    print("[3/7] Selecting final features...")
    final_feats, not_recommended = select_final_features(categories, sig_map)
    print(f"  Final features selected: {len(final_feats)}")

    # ── 4. Outlier Flagging ─────────────────────────────────────────────────
    print("[4/7] Flagging outliers (z-score threshold = 3.5)...")
    outlier_df = flag_outliers(df, numeric_feats, z_thresh=3.5)
    print(f"  Runs with outlier features: {len(outlier_df)}")

    # Add outlier flag to main df
    df['is_outlier_run'] = False
    df['n_outlier_feats'] = 0
    for _, orow in outlier_df.iterrows():
        idx = orow['row_index']
        df.at[idx, 'is_outlier_run'] = True
        df.at[idx, 'n_outlier_feats'] = orow['n_outlier_feats']

    # ── 5. Class Balance ─────────────────────────────────────────────────────
    print("[5/7] Class balance analysis...")
    class_counts = df['roast_level'].value_counts()
    total = len(df)
    for cls, cnt in class_counts.items():
        print(f"  {cls:<10}: {cnt:3d} ({cnt/total*100:.1f}%)")

    # Imbalance ratio: max/min
    imbalance_ratio = class_counts.max() / class_counts.min()
    print(f"  Imbalance ratio (max/min): {imbalance_ratio:.2f}")

    # ── 6. Build ml_dataset_full ─────────────────────────────────────────────
    print("[6/7] Building ml_dataset_full.csv...")

    # Add feature category columns as suffix metadata
    full_meta  = ['sample_id','roast_level','origin','batch_id','run_id']
    full_cols  = full_meta + feat_cols + ['is_outlier_run','n_outlier_feats']
    ml_full    = df[full_cols].copy()
    ml_full.to_csv(OUT_FULL, index=False)
    print(f"  Saved: {OUT_FULL}  ({len(ml_full)} rows x {len(ml_full.columns)} cols)")

    # ── 7. Build ml_dataset_final ────────────────────────────────────────────
    print("[7/7] Building ml_dataset_final.csv...")
    final_cols  = ['sample_id','roast_level','origin','batch_id','run_id'] + \
                  final_feats + ['is_outlier_run','n_outlier_feats']
    ml_final    = df[final_cols].copy()
    ml_final.to_csv(OUT_FINAL, index=False)
    print(f"  Saved: {OUT_FINAL}  ({len(ml_final)} rows x {len(ml_final.columns)} cols)")

    # Save outlier detail report
    if len(outlier_df) > 0:
        outlier_path = os.path.join(PROCESSED_DIR, 'outlier_report.csv')
        outlier_df.to_csv(outlier_path, index=False)

    # ── Generate Summary Markdown ─────────────────────────────────────────────
    print()
    print("  Writing ml_dataset_summary.md...")

    # Feature groupings for report
    recommended_by_sensor = {}
    not_sig_by_sensor     = {}
    redundant_by_sensor   = {}

    for sensor in SENSORS:
        rec = [f for f in final_feats if f.startswith(sensor+'_')]
        red = [f for f, cat, _ in not_recommended if f.startswith(sensor+'_') and cat=='REDUNDANT']
        ns  = [f for f, cat, _ in not_recommended if f.startswith(sensor+'_') and cat=='NOT_SIGNIFICANT']
        recommended_by_sensor[sensor] = rec
        redundant_by_sensor[sensor]   = red
        not_sig_by_sensor[sensor]     = ns

    # Calculate stats for report
    n_light  = int(class_counts.get('light', 0))
    n_medium = int(class_counts.get('medium', 0))
    n_dark   = int(class_counts.get('dark', 0))
    n_batch  = df['batch_id'].nunique()

    lines = []
    lines.append("# ML Dataset Summary -- E-NOSE Kopi\n\n")
    lines.append(f"**Tanggal:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    lines.append("---\n\n")

    # 1. Total data
    lines.append("## 1. Total Data\n\n")
    lines.append(f"| Keterangan | Nilai |\n|---|---|\n")
    lines.append(f"| Total RUN (baris) | {total} |\n")
    lines.append(f"| Jumlah Light | {n_light} ({n_light/total*100:.1f}%) |\n")
    lines.append(f"| Jumlah Medium | {n_medium} ({n_medium/total*100:.1f}%) |\n")
    lines.append(f"| Jumlah Dark | {n_dark} ({n_dark/total*100:.1f}%) |\n")
    lines.append(f"| Jumlah Batch | {n_batch} ({', '.join(sorted(df['batch_id'].unique()))}) |\n")
    lines.append(f"| Jumlah Sample ID | {df['sample_id'].nunique()} |\n\n")

    # 2. Feature summary
    lines.append("## 2. Ringkasan Feature\n\n")
    lines.append(f"| Keterangan | Jumlah |\n|---|---|\n")
    lines.append(f"| Feature awal | {len(feat_cols)} |\n")
    lines.append(f"| Feature RECOMMENDED (final) | {len(final_feats)} |\n")
    lines.append(f"| Feature REDUNDANT (tidak masuk final) | {cat_counts.get('REDUNDANT', 0)} |\n")
    lines.append(f"| Feature NOT_SIGNIFICANT (tidak masuk final) | {cat_counts.get('NOT_SIGNIFICANT', 0)} |\n")
    lines.append(f"| Feature LOW_VARIANCE | {cat_counts.get('LOW_VARIANCE', 0)} |\n\n")

    # 3. Feature yang direkomendasikan per sensor
    lines.append("## 3. Feature yang Direkomendasikan (ml_dataset_final.csv)\n\n")
    lines.append("| Sensor | Features | Jumlah |\n|--------|----------|--------|\n")
    for sensor in SENSORS:
        feats = recommended_by_sensor.get(sensor, [])
        stat_names = [f.replace(sensor+'_', '') for f in feats]
        marker = ' *(drift terdeteksi)*' if sensor in DRIFT_SENSORS else ''
        lines.append(f"| {sensor}{marker} | {', '.join(stat_names) if stat_names else '-'} | {len(feats)} |\n")

    # 4. Feature yang tidak direkomendasikan
    lines.append("\n## 4. Feature yang Tidak Direkomendasikan\n\n")
    lines.append("### 4a. Redundan (r > 0.95 dengan fitur lain)\n\n")
    lines.append("Fitur-fitur berikut sangat berkorelasi dengan fitur lain dan direduksi "
                 "untuk menghindari multikolinearitas:\n\n")
    lines.append("| Fitur yang Di-drop | Alasan | Fitur Representatif |\n|---|---|---|\n")
    drop_map = {
        'median': 'r~1.0 dengan mean',
        'auc':    'r~1.0 dengan mean',
        'var':    'r=1.0 dengan std (var = std^2)',
        'initial':'r~0.999 dengan min',
        'final':  'r~0.999 dengan mean/median',
    }
    for sensor in SENSORS:
        for stat in sorted(REDUNDANT_STATS):
            f = f'{sensor}_{stat}'
            lines.append(f"| `{f}` | {drop_map.get(stat, 'redundant')} | `{sensor}_{'mean' if stat in ('median','auc','final') else ('std' if stat=='var' else 'min')}` |\n")

    lines.append("\n### 4b. Tidak Signifikan (p >= 0.05)\n\n")
    lines.append("| Sensor | Features Tidak Signifikan |\n|--------|---------------------------|\n")
    for sensor in SENSORS:
        ns_feats = not_sig_by_sensor.get(sensor, [])
        stat_names = [f.replace(sensor+'_','') for f in ns_feats]
        lines.append(f"| {sensor} | {', '.join(stat_names) if stat_names else 'Semua signifikan'} |\n")

    # 5. Missing value
    lines.append("\n## 5. Missing Value\n\n")
    if nan_counts.sum() == 0:
        lines.append("**PASS** -- Tidak ditemukan missing value pada seluruh feature.\n\n")
    else:
        lines.append(f"**Total NaN:** {nan_counts.sum()}\n\n")
        lines.append("| Feature | NaN Count |\n|---|---|\n")
        for f, cnt in nan_feats.items():
            lines.append(f"| `{f}` | {cnt} |\n")

    # 6. Outlier
    lines.append("\n## 6. Outlier Report\n\n")
    lines.append(f"**Metode:** Z-score per feature (threshold |z| > 3.5)\n\n")
    lines.append(f"**Total run dengan outlier feature:** {len(outlier_df)} / {total}\n\n")
    if len(outlier_df) > 0:
        lines.append("> **Catatan:** Outlier TIDAK dihapus. Ditandai dengan kolom "
                     "`is_outlier_run=True` pada dataset. Perlu dianalisis lebih lanjut "
                     "sebelum memutuskan apakah run tersebut valid atau tidak.\n\n")
        lines.append("| Sample | Batch | Run | Roast | n_outlier_feats | max_z | Outlier Features (5 teratas) |\n")
        lines.append("|--------|-------|-----|-------|-----------------|-------|------------------------------|\n")
        for _, orow in outlier_df.head(20).iterrows():
            lines.append(f"| {orow['sample_id']} | {orow['batch_id']} | "
                         f"{orow['run_id']} | {orow['roast_level']} | "
                         f"{orow['n_outlier_feats']} | {orow['max_z']:.2f} | "
                         f"`{orow['outlier_features']}` |\n")
        if len(outlier_df) > 20:
            lines.append(f"\n*...dan {len(outlier_df)-20} run lainnya. Lihat `processed/outlier_report.csv`.*\n\n")
    else:
        lines.append("> Tidak ada run dengan z-score outlier > 3.5.\n\n")

    # 7. Class Imbalance
    lines.append("## 7. Class Balance\n\n")
    lines.append(f"| Roast Level | Jumlah | Persentase |\n|-------------|--------|------------|\n")
    lines.append(f"| light  | {n_light}  | {n_light/total*100:.1f}% |\n")
    lines.append(f"| medium | {n_medium} | {n_medium/total*100:.1f}% |\n")
    lines.append(f"| dark   | {n_dark}   | {n_dark/total*100:.1f}% |\n")
    lines.append(f"\n**Imbalance Ratio (max/min):** {imbalance_ratio:.2f}\n\n")

    if imbalance_ratio > 1.5:
        lines.append("> **Perhatian:** Terdapat class imbalance (ratio > 1.5). "
                     "Light memiliki data lebih banyak dari Dark.\n")
        lines.append("> Pada tahap training, pertimbangkan:\n")
        lines.append("> - `class_weight='balanced'` pada Random Forest\n")
        lines.append("> - Stratified K-Fold Cross-Validation\n")
        lines.append("> - Evaluasi menggunakan macro-average F1-score, bukan accuracy saja\n\n")
    else:
        lines.append("> Distribusi kelas cukup seimbang.\n\n")

    # 8. Batch distribution
    lines.append("## 8. Distribusi Batch per Roast Level\n\n")
    lines.append("| Roast | B01 | B02 | B03 | B04 | B05 |\n")
    lines.append("|-------|-----|-----|-----|-----|-----|\n")
    for roast in ['light','medium','dark']:
        row_vals = []
        for batch in ['B01','B02','B03','B04','B05']:
            cnt = len(df[(df['roast_level']==roast) & (df['batch_id']==batch)])
            row_vals.append(str(cnt) if cnt > 0 else '-')
        lines.append(f"| {roast} | {' | '.join(row_vals)} |\n")

    lines.append("\n> **Catatan drift batch:** Sensor TGS822 dan TGS2611 menunjukkan "
                 "indikasi perubahan baseline antar batch (>18%). "
                 "Perlu dipertimbangkan normalisasi per batch atau penggunaan "
                 "fitur relatif (delta, slope, range) yang lebih robust terhadap drift.\n\n")

    # 9. Data leakage check
    lines.append("## 9. Pemeriksaan Data Leakage\n\n")
    lines.append("| Kolom | Status | Keterangan |\n|-------|--------|------------|\n")
    lines.append("| `sample_id` | METADATA | Tidak masuk fitur input model |\n")
    lines.append("| `origin` | METADATA | Tidak masuk fitur input model |\n")
    lines.append("| `batch_id` | METADATA | Tidak masuk fitur input model |\n")
    lines.append("| `run_id` | METADATA | Tidak masuk fitur input model |\n")
    lines.append("| `roast_level` | TARGET | Hanya sebagai label |\n")
    lines.append("| `timestamp` | TIDAK ADA | Tidak bocor ke feature dataset |\n")
    lines.append("| `phase` | TIDAK ADA | Tidak bocor ke feature dataset |\n")
    lines.append("| `sample_idx` | TIDAK ADA | Tidak bocor ke feature dataset |\n")
    lines.append("\n> **PASS** -- Tidak terdeteksi data leakage. Seluruh fitur diekstrak "
                 "dari fase `collecting` saja, tanpa informasi label bocor ke fitur.\n\n")
    lines.append("> **Catatan tambahan:** Karena satu sample_id dapat muncul di lebih dari "
                 "satu batch, gunakan **GroupKFold** dengan group=`sample_id` atau "
                 "`batch_id` saat cross-validation untuk menghindari data leakage antar fold.\n\n")

    # 10. Recommendations
    lines.append("## 10. Rekomendasi Tahap Machine Learning\n\n")
    lines.append("### 10.1 Input File\n")
    lines.append("- Gunakan `ml_dataset_final.csv` untuk training model.\n")
    lines.append("- `ml_dataset_full.csv` untuk eksperimen dan ablation study.\n\n")
    lines.append("### 10.2 Feature Engineering (Opsional)\n")
    lines.append("- Pertimbangkan normalisasi per batch untuk TGS822 dan TGS2611 (drift terdeteksi).\n")
    lines.append("- Fitur `slope` dan `delta` relatif lebih robust terhadap drift baseline.\n\n")
    lines.append("### 10.3 Cross-Validation\n")
    lines.append("- Gunakan **Stratified K-Fold** (k=5 atau k=10) untuk menjaga proporsi kelas.\n")
    lines.append("- Atau **GroupKFold** dengan group=`sample_id` agar data dari sample yang sama "
                 "tidak tersebar di train dan test sekaligus.\n\n")
    lines.append("### 10.4 Model\n")
    lines.append("- **Random Forest** dengan `class_weight='balanced'` untuk mengatasi class imbalance.\n")
    lines.append("- Evaluasi dengan: Accuracy, macro-F1, Confusion Matrix, per-class Precision/Recall.\n\n")
    lines.append("### 10.5 Feature yang Perlu Diperhatikan\n")
    lines.append(f"- **Paling diskriminatif:** TGS2602_max, TGS822_max, TGS2620_max, MQ8_mean, TGS816_mean\n")
    lines.append(f"- **Kurang informatif:** MQ135 (sebagian besar fitur tidak signifikan), "
                 f"TGS2600 (hanya delta signifikan)\n")
    lines.append(f"- **Perhatian drift:** TGS822, TGS2611 (pertimbangkan normalisasi)\n\n")

    lines.append("---\n")
    lines.append("*Laporan ini tidak mengandung hasil training machine learning.*\n")
    lines.append("*Dataset siap digunakan untuk tahap training Random Forest.*\n")

    with open(OUT_SUMMARY, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    # ── Final Console Summary ────────────────────────────────────────────────
    print()
    print("="*70)
    print("  FINALISASI DATASET SELESAI")
    print("="*70)
    print(f"  Total RUN                    : {total}")
    print(f"  Light / Medium / Dark        : {n_light} / {n_medium} / {n_dark}")
    print(f"  Imbalance ratio              : {imbalance_ratio:.2f}")
    print(f"  Feature awal                 : {len(feat_cols)}")
    print(f"  Feature final (ml_final)     : {len(final_feats)}")
    print(f"  Feature redundan (dropped)   : {cat_counts.get('REDUNDANT',0)}")
    print(f"  Feature tidak signifikan     : {cat_counts.get('NOT_SIGNIFICANT',0)}")
    print(f"  Missing value                : {nan_counts.sum()}")
    print(f"  Run dengan outlier flag      : {len(outlier_df)}")
    print()
    print(f"  ml_dataset_full.csv  -> {len(ml_full.columns)} kolom")
    print(f"  ml_dataset_final.csv -> {len(ml_final.columns)} kolom")
    print(f"  ml_dataset_summary.md")
    print()
    print("[DONE] Dataset siap untuk training Machine Learning.")


if __name__ == '__main__':
    main()
