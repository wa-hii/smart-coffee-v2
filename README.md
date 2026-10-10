# Smart Coffee E-Nose v2

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
