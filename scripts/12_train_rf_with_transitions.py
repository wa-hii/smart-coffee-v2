"""
12_train_rf_with_transitions.py
Training Random Forest dengan Fitur Transisi Sinyal -- E-NOSE Kopi

FITUR BARU: Karakteristik Transisi Antar Fase
[A] ONSET (purging->collecting): Sampel pertama fase collecting
    - onset_slope  : kemiringan regresi (ADC/sampel) -- seberapa cepat naik
    - onset_delta  : nilai_akhir - nilai_awal window onset
    - onset_rise_drop: perubahan 5 sampel pertama

[B] DECAY (collecting->purging): Sampel pertama fase purging
    - decay_slope  : kemiringan (biasanya negatif -- turun)
    - decay_delta  : nilai_akhir - nilai_awal window decay
    - decay_rise_drop: penurunan 5 sampel pertama

Total Fitur: 48 (statistik collecting) + 60 (transisi 10 sensor x 6) = 108

Cara Pakai:
    pip install scikit-learn pandas numpy matplotlib seaborn joblib scipy
    python scripts/12_train_rf_with_transitions.py
"""

import os
import glob
import sys
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from scipy import stats as sp_stats
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
import joblib

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns
    HAS_PLOT = True
except ImportError:
    HAS_PLOT = False
    print("WARNING: matplotlib/seaborn belum terinstal -- plot dilewati.")

# -- Path Konfigurasi --
SCRIPTS_DIR   = os.path.dirname(os.path.abspath(__file__))
BASE_DIR      = os.path.normpath(os.path.join(SCRIPTS_DIR, ".."))
DATA_DIR      = os.path.join(BASE_DIR, "data")
INCLUDE_DIR   = os.path.join(BASE_DIR, "include")
OUTPUT_CSV    = os.path.join(DATA_DIR, "dataset_fitur_transisi.csv")
MODEL_PATH    = os.path.join(DATA_DIR, "model_rf_transisi.joblib")
OUTPUT_HEADER = os.path.join(INCLUDE_DIR, "model_rf_atmega.h")
OUTPUT_PLOT   = os.path.join(DATA_DIR, "confusion_matrix_transisi.png")

# -- 10 Kanal Sensor Array --
ADC_COLS = [
    "adc_tgs822", "adc_mq135",  "adc_mq9",    "adc_tgs2611",
    "adc_tgs2620", "adc_tgs2600", "adc_tgs2602", "adc_mq8",
    "adc_tgs813",  "adc_tgs816"
]

VALID_LABELS = ["light", "medium", "dark"]

# -- Hyperparameter RF --
RF_N_ESTIMATORS = 10
RF_MAX_DEPTH    = 5
RF_RANDOM_STATE = 42

# -- Window Transisi (jumlah sampel yang dianalisis di tepi transisi) --
ONSET_WINDOW = 20   # Sampel pertama fase collecting (purging->collecting)
DECAY_WINDOW = 20   # Sampel pertama fase purging (collecting->purging)


# ===========================================================================
# 1. LOAD DATA
# ===========================================================================
def load_raw_data():
    """Muat semua CSV mentah dari data/."""
    csv_files = glob.glob(os.path.join(DATA_DIR, "*.csv"))
    SKIP = ["dataset_fitur", "dataset_interactive", "anomal"]
    csv_files = [f for f in csv_files if not any(p in os.path.basename(f).lower() for p in SKIP)]

    if not csv_files:
        print(f"ERROR: Tidak ada CSV mentah di {DATA_DIR}")
        sys.exit(1)

    print(f"Ditemukan {len(csv_files)} file CSV:")
    dfs = []
    for f in csv_files:
        try:
            df = pd.read_csv(f)
            if "source_file" not in df.columns:
                df["source_file"] = os.path.basename(f)
            lc = df["label"].value_counts().to_dict() if "label" in df.columns else {}
            print(f"  OK {os.path.basename(f):45s} | {len(df):5d} baris | {lc}")
            dfs.append(df)
        except Exception as e:
            print(f"  FAIL {os.path.basename(f)}: {e}")

    df_all = pd.concat(dfs, ignore_index=True)
    print(f"\nTotal: {len(df_all)} baris dari {len(dfs)} file")
    return df_all


