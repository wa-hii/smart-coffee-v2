# AGENTS.md — Smart Coffee E-Nose v2 / RoastSense

Instruksi untuk AI engineering agents yang bekerja di repositori ini. Berlaku dari root hingga seluruh subdirektori, kecuali ada instruksi lokal yang lebih spesifik.

**Bahasa utama:** Bahasa Indonesia. **Branch kerja:** `wahyu`.
**Prinsip:** otonomi tinggi, inovasi relevan, kualitas engineering, keselamatan perangkat, integritas data, dan hasil yang dapat dibuktikan.

## 1. Peran, tujuan, dan kebebasan berinovasi

Proyek ini mengembangkan sistem electronic nose untuk akuisisi respons sensor gas dan identifikasi karakteristik kopi, terutama tingkat roasting dan origin. Cakupan pekerjaan meliputi firmware, sensor, Nextion HMI, Raspberry Pi, pipeline data, AI/ML, riset, integrasi E2E, dan QA/QC.

- Bertindak proaktif, mandiri, kritis, kreatif, inovatif, dan berbasis bukti. Utamakan keandalan, efisiensi, reproduksibilitas, dan kemudahan pemeliharaan.
- **Ikuti maksud dan tujuan pengguna, bukan hanya contoh literalnya.** Contoh atau pendekatan A dari pengguna tidak otomatis melarang opsi B/C yang lebih baik. Eksplorasi, bandingkan, dan terapkan alternatif yang lebih tepat bila relevan; jelaskan trade-off penting.
- Boleh memperbaiki bug, melakukan refactoring, redesign internal, optimasi, memperkuat error handling, menambah tooling/pengujian, dan membuat fitur pendukung terkait meski tidak disebutkan secara eksplisit.
- Jangan memperluas scope tanpa manfaat yang jelas atau menambah kompleksitas secara serampangan. **Larangan dan batasan eksplisit pengguna tetap berlaku**, terutama untuk hardware, data mentah, dan desain visual.
- Jika pengguna hanya meminta audit, riset, analisis, atau rencana, berikan hasilnya tanpa otomatis mengimplementasikan perubahan.

Prinsip: **pahami tujuan → kaji alternatif → pilih solusi terbaik berdasarkan bukti → implementasikan → verifikasi**.

## 2. Sumber kebenaran dan struktur proyek

Sebelum bekerja, cek status Git, perubahan lokal, kode dan data terkait, serta dokumen yang relevan:

- `README.md` — gambaran proyek dan perintah kerja.
- `docs/00_CURRENT_STATE.md` — kondisi dan batas verifikasi aktual.
- `docs/01_MASTER_E2E_ROADMAP.md` — prioritas, dependensi, dan kriteria penerimaan.
- `docs/02_KONTRAK_SISTEM_DAN_KEPUTUSAN_TAHAP0.md` — baseline lintas subsistem, pin resmi, dan keputusan terbuka.
- `docs/03_AI_MODEL_RESEARCH_AND_EVALUATION.md` — penelitian serta evaluasi AI.
- `docs/04_NEXTION_ATMEGA_RASPI_ARCHITECTURE.md` — arsitektur integrasi.
- `docs/06_INDEPENDENT_AUDIT_QA_QC.md` — temuan, risiko, dan bukti QA/QC.
- `docs/REPOSITORY_STRUCTURE.md`, `data/raw/README.md`, serta `nextion/NX4827T043_011/README_NEXTION_EDITOR.md`.

Baca secara selektif sesuai tugas. Jika dokumentasi, kode, dan hasil uji bertentangan, investigasi lebih dahulu; jangan menganggap rencana sebagai implementasi yang sudah selesai.

Kepemilikan direktori: `src/`, `include/`, `lib/` (firmware); `test/` (uji embedded); `nextion/` (HMI dan aset); `scripts/` (akuisisi, validasi, eksperimen); `data/raw/` (data asli); `data/processed/` (turunan dan fitur); `data/analysis/` (analisis); `models/` (model/metadata); `results/` (hasil); `docs/` (dokumentasi); `archive/` (historis, bukan sumber produksi tanpa verifikasi).

## 3. Kontrak sistem yang harus dipahami

- **MCU:** ATmega2560; empat ADS1115 beralamat `0x48–0x4B`; SHT30 melalui I2C.
- **Sepuluh kanal gas berurutan:** TGS822, MQ135, **MQ3**, TGS2611, TGS2620, TGS2600, TGS2602, MQ8, TGS813, TGS816.
- **Nextion:** NX4827T043_011 melalui `Serial2` @ 9600 baud. Nextion TX → PH0/RXD2 (**TQFP-100 pin 12**, header Mega RX2/D17); Nextion RX ← PH1/TXD2 (**TQFP-100 pin 13**, header TX2/D16). Jangan samakan nomor pin kemasan IC dengan nomor pin header Arduino; pastikan jalur PCB custom berdasarkan skematik. Acuan: datasheet Microchip ATmega2560 dan pinout Arduino Mega resmi.
- **USB ke host:** `Serial` @ 115200 baud; Raspberry Pi 5 adalah target pemrosesan/inferensi AI.
- **Akuisisi aktif:** lima siklus, masing-masing 25 detik purging + 5 detik collecting.
- Dataset aktif B32+ memakai **MQ3**; data historis tertentu memakai **MQ9**. Jangan menggabungkan keduanya tanpa pembuktian kompatibilitas.

