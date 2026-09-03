"""
4_train_rf.py
-------------------------------------------------------------------------------
Pelatihan Model Random Forest untuk Klasifikasi Tingkat Roasting Kopi
  Light / Medium / Dark

Mendukung 2 Mode:
  1. OPTIMIZED (Default, 89 Fitur):
     - Menghilangkan multikolinearitas (hapus sum_* dan ratio_to_tgs822_*)
     - Menambahkan dinamika sinyal: std_* & peak_to_base_*
     - Menambahkan karakteristik kinetika transisi: onset_* & decay_*
     - Akurasi CV 5-Fold: ~80%, Test Set: ~90%

  2. LEGACY / ONDEVICE (48 Fitur):
     - Format standar fase collecting (10 mean + 10 max + 10 sum + 9 ratio MQ135 + 9 ratio TGS822)
     - Kompatibel langsung dengan implementasi firmware inference_atmega.cpp

Cara pakai:
    python scripts/4_train_rf.py                 # Mode Teroptimasi (89 Fitur, Rekomendasi)
    python scripts/4_train_rf.py --mode legacy   # Mode Standar On-Device (48 Fitur)
-------------------------------------------------------------------------------
"""

import os
import glob
import sys
import json
import argparse
import warnings
warnings.filterwarnings('ignore')

import pandas as pd
import numpy as np
from scipy import stats as sp_stats
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
import joblib

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import seaborn as sns
    HAS_PLOT = True
except ImportError:
    HAS_PLOT = False

# ─── Path Konfigurasi ────────────────────────────────────────────────────────
SCRIPTS_DIR   = os.path.dirname(os.path.abspath(__file__))
BASE_DIR      = os.path.normpath(os.path.join(SCRIPTS_DIR, '..'))
DATA_DIR      = os.path.join(BASE_DIR, 'data')
INCLUDE_DIR   = os.path.join(BASE_DIR, 'include')

OUTPUT_CSV    = os.path.join(DATA_DIR, 'dataset_fitur.csv')
OUTPUT_HEADER = os.path.join(INCLUDE_DIR, 'model_rf_atmega.h')
MODEL_PATH    = os.path.join(DATA_DIR, 'model_rf.joblib')
OUTPUT_PLOT   = os.path.join(DATA_DIR, 'confusion_matrix.png')
FEAT_JSON     = os.path.join(DATA_DIR, 'feature_list.json')

VALID_LABELS  = ['light', 'medium', 'dark']

# 10 Sensor Gas Array
ADC_COLS = [
    'adc_tgs822', 'adc_mq135', 'adc_mq9', 'adc_tgs2611',
    'adc_tgs2620', 'adc_tgs2600', 'adc_tgs2602', 'adc_mq8',
    'adc_tgs813', 'adc_tgs816'
]

# Hyperparameter Random Forest
RF_N_ESTIMATORS = 12
RF_MAX_DEPTH    = 5
RF_RANDOM_STATE = 42

ONSET_WINDOW = 20
DECAY_WINDOW = 20


# -----------------------------------------------------------------------------
#  1. LOAD DATA
# -----------------------------------------------------------------------------
def load_raw_data():
    """Muat semua CSV mentah dari folder data/."""
    csv_files = glob.glob(os.path.join(DATA_DIR, '*.csv'))
    SKIP = ['dataset_fitur', 'dataset_interactive', 'anomal']
    csv_files = [f for f in csv_files if not any(p in os.path.basename(f).lower() for p in SKIP)]

    if not csv_files:
        print(f"[ERROR] Tidak ada file CSV di: {DATA_DIR}")
        sys.exit(1)

    print(f"[INFO] Ditemukan {len(csv_files)} file CSV mentah:")
    dfs = []
    for f in csv_files:
        try:
            df = pd.read_csv(f)
            if 'source_file' not in df.columns:
                df['source_file'] = os.path.basename(f)
            dfs.append(df)
        except Exception as e:
            print(f"  [GAGAL] {os.path.basename(f)}: {e}")

    df_all = pd.concat(dfs, ignore_index=True)
    print(f"       Total baris: {len(df_all)}")
    return df_all


