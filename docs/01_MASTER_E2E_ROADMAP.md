# PETA JALAN INDUK PENELITIAN DAN IMPLEMENTASI AI E2E SMART COFFEE E-NOSE

**Dokumen acuan utama versi 1.2 — audit Tahap 0 dan penguatan offline Tahap 1 tanggal 9 Oktober 2026.** Ruang lingkup: Smart Coffee E-Nose v2 / RoastSense dengan ATmega2560, Nextion, komputer host dan Raspberry Pi 5. Pengembangan dilakukan dengan menjaga kestabilan akuisisi yang telah berjalan. **Jangan otomatis mengerjakan semua tahap berikutnya.**

Dokumen bukti dasar: **00_CURRENT_STATE.md**, **02_KONTRAK_SISTEM_DAN_KEPUTUSAN_TAHAP0.md**, dan **06_INDEPENDENT_AUDIT_QA_QC.md**. Keputusan tentang model dan protokol lanjutan dijabarkan pada dokumen **03** dan **04**.

## A. Prinsip kerja dan batas keselamatan

1. Kode sumber, status Git, data mentah aktual, dan hasil pengujian yang dapat diulang lebih kuat daripada dokumentasi lama. Pisahkan fungsi yang sudah diuji dari yang masih direncanakan.
2. Pertahankan dataset historis MQ9, raw MQ3 B32+, seluruh HMI, dan aset Figma yang sudah dikunci. Tidak boleh menimpa raw, membuka COM5 yang sedang dipakai, mengganti EEPROM, flashing, atau melakukan akuisisi fisik tanpa persetujuan.
3. Bedakan **file akuisisi**, **siklus**, **batch**, **sesi/hari pengukuran**, **spesimen kopi fisik**, dan **label roast/origin**. Pembagian data training dan test harus menghindari kebocoran antar-unit yang berkorelasi.
4. Kesiapan dinilai lewat **tiga gerbang terpisah**: pengujian software offline, pengujian hardware nyata, dan validasi inferensi prospektif. Keberhasilan satu gerbang tidak berarti seluruh sistem siap.
5. Terapkan alur kerja: **inspeksi → reproduksi masalah → analisis akar masalah → perbaikan → pengujian regresi → QA independen → dokumentasi → keputusan go/no-go**.
6. Prioritas: **P0** untuk kebenaran sistem/data dan validitas metode; **P1** untuk evaluasi AI serta integrasi; **P2** untuk penyempurnaan tambahan. Simpan bukti berupa keluaran CLI, hash, metrik, dan commit.

## B. Ringkasan status dan dependensi

| Tahap | Status saat audit | Prioritas | Dependensi utama | Perangkat fisik diperlukan? |
|---|---|---|---|---|
| 0. Penutupan kondisi aktual dan metodologi | **AUDIT OFFLINE SELESAI; keputusan label/PCB diteruskan sebagai blocker tahap terkait** | P0 | Tidak ada | Tidak |
| 1. Mutu firmware, sensor, Nextion, dan akuisisi | **OFFLINE PASS + NORMAL FLOW OPERATOR PASS; NEGATIVE/QUANTITATIVE BENCH TERBUKA** | P0 | 0 | Ya, untuk verifikasi final |
| 2. Inventaris dan kualitas dataset | **AUDIT REPRODUKSIBEL SELESAI; PROVENANCE LABEL/SPESIMEN P0 TERHAMBAT** | P0 | 0–1 | Tidak untuk data lama; ya untuk sampel baru |
| 3. Preprocessing dan fitur yang dapat direproduksi | **PIPELINE OFFLINE PASS; FITUR KANDIDAT, METODOLOGI ML BELUM VALID** | P0 | 2 | Tidak |
| 4. Penelitian model baseline dan challenger | **BENCHMARK LOBO OFFLINE SELESAI; MODEL BELUM TERVALIDASI** | P1 | 3 | Tidak |
| 5. Generalisasi lintas batch, drift dan unknown | **DIAGNOSTIK OFFLINE PASS; UNKNOWN NO-GO, PROSPEKTIF TERBUKA** | P0 | 3–4 | Ya untuk pengujian prospektif |
| 6. Pemilihan model dan kontrak artefak | TERHAMBAT OLEH 5 | P1 | 5 | Ya untuk benchmark perangkat |
| 7. Persiapan integrasi Raspberry Pi–ATmega | SEBAGIAN (DESAIN) | P1 | 1, 6 | Ya untuk integrasi |
| 8. Simulasi E2E penuh secara offline | DIRENCANAKAN | P1 | 6–7 | Tidak |
| 9. Integrasi dan validasi hardware | MENUNGGU PERSETUJUAN | P1 | 8 | Ya |
| 10. Validasi prospektif dan promosi model final | TERHAMBAT | P0 (gerbang rilis) | 5, 9 | Ya |

