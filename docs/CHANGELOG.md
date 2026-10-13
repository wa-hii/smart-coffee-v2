# Catatan perubahan proyek

## 14 Oktober 2026 05:34–05:37 WIB — QA remote unattended

- User remote, tidak berada di dekat alat: tidak menjalankan
  perintah yang memicu pompa/valve, serial open (berpotensi
  auto-reset MCU), flashing, atau reboot.
- Preflight read-only **tanpa membuka tty**: Pi SSH tersedia,
  FT232R `A10KMM3S` tetap pada `/dev/ttyUSB0`, tidak ada
  port owner, `get_throttled=0x0`.
- Regression suites Windows/Pi untuk Stage1/6/7/8 PASS;
  replay CSV existing pada Pi COMPLETE_QA 151 sampel,
  `hardware_serial_opened=false`, AI N/A.
- Tambah penghitung `acq_start_contract_outcomes`, mengenali
  penolakan `ai_test_label_leakage` firmware lama,
  `bad_start_contract`, accepted; hanya enum alasan statis,
  label kopi tetap tidak direkam. Tes regresi tiga kondisi PASS.
- G3 fisik masih INCONCLUSIVE. Evidence dan langkah
  keselamatan di `docs/reports/2026-10-14_TAHAP7_REMOTE_UNATTENDED_OFFLINE_QA.md`.


## 13 Oktober 2026 20:42–20:49 WIB — Fingerprint versi firmware runtime

- FT232R `A10KMM3S` read-only 15s: 5.026 byte, 38 baris;
  14 frame sensor-shaped ditolak karena `invalid_phase`.
- Perluasan diagnostik host: fase dalam enum tetap dan kategori
  `nextion_event` allowlist; tidak menyimpan data sensor mentah.
- Read-only 8s: 3.043 byte, 31 baris, 7/7 sensor-shaped
  memiliki `phase=idle`; USB tetap terenumerasi, tidak ada
  perintah aktuator/flash/perubahan EEPROM.
- Riwayat Git menunjukkan source sebelum `75cb38a` memang
  mengirim sensor JSON saat IDLE; firmware PCB diduga memakai
  implementasi sebelum perbaikan. Versi binary masih belum pasti.
- Regresi Windows–Pi, build firmware/Nextion offline PASS.
  Tidak ada pengujian lima siklus G3 baru; model tetap NO-GO.
- Rujukan: `docs/reports/2026-10-13_TAHAP7_P2_RUNTIME_FIRMWARE_DIAGNOSIS.md`.


## 13 Oktober 2026 sekitar 20:20 WIB — Pembacaan USB IDLE 15s

- Dengan izin operator, FT232R 115200 dibuka **satu kali**;
  menerima 5.026 byte, 37 baris (23 JSON, 14 non-JSON),
  tanpa USB disconnect. Tidak mengirim perintah MCU.
- Sebanyak 14 JSON memuat nama field sensor, tetapi 0 lolos
  validasi sampel aktif; 0 event akuisisi sesuai mode IDLE.
  Data mentah nilai sensor tidak direkam; status G3 tetap
  INCONCLUSIVE dan AI `N/A`.
- Menambah diagnostik host privacy-safe berupa agregat kode
  alasan penolakan frame sensor-shaped dan uji regresi.
  Tidak ada tes serial kedua ataupun flashing firmware.
- Evidence dan diagnosis: `docs/reports/2026-10-13_TAHAP7_P1_USB_IDLE_SCHEMA_15S_RESULT.md`.


## 13 Oktober 2026 20:09–20:12 WIB — Re-audit independen P0 pasca-reboot

- Re-check SSH pasif mengonfirmasi FT232R `A10KMM3S` masih
  terenumerasi dengan driver `ftdi_sio`; belum ada
  `USB disconnect` baru pada log boot yang diperiksa.
- SHA256 adapter pada Windows/Pi identik, bukti G3 Run02 di Pi
  tetap cocok dengan checksum historis.
- Tes Stage 7 Bridge/Adapter/USB Probe dan Stage 8 offline
  PASS di Windows dan Pi. Firmware `mega2560`/`nextion_test`,
  kontrak HMI, Stage 1 dan Stage 6 PASS offline Windows.
- Roadmap Tahap 7 dan status arsitektur diperbarui. USB open,
  stabilitas elektrik, firmware PCB aktual, G3 dan rilis AI
  **belum tervalidasi**; tidak ada tindakan hardware baru.


Dokumen ini mencatat milestone engineering yang relevan; detail teknis dan risiko tetap berada dalam laporan milestone terkait. Untuk riwayat perubahan terperinci, gunakan `git log` pada branch `wahyu`.

## 13 Oktober 2026 19:50 WIB — Enumerasi FT232R pulih setelah reboot Pi

- Operator melakukan reboot Raspberry Pi:
  boot baru terbukti pada **19:49:19 WIB**.
- FT232R `0403:6001` / `A10KMM3S`
  kembali terlihat di `lsusb` dan
  `/dev/ttyUSB0` (by-id terverifikasi);
  driver `ftdi_sio` aktif.
- Port bebas, getty/ModemManager inactive,
  Pi `throttled=0x0`; pemeriksaan
  **pasif tanpa membuka serial**.
- Penyebab disconnect sebelumnya belum
  pasti. Pembacaan JSON dan G3 fisik
  masih menunggu izin pengujian baru.

