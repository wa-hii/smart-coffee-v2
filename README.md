# Smart Coffee E-Nose v2

**19 Oktober 2026 — diagnosis dropout COM7 dan sesi lanjutan:** log Windows
Probook memperlihatkan dua sesi lengkap (ALAT_1/COM5 `M-GRB_B61`,
ALAT_2/COM6 `L-MING_B51`: masing-masing 900 baris, PASS) dan satu
dropout USB pada ALAT_3/COM7 `L-MING_B52` setelah 597 baris dengan
`ClearCommError Access is denied`, diikuti `usb_not_found`.
`M-GRB_B62` baru terlihat `ACQ START`; keberhasilan akhirnya belum
diketahui dari potongan log. Paket v6 menambah diagnostik read-only,
identitas alat pada output console, log untuk event completion yang ditolak,
dan pengujian 2 sesi berurutan pada tiap alat secara paralel.
ZIP: `dist/Smart_Coffee_ENose_USB_Receiver_Windows_v6_ThreeDevices_Diagnostics.zip`.
**Tidak ada uji hardware baru ataupun jaminan koneksi fisik COM7 telah pulih.**

**19 Oktober 2026 — dukungan multi-device receiver (software-only):** satu
laptop Windows kini dapat menggunakan tiga alat E-Nose pada COM5/COM6/COM7
secara paralel melalui `scripts/multi_device_receiver.py`. Setiap proses
menulis CSV dan log ke folder `data/raw/devices/ALAT_1..3/` serta
`logs/devices/ALAT_1..3/`, dan memakai USB serial bridge untuk identitas
stabil bila tersedia. Tidak ada perubahan firmware, HMI, atau pengoperasian
hardware. Paket portabel terbaru:
`dist/Smart_Coffee_ENose_USB_Receiver_Windows_v5_ThreeDevices.zip`.
Panduan: `windows_receiver/README_THREE_DEVICES.md`. Pengujian tiga proses
paralel dengan CSV sintetis 900 sampel per perangkat PASS, tetapi belum
terverifikasi dengan tiga alat fisik.

**18 Oktober 2026 — perbaikan salah folder dan receiver ganda (Windows):**
audit menemukan tiga instalasi receiver aktif sekaligus (lima proses Python,
termasuk proses launcher), satu receiver repo mencoba COM5 yang tidak ada,
dan portable receiver lama justru merekam COM4 ke `Downloads/.../data/raw`.
Tiga CSV lengkap `L-MING_B50*` (900 sampel per file, QA PASS) sudah disalin
secara aman ke `data/raw/` repo dengan hash cocok; sumber tidak dihapus.
Paket v4 `dist/Smart_Coffee_ENose_USB_Receiver_Windows_v4_SingleInstance.zip`
menambahkan host mutex, informasi lokasi penyimpanan pada status, diagnostik
proses, dan utilitas recovery. Startup Windows pada host pengembangan telah
diarahkan ke satu listener repo `--port auto` untuk login berikutnya, tetapi
receiver yang sedang berjalan tidak dihentikan, dan belum ada uji live baru.
Panduan: `windows_receiver/README_WINDOWS_RECEIVER.md`.

**16 Oktober 2026 — Windows USB Receiver otomatis:** listener Take Data kini
mendukung `--port auto` (default), mendeteksi USB FTDI/Arduino/CH340/CP210x
tanpa hardcode COM5, membuat `data/raw/` jika belum ada, dan reconnect saat
USB dicabut/dicolok kembali. Paket portable dan installer Startup untuk laptop
lain ada di `dist/Smart_Coffee_ENose_USB_Receiver_Windows.zip`; panduan di
`windows_receiver/README_WINDOWS_RECEIVER.md`. **Laptop penerima wajib
memasang/jalankan aplikasi sekali**, firmware saja tidak dapat membuat CSV
Windows. Data tetap ditulis hanya selama Take Data melalui Nextion.