Status **SEBAGIAN** berarti sebagian kode atau bukti telah tersedia, tetapi kriteria selesai belum terpenuhi. Status **TERHAMBAT** berarti pelaksanaan final belum boleh dilakukan. Tahap 0–3 dapat banyak diselesaikan offline; tahap 9–10 tidak dapat dinyatakan selesai hanya berdasarkan simulasi.

## Tahap 0 — Penutupan kondisi aktual dan metodologi

**Hasil audit 9 Oktober:** baseline firmware–Nextion–CSV–AI–host, sumber acuan tiap subsistem, koreksi datasheet untuk pin Nextion IC, status USB vs opsi UART, dan konflik label telah direkam di `02_KONTRAK_SISTEM_DAN_KEPUTUSAN_TAHAP0.md`. Komentar firmware lama tentang durasi fase diperbaiki; pengujian statis otomatis tersedia di `scripts/test_stage0_contract.py`. Koreksi teknis di dokumen **tidak mengubah wiring, baud, atau kendali aktuator**.

**Batas penutupan:** tahap audit dan dokumentasi offline selesai; masalah berkode T0-01 s.d. T0-07 masih terbuka dan ditugaskan kepada Tahap 1/2/3/7/9/10. Jangan menganggap status Tahap 0 sebagai persetujuan untuk perubahan hardware, kelayakan model, atau penutupan masalah lain.

- **Tujuan, status, prioritas:** menetapkan arsitektur, cakupan eksperimen, dan dokumen acuan proyek; **SEBAGIAN, P0**.
- **Dependensi dan desain:** inventaris branch, subsistem, protokol labeled_data/AI_TEST, versi skema, serta keputusan siapa yang mengendalikan sensor dan aktuator. Tidak memerlukan perangkat fisik.
- **Pekerjaan:** cocokkan riwayat Git relevan, dokumentasi, dan implementasi; periksa peta ADC, **lima siklus yang masing-masing terdiri atas dua fase**, 12 halaman Nextion, HMI final, urutan sensor, baud, serta ketidakcocokan istilah dan asal kopi. Definisikan kebutuhan ID sesi/spesimen yang lebih jelas tanpa menganggap field baru sudah aktif.
- **Modul relevan:** README.md, platformio.ini, src/, nextion/, scripts/, docs/00_CURRENT_STATE.md.
- **Pengujian dan skenario negatif:** git status --short --branch; kompilasi PlatformIO; verifikasi HMI; cari label yang tidak konsisten, versi TFT lama, baud berbeda, dan kemungkinan perubahan lokal tertimpa.
- **Keluaran dan bukti:** peta subsistem, dokumen kondisi aktual, kontrak dataset/protokol pada dokumen 02, laporan `docs/reports/`, pengujian statis yang dapat diulang, dan identitas commit.
- **Kriteria selesai / go-no-go:** setiap subsistem memiliki sumber acuan dan tingkat bukti yang jelas. Konflik yang belum terselesaikan wajib dicatat sebagai **TERHAMBAT pada tahap pelaksanaannya** dengan pemilik dan mitigasi, bukan diam-diam dinyatakan selesai.
- **Risiko:** dokumentasi historis dapat berbeda dari perangkat; gunakan bukti kode dan pengujian, bukan hanya narasi. Tahap dinyatakan SELESAI setelah seluruh konflik utama ditutup dan ditinjau.

## Tahap 1 — Penutupan mutu firmware, Nextion, dan akuisisi

**Pelaksanaan 9 Oktober 2026:** pengamanan kode firmware dan QA offline dilakukan. Perintah `#pin_scan;` kini mengembalikan `PIN_SCAN_DISABLED` tanpa menyentuh pin; `#valve_on/off/test;` dinonaktifkan pada build default dan hanya dapat diaktifkan lewat flag build untuk SOP bench. Perintah serial `#start;` menolak sensor/ADC yang belum siap, dan `#scan;` ditolak selama akuisisi. Event `ACQ_START` pada `ai_test` tidak lagi membawa label roast/origin/batch atau nama file. `adsCallback` sekarang mengirim sampel dengan fase/siklus aslinya **sebelum** `processAcquisitionState()` menerbitkan `PHASE_CHANGE`/`ACQ_COMPLETE`; sampel idle/paused tidak lagi mengalir sebagai payload sensor. Regresi sintetik dan pengujian kontrak baru ada pada `scripts/test_stage1_firmware_contract.py` serta `scripts/test_acquisition_integrity.py`.

