# Penelitian dan Evaluasi Model AI — 8 Oktober 2026

## Addendum 10 Oktober — data riset eksternal dan batas Tahap 6

CoffeePow-4 (3.583 rangkaian) dan Aroma-7 (4.750 rangkaian
lengkap) dari Stefanone et al. (2025), *Results in Engineering*
27, 106309 (`10.1016/j.rineng.2025.106309`),
telah diunduh dengan hash MD5 penerbit yang cocok dan
dievaluasi **secara terpisah**. CoffeePow-4 identik dengan
bagian awal Aroma-7, bukan sumber independen kedua.
CSV satu kolom gas resistance/sepuluh heater steps;
**bukan sepuluh kanal MQ/TGS**. Label produk/udara/krim
tidak sepadan dengan roast dan origin.

Random Forest 4 kelas CoffeePow-4 memperoleh macro-F1
`0,906` split acak versus `0,501` pada
holdout urutan 20% akhir per kelas. Kedua metode
belum membuktikan sesi/hari/spesimen independen.
Data 9 MOS kopi 2023 memiliki **enam sensor sama**
tetapi data tersedia berdasarkan permintaan.

Tahap 6: gerbang **NO-GO**, bukan pemilihan model final.
Sebelum coffee-vs-air lokal, unknown kopi,
roast label fisik dan tes prospektif lolos,
`AI_TEST` harus berstatus `N/A`.
Laporan lengkap
`docs/reports/2026-10-10_RISET_DATASET_EKSTERNAL_DAN_TAHAP6.md`.

## Addendum terbaru — gerbang unknown Tahap 5 (9 Oktober 2026)

Analisis offline `results/stage5_validation_v1/` memakai dua
konfigurasi yang sebelumnya dibandingkan pada LOBO Tahap 4.
Keduanya hanya **45/83 prediksi roast benar** pada snapshot kandidat
dan **memprediksi light roast pada seluruh 5 udara bersih valid**.
Tidak satu pun udara bersih terabstain pada confidence threshold 0,6.
Karena itu **tidak ada threshold confidence siap produksi, model
unknown siap pakai, atau klaim deteksi udara bersih yang aman**.
Pooled OOF macro-F1 dan rerata macro-F1 per fold adalah ukuran
berbeda; jangan mencampurnya. Bootstrap 4 cluster sangat terbatas.
Kontrak pengambilan data prospektif dan validasi unknown kopi
belum terpenuhi. Laporan:
`docs/reports/2026-10-09_TAHAP5_GENERALISASI_UNKNOWN_QA.md`.

## Addendum terbaru — koreksi CAW dan benchmark Tahap 4 (9 Oktober 2026)

**Konfirmasi operator: CAW dan seluruh batch B37 adalah udara bersih.**
Empat CSV CAW B33–B35 serta dua B37 dikecualikan berdasarkan nama/hash,
bukan diberi label roasting dari UI. Semua angka dan narasi 86/87 sampel
di bawah adalah **snapshot historis sebelum koreksi**, bukan cohort
canonical penelitian saat ini. Gunakan `data/analysis/stage2_v2/` dan
`data/processed/stage3_v2/` yang memiliki **83 file kandidat kopi**.

Benchmark klasifikasi roast-only **eksploratori** telah dijalankan melalui
`scripts/stage4_model_benchmark.py`: 7 kelompok fitur × 8 model
× Leave-One-Batch-Out pada B32–B35 (224 fit/fold). RF 82 fitur
macro-F1 rerata **0,490** (balanced accuracy **0,545**), LDA 10 fitur
macro-F1 **0,482** (balanced accuracy **0,544**). Fold RF B34/B35
memiliki macro-F1 **0,344/0,383**, menunjukkan variasi performa antarbatches.
Ini **bukan skor test akhir unbiased**, sebab ranking ditentukan dari
fold yang dilihat semuanya. Belum ada model disetujui/di-deploy, label
fisik kopi belum diaudit, dan belum diuji prospektif. Semua detail di
`docs/reports/2026-10-09_TAHAP4_MODEL_LOBO_CAW_CORRECTION.md`.

