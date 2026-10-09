# Audit Independen dan QA/QC — Smart Coffee E-Nose v2

**Tanggal:** 8 Oktober 2026. **Branch:** wahyu. **HEAD awal:** 54d3321.

**Ruang lingkup:** pemeriksaan statis firmware dan arsitektur, kontrak HMI Nextion, listener CSV, kualitas dataset B32–B35, artefak AI historis, serta rancangan integrasi Raspberry Pi 5. Tidak dilakukan akses COM5, perubahan EEPROM, pengambilan data fisik, flashing, maupun training model baru.

## 1. Ringkasan eksekutif

Dataset akuisisi yang tersedia **lolos validasi struktur dan dapat digunakan sebagai kandidat penelitian**, tetapi belum ada model AI yang teruji generalisasinya secara independen. Pipeline fitur MQ9/collecting panjang sebelumnya tidak cocok dengan kontrak baru MQ3/collecting 5 detik. Keberhasilan kompilasi firmware bukan bukti bahwa integrasi Raspberry Pi dan seluruh perangkat telah berjalan.

## 2. Temuan berdasarkan bukti

| Prioritas | Temuan | Bukti | Tindakan/status |
|---|---|---|---|
| **P0** | Event PHASE_CHANGE dahulu ditulis sebagai baris CSV sensor | Terdapat 612 baris metadata-only pada B33–B35; bugfix sebelumnya 54d3321 | Regresi kontrak diperiksa ulang; event dikecualikan saat pembacaan tanpa mengubah raw |
| **P0** | Payload ADC non-null sebelumnya menerima string atau bilangan di luar rentang | Validator lama hanya mengecek nilai bukan None | Ditambah validasi tipe integer/rentang dan pengujian kasus salah |
| **P0** | Indeks sensor duplikat belum ditangani | Validator lama tidak memeriksa run_id/phase/sample_idx yang sama | Ditambahkan aturan duplikasi dan pengujian CSV sintetis |
| **P0** | Nama file autosave bisa berbenturan dan berisiko tertimpa | Sufiks detik dan os.replace pada implementasi lama | Penomoran nama unik, file staging UUID dan publikasi yang menolak penimpaan |
| **P0** | Ekstraktor MQ9 mensyaratkan minimal 10 titik collecting | scripts/8_extract_features.py | Ditambah penolakan pencampuran; ekstraktor kandidat MQ3 dibuat terpisah |
| **P0** | Hasil ML historis tidak mewakili data B32+ | Random Forest B01–B05: 57,50% dan 55,00%; CV memakai run yang berkorelasi | Promosi model ditahan; evaluasi berbasis kelompok dirancang |
| **P1** | Risiko sampel salah diberi label fase pada batas transisi | ADC dibaca sebelum perubahan state, JSON dikirim sesudahnya | Dicatat untuk pengujian timing; **belum diubah** |
| **P1** | Origin dan confidence belum memiliki sumber hasil valid | TinyML dinonaktifkan secara bawaan; halaman hasil memakai N/A | Integrasi inferensi hybrid dirancang, **belum diterapkan** |
| **P1** | Tidak ada ID sesi/spesimen fisik eksplisit | sample_id/batch_id tidak membuktikan independensi; millis() adalah uptime | Direncanakan identitas UID, timestamp host dan metadata spesimen |
| **P2** | Pemeriksa HMI menggunakan metode Pillow yang akan dihentikan | Muncul peringatan deprecated pada fungsi getdata() | Kandidat pemeliharaan tooling, tidak menghalangi QA sekarang |

## 3. Hasil audit dataset aktual

| Parameter | Hasil |
|---|---:|
| Jumlah file B32 / B33 / B34 / B35 | 18 / 20 / 22 / 26 |
| Jumlah file keseluruhan | **86** |
| Baris sensor lengkap | **13.003** |
| Baris event metadata-only | **612** |
| Baris sensor parsial | **0** |
| Baris sensor purging / collecting | 10.756 / 2.247 |
| Nilai suhu / kelembapan yang hilang | 0 / 0 |
| Nilai ADC 0 / saturasi 32767 yang ditemukan | 0 / 0 |
| Jumlah file light / medium / dark | 30 / 28 / 28 |
| Kombinasi kode roast × origin teramati | 23 |
| CSV lolos validator | **86/86** |
| Jumlah fitur kandidat tiap file | **62** |

