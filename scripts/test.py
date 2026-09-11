import threading
import time
import json
import os
import sys
from datetime import datetime
import serial
import serial.tools.list_ports

# ══════════════════════════════════════════════════════════════════════════════
# Konfigurasi Default
# ══════════════════════════════════════════════════════════════════════════════
DEFAULT_PORT = "COM18"
DEFAULT_BAUD = 115200

# Mapping shortcut input keyboard ke perintah firmware E-Nose
COMMAND_MAP = {
    # Kontrol Valve Festo 3/2 (Pin 10 & 11)
    "on": ("#on;", "Valve ON (HIGH / Purge)"),
    "off": ("#off;", "Valve OFF (LOW / Collecting)"),
    "t": ("#toggle;", "Toggle Jalur Valve 3/2"),
    "toggle": ("#toggle;", "Toggle Jalur Valve 3/2"),
    "b": ("#blink;", "Tes Klik Mekanis Valve 3x"),
    "blink": ("#blink;", "Tes Klik Mekanis Valve 3x"),
    "swap": ("#swap;", "Tukar Polaritas H-Bridge"),
    
    # Kontrol Siklus E-Nose
    "1": ("#start;", "Mulai Siklus Akuisisi Otomatis"),
    "start": ("#start;", "Mulai Siklus Akuisisi Otomatis"),
    "0": ("#stop;", "Hentikan Akuisisi & Matikan Valve"),
    "stop": ("#stop;", "Hentikan Akuisisi & Matikan Valve"),
    "c": ("#collect;", "Set Fase Collecting"),
    "p": ("#purge;", "Set Fase Purging"),
    
    # Diagnostik
    "scan": ("#scan;", "Scan I2C Bus"),
    "h": ("#help;", "Tampilkan Bantuan Firmware"),
    "help": ("#help;", "Tampilkan Bantuan Firmware"),
}

class ENoseLogger:
    def __init__(self, port=DEFAULT_PORT, baud=DEFAULT_BAUD):
        self.port = self.auto_detect_port(port)
        self.baud = baud
        self.ser = None
        self.is_running = True
        
        # Buat nama file log berdasarkan tanggal & jam saat dijalankan
        os.makedirs("data", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filename = os.path.join("data", f"enose_data_{timestamp}.jsonl")
        
    def auto_detect_port(self, preferred_port):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        if preferred_port in ports:
            return preferred_port
        if ports:
            print(f"[!] Port {preferred_port} tidak ditemukan. Menggunakan port terdeteksi: {ports[0]}")
            return ports[0]
        return preferred_port

    def connect(self):
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=1.0)
            time.sleep(1.5)  # Tunggu Arduino reset setelah koneksi serial
            self.ser.flushInput()
            self.ser.flushOutput()
            print(f"[OK] Berhasil terhubung ke E-Nose di {self.port} ({self.baud} baud)")
            print(f"[OK] File logging: {self.filename}")
            return True
        except Exception as e:
            print(f"[ERROR] Gagal membuka port {self.port}: {e}")
            return False

    def send_cmd(self, raw_cmd, desc=""):
        if not self.ser or not self.ser.is_open:
            print("[!] Serial belum terhubung.")
            return
        cmd_str = raw_cmd.strip()
        if not cmd_str.endswith(";"):
            cmd_str += ";"
        try:
            self.ser.write((cmd_str + "\n").encode("utf-8"))
            print(f"\n--> Terkirim: {cmd_str} {('(' + desc + ')') if desc else ''}")
        except Exception as e:
            print(f"[ERROR] Gagal mengirim: {e}")

    def read_loop(self):
        """Thread latar belakang untuk membaca data serial secara non-blocking"""
        while self.is_running and self.ser and self.ser.is_open:
            try:
                line = self.ser.readline()
                if not line:
                    continue
                
                text = line.decode("utf-8", errors="replace").strip()
                if not text:
                    continue
                
                # Jika format JSON
                if text.startswith("{") and text.endswith("}"):
                    try:
                        data = json.loads(text)
                        
                        # Jika paket data sensor akuisisi
                        if "sensor_readings" in data or "adc_tgs2602" in data or "phase" in data:
                            phase = data.get("phase", "-").upper()
                            cycle = data.get("cycle", "-")
                            sample = data.get("sample", "-")
                            print(f"[SENSOR] Siklus {cycle} | Fase: {phase:<10} | Sampel #{sample}")
                        
                        # Jika paket status event / notifikasi valve
                        elif "event" in data:
                            evt = data.get("event")
                            valve = data.get("valve", "-")
                            jalur = data.get("jalur", "")
                            print(f"[*] EVENT: {evt} | Valve: {valve} {('[' + jalur + ']') if jalur else ''}")
                        
                        elif "info" in data:
                            print(f"[*] INFO: {data.get('info')}")
                        elif "warn" in data:
                            print(f"[!] WARN: {data.get('warn')}")
                        else:
                            print(f"[*] DATA: {text}")

                        # Simpan ke file log JSONL
                        with open(self.filename, "a", encoding="utf-8") as f:
                            data["_pc_time"] = datetime.now().isoformat()
                            f.write(json.dumps(data) + "\n")

                    except json.JSONDecodeError:
                        print(f"[-] {text}")
                else:
                    # Teks biasa / welcome banner
                    print(f"[-] {text}")

            except Exception as e:
                if self.is_running:
                    print(f"[!] Read error: {e}")
                break

    def print_menu(self):
        print("\n" + "=" * 58)
        print("   SMART COFFEE E-NOSE v2 - Interactive Controller")
        print("=" * 58)
        print("  Kontrol Valve Festo 3/2:")
        print("    on     : Aktifkan Valve (Jalur 2 - Sampel Kopi)")
        print("    off    : Matikan Valve (Jalur 1 - Udara Bersih)")
        print("    t      : Toggle Jalur Valve (Jalur 1 <-> Jalur 2)")
        print("    b      : Tes Klik Mekanis Valve 3x (Blink)")
        print("    swap   : Tukar Polaritas H-Bridge (+/-)")
        print("-" * 58)
        print("  Kontrol Akuisisi:")
        print("    1/start: Mulai Siklus Akuisisi Lengkap")
        print("    0/stop : Hentikan Akuisisi")
        print("    scan   : Scan I2C Bus")
        print("    q      : Keluar (Quit)")
        print("=" * 58 + "\n")

    def input_loop(self):
        self.print_menu()
        while self.is_running:
            try:
                user_input = input(">> ").strip().lower()
                if not user_input:
                    continue
                
                if user_input in ["q", "exit", "quit"]:
                    print("[*] Menutup aplikasi...")
                    self.is_running = False
                    break
                
                if user_input in ["menu", "help"]:
                    self.print_menu()
                    continue

                if user_input in COMMAND_MAP:
                    raw_cmd, desc = COMMAND_MAP[user_input]
                    self.send_cmd(raw_cmd, desc)
                elif user_input.startswith("#"):
                    self.send_cmd(user_input)
                else:
                    print(f"[!] Perintah '{user_input}' tidak dikenal. Ketik 'menu' untuk daftar perintah.")

            except (KeyboardInterrupt, EOFError):
                self.is_running = False
                break

        # Cleanup
        if self.ser and self.ser.is_open:
            self.ser.close()
        print("[OK] Selesai.")

if __name__ == "__main__":
    # Port bisa diubah jika perlu, default: COM18
    target_port = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PORT
    app = ENoseLogger(port=target_port, baud=DEFAULT_BAUD)
    
    if app.connect():
        t = threading.Thread(target=app.read_loop, daemon=True)
        t.start()
        app.input_loop()