## 13 Oktober 2026 19:47 WIB — Reboot Pi tertahan autentikasi

- Operator memberikan izin reboot Pi.
  Sebelum percobaan, tidak ada proses
  akuisisi serial aktif; FT232R belum
  terdeteksi, power Pi `0x0`.
- `sudo -n -v` membutuhkan password;
  `systemctl --no-ask-password reboot`
  gagal karena butuh autentikasi interaktif.
- **Pi belum reboot**; tidak dilakukan
  bypass, reset USB, serial open, atau
  perubahan firmware. Tindak lanjut
  `sudo reboot` oleh operator secara lokal.

## 13 Oktober 2026 19:41 WIB — Cek ulang setelah restart operator

- Pemeriksaan pasif FT232R pada Pi
  dilakukan setelah operator melaporkan
  restart; **FT232R belum kembali**
  di `lsusb`, tidak ada `ttyUSB0`.
- Pi menunjukkan boot time `14:24`
  dan log kernel berakhir di USB
  disconnect `19:24:44`; Pi belum
  tampak di-restart sejak kejadian.
- Tidak ada percobaan serial open
  atau reset USB. Status tetap BLOCKED,
  perlu inspeksi kabel/jalur FT232R.

## 13 Oktober 2026 19:33 WIB — FT232R belum muncul kembali

- Operator menegaskan PCB custom dan
  Nextion menyala normal, kabel USB
  terpasang kedua ujungnya.
- Pi masih aktif, root hub USB
  muncul, tetapi FT232R `0403:6001`
  **hilang** dari `lsusb`,
  `/dev/ttyUSB0` dan sysfs.
  Tidak ada enumerasi ulang sesudah
  disconnect `19:24:44`.
- Ini pemeriksaan **pasif saja**,
  tanpa pembukaan port, reset driver,
  aktusi alat, flashing, atau
  percobaan ulang.
- Tindak lanjut dialihkan ke
  inspeksi fisik USB/power
  sebelum membuka serial lagi.

## 13 Oktober 2026 19:24 WIB — USB FT232R disconnect saat uji 15s

- Satu pembacaan read-only 15s mendapat izin
  pengguna; preflight FT232R dan uji offline PASS.
- `serial-readonly` gagal saat open dengan
  `Errno 19`; kernel menunjukkan kegagalan
  set termios/baud dan **USB disconnect**.
- Pasca-kegagalan, FT232R tidak lagi terdeteksi
  `lsusb`, tidak ada `ttyUSB0`, output JSON
  **tidak dibuat**, dan Pi `throttled=0x0`.
- Tidak mengirim perintah MCU, tidak mengulang
  port open atau menjalankan G3. Tahan
  pengujian hingga pemeriksaan USB/power
  bersama operator.
- Bukti dan batas diagnosis:
  `docs/reports/2026-10-13_TAHAP7_USB_READONLY_15S_DISCONNECT.md`.

## 13 Oktober 2026 malam — Konfirmasi G3 Run02 dan diagnostik skema JSON

- Operator mengonfirmasi START AI TEST
  ditekan dan kelima siklus Nextion
  berjalan sampai selesai **pada Run02**.
  Ketidaksesuaian pembacaan Pi masih
  belum terdiagnosis dari agregat lama.
- Menambah diagnostik `other_json_key_signatures`
  pada parser Pi untuk menangkap hanya
  key path JSON dan frekuensinya,
  dibatasi 8 skema/32 nama key; tidak
  menyimpan nilai sensor atau raw payload.
  Regresi offline/no-values **PASS
  Windows dan Pi**, skrip telah
  dideploy ke Pi dengan checksum.
- Tidak menjalankan ulang G3, USB port,
  flashing firmware, operasi aktuator,
  atau perubahan dataset/model.
  Pembacaan lanjut memerlukan izin baru.

## 13 Oktober 2026 — G3 USB Run02 di Raspberry Pi

- Setelah perbaikan reassembly serial,
  listener G3 kedua benar-benar
  berjalan di Pi pada USB FT232R
  115200 selama 180s (SHA256 source
  Pi sama dengan Windows; tes
  offline Pi PASS).
- Dibaca **52.224 byte, 303 nonempty
  chunk, 203 baris, 189 JSON valid,
  14 invalid/non-JSON**; **tidak
  ditemukan ACQ_START/COMPLETE ataupun
  sampel sensor sesuai skema**.
  Hasil `NOT_STARTED`, bukti asli
  `run02.json` di Pi beserta
  checksum tercatat pada laporan.
- Tidak ada uji ulang otomatis,
  flashing, perintah TX atau
  perubahan aktuator oleh listener.
  Menunggu konfirmasi aktivitas
  Nextion selama G3 Run02 sebelum
  memperluas diagnosis schema.

## 13 Oktober 2026 — Bug framing listener G3 diperbaiki

- Operator memastikan START AI TEST
  ditekan saat listener aktif dan
  lima siklus terlihat berjalan.
  G3 host tetap `NOT_STARTED`,
  jadi asumsi 'START belum ditekan'
  dikoreksi pada laporan historis.
- Memperbaiki `stage7_pi_adapter.py`:
  tambahkan reassembly byte sampai LF
  (tidak menganggap read timeout
  sebagai frame penuh), maksimum
  4096 byte per line, diagnostik
  jumlah byte/chunk/JSON/event/sampel
  tanpa menulis raw atau TX ke MCU.
