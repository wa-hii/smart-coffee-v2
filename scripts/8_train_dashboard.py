import os
import glob
import sys
import pandas as pd
import numpy as np
import streamlit as st
import matplotlib.pyplot as plt
import seaborn as sns
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

# Add scripts directory to path to import generate_model_atmega
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPTS_DIR)
from generate_model_atmega import export_model_atmega

# Paths
DATA_DIR = os.path.join(SCRIPTS_DIR, '..', 'data')
OUTPUT_HEADER = os.path.join(SCRIPTS_DIR, '..', 'include', 'model_rf_atmega.h')
MODEL_PATH = os.path.join(DATA_DIR, 'model_rf.joblib')

ADC_COLS = [
    'adc_tgs822', 'adc_mq135', 'adc_mq3', 'adc_tgs2611',
    'adc_tgs2620', 'adc_tgs2600', 'adc_tgs2602', 'adc_mq8',
    'adc_tgs813', 'adc_tgs816'
]

# Set page config
st.set_page_config(
    page_title="☕ E-Nose Roast Trainer",
    page_icon="☕",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Dark-theme and custom styling injection
st.markdown("""
<style>
    .reportview-container {
        background: #0F172A;
    }
    .metric-card {
        background-color: #1E293B;
        padding: 22px;
        border-radius: 16px;
        text-align: center;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
        margin-bottom: 20px;
        border: 1px solid #334155;
    }
    .cv-card {
        border-left: 6px solid #10B981;
        box-shadow: 0 4px 15px rgba(16, 185, 129, 0.15);
    }
    .test-card {
        border-left: 6px solid #F59E0B;
        box-shadow: 0 4px 15px rgba(245, 158, 11, 0.15);
    }
    .feat-card {
        border-left: 6px solid #3B82F6;
        box-shadow: 0 4px 15px rgba(59, 130, 246, 0.15);
    }
    .metric-value {
        font-size: 34px;
        font-weight: bold;
    }
    .cv-card .metric-value {
        color: #10B981;
    }
    .test-card .metric-value {
        color: #F59E0B;
    }
    .feat-card .metric-value {
        color: #3B82F6;
    }
    .metric-label {
        font-size: 14px;
        font-weight: 500;
        color: #94A3B8;
        margin-top: 8px;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_raw_data():
    csv_files = glob.glob(os.path.join(DATA_DIR, '*.csv'))
    skip = ['dataset_fitur', 'dataset_interactive', 'anomal']
    csv_files = [f for f in csv_files if not any(p in os.path.basename(f).lower() for p in skip)]
    
    if not csv_files:
        return None
        
    import re
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
                df['batch_id'] = m.group(1).upper() if m else 'Legacy / Lainnya'
            else:
                df['batch_id'] = df['batch_id'].astype(str).str.strip().str.upper()
                
            dfs.append(df)
        except Exception as e:
            pass
            
    if not dfs:
        return None
    return pd.concat(dfs, ignore_index=True)

def extract_features(df_all, selected_features):
    df_col = df_all[df_all['phase'] == 'collecting'].copy()
    
    if df_col.empty:
        return None
        
    df_col = df_col[df_col['label'].isin(['light', 'medium', 'dark'])].copy()
    if df_col.empty:
        return None
        
    for col in ADC_COLS:
        df_col[col] = pd.to_numeric(df_col[col], errors='coerce').fillna(0)
        
    if 'cycle' not in df_col.columns:
        df_col['cycle'] = 1
        
    group_keys = ['source_file', 'batch_id', 'label', 'cycle']
    available_keys = [k for k in group_keys if k in df_col.columns]
    
    rows = []
    for keys, group in df_col.groupby(available_keys):
        key_dict = dict(zip(available_keys, keys if isinstance(keys, tuple) else (keys,)))
        
        row = {
            'source_file': key_dict.get('source_file', '?'),
            'batch_id': key_dict.get('batch_id', '?'),
            'label': key_dict.get('label', '?'),
            'cycle': key_dict.get('cycle', 1)
        }
        
        # Base Mean & Max
        for col in ADC_COLS:
            vals = group[col].values
            row[f'mean_{col}'] = float(np.mean(vals))
            row[f'max_{col}'] = float(np.max(vals))
            
            if 'AUC (Sum)' in selected_features:
                row[f'sum_{col}'] = float(np.sum(vals))
            if 'Skewness' in selected_features:
                series = pd.Series(vals)
                row[f'skew_{col}'] = float(series.skew()) if len(vals) > 2 and series.std() > 0 else 0.0
            if 'Kurtosis' in selected_features:
                series = pd.Series(vals)
                row[f'kurt_{col}'] = float(series.kurt()) if len(vals) > 3 and series.std() > 0 else 0.0
                
        # Ratios
        if 'Ratios to MQ135' in selected_features:
            mq135_max = row['max_adc_mq135'] if row['max_adc_mq135'] > 0 else 1.0
            for col in ADC_COLS:
                if col != 'adc_mq135':
                    row[f'ratio_to_mq135_{col}'] = row[f'max_{col}'] / mq135_max
                    
        if 'Ratios to TGS822' in selected_features:
            tgs822_max = row['max_adc_tgs822'] if row['max_adc_tgs822'] > 0 else 1.0
            for col in ADC_COLS:
                if col != 'adc_tgs822':
                    row[f'ratio_to_tgs822_{col}'] = row[f'max_{col}'] / tgs822_max
                    
        rows.append(row)
        
    return pd.DataFrame(rows)

def main():
    # Gradient title
    st.markdown("""
        <h1 style='background: linear-gradient(90deg, #F59E0B, #10B981, #3B82F6, #EC4899); 
                    -webkit-background-clip: text; -webkit-text-fill-color: transparent; 
                    font-size: 40px; font-weight: 800; margin-bottom: 5px;'>
            ☕ E-Nose Coffee Roast Trainer Dashboard
        </h1>
        <p style='color: #94A3B8; font-size: 16px; margin-bottom: 15px;'>
            Eksplorasi data sensor E-Nose secara visual, pilih database batch pembanding, latih model Random Forest (TinyML), dan ekspor C++ header.
        </p>
    """, unsafe_allow_html=True)
    
    df_raw = load_raw_data()
    if df_raw is None:
        st.error("❌ Tidak ada file CSV raw ditemukan di folder data/.")
        st.stop()
        
    # ── Sidebar: Pemilihan Database Batch Pembanding ──
    st.sidebar.markdown("### 📁 Database Pembanding (Multi-Batch)")
    
    # Ambil list batch unik
    all_batches_raw = df_raw['batch_id'].dropna().unique().tolist()
    all_batches = sorted(all_batches_raw, key=lambda x: (x.startswith('Legacy'), x))
    
    # Mode pemilihan batch (Dapat memilih lebih dari 1 batch)
    batch_mode = st.sidebar.radio(
        "Mode Pemilihan Batch:",
        options=[
            "🎯 Multi-Batch (Pilih Lebih Dari 1 Batch)",
            "⭐ Hanya Batch 10 (Rekomendasi - 21 File)",
            "🌐 Semua Batch (Gabungan Seluruh Database)"
        ],
        index=0,
        help="Pilih satu atau beberapa batch datasheet untuk digabungkan sebagai database pembanding klasifikasi."
    )
    
    if batch_mode.startswith("⭐ Hanya Batch 10"):
        active_batches = ["B10"] if "B10" in all_batches else [all_batches[0]]
    elif batch_mode.startswith("🌐 Semua Batch"):
        active_batches = all_batches
    else:
        active_batches = st.sidebar.multiselect(
            "Pilih Batch-Batch Aktif:",
            options=all_batches,
            default=["B10"] if "B10" in all_batches else [all_batches[0]],
            help="Pilih satu atau lebih batch sekaligus untuk digabungkan."
        )
        
    if not active_batches:
        st.sidebar.warning("⚠️ Harap pilih minimal 1 batch pembanding!")
        st.stop()
        
    # Filter dataset mentah sesuai batch yang dipilih
    df_filtered_raw = df_raw[df_raw['batch_id'].isin(active_batches)].copy()
    n_active_files = df_filtered_raw['source_file'].nunique()
    
    # Status card di sidebar
    batches_display = ", ".join(active_batches) if len(active_batches) <= 4 else f"{len(active_batches)} Batch Terpilih"
    st.sidebar.markdown(f"""
    <div style="background-color: #1E293B; border: 1px solid #334155; border-radius: 12px; padding: 12px 16px; margin-bottom: 20px;">
        <div style="font-size: 11px; color: #94A3B8; text-transform: uppercase; font-weight: bold; letter-spacing: 0.5px;">Batch Pembanding Aktif</div>
        <div style="font-size: 16px; font-weight: bold; color: #38BDF8; margin-top: 3px;">{batches_display}</div>
        <div style="font-size: 12px; color: #E2E8F0; margin-top: 4px;">
            📄 <b>{n_active_files}</b> file datasheet CSV
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar config
    st.sidebar.header("⚙️ Konfigurasi Model")
    
    # Hyperparameters
    n_estimators = st.sidebar.slider("Jumlah Pohon (n_estimators)", min_value=1, max_value=25, value=12)
    max_depth = st.sidebar.slider("Kedalaman Maks (max_depth)", min_value=1, max_value=10, value=5)
    test_size = st.sidebar.slider("Rasio Data Test (%)", min_value=10, max_value=40, value=20) / 100.0
    
    # Feature Selectors
    st.sidebar.subheader("🔌 Fitur Ekstraksi")
    feature_options = ["AUC (Sum)", "Ratios to MQ135", "Ratios to TGS822", "Skewness", "Kurtosis"]
    selected_features = st.sidebar.multiselect(
        "Pilih Fitur Tambahan (Mean & Max aktif otomatis):",
        options=feature_options,
        default=["AUC (Sum)", "Ratios to MQ135", "Ratios to TGS822"]
    )
    
    # Trigger Feature Extraction hanya dari batch yang dipilih
    df_feat = extract_features(df_filtered_raw, selected_features)
    if df_feat is None or df_feat.empty:
        st.error(f"Gagal melakukan ekstraksi fitur untuk batch: {', '.join(active_batches)}.")
        st.stop()
        
    n_active_samples = len(df_feat)
    
    # Tampilkan banner status database pembanding di atas layar utama
    st.markdown(f"""
    <div style="background: linear-gradient(90deg, #1E293B, #0F172A); border-left: 6px solid #38BDF8; border-radius: 12px; padding: 14px 20px; margin-bottom: 22px; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 4px 15px rgba(0,0,0,0.2);">
        <div>
            <span style="background: #2563EB; color: #FFFFFF; font-size: 11px; font-weight: bold; padding: 3px 8px; border-radius: 4px; margin-right: 8px;">DATABASE PEMBANDING</span>
            <span style="color: #F8FAFC; font-weight: 600; font-size: 15px;">Batch Aktif: <span style="color: #38BDF8; font-weight: bold;">{batches_display}</span></span>
        </div>
        <div style="color: #94A3B8; font-size: 13px;">
            📄 <b>{n_active_files} File CSV</b> &nbsp;|&nbsp; 🔄 <b>{n_active_samples} Siklus Sampel</b> &nbsp;|&nbsp; 🟢 <span style="color: #10B981; font-weight: 600;">Siap Sebagai Acuan Klasifikasi</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Build list of feature columns
    base_cols = [f'mean_{c}' for c in ADC_COLS] + [f'max_{c}' for c in ADC_COLS]
    added_cols = []
    if 'AUC (Sum)' in selected_features:
        added_cols += [f'sum_{c}' for c in ADC_COLS]
    if 'Skewness' in selected_features:
        added_cols += [f'skew_{c}' for c in ADC_COLS]
    if 'Kurtosis' in selected_features:
        added_cols += [f'kurt_{c}' for c in ADC_COLS]
    if 'Ratios to MQ135' in selected_features:
        added_cols += [f'ratio_to_mq135_{c}' for c in ADC_COLS if c != 'adc_mq135']
    if 'Ratios to TGS822' in selected_features:
        added_cols += [f'ratio_to_tgs822_{c}' for c in ADC_COLS if c != 'adc_tgs822']
        
    feature_cols = base_cols + added_cols
    
    # Initialize session state for training output
    if 'trained' not in st.session_state:
        st.session_state.trained = False
        
    # Sidebar Training Button
    if st.sidebar.button("Latih & Evaluasi Model", use_container_width=True):
        with st.spinner("Melatih model Random Forest..."):
            X = df_feat[feature_cols].fillna(0).to_numpy(dtype=np.float32)
            y = df_feat['label'].astype(str).to_numpy()
            
            # 1. 5-Fold Cross Validation
            cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
            clf_cv = RandomForestClassifier(
                n_estimators=n_estimators,
                max_depth=max_depth,
                random_state=42,
                class_weight='balanced'
            )
            scores = cross_val_score(clf_cv, X, y, cv=cv, scoring='accuracy')
            st.session_state.cv_acc = scores.mean() * 100
            st.session_state.cv_std = scores.std() * 100
            
            # 2. Train Test Split & Final Fit
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=test_size, stratify=y, random_state=42
            )
            clf = RandomForestClassifier(
                n_estimators=n_estimators,
                max_depth=max_depth,
                random_state=42,
                class_weight='balanced'
            )
            clf.fit(X_train, y_train)
            
            y_pred = clf.predict(X_test)
            st.session_state.test_acc = accuracy_score(y_test, y_pred) * 100
            
            # Confusion matrix
            labels_order = sorted(list(set(y)))
            st.session_state.cm = confusion_matrix(y_test, y_pred, labels=labels_order)
            st.session_state.labels_order = labels_order
            
            # Feature Importance
            importances = pd.Series(clf.feature_importances_, index=feature_cols)
            top_10 = importances.sort_values(ascending=False).head(10)
            st.session_state.top_10_names = top_10.index.tolist()
            st.session_state.top_10_vals = top_10.values.tolist()
            
            # Classification report
            rep = classification_report(y_test, y_pred, output_dict=True, zero_division=0)
            st.session_state.rep_df = pd.DataFrame(rep).transpose()
            
            # Save dataset_fitur.csv dan model joblib
            OUTPUT_CSV = os.path.join(DATA_DIR, 'dataset_fitur.csv')
            df_feat.to_csv(OUTPUT_CSV, index=False)
            joblib.dump(clf, MODEL_PATH)
            
            st.session_state.active_batches_trained = batches_display
            st.session_state.trained = True
            st.success(f"✓ Model Random Forest berhasil dilatih pada database: {batches_display}!")
            
    # Create Tabs
    tab1, tab2 = st.tabs(["Dataset Explorer (Tampilan Awal)", "Model Training & Evaluation"])
    
    # ── Tab 1: Dataset Explorer ──
    with tab1:
        st.markdown(f"### 🔍 Eksplorasi Data E-Nose Kopi — Batch: <span style='color:#38BDF8;'>{batches_display}</span>", unsafe_allow_html=True)
        explore_col1, explore_col2 = st.columns([1, 1.8])
        
        with explore_col1:
            st.markdown(f"**Distribusi Kelas ({len(df_feat)} Sampel Siklus):**")
            # Coffee themed colors
            COLORS = {"light": "#E6A23C", "medium": "#3B82F6", "dark": "#593A2E"}
            counts = df_feat['label'].value_counts()
            
            fig, ax = plt.subplots(figsize=(6, 4))
            fig.patch.set_facecolor('#1E293B')
            ax.set_facecolor('#1E293B')
            
            colors_list = [COLORS.get(label, '#ffffff') for label in counts.index]
            bars = ax.bar(counts.index, counts.values, color=colors_list, edgecolor='#475569', width=0.5)
            ax.set_ylabel('Jumlah Siklus', color='white', fontsize=12)
            ax.tick_params(colors='white', labelsize=11)
            for spine in ax.spines.values():
                spine.set_edgecolor('#475569')
            
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2.0, height + 0.5, f'{int(height)}', 
                        ha='center', va='bottom', color='white', fontweight='bold')
            st.pyplot(fig)
            
            # Ringkasan per label
            label_summary = " &bull; ".join([f"<b>{k.upper()}:</b> {v}" for k, v in counts.items()])
            st.markdown(f"""
            <div style="background-color: #1E293B; border: 1px solid #334155; border-radius: 8px; padding: 10px 14px; font-size: 13px; color: #CBD5E1;">
                {label_summary}
            </div>
            """, unsafe_allow_html=True)
            
        with explore_col2:
            st.markdown("**Grafik Kurva Respons Sensor Gas (Real-Time curves):**")
            all_csvs = glob.glob(os.path.join(DATA_DIR, '*.csv'))
            skip = ['dataset_fitur', 'dataset_interactive', 'anomal']
            all_csvs = [f for f in all_csvs if not any(p in os.path.basename(f).lower() for p in skip)]
            
            # Hanya ambil file dari datasheet / batch pembanding yang aktif
            active_filenames = set(df_filtered_raw['source_file'].dropna().unique())
            active_csvs = [f for f in all_csvs if os.path.basename(f) in active_filenames]
            active_csvs = sorted(active_csvs, key=lambda x: os.path.basename(x))
            
            if active_csvs:
                selected_file_path = st.selectbox(
                    "Pilih File CSV Kopi (Datasheet Aktif):", 
                    options=active_csvs,
                    format_func=lambda fpath: os.path.basename(fpath)
                )
                df_sample = pd.read_csv(selected_file_path)
                
                # Plot the 10 sensors
                fig, ax = plt.subplots(figsize=(10, 5.5))
                fig.patch.set_facecolor('#1E293B')
                ax.set_facecolor('#1E293B')
                
                # Vibrant custom colors for sensors
                sensor_colors = {
                    'adc_tgs822': '#00E676', 'adc_mq135': '#FF6D00', 'adc_mq3': '#FF3D00', 
                    'adc_tgs2611': '#00BFA5', 'adc_tgs2620': '#18FFFF', 'adc_tgs2600': '#64FFDA', 
                    'adc_tgs2602': '#A7FFEB', 'adc_mq8': '#FFAB00', 'adc_tgs813': '#B2FF59', 
                    'adc_tgs816': '#76FF03'
                }
                
                for col in ADC_COLS:
                    if col in df_sample.columns:
                        ax.plot(df_sample[col], label=col.replace('adc_', '').upper(), 
                                color=sensor_colors.get(col, '#ffffff'), linewidth=2)
                        
                ax.set_xlabel('Waktu (Detik / Indeks Sampel)', color='white', fontsize=12)
                ax.set_ylabel('Nilai ADC', color='white', fontsize=12)
                ax.tick_params(colors='white', labelsize=10)
                ax.grid(True, linestyle='--', alpha=0.2, color='#94A3B8')
                ax.legend(facecolor='#1E293B', edgecolor='#475569', labelcolor='white', 
                          bbox_to_anchor=(1.02, 1), loc='upper left')
                plt.tight_layout()
                st.pyplot(fig)
            else:
                st.warning("Tidak ada file datasheet CSV yang cocok dengan batch aktif saat ini.")
                
    # ── Tab 2: Training & Evaluation ──
    with tab2:
        st.markdown(f"**Database Pembanding:** `{batches_display}` &nbsp;|&nbsp; **Jumlah Fitur Aktif:** `{len(feature_cols)}` fitur.")
        if st.session_state.trained:
            trained_batch = getattr(st.session_state, 'active_batches_trained', batches_display)
            st.info(f"ℹ️ Model Random Forest aktif saat ini dilatih dengan database pembanding: **{trained_batch}** ({len(df_feat)} siklus sampel).")
        
        if st.session_state.trained:
            # Layout splits
            col1, col2, col3 = st.columns(3)
            
            # Display KPI cards
            with col1:
                st.markdown(f"""
                <div class="metric-card cv-card">
                    <div class="metric-value">{st.session_state.cv_acc:.2f}%</div>
                    <div class="metric-label">Cross-Validation Accuracy (± {st.session_state.cv_std:.2f}%)</div>
                </div>
                """, unsafe_allow_html=True)
                
            with col2:
                st.markdown(f"""
                <div class="metric-card test-card">
                    <div class="metric-value">{st.session_state.test_acc:.2f}%</div>
                    <div class="metric-label">Test Set Accuracy</div>
                </div>
                """, unsafe_allow_html=True)
                
            with col3:
                st.markdown(f"""
                <div class="metric-card feat-card">
                    <div class="metric-value">{len(feature_cols)}</div>
                    <div class="metric-label">Jumlah Fitur Masukan</div>
                </div>
                """, unsafe_allow_html=True)
                
            # Display evaluation plots & metrics
            st.markdown("### 📊 Hasil Analisis Model")
            chart_col1, chart_col2 = st.columns(2)
            
            with chart_col1:
                st.markdown("**Confusion Matrix**")
                fig, ax = plt.subplots(figsize=(6, 5))
                fig.patch.set_facecolor('#1E293B')
                ax.set_facecolor('#1E293B')
                sns.heatmap(st.session_state.cm, annot=True, fmt='d', cmap='plasma',
                            xticklabels=st.session_state.labels_order, 
                            yticklabels=st.session_state.labels_order, ax=ax,
                            cbar=False, annot_kws={"size": 14, "weight": "bold"})
                ax.set_xlabel('Prediksi', color='white', fontsize=12, labelpad=10)
                ax.set_ylabel('Sebenarnya', color='white', fontsize=12, labelpad=10)
                ax.tick_params(colors='white', labelsize=11)
                for spine in ax.spines.values():
                    spine.set_edgecolor('#475569')
                st.pyplot(fig)
                
            with chart_col2:
                st.markdown("**10 Fitur Terpenting (Feature Importance)**")
                fig, ax = plt.subplots(figsize=(7, 5))
                fig.patch.set_facecolor('#1E293B')
                ax.set_facecolor('#1E293B')
                sns.barplot(x=st.session_state.top_10_vals, y=st.session_state.top_10_names, 
                            palette='plasma', ax=ax)
                ax.set_xlabel('Nilai Importance', color='white', fontsize=12, labelpad=10)
                ax.tick_params(colors='white', labelsize=10)
                ax.grid(axis='x', linestyle='--', alpha=0.3, color='#94A3B8')
                for spine in ax.spines.values():
                    spine.set_edgecolor('#475569')
                st.pyplot(fig)
                
            # Classification report
            st.markdown("**Classification Report**")
            st.dataframe(st.session_state.rep_df.style.format(precision=3), use_container_width=True)
            
            # C++ Compilation Check & Export Card
            st.markdown("---")
            st.markdown("### 🛠️ TinyML C++ Export Module (ATmega2560 / ESP32)")
            
            exp_col1, exp_col2 = st.columns([1, 2])
            with exp_col1:
                st.markdown("**Ekspor ke C++ Header:**")
                if st.button("Generate & Save model_rf_atmega.h", use_container_width=True):
                    success = export_model_atmega(MODEL_PATH, OUTPUT_HEADER, max_trees=n_estimators, max_depth=max_depth)
                    if success:
                        st.success(f"✓ File C++ header berhasil dibuat di {OUTPUT_HEADER}!")
                    else:
                        st.error("Gagal meng-export model ke C++.")
                        
            with exp_col2:
                if os.path.exists(OUTPUT_HEADER):
                    st.markdown("**Preview model_rf_atmega.h (25 baris pertama):**")
                    with open(OUTPUT_HEADER, 'r') as f:
                        lines = [f.readline() for _ in range(25)]
                    st.code("".join(lines), language='cpp')
                else:
                    st.info("Klik tombol di sebelah kiri untuk menghasilkan file header C++.")
        else:
            st.warning("👈 Silakan atur hyperparameter di sidebar dan klik **Latih & Evaluasi Model** untuk memulai melatih model dan melihat evaluasinya.")

if __name__ == '__main__':
    main()