**Gerbang QA:** kompilasi dan pengujian offline merupakan satu milestone, **bukan penutupan seluruh Tahap 1**. Timing fisik ADC–valve, jumlah sampel di perangkat, cara kerja pause/resume terhadap ruang aroma, GPIO dan driver aktuator, perbedaan USB serial, kalibrasi, EEPROM, Nextion Editor/TFT, serta pemulihan koneksi tetap **BELUM DIUJI**; membutuhkan SOP bench, jadwal, dan bukti terukur. Laporan: `docs/reports/2026-10-09_TAHAP1_FIRMWARE_AKUISISI_QA.md`.

**Preflight bench pasif 9 Oktober:** listener `pythonw.exe` (PID 16472) terhubung COM5@115200 dan menyelesaikan satu sesi `L-MING_B32_20261009_172056.csv`. CSV final memiliki **150 sampel**, 5× (25 purging + 5 collecting), sample_idx kontigu, timestamp MCU 996–1004 ms antar-sampel, serta validator PASS. Ini **bukti jalur host→CSV**, bukan verifikasi timing aktuator atau versi firmware yang terpasang. Lihat `docs/reports/2026-10-09_TAHAP1_BENCH_PASIF_PRECHECK.md` dan **draf** `docs/SOP_BENCH_TAHAP1.md`. COM5 tidak diambil alih. Kriteria lulus hardware Tahap 1 **belum terpenuhi**.

**Bench operator B37 (udara bersih), 9 Oktober:** dua run dilaporkan dimulai melalui Nextion dan tercatat di log COM5. `L-MING_B37.csv` = 150 frame, validator canonical PASS dan target 25/5×5 PASS. `M-MING_B37.csv` = 152 frame, validator canonical PASS namun target ketat **FAIL** (6 collecting pada siklus 1 dan 5). Kedua file adalah **BENCH_ONLY**, bukan data training/evaluasi kopi sesuai label UI. Detail dan SHA256: `docs/reports/2026-10-09_TAHAP1_BENCH_B37_UDARA_BERSIH.md`; manifest `data/analysis/bench_only_exclusions.csv`. **Timing valve/pompa dan perilaku fisik Nextion tetap belum diverifikasi independen**. Tidak ada flashing atau pengambilalihan COM5.

- **Tujuan, status, prioritas:** tidak ada sampel salah fase, baris CSV palsu, hilang atau tertimpa secara diam-diam; **SEBAGIAN, P0**. Sejumlah perbaikan validator dan listener sudah teruji offline.
- **Dependensi dan desain:** pembacaan sepuluh kanal ADC dengan SHT30 pada I2C; state machine dan keselamatan aktuator di ATmega; komunikasi Nextion 9600 dan USB 115200 baud.
- **Pekerjaan:** audit alamat/gain/saturasi ADS, pemanasan dan stabilisasi R0/RL, EEPROM, SHT30 gagal, sample_idx, millis rollover, pembacaan tepat batas fase, timer, pemulihan pause/resume, pompa/valve, serial reconnect, kontrol layar dan log; **amankan perintah diagnostik `#pin_scan;` yang saat ini dapat memanipulasi D19/RX1 dan D20/SDA**.
- **Modul relevan:** src/main.cpp, sensor.*, actuator.*, sht30.*, nextion_transport.*, scripts/acquisition_schema.py, manual collector, listener LCD dan validator.
- **Pengujian:** pio run -e mega2560 -e nextion_test; python scripts/test_acquisition_suite.py; pemeriksa kontrak HMI.
- **Skenario negatif:** event-only row, ADC rusak, sample_idx duplikat, file bertabrakan, USB terputus, Nextion reboot, cancel, sensor hilang dan fail-safe aktuator.
- **Keluaran dan bukti:** regression tests, jejak perubahan fase, sampel CSV, serta pengukuran aktual durasi pompa/valve menggunakan alat yang disetujui.
- **Kriteria selesai / go-no-go:** tidak ada metadata yang disimpan sebagai sensor, tidak ada overwrite, semua input dinilai ketat, fase 25+5 detik dibuktikan di perangkat. Tanpa uji fisik, klaim kebenaran timing tetap **NO-GO**. Periksa juga bahwa perubahan urutan callback tidak mengubah definisi sinyal atau akuisisi valid akibat latency serial.
- **Risiko:** perubahan state machine dapat mengubah semantik dataset lama. Lakukan simulasi lalu bench test terkontrol; jangan refactor timing tanpa bukti.