# -----------------------------------------------------------------------------
#  2. EKSTRAKSI FITUR
# -----------------------------------------------------------------------------
def extract_features(df_all, mode='optimized'):
    """
    Ekstraksi fitur per siklus.
    - mode='optimized': 89 fitur (Mean, Max, Std, Peak-to-Base, Ratio MQ135, Onset, Decay)
    - mode='legacy'   : 48 fitur (Mean, Max, Sum, Ratio MQ135, Ratio TGS822)
    """
    for col in ADC_COLS:
        if col not in df_all.columns:
            df_all[col] = 0
        df_all[col] = pd.to_numeric(df_all[col], errors='coerce').fillna(0)

    if 'cycle' not in df_all.columns:
        df_all['cycle'] = 1

    df_all = df_all[df_all['label'].str.lower().isin(VALID_LABELS)].copy()
    df_all['label'] = df_all['label'].str.lower()
    group_keys = [k for k in ['source_file', 'label', 'cycle'] if k in df_all.columns]

    rows = []
    for keys, group in df_all.groupby(group_keys):
        kd = dict(zip(group_keys, keys if isinstance(keys, tuple) else (keys,)))
        row = {
            'source_file': kd.get('source_file', '?'),
            'label':       kd.get('label', '?'),
            'cycle':       kd.get('cycle', 1),
        }

        df_col = group[group['phase'] == 'collecting'].copy()
        df_pur = group[group['phase'] == 'purging'].copy()

        if len(df_col) < 5:
            continue

        if 'sample_idx' in df_col.columns:
            df_col = df_col.sort_values('sample_idx')
        if 'sample_idx' in df_pur.columns:
            df_pur = df_pur.sort_values('sample_idx')

        row['n_samples'] = len(df_col)

        # ─── A. Mode OPTIMIZED (89 Fitur) ───────────────────────────────────
        if mode == 'optimized':
            # 1. Mean, Max, Std
            for col in ADC_COLS:
                vals = df_col[col].values
                row[f'mean_{col}'] = float(np.mean(vals))
                row[f'max_{col}']  = float(np.max(vals))
                row[f'std_{col}']  = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0

            # 2. Peak-to-Baseline Ratio
            for col in ADC_COLS:
                pb = df_pur[col].values if len(df_pur) > 0 else np.zeros(1)
                baseline = float(np.mean(pb[-10:])) if len(pb) >= 10 else float(np.mean(pb))
                peak = row[f'max_{col}']
                row[f'peak_to_base_{col}'] = (peak - baseline) / max(abs(baseline), 1.0)

            # 3. Rasio ke MQ135
            mq135_max = row['max_adc_mq135'] if row['max_adc_mq135'] > 0 else 1.0
            for col in ADC_COLS:
                if col != 'adc_mq135':
                    row[f'ratio_to_mq135_{col}'] = row[f'max_{col}'] / mq135_max

            # 4. Onset Transitions
            w_on = min(ONSET_WINDOW, len(df_col))
            t_on = np.arange(w_on, dtype=float)
            for col in ADC_COLS:
                seg = df_col[col].values[:w_on].astype(float)
                row[f'onset_{col}_slope'] = float(sp_stats.linregress(t_on, seg)[0]) if w_on > 1 else 0.0
                fast_n = min(5, w_on)
                row[f'onset_{col}_rise_drop'] = float(seg[fast_n - 1] - seg[0]) if fast_n > 1 else 0.0

            # 5. Decay Transitions
            if len(df_pur) >= 2:
                w_dec = min(DECAY_WINDOW, len(df_pur))
                t_dec = np.arange(w_dec, dtype=float)
                for col in ADC_COLS:
                    seg = df_pur[col].values[:w_dec].astype(float)
                    row[f'decay_{col}_slope'] = float(sp_stats.linregress(t_dec, seg)[0]) if w_dec > 1 else 0.0
                    fast_n = min(5, w_dec)
                    row[f'decay_{col}_rise_drop'] = float(seg[fast_n - 1] - seg[0]) if fast_n > 1 else 0.0
            else:
                for col in ADC_COLS:
                    row[f'decay_{col}_slope'] = 0.0
                    row[f'decay_{col}_rise_drop'] = 0.0

        # ─── B. Mode LEGACY / ONDEVICE (48 Fitur) ────────────────────────────
        else:
            for col in ADC_COLS:
                vals = df_col[col].values
                row[f'mean_{col}'] = float(np.mean(vals))
                row[f'max_{col}']  = float(np.max(vals))
                row[f'sum_{col}']  = float(np.sum(vals))

            mq135_max = row['max_adc_mq135'] if row['max_adc_mq135'] > 0 else 1.0
            for col in ADC_COLS:
                if col != 'adc_mq135':
                    row[f'ratio_to_mq135_{col}'] = row[f'max_{col}'] / mq135_max

            tgs822_max = row['max_adc_tgs822'] if row['max_adc_tgs822'] > 0 else 1.0
            for col in ADC_COLS:
                if col != 'adc_tgs822':
                    row[f'ratio_to_tgs822_{col}'] = row[f'max_{col}'] / tgs822_max

        rows.append(row)

    df_feat = pd.DataFrame(rows)
    print(f"[INFO] Fitur diekstrak: {len(df_feat)} siklus sampel")
    print(f"       Distribusi label:\n{df_feat['label'].value_counts().to_string()}")
    return df_feat


