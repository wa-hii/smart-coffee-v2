# Addendum hasil gabungan — M-MING_B65.csv

Tambahan setelah pembuatan `MANIFEST_GABUNGAN.json` asli: satu file baru,
`01_VALID_GABUNGAN/M-MING_B65.csv`, telah lolos audit independen:

- Origin: MING; roast: medium; batch: B65.
- 900 sampel, 30 siklus, 750 purging + 150 collecting.
- Purging 25 sampel dan collecting 5 sampel untuk setiap siklus, runtut.
- Durasi 899,999 detik, median selang waktu 1000 ms, maksimum 1003 ms.
- SHA-256 `c629554c9cc7de65f5c22339807626fe708188ed225da6a87155cb6e2b62d1e3`.
- Tidak ditemukan duplikat byte maupun fingerprint time-series terhadap 111
  rekaman valid gabungan sebelumnya.
- Folder `01_VALID_GABUNGAN` kini berisi **112 CSV valid**. MING Medium kini
  mempunyai lima batch valid: B61, B62, B63, B64, dan B65.

**Catatan provenance:** `MANIFEST_GABUNGAN.json` dan
`AUDIT_PEMENUHAN_5X_PER_KOPI.csv` merekam snapshot penggabungan pertama
sebelum penambahan B65 (111 file valid / MING Medium 4 dari 5). Kedua file
historis itu **tidak ditimpa**. Addendum ini dan
`results/plots_30_siklus_merged_20261021_112csv_5skema/` mencatat keadaan
terbaru setelah B65 ditambahkan.

Hasil plotting baru: **2.160 PNG**, lima jenis grafik untuk sepuluh sensor,
termasuk lintas batch raw dan normalisasi t0; seluruh 112 CSV diperiksa ulang,
nilai ADC/timestamp tidak diedit. Indeks `input_provenance.csv`, `plot_index.csv`,
`comparison_groups.csv`, dan `summary.json` berada di folder hasil plot.