# ===========================================================================
# 2. FITUR STATISTIK FASE COLLECTING (48 Fitur)
# ===========================================================================
def extract_collecting_features(df_col, row):
    """10 mean + 10 max + 10 sum + 9 ratio MQ135 + 9 ratio TGS822 = 48."""
    for col in ADC_COLS:
        vals = df_col[col].values
        row[f"mean_{col}"] = float(np.mean(vals))
        row[f"max_{col}"]  = float(np.max(vals))
        row[f"sum_{col}"]  = float(np.sum(vals))

    mq135_max = row["max_adc_mq135"] if row["max_adc_mq135"] > 0 else 1.0
    for col in ADC_COLS:
        if col != "adc_mq135":
            row[f"ratio_to_mq135_{col}"] = row[f"max_{col}"] / mq135_max

    tgs822_max = row["max_adc_tgs822"] if row["max_adc_tgs822"] > 0 else 1.0
    for col in ADC_COLS:
        if col != "adc_tgs822":
            row[f"ratio_to_tgs822_{col}"] = row[f"max_{col}"] / tgs822_max

    return row


# ===========================================================================
# 3. FITUR TRANSISI -- ONSET & DECAY (60 Fitur Baru)
# ===========================================================================
def transition_stats(vals, window, prefix):
    """
    Hitung 3 fitur dari N sampel pertama suatu transisi fase:
    - slope     : kemiringan regresi linear (positif=naik, negatif=turun)
    - delta     : nilai[-1] - nilai[0]  (besar perubahan total dalam window)
    - rise_drop : nilai[4] - nilai[0]   (perubahan cepat 5 sampel pertama)
    """
    n = len(vals)
    w = min(window, n)

    if w < 2:
        return {f"{prefix}_slope": 0.0, f"{prefix}_delta": 0.0, f"{prefix}_rise_drop": 0.0}

    seg = vals[:w].astype(float)
    t   = np.arange(w, dtype=float)

    slope     = float(sp_stats.linregress(t, seg)[0])
    delta     = float(seg[-1] - seg[0])
    fast_n    = min(5, w)
    rise_drop = float(seg[fast_n - 1] - seg[0]) if fast_n > 1 else 0.0

    return {f"{prefix}_slope": slope, f"{prefix}_delta": delta, f"{prefix}_rise_drop": rise_drop}


def extract_transition_features(df_cycle, row, onset_window=ONSET_WINDOW, decay_window=DECAY_WINDOW):
    """
    [A] ONSET (purging->collecting):
        Sampel pertama fase collecting per siklus.
        Menunjukkan seberapa cepat sensor merespons aroma kopi.

    [B] DECAY (collecting->purging):
        Sampel pertama fase purging per siklus.
        Menunjukkan kecepatan recovery sensor saat aroma dihentikan.

    Per sensor (10): 3 onset + 3 decay = 6 fitur
    Total 10 sensor x 6 = 60 fitur transisi
    """
    df_col = df_cycle[df_cycle["phase"] == "collecting"].copy()
    df_pur = df_cycle[df_cycle["phase"] == "purging"].copy()

    if "sample_idx" in df_col.columns:
        df_col = df_col.sort_values("sample_idx")
        df_pur = df_pur.sort_values("sample_idx")

    for col in ADC_COLS:
        # [A] ONSET: N sampel pertama fase collecting
        if len(df_col) >= 2:
            row.update(transition_stats(df_col[col].values, onset_window, f"onset_{col}"))
        else:
            row.update({f"onset_{col}_slope": 0.0, f"onset_{col}_delta": 0.0, f"onset_{col}_rise_drop": 0.0})

        # [B] DECAY: N sampel pertama fase purging
        if len(df_pur) >= 2:
            row.update(transition_stats(df_pur[col].values, decay_window, f"decay_{col}"))
        else:
            row.update({f"decay_{col}_slope": 0.0, f"decay_{col}_delta": 0.0, f"decay_{col}_rise_drop": 0.0})

    return row