- Regresi `test_stage7_pi_adapter.py`
  ditambah kasus potongan START
  dan replay data sensor asli
  151 sampel/five-cycle
  `COMPLETE_QA`: **PASS Windows**.
- **G3 belum diulang**; Pi runtime
  versi baru perlu diverifikasi
  sebelum izin satu sesi ulang.
  Firmware, CSV raw, aktuator dan
  AI model tidak diubah.
## 13 Oktober 2026 — G3 Nextion pertama, belum terverifikasi

- G3 listener USB fisik FT232R pada Pi
  berjalan 180s, setelah izin satu
  sesi melalui Nextion; operator
  diminta START AI TEST via LCD.
- Terdapat **304 nonempty read chunks**,
  namun `ACQ_START` valid tidak terdeteksi;
  `final.quality=NOT_STARTED`,
  `terminal_event_count=0`,
  `final.status=N/A`.
  **Tidak ada klaim sampel valid,
  lima siklus complete atau E2E PASS**.
- Port ditutup, Pi throttle `0x0`,
  raw CSV/firmware/aktuator tidak
  dimodifikasi/diperintah dari Pi.
  Minta konfirmasi operator mengenai
  START dan perilaku LCD sebelum
  uji ulang. Laporan:
  `docs/reports/2026-10-13_TAHAP7_G3_NEXTION_RUN01_INCONCLUSIVE.md`.

## 13 Oktober 2026 — Observasi alat setelah G2

- Operator mengonfirmasi **perangkat tetap
  normal seperti biasanya** sesudah
  pembacaan USB FT232R 12 detik.
- Tidak dilaporkan perilaku perangkat
  abnormal. Ini bukan bukti independen
  bahwa auto-reset MCU tidak terjadi.
- Status tetap: G2 USB RX **PASS**,
  validasi payload **PARTIAL**;
  G3 Nextion/pompa/valve **NOT RUN**.
  Hasil observasi ditambahkan pada
  laporan G2 tanpa membuka port lagi.

## 13 Oktober 2026 — G2 live USB PCB custom berhasil menerima bytes

- Berdasarkan persetujuan eksplisit operator,
  membuka FT232R by-id `A10KMM3S` pada
  Pi **115200 selama 12s** (bukan simulator).
  **4.313 byte, 33 baris** direkam dalam
  evidence JSON pada Pi, checksum SHA256
  ditulis di laporan.
- Klasifikasi: 14 other_json,
  5 i2c_found, 1 i2c_scan_done,
  13 invalid_json, **0 sensor samples**.
  Data I2C konsisten dengan startup;
  invalid mungkin banner plain text
  `printWelcome()` di source. Status
  `SERIAL_DATA_INCONCLUSIVE` dari
  classifier **tidak ditimpa**.
- Transport RX fisik **PASS**,
  validasi payload end-to-end belum
  PASS. Tidak ada perintah TX,
  operasi aktuator, pengaktifan
  akuisisi, atau AI model.
  Pi setelah uji throttling=0x0.
- Dokumentasi:
  `docs/reports/2026-10-13_TAHAP7_G2_USB_LIVE_RESULT.md`.
## 13 Oktober 2026 — Probe G2 USB PCB custom disiapkan

- Pembuat PCB menyatakan desain daya aman
  (attestation, tidak menggantikan
  pengukuran independen VBUS/backfeed).
- FT232R `A10KMM3S` by-id USB Pi
  terkonfirmasi, port/getty siap
  untuk uji G2 setelah kontrol
  keselamatan operasional terpenuhi.
- Menambah `scripts/stage7_usb_readonly_probe.py`
  dan `scripts/test_stage7_usb_readonly_probe.py`
  dengan opt-in G2 + IDLE + onsite,
  framing incremental, bounded
  read dan output evidence nonraw,
  tanpa serial write/aktuator/model.
  QA Windows + Pi **PASS**,
  skrip sudah ada di lingkungan Pi.
- **Port live belum dibuka**.
  G3 Nextion/aktuator tidak dijalankan;
  SOP dan laporan diperbarui.
## 13 Oktober 2026 — G0 foto USB PCB custom

- Audit foto Pi USB-A/USB-C dan PCB custom
  ATmega2560 (USB Type-B, DB9, sakelar
  dan adaptor daya terpisah). Jalur
  VBUS internal belum terlihat/diketahui.
- Pi USB enumerates FTDI FT232R `0403:6001`
  `ttyUSB0`; USB descriptor terdeteksi
  **Bus Powered 90mA** (nilai deklarasi),
  tanpa bukti electrical power isolation.
- **G0 partial/blocked**, G2/G3 NOT RUN.
  Checklist inspeksi PCB sisi dalam,
  pembagian rail USB/DC dan backfeed
  serta larangan membuka serial sementara
  diperjelas dalam SOP dan laporan baru.
- Tes UART testbed Arduino Mega yang
  sebelumnya sukses tetap valid sebagai
  **hasil board terpisah**, bukan klaim
  verifikasi PCB custom Smart Coffee.

## 12 Oktober 2026 — UART hardware testbed E2E PASS

- Pengguna memperbaiki wiring
  `HV1→Mega TX1 D18` dan
  `HV2→Mega RX1 D19`.