**14 Oktober 2026 — P0 pra-onsite software freeze RC1:**
enam temuan integritas diselesaikan pada source software
dan diuji offline (gap indeks, urutan fase, cross-mode LCD,
serial framing, collector manual, dan identitas firmware).
88/89 CSV B32+ valid; 1 clean-air `L-CAW_B34.csv` memang
rusak dan dikecualikan berdasarkan SHA256, bukan ditambal.
Pi listener menggunakan `serial_wire.py` bersama Windows.
Firmware baru mengirim `FW_HELLO` setelah nanti di-flash,
tetapi **belum terpasang** pada PCB. Software freeze tag
`pre-onsite-software-2026-10-14-rc1` hanya berlaku untuk
source/build offline; AI N/A, G3 live INCONCLUSIVE.
Laporan: `docs/reports/2026-10-14_P0_6_ISSUES_FIXED_INDEPENDENT_QA_SOFTWARE_FREEZE.md`.

**14 Oktober 2026 — milestone Tahap 8/9 remote-only:**
integrasi transport baru `scripts/stage8_transport_integration.py`
menjalankan **15 skenario UART-fragmentation → parser Pi →
validator lima siklus** berbasis `D-GAW_B33.csv` (ADC nyata;
frame UART disimulasikan, bukan capture hardware). Hasil:
2 `COMPLETE_QA`, 10 `FAIL_CLOSED`, 3 `NOT_STARTED`, semuanya
AI `N/A`. Bug sesi START duplikat pada *listener Pi*
diperbaiki menjadi fail-closed dengan satu final.
`scripts/stage9_passive_readiness.py` mengonfirmasi FT232R
`A10KMM3S`/driver `ftdi_sio`/port bebas/throttle normal di
Pi **tanpa membuka tty**. Hardware G3 dan isolasi USB-VBUS
tetap belum diverifikasi; AI tetap NO-GO. Report lengkap:
`docs/reports/2026-10-14_TAHAP8_9_TRANSPORT_E2E_AND_PASSIVE_HARDWARE_GATE.md`.

**14 Oktober 2026 — QA remote tanpa operator di dekat alat:**
Raspberry Pi dan FT232R terdeteksi sehat pada preflight
non-invasif; regresi offline Windows–Pi PASS. Replay pada Pi
dari `D-GAW_B33.csv` menghasilkan `COMPLETE_QA`, 151 sampel
5 siklus (nominal 150 tidak persis), **AI `N/A`**. Listener
sekarang mencatat alasan `ACQ_START` diterima/ditolak
(termasuk `ai_test_label_leakage`) tanpa menyimpan label.
Tidak ada USB serial open, firmware flashing, atau aktuasi
fisik pada sesi remote ini: G3 live masih **INCONCLUSIVE**.
Laporan: `docs/reports/2026-10-14_TAHAP7_REMOTE_UNATTENDED_OFFLINE_QA.md`.

**13 Oktober 2026 20:49 WIB — diagnosis P2:** firmware yang
sedang berjalan mengeluarkan JSON dengan `phase=idle` tiap
sekitar 1 detik; 7/7 frame demikian tertangkap pada tes 8s.
Ini konsisten dengan source firmware pra-`75cb38a`, bukan
bukti definitif versi binary di PCB. Reader Stage 7 kini
mencatat enum fase/Nextion event secara terbatas, tanpa
raw values; tes Windows/Pi PASS. G3 **masih INCONCLUSIVE**,
AI **NO-GO**. Jangan flash atau START otomatis. Rincian:
`docs/reports/2026-10-13_TAHAP7_P2_RUNTIME_FIRMWARE_DIAGNOSIS.md`.

**13 Oktober sekitar 20:20 WIB:** pengujian USB read-only 15 detik
pasca-reboot **berhasil** menerima 5.026 byte/37 baris tanpa
disconnect. Ada 14 JSON dengan field sensor lengkap, tetapi
0 sampel valid dalam kondisi IDLE; jangan menganggapnya
data kopi. G3 tetap INCONCLUSIVE, tidak ada model yang dirilis.
Laporan: `docs/reports/2026-10-13_TAHAP7_P1_USB_IDLE_SCHEMA_15S_RESULT.md`.