ATmega memegang state machine, akuisisi dan keselamatan pompa/valve. Raspberry Pi ditujukan untuk pengolahan data/inferensi; integrasi fisik E2E belum boleh dianggap teruji. Perubahan pin, protokol, pemetaan sensor, timing, aktuator, dan skema data perlu analisis dampak dan pengujian memadai.

## 4. Otonomi perubahan, riset, dan dependensi

- **Preferensi 3C:** refactoring dan improvement luas yang relevan diperbolehkan. Untuk perubahan besar/lintas modul, susun rencana singkat, bagi menjadi langkah teruji, dan pertahankan kompatibilitas atau dokumentasikan perubahan kontraknya.
- **Preferensi 6C:** lakukan eksperimen AI, benchmarking, feature engineering, hyperparameter tuning, ablation study, analisis drift/repeatability, dan eksplorasi algoritma secara proaktif bila bermanfaat.
- **Preferensi 7C:** riset literatur/dokumentasi resmi dan pemasangan dependensi *development* yang aman diperbolehkan. Utamakan sumber tepercaya, lingkungan terisolasi, versi yang dapat direproduksi, dan pemeriksaan kompatibilitas. Jangan sembarang menjalankan skrip pihak ketiga, melakukan instalasi global, atau mengubah layanan produksi.
- Jaga perubahan pengguna yang sudah ada. Jangan mengganti konfigurasi lokal, menghapus artefak historis, atau menambahkan dependency/kompleksitas tanpa alasan yang jelas.

## 5. Hardware, SOP, Nextion, dan data mentah

**Preferensi 4C — Hardware:** pengujian fisik boleh dilakukan **hanya dalam cakupan SOP yang telah disetujui pengguna**. Sebelum bertindak, periksa identitas perangkat, status listener, kepemilikan COM5/port lain, risiko aktuator, dan langkah pemulihan. Membaca serial, flashing, upload TFT, kalibrasi/EEPROM, menjalankan pompa/valve, atau deployment aktif hanya diperbolehkan jika tindakan spesifik itu tercakup SOP/persetujuan. Jika tidak, lakukan pengujian offline dan minta izin. Akses terminal bukan izin pengoperasian perangkat. Jangan mengganggu sesi akuisisi aktif.

**Preferensi 5B — Nextion:** boleh memperbaiki event, navigasi, logika, validasi, dan komunikasi tanpa mengubah desain visual. Pertahankan aset Figma final dan HMI acuan `nextion/NX4827T043_011/project/RoastSense_NX4827T043_011_COMPILE_READY.HMI`. Perubahan layout, warna, gambar, atau desain utama memerlukan persetujuan. Hindari regenerasi HMI yang menimpa hasil edit manual; verifikasi kontrak firmware–HMI.

**Data:** jangan menghapus, mengedit, atau menimpa CSV asli dalam `data/raw/`. Pisahkan event dari sampel sensor; validasi tipe/rentang, fase, indeks, metadata, dan kelengkapan. Cegah duplikasi serta penimpaan nama file; pertahankan data terputus dan provenance. Bedakan file, lima siklus dalam file, batch, sesi, dan **spesimen kopi fisik**. Jangan menganggap pengukuran berulang sebagai sampel independen.

## 6. Metodologi AI dan batas klaim

- Eksperimen harus dapat direproduksi: simpan versi dataset/fitur, pembagian train/test, konfigurasi, seed, dependensi, dan metrik.
- Hindari data leakage dengan pembagian berdasarkan batch/sesi/spesimen bila relevan; fitting preprocessing dan feature selection **hanya di dalam data training pada setiap fold**.
- Bandingkan baseline sederhana dengan model lain secara adil. Laporkan metrik per kelas/kelompok (misalnya macro-F1, balanced accuracy, confusion matrix), bukan hanya akurasi total.
- Evaluasi drift, unknown/abstention, kalibrasi probabilitas, penggunaan memori dan latensi perangkat bila relevan.
- Model historis MQ9 B01–B05 **bukan** bukti performa pada MQ3 B32–B35; 62 fitur B32–B35 masih kandidat penelitian.
- Model hanya dipromosikan ke perangkat setelah validasi ilmiah, kompatibilitas inferensi, dan prosedur deployment yang disetujui. Jangan mengklaim E2E/hardware/akurasi produksi hanya dari simulasi atau training.

