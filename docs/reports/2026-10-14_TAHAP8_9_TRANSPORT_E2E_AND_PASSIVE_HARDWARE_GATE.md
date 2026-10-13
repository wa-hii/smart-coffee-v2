# Smart Coffee E-Nose v2 — integrasi E2E Tahap 8 / kesiapan pasif Tahap 9

**Tanggal:** 14 Oktober 2026 (WIB). **Konteks:** operator
remote, tidak berada di dekat PCB/Nextion. Target:
meneruskan bagian roadmap yang dapat diverifikasi tanpa
flashing, USB serial open, reset, kalibrasi, atau aktuasi.

## 1. Batas klaim

| Lapisan | Hasil | Yang belum dibuktikan |
|---|---|---|
| Firmware `mega2560` dan `nextion_test` di Windows | Build SUCCESS | Binary benar-benar terpasang di PCB |
| Kontrak Nextion 12 halaman, 23 event, Serial2 9600 | PASS statis | Touch event LCD secara fisik ke ATmega |
| UART bytes → Python parser → sesi 5 siklus → AI N/A | PASS offline | 150 detik nyata via FT232R |
| Identitas FT232R dan Pi power throttle | PASS pasif | Isolasi VBUS/backfeed, pin fisik, keselamatan aktuator |
| AI model | NO-GO | Generalisasi, unknown, validasi prospektif |
| G3 sesi fisik lima siklus | INCONCLUSIVE | START→COMPLETE aktual dan latency fase |

Tidak ada dasar mengklaim integrasi fisik E2E atau akurasi
model dari hasil ini. Binary MCU masih diduga lebih lama
dari `75cb38a`; ini **hipotesis**, bukan fingerprint binary.

## 2. Implementasi baru: transport integration offline

**Source**: `scripts/stage8_transport_integration.py`,
uji: `scripts/test_stage8_transport_integration.py`.

Sumber tetap `data/raw/D-GAW_B33.csv`, SHA256:
`d5e690f538a3967e2d07ded64903d284a348c1988bcc331a380dd50b0a8be819`.
Data ADC **asli** dari file ini dipakai in-memory untuk
memperoleh 151 frame selama 5 siklus. Tetapi UART JSON,
banner, event Nextion dan frame IDLE semuanya
**direkonstruksi/disimulasikan**. Tidak pernah membaca
UART fisik pada pengujian ini; input mentah tidak berubah.

Urutan perangkat lunak yang diuji:

```text
CSV riil historis B33 [read-only]
  → firmware-like wire JSON [SIMULATED in RAM]
  → USB chunk fragmentation & empty read [SIMULATED]
  → stage7_pi_adapter.SerialLineFramer
  → stage7_bridge.LegacySessionBridge
  → stage6_release_gate / AI N/A / NO_GO
  → metadata evidence without ADC values
```

**15 skenario**, masing-masing dinilai pada host Windows
dan Raspberry Pi menggunakan regresi deterministik:

| Kasus | Terminal | Catatan |
|---|---|---|
| Normal + startup/IDLE | `COMPLETE_QA` | 151 sampel aktif + 1 IDLE ditolak |
| Normal tanpa startup | `COMPLETE_QA` | 151 sampel aktif |
| AI_TEST START dengan label firmware legacy | `NOT_STARTED` | Label leak diketahui dan ditolak |
| Timing ACQ_START salah | `NOT_STARTED` | Start contract reject |
| ACQ_START tidak muncul | `NOT_STARTED` | Tidak ada sesi yang boleh diciptakan |
| ACQ_START duplikat ketika sesi aktif | `FAIL_CLOSED` | Abort setelah satu hasil final |
| ACQ_COMPLETE hilang | `FAIL_CLOSED` | EOF stream |
| Serial disconnect di tengah JSON | `FAIL_CLOSED` | Partial tail dan stream putus |
| Kanal MQ3 hilang | `FAIL_CLOSED` | Payload invalid |
| Indeks sampel duplikat | `FAIL_CLOSED` | Tidak ada pemulihan diam-diam |
| Timestamp usang | `FAIL_CLOSED` | Replay/stale reject |
| JSON rusak di tengah sesi | `FAIL_CLOSED` | Parser reject |
| Fase `idle` di tengah akuisisi | `FAIL_CLOSED` | Tidak dihitung sebagai kopi |
| Total ACQ_COMPLETE salah | `FAIL_CLOSED` | Counts tidak konsisten |
| Event INFERENCE dengan label belum diizinkan | `FAIL_CLOSED` | AI release policy |

**Agregasi:** 2 complete, 10 fail-closed, 3 not-started;
semuanya AI `N/A`, tidak ada port serial dibuka, TX ke
MCU=0, pompa/valve=0, model tidak dimuat, raw CSV tidak
ditimpa. `nominal=150` **tidak dipaksakan** sebab B33
memang mempunyai 151 sensor samples; validator menerapkan
toleransi jumlah per fase yang sudah diuji sebelumnya.