- Raw UART pada GPIO15 Pi sekarang
  menerima heartbeat JSON valid;
  ditemukan bug parser read_until
  yang menyalahkan potongan frame
  akibat timeout 0,5s untuk
  trafik Arduino periodik 1s.
- Mengganti receiver dengan
  incremental bounded LineFramer
  dan test fragmentasi/CRLF/oversize.
  **RX-only PASS** 5 frame/0 error.
- **PING/PONG E2E PASS**: Pi
  5 heartbeat + 1 PONG, USB Mega
  COM6 1 PING ACK. Uji 30s
  28 heartbeat/1 PONG/0 error.
- Menambah raw passive diagnostic,
  monitor USB laptop, ringkasan
  checksum evidence dan laporan
  post-rewiring.
- Hanya **Mega 2560 testbed
  dan Pi UART GPIO**; produksi
  Smart Coffee/PCB custom,
  Nextion, 115200 GPIO, AI
  belum dinyatakan PASS.

## 12 Oktober 2026 — UART testbed Mega 2560 ↔ Pi 5, diagnosis hardware

- Menambah proyek bench terisolasi
  `bench/mega_pi_uart/`: `platformio.ini`
  Mega, firmware heartbeat USB 115200/
  Serial1 GPIO 9600, parser Python
  Pi dengan timeout, limit frame, nonce
  PING allowlist, validasi seq/uptime,
  unit tests dan SOP.
- Upload sketch baru **HANYA ke Mega
  testbed COM6 CH340**, signature
  0x1e9801 tervalidasi dan flash
  **3212 bytes verified**; USB debug
  Mega mengirim HEARTBEAT 1–19.
- Pi SSH: `ttyAMA0` GPIO14/15
  UART aktif, serial-getty nonaktif.
  Pengujian RX 20s mendapatkan **0
  frame**. Pi diagnostic PING satu
  kali (bukan perintah aktuator)
  tidak mendapatkan PONG, dan
  Mega debug **tidak menerima PING**.
- **UART E2E testbed belum PASS**.
  Perlindungan 5 V→3,3 V dan
  sambungan level converter harus
  diperiksa secara fisik sebelum
  uji lanjut. Firmware utama
  PCB custom, konfigurasi lokal
  `platformio.ini` root, CSV/AI
  tidak diubah.
- Bukti JSON pada `bench/mega_pi_uart/evidence/`,
  laporan `bench/mega_pi_uart/reports/2026-10-12_BENCH_TEST.md`.
## 12 Oktober 2026 — Riset keamanan USB dan E2E offline Tahap 8

- Meneliti sumber resmi Raspberry Pi (batas
  USB dan larangan back-powering) dan FTDI
  FT232R (skema self-powered); port USB Pi
  normal bagi perangkat USB compliant.
  PCB ATmega custom dengan PSU berbeda
  **belum dibuktikan proteksi VBUS/backfeed**,
  sehingga G0 belum PASS, G2/G3 NOT RUN.
- SSH read-only Pi: `usb_max_current_enable=1`,
  `throttled=0x0`, FT232R `ttyUSB0`
  dan tidak terlihat overcurrent dalam
  potongan kernel log yang difilter.
  Tidak ada serial port opened.
- Menambah `scripts/stage8_offline_e2e.py`,
  regresi `scripts/test_stage8_offline_e2e.py`,
  dan bukti `results/stage8_offline_e2e_v1/`.
  **11/11 kontrak mock E2E PASS** di Windows
  dan langsung pada Pi: 151 frame nyata,
  151/151 projection autosave in-memory,
  9 negative FAIL_CLOSED, keputusan AI N/A.
  Bukti Pi identik dengan output Windows;
  tidak ada raw edited, firmware flashing,
  Nextion nyata/aktuator atau model diaktifkan.
- **Tahap 8 mock selesai; Tahap 9 fisik dan
  Tahap 10 rilis AI tetap NO-GO**.
  Laporan `docs/reports/2026-10-12_RISET_USB_PI5_DAN_E2E_TAHAP8.md`.
## 12 Oktober 2026 — Catu daya ATmega dan Pi terpisah

- Operator menegaskan USB ATmega↔Pi tetap
  terhubung, sementara ATmega dan Pi masing-
  masing memakai adaptor daya sendiri.
- Menambahkan pemeriksaan G0 terkait
  jenis board/USB FT232R, jalur adaptor
  eksternal, pemilihan VBUS/backfeed,
  catu aktuator/sensor, dan dampak reset.
  Arduino Mega Rev3 mempunyai pemilihan
  sumber otomatis, tetapi tidak boleh
  diasumsikan pada PCB custom.
- **G0 partial/belum PASS, G2/G3 tetap
  tidak dijalankan**. Tidak ada pembukaan
  port serial, flashing, atau pengendalian
  aktuator.

## 12 Oktober 2026 — Klarifikasi USB langsung ATmega → Pi

- Operator menegaskan koneksi **kabel USB langsung
  dari board ATmega ke USB Raspberry Pi**,
  bukan GPIO14/15 atau FT232 TTL kabel eksternal.
  USB FT232R `ttyUSB0` terenumerasi secara
  pasif dan konsisten sebagai bridge USB-serial,
  tetapi pencocokan board dan daya USB
  belum ada bukti fisik.