## Tahap 2 — Inventaris, provenance, dan evaluasi kualitas dataset

**Audit dataset 9 Oktober 2026:** skrip `scripts/stage2_dataset_audit.py` beserta tes negatif menghasilkan manifest SHA256, QC per file dan per fase, matriks `sample_id×batch`, proxy purging/carryover, pasangan baseline B32–B35, dan flag anomali untuk review. Snapshot: **89 file B32+** dengan **87 kandidat B32–B35 valid secara struktur** dan dua file B37 berstatus **excluded_bench_clean_air**. Ada **9 sel kombinasi kode–batch kosong, 4 sel dengan file berulang, 33 flag file–kanal untuk review**, serta metadata spesimen/hari/urutan sesi yang belum ada. Sumber: `docs/reports/2026-10-09_TAHAP2_PROVENANCE_KUALITAS_DATASET.md` dan `data/analysis/stage2/`.

**Keputusan:** mesin audit dan dokumentasi provenance selesai; **kelayakan ilmiah label serta independensi spesimen masih P0 TERHAMBAT**. Tidak ada relabel otomatis, raw tidak disentuh, dataset bench udara bersih tidak dimasukkan ke data kopi. Artefak fitur kandidat 86 observasi yang lama belum otomatis diperbarui ke 87; hanya lanjut Tahap 3 sebagai riset **kandidat**, bukan training/deployment yang diklaim valid.

- **Tujuan, status, prioritas:** menentukan unit sampel independen yang benar serta kelayakan dataset; **SEBAGIAN, P0**. Inventaris awal 86 file dan validator selesai, penilaian ilmiah masih berjalan.
- **Dependensi dan desain:** skema MQ3 aktif dari Tahap 1; MQ9 historis dipisahkan; inventaris raw yang ada dapat diproses offline.
- **Pekerjaan:** buat manifest hash tiap file; hitung distribusi roast, origin, batch, siklus, sensor hilang dan outlier. **Rekonsiliasi cakupan preset antar-kolektor dan arti TEM/MUK/CAW bersama operator** tanpa mengubah raw. Evaluasi drift, baseline recovery, carryover, urutan pengukuran, suhu/kelembapan, tanggal/sesi, massa dan persiapan kopi, serta spesimen yang diukur ulang. Tinjau grafik B32–B35 berdasarkan batas fase.
- **Modul relevan:** data/raw/, scripts/audit_b32_dataset.py, validate_acquisition.py, plot_sensor_pattern.py dan data/analysis/.
- **Pengujian dan kasus negatif:** python scripts/audit_b32_dataset.py; deteksi MQ9 pada data MQ3, baris parsial, timestamp tidak valid, duplikasi, label origin tidak konsisten, serta grafik yang menggabungkan run berbeda.
- **Keluaran dan bukti:** katalog dataset ber-hash, tabel kelengkapan kelas, daftar masalah provenance dan laporan drift/kualitas sinyal.
- **Kriteria selesai / go-no-go:** tiap file training memiliki skema, hash, batch, status kualitas, serta asumsi independensi yang eksplisit. File gagal validasi tidak boleh masuk model. Validitas CSV tidak sama dengan generalisasi sensor.
- **Risiko:** empat batch mungkin tetap berkorelasi antar-hari atau spesimen. Pengumpulan sampel baru harus menggunakan ID spesimen/sesi.

## Tahap 3 — Preprocessing dan ekstraksi fitur yang dapat diulang

**Implementasi 9 Oktober 2026:** ekstraksi deterministik dari manifest SHA256 Tahap 2 menggunakan fungsi bersama `extract_sensor_features` (tanpa label, sama untuk frame CSV dan frame sensor in-memory). Dari **87 file B32–B35**, **86** lolos aturan fitur ketat, **1** (`L-CAW_B34.csv`) ditahan karena `sample_idx=8` pada purging siklus 1 hilang, walaupun lolos validator canonical yang lebih permisif. Dua run B37 udara bersih tetap dikecualikan. Terdapat tujuh grup ablation 10/20/30/32/10/62/82 fitur, output `data/processed/stage3_v1/`, dan `feature_rejections.csv`. Tes hash/snapshot, parity CSV–frame sensor, byte-for-byte reproduksi, invalid/missing ADC/SHT30/phase dan konflik B37 **PASS**. Rujukan: `docs/reports/2026-10-09_TAHAP3_PREPROCESSING_FEATURE_QA.md` serta `data/processed/STAGE3_FEATURE_CONTRACT.md`.

