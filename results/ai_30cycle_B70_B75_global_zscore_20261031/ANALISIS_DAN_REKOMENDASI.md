# Smart Coffee E-Nose — gabungan B70–B75 dan screening model AI

## 1. Penggabungan dan QC

- Arsip lama: **112 CSV** valid; B70–B75: **126 CSV**, dengan **121 valid dan 5 incomplete**.
- Total **233 CSV valid** dari 238 input, **231 rekaman dengan kombinasi origin–roast–batch unik**.
- Lima incomplete: `M-TOR_B70_3328c9859044444ba86977be746831e2_INCOMPLETE.csv`, `M-TEM_B73_a00116bc923c42b888da60e07fad130c_INCOMPLETE.csv`, `L-MING_B75_8d9adafb31744b538fa663e1fef1b18c_INCOMPLETE.csv`, `L-TOR_B75_ad0a30d7ece544609ad4efcb742504e2_INCOMPLETE.csv`, `M-GAW_B75_bc7301af72124e398d4edb8626b1836e_INCOMPLETE.csv`.
- Semua 5 incomplete berjumlah 888–893 titik; jangan membuat sampel 900 titik sintetis dengan interpolasi. Periksa sambungan receiver/USB, loss frame dan validasi index sebelum mengulang.
- Dua rekaman lama dengan ID origin–roast–batch yang sama tetap ada di arsip tetapi tidak dianggap pengulangan independen.

## 2. Preprocessing yang diuji

1. Validasi per CSV: 900 baris, 30 siklus, urutan purging 25 detik dan collecting 5 detik, metadata dan hash.
2. Baseline lokal **di setiap siklus** dan sensor: median ADC purging sampel 21–25. Collecting dikoreksi dengan mengurangi baseline tersebut dari lima pembacaan ADC saat collecting.
3. Ringkas 30 siklus menjadi fitur satu rekaman: median respons, IQR, slope tren antarsiklus, median amplitudo puncak relatif baseline, median slope lima titik collecting.
4. Pisahkan **training 93 rekaman lama** dan **testing 103 rekaman baru B70–B75**, hanya enam origin yang masing-masing mempunyai ketiga roasting (CAT, GAW, GRB, MING, TEM, TOR). RAT/GAY/MUK tetap terarsip namun tidak dijadikan label kelas roasting lintas-origin.
5. **Global Z-score**: setiap fitur memakai μ dan σ dari 93 rekaman training untuk semua kelas bersama-sama. Tidak melakukan fit ulang pada testing, tidak menghitung Z-score terpisah per roasting atau CSV.
6. Ranking sensor dihitung menggunakan **leave-one-origin-out CV dari training saja** dengan Logistic Regression L2 (fit scaler setiap fold). Model gabungan dibandingkan pada B70–B75 yang tidak dipakai untuk memilih sensor.

## 3. Ranking sensor

| Ranking CV lama | Sensor | Balanced accuracy CV training | Balanced accuracy batch baru | Drift/respons median batch baru |
|---:|---|---:|---:|---:|
| 1 | MQ8 | 50.1% | 31.9% | 1.69 |
| 2 | TGS816 | 49.2% | 38.8% | 1.85 |
| 3 | TGS2611 | 48.9% | 32.7% | 19.27 |
| 4 | TGS2620 | 48.0% | 30.3% | 9.68 |
| 5 | TGS822 | 47.9% | 44.2% | 0.72 |
| 6 | TGS2602 | 46.9% | 43.0% | 3.86 |
| 7 | MQ135 | 43.2% | 35.9% | 1.82 |
| 8 | MQ3 | 42.2% | 26.3% | 1.76 |
| 9 | TGS2600 | 34.6% | 32.2% | 1.43 |
| 10 | TGS813 | 26.2% | 36.2% | 8.22 |

**Penting:** urutan pada tabel adalah ranking **di training**. Skor pada kolom testing adalah pemeriksaan generalisasi, bukan kriteria seleksi sensor. Ranking dari batch lama tidak selalu konsisten dengan batch baru.

## 4. Akurasi dan pemilihan metode

- Kombinasi dengan CV training tertinggi adalah `ALL10_raw_ADC` + `LogReg_L2` (74.0% CV), tetapi pada batch baru hanya 44.2% balanced accuracy.
- Pendekatan sederhana 3 sensor peringkat teratas + Logistic Regression: 48.8% CV training, 45.7% testing. **Model ini tidak memprediksi satu pun Dark** di batch baru, sehingga skor keseluruhan menyesatkan jika dibaca sendirian.
- Perbandingan raw ADC + Logistic Regression turun dari 74.0% CV ke 44.2% testing. Ini konsisten dengan potensi pergeseran distribusi/alat/sesi.
- Fitur t0-only dan suhu/RH-only tidak secara konsisten meningkatkan generalisasi; tetap gunakan sebagai *negative control* untuk melihat model yang memakai informasi perancu.