**Status terbaru 13 Oktober 20:12 WIB:** reboot Pi yang
dilakukan operator memulihkan enumerasi FT232R
`0403:6001 / A10KMM3S` ke `/dev/ttyUSB0`;
dua cek SSH pasif dan regresi Stage 7/8 offline Windows/Pi PASS.
Kegagalan G3 Run02 (189 JSON lain, nol event/sampel sesuai skema)
**belum terpecahkan**. Jangan membuka serial atau mengulang AI TEST
tanpa persetujuan fisik baru. Detail:
`docs/reports/2026-10-13_TAHAP7_P0_REAUDIT_POST_REBOOT.md`.

**G3 update 13 Oktober 2026:** operator
melihat AI TEST lima siklus berjalan di
Nextion, meski listener Pi lama
`NOT_STARTED`. Bug fragmentasi pesan
USB serial pada `read_until` timeout
telah ditangani via `SerialLineFramer`
dan `receive_serial_chunks`. Uji
fragmentasi serta replay 151 sampel
`COMPLETE_QA` PASS **offline Windows**.
**G3 hardware belum terverifikasi ulang**;
tidak ada firmware atau model yang
dipromosikan. Laporan:
`docs/reports/2026-10-13_TAHAP7_G3_UART_RX_FRAMING_FIX.md`.

**UPDATE UART testbed Mega↔Pi (12 Oktober 2026):**
Setelah perbaikan wiring HV1→D18 TX1,
HV2→D19 RX1 dan bug parser timeout,
**komunikasi dua arah 9600 baud berhasil
di hardware nyata**. Pi 5 `ttyAMA0`
menerima 5 heartbeat dan 1 PONG
tanpa error; tes stabilitas 30 s
**28 heartbeat berurutan, 1 PONG,
0 malformed/gap/duplikasi**.
USB debug Mega COM6 mencatat 1
`PING ACK`. Firmware Smart Coffee
PCB custom, Nextion, AI dan
test 115200 pada GPIO UART **belum
divalidasi dari bukti ini**.
Laporan `bench/mega_pi_uart/reports/2026-10-12_BENCH_TEST.md`.

**UART TESTBED Mega 2560 ↔ Raspberry Pi 5 (12 Oktober 2026):**
proyek eksperimen terpisah `bench/mega_pi_uart/`
mencakup firmware PlatformIO untuk board
Arduino Mega, penerima Python Pi,
uji protokol dan evidence hardware.
Upload firmware **PASS ke CH340 COM6**
(signature ATmega2560 0x1e9801, verify sukses),
heartbeat USB laptop **PASS**;
uji penerimaan Pi GPIO15 /dev/ttyAMA0
9600 baud 20 detik **0 frame**, uji
PING Pi→Mega **0 ACK**. UART fisik
**BELUM BERHASIL**; perlu cek wiring
HV/LV/GND dan D18/D19 Mega ke
GPIO15/14 Pi. Lihat
`bench/mega_pi_uart/reports/2026-10-12_BENCH_TEST.md`.
Firmware Smart Coffee PCB custom,
Nextion, data mentah, model AI
**tidak diubah oleh testbed ini**.

**Riset USB dan E2E offline (12 Oktober 2026):**
Pi 5 menerima perangkat USB self-powered
yang sesuai standar; FT232R telah
terenumerasi. **Keamanan VBUS/backfeed
PCB custom ATmega dengan PSU berbeda
belum bisa dinyatakan PASS**.
Tahap 8 mock E2E dari 151 sampel
sensor asli **11/11 kasus PASS**
di Windows dan Pi; 9 kasus negatif
fail-closed, AI_TEST tetap N/A,
autosave 151/151 diverifikasi di
memori tanpa menulis raw.
Port serial fisik belum dibuka,
Nextion/aktuator/model belum
diaktifkan. Laporan:
`docs/reports/2026-10-12_RISET_USB_PI5_DAN_E2E_TAHAP8.md`.

