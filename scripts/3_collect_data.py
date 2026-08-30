"""
3_collect_data.py
═══════════════════════════════════════════════════════════════════════════════
Script Pengumpulan RAW DATA E-NOSE Kopi via Serial ke CSV (dengan Live Plot).

Eksperimen 11 Sampel Kopi:
  LIGHT  : L-MAN (Manglayang Jabar), L-RAT (Ratawali Aceh), L-GAY (Gayo Aceh), L-MER (Merapi)
  MEDIUM : M-MAN (Manglayang Jabar), M-RAT (Ratawali Aceh), M-TEM (Temanggung), M-TIM (Timor Leste)
  DARK   : D-MAN (Manglayang Jabar), D-RAT (Ratawali Aceh), D-GAY (Gayo Aceh)

Flow per Sampel (10 Run):
  Satu Run  : PURGING (30 s) ──► COLLECTING (180 s) ──► Simpan Raw Data
  Satu File : 10 Run per Sampel ──► Output CSV: <sample_id>_<batch_id>.csv

Metadata per Baris:
  timestamp, sample_id, roast_level, origin, batch_id, run_id, phase, sample_idx,
  10 Raw ADC Readings (adc_tgs822, adc_mq135, adc_mq9, adc_tgs2611, adc_tgs2620,
  adc_tgs2600, adc_tgs2602, adc_mq8, adc_tgs813, adc_tgs816), temperature, humidity

Cara Pakai:
  python 3_collect_data.py
  python 3_collect_data.py --port COM5 --sample L-MAN --batch B01
  python 3_collect_data.py --no-plot
═══════════════════════════════════════════════════════════════════════════════
"""

import argparse
import json
import os
import sys
import time
import threading
from collections import deque
from datetime import datetime

import pandas as pd
from serial import Serial

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.animation as animation

try:
    matplotlib.use('TkAgg')
except Exception:
    pass

# ─── Konfigurasi Akuisisi Default ──────────────────────────────────────────────
BAUD_RATE        = 115200
OUTPUT_DIR       = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'data'))
ACQ_PURGE_S      = 120    # Durasi purging per run (detik)
ACQ_COLLECT_S    = 120   # Durasi collecting per run (detik)
ACQ_REPETITIONS  = 5    # Jumlah run per sampel kopi

# ─── Database Sampel Eksperimen (Predefined Metadata) ───────────────────────────
KNOWN_SAMPLES = {
    # LIGHT ROAST
    'L-MAN': {'roast_level': 'light',  'origin': 'Arabika Manglayang Jawa Barat'},
    'L-RAT': {'roast_level': 'light',  'origin': 'Arabika Ratawali Aceh'},
    'L-GAY': {'roast_level': 'light',  'origin': 'Arabika Gayo Aceh'},
    'L-MER': {'roast_level': 'light',  'origin': 'Arabika Merapi'},

    # MEDIUM ROAST
    'M-MAN': {'roast_level': 'medium', 'origin': 'Arabika Manglayang Jawa Barat'},
    'M-RAT': {'roast_level': 'medium', 'origin': 'Arabika Ratawali Aceh'},
    'M-TEM': {'roast_level': 'medium', 'origin': 'Arabika Temanggung'},
    'M-TIM': {'roast_level': 'medium', 'origin': 'Arabika Timor Leste'},

    # DARK ROAST
    'D-MAN': {'roast_level': 'dark',   'origin': 'Arabika Manglayang Jawa Barat'},
    'D-RAT': {'roast_level': 'dark',   'origin': 'Arabika Ratawali Aceh'},
    'D-GAY': {'roast_level': 'dark',   'origin': 'Arabika Gayo Aceh'},
    'D-BAR': {'roast_level': 'dark',   'origin': 'Arabika Jawa Barat'},
}

VALID_ROAST_LEVELS = ['light', 'medium', 'dark']

# Kolom Raw ADC 10 Sensor Gas E-NOSE v2
ADC_COLS = [
    'adc_tgs822', 'adc_mq135', 'adc_mq9', 'adc_tgs2611', 'adc_tgs2620',
    'adc_tgs2600', 'adc_tgs2602', 'adc_mq8', 'adc_tgs813', 'adc_tgs816'
]