# ===========================================================================
# 4. EKSTRAKSI GABUNGAN (1 baris = 1 siklus = 108 fitur)
# ===========================================================================
def extract_all_features(df_all, onset_window=ONSET_WINDOW, decay_window=DECAY_WINDOW):
    """Gabungkan 48 fitur statistik + 60 fitur transisi = 108 fitur per siklus."""
    for col in ADC_COLS:
        if col not in df_all.columns:
            df_all[col] = 0
        df_all[col] = pd.to_numeric(df_all[col], errors="coerce").fillna(0)

    if "cycle" not in df_all.columns:
        df_all["cycle"] = 1

    df_all = df_all[df_all["label"].str.lower().isin(VALID_LABELS)].copy()
    df_all["label"] = df_all["label"].str.lower()

    group_keys = [k for k in ["source_file", "label", "cycle"] if k in df_all.columns]

    rows = []
    for keys, group in df_all.groupby(group_keys):
        kd = dict(zip(group_keys, keys if isinstance(keys, tuple) else (keys,)))
        row = {
            "source_file": kd.get("source_file", "?"),
            "label":       kd.get("label", "?"),
            "cycle":       kd.get("cycle", 1),
            "n_collecting": int((group["phase"] == "collecting").sum()),
            "n_purging":    int((group["phase"] == "purging").sum()),
        }

        df_col = group[group["phase"] == "collecting"]
        if df_col.empty:
            continue

        # Fitur statistik collecting (48)
        row = extract_collecting_features(df_col, row)

        # Fitur transisi (60)
        row = extract_transition_features(group, row, onset_window, decay_window)

        rows.append(row)

    df_feat = pd.DataFrame(rows)
    print(f"\nEkstraksi selesai: {len(df_feat)} siklus")
    print(f"Distribusi kelas:\n{df_feat['label'].value_counts().to_string()}")
    return df_feat


# ===========================================================================
# 5. SUSUN DAFTAR NAMA FITUR
# ===========================================================================
def build_feature_columns(df_feat):
    """Susun 108 kolom fitur dengan urutan terstruktur."""
    # 48 Statistik Collecting
    collecting = (
        [f"mean_{c}"  for c in ADC_COLS] +
        [f"max_{c}"   for c in ADC_COLS] +
        [f"sum_{c}"   for c in ADC_COLS] +
        [f"ratio_to_mq135_{c}"  for c in ADC_COLS if c != "adc_mq135"] +
        [f"ratio_to_tgs822_{c}" for c in ADC_COLS if c != "adc_tgs822"]
    )
    # 30 Onset (purging->collecting)
    onset = [f"onset_{col}_{s}" for col in ADC_COLS for s in ["slope", "delta", "rise_drop"]]
    # 30 Decay (collecting->purging)
    decay = [f"decay_{col}_{s}" for col in ADC_COLS for s in ["slope", "delta", "rise_drop"]]

    all_feats = collecting + onset + decay
    available = [c for c in all_feats if c in df_feat.columns]

    n_col  = len([c for c in collecting if c in available])
    n_ons  = len([c for c in onset if c in available])
    n_dec  = len([c for c in decay if c in available])
    print(f"\nTotal fitur: {len(available)}")
    print(f"  Statistik collecting : {n_col}")
    print(f"  Onset (purge->col)   : {n_ons}")
    print(f"  Decay (col->purge)   : {n_dec}")

    return available