- Mengonfirmasi UART0/Serial 115200 untuk
  host, Serial2 9600 untuk Nextion,
  Serial1 belum aktif. Membetulkan satu
  dokumen wiring historis TQFP-100
  dari pin kemasan 8/9 yang salah menjadi
  PH0/RXD2 12 dan PH1/TXD2 13.
- Mengarahkan SOP ke jalur USB langsung,
  mempertegas gerbang G0 VBUS/backfeed
  belum PASS, G1 kabel terpasang menurut
  operator, G2/G3 NOT RUN.
  Tidak ada port serial dibuka/flash/
  kontrol aktuator selama pemeriksaan.
- Menambah regresi static contract
  `scripts/test_stage7_usb_contract.py`.
## 12 Oktober 2026 — Konfirmasi jalur FT232 dan G0 safety hold

- Operator menetapkan **FT232 USB-to-TTL**
  (`ttyUSB0`) sebagai jalur Pi–ATmega,
  namun tidak mengetahui USART MCU dan
  belum memverifikasi level tegangan TTL
  sambungan langsung.
- Audit repo tidak menemukan skematik PCB
  yang cukup untuk membuktikan TX/RX,
  ground, VCCIO, atau VBUS/backfeed.
- SOP UART diberi checklist foto, pemeriksaan
  pin dengan daya mati, identitas VCCIO,
  dan izin G2 terpisah. **G0 BLOCKED**;
  tidak membuka serial, menjalankan
  model, atau menggerakkan aktuator.

## 12 Oktober 2026 — Verifikasi topologi UART Pi (tanpa port open)

- Operator menyatakan telah memasang koneksi
  UART ATmega2560 ke Pi. SSH Tailscale
  berhasil setelah autentikasi ulang.
- Audit Pi read-only: FT232R USB-to-TTL
  `ttyUSB0`, GPIO UART0 `ttyAMA0`,
  pinmux GPIO14 TXD0/GPIO15 RXD0,
  `serial0 -> ttyAMA10` debug.
- Source firmware menulis ke `Serial`
  115200, bukan `Serial1` D18/D19;
  pemetaan kabel dan level tegangan
  belum diketahui. **Tidak ada port
  dibuka, flashing atau aktuator yang
  dikendalikan.**
- Menambah skrip dan regresi
  `stage7_uart_preflight.py`,
  `test_stage7_uart_preflight.py`
  serta SOP/report khusus UART.
  Gerbang fisik tetap **NO-GO**
  sampai wiring/voltage dan izin tes
  read-only dikonfirmasi.
## 11 Oktober 2026 — SOP bench USB ATmega → Raspberry Pi

- Membuat `docs/STAGE7_USB_ATMEGA_PI_BENCH_SOP.md`
  dengan G0 pengecekan PCB/sumber daya/VBUS,
  G1 pemasangan kabel, G2 pembacaan serial
  **115200 read-only** dan auto-reset DTR,
  G3 opsional satu siklus pengujian Nextion
  **5 × (25s purging + 5s collecting)**.
- Perintah enumerasi dan pemilik port disusun
  agar **tidak otomatis membuka** tty,
  beserta kriteria PASS/FAIL/INCONCLUSIVE,
  formulir operator, penghentian/rollback
  dan larangan flashing/USB bypass/aktuator
  tanpa izin tambahan.
- `stage7_pi_adapter.py` menerapkan
  POSIX exclusive advisory dan batas panjang
  pembacaan USB; regresi stub PySerial memeriksa
  DTR/RTS nonaktif, batas buffer, dan
  **tidak pernah menulis ke MCU**.
- **SOP PREPARED, hardware NOT RUN**.
  Laporan `docs/reports/2026-10-11_TAHAP7_USB_BENCH_SOP_QA.md`.
## 11 Oktober 2026 — Tahap 7: venv dan replay CSV asli langsung di Pi

- SSH Tailscale ke `enose-v3@enose-pi5` berhasil;
  Raspberry Pi 5 Model B Rev 1.1, Debian 13,
  Python 3.13.5 dan preflight read-only terverifikasi.
- Membuat `~/smart-coffee-stage7/.venv` di Pi
  dan memasang **pyserial==3.5** hanya ke venv;
  tidak mengubah Python global/layanan.
- Menambah `scripts/stage7_pi_adapter.py` (mode
  replay-csv/replay-jsonl dan serial-readonly
  yang dilindungi izin eksplisit), regresi
  `scripts/test_stage7_pi_adapter.py`,
  serta `scripts/requirements-stage7-pi.txt`.
- Mentransfer satu CSV asli dan source + ringkasan
  gate melalui SSH/SCP; hash SHA256 CSV cocok
  antara host dan Pi. Regresi bridge/adapter/
  preflight **PASS di Pi**, replay
  `D-GAW_B33.csv` **151 sampel, COMPLETE_QA,
  AI_TEST=N/A**, tanpa serial fisik.
- Menambah laporan dan bukti
  `docs/reports/2026-10-11_TAHAP7_PI_VENV_OFFLINE_REPLAY.md`
  dan `results/stage7_pi_remote_v1/`.
  ATmega/Nextion/aktuator/COM5 tetap tidak disentuh.

## 10 Oktober 2026 — Tahap 7: adapter Pi dan mock protokol aman

- Berdasarkan konfirmasi operator, ATmega tidak dikoneksikan ke
  COM5 dan Pi 5 sudah dinyalakan untuk remote. Tanpa identitas
  SSH valid, **tidak mengklaim Pi telah diakses**, USB/UART
  fisik belum dapat diuji.