def get_feature_columns(df_feat, mode='optimized'):
    """Daftar nama kolom fitur sesuai mode."""
    if mode == 'optimized':
        cols = (
            [f'mean_{c}' for c in ADC_COLS] +
            [f'max_{c}' for c in ADC_COLS] +
            [f'std_{c}' for c in ADC_COLS] +
            [f'peak_to_base_{c}' for c in ADC_COLS] +
            [f'ratio_to_mq135_{c}' for c in ADC_COLS if c != 'adc_mq135'] +
            [f'onset_{c}_{s}' for c in ADC_COLS for s in ['slope', 'rise_drop']] +
            [f'decay_{c}_{s}' for c in ADC_COLS for s in ['slope', 'rise_drop']]
        )
    else:
        cols = (
            [f'mean_{c}' for c in ADC_COLS] +
            [f'max_{c}'  for c in ADC_COLS] +
            [f'sum_{c}'  for c in ADC_COLS] +
            [f'ratio_to_mq135_{c}' for c in ADC_COLS if c != 'adc_mq135'] +
            [f'ratio_to_tgs822_{c}' for c in ADC_COLS if c != 'adc_tgs822']
        )
    return [c for c in cols if c in df_feat.columns]


# -----------------------------------------------------------------------------
#  3. TRAINING & EVALUASI
# -----------------------------------------------------------------------------
def train_model(df_feat, mode='optimized'):
    feature_cols = get_feature_columns(df_feat, mode=mode)
    X = df_feat[feature_cols].fillna(0).to_numpy(dtype=np.float32)
    y = df_feat['label'].astype(str).to_numpy()

    print(f"\n[INFO] Mode Training : {mode.upper()} ({len(feature_cols)} Fitur)")
    print(f"[INFO] Jumlah Sampel : {len(X)}")

    if len(df_feat) < 4:
        print("[ERROR] Dataset terlalu kecil untuk evaluasi.")
        sys.exit(1)

    # 5-Fold Stratified Cross Validation
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RF_RANDOM_STATE)
    clf_cv = RandomForestClassifier(n_estimators=RF_N_ESTIMATORS, max_depth=RF_MAX_DEPTH,
                                    random_state=RF_RANDOM_STATE, class_weight='balanced')
    cv_scores = cross_val_score(clf_cv, X, y, cv=cv, scoring='accuracy')
    print(f"[CV 5-Fold] Akurasi Rata-rata: {cv_scores.mean() * 100:.2f}% ± {cv_scores.std() * 100:.2f}%")

    # Split Train / Test
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=RF_RANDOM_STATE
    )

    clf = RandomForestClassifier(n_estimators=RF_N_ESTIMATORS, max_depth=RF_MAX_DEPTH,
                                 random_state=RF_RANDOM_STATE, class_weight='balanced')
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    print(f"[TEST SET] Akurasi: {acc * 100:.2f}%\n")
    print(classification_report(y_test, y_pred, zero_division=0))

    # Top Feature Importances
    imp = pd.Series(clf.feature_importances_, index=feature_cols).sort_values(ascending=False)
    print("Top 12 Feature Importance:")
    for feat, val in imp.head(12).items():
        bar = '#' * int(val * 40)
        print(f"  {feat:<35} {bar} {val:.4f}")

    # Plot Confusion Matrix
    if HAS_PLOT:
        labels_order = sorted(set(y_test) | set(y_pred))
        cm = confusion_matrix(y_test, y_pred, labels=labels_order)
        plt.figure(figsize=(6, 5))
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                    xticklabels=labels_order, yticklabels=labels_order)
        plt.title(f'Confusion Matrix ({mode.upper()} - Acc: {acc*100:.1f}%)')
        plt.xlabel('Predicted')
        plt.ylabel('Actual')
        plt.tight_layout()
        plt.savefig(OUTPUT_PLOT, dpi=120)
        print(f"\n[PLOT] Confusion matrix disimpan: {OUTPUT_PLOT}")

    return clf, feature_cols