### Uji kontrol sensor terpilih sebelum B70–B75

TGS822, TGS2602, TGS816 telah diusulkan dari audit drift sebelum tambahan B70–B75. Hasilnya disimpan dalam `preaudit_fixed_3sensor_control.csv` agar pilihan yang sudah ada tidak disamakan dengan pilihan berdasarkan test set.

## 5. Drift dan kondisi alat

- Pada dataset B70–B75, sensor TGS822 mempunyai median drift/respons 0.72; ini lebih rendah daripada sebagian besar sensor lain, tetapi **bukan bukti klasifikasi paling baik**.
- `ALAT_1/2/3` kini tersedia dari `.quality.json` untuk B70–B75; perangkat pada dataset lama tidak tercatat, sehingga tidak bisa dipastikan train dan test berasal dari domain alat yang sama.
- Pada banyak origin, kelas Light/Medium/Dark dibagi antarperangkat secara tidak seimbang. Penting mengulang **setiap level roasting di setiap perangkat**, bukan satu level per alat.
- Outlier dan drift bukan otomatis kegagalan sensor; perlu uji blank clean-air, persiapan spesimen terpisah, urutan sampel acak, serta log suhu dan RH.

### Rekaman B70–B75 yang paling perlu ditinjau

Audit ulang gabungan menghasilkan status screening untuk **121 rekaman baru**:
**3 prioritas uji ulang**, **68 perlu review**, dan **50 tanpa flag besar**.

| CSV | Dasar indikator | Langkah awal |
|---|---|---|
| `D-GAW_B70.csv` | Respons collecting berbeda dari peer pada 5 sensor | Konfirmasi kondisi chamber, sampel dan alat |
| `D-RAT_B73.csv` | Drift dominan pada 8 sensor dan drift berbeda pada 2 sensor | Periksa blank udara bersih serta stabilitas purging |
| `M-TEM_B70.csv` | Respons berbeda pada 5 sensor, drift dominan pada 7 sensor | Periksa purge, residu chamber, dan pengulangan Medium TEM |

Ketiganya **valid 900 titik** dan hanya menjadi kandidat pemeriksaan, bukan sampel yang otomatis salah.
Lima CSV incomplete dilaporkan terpisah pada `quarantined_records.csv`.

Konfigurasi tiga sensor yang telah diusulkan *sebelum* B70–B75 (TGS822, TGS2602, TGS816)
dengan SVM menghasilkan recall Light 64,7%, Medium 21,2%, dan Dark 50,0% pada batch baru.
Kemampuannya masih tidak seimbang dan belum layak dijadikan klaim keberhasilan model produksi.

## 6. Keputusan metode dan roadmap

1. **Belum deploy model AI final.** Data baru membuktikan generalisasi masih rendah dan beberapa model gagal memprediksi seluruh kelas.
2. Prioritaskan **baseline lokal per siklus → fitur level rekaman → global Z-score yang di-fit hanya pada training → Logistic Regression L2** sebagai baseline mudah diaudit; bandingkan SVM dan Random Forest.
3. Untuk pemilihan hardware dan rencana dataset, **TGS822, TGS2602 dan TGS816** layak menjadi kandidat fisik yang lebih stabil berdasarkan respons/drift; MQ8 dan TGS2611 tetap diuji secara terkontrol karena performa CV lama tidak cukup stabil saat diuji pada batch baru.
4. Rekam data baru dengan desain faktorial **origin × roast × device**, minimal lima persiapan kopi independen tiap sel yang memungkinkan, dengan `device_id`, `preparation_id`, `run_id`, `roast_date`, berat, suhu/RH, operator dan jam absolut.
5. Evaluasi melalui *held-out device/session/batch cohort*, lalu nested CV untuk memilih hiperparameter, jumlah fitur dan PCA. Jangan memilih fitur dengan skor set B70–B75 lalu mengklaim skor yang sama sebagai estimasi performa unbiased.

## 7. Berkas audit

- `../combined_30cycle_B70_B75_20261031/` — CSV gabungan, manifest dan karantina.
- `../combined_drift_B70_B75_20261031/` — drift, variasi dan per-record flags.
- `features_per_recording.csv` — tabel fitur setelah baseline correction per siklus.
- `global_zscore_mu_sigma_from_training.csv` — parameter scaler global untuk training.
- `sensor_ranking_train_cv_and_new_test.csv` — ranking sepuluh sensor dan holdout.
- `model_comparison_traincv_newtest.csv` — model, prepro pembanding dan confusion matrix.
- `new_test_per_class_recall.csv` — recall Light, Medium, Dark untuk setiap pipeline.
- `new_device_origin_roast_distribution.csv` — confounding device × origin × roast.

**Batas hasil:** skor bukan kinerja klasifikasi produksi; batch berbeda belum membuktikan spesimen independen, dan data lama tidak memiliki device_id.