- Memprioritaskan USB Serial 115200 untuk integrasi pertama.
  Serial1 GPIO memerlukan bukti skematik/level shifter
  dan konfigurasi UART Pi 5; debug UART utama default
  berada pada header khusus.
- Menambah `scripts/stage7_bridge.py`: validator
  JSON-per-line legacy, session ID lokal, kontrol urutan
  fase/indeks/uptime, fail-closed disconnect/duplikasi,
  keputusan AI_TEST N/A tanpa model. Envelope v1 dan
  ACK/NACK baru **simulasi**, belum aktif di firmware.
- Menambah `scripts/stage7_pi_preflight.py` read-only
  dan tes `test_stage7_bridge.py`,
  `test_stage7_pi_preflight.py`, replay CSV asli
  `results/stage7_offline_v1/` tanpa mengubah raw.
- SOP `docs/STAGE7_PI_REMOTE_AND_SERIAL_SOP.md` dan
  laporan `docs/reports/2026-10-10_TAHAP7_PI_INTEGRATION_PREP.md`.
  Firmware, HMI, USB/COM5, EEPROM dan aktuator tidak diubah.
- QA regresi Stage 0–7, CSV umum 89/89, kontrak HMI
  12 halaman/23 event, build PlatformIO 2/2 **PASS**.
  Klien SSH Windows tersedia; remote Pi dan serial
  hardware tetap **NOT TESTED**.
## 10 Oktober 2026 — Dataset ilmiah riil dan gerbang Tahap 6

- Meneliti dataset publik kopi E-Nose yang berkaitan
  dengan artikel peer-reviewed, terutama CoffeePow-4,
  Aroma-7, Colombian Coffee (58 pengukuran), dan
  riset sembilan sensor MOS kopi 2023.
- Mengunduh CoffeePow-4/Aroma-7 asli dari Zenodo
  (MD5 publisher dan SHA256 **PASS**), menemukan
  3.583/4.750 rangkaian lengkap, 4 pembacaan tail
  tak lengkap pada Aroma-7, serta overlap data
  CoffeePow-4 secara **identik** di Aroma-7.
- Menambah downloader hash-verified, benchmark
  40 kombinasi (2 dataset × 2 target × 2 split × 5 model),
  tes regresi, dan hasil `results/external_coffee_enose_v1/`.
  RF 4-kelas CoffeePow-4 macro-F1 0,906 random
  vs 0,501 tail; **bukan** skor perangkat lokal.
- Dataset Colombian Mendeley terverifikasi metadata
  tetapi **HTTP 403** saat unduh melalui API; data
  9 MOS paling mirip hardware **on request**.
- Tahap 6 hanya implementasi gerbang fail-closed
  `stage6_release_gate.py` dan regresinya;
  `model_promotion_allowed=false`, AI_TEST N/A.
  Tidak ada model final, flashing, pengubahan
  firmware/Nextion/COM5 atau penggabungan data luar ke lokal.
- Laporan `docs/reports/2026-10-10_RISET_DATASET_EKSTERNAL_DAN_TAHAP6.md`.
## 9 Oktober 2026 — Tahap 5: risiko model, drift sintetik dan unknown

- Mengembangkan `scripts/stage5_validation.py` beserta uji
  `scripts/test_stage5_validation.py`, menggunakan input SHA256
  snapshot Stage2/3 versi terkoreksi dan **83 kandidat kopi**.
- Membandingkan RF82 dan LDA10 pada 4-fold LOBO dengan prediksi
  out-of-fold, risk–coverage a priori, metrik per kelas, dan
  bootstrap empat batch secara deskriptif; **tidak melakukan
  tuning threshold atau menyimpan model akhir**.
- **P0:** kedua model memprediksi *light roast* terhadap **5/5
  sampel udara bersih valid**, 0/5 ditolak pada ambang 0,6.
  Kedua model salah pada 38/83 file kopi OOF. Ketepatan
  confidence dan kemampuan deteksi unknown **tidak tervalidasi**.
- Simulasi pergeseran gain ADC ±5%/±10% memperlihatkan
  RF berubah prediksi pada 8–17 file, sedangkan LDA response10
  tetap dalam asumsi transformasi sintetik (bukan data fisik).
- Keluaran `results/stage5_validation_v1/`, laporan
  `docs/reports/2026-10-09_TAHAP5_GENERALISASI_UNKNOWN_QA.md`.
  Tahap 5 engineering offline selesai tetapi **NO-GO
  validasi prospektif, unknown, dan promosi model**.
- QA regresi Stage 0–5, PlatformIO dua environment, Nextion 12
  halaman/23 event, dan validator struktur 89/89 CSV **PASS**;
  tes tersebut bukan bukti kelayakan inferensi produksi.

## 9 Oktober 2026 — Tahap 4: CAW udara bersih dan benchmark LOBO

- Operator mengonfirmasi **kode CAW dan seluruh batch B37 = udara bersih**.
  Menambahkan empat CAW B33–B35 ke daftar pengecualian yang sebelumnya
  mencakup dua B37. Kode audit/fitur/plot mencegah kebocoran CAW/B37
  ke training dan grafik berlabel kopi, termasuk fail-closed SHA256.
