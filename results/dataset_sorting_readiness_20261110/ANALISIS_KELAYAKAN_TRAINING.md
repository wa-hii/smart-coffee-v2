# Evaluasi kelayakan dataset sorting untuk training AI Smart Coffee E-Nose v2

**Tanggal pemeriksaan:** 10 November 2026. **Input:** `data/dataset sorting/{a,b,c}/{kept,maybe,excluded}`. Semua input CSV dibaca tanpa modifikasi. **Keputusan: layak untuk uji coba model, belum siap menjadi dataset pelatihan final tanpa pembersihan QC dan perbaikan desain pengambilan.**

## Ringkasan temuan

| Cohort | kept | maybe | excluded | total |
|---|---:|---:|---:|---:|
| a (B60–B69) | 64 | 28 | 19 | 111 |
| b (B70–B75) | 96 | 18 | 12 | 126 |
| c (B80–B90) | 72 | 2 | 55 | 129 |
| **Total** | **232** | **48** | **86** | **366** |

Audit lengkap memeriksa 900 sampel, 30 siklus, urutan fase purging 25/collecting 5, nama dan metadata CSV, interval waktu serta ADC. **361 CSV VALID secara struktur, 5 INCOMPLETE**. Dari 232 `kept`, **4 incomplete salah ditempatkan**; tinggal **228 kept valid**, dan **227 identitas origin–roast–batch unik**, karena satu batch lama mempunyai dua rekaman valid.

**Empat incomplete di kept (wajib keluar dari training):**

- `b/kept/L-MING_B75_8d9adafb31744b538fa663e1fef1b18c_INCOMPLETE.csv` (893 titik)
- `b/kept/L-TOR_B75_ad0a30d7ece544609ad4efcb742504e2_INCOMPLETE.csv` (892 titik)
- `b/kept/M-GAW_B75_bc7301af72124e398d4edb8626b1836e_INCOMPLETE.csv` (891 titik)
- `b/kept/M-TEM_B73_a00116bc923c42b888da60e07fad130c_INCOMPLETE.csv` (888 titik)

**Satu incomplete tambahan ada di maybe:** `b/maybe/M-TOR_B70_3328c9859044444ba86977be746831e2_INCOMPLETE.csv` (892 titik).

**Dua file kept memakai identitas origin–roast–batch yang sama:** `a/kept/M-TEM_B62.csv` dan `a/kept/M-TEM_B62_20261019_175906.csv`. Kedua sinyal berbeda; **jangan menghitungnya sebagai spesimen independen** tanpa bukti persiapan sampel dan sesi pengukuran. Pilih satu representatif untuk evaluasi awal dan catat keduanya dalam manifest. Kombinasi identitas bukan bukti kemandirian spesimen fisik.

**86/86 file excluded valid secara struktur.** Ini **bukan bukti** semuanya layak untuk training: kategori `excluded` mungkin berdasarkan respons sensor lemah, outlier atau gangguan eksperimen; tetapi **alasan sorting belum terdokumentasi dalam CSV**. Keputusan eksklusi sebaiknya berupa aturan QA yang dapat diaudit dan ditetapkan tanpa mengetahui target kelas.

## Bukti kemungkinan manfaat dan bias sorting

Pada kelompok c, median absolut respons fase collecting−purging (sensor TGS822):

| Status | Jumlah CSV | Median respons absolut (ADC) | File dengan respons <=5 ADC | Median rasio drift/respons |
|---|---:|---:|---:|---:|
| Kept | 72 | **184,15** | **1** | 0,71 |
| Maybe | 2 | 261,50 | 0 | 0,69 |
| Excluded | 55 | **1,00** | **29** | 5,88 |

Artinya sorting c memang memisahkan banyak rekaman dengan respons TGS822 sangat lemah; kemungkinan keputusan sebagian didukung kualitas sinyal. **Namun 26 dari 55 file c/excluded memiliki respons TGS822 >5 ADC** sehingga tidak boleh ditolak hanya dari satu ambang tersebut; bandingkan kanal lain, baseline, perangkat, aliran/pompa, dan preparasi. Data outlier yang benar-benar mencerminkan variasi fisik tetap penting bagi generalisasi.

Di kelompok a/b, `excluded` juga lengkap secara struktur. Contoh: pada b, median respons TGS822 `excluded` justru sekitar 253,85 ADC, lebih besar daripada `kept` sekitar 177,45 ADC. Karena itu **ambang satu sensor tidak menjelaskan seluruh keputusan manual sorting**.

## Integritas data dan relasi dengan arsip sebelumnya

- **366 SHA-256 unik dan 366 fingerprint sinyal unik dalam sorting**, jadi tidak ada salinan identik di folder tersebut.
- **232 fingerprint sinyal** cocok dengan dataset valid B60–B75 yang telah digabungkan sebelumnya: semua 111 file a dan 121 file b yang lengkap; **129 file c** adalah sinyal baru yang belum ada di arsip gabungan sebelumnya.
- Hanya **121 byte-hash** cocok dengan arsip lama: CSV kelompok a memiliki sinyal sama tetapi serialisasi byte berbeda, misalnya akhir baris LF vs CRLF. Perbedaan checksum byte **tidak berarti 111 pengambilan baru**. Contoh `a/kept/D-CAT_B60.csv` dan arsip valid lama memiliki semua nilai kolom sama.
- File sumber yang belum punya alasan sorting/dokumen `quality.json` asli harus diperlakukan sebagai **provenance terbatas**. Pada kelompok b, sebagian metadata receiver tersedia di `data/raw/B70..B75/*.quality.json` dan mendeteksi lima incomplete.

## Risiko utama: label, origin, perangkat, dan waktu saling berkaitan

Data kept valid setelah satu identitas batch ganda disisihkan mempunyai **227 rekaman terpilih**. Tetapi hanya **199** dari enam origin yang memiliki tiga tingkat roasting dalam gabungan cohort (CAT, GAW, GRB, MING, TEM, TOR). Origin GAY hanya Light, MUK hanya Medium, RAT hanya Dark sehingga **jangan dimasukkan secara membabi buta** untuk klasifikasi roasting lintas-origin: model bisa menggunakan identitas origin sebagai jalan pintas.

Distribusi data kept group c (B80–B90) belum seimbang:

| Origin | Light | Medium | Dark |
|---|---:|---:|---:|
| CAT | 6 | 7 | 2 |
| GAW | 0 | 5 | 6 |
| GRB | 0 | 11 | 5 |
| TEM | 3 | 11 | 2 |
| TOR | 5 | 0 | 3 |
| MUK | 0 | 6 | 0 |

**Tidak ada MING di kept group c.** Untuk CAT/TEM, Dark hanya dua rekaman; grup GAW/GRB tidak memiliki Light, TOR tidak memiliki Medium. Akibatnya, satu skor test c sulit mewakili generalisasi di semua kombinasi origin–roasting.

Data b masih memiliki **device-label confounding**: dari 16 kombinasi origin×device yang memiliki data kept valid, **12 hanya memuat satu roasting**, 4 memuat dua, dan **tidak satu pun memuat semua tiga roasting**. Contoh CAT Light hanya pada ALAT_1; CAT Dark/Medium hanya ALAT_3. Sensor bisa mengenali perbedaan instrumen, bukan aroma. Pada kelompok a dan c tidak ada `device_id` yang bisa dipulihkan dari CSV dalam audit ini (136 rekaman kept valid berstatus `UNKNOWN`). Perlu ledger alat/sesi/sampel.

Kondisi lingkungan juga tidak seragam: rerata suhu kelompok c/kept Light sekitar **32,95°C** sedangkan Dark **30,30°C** dan Medium **30,62°C**. Suhu/RH harus dikendalikan, dicatat, dan dijadikan *negative control* agar model tidak mengambil jalan pintas.

## Benchmark model awal (diagnostik, bukan akurasi produksi)

Menggunakan **133 rekaman** kept+valid dari kelompok a+b dengan enam origin L/M/D untuk training dan **66 rekaman** kept+valid dari kelompok c sebagai temporal holdout. Seluruh satu CSV = satu observasi. Sebelum model, setiap sensor direpresentasikan dengan tiga fitur respons collecting terhadap baseline lokal purging tiap siklus (median 5 titik akhir purging, rerata collecting 5 titik, ringkasan per rekaman). Scaler Z-score hanya di-*fit* pada training untuk setiap model/fold. Validasi internal training memakai *leave-one-origin-out*, testing c tidak digunakan untuk menghitung μ/σ.

| Fitur dan model | CV origin pada training | Test cohort c | Recall Light | Recall Medium | Recall Dark |
|---|---:|---:|---:|---:|---:|
| TGS822+TGS2602+TGS816, SVM RBF | 54,7% | **65,3%** | 92,9% | 52,9% | 50,0% |
| TGS822+TGS2602+TGS816, Logistic Regression L2 | 50,5% | 61,0% | 100% | 44,1% | 38,9% |
| 10 sensor, Logistic Regression L2 | 55,1% | 48,8% | 71,4% | 47,1% | 27,8% |
| 10 sensor, SVM RBF | 48,4% | 45,5% | 57,1% | 29,4% | 50,0% |
| Suhu+kelembapan saja, Logistic Regression | 47,2% | 42,0% | 50,0% | 20,6% | 55,6% |
| Dummy (prediksi kelas terbanyak) | 28,6% | 33,3% | 0% | 100% | 0% |

Semua angka utama menggunakan **balanced accuracy** (rata-rata recall kelas), kecuali kolom recall masing-masing kelas. Hasil diagnostik tertinggi (**65,3%**) **belum dapat dijadikan bukti kesiapan AI**, karena (a) kelompok c dikurasi secara manual dari sinyal, (b) distribusi origin–roasting c tidak lengkap, (c) tidak tersedia metadata perangkat c, (d) seleksi model/fitur dilakukan sebagai eksplorasi, dan (e) belum ada bukti setiap batch berasal dari preparasi kopi fisik independen. Nilai 65,3% merupakan hasil yang terlihat setelah perbandingan alternatif; bukan estimasi prospektif *unbiased*.

**Confusion matrix SVM 3 sensor pada c** (baris kelas sebenarnya dan kolom prediksi, urutan Light/Medium/Dark): `[[13,1,0],[12,18,4],[5,4,9]]`. Salah klasifikasi terbesar terjadi pada Medium yang dianggap Light dan Dark yang dianggap Light.

## Keputusan dan langkah perbaikan berurutan

1. **Jangan langsung menggunakan semua file `kept`.** Keluarkan empat incomplete dari kandidat; putuskan satu representatif untuk duplikasi M-TEM_B62 dan catat alasan pada manifest eksternal, tanpa mengubah file asli.
2. **Definisikan aturan sorting yang tertulis dan label-agnostik**: keutuhan 900 titik, keutuhan fase, tidak saturasi, uji blank/pompa, ketidakstabilan baseline berdasarkan *kontrol kosong*, respons terhadap sampel positif yang valid; jangan membuang data hanya karena kurva tidak sesuai urutan L/M/D yang diharapkan.
3. **Periksa kembali 47 maybe-valid dan 86 excluded-valid**. Prioritaskan 26 c/excluded dengan respons TGS822 >5 ADC serta semua file a/b excluded karena struktur mereka valid. Jangan otomatis diterima: tetap mungkin ada gangguan alat/chamber.
4. **Catat `device_id`, `preparation_id`, `session_id`, jam sebenarnya, urutan sampel, berat kopi, grinding, roast date, suhu/RH dan blank run** pada setiap akuisisi baru. Identitas batch bukan bukti spesimen fisik baru. Semua origin×roast harus diukur pada setiap ALAT_1/2/3 jika tujuan model lintas perangkat.
5. Untuk eksperimen: **raw 30 siklus → QC lokal → baseline correction per siklus → ekstraksi fitur per CSV → split berdasarkan sesi/perangkat/spesimen → global Z-score yang hanya di-fit pada training → PCA opsional (fit training) → model**. Bandingkan Logistic Regression, SVM RBF dan Random Forest, laporkan recall per kelas.
6. **Jangan menggunakan c/kept sebagai satu-satunya test final**. Siapkan prospektif batch berikutnya dengan protokol sama, tetapi label/sesi/perangkat seimbang. Simpan set itu tersegel sampai pemilihan model selesai.
7. Pisahkan dua tujuan yang berbeda: **roasting classifier** (fokus enam origin L/M/D lengkap) dan **origin classifier** (butuh setiap origin dengan banyak roast agar tidak tertukar roasting dengan origin).

## Berkas hasil dan interpretasi

- `all_csv_audit.csv`: audit lengkap 366 file, status manual, status QC, fingerprint, status perangkat dan sumber.
- `sensor_signal_metrics.csv`: indikator phase response, drift, clipping per sensor–CSV, semua kelas sorting.
- `class_distribution_all_status.csv`, `kept_cohort_class_distribution.csv`: ketimpangan kelas per origin/cohort.
- `sensor_drift_by_cohort_status.csv`, `environment_by_cohort_status_roast.csv`: perbandingan kondisi sensor dan lingkungan.
- `cohort_c_holdout_model_diagnostic.csv`: benchmark per pipeline, train CV dan holdout c.
- `cohort_c_holdout_per_origin.csv`: rincian performa per origin (berhati-hati pada origin yang kelasnya tidak lengkap).
- `summary.json` dan `model_diagnostic_summary.json`: hitungan dan metodologi yang dapat diuji ulang.

**Batas keputusan:** audit CSV mendeteksi kesesuaian struktur 30 siklus, bukan kebenaran label kopi, kondisi sensor fisik, reliabilitas pompa, atau kemandirian spesimen. Semua keputusan eksklusi atas dasar respons gas tetap membutuhkan metadata eksperimen dan pengujian kontrol.