SENSOR_CONFIG = {
    'adc_tgs822':  {'label': 'TGS822',  'color': '#00E676', 'group': 'TGS'},
    'adc_tgs2611': {'label': 'TGS2611', 'color': '#00BFA5', 'group': 'TGS'},
    'adc_tgs2620': {'label': 'TGS2620', 'color': '#18FFFF', 'group': 'TGS'},
    'adc_tgs2600': {'label': 'TGS2600', 'color': '#64FFDA', 'group': 'TGS'},
    'adc_tgs2602': {'label': 'TGS2602', 'color': '#A7FFEB', 'group': 'TGS'},
    'adc_tgs813':  {'label': 'TGS813',  'color': '#B2FF59', 'group': 'TGS'},
    'adc_tgs816':  {'label': 'TGS816',  'color': '#76FF03', 'group': 'TGS'},
    'adc_mq135':   {'label': 'MQ135',   'color': '#FF6D00', 'group': 'MQ'},
    'adc_mq9':     {'label': 'MQ9',     'color': '#FF3D00', 'group': 'MQ'},
    'adc_mq8':     {'label': 'MQ8',     'color': '#FFAB00', 'group': 'MQ'},
}

# ─── CLI Argument Parser ──────────────────────────────────────────────────────
def parse_args():
    p = argparse.ArgumentParser(description='E-NOSE Kopi — Pengumpulan Raw Data')
    p.add_argument('--port',        type=str, default=None, help='Port Serial (misal COM5)')
    p.add_argument('--sample',      type=str, default=None, help='Sample ID (misal L-MAN, M-TEM, D-RAT)')
    p.add_argument('--roast-level', type=str, default=None, help='Roast Level (light, medium, dark)')
    p.add_argument('--origin',      type=str, default=None, help='Asal Kopi (Origin)')
    p.add_argument('--batch',       type=str, default=None, help='Batch ID (misal B01)')
    p.add_argument('--baud',        type=int, default=BAUD_RATE)
    p.add_argument('--purge-s',     type=int, default=ACQ_PURGE_S,   help='Durasi purging per run (s)')
    p.add_argument('--collect-s',   type=int, default=ACQ_COLLECT_S, help='Durasi collecting per run (s)')
    p.add_argument('--repetitions', type=int, default=ACQ_REPETITIONS, help='Jumlah run (default 10)')
    p.add_argument('--no-plot',     action='store_true', help='Matikan GUI grafik real-time')
    return p.parse_args()


# ─── Interactive Prompt Helpers ───────────────────────────────────────────────
def prompt_port():
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
            num = int(idx)
            if 0 <= num < len(ports):
                return ports[num].device
            else:
                return f"COM{num}"
        except ValueError:
            return idx
    else:
        return input("Masukkan nama port Serial (misal COM5): ").strip()


def prompt_metadata():
    """Meminta input Sample ID, Roast Level, Origin, dan Batch ID secara interaktif."""
    print("\n📋 SAMPLING METADATA ENTRY")
    print("Daftar Sample ID Terdaftar:")
    for sid, info in KNOWN_SAMPLES.items():
        print(f"  • {sid:<6} : {info['roast_level'].upper():<7} | {info['origin']}")

    # 1. Sample ID
    sid = input("\nMasukkan Sample ID (misal L-MAN): ").strip().upper()

    if sid in KNOWN_SAMPLES:
        default_roast = KNOWN_SAMPLES[sid]['roast_level']
        default_origin = KNOWN_SAMPLES[sid]['origin']
        print(f"  ✓ Terdeteksi preset: Roast={default_roast}, Origin={default_origin}")

        roast_in = input(f"Masukkan Roast Level [{default_roast}]: ").strip().lower()
        roast_level = roast_in if roast_in else default_roast

        origin_in = input(f"Masukkan Origin [{default_origin}]: ").strip()
        origin = origin_in if origin_in else default_origin
    else:
        roast_level = input("Masukkan Roast Level (light/medium/dark): ").strip().lower()
        origin = input("Masukkan Origin (asal kopi): ").strip()

    # Batch ID
    batch_in = input("Masukkan Batch ID [default: B01]: ").strip().upper()
    batch_id = batch_in if batch_in else "B01"

    return sid, roast_level, origin, batch_id


