"""
3_collect_data.py
═══════════════════════════════════════════════════════════════════════════════
Script pengumpulan data E-NOSE Kopi via Serial ke CSV.

Alur:
  1. User masukkan label roasting (light / medium / dark)
  2. Script kirim #start; ke ESP32
  3. ESP32 mulai siklus Collecting (180 s) → Purging (60 s) × 10 siklus
  4. Data JSON diterima setiap detik, disimpan ke CSV
     (collecting = data dari aroma kopi, purging = baseline udara bebas)
  5. Setelah COMPLETE, file CSV disimpan otomatis

Cara pakai:
  pip install pyserial pandas tqdm
  python 3_collect_data.py --port COM5 --label light_roast

Atau jalankan tanpa argumen untuk mode interaktif:
  python 3_collect_data.py
═══════════════════════════════════════════════════════════════════════════════
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime

import pandas as pd
from serial import Serial
from tqdm import tqdm

# ─── Konfigurasi ─────────────────────────────────────────────────────────────
BAUD_RATE        = 115200
OUTPUT_DIR       = os.path.join(os.path.dirname(__file__), '..', 'data')
ACQ_COLLECT_S    = 180   # harus sama dengan ACQ_COLLECTION_SECONDS di firmware
ACQ_PURGE_S      = 60    # harus sama dengan ACQ_PURGE_SECONDS di firmware
ACQ_REPETITIONS  = 10    # harus sama dengan ACQ_REPETITIONS di firmware

VALID_LABELS = ['light', 'medium', 'dark']

# Kolom ADC mentah (urutan fitur untuk inferensi on-device)
ADC_COLS = ['adc_mq135', 'adc_mq136', 'adc_mq137', 'adc_mq138',
            'adc_mq2',   'adc_mq3',   'adc_tgs822', 'adc_tgs2620']

# ─── Argumen CLI ─────────────────────────────────────────────────────────────
def parse_args():
    p = argparse.ArgumentParser(description='E-NOSE Kopi — Pengumpulan Data')
    p.add_argument('--port',  type=str, default=None,
                   help='Port Serial ESP32, misal COM5 atau /dev/ttyUSB0')
    p.add_argument('--label', type=str, default=None,
                   help=f'Label roasting: {VALID_LABELS}')
    p.add_argument('--baud',  type=int, default=BAUD_RATE)
    p.add_argument('--collect-s', type=int, default=ACQ_COLLECT_S,
                   help='Durasi collecting (detik)')
    p.add_argument('--purge-s', type=int, default=ACQ_PURGE_S,
                   help='Durasi purging (detik)')
    p.add_argument('--repetitions', type=int, default=ACQ_REPETITIONS,
                   help='Jumlah siklus pengulangan')
    return p.parse_args()


def prompt_port():
    """Daftar port serial yang tersedia dan minta user pilih."""
    try:
        import serial.tools.list_ports
        ports = list(serial.tools.list_ports.comports())
    except Exception:
        ports = []

    if ports:
        print("\n📡 Port Serial yang tersedia:")
        for i, p in enumerate(ports):
            print(f"  [{i}] {p.device}  – {p.description}")
        idx = input("Pilih nomor port (atau ketik nama port langsung): ").strip()
        try:
            return ports[int(idx)].device
        except (ValueError, IndexError):
            return idx
    else:
        return input("Masukkan nama port Serial (misal COM5): ").strip()


def prompt_label():
    print(f"\n🏷️  Label tingkat roasting yang tersedia: {VALID_LABELS}")
    label = input("Masukkan label: ").strip().lower()
    if label not in VALID_LABELS:
        print(f"⚠️  Label tidak dikenal. Tetap menggunakan '{label}' sebagai label kustom.")
    return label


# ─── Progress bar helper ──────────────────────────────────────────────────────
class PhaseBar:
    def __init__(self, total, desc, unit='sampel'):
        self.bar = tqdm(total=total, desc=desc, unit=unit,
                        bar_format='{l_bar}{bar}| {n}/{total} [{elapsed}<{remaining}]',
                        colour='green', ncols=80)
        self.n = 0

    def update(self):
        self.bar.update(1)
        self.n += 1

    def close(self):
        self.bar.close()


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    args = parse_args()

    # ── Validasi / prompt parameter ──────────────────────────────────────────
    port  = args.port  or prompt_port()
    label = args.label or prompt_label()

    collect_s   = args.collect_s
    purge_s     = args.purge_s
    repetitions = args.repetitions

    total_collect = collect_s * repetitions  # jumlah sampel collecting yang diharapkan
    total_purge   = purge_s  * repetitions   # jumlah sampel purging yang diharapkan

    print(f"""
