import os
import glob
import sys
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score

# Paths
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPTS_DIR, '..', 'data')
PLOTS_DIR = os.path.join(SCRIPTS_DIR, '..', 'plots')
os.makedirs(PLOTS_DIR, exist_ok=True)

ADC_COLS = [
    'adc_tgs822', 'adc_mq135', 'adc_mq9', 'adc_tgs2611',
    'adc_tgs2620', 'adc_tgs2600', 'adc_tgs2602', 'adc_mq8',
    'adc_tgs813', 'adc_tgs816'
]

def load_raw_data():
    csv_files = glob.glob(os.path.join(DATA_DIR, '*.csv'))
    csv_files = [f for f in csv_files if 'dataset_fitur' not in os.path.basename(f)]
    
    if not csv_files:
        print(f"No CSV files found in {DATA_DIR}")
        sys.exit(1)
        
    dfs = []
    for f in csv_files:
        try:
            df = pd.read_csv(f)
            if 'source_file' not in df.columns:
                df['source_file'] = os.path.basename(f)
            dfs.append(df)
        except Exception as e:
            print(f"Error loading {f}: {e}")
            
    return pd.concat(dfs, ignore_index=True)

def extract_features(df_all):
    df_col = df_all[df_all['phase'] == 'collecting'].copy()
    
    if df_col.empty:
        print("No collecting phase found in dataset!")
        sys.exit(1)
        
    # Ensure numeric columns
    for col in ADC_COLS:
        if col not in df_col.columns:
            df_col[col] = 0
        df_col[col] = pd.to_numeric(df_col[col], errors='coerce').fillna(0)
        
    if 'cycle' not in df_col.columns:
        df_col['cycle'] = 1
        
    group_keys = ['source_file', 'label', 'cycle']
    available_keys = [k for k in group_keys if k in df_col.columns]
    
    rows = []
    for keys, group in df_col.groupby(available_keys):
        key_dict = dict(zip(available_keys, keys if isinstance(keys, tuple) else (keys,)))
        
        row = {
            'source_file': key_dict.get('source_file', '?'),
            'label': key_dict.get('label', '?'),
            'cycle': key_dict.get('cycle', 1)
        }
        
        # 1. Means, Maxes, and Sums (AUC)
        for col in ADC_COLS:
            vals = group[col].values
            row[f'mean_{col}'] = float(np.mean(vals))
            row[f'max_{col}'] = float(np.max(vals))
            row[f'sum_{col}'] = float(np.sum(vals)) # AUC
            
        # 2. Ratios to MQ135
        mq135_max = row['max_adc_mq135'] if row['max_adc_mq135'] > 0 else 1.0
        for col in ADC_COLS:
            if col != 'adc_mq135':
                row[f'ratio_to_mq135_{col}'] = row[f'max_{col}'] / mq135_max
                
        # 3. Ratios to TGS822
        tgs822_max = row['max_adc_tgs822'] if row['max_adc_tgs822'] > 0 else 1.0
        for col in ADC_COLS:
            if col != 'adc_tgs822':
                row[f'ratio_to_tgs822_{col}'] = row[f'max_{col}'] / tgs822_max
                
        rows.append(row)
        
    return pd.DataFrame(rows)

def make_plots(df_feat):
    sns.set_theme(style="whitegrid")
    
    # ── Plot 1: Sensor Ratios Comparison ──
    # Let's plot ratio_to_tgs822_adc_mq135 and ratio_to_mq135_adc_tgs2620 side-by-side
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    # Sort order for labels
    labels_order = sorted(df_feat['label'].unique())
    
    sns.boxplot(ax=axes[0], data=df_feat, x='label', y='ratio_to_tgs822_adc_mq135', 
                order=labels_order, palette='Set2', hue='label', legend=False)
    axes[0].set_title('Ratio of MQ135 Max to TGS822 Max', fontsize=14, fontweight='bold')
    axes[0].set_xlabel('Roast Level', fontsize=12)
    axes[0].set_ylabel('Ratio Value', fontsize=12)
    
    sns.boxplot(ax=axes[1], data=df_feat, x='label', y='ratio_to_mq135_adc_tgs2620', 
                order=labels_order, palette='Set2', hue='label', legend=False)
    axes[1].set_title('Ratio of TGS2620 Max to MQ135 Max', fontsize=14, fontweight='bold')
    axes[1].set_xlabel('Roast Level', fontsize=12)
    axes[1].set_ylabel('Ratio Value', fontsize=12)
    
    plt.suptitle('Comparison of Sensor Ratio Features Across Roast Levels', fontsize=16, fontweight='bold', y=0.98)
    plt.tight_layout()
    
    plot_ratio_path = os.path.join(PLOTS_DIR, 'feature_ratios_comparison.png')
    plt.savefig(plot_ratio_path, dpi=150)
    plt.close()
    print(f"[OK] Saved sensor ratio comparison plot to: {plot_ratio_path}")
    
    # ── Plot 2: Model Accuracy Comparison ──
    base_feats = [f'mean_{c}' for c in ADC_COLS] + [f'max_{c}' for c in ADC_COLS]
    ratio_feats = [c for c in df_feat.columns if 'ratio_to_' in c]
    auc_feats = [f'sum_{c}' for c in ADC_COLS]
    
    feature_sets = {
        'Baseline (Mean + Max)': base_feats,
        'Baseline + AUC': base_feats + auc_feats,
        'Baseline + Ratios': base_feats + ratio_feats,
        'Proposed (Mean + Max + AUC + Ratios)': base_feats + auc_feats + ratio_feats
    }
    
    X_dict = {name: df_feat[cols].fillna(0).values for name, cols in feature_sets.items()}
    y = df_feat['label'].values
    
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    accuracies = []
    std_devs = []
    names = []
    
    for name, X in X_dict.items():
        clf = RandomForestClassifier(
            n_estimators=8,
            max_depth=4,
            random_state=42,
            class_weight='balanced'
        )
        scores = cross_val_score(clf, X, y, cv=cv, scoring='accuracy')
        accuracies.append(scores.mean() * 100)
        std_devs.append(scores.std() * 100)
        names.append(name)
        
    plt.figure(figsize=(10, 6))
    bars = plt.bar(names, accuracies, yerr=std_devs, capsize=8, color=['#7f7f7f', '#aec7e8', '#ffbb78', '#ff9896'], edgecolor='black', width=0.6)
    
    # Add values on top of bars
    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2.0, yval + 1, f'{yval:.2f}%', ha='center', va='bottom', fontweight='bold', fontsize=11)
        
    plt.title('Random Forest Cross-Validation Accuracy Comparison', fontsize=14, fontweight='bold')
    plt.ylabel('Accuracy (%)', fontsize=12)
    plt.ylim(0, 100)
    plt.xticks(rotation=15, ha='right', fontsize=11)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()
    
    plot_acc_path = os.path.join(PLOTS_DIR, 'model_accuracy_comparison.png')
    plt.savefig(plot_acc_path, dpi=150)
    plt.close()
    print(f"[OK] Saved model accuracy comparison plot to: {plot_acc_path}")

if __name__ == '__main__':
    print("Loading raw data...")
    df_raw = load_raw_data()
    print("Extracting features...")
    df_feat = extract_features(df_raw)
    print("Generating plots...")
    make_plots(df_feat)
    print("Done!")