Hasil di atas **hanya menunjukkan kesesuaian dengan validator struktur**, bukan bukti bahwa label roast/origin benar, sensor terkalibrasi, data bebas drift, atau terdapat 86 spesimen kopi fisik independen.

## 4. Perintah pengujian offline yang dapat diulang

Jalankan dari root repositori:

    pio run -e mega2560 -e nextion_test
    python nextion/NX4827T043_011/tools/verify_nextion_atmega_contract.py
    python scripts/test_acquisition_suite.py
    python scripts/test_feature_pipeline.py
    python scripts/audit_b32_dataset.py
    python scripts/validate_b32_acquisition.py

Untuk menghasilkan **artefak fitur kandidat** secara terpisah (tanpa training):

    python scripts/extract_b32_features.py --output data/processed/b32_b35_features_candidate.csv

Skrip fitur sengaja menolak penimpaan file output yang sudah ada. Untuk eksperimen baru, gunakan nama output berbeda.

## 5. Hasil QA yang dapat dibuktikan

- **Kompilasi PlatformIO PASS:** mega2560 dan nextion_test. Sebelum perubahan Python ini, firmware utama menggunakan RAM statis 3.720/8.192 byte (45,4%) dan flash 35.854/253.952 byte (14,1%); firmware uji menggunakan RAM 541/8.192 byte dan flash 5.062/253.952 byte.
- **Kontrak HMI offline PASS:** 12 aset Figma terkunci, 12 halaman HMI, 23 event terwakili pada handler, Serial2 @ 9600 baud dan tipe komponen utama pDataRun.
- **QA data PASS:** regresi payload, validator CSV sintetis, pengujian benturan nama file dan validasi 86/86 berkas B32–B35. Ekstraksi kandidat 62 fitur juga lolos pengujian deterministik.
- **Batas penting:** tidak ada pembuktian kompilasi dan upload TFT melalui Nextion Editor, pengukuran UART nyata, validasi fisik sensor, akurasi model B32–B35, maupun latensi Pi.

## 6. Risiko tersisa dan langkah verifikasi independen

1. **Pengujian fisik:** verifikasi batas fase, alamat/kanal ADS, SHT30, urutan sensor, PWM, pompa/valve, pemanasan, kalibrasi, serta HMI/TFT nyata.
2. **Pengujian model:** benchmark B32–B35 lintas batch, kualitas klasifikasi origin, kalibrasi probabilitas, deteksi unknown, dan inferensi Raspberry Pi 5 belum tersedia.
3. **Validasi prospektif:** diperlukan spesimen/sesi baru yang benar-benar independen serta data uji yang dikunci sebelumnya; empat batch lama hanya tahap eksplorasi.
4. **Keseragaman label:** pastikan kode TEM/MUK tidak mencampurkan origin, metode proses, varietas, vendor atau kondisi roasting yang berbeda.
5. **Tindakan yang memerlukan persetujuan:** membuka COM5, flashing ATmega, upload TFT, kalibrasi/EEPROM, pengoperasian pompa/valve, dan deployment Pi secara langsung.

## 7. Keputusan QA akhir

| Gerbang verifikasi | Status |
|---|---|
| Kompilasi firmware, kontrak HMI, dan integritas CSV secara offline | **PASS dalam batas pengujian yang disebutkan** |
| Generalisasi ilmiah model AI | **BELUM DINILAI / TERHAMBAT** |
| Integrasi fisik Raspberry Pi–ATmega–Nextion secara menyeluruh | **BELUM DIUJI / TERHAMBAT** |