**Status: rancangan penelitian dan evaluasi. Belum ada model B32–B35 yang dilatih atau disetujui untuk digunakan pada perangkat.**

## Addendum Tahap 2 — provenance dan cohort (9 Oktober 2026)

Manifest input yang sekarang diaudit: `data/analysis/stage2/file_manifest.csv` dan ringkasan `data/analysis/stage2/summary.json`. Terdapat **87 file kandidat B32–B35** setelah penambahan satu CSV B32, **bukan 87 spesimen fisik independen yang telah dibuktikan**. Dua CSV B37 `L-MING_B37.csv` dan `M-MING_B37.csv` adalah uji **udara bersih** dengan label UI kopi yang **tidak sah sebagai ground truth**; jangan dipakai untuk training ataupun evaluasi kopi.

Distribusi label kandidat: light 31, medium 28, dark 28. Matriks 23 kode sampel pada empat batch memiliki **9 sel kosong**, **4 sel berisi lebih dari satu file**. Grouping minimal berdasarkan batch membatasi kebocoran antarsiklus, tetapi **belum mengontrol identitas spesimen yang diuji ulang**, sehingga semua nilai generalisasi model yang muncul sebelum metadata independensi tersedia harus berstatus eksploratori. Pengujian fold lintas batch harus memeriksa dukungan tiap kelas dan kode origin, dan tidak boleh memilih hyperparameter berdasarkan batch uji yang sama.

Skor respons relatif dan beda baseline di `phase_metrics.csv`/`paired_baseline_drift.csv` bersifat **diagnostik sensor**, bukan fitur yang sudah terbukti stabil atau bukti drift terisolasi. Kandidat fitur 62 dimensi/86 file saat ini adalah artefak snapshot lama sebelum file B32 tambahan; Tahap 3 perlu ekstraksi ulang ke **output versi baru** dengan input manifest/hash dibekukan, preprocessing sama antara train dan inferensi, dan aturan pengecualian B37 fail-closed.

Angka **86 file** pada bagian metodologi lama di bawah merupakan **snapshot awal 8 Oktober**, bukan total terbaru. Jangan memperbarui klaim performa AI hanya karena jumlah file bertambah.

## Addendum Tahap 3 — Kontrak fitur versi 1 (9 Oktober 2026)

Snapshot Stage 2 B32–B35 terdiri atas 87 file kandidat, tetapi hanya **86 file memenuhi kontrak fitur yang lebih ketat**. File `L-CAW_B34.csv` ditahan: purging siklus 1 mempunyai indeks sensor 1–25 dengan **indeks 8 tidak ada**; raw tidak ditambal. Dua run B37 udara bersih tetap dikecualikan. Cohort fitur baru **berbeda** dari file historis 86-observasi sebelumnya.

Pipeline baru `scripts/stage3_feature_pipeline.py` dan fungsi `extract_sensor_features` menghasilkan **62 fitur legacy** serta **82 fitur eksploratori** dari data sensor (bukan label). Kontrak tujuh grup kandidat di `data/processed/stage3_v1/feature_groups.json`: `response10`, `response20`, `dynamic30`, `dynamic32_environment`, `raw_collect10`, `legacy62`, `expanded82`. Semua **ditetapkan a priori**, bukan berdasarkan hasil pada test set. Tidak dilakukan normalisasi global atau pelatihan model.

**Protokol Tahap 4:** semua model menerima **hanya kolom `f_*` dari grup yang ditentukan**; label/filename/sha/batch/metadata dilarang masuk matriks fitur. Baseline per siklus merupakan transformasi tanpa fit antardata; StandardScaler/imputer/PCA/seleksi lain harus dibentuk dan fit **di dalam training fold**. Ukuran 82 fitur untuk 86 file berisiko overfit; jangan menyatakan `expanded82` lebih baik sebelum eksperimen LOBO/batch grouping. Sementara provenance label belum diverifikasi, semua hasil training/evaluasi masa depan bersifat eksploratori.

## 1. Dasar bukti dan rumusan tugas

