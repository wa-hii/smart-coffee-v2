# Benchmark sensor asli Zenodo — penelitian terpisah, bukan akurasi alat kita

Input publikasi *Results in Engineering* 2025, DOI
`10.1016/j.rineng.2025.106309`, dataset DOI
`10.5281/zenodo.15425922`.

Dataset yang terunduh pada PC proyek:
`data/external/zenodo_15425922/CoffeePow-4.csv` dan
`Aroma-7.csv`. MD5 cocok dengan Zenodo, SHA256 dicatat dalam
`dataset_integrity.csv`. Raw publikasi tidak di-commit.

Jalankan ulang:

    python scripts/research_external_coffee_datasets.py
    python scripts/evaluate_external_coffee_enose.py --output-dir results/external_coffee_enose_v2

`evaluation_metrics.csv` memuat 40 kombinasi (2 dataset × 2
target × 2 split × 5 model). `per_class_metrics.csv` berisi metrik
setiap kelas dan `split_manifest.csv` menyimpan indeks rangkaian
asli train/test (tidak berisi salinan sinyal).
`summary.json` mencatat hash, overlap antar-dataset, serta larangan
penggabungan data eksternal ke pipeline MQ/TGS.

**Protokol:** setiap 10 baris = 10 langkah heater BME688 satu rangkaian;
klasifikasi kelas asli dan klasifikasi nonkopi-vs-kopi menggunakan urutan
kelas yang **diasumsikan dari README penulis** (bukan verifikasi
identitas sampel per indeks). Sinyal resistansi positif diubah
`log10`, scaler `fit` hanya pada train. Model: Dummy prior, Logistic,
LDA shrinkage, SVM RBF, Random Forest fixed seed/parameter.

**Dua pembagian diagnostik, bukan bukti prospektif:**

- `stratified_random`: stratified shuffle 80% train / 20% test
  pada rangkaian, berpotensi mengandung sampel yang sangat berdekatan
  dalam urutan eksperimen.
- `within_class_tail`: 20% rangkaian **terakhir per kelas** sebagai
  test. Ini lebih konservatif dalam urutan file, tetapi **tidak
  membuktikan waktu, sesi, hari, alat atau spesimen independen**.

Angka yang menarik (RF, rerata macro-F1):

| Tugas | Split acak | Bagian akhir per kelas |
|---|---:|---:|
| CoffeePow-4, 4 kelas | 0,906 | **0,501** |
| CoffeePow-4, air vs kopi (pemetaan kelas diasumsikan) | 0,929 | 0,866 |
| Aroma-7, 7 kelas | 0,950 | **0,690** |

**Tidak dapat digunakan sebagai skor roast-level, origin, atau coffee
presence pada perangkat Smart Coffee**. Sumber alat, label dan
fase sinyal berbeda, dan semua pengujian masih satu publikasi yang
tidak menyediakan identitas sesi/spesimen. Laporan lengkap:
`docs/reports/2026-10-10_RISET_DATASET_EKSTERNAL_DAN_TAHAP6.md`.
