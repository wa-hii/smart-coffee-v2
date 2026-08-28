"""
9_interactive_trainer.py
═══════════════════════════════════════════════════════════════════════════════
Interactive Active Learning — E-NOSE Kopi

Alur Kerja:
  1. Hubungkan ke ATmega via Serial
  2. Jalankan 1 siklus akuisisi (purging + collecting)
  3. Ekstraksi 48 fitur dari data collecting
  4. Model menebak tingkat roasting kopi
  5. User memberikan koreksi / konfirmasi label
  6. Data baru disimpan ke dataset_interactive.csv
  7. Model di-retrain otomatis dari seluruh dataset
  8. Ulangi dari langkah 2, atau keluar & export C++ header

Cara Pakai:
  python scripts/9_interactive_trainer.py
  python scripts/9_interactive_trainer.py --port COM18

Catatan:
  - Firmware ATmega TIDAK perlu diubah. Script ini otomatis mengirim
    #stop; setelah 1 siklus selesai.
  - Data interaktif disimpan kumulatif di data/dataset_interactive.csv
  - Model di-retrain menggunakan gabungan data batch (dataset_fitur.csv)
    + data interaktif (dataset_interactive.csv)
═══════════════════════════════════════════════════════════════════════════════
"""

import argparse
import json
import os
import sys
import time
import threading
from datetime import datetime

import numpy as np
import pandas as pd
import joblib

from serial import Serial

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.metrics import accuracy_score, classification_report

# ─── Path Konfigurasi ────────────────────────────────────────────────────────
SCRIPTS_DIR       = os.path.dirname(os.path.abspath(__file__))
DATA_DIR          = os.path.normpath(os.path.join(SCRIPTS_DIR, '..', 'data'))
INCLUDE_DIR       = os.path.normpath(os.path.join(SCRIPTS_DIR, '..', 'include'))
MODEL_PATH        = os.path.join(DATA_DIR, 'model_rf.joblib')
BATCH_DATASET     = os.path.join(DATA_DIR, 'dataset_fitur.csv')
INTERACTIVE_CSV   = os.path.join(DATA_DIR, 'dataset_interactive.csv')
OUTPUT_HEADER     = os.path.join(INCLUDE_DIR, 'model_rf_atmega.h')

BAUD_RATE         = 115200
VALID_LABELS      = ['light', 'medium', 'dark']

# ─── Kolom ADC (urutan HARUS konsisten dengan firmware & 4_train_rf.py) ──────
ADC_COLS = [
    'adc_tgs822', 'adc_mq135', 'adc_mq9', 'adc_tgs2611', 'adc_tgs2620',
    'adc_tgs2600', 'adc_tgs2602', 'adc_mq8', 'adc_tgs813', 'adc_tgs816'
]

# ─── Hyperparameter RF (konsisten dengan 4_train_rf.py) ──────────────────────
RF_N_ESTIMATORS = 8
RF_MAX_DEPTH    = 4
RF_RANDOM_STATE = 42

# ─── 48 Feature Columns (urutan identik dengan 4_train_rf.py) ────────────────
FEATURE_COLS = (
    [f'mean_{c}' for c in ADC_COLS] +
    [f'max_{c}'  for c in ADC_COLS] +
    [f'sum_{c}'  for c in ADC_COLS] +
    [f'ratio_to_mq135_{c}' for c in ADC_COLS if c != 'adc_mq135'] +
    [f'ratio_to_tgs822_{c}' for c in ADC_COLS if c != 'adc_tgs822']
)


# ═════════════════════════════════════════════════════════════════════════════
#  UTILITAS
# ═════════════════════════════════════════════════════════════════════════════

def clear_line():
    """Hapus baris terminal saat ini."""
    print('\r' + ' ' * 80 + '\r', end='', flush=True)