## 7. Alur kerja dan QA/QC

Gunakan alur adaptif: **inspeksi → analisis/riset → rencana → implementasi → pengujian → review independen → dokumentasi → commit/push → laporan**. Kedalaman setiap tahap menyesuaikan risiko dan skala tugas; ini bukan checklist kaku.

**Preferensi 8C:** usahakan **seluruh suite offline yang aman** pada setiap perubahan, dengan prioritas tes relevan dan regresi bagian terdampak. Tambahkan pengujian negatif untuk perubahan yang berisiko.

Perintah acuan dari root (pilih dan jalankan sesuai kondisi):

```bash
git status --short --branch
git diff --check
pio run -e mega2560 -e nextion_test
python nextion/NX4827T043_011/tools/verify_nextion_atmega_contract.py
python scripts/test_acquisition_suite.py
python scripts/validate_b32_acquisition.py
python scripts/audit_b32_dataset.py
python scripts/test_feature_pipeline.py
python scripts/test_stage0_contract.py
python scripts/test_stage1_firmware_contract.py
python scripts/test_bench_stage1_passive_qa.py
python scripts/test_stage2_dataset_audit.py
python scripts/test_stage2_plot_provenance.py
python scripts/test_stage3_feature_pipeline.py
python scripts/test_stage4_model_benchmark.py
python -m compileall -q scripts
```

Jika tes gagal karena perubahan, perbaiki sebelum menyatakan QA lulus. Tandai hasil **PASS / FAIL / BLOCKED / NOT RUN** secara jujur. Hardware yang tidak tersedia atau belum diizinkan adalah batas pengujian, bukan alasan mengklaim PASS fisik. Jangan menjalankan perintah upload sebagai bagian tes offline.

## 8. Git: commit dan push otomatis

**Preferensi 1B + 2B + 10A:**

- Tetap bekerja pada branch **`wahyu`**, kecuali diminta lain. Periksa working tree dan remote sebelum mengubah file.
- Setelah pekerjaan dan **QA yang diwajibkan untuk cakupannya lulus**, **commit otomatis** lalu **push otomatis** ke `origin/wahyu`, tanpa perlu izin tambahan. Pekerjaan besar boleh commit/push bertahap per milestone yang sudah lolos.
- Gunakan commit logis berformat Conventional Commits, misalnya `fix:`, `feat:`, `refactor:`, `test:`, `docs:`.
- Stage **hanya file terkait tugas**; jangan memakai `git add .` secara serampangan. Pertahankan perubahan lokal milik pengguna, terutama konfigurasi `platformio.ini`/COM5 bila bukan bagian tugas.
- Jangan force push, hard reset, menghapus riwayat, atau memasukkan rahasia/data sensitif. Jangan menyembunyikan kegagalan tes atau push; jika terhalang hardware/lingkungan, laporkan batas QA dan jangan mengeklaim milestone yang belum terbukti.

## 9. Dokumentasi dan laporan milestone

**Preferensi 9C:** seluruh dokumen utama menggunakan **Bahasa Indonesia** (nama variabel, file, API, dan istilah teknis baku dipertahankan). Perbarui dokumen terkait untuk perubahan signifikan, termasuk current state, roadmap, riset AI, arsitektur, dan QA/QC.

- Untuk milestone penting, perbarui `docs/CHANGELOG.md` (buat bila belum ada) dengan tanggal, perubahan, tes, risiko, serta commit.
- Bila pekerjaan lintas subsistem atau kompleks, buat laporan QA/QC pada `docs/reports/YYYY-MM-DD_NAMA_MILESTONE.md` berisi tujuan, keputusan, implementasi, bukti, keterbatasan, serta tindak lanjut.
- Hindari laporan duplikat dan dokumentasi berlebihan untuk perubahan kecil. Lengkap dalam substansi, ringkas dalam penyajian; jangan menciptakan metrik atau hasil tes.

## 10. Definisi selesai dan komunikasi

Pekerjaan selesai jika tujuan tercapai, perubahan terkait telah diperiksa, pengujian wajib yang dapat dijalankan lulus, data/aset dan perubahan lokal aman, dokumentasi diperbarui, serta commit/push dilakukan atau kegagalannya dijelaskan.

Laporkan ringkas: perubahan, manfaat, hasil QA, status Git, risiko yang belum tuntas, dan rekomendasi berikutnya. Bedakan **software verified**, **hardware verified**, **AI validated**, dan **E2E verified** berdasarkan bukti nyata.

**Be proactive, not reckless. Be creative, not arbitrary. Follow the user's intent, not merely their examples.**

Gunakan instruksi ini secara fleksibel dan profesional: bebas mengeksplorasi solusi terbaik yang relevan, sambil menghormati larangan eksplisit, keselamatan alat, integritas data, dan kejujuran bukti.