# ===========================================================================
# 6. TRAINING & EVALUASI
# ===========================================================================
def train_model(df_feat):
    feature_cols = build_feature_columns(df_feat)
    X = df_feat[feature_cols].fillna(0).to_numpy(dtype=np.float32)
    y = df_feat["label"].astype(str).to_numpy()

    print(f"\nMelatih RF: {RF_N_ESTIMATORS} pohon, depth={RF_MAX_DEPTH}, {len(X)} sampel...")

    if len(df_feat) < 3:
        print("ERROR: Dataset terlalu kecil.")
        sys.exit(1)

    # Cross-Validation
    if len(df_feat) >= 10:
        n_splits = min(5, len(df_feat) // 2)
        cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=RF_RANDOM_STATE)
        cv_clf = RandomForestClassifier(n_estimators=RF_N_ESTIMATORS, max_depth=RF_MAX_DEPTH,
                                        random_state=RF_RANDOM_STATE, class_weight="balanced")
        scores = cross_val_score(cv_clf, X, y, cv=cv, scoring="accuracy")
        print(f"CV Accuracy ({n_splits}-fold): {scores.mean()*100:.2f}% +/- {scores.std()*100:.2f}%")

    # Train/Test Split
    if len(df_feat) >= 6:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, stratify=y, random_state=RF_RANDOM_STATE)
    else:
        X_train, X_test, y_train, y_test = X, X, y, y
        print("WARN: Dataset kecil -- training tanpa split.")

    # Fit
    clf = RandomForestClassifier(n_estimators=RF_N_ESTIMATORS, max_depth=RF_MAX_DEPTH,
                                  random_state=RF_RANDOM_STATE, class_weight="balanced")
    clf.fit(X_train, y_train)
    y_pred = clf.predict(X_test)
    acc = accuracy_score(y_test, y_pred)

    print(f"\nAkurasi Test Set: {acc*100:.2f}%")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, zero_division=0))

    # Top 15 Feature Importance
    imp = pd.Series(clf.feature_importances_, index=feature_cols).sort_values(ascending=False)
    print("\nTop 15 Feature Importance:")
    for feat, iv in imp.head(15).items():
        tag  = "[NEW]" if ("onset_" in feat or "decay_" in feat) else "     "
        bar  = "#" * int(iv * 50)
        print(f"  {tag} {feat:<40} {bar} {iv:.4f}")

    # Confusion matrix
    if HAS_PLOT:
        labels_order = sorted(set(y_test) | set(y_pred))
        cm = confusion_matrix(y_test, y_pred, labels=labels_order)
        fig, ax = plt.subplots(figsize=(6, 5))
        sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                    xticklabels=labels_order, yticklabels=labels_order, ax=ax)
        ax.set_title(f"Confusion Matrix -- Fitur Transisi\nAcc: {acc*100:.1f}% | {len(feature_cols)} fitur")
        ax.set_xlabel("Predicted")
        ax.set_ylabel("Actual")
        plt.tight_layout()
        plt.savefig(OUTPUT_PLOT, dpi=120)
        print(f"\nConfusion matrix: {OUTPUT_PLOT}")

    return clf, feature_cols


# ===========================================================================
# 7. SIMPAN MODEL & EXPORT C++ HEADER
# ===========================================================================
def save_and_export(clf, feature_cols):
    joblib.dump(clf, MODEL_PATH)
    print(f"\nModel Python: {MODEL_PATH}")

    sys.path.insert(0, SCRIPTS_DIR)
    try:
        from generate_model_atmega import export_model_atmega
        os.makedirs(INCLUDE_DIR, exist_ok=True)
        export_model_atmega(MODEL_PATH, OUTPUT_HEADER,
                            max_trees=RF_N_ESTIMATORS, max_depth=RF_MAX_DEPTH)
    except ImportError:
        print("WARN: generate_model_atmega.py tidak ditemukan -- export C++ dilewati.")
    except Exception as e:
        print(f"WARN: Gagal export C++: {e}")

    import json
    feat_json = os.path.join(DATA_DIR, "feature_list_transisi.json")
    with open(feat_json, "w") as f:
        json.dump({"total_features": len(feature_cols), "feature_names": feature_cols,
                   "onset_window": ONSET_WINDOW, "decay_window": DECAY_WINDOW,
                   "rf_n_estimators": RF_N_ESTIMATORS, "rf_max_depth": RF_MAX_DEPTH}, f, indent=2)
    print(f"Feature list JSON: {feat_json}")