# ─── Data Collector & Store Thread ──────────────────────────────────────────
class RawDataCollector:
    def __init__(self, ser, sample_id, roast_level, origin, batch_id, out_csv):
        self.ser = ser
        self.sample_id = sample_id
        self.roast_level = roast_level
        self.origin = origin
        self.batch_id = batch_id
        self.out_csv = out_csv
        self.lock = threading.Lock()

        self.rows = []
        self.acquisition_done = False
        self.stop_requested = False

        # Data Deques untuk Live Plotting
        self.max_plot_pts = 600
        self.timestamps = deque(maxlen=self.max_plot_pts)
        self.sensor_data = {col: deque(maxlen=self.max_plot_pts) for col in ADC_COLS}

        # Status State
        self.phase = 'idle'
        self.cycle = 0          # run_id (1 s.d. 10)
        self.cycles_total = ACQ_REPETITIONS
        self.collect_s = ACQ_COLLECT_S
        self.purge_s = ACQ_PURGE_S
        self.status_msg = 'Menunggu data serial...'

    def run(self):
        """Thread penerima data Serial dari ATmega 2560."""
        try:
            self.ser.write(b'#start;')
            print("📤 Mengirim perintah #start; ke ATmega 2560...\n")
            time.sleep(0.5)

            while not self.acquisition_done and not self.stop_requested:
                raw = self.ser.readline()
                if not raw:
                    continue

                line = raw.decode('utf-8', errors='ignore').strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    print(f"  [non-JSON] {line[:80]}")
                    continue

                event = data.get('event', '')

                if event == 'ACQ_START':
                    self.collect_s = data.get('collect_s', self.collect_s)
                    self.purge_s = data.get('purge_s', self.purge_s)
                    self.cycles_total = data.get('cycles_total', self.cycles_total)
                    self.cycle = data.get('cycle', 1)
                    self.phase = data.get('phase', 'purging')
                    self.status_msg = f"🚀 Start: Run 01/{self.cycles_total:02d} ({self.phase.upper()})"
                    print(f"🚀 Akuisisi Dimulai — {self.cycles_total} Run × ({self.purge_s}s purging + {self.collect_s}s collecting)")
                    continue

                if event == 'PHASE_CHANGE':
                    self.cycle = data.get('cycle', self.cycle)
                    self.phase = data.get('phase', self.phase)
                    self.status_msg = f"Phase -> {self.phase.upper()} (Run {self.cycle:02d}/{self.cycles_total:02d})"
                    print(f"  🔄 Phase: {self.phase.upper()} | Run {self.cycle:02d}/{self.cycles_total:02d}")
                    continue

                if event == 'ACQ_COMPLETE':
                    total = data.get('total_samples', len(self.rows))
                    self.status_msg = f"✅ Akuisisi Selesai ({total} Sampel Raw Data)"
                    print(f"\n✅ 10 Run selesai! Total sampel raw data: {total}")
                    self.acquisition_done = True
                    continue

                if event == 'ACQ_STOP':
                    self.status_msg = "⏹️ Akuisisi Dihentikan Manual"
                    print("\n⏹️ Akuisisi dihentikan oleh user.")
                    self.acquisition_done = True
                    continue

                # Data sampel raw sensor
                phase = data.get('phase', 'idle')
                cycle = data.get('cycle', 0)
                sample_idx = data.get('sample_idx', 0)

                if phase in ('purging', 'collecting'):
                    # Susun metadata lengkap untuk setiap baris data
                    row = {
                        'timestamp': data.get('timestamp', int(time.time() * 1000)),
                        'sample_id': self.sample_id,
                        'roast_level': self.roast_level,
                        'origin': self.origin,
                        'batch_id': self.batch_id,
                        'run_id': cycle,
                        'phase': phase,
                        'sample_idx': sample_idx,
                    }

                    # Masukkan 10 raw ADC sensor values
                    for col in ADC_COLS:
                        row[col] = data.get(col, None)

                    # Sensor Suhu & Kelembapan (jika tersedia)
                    row['temperature'] = data.get('temp', None)
                    row['humidity'] = data.get('humidity', None)

                    with self.lock:
                        self.rows.append(row)
                        self.phase = phase
                        self.cycle = cycle

                        # Push ke plot deques
                        t_sec = len(self.rows)
                        self.timestamps.append(t_sec)
                        for col in ADC_COLS:
                            self.sensor_data[col].append(data.get(col, 0))

                        self.status_msg = f"Run {cycle:02d}/{self.cycles_total:02d} | {phase.upper()} #{sample_idx}"

        except Exception as e:
            print(f"\n❌ Error serial loop: {e}")
        finally:
            self.acquisition_done = True