- Dataset B32–B35 memiliki **86 file akuisisi**, **23 kombinasi roast–origin**, dan **4 batch**. Setiap siklus hanya memiliki sekitar 5 titik collecting; lima siklus dalam satu file merupakan pengukuran berulang, bukan lima spesimen independen.
- Model Random Forest historis B01–B05 menggunakan MQ9 dan 45 fitur terpilih. Akurasi uji baseline 57,50% dan tuned 55,00% **tidak boleh diklaim sebagai kinerja B32–B35**.
- Ekstraktor kandidat **scripts/extract_b32_features.py** menghasilkan satu baris per CSV beserta skema fitur. Untuk setiap siklus, dihitung baseline dari lima titik purging terakhir, respons relatif collecting, standar deviasi, dan kemiringan respons; lalu dihitung rerata dan standar deviasi antar-lima siklus. Rerata suhu serta kelembapan juga ditambahkan. **Total 62 fitur numerik bersifat sementara.**
- Tugas awal yang diprioritaskan adalah **klasifikasi tingkat roasting** (light/medium/dark). Tugas kedua adalah **klasifikasi origin yang telah dikenal**, hanya jika jumlah spesimen independen mencukupi.
- Klasifikasi hierarkis, multi-output, dan gabungan origin × roasting merupakan opsi penelitian, bukan keputusan final. Sampel dengan origin tidak dikenal atau sinyal tidak meyakinkan harus dapat menghasilkan status **unknown/N/A**.

## 2. Matriks pemilihan kandidat algoritma

| Algoritma | Kelebihan potensial | Keterbatasan/risiko | Prioritas |
|---|---|---|---|
| Logistic Regression L2 dan LDA dengan shrinkage | Ringan, relatif mudah dijelaskan, cocok sebagai pembanding data kecil | Pemisahan kelas mungkin tidak linear | **Baseline utama** |
| SVM linear dan SVM RBF + StandardScaler | Dapat mempelajari pola nonlinear dari data terbatas | Perlu tuning dan kalibrasi probabilitas | **Challenger utama** |
| Random Forest dan Extra Trees dengan regularisasi | Menangkap interaksi nonlinear dan menyediakan analisis pentingnya fitur | Berisiko overfitting pada 86 observasi berkelompok | **Challenger tambahan** |
| PLS-DA | Membantu merangkum fitur sensor yang berkorelasi | Jumlah komponen harus dipilih di dalam cross-validation | Pembanding penelitian |
| QDA dan k-NN | Baseline sederhana | Kovarians QDA bisa tidak stabil; k-NN sensitif skala dan drift | Uji terbatas |
| Gradient Boosting, XGBoost, LightGBM, CatBoost | Mempelajari hubungan nonlinear kompleks | Tuning lebih banyak dan membutuhkan data yang lebih kuat | Opsional setelah baseline |
| ROCKET/MiniROCKET, CNN 1D, CNN-LSTM, LSTM, GRU | Memanfaatkan dinamika deret waktu | Lima titik collecting dan 86 unit akuisisi belum cukup untuk membenarkan kompleksitasnya | **Ditunda** |

**Belum ada model yang dapat disebut paling akurat.** Keputusan final harus berasal dari evaluasi lintas batch, ketahanan terhadap drift, dan pengujian prospektif. Jika kinerja setara, utamakan model yang lebih sederhana dan mudah dipelihara.

## 3. Protokol evaluasi yang wajib digunakan

