# Catatan perubahan proyek

Dokumen ini mencatat milestone engineering yang relevan; detail teknis dan risiko tetap berada dalam laporan milestone terkait. Untuk riwayat perubahan terperinci, gunakan `git log` pada branch `wahyu`.

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
