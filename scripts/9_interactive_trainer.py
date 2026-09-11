"""
9_interactive_trainer.py
═══════════════════════════════════════════════════════════════════════════════
Interactive Active Learning -- E-NOSE Kopi

Sinkron dengan fitur 4_train_rf.py:
  - Menggunakan skema fitur dari 4_train_rf.py (membaca data/feature_list.json)
  - Mendukung 89 Fitur Teroptimasi (Mean, Max, Std, Peak-to-Base, Onset & Decay Transitions)
  - Merekam sampel purging (baseline), collecting (onset + mean/max/std), dan decay
  - Retrain otomatis dan update model C++ header

Alur Kerja:
  1. Hubungkan ke mikrokontroler via Serial
  2. Jalankan 1 siklus akuisisi (purging -> collecting -> decay)
  3. Ekstraksi fitur yang sinkron dengan 4_train_rf.py
  4. Model menebak tingkat roasting kopi
  5. User konfirmasi / koreksi label
  6. Data disimpan ke dataset_interactive.csv
  7. Model di-retrain otomatis dan export ke model_rf_atmega.h

Cara Pakai:
  python scripts/9_interactive_trainer.py
  python scripts/9_interactive_trainer.py --port COM18
═══════════════════════════════════════════════════════════════════════════════
"""

import argparse
import glob
import json
import os
import re
import sys
import time
from datetime import datetime
import threading

import numpy as np
import pandas as pd
from scipy import stats as sp_stats
import joblib

import serial
import serial.tools.list_ports
from serial import Serial

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.metrics import accuracy_score, classification_report

# ─── Path Konfigurasi ────────────────────────────────────────────────────────
SCRIPTS_DIR       = os.path.dirname(os.path.abspath(__file__))
BASE_DIR          = os.path.normpath(os.path.join(SCRIPTS_DIR, '..'))
DATA_DIR          = os.path.join(BASE_DIR, 'data')
INCLUDE_DIR       = os.path.join(BASE_DIR, 'include')
MODEL_PATH        = os.path.join(DATA_DIR, 'model_rf.joblib')
BATCH_DATASET     = os.path.join(DATA_DIR, 'dataset_fitur.csv')
INTERACTIVE_CSV   = os.path.join(DATA_DIR, 'dataset_interactive.csv')
OUTPUT_HEADER     = os.path.join(INCLUDE_DIR, 'model_rf_atmega.h')
FEAT_JSON         = os.path.join(DATA_DIR, 'feature_list.json')

BAUD_RATE         = 115200
VALID_LABELS      = ['light', 'medium', 'dark']

ADC_COLS = [
    'adc_tgs822', 'adc_mq135', 'adc_mq3', 'adc_tgs2611', 'adc_tgs2620',
    'adc_tgs2600', 'adc_tgs2602', 'adc_mq8', 'adc_tgs813', 'adc_tgs816'
]

RF_N_ESTIMATORS = 12
RF_MAX_DEPTH    = 5
RF_RANDOM_STATE = 42

ONSET_WINDOW = 20
DECAY_WINDOW = 20


# ═════════════════════════════════════════════════════════════════════════════
#  UTILITAS & SINKRONISASI FITUR DENGAN 4_train_rf.py
# ═════════════════════════════════════════════════════════════════════════════

def get_active_features():
    """Membaca daftar fitur aktif dari data/feature_list.json (dibuat oleh 4_train_rf.py)."""
    if os.path.exists(FEAT_JSON):
        try:
            with open(FEAT_JSON, 'r') as f:
                meta = json.load(f)
            features = meta.get('features', [])
            mode = meta.get('mode', 'optimized')
            if features:
                return features, mode
        except Exception:
            pass

    # Fallback default ke 89 fitur teroptimasi
    cols = (
        [f'mean_{c}' for c in ADC_COLS] +
        [f'max_{c}' for c in ADC_COLS] +
        [f'std_{c}' for c in ADC_COLS] +
        [f'peak_to_base_{c}' for c in ADC_COLS] +
        [f'ratio_to_mq135_{c}' for c in ADC_COLS if c != 'adc_mq135'] +
        [f'onset_{c}_{s}' for c in ADC_COLS for s in ['slope', 'rise_drop']] +
        [f'decay_{c}_{s}' for c in ADC_COLS for s in ['slope', 'rise_drop']]
    )
    return cols, 'optimized'


def clear_line():
    print('\r' + ' ' * 80 + '\r', end='', flush=True)


def print_header(mode_name, n_feats):
    print()
    print("+--------------------------------------------------------------+")
    print("|   E-NOSE Kopi -- Interactive Active Learning Trainer         |")
    print(f"|   Sinkron dengan 4_train_rf.py: {mode_name.upper():<10} ({n_feats} Fitur)     |")
    print("+--------------------------------------------------------------+")
    print()


def find_serial_port(preferred=None):
    if preferred:
        return preferred

    try:
        import serial.tools.list_ports
        ports = list(serial.tools.list_ports.comports())
    except Exception:
        ports = []

    if not ports:
        port = input("Masukkan nama port Serial (misal COM18): ").strip()
        return port

    print("Port Serial yang tersedia:")
    for i, p in enumerate(ports):
        print(f"  [{i}] {p.device}  - {p.description}")

    idx = input("Pilih nomor port (atau ketik nama port langsung): ").strip()
    try:
        num = int(idx)
        if 0 <= num < len(ports):
            return ports[num].device
    except ValueError:
        pass
    return idx.strip()


# ═════════════════════════════════════════════════════════════════════════════
#  AKUISISI SERIAL (MEREKAM PURGING + COLLECTING + DECAY)
# ═════════════════════════════════════════════════════════════════════════════

def run_single_cycle(ser):
    """
    Menjalankan 1 siklus 3-tahap di terminal (CLI):
      Tahap 1: COLLECTING 1 (120 detik)
      Tahap 2: PURGING (120 detik)
      Tahap 3: COLLECTING 2 (120 detik)
    Total durasi: 360 detik.
    """
    collecting1_samples = []
    purging_samples = []
    collecting2_samples = []

    current_stage = 'COLLECT_1'
    stage_duration = 120
    stage_start = time.time()
    total_start = stage_start

    ser.reset_input_buffer()
    time.sleep(0.2)
    ser.write(b'#start;')

    print("\n" + "="*70)
    print("  [MULAI] PENGUJIAN 3-TAHAP (Total 360 Detik)")
    print("  Alur: [1] Collect 120s -> [2] Purge 120s -> [3] Collect 120s -> AI Predict")
    print("="*70)

    while True:
        try:
            raw = ser.readline()
            if not raw:
                continue

            line = raw.decode('utf-8', errors='ignore').strip()
            if not line:
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            if any(k in data for k in ADC_COLS):
                sample = {col: float(data.get(col, 0)) for col in ADC_COLS}
                now_str = datetime.now().strftime("%H:%M:%S WIB")
                elapsed_stage = int(time.time() - stage_start)
                rem_stage = max(0, stage_duration - elapsed_stage)
                total_elapsed = int(time.time() - total_start)

                bar_len = 20
                prog = min(1.0, elapsed_stage / stage_duration)
                filled = int(bar_len * prog)
                bar = '#' * filled + '-' * (bar_len - filled)

                clear_line()

                # ── Tahap 1: COLLECTING 1 (120s) ──
                if current_stage == 'COLLECT_1':
                    collecting1_samples.append(sample)
                    print(f"[{now_str}] 🟢 COLLECTING 1 [{bar}] Sisa: {rem_stage:>3}s ({elapsed_stage:>3}s/120s) | Sampel: {len(collecting1_samples)}", end='', flush=True)

                    if elapsed_stage >= stage_duration or len(collecting1_samples) >= stage_duration:
                        current_stage = 'PURGE'
                        stage_start = time.time()
                        print(f"\n[{now_str}] 🔴 Transisi ke FASE 2: PURGING (Membersihkan chamber 120s)...")

                # ── Tahap 2: PURGING (120s) ──
                elif current_stage == 'PURGE':
                    purging_samples.append(sample)
                    print(f"[{now_str}] 🔴 PURGING      [{bar}] Sisa: {rem_stage:>3}s ({elapsed_stage:>3}s/120s) | Sampel: {len(purging_samples)}", end='', flush=True)

                    if elapsed_stage >= stage_duration or len(purging_samples) >= stage_duration:
                        current_stage = 'COLLECT_2'
                        stage_start = time.time()
                        print(f"\n[{now_str}] 🟢 Transisi ke FASE 3: COLLECTING 2 (Menghirup kembali aroma 120s)...")

                # ── Tahap 3: COLLECTING 2 (120s) ──
                elif current_stage == 'COLLECT_2':
                    collecting2_samples.append(sample)
                    print(f"[{now_str}] 🟢 COLLECTING 2 [{bar}] Sisa: {rem_stage:>3}s ({elapsed_stage:>3}s/120s) | Sampel: {len(collecting2_samples)}", end='', flush=True)

                    if elapsed_stage >= stage_duration or len(collecting2_samples) >= stage_duration:
                        ser.write(b'#stop;')
                        time.sleep(0.3)
                        ser.reset_input_buffer()
                        print("\n\n[OK] Siklus 360s Selesai Tuntas!")
                        print(f"     Collect 1: {len(collecting1_samples)} sampel | Purge: {len(purging_samples)} sampel | Collect 2: {len(collecting2_samples)} sampel")
                        break

        except KeyboardInterrupt:
            print("\n[STOP] Dihentikan oleh user.")
            ser.write(b'#stop;')
            time.sleep(0.3)
            return None
        except Exception as e:
            print(f"\n[ERROR] Serial error: {e}")
            return None

    if len(collecting1_samples) < 5:
        print("[WARN] Terlalu sedikit sampel yang terekam.")
        return None

    return {
        'collecting1': collecting1_samples,
        'purging': purging_samples,
        'collecting2': collecting2_samples,
        'collecting': collecting1_samples + collecting2_samples,
        'decay': purging_samples
    }


# ═════════════════════════════════════════════════════════════════════════════
#  EKSTRAKSI FITUR (3-TAHAP: 120s - 120s - 120s)
# ═════════════════════════════════════════════════════════════════════════════

def extract_features_from_cycle(cycle_data):
    """
    Ekstraksi fitur lengkap dari siklus 3-tahap:
      - 120s Collecting 1 (onset aroma)
      - 120s Purging (decay & baseline pembersihan)
      - 120s Collecting 2 (re-adsorpsi & stabilitas)
    Total durasi: 360 detik.
    Kompatibel penuh dengan skema 89 fitur (optimized) dan 48 fitur (legacy).
    """
    c1 = cycle_data.get('collecting1', cycle_data.get('collecting', []))
    pu = cycle_data.get('purging', [])
    c2 = cycle_data.get('collecting2', cycle_data.get('decay', []))

    df_col1 = pd.DataFrame(c1)
    df_pur  = pd.DataFrame(pu)
    df_col2 = pd.DataFrame(c2)

    # Gabungan seluruh data uap aroma kopi (Collecting 1 + Collecting 2)
    if len(df_col2) > 0:
        df_col = pd.concat([df_col1, df_col2], ignore_index=True)
    else:
        df_col = df_col1

    row = {}

    # A. Mean, Max, Std (karakteristik intensitas uap kopi)
    for col in ADC_COLS:
        vals = pd.to_numeric(df_col[col], errors='coerce').fillna(0).to_numpy(dtype=float) if col in df_col and len(df_col) > 0 else np.zeros(1)
        row[f'mean_{col}'] = float(np.mean(vals))
        row[f'max_{col}']  = float(np.max(vals))
        row[f'std_{col}']  = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
        row[f'sum_{col}']  = float(np.sum(vals))  # untuk mode legacy

    # B. Peak-to-Baseline Ratio (relatif terhadap 15 sampel baseline purging)
    for col in ADC_COLS:
        if col in df_pur and len(df_pur) > 0:
            pb = pd.to_numeric(df_pur[col], errors='coerce').fillna(0).to_numpy(dtype=float)
            baseline = float(np.mean(pb[-15:])) if len(pb) >= 15 else float(np.mean(pb))
        else:
            baseline = 1.0
        peak = row[f'max_{col}']
        row[f'peak_to_base_{col}'] = (peak - baseline) / max(abs(baseline), 1.0)

    # C. Ratio ke MQ135
    mq135_max = row['max_adc_mq135'] if row['max_adc_mq135'] > 0 else 1.0
    for col in ADC_COLS:
        if col != 'adc_mq135':
            row[f'ratio_to_mq135_{col}'] = row[f'max_{col}'] / mq135_max

    # D. Ratio ke TGS822
    tgs822_max = row['max_adc_tgs822'] if row['max_adc_tgs822'] > 0 else 1.0
    for col in ADC_COLS:
        if col != 'adc_tgs822':
            row[f'ratio_to_tgs822_{col}'] = row[f'max_{col}'] / tgs822_max

    # E. Onset Transitions (20 sampel pertama saat mulai Collecting 1)
    w_on = min(ONSET_WINDOW, len(df_col1))
    t_on = np.arange(w_on, dtype=float)
    for col in ADC_COLS:
        if col in df_col1 and w_on > 1:
            seg = pd.to_numeric(df_col1[col], errors='coerce').fillna(0).to_numpy(dtype=float)[:w_on]
            row[f'onset_{col}_slope'] = float(sp_stats.linregress(t_on, seg)[0])
            fast_n = min(5, w_on)
            row[f'onset_{col}_rise_drop'] = float(seg[fast_n - 1] - seg[0])
        else:
            row[f'onset_{col}_slope'] = 0.0
            row[f'onset_{col}_rise_drop'] = 0.0

    # F. Decay Transitions (20 sampel awal saat Purging pembersihan)
    w_dec = min(DECAY_WINDOW, len(df_pur))
    t_dec = np.arange(w_dec, dtype=float)
    for col in ADC_COLS:
        if col in df_pur and w_dec > 1:
            seg = pd.to_numeric(df_pur[col], errors='coerce').fillna(0).to_numpy(dtype=float)[:w_dec]
            row[f'decay_{col}_slope'] = float(sp_stats.linregress(t_dec, seg)[0])
            fast_n = min(5, w_dec)
            row[f'decay_{col}_rise_drop'] = float(seg[fast_n - 1] - seg[0])
        else:
            row[f'decay_{col}_slope'] = 0.0
            row[f'decay_{col}_rise_drop'] = 0.0

    return row


def load_model():
    if os.path.exists(MODEL_PATH):
        try:
            return joblib.load(MODEL_PATH)
        except Exception as e:
            print(f"[WARN] Gagal memuat model: {e}")
    return None


def predict(clf, features, active_feature_cols):
    """Prediksi label berdasarkan fitur yang aktif pada model."""
    X = np.array([[features.get(col, 0.0) for col in active_feature_cols]], dtype=np.float32)
    pred = clf.predict(X)[0]

    proba = clf.predict_proba(X)[0]
    classes = clf.classes_
    conf = {str(c): float(p) for c, p in zip(classes, proba)}

    return str(pred), conf


