"""
5_realtime_dashboard.py
═══════════════════════════════════════════════════════════════════════════════
Dashboard real-time untuk monitoring respon sensor E-NOSE selama pengujian.

Script ini STANDALONE — tidak mengubah arsitektur firmware atau script lain.
Membaca data serial dari ATmega dan menampilkan plot 10 sensor secara live.

Cara pakai:
  pip install pyserial matplotlib numpy
  python 5_realtime_dashboard.py --port COM5
  python 5_realtime_dashboard.py                 # mode interaktif

Fitur:
  • Plot real-time 10 sensor gas (ADC raw value)
  • Indikator phase (Collecting / Purging / Idle)
  • Statistik live (min, max, mean per sensor)
  • Otomatis kirim #start; ke ATmega
  • Bisa dijalankan bersamaan tanpa mengganggu firmware
═══════════════════════════════════════════════════════════════════════════════
"""

import argparse
import json
import sys
import time
import threading
from collections import deque
from datetime import datetime

import numpy as np
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patches import FancyBboxPatch

from serial import Serial

# ─── Konfigurasi ──────────────────────────────────────────────────────────────
BAUD_RATE = 115200
MAX_POINTS = 300          # jumlah titik data dalam grafik (5 menit @ 1Hz)
ANIM_INTERVAL_MS = 200    # refresh grafik setiap 200ms

# Sensor dan warna (dikelompokkan berdasarkan jenis)
SENSORS = {
    # TGS Series (hijau-biru)
    'adc_tgs822':  {'label': 'TGS822',  'color': '#00E676', 'group': 'TGS'},
    'adc_tgs2611': {'label': 'TGS2611', 'color': '#00BFA5', 'group': 'TGS'},
    'adc_tgs2620': {'label': 'TGS2620', 'color': '#18FFFF', 'group': 'TGS'},
    'adc_tgs2600': {'label': 'TGS2600', 'color': '#64FFDA', 'group': 'TGS'},
    'adc_tgs2602': {'label': 'TGS2602', 'color': '#A7FFEB', 'group': 'TGS'},
    'adc_tgs813':  {'label': 'TGS813',  'color': '#B2FF59', 'group': 'TGS'},
    'adc_tgs816':  {'label': 'TGS816',  'color': '#76FF03', 'group': 'TGS'},
    # MQ Series (oranye-merah)
    'adc_mq135':   {'label': 'MQ135',   'color': '#FF6D00', 'group': 'MQ'},
    'adc_mq9':     {'label': 'MQ9',     'color': '#FF3D00', 'group': 'MQ'},
    'adc_mq8':     {'label': 'MQ8',     'color': '#FFAB00', 'group': 'MQ'},
}

SENSOR_KEYS = list(SENSORS.keys())


# ─── Port Selection (reuse dari 3_collect_data.py) ────────────────────────────
def prompt_port():
    """Daftar port serial yang tersedia dan minta user pilih."""
    try:
        import serial.tools.list_ports
        ports = list(serial.tools.list_ports.comports())
    except Exception:
        ports = []

    if ports:
        print("\n Port Serial yang tersedia:")
        for i, p in enumerate(ports):
            print(f"  [{i}] {p.device}  - {p.description}")
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


