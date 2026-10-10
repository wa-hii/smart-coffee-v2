# SOP Tahap 7 — Remote Raspberry Pi 5 dan komunikasi ke ATmega (AMAN)

**Kondisi operator saat mulai Tahap 7:** ATmega2560 **tidak tersambung
ke COM5**; Raspberry Pi 5 **telah dinyalakan** agar bisa diakses
jarak jauh. **Hostname/IP, SSH user dan otorisasi session belum
tersedia dalam repo**, sehingga koneksi SSH live **belum diverifikasi**.
Belum ada kabel USB/UART antara Pi dan ATmega yang diuji pada sesi ini.

**Pembaruan hasil aktual 11 Oktober:** SSH
`enose-v3@enose-pi5` melalui Tailscale **BERHASIL**
dengan host key checking aktif. Identitas Pi 5
Rev 1.1, Debian 13, Python 3.13.5 diverifikasi.
Venv di `~/smart-coffee-stage7/.venv` dibuat
dan PySerial 3.5 diinstal hanya di dalamnya.
Replay `D-GAW_B33.csv` dilakukan **langsung pada
Pi** secara offline (151 sampel, `COMPLETE_QA`,
`AI_TEST=N/A`); port serial fisik tidak dibuka.
Detail dan bukti:
`docs/reports/2026-10-11_TAHAP7_PI_VENV_OFFLINE_REPLAY.md`.

## 1. Pilihan transport dan wiring yang boleh dilakukan kemudian

| Pilihan | Keterangan dan risiko |
|---|---|
| **USB serial (disarankan pertama)** | Port USB ATmega2560 → USB Pi, device Linux melalui `/dev/serial/by-id/*` atau `/dev/ttyACM*`. Firmware sekarang mengirim JSON di `Serial` **115200 baud**. Jangan bergantung pada nama COM5 milik Windows, atau langsung membuka port sebelum kepemilikan disepakati. Sambungan USB bisa me-reset ATmega karena DTR; lakukan di bawah SOP perangkat. |
| **UART GPIO (alternatif setelah skematik)** | USART1 ATmega **TX1 D18 / RX1 D19** bila jalur PCB benar-benar tersedia. Nextion tetap memakai **USART2/Serial2 @ 9600**. Pi 5 perlu konfigurasi UART yang diverifikasi; UART utama default Pi 5 justru pada **header debug dedicated**, bukan otomatis pin GPIO14/15. Semua GPIO Pi bekerja pada **3,3 V**; wajib penerjemah level 5↔3,3 V pada UART TTL. GND bersama, TX→RX silang. Jangan sambungkan TX 5 V ATmega langsung ke GPIO Pi. Jangan menghubungkan kabel atau memodifikasi `config.txt` tanpa pemeriksaan PCB/SOP baru. |

Rujukan Raspberry Pi resmi:
https://www.raspberrypi.com/documentation/computers/configuration.html
https://www.raspberrypi.com/documentation/computers/raspberry-pi.html

**Keputusan untuk Tahap 7 offline:** pilih *USB-first candidate*.
Ini keputusan desain, **belum uji port/baud fisik**. UART terpisah
tetap kandidat setelah pinout dan perangkat level shifter diverifikasi.
`#pin_scan;` dilarang karena akses GPIO/I2C berisiko, dan kontrol
pompa/valve tetap menjadi kewenangan firmware ATmega.

## 2. Akses Pi jarak jauh yang aman (saat operator menyediakan target SSH)

Prasyarat: Pi dan host tersedia dalam jaringan dengan akses yang
sah (LAN/VPN), layanan SSH telah diaktifkan, host-key/fingerprint
telah diverifikasi melalui kanal tepercaya, dan akun SSH sendiri.
**Jangan kirim password, token, atau private SSH key ke chat.**
Jangan expose port SSH langsung ke internet tanpa pengamanan.

Dari PowerShell Windows di root repo:

```powershell
# Ganti <user>@<hostname-or-ip> dengan identitas Pi yang sudah diketahui.
ssh -o StrictHostKeyChecking=yes -o BatchMode=yes -o ConnectTimeout=5 <user>@<hostname-or-ip> "uname -a"

# Kirim skrip read-only lewat stdin, tanpa menyalin/menginstal file ke Pi.
Get-Content -Raw scripts/stage7_pi_preflight.py |
  ssh -o StrictHostKeyChecking=yes -o BatchMode=yes <user>@<hostname-or-ip> python3 -
```

Perintah preflight mengamati:
- `/proc/device-tree/model` (klaim Pi 5)
- versi Linux/Python dan arsitektur CPU
- calon path port (tanpa `open()`)
- `vcgencmd get_throttled` jika tersedia; aman tanpa sudo

Hasil boleh disalin ke laporan QA setelah operator menghapus
informasi hostname/IP pribadi bila perlu. **Jangan menafsirkan
port tercantum sebagai bukti komunikasi berhasil.**

Jika hostname/IP belum diketahui, cek layar lokal atau router
yang memang Anda kelola; jangan melakukan pemindaian jaringan luas.
Jika fingerprint host SSH tidak cocok, hentikan dan verifikasi,
jangan mematikan `StrictHostKeyChecking`.

