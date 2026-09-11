"""
12_eda_decision_boundary.py
═══════════════════════════════════════════════════════════════════════════════
Exploratory Data Analysis + Decision Boundary Visualisasi
  - PCA 2D Scatter (roast levels)
  - Random Forest Decision Boundary (2D PCA)
  - Feature Importance (Top 20)
  - Correlation Heatmap
  - Boxplot Distribusi per Sensor per Roast
  - Pairplot Top Features

Output: plots/eda/*.png
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import sys
import glob
import re
import argparse
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import ListedColormap, LinearSegmentedColormap
import seaborn as sns

from sklearn.ensemble import RandomForestClassifier
from sklearn.decomposition import PCA
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.metrics import confusion_matrix, classification_report
from scipy import stats as sp_stats

# ─── Path Konfigurasi ────────────────────────────────────────────────────────
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR    = os.path.normpath(os.path.join(SCRIPTS_DIR, '..'))
DATA_DIR    = os.path.join(BASE_DIR, 'data')
PLOTS_DIR   = os.path.join(BASE_DIR, 'plots', 'eda')
os.makedirs(PLOTS_DIR, exist_ok=True)

VALID_LABELS = ['light', 'medium', 'dark']

ADC_COLS = [
    'adc_tgs822', 'adc_mq135', 'adc_mq3', 'adc_tgs2611',
    'adc_tgs2620', 'adc_tgs2600', 'adc_tgs2602', 'adc_mq8',
    'adc_tgs813', 'adc_tgs816'
]

# ─── Warna Premium ───────────────────────────────────────────────────────────
ROAST_COLORS = {
    'light':  '#F59E0B',
    'medium': '#10B981',
    'dark':   '#6366F1'
}
ROAST_PALETTE = [ROAST_COLORS[r] for r in VALID_LABELS]

RF_N_ESTIMATORS = 12
RF_MAX_DEPTH = 5
RF_RANDOM_STATE = 42

ONSET_WINDOW = 20
DECAY_WINDOW = 20


# ═════════════════════════════════════════════════════════════════════════════
#  LOAD & EXTRACT
# ═════════════════════════════════════════════════════════════════════════════

def load_raw_data(batch_filter=None):
    csv_files = glob.glob(os.path.join(DATA_DIR, '*.csv'))
    SKIP = ['dataset_fitur', 'dataset_interactive', 'anomal', 'dataset_fitur_ai',
            'dataset_fitur_transisi', 'dataset_interactive']
    csv_files = [f for f in csv_files if not any(p in os.path.basename(f).lower() for p in SKIP)]

    if not csv_files:
        print(f"[ERROR] Tidak ada file CSV di: {DATA_DIR}")
        sys.exit(1)

    # Filter batch pembanding jika ditentukan
    if batch_filter and batch_filter != ["ALL"] and batch_filter != "ALL":
        target_batches = [b.upper() for b in (batch_filter if isinstance(batch_filter, list) else [batch_filter])]
        filtered = []
        for f in csv_files:
            fname = os.path.basename(f)
            m = re.search(r'_(B\d+)', fname, re.IGNORECASE)
            b_code = m.group(1).upper() if m else 'LEGACY'
            if b_code in target_batches or (('LEGACY' in target_batches or 'Legacy' in target_batches) and not m):
                filtered.append(f)
        if filtered:
            csv_files = filtered
            print(f"[INFO] Filter batch aktif: {target_batches} -> {len(csv_files)} file CSV")
        else:
            print(f"[WARN] Tidak ada file cocok untuk filter {target_batches}, memuat seluruh file.")

    dfs = []
    for f in csv_files:
        try:
            df = pd.read_csv(f)
            fname = os.path.basename(f)
            if 'source_file' not in df.columns:
                df['source_file'] = fname

            # Standarisasi Label Roasting
            if 'label' not in df.columns and 'roast_level' in df.columns:
                df['label'] = df['roast_level']
            if 'label' in df.columns:
                df['label'] = df['label'].astype(str).str.lower().str.strip()

            # Standarisasi Siklus / Run ID
            if 'cycle' not in df.columns:
                if 'run_id' in df.columns:
                    df['cycle'] = df['run_id']
                else:
                    df['cycle'] = 1

            # Standarisasi Batch ID
            if 'batch_id' not in df.columns or df['batch_id'].dropna().empty:
                m = re.search(r'_(B\d+)', fname, re.IGNORECASE)
                df['batch_id'] = m.group(1).upper() if m else 'LEGACY'
            else:
                df['batch_id'] = df['batch_id'].astype(str).str.strip().str.upper()

            dfs.append(df)
        except Exception as e:
            print(f"  [GAGAL] {os.path.basename(f)}: {e}")

    df_all = pd.concat(dfs, ignore_index=True)
    print(f"[INFO] Loaded {len(df_all)} baris dari {len(csv_files)} file CSV")
    return df_all


def extract_features(df_all):
    """Ekstraksi fitur optimized (89 fitur) per siklus."""
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

        for col in ADC_COLS:
            vals = df_col[col].values
            row[f'mean_{col}'] = float(np.mean(vals))
            row[f'max_{col}']  = float(np.max(vals))
            row[f'std_{col}']  = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0

        for col in ADC_COLS:
            pb = df_pur[col].values if len(df_pur) > 0 else np.zeros(1)
            baseline = float(np.mean(pb[-10:])) if len(pb) >= 10 else float(np.mean(pb))
            peak = row[f'max_{col}']
            row[f'peak_to_base_{col}'] = (peak - baseline) / max(abs(baseline), 1.0)

        mq135_max = row['max_adc_mq135'] if row['max_adc_mq135'] > 0 else 1.0
        for col in ADC_COLS:
            if col != 'adc_mq135':
                row[f'ratio_to_mq135_{col}'] = row[f'max_{col}'] / mq135_max

        w_on = min(ONSET_WINDOW, len(df_col))
        t_on = np.arange(w_on, dtype=float)
        for col in ADC_COLS:
            seg = df_col[col].values[:w_on].astype(float)
            row[f'onset_{col}_slope'] = float(sp_stats.linregress(t_on, seg)[0]) if w_on > 1 else 0.0
            fast_n = min(5, w_on)
            row[f'onset_{col}_rise_drop'] = float(seg[fast_n - 1] - seg[0]) if fast_n > 1 else 0.0

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

        rows.append(row)

    df_feat = pd.DataFrame(rows)
    print(f"[INFO] Fitur diekstrak: {len(df_feat)} sampel")
    print(f"  Distribusi: {dict(df_feat['label'].value_counts())}")
    return df_feat


def get_feature_cols(df_feat):
    """Dapatkan kolom fitur numerik saja."""
    meta_cols = ['source_file', 'label', 'cycle', 'n_samples']
    return [c for c in df_feat.columns if c not in meta_cols]


# ═════════════════════════════════════════════════════════════════════════════
#  PLOT 1: PCA 2D SCATTER
# ═════════════════════════════════════════════════════════════════════════════

def plot_pca_scatter(X_scaled, y, pca, title_suffix=""):
    """Scatter plot PCA 2D dengan styling premium."""
    X_pca = pca.transform(X_scaled)

    fig, ax = plt.subplots(figsize=(10, 8), facecolor='#0F172A')
    ax.set_facecolor('#1E293B')

    for label in VALID_LABELS:
        mask = (y == label)
        ax.scatter(
            X_pca[mask, 0], X_pca[mask, 1],
            c=ROAST_COLORS[label], label=label.capitalize(),
            s=90, alpha=0.82, edgecolors='white', linewidths=0.6, zorder=5
        )

    ax.set_xlabel(f'PC1 ({pca.explained_variance_ratio_[0]*100:.1f}%)',
                  color='#F8FAFC', fontsize=12, fontweight='bold')
    ax.set_ylabel(f'PC2 ({pca.explained_variance_ratio_[1]*100:.1f}%)',
                  color='#F8FAFC', fontsize=12, fontweight='bold')
    ax.set_title(f'PCA 2D — Distribusi Kelas Roasting Kopi {title_suffix}',
                 color='#F59E0B', fontsize=14, fontweight='bold', pad=15)
    ax.tick_params(colors='#94A3B8', labelsize=9)
    for spine in ax.spines.values():
        spine.set_color('#334155')
    ax.grid(True, linestyle='--', alpha=0.2, color='#64748B')

    legend = ax.legend(loc='upper right', fontsize=11, facecolor='#1E293B',
                       edgecolor='#334155', labelcolor='#F8FAFC')
    legend.get_frame().set_alpha(0.9)

    var_total = sum(pca.explained_variance_ratio_[:2]) * 100
    ax.text(0.02, 0.02, f'Total Explained Variance: {var_total:.1f}%',
            transform=ax.transAxes, fontsize=9, color='#94A3B8',
            fontstyle='italic')

    plt.tight_layout()
    out = os.path.join(PLOTS_DIR, 'pca_2d_scatter.png')
    plt.savefig(out, dpi=180, bbox_inches='tight', facecolor='#0F172A')
    plt.close()
    print(f"  [OK] PCA 2D Scatter -> {out}")
    return X_pca


# ═════════════════════════════════════════════════════════════════════════════
#  PLOT 2: DECISION BOUNDARY (Random Forest + PCA)
# ═════════════════════════════════════════════════════════════════════════════

def plot_decision_boundary(X_scaled, y, pca, title_suffix=""):
    """Decision boundary Random Forest di ruang PCA 2D."""
    X_pca = pca.transform(X_scaled)

    le = LabelEncoder()
    y_enc = le.fit_transform(y)

    clf_2d = RandomForestClassifier(
        n_estimators=RF_N_ESTIMATORS, max_depth=RF_MAX_DEPTH,
        random_state=RF_RANDOM_STATE, class_weight='balanced'
    )
    clf_2d.fit(X_pca, y_enc)

    # Meshgrid
    x_min, x_max = X_pca[:, 0].min() - 1.5, X_pca[:, 0].max() + 1.5
    y_min, y_max = X_pca[:, 1].min() - 1.5, X_pca[:, 1].max() + 1.5
    h = 0.08
    xx, yy = np.meshgrid(np.arange(x_min, x_max, h), np.arange(y_min, y_max, h))
    Z = clf_2d.predict(np.c_[xx.ravel(), yy.ravel()])
    Z = Z.reshape(xx.shape)

    # Custom cmap
    colors_bg = ['#FDE68A', '#A7F3D0', '#C7D2FE']  # light yellow, green, indigo
    cmap_bg = ListedColormap(colors_bg)
    colors_pt = [ROAST_COLORS[l] for l in le.classes_]

    fig, ax = plt.subplots(figsize=(11, 9), facecolor='#0F172A')
    ax.set_facecolor('#1E293B')

    ax.contourf(xx, yy, Z, alpha=0.25, cmap=cmap_bg, levels=[-0.5, 0.5, 1.5, 2.5])
    ax.contour(xx, yy, Z, colors='#64748B', linewidths=0.6, alpha=0.5)

    for idx, label in enumerate(le.classes_):
        mask = (y == label)
        ax.scatter(
            X_pca[mask, 0], X_pca[mask, 1],
            c=ROAST_COLORS[label], label=label.capitalize(),
            s=90, alpha=0.85, edgecolors='white', linewidths=0.7, zorder=5
        )

    ax.set_xlabel(f'PC1 ({pca.explained_variance_ratio_[0]*100:.1f}%)',
                  color='#F8FAFC', fontsize=12, fontweight='bold')
    ax.set_ylabel(f'PC2 ({pca.explained_variance_ratio_[1]*100:.1f}%)',
                  color='#F8FAFC', fontsize=12, fontweight='bold')
    ax.set_title(f'Random Forest Decision Boundary (PCA 2D Projection) {title_suffix}'.strip(),
                 color='#F59E0B', fontsize=14, fontweight='bold', pad=15)
    ax.tick_params(colors='#94A3B8', labelsize=9)
    for spine in ax.spines.values():
        spine.set_color('#334155')
    ax.grid(True, linestyle='--', alpha=0.15, color='#64748B')

    legend = ax.legend(loc='upper right', fontsize=11, facecolor='#1E293B',
                       edgecolor='#334155', labelcolor='#F8FAFC')
    legend.get_frame().set_alpha(0.9)

    # Accuracy in PCA space
    acc_2d = clf_2d.score(X_pca, y_enc) * 100
    ax.text(0.02, 0.02, f'2D PCA Model Accuracy: {acc_2d:.1f}%',
            transform=ax.transAxes, fontsize=10, color='#38BDF8',
            fontweight='bold')

    plt.tight_layout()
    out = os.path.join(PLOTS_DIR, 'decision_boundary_rf.png')
    plt.savefig(out, dpi=180, bbox_inches='tight', facecolor='#0F172A')
    plt.close()
    print(f"  [OK] Decision Boundary -> {out}")


# ═════════════════════════════════════════════════════════════════════════════
#  PLOT 3: FEATURE IMPORTANCE (Top 20)
# ═════════════════════════════════════════════════════════════════════════════

def plot_feature_importance(clf, feature_cols, title_suffix=""):
    """Feature importance bar chart premium."""
    importances = pd.Series(clf.feature_importances_, index=feature_cols)
    top20 = importances.sort_values(ascending=True).tail(20)

    fig, ax = plt.subplots(figsize=(10, 8), facecolor='#0F172A')
    ax.set_facecolor('#1E293B')

    colors = plt.cm.viridis(np.linspace(0.3, 0.95, len(top20)))
    bars = ax.barh(range(len(top20)), top20.values, color=colors,
                   edgecolor='#334155', height=0.7)

    ax.set_yticks(range(len(top20)))
    ax.set_yticklabels([n.replace('adc_', '').replace('_', ' ').title() for n in top20.index],
                       fontsize=9, color='#F8FAFC')
    ax.set_xlabel('Importance Score', color='#F8FAFC', fontsize=11, fontweight='bold')
    ax.set_title(f'Random Forest — Top 20 Feature Importance {title_suffix}'.strip(),
                 color='#F59E0B', fontsize=14, fontweight='bold', pad=15)
    ax.tick_params(colors='#94A3B8', labelsize=9)
    for spine in ax.spines.values():
        spine.set_color('#334155')
    ax.grid(axis='x', linestyle='--', alpha=0.2, color='#64748B')

    for bar, val in zip(bars, top20.values):
        ax.text(bar.get_width() + 0.002, bar.get_y() + bar.get_height()/2,
                f'{val:.4f}', va='center', fontsize=8, color='#38BDF8', fontweight='bold')

    plt.tight_layout()
    out = os.path.join(PLOTS_DIR, 'feature_importance_top20.png')
    plt.savefig(out, dpi=180, bbox_inches='tight', facecolor='#0F172A')
    plt.close()
    print(f"  [OK] Feature Importance -> {out}")


# ═════════════════════════════════════════════════════════════════════════════
#  PLOT 4: CORRELATION HEATMAP
# ═════════════════════════════════════════════════════════════════════════════

def plot_correlation_heatmap(df_feat, feature_cols):
    """Heatmap korelasi top fitur."""
    # Ambil top 25 fitur berdasarkan variance untuk readability
    variances = df_feat[feature_cols].var().sort_values(ascending=False)
    top_cols = variances.head(25).index.tolist()

    corr = df_feat[top_cols].corr()

    fig, ax = plt.subplots(figsize=(14, 12), facecolor='#0F172A')
    ax.set_facecolor('#1E293B')

    cmap = LinearSegmentedColormap.from_list('custom',
        ['#6366F1', '#1E293B', '#F59E0B'], N=256)

    short_labels = [c.replace('adc_', '').replace('_', ' ').title()[:18] for c in top_cols]
    mask = np.triu(np.ones_like(corr, dtype=bool), k=1)
    sns.heatmap(corr, mask=mask, annot=True, fmt='.2f', cmap=cmap,
                center=0, vmin=-1, vmax=1,
                xticklabels=short_labels, yticklabels=short_labels,
                ax=ax, linewidths=0.5, linecolor='#334155',
                annot_kws={'size': 7, 'color': '#F8FAFC'},
                cbar_kws={'label': 'Pearson r', 'shrink': 0.8})

    ax.set_title('Feature Correlation Heatmap (Top 25 by Variance)',
                 color='#F59E0B', fontsize=14, fontweight='bold', pad=15)
    ax.tick_params(colors='#94A3B8', labelsize=8, rotation=45)
    plt.setp(ax.get_xticklabels(), rotation=45, ha='right', color='#F8FAFC')
    plt.setp(ax.get_yticklabels(), rotation=0, color='#F8FAFC')

    plt.tight_layout()
    out = os.path.join(PLOTS_DIR, 'correlation_heatmap.png')
    plt.savefig(out, dpi=150, bbox_inches='tight', facecolor='#0F172A')
    plt.close()
    print(f"  [OK] Correlation Heatmap -> {out}")


# ═════════════════════════════════════════════════════════════════════════════
#  PLOT 5: BOXPLOT DISTRIBUSI PER SENSOR
# ═════════════════════════════════════════════════════════════════════════════

def plot_boxplot_per_sensor(df_feat):
    """Boxplot distribusi mean per sensor per roast level."""
    mean_cols = [f'mean_{c}' for c in ADC_COLS if f'mean_{c}' in df_feat.columns]
    if not mean_cols:
        return

    fig, axes = plt.subplots(2, 5, figsize=(22, 10), facecolor='#0F172A')
    fig.suptitle('Distribusi Mean ADC per Sensor — per Roast Level',
                 color='#F59E0B', fontsize=16, fontweight='bold', y=1.02)

    for idx, col in enumerate(mean_cols):
        ax = axes[idx // 5][idx % 5]
        ax.set_facecolor('#1E293B')

        data_per_roast = []
        for r in VALID_LABELS:
            vals = df_feat[df_feat['label'] == r][col].dropna().values
            data_per_roast.append(vals)

        bp = ax.boxplot(data_per_roast, patch_artist=True,
                        labels=[r.capitalize() for r in VALID_LABELS],
                        widths=0.5,
                        medianprops=dict(color='white', linewidth=2))

        for patch, color in zip(bp['boxes'], ROAST_PALETTE):
            patch.set_facecolor(color)
            patch.set_alpha(0.8)
            patch.set_edgecolor('white')
        for element in ['whiskers', 'caps']:
            for line in bp[element]:
                line.set_color('#94A3B8')
        for flier in bp['fliers']:
            flier.set(marker='o', markerfacecolor='#EF4444', markersize=4, alpha=0.6)

        sensor_name = col.replace('mean_adc_', '').upper()
        ax.set_title(sensor_name, color='#38BDF8', fontsize=11, fontweight='bold')
        ax.tick_params(colors='#94A3B8', labelsize=8)
        for spine in ax.spines.values():
            spine.set_color('#334155')
        ax.grid(axis='y', linestyle='--', alpha=0.2, color='#64748B')

    plt.tight_layout()
    out = os.path.join(PLOTS_DIR, 'boxplot_sensor_distribution.png')
    plt.savefig(out, dpi=150, bbox_inches='tight', facecolor='#0F172A')
    plt.close()
    print(f"  [OK] Boxplot Distribusi -> {out}")


# ═════════════════════════════════════════════════════════════════════════════
#  PLOT 6: PAIRPLOT TOP 4 FEATURES
# ═════════════════════════════════════════════════════════════════════════════

def plot_pairplot_top_features(df_feat, clf, feature_cols):
    """Pairplot 4 fitur teratas berdasarkan importance."""
    importances = pd.Series(clf.feature_importances_, index=feature_cols)
    top4 = importances.sort_values(ascending=False).head(4).index.tolist()

    plot_df = df_feat[top4 + ['label']].copy()
    plot_df.columns = [c.replace('adc_', '').replace('_', ' ').title()[:20] for c in top4] + ['label']

    sns.set_theme(style="darkgrid", rc={
        'figure.facecolor': '#0F172A',
        'axes.facecolor': '#1E293B',
        'text.color': '#F8FAFC',
        'axes.labelcolor': '#F8FAFC',
        'xtick.color': '#94A3B8',
        'ytick.color': '#94A3B8',
    })

    g = sns.pairplot(
        plot_df, hue='label', palette=ROAST_COLORS,
        diag_kind='kde', plot_kws={'alpha': 0.7, 's': 50, 'edgecolor': 'white', 'linewidth': 0.3},
        diag_kws={'linewidth': 2},
        height=2.8, aspect=1.1
    )
    g.figure.set_facecolor('#0F172A')
    g.figure.suptitle('Pairplot — Top 4 Features by Importance',
                      color='#F59E0B', fontsize=14, fontweight='bold', y=1.02)

    plt.tight_layout()
    out = os.path.join(PLOTS_DIR, 'pairplot_top4_features.png')
    plt.savefig(out, dpi=150, bbox_inches='tight', facecolor='#0F172A')
    plt.close()
    print(f"  [OK] Pairplot Top 4 -> {out}")

    # Reset seaborn theme
    sns.set_theme(style="whitegrid")


# ═════════════════════════════════════════════════════════════════════════════
#  PLOT 7: CONFUSION MATRIX
# ═════════════════════════════════════════════════════════════════════════════

def plot_confusion_matrix(clf, X, y, title_suffix=""):
    """Confusion matrix full-feature model."""
    y_pred = clf.predict(X)
    labels = sorted(set(y) | set(y_pred))
    cm = confusion_matrix(y, y_pred, labels=labels)

    fig, ax = plt.subplots(figsize=(8, 7), facecolor='#0F172A')
    ax.set_facecolor('#1E293B')

    cmap = LinearSegmentedColormap.from_list('cm_custom',
        ['#1E293B', '#3B82F6', '#F59E0B'], N=256)

    sns.heatmap(cm, annot=True, fmt='d', cmap=cmap,
                xticklabels=[l.capitalize() for l in labels],
                yticklabels=[l.capitalize() for l in labels],
                ax=ax, linewidths=1, linecolor='#334155',
                annot_kws={'size': 16, 'fontweight': 'bold', 'color': '#F8FAFC'},
                cbar_kws={'shrink': 0.8})

    acc = np.trace(cm) / np.sum(cm) * 100
    ax.set_title(f'Confusion Matrix — Random Forest ({acc:.1f}%) {title_suffix}'.strip(),
                 color='#F59E0B', fontsize=14, fontweight='bold', pad=15)
    ax.set_xlabel('Predicted', color='#F8FAFC', fontsize=12, fontweight='bold')
    ax.set_ylabel('Actual', color='#F8FAFC', fontsize=12, fontweight='bold')
    ax.tick_params(colors='#F8FAFC', labelsize=11)

    plt.tight_layout()
    out = os.path.join(PLOTS_DIR, 'confusion_matrix.png')
    plt.savefig(out, dpi=180, bbox_inches='tight', facecolor='#0F172A')
    plt.close()
    print(f"  [OK] Confusion Matrix -> {out}")


# ═════════════════════════════════════════════════════════════════════════════
#  PLOT 8: FOREST TREE VISUALIZATION (Single Tree)
# ═════════════════════════════════════════════════════════════════════════════

def plot_single_tree(clf, feature_cols):
    """Visualisasi salah satu decision tree dari Random Forest."""
    from sklearn.tree import plot_tree

    fig, ax = plt.subplots(figsize=(28, 14), facecolor='#FFFFFF')
    tree_idx = 0  # Ambil tree pertama
    plot_tree(
        clf.estimators_[tree_idx],
        feature_names=[c.replace('adc_', '').replace('_', ' ').title()[:20] for c in feature_cols],
        class_names=[l.capitalize() for l in clf.classes_],
        filled=True, rounded=True, fontsize=7,
        ax=ax, proportion=True,
        impurity=True
    )
    ax.set_title(f'Decision Tree #1 dari Random Forest ({clf.n_estimators} Trees)',
                 fontsize=16, fontweight='bold', pad=20)

    plt.tight_layout()
    out = os.path.join(PLOTS_DIR, 'forest_tree_visualization.png')
    plt.savefig(out, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  [OK] Forest Tree -> {out}")


# ═════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="EDA & Decision Boundary Visualization")
    parser.add_argument("--batches", type=str, default=None,
                        help="Filter batch pembanding, e.g. 'B10' atau 'B10,B04' atau 'ALL'")
    args = parser.parse_args()

    batch_filter = None
    batch_str = "Semua Batch"
    if args.batches and args.batches.strip().upper() != "ALL":
        batch_filter = [b.strip().upper() for b in args.batches.split(",") if b.strip()]
        batch_str = f"Batch {', '.join(batch_filter)}"

    print("=" * 60)
    print(f"  E-NOSE Kopi - EDA + Decision Boundary Visualization ({batch_str})")
    print("=" * 60)

    # 1. Load & Extract
    print(f"[STEP 1] Loading dan ekstraksi fitur ({batch_str})...")
    df_raw = load_raw_data(batch_filter=batch_filter)
    df_feat = extract_features(df_raw)

    feature_cols = get_feature_cols(df_feat)
    X = df_feat[feature_cols].fillna(0).to_numpy(dtype=np.float32)
    y = np.array(df_feat['label'].tolist(), dtype=str)

    # 2. Scale + PCA
    print("\n[STEP 2] PCA + Scaling...")
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    pca = PCA(n_components=2, random_state=RF_RANDOM_STATE)
    pca.fit(X_scaled)

    print(f"  Explained variance ratio: PC1={pca.explained_variance_ratio_[0]*100:.1f}%, PC2={pca.explained_variance_ratio_[1]*100:.1f}%")

    # 3. Train Full RF Model
    print(f"\n[STEP 3] Training Random Forest ({batch_str})...")
    clf = RandomForestClassifier(
        n_estimators=RF_N_ESTIMATORS, max_depth=RF_MAX_DEPTH,
        random_state=RF_RANDOM_STATE, class_weight='balanced'
    )
    clf.fit(X, y)

    unique, counts = np.unique(y, return_counts=True)
    for label, count in zip(unique, counts):
        print(f"  {label}: {count} sampel")

    if len(unique) >= 2 and min(counts) >= 2:
        n_splits = min(5, min(counts))
        cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=RF_RANDOM_STATE)
        cv_scores = cross_val_score(clf, X, y, cv=cv, scoring='accuracy')
        print(f"  CV Accuracy: {cv_scores.mean()*100:.1f}% ± {cv_scores.std()*100:.1f}%")

    # 4. Generate All Plots
    print("\n[STEP 4] Generating visualisasi...")
    print("=" * 60)

    suffix = f"({batch_str})"
    plot_pca_scatter(X_scaled, y, pca, title_suffix=suffix)
    plot_decision_boundary(X_scaled, y, pca, title_suffix=suffix)
    plot_feature_importance(clf, feature_cols, title_suffix=suffix)
    plot_correlation_heatmap(df_feat, feature_cols)
    plot_boxplot_per_sensor(df_feat)
    plot_pairplot_top_features(df_feat, clf, feature_cols)
    plot_confusion_matrix(clf, X, y, title_suffix=suffix)
    plot_single_tree(clf, feature_cols)

    print("=" * 60)
    print(f"\n[SELESAI] Semua visualisasi tersimpan di: {PLOTS_DIR}")
    print(f"   Total file: 8 gambar PNG untuk {batch_str}\n")


if __name__ == '__main__':
    main()