# ===========================================================================
# 8. VISUALISASI PROFIL TRANSISI (opsional)
# ===========================================================================
def plot_transition_profiles(df_all, sensor="adc_tgs822"):
    """Plot profil rata-rata onset & decay per kelas roasting untuk satu sensor."""
    if not HAS_PLOT:
        return

    df_all = df_all[df_all["label"].str.lower().isin(VALID_LABELS)].copy()
    df_all["label"] = df_all["label"].str.lower()
    if "cycle" not in df_all.columns:
        df_all["cycle"] = 1
    if "source_file" not in df_all.columns:
        df_all["source_file"] = "unknown"

    COLORS = {"light": "#F59E0B", "medium": "#10B981", "dark": "#3B82F6"}
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle(f"Profil Transisi -- {sensor.upper().replace('ADC_','')}", fontsize=13, fontweight="bold")

    for label, color in COLORS.items():
        grp_lbl = df_all[df_all["label"] == label]
        onset_segs, decay_segs = [], []

        for _, grp in grp_lbl.groupby(["source_file", "cycle"]):
            dc = grp[grp["phase"] == "collecting"].copy()
            dp = grp[grp["phase"] == "purging"].copy()
            if "sample_idx" in dc.columns:
                dc = dc.sort_values("sample_idx")
                dp = dp.sort_values("sample_idx")
            if sensor in dc.columns and len(dc) >= ONSET_WINDOW:
                onset_segs.append(dc[sensor].values[:ONSET_WINDOW])
            if sensor in dp.columns and len(dp) >= DECAY_WINDOW:
                decay_segs.append(dp[sensor].values[:DECAY_WINDOW])

        if onset_segs:
            mn = np.mean(np.vstack(onset_segs), axis=0)
            sd = np.std(np.vstack(onset_segs), axis=0)
            x  = np.arange(len(mn))
            axes[0].plot(x, mn, color=color, label=label, linewidth=2.5)
            axes[0].fill_between(x, mn - sd, mn + sd, alpha=0.18, color=color)

        if decay_segs:
            mn = np.mean(np.vstack(decay_segs), axis=0)
            sd = np.std(np.vstack(decay_segs), axis=0)
            x  = np.arange(len(mn))
            axes[1].plot(x, mn, color=color, label=label, linewidth=2.5)
            axes[1].fill_between(x, mn - sd, mn + sd, alpha=0.18, color=color)

    for ax, title in zip(axes, ["ONSET: Purging -> Collecting", "DECAY: Collecting -> Purging"]):
        ax.set_title(title, fontsize=11)
        ax.set_xlabel("Sampel ke-N dari awal transisi")
        ax.set_ylabel("ADC Value")
        ax.legend(title="Roasting Level")
        ax.grid(alpha=0.3)

    plt.tight_layout()
    out = os.path.join(DATA_DIR, f"transition_profile_{sensor}.png")
    plt.savefig(out, dpi=120)
    print(f"Plot profil transisi: {out}")


# ===========================================================================
# MAIN
# ===========================================================================
def main():
    print("""
+--------------------------------------------------------------+
|  E-NOSE Kopi -- Training RF + Fitur Transisi Sinyal         |
|  48 Fitur Statistik  +  60 Fitur Transisi  =  108 Total    |
+--------------------------------------------------------------+
""")
    print(f"Konfigurasi Jendela Transisi:")
    print(f"  ONSET window (purging->collecting) : {ONSET_WINDOW} sampel pertama fase collecting")
    print(f"  DECAY window (collecting->purging) : {DECAY_WINDOW} sampel pertama fase purging")

    df_all = load_raw_data()
    df_feat = extract_all_features(df_all, ONSET_WINDOW, DECAY_WINDOW)

    os.makedirs(DATA_DIR, exist_ok=True)
    df_feat.to_csv(OUTPUT_CSV, index=False)
    print(f"\nDataset fitur: {OUTPUT_CSV}  [{df_feat.shape[0]} baris x {df_feat.shape[1]} kolom]")

    clf, feature_cols = train_model(df_feat)
    save_and_export(clf, feature_cols)

    print("\nMembuat plot profil transisi...")
    plot_transition_profiles(df_all, sensor="adc_tgs822")
    plot_transition_profiles(df_all, sensor="adc_tgs2602")

    print("""
+--------------------------------------------------------------+
  SELESAI! Catatan Penting:
  - Bandingkan akurasi dengan model 48 fitur (4_train_rf.py)
  - Fitur transisi TIDAK bisa dijalankan real-time di firmware
    (butuh data purging sebelumnya di memori)
  - Gunakan untuk validasi lab / analisis offline
  - Jika akurasi lebih baik -> include/model_rf_atmega.h diupdate
+--------------------------------------------------------------+
""")

if __name__ == "__main__":
    main()