# ─── Live Plot GUI Window ────────────────────────────────────────────────────
def run_live_gui(collector):
    plt.style.use('dark_background')
    fig = plt.figure(figsize=(14, 8), facecolor='#0D1117')
    fig.canvas.manager.set_window_title(
        f'E-NOSE Kopi — Real-Time Raw Data [{collector.sample_id} | {collector.batch_id}]')

    gs = fig.add_gridspec(2, 1, height_ratios=[1, 1], hspace=0.3, left=0.06, right=0.98, top=0.91, bottom=0.07)

    ax_tgs = fig.add_subplot(gs[0])
    ax_mq  = fig.add_subplot(gs[1])

    for ax in [ax_tgs, ax_mq]:
        ax.set_facecolor('#161B22')
        ax.grid(True, alpha=0.15, color='#30363D')
        ax.tick_params(colors='#8B949E', labelsize=8)
        for spine in ax.spines.values():
            spine.set_color('#30363D')

    ax_tgs.set_title('TGS Series Sensors (Raw ADC)', fontsize=10, color='#58A6FF', fontweight='bold', loc='left')
    ax_tgs.set_ylabel('ADC Value', fontsize=8, color='#8B949E')

    ax_mq.set_title('MQ Series Sensors (Raw ADC)', fontsize=10, color='#F0883E', fontweight='bold', loc='left')
    ax_mq.set_ylabel('ADC Value', fontsize=8, color='#8B949E')
    ax_mq.set_xlabel('Sampel Total (detik)', fontsize=8, color='#8B949E')

    fig.suptitle(f'E-NOSE Raw Data — Sample: {collector.sample_id} ({collector.roast_level.upper()}) | Batch: {collector.batch_id}',
                 fontsize=12, color='#E6EDF3', fontweight='bold', y=0.97)

    lines = {}
    for col in ADC_COLS:
        cfg = SENSOR_CONFIG[col]
        ax = ax_tgs if cfg['group'] == 'TGS' else ax_mq
        line, = ax.plot([], [], color=cfg['color'], linewidth=1.3, alpha=0.9, label=cfg['label'])
        lines[col] = line

    ax_tgs.legend(loc='upper right', fontsize=7, ncol=4, framealpha=0.3, facecolor='#161B22', edgecolor='#30363D', labelcolor='#C9D1D9')
    ax_mq.legend(loc='upper right', fontsize=7, ncol=3, framealpha=0.3, facecolor='#161B22', edgecolor='#30363D', labelcolor='#C9D1D9')

    status_text = fig.text(0.06, 0.94, 'Status: Menyiapkan...', fontsize=9, color='#3FB950', fontweight='bold')

    def update(frame):
        with collector.lock:
            if not collector.timestamps:
                return list(lines.values())

            ts = list(collector.timestamps)
            for col in ADC_COLS:
                vals = list(collector.sensor_data[col])
                lines[col].set_data(ts[:len(vals)], vals)

            msg = collector.status_msg
            status_text.set_text(f"Status: {msg} | Total Data: {len(collector.rows)} sampel")

            if collector.phase == 'collecting':
                status_text.set_color('#3FB950')
            elif collector.phase == 'purging':
                status_text.set_color('#58A6FF')

        for ax in [ax_tgs, ax_mq]:
            ax.relim()
            ax.autoscale_view()
            if len(ts) > 1:
                ax.set_xlim(max(0, ts[0]), ts[-1] + 2)

        if collector.acquisition_done:
            status_text.set_text(f"[OK] 10 Run Selesai! CSV: {os.path.basename(collector.out_csv)}")
            status_text.set_color('#A371F7')

        return list(lines.values())

    ani = animation.FuncAnimation(fig, update, interval=250, blit=False, cache_frame_data=False)

    def on_close(event):
        collector.stop_requested = True

    fig.canvas.mpl_connect('close_event', on_close)
    plt.show(block=True)