def save_interactive_sample(features, label, session_id, cycle_num, active_feature_cols):
    """Menyimpan 1 sampel berlabel ke dataset_interactive.csv dengan alignment kolom yang benar."""
    row = {
        'source_file': f'interactive_{session_id}',
        'label': label,
        'cycle': cycle_num,
        'n_samples': features.get('n_samples', 180),
    }
    # Sertakan fitur aktif
    for col in active_feature_cols:
        row[col] = features.get(col, 0.0)

    df_new = pd.DataFrame([row])

    if os.path.exists(INTERACTIVE_CSV):
        df_old = pd.read_csv(INTERACTIVE_CSV)
        df_combined = pd.concat([df_old, df_new], ignore_index=True)
        df_combined.to_csv(INTERACTIVE_CSV, index=False)
    else:
        df_new.to_csv(INTERACTIVE_CSV, index=False)

    return True


def load_combined_dataset(active_feature_cols, batch_filter=None):
    dfs = []
    n_batch = 0
    if os.path.exists(BATCH_DATASET):
        df_batch = pd.read_csv(BATCH_DATASET)
        df_batch = df_batch[df_batch['label'].isin(VALID_LABELS)]
        
        # Terapkan filter batch pembanding jika ditentukan
        if batch_filter and batch_filter != "ALL" and batch_filter != ["ALL"]:
            if isinstance(batch_filter, str):
                target_batches = [batch_filter.upper()]
            else:
                target_batches = [str(b).upper() for b in batch_filter]

            if 'batch_id' in df_batch.columns:
                df_b_filtered = df_batch[df_batch['batch_id'].astype(str).str.upper().isin(target_batches)]
            elif 'source_file' in df_batch.columns:
                pattern = '|'.join(target_batches)
                df_b_filtered = df_batch[df_batch['source_file'].astype(str).str.contains(pattern, case=False, na=False)]
            else:
                df_b_filtered = df_batch
            if len(df_b_filtered) > 0:
                df_batch = df_b_filtered
                
        n_batch = len(df_batch)
        if n_batch > 0:
            dfs.append(df_batch)

    n_interactive = 0
    if os.path.exists(INTERACTIVE_CSV):
        df_inter = pd.read_csv(INTERACTIVE_CSV)
        df_inter = df_inter[df_inter['label'].isin(VALID_LABELS)]
        n_interactive = len(df_inter)
        if n_interactive > 0:
            dfs.append(df_inter)

    if not dfs:
        return None, None, 0, 0

    df_all = pd.concat(dfs, ignore_index=True)

    available_cols = [c for c in active_feature_cols if c in df_all.columns]
    X = df_all[available_cols].fillna(0).to_numpy(dtype=np.float32)
    y = df_all['label'].astype(str).to_numpy()

    return X, y, n_batch, n_interactive


def retrain_model(active_feature_cols, batch_filter=None):
    X, y, n_batch, n_interactive = load_combined_dataset(active_feature_cols, batch_filter=batch_filter)

    if X is None or len(X) < 4:
        print(f"[WARN] Dataset terlalu kecil ({0 if X is None else len(X)} sampel).")
        return None

    total = len(X)
    print(f"\n[INFO] Dataset gabungan: {total} sampel (batch={n_batch}, interaktif={n_interactive})")

    unique, counts = np.unique(y, return_counts=True)
    for label, count in zip(unique, counts):
        print(f"   {label:>8}: {count} sampel")

    clf = RandomForestClassifier(
        n_estimators=RF_N_ESTIMATORS,
        max_depth=RF_MAX_DEPTH,
        random_state=RF_RANDOM_STATE,
        class_weight='balanced'
    )

    cv_acc = 0.0
    cv_std = 0.0
    if total >= 6 and len(unique) >= 2 and min(counts) >= 2:
        n_splits = min(5, min(counts))
        cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=RF_RANDOM_STATE)
        scores = cross_val_score(clf, X, y, cv=cv, scoring='accuracy')
        cv_acc = scores.mean() * 100
        cv_std = scores.std() * 100
        print(f"[CV 5-Fold] Akurasi: {cv_acc:.2f}% ± {cv_std:.2f}%")

    clf.fit(X, y)
    joblib.dump(clf, MODEL_PATH)
    print(f"[SIMPAN] Model disimpan: {MODEL_PATH}")

    # Export C++ Header
    try:
        sys.path.insert(0, SCRIPTS_DIR)
        from generate_model_atmega import export_model_atmega
        export_model_atmega(MODEL_PATH, OUTPUT_HEADER,
                            max_trees=RF_N_ESTIMATORS, max_depth=RF_MAX_DEPTH)
        print(f"[EXPORT] Header C++ diekspor: {OUTPUT_HEADER}")
    except Exception as e:
        print(f"[WARN] Export C++: {e}")

    return clf, cv_acc, cv_std, total


# ═════════════════════════════════════════════════════════════════════════════
#  MAIN INTERACTIVE LOOP
# ═════════════════════════════════════════════════════════════════════════════

# ═════════════════════════════════════════════════════════════════════════════
#  GUI MONITOR (HUMAN-MACHINE INTERFACE DESKTOP)
# ═════════════════════════════════════════════════════════════════════════════