**Konfirmasi perangkat 12 Oktober 2026:**
ATmega terhubung **USB langsung ke
Raspberry Pi**, bukan via GPIO Pi.
USB bridge FT232R dilihat sebagai
`/dev/ttyUSB0`. Data firmware tersedia
di `Serial`/UART0 115200, **Nextion
memakai Serial2 9600**, Serial1 tidak aktif.
SOP utama:
`docs/STAGE7_USB_ATMEGA_PI_BENCH_SOP.md`.
Kabel sudah terpasang; audit VBUS,
auto-reset dan safety G0 tetap
diperlukan **sebelum membuka port**.

**UART Pi–ATmega (12 Oktober 2026):** ada
FT232R USB-to-UART `/dev/ttyUSB0`
dan native GPIO UART0 `/dev/ttyAMA0`
di Pi 5. `/dev/serial0` justru
mengarah debug ttyAMA10 pada konfigurasi
ini. Koneksi UART ke ATmega dan
level shifter **belum diverifikasi**,
serta firmware belum mengeluarkan data
di `Serial1`. Baca
`docs/STAGE7_UART_ATMEGA_PI5_SOP.md`
sebelum membuka serial.

**SOP bench USB Tahap 7 (11 Oktober 2026):**
`docs/STAGE7_USB_ATMEGA_PI_BENCH_SOP.md`.
G0 cek daya/backfeed, G1 pemasangan kabel,
G2 izin serial read-only 115200 beserta
auto-reset DTR, G3 opsional izin menjalankan
satu sesi lima siklus lewat Nextion.
**Belum ada pengujian fisik/port terbuka**;
berbeda dari SSH dan replay Pi yang sudah PASS.

**Update 11 Oktober 2026 — Raspberry Pi 5 langsung:**
SSH Tailscale ke `enose-v3@enose-pi5` berhasil.
Venv `~/smart-coffee-stage7/.venv` dan adapter
`scripts/stage7_pi_adapter.py` telah disiapkan
langsung di Pi. Replay CSV nyata
`D-GAW_B33.csv` **PASS (151 sampel, AI=N/A)**,
tanpa menghubungkan ATmega atau membuka
port serial. Dokumentasi:
`docs/reports/2026-10-11_TAHAP7_PI_VENV_OFFLINE_REPLAY.md`.

**Tahap 7 (10 Oktober 2026):** ATmega belum dihubungkan
ke COM5; Pi 5 dinyalakan untuk remote, tetapi identitas
SSH belum tersedia untuk verifikasi. Adapter **mock
read-only** untuk USB Serial ATmega 115200 selesai
disiapkan; hasil AI_TEST tetap **N/A** dan tidak dikirim
ke MCU karena model belum tervalidasi. Rujukan
`docs/STAGE7_PI_REMOTE_AND_SERIAL_SOP.md`.

**Update 10 Oktober 2026 — dataset ilmiah nyata dan Tahap 6:**
dataset CoffeePow-4 dan Aroma-7 dari *Results in Engineering*
2025 telah diunduh dari Zenodo, diverifikasi dengan
checksum MD5 resmi dan SHA256, serta diuji pada benchmark
terpisah. **Jangan menggabungkan BME688 10 heater steps
dengan 10 ADC MQ/TGS untuk klasifikasi roast/origin.**
Laporan `docs/reports/2026-10-10_RISET_DATASET_EKSTERNAL_DAN_TAHAP6.md`.
Tahap 6 baru memiliki gerbang fail-closed **AI_TEST=N/A**,
belum model siap pakai.

**Update Tahap 5 (9 Oktober 2026):** risiko dan unknown dievaluasi
di `results/stage5_validation_v1/`. Kedua model roast-only
yang ditinjau masih **mengklasifikasikan 5/5 udara bersih sebagai
light roast**, dengan confidence yang tidak dikalibrasi.
**Jangan aktifkan AI_TEST roast atau unknown di perangkat**
berdasarkan model kandidat ini. Detail:
`docs/reports/2026-10-09_TAHAP5_GENERALISASI_UNKNOWN_QA.md`.

