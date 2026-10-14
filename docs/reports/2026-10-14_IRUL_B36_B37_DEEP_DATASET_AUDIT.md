# Deep audit dataset B36–B37 dari branch irul

**Status:** audit kualitas offline selesai, **belum layak untuk final blind test**.

## Provenance dan integritas

Sumber: `origin/irul` commit `f51a0d436656e9279dc96bd2c71500c1b6bc8fa4`. Data mentah 32 CSV berada di `data/raw/irul_B36_B37/` dengan checksum cocok pada manifest `data/analysis/irul_B36_B37_import_manifest.csv`. Snapshot B32–B35 yang pernah dipakai memilih model dipertahankan terpisah; tidak ditemukan SHA256 sama antara berkas import dan snapshot Stage2. Ini **tidak membuktikan spesimen fisik berbeda** atau label/lot independen.

## Ringkasan kuantitatif

| Indikator | B36 | B37 | Total |
|---|---:|---:|---:|
| CSV | 21 | 11 | 32 |
| Baseline kontrol | 1 | 1 | 2 |
| CSV berlabel kopi | 20 | 10 | 30 |
| Lolos validasi struktur | 16 | 11 | 27 |
| Ditahan karena urutan indeks | 5 | 0 | 5 |
| Kopi lolos struktur | 15 | 10 | 25 |

Seluruh 32 file berisi total **4.825 baris sensor lengkap**: 3.994 purging, 831 collecting; **tidak ditemukan sel ADC hilang/nol/saturasi** menurut pemeriksaan numerik. Semua 32 file **tidak memiliki pembacaan temperature dan humidity yang valid**; ini kelemahan provenance lingkungan, bukan alasan memalsukan nilai suhu/RH. Terdapat 1.600 pasangan siklus-kanal (32 CSV × 5 siklus × 10 kanal) untuk diagnostik baseline/response.

## Lima file yang harus HOLD

| File | Temuan |
|---|---|
| `D-CAT_B36.csv` | Indeks `run 2 purging` dan `run 5 collecting` tidak kontigu; hanya 148 sensor rows |
| `D-GAW_B36.csv` | Indeks `run 1 purging` tidak kontigu |
| `D-GRB_B36.csv` | Indeks `run 1 purging` tidak kontigu |
| `D-MING_B36.csv` | Indeks `run 2 purging` tidak kontigu |
| `L-TOR_B36.csv` | Indeks `run 2 purging` tidak kontigu |

Jangan menyisipkan/interpolasi sampel lalu menandai seolah akuisisi lengkap. Simpan apa adanya, dan gunakan hanya setelah kebijakan analisis khusus missing samples disetujui dan dinilai terpisah; jangan pakai pada evaluasi strict canonical.

## Kondisi respons dan risiko generalisasi

Median respons relatif per pasangan siklus/kanal (collecting mean dikurangi median lima purging terakhir, dibagi maksimum nilai mutlak baseline dan 1): **B36 0,00796** dan **B37 0,00811**. Rentang B36 -0,01001 hingga 0,35251; B37 -0,00184 hingga 0,13271. Besaran ini **diagnostik ADC, bukan bukti pemisahan kelas atau kualitas aroma**; distribusi tidak dibandingkan dengan label secara inferensial karena data kandidat evaluasi belum dibuka sebagai holdout independen.

Label pilihan HMI tercatat B36: dark 6, light 7, medium 7; B37: dark 4, light 3, medium 3. Sesudah validasi ketat, B36 hanya dark 2, light 6, medium 7; B37 dark 4, light 3, medium 3. Ketidakseimbangan terutama pada **dark B36** meningkatkan risiko bias metrik pada dataset kecil.

`BASELINE_B36.csv` dan `BASELINE_B37.csv` adalah kontrol, bukan kelas roasting. Dua nama file lokal `L-MING_B37.csv` dan `M-MING_B37.csv` di root raw memiliki checksum yang berbeda dari branch irul; jangan digabungkan tanpa adjudikasi sumber.

## Keputusan gate

- **PASS sebagai data raw terarsip dan sumber kajian kualitas:** 32/32 hash verified.
- **Lolos strict canonical structural QC:** 27/32, termasuk kedua baseline; 25 file kopi.
- **HOLD untuk perbaikan proses akuisisi atau review:** lima file dengan indeks tidak kontigu.
- **BLOCKED untuk independent prospective blind evaluation:** tidak ada bukti tanggal/sesi/lot/spesimen terpisah, verifikasi label independen, freeze model/threshold sebelum label terbuka, atau custodian yang memisahkan ground truth. Metadata roast/origin juga terlihat di CSV sehingga hanya dapat di-blind dengan fitur berkode anonim dan pengelola independen.
- **Model promotion:** NO-GO; tidak melatih ulang, melakukan pemilihan model, atau mengumumkan skor baru dari B36/B37 dalam audit ini.

Artefak hasil: `results/irul_b36_b37_deep_audit_20261014/summary.json`, `file_quality.csv`, dan `cycle_channel_diagnostics.csv`. Program audit: `scripts/audit_irul_b36_b37.py`. Data asli tidak diubah dan firmware/G3 tidak disentuh.