Dokumen tindak lanjut utama adalah **01_MASTER_E2E_ROADMAP.md**. Jangan menyatakan perangkat telah siap penuh sebelum gerbang pengujian AI dan perangkat fisik benar-benar ditutup dengan bukti.

## Lampiran — verifikasi ulang Tahap 0 (9 Oktober 2026)

Hasil QA offline terbaru tercatat pada `docs/reports/2026-10-09_TAHAP0_AUDIT_KONTRAK_DAN_QA.md`. Ringkasan:

- **PASS:** build `mega2560` dan `nextion_test`; validasi HMI offline 12 halaman/23 event; validator 86/86 CSV B32–B35 serta 18/18 B32; regresi akuisisi, fitur, dan kontrak statis baru; `compileall` serta `git diff --check`.
- **Koreksi yang dibuktikan datasheet:** pin TQFP-100 `PH0/RXD2=12`, `PH1/TXD2=13`, bukan 8/9. Implementasi UART Nextion tidak berubah; pin PCB nyata belum diuji.
- **Temuan baru yang masih terbuka:** `#pin_scan;` mencakup D19/RX1 dan D20/SDA; `AI_TEST` masih mengeluarkan label pilihan antarmuka pada event `ACQ_START`; tiga preset kolektor manual (`L-CAW`, `M-CAW`, `M-MUK`) tidak memiliki entri khusus di pemetaan per-sampel listener LCD. Ini bukan regresi akibat audit, tetapi temuan existing yang perlu ditangani berdasarkan tahap dan SOP.

**Keputusan:** audit statis dan dokumentasi kontrak Tahap 0 selesai; tindak lanjut implementasi/hardware tetap **terbuka atau terhambat** sesuai daftar T0-01 sampai T0-07 dalam dokumen 02.

## Lampiran — milestone Tahap 1 (9 Oktober 2026)

Perbaikan offline: penonaktifan `#pin_scan`, pengamanan perintah valve manual di balik flag default OFF, penolakan `#start` tanpa ADC siap, pemisahan metadata `AI_TEST`, dan perubahan urutan sampel sebelum `PHASE_CHANGE`/`ACQ_COMPLETE`. Regresi autosave juga menambahkan kasus AI_TEST tanpa label, COMPLETE ganda dan STOP parsial.

Tes baru `python scripts/test_stage1_firmware_contract.py` memverifikasi struktur kode serta simulasi waktu ideal 1 Hz; **tidak mengukur timing fisik**. Bukti lengkap, status QA, dan daftar risiko tersisa: `docs/reports/2026-10-09_TAHAP1_FIRMWARE_AKUISISI_QA.md`.

Status Tahap 1 tetap **SEBAGIAN** sampai wiring, valve, sensor, UART, Nextion TFT dan ketepatan fase telah diverifikasi pada bench dengan SOP. Hasil QA offline tidak berarti sistem fisik siap beroperasi.

## Addendum Tahap 2 — provenance dan audit dataset (9 Oktober 2026)

Operator mengonfirmasi pompa/valve berpindah mengikuti fase nominal 25/5 detik dan layar Nextion sampai halaman selesai tanpa error. Ini merupakan **observasi operator**, bukan pengukuran dengan instrumen. Penyimpangan dua collecting pada `M-MING_B37.csv` dan uji negatif/fail-safe tetap menjadi temuan terbuka Tahap 1.

Inventaris baru: **89 CSV B32+** (87 kandidat B32–B35, dua B37 udara bersih) dan pengecualian bench ber-SHA256. Dua pengujian B37 valid menurut validator canonical, tetapi **tidak mewakili kopi sesuai label UI** dan tidak boleh masuk training/evaluasi kopi.

Audit `scripts/stage2_dataset_audit.py` menghasilkan manifest SHA256, 23 kode sampel, distribusi 31 light/28 medium/28 dark, **9 sel kode–batch kosong**, **4 sel dengan file berulang**, 180 pasangan baseline B32/B35 (18 kode × 10 kanal), dan **33 flag file–kanal** sebagai antrian review. Nilai perubahan baseline hanya proxy eksploratori; identitas spesimen, waktu pengukuran dan label TEM/MUK/CAW belum terverifikasi.