**Update dataset dan benchmark 9 Oktober 2026:** operator mengonfirmasi
**kode CAW dan batch B37 adalah udara bersih**, bukan origin kopi. Gunakan
`data/analysis/stage2_v2/` dan `data/processed/stage3_v2/` untuk 83
file kandidat kopi setelah pengecualian; `stage2/` dan `stage3_v1/`
merupakan arsip pra-koreksi label. Benchmark Tahap 4 eksploratori
`results/stage4_lobo_v2/` memakai LOBO dan **belum menghasilkan model
yang boleh dipakai di Raspberry Pi**. Panduan detail:
`docs/reports/2026-10-09_TAHAP4_MODEL_LOBO_CAW_CORRECTION.md`.

Firmware, antarmuka Nextion, akuisisi data, dan alur pemrosesan AI untuk sistem
e-nose berbasis **ATmega2560**.

## Perangkat keras utama

- ATmega2560
- 10 kanal sensor gas melalui ADS1115
- SHT30 untuk temperatur/kelembapan
- pompa + valve
- Nextion NX4827T043_011
- Raspberry Pi 5 untuk integrasi dan inferensi lanjutan

## Komunikasi serial

### USB/komputer host

`Serial` menggunakan **115200 baud** untuk pencatatan, perintah, dan akuisisi data ke
PC/Raspberry Pi.

### Nextion

Nextion menggunakan **USART2 / `Serial2` pada 9600 baud**, sesuai konfigurasi
aktif file HMI.

| Jalur | Pin fisik IC ATmega2560 | Pin setara pada header Arduino Mega |
|---|---|---|
| Nextion TX → MCU RX | PH0 / RXD2, pin TQFP-100 **12** | RX2 / D17 |
| Nextion RX ← MCU TX | PH1 / TXD2, pin TQFP-100 **13** | TX2 / D16 |
| Ground | GND | GND |

Catatan: nomor pin IC TQFP-100 berbeda dari nomor pada header Arduino
Mega. Datasheet Microchip menempatkan PH0/PH1 pada pin IC **12/13**,
bukan 8/9; pemetaan PCB custom harus diperiksa terhadap skematik sebelum
mengubah sambungan fisik. Firmware memakai `Serial2`.

## Struktur repositori

```text
.
├── src/                 firmware ATmega2560 utama
├── include/             header/model untuk firmware
├── lib/                 library embedded lokal
├── test/                smoke/unit test firmware
├── platformio.ini       konfigurasi PlatformIO
├── nextion/             source HMI, TFT, asset, event, dokumentasi
├── scripts/             akuisisi, validasi, feature engineering, training
├── data/
│   ├── raw/             data sensor mentah
│   ├── processed/       feature dataset dan dataset ML
│   └── analysis/        hasil validasi kualitas data
├── models/              model AI dan metadata fitur
├── results/
│   ├── plots/           plot analisis/model
│   └── sensor-plots/    plot detail tiap sampel/sensor
├── docs/                dokumentasi proyek
└── archive/             kode/eksperimen lama yang tidak lagi canonical
```

Firmware utama hanya berada di `src/`. File lama dan eksperimen tidak
boleh dijadikan sumber implementasi produksi tanpa verifikasi.

## Kompilasi firmware

```powershell
pio run -e mega2560
```

Unggah ke board (hanya setelah ada persetujuan penggunaan perangkat):

```powershell
pio run -e mega2560 -t upload
```

Serial Monitor USB:

```powershell
pio device monitor -e mega2560
```

## Uji komunikasi Nextion

Konfigurasi pengujian `nextion_test` dipakai untuk mengisolasi komunikasi LCD dari
sensor/aktuator.

```powershell
pio run -e nextion_test
pio run -e nextion_test -t upload
pio device monitor -e nextion_test
```