**Keputusan:** bagian engineering Tahap 3 **selesai secara offline**. Fitur masih **kandidat**: tidak ada fitting/training dan 82 fitur untuk 86 akuisisi sangat rawan overfitting. Baseline lima titik purge terakhir perlu evaluasi fisik dan model hanya dapat dipilih setelah Tahap 4–5; provenance label dan identitas spesimen fisik Tahap 2 belum terkonfirmasi.

- **Tujuan, status, prioritas:** menghasilkan vektor masukan yang sama antara training dan inferensi; **SEBAGIAN (KANDIDAT), P0**. Artefak awal: 86 observasi, 62 fitur numerik.
- **Dependensi dan desain:** hanya data MQ3 yang lolos validator; **satu file = satu observasi**, lima siklus di dalamnya diagregasi. Operasi preprocessing yang memerlukan fitting hanya boleh memakai data training.
- **Pekerjaan:** evaluasi rerata sensor, respons relatif baseline, slope, SD, suhu/kelembapan, agregasi antar-siklus, kestabilan fitur, serta jumlah fitur optimal. Uji apakah memakai lima titik purging terakhir valid secara fisik.
- **Modul relevan:** `scripts/extract_b32_features.py`, `scripts/stage3_feature_pipeline.py`, `data/processed/stage3_v1/`; artefak `data/processed/b32_b35_features_candidate.csv` 86-file yang lama dipertahankan untuk audit historis, bukan sumber dataset baru.
- **Pengujian dan kasus negatif:** ekstraksi berulang menghasilkan nilai identik; file dengan ADC kosong, timestamp tidak berurutan, fase tertukar, data MQ9 atau output yang sudah ada harus ditolak. Gunakan path output baru untuk percobaan berbeda.
- **Keluaran dan bukti:** tabel fitur dengan provenance, skema fitur berurutan, log pengujian deterministik dan daftar fitur hanya dengan awalan f_.
- **Kriteria selesai / go-no-go:** nol fitur NaN/inf, urutan fitur konsisten, satu baris per file, tidak mengubah raw, fitur inference sesuai fitur training. Status tetap KANDIDAT sampai evaluasi ilmiah lulus.
- **Risiko:** 62 fitur untuk 86 observasi mudah overfitting. Bandingkan himpunan fitur lebih ringkas dengan regularisasi di dalam fold.

## Tahap 4 — Penelitian model baseline dan challenger

**9 Oktober 2026 — provenance direvisi berdasarkan operator:** seluruh
`CAW` dan batch `B37` merupakan **udara bersih**. Empat file CAW
B33–B35 dan dua file B37 dikecualikan melalui daftar nama/SHA256.
Dataset kopi baru `stage2_v2` = **83 file kandidat** (dari 87 B32–B35),
dan `stage3_v2` = **83 vektor fitur valid**; snapshot lama tetap arsip
dan tidak boleh digunakan untuk training. Tidak ada CSV mentah yang diubah.

**Benchmark offline dilakukan:** 7 grup fitur a priori × 8 baseline/challenger
× 4 fold Leave-One-Batch-Out = **224 fit/fold**. Kode
`scripts/stage4_model_benchmark.py`, hasil `results/stage4_lobo_v2/`,
QA `scripts/test_stage4_model_benchmark.py`, laporan
`docs/reports/2026-10-09_TAHAP4_MODEL_LOBO_CAW_CORRECTION.md`.
Peringkat deskriptif: RF expanded82 macro-F1 **0,490**, LDA response10
**0,482**. Performa RF antarbatch B32/B33/B34/B35 adalah
**0,655/0,577/0,344/0,383**; belum stabil. **Tidak ada model dipilih,
disimpan atau dipromosikan**; data uji final independen, label/spesimen
terverifikasi dan uji prospektif belum tersedia (Tahap 5).

- **Tujuan, status, prioritas:** membandingkan model sederhana dan kompleks dengan metode adil; **DIRENCANAKAN, P1**. Random Forest MQ9 lama bukan baseline baru.
- **Dependensi dan desain:** Tahap 3 selesai; pembagian data evaluasi dan target roast-only/known-origin ditetapkan sebelum tuning.
- **Pekerjaan:** uji DummyClassifier, Logistic Regression, shrinkage LDA, SVM linear/RBF, RF/ExtraTrees, PLS-DA, k-NN dan boosting opsional. Model temporal mendalam hanya bila tambahan dataset dan panjang sinyal membenarkannya.
- **Modul relevan:** skrip eksperimen baru yang terversi; simpan model kandidat terpisah dari models/random_forest_final.joblib historis.
- **Pengujian dan kasus negatif:** grouped CV, scaler dan feature selector hanya pada training fold, seed tetap, uji pengacakan label, serta pemeriksaan fold yang tidak memiliki kelas tertentu.
- **Keluaran dan bukti:** macro-F1, balanced accuracy, confusion matrix, metrik per batch, latensi, ukuran artefak dan konfigurasi eksperimen yang dapat diulang.
- **Kriteria selesai / go-no-go:** semua hasil melampirkan pembagian kelompok dan tanpa data leakage; model tidak dipilih berdasarkan data uji final. Tidak mempromosikan model hanya dari 86 file berkorelasi.
- **Risiko:** variasi kelas dan sampel sangat terbatas; gunakan regularisasi, hyperparameter sederhana, serta laporkan ketidakpastian.