1. **Bekukan inventaris data.** Simpan source_sha256, nama file akuisisi, kode sampel, roast, definisi origin, batch, versi firmware dan hardware, tanggal, **ID spesimen fisik**, serta **ID sesi pengukuran** pada pengambilan data baru. Hitung jumlah spesimen independen sebenarnya, bukan sekadar jumlah siklus atau file.
2. **Validasi sebelum ekstraksi.** Tolak CSV yang tidak lolos aturan kualitas. Jangan pernah memasukkan sample_id, roast_level, origin, batch_id, nama file, hash, sample_idx, atau uptime sebagai fitur masukan model karena merupakan label atau metadata yang dapat membocorkan identitas sampel.
3. **Gunakan pemisahan berdasarkan kelompok.** Pada data yang ada, uji awal dapat memakai LeaveOneGroupOut dengan group=batch_id untuk B32–B35. Laporkan masing-masing empat fold dan periksa ketersediaan tiap kelas. Karena batch telah sering diperiksa selama pengembangan, ini belum menggantikan uji prospektif final.
4. **Lakukan fitting hanya pada data latih.** StandardScaler, imputer, pemilihan fitur, PCA/PLS, kalibrasi, serta model harus dilatih dalam fold training melalui sklearn Pipeline. Tuning parameter C, gamma, pohon, jumlah komponen dan ambang abstain dilakukan dengan validasi kelompok bersarang hanya bila jumlah kelompok memadai; jika tidak, gunakan ruang parameter kecil yang telah ditentukan sebelum evaluasi.
5. **Hitung metrik pada tingkat file/spesimen.** Minimal akurasi, balanced accuracy, macro-F1, precision/recall/F1 tiap kelas, confusion matrix, metrik kalibrasi (jika valid), cakupan abstain, risiko salah prediksi, latensi inferensi, ukuran model, dan penggunaan memori.
6. **Lakukan ablation study.** Bandingkan rerata collecting saja, respons relatif terhadap baseline, slope/SD, penggunaan suhu–kelembapan, agregasi antar-siklus, serta keputusan dari siklus awal. Ukur pengaruh drift, pengukuran ulang, perbedaan batch, dan perubahan kondisi lingkungan.
7. **Pisahkan data uji final.** Bekukan aturan evaluasi sebelum training; kumpulkan batch dan spesimen fisik baru secara prospektif. Data uji final tidak boleh digunakan berulang kali untuk memilih fitur, hyperparameter, atau ambang confidence.
8. **Evaluasi origin dengan benar.** Jangan menilai origin yang tidak pernah muncul di training sebagai klasifikasi known-origin yang seharusnya dapat ditebak. Gunakan pengujian unknown/out-of-distribution secara terpisah dan laporkan cakupan origin yang benar-benar tersedia.

## 4. Kontrak artefak model dan syarat promosi

Artefak model yang kelak digunakan harus berisi model beserta preprocessing yang telah di-fit, versi skema fitur, **urutan nama fitur**, urutan kanal ADC, kebijakan nilai hilang, pemetaan label, kompatibilitas firmware/sensor, konfigurasi ambang unknown, hash dataset asal, commit training, serta versi Python/library.

Kriteria **go/no-go**:

- Tidak ada kebocoran data train–test dan ekstraksi fitur dapat direproduksi.
- Hasil generalisasi lintas batch ditampilkan per kelompok dan per kelas.
- Kelas origin di luar cakupan model dapat ditolak secara eksplisit.
- Confidence hanya ditampilkan jika probabilitas telah dikalibrasi dan diuji.
- Fitur training sama persis dengan fitur inferensi; output salah skema ditolak.
- Model memenuhi batas latensi, memori, dan ukuran pada **Raspberry Pi 5 aktual**.
- Hasil pada dataset prospektif memenuhi target mutu yang disepakati **sebelum** melihat hasil pengujian.

Tanpa bukti tersebut, status model tetap **kandidat penelitian**, tidak boleh diaktifkan sebagai model produksi.

## 5. Referensi yang tercatat untuk penelitian lanjutan

Rujukan berikut dipertahankan dari dokumentasi penelitian awal dan perlu ditelaah ulang kesesuaian bibliografinya sebelum digunakan dalam publikasi:

- Studi E-Nose kopi (2023), eksplorasi PLSR, LDA, dan ANN: https://doi.org/10.1016/j.snb.2023.134229
- Studi profil roasting dengan sensor TGS dan ANN (2024): https://doi.org/10.1016/j.sbsr.2024.100632
- Tinjauan E-Nose pangan, drift, dan keandalan (2025): https://pmc.ncbi.nlm.nih.gov/articles/PMC12301011/
- Dokumentasi resmi scikit-learn untuk validasi kelompok: https://scikit-learn.org/stable/modules/cross_validation.html
- Dokumentasi resmi scikit-learn tentang data leakage dan Pipeline: https://scikit-learn.org/stable/common_pitfalls.html

Hasil penelitian lain tidak otomatis berlaku pada susunan sensor, batch, dan kondisi eksperimen RoastSense.