**Perbaikan spesifik:** di `receive_serial_chunks()`,
`ACQ_START` kedua ketika ada sesi aktif tidak boleh
membuat sesi baru. Listener mengakhiri pertama sebagai
`duplicate_start_while_active`/`FAIL_CLOSED`, persis
**satu** `SESSION_FINAL`, tanpa retry.
Direct `LegacySessionBridge` yang bersifat umum tidak
diubah; aturan satu-sesi ditambahkan khusus adapter
listener fisik. Ditambah test regresi untuk tiga START
berurutan yang hanya boleh mengonsumsi dua sebelum abort.

## 3. Tahap 9 — USB identity passive, bukan penilaian listrik

**Source**: `scripts/stage9_passive_readiness.py`,
uji: `scripts/test_stage9_passive_readiness.py`.
Skrip hanya menjalankan `udevadm info`, `fuser`,
`vcgencmd get_throttled`, serta inspeksi symlink dan
jenis file device. Tidak menjalankan pyserial/open tty,
GPIO, `lsusb -v` yang berpotensi control transfer,
rebind kernel, sudo, reset, atau flash.

Output aktual Pi:

- Serial FT232R: `A10KMM3S`.
- USB VID:PID `0403:6001`.
- udev driver: `ftdi_sio`.
- By-id symlink valid → `/dev/ttyUSB0`, character device.
- `fuser`: **NO_VISIBLE_OWNER** (dengan keterbatasan
  observabilitas privilege proses yang dimiliki user).
- `vcgencmd get_throttled`: `throttled=0x0`.
- Status eksplisit:
  `PASS_PASSIVE_IDENTITY_ONLY_HARDWARE_E2E_NOT_TESTED`.
- Flag keselamatan: `physical_power_backfeed_tested=false`,
  `mcu_binary_version_verified=false`,
  `nextion_live_command_verified=false`,
  `five_cycle_actuation_verified=false`,
  `g3_live_release_allowed=false`.

**Jangan mengartikan pemeriksaan ini sebagai G0 listrik
PASS**. Backfeed antara PSU eksternal PCB dan USB Pi hanya
boleh dibuktikan lewat skematik dan pengukuran hardware
dengan teknisi onsite.

## 4. Bukti di Raspberry Pi / hasil QA

Project Pi: `/home/enose-v3/smart-coffee-stage7`.
File hasil dibuat memakai mode create-exclusive, dengan
nama baru, tanpa menghapus evidence sebelumnya:

1. `results/pi_stage8/transport_integration_v2_20261014.json`
   SHA256 `0453616901a4109ab446818a3507c83a55c4737eca5f50033b787727b7cf6927`.
2. `results/pi_stage9/passive_identity_v2_20261014.json`
   SHA256 `dc44d3a23e9d509702814e1b302b6f8494ea763d90b9ce6297179b7e62fd538a`.

Checksums source scripts Windows/Pi identik:

- Stage7 adapter `c5d3b41d4ab962ef919845841d05afb147722345c7d62b3d75e6e8c20d3979e5`.
- Stage8 transport `eca65583a663bcc8df0d6c569fc1ad3ab26554ee08d0ce1db1d27dc7600ababa`.
- Stage9 passive `c9e2c8588004824f3f8cde4907534a0b833f48eeb2ade3cd68798726a7136f93`.

Regresi yang dijalankan:

- Windows: Stage0, Stage1, Stage6, Stage7 bridge/adapter,
  Stage7 guarded USB (offline), Stage8 baseline dan byte-stream,
  Stage9 passive tests, Python `compileall`: **PASS**.
- Pi `.venv`: Stage7 adapter, Stage8 transport/baseline,
  Stage9 passive tests, plus CLI dua evidence: **PASS**.
- `pio run -e mega2560 -e nextion_test` Windows:
  dua environment **SUCCESS** (tanpa flashing).
- Nextion Figma/HMI static checker Windows:
  12 pages, 23 events, Serial2 9600 **PASS**;
  warning Pillow `getdata` deprecation tidak memengaruhi status.
- `git diff --check`: PASS.

## 5. Status dan pekerjaan berikutnya

**Verified software:** protokol synthetic UART → Pi parser
→ sesi 5 siklus + fault fail-safe. **Verified passive USB
identity:** perangkat FT232R dengan serial benar terdeteksi.

**Belum terverifikasi secara fisik:** kontrak START Nextion
ke MCU, binary firmware yang di-flash, arus/isolasi USB-VBUS,
sensor membaca selama 5 siklus live, pompa dan valve aman,
ACQ_COMPLETE/latensi live, hasil dari Pi muncul di pResult.

**Gerbang selanjutnya** saat tersedia operator di depan alat:
verifikasi skema listrik dan identitas firmware; lakukan
satu G3 5 siklus yang diawasi secara fisik dengan listener
RX 115200 dan evidence baru; nilai event dan fase serta
jumlah sampel, kemudian putuskan perbaikan firmware.
Tidak boleh ada perubahan ACQ/AI label gate, flashing,
kalibrasi EEPROM, atau remote START otomatis untuk menutup
gap tersebut. **AI model release tetap NO-GO.**