## Tahap 5 — Evaluasi lintas batch, drift, dan penolakan unknown

**Implementasi 9 Oktober 2026:** `scripts/stage5_validation.py`
mengevaluasi dua pembanding Tahap 4 pada 83 observasi kopi kandidat
melalui 4 fold LOBO, dengan probabilitas OOF, metrik per kelas,
kurva risk–coverage threshold a priori, bootstrap empat batch,
simulasi gain ADC dan uji lima data udara bersih valid.
Artefak `results/stage5_validation_v1/`, regresi
`scripts/test_stage5_validation.py`, laporan lengkap
`docs/reports/2026-10-09_TAHAP5_GENERALISASI_UNKNOWN_QA.md`.

**Temuan P0:** baik RF expanded82 maupun LDA response10
**memprediksi light roast pada 5/5 udara bersih**, dan **tidak
menolak satu pun** pada ambang confidence 0,6.
Keduanya salah pada **38/83** observasi OOF kopi kandidat.
Pada ambang 0,8 RF menerima 9 observasi (3 salah), LDA
menerima 20 (6 salah). Confidence **belum dikalibrasi**; threshold
eksploratori tidak boleh dijadikan keputusan produksi.
Identitas spesimen dan batch prospektif, unknown origin kopi, serta
detektor kopi-vs-udara-bersih **belum diuji**. **Tahap 5
engineering diagnostik PASS; gerbang ilmiah/release NO-GO**.
Tahap 6 dan deployment tetap tertahan.

- **Tujuan, status, prioritas:** membuktikan generalisasi pada pengambilan data baru; **DIRENCANAKAN, P0 sebagai syarat rilis AI**.
- **Dependensi dan desain:** Tahap 2–4, target serta ambang dipastikan sebelum evaluasi; validasi Leave-One-Batch-Out (LOBO) awal dan pengujian spesimen/hari baru secara prospektif.
- **Pekerjaan:** evaluasi empat fold lintas batch B32–B35, ketersediaan kelas pada tiap fold, pemisahan berdasarkan ID spesimen/sesi baru, kalibrasi confidence, unknown origin, efek drift/suhu/kelembapan, serta kelayakan keputusan sebelum lima siklus berakhir.
- **Modul relevan:** manifest evaluasi tetap, laporan results/, artefak sklearn Pipeline per fold, dan dokumentasi 03.
- **Pengujian dan kasus negatif:** tidak boleh ada group overlap; uji kelas yang tak tersedia, origin asing, ADC rusak, pergeseran baseline, outlier, dan threshold confidence yang terlalu optimistis.
- **Keluaran dan bukti:** confusion matrix per batch, metrik per kelas, kurva risiko/cakupan abstain, interval ketidakpastian, serta dataset prospektif terpisah.
- **Kriteria selesai / go-no-go:** kebocoran antar-fold nihil, kesalahan confident terkendali, batas mutu ditetapkan sebelum pengujian prospektif. Jika kelas tidak ada pada fold, nyatakan keterbatasannya, bukan menyamarkan dengan rerata.
- **Risiko:** empat batch dan ketimpangan kombinasi kelas dapat menghasilkan metrik tidak stabil. Penutupan tahap membutuhkan data tambahan yang independen.

## Tahap 6 — Pemilihan model dan kontrak artefak inferensi