Tes negatif `scripts/test_stage2_dataset_audit.py` dan `scripts/test_stage2_plot_provenance.py` harus **PASS** sebelum promosi perbaikan. Generator grafik sekarang mengecualikan data bench udara bersih yang tercatat manifest dan menahan batch B36+ tanpa audit. **Status akhir:** ketersediaan alat audit dan struktur data PASS; metodologi label independen untuk training/validasi model **P0 TERHAMBAT**. Laporan detail `docs/reports/2026-10-09_TAHAP2_PROVENANCE_KUALITAS_DATASET.md`.

## Addendum Tahap 3 — QA pipeline fitur (9 Oktober 2026)

**Addendum Tahap 5 (9 Oktober):** audit pengujian unknown dan
ketahanan disimpan di
`docs/reports/2026-10-09_TAHAP5_GENERALISASI_UNKNOWN_QA.md`.
Pada 83 file kandidat kopi, RF82/LDA10 menghasilkan masing-masing
45 benar dan 38 salah pada OOF; pada 5 file udara bersih valid
**semuanya tetap diprediksi sebagai light roast**, termasuk
tanpa ada yang ditolak pada threshold 0,6. Threshold
confidence tidak terkalibrasi, simulasi gain bukan drift fisik,
dan 4 batch bukan set prospektif. **NO-GO unknown/deployment**.
Tes baru `python scripts/test_stage5_validation.py`.

**Addendum lebih baru (9 Oktober): CAW dan B37 merupakan udara bersih.**
Snapshot `stage2/`, `stage3_v1/` serta statistik di bagian-bagian
sebelumnya dipertahankan sebagai bukti historis. Untuk benchmark kopi
gunakan `stage2_v2/` + `stage3_v2/` dengan 83 kandidat dan enam file
udara bersih dikecualikan. Benchmark LOBO Tahap 4 (7 grup × 8 model ×
4 fold) **dijalankan offline**, tetapi hasilnya belum validasi prospektif.
QA dan hasil pada `docs/reports/2026-10-09_TAHAP4_MODEL_LOBO_CAW_CORRECTION.md`.

- `scripts/stage3_feature_pipeline.py` menggunakan manifest SHA256 Tahap 2, verifikasi checksum setiap CSV, dan fungsi `extract_sensor_features` bersama untuk data CSV maupun in-memory (calon host Pi). Tidak menerima label sebagai masukan formula sensor, dan tidak melakukan fit/seleksi fitur global.
- Dari 87 kandidat B32–B35, **86 menerima vektor fitur**, satu (`L-CAW_B34.csv`) **HOLD_FOR_QA** karena `sample_idx=8` hilang pada fase purging siklus 1. Sebelumnya file tersebut lolos validator umum; kebutuhan QA fitur lebih ketat kini terdokumentasi. File asli tidak diubah.
- Snapshot `data/processed/stage3_v1/` berisi 62 fitur legacy dan 82 fitur expanded, tujuh kelompok fitur ditentukan a priori, feature quality deskriptif, hash manifest/sumber, serta daftar hold. Dua file B37 udara bersih tidak ikut.
- `scripts/test_stage3_feature_pipeline.py` menguji hash/input drift, metadata bench salah label, output overwrite, raw write protection, fitur nonfinite, hilang ADC/SHT30, mismatch fase dan parity in-memory. Existing test 62 fitur tetap PASS.

**Status:** engineering Tahap 3 **PASS offline untuk 86 file terpilih**; fitting model, pemilihan jumlah fitur optimal dan generalisasi **BELUM DIUJI**. Ketidakjelasan identitas spesimen/label kopi, baseline fisik dan file yang ditahan adalah blocker penerimaan ilmiah. Laporan `docs/reports/2026-10-09_TAHAP3_PREPROCESSING_FEATURE_QA.md`.
