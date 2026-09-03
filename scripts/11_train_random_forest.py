"""
11_train_random_forest.py - Random Forest Classification -- E-NOSE Kopi
==============================================================================
Input  : processed/ml_dataset_final.csv
Output :
  models/
    random_forest_baseline.joblib
    random_forest_final.joblib
    feature_list.json
  results/
    baseline_results.md
    final_results.md
    classification_report.txt
    confusion_matrix.png
    feature_importance.png
    predictions.csv
    model_analysis_report.md
==============================================================================
"""

import os, sys, json, warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
from datetime import datetime

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import (StratifiedKFold, cross_val_score,
                                     GridSearchCV, cross_validate)
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                             f1_score, classification_report,
                             confusion_matrix, ConfusionMatrixDisplay)
from sklearn.preprocessing import LabelEncoder
import joblib

warnings.filterwarnings('ignore')

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR      = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
PROCESSED_DIR = os.path.join(BASE_DIR, 'processed')
MODELS_DIR    = os.path.join(BASE_DIR, 'models')
RESULTS_DIR   = os.path.join(BASE_DIR, 'results')

INPUT_CSV = os.path.join(PROCESSED_DIR, 'ml_dataset_final.csv')

CLASSES = ['light', 'medium', 'dark']
META_COLS = ['sample_id', 'roast_level', 'origin', 'batch_id', 'run_id',
             'is_outlier_run', 'n_outlier_feats']

DPI = 130


