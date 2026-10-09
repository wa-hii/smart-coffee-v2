# Benchmark Tahap 4 — eksploratori, bukan model siap pakai

Input `data/processed/stage3_v2/` dengan 83 file B32–B35; **CAW dan semua
B37 dikecualikan** sesuai konfirmasi operator. Tidak ada keluaran model
`.joblib` atau berkas untuk deployment.

Jalankan ulang dengan lokasi output BARU:

    python scripts/stage4_model_benchmark.py --output-dir results/stage4_lobo_v3

`config.json` menyimpan hash input, paket sklearn, random seed, definisi
model dan protokol. `fold_metrics.csv` berisi setiap kombinasi grup/model/
batch uji, dukungan jumlah train/test, macro-F1, balanced accuracy dan
confusion matrix dengan urutan [dark, light, medium]. `predictions.csv`
mencatat tiap file pada batch yang ditahan. `class_metrics.csv` merinci
precision, recall dan F1 per kelas, `model_ranking.csv` hanya
**pemeringkatan deskriptif dari 4 fold yang sama**, dan `summary.json`
menegaskan status **tidak tervalidasi**.

Tidak ada tuning berdasarkan batch uji di dalam satu konfigurasi: semua model
memakai satu parameter awal tetap, scaler selalu `fit` hanya pada batch
training. Tetapi memilih kombinasi terbaik setelah melihat semua fold tetap
menimbulkan **bias pemilihan model**. Tidak ada data uji final independen,
identitas spesimen fisik, kalibrasi probabilitas, uji unknown atau prospektif.
Semua label roast masih berasal dari metadata pencatatan yang perlu diaudit.