def run_gui(active_features, mode_name):
    """Menjalankan antarmuka grafis (GUI Desktop) langsung dari script ini."""
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox, scrolledtext
        import matplotlib
        matplotlib.use('TkAgg')
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    except ImportError as e:
        print(f"[ERR] Library GUI belum lengkap: {e}. Menjalankan mode CLI...")
        return False

    class LightNavigationToolbar(NavigationToolbar2Tk):
        """Toolbar navigasi Matplotlib bertema putih/bersih yang serasi dengan UI."""
        def __init__(self, canvas, window):
            super().__init__(canvas, window)
            try:
                self.configure({'background': '#FFFFFF'})
                if hasattr(self, '_message_label'):
                    self._message_label.configure({'background': '#FFFFFF', 'foreground': '#475569'})
                for child in self.winfo_children():
                    try:
                        child.configure({'background': '#FFFFFF'})
                    except Exception:
                        pass
            except Exception:
                pass

    # Alias agar kompatibel ke belakang
    DarkNavigationToolbar = LightNavigationToolbar

    sensor_colors = {
        'adc_tgs822':  '#E11D48', 'adc_mq135':   '#EA580C', 'adc_mq3':     '#D97706',
        'adc_tgs2611': '#059669', 'adc_tgs2620': '#0891B2', 'adc_tgs2600': '#2563EB',
        'adc_tgs2602': '#4F46E5', 'adc_mq8':     '#7C3AED', 'adc_tgs813':  '#C026D3',
        'adc_tgs816':  '#65A30D'
    }
    label_colors = {'light': '#D97706', 'medium': '#059669', 'dark': '#2563EB'}

    class ScrollableFrame(tk.Frame):
        """Container Frame Tkinter yang mendukung vertical scrollbar dan mousewheel scrolling otomatis."""
        def __init__(self, parent, bg="#FFFFFF", width=None, *args, **kwargs):
            super().__init__(parent, bg=bg, *args, **kwargs)
            if width:
                self.configure(width=width)
                self.pack_propagate(False)

            # PENTING: Scrollbar HARUS di-pack terlebih dahulu sebelum canvas agar tidak terdorong keluar layar
            self.scrollbar = ttk.Scrollbar(self, orient="vertical")
            self.scrollbar.pack(side="right", fill="y")

            self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, borderwidth=0)
            self.canvas.pack(side="left", fill="both", expand=True)

            self.canvas.configure(yscrollcommand=self.scrollbar.set)
            self.scrollbar.configure(command=self.canvas.yview)

            self.content = tk.Frame(self.canvas, bg=bg)
            self.window_id = self.canvas.create_window((0, 0), window=self.content, anchor="nw")

            self.content.bind("<Configure>", self._on_content_configure)
            self.canvas.bind("<Configure>", self._on_canvas_resize)

            # Global mousewheel listener dengan deteksi bounding box pointer
            self.bind_all("<MouseWheel>", self._on_mousewheel, add="+")

        def _on_content_configure(self, event):
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))

        def _on_canvas_resize(self, event):
            self.canvas.itemconfig(self.window_id, width=event.width)

        def _on_mousewheel(self, event):
            if not self.winfo_exists() or not self.canvas.winfo_exists():
                return
            try:
                x = event.x_root
                y = event.y_root
                rx = self.winfo_rootx()
                ry = self.winfo_rooty()
                rw = self.winfo_width()
                rh = self.winfo_height()
                if rx <= x <= rx + rw and ry <= y <= ry + rh:
                    # Jangan override jika kursor berada tepat di dalam kotak Text / ScrolledText independen
                    widget = self.winfo_containing(x, y)
                    if widget and isinstance(widget, (tk.Text, scrolledtext.ScrolledText)):
                        return
                    # Step 2 unit per notch mousewheel agar scrolling terasa lincah dan responsif
                    step = int(-1 * (event.delta / 120)) * 2
                    self.canvas.yview_scroll(step, "units")
            except Exception:
                pass

    class ENoseTrainerGUI(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title("Smart Coffee E-Nose - Interactive Active Learning Trainer")
            self.geometry("1380x820")
            self.minsize(1000, 600)
            self.configure(bg="#F8FAFC")

            self.ser = None
            self.serial_thread = None
            self.is_connected = False
            self.is_acquiring = False

            # Status Siklus 3-Tahap (120s - 120s - 120s)
            self.acq_stage = "IDLE"  # "COLLECT_1", "PURGE", "COLLECT_2", "DONE"
            self.stage_duration = 120
            self.stage_start_time = 0
            self.total_start_time = 0

            self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.cycle_count = 0
            self.current_features = None

            # Multi-channel visualizer buffer (360 detik) & status zoom
            self.max_plot_len = 360
            self.plot_time = []
            self.plot_data = {col: [] for col in ADC_COLS}
            self.auto_fit_oscilloscope = True

            # Buffer Sampel 3-Tahap
            self.collecting1_samples = []
            self.purging_samples = []
            self.collecting2_samples = []

            self.current_page = "live"
            self.nav_buttons = {}

            self.clf = load_model()
            self._build_ui()
            self._update_metrics_display()
            self.after(100, self._periodic_gui_update)

        def _build_ui(self):
            style = ttk.Style(self)
            style.theme_use("clam")
            style.configure("TFrame", background="#F8FAFC")
            style.configure("Card.TFrame", background="#FFFFFF", relief="solid", borderwidth=1)
            style.configure("TLabel", background="#FFFFFF", foreground="#0F172A", font=("Segoe UI", 10))
            style.configure("Sub.TLabel", background="#FFFFFF", foreground="#64748B", font=("Segoe UI", 9))
            style.configure("Metric.TLabel", background="#FFFFFF", foreground="#0F172A", font=("Segoe UI", 15, "bold"))
            style.configure("Horizontal.TProgressbar", troughcolor="#F1F5F9", background="#2563EB", bordercolor="#E2E8F0")

            # ═════════════════════════════════════════════════════════════
            #  SIDEBAR KIRI: Navigasi Vertikal & Kontrol Perangkat (Scrollable)
            # ═════════════════════════════════════════════════════════════
            self.sidebar_frame = ScrollableFrame(self, bg="#FFFFFF", width=295, highlightthickness=1, highlightbackground="#E2E8F0")
            self.sidebar_frame.pack(side="left", fill="y")
            self.sidebar = self.sidebar_frame.content

            # 1. Header & Brand Logo
            brand_box = tk.Frame(self.sidebar, bg="#FFFFFF", padx=16, pady=16)
            brand_box.pack(fill="x")

            lbl_brand = tk.Label(brand_box, text="☕ SMART COFFEE", font=("Segoe UI", 13, "bold"),
                                 bg="#FFFFFF", fg="#0F172A", anchor="w")
            lbl_brand.pack(fill="x")
            lbl_brand_sub = tk.Label(brand_box, text="E-Nose Interactive Trainer", font=("Segoe UI", 8, "bold"),
                                     bg="#FFFFFF", fg="#D97706", anchor="w")
            lbl_brand_sub.pack(fill="x", pady=(2, 0))

            tk.Frame(self.sidebar, bg="#E2E8F0", height=1).pack(fill="x", padx=14, pady=(0, 12))

            # 2. Label Navigasi Vertikal
            tk.Label(self.sidebar, text="MENU HALAMAN", font=("Segoe UI", 8, "bold"),
                     bg="#FFFFFF", fg="#94A3B8", anchor="w", padx=16).pack(fill="x", pady=(0, 6))

            # Tombol-tombol Navigasi Halaman (Vertikal)
            nav_items = [
                ("live", "Live Monitor", "Sensor & AI Real-Time"),
                ("eda", "EDA & Boundary", "Scatter, Boundary & Fitur"),
                ("dataset", "Dataset Summary", "Distribusi Kelas & Sumber"),
            ]

            for page_id, title, subtitle in nav_items:
                btn = tk.Button(
                    self.sidebar,
                    text=f"{title}\n  {subtitle}",
                    justify="left",
                    anchor="w",
                    font=("Segoe UI", 9),
                    padx=14,
                    pady=8,
                    relief="flat",
                    cursor="hand2",
                    command=lambda pid=page_id: self._switch_page(pid)
                )
                btn.pack(fill="x", padx=10, pady=3)
                self.nav_buttons[page_id] = btn

                # Hover micro-animation
                def _bind_hover(b, pid):
                    def _enter(e):
                        if getattr(self, 'current_page', None) != pid:
                            b.configure(bg="#F1F5F9", fg="#0F172A")
                    def _leave(e):
                        if getattr(self, 'current_page', None) != pid:
                            b.configure(bg="#FFFFFF", fg="#475569")
                    b.bind("<Enter>", _enter)
                    b.bind("<Leave>", _leave)
                _bind_hover(btn, page_id)

            tk.Frame(self.sidebar, bg="#E2E8F0", height=1).pack(fill="x", padx=14, pady=12)

            # 3. Serial Connection Box di Sidebar
            tk.Label(self.sidebar, text="KONEKSI HARDWARE", font=("Segoe UI", 8, "bold"),
                     bg="#FFFFFF", fg="#94A3B8", anchor="w", padx=16).pack(fill="x", pady=(0, 6))

            conn_box = tk.Frame(self.sidebar, bg="#F8FAFC", highlightthickness=1, highlightbackground="#E2E8F0", padx=10, pady=10)
            conn_box.pack(fill="x", padx=10, pady=(0, 10))

            port_row = tk.Frame(conn_box, bg="#F8FAFC")
            port_row.pack(fill="x", pady=(0, 6))

            tk.Label(port_row, text="Port:", font=("Segoe UI", 8, "bold"), bg="#F8FAFC", fg="#475569").pack(side="left")
            self.cbo_ports = ttk.Combobox(port_row, width=10, state="readonly")
            self.cbo_ports.pack(side="left", padx=4, fill="x", expand=True)
            self._refresh_ports()

            btn_ref = tk.Button(port_row, text="Refresh", width=6, bg="#FFFFFF", fg="#475569", relief="solid", borderwidth=1,
                                font=("Segoe UI", 8), command=self._refresh_ports)
            btn_ref.pack(side="left", padx=(2, 0))

            self.btn_connect = tk.Button(conn_box, text="Hubungkan Serial", bg="#2563EB", fg="#FFFFFF",
                                         font=("Segoe UI", 9, "bold"), relief="flat", pady=6, cursor="hand2",
                                         command=self._toggle_connection)
            self.btn_connect.pack(fill="x")

            # 4. Mode & Feature Info Box
            tk.Label(self.sidebar, text="STATUS SISTEM", font=("Segoe UI", 8, "bold"),
                     bg="#FFFFFF", fg="#94A3B8", anchor="w", padx=16).pack(fill="x", pady=(0, 6))

            mode_card = tk.Frame(self.sidebar, bg="#F1F5F9", highlightthickness=1, highlightbackground="#E2E8F0", padx=10, pady=8)
            mode_card.pack(fill="x", padx=10, pady=(0, 10))

            tk.Label(mode_card, text=f"MODE: {mode_name.upper()}", font=("Segoe UI", 8, "bold"),
                     bg="#F1F5F9", fg="#2563EB", anchor="w").pack(fill="x")
            tk.Label(mode_card, text=f"{len(active_features)} Fitur Digunakan", font=("Segoe UI", 8),
                     bg="#F1F5F9", fg="#64748B", anchor="w").pack(fill="x")

            # 5. Database Batch Pembanding Selector (Multi-Batch)
            tk.Label(self.sidebar, text="DATABASE PEMBANDING", font=("Segoe UI", 8, "bold"),
                     bg="#FFFFFF", fg="#94A3B8", anchor="w", padx=16).pack(fill="x", pady=(0, 4))

            batch_card = tk.Frame(self.sidebar, bg="#F8FAFC", highlightthickness=1, highlightbackground="#E2E8F0", padx=8, pady=8)
            batch_card.pack(fill="x", padx=10, pady=(0, 10))

            # Status label batch aktif
            self.lbl_batch_sel_info = tk.Label(batch_card, text="Aktif: ⭐ Batch 10", font=("Segoe UI", 8, "bold"),
                                               bg="#F8FAFC", fg="#2563EB", anchor="w", wraplength=260, justify="left")
            self.lbl_batch_sel_info.pack(fill="x", pady=(0, 4))

            # Tombol Preset Cepat
            btn_row = tk.Frame(batch_card, bg="#F8FAFC")
            btn_row.pack(fill="x", pady=(0, 6))

            btn_b10 = tk.Button(btn_row, text="Hanya B10", font=("Segoe UI", 7, "bold"),
                                bg="#2563EB", fg="#FFFFFF", relief="flat", padx=4, pady=2, cursor="hand2",
                                command=self._select_only_b10)
            btn_b10.pack(side="left", fill="x", expand=True, padx=(0, 2))

            btn_all = tk.Button(btn_row, text="Pilih Semua", font=("Segoe UI", 7, "bold"),
                                bg="#F1F5F9", fg="#334155", relief="solid", borderwidth=1, padx=4, pady=2, cursor="hand2",
                                command=self._select_all_batches)
            btn_all.pack(side="right", fill="x", expand=True, padx=(2, 0))

            # Checklist Multi-Batch (2 Kolom Compact)
            chk_frame = tk.Frame(batch_card, bg="#F8FAFC")
            chk_frame.pack(fill="x")
            chk_frame.columnconfigure(0, weight=1)
            chk_frame.columnconfigure(1, weight=1)

            self.batch_vars = {}
            batch_items = [
                ("B10", "B10 (21)"), ("B04", "B04 (7)"),
                ("B01", "B01 (5)"),  ("B02", "B02 (4)"),
                ("B03", "B03 (3)"),  ("B07", "B07 (2)"),
                ("B09", "B09 (2)"),  ("B05", "B05 (1)"),
                ("B08", "B08 (1)"),  ("Legacy", "Legacy (6)")
            ]

            for i, (b_code, b_lbl) in enumerate(batch_items):
                r = i // 2
                c = i % 2
                var = tk.BooleanVar(value=(b_code == "B10"))
                self.batch_vars[b_code] = var
                cb = tk.Checkbutton(
                    chk_frame, text=b_lbl, variable=var,
                    font=("Segoe UI", 8), bg="#F8FAFC", activebackground="#F8FAFC",
                    selectcolor="#FFFFFF", cursor="hand2",
                    command=self._on_batch_changed
                )
                cb.grid(row=r, column=c, sticky="w", padx=3, pady=1)

            # 6. Quick Metrics Footer di Bawah Sidebar
            stat_box = tk.Frame(self.sidebar, bg="#FFFFFF", padx=16, pady=6)
            stat_box.pack(fill="x", padx=10, pady=(8, 20))

            tk.Frame(stat_box, bg="#E2E8F0", height=1).pack(fill="x", pady=(0, 8))

            r1 = tk.Frame(stat_box, bg="#FFFFFF")
            r1.pack(fill="x", pady=2)
            tk.Label(r1, text="Total Dataset:", font=("Segoe UI", 8), bg="#FFFFFF", fg="#64748B").pack(side="left")
            self.lbl_sidebar_samples = tk.Label(r1, text="0", font=("Segoe UI", 8, "bold"), bg="#FFFFFF", fg="#0F172A")
            self.lbl_sidebar_samples.pack(side="right")

            r2 = tk.Frame(stat_box, bg="#FFFFFF")
            r2.pack(fill="x", pady=2)
            tk.Label(r2, text="Akurasi CV:", font=("Segoe UI", 8), bg="#FFFFFF", fg="#64748B").pack(side="left")
            self.lbl_sidebar_acc = tk.Label(r2, text="0.0%", font=("Segoe UI", 8, "bold"), bg="#FFFFFF", fg="#059669")
            self.lbl_sidebar_acc.pack(side="right")

            # ═════════════════════════════════════════════════════════════
            #  MAIN CONTENT AREA (KOLOM KANAN)
            # ═════════════════════════════════════════════════════════════
            content_area = tk.Frame(self, bg="#F8FAFC")
            content_area.pack(side="right", fill="both", expand=True, padx=(10, 15), pady=10)

            # Top Header Bar di Area Konten
            header_bar = tk.Frame(content_area, bg="#FFFFFF", highlightthickness=1, highlightbackground="#E2E8F0", padx=16, pady=10)
            header_bar.pack(fill="x", pady=(0, 10))

            self.lbl_page_title = tk.Label(header_bar, text="📊 Live Monitor (Real-time Sensor & AI Inference)",
                                           font=("Segoe UI", 11, "bold"), bg="#FFFFFF", fg="#0F172A")
            self.lbl_page_title.pack(side="left")

            self.lbl_timestamp = tk.Label(header_bar, text="🕒 --:--:-- WIB", font=("Consolas", 10, "bold"),
                                          bg="#FFFFFF", fg="#2563EB")
            self.lbl_timestamp.pack(side="right")

            # Kontainer Halaman
            self.pages_container = tk.Frame(content_area, bg="#F8FAFC")
            self.pages_container.pack(fill="both", expand=True)

            self.page_live = ttk.Frame(self.pages_container, style="TFrame")
            self.page_eda = ttk.Frame(self.pages_container, style="TFrame")
            self.page_dataset = ttk.Frame(self.pages_container, style="TFrame")

            # === HALAMAN 1: LIVE MONITOR ===
            main_paned = ttk.Frame(self.page_live, style="TFrame")
            main_paned.pack(fill="both", expand=True)

            # ── Panel Kiri: Live Oscilloscope ──
            left_frame = ttk.Frame(main_paned, style="Card.TFrame", padding=10)
            left_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

            # Row 1: Judul & Info
            osc_top = ttk.Frame(left_frame, style="Card.TFrame")
            osc_top.pack(fill="x", pady=(0, 4))
            ttk.Label(osc_top, text="📈 LIVE MULTI-CHANNEL SENSOR OSCILLOSCOPE", font=("Segoe UI", 11, "bold"),
                      background="#FFFFFF", foreground="#0F172A").pack(side="left")
            self.lbl_osc_info = ttk.Label(osc_top, text="Jendela: 360 Detik", style="Sub.TLabel")
            self.lbl_osc_info.pack(side="right")

            # Row 2: Bar Navigasi & Filter Kanal
            osc_ctrls = ttk.Frame(left_frame, style="Card.TFrame")
            osc_ctrls.pack(fill="x", pady=(0, 6))

            ttk.Label(osc_ctrls, text="Fokus Kanal:", background="#FFFFFF", foreground="#64748B",
                      font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 4))
            self.cbo_channel_filter = ttk.Combobox(
                osc_ctrls, width=18, state="readonly",
                values=["Semua Sensor (10 Kanal)"] + [c.replace('adc_', '').upper() for c in ADC_COLS]
            )
            self.cbo_channel_filter.set("Semua Sensor (10 Kanal)")
            self.cbo_channel_filter.pack(side="left", padx=(0, 8))
            self.cbo_channel_filter.bind("<<ComboboxSelected>>", self._on_channel_filter_changed)

            self.btn_toggle_autofit = tk.Button(osc_ctrls, text="Auto-Fit: ON", bg="#059669", fg="#FFFFFF",
                                                font=("Segoe UI", 8, "bold"), padx=8, pady=2, relief="flat", command=self._toggle_autofit)
            self.btn_toggle_autofit.pack(side="left", padx=4)

            self.btn_reset_osc = tk.Button(osc_ctrls, text="Reset ke 0", bg="#F1F5F9", fg="#0F172A",
                                           font=("Segoe UI", 8, "bold"), padx=8, pady=2, relief="solid", borderwidth=1, command=self._reset_monitor)
            self.btn_reset_osc.pack(side="left", padx=4)

            self.btn_popout_osc = tk.Button(osc_ctrls, text="Pop-out Jendela", bg="#F1F5F9", fg="#0F172A",
                                            font=("Segoe UI", 8, "bold"), padx=8, pady=2, relief="solid", borderwidth=1, command=self._open_oscilloscope_popout)
            self.btn_popout_osc.pack(side="right")

            self.fig = Figure(figsize=(7, 5), dpi=100, facecolor="#FFFFFF")
            self.ax = self.fig.add_subplot(111)
            self.ax.set_facecolor("#FFFFFF")
            self.ax.tick_params(colors="#64748B", labelsize=8)
            for s in ["bottom", "top", "left", "right"]:
                self.ax.spines[s].set_color("#CBD5E1")
            self.ax.grid(True, linestyle="--", alpha=0.5, color="#E2E8F0")
            self.ax.set_ylabel("ADC Value", color="#475569", fontsize=9)
            self.ax.set_xlabel("Sampel Waktu (detik)", color="#475569", fontsize=9)

            self.lines = {}
            for col in ADC_COLS:
                line, = self.ax.plot([], [], label=col.replace("adc_", "").upper(),
                                     color=sensor_colors[col], linewidth=1.8)
                self.lines[col] = line

            self.ax.legend(loc="upper right", facecolor="#FFFFFF", edgecolor="#E2E8F0",
                           labelcolor="#0F172A", fontsize=7, ncol=5)

            self.canvas = FigureCanvasTkAgg(self.fig, master=left_frame)
            self.canvas.get_tk_widget().pack(fill="both", expand=True, pady=(2, 4))

            # Toolbar Navigasi Interaktif (Light Themed)
            osc_tb_frame = ttk.Frame(left_frame, style="Card.TFrame")
            osc_tb_frame.pack(fill="x", pady=(0, 2))
            self.osc_toolbar = LightNavigationToolbar(self.canvas, osc_tb_frame)
            self.osc_toolbar.update()

            # Event Mouse Scroll Zoom & Double-Click Reset
            self.canvas.mpl_connect('scroll_event', lambda ev: self._on_scroll_zoom(ev, self.ax, self.canvas, is_live=True))
            self.canvas.mpl_connect('button_press_event', lambda ev: self._on_canvas_dblclick(ev, is_live=True))

            # ── Panel Kanan: Controls, Timer, Feedback & AI Guess (Scrollable) ──
            right_container = ScrollableFrame(main_paned, bg="#FFFFFF", width=460, highlightthickness=1, highlightbackground="#E2E8F0")
            right_container.pack(side="right", fill="both")
            right_frame = right_container.content
            right_frame.configure(padx=14, pady=10)

            # 1. Status Bar
            status_bar = ttk.Frame(right_frame, style="Card.TFrame")
            status_bar.pack(fill="x", pady=(0, 6))

            ttk.Label(status_bar, text="PANEL KONTROL SIKLUS", font=("Segoe UI", 9, "bold"),
                      background="#FFFFFF", foreground="#64748B").pack(side="left")

            self.lbl_total_elapsed = tk.Label(status_bar, text="Total: 0s / 360s", bg="#FFFFFF", fg="#64748B", font=("Segoe UI", 9, "bold"))
            self.lbl_total_elapsed.pack(side="right")

            # 2. Big Phase Banner
            self.phase_banner = tk.Label(right_frame, text="STANDBY (SIAP MEMULAI)", bg="#F1F5F9", fg="#334155",
                                         font=("Segoe UI", 13, "bold"), pady=8, relief="solid", borderwidth=1)
            self.phase_banner.pack(fill="x", pady=(0, 8))

            # 3. Dynamic Countdown Card
            timer_card = tk.LabelFrame(right_frame, text=" ⏳ HITUNG MUNDUR SISA WAKTU FASE ", bg="#FFFFFF", fg="#D97706",
                                       font=("Segoe UI", 9, "bold"), padx=10, pady=8)
            timer_card.pack(fill="x", pady=(0, 10))

            self.lbl_countdown = tk.Label(timer_card, text="Tekan 'Mulai Siklus Baru' untuk pengujian 360s",
                                          bg="#FFFFFF", fg="#0F172A", font=("Segoe UI", 10, "bold"),
                                          wraplength=410, justify="center")
            self.lbl_countdown.pack(pady=2)

            self.progress_phase = ttk.Progressbar(timer_card, orient="horizontal", length=400, mode="determinate", maximum=120)
            self.progress_phase.pack(fill="x", pady=4)

            self.lbl_detail_stage = tk.Label(timer_card, text="Alur: [1] Collect 120s ➔ [2] Purge 120s ➔ [3] Collect 120s ➔ AI Predict",
                                             bg="#FFFFFF", fg="#64748B", font=("Segoe UI", 8),
                                             wraplength=410, justify="center")
            self.lbl_detail_stage.pack()

            # 4. Action Buttons (Start / Stop / Reset)
            ctrl_frame = ttk.Frame(right_frame, style="Card.TFrame")
            ctrl_frame.pack(fill="x", pady=(0, 10))

            self.btn_start = tk.Button(ctrl_frame, text="Mulai (360s)", bg="#059669", fg="#FFFFFF",
                                       font=("Segoe UI", 10, "bold"), relief="flat", pady=6, command=self._start_cycle)
            self.btn_start.pack(side="left", fill="x", expand=True, padx=(0, 3))

            self.btn_stop = tk.Button(ctrl_frame, text="Hentikan", bg="#DC2626", fg="#FFFFFF",
                                      font=("Segoe UI", 10, "bold"), relief="flat", pady=6, command=self._stop_cycle)
            self.btn_stop.pack(side="left", fill="x", expand=True, padx=3)

            self.btn_reset = tk.Button(ctrl_frame, text="Reset Nol", bg="#4F46E5", fg="#FFFFFF",
                                       font=("Segoe UI", 10, "bold"), relief="flat", pady=6, command=self._reset_monitor)
            self.btn_reset.pack(side="right", fill="x", expand=True, padx=(3, 0))

            # 5. AI Guess Card (Random Forest Real-Time)
            guess_card = tk.LabelFrame(right_frame, text=" 🤖 PREDIKSI RANDOM FOREST (REAL-TIME) ", bg="#FFFFFF", fg="#2563EB",
                                       font=("Segoe UI", 9, "bold"), padx=10, pady=8)
            guess_card.pack(fill="x", pady=(0, 10))

            self.lbl_pred_badge = tk.Label(guess_card, text="STANDBY (MENUNGGU SIKLUS)", bg="#FFFFFF", fg="#64748B",
                                           font=("Segoe UI", 8, "bold"))
            self.lbl_pred_badge.pack(pady=(0, 2))

            self.lbl_guess = tk.Label(guess_card, text="MENUNGGU DATA SIKLUS", bg="#FFFFFF", fg="#0F172A",
                                      font=("Segoe UI", 13, "bold"))
            self.lbl_guess.pack(pady=2)

            self.conf_bars = {}
            self.conf_labels = {}
            for lbl in VALID_LABELS:
                row = ttk.Frame(guess_card, style="Card.TFrame")
                row.pack(fill="x", pady=2)
                ttk.Label(row, text=f"{lbl.capitalize():<7}:", background="#FFFFFF", foreground="#334155", width=8).pack(side="left")
                clbl = ttk.Label(row, text="0.0%", background="#FFFFFF", foreground="#334155", width=6)
                clbl.pack(side="right")
                pbar = ttk.Progressbar(row, orient="horizontal", mode="determinate")
                pbar.pack(side="left", fill="x", expand=True, padx=6)
                self.conf_bars[lbl] = pbar
                self.conf_labels[lbl] = clbl

            # 6. Human Verification Feedback Buttons
            feedback_card = tk.LabelFrame(right_frame, text=" 📝 KONFIRMASI / KOREKSI LABEL MANUSIA ", bg="#FFFFFF", fg="#D97706",
                                          font=("Segoe UI", 9, "bold"), padx=10, pady=8)
            feedback_card.pack(fill="x", pady=(0, 10))

            btn_row = ttk.Frame(feedback_card, style="Card.TFrame")
            btn_row.pack(fill="x", pady=2)

            self.btn_light = tk.Button(btn_row, text="Light", bg="#F59E0B", fg="#FFFFFF", font=("Segoe UI", 9, "bold"),
                                       relief="flat", pady=5, command=lambda: self._submit_label("light"))
            self.btn_light.pack(side="left", fill="x", expand=True, padx=2)

            self.btn_med = tk.Button(btn_row, text="Medium", bg="#059669", fg="#FFFFFF", font=("Segoe UI", 9, "bold"),
                                     relief="flat", pady=5, command=lambda: self._submit_label("medium"))
            self.btn_med.pack(side="left", fill="x", expand=True, padx=2)

            self.btn_dark = tk.Button(btn_row, text="Dark", bg="#2563EB", fg="#FFFFFF", font=("Segoe UI", 9, "bold"),
                                      relief="flat", pady=5, command=lambda: self._submit_label("dark"))
            self.btn_dark.pack(side="left", fill="x", expand=True, padx=2)

            self.btn_skip = tk.Button(feedback_card, text="Lewati Sampel Ini (Jangan Simpan)", bg="#F1F5F9", fg="#475569",
                                      font=("Segoe UI", 8), relief="solid", borderwidth=1, pady=3, command=self._skip_sample)
            self.btn_skip.pack(fill="x", pady=(3, 0))

            # 7. Metrics (Total Dataset, Akurasi CV, Siklus)
            metrics_frame = ttk.Frame(right_frame, style="Card.TFrame")
            metrics_frame.pack(fill="x", pady=(0, 6))

            m1 = ttk.Frame(metrics_frame, style="Card.TFrame")
            m1.pack(side="left", fill="x", expand=True)
            ttk.Label(m1, text="Total Dataset", style="Sub.TLabel").pack()
            self.lbl_total_samples = ttk.Label(m1, text="0", style="Metric.TLabel")
            self.lbl_total_samples.pack()

            m2 = ttk.Frame(metrics_frame, style="Card.TFrame")
            m2.pack(side="left", fill="x", expand=True)
            ttk.Label(m2, text="Akurasi Model", style="Sub.TLabel").pack()
            self.lbl_accuracy = ttk.Label(m2, text="0.0%", style="Metric.TLabel")
            self.lbl_accuracy.pack()

            m3 = ttk.Frame(metrics_frame, style="Card.TFrame")
            m3.pack(side="left", fill="x", expand=True)
            ttk.Label(m3, text="Siklus Sesi", style="Sub.TLabel").pack()
            self.lbl_session_cycles = ttk.Label(m3, text="0", style="Metric.TLabel")
            self.lbl_session_cycles.pack()

            # 8. Activity Log Console
            self.log_box = scrolledtext.ScrolledText(right_frame, height=5, bg="#F8FAFC", fg="#334155",
                                                     insertbackground="#0F172A", font=("Consolas", 8),
                                                     relief="solid", borderwidth=1)
            self.log_box.pack(fill="x", pady=(4, 10))
            self._log("Aplikasi GUI Monitor siap. Menunggu sambungan serial.")

            # === BANGUN HALAMAN 2 & 3 ===
            self._build_eda_tab()
            self._build_dataset_tab()

            # Default aktifkan halaman Live Monitor
            self._switch_page("live")

        def _switch_page(self, page_id):
            """Beralih tampilan halaman dari menu navigasi vertikal di sidebar kiri."""
            self.current_page = page_id

            # Sembunyikan semua halaman
            self.page_live.pack_forget()
            self.page_eda.pack_forget()
            self.page_dataset.pack_forget()

            # Tampilkan halaman yang dipilih & perbarui judul di header
            if page_id == "live":
                self.page_live.pack(fill="both", expand=True)
                self.lbl_page_title.configure(text="📊 Live Monitor (Real-time Sensor & AI Inference)")
            elif page_id == "eda":
                self.page_eda.pack(fill="both", expand=True)
                self.lbl_page_title.configure(text="EDA & Decision Boundary Visualization")
                cur_disp = self._get_active_batch_display()
                if getattr(self, 'eda_last_batch', None) != cur_disp:
                    self._regenerate_eda()
                else:
                    self._refresh_eda_plots()
            elif page_id == "dataset":
                self.page_dataset.pack(fill="both", expand=True)
                self.lbl_page_title.configure(text="📈 Dataset & Model Performance Summary")
                self._refresh_dataset_summary()

            # Update style tombol aktif vs inaktif
            for pid, btn in self.nav_buttons.items():
                if pid == page_id:
                    btn.configure(
                        bg="#EFF6FF",
                        fg="#2563EB",
                        font=("Segoe UI", 9, "bold"),
                        relief="solid",
                        bd=1
                    )
                else:
                    btn.configure(
                        bg="#FFFFFF",
                        fg="#475569",
                        font=("Segoe UI", 9),
                        relief="flat",
                        bd=0
                    )

        def _refresh_ports(self):
            ports = [p.device for p in serial.tools.list_ports.comports()]
            self.cbo_ports["values"] = ports
            if ports:
                self.cbo_ports.current(0)

        def _toggle_connection(self):
            if not self.is_connected:
                port = self.cbo_ports.get().strip()
                if not port:
                    messagebox.showerror("Error", "Pilih port serial terlebih dahulu.")
                    return
                try:
                    self.ser = Serial(port, 115200, timeout=1)
                    time.sleep(1.8)
                    self.ser.reset_input_buffer()
                    self.is_connected = True
                    self.btn_connect.configure(text="Putuskan Serial", bg="#DC2626")
                    self._log(f"Terhubung ke {port} @ 115200 baud.")

                    self.serial_thread = threading.Thread(target=self._serial_reader_loop, daemon=True)
                    self.serial_thread.start()
                except Exception as e:
                    messagebox.showerror("Koneksi Gagal", f"Tidak dapat membuka {port}:\n" + str(e))
            else:
                self._disconnect()

        def _disconnect(self):
            self.is_connected = False
            if self.ser:
                try:
                    self.ser.write(b"#stop;")
                    self.ser.close()
                except Exception:
                    pass
                self.ser = None
            self.btn_connect.configure(text="Hubungkan Serial", bg="#2563EB")
            self._set_phase("OFFLINE", "#F1F5F9", fg="#64748B")
            self.lbl_countdown.configure(text="Port serial terputus.", fg="#64748B")
            self._log("Port serial terputus.")

        def _start_cycle(self):
            if not self.is_connected or not self.ser:
                messagebox.showwarning("Belum Terhubung", "Hubungkan ke alat terlebih dahulu.")
                return

            self.collecting1_samples.clear()
            self.purging_samples.clear()
            self.collecting2_samples.clear()
            self.plot_time.clear()
            for col in ADC_COLS:
                self.plot_data[col].clear()

            self.current_features = None
            self.lbl_guess.configure(text="MENGAMBIL DATA SIKLUS...", fg="#2563EB")
            for lbl in VALID_LABELS:
                self.conf_bars[lbl]["value"] = 0
                self.conf_labels[lbl]["text"] = "0.0%"

            try:
                self.ser.reset_input_buffer()
                time.sleep(0.1)
                self.ser.write(b"#start;")
                self.is_acquiring = True
                self.acq_stage = "COLLECT_1"
                self.stage_start_time = time.time()
                self.total_start_time = self.stage_start_time
                self.cycle_count += 1
                self.lbl_session_cycles.configure(text=str(self.cycle_count))
                self._set_phase("🟢 FASE 1: COLLECTING 1 (120s)", "#059669", fg="#FFFFFF")
                self._log(f"Siklus #{self.cycle_count} dimulai: FASE 1 (Collecting 120s).")
            except Exception as e:
                self._log(f"Gagal mengirim #start;: {e}")

        def _stop_cycle(self):
            if self.is_connected and self.ser:
                try:
                    self.ser.write(b"#stop;")
                    self.is_acquiring = False
                    self.acq_stage = "IDLE"
                    self._set_phase("STANDBY (DIHENTIKAN)", "#F1F5F9", fg="#334155")
                    self.lbl_countdown.configure(text="Akuisisi dihentikan manual oleh user.", fg="#64748B")
                    self._log("Akuisisi dihentikan manual oleh user.")
                except Exception as e:
                    self._log(f"Error stop: {e}")

        def _reset_monitor(self):
            """Mereset serial monitor dan grafik osiloskop agar kembali mulai dari detik 0."""
            if self.is_acquiring and self.ser:
                try:
                    self.ser.write(b"#stop;")
                except Exception:
                    pass
                self.is_acquiring = False

            self.acq_stage = "IDLE"
            self.stage_start_time = 0
            self.total_start_time = 0

            # Bersihkan buffer data grafik & garis kurva
            self.plot_time.clear()
            for col in ADC_COLS:
                self.plot_data[col].clear()
                self.lines[col].set_data([], [])

            self.collecting1_samples.clear()
            self.purging_samples.clear()
            self.collecting2_samples.clear()
            self.current_features = None

            # Reset sumbu osiloskop ke nol
            self.auto_fit_oscilloscope = True
            if hasattr(self, 'btn_toggle_autofit'):
                self.btn_toggle_autofit.configure(text="Auto-Fit: ON", bg="#059669")
            self.ax.set_xlim(0, self.max_plot_len)
            self.ax.set_ylim(0, 1023)
            self.canvas.draw_idle()

            if self.ser:
                try:
                    self.ser.reset_input_buffer()
                except Exception:
                    pass

        def _toggle_autofit(self):
            """Mengubah mode auto-fit pelacakan sumbu pada osiloskop."""
            self.auto_fit_oscilloscope = not self.auto_fit_oscilloscope
            if self.auto_fit_oscilloscope:
                self.btn_toggle_autofit.configure(text="Auto-Fit: ON", bg="#059669")
                self._apply_oscilloscope_limits()
                self.canvas.draw_idle()
            else:
                self.btn_toggle_autofit.configure(text="Auto-Fit: OFF", bg="#DC2626")

        def _on_channel_filter_changed(self, event=None):
            """Mengatur isolasi atau highlight kurva sensor yang dipilih."""
            selected = self.cbo_channel_filter.get()
            if not selected or "Semua" in selected:
                for col in ADC_COLS:
                    self.lines[col].set_alpha(1.0)
                    self.lines[col].set_linewidth(1.8)
            else:
                sel_clean = selected.lower().replace("adc_", "")
                target_col = f"adc_{sel_clean}"
                for col in ADC_COLS:
                    if col == target_col:
                        self.lines[col].set_alpha(1.0)
                        self.lines[col].set_linewidth(3.0)
                    else:
                        self.lines[col].set_alpha(0.15)
                        self.lines[col].set_linewidth(1.0)
            if self.auto_fit_oscilloscope:
                self._apply_oscilloscope_limits()
            self.canvas.draw_idle()

        def _apply_oscilloscope_limits(self):
            """Menyesuaikan batas sumbu X dan Y osiloskop secara proporsional dan presisi."""
            if not self.auto_fit_oscilloscope:
                return
            x_data = list(self.plot_time)[-self.max_plot_len:]
            x_len = len(x_data)
            self.ax.set_xlim(0, max(self.max_plot_len, x_len))

            selected = self.cbo_channel_filter.get() if hasattr(self, 'cbo_channel_filter') else ""
            if selected and "Semua" not in selected:
                sel_clean = selected.lower().replace("adc_", "")
                target_col = f"adc_{sel_clean}"
                data_window = self.plot_data.get(target_col, [])[-60:]
                all_y = list(data_window)
            else:
                all_y = [val for col in ADC_COLS for val in self.plot_data[col][-60:]]

            if all_y:
                min_y, max_y = min(all_y), max(all_y)
                dy = max_y - min_y
                margin = max(30, int(dy * 0.15)) if dy > 0 else 60
                self.ax.set_ylim(max(0, min_y - margin), max_y + margin)
            else:
                self.ax.set_ylim(0, 1023)

        def _on_scroll_zoom(self, event, ax, canvas, is_live=False):
            """Zoom in/out interaktif menggunakan scroll wheel mouse berpusat pada kursor."""
            if event.inaxes != ax:
                return
            base_scale = 1.25
            cur_xlim = ax.get_xlim()
            cur_ylim = ax.get_ylim()
            xdata = event.xdata
            ydata = event.ydata
            if xdata is None or ydata is None:
                return

            if event.button == 'up':
                scale_factor = 1 / base_scale
            elif event.button == 'down':
                scale_factor = base_scale
            else:
                scale_factor = 1.0

            new_width = (cur_xlim[1] - cur_xlim[0]) * scale_factor
            new_height = (cur_ylim[1] - cur_ylim[0]) * scale_factor

            relx = (cur_xlim[1] - xdata) / (cur_xlim[1] - cur_xlim[0]) if (cur_xlim[1] - cur_xlim[0]) != 0 else 0.5
            rely = (cur_ylim[1] - ydata) / (cur_ylim[1] - cur_ylim[0]) if (cur_ylim[1] - cur_ylim[0]) != 0 else 0.5

            ax.set_xlim([xdata - new_width * (1 - relx), xdata + new_width * relx])
            ax.set_ylim([ydata - new_height * (1 - rely), ydata + new_height * rely])

            if is_live:
                self.auto_fit_oscilloscope = False
                if hasattr(self, 'btn_toggle_autofit'):
                    self.btn_toggle_autofit.configure(text="Auto-Fit: OFF", bg="#DC2626")

            canvas.draw_idle()

        def _on_canvas_dblclick(self, event, is_live=True):
            """Double-click pada osiloskop mengembalikan auto-fit zoom."""
            if event.dblclick and is_live:
                self.auto_fit_oscilloscope = True
                if hasattr(self, 'btn_toggle_autofit'):
                    self.btn_toggle_autofit.configure(text="Auto-Fit: ON", bg="#059669")
                self._apply_oscilloscope_limits()
                self.canvas.draw_idle()

        def _open_oscilloscope_popout(self):
            """Membuka jendela pop-out osiloskop berukuran besar untuk multi-monitor / analisis detail."""
            pop = tk.Toplevel(self)
            pop.title("📈 E-NOSE LIVE OSCILLOSCOPE (HD DETACHED MONITOR)")
            pop.geometry("1200x750")
            pop.minsize(900, 550)
            pop.configure(bg="#F8FAFC")

            top_bar = ttk.Frame(pop, style="Card.TFrame", padding=(12, 8))
            top_bar.pack(fill="x", padx=10, pady=6)
            ttk.Label(top_bar, text="📈 Live Detached Monitor (Multi-Channel E-Nose)", font=("Segoe UI", 11, "bold"),
                      background="#FFFFFF", foreground="#0F172A").pack(side="left")
            ttk.Label(top_bar, text="Scroll wheel: Zoom In/Out | Drag: Pan | Toolbar di bawah",
                      font=("Segoe UI", 9), background="#FFFFFF", foreground="#64748B").pack(side="right")

            pop_fig = Figure(figsize=(12, 7), dpi=100, facecolor="#FFFFFF")
            pop_ax = pop_fig.add_subplot(111)
            pop_ax.set_facecolor("#FFFFFF")
            pop_ax.tick_params(colors="#64748B", labelsize=9)
            for s in ["bottom", "top", "left", "right"]:
                pop_ax.spines[s].set_color("#CBD5E1")
            pop_ax.grid(True, linestyle="--", alpha=0.5, color="#E2E8F0")
            pop_ax.set_ylabel("ADC Value", color="#475569", fontsize=10)
            pop_ax.set_xlabel("Waktu (Detik)", color="#475569", fontsize=10)

            pop_lines = {}
            for col in ADC_COLS:
                line, = pop_ax.plot([], [], label=col.replace("adc_", "").upper(),
                                    color=sensor_colors[col], linewidth=2.0)
                pop_lines[col] = line

            pop_ax.legend(loc="upper right", facecolor="#FFFFFF", edgecolor="#E2E8F0",
                          labelcolor="#0F172A", fontsize=8, ncol=5)

            pop_canvas = FigureCanvasTkAgg(pop_fig, master=pop)
            pop_canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=(2, 4))

            pop_tb_frame = ttk.Frame(pop, style="Card.TFrame")
            pop_tb_frame.pack(fill="x", padx=10, pady=(0, 6))
            pop_tb = LightNavigationToolbar(pop_canvas, pop_tb_frame)
            pop_tb.update()

            pop_auto = [True]

            def _pop_scroll(event):
                pop_auto[0] = False
                self._on_scroll_zoom(event, pop_ax, pop_canvas)

            pop_canvas.mpl_connect('scroll_event', _pop_scroll)

            def _update_pop():
                if not pop.winfo_exists():
                    return
                if len(self.plot_time) > 2:
                    x_data = list(self.plot_time)[-self.max_plot_len:]
                    for col in ADC_COLS:
                        y_data = list(self.plot_data[col])[-self.max_plot_len:]
                        pop_lines[col].set_data(range(len(y_data)), y_data)
                    if pop_auto[0]:
                        pop_ax.set_xlim(0, max(self.max_plot_len, len(x_data)))
                        all_y = [val for col in ADC_COLS for val in self.plot_data[col][-60:]]
                        if all_y:
                            min_y, max_y = min(all_y), max(all_y)
                            dy = max_y - min_y
                            margin = max(30, int(dy * 0.15)) if dy > 0 else 60
                            pop_ax.set_ylim(max(0, min_y - margin), max_y + margin)
                    pop_canvas.draw_idle()
                pop.after(150, _update_pop)

            pop.after(150, _update_pop)

            self._set_phase("STANDBY (GRAFIK DIRESET KE 0)", "#F1F5F9", fg="#334155")
            self.lbl_countdown.configure(text="Grafik berhasil direset ke detik 0. Siap memulai siklus.", fg="#2563EB")
            self.progress_phase["value"] = 0
            self.lbl_total_elapsed.configure(text="Total: 0s / 360s")
            self.lbl_guess.configure(text="MENUNGGU DATA SIKLUS", fg="#64748B")
            self.lbl_pred_badge.configure(text="STANDBY (MENUNGGU SIKLUS)", fg="#64748B")
            for lbl in VALID_LABELS:
                self.conf_bars[lbl]["value"] = 0
                self.conf_labels[lbl]["text"] = "0.0%"

            self._log("Grafik osiloskop & serial monitor berhasil direset ke detik 0.")

        def _set_phase(self, text, color, fg="#FFFFFF"):
            self.phase_banner.configure(text=text, bg=color, fg=fg)

        def _serial_reader_loop(self):
            while self.is_connected and self.ser:
                try:
                    line = self.ser.readline().decode("utf-8", errors="ignore").strip()
                    if not line or not line.startswith("{"):
                        continue

                    data = json.loads(line)

                    # Jika ada pembacaan sensor ADC
                    if any(k in data for k in ADC_COLS) and self.is_acquiring:
                        sample = {col: float(data.get(col, 0)) for col in ADC_COLS}

                        t_now = len(self.plot_time) + 1
                        self.plot_time.append(t_now)
                        for col in ADC_COLS:
                            self.plot_data[col].append(sample[col])

                        elapsed_stage = int(time.time() - self.stage_start_time)

                        # ── TAHAP 1: COLLECTING 1 (120 detik) ──
                        if self.acq_stage == "COLLECT_1":
                            self.collecting1_samples.append(sample)
                            if elapsed_stage >= self.stage_duration or len(self.collecting1_samples) >= 120:
                                self.acq_stage = "PURGE"
                                self.stage_start_time = time.time()
                                self.after(0, lambda: self._set_phase("🔴 FASE 2: PURGING (120s)", "#DC2626", fg="#FFFFFF"))
                                self._log("Transisi ke FASE 2: PURGING (120 detik pembersihan)...")

                        # ── TAHAP 2: PURGING (120 detik) ──
                        elif self.acq_stage == "PURGE":
                            self.purging_samples.append(sample)
                            if elapsed_stage >= self.stage_duration or len(self.purging_samples) >= 120:
                                self.acq_stage = "COLLECT_2"
                                self.stage_start_time = time.time()
                                self.after(0, lambda: self._set_phase("🟢 FASE 3: COLLECTING 2 (120s)", "#059669", fg="#FFFFFF"))
                                self._log("Transisi ke FASE 3: COLLECTING 2 (120 detik re-adsorpsi)...")

                        # ── TAHAP 3: COLLECTING 2 (120 detik) ──
                        elif self.acq_stage == "COLLECT_2":
                            self.collecting2_samples.append(sample)
                            if elapsed_stage >= self.stage_duration or len(self.collecting2_samples) >= 120:
                                # Selesai penuh 360 detik!
                                try:
                                    self.ser.write(b"#stop;")
                                except Exception:
                                    pass
                                self.is_acquiring = False
                                self.acq_stage = "DONE"
                                self.after(0, lambda: self._set_phase("🟡 SIKLUS 360s SELESAI TUNTAS", "#D97706", fg="#FFFFFF"))
                                self.after(0, self._on_cycle_finished)

                except Exception:
                    pass

        def _on_cycle_finished(self):
            total_samples = len(self.collecting1_samples) + len(self.purging_samples) + len(self.collecting2_samples)
            if len(self.collecting1_samples) < 5:
                self._log("[WARN] Sampel collecting terlalu sedikit.")
                return

            self._log(f"Siklus selesai: {len(self.collecting1_samples)} collect1, {len(self.purging_samples)} purge, {len(self.collecting2_samples)} collect2 (Total: {total_samples}s).")
            self.lbl_countdown.configure(
                text=f"Selesai: {total_samples} sampel data. Menjalankan deteksi AI...",
                fg="#D97706"
            )

            cycle_data = {
                'collecting1': self.collecting1_samples,
                'purging': self.purging_samples,
                'collecting2': self.collecting2_samples,
                'collecting': self.collecting1_samples + self.collecting2_samples,
                'decay': self.purging_samples
            }
            feats = extract_features_from_cycle(cycle_data)
            feats["n_samples"] = len(self.collecting1_samples) + len(self.collecting2_samples)
            self.current_features = feats

            # ── Prediksi Random Forest ──
            if self.clf is not None:
                try:
                    pred, conf = predict(self.clf, feats, active_features)
                    color = label_colors.get(pred, "#0F172A")
                    self.lbl_guess.configure(text=f"[FINAL] {pred.upper()} ROAST ({conf.get(pred, 0.0)*100:.1f}%)", fg=color)
                    self.lbl_pred_badge.configure(text="[SELESAI] PREDIKSI FINAL SIKLUS (360s TUNTAS)", fg="#2563EB")

                    for lbl in VALID_LABELS:
                        p = conf.get(lbl, 0.0) * 100
                        self.conf_bars[lbl]["value"] = p
                        self.conf_labels[lbl]["text"] = f"{p:.1f}%"

                    self._log(f"Tebakan AI (Random Forest): {pred.upper()} ({conf.get(pred, 0.0)*100:.1f}%)")
                    self.lbl_countdown.configure(
                        text=f"Deteksi AI: {pred.upper()} ({conf.get(pred, 0.0)*100:.1f}%). Silakan konfirmasi label di bawah.",
                        fg=color
                    )
                except Exception as e:
                    self._log(f"Gagal prediksi AI: {e}")
            else:
                self.lbl_guess.configure(text="MODEL BELUM TERSEDIA", fg="#64748B")

        def _submit_label(self, chosen_label):
            if self.current_features is None:
                messagebox.showwarning("Perhatian", "Belum ada data siklus yang selesai.")
                return

            save_interactive_sample(self.current_features, chosen_label, self.session_id, self.cycle_count, active_features)
            self._log(f"Label dikonfirmasi: {chosen_label.upper()} -> Tersimpan.")
            self.current_features = None

            threading.Thread(target=self._run_retrain_task, daemon=True).start()

        def _skip_sample(self):
            self.current_features = None
            self.lbl_guess.configure(text="SAMPEL DILEWATI", fg="#64748B")
            self._log("Sampel dilewati oleh user.")

        def _select_only_b10(self):
            for code, var in self.batch_vars.items():
                var.set(code == "B10")
            self._on_batch_changed()

        def _select_all_batches(self):
            for var in self.batch_vars.values():
                var.set(True)
            self._on_batch_changed()

        def _get_active_batch_codes(self):
            if not hasattr(self, 'batch_vars'):
                return ["B10"]
            selected = [code for code, var in self.batch_vars.items() if var.get()]
            if not selected:
                if "B10" in self.batch_vars:
                    self.batch_vars["B10"].set(True)
                return ["B10"]
            if len(selected) == len(self.batch_vars):
                return ["ALL"]
            return selected

        def _get_active_batch_display(self):
            codes = self._get_active_batch_codes()
            if codes == ["ALL"]:
                return "Semua Batch (Gabungan)"
            elif len(codes) == 1:
                return f"Batch {codes[0]}"
            elif len(codes) <= 3:
                return f"Batch {', '.join(codes)}"
            else:
                return f"{len(codes)} Batch Terpilih ({', '.join(codes[:2])}...)"

        def _on_batch_changed(self, event=None):
            self._cached_batch_raw_key = None
            self._cached_batch_raw_df = None
            disp = self._get_active_batch_display()
            if hasattr(self, 'lbl_batch_sel_info'):
                self.lbl_batch_sel_info.configure(text=f"Aktif: {disp}")
            self._log(f"Database pembanding diubah ke: {disp}")
            self._update_metrics_display()
            if getattr(self, 'current_page', None) == 'dataset':
                self._refresh_dataset_summary()
            elif getattr(self, 'current_page', None) == 'eda':
                cur_v = self.cbo_eda_view.get() if hasattr(self, 'cbo_eda_view') else ""
                if "Sensor" in cur_v or cur_v.startswith("5"):
                    self._refresh_eda_plots()
                else:
                    self._regenerate_eda()
            else:
                if hasattr(self, 'lbl_eda_status'):
                    self.lbl_eda_status.configure(text=f"Perlu update ({disp})")

        def _run_retrain_task(self):
            b_codes = self._get_active_batch_codes()
            disp = self._get_active_batch_display()
            self._log(f"Melatih ulang model Random Forest dengan pembanding: {disp}...")
            res = retrain_model(active_features, batch_filter=b_codes)
            if res is not None:
                clf, acc, _, total = res
                self.clf = clf
                self.after(0, lambda: self._on_retrain_done(acc, total))
            else:
                self._log("Retrain selesai tanpa perubahan.")

        def _on_retrain_done(self, acc, total):
            self.lbl_accuracy.configure(text=f"{acc:.1f}%")
            self.lbl_total_samples.configure(text=str(total))
            if hasattr(self, 'lbl_sidebar_acc'):
                self.lbl_sidebar_acc.configure(text=f"{acc:.1f}%")
            if hasattr(self, 'lbl_sidebar_samples'):
                self.lbl_sidebar_samples.configure(text=str(total))
            disp = self._get_active_batch_display()
            msg = f"Model AI berhasil diperbarui!\nDatabase Pembanding: {disp}\nTotal Sampel: {total}\nAkurasi CV: {acc:.1f}%\nHeader C++ otomatis diekspor."
            messagebox.showinfo("Retrain Sukses", msg)

        def _update_metrics_display(self):
            total = 0
            b_codes = self._get_active_batch_codes()
            if os.path.exists(BATCH_DATASET):
                try:
                    df_b = pd.read_csv(BATCH_DATASET)
                    if b_codes != ["ALL"] and b_codes != "ALL":
                        target_batches = [b.upper() for b in (b_codes if isinstance(b_codes, list) else [b_codes])]
                        if 'batch_id' in df_b.columns:
                            df_b = df_b[df_b['batch_id'].astype(str).str.upper().isin(target_batches)]
                        elif 'source_file' in df_b.columns:
                            pattern = '|'.join(target_batches)
                            df_b = df_b[df_b['source_file'].astype(str).str.contains(pattern, case=False, na=False)]
                    total += len(df_b)
                except Exception: pass
            if os.path.exists(INTERACTIVE_CSV):
                try: total += len(pd.read_csv(INTERACTIVE_CSV))
                except Exception: pass
            self.lbl_total_samples.configure(text=str(total))
            if hasattr(self, 'lbl_sidebar_samples'):
                self.lbl_sidebar_samples.configure(text=str(total))

        def _periodic_gui_update(self):
            # 1. Update Live Timestamp Clock
            now_str = f"🕒 {datetime.now().strftime('%H:%M:%S')} WIB"
            self.lbl_timestamp.configure(text=now_str)

            # 2. Update Real-time Countdown & Progress Bars
            if self.is_acquiring and self.stage_start_time > 0:
                elapsed_stage = int(time.time() - self.stage_start_time)
                rem_stage = max(0, self.stage_duration - elapsed_stage)
                self.progress_phase["value"] = min(120, elapsed_stage)

                total_elapsed = len(self.collecting1_samples) + len(self.purging_samples) + len(self.collecting2_samples)
                self.lbl_total_elapsed.configure(text=f"Total: {total_elapsed}s / 360s")

                if self.acq_stage == "COLLECT_1":
                    self.lbl_countdown.configure(
                        text=f"🟢 Collecting 1 kurang: {rem_stage} detik lagi (Berjalan: {elapsed_stage}s / 120s)",
                        fg="#059669"
                    )
                elif self.acq_stage == "PURGE":
                    self.lbl_countdown.configure(
                        text=f"🔴 Purging kurang: {rem_stage} detik lagi (Berjalan: {elapsed_stage}s / 120s)",
                        fg="#DC2626"
                    )
                elif self.acq_stage == "COLLECT_2":
                    self.lbl_countdown.configure(
                        text=f"🟢 Collecting 2 kurang: {rem_stage} detik lagi (Berjalan: {elapsed_stage}s / 120s)",
                        fg="#059669"
                    )

            # 3. Update Multi-channel Oscilloscope
            if len(self.plot_time) > 2:
                x_data = list(self.plot_time)[-self.max_plot_len:]
                for col in ADC_COLS:
                    y_data = list(self.plot_data[col])[-self.max_plot_len:]
                    self.lines[col].set_data(range(len(y_data)), y_data)

                if getattr(self, 'auto_fit_oscilloscope', True):
                    self._apply_oscilloscope_limits()

                self.canvas.draw_idle()

            # 4. Prediksi AI Real-Time (Dijalankan Dinamis Setiap 1 Detik saat Mengambil Data)
            self.periodic_counter = getattr(self, 'periodic_counter', 0) + 1
            if self.is_acquiring and self.clf is not None and (self.periodic_counter % 5 == 0):
                if len(self.collecting1_samples) >= 3:
                    try:
                        cur_col = self.collecting1_samples + self.collecting2_samples
                        cur_pur = self.purging_samples if self.purging_samples else self.collecting1_samples[:5]
                        c_data = {
                            'collecting1': self.collecting1_samples,
                            'purging': cur_pur,
                            'collecting2': self.collecting2_samples,
                            'collecting': cur_col,
                            'decay': cur_pur
                        }
                        cur_feats = extract_features_from_cycle(c_data)
                        pred, conf = predict(self.clf, cur_feats, active_features)
                        color = label_colors.get(pred, "#0F172A")
                        self.lbl_guess.configure(
                            text=f"[LIVE] {pred.upper()} ROAST ({conf.get(pred, 0.0)*100:.1f}%)",
                            fg=color
                        )
                        self.lbl_pred_badge.configure(
                            text="[LIVE] REAL-TIME INFERENCE (1 Hz)",
                            fg="#059669"
                        )
                        for lbl in VALID_LABELS:
                            p = conf.get(lbl, 0.0) * 100
                            self.conf_bars[lbl]["value"] = p
                            self.conf_labels[lbl]["text"] = f"{p:.1f}%"
                    except Exception:
                        pass

            self.after(200, self._periodic_gui_update)

        def _log(self, text):
            t_str = datetime.now().strftime("%H:%M:%S")
            self.log_box.insert("end", f"[{t_str}] {text}\n")
            self.log_box.see("end")

        # ═════════════════════════════════════════════════════════════════
        #  HALAMAN 2: EDA & DECISION BOUNDARY VISUALIZATION
        # ═════════════════════════════════════════════════════════════════
        def _build_eda_tab(self):
            """Membangun halaman EDA dengan visualisasi PCA, Decision Boundary, Feature Importance."""
            tab_eda = self.page_eda

            # Top bar kontrol EDA
            eda_top = ttk.Frame(tab_eda, style="Card.TFrame", padding=(15, 8))
            eda_top.pack(fill="x", padx=10, pady=(10, 5))

            ttk.Label(eda_top, text="Eksplorasi Data & Decision Boundary",
                      font=("Segoe UI", 11, "bold"), background="#FFFFFF", foreground="#0F172A").pack(side="left")

            ttk.Label(eda_top, text="Mode Tampilan:", background="#FFFFFF", foreground="#64748B", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(15, 4))
            self.cbo_eda_view = ttk.Combobox(
                eda_top, width=28, state="readonly",
                values=[
                    "Grid 2x2 (Ringkasan)",
                    "1. PCA 2D Scatter",
                    "2. Decision Boundary",
                    "3. Feature Importance (Top-20)",
                    "4. Confusion Matrix",
                    "5. Persebaran per Sensor"
                ]
            )
            self.cbo_eda_view.set("Grid 2x2 (Ringkasan)")
            self.cbo_eda_view.pack(side="left", padx=4)
            self.cbo_eda_view.bind("<<ComboboxSelected>>", lambda e: self._refresh_eda_plots())

            ttk.Label(eda_top, text="Pilih Sensor:", background="#FFFFFF", foreground="#64748B", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(12, 4))
            sensor_options = ["Semua Sensor (10 Kanal)"] + [c.replace('adc_', '').upper() for c in ADC_COLS]
            self.cbo_eda_sensor = ttk.Combobox(
                eda_top, width=18, state="readonly",
                values=sensor_options
            )
            self.cbo_eda_sensor.set("Semua Sensor (10 Kanal)")
            self.cbo_eda_sensor.pack(side="left", padx=4)
            self.cbo_eda_sensor.bind("<<ComboboxSelected>>", self._on_eda_sensor_changed)

            self.btn_popout_eda = tk.Button(eda_top, text="Buka HD Baru", bg="#F1F5F9", fg="#0F172A",
                                            font=("Segoe UI", 9, "bold"), padx=10, relief="solid", borderwidth=1,
                                            command=self._open_eda_popout)
            self.btn_popout_eda.pack(side="left", padx=6)

            self.btn_refresh_eda = tk.Button(eda_top, text="Refresh",
                                             bg="#4F46E5", fg="#FFFFFF", font=("Segoe UI", 9, "bold"),
                                             padx=12, relief="flat", command=self._refresh_eda_plots)
            self.btn_refresh_eda.pack(side="right", padx=5)

            self.btn_gen_eda = tk.Button(eda_top, text="Generate Ulang",
                                         bg="#059669", fg="#FFFFFF", font=("Segoe UI", 9, "bold"),
                                         padx=12, relief="flat", command=self._regenerate_eda)
            self.btn_gen_eda.pack(side="right", padx=5)

            self.lbl_eda_status = ttk.Label(eda_top, text="", style="Sub.TLabel")
            self.lbl_eda_status.pack(side="right", padx=10)

            # Canvas area with toolbar
            eda_canvas_frame = ttk.Frame(tab_eda, style="Card.TFrame", padding=10)
            eda_canvas_frame.pack(fill="both", expand=True, padx=10, pady=5)

            self.eda_fig = Figure(figsize=(14, 9), dpi=100, facecolor="#FFFFFF")
            self.eda_canvas = FigureCanvasTkAgg(self.eda_fig, master=eda_canvas_frame)
            self.eda_canvas.get_tk_widget().pack(fill="both", expand=True, pady=(0, 4))

            # Light-Themed Toolbar untuk Tab EDA
            eda_tb_frame = ttk.Frame(eda_canvas_frame, style="Card.TFrame")
            eda_tb_frame.pack(fill="x", pady=(0, 2))
            self.eda_toolbar = LightNavigationToolbar(self.eda_canvas, eda_tb_frame)
            self.eda_toolbar.update()

            # Mouse wheel zoom & click listener
            self.eda_canvas.mpl_connect('scroll_event', lambda ev: self._on_scroll_zoom(ev, ev.inaxes, self.eda_canvas) if ev.inaxes else None)
            self.eda_canvas.mpl_connect('button_press_event', self._on_eda_canvas_click)

            # Load existing plots if available
            self._refresh_eda_plots()

        def _get_active_batch_raw_df(self):
            b_codes = self._get_active_batch_codes()
            cache_key = tuple(b_codes) if isinstance(b_codes, list) else (b_codes,)
            if getattr(self, '_cached_batch_raw_key', None) == cache_key and getattr(self, '_cached_batch_raw_df', None) is not None:
                return self._cached_batch_raw_df

            csv_files = glob.glob(os.path.join(DATA_DIR, '*.csv'))
            SKIP = ['dataset_fitur', 'dataset_interactive', 'anomal', 'dataset_fitur_ai',
                    'dataset_fitur_transisi', 'dataset_interactive']
            csv_files = [f for f in csv_files if not any(p in os.path.basename(f).lower() for p in SKIP)]

            if b_codes != ["ALL"] and b_codes != "ALL":
                target_batches = [b.upper() for b in (b_codes if isinstance(b_codes, list) else [b_codes])]
                filtered = []
                for f in csv_files:
                    fname = os.path.basename(f)
                    m = re.search(r'_(B\d+)', fname, re.IGNORECASE)
                    b_code = m.group(1).upper() if m else 'LEGACY'
                    if b_code in target_batches or (('LEGACY' in target_batches or 'Legacy' in target_batches) and not m):
                        filtered.append(f)
                if filtered:
                    csv_files = filtered

            dfs = []
            for f in csv_files:
                try:
                    df = pd.read_csv(f)
                    fname = os.path.basename(f)
                    if 'source_file' not in df.columns:
                        df['source_file'] = fname
                    if 'label' not in df.columns and 'roast_level' in df.columns:
                        df['label'] = df['roast_level']
                    if 'label' in df.columns:
                        df['label'] = df['label'].astype(str).str.lower().str.strip()
                    if 'cycle' not in df.columns:
                        df['cycle'] = df['run_id'] if 'run_id' in df.columns else 1
                    dfs.append(df)
                except Exception:
                    pass

            if not dfs:
                return None

            df_all = pd.concat(dfs, ignore_index=True)
            self._cached_batch_raw_key = cache_key
            self._cached_batch_raw_df = df_all
            return df_all

        def _on_eda_sensor_changed(self, event=None):
            self.cbo_eda_view.set("5. Persebaran per Sensor")
            self._refresh_eda_plots()

        def _render_sensor_distribution(self, fig, sensor_choice):
            """Merender visualisasi persebaran data per sensor atau 10-kanal sensor overview."""
            fig.clear()
            b_disp = self._get_active_batch_display()
            try:
                df_raw = self._get_active_batch_raw_df()

                if df_raw is None or df_raw.empty:
                    ax = fig.add_subplot(1, 1, 1)
                    ax.set_facecolor('#FFFFFF')
                    ax.text(0.5, 0.5, f"Tidak ada data ditemukan untuk database pembanding: {b_disp}",
                            ha='center', va='center', color='#64748B', fontsize=12)
                    ax.axis('off')
                    return

                df_valid = df_raw.copy()
                if 'label' not in df_valid.columns and 'roast_level' in df_valid.columns:
                    df_valid['label'] = df_valid['roast_level']
                df_valid = df_valid[df_valid['label'].astype(str).str.lower().isin(VALID_LABELS)].copy()
                df_valid['label'] = df_valid['label'].astype(str).str.lower().str.strip()

                if 'phase' in df_valid.columns:
                    df_col = df_valid[df_valid['phase'].astype(str).str.lower() == 'collecting'].copy()
                else:
                    df_col = df_valid.copy()
                if df_col.empty:
                    df_col = df_valid.copy()

                for c in ADC_COLS:
                    if c in df_col.columns:
                        df_col[c] = pd.to_numeric(df_col[c], errors='coerce').fillna(0)

                colors = ['#F59E0B', '#10B981', '#2563EB']  # Light, Medium, Dark

                # ── Kasus 1: Overview Semua 10 Kanal Sensor ──
                if not sensor_choice or "Semua" in sensor_choice:
                    fig.subplots_adjust(hspace=0.45, wspace=0.28, left=0.05, right=0.96, top=0.91, bottom=0.07)
                    fig.suptitle(f"Distribusi Mean Nilai ADC 10 Sensor Gas E-Nose — ({b_disp})",
                                 fontsize=13, fontweight='bold', color='#0F172A')

                    group_keys = [k for k in ['source_file', 'label', 'cycle'] if k in df_col.columns]
                    cycle_stats = df_col.groupby(group_keys)[ADC_COLS].mean().reset_index()

                    for idx, col in enumerate(ADC_COLS):
                        ax = fig.add_subplot(2, 5, idx + 1)
                        ax.set_facecolor('#FFFFFF')
                        data = [cycle_stats[cycle_stats['label'] == r][col].dropna().values for r in VALID_LABELS]
                        try:
                            bp = ax.boxplot(data, patch_artist=True, tick_labels=['Light', 'Med', 'Dark'], widths=0.5,
                                            medianprops=dict(color='#0F172A', linewidth=1.5))
                        except TypeError:
                            bp = ax.boxplot(data, patch_artist=True, labels=['Light', 'Med', 'Dark'], widths=0.5,
                                            medianprops=dict(color='#0F172A', linewidth=1.5))
                        for patch, c in zip(bp['boxes'], colors):
                            patch.set_facecolor(c)
                            patch.set_alpha(0.8)
                            patch.set_edgecolor('#334155')
                        for el in ['whiskers', 'caps']:
                            for line in bp[el]:
                                line.set_color('#64748B')

                        sensor_title = col.replace('adc_', '').upper()
                        ax.set_title(sensor_title, color='#0F172A', fontsize=10, fontweight='bold')
                        ax.tick_params(colors='#475569', labelsize=8)
                        for s in ax.spines.values():
                            s.set_color('#CBD5E1')
                        ax.grid(axis='y', linestyle='--', alpha=0.3, color='#CBD5E1')
                    return

                # ── Kasus 2: Eksplorasi 1 Sensor Spesifik (4 Panel Diagnostik) ──
                col = 'adc_' + sensor_choice.lower()
                if col not in df_col.columns:
                    ax = fig.add_subplot(1, 1, 1)
                    ax.set_facecolor('#FFFFFF')
                    ax.text(0.5, 0.5, f"Kanal sensor '{col}' tidak ditemukan dalam dataset.",
                            ha='center', va='center', color='#DC2626', fontsize=12)
                    ax.axis('off')
                    return

                fig.subplots_adjust(hspace=0.35, wspace=0.25, left=0.06, right=0.96, top=0.92, bottom=0.08)
                fig.suptitle(f"Eksplorasi Persebaran Data Sensor: {sensor_choice} — Database: {b_disp}",
                             fontsize=13, fontweight='bold', color='#0F172A')

                group_keys = [k for k in ['source_file', 'label', 'cycle'] if k in df_col.columns]
                cycle_stats = df_col.groupby(group_keys)[col].agg(['mean', 'max', 'std']).reset_index()

                vals_mean = {r: cycle_stats[cycle_stats['label'] == r]['mean'].dropna().values for r in VALID_LABELS}
                vals_max  = {r: cycle_stats[cycle_stats['label'] == r]['max'].dropna().values for r in VALID_LABELS}

                # 1. Boxplot + Jitter Scatter
                ax1 = fig.add_subplot(2, 2, 1)
                ax1.set_facecolor('#FFFFFF')
                try:
                    bp = ax1.boxplot([vals_mean[r] for r in VALID_LABELS], patch_artist=True,
                                     tick_labels=[r.capitalize() for r in VALID_LABELS], widths=0.45,
                                     medianprops=dict(color='#0F172A', linewidth=2))
                except TypeError:
                    bp = ax1.boxplot([vals_mean[r] for r in VALID_LABELS], patch_artist=True,
                                     labels=[r.capitalize() for r in VALID_LABELS], widths=0.45,
                                     medianprops=dict(color='#0F172A', linewidth=2))
                for patch, c in zip(bp['boxes'], colors):
                    patch.set_facecolor(c)
                    patch.set_alpha(0.8)
                    patch.set_edgecolor('#334155')

                np.random.seed(42)
                for idx, r in enumerate(VALID_LABELS):
                    y_pts = vals_mean[r]
                    x_pts = np.random.normal(idx + 1, 0.04, size=len(y_pts))
                    ax1.scatter(x_pts, y_pts, alpha=0.65, s=36, color='#0F172A', edgecolors='white', linewidth=0.5, zorder=4)

                ax1.set_title(f'1. Boxplot & Persebaran Sampel ({sensor_choice})', fontsize=11, fontweight='bold', color='#0F172A')
                ax1.set_ylabel('Nilai Mean ADC', fontsize=9, color='#475569')
                ax1.tick_params(colors='#475569', labelsize=9)
                for s in ax1.spines.values(): s.set_color('#CBD5E1')
                ax1.grid(axis='y', linestyle='--', alpha=0.3, color='#CBD5E1')

                # 2. KDE Density Distribution
                ax2 = fig.add_subplot(2, 2, 2)
                ax2.set_facecolor('#FFFFFF')
                import seaborn as sns
                for r, color in zip(VALID_LABELS, colors):
                    data = vals_mean[r]
                    if len(data) > 1:
                        try:
                            sns.kdeplot(data, ax=ax2, label=r.capitalize(), color=color, fill=True, alpha=0.3, linewidth=2)
                        except Exception:
                            ax2.hist(data, bins=10, color=color, alpha=0.4, label=r.capitalize(), density=True)
                    elif len(data) == 1:
                        ax2.axvline(data[0], color=color, label=r.capitalize(), linewidth=2, linestyle='--')
                ax2.set_title(f'2. Kurva Distribusi Densitas ({sensor_choice})', fontsize=11, fontweight='bold', color='#0F172A')
                ax2.set_xlabel('Nilai Mean ADC', fontsize=9, color='#475569')
                ax2.set_ylabel('Densitas', fontsize=9, color='#475569')
                ax2.tick_params(colors='#475569', labelsize=9)
                ax2.legend(loc='upper right', fontsize=8, facecolor='#FFFFFF', edgecolor='#CBD5E1')
                for s in ax2.spines.values(): s.set_color('#CBD5E1')
                ax2.grid(axis='y', linestyle='--', alpha=0.3, color='#CBD5E1')

                # 3. Dynamic Response Profile
                ax3 = fig.add_subplot(2, 2, 3)
                ax3.set_facecolor('#FFFFFF')
                for r, color in zip(VALID_LABELS, colors):
                    df_r = df_col[df_col['label'] == r]
                    if not df_r.empty and 'sample_idx' in df_r.columns:
                        agg_time = df_r.groupby('sample_idx')[col].agg(['mean', 'std']).reset_index()
                        x_t = agg_time['sample_idx'].values
                        y_m = agg_time['mean'].values
                        y_s = agg_time['std'].fillna(0).values
                        ax3.plot(x_t, y_m, color=color, linewidth=2, label=f"{r.capitalize()}")
                        ax3.fill_between(x_t, y_m - y_s, y_m + y_s, color=color, alpha=0.15)
                ax3.set_title('3. Dinamika Respons Waktu (Collecting Phase)', fontsize=11, fontweight='bold', color='#0F172A')
                ax3.set_xlabel('Waktu (Detik / sample_idx)', fontsize=9, color='#475569')
                ax3.set_ylabel('Nilai ADC Sensor', fontsize=9, color='#475569')
                ax3.tick_params(colors='#475569', labelsize=9)
                ax3.legend(loc='upper right', fontsize=8, facecolor='#FFFFFF', edgecolor='#CBD5E1')
                for s in ax3.spines.values(): s.set_color('#CBD5E1')
                ax3.grid(True, linestyle='--', alpha=0.3, color='#CBD5E1')

                # 4. Bar Comparison & ANOVA
                ax4 = fig.add_subplot(2, 2, 4)
                ax4.set_facecolor('#FFFFFF')
                x_pos = np.arange(3)
                w = 0.35
                means = [np.mean(vals_mean[r]) if len(vals_mean[r]) else 0 for r in VALID_LABELS]
                maxs  = [np.mean(vals_max[r])  if len(vals_max[r])  else 0 for r in VALID_LABELS]
                stds  = [np.std(vals_mean[r])  if len(vals_mean[r])  else 0 for r in VALID_LABELS]

                ax4.bar(x_pos - w/2, means, width=w, color='#3B82F6', label='Mean ADC', edgecolor='#1D4ED8')
                ax4.bar(x_pos + w/2, maxs,  width=w, color='#F59E0B', label='Peak / Max ADC', edgecolor='#D97706')
                ax4.set_xticks(x_pos)
                ax4.set_xticklabels([r.capitalize() for r in VALID_LABELS], fontsize=9, fontweight='bold')

                f_val = 0.0
                p_val = 1.0
                try:
                    from scipy import stats as sp_stats
                    valid_groups = [vals_mean[r] for r in VALID_LABELS if len(vals_mean[r]) > 1]
                    if len(valid_groups) == 3:
                        f_val, p_val = sp_stats.f_oneway(*valid_groups)
                except Exception:
                    pass

                stat_text = f"ANOVA F-Score: {f_val:.1f} (p={p_val:.2e})\n"
                for r, m, s in zip(VALID_LABELS, means, stds):
                    stat_text += f"{r.capitalize()}: {m:.0f} ± {s:.0f}\n"
                ax4.text(0.97, 0.95, stat_text.strip(), transform=ax4.transAxes, fontsize=8,
                         verticalalignment='top', horizontalalignment='right',
                         bbox=dict(boxstyle='round,pad=0.5', facecolor='#F8FAFC', edgecolor='#CBD5E1', alpha=0.9))

                ax4.set_title(f'4. Perbandingan Nilai & Daya Pisah ({sensor_choice})', fontsize=11, fontweight='bold', color='#0F172A')
                ax4.set_ylabel('Nilai ADC', fontsize=9, color='#475569')
                ax4.tick_params(colors='#475569', labelsize=9)
                ax4.legend(loc='upper left', fontsize=8, facecolor='#FFFFFF', edgecolor='#CBD5E1')
                for s in ax4.spines.values(): s.set_color('#CBD5E1')
                ax4.grid(axis='y', linestyle='--', alpha=0.3, color='#CBD5E1')

            except Exception as err:
                fig.clear()
                ax = fig.add_subplot(1, 1, 1)
                ax.set_facecolor('#FFFFFF')
                ax.text(0.5, 0.5, f"Gagal merender persebaran sensor: {err}",
                        ha='center', va='center', color='#DC2626', fontsize=11)
                ax.axis('off')

        def _on_eda_canvas_click(self, event):
            """Klik ganda pada salah satu subplot grid untuk memperbesar ke tampilan single."""
            if event.dblclick and event.inaxes:
                plot_key = getattr(event.inaxes, '_plot_key', None)
                cur_mode = self.cbo_eda_view.get()
                if "Grid" in cur_mode and plot_key:
                    for val in self.cbo_eda_view['values']:
                        if plot_key.lower() in val.lower():
                            self.cbo_eda_view.set(val)
                            self._refresh_eda_plots()
                            return
                elif "Grid" not in cur_mode and "Sensor" not in cur_mode and not cur_mode.startswith("5"):
                    # Switch back to 2x2 grid on double click
                    self.cbo_eda_view.set("Grid 2x2 (Ringkasan)")
                    self._refresh_eda_plots()

        def _render_eda_image(self, ax, title, fpath, is_single=False):
            """Merender gambar plot dengan kualitas tajam dan penanganan fallback."""
            if os.path.exists(fpath):
                try:
                    from PIL import Image
                    with Image.open(fpath) as im:
                        img = np.array(im.convert("RGB"))
                    ax.imshow(img, interpolation='bicubic')
                    sub_hint = " (Klik ganda untuk perbesar penuh)" if not is_single else " (Tampilan Penuh HD - Scroll mouse untuk zoom)"
                    ax.set_title(f"{title}{sub_hint}", color='#0F172A', fontsize=12 if is_single else 10, fontweight='bold', pad=6)
                    ax.axis('off')
                except Exception:
                    try:
                        import matplotlib.image as mpimg
                        img = mpimg.imread(fpath)
                        ax.imshow(img, interpolation='bicubic')
                        ax.set_title(title, color='#0F172A', fontsize=12 if is_single else 10, fontweight='bold', pad=6)
                        ax.axis('off')
                    except Exception:
                        ax.text(0.5, 0.5, f'{title}\n(Error loading)', ha='center', va='center',
                                color='#DC2626', fontsize=11, transform=ax.transAxes)
                        ax.axis('off')
            else:
                ax.text(0.5, 0.5, f'{title}\n\nBelum tersedia.\nKlik "Generate Ulang"\nuntuk membuat.',
                        ha='center', va='center', color='#64748B', fontsize=11,
                        transform=ax.transAxes)
                ax.axis('off')

        def _refresh_eda_plots(self):
            """Load dan tampilkan visualisasi EDA sesuai mode tampilan yang dipilih."""
            cur_view = self.cbo_eda_view.get() if hasattr(self, 'cbo_eda_view') else "Grid 2x2 (Ringkasan)"

            # Jika memilih eksplorasi persebaran per sensor
            if "Sensor" in cur_view or cur_view.startswith("5"):
                sensor_choice = self.cbo_eda_sensor.get() if hasattr(self, 'cbo_eda_sensor') else "Semua Sensor (10 Kanal)"
                self._render_sensor_distribution(self.eda_fig, sensor_choice)
                self.eda_canvas.draw()
                status = f"Persebaran Sensor: {sensor_choice}"
                self.lbl_eda_status.configure(text=status)
                self._log(f"EDA tab di-refresh: {status}")
                return

            plots_dir = os.path.join(BASE_DIR, 'plots', 'eda')

            plot_files = {
                'PCA 2D Scatter': os.path.join(plots_dir, 'pca_2d_scatter.png'),
                'Decision Boundary': os.path.join(plots_dir, 'decision_boundary_rf.png'),
                'Feature Importance': os.path.join(plots_dir, 'feature_importance_top20.png'),
                'Confusion Matrix': os.path.join(plots_dir, 'confusion_matrix.png'),
            }

            self.eda_fig.clear()
            found = 0

            if "Grid" in cur_view:
                self.eda_fig.subplots_adjust(hspace=0.35, wspace=0.30, left=0.04, right=0.96, top=0.94, bottom=0.06)
                for idx, (title, fpath) in enumerate(plot_files.items()):
                    ax = self.eda_fig.add_subplot(2, 2, idx + 1)
                    ax.set_facecolor('#FFFFFF')
                    ax._plot_key = title
                    self._render_eda_image(ax, title, fpath, is_single=False)
                    if os.path.exists(fpath):
                        found += 1
            else:
                self.eda_fig.subplots_adjust(left=0.04, right=0.96, top=0.94, bottom=0.06)
                ax = self.eda_fig.add_subplot(1, 1, 1)
                ax.set_facecolor('#FFFFFF')

                target_key = None
                for key in plot_files.keys():
                    if key.lower() in cur_view.lower() or any(w.lower() in key.lower() for w in cur_view.split()):
                        target_key = key
                        break
                if not target_key:
                    target_key = list(plot_files.keys())[0]

                ax._plot_key = target_key
                fpath = plot_files[target_key]
                self._render_eda_image(ax, target_key, fpath, is_single=True)
                if os.path.exists(fpath):
                    found = 1

            self.eda_canvas.draw()
            status = f"Tampilan: {cur_view}"
            self.lbl_eda_status.configure(text=status)
            self._log(f"EDA tab di-refresh: {status}")

        def _open_eda_popout(self):
            """Membuka visualisasi EDA dalam jendela Toplevel tersendiri yang berukuran besar dengan toolbar interaktif."""
            cur_view = self.cbo_eda_view.get() if hasattr(self, 'cbo_eda_view') else ""
            sensor_choice = self.cbo_eda_sensor.get() if hasattr(self, 'cbo_eda_sensor') else "Semua Sensor (10 Kanal)"

            pop = tk.Toplevel(self)
            pop.geometry("1200x850")
            pop.minsize(850, 600)
            pop.configure(bg="#F8FAFC")

            if "Sensor" in cur_view or cur_view.startswith("5"):
                pop.title(f"HD Viewer - Persebaran Sensor {sensor_choice}")
                top_ctrl = ttk.Frame(pop, style="Card.TFrame", padding=(12, 8))
                top_ctrl.pack(fill="x", padx=10, pady=6)
                ttk.Label(top_ctrl, text=f"Tampilan HD: Persebaran Sensor {sensor_choice}", font=("Segoe UI", 11, "bold"),
                          background="#FFFFFF", foreground="#0F172A").pack(side="left")
                ttk.Label(top_ctrl, text="Gunakan Scroll Mouse atau Toolbar di bawah untuk Zoom In/Out & Pan",
                          font=("Segoe UI", 9), background="#FFFFFF", foreground="#64748B").pack(side="right")

                fig = Figure(figsize=(13, 8.5), dpi=120, facecolor="#FFFFFF")
                self._render_sensor_distribution(fig, sensor_choice)

                canvas = FigureCanvasTkAgg(fig, master=pop)
                canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=(2, 4))
                tb_frame = ttk.Frame(pop, style="Card.TFrame")
                tb_frame.pack(fill="x", padx=10, pady=(0, 6))
                tb = LightNavigationToolbar(canvas, tb_frame)
                tb.update()
                canvas.draw()
                return

            plots_dir = os.path.join(BASE_DIR, 'plots', 'eda')
            plot_files = {
                'PCA 2D Scatter': os.path.join(plots_dir, 'pca_2d_scatter.png'),
                'Decision Boundary': os.path.join(plots_dir, 'decision_boundary_rf.png'),
                'Feature Importance': os.path.join(plots_dir, 'feature_importance_top20.png'),
                'Confusion Matrix': os.path.join(plots_dir, 'confusion_matrix.png'),
            }

            target_key = None
            for key in plot_files.keys():
                if key.lower() in cur_view.lower() or any(w.lower() in key.lower() for w in cur_view.split()):
                    target_key = key
                    break
            if not target_key or "Grid" in cur_view:
                target_key = 'Feature Importance'

            fpath = plot_files.get(target_key)
            if not fpath or not os.path.exists(fpath):
                messagebox.showinfo("Informasi", f"File plot {target_key} belum dibuat. Klik 'Generate Ulang' terlebih dahulu.")
                pop.destroy()
                return

            pop.title(f"HD Viewer - {target_key}")
            top_ctrl = ttk.Frame(pop, style="Card.TFrame", padding=(12, 8))
            top_ctrl.pack(fill="x", padx=10, pady=6)
            ttk.Label(top_ctrl, text=f"Tampilan HD: {target_key}", font=("Segoe UI", 11, "bold"),
                      background="#FFFFFF", foreground="#0F172A").pack(side="left")
            ttk.Label(top_ctrl, text="Gunakan Scroll Mouse atau Toolbar di bawah untuk Zoom In/Out & Pan",
                      font=("Segoe UI", 9), background="#FFFFFF", foreground="#64748B").pack(side="right")

            fig = Figure(figsize=(12, 8), dpi=120, facecolor="#FFFFFF")
            ax = fig.add_subplot(1, 1, 1)
            ax.set_facecolor('#FFFFFF')

            self._render_eda_image(ax, target_key, fpath, is_single=True)
            fig.tight_layout()

            canvas = FigureCanvasTkAgg(fig, master=pop)
            canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=(2, 4))

            tb_frame = ttk.Frame(pop, style="Card.TFrame")
            tb_frame.pack(fill="x", padx=10, pady=(0, 6))
            tb = LightNavigationToolbar(canvas, tb_frame)
            tb.update()

            canvas.mpl_connect('scroll_event', lambda ev: self._on_scroll_zoom(ev, ax, canvas))
            canvas.draw()

        def _regenerate_eda(self):
            """Jalankan ulang script EDA di background thread sesuai batch pembanding aktif."""
            b_codes = self._get_active_batch_codes()
            b_disp = self._get_active_batch_display()
            self.lbl_eda_status.configure(text=f"Generating {b_disp}... (tunggu sebentar)")
            self.btn_gen_eda.configure(state="disabled")
            self._log(f"Menjalankan visualisasi EDA untuk: {b_disp}...")

            def _run_eda():
                import subprocess
                script = os.path.join(SCRIPTS_DIR, '12_eda_decision_boundary.py')
                env = os.environ.copy()
                env['PYTHONIOENCODING'] = 'utf-8'

                cmd = [sys.executable, script]
                if b_codes != ["ALL"] and b_codes != "ALL":
                    batch_arg = ",".join(b_codes) if isinstance(b_codes, list) else str(b_codes)
                    cmd.extend(["--batches", batch_arg])

                try:
                    result = subprocess.run(
                        cmd, capture_output=True, text=True, timeout=120, env=env
                    )
                    if result.returncode == 0:
                        self.after(0, lambda: self._on_eda_done(True, result.stdout, b_disp))
                    else:
                        self.after(0, lambda: self._on_eda_done(False, result.stderr, b_disp))
                except Exception as e:
                    self.after(0, lambda: self._on_eda_done(False, str(e), b_disp))

            threading.Thread(target=_run_eda, daemon=True).start()

        def _on_eda_done(self, success, output, b_disp):
            self.btn_gen_eda.configure(state="normal")
            if success:
                self.eda_last_batch = b_disp
                self.lbl_eda_status.configure(text=f"Sinkron: {b_disp}")
                self._log(f"EDA berhasil dibuat untuk {b_disp}. Memuat ulang visualisasi...")
                self._refresh_eda_plots()
            else:
                self.lbl_eda_status.configure(text="Gagal. Lihat log.")
                self._log(f"EDA gagal: {output[:200]}")

        # ═════════════════════════════════════════════════════════════════
        #  HALAMAN 3: DATASET SUMMARY
        # ═════════════════════════════════════════════════════════════════
        def _build_dataset_tab(self):
            """Halaman ringkasan dataset dengan chart distribusi dan tabel statistik."""
            tab_ds = self.page_dataset

            ds_top = ttk.Frame(tab_ds, style="Card.TFrame", padding=(15, 8))
            ds_top.pack(fill="x", padx=10, pady=(10, 5))

            ttk.Label(ds_top, text="Ringkasan Dataset & Performa Model",
                      font=("Segoe UI", 11, "bold"), background="#FFFFFF", foreground="#0F172A").pack(side="left")

            self.btn_refresh_ds = tk.Button(ds_top, text="Refresh", bg="#4F46E5", fg="#FFFFFF",
                                            font=("Segoe UI", 9, "bold"), padx=12, relief="flat",
                                            command=self._refresh_dataset_summary)
            self.btn_refresh_ds.pack(side="right")

            ds_body = ttk.Frame(tab_ds, style="Card.TFrame", padding=15)
            ds_body.pack(fill="both", expand=True, padx=10, pady=5)

            # Chart + Info side by side
            self.ds_fig = Figure(figsize=(12, 7), dpi=100, facecolor="#FFFFFF")
            self.ds_canvas = FigureCanvasTkAgg(self.ds_fig, master=ds_body)
            self.ds_canvas.get_tk_widget().pack(fill="both", expand=True, pady=(0, 4))

            ds_tb_frame = ttk.Frame(ds_body, style="Card.TFrame")
            ds_tb_frame.pack(fill="x", pady=(0, 2))
            self.ds_toolbar = LightNavigationToolbar(self.ds_canvas, ds_tb_frame)
            self.ds_toolbar.update()

            self.ds_canvas.mpl_connect('scroll_event', lambda ev: self._on_scroll_zoom(ev, ev.inaxes, self.ds_canvas) if ev.inaxes else None)

            self._refresh_dataset_summary()

        def _refresh_dataset_summary(self):
            """Buat chart ringkasan dataset bertema putih bersih."""
            self.ds_fig.clear()

            b_codes = self._get_active_batch_codes()
            b_disp = self._get_active_batch_display()

            # Load dataset
            total_batch = 0
            total_interactive = 0
            label_counts = {'light': 0, 'medium': 0, 'dark': 0}

            if os.path.exists(BATCH_DATASET):
                try:
                    df_b = pd.read_csv(BATCH_DATASET)
                    df_b = df_b[df_b['label'].isin(VALID_LABELS)]
                    if b_codes != ["ALL"] and b_codes != "ALL":
                        target_batches = [b.upper() for b in (b_codes if isinstance(b_codes, list) else [b_codes])]
                        if 'batch_id' in df_b.columns:
                            df_b = df_b[df_b['batch_id'].astype(str).str.upper().isin(target_batches)]
                        elif 'source_file' in df_b.columns:
                            pattern = '|'.join(target_batches)
                            df_b = df_b[df_b['source_file'].astype(str).str.contains(pattern, case=False, na=False)]
                    total_batch = len(df_b)
                    for lbl in VALID_LABELS:
                        label_counts[lbl] += len(df_b[df_b['label'] == lbl])
                except Exception:
                    pass

            if os.path.exists(INTERACTIVE_CSV):
                try:
                    df_i = pd.read_csv(INTERACTIVE_CSV)
                    df_i = df_i[df_i['label'].isin(VALID_LABELS)]
                    total_interactive = len(df_i)
                    for lbl in VALID_LABELS:
                        label_counts[lbl] += len(df_i[df_i['label'] == lbl])
                except Exception:
                    pass

            total = total_batch + total_interactive

            # Subplot 1: Class Distribution Bar Chart
            ax1 = self.ds_fig.add_subplot(1, 2, 1)
            ax1.set_facecolor('#FFFFFF')
            bars_colors = ['#F59E0B', '#10B981', '#2563EB']
            labels_list = [l.capitalize() for l in VALID_LABELS]
            counts_list = [label_counts[l] for l in VALID_LABELS]

            max_count = max(counts_list) if counts_list else 0
            ax1.set_ylim(0, max(max_count * 1.25, 5))
            bars = ax1.bar(labels_list, counts_list, color=bars_colors,
                           edgecolor='#CBD5E1', width=0.5, linewidth=1.2)
            for bar, val in zip(bars, counts_list):
                ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                         str(val), ha='center', va='bottom', color='#0F172A',
                         fontweight='bold', fontsize=12)

            batch_title = f"Pembanding: {b_disp}"
            ax1.set_title(f'Distribusi Kelas ({batch_title})', color='#0F172A', fontsize=11, fontweight='bold')
            ax1.set_ylabel('Jumlah Sampel', color='#334155', fontsize=10)
            ax1.tick_params(colors='#64748B', labelsize=10)
            for s in ax1.spines.values():
                s.set_color('#CBD5E1')
            ax1.grid(axis='y', linestyle='--', alpha=0.5, color='#E2E8F0')

            # Subplot 2: Data Sources Pie Chart
            ax2 = self.ds_fig.add_subplot(1, 2, 2)
            ax2.set_facecolor('#FFFFFF')

            if total > 0:
                data_sources = [
                    (total_batch, f'Batch\n({total_batch})', '#2563EB'),
                    (total_interactive, f'Interactive\n({total_interactive})', '#10B981')
                ]
                valid_sources = [ds for ds in data_sources if ds[0] > 0]
                if valid_sources:
                    sizes = [ds[0] for ds in valid_sources]
                    pie_labels = [ds[1] for ds in valid_sources]
                    pie_colors = [ds[2] for ds in valid_sources]
                    pie_result = ax2.pie(
                        sizes, labels=pie_labels, colors=pie_colors,
                        autopct='%1.0f%%', startangle=90,
                        textprops={'color': '#0F172A', 'fontsize': 11, 'fontweight': 'bold'},
                        wedgeprops={'edgecolor': '#FFFFFF', 'linewidth': 2}
                    )
                    autotexts = pie_result[2] if len(pie_result) > 2 else []
                    for autotext in autotexts:
                        autotext.set_color('#FFFFFF')
                        autotext.set_fontweight('bold')
                else:
                    ax2.axis('off')
                    ax2.text(0.5, 0.5, 'Belum ada data', ha='center', va='center',
                             color='#64748B', fontsize=14, transform=ax2.transAxes)
                ax2.set_title(f'Sumber Data (Total: {total} sampel)',
                              color='#0F172A', fontsize=13, fontweight='bold')
            else:
                ax2.axis('off')
                ax2.text(0.5, 0.5, 'Belum ada data', ha='center', va='center',
                         color='#64748B', fontsize=14, transform=ax2.transAxes)
                ax2.set_title('Sumber Data', color='#0F172A', fontsize=13, fontweight='bold')

            try:
                self.ds_fig.tight_layout(pad=2.0)
            except Exception:
                pass
            self.ds_canvas.draw_idle()

    app = ENoseTrainerGUI()
    app.mainloop()
    return True


