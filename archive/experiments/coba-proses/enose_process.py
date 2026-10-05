"""
enose_process.py
═══════════════════════════════════════════════════════════════════════════════
Script Pemrosesan Data E-NOSE Kopi — dari RAW CSV → Feature Extraction →
Random Forest Classification (Light / Medium / Dark).

Input  : Seluruh file CSV di folder data/ (output dari 3_collect_data.py)
Output : Model klasifikasi, confusion matrix, classification report, PCA plot

Kolom CSV yang diharapkan:
  timestamp, sample_id, roast_level, origin, batch_id, run_id, phase,
  sample_idx, adc_tgs822, adc_mq135, adc_mq3 (atau adc_mq9), adc_tgs2611,
  adc_tgs2620, adc_tgs2600, adc_tgs2602, adc_mq8, adc_tgs813, adc_tgs816,
  temperature, humidity
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import re
import glob
import warnings

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend — save to file tanpa buka window
import matplotlib.pyplot as plt

from scipy.stats import skew, kurtosis
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.decomposition import PCA
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    ConfusionMatrixDisplay,
    accuracy_score,
)
import joblib

warnings.filterwarnings("ignore")

# ============================================================
# 1. KONFIGURASI
# ============================================================

# Path ke folder data (sesuaikan jika berbeda)
DATA_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data")
)

# Nama kolom sensor ADC di CSV
SENSOR_COLS = [
    "adc_tgs822",
    "adc_mq135",
    "adc_mq3",    # beberapa file lama mungkin "adc_mq9"
    "adc_tgs2611",
    "adc_tgs2620",
    "adc_tgs2600",
    "adc_tgs2602",
    "adc_mq8",
    "adc_tgs813",
    "adc_tgs816",
]

# Label sensor untuk display
SENSOR_NAMES = [
    "TGS822", "MQ135", "MQ3", "TGS2611", "TGS2620",
    "TGS2600", "TGS2602", "MQ8", "TGS813", "TGS816",
]

# File yang harus di-skip (bukan data eksperimen valid)
SKIP_PATTERNS = [
    "COBA_", "dark_2026", "dataset_fitur", "coffee_roast_model",
    "_20260",  # file duplikat dengan timestamp
]

RANDOM_STATE = 42

print(f"Data directory: {DATA_DIR}")
print(f"Jumlah sensor : {len(SENSOR_COLS)}")

# ============================================================
# 2. LOAD DAN GABUNGKAN SELURUH CSV
# ============================================================

csv_files = sorted(glob.glob(os.path.join(DATA_DIR, "*.csv")))

# Filter file yang valid
valid_files = []
for f in csv_files:
    basename = os.path.basename(f)
    if any(pat in basename for pat in SKIP_PATTERNS):
        continue
    # Harus mengikuti pola <SAMPLE>_<BATCH>.csv
    if re.match(r"^[LMD]-[A-Z]{3}_B\d+\.csv$", basename):
        valid_files.append(f)

print(f"\nJumlah file CSV valid: {len(valid_files)}")
for f in valid_files[:10]:
    print(f"  {os.path.basename(f)}")
if len(valid_files) > 10:
    print(f"  ... dan {len(valid_files) - 10} file lainnya")

# Baca dan gabungkan semua CSV
all_dfs = []
for f in valid_files:
    try:
        df = pd.read_csv(f)
        
        # Handle kolom lama: rename adc_mq9 -> adc_mq3
        if "adc_mq9" in df.columns and "adc_mq3" not in df.columns:
            df = df.rename(columns={"adc_mq9": "adc_mq3"})
        
        # Pastikan kolom sensor ada
        missing = [c for c in SENSOR_COLS if c not in df.columns]
        if missing:
            print(f"  WARNING SKIP {os.path.basename(f)}: kolom missing {missing}")
            continue
            
        all_dfs.append(df)
    except Exception as e:
        print(f"  ERROR baca {os.path.basename(f)}: {e}")

raw_df = pd.concat(all_dfs, ignore_index=True)
print(f"\nTotal baris raw data: {len(raw_df):,}")
print(f"Kolom: {list(raw_df.columns)}")
print(f"\nRoast levels: {raw_df['roast_level'].unique()}")
print(f"Sample IDs  : {sorted(raw_df['sample_id'].unique())}")

# ============================================================
# 3. FILTER HANYA FASE COLLECTING
# ============================================================

collecting_df = raw_df[raw_df["phase"] == "collecting"].copy()
print(f"\nBaris collecting : {len(collecting_df):,}")
print(f"Baris purging    : {len(raw_df[raw_df['phase'] == 'purging']):,}")

# ============================================================
# 4. FEATURE EXTRACTION PER RUN
# ============================================================

def extract_features(group, key):
    """
    Ekstraksi fitur statistik dari satu run (fase collecting saja).
    key = (sample_id, batch_id, run_id) dari groupby keys.
    """
    features = {}
    
    # Metadata dari groupby keys
    features["sample_id"]   = key[0]
    features["batch_id"]    = key[1]
    features["run_id"]      = key[2]
    
    # Ambil metadata tambahan dari data jika tersedia
    if "roast_level" in group.columns:
        features["roast_level"] = group["roast_level"].iloc[0]
    if "origin" in group.columns:
        features["origin"] = group["origin"].iloc[0]
    features["n_samples"] = len(group)
    
    for col, name in zip(SENSOR_COLS, SENSOR_NAMES):
        vals = group[col].dropna().values.astype(float)
        if len(vals) == 0:
            continue
        
        features[f"{name}_mean"]     = np.mean(vals)
        features[f"{name}_std"]      = np.std(vals)
        features[f"{name}_min"]      = np.min(vals)
        features[f"{name}_max"]      = np.max(vals)
        features[f"{name}_range"]    = np.max(vals) - np.min(vals)
        features[f"{name}_median"]   = np.median(vals)
        features[f"{name}_skew"]     = skew(vals) if len(vals) > 2 else 0
        features[f"{name}_kurtosis"] = kurtosis(vals) if len(vals) > 2 else 0
        features[f"{name}_auc"]      = np.trapezoid(vals)  # area under curve
        features[f"{name}_delta"]    = vals[-1] - vals[0]  # final - initial
        
        # Slope (linear regression sederhana)
        if len(vals) > 1:
            x = np.arange(len(vals))
            coeffs = np.polyfit(x, vals, 1)
            features[f"{name}_slope"] = coeffs[0]
        else:
            features[f"{name}_slope"] = 0.0
    
    return pd.Series(features)


print("\nEkstraksi fitur per run (hanya fase collecting)...")

# Gunakan loop manual untuk menghindari masalah groupby keys
groups = collecting_df.groupby(["sample_id", "batch_id", "run_id"])
feature_rows = []
for key, group in groups:
    row = extract_features(group, key)
    feature_rows.append(row)

feature_df = pd.DataFrame(feature_rows)

print(f"Jumlah run (samples): {len(feature_df)}")
print(f"Jumlah fitur        : {len([c for c in feature_df.columns if c not in ['sample_id','roast_level','origin','batch_id','run_id','n_samples']])}")

# Distribusi per roast level
print(f"\nDistribusi per roast level:")
print(feature_df["roast_level"].value_counts())

# ============================================================
# 5. SIMPAN DATASET FITUR
# ============================================================

feature_out = os.path.join(DATA_DIR, "dataset_fitur_ai.csv")
feature_df.to_csv(feature_out, index=False)
print(f"\nDataset fitur disimpan ke: {feature_out}")

# ============================================================
# 6. PERSIAPAN DATA UNTUK MACHINE LEARNING
# ============================================================

# Kolom metadata (JANGAN dimasukkan sebagai fitur)
META_COLS = ["sample_id", "roast_level", "origin", "batch_id", "run_id", "n_samples"]

# Kolom fitur numerik
feature_cols = [c for c in feature_df.columns if c not in META_COLS]

X = feature_df[feature_cols].copy()
y = feature_df["roast_level"].copy()

# Handle missing/infinite values
X = X.replace([np.inf, -np.inf], np.nan)
X = X.fillna(X.median())

# Encode target
le = LabelEncoder()
y_encoded = le.fit_transform(y)

print(f"\nShape X: {X.shape}")
print(f"Classes : {le.classes_}")
print(f"Distribusi y: {dict(zip(le.classes_, np.bincount(y_encoded)))}")

# ============================================================
# 7. TRAIN-TEST SPLIT
# ============================================================

X_train, X_test, y_train, y_test = train_test_split(
    X, y_encoded,
    test_size=0.2,
    random_state=RANDOM_STATE,
    stratify=y_encoded,
)

print(f"\nTrain: {len(X_train)} samples")
print(f"Test : {len(X_test)} samples")

# Standardisasi
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# ============================================================
# 8. TRAINING RANDOM FOREST
# ============================================================

print("\n" + "="*60)
print("TRAINING RANDOM FOREST CLASSIFIER")
print("="*60)

rf = RandomForestClassifier(
    n_estimators=200,
    max_depth=None,
    min_samples_split=5,
    min_samples_leaf=2,
    random_state=RANDOM_STATE,
    n_jobs=-1,
)

rf.fit(X_train_scaled, y_train)

# ============================================================
# 9. EVALUASI MODEL
# ============================================================

y_pred = rf.predict(X_test_scaled)

print(f"\n{'='*60}")
print(f"HASIL EVALUASI")
print(f"{'='*60}")
print(f"Accuracy: {accuracy_score(y_test, y_pred):.4f}")
print(f"\nClassification Report:")
print(classification_report(y_test, y_pred, target_names=le.classes_))

# Cross-validation
print(f"\nCross-Validation (5-fold):")
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
cv_scores = cross_val_score(rf, scaler.transform(X), y_encoded, cv=cv, scoring="accuracy")
print(f"  Scores : {cv_scores}")
print(f"  Mean   : {cv_scores.mean():.4f} +/- {cv_scores.std():.4f}")

# ============================================================
# 10. VISUALISASI
# ============================================================

output_dir = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(output_dir, exist_ok=True)

# --- Confusion Matrix ---
fig, ax = plt.subplots(figsize=(8, 6))
cm = confusion_matrix(y_test, y_pred)
disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=le.classes_)
disp.plot(ax=ax, cmap="Blues")
ax.set_title("Confusion Matrix - Random Forest E-NOSE Kopi", fontsize=14)
plt.tight_layout()
plt.savefig(os.path.join(output_dir, "confusion_matrix.png"), dpi=150)
plt.show()

# --- Feature Importance (Top 20) ---
importances = rf.feature_importances_
feat_imp = pd.Series(importances, index=feature_cols).sort_values(ascending=False)

fig, ax = plt.subplots(figsize=(10, 8))
feat_imp.head(20).plot(kind="barh", ax=ax, color="steelblue")
ax.set_xlabel("Importance")
ax.set_title("Top 20 Feature Importance - Random Forest", fontsize=14)
ax.invert_yaxis()
plt.tight_layout()
plt.savefig(os.path.join(output_dir, "feature_importance.png"), dpi=150)
plt.show()

# --- PCA 2D ---
pca = PCA(n_components=2)
X_pca = pca.fit_transform(scaler.transform(X))

fig, ax = plt.subplots(figsize=(10, 8))
colors = {"light": "#FFD700", "medium": "#CD853F", "dark": "#4B3621"}
for label in le.classes_:
    mask = y == label
    ax.scatter(
        X_pca[mask, 0], X_pca[mask, 1],
        label=label.capitalize(),
        color=colors.get(label, "gray"),
        alpha=0.7, edgecolors="k", linewidth=0.5, s=60,
    )

ax.set_xlabel(f"PC1 ({pca.explained_variance_ratio_[0]*100:.1f}%)")
ax.set_ylabel(f"PC2 ({pca.explained_variance_ratio_[1]*100:.1f}%)")
ax.set_title("PCA - E-NOSE Coffee Roast Classification", fontsize=14)
ax.legend()
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(os.path.join(output_dir, "pca_plot.png"), dpi=150)
plt.show()

# ============================================================
# 11. SIMPAN MODEL
# ============================================================

model_path = os.path.join(DATA_DIR, "coffee_roast_model.pkl")
joblib.dump({
    "model": rf,
    "scaler": scaler,
    "label_encoder": le,
    "feature_cols": feature_cols,
    "sensor_cols": SENSOR_COLS,
}, model_path)

print(f"\nModel disimpan ke: {model_path}")
print(f"{'='*60}")
print("PROSES SELESAI")
print(f"{'='*60}")