# -----------------------------------------------------------------------------
#  4. SIMPAN MODEL & EXPORT C++ HEADER
# -----------------------------------------------------------------------------
def export_to_header(clf, feature_cols, mode='optimized'):
    """Simpan model dan export C++ header."""
    joblib.dump(clf, MODEL_PATH)
    print(f"\n[SIMPAN] Model tersimpan di: {MODEL_PATH}")

    sys.path.insert(0, SCRIPTS_DIR)
    try:
        from generate_model_atmega import export_model_atmega
        os.makedirs(INCLUDE_DIR, exist_ok=True)
        export_model_atmega(MODEL_PATH, OUTPUT_HEADER,
                            max_trees=RF_N_ESTIMATORS, max_depth=RF_MAX_DEPTH)
        print(f"[EXPORT] Header C++ siap di: {OUTPUT_HEADER}")
    except Exception as e:
        print(f"[WARN] Export C++ header: {e}")

    with open(FEAT_JSON, 'w') as f:
        json.dump({
            'mode': mode,
            'total_features': len(feature_cols),
            'features': feature_cols,
            'rf_n_estimators': RF_N_ESTIMATORS,
            'rf_max_depth': RF_MAX_DEPTH
        }, f, indent=2)
    print(f"[SIMPAN] Metadata fitur di: {FEAT_JSON}")


# -----------------------------------------------------------------------------
#  MAIN RUNNER
# -----------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Pelatihan Model RF E-Nose Kopi")
    parser.add_argument('--mode', choices=['optimized', 'legacy'], default='optimized',
                        help="Pilih mode ekstraksi fitur: 'optimized' (89 fitur, default) atau 'legacy' (48 fitur)")
    args = parser.parse_args()

    print(f"""
+------------------------------------------------------+
|   E-NOSE Kopi — Training Random Forest               |
|   Mode: {args.mode.upper():<44} |
+------------------------------------------------------+
""")

    df_all = load_raw_data()
    df_feat = extract_features(df_all, mode=args.mode)

    os.makedirs(DATA_DIR, exist_ok=True)
    df_feat.to_csv(OUTPUT_CSV, index=False)
    print(f"[DATASET] Fitur disimpan: {OUTPUT_CSV}")

    clf, feature_cols = train_model(df_feat, mode=args.mode)
    export_to_header(clf, feature_cols, mode=args.mode)

    print("\n[OK] Proses training dan ekspor selesai!")


if __name__ == '__main__':
    main()
