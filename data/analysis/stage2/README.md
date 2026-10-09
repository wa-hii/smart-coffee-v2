# Analisis dataset Tahap 2 — snapshot lokal 9 Oktober 2026

Seluruh berkas di direktori ini adalah **turunan/hasil audit**, bukan sumber kebenaran label fisik. Raw CSV tetap di `data/raw/` dan tidak diubah.

## Cara menghasilkan ulang

Dari root repo (dengan akses ke CSV lokal yang sama):

    python scripts/test_stage2_dataset_audit.py
    python scripts/stage2_dataset_audit.py --output-dir data/analysis/stage2 --replace-derived

Flag `--replace-derived` hanya mengizinkan penggantian hasil audit di direktori output yang diminta, **bukan** raw. Jika menjalankan di clone tanpa data B37 lokal, laporan akan mencatat file pengecualian yang tidak tersedia dan menghasilkan snapshot lebih kecil. Samakan manifest SHA256 sebelum membandingkan hasil antar mesin.

## Isi output

| File | Interpretasi |
|---|---|
| `file_manifest.csv` | Satu baris per file CSV final B32+ yang ditemukan, SHA256, schema, metadata, kelengkapan, dan status calon data ML. |
| `phase_metrics.csv` | Nilai 5 siklus × 10 sensor per file (jika lolos), **tidak** merupakan observasi ML independen. Menghitung baseline awal/akhir purge, collecting mean, respons relatif, dan proxy perubahan purge. |
| `sample_batch_coverage.csv` | Matriks jumlah file per kombinasi kode sampel–batch B32–B35. Isi nol = missing, nilai di atas satu = pengulangan file yang independensinya belum diverifikasi. |
| `paired_baseline_drift.csv` | Pasangan median baseline B32 vs B35 pada sample_id yang tersedia di kedua batch. Angka ini **bukan pengukuran drift sensor terkontrol**, karena spesimen, pengondisian, hari, dan urutan eksperimen belum diverifikasi. |
| `outlier_review.csv` | Flag pemeriksaan eksploratori respons relatif, memakai robust-score terhadap file dengan kode sample_id sama. **Bukan alasan otomatis membuang data**. |
| `summary.json` | Statistik ringkas dan batas klaim penelitian. |

## Keputusan provenance

- `candidate_labels_unverified`: struktur valid dan berasal dari B32–B35; **belum dinyatakan training-ready** sampai identitas asal kopi, roast, sesi/hari, dan spesimen fisik dikonfirmasi.
- `excluded_bench_clean_air`: data udara bersih batch B37 yang operator nyatakan sebagai uji hardware, bukan kopi berlabel. Lihat `data/analysis/bench_only_exclusions.csv`, diverifikasi dengan SHA256.
- `hold_new_batch_for_review`: B36+ lainnya, default ditahan agar tidak diasumsikan memiliki label kopi.
- `rejected_invalid`: tidak boleh masuk pipeline fitur/AI sampai penyebab kegagalan ditangani tanpa mengubah raw.

Unit evaluasi sekarang **satu file akuisisi = satu observasi kandidat**, bukan lima siklus independen. `timestamp` adalah uptime MCU, **bukan** tanggal/waktu pengambilan sampel. Sebelum evaluasi ML, wajib menentukan kelompok independensi, melakukan split berbasis batch minimal, dan menangani kelas yang tidak hadir di setiap batch. Dataset B37 udara bersih tidak boleh menyelinap melalui grafik per origin maupun pipeline training.

Laporan interpretasi utama: `docs/reports/2026-10-09_TAHAP2_PROVENANCE_KUALITAS_DATASET.md`.