def print_header():
    """Tampilkan header program."""
    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║   ☕ E-NOSE Kopi — Interactive Active Learning Trainer      ║")
    print("║   Metode: 1 Siklus → Tebak → Koreksi → Retrain            ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()


def find_serial_port(preferred=None):
    """Auto-detect port serial atau gunakan yang diberikan."""
    if preferred:
        return preferred

    try:
        import serial.tools.list_ports
        ports = list(serial.tools.list_ports.comports())
    except Exception:
        ports = []

    if not ports:
        port = input("📡 Masukkan nama port Serial (misal COM18): ").strip()
        return port

    print("📡 Port Serial yang tersedia:")
    for i, p in enumerate(ports):
        print(f"  [{i}] {p.device}  – {p.description}")

    idx = input("Pilih nomor port (atau ketik nama port langsung): ").strip()
    try:
        num = int(idx)
        if 0 <= num < len(ports):
            return ports[num].device
        return f"COM{num}"
    except ValueError:
        return idx


# ═════════════════════════════════════════════════════════════════════════════
#  AKUISISI 1 SIKLUS
# ═════════════════════════════════════════════════════════════════════════════

def run_single_cycle(ser):
    """
    Jalankan 1 siklus akuisisi (purging + collecting) lalu kirim #stop;.

    Returns:
        list[dict]: Data sampel sensor selama fase 'collecting' dari siklus 1.
        None jika gagal atau dibatalkan.
    """
    collecting_samples = []
    cycle_done = False
    current_phase = 'idle'
    current_cycle = 0
    acq_started = False
    collect_s = 180
    purge_s = 60

    # Flush buffer serial
    ser.reset_input_buffer()
    time.sleep(0.2)

    # Kirim #start;
    ser.write(b'#start;')
    print("📤 Mengirim #start; ke ATmega...")
    print()

    phase_start_time = time.time()

    while not cycle_done:
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

            event = data.get('event', '')

            # ── Event: ACQ_START ──
            if event == 'ACQ_START':
                acq_started = True
                collect_s = data.get('collect_s', 180)
                purge_s = data.get('purge_s', 60)
                current_cycle = data.get('cycle', 1)
                current_phase = 'purging'
                phase_start_time = time.time()
                print(f"🚀 Akuisisi dimulai — Siklus 1 ({purge_s}s purging + {collect_s}s collecting)")
                print()
                continue

            # ── Event: PHASE_CHANGE ──
            if event == 'PHASE_CHANGE':
                new_phase = data.get('phase', '')
                new_cycle = data.get('cycle', current_cycle)

                # Siklus 1 collecting selesai → siklus 2 purging dimulai → STOP
                if new_cycle >= 2 and new_phase == 'purging':
                    print()
                    print(f"✅ Siklus 1 selesai! ({len(collecting_samples)} sampel collecting)")
                    # Kirim #stop; untuk menghentikan siklus berikutnya
                    ser.write(b'#stop;')
                    time.sleep(0.3)
                    # Flush remaining data
                    ser.reset_input_buffer()
                    cycle_done = True
                    continue

                # Transisi purging → collecting di siklus 1
                if new_phase == 'collecting' and new_cycle == 1:
                    current_phase = 'collecting'
                    phase_start_time = time.time()
                    clear_line()
                    print("🟢 Fase COLLECTING dimulai — Menghirup aroma kopi...")
                    continue

                current_phase = new_phase
                current_cycle = new_cycle
                phase_start_time = time.time()
                continue

            # ── Event: ACQ_COMPLETE (jika ACQ_REPETITIONS=1) ──
            if event == 'ACQ_COMPLETE':
                print()
                print(f"✅ Akuisisi selesai! ({len(collecting_samples)} sampel collecting)")
                cycle_done = True
                continue

            # ── Event: ACQ_STOP (konfirmasi stop) ──
            if event == 'ACQ_STOP':
                cycle_done = True
                continue

            # ── Data Sampel Sensor ──
            phase = data.get('phase', 'idle')
            if phase in ('collecting', 'purging') and any(k in data for k in ADC_COLS):
                elapsed = time.time() - phase_start_time

                if phase == 'purging':
                    remaining = max(0, purge_s - elapsed)
                    clear_line()
                    bar_len = 30
                    progress = min(1.0, elapsed / purge_s)
                    filled = int(bar_len * progress)
                    bar = '█' * filled + '░' * (bar_len - filled)
                    print(f"  🔴 PURGING  |{bar}| {int(remaining):>3}s tersisa", end='', flush=True)

                elif phase == 'collecting':
                    # Simpan data collecting siklus 1
                    sample = {}
                    for col in ADC_COLS:
                        sample[col] = data.get(col, 0)
                    collecting_samples.append(sample)

                    remaining = max(0, collect_s - elapsed)
                    clear_line()
                    bar_len = 30
                    progress = min(1.0, elapsed / collect_s)
                    filled = int(bar_len * progress)
                    bar = '█' * filled + '░' * (bar_len - filled)
                    print(f"  🟢 COLLECT  |{bar}| {int(remaining):>3}s tersisa  [{len(collecting_samples)} sampel]", end='', flush=True)

        except KeyboardInterrupt:
            print("\n\n⏹️  Dibatalkan oleh user.")
            ser.write(b'#stop;')
            time.sleep(0.3)
            return None
        except Exception as e:
            print(f"\n❌ Error serial: {e}")
            return None

    print()
    if len(collecting_samples) < 10:
        print(f"⚠️  Terlalu sedikit sampel collecting ({len(collecting_samples)}). Minimal 10.")
        return None

    return collecting_samples


# ═════════════════════════════════════════════════════════════════════════════
#  EKSTRAKSI FITUR (identik dengan 4_train_rf.py)
# ═════════════════════════════════════════════════════════════════════════════

def extract_features_from_samples(samples):
    """
    Ekstraksi 48 fitur dari satu siklus collecting.

    Args:
        samples: list[dict] — data sensor per detik selama collecting.

    Returns:
        dict: 48 fitur (mean, max, sum, ratios) — siap untuk prediksi/training.
    """
    df = pd.DataFrame(samples)

    row = {}

    # Mean, Max, Sum per sensor
    for col in ADC_COLS:
        vals = pd.to_numeric(df[col], errors='coerce').fillna(0).to_numpy()
        row[f'mean_{col}'] = float(np.mean(vals))
        row[f'max_{col}']  = float(np.max(vals))
        row[f'sum_{col}']  = float(np.sum(vals))

    # Ratios to MQ135
    mq135_max = row['max_adc_mq135'] if row['max_adc_mq135'] > 0 else 1.0
    for col in ADC_COLS:
        if col != 'adc_mq135':
            row[f'ratio_to_mq135_{col}'] = row[f'max_{col}'] / mq135_max

    # Ratios to TGS822
    tgs822_max = row['max_adc_tgs822'] if row['max_adc_tgs822'] > 0 else 1.0
    for col in ADC_COLS:
        if col != 'adc_tgs822':
            row[f'ratio_to_tgs822_{col}'] = row[f'max_{col}'] / tgs822_max

    return row


# ═════════════════════════════════════════════════════════════════════════════
#  PREDIKSI
# ═════════════════════════════════════════════════════════════════════════════

def load_model():
    """Muat model RF dari joblib. Return None jika belum ada."""
    if os.path.exists(MODEL_PATH):
        try:
            clf = joblib.load(MODEL_PATH)
            return clf
        except Exception as e:
            print(f"⚠️  Gagal memuat model: {e}")
    return None


def predict(clf, features):
    """
    Prediksi label dari 48 fitur.

    Returns:
        (predicted_label, confidence_dict)
    """
    X = np.array([[features.get(col, 0) for col in FEATURE_COLS]], dtype=np.float32)
    pred = clf.predict(X)[0]

    # Confidence per kelas
    proba = clf.predict_proba(X)[0]
    classes = clf.classes_
    conf = {str(c): float(p) for c, p in zip(classes, proba)}

    return str(pred), conf


# ═════════════════════════════════════════════════════════════════════════════
#  SIMPAN DATA INTERAKTIF
# ═════════════════════════════════════════════════════════════════════════════

def save_interactive_sample(features, label, session_id, cycle_num):
    """
    Simpan 1 sampel berlabel ke dataset_interactive.csv (append mode).
    """
    row = {
        'source_file': f'interactive_{session_id}',
        'label': label,
        'cycle': cycle_num,
        'n_samples': 0,
    }
    row.update(features)

    df_new = pd.DataFrame([row])

    if os.path.exists(INTERACTIVE_CSV):
        df_new.to_csv(INTERACTIVE_CSV, mode='a', header=False, index=False)
    else:
        df_new.to_csv(INTERACTIVE_CSV, index=False)

    return True


# ═════════════════════════════════════════════════════════════════════════════
#  RETRAIN MODEL
# ═════════════════════════════════════════════════════════════════════════════

def load_combined_dataset():
    """
    Gabungkan dataset batch (dataset_fitur.csv) + interactive (dataset_interactive.csv).

    Returns:
        (X, y, n_batch, n_interactive)
    """
    dfs = []

    # Dataset batch (dari 4_train_rf.py)
    n_batch = 0
    if os.path.exists(BATCH_DATASET):
        df_batch = pd.read_csv(BATCH_DATASET)
        df_batch = df_batch[df_batch['label'].isin(VALID_LABELS)]
        n_batch = len(df_batch)
        if n_batch > 0:
            dfs.append(df_batch)

    # Dataset interaktif
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

    # Pastikan semua feature cols ada
    available_cols = [c for c in FEATURE_COLS if c in df_all.columns]
    X = df_all[available_cols].fillna(0).to_numpy(dtype=np.float32)
    y = df_all['label'].astype(str).to_numpy()

    return X, y, n_batch, n_interactive


def retrain_model():
    """
    Retrain model RF dari gabungan seluruh dataset.

    Returns:
        (clf, cv_acc, cv_std, total_samples) atau None jika gagal.
    """
    X, y, n_batch, n_interactive = load_combined_dataset()

    if X is None or len(X) < 3:
        print(f"⚠️  Dataset terlalu kecil ({0 if X is None else len(X)} sampel). Minimal 3.")
        return None

    total = len(X)
    print(f"\n📊 Dataset gabungan: {total} sampel (batch={n_batch}, interaktif={n_interactive})")

    # Distribusi kelas
    unique, counts = np.unique(y, return_counts=True)
    for label, count in zip(unique, counts):
        print(f"   {label:>8}: {count} sampel")

    # Cross-validation (jika cukup data)
    clf = RandomForestClassifier(
        n_estimators=RF_N_ESTIMATORS,
        max_depth=RF_MAX_DEPTH,
        random_state=RF_RANDOM_STATE,
        class_weight='balanced'
    )

    cv_acc = 0.0
    cv_std = 0.0

    n_classes = len(unique)
    min_class_count = min(counts)

    if total >= 6 and n_classes >= 2 and min_class_count >= 2:
        n_splits = min(5, min_class_count)
        cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=RF_RANDOM_STATE)
        scores = cross_val_score(clf, X, y, cv=cv, scoring='accuracy')
        cv_acc = scores.mean() * 100
        cv_std = scores.std() * 100
        print(f"\n📈 Cross-Validation Accuracy: {cv_acc:.2f}% ± {cv_std:.2f}%")

    # Train final model pada seluruh dataset
    clf.fit(X, y)
    joblib.dump(clf, MODEL_PATH)
    print(f"💾 Model disimpan: {MODEL_PATH}")

    return clf, cv_acc, cv_std, total