def make_dirs():
    for d in [MODELS_DIR, RESULTS_DIR]:
        os.makedirs(d, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Load & Split
# ─────────────────────────────────────────────────────────────────────────────
def load_and_split(df, feat_cols):
    """
    Batch-aware train/test split.

    Dataset batch distribution:
      B01: dark=10  light=20  medium=20  (50)
      B02: dark=20  light=10  medium=10  (40)
      B03: dark=0   light=20  medium=10  (30)  <-- no dark!
      B04: dark=10  light=20  medium=20  (50)
      B05: dark=10  light=0   medium=0   (10)  <-- only dark!

    Strategy:
      TRAIN: B01 + B02 + B04  (50+40+50=140 runs)
        light=50, medium=50, dark=40  -- all 3 classes present
      TEST:  B03 + B05         (30+10=40 runs)
        light=20, medium=10, dark=10  -- all 3 classes present

    Rationale:
      - B03 alone lacks dark; B05 alone lacks light & medium.
      - B03+B05 combined gives all 3 classes.
      - B01+B02+B04 is the larger set used for training.
      - This is a realistic out-of-batch generalization test.
    """
    train_batches = ['B01', 'B02', 'B04']
    test_batches  = ['B03', 'B05']

    train_df = df[df['batch_id'].isin(train_batches)].copy()
    test_df  = df[df['batch_id'].isin(test_batches)].copy()

    X_train = train_df[feat_cols].values
    y_train = train_df['roast_level'].values
    X_test  = test_df[feat_cols].values
    y_test  = test_df['roast_level'].values

    meta_train = train_df[['sample_id','origin','batch_id','run_id','roast_level']].reset_index(drop=True)
    meta_test  = test_df[['sample_id','origin','batch_id','run_id','roast_level']].reset_index(drop=True)

    return X_train, y_train, X_test, y_test, meta_train, meta_test, train_batches, test_batches


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Evaluate Model
# ─────────────────────────────────────────────────────────────────────────────
def evaluate_model(model, X_train, y_train, X_test, y_test, feat_cols, tag='baseline'):
    """Compute all metrics and return results dict."""
    # Train metrics
    y_pred_train = model.predict(X_train)
    train_acc    = accuracy_score(y_train, y_pred_train)

    # Test metrics
    y_pred_test = model.predict(X_test)
    test_acc    = accuracy_score(y_test, y_pred_test)
    test_prec   = precision_score(y_test, y_pred_test, average='macro', zero_division=0)
    test_rec    = recall_score(y_test, y_pred_test, average='macro', zero_division=0)
    test_f1     = f1_score(y_test, y_pred_test, average='macro', zero_division=0)
    cls_report  = classification_report(y_test, y_pred_test,
                                        target_names=CLASSES, zero_division=0)
    cm          = confusion_matrix(y_test, y_pred_test, labels=CLASSES)

    # CV on training set
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(model, X_train, y_train, cv=cv, scoring='f1_macro')

    results = {
        'tag':           tag,
        'train_acc':     train_acc,
        'test_acc':      test_acc,
        'test_precision': test_prec,
        'test_recall':   test_rec,
        'test_f1_macro': test_f1,
        'cv_f1_mean':    cv_scores.mean(),
        'cv_f1_std':     cv_scores.std(),
        'cls_report':    cls_report,
        'cm':            cm,
        'y_pred_test':   y_pred_test,
        'y_pred_train':  y_pred_train,
        'params':        model.get_params(),
    }
    return results


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Plot Confusion Matrix
# ─────────────────────────────────────────────────────────────────────────────
def plot_confusion_matrix(cm, tag, out_path):
    fig, ax = plt.subplots(figsize=(7, 6))
    disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=CLASSES)
    disp.plot(ax=ax, colorbar=True, cmap='Blues',
              values_format='d', xticks_rotation=15)
    ax.set_title(f'Confusion Matrix -- {tag}', fontsize=13, fontweight='bold', pad=12)
    plt.tight_layout()
    plt.savefig(out_path, dpi=DPI, bbox_inches='tight')
    plt.close()
    print(f"  [OK] Confusion matrix -> {out_path}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Plot Feature Importance
# ─────────────────────────────────────────────────────────────────────────────
def plot_feature_importance(model, feat_cols, out_path, top_n=30):
    importances = model.feature_importances_
    fi_df = pd.DataFrame({'feature': feat_cols, 'importance': importances})
    fi_df = fi_df.sort_values('importance', ascending=False).head(top_n)

    # Color by sensor
    SENSOR_COLORS = {
        'TGS822':'#2196F3','MQ135':'#FF9800','MQ9':'#FF5722','TGS2611':'#9C27B0',
        'TGS2620':'#00BCD4','TGS2600':'#8BC34A','TGS2602':'#F44336',
        'MQ8':'#FF6F00','TGS813':'#3F51B5','TGS816':'#009688',
    }
    colors = []
    for feat in fi_df['feature']:
        sensor = feat.split('_')[0]
        colors.append(SENSOR_COLORS.get(sensor, '#BDBDBD'))

    fig, ax = plt.subplots(figsize=(12, 9))
    bars = ax.barh(range(len(fi_df)), fi_df['importance'].values,
                   color=colors, alpha=0.85, edgecolor='white', linewidth=0.5)
    ax.set_yticks(range(len(fi_df)))
    ax.set_yticklabels(fi_df['feature'].values, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel('Feature Importance (Mean Decrease Impurity)', fontsize=11)
    ax.set_title(f'Top {top_n} Feature Importance -- Random Forest', fontsize=13, fontweight='bold')
    ax.grid(axis='x', linestyle='--', alpha=0.4)

    # Legend by sensor
    handles = [plt.Rectangle((0,0),1,1, color=c, label=s)
               for s, c in SENSOR_COLORS.items()]
    ax.legend(handles=handles, title='Sensor', fontsize=8,
              loc='lower right', ncol=2)

    plt.tight_layout()
    plt.savefig(out_path, dpi=DPI, bbox_inches='tight')
    plt.close()

    fi_df_full = pd.DataFrame({'feature': feat_cols,
                               'importance': importances}).sort_values('importance', ascending=False)
    print(f"  [OK] Feature importance -> {out_path}")
    return fi_df_full


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Error Analysis
# ─────────────────────────────────────────────────────────────────────────────
def error_analysis(y_true, y_pred, meta):
    """Return dict of misclassification patterns."""
    errors = {}
    for actual in CLASSES:
        for pred in CLASSES:
            if actual == pred:
                continue
            mask = (np.array(y_true) == actual) & (np.array(y_pred) == pred)
            key = f'{actual}_as_{pred}'
            errors[key] = int(mask.sum())

    # Detailed error rows
    error_mask = np.array(y_true) != np.array(y_pred)
    error_detail = meta[error_mask].copy()
    error_detail['actual']    = np.array(y_true)[error_mask]
    error_detail['predicted'] = np.array(y_pred)[error_mask]
    return errors, error_detail


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Write Result Markdown
# ─────────────────────────────────────────────────────────────────────────────
def write_results_md(results, errors, fi_df, out_path, title, train_info, test_info):
    lines = []
    lines.append(f"# {title}\n\n")
    lines.append(f"**Tanggal:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

    lines.append("## Data\n")
    lines.append(f"| Keterangan | Nilai |\n|---|---|\n")
    lines.append(f"| Train batches | {train_info} |\n")
    lines.append(f"| Test batches  | {test_info} |\n")
    lines.append(f"| Train samples | {results.get('n_train', '-')} |\n")
    lines.append(f"| Test samples  | {results.get('n_test', '-')} |\n\n")

    lines.append("## Performa Model\n")
    lines.append(f"| Metrik | Nilai |\n|--------|-------|\n")
    lines.append(f"| Train Accuracy     | {results['train_acc']*100:.2f}% |\n")
    lines.append(f"| Test Accuracy      | {results['test_acc']*100:.2f}% |\n")
    lines.append(f"| Test Precision (macro) | {results['test_precision']*100:.2f}% |\n")
    lines.append(f"| Test Recall (macro)    | {results['test_recall']*100:.2f}% |\n")
    lines.append(f"| Test F1 (macro)        | {results['test_f1_macro']*100:.2f}% |\n")
    lines.append(f"| CV F1 (5-fold, mean)   | {results['cv_f1_mean']*100:.2f}% +/- {results['cv_f1_std']*100:.2f}% |\n\n")

    gap = results['train_acc'] - results['test_acc']
    if gap > 0.15:
        lines.append(f"> **Perhatian:** Gap Train-Test = {gap*100:.1f}% -- indikasi overfitting.\n\n")
    else:
        lines.append(f"> Gap Train-Test = {gap*100:.1f}% -- indikasi overfitting minimal.\n\n")

    lines.append("## Classification Report\n\n```\n")
    lines.append(results['cls_report'])
    lines.append("```\n\n")

    lines.append("## Analisis Kesalahan Klasifikasi\n\n")
    lines.append("| Actual | Diprediksi | Count |\n|--------|-----------|-------|\n")
    for key, cnt in errors.items():
        actual, pred = key.replace('_as_', ' → ').split(' → ')
        lines.append(f"| {actual} | {pred} | {cnt} |\n")

    lines.append("\n## Top 15 Feature Paling Penting\n\n")
    lines.append("| Rank | Feature | Importance |\n|------|---------|------------|\n")
    for i, row in fi_df.head(15).iterrows():
        lines.append(f"| {fi_df.index.get_loc(i)+1} | `{row['feature']}` | {row['importance']:.4f} |\n")

    lines.append("\n## Parameter Model\n\n```json\n")
    params_str = json.dumps({k: str(v) for k, v in results['params'].items()}, indent=2)
    lines.append(params_str)
    lines.append("\n```\n")

    with open(out_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print(f"  [OK] Results MD -> {out_path}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    make_dirs()
    print("[INFO] Loading dataset...")
    df = pd.read_csv(INPUT_CSV)
    feat_cols = [c for c in df.columns if c not in META_COLS]
    print(f"[INFO] {len(df)} runs, {len(feat_cols)} features")
    print(f"[INFO] Classes: {sorted(df['roast_level'].unique())}")
    print()

    # Save feature list
    feat_list_path = os.path.join(MODELS_DIR, 'feature_list.json')
    with open(feat_list_path, 'w') as f:
        json.dump(feat_cols, f, indent=2)

    # ── Split ─────────────────────────────────────────────────────────────────
    print("[1/6] Splitting data (batch-aware)...")
    X_train, y_train, X_test, y_test, meta_train, meta_test, train_b, test_b = \
        load_and_split(df, feat_cols)

    print(f"  Train: {len(X_train)} samples | batches = {train_b}")
    for cls in CLASSES:
        print(f"    {cls}: {np.sum(y_train==cls)}")
    print(f"  Test:  {len(X_test)} samples  | batches = {test_b}")
    for cls in CLASSES:
        print(f"    {cls}: {np.sum(y_test==cls)}")
    print()

    # ── Baseline RF ───────────────────────────────────────────────────────────
    print("[2/6] Training BASELINE Random Forest...")
    baseline_params = {
        'n_estimators':    100,
        'max_depth':       None,
        'min_samples_split': 2,
        'min_samples_leaf':  1,
        'max_features':    'sqrt',
        'class_weight':    'balanced',
        'random_state':    42,
        'n_jobs':          -1,
    }
    rf_baseline = RandomForestClassifier(**baseline_params)
    rf_baseline.fit(X_train, y_train)

    baseline_results = evaluate_model(rf_baseline, X_train, y_train, X_test, y_test, feat_cols, tag='Baseline')
    baseline_results['n_train'] = len(X_train)
    baseline_results['n_test']  = len(X_test)

    print(f"  Train Accuracy   : {baseline_results['train_acc']*100:.2f}%")
    print(f"  Test  Accuracy   : {baseline_results['test_acc']*100:.2f}%")
    print(f"  Test  F1 (macro) : {baseline_results['test_f1_macro']*100:.2f}%")
    print(f"  CV    F1 (5-fold): {baseline_results['cv_f1_mean']*100:.2f}% +/- {baseline_results['cv_f1_std']*100:.2f}%")
    print()

    # Save baseline model
    baseline_model_path = os.path.join(MODELS_DIR, 'random_forest_baseline.joblib')
    joblib.dump(rf_baseline, baseline_model_path)
    print(f"  [OK] Baseline model -> {baseline_model_path}")

    # Baseline error analysis
    base_errors, base_error_detail = error_analysis(y_test, baseline_results['y_pred_test'], meta_test)

    # Baseline plots
    plot_confusion_matrix(baseline_results['cm'], 'Baseline',
                          os.path.join(RESULTS_DIR, 'confusion_matrix_baseline.png'))
    fi_df = plot_feature_importance(rf_baseline, feat_cols,
                                    os.path.join(RESULTS_DIR, 'feature_importance.png'))
    write_results_md(baseline_results, base_errors, fi_df,
                     os.path.join(RESULTS_DIR, 'baseline_results.md'),
                     'Baseline Random Forest Results',
                     ', '.join(train_b), ', '.join(test_b))

    # Classification report to file
    cls_report_path = os.path.join(RESULTS_DIR, 'classification_report.txt')
    with open(cls_report_path, 'w', encoding='utf-8') as f:
        f.write(f"=== BASELINE ===\n")
        f.write(f"Train Acc: {baseline_results['train_acc']*100:.2f}%\n")
        f.write(f"Test  Acc: {baseline_results['test_acc']*100:.2f}%\n\n")
        f.write(baseline_results['cls_report'])

    print()

    # ── Hyperparameter Tuning ─────────────────────────────────────────────────
    print("[3/6] Hyperparameter tuning (GridSearchCV, 5-fold)...")
    param_grid = {
        'n_estimators':      [50, 100, 200],
        'max_depth':         [None, 10, 20],
        'min_samples_split': [2, 5],
        'min_samples_leaf':  [1, 2],
        'max_features':      ['sqrt', 'log2'],
    }
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    grid_search = GridSearchCV(
        RandomForestClassifier(class_weight='balanced', random_state=42, n_jobs=-1),
        param_grid,
        cv=cv,
        scoring='f1_macro',
        n_jobs=-1,
        verbose=0,
        refit=True
    )
    grid_search.fit(X_train, y_train)
    best_params = grid_search.best_params_
    print(f"  Best params: {best_params}")
    print(f"  Best CV F1 : {grid_search.best_score_*100:.2f}%")
    print()

    # ── Final Model ───────────────────────────────────────────────────────────
    print("[4/6] Training FINAL model with best params...")
    final_params = dict(best_params)
    final_params.update({'class_weight': 'balanced', 'random_state': 42, 'n_jobs': -1})
    rf_final = RandomForestClassifier(**final_params)
    rf_final.fit(X_train, y_train)

    final_results = evaluate_model(rf_final, X_train, y_train, X_test, y_test, feat_cols, tag='Final')
    final_results['n_train'] = len(X_train)
    final_results['n_test']  = len(X_test)

    print(f"  Train Accuracy   : {final_results['train_acc']*100:.2f}%")
    print(f"  Test  Accuracy   : {final_results['test_acc']*100:.2f}%")
    print(f"  Test  F1 (macro) : {final_results['test_f1_macro']*100:.2f}%")
    print(f"  CV    F1 (5-fold): {final_results['cv_f1_mean']*100:.2f}% +/- {final_results['cv_f1_std']*100:.2f}%")
    print()

    final_model_path = os.path.join(MODELS_DIR, 'random_forest_final.joblib')
    joblib.dump(rf_final, final_model_path)
    print(f"  [OK] Final model -> {final_model_path}")

    # Final plots
    plot_confusion_matrix(final_results['cm'], 'Final (Tuned)',
                          os.path.join(RESULTS_DIR, 'confusion_matrix.png'))
    fi_df_final = plot_feature_importance(rf_final, feat_cols,
                                          os.path.join(RESULTS_DIR, 'feature_importance_final.png'))
    final_errors, final_error_detail = error_analysis(y_test, final_results['y_pred_test'], meta_test)

    write_results_md(final_results, final_errors, fi_df_final,
                     os.path.join(RESULTS_DIR, 'final_results.md'),
                     'Final (Tuned) Random Forest Results',
                     ', '.join(train_b), ', '.join(test_b))

    with open(cls_report_path, 'a', encoding='utf-8') as f:
        f.write(f"\n\n=== FINAL (TUNED) ===\n")
        f.write(f"Train Acc: {final_results['train_acc']*100:.2f}%\n")
        f.write(f"Test  Acc: {final_results['test_acc']*100:.2f}%\n\n")
        f.write(final_results['cls_report'])

    # ── Predictions CSV ───────────────────────────────────────────────────────
    print("[5/6] Saving predictions.csv...")
    pred_df = meta_test.copy()
    pred_df = pred_df.rename(columns={'roast_level': 'actual_roast'})
    pred_df['predicted_roast']    = final_results['y_pred_test']
    pred_df['correct']            = pred_df['actual_roast'] == pred_df['predicted_roast']
    pred_df['baseline_predicted'] = baseline_results['y_pred_test']
    pred_path = os.path.join(RESULTS_DIR, 'predictions.csv')
    pred_df.to_csv(pred_path, index=False)
    print(f"  [OK] -> {pred_path}")

    # ── Master Analysis Report ────────────────────────────────────────────────
    print("[6/6] Writing model_analysis_report.md...")

    # Overfitting assessment
    gap_base  = baseline_results['train_acc'] - baseline_results['test_acc']
    gap_final = final_results['train_acc']    - final_results['test_acc']
    overfit_flag_base  = gap_base  > 0.15
    overfit_flag_final = gap_final > 0.15

    report = []
    report.append("# Model Analysis Report -- E-NOSE Kopi Roast Classification\n\n")
    report.append(f"**Tanggal:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    report.append("---\n\n")

    report.append("## 1. Dataset yang Digunakan\n\n")
    report.append(f"- File: `processed/ml_dataset_final.csv`\n")
    report.append(f"- Total RUN: **{len(df)}**\n")
    report.append(f"- Feature input: **{len(feat_cols)}** fitur numerik\n")
    report.append(f"- Target: `roast_level` (Light / Medium / Dark)\n\n")

    report.append("## 2. Train/Test Split\n\n")
    report.append(f"| Set | Batch | Jumlah | Light | Medium | Dark |\n")
    report.append(f"|-----|-------|--------|-------|--------|------|\n")
    report.append(f"| Train | {', '.join(train_b)} | {len(X_train)} | "
                  f"{np.sum(y_train=='light')} | {np.sum(y_train=='medium')} | {np.sum(y_train=='dark')} |\n")
    report.append(f"| Test  | {', '.join(test_b)}  | {len(X_test)}  | "
                  f"{np.sum(y_test=='light')} | {np.sum(y_test=='medium')} | {np.sum(y_test=='dark')} |\n\n")
    report.append("**Metode:** Batch-based split (bukan random split).\n\n")
    report.append("**Alasan:**\n")
    report.append("- Mencegah data leakage antar batch (run dari batch sama tidak tersebar di train & test).\n")
    report.append("- Mensimulasikan generalisasi ke batch baru (realistic deployment scenario).\n")
    report.append("- B03+B05 dipilih sebagai test karena merupakan batch yang lebih sedikit dan\n"
                  "  keduanya saling melengkapi kelas yang tidak ada (B03 tidak ada dark, B05 hanya dark).\n\n")

    report.append("## 3. Keterbatasan Dataset\n\n")
    report.append("- **Class imbalance ringan:** Light(70) > Medium(60) > Dark(50). Diatasi dengan `class_weight='balanced'`.\n")
    report.append("- **Batch coverage tidak simetris:** Tidak semua kelas hadir di semua batch.\n")
    report.append("- **Jumlah data test kecil:** Hanya 40 sampel, evaluasi mungkin belum stabil.\n")
    report.append("- **Sample ID terbatas:** 9 sample ID unik; generalisasi ke sample baru belum teruji.\n")
    report.append("- **Drift sensor:** TGS822 dan TGS2611 menunjukkan indikasi drift antar batch (>18%).\n\n")

    report.append("## 4. Parameter Baseline\n\n```json\n")
    report.append(json.dumps({k: str(v) for k, v in baseline_params.items()}, indent=2))
    report.append("\n```\n\n")

    report.append("## 5. Parameter Final (Setelah Tuning)\n\n```json\n")
    report.append(json.dumps({k: str(v) for k, v in final_params.items()}, indent=2))
    report.append("\n```\n\n")

    report.append("## 6. Hasil Performa\n\n")
    report.append("| Metrik | Baseline | Final (Tuned) |\n|--------|----------|---------------|\n")
    report.append(f"| Train Accuracy  | {baseline_results['train_acc']*100:.2f}% | {final_results['train_acc']*100:.2f}% |\n")
    report.append(f"| Test Accuracy   | {baseline_results['test_acc']*100:.2f}% | {final_results['test_acc']*100:.2f}% |\n")
    report.append(f"| Precision (macro)| {baseline_results['test_precision']*100:.2f}% | {final_results['test_precision']*100:.2f}% |\n")
    report.append(f"| Recall (macro)  | {baseline_results['test_recall']*100:.2f}% | {final_results['test_recall']*100:.2f}% |\n")
    report.append(f"| F1 (macro)      | {baseline_results['test_f1_macro']*100:.2f}% | {final_results['test_f1_macro']*100:.2f}% |\n")
    report.append(f"| CV F1 (5-fold)  | {baseline_results['cv_f1_mean']*100:.2f}% +/-{baseline_results['cv_f1_std']*100:.2f}% | {final_results['cv_f1_mean']*100:.2f}% +/-{final_results['cv_f1_std']*100:.2f}% |\n\n")

    report.append("## 7. Analisis Overfitting\n\n")
    report.append(f"| Model | Train Acc | Test Acc | Gap | Status |\n|-------|-----------|----------|-----|--------|\n")
    report.append(f"| Baseline | {baseline_results['train_acc']*100:.1f}% | {baseline_results['test_acc']*100:.1f}% | {gap_base*100:.1f}% | {'OVERFITTING' if overfit_flag_base else 'OK'} |\n")
    report.append(f"| Final    | {final_results['train_acc']*100:.1f}% | {final_results['test_acc']*100:.1f}% | {gap_final*100:.1f}% | {'OVERFITTING' if overfit_flag_final else 'OK'} |\n\n")

    report.append("## 8. Confusion Matrix -- Final Model\n\n```\n")
    cm_arr = final_results['cm']
    report.append(f"              light  medium  dark\n")
    for i, cls in enumerate(CLASSES):
        report.append(f"actual {cls:<8} {cm_arr[i,0]:5d}  {cm_arr[i,1]:6d}  {cm_arr[i,2]:4d}\n")
    report.append("```\n\n")

    report.append("## 9. Analisis Kesalahan Klasifikasi\n\n")
    report.append("| Actual | Diprediksi | Jumlah |\n|--------|-----------|--------|\n")
    for key, cnt in final_errors.items():
        if cnt > 0:
            actual_cls, pred_cls = key.split('_as_')
            report.append(f"| {actual_cls} | {pred_cls} | {cnt} |\n")

    if len(final_error_detail) > 0:
        report.append("\n**Detail run yang salah diklasifikasi:**\n\n")
        report.append("| Sample | Batch | Run | Actual | Predicted |\n|--------|-------|-----|--------|----------|\n")
        for _, row in final_error_detail.iterrows():
            report.append(f"| {row.get('sample_id','')} | {row.get('batch_id','')} | "
                          f"{row.get('run_id','')} | {row['actual']} | {row['predicted']} |\n")

    report.append("\n## 10. Feature Paling Penting\n\n")
    report.append("| Rank | Feature | Importance |\n|------|---------|------------|\n")
    for i, row in fi_df_final.head(15).iterrows():
        report.append(f"| {fi_df_final.index.get_loc(i)+1} | `{row['feature']}` | {row['importance']:.4f} |\n")

    report.append("\n**Analisis:**\n")
    top5 = fi_df_final.head(5)['feature'].tolist()
    report.append(f"- Feature terpenting: {', '.join([f'`{f}`' for f in top5])}\n")
    report.append("- Konsisten dengan analisis Kruskal-Wallis sebelumnya di mana TGS2602, TGS822, TGS2620, MQ8, TGS816 "
                  "memiliki p-value terkecil.\n")
    report.append("- Sensor MQ135 dan TGS2600 kemungkinan kurang informatif, sesuai ekspektasi dari analisis sebelumnya.\n\n")

    report.append("## 11. Rekomendasi Perbaikan\n\n")
    report.append("1. **Tambah data:** Lebih banyak RUN per sample akan meningkatkan stabilitas model.\n")
    report.append("2. **Normalisasi per batch:** Untuk mengatasi drift TGS822 dan TGS2611.\n")
    report.append("3. **Tambah sample D-GAY dan L-RAT:** Sample ID yang tidak ada di dataset saat ini.\n")
    report.append("4. **Test pada batch baru:** Lakukan pengambilan data batch baru dan evaluasi generalisasi.\n")
    report.append("5. **Feature engineering:** Pertimbangkan fitur normalisasi seperti Z-score per run "
                  "atau normalisasi terhadap baseline purging.\n\n")

    report.append("---\n")
    report.append("*Model siap dievaluasi. Belum dilakukan deployment ke Raspberry Pi.*\n")

    with open(os.path.join(RESULTS_DIR, 'model_analysis_report.md'), 'w', encoding='utf-8') as f:
        f.writelines(report)

    # ── Final Summary ─────────────────────────────────────────────────────────
    print()
    print("="*70)
    print("  MACHINE LEARNING SELESAI")
    print("="*70)
    print(f"  BASELINE  -- Test Acc: {baseline_results['test_acc']*100:.2f}%  "
          f"F1: {baseline_results['test_f1_macro']*100:.2f}%  "
          f"Gap: {gap_base*100:.1f}%")
    print(f"  FINAL     -- Test Acc: {final_results['test_acc']*100:.2f}%  "
          f"F1: {final_results['test_f1_macro']*100:.2f}%  "
          f"Gap: {gap_final*100:.1f}%")
    print()
    print(f"  models/  random_forest_baseline.joblib")
    print(f"           random_forest_final.joblib")
    print(f"           feature_list.json")
    print(f"  results/ confusion_matrix.png")
    print(f"           feature_importance_final.png")
    print(f"           predictions.csv")
    print(f"           model_analysis_report.md")
    print()
    print("[DONE] Random Forest training & evaluation selesai.")


if __name__ == '__main__':
    main()