# ─── Main Execution ───────────────────────────────────────────────────────────
def main():
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    args = parse_args()

    port = args.port or prompt_port()

    # Dapatkan metadata sampel
    if args.sample:
        sample_id = args.sample.upper()
        if sample_id in KNOWN_SAMPLES:
            roast_level = args.roast_level or KNOWN_SAMPLES[sample_id]['roast_level']
            origin      = args.origin      or KNOWN_SAMPLES[sample_id]['origin']
        else:
            roast_level = args.roast_level or 'custom'
            origin      = args.origin      or 'custom'
        batch_id = (args.batch or 'B01').upper()
    else:
        sample_id, roast_level, origin, batch_id = prompt_metadata()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Format Nama File: <sample_id>_<batch_id>.csv (contoh: L-MAN_B01.csv)
    base_filename = f"{sample_id}_{batch_id}.csv"
    out_csv = os.path.join(OUTPUT_DIR, base_filename)

    # Perlindungan File Tertimpa (Accidental Overwrite Protection)
    if os.path.exists(out_csv):
        timestamp_suffix = datetime.now().strftime('%Y%m%d_%H%M%S')
        out_csv = os.path.join(OUTPUT_DIR, f"{sample_id}_{batch_id}_{timestamp_suffix}.csv")
        print(f"⚠️  File {base_filename} sudah ada. Nama file disesuaikan menjadi: {os.path.basename(out_csv)}")

    print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║           E-NOSE Kopi — Pengumpulan Raw Data (10 Run)                ║
╠══════════════════════════════════════════════════════════════════════╣
║  Sample ID    : {sample_id:<52} ║
║  Roast Level  : {roast_level.upper():<52} ║
║  Origin       : {origin:<52} ║
║  Batch ID     : {batch_id:<52} ║
║  Port Serial  : {port:<52} ║
║  Skema Run    : 5 Run × ({ACQ_PURGE_S}s Purging + {ACQ_COLLECT_S}s Collecting){'':<14} ║
║  Output File  : {os.path.basename(out_csv):<52} ║
╚══════════════════════════════════════════════════════════════════════╝
""")

    # ── Buka Serial ──────────────────────────────────────────────────────────
    try:
        ser = Serial(port=port, baudrate=args.baud, timeout=2)
        print(f"✅ Serial terbuka: {port} @ {args.baud} baud")
    except Exception as e:
        print(f"❌ Gagal membuka Serial: {e}")
        sys.exit(1)

    time.sleep(2)  # Wait for ATmega boot

    collector = RawDataCollector(ser, sample_id, roast_level, origin, batch_id, out_csv)
    t_thread = threading.Thread(target=collector.run, daemon=True)
    t_thread.start()

    try:
        if not args.no_plot:
            print("📊 Membuka window grafik real-time...")
            run_live_gui(collector)
        else:
            print("⏳ Memproses data (mode tanpa GUI)...")
            while not collector.acquisition_done:
                time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n⚠️ Dihentikan oleh user (Ctrl+C)")
        collector.stop_requested = True
    finally:
        collector.acquisition_done = True
        try:
            ser.write(b'#stop;')
            print("📤 Mengirim #stop; ke ATmega...")
        except Exception:
            pass
        time.sleep(0.5)
        ser.close()

    # ── Simpan RAW DATA ke CSV ─────────────────────────────────────────────────
    rows = collector.rows
    if rows:
        df = pd.DataFrame(rows)

        # Urutan Kolom Standard Metadata & Raw ADC
        ordered_cols = [
            'timestamp', 'sample_id', 'roast_level', 'origin', 'batch_id',
            'run_id', 'phase', 'sample_idx'
        ] + ADC_COLS

        # Tambahkan temperature & humidity jika ada di DataFrame
        if 'temperature' in df.columns: ordered_cols.append('temperature')
        if 'humidity' in df.columns:    ordered_cols.append('humidity')

        # Pastikan hanya kolom yang ada di df yang disertakan
        final_cols = [c for c in ordered_cols if c in df.columns]
        df = df[final_cols]

        df.to_csv(out_csv, index=False)

        collecting_n = len(df[df['phase'] == 'collecting'])
        purging_n    = len(df[df['phase'] == 'purging'])
        print(f"""
📄 RAW DATA BERHASIL DISIMPAN KE CSV!
   File Location : {out_csv}
   Sample ID     : {sample_id}
   Roast Level   : {roast_level}
   Origin        : {origin}
   Batch ID      : {batch_id}
   Purging Rows  : {purging_n} sampel ({ACQ_PURGE_S}s × 10 run)
   Collect Rows  : {collecting_n} sampel ({ACQ_COLLECT_S}s × 10 run)
   Total Baris   : {len(df)} baris raw data
   Total Kolom   : {len(df.columns)} kolom
""")
    else:
        print("\n⚠️ Tidak ada data yang diterima. File CSV tidak dibuat.")


if __name__ == '__main__':
    main()