## 3. Adapter serial Tahap 7 yang sudah dapat digunakan OFFLINE

```powershell
python scripts/test_stage7_bridge.py
python scripts/test_stage7_pi_preflight.py
python scripts/stage7_bridge.py --replay-csv data/raw/D-GAW_B33.csv --output results/stage7_offline_v2/replay.json
```

Adapter menerima **JSON-per-line legacy** yang benar-benar
dikeluarkan firmware saat ini. Parser membatasi ukuran 4.096 byte,
menolak JSON malformed/duplicate keys/NaN, sensor 10 ADC tidak
lengkap, fase/indeks/timestamp salah, duplikasi, kehilangan sampel,
pause yang invalid, dan COMPLETE tidak konsisten. Session ID
dihasilkan **di host**, bukan diklaim berasal dari firmware.
Setiap sesi maksimal satu terminal `SESSION_FINAL`; disconnect,
restart atau kegagalan menghasilkan status `N/A`/FAIL_CLOSED.

Mode `AI_TEST` **tidak membaca label pilihan Nextion** sebagai
ground truth dan **tidak pernah mengeluarkan prediksi roast**:
gerbang Tahap 6 menegaskan `model_promotion_allowed=false`.
Hasil replay adalah diagnostik host, **belum dikirim ke
ATmega/Nextion** dan tidak menulis raw file.

Skema protokol versi 1 yang diusulkan (`version`, `type`,
`device_id`, `session_id`, `message_seq`,
`emitted_uptime_ms`, `mode`, `payload`) serta penjaga
sequence/ACK/NACK **hanya simulasi**. Firmware saat ini
belum mengeluarkan envelope versi 1, belum menerima ACK/NACK,
dan belum memiliki handler hasil Pi→Nextion; jangan mengaku
komunikasi dua arah sudah siap.

## 4. Tindakan fisik / deployment yang belum disetujui

- Menghubungkan ATmega via USB ke Pi, memilih port `/dev/ttyACM*`
  atau membuka `/dev/serial/by-id/*` dengan pyserial.
- Flash firmware ATmega, upload TFT, menyalakan/mematikan pompa
  atau valve, mengubah EEPROM/kontrol daya.
- Menambah/menyalakan service systemd, memasang paket global,
  memodifikasi SSH, UART, `config.txt`, serial console, atau GPIO Pi.
- Mengirim `INFERENCE_RESULT` ke ATmega atau menampilkan prediksi
  kopi dari model yang belum tervalidasi.

**Tahap 7 software offline PASS ≠ SSH Pi PASS ≠ serial fisik PASS.
Gerbang rilis keseluruhan tetap NO-GO.**

## 5. Urutan lanjutan setelah akses Pi diketahui

1. Jalankan SSH read-only dan cocokkan identitas Pi 5, arsitektur,
   suhu/power throttle dan versi Python dengan bukti hasil nyata.
2. Setelah operator setuju koneksi kabel, lakukan USB serial
   read-only dengan perangkat dalam keadaan aman dan pemilik port
   tunggal; ukur frame timing, kehilangan paket serta kemungkinan
   reset saat USB dicolok.
3. Tambahkan ACK/NACK dan session ID firmware hanya setelah
   kontrak v1 disepakati, firmware di-build QA dan uji negatif
   replay sudah lulus. Jangan ubah wire protocol tengah akuisisi.
4. Sinkronkan handler hasil Pi dan pResult Nextion,
   dengan default N/A dan tanpa kontrol aktuator oleh Pi.
5. Laksanakan simulasi E2E Tahap 8 terlebih dahulu; Tahap 9
   hardware tetap butuh izin bench yang terpisah.

## 6. Runner Raspberry Pi yang sudah tersedia

Perintah pada Pi setelah SSH:

```bash
cd ~/smart-coffee-stage7
.venv/bin/python scripts/test_stage7_pi_adapter.py
.venv/bin/python scripts/stage7_pi_adapter.py replay-csv \
  --input data/raw/D-GAW_B33.csv \
  --output results/pi_stage7/replay_d_gaw_b33_new.json
```

Program `stage7_pi_adapter.py` menggunakan mode
`replay-csv` atau `replay-jsonl` secara offline,
serta menyiapkan `serial-readonly` untuk *bench
terpisah yang belum disetujui saat ini*. Mode serial
menuntut opt-in khusus dan path USB serial yang
dibatasi, tetapi pembukaan USB masih berisiko reset
ATmega. **Jangan jalankan mode serial** hanya karena
software-nya sudah terpasang. Program mengembalikan
exit code 0 pada replay `COMPLETE_QA`, exit code 2
pada kualitas yang tidak lulus. Hasil `N/A`
berarti tidak ada inferensi model yang disetujui.

Semua proses replay satu kali berhenti otomatis.
`Ctrl+C` dapat menghentikan proses interaktif,
tidak perlu `systemctl stop` karena tidak ada
service yang dibuat.