Jika komunikasi benar, firmware pengujian akan mengubah halaman Nextion dan event
sentuhan akan muncul sebagai `[NEXTION RX] EVT:...` pada Serial Monitor.

Firmware utama juga mencetak event yang diterima sebagai:

```text
{"nextion_event":"EVT:DATA_START"}
```

## Akuisisi data

Data baru dari `scripts/3_collect_data.py` disimpan ke `data/raw/`.
Kontrak akuisisi aktif mulai B32 adalah:

- 5 siklus;
- 25 detik purging + 5 detik collecting per run;
- 10 kanal gas menggunakan adc_mq3, bukan adc_mq9;
- suhu dan kelembapan SHT30 ikut disimpan pada setiap baris.

Validasi raw B32 secara khusus:

    python scripts/validate_b32_acquisition.py

Validasi seluruh batch B32–B35, pengujian regresi dan inventaris kualitas
terbaru (semuanya aman dijalankan secara offline tanpa COM5):

    python scripts/test_acquisition_suite.py
    python scripts/test_feature_pipeline.py
    python scripts/audit_b32_dataset.py

Pembuatan skema fitur kandidat dari MQ3 (tidak melatih model AI):

    python scripts/extract_b32_features.py --output data/processed/b32_b35_features_candidate.csv

Perintah ekstraksi menolak penimpaan file keluaran yang sudah ada; gunakan nama file
keluaran baru untuk eksperimen/revisi selanjutnya. Setiap CSV menjadi satu
observasi agregat lima siklus, bukan lima sampel independen.

### Pipeline fitur Tahap 3 (kontrak terbaru)

Tahap 3 telah membuat **input snapshot SHA256** yang dibekukan dari Tahap 2.
Dari 87 kandidat B32–B35, **86 file lolos ekstraksi ketat** dan satu file
`L-CAW_B34.csv` ditahan karena indeks purging siklus 1 tidak lengkap.
Dua file B37 berisi udara bersih tetap dikecualikan dari training/evaluasi kopi.

    python scripts/test_stage3_feature_pipeline.py
    python scripts/stage3_feature_pipeline.py --output-dir data/processed/stage3_v2

Gunakan output versi baru agar `stage3_v1` tidak tertimpa. Kontrak lengkap:
`data/processed/STAGE3_FEATURE_CONTRACT.md`; QA/QC:
`docs/reports/2026-10-09_TAHAP3_PREPROCESSING_FEATURE_QA.md`.

Matriks kandidat menyediakan 62 fitur legacy dan 82 fitur eksploratori,
dengan tujuh kelompok untuk ablation selanjutnya. **Belum ada pelatihan
model, validasi akurasi atau izin deployment.** Kolom label, batch, filename,
dan hash hanya metadata; untuk model, hanya kolom `f_*` yang digunakan,
dengan normalisasi dan seleksi fitur di dalam training fold.

**Baca sebelum implementasi AI:** `docs/00_CURRENT_STATE.md`,
`docs/01_MASTER_E2E_ROADMAP.md`,
`docs/02_KONTRAK_SISTEM_DAN_KEPUTUSAN_TAHAP0.md`,
`docs/03_AI_MODEL_RESEARCH_AND_EVALUATION.md`,
`docs/04_NEXTION_ATMEGA_RASPI_ARCHITECTURE.md`, dan
`docs/06_INDEPENDENT_AUDIT_QA_QC.md`.

### Penguatan firmware dan akuisisi — Tahap 1

Firmware sekarang menerbitkan sampel sensor **sebelum** event perubahan fase atau `ACQ_COMPLETE`, sehingga sampel terakhir tidak tertinggal setelah penutupan file di listener. Saat idle/paused tidak ada frame sensor akuisisi. Mode `ai_test` tidak membawa metadata label jawaban, sedangkan `labeled_data` tetap kompatibel dengan penyimpanan CSV.