# ─── Data Store (thread-safe) ─────────────────────────────────────────────────
class SensorDataStore:
    """Thread-safe storage untuk data sensor real-time."""

    def __init__(self, max_points=MAX_POINTS):
        self.max_points = max_points
        self.lock = threading.Lock()

        # Deque per sensor
        self.data = {key: deque(maxlen=max_points) for key in SENSOR_KEYS}
        self.timestamps = deque(maxlen=max_points)

        # Status
        self.phase = 'idle'
        self.cycle = 0
        self.sample_count = 0
        self.last_update = None
        self.connected = False
        self.event_log = deque(maxlen=10)

    def add_sample(self, json_data):
        with self.lock:
            t = json_data.get('timestamp', 0) / 1000.0  # ms -> s
            self.timestamps.append(t)
            for key in SENSOR_KEYS:
                val = json_data.get(key, 0)
                self.data[key].append(val)

            self.phase = json_data.get('phase', self.phase)
            self.cycle = json_data.get('cycle', self.cycle)
            self.sample_count += 1
            self.last_update = time.time()

    def add_event(self, msg):
        with self.lock:
            ts = datetime.now().strftime('%H:%M:%S')
            self.event_log.append(f"[{ts}] {msg}")

    def get_snapshot(self):
        with self.lock:
            return {
                'timestamps': list(self.timestamps),
                'data': {k: list(v) for k, v in self.data.items()},
                'phase': self.phase,
                'cycle': self.cycle,
                'sample_count': self.sample_count,
                'last_update': self.last_update,
                'connected': self.connected,
                'event_log': list(self.event_log),
            }


# ─── Serial Reader Thread ────────────────────────────────────────────────────
def serial_reader(ser, store, stop_event):
    """Background thread: membaca serial dan parsing JSON."""
    store.connected = True
    store.add_event("Serial terhubung")

    # Kirim #start;
    try:
        ser.write(b'#start;')
        store.add_event("Mengirim #start; ke ATmega")
        time.sleep(0.5)
    except Exception as e:
        store.add_event(f"Gagal kirim start: {e}")

    while not stop_event.is_set():
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

            if event == 'ACQ_START':
                cycles = data.get('cycles_total', '?')
                store.add_event(f"Akuisisi dimulai ({cycles} siklus)")
                store.phase = 'collecting'
                store.cycle = data.get('cycle', 1)
                continue

            if event == 'PHASE_CHANGE':
                new_phase = data.get('phase', 'idle')
                cycle = data.get('cycle', store.cycle)
                store.phase = new_phase
                store.cycle = cycle
                store.add_event(f"Phase -> {new_phase} (Cycle {cycle})")
                continue

            if event == 'ACQ_COMPLETE':
                total = data.get('total_samples', '?')
                store.add_event(f"Akuisisi selesai! Total: {total}")
                store.phase = 'complete'
                continue

            if event == 'ACQ_STOP':
                store.add_event("Akuisisi dihentikan manual")
                store.phase = 'stopped'
                continue

            # Data sampel sensor
            phase = data.get('phase', 'idle')
            if phase in ('collecting', 'purging', 'idle'):
                # Pastikan ini data sensor (ada setidaknya 1 key ADC)
                if any(k in data for k in SENSOR_KEYS):
                    store.add_sample(data)

        except Exception as e:
            store.add_event(f"Error baca serial: {e}")
            time.sleep(0.5)

    store.connected = False
    store.add_event("Serial terputus")


