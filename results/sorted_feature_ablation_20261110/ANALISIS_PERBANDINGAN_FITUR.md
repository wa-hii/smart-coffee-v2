# Perbandingan 9 fitur vs. penambahan peak, area collecting dan variasi baseline

**Proyek:** Smart Coffee E-Nose v2 — dataset sorting 30 siklus, 10 November 2026.
**Status:** eksploratif; **tidak** digunakan untuk menentukan model produksi secara final.

## 1. Dataset dan kontrol kualitas

- Sumber hanya CSV di `data/dataset sorting/{a,b,c}/kept/` yang lolos audit struktur 30 siklus. CSV pada `maybe/` dan `excluded/` tidak ikut model.
- **Empat incomplete yang keliru berada pada folder `kept` dikeluarkan**, dan satu duplikasi identitas origin–roast–batch (`M-TEM_B62_20261019_175906.csv`) tidak dihitung sebagai observasi independen.
- **199 rekaman** dari enam origin (CAT, GAW, GRB, MING, TEM, TOR): **133 training** dari cohort a+b, **66 testing** cohort c (B80–B90). Setiap CSV 30 siklus = satu observasi.
- Test c tidak dipakai untuk menghitung Z-score, memilih jumlah sensor/fitur, atau menyetel model. Validasi internal training menggunakan **leave-one-origin-out (6 fold)** dengan StandardScaler di dalam pipeline setiap fold.
- Skrip melakukan verifikasi SHA-256 dari berkas sumber, tanpa memodifikasi raw CSV.

## 2. Definisi fitur yang dibandingkan

Untuk sensor `s` dan siklus `c`, baseline lokal `B[c,s]` adalah median **lima pembacaan terakhir fase purging (sampel 21–25)**. Lima ADC fase collecting dikurangi `B[c,s]` sehingga diperoleh sinyal terkoreksi `R[c,1..5,s]`. Ini identik dengan metode pada audit sebelumnya.

**Tiga fitur awal per sensor (3 × 3 sensor = 9 fitur):**

1. `median_phase_response`: median dari 30 nilai mean lima titik collecting yang sudah dikoreksi baseline.
2. `mean_phase_response`: rata-rata 30 nilai mean lima titik collecting terkoreksi.
3. `response_early_late`: median respons collecting siklus 26–30 dikurangi median respons siklus 1–5.

**Tiga fitur tambahan per sensor:**

4. `peak_response`: median dari 30 puncak `max(R[c,1..5,s])`.
5. `collect_auc_trapz`: median dari 30 luas trapesium **bertanda** pada 5 titik collecting terkoreksi (`0.5 R1 + R2 + R3 + R4 + 0.5 R5`, dengan interval sampling 1 detik). **Lima titik hanya meliputi empat interval detik teramati**, bukan mengarang titik awal collecting sebelum sensor dibaca. Unit ADC·s.
6. `baseline_iqr_30cycles`: `Q75(B[1..30]) - Q25(B[1..30])`. Mengukur variasi baseline purging antarsiklus sepanjang satu CSV; tidak memakai informasi kelas maupun data lain.

Varian 3 sensor (TGS822, TGS2602, TGS816) dibandingkan pada **9, 12, 15, dan 18 fitur**. Varian 10 sensor pada **30, 40, dan 60 fitur**. SVM RBF dan Logistic Regression L2 menggunakan hiperparameter tetap (tanpa tuning).

## 3. Hasil lengkap pada tiga sensor utama

| Konfigurasi | Jumlah fitur | SVM CV training | SVM test c | Logistic CV training | Logistic test c |
|---|---:|---:|---:|---:|---:|
| **Fitur awal saja** | 9 | **54,7%** | 65,3% | **50,5%** | 61,0% |
| + Peak | 12 | 52,4% | 66,7% | 50,4% | 63,8% |
| + Area collecting | 12 | 53,1% | 65,3% | 49,1% | 61,0% |
| + Baseline IQR | 12 | 52,2% | 68,0% | 46,2% | 62,0% |
| + Peak dan area | 15 | 51,6% | 67,6% | 49,7% | 63,0% |
| + Peak dan baseline IQR | 15 | 51,5% | 67,1% | 46,0% | 59,9% |
| + Area dan baseline IQR | 15 | 52,2% | 66,2% | 46,1% | 63,0% |
| **+ Semua fitur** | 18 | 49,7% | **68,1%** | 46,0% | 59,0% |

Seluruh persentase merupakan **balanced accuracy**. Kolom CV training dihitung dari prediksi out-of-origin; kolom test c menggunakan 66 rekaman cohort c yang belum dilihat saat fitting.

### Recall per kelas (SVM, 3 sensor)

| Fitur | Light | Medium | Dark | Macro F1 test c |
|---|---:|---:|---:|---:|
| 9 awal | 92,9% | 52,9% | 50,0% | 60,1% |
| 9 + baseline IQR | 78,6% | **58,8%** | **66,7%** | **65,0%** |
| 18 fitur lengkap | 92,9% | 55,9% | 55,6% | 63,5% |

Menambahkan baseline IQR terlihat membantu recall Medium dan Dark pada test c, tetapi sedikit mengurangi recall Light. **Pada CV training, skor justru menurun dari 54,7% menjadi 52,2%**. Kenaikan test c belum cukup untuk menyimpulkan fitur baru pasti lebih baik pada pengambilan kopi selanjutnya.

## 4. Pembanding bila semua 10 sensor digunakan

