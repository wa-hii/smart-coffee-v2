"""
9_analyze_features.py - Feature Dataset Analysis -- E-NOSE Kopi
==============================================================================
Input : processed/feature_dataset.csv
Output:
  plots/features/boxplots/        - Boxplot per sensor per fitur statistik
  plots/features/distributions/   - Distribusi KDE per roast level
  plots/features/correlations/    - Correlation heatmap
  plots/features/batch_comparison/ - Batch effect analysis
  processed/feature_analysis_report.md

TIDAK ADA Training ML / Random Forest.
RAW CSV TIDAK DIUBAH.
==============================================================================
"""

import os
import sys
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.colors import LinearSegmentedColormap
from scipy import stats as sp_stats
from scipy.stats import f_oneway, kruskal

warnings.filterwarnings('ignore')

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR      = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
PROCESSED_DIR = os.path.join(BASE_DIR, 'processed')
PLOTS_DIR     = os.path.join(BASE_DIR, 'plots', 'features')

FEATURE_CSV = os.path.join(PROCESSED_DIR, 'feature_dataset.csv')
REPORT_MD   = os.path.join(PROCESSED_DIR, 'feature_analysis_report.md')

PLOT_BOXPLOT = os.path.join(PLOTS_DIR, 'boxplots')
PLOT_DIST    = os.path.join(PLOTS_DIR, 'distributions')
PLOT_CORR    = os.path.join(PLOTS_DIR, 'correlations')
PLOT_BATCH   = os.path.join(PLOTS_DIR, 'batch_comparison')

# ── Sensor & Feature Config ────────────────────────────────────────────────────
SENSORS = ['TGS822','MQ135','MQ9','TGS2611','TGS2620',
           'TGS2600','TGS2602','MQ8','TGS813','TGS816']

STATS = ['mean','median','min','max','range','std','var',
         'initial','final','delta','slope','auc']

ROAST_LEVELS  = ['light','medium','dark']
ROAST_COLORS  = {'light':'#F4A261','medium':'#E76F51','dark':'#264653'}
ROAST_PALETTE = [ROAST_COLORS[r] for r in ROAST_LEVELS]

# Key stats to highlight in analysis
KEY_STATS = ['mean','std','delta','slope','range','auc']

FIGSIZE_WIDE = (18, 10)
DPI = 120