- **Tujuan, status, prioritas:** memilih pipeline yang telah dibekukan dan kompatibel dengan perangkat; **TERHAMBAT oleh Tahap 5, P1**.
- **Dependensi dan desain:** model hanya dipromosikan setelah generalisasi, kalibrasi, dan validasi prospektif; seluruh model memiliki identitas/hash dan model card.
- **Pekerjaan:** pilih model roast dan kebijakan origin, threshold unknown, urutan label, nama/urutan fitur, aturan nilai hilang, versi sensor/firmware, batas RAM dan latensi.
- **Modul relevan:** registry models/ yang direncanakan, sklearn Pipeline, skema fitur JSON, dokumentasi 03 dan tes inferensi.
- **Pengujian negatif:** skema fitur berbeda, jumlah/urutan fitur salah, model tidak ditemukan, artefak rusak, origin asing, library tidak kompatibel dan timeout → hasil N/A atau error.
- **Keluaran dan bukti:** model card, hash artefak, versi dependency, provenance data latih/uji, uji kompatibilitas, dan benchmark perangkat.
- **Kriteria selesai / go-no-go:** seluruh ambang penerimaan yang telah ditetapkan terpenuhi; fitur train–serve identik; confidence memiliki dasar kalibrasi; jika belum, model tidak dipromosikan.
- **Risiko:** header model_rf.h historis bisa tidak sesuai MQ3/62 fitur. Jangan otomatis mengaktifkan TinyML ATmega.

## Tahap 7 — Persiapan integrasi Raspberry Pi 5 dan ATmega

- **Tujuan, status, prioritas:** menyediakan kontrak komunikasi dua arah yang dapat diandalkan; **SEBAGIAN (DESAIN), P1**.
- **Dependensi dan desain:** Tahap 1 dan 6. ATmega tetap mengendalikan aktuator/timing; host hanya bertanggung jawab atas validasi, penyimpanan, dan AI.
- **Pekerjaan:** verifikasi skematik dan pilih **USB `Serial` atau UART terpisah `Serial1`** untuk Pi; untuk UART GPIO wajib translator level 5 V↔3,3 V, pemeriksaan pin dan mitigasi `#pin_scan;`. Rancang NDJSON terversi dengan session_id/message_seq, ACK/NACK, timeout, pesan duplikat, reconnect, result mapping, unknown/N/A, dan **pemisahan label AMBIL DATA dari AI_TEST**.
- **Modul relevan:** adapter host yang akan dibuat, src/main.cpp hanya setelah persetujuan, nextion_transport.*, dokumen 04.
- **Pengujian negatif:** USB terputus, paket rusak/terlambat/duplikat, restart MCU/Nextion/Pi, file berbahaya, hasil model tanpa sumber, dan dua proses berebut COM5.
- **Keluaran dan bukti:** diagram antarmuka, spesifikasi payload, fixture protokol, rencana deployment Pi, skenario error dan rollback.
- **Kriteria selesai / go-no-go:** setiap sesi menghasilkan paling banyak satu hasil final yang konsisten; semua kegagalan berujung status aman dan informatif; tidak ada perubahan kontrol aktuator oleh host.
- **Risiko:** pembaruan protokol dapat mengganggu listener produksi. Siapkan kompatibilitas dua versi, uji mock dahulu, dan pengujian fisik hanya dengan izin.

## Tahap 8 — Simulasi E2E lengkap tanpa hardware

- **Tujuan, status, prioritas:** membuktikan alur tombol hingga hasil secara software; **DIRENCANAKAN, P1**.
- **Dependensi dan desain:** Tahap 6–7; mock event Nextion, trace ATmega, validator, ekstraktor fitur, model, dan hasil/galat.
- **Pekerjaan:** replay data B32+ berlabel melalui simulasi autosave; jalankan AI_TEST melalui validator → model → keputusan → mock pResult. Pastikan ground truth tidak bocor ke prediksi.
- **Modul relevan:** fixture baru, pengujian CLI, skema fitur/model, rancangan komunikasi versi 1.
- **Pengujian negatif:** event duplikat, stop/pause, akuisisi tidak lengkap, model hilang, prediksi rendah confidence, session_id lama, koneksi terputus.
- **Keluaran dan bukti:** laporan tes E2E offline, trace JSON deterministik, hasil prediksi yang dapat ditelusuri dan tanpa modifikasi input.
- **Kriteria selesai / go-no-go:** seluruh kasus positif dan negatif lolos pada lingkungan bersih, dengan log dan hash yang dapat diperiksa. Tetap **belum** berarti E2E perangkat fisik.
- **Risiko:** mock tidak dapat membuktikan wiring, saturasi ADC, kualitas aroma atau timing nyata.

## Tahap 9 — Integrasi dan validasi perangkat fisik

