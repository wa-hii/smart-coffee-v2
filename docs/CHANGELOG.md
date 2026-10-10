# Catatan perubahan proyek

Dokumen ini mencatat milestone engineering yang relevan; detail teknis dan risiko tetap berada dalam laporan milestone terkait. Untuk riwayat perubahan terperinci, gunakan `git log` pada branch `wahyu`.

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
