# Audit akuisisi lokal baru B36 di branch wahyu

**Waktu audit:** 16 Oktober 2026. **Scope:** file root `data/raw/` yang belum tercatat Git (`*_B36.csv` dan `*_B37.csv`), dibaca tanpa memodifikasi raw/firmware/Nextion.

## Bukti

Audit `scripts/audit_local_new_b36.py` mencatat 20 file: 18 B36 baru bertanggal 15 Oktober dan dua B37 lokal historis. **Seluruh 20 lolos validator canonical** (5 siklus/file; total **3.026 baris sensor**), semua baris memiliki temperature/humidity, tanpa ADC missing/zero/saturation. **B36** seimbang menurut pilihan UI: dark 6, light 6, medium 6. Dataset B36 bukan otomatis 18 spesimen/lot fisik yang independen.

Dua B37 (`L-MING_B37.csv` dan `M-MING_B37.csv`) SHA256-nya cocok dengan sumber historis pada manifest Stage2 dan sebelumnya dikonfirmasi sebagai **bench udara bersih** walaupun label UI memilih kopi. **Jangan masukkan ke cohort kopi atau uji roast/origin.**

Ada 19 benturan nama berkas dengan sumber `irul_B36_B37/`, tetapi **tidak ada** yang byte-identical. Ini adalah rekaman berbeda yang harus diidentifikasi lewat hash, bukan nama file. Jangan menimpa/menggabungkan CSV berdasarkan basename. Hasil lengkap tersedia pada `results/local_b36_b37_audit_20261016/file_quality.csv`, `cycle_diagnostics.csv` dan `summary.json`.

## Keputusan

- **PASS** QA format/fase bagi 18 B36; simpan raw tanpa edit sebagai kandidat pengembangan/pengujian.
- **EXCLUDE** dua B37 bench dari data kopi; simpan CSV lokal dan hash historis, jangan relabel.
- **BLOCKED** klaim tes prospektif independen: belum ada registri UID fisik spesimen, lot, sesi, verifikasi label roast/origin eksternal dan custodian/blind freeze.
- **NO-GO** deployment model; jangan retrain/select model menggunakan holdout yang ingin tetap blind.

## Rekomendasi prioritas

1. Lengkapi lembar provenance per CSV B36: `physical_specimen_id`, `coffee_lot_id`, `roast_batch_id`, tanggal/sesi, operator, suhu/RH, referensi asal kopi/roast, dokumentasi pengukuran, serta checker independen.
2. Pisahkan peran development/calibration/final holdout **berdasar lot + specimen + session + hari**. `B36` sebagai batch HMI bukan ID lot independen. Pastikan asal dan tingkat roasting berimbang per partisi.
3. Audit signal quality per siklus: response relatif terhadap lima sampel purging akhir, repeatability, drift antar siklus dan carryover/blank; simpulkan abnormal hanya dengan kriteria pradefinisi, bukan berdasarkan akurasi model.
4. Periksa kasus dua nama sama dengan arsip `irul` memakai SHA256; tampilkan identitas file berdasarkan `sha`, source dan metadata pengukuran sebelum merge.
5. Bekukan fitur/model/threshold sebelum label blind dibuka. Laporkan balanced accuracy, macro-F1/recall tiap roast, unknown rejection, confidence calibration, dan uncertainty dengan unit spesimen independen.

Tidak ada source firmware, file HMI maupun `platformio.ini` diubah. Program dan laporan audit ini bukan sertifikat performa model AI.