- Menghasilkan snapshot baru `data/analysis/stage2_v2/` (83 kandidat
  kopi + 6 udara bersih, total 89 CSV), `data/processed/stage3_v2/`
  (**83 fitur kandidat valid**), mempertahankan snapshot lama sebagai arsip
  dan **tidak** mengedit raw.
- Menambahkan `scripts/stage4_model_benchmark.py` dan regresi negatif
  `scripts/test_stage4_model_benchmark.py`: 7 grup fitur × 8 baseline/
  challenger × 4 batch LOBO = **224 fit/fold**, 4.648 prediksi.
  Skor deskriptif tertinggi RF expanded82 macro-F1 **0,490**; LDA response10
  **0,482**; penurunan pada B34/B35 masih tinggi.
- Artefak benchmark `results/stage4_lobo_v2/` meliputi metrik fold,
  metrik per kelas, confusion matrix, prediksi terindeks SHA256, peringkat
  eksploratori serta config versi sklearn. Tidak ada model disimpan atau
  di-deploy. Laporan `docs/reports/2026-10-09_TAHAP4_MODEL_LOBO_CAW_CORRECTION.md`.

## 9 Oktober 2026 — Tahap 3: kontrak fitur MQ3 deterministik

- Menjadikan `extract_sensor_features` fungsi ekstraksi murni untuk input frame sensor tanpa label; kontrak legacy 62 fitur dipertahankan. Tambah varian eksploratori 82 fitur, dengan tujuh grup subset yang didefinisikan tanpa fitting/model.
- Memeriksa 87 kandidat Stage 2 berdasarkan SHA256. **86 lolos ekstraksi ketat**, `L-CAW_B34.csv` ditahan (sampel purging indeks 8 siklus 1 hilang). Data raw tidak diubah; dua file bench B37 dikecualikan.
- Tambah `scripts/stage3_feature_pipeline.py`, `scripts/test_stage3_feature_pipeline.py`, `data/processed/stage3_v1/`, dan kontrak `data/processed/STAGE3_FEATURE_CONTRACT.md`. Melindungi dari file/hash berbeda, metadata/label bocor ke model, CSV ADC invalid, suhu/kelembapan hilang, penulisan ke raw atau overwrite output tidak sengaja.
- Dokumentasi: `docs/reports/2026-10-09_TAHAP3_PREPROCESSING_FEATURE_QA.md`. Model belum dilatih; label/spesimen independen, baseline dan evaluasi LOBO masih membutuhkan Tahap 2/4/5.
- QA akhir **PASS**: PlatformIO kedua environment, HMI 12 halaman/23 event, validator 89/89 CSV umum, 87/87 B32–B35 canonical, regresi Stage 0–3, parity/tes negatif dan compileall. **Satu file Stage 3 tetap HOLD** bukan kegagalan yang disembunyikan.

## 9 Oktober 2026 — Tahap 2: provenance dan kualitas data

**Status:** perangkat audit snapshot dan QA reproduksibel selesai; verifikasi label/origin serta identitas spesimen tetap P0 terbuka.

- Catat konfirmasi operator bahwa valve/pompa berpindah mengikuti 25/5 detik dan Nextion mencapai halaman selesai tanpa error (bukti observasi, belum pengukuran instrumen). Uji negatif Tahap 1 tetap terbuka.
- Tambahkan skrip `stage2_dataset_audit.py` beserta tes negatif untuk manifest SHA256, kualitas CSV, label dan cohort, kelengkapan kelas, perubahan baseline purge, proxy drift, serta flag outlier eksploratori.
- Audit **89 CSV B32+**: 87 kandidat belum disetujui untuk ML dari B32–B35 dan 2 file udara bersih B37 dikecualikan. Terdapat 9 sel kode–batch kosong, 4 sel berulang dan 33 flag file–kanal untuk review (bukan 33 file rusak).
- Perkuat generator plot agar mengabaikan bench B37 berdasarkan hash serta menahan batch baru B36+ sampai provenance direview; data mentah dan grafik eksisting tidak dihapus.
- Buat keluaran `data/analysis/stage2/` dan laporan `docs/reports/2026-10-09_TAHAP2_PROVENANCE_KUALITAS_DATASET.md`. Tidak dilakukan training model atau operasi alat.

## 9 Oktober 2026 — Hasil bench Nextion B37 dengan udara bersih

- Operator menyampaikan selang menggunakan udara bersih selama batch B37; dua file final `L-MING_B37.csv` dan `M-MING_B37.csv` ditemukan dari log listener COM5.
- Validator canonical untuk **150 dan 152 baris** sama-sama PASS. Evaluasi target ketat 25/5×5 PASS untuk L-MING, dan FAIL untuk M-MING karena ada 6 collecting pada siklus 1 dan 5; indeks tetap kontigu.
- Mencatat checksum serta hasil SOP B01–B08 pada `docs/reports/2026-10-09_TAHAP1_BENCH_B37_UDARA_BERSIH.md`. Tidak ada aksi serial atau modifikasi hardware oleh agen.
- Menambahkan `data/analysis/bench_only_exclusions.csv` dan peringatan di `data/raw/README.md`: label kopi dalam kedua file B37 **tidak valid sebagai ground truth**, kecualikan dari training/evaluasi roast/origin. File mentah tetap utuh.
- Memperbaiki laporan QA bench agar kasus ekstra sampel tidak disalahartikan sebagai sample_idx nonkontigu, dan membedakan validator CSV umum dengan target bench ketat.