Untuk keselamatan, `#pin_scan;` dinonaktifkan, `#valve_on;`/`#valve_off;`/`#valve_test;` ditolak pada build default (`ENABLE_MANUAL_ACTUATOR_TESTS=0`), `#start;` mensyaratkan seluruh ADC siap, dan pemindaian I2C tidak dilakukan saat akuisisi aktif. Mengaktifkan pengujian valve manual pada build khusus memerlukan SOP yang disetujui; **jangan mengunggah firmware atau menyentuh COM5 hanya berdasarkan PASS offline**.

Regresi khusus: `python scripts/test_stage1_firmware_contract.py`. Laporan: `docs/reports/2026-10-09_TAHAP1_FIRMWARE_AKUISISI_QA.md`. Durasi 25+5 detik masih perlu validasi timing pada perangkat.

Raw data lama yang masih menggunakan MQ9 tidak dihapus. File tersebut
dipisahkan ke data/raw/legacy_mq9/ dan dikecualikan dari validasi B32.

Model historis B01–B05 (MQ9) bukan model yang siap diterapkan pada data B32–B35 (MQ3).
Penelitian fitur awal telah dimulai, tetapi belum ada model B32–B35 yang
tervalidasi untuk inferensi perangkat atau penerapan pada Raspberry Pi 5.

### Akuisisi langsung dari LCD Nextion

Laptop dapat menjadi penerima dan penyimpan data secara pasif melalui USB Serial COM5. Setelah
firmware terbaru terpasang, alurnya:

    pilih Tingkat Roasting / Origin / Batch di pTake
        -> tekan START di Nextion
        -> ATmega menjalankan 5 siklus
        -> COM5 mengirim data JSON mentah + metadata pilihan LCD
        -> scripts/lcd_acquisition_service.py menyimpan CSV ke data/raw/

Layanan penerima tidak mengirim perintah START ke ATmega. START tetap berasal dari LCD.
Layanan hanya menyimpan mode labeled_data; pengujian AI tidak dimasukkan ke
dataset.

Pasang layanan penerima yang berjalan otomatis saat Windows dinyalakan:

    powershell -ExecutionPolicy Bypass -File scripts/install_lcd_autosave.ps1

Cek status:

    powershell -ExecutionPolicy Bypass -File scripts/status_lcd_autosave.ps1

Hentikan dan lepaskan pengaktifan otomatis:

    powershell -ExecutionPolicy Bypass -File scripts/uninstall_lcd_autosave.ps1

Saat layanan penerima aktif, COM5 hanya dapat dimiliki satu proses. Hentikan
layanan tersebut sebelum mengunggah firmware melalui PlatformIO, menggunakan Serial Monitor, atau menjalankan 3_collect_data.py.

Data akuisisi aktif ditulis lebih dahulu ke data/raw/.incoming/. Setelah
ACQ_COMPLETE diterima dan validasi lolos, file diterbitkan sebagai CSV final. Akuisisi terputus
dipertahankan di data/raw/incomplete/ agar data tidak hilang diam-diam.

## Alur pengolahan data dan AI

- data akuisisi mentah: `data/raw/`
- dataset fitur dan pembelajaran mesin: `data/processed/`
- laporan validasi: `data/analysis/`
- model yang telah dilatih: `models/`
- hasil evaluasi dan grafik: `results/`

Jangan memasukkan cache Python, lingkungan virtual, atau hasil kompilasi PlatformIO ke commit.

## Kebijakan bahasa dokumentasi

Dokumentasi utama proyek ini **ditulis dalam Bahasa Indonesia**. Istilah
teknis yang merupakan nama protokol, nama variabel, perintah, nama file, atau
identitas perangkat tetap ditulis sesuai bentuk aslinya agar dapat digunakan
dan ditelusuri tanpa salah tafsir.

Dokumen dalam `docs/`, panduan antarmuka Nextion, serta README proyek
menggunakan Bahasa Indonesia. Arsip pustaka pihak ketiga dan laporan hasil
eksperimen historis dipertahankan sebagai bukti asli; jangan mengubah angka,
keluaran program, atau lisensi hanya untuk menerjemahkan dokumentasi.
