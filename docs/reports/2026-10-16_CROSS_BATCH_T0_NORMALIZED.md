# Grup 03 — grafik cross-batch t0-normalized (B32–B36)

Hasil tambahan **210 PNG** pada `results/plots_final_t0norm/03_same_origin_roast_cross_batch_t0norm/`; grafik asli dalam `results/plots_final/` dan direktori sebelumnya dipertahankan, tidak dihapus atau ditimpa.

## Metode

- Untuk setiap sensor dan pasangan origin+roast yang sama, plot **seluruh** B32, B33, B34, B35, B36 yang tersedia dan lolos filter akuisisi; tidak mencampur B40.
- Setiap file harus memiliki lima run dengan fase lengkap, indeks sampel kontigu dan nilai ADC finite; event pergantian fase yang semua nilai ADC-nya kosong diabaikan tanpa modifikasi sumber. Tidak interpolasi.
- Titik `t0` adalah **pembacaan ADC pada sampel terakhir purging run pertama**, tepat sebelum collecting run pertama. `y(t) = ADC(t) − ADC(t0)`; semua kurva tepat pada `(x=0, y=0)`.
- `x` ialah **indeks sampel relatif terhadap t0**, bukan detik aktual yang terkalibrasi. Sampel collecting pertama memiliki x positif. Semua lima siklus disertakan, sehingga puncak tiap run dan perubahan baseline tetap dapat diamati.
- `series_diagnostics.csv` merekam ADC absolut t0 tiap batch/kanal, jumlah sampel purging run pertama, posisi collecting pertama, puncak delta keseluruhan dan puncak lima sampel collecting pertama. `plot_index.csv` mencatat batch apa saja yang tampil pada tiap PNG. Nilai peak keseluruhan mungkin terjadi pada run selanjutnya; gunakan diagnostik siklus spesifik jika diperlukan.

## QA dan batasan

Hasil: 210 PNG; 97 CSV kopi eligible, 970 seri grafik, 0 CSV excluded dalam seleksi script. Setiap seri harus melewati pengujian agar t0 berada sebelum collecting pertama dan menghasilkan delta tepat nol pada t0. Normalisasi hanya menggeser titik nol vertikal; **tidak menghilangkan drift baseline antar-run atau variabel lingkungan**, dan bukan data prospektif/blind. Tidak ada pelatihan atau promosi model AI.

## Lokasi

`results/plots_final_t0norm/plot_index.csv`, `series_diagnostics.csv`, `skipped.csv`, `summary.json` serta 210 PNG di subfolder `03_same_origin_roast_cross_batch_t0norm`.