- **Tujuan, status, prioritas:** membuktikan komunikasi serta fungsi nyata ATmega–Nextion–Pi; **MENUNGGU PERSETUJUAN, P1**.
- **Dependensi dan desain:** Tahap 8 lulus; jadwal bench test aman, COM5 eksklusif, backup firmware/HMI dan prosedur pemulihan disiapkan.
- **Pekerjaan:** ukur kanal/alamat ADS, SHT30, tegangan, pemanasan, alur pompa/valve; verifikasi skematik Nextion pada PH0/PH1 (**pin TQFP-100 12/13**, bukan 8/9), TFT hasil kompilasi terbaru, navigasi 12 halaman, hasil Pi → Nextion serta latensi nyata.
- **Modul relevan:** build firmware dengan hash, proyek dan TFT Nextion, log host, foto/video atau trace pengukuran, SOP bench.
- **Pengujian negatif:** sensor atau USB dicabut, akuisisi parsial, restart MCU/LCD/Pi, pause/resume, kegagalan aktuator, kalibrasi tidak selesai, dan kopi tidak dikenal.
- **Keluaran dan bukti:** rekaman timing aktuator, keandalan serial, hasil pengukuran, daftar perbaikan, dan prosedur rollback.
- **Kriteria selesai / go-no-go:** tidak ada gerakan aktuator tidak aman, status N/A benar pada kegagalan, semua jalur komunikasi diuji pada perangkat nyata dan diverifikasi independen.
- **Risiko:** uji fisik dapat mengubah kalibrasi atau mencemari ruang aroma. Pisahkan sampel uji, ikuti SOP dan jangan flashing tanpa persetujuan.

## Tahap 10 — Validasi prospektif dan promosi model final

- **Tujuan, status, prioritas:** membuktikan prediksi pada kopi baru dan merilis model secara bertanggung jawab; **TERHAMBAT, P0 sebagai gerbang rilis**.
- **Dependensi dan desain:** Tahap 5, 6, 9 telah diselesaikan; protokol dan ambang penerimaan dibekukan sebelum menguji data prospektif.
- **Pekerjaan:** akuisisi buta pada spesimen fisik baru lintas roast/origin/hari, SOP pemanasan/purging/collecting yang seragam, uji repeatability, drift, suhu/kelembapan, unknown, error rate, durasi inferensi, serta keandalan selama penggunaan.
- **Modul relevan:** manifest prospektif terkunci, results/, model card final, deployment Pi yang diuji dan prosedur rollback.
- **Pengujian negatif:** origin baru, sensor terlepas, kelembapan ekstrem, kalibrasi bergeser, jumlah siklus tidak cocok, model rusak, USB hilang saat inferensi.
- **Keluaran dan bukti:** confusion matrix prospektif, macro-F1/per-class F1, risk–coverage, log kegagalan, bukti perangkat fisik dan persetujuan hasil.
- **Kriteria selesai / go-no-go:** memenuhi batas mutu yang disepakati sebelum penelitian, mampu mengeluarkan unknown/error secara aman, lolos pengujian perangkat nyata. Jika gagal, kembali ke pengumpulan data atau revisi desain.
- **Risiko:** empat batch historis tidak cukup sebagai bukti akurasi di lapangan. Hanya data uji baru dan pengukuran nyata yang dapat menutup tahap ini.

## C. Urutan pekerjaan praktis dan batas persetujuan

1. **P0, bisa dilakukan offline:** finalisasi regresi akuisisi, dokumentasikan risiko batas fase, pertahankan dataset/model historis, lengkapi inventaris B32–B35, uji konsistensi fitur satu-observasi-per-file, serta simpan bukti Git dan hasil tes.
2. **P0, eksperimen data berikutnya:** tambahkan **ID spesimen fisik**, ID sesi unik, waktu kalender, versi hardware/firmware, lama pemanasan, massa kopi, preparasi dan definisi kelas origin pada metadata pengukuran baru.
3. **P1, penelitian AI offline:** bangun baseline sederhana yang reproducible, gunakan grouped cross-validation, analisis metrik per batch/roast/origin, dan kaji mekanisme unknown.
4. **P1, persiapan integrasi:** lengkapi rancangan serial dan adapter Pi, lakukan simulasi alur Nextion → ATmega → Pi → hasil termasuk putus koneksi.
5. **Wajib persetujuan terpisah:** akses COM5 langsung, flashing firmware, kompilasi/upload TFT untuk alat, aktivasi pompa/valve, kalibrasi/EEPROM, serta deployment Pi live.

## D. Definisi kesiapan proyek saat ini

**Sudah ada bukti:** kompilasi firmware offline, kontrak HMI offline, validator akuisisi yang diperketat, serta kandidat skema fitur.

**Belum dapat dinyatakan selesai:** validasi model B32–B35 lintas batch dan prospektif, inferensi Raspberry Pi dua arah, serta pengujian seluruh perangkat fisik. Audit roadmap ini setiap ada batch baru, kandidat model, atau bukti bench test. **Grafik yang terlihat bagus dan akurasi training tinggi tidak otomatis membuktikan sistem siap digunakan.**