## 9 Oktober 2026 — Preflight bench pasif Tahap 1

**Status:** satu sesi serial USB→listener→CSV final **PASS** berdasarkan bukti read-only, belum menjadi verifikasi aktuator/Nextion/perangkat menyeluruh.

- Memeriksa status listener aktif COM5@115200 dan log START/COMPLETE tanpa membuka COM5 maupun mengganggu proses.
- Memvalidasi `L-MING_B32_20261009_172056.csv`: 150 baris sensor, lima siklus × 25 purging + 5 collecting, timestamp MCU 996–1004 ms antar-sampel, kanal numerik lengkap, suhu/kelembapan terbaca. File mentah **tidak** diubah/di-commit.
- Menambah `scripts/bench_stage1_passive_qa.py` (validator CSV final non-destruktif) dan `scripts/test_bench_stage1_passive_qa.py` (fixture positif/negatif).
- Membuat **draf** `docs/SOP_BENCH_TAHAP1.md` dan bukti `docs/reports/2026-10-09_TAHAP1_BENCH_PASIF_PRECHECK.md`.
- Remaining gate: operator mengesahkan scope dan keselamatan SOP aktif, periksa firmware terpasang, uji valve/Nextion/fault cases pada perangkat fisik. **Tidak ada flashing atau penghentian listener.**

## 9 Oktober 2026 — Tahap 1: pengamanan firmware dan akuisisi (offline)

**Status:** peningkatan firmware/QA offline diterapkan; tahap verifikasi timing dan hardware fisik **BELUM SELESAI**.

- `#pin_scan;` kini selalu ditolak dengan `PIN_SCAN_DISABLED`, tanpa mengubah pin GPIO/I2C/UART; implementasi pemindaian lama dibuang.
- Uji valve manual melalui serial dinonaktifkan secara default lewat `ENABLE_MANUAL_ACTUATOR_TESTS=0`; hanya dapat diaktifkan melalui build khusus ber-SOP.
- Perintah serial `#start;` menolak ADC yang belum lengkap; `#scan;` menolak pemindaian I2C selama akuisisi aktif.
- Event `ACQ_START` pada `ai_test` tidak lagi memuat label roast/origin/batch atau filename. Metadata untuk `labeled_data` tetap kompatibel.
- `adsCallback` mengirim data sesuai fase saat dibaca terlebih dahulu, baru memproses transisi/COMPLETE; tidak lagi mengirim frame sensor saat idle/paused. Ini mencegah event COMPLETE menutup CSV sebelum sampel terakhir dikirim pada callback yang sama.
- Menambah `scripts/test_stage1_firmware_contract.py` dan kasus tambahan `scripts/test_acquisition_integrity.py` (AI_TEST tanpa label, completion duplikat, STOP parsial).
- Bukti, mitigasi dan pekerjaan bench: `docs/reports/2026-10-09_TAHAP1_FIRMWARE_AKUISISI_QA.md`. Tidak ada flashing, akses COM5, perubahan EEPROM, atau uji aktuator fisik.

## 9 Oktober 2026 — Tahap 0: audit kontrak sistem dan revisi baseline

**Status:** audit offline dan dokumentasi **selesai**; verifikasi fisik, keputusan label, serta transport Pi masih menjadi pekerjaan tahap berikutnya.

- Menambahkan `docs/02_KONTRAK_SISTEM_DAN_KEPUTUSAN_TAHAP0.md`: matriks sumber acuan, batas bukti, pemetaan UART/USB, definisi dataset, dan daftar tindak lanjut T0-01–T0-07.
- Mengoreksi kekeliruan dokumentasi tentang pin TQFP-100 Nextion berdasarkan datasheet Microchip: PH0/RXD2 = pin 12 dan PH1/TXD2 = pin 13 (header Arduino D17/D16 tetap).
- Memperbaiki komentar durasi akuisisi firmware yang usang (180/60 detik → 25/5 detik, 5 siklus), keterangan diagnostik pin D19/RX1, dan label I2C hardware tanpa mengubah logika kontrol aktuator.
- Menambahkan `scripts/test_stage0_contract.py` untuk pemeriksaan otomatis lintas firmware, JSON, CSV, urutan ADC, alamat ADS1115, pin Nextion, HMI dan konsistensi metadata preset.
- Menyelaraskan current state, roadmap, arsitektur Pi, README, panduan Nextion, AGENTS.md, dan audit QA/QC. Transport Pi saat ini USB Serial; UART terpisah masih rancangan.
- Pengujian: **PASS** build PlatformIO dua environment, pemeriksaan HMI, regresi akuisisi/fitur, 86/86 CSV B32–B35, 18/18 B32, tes kontrak Tahap 0, sintaks Python, dan Git diff check.
- Risiko tersisa: `#pin_scan` menyentuh D19/RX1 dan D20/SDA; label UI masih masuk ke event `AI_TEST`; kode origin TEM/MUK/CAW dan tiga preset tambahan perlu konfirmasi; wiring fisik serta inferensi Pi belum diuji.

**Bukti dan langkah berikutnya:** `docs/reports/2026-10-09_TAHAP0_AUDIT_KONTRAK_DAN_QA.md`, `docs/01_MASTER_E2E_ROADMAP.md`. Commit milestone dapat dilacak melalui Git pada branch `wahyu`.