# ═════════════════════════════════════════════════════════════════════════════
#  EXPORT C++ HEADER
# ═════════════════════════════════════════════════════════════════════════════

def export_cpp_header():
    """Export model terbaru ke C++ header untuk ATmega2560."""
    try:
        sys.path.insert(0, SCRIPTS_DIR)
        from generate_model_atmega import export_model_atmega
        success = export_model_atmega(
            MODEL_PATH, OUTPUT_HEADER,
            max_trees=RF_N_ESTIMATORS,
            max_depth=RF_MAX_DEPTH
        )
        if success:
            size_kb = os.path.getsize(OUTPUT_HEADER) / 1024
            print(f"✅ C++ header diekspor: {OUTPUT_HEADER} ({size_kb:.1f} KB)")
        else:
            print("❌ Gagal mengekspor C++ header.")
        return success
    except Exception as e:
        print(f"❌ Error export: {e}")
        return False


# ═════════════════════════════════════════════════════════════════════════════
#  MAIN INTERACTIVE LOOP
# ═════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description='E-NOSE Kopi — Interactive Active Learning')
    parser.add_argument('--port', type=str, default=None, help='Port Serial (misal COM18)')
    parser.add_argument('--baud', type=int, default=BAUD_RATE)
    args = parser.parse_args()

    print_header()

    # ── Koneksi Serial ──
    port = find_serial_port(args.port)
    print(f"\n🔌 Menghubungkan ke {port} @ {args.baud} baud...")

    try:
        ser = Serial(port, args.baud, timeout=2)
        time.sleep(2)  # Tunggu Arduino reset
        ser.reset_input_buffer()
        print(f"✅ Terhubung ke {port}")
    except Exception as e:
        print(f"❌ Gagal terhubung: {e}")
        sys.exit(1)

    # ── Load model awal (jika ada) ──
    clf = load_model()
    if clf is not None:
        n_classes = len(clf.classes_)
        print(f"📦 Model awal dimuat: {clf.n_estimators} trees, {n_classes} kelas ({', '.join(clf.classes_)})")
    else:
        print("📦 Belum ada model. Tebakan akan tersedia setelah minimal 3 sampel berlabel.")

    # ── Session ID ──
    session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
    cycle_num = 0
    model_updated = False

    print()
    print("═" * 60)
    print("  Letakkan sampel kopi di depan sensor E-Nose, lalu")
    print("  tekan ENTER untuk memulai 1 siklus akuisisi.")
    print("  Ketik 'q' untuk keluar.")
    print("═" * 60)

    try:
        while True:
            print()
            user_input = input("▶ Tekan ENTER untuk mulai siklus berikutnya (atau 'q' untuk keluar): ").strip().lower()

            if user_input == 'q':
                break

            cycle_num += 1
            print(f"\n{'─' * 60}")
            print(f"  SIKLUS #{cycle_num}")
            print(f"{'─' * 60}")

            # ── 1. Jalankan 1 siklus akuisisi ──
            samples = run_single_cycle(ser)
            if samples is None:
                print("⚠️  Siklus dibatalkan atau gagal. Coba lagi.")
                cycle_num -= 1
                continue

            # ── 2. Ekstraksi fitur ──
            features = extract_features_from_samples(samples)
            n_samples = len(samples)
            features['n_samples'] = n_samples

            print(f"\n🔢 Fitur diekstrak: {len(FEATURE_COLS)} fitur dari {n_samples} sampel")

            # Tampilkan top 3 sensor responses
            print("   Respon sensor tertinggi:")
            max_vals = [(col.replace('adc_', '').upper(), features[f'max_{col}'])
                        for col in ADC_COLS]
            max_vals.sort(key=lambda x: x[1], reverse=True)
            for name, val in max_vals[:3]:
                print(f"     • {name:<10}: {val:.0f}")

            # ── 3. Prediksi (jika model tersedia) ──
            if clf is not None:
                pred_label, confidence = predict(clf, features)
                print(f"\n🤖 Tebakan Model: ╔═══════════════════════════╗")
                print(f"                  ║  {pred_label.upper():^23}  ║")
                print(f"                  ╚═══════════════════════════╝")
                print(f"   Confidence:")
                for label in VALID_LABELS:
                    conf_val = confidence.get(label, 0) * 100
                    bar_len = int(conf_val / 5)
                    bar = '█' * bar_len
                    marker = " ◄" if label == pred_label else ""
                    print(f"     {label:>7}: {bar:<20} {conf_val:5.1f}%{marker}")
            else:
                print("\n🤖 Model belum tersedia — tidak bisa menebak.")
                pred_label = None

            # ── 4. Minta koreksi dari user ──
            print(f"\n📝 Apa label yang BENAR untuk sampel ini?")
            print(f"   [1] Light    [2] Medium    [3] Dark    [S] Skip (tidak simpan)")
            if pred_label:
                default_idx = VALID_LABELS.index(pred_label) + 1 if pred_label in VALID_LABELS else 0
                prompt = f"   Pilihan [{default_idx} = {pred_label}]: "
            else:
                prompt = "   Pilihan: "

            choice = input(prompt).strip().lower()

            if choice == 's':
                print("⏭️  Sampel dilewati (tidak disimpan).")
                continue

            # Map input ke label
            if choice == '1':
                correct_label = 'light'
            elif choice == '2':
                correct_label = 'medium'
            elif choice == '3':
                correct_label = 'dark'
            elif choice == '' and pred_label:
                correct_label = pred_label
                print(f"   → Menggunakan tebakan model: {correct_label}")
            elif choice in VALID_LABELS:
                correct_label = choice
            else:
                print("⚠️  Input tidak valid. Sampel dilewati.")
                continue

            # Tampilkan koreksi
            if pred_label and correct_label != pred_label:
                print(f"   ✏️  Koreksi: {pred_label} → {correct_label}")
            elif pred_label and correct_label == pred_label:
                print(f"   ✅ Konfirmasi: tebakan {pred_label} BENAR!")
            else:
                print(f"   📌 Label: {correct_label}")

            # ── 5. Simpan sampel berlabel ──
            save_interactive_sample(features, correct_label, session_id, cycle_num)
            print(f"💾 Sampel disimpan ke dataset_interactive.csv")

            # ── 6. Retrain model ──
            print("\n🔄 Melatih ulang model Random Forest...")
            result = retrain_model()
            if result is not None:
                clf, cv_acc, cv_std, total = result
                model_updated = True
                print(f"\n✅ Model diperbarui! ({total} sampel total)")
            else:
                print("⚠️  Retrain gagal. Model lama tetap digunakan.")

    except KeyboardInterrupt:
        print("\n\n⏹️  Dihentikan oleh user.")

    # ── Cleanup & Export ──
    print(f"\n{'═' * 60}")
    print(f"  RINGKASAN SESI")
    print(f"{'═' * 60}")
    print(f"  Siklus selesai : {cycle_num}")
    print(f"  Session ID     : {session_id}")

    if model_updated:
        print(f"\n🛠️  Mengekspor model terbaru ke C++ header...")
        export_cpp_header()

    # Tutup serial
    try:
        ser.close()
        print(f"\n🔌 Serial {port} ditutup.")
    except Exception:
        pass

    print()
    print("══════════════════════════════════════════════════════════════")
    print("  Selesai! Langkah selanjutnya:")
    print("    1. Flash firmware ke ATmega2560: pio run -t upload")
    print("    2. Alat siap melakukan inferensi on-device!")
    print("══════════════════════════════════════════════════════════════")
    print()


if __name__ == '__main__':
    main()