def make_dirs():
    for d in [PLOT_BOXPLOT, PLOT_DIST, PLOT_CORR, PLOT_BATCH]:
        os.makedirs(d, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Boxplots per Sensor
# ─────────────────────────────────────────────────────────────────────────────
def plot_boxplots(df, feat_cols, report):
    print("[1/4] Generating boxplots...")
    report.append("## 1. Boxplot Perbandingan Roast Level\n")
    report.append("Boxplot berikut menampilkan distribusi fitur statistik setiap sensor "
                  "terhadap roast level (Light / Medium / Dark).\n")

    groups = {r: df[df['roast_level']==r] for r in ROAST_LEVELS}

    for sensor in SENSORS:
        sensor_feat = [f'{sensor}_{s}' for s in STATS if f'{sensor}_{s}' in feat_cols]
        if not sensor_feat:
            continue

        # Use KEY_STATS for primary boxplot
        key_feats = [f'{sensor}_{s}' for s in KEY_STATS if f'{sensor}_{s}' in feat_cols]
        n_key = len(key_feats)

        fig, axes = plt.subplots(2, 3, figsize=FIGSIZE_WIDE)
        fig.suptitle(f'Sensor {sensor} -- Distribusi per Roast Level',
                     fontsize=14, fontweight='bold', y=1.01)

        for idx, feat in enumerate(key_feats[:6]):
            ax = axes[idx // 3][idx % 3]
            data_per_roast = [groups[r][feat].dropna().values for r in ROAST_LEVELS]
            bp = ax.boxplot(data_per_roast,
                            patch_artist=True,
                            labels=ROAST_LEVELS,
                            widths=0.5,
                            medianprops=dict(color='black', linewidth=2))
            for patch, color in zip(bp['boxes'], ROAST_PALETTE):
                patch.set_facecolor(color)
                patch.set_alpha(0.8)
            stat_name = feat.replace(f'{sensor}_','')
            ax.set_title(f'{stat_name.upper()}', fontsize=11, fontweight='bold')
            ax.set_ylabel('ADC Value')
            ax.tick_params(axis='x', labelsize=9)
            ax.grid(axis='y', linestyle='--', alpha=0.4)

        plt.tight_layout()
        out_path = os.path.join(PLOT_BOXPLOT, f'boxplot_{sensor}.png')
        plt.savefig(out_path, dpi=DPI, bbox_inches='tight')
        plt.close()

    report.append(f"File disimpan di: `plots/features/boxplots/boxplot_<sensor>.png`\n")
    print(f"  [OK] Boxplots saved -> {PLOT_BOXPLOT}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Distributions (KDE)
# ─────────────────────────────────────────────────────────────────────────────
def plot_distributions(df, feat_cols, report):
    print("[2/4] Generating distribution plots...")
    report.append("## 2. Distribusi Fitur per Roast Level (KDE)\n")
    report.append("Plot distribusi KDE menampilkan tumpang tindih antar roast level. "
                  "Separasi yang baik mengindikasikan fitur berpotensi diskriminatif.\n")

    for sensor in SENSORS:
        key_feats = [f'{sensor}_{s}' for s in KEY_STATS if f'{sensor}_{s}' in feat_cols]
        if not key_feats:
            continue

        fig, axes = plt.subplots(2, 3, figsize=FIGSIZE_WIDE)
        fig.suptitle(f'Sensor {sensor} -- Distribusi KDE per Roast Level',
                     fontsize=14, fontweight='bold')

        for idx, feat in enumerate(key_feats[:6]):
            ax = axes[idx // 3][idx % 3]
            for roast in ROAST_LEVELS:
                vals = df[df['roast_level']==roast][feat].dropna().values
                if len(vals) > 3:
                    kde_x = np.linspace(vals.min(), vals.max(), 200)
                    try:
                        kde = sp_stats.gaussian_kde(vals, bw_method='scott')
                        ax.fill_between(kde_x, kde(kde_x), alpha=0.35,
                                        color=ROAST_COLORS[roast], label=roast)
                        ax.plot(kde_x, kde(kde_x), color=ROAST_COLORS[roast],
                                linewidth=2)
                    except Exception:
                        ax.hist(vals, bins=15, alpha=0.5,
                                color=ROAST_COLORS[roast], label=roast, density=True)
            stat_name = feat.replace(f'{sensor}_','')
            ax.set_title(f'{stat_name.upper()}', fontsize=11, fontweight='bold')
            ax.set_xlabel('Value')
            ax.set_ylabel('Density')
            ax.legend(fontsize=8)
            ax.grid(linestyle='--', alpha=0.3)

        plt.tight_layout()
        out_path = os.path.join(PLOT_DIST, f'dist_{sensor}.png')
        plt.savefig(out_path, dpi=DPI, bbox_inches='tight')
        plt.close()

    report.append(f"File disimpan di: `plots/features/distributions/dist_<sensor>.png`\n")
    print(f"  [OK] Distributions saved -> {PLOT_DIST}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Correlation Matrix
# ─────────────────────────────────────────────────────────────────────────────
def plot_correlations(df, feat_cols, report):
    print("[3/4] Generating correlation heatmaps...")
    report.append("## 3. Correlation Matrix\n")
    report.append("Heatmap korelasi Pearson antar fitur. Korelasi tinggi (>0.95) "
                  "mengindikasikan fitur yang redundan.\n")

    numeric_df = df[feat_cols].select_dtypes(include=[np.number])

    # ── 3a. Full correlation heatmap (downsampled to mean per sensor per stat)
    # Aggregate: mean value per sensor-stat across all runs
    agg_cols_by_stat = {}
    for stat in KEY_STATS:
        cols = [f'{s}_{stat}' for s in SENSORS if f'{s}_{stat}' in feat_cols]
        agg_cols_by_stat[stat] = cols

    for stat in KEY_STATS:
        cols = agg_cols_by_stat[stat]
        if not cols:
            continue
        corr_df = numeric_df[cols].corr()
        short_labels = [c.replace(f'_{stat}','') for c in cols]

        fig, ax = plt.subplots(figsize=(12, 10))
        cmap = plt.cm.RdYlGn
        im = ax.imshow(corr_df.values, cmap=cmap, vmin=-1, vmax=1, aspect='auto')
        plt.colorbar(im, ax=ax, shrink=0.8, label='Pearson r')

        ax.set_xticks(range(len(short_labels)))
        ax.set_yticks(range(len(short_labels)))
        ax.set_xticklabels(short_labels, rotation=45, ha='right', fontsize=9)
        ax.set_yticklabels(short_labels, fontsize=9)

        for i in range(len(corr_df)):
            for j in range(len(corr_df)):
                val = corr_df.values[i, j]
                ax.text(j, i, f'{val:.2f}', ha='center', va='center',
                        fontsize=7, color='black' if abs(val) < 0.7 else 'white')

        ax.set_title(f'Korelasi Sensor -- Fitur: {stat.upper()}', fontsize=13, fontweight='bold')
        plt.tight_layout()
        out_path = os.path.join(PLOT_CORR, f'corr_{stat}.png')
        plt.savefig(out_path, dpi=DPI, bbox_inches='tight')
        plt.close()

    # ── 3b. Identify highly correlated feature pairs
    corr_matrix = numeric_df.corr().abs()
    upper_tri = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
    high_corr = [(col, row, upper_tri.loc[row, col])
                 for col in upper_tri.columns
                 for row in upper_tri.index
                 if pd.notna(upper_tri.loc[row, col]) and upper_tri.loc[row, col] > 0.95]
    high_corr.sort(key=lambda x: -x[2])

    report.append(f"\n### Pasangan Fitur dengan Korelasi Sangat Tinggi (r > 0.95)\n")
    report.append(f"Total: {len(high_corr)} pasangan\n")
    report.append("| Fitur A | Fitur B | r |\n|---------|---------|---|\n")
    for a, b, r in high_corr[:20]:
        report.append(f"| {a} | {b} | {r:.4f} |\n")

    report.append(f"\nFile disimpan di: `plots/features/correlations/corr_<stat>.png`\n")
    print(f"  [OK] Correlations saved -> {PLOT_CORR}")
    return high_corr


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Batch Analysis
# ─────────────────────────────────────────────────────────────────────────────
def plot_batch_analysis(df, feat_cols, report):
    print("[4/4] Generating batch analysis plots...")
    report.append("## 4. Analisis Batch Effect\n")
    report.append("Analisis ini mendeteksi apakah terdapat perbedaan baseline atau drift "
                  "antar batch pengambilan data.\n")

    batches = sorted(df['batch_id'].unique())

    # For each sensor mean feature, compare batch distributions
    for sensor in SENSORS:
        mean_feat = f'{sensor}_mean'
        std_feat  = f'{sensor}_std'
        delta_feat = f'{sensor}_delta'

        feats_avail = [f for f in [mean_feat, std_feat, delta_feat] if f in feat_cols]
        if not feats_avail:
            continue

        fig, axes = plt.subplots(1, len(feats_avail), figsize=(6*len(feats_avail), 6))
        if len(feats_avail) == 1:
            axes = [axes]
        fig.suptitle(f'Sensor {sensor} -- Batch Comparison', fontsize=13, fontweight='bold')

        batch_colors = plt.cm.Set2(np.linspace(0, 0.8, len(batches)))

        for ax, feat in zip(axes, feats_avail):
            data_per_batch = []
            labels = []
            for batch in batches:
                vals = df[df['batch_id']==batch][feat].dropna().values
                if len(vals) > 0:
                    data_per_batch.append(vals)
                    labels.append(batch)

            bp = ax.boxplot(data_per_batch, patch_artist=True,
                            labels=labels, widths=0.5,
                            medianprops=dict(color='black', linewidth=2))
            for patch, color in zip(bp['boxes'], batch_colors[:len(labels)]):
                patch.set_facecolor(color)
                patch.set_alpha(0.8)
            stat_name = feat.replace(f'{sensor}_','')
            ax.set_title(stat_name.upper(), fontsize=11)
            ax.set_ylabel('ADC Value')
            ax.grid(axis='y', linestyle='--', alpha=0.4)

        plt.tight_layout()
        out_path = os.path.join(PLOT_BATCH, f'batch_{sensor}.png')
        plt.savefig(out_path, dpi=DPI, bbox_inches='tight')
        plt.close()

    # ── Batch drift metric: mean of sensor means per batch
    report.append("\n### Ringkasan Perubahan Mean ADC Antar Batch\n")
    report.append("| Sensor | B01 | B02 | B03 | B04 | B05 | Trend |\n")
    report.append("|--------|-----|-----|-----|-----|-----|-------|\n")

    drift_flags = []
    for sensor in SENSORS:
        mean_feat = f'{sensor}_mean'
        if mean_feat not in feat_cols:
            continue
        row_vals = []
        for batch in ['B01','B02','B03','B04','B05']:
            vals = df[df['batch_id']==batch][mean_feat].dropna().values
            row_vals.append(f"{np.mean(vals):.0f}" if len(vals) > 0 else "-")

        # Trend check: compare first and last available means
        numeric_means = []
        for batch in ['B01','B02','B03','B04','B05']:
            vals = df[df['batch_id']==batch][mean_feat].dropna().values
            if len(vals) > 0:
                numeric_means.append((batch, np.mean(vals)))
        if len(numeric_means) >= 2:
            first_val = numeric_means[0][1]
            last_val  = numeric_means[-1][1]
            pct_chg   = (last_val - first_val) / (first_val + 1e-9) * 100
            if abs(pct_chg) > 10:
                trend = f"DRIFT {pct_chg:+.1f}%"
                drift_flags.append((sensor, pct_chg))
            else:
                trend = f"Stabil ({pct_chg:+.1f}%)"
        else:
            trend = "N/A"
        report.append(f"| {sensor} | {' | '.join(row_vals)} | {trend} |\n")

    if drift_flags:
        report.append(f"\n> **Perhatian:** Indikasi drift terdeteksi pada sensor: "
                      f"{', '.join([s for s,_ in drift_flags])}. "
                      f"Perlu dianalisis lebih lanjut apakah ini drift sensor atau "
                      f"perbedaan kondisi pengambilan sampel.\n")
    else:
        report.append(f"\n> Tidak ada indikasi drift yang signifikan (>10%) antar batch.\n")

    report.append(f"\nFile disimpan di: `plots/features/batch_comparison/batch_<sensor>.png`\n")
    print(f"  [OK] Batch analysis saved -> {PLOT_BATCH}")
    return drift_flags


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Statistical Discrimination Test (ANOVA / Kruskal-Wallis)
# ─────────────────────────────────────────────────────────────────────────────
def analyze_discrimination(df, feat_cols, report):
    print("[5/5] Running discrimination analysis (ANOVA / Kruskal-Wallis)...")

    groups_by_roast = {r: df[df['roast_level']==r] for r in ROAST_LEVELS}
    numeric_feat_cols = [c for c in feat_cols if df[c].dtype in [np.float64, np.float32, np.int64]]

    discriminative_feats  = []
    low_variance_feats    = []
    non_discriminative    = []
    high_variance_feats   = []

    results = []
    for feat in numeric_feat_cols:
        vals_per_group = [groups_by_roast[r][feat].dropna().values for r in ROAST_LEVELS]
        if any(len(v) < 3 for v in vals_per_group):
            continue

        overall_std  = df[feat].std()
        overall_mean = df[feat].mean()
        cv = overall_std / (abs(overall_mean) + 1e-9)

        try:
            _, p_kw = kruskal(*vals_per_group)
        except Exception:
            p_kw = 1.0

        try:
            _, p_anova = f_oneway(*vals_per_group)
        except Exception:
            p_anova = 1.0

        results.append({
            'feature': feat,
            'overall_mean': overall_mean,
            'overall_std':  overall_std,
            'cv':           cv,
            'p_kruskal':    p_kw,
            'p_anova':      p_anova,
            'significant':  p_kw < 0.05
        })

        if overall_std < 1e-3:
            low_variance_feats.append(feat)
        elif cv > 0.5:
            high_variance_feats.append(feat)

        if p_kw < 0.05:
            discriminative_feats.append(feat)
        else:
            non_discriminative.append(feat)

    results_df = pd.DataFrame(results).sort_values('p_kruskal')
    results_df.to_csv(os.path.join(PROCESSED_DIR, 'feature_significance.csv'), index=False)

    # ── Add to report
    report.append("## 5. Uji Diskriminasi Fitur (Kruskal-Wallis)\n")
    report.append("Kruskal-Wallis H-test menguji apakah distribusi fitur berbeda secara signifikan "
                  "antar roast level (p < 0.05 = signifikan).\n")
    report.append(f"\n**Total fitur diuji    :** {len(results)}\n")
    report.append(f"**Fitur signifikan (p<0.05):** {len(discriminative_feats)}\n")
    report.append(f"**Fitur tidak signifikan  :** {len(non_discriminative)}\n\n")

    report.append("### Top 30 Fitur Paling Diskriminatif (p terkecil)\n")
    report.append("| Rank | Fitur | p-value (Kruskal) | CV |\n")
    report.append("|------|-------|-------------------|----|\n")
    for i, row in results_df.head(30).iterrows():
        report.append(f"| {results_df.index.get_loc(i)+1} | {row['feature']} "
                      f"| {row['p_kruskal']:.4e} | {row['cv']:.3f} |\n")

    return results_df, discriminative_feats, low_variance_feats, high_variance_feats


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Mean per Roast Level Summary Table
# ─────────────────────────────────────────────────────────────────────────────
def summarize_by_roast(df, feat_cols, report):
    report.append("## 6. Ringkasan Mean per Roast Level\n")
    report.append("Tabel ini menampilkan perbedaan rata-rata fitur `mean` per sensor "
                  "antara roast level.\n")
    report.append("\n| Sensor | Fitur | Light Mean | Medium Mean | Dark Mean | Diff L-D |\n")
    report.append("|--------|-------|-----------|------------|---------|----------|\n")

    interesting = []
    for sensor in SENSORS:
        for stat in ['mean','delta','slope']:
            feat = f'{sensor}_{stat}'
            if feat not in feat_cols:
                continue
            vals = {}
            for r in ROAST_LEVELS:
                v = df[df['roast_level']==r][feat].mean()
                vals[r] = v
            diff_ld = vals['light'] - vals['dark']
            pct_diff = abs(diff_ld) / (abs(vals['light']) + 1e-9) * 100
            if pct_diff > 15:
                interesting.append((feat, pct_diff))
            report.append(f"| {sensor} | {stat} | {vals['light']:.1f} | "
                          f"{vals['medium']:.1f} | {vals['dark']:.1f} | "
                          f"{diff_ld:+.1f} ({pct_diff:.1f}%) |\n")

    return interesting


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    make_dirs()

    # Load data
    if not os.path.exists(FEATURE_CSV):
        print(f"[ERROR] File tidak ditemukan: {FEATURE_CSV}")
        sys.exit(1)

    df = pd.read_csv(FEATURE_CSV)
    meta_cols = ['sample_id','roast_level','origin','batch_id','run_id','n_collect_pts']
    feat_cols = [c for c in df.columns if c not in meta_cols]

    print(f"[INFO] Loaded: {len(df)} baris, {len(feat_cols)} fitur numerik")
    print(f"[INFO] Roast: {dict(df['roast_level'].value_counts())}")
    print()

    report = []
    report.append("# Feature Analysis Report -- E-NOSE Kopi\n\n")
    report.append(f"**Tanggal Analisis:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    report.append("---\n\n")
    report.append("## 0. Ringkasan Dataset\n")
    report.append(f"| Keterangan | Nilai |\n|---|---|\n")
    report.append(f"| Total RUN | {len(df)} |\n")
    report.append(f"| Total Fitur Numerik | {len(feat_cols)} |\n")
    report.append(f"| Sensor | 10 channel ADC |\n")
    report.append(f"| Statistik per sensor | 12 |\n")
    report.append(f"| Roast: Light | {len(df[df.roast_level=='light'])} RUN |\n")
    report.append(f"| Roast: Medium | {len(df[df.roast_level=='medium'])} RUN |\n")
    report.append(f"| Roast: Dark | {len(df[df.roast_level=='dark'])} RUN |\n")
    report.append(f"| Batch | {', '.join(sorted(df.batch_id.unique()))} |\n\n")

    # Run all analyses
    plot_boxplots(df, feat_cols, report)
    plot_distributions(df, feat_cols, report)
    high_corr = plot_correlations(df, feat_cols, report)
    drift_flags = plot_batch_analysis(df, feat_cols, report)
    results_df, disc_feats, low_var, high_var = analyze_discrimination(df, feat_cols, report)
    interesting_feats = summarize_by_roast(df, feat_cols, report)

    # ── Final Report Section: Recommendations
    report.append("\n## 7. Ringkasan & Rekomendasi\n\n")
    report.append("### 7.1 Fitur Stabil (Low Variance)\n")
    if low_var:
        report.append(f"Jumlah: {len(low_var)}\n")
        for f in low_var[:10]:
            report.append(f"- `{f}`\n")
    else:
        report.append("Tidak ada fitur dengan variance sangat kecil.\n")

    report.append("\n### 7.2 Fitur dengan Variasi Tinggi (CV > 0.5)\n")
    report.append(f"Jumlah: {len(high_var)}\n")
    for f in high_var[:15]:
        report.append(f"- `{f}`\n")

    report.append("\n### 7.3 Fitur yang Menunjukkan Indikasi Perbedaan Roast Level\n")
    report.append(f"*(p-value Kruskal-Wallis < 0.05)*\n\n")
    report.append(f"Total: **{len(disc_feats)}** fitur signifikan\n\n")
    # Group by sensor
    report.append("| Sensor | Fitur Signifikan |\n|--------|------------------|\n")
    for sensor in SENSORS:
        sensor_disc = [f for f in disc_feats if f.startswith(sensor+'_')]
        stat_names  = [f.replace(sensor+'_','') for f in sensor_disc]
        report.append(f"| {sensor} | {', '.join(stat_names) if stat_names else '-'} |\n")

    report.append("\n### 7.4 Fitur Sangat Berkorelasi (r > 0.95) - Kemungkinan Redundan\n")
    report.append(f"Total pasangan: {len(high_corr)}\n")
    report.append("Beberapa fitur yang sangat berkorelasi dapat direduksi pada tahap preprocessing ML.\n")

    report.append("\n### 7.5 Perbedaan Antar Batch\n")
    if drift_flags:
        report.append(f"**Indikasi drift terdeteksi** pada sensor: "
                      f"{', '.join([s for s,_ in drift_flags])}.\n")
        report.append("Kemungkinan penyebab: kondisi lingkungan berbeda antar hari pengambilan, "
                      "atau sensor baseline bergeser. Disarankan untuk:\n")
        report.append("- Menganalisis lebih lanjut apakah drift terjadi sistematis atau acak.\n")
        report.append("- Mempertimbangkan normalisasi per batch pada tahap preprocessing ML.\n")
    else:
        report.append("Tidak ada indikasi drift batch yang signifikan (>10%).\n")

    report.append("\n### 7.6 Rekomendasi untuk Tahap Machine Learning\n\n")
    report.append("> **CATATAN:** Rekomendasi ini berdasarkan analisis statistik eksploratoris.\n")
    report.append("> Validasi akhir fitur harus dilakukan setelah training model.\n\n")

    # Top features by significance
    top_feats = results_df.head(30)['feature'].tolist()
    report.append("**Kandidat Fitur Prioritas** (30 fitur dengan p-value terkecil):\n\n")
    for i, f in enumerate(top_feats, 1):
        p_val = results_df[results_df['feature']==f]['p_kruskal'].values[0]
        report.append(f"{i}. `{f}` (p = {p_val:.4e})\n")

    report.append("\n**Fitur yang kemungkinan tidak informatif** (p > 0.05):\n")
    for f in results_df[results_df['p_kruskal'] > 0.05].head(10)['feature'].tolist():
        report.append(f"- `{f}` -- indikasi tidak membedakan roast level\n")

    report.append("\n---\n")
    report.append("*Laporan ini tidak mengandung output training machine learning.*\n")
    report.append("*RAW CSV data tidak diubah selama seluruh proses analisis.*\n")

    # Write report
    with open(REPORT_MD, 'w', encoding='utf-8') as f:
        f.writelines(report)

    print()
    print("="*70)
    print("  ANALISIS SELESAI")
    print("="*70)
    print(f"  Fitur signifikan (Kruskal p<0.05) : {len(disc_feats)} / {len(feat_cols)}")
    print(f"  Fitur sangat berkorelasi (r>0.95)  : {len(high_corr)} pasangan")
    print(f"  Indikasi drift batch               : {len(drift_flags)} sensor")
    print()
    print(f"  Plots       -> plots/features/")
    print(f"  Report      -> {REPORT_MD}")
    print(f"  Significance-> {os.path.join(PROCESSED_DIR,'feature_significance.csv')}")
    print()
    print("[DONE] Feature analysis selesai.")


if __name__ == '__main__':
    main()