╔══════════════════════════════════════════════════════╗
║       E-NOSE Kopi — Pengumpulan Data                ║
╠══════════════════════════════════════════════════════╣
║  Label      : {label:<36} ║
║  Port       : {port:<36} ║
║  Collecting : {collect_s} detik × {repetitions} siklus = {total_collect} sampel{'':<6} ║
║  Purging    : {purge_s} detik × {repetitions} siklus = {total_purge} sampel{'':<7} ║
╚══════════════════════════════════════════════════════╝
""")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_csv = os.path.join(OUTPUT_DIR, f'{label}_{timestamp_str}.csv')

    # ── Buka Serial ──────────────────────────────────────────────────────────
    try:
        ser = Serial(port=port, baudrate=args.baud, timeout=2)
        print(f"✅ Serial terbuka: {port} @ {args.baud} baud")
    except Exception as e:
        print(f"❌ Gagal membuka Serial: {e}")
        sys.exit(1)

    time.sleep(2)  # tunggu ESP32 boot / reset

    rows = []          # daftar dict yang akan jadi CSV
    current_phase = 'idle'
    current_cycle = 0
    collecting_bar = None
    purging_bar    = None

    def flush_bars():
        nonlocal collecting_bar, purging_bar
        if collecting_bar: collecting_bar.close(); collecting_bar = None
        if purging_bar:    purging_bar.close();    purging_bar    = None

    try:
        # Kirim perintah #start; ke ESP32
        ser.write(b'#start;')
        print("📤 Mengirim #start; ke ESP32...\n")
        time.sleep(0.5)

        acquisition_done = False

        while not acquisition_done:
            raw = ser.readline()
            if not raw:
                continue

            line = raw.decode('utf-8', errors='ignore').strip()
            if not line:
                continue

            # ── Parse JSON ──────────────────────────────────────────────────
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                # bukan JSON valid → abaikan (bisa pesan debug firmware)
                print(f"  [non-JSON] {line[:80]}")
                continue

            event = data.get('event', '')

            # ── Event: ACQ_START ─────────────────────────────────────────────
            if event == 'ACQ_START':
                collect_s   = data.get('collect_s',   collect_s)
                purge_s     = data.get('purge_s',     purge_s)
                repetitions = data.get('cycles_total', repetitions)
                total_collect = collect_s * repetitions
                total_purge   = purge_s  * repetitions
                print(f"🚀 Akuisisi dimulai — {repetitions} siklus × ({collect_s}s collecting + {purge_s}s purging)")
                current_cycle = data.get('cycle', 1)
                collecting_bar = PhaseBar(collect_s, f"  🫁 Cycle {current_cycle:02d}/{repetitions} Collecting")
                continue

            # ── Event: PHASE_CHANGE ──────────────────────────────────────────
            if event == 'PHASE_CHANGE':
                flush_bars()
                current_cycle = data.get('cycle', current_cycle)
                new_phase     = data.get('phase', 'idle')
                if new_phase == 'purging':
                    purging_bar = PhaseBar(purge_s, f"  💨 Cycle {current_cycle:02d}/{repetitions} Purging ")
                elif new_phase == 'collecting':
                    collecting_bar = PhaseBar(collect_s, f"  🫁 Cycle {current_cycle:02d}/{repetitions} Collecting")
                continue

            # ── Event: ACQ_COMPLETE ──────────────────────────────────────────
            if event == 'ACQ_COMPLETE':
                flush_bars()
                total = data.get('total_samples', len(rows))
                print(f"\n✅ Akuisisi selesai! Total sampel diterima: {total}")
                acquisition_done = True
                continue

            # ── Event: INFERENCE (on-device) ─────────────────────────────────
            if event == 'INFERENCE':
                result = data.get('result', '?')
                n_feat = data.get('feat_count', '-')
                print(f"\n🤖 Hasil Inferensi On-Device: \033[1;33m{result.upper()}\033[0m  (dari {n_feat} sampel)")
                continue

            # ── Event: ACQ_STOP (user hentikan manual) ───────────────────────
            if event == 'ACQ_STOP':
                flush_bars()
                print("\n⏹️  Akuisisi dihentikan manual.")
                acquisition_done = True
                continue

            # ── Data sampel sensor ────────────────────────────────────────────
            phase      = data.get('phase', 'idle')
            cycle      = data.get('cycle', 0)
            sample_idx = data.get('sample_idx', 0)

            # Update progress bar
            if phase == 'collecting' and collecting_bar:
                collecting_bar.update()
            elif phase == 'purging' and purging_bar:
                purging_bar.update()

            # Simpan semua sampel (collecting + purging) ke rows
            if phase in ('collecting', 'purging'):
                row = {'label': label, 'source_file': out_csv}
                row.update(data)
                rows.append(row)

    except KeyboardInterrupt:
        print("\n\n⚠️  Dihentikan oleh user (Ctrl+C)")
        try:
            ser.write(b'#stop;')
            print("📤 Mengirim #stop; ke ESP32...")
        except Exception:
            pass
    finally:
        flush_bars()
        ser.close()

    # ── Simpan ke CSV ─────────────────────────────────────────────────────────
    if rows:
        df = pd.DataFrame(rows)

        # Urutkan kolom: metadata dulu, baru sensor
        priority_cols = ['label', 'phase', 'cycle', 'sample_idx', 'timestamp'] + ADC_COLS + ['temp', 'humidity']
        other_cols    = [c for c in df.columns if c not in priority_cols and c != 'source_file']
        ordered_cols  = [c for c in priority_cols if c in df.columns] + other_cols
        if 'source_file' in df.columns:
            ordered_cols.append('source_file')
        df = df[ordered_cols]

        df.to_csv(out_csv, index=False)

        collecting_n = len(df[df['phase'] == 'collecting'])
        purging_n    = len(df[df['phase'] == 'purging'])
        print(f"""
📄 Data disimpan ke: {out_csv}
   Label       : {label}
   Collecting  : {collecting_n} baris
   Purging     : {purging_n} baris
   Total baris : {len(df)}
   Kolom       : {len(df.columns)}

💡 Langkah selanjutnya:
   Jalankan: python 4_train_rf.py
""")
    else:
        print("\n⚠️  Tidak ada data yang diterima. File CSV tidak dibuat.")


if __name__ == '__main__':
    main()