# ─── Dashboard Plot ───────────────────────────────────────────────────────────
def create_dashboard(store, stop_event):
    """Membuat dan menjalankan dashboard matplotlib."""

    # ── Setup Figure ──────────────────────────────────────────────────────────
    plt.style.use('dark_background')
    fig = plt.figure(figsize=(16, 9), facecolor='#0D1117')
    fig.canvas.manager.set_window_title('E-NOSE Real-Time Dashboard')

    # Grid: 2 baris plot + 1 baris status
    gs = fig.add_gridspec(3, 2, height_ratios=[3, 3, 1],
                          hspace=0.35, wspace=0.25,
                          left=0.06, right=0.98, top=0.92, bottom=0.05)

    ax_tgs = fig.add_subplot(gs[0, :])     # TGS sensors (atas)
    ax_mq  = fig.add_subplot(gs[1, :])     # MQ sensors (tengah)
    ax_info = fig.add_subplot(gs[2, 0])    # Info panel (kiri bawah)
    ax_log  = fig.add_subplot(gs[2, 1])    # Event log (kanan bawah)

    # Styling axes
    for ax in [ax_tgs, ax_mq]:
        ax.set_facecolor('#161B22')
        ax.grid(True, alpha=0.15, color='#30363D')
        ax.tick_params(colors='#8B949E', labelsize=8)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_color('#30363D')
        ax.spines['left'].set_color('#30363D')

    ax_tgs.set_title('TGS Series Sensors', fontsize=11, color='#58A6FF',
                      fontweight='bold', pad=8)
    ax_tgs.set_ylabel('ADC Value', fontsize=9, color='#8B949E')

    ax_mq.set_title('MQ Series Sensors', fontsize=11, color='#F0883E',
                     fontweight='bold', pad=8)
    ax_mq.set_ylabel('ADC Value', fontsize=9, color='#8B949E')
    ax_mq.set_xlabel('Time (s)', fontsize=9, color='#8B949E')

    for ax in [ax_info, ax_log]:
        ax.set_facecolor('#161B22')
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_color('#30363D')

    # ── Title ─────────────────────────────────────────────────────────────────
    fig.suptitle('E-NOSE Kopi v2 — Real-Time Sensor Dashboard',
                 fontsize=14, color='#E6EDF3', fontweight='bold', y=0.97)

    # ── Create line objects ───────────────────────────────────────────────────
    lines = {}
    for key, cfg in SENSORS.items():
        ax = ax_tgs if cfg['group'] == 'TGS' else ax_mq
        line, = ax.plot([], [], color=cfg['color'], linewidth=1.2,
                        alpha=0.85, label=cfg['label'])
        lines[key] = line

    ax_tgs.legend(loc='upper left', fontsize=7, ncol=4,
                  framealpha=0.3, facecolor='#161B22', edgecolor='#30363D',
                  labelcolor='#C9D1D9')
    ax_mq.legend(loc='upper left', fontsize=7, ncol=3,
                 framealpha=0.3, facecolor='#161B22', edgecolor='#30363D',
                 labelcolor='#C9D1D9')

    # ── Phase indicator colors ────────────────────────────────────────────────
    PHASE_COLORS = {
        'idle':       ('#8B949E', 'IDLE'),
        'collecting': ('#3FB950', 'COLLECTING'),
        'purging':    ('#58A6FF', 'PURGING'),
        'complete':   ('#A371F7', 'COMPLETE'),
        'stopped':    ('#F85149', 'STOPPED'),
    }

    # ── Animation Update ──────────────────────────────────────────────────────
    def update(frame):
        snap = store.get_snapshot()
        timestamps = snap['timestamps']

        if not timestamps:
            return list(lines.values())

        t = np.array(timestamps)

        # Normalize time to start from 0
        if len(t) > 0:
            t = t - t[0]

        # Update lines
        for key in SENSOR_KEYS:
            vals = snap['data'][key]
            if vals:
                lines[key].set_data(t[:len(vals)], vals)

        # Adjust axes
        for ax in [ax_tgs, ax_mq]:
            ax.relim()
            ax.autoscale_view()
            if len(t) > 1:
                ax.set_xlim(max(0, t[-1] - MAX_POINTS), t[-1] + 5)

        # ── Info Panel ────────────────────────────────────────────────────────
        ax_info.clear()
        ax_info.set_facecolor('#161B22')
        ax_info.set_xticks([])
        ax_info.set_yticks([])
        for spine in ax_info.spines.values():
            spine.set_color('#30363D')

        phase = snap['phase']
        phase_color, phase_text = PHASE_COLORS.get(phase, ('#8B949E', phase.upper()))

        info_lines = [
            f"Phase: {phase_text}",
            f"Cycle: {snap['cycle']}",
            f"Samples: {snap['sample_count']}",
            f"Status: {'CONNECTED' if snap['connected'] else 'DISCONNECTED'}",
        ]

        # Add sensor stats (mean of last 10 samples)
        if snap['sample_count'] > 0:
            elapsed = t[-1] if len(t) > 0 else 0
            info_lines.append(f"Elapsed: {elapsed:.0f}s")

        ax_info.text(0.05, 0.95, '\n'.join(info_lines),
                     transform=ax_info.transAxes, fontsize=8,
                     color='#C9D1D9', verticalalignment='top',
                     fontfamily='monospace',
                     bbox=dict(boxstyle='round,pad=0.3',
                               facecolor=phase_color, alpha=0.2,
                               edgecolor=phase_color))

        # ── Event Log Panel ───────────────────────────────────────────────────
        ax_log.clear()
        ax_log.set_facecolor('#161B22')
        ax_log.set_xticks([])
        ax_log.set_yticks([])
        for spine in ax_log.spines.values():
            spine.set_color('#30363D')

        log_text = '\n'.join(snap['event_log'][-6:]) if snap['event_log'] else 'Menunggu data...'
        ax_log.text(0.05, 0.95, log_text,
                    transform=ax_log.transAxes, fontsize=7,
                    color='#8B949E', verticalalignment='top',
                    fontfamily='monospace')
        ax_log.set_title('Event Log', fontsize=8, color='#8B949E', loc='left')

        return list(lines.values())

    # ── Start Animation ───────────────────────────────────────────────────────
    ani = animation.FuncAnimation(fig, update, interval=ANIM_INTERVAL_MS,
                                  blit=False, cache_frame_data=False)

    try:
        plt.show()
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description='E-NOSE Kopi — Real-Time Sensor Dashboard')
    parser.add_argument('--port', type=str, default=None,
                        help='Port Serial ATmega, misal COM5')
    parser.add_argument('--baud', type=int, default=BAUD_RATE)
    parser.add_argument('--no-start', action='store_true',
                        help='Jangan kirim #start; (hanya monitor)')
    args = parser.parse_args()

    port = args.port or prompt_port()

    print(f"""
+------------------------------------------------------+
|    E-NOSE Kopi — Real-Time Sensor Dashboard          |
+------------------------------------------------------+
|  Port       : {port:<38} |
|  Baud       : {args.baud:<38} |
|  Sensors    : 10 channels (7 TGS + 3 MQ)            |
|  Window     : {MAX_POINTS} samples                           |
+------------------------------------------------------+
""")

    # ── Buka Serial ───────────────────────────────────────────────────────────
    try:
        ser = Serial(port=port, baudrate=args.baud, timeout=2)
        print(f"Serial terbuka: {port} @ {args.baud} baud")
    except Exception as e:
        print(f"Gagal membuka Serial: {e}")
        sys.exit(1)

    time.sleep(2)  # tunggu ATmega boot

    # ── Setup ─────────────────────────────────────────────────────────────────
    store = SensorDataStore()
    stop_event = threading.Event()

    # Start serial reader thread
    reader_args = (ser, store, stop_event)
    if args.no_start:
        # Modifikasi reader supaya tidak kirim #start;
        def reader_no_start(ser, store, stop_event):
            store.connected = True
            store.add_event("Serial terhubung (monitor only)")
            while not stop_event.is_set():
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
                    if event:
                        store.add_event(f"Event: {event}")
                        continue
                    phase = data.get('phase', 'idle')
                    if any(k in data for k in SENSOR_KEYS):
                        store.add_sample(data)
                except Exception as e:
                    store.add_event(f"Error: {e}")
                    time.sleep(0.5)
            store.connected = False
        reader_thread = threading.Thread(target=reader_no_start, args=reader_args,
                                         daemon=True)
    else:
        reader_thread = threading.Thread(target=serial_reader, args=reader_args,
                                         daemon=True)

    reader_thread.start()
    print("Serial reader thread started")
    print("Membuka dashboard... (tutup window atau Ctrl+C untuk berhenti)\n")

    # ── Run Dashboard (blocking) ──────────────────────────────────────────────
    try:
        create_dashboard(store, stop_event)
    except Exception as e:
        print(f"\nDashboard error: {e}")
    finally:
        stop_event.set()
        try:
            ser.write(b'#stop;')
            print("\nMengirim #stop; ke ATmega...")
        except Exception:
            pass
        time.sleep(0.5)
        ser.close()
        print("Serial ditutup. Selesai.")


if __name__ == '__main__':
    main()