| Fitur 10 sensor | Jumlah fitur | Logistic CV train | Logistic test c | SVM CV train | SVM test c |
|---|---:|---:|---:|---:|---:|
| Fitur awal | 30 | **55,1%** | 48,8% | **48,4%** | 45,5% |
| + Peak | 40 | 55,1% | 50,1% | 49,1% | 46,4% |
| + Area | 40 | 52,9% | 47,9% | 48,5% | 49,3% |
| + Baseline IQR | 40 | 46,1% | 47,1% | 43,3% | 56,0% |
| + Semua fitur | 60 | 49,8% | 53,3% | 46,2% | 54,9% |

Pada **validasi CV training**, konfigurasi terbaik dari seluruh kombinasi yang diuji adalah Logistic Regression menggunakan **30 fitur awal dari 10 sensor (55,1%)**. Namun skornya turun menjadi **48,8% pada c**. Ini menggarisbawahi bahwa skor CV saja tidak menjamin ketahanan terhadap perpindahan periode/alat.

## 5. Apakah fitur baru menyumbang informasi unik?

Pada 133 rekaman training, korelasi absolut terhadap fitur `mean_phase_response` untuk setiap sensor:

| Fitur baru | Median korelasi absolut terhadap mean response | Interpretasi |
|---|---:|---|
| Peak response | **0,954** | Sebagian besar merepresentasikan amplitudo yang sudah ditangkap fitur awal |
| Area collecting (AUC) | **0,981** | Hampir redundan dengan rata-rata respons collecting pada segmen lima titik |
| Baseline IQR 30 siklus | **0,049** | Memuat pola variabilitas berbeda, tetapi mungkin berkaitan dengan kondisi alat, suhu dan drift |

Korelasi dihitung hanya dari **training** agar diagnosis tidak memanfaatkan statistik test c. Area collecting dekat dengan `mean_phase_response` secara matematis karena kedua fitur dihasilkan dari lima pembacaan collecting yang sama; perbedaan muncul dari bobot trapesium dan median antar-siklus. PCA atau seleksi fitur tidak otomatis mengatasi confounding perangkat.

## 6. Ketidakpastian kenaikan skor testing

Uji deskriptif *paired stratified bootstrap* 5.000 pengulangan pada 66 file test c (strata label roasting; unit resampling file, bukan siklus):

| Perbandingan terhadap SVM 9 fitur | Perubahan balanced accuracy c | Interval bootstrap 95% |
|---|---:|---:|
| Tambah baseline IQR → 12 fitur | +2,75 poin | **−8,01 s.d. +13,07 poin** |
| Tambah semua → 18 fitur | +2,83 poin | **−6,61 s.d. +12,81 poin** |

Interval **melewati nol**, sehingga kenaikan sekitar 2,8 poin pada c belum menunjukkan perbaikan yang meyakinkan. Bootstrap ini hanya mendeskripsikan variasi **di dalam 66 rekaman terpilih**. Interval tersebut belum memperhitungkan kemungkinan spesimen/kondisi yang bergantung maupun bias sorting, sehingga **bukan** confidence interval performa produksi.

## 7. Keputusan metodologis

**Saran utama: pertahankan 9 fitur tiga sensor + SVM RBF sebagai baseline awal yang paling sederhana dan relatif kuat pada CV training**, lalu simpan `peak` dan `baseline_iqr` sebagai fitur kandidat pada eksperimen berikutnya. Jangan mengadopsi 18 fitur hanya karena skor c naik beberapa poin. **Area collecting belum menjadi prioritas** karena hampir duplikat mean collecting.

Selanjutnya, kumpulkan **data baru yang tidak disorting berdasarkan bentuk kurva**, dengan semua roasting pada setiap origin dan perangkat yang sama (ALAT_1/2/3), `preparation_id`, `device_id`, `session_id`, suhu/RH, massa kopi dan urutan pengambilan. Pilih fitur serta hiperparameter menggunakan **nested CV di training**, lalu gunakan set prospektif yang tidak tersentuh untuk evaluasi akhir.

Data c yang digunakan di sini sudah melalui sorting dan distribusi origin–roastingnya tidak lengkap; nilai di atas **bukan klaim kesiapan implementasi AI di Raspberry Pi**.

## File pendukung

- `recording_features_extracted.csv`: semua fitur lama dan baru untuk 199 rekaman.
- `ablation_model_scores.csv`: 26 konfigurasi model (13 kumpulan fitur × 2 algoritma), CV dan hasil c.
- `holdout_c_predictions.csv` dan `train_origin_cv_predictions.csv`: keluaran per rekaman untuk memeriksa kesalahan.
- `holdout_c_per_origin.csv`: pemeriksaan tiap origin (beberapa origin di c tidak memiliki ketiga roasting).
- `feature_redundancy_training_only.csv`: korelasi fitur baru vs. rata-rata respons.
- `paired_holdout_uncertainty.csv`: perubahan akurasi beserta interval bootstrap deskriptif.
- `feature_sets.json` dan `summary.json`: definisi fitur, split dan asumsi.
- `feature_ablation_train_cv.png`: grafik perbandingan fitur pada CV training.

**Reproduksi:** `python scripts/compare_sorted_30cycle_feature_ablation.py` untuk direktori output baru; skrip sengaja menolak overwrite agar hasil yang sudah diperiksa tidak tertimpa. Validasi `python scripts/test_sorted_feature_ablation.py`.