def main():
    parser = argparse.ArgumentParser(description='E-NOSE Kopi -- Interactive Active Learning')
    parser.add_argument('--port', type=str, default=None, help='Port Serial (misal COM18)')
    parser.add_argument('--baud', type=int, default=BAUD_RATE)
    parser.add_argument('--cli', action='store_true', help='Jalankan mode terminal teks (CLI) tanpa GUI')
    args = parser.parse_args()

    active_features, mode_name = get_active_features()

    if not args.cli:
        print("[INFO] Membuka antarmuka grafis (GUI Desktop Monitor)...")
        print("       (Tambahkan --cli jika ingin menjalankan mode teks di terminal)")
        if run_gui(active_features, mode_name):
            return

    # ── CLI Fallback Mode ──
    print_header(mode_name, len(active_features))
    port = find_serial_port(args.port)
    print(f"[KONEKSI] Menghubungkan ke {port} @ {args.baud} baud...")

    try:
        ser = Serial(port, args.baud, timeout=2)
        time.sleep(2)
        ser.reset_input_buffer()
        print(f"[OK] Terhubung ke {port}")
    except Exception as e:
        print(f"[ERR] Gagal terhubung ke {port}: {e}")
        sys.exit(1)

    clf = load_model()
    if clf is not None:
        print(f"[MODEL] Model aktif: {clf.n_estimators} trees, {len(clf.classes_)} kelas ({', '.join(clf.classes_)})")
    else:
        print("[MODEL] Belum ada model. Tebakan akan aktif setelah melatih.")

    session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
    cycle_num = 0

    print("-" * 65)
    print("  Letakkan sampel kopi di chamber E-Nose, lalu")
    print("  tekan ENTER untuk memulai pengujian 360 detik (120s - 120s - 120s).")
    print("  Ketik 'q' untuk keluar.")
    print("-" * 65)

    try:
        while True:
            print()
            user_input = input("Tekan ENTER untuk mulai siklus (atau 'q' untuk keluar): ").strip().lower()
            if user_input == 'q':
                break

            cycle_num += 1
            print(f"\n>>> SIKLUS #{cycle_num}")

            # 1. Jalankan siklus 3-tahap (120s - 120s - 120s)
            cycle_data = run_single_cycle(ser)
            if cycle_data is None:
                print("[WARN] Siklus dibatalkan atau gagal.")
                cycle_num -= 1
                continue

            # 2. Ekstraksi fitur sinkron
            features = extract_features_from_cycle(cycle_data)
            n_col = len(cycle_data.get('collecting', []))
            features['n_samples'] = n_col
            print(f"[FITUR] {len(active_features)} fitur berhasil diekstrak ({n_col} sampel aroma).")

            # 3. Prediksi Random Forest
            pred_label = None
            if clf is not None:
                try:
                    pred_label, confidence = predict(clf, features, active_features)
                    print(f"\n[AI RANDOM FOREST]: *** {pred_label.upper()} ***")
                    print("Confidence:")
                    for lbl in VALID_LABELS:
                        c_val = confidence.get(lbl, 0) * 100
                        bar = '#' * int(c_val / 5)
                        marker = " <--" if lbl == pred_label else ""
                        print(f"  {lbl:>7}: {bar:<20} {c_val:5.1f}%{marker}")
                except Exception as e:
                    print(f"[WARN] Gagal memprediksi: {e}")

            # 4. Verifikasi label manusia
            print(f"\nLabel yang BENAR untuk sampel ini?")
            print(f"  [1] Light   [2] Medium   [3] Dark   [S] Skip")
            prompt = f"Pilihan [1=light, 2=medium, 3=dark]: "
            choice = input(prompt).strip().lower()
            if choice == 's':
                print("[SKIP] Sampel dilewati.")
                continue

            if choice == '1': correct_label = 'light'
            elif choice == '2': correct_label = 'medium'
            elif choice == '3': correct_label = 'dark'
            elif choice in VALID_LABELS: correct_label = choice
            elif pred_label: correct_label = pred_label
            else:
                print("[WARN] Input tidak valid. Sampel dilewati.")
                continue

            # 5. Simpan sampel
            save_interactive_sample(features, correct_label, session_id, cycle_num, active_features)
            print(f"[SIMPAN] Sampel tersimpan ke {INTERACTIVE_CSV}")

            # 6. Retrain Random Forest
            print("\n[RETRAIN] Melatih ulang Random Forest...")
            res = retrain_model(active_features)
            if res is not None:
                clf, cv_acc, cv_std, total = res
                print(f"[OK] Model berhasil diperbarui! ({total} sampel, CV: {cv_acc:.1f}%)")

    except KeyboardInterrupt:
        print("\n[STOP] Dihentikan oleh user.")

    try:
        ser.close()
        print(f"\n[SERIAL] Port {port} ditutup.")
    except Exception:
        pass

    print("\nSelesai! Terima kasih.")

if __name__ == '__main__':
    main()