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
import json
import os
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
    'adc_tgs822', 'adc_mq135', 'adc_mq9', 'adc_tgs2611', 'adc_tgs2620',
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


def load_combined_dataset(active_feature_cols):
    dfs = []
    n_batch = 0
    if os.path.exists(BATCH_DATASET):
        df_batch = pd.read_csv(BATCH_DATASET)
        df_batch = df_batch[df_batch['label'].isin(VALID_LABELS)]
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


def retrain_model(active_feature_cols):
    X, y, n_batch, n_interactive = load_combined_dataset(active_feature_cols)

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
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    except ImportError as e:
        print(f"[ERR] Library GUI belum lengkap: {e}. Menjalankan mode CLI...")
        return False

    sensor_colors = {
        'adc_tgs822':  '#E11D48', 'adc_mq135':   '#F97316', 'adc_mq9':     '#FBBF24',
        'adc_tgs2611': '#10B981', 'adc_tgs2620': '#06B6D4', 'adc_tgs2600': '#3B82F6',
        'adc_tgs2602': '#6366F1', 'adc_mq8':     '#8B5CF6', 'adc_tgs813':  '#D946EF',
        'adc_tgs816':  '#84CC16'
    }
    label_colors = {'light': '#F59E0B', 'medium': '#10B981', 'dark': '#3B82F6'}

    class ENoseTrainerGUI(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title("☕ Smart Coffee E-Nose — Interactive Active Learning Trainer")
            self.geometry("1300x840")
            self.minsize(1120, 740)
            self.configure(bg="#0F172A")

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

            # Multi-channel visualizer buffer (360 detik)
            self.max_plot_len = 360
            self.plot_time = []
            self.plot_data = {col: [] for col in ADC_COLS}

            # Buffer Sampel 3-Tahap
            self.collecting1_samples = []
            self.purging_samples = []
            self.collecting2_samples = []

            self.clf = load_model()
            self._build_ui()
            self._update_metrics_display()
            self.after(100, self._periodic_gui_update)

        def _build_ui(self):
            style = ttk.Style(self)
            style.theme_use("clam")
            style.configure("TFrame", background="#0F172A")
            style.configure("Card.TFrame", background="#1E293B", relief="solid", borderwidth=1)
            style.configure("TLabel", background="#0F172A", foreground="#F8FAFC", font=("Segoe UI", 10))
            style.configure("Sub.TLabel", background="#1E293B", foreground="#94A3B8", font=("Segoe UI", 9))
            style.configure("Metric.TLabel", background="#1E293B", foreground="#F8FAFC", font=("Segoe UI", 15, "bold"))

            # Top Header Bar
            top_bar = ttk.Frame(self, style="Card.TFrame", padding=(15, 10))
            top_bar.pack(fill="x", padx=15, pady=(15, 10))

            lbl_t = ttk.Label(top_bar, text="☕ E-NOSE COFFEE ROAST TRAINER", font=("Segoe UI", 12, "bold"), background="#1E293B", foreground="#F59E0B")
            lbl_t.pack(side="left", padx=(0, 15))

            ttk.Label(top_bar, text="Port:", background="#1E293B").pack(side="left", padx=4)
            self.cbo_ports = ttk.Combobox(top_bar, width=12, state="readonly")
            self.cbo_ports.pack(side="left", padx=4)
            self._refresh_ports()

            ttk.Button(top_bar, text="🔄", width=3, command=self._refresh_ports).pack(side="left", padx=2)

            self.btn_connect = tk.Button(top_bar, text="Hubungkan", bg="#3B82F6", fg="#FFFFFF", font=("Segoe UI", 9, "bold"),
                                         padx=10, relief="flat", command=self._toggle_connection)
            self.btn_connect.pack(side="left", padx=10)

            # Mode & Feature Badge
            lbl_m = tk.Label(top_bar, text=f"MODE: {mode_name.upper()} ({len(active_features)} FITUR)",
                             bg="#334155", fg="#38BDF8", font=("Segoe UI", 9, "bold"), padx=10, pady=3)
            lbl_m.pack(side="right")

            main_paned = ttk.Frame(self)
            main_paned.pack(fill="both", expand=True, padx=15, pady=(0, 15))

            # ── Panel Kiri: Live Oscilloscope ──
            left_frame = ttk.Frame(main_paned, style="Card.TFrame", padding=10)
            left_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

            osc_top = ttk.Frame(left_frame, style="Card.TFrame")
            osc_top.pack(fill="x", pady=(0, 4))
            ttk.Label(osc_top, text="📈 LIVE MULTI-CHANNEL SENSOR OSCILLOSCOPE", font=("Segoe UI", 11, "bold"), background="#1E293B", foreground="#38BDF8").pack(side="left")
            self.lbl_osc_info = ttk.Label(osc_top, text="Jendela: 360 Detik", style="Sub.TLabel")
            self.lbl_osc_info.pack(side="right")
            self.btn_reset_osc = tk.Button(osc_top, text="🔄 Reset Grafik ke Nol", bg="#334155", fg="#38BDF8",
                                           font=("Segoe UI", 8, "bold"), padx=8, pady=2, relief="flat", command=self._reset_monitor)
            self.btn_reset_osc.pack(side="right", padx=(0, 10))

            self.fig = Figure(figsize=(7, 5), dpi=100, facecolor="#1E293B")
            self.ax = self.fig.add_subplot(111)
            self.ax.set_facecolor("#0F172A")
            self.ax.tick_params(colors="#94A3B8", labelsize=8)
            for s in ["bottom", "top", "left", "right"]:
                self.ax.spines[s].set_color("#334155")
            self.ax.grid(True, linestyle="--", alpha=0.25, color="#64748B")
            self.ax.set_ylabel("ADC Value", color="#94A3B8", fontsize=9)
            self.ax.set_xlabel("Sampel Waktu (detik)", color="#94A3B8", fontsize=9)

            self.lines = {}
            for col in ADC_COLS:
                line, = self.ax.plot([], [], label=col.replace("adc_", "").upper(),
                                     color=sensor_colors[col], linewidth=1.6)
                self.lines[col] = line

            self.ax.legend(loc="upper right", facecolor="#1E293B", edgecolor="#334155",
                           labelcolor="#F8FAFC", fontsize=7, ncol=5)

            self.canvas = FigureCanvasTkAgg(self.fig, master=left_frame)
            self.canvas.get_tk_widget().pack(fill="both", expand=True, pady=5)

            # ── Panel Kanan: Controls, Timer, Feedback & AI Guess ──
            right_frame = ttk.Frame(main_paned, style="Card.TFrame", padding=15, width=460)
            right_frame.pack(side="right", fill="both")
            right_frame.pack_propagate(False)

            # 1. Live Timestamp & Status Bar
            status_bar = ttk.Frame(right_frame, style="Card.TFrame")
            status_bar.pack(fill="x", pady=(0, 6))

            self.lbl_timestamp = tk.Label(status_bar, text="🕒 --:--:-- WIB", bg="#1E293B", fg="#38BDF8", font=("Consolas", 11, "bold"))
            self.lbl_timestamp.pack(side="left")

            self.lbl_total_elapsed = tk.Label(status_bar, text="Total: 0s / 360s", bg="#1E293B", fg="#94A3B8", font=("Segoe UI", 9, "bold"))
            self.lbl_total_elapsed.pack(side="right")

            # 2. Big Phase Banner
            self.phase_banner = tk.Label(right_frame, text="STANDBY (SIAP MEMULAI)", bg="#334155", fg="#F8FAFC",
                                         font=("Segoe UI", 14, "bold"), pady=8)
            self.phase_banner.pack(fill="x", pady=(0, 6))

            # 3. Dynamic Countdown Card (Collecting kurang ... / Purging kurang ...)
            timer_card = tk.LabelFrame(right_frame, text=" ⏳ HITUNG MUNDUR SISA WAKTU FASE ", bg="#1E293B", fg="#F59E0B",
                                       font=("Segoe UI", 9, "bold"), padx=10, pady=8)
            timer_card.pack(fill="x", pady=(0, 10))

            self.lbl_countdown = tk.Label(timer_card, text="Tekan 'Mulai Siklus Baru' untuk pengujian 360s",
                                          bg="#1E293B", fg="#F8FAFC", font=("Segoe UI", 11, "bold"))
            self.lbl_countdown.pack(pady=2)

            self.progress_phase = ttk.Progressbar(timer_card, orient="horizontal", length=400, mode="determinate", maximum=120)
            self.progress_phase.pack(fill="x", pady=4)

            self.lbl_detail_stage = tk.Label(timer_card, text="Alur: [1] Collect 120s ➔ [2] Purge 120s ➔ [3] Collect 120s ➔ AI Predict",
                                             bg="#1E293B", fg="#94A3B8", font=("Segoe UI", 8))
            self.lbl_detail_stage.pack()

            # 4. Action Buttons (Start / Stop / Reset)
            ctrl_frame = ttk.Frame(right_frame, style="Card.TFrame")
            ctrl_frame.pack(fill="x", pady=(0, 12))

            self.btn_start = tk.Button(ctrl_frame, text="▶ Mulai (360s)", bg="#10B981", fg="#FFFFFF",
                                       font=("Segoe UI", 10, "bold"), relief="flat", pady=6, command=self._start_cycle)
            self.btn_start.pack(side="left", fill="x", expand=True, padx=(0, 3))

            self.btn_stop = tk.Button(ctrl_frame, text="⏹ Hentikan", bg="#EF4444", fg="#FFFFFF",
                                      font=("Segoe UI", 10, "bold"), relief="flat", pady=6, command=self._stop_cycle)
            self.btn_stop.pack(side="left", fill="x", expand=True, padx=3)

            self.btn_reset = tk.Button(ctrl_frame, text="🔄 Reset Nol", bg="#6366F1", fg="#FFFFFF",
                                       font=("Segoe UI", 10, "bold"), relief="flat", pady=6, command=self._reset_monitor)
            self.btn_reset.pack(side="right", fill="x", expand=True, padx=(3, 0))

            # 5. AI Guess Card (Random Forest)
            guess_card = tk.LabelFrame(right_frame, text=" 🤖 HASIL PREDIKSI RANDOM FOREST ", bg="#1E293B", fg="#38BDF8",
                                       font=("Segoe UI", 9, "bold"), padx=10, pady=8)
            guess_card.pack(fill="x", pady=(0, 12))

            self.lbl_guess = tk.Label(guess_card, text="MENUNGGU DATA SIKLUS", bg="#1E293B", fg="#94A3B8",
                                      font=("Segoe UI", 14, "bold"))
            self.lbl_guess.pack(pady=3)

            self.conf_bars = {}
            self.conf_labels = {}
            for lbl in VALID_LABELS:
                row = ttk.Frame(guess_card, style="Card.TFrame")
                row.pack(fill="x", pady=2)
                ttk.Label(row, text=f"{lbl.capitalize():<7}:", background="#1E293B", width=8).pack(side="left")
                pbar = ttk.Progressbar(row, orient="horizontal", length=180, mode="determinate")
                pbar.pack(side="left", padx=5)
                clbl = ttk.Label(row, text="0.0%", background="#1E293B", width=6)
                clbl.pack(side="left")
                self.conf_bars[lbl] = pbar
                self.conf_labels[lbl] = clbl

            # 6. Human Verification Feedback Buttons
            feedback_card = tk.LabelFrame(right_frame, text=" 📝 KONFIRMASI / KOREKSI LABEL MANUSIA ", bg="#1E293B", fg="#F59E0B",
                                          font=("Segoe UI", 9, "bold"), padx=10, pady=8)
            feedback_card.pack(fill="x", pady=(0, 10))

            btn_row = ttk.Frame(feedback_card, style="Card.TFrame")
            btn_row.pack(fill="x", pady=3)

            self.btn_light = tk.Button(btn_row, text="🟡 Light", bg="#D97706", fg="#FFFFFF", font=("Segoe UI", 10, "bold"),
                                       relief="flat", pady=5, command=lambda: self._submit_label("light"))
            self.btn_light.pack(side="left", fill="x", expand=True, padx=2)

            self.btn_med = tk.Button(btn_row, text="🟢 Medium", bg="#059669", fg="#FFFFFF", font=("Segoe UI", 10, "bold"),
                                     relief="flat", pady=5, command=lambda: self._submit_label("medium"))
            self.btn_med.pack(side="left", fill="x", expand=True, padx=2)

            self.btn_dark = tk.Button(btn_row, text="🔵 Dark", bg="#2563EB", fg="#FFFFFF", font=("Segoe UI", 10, "bold"),
                                      relief="flat", pady=5, command=lambda: self._submit_label("dark"))
            self.btn_dark.pack(side="left", fill="x", expand=True, padx=2)

            self.btn_skip = tk.Button(feedback_card, text="⏭ Lewati Sampel Ini (Jangan Simpan)", bg="#475569", fg="#FFFFFF",
                                      font=("Segoe UI", 9), relief="flat", pady=3, command=self._skip_sample)
            self.btn_skip.pack(fill="x", pady=(3, 0))

            # 7. Metrics (Total Dataset, Akurasi CV, Siklus)
            metrics_frame = ttk.Frame(right_frame, style="Card.TFrame")
            metrics_frame.pack(fill="x", pady=(0, 8))

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
            self.log_box = scrolledtext.ScrolledText(right_frame, height=4, bg="#0F172A", fg="#94A3B8",
                                                     font=("Consolas", 8), relief="flat")
            self.log_box.pack(fill="both", expand=True)
            self._log("Aplikasi GUI Monitor siap. Menunggu sambungan serial.")

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
                    self.btn_connect.configure(text="Putuskan", bg="#EF4444")
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
            self.btn_connect.configure(text="Hubungkan", bg="#3B82F6")
            self._set_phase("OFFLINE", "#334155")
            self.lbl_countdown.configure(text="Port serial terputus.", fg="#94A3B8")
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
            self.lbl_guess.configure(text="MENGAMBIL DATA SIKLUS...", fg="#38BDF8")
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
                self._set_phase("🟢 FASE 1: COLLECTING 1 (120s)", "#059669")
                self._log(f"Siklus #{self.cycle_count} dimulai: FASE 1 (Collecting 120s).")
            except Exception as e:
                self._log(f"Gagal mengirim #start;: {e}")

        def _stop_cycle(self):
            if self.is_connected and self.ser:
                try:
                    self.ser.write(b"#stop;")
                    self.is_acquiring = False
                    self.acq_stage = "IDLE"
                    self._set_phase("STANDBY (DIHENTIKAN)", "#334155")
                    self.lbl_countdown.configure(text="Akuisisi dihentikan manual oleh user.", fg="#94A3B8")
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
            self.ax.set_xlim(0, self.max_plot_len)
            self.canvas.draw_idle()

            if self.ser:
                try:
                    self.ser.reset_input_buffer()
                except Exception:
                    pass

            self._set_phase("STANDBY (GRAFIK DIRESET KE 0)", "#334155")
            self.lbl_countdown.configure(text="Grafik berhasil direset ke detik 0. Siap memulai siklus.", fg="#38BDF8")
            self.progress_phase["value"] = 0
            self.lbl_total_elapsed.configure(text="Total: 0s / 360s")
            self.lbl_guess.configure(text="MENUNGGU DATA SIKLUS", fg="#94A3B8")
            for lbl in VALID_LABELS:
                self.conf_bars[lbl]["value"] = 0
                self.conf_labels[lbl]["text"] = "0.0%"

            self._log("Grafik osiloskop & serial monitor berhasil direset ke detik 0.")

        def _set_phase(self, text, color):
            self.phase_banner.configure(text=text, bg=color)

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
                                self.after(0, lambda: self._set_phase("🔴 FASE 2: PURGING (120s)", "#DC2626"))
                                self._log("Transisi ke FASE 2: PURGING (120 detik pembersihan)...")

                        # ── TAHAP 2: PURGING (120 detik) ──
                        elif self.acq_stage == "PURGE":
                            self.purging_samples.append(sample)
                            if elapsed_stage >= self.stage_duration or len(self.purging_samples) >= 120:
                                self.acq_stage = "COLLECT_2"
                                self.stage_start_time = time.time()
                                self.after(0, lambda: self._set_phase("🟢 FASE 3: COLLECTING 2 (120s)", "#059669"))
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
                                self.after(0, lambda: self._set_phase("🟡 SIKLUS 360s SELESAI TUNTAS", "#D97706"))
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
                fg="#F59E0B"
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
                    color = label_colors.get(pred, "#F8FAFC")
                    self.lbl_guess.configure(text=f"☕ {pred.upper()} ROAST ({conf.get(pred, 0.0)*100:.1f}%)", fg=color)

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
                self.lbl_guess.configure(text="MODEL BELUM TERSEDIA", fg="#94A3B8")

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
            self.lbl_guess.configure(text="SAMPEL DILEWATI", fg="#94A3B8")
            self._log("Sampel dilewati oleh user.")

        def _run_retrain_task(self):
            self._log("Melatih ulang model Random Forest...")
            res = retrain_model(active_features)
            if res is not None:
                clf, acc, _, total = res
                self.clf = clf
                self.after(0, lambda: self._on_retrain_done(acc, total))
            else:
                self._log("Retrain selesai tanpa perubahan.")

        def _on_retrain_done(self, acc, total):
            self.lbl_accuracy.configure(text=f"{acc:.1f}%")
            self.lbl_total_samples.configure(text=str(total))
            msg = f"Model AI berhasil diperbarui!\nTotal Sampel: {total}\nAkurasi CV: {acc:.1f}%\nHeader C++ otomatis diekspor."
            messagebox.showinfo("Retrain Sukses", msg)

        def _update_metrics_display(self):
            total = 0
            if os.path.exists(BATCH_DATASET):
                try: total += len(pd.read_csv(BATCH_DATASET))
                except Exception: pass
            if os.path.exists(INTERACTIVE_CSV):
                try: total += len(pd.read_csv(INTERACTIVE_CSV))
                except Exception: pass
            self.lbl_total_samples.configure(text=str(total))

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
                        fg="#34D399"
                    )
                elif self.acq_stage == "PURGE":
                    self.lbl_countdown.configure(
                        text=f"🔴 Purging kurang: {rem_stage} detik lagi (Berjalan: {elapsed_stage}s / 120s)",
                        fg="#F87171"
                    )
                elif self.acq_stage == "COLLECT_2":
                    self.lbl_countdown.configure(
                        text=f"🟢 Collecting 2 kurang: {rem_stage} detik lagi (Berjalan: {elapsed_stage}s / 120s)",
                        fg="#34D399"
                    )

            # 3. Update Multi-channel Oscilloscope
            if len(self.plot_time) > 2:
                x_data = list(self.plot_time)[-self.max_plot_len:]
                for col in ADC_COLS:
                    y_data = list(self.plot_data[col])[-self.max_plot_len:]
                    self.lines[col].set_data(range(len(y_data)), y_data)

                self.ax.set_xlim(0, max(self.max_plot_len, len(x_data)))
                all_y = [val for col in ADC_COLS for val in self.plot_data[col][-60:]]
                if all_y:
                    min_y, max_y = min(all_y), max(all_y)
                    self.ax.set_ylim(max(0, min_y - 400), max_y + 600)

                self.canvas.draw_idle()

            self.after(200, self._periodic_gui_update)

        def _log(self, text):
            t_str = datetime.now().strftime("%H:%M:%S")
            self.log_box.insert("end", f"[{t_str}] {text}\n")
            self.log_box.see("end")

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