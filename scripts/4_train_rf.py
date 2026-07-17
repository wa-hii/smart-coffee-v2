"""
4_train_rf.py
═══════════════════════════════════════════════════════════════════════════════
Training Random Forest untuk Klasifikasi Tingkat Roasting Kopi
  Light / Medium / Dark

Pipeline:
  1. Load semua CSV dari folder data/
  2. Ekstraksi fitur statistik per siklus collecting
     (mean + max per sensor = 16 fitur)
  3. Split train/test → Train RandomForestClassifier
  4. Evaluasi (akurasi, confusion matrix, feature importance)
  5. Export model ke C++ header (include/model_rf.h) via micromlgen
     → siap di-include di ESP32 firmware untuk inferensi on-device

Cara pakai:
  pip install scikit-learn pandas matplotlib seaborn micromlgen
  python 4_train_rf.py

Setelah berhasil:
  1. Buka src/main.cpp
  2. Ubah: #define USE_ON_DEVICE_INFERENCE 1
  3. Flash ulang ke ESP32
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import glob
import sys
import warnings
warnings.filterwarnings('ignore')

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.preprocessing import LabelEncoder

try:
    import matplotlib
    matplotlib.use('Agg')  # non-interactive backend (bisa diganti 'TkAgg' jika ingin tampil)
    import matplotlib.pyplot as plt
    import seaborn as sns
    HAS_PLOT = True
except ImportError:
    HAS_PLOT = False
    print("⚠️  matplotlib/seaborn tidak terinstall – plot dinonaktifkan.")

try:
    from micromlgen import port
    HAS_MICROMLGEN = True
except ImportError:
    HAS_MICROMLGEN = False
    print("⚠️  micromlgen tidak terinstall.")
    print("   Jalankan: pip install micromlgen")

# ─── Path konfigurasi ────────────────────────────────────────────────────────
SCRIPTS_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_DIR      = os.path.join(SCRIPTS_DIR, '..', 'data')
OUTPUT_DIR    = os.path.join(SCRIPTS_DIR, '..', 'data')
INCLUDE_DIR   = os.path.join(SCRIPTS_DIR, '..', 'include')
OUTPUT_CSV    = os.path.join(OUTPUT_DIR,  'dataset_fitur.csv')
OUTPUT_HEADER = os.path.join(INCLUDE_DIR, 'model_rf.h')
OUTPUT_PLOT   = os.path.join(OUTPUT_DIR,  'confusion_matrix.png')

VALID_LABELS  = ['light', 'medium', 'dark']

# ─── Kolom ADC yang digunakan sebagai dasar fitur ────────────────────────────
# Urutan HARUS sama dengan feat_sum_/feat_max_ di main.cpp doInference()
ADC_COLS = ['adc_mq135', 'adc_mq136', 'adc_mq137', 'adc_mq138',
            'adc_mq2',   'adc_mq3',   'adc_tgs822', 'adc_tgs2620']

# ─── Hyperparameter Random Forest ────────────────────────────────────────────
# Diset kecil agar model ringan di RAM ESP32 (~60 KB)
RF_N_ESTIMATORS = 15
RF_MAX_DEPTH    = 6
RF_RANDOM_STATE = 42


# ═════════════════════════════════════════════════════════════════════════════
#  1. LOAD DATA
# ═════════════════════════════════════════════════════════════════════════════
def load_raw_data():
    """Muat semua CSV dari data/ dan gabungkan."""
    csv_files = glob.glob(os.path.join(DATA_DIR, '*.csv'))
    csv_files = [f for f in csv_files if 'dataset_fitur' not in os.path.basename(f)]

    if not csv_files:
        print(f"❌ Tidak ada file CSV di: {DATA_DIR}")
        print("   Jalankan 3_collect_data.py terlebih dahulu untuk mengumpulkan data.")
        sys.exit(1)

    print(f"📂 Ditemukan {len(csv_files)} file CSV:")
    dfs = []
    for f in csv_files:
        try:
            df = pd.read_csv(f)
            # Tambahkan nama file sebagai sumber jika belum ada
            if 'source_file' not in df.columns:
                df['source_file'] = os.path.basename(f)
            dfs.append(df)
            label_cnt = df['label'].value_counts().to_dict() if 'label' in df.columns else {}
            phase_cnt = df['phase'].value_counts().to_dict() if 'phase' in df.columns else {}
            print(f"   ✓ {os.path.basename(f):40s} | {len(df):5d} baris | label: {label_cnt} | phase: {phase_cnt}")
        except Exception as e:
            print(f"   ✗ {os.path.basename(f)} — GAGAL: {e}")

    if not dfs:
        print("❌ Tidak ada data berhasil dimuat.")
        sys.exit(1)

    df_all = pd.concat(dfs, ignore_index=True)
    print(f"\n📊 Total: {len(df_all)} baris, {df_all['label'].nunique()} kelas")
    return df_all


# ═════════════════════════════════════════════════════════════════════════════
#  2. EKSTRAKSI FITUR
# ═════════════════════════════════════════════════════════════════════════════
def extract_features(df_all):
    """
    Ekstraksi fitur per siklus (cycle) dari fase COLLECTING.

    Setiap siklus (1 cycle = 180 sampel di fase collecting) menghasilkan 1 baris:
    - mean_<sensor> × 8  → rata-rata ADC selama collecting
    - max_<sensor>  × 8  → nilai puncak ADC selama collecting
    Total: 16 fitur + label

    Fitur ini KONSISTEN dengan doInference() di main.cpp yang menggunakan
    feat_sum_/feat_max_ dari fase collecting saja.
    """
    # Filter hanya fase collecting (purging disimpan di CSV tapi tidak untuk training fitur utama)
    df_col = df_all[df_all['phase'] == 'collecting'].copy()

    if df_col.empty:
        print("❌ Tidak ada baris dengan phase='collecting' di dataset.")
        sys.exit(1)

    # Pastikan kolom ADC ada dan numerik
    for col in ADC_COLS:
        if col not in df_col.columns:
            print(f"⚠️  Kolom '{col}' tidak ditemukan, diisi 0.")
            df_col[col] = 0
        df_col[col] = pd.to_numeric(df_col[col], errors='coerce').fillna(0)

    # Group by: sumber file + label + cycle → satu baris fitur
    group_keys = ['source_file', 'label', 'cycle']
    available_keys = [k for k in group_keys if k in df_col.columns]
    if 'cycle' not in df_col.columns:
        print("⚠️  Kolom 'cycle' tidak ada → semua dianggap cycle 1 per file.")
        df_col['cycle'] = 1
        available_keys = ['source_file', 'label', 'cycle']

    rows = []
    for keys, group in df_col.groupby(available_keys):
        key_dict = dict(zip(available_keys, keys if isinstance(keys, tuple) else (keys,)))
        row = {
            'source_file': key_dict.get('source_file', '?'),
            'label':       key_dict.get('label', '?'),
            'cycle':       key_dict.get('cycle', 1),
            'n_samples':   len(group),
        }
        for col in ADC_COLS:
            vals = group[col].values
            row[f'mean_{col}'] = float(np.mean(vals))
            row[f'max_{col}']  = float(np.max(vals))
        rows.append(row)

    df_feat = pd.DataFrame(rows)
    print(f"\n🔢 Fitur diekstrak: {len(df_feat)} sampel siklus")
    print(f"   Distribusi kelas:\n{df_feat['label'].value_counts().to_string()}")
    return df_feat


# ═════════════════════════════════════════════════════════════════════════════
#  3. TRAINING
# ═════════════════════════════════════════════════════════════════════════════
def train_model(df_feat):
    """
    Train RandomForestClassifier dan evaluasi hasilnya.
    Mengembalikan (clf, feature_cols, label_encoder).
    """
    # Buat daftar kolom fitur (mean + max, urutan konsisten dengan main.cpp)
    feature_cols = (
        [f'mean_{c}' for c in ADC_COLS] +
        [f'max_{c}'  for c in ADC_COLS]
    )
    # Filter kolom yang benar-benar ada
    feature_cols = [c for c in feature_cols if c in df_feat.columns]

    X = df_feat[feature_cols].values
    y = df_feat['label'].values

    print(f"\n⚙️  Jumlah fitur: {len(feature_cols)}")
    print(f"   Fitur: {feature_cols}")

    if len(df_feat) < 3:
        print("⚠️  Dataset terlalu kecil (<3 sampel). Kumpulkan lebih banyak data.")
        sys.exit(1)

    # ── Cross-validation (jika cukup data) ───────────────────────────────────
    if len(df_feat) >= 10:
        cv = StratifiedKFold(n_splits=min(5, len(df_feat)//2), shuffle=True, random_state=RF_RANDOM_STATE)
        clf_cv = RandomForestClassifier(
            n_estimators=RF_N_ESTIMATORS,
            max_depth=RF_MAX_DEPTH,
            random_state=RF_RANDOM_STATE)
        cv_scores = cross_val_score(clf_cv, X, y, cv=cv, scoring='accuracy')
        print(f"\n📊 Cross-Validation Accuracy: {cv_scores.mean()*100:.2f}% ± {cv_scores.std()*100:.2f}%")

    # ── Train/Test split ──────────────────────────────────────────────────────
    if len(df_feat) >= 6:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, stratify=y, random_state=RF_RANDOM_STATE)
    else:
        print("⚠️  Dataset kecil (<6 sampel) → training tanpa split test.")
        X_train, X_test, y_train, y_test = X, X, y, y

    # ── Fit model ────────────────────────────────────────────────────────────
    clf = RandomForestClassifier(
        n_estimators=RF_N_ESTIMATORS,
        max_depth=RF_MAX_DEPTH,
        random_state=RF_RANDOM_STATE,
        class_weight='balanced'   # atasi ketidakseimbangan kelas
    )
    clf.fit(X_train, y_train)

    # ── Evaluasi ─────────────────────────────────────────────────────────────
    y_pred = clf.predict(X_test)
    acc    = accuracy_score(y_test, y_pred)

    print(f"\n📈 === Hasil Evaluasi ===")
    print(f"   Akurasi Test Set : {acc*100:.2f}%")
    print(f"\n{classification_report(y_test, y_pred, zero_division=0)}")

    # ── Feature importance ────────────────────────────────────────────────────
    importances = pd.Series(clf.feature_importances_, index=feature_cols)
    importances_sorted = importances.sort_values(ascending=False)
    print("🏆 Feature Importance (top 10):")
    for feat, imp in importances_sorted.head(10).items():
        bar = '█' * int(imp * 40)
        print(f"   {feat:<20} {bar} {imp:.4f}")

    # ── Plot confusion matrix ─────────────────────────────────────────────────
    if HAS_PLOT:
        labels_order = sorted(set(y_test) | set(y_pred))
        cm = confusion_matrix(y_test, y_pred, labels=labels_order)
        plt.figure(figsize=(6, 5))
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                    xticklabels=labels_order, yticklabels=labels_order)
        plt.title(f'Confusion Matrix  (Accuracy: {acc*100:.1f}%)')
        plt.xlabel('Predicted'); plt.ylabel('Actual')
        plt.tight_layout()
        plt.savefig(OUTPUT_PLOT, dpi=120)
        print(f"\n📊 Confusion matrix disimpan: {OUTPUT_PLOT}")

    return clf, feature_cols


# ═════════════════════════════════════════════════════════════════════════════
#  4. EXPORT KE C++ HEADER (TinyML)
# ═════════════════════════════════════════════════════════════════════════════
def export_to_header(clf, feature_cols):
    """Export model ke C++ header untuk inferensi on-device di ESP32."""
    if not HAS_MICROMLGEN:
        print("\n❌ micromlgen tidak terinstall. Jalankan: pip install micromlgen")
        return

    os.makedirs(INCLUDE_DIR, exist_ok=True)

    try:
        c_code = port(clf, classmap={
            'light':  0,
            'medium': 1,
            'dark':   2,
        })
    except TypeError:
        # micromlgen versi lama tidak mendukung classmap
        c_code = port(clf)

    # Tambahkan header komentar agar mudah diidentifikasi
    header_comment = f"""\
/*
 * model_rf.h — Random Forest untuk E-NOSE Kopi
 * Di-generate otomatis oleh 4_train_rf.py via micromlgen
 *
 * Label   : light(0) / medium(1) / dark(2)
 * Fitur   : {len(feature_cols)} ({', '.join(feature_cols[:4])}...)
 * Trees   : {clf.n_estimators}
 * MaxDepth: {clf.max_depth}
 *
 * Cara pakai di main.cpp:
 *   #define USE_ON_DEVICE_INFERENCE 1
 *   #include "model_rf.h"
 *   Eloquent::ML::Port::RandomForest classifier;
 *   float features[{len(feature_cols)}] = {{ mean_mq135, ..., max_tgs2620 }};
 *   const char* label = classifier.predictLabel(features);
 */
"""
    full_code = header_comment + c_code

    with open(OUTPUT_HEADER, 'w', encoding='utf-8') as f:
        f.write(full_code)

    print(f"\n🎉 Model berhasil diekspor ke: {OUTPUT_HEADER}")
    print(f"   ({os.path.getsize(OUTPUT_HEADER)//1024} KB)")


# ═════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═════════════════════════════════════════════════════════════════════════════
def main():
    print("""
╔══════════════════════════════════════════════════════╗
║   E-NOSE Kopi — Training Random Forest (TinyML)     ║
╚══════════════════════════════════════════════════════╝
""")

    # 1. Load data mentah
    df_all = load_raw_data()

    # 2. Ekstraksi fitur per siklus
    df_feat = extract_features(df_all)

    # 3. Simpan dataset fitur (untuk referensi)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    df_feat.to_csv(OUTPUT_CSV, index=False)
    print(f"\n💾 Dataset fitur disimpan: {OUTPUT_CSV}")

    # 4. Training
    clf, feature_cols = train_model(df_feat)

    # 5. Export ke C++ header
    export_to_header(clf, feature_cols)

    # ─── Instruksi berikutnya ───────────────────────────────────────────────
    print(f"""
══════════════════════════════════════════════════════
  ✅ SELESAI! Langkah selanjutnya:
  1. Pastikan file include/model_rf.h sudah ada
  2. Buka src/main.cpp
  3. Ubah baris:  #define USE_ON_DEVICE_INFERENCE 0
             ke:  #define USE_ON_DEVICE_INFERENCE 1
  4. Flash ulang ke ESP32: pio run --target upload
  5. Kirim #start; dari Serial Monitor → setelah 10 siklus,
     ESP32 akan mencetak hasil klasifikasi roasting secara
     otomatis tanpa koneksi internet!
══════════════════════════════════════════════════════
""")


if __name__ == '__main__':
    main()
