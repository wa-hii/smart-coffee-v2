# Audit independen kelayakan model AI Smart Coffee E-Nose (Stage 10)

**Tanggal:** 14 Oktober 2026. **Keputusan:** `NO_GO_NOT_READY_FOR_DEVICE`.
**Yang dilakukan:** audit SHA256/data/features, re-evaluasi out-of-fold,
kalibrasi deskriptif, sensitivitas terhadap grup, kelayakan origin,
uji udara bersih, dan pemeriksaan kesetaraan fitur training–runtime.

**Yang sama sekali tidak dilakukan:** membuka USB/COM5, flashing,
memodifikasi firmware RC2/Nextion, menekan START, mengulang G3,
mengaktifkan aktuator, memodifikasi CSV asli, atau memasang model.
Firmware yang sudah lolos G3 tetap pada tag RC2.

## 1. Data dan batas inferensi

- 83 **akuisisi CSV** kandidat B32–B35 (28 dark, 28 light,
  27 medium), 21 kombinasi kode sample_id, empat batch dan
  **sembilan nama origin**. Satu CSV terdiri dari lima siklus
  berkorelasi; unit evaluasi **satu akuisisi**, bukan 5 atau 150
  observasi independen.
- Metadata label roast dan origin berasal dari pencatatan pengguna
  saat pengambilan sampel, **belum diaudit terhadap spesimen fisik,
  pengukuran tingkat sangrai, provenance lot, atau sertifikat origin**.
- Tidak ada `physical_specimen_id`, `roast_batch_id`, pengukuran
  terstruktur hari/session/urutan/replikasi independen untuk
  mengisolasi drift dan carryover. Meski Leave-One-Batch-Out
  memisahkan file pada B32–B35, spesimen atau sesi sebenarnya
  **mungkin sama/terkorelasi** antarbatches.
- Semua angka hasil adalah **eksploratori pada dataset yang telah
  terlihat**, bukan estimasi prospektif blind holdout dan bukan
  bukti kinerja produksi. Benchmark Stage4 sebelumnya mencoba
  7 grup × 8 model (224 fit); peringkat tertinggi mengalami
  *model selection optimism*.
- Manifest Stage3, Stage2 dan probabilitas Stage5 dibaca dari
  berkas frozen; keutuhan filename/SHA256, label, pemisahan
  batch, kelas dan probabilitas diperiksa oleh audit Stage10.

## 2. Roast Level — hasil yang dapat dibuktikan

| Evaluasi | RF (82 fitur) | LDA (10 fitur) |
|---|---:|---:|
| LOBO antar batch: benar/total | 45/83 | 45/83 |
| LOBO accuracy | 54,22% | 54,22% |
| LOBO pooled macro-F1 | 0,5118 | 0,5389 |
| Leave-one-sample-code-out accuracy | 49,40% | 51,81% |
| Leave-one-origin-out accuracy (roast saja) | 53,01% | 53,01% |
| Max-confidence ECE, **diagnostik saja** | 0,1839 | 0,1673 |

Angka terbaik Stage4 yang terdokumentasi adalah **RF expanded82,
mean fold macro-F1 0,4898**. Rata-rata macro-F1 empat fold tidak
sama dengan pooled macro-F1 di tabel; jangan menyamakan keduanya.
Kedua kandidat dipilih setelah melihat Stage4; hasil pada dataset
yang sama **bukan** final held-out test.

### Probabilitas belum layak muncul pada LCD

Pada threshold yang **diperiksa secara deskriptif, bukan
dituning/diotorisasi** dari pengujian:

| Prediksi dengan confidence ≥80% | RF | LDA |
|---|---:|---:|
| Dianggap dapat diprediksi | 9/83 | 20/83 |
| Salah meski confidence tinggi | **3** | **6** |
| Akurasi subset | 66,7% | 70,0% |

Confidence mentah `predict_proba` bukan probabilitas kesalahan
terkalibrasi. Hasil ini tidak memenuhi dasar untuk menampilkan
misalnya “Roast Probability 85%” kepada pengguna. Ukuran sampel
subset sangat kecil, sehingga akurasi subset tidak stabil.

## 3. Coffee Origin — belum tervalidasi

Analisis Stage10 melakukan perbandingan baru **untuk diagnosis,
bukan pemilihan model baru** pada sembilan nilai metadata origin
dengan split antar-batch yang sama:

| Algoritma | Benar/83 | Accuracy | Macro-F1 |
|---|---:|---:|---:|
| Random Forest expanded82 | 21/83 | 25,30% | 0,1639 |
| Dummy prior | 12/83 | 14,46% | 0,0458 |

**Origin tidak cukup terwakili:** dua dari sembilan origin
memiliki hanya satu kelas roast, beberapa origin hanya dua
hingga tiga akuisisi, dan hanya tujuh origin memiliki ≥5
akuisisi. Bahkan jika angka origin lebih tinggi, validasi
provenance/lot secara independen tetap mutlak dibutuhkan.
Origin classification belum memiliki artefak model approved.

## 4. Udara bersih, unknown rejection dan open-set safety

Lima pengambilan udara bersih yang lolos kontrak fitur tidak
pernah ikut training kopi. Sebagai **uji surrogate terhadap
model closed-set tanpa penolakan unknown**, kedua model
memaksa **5/5 udara bersih menjadi `light`**:

- RF: confidence tertinggi 0,789–0,908 pada udara bersih.
- LDA: confidence tertinggi 0,695–0,963 pada udara bersih.
- Aturan abstain 0,6 tidak menolak satu pun dari lima udara itu.

Ini **bukan** estimasi false-positive rate suatu detector yang
belum ada; hasilnya justru membuktikan closed-set classifier
tidak boleh langsung diinterpretasikan sebagai detektor kopi.
Belum tersedia pengujian blind kopi asal tak dikenal atau VOC
nonkopi. Kelas `unknown` / `no coffee` dan deteksi kondisi
sensor invalid wajib dipisahkan dari pengklasifikasi roasting.

## 5. Kontrak fitur runtime berbeda

Source `src/inference.cpp` lama menggunakan mean dan maksimum
`NUM_SENSORS=10` (total **20 fitur** bila flag model diaktifkan),
sedangkan Stage3 terbaru `expanded82` menggunakan **82 fitur**
agregat lima siklus; LDA memakai `response10`. Ini **belum
memiliki uji kesetaraan feature-by-feature pada input perangkat
yang sama**. `USE_ON_DEVICE_INFERENCE=0` tetap aman dan tidak
diubah. `models/feature_list.json` lama masih menyebut sensor
**MQ9**, yang tidak ada pada kontrak sepuluh ADC firmware RC2
(MQ3 digunakan). Jangan memperlakukan artefak `.joblib` lama
sebagai model produksi kompatibel. Firmware RC2 juga belum
menyediakan model origin/probability yang tervalidasi.

## 6. Gerbang promosi model — **harus dilalui sebelum integrasi**

1. **Ground truth dan provenance:** identitas fisik kopi dan
   lot/asal ditelusuri; kelas roast diverifikasi dengan
   metode independen, bukan hanya pilihan di HMI; catat
   tanggal, operator, sesi, firmware, warm-up, suhu/RH,
   pembersihan chamber serta penanda spesimen. Pastikan
   `sample_id` tidak menyamar sebagai ID spesimen independen.
2. **Pemisahan sumber data:** kelompokkan seluruh pengulangan
   atas spesimen/lot dan sesi yang sama dalam split yang sama.
   Siapkan data *train*, *calibration*, dan **prospective blind
   final holdout** terpisah secara fisik. Bekukan model,
   preprocessing, threshold serta metrik sebelum membuka
   final holdout. Cukupkan semua kelas, origin, dan hari.
3. **Roast:** uji macro-F1, balanced accuracy, confusion
   matrix, error tiap kelas dan uncertainty per spesimen.
   **Usulan target penerimaan proyek** (bukan baku standar):
   macro-F1 ≥0,85, balanced accuracy ≥0,85, dan recall
   setiap kelas ≥0,80 pada final blind holdout yang representatif.
   Pelaporan interval ketidakpastian tetap wajib; ambang dapat
   dirundingkan sebelum pengumpulan final set, tidak setelahnya.
4. **Origin:** definisikan sembilan label yang benar-benar
   berbeda, audit semantik kode dan cakupan roasting.
   Origin harus dievaluasi terpisah dengan macro-F1,
   recall per origin dan matriks kebingungan. Untuk origin
   yang belum memiliki cukup spesimen independen, tampilkan
   `N/A` daripada memaksa salah satu origin.
5. **Open-set:** uji kopi tidak dikenal, udara bersih,
   VOC nonkopi dan kondisi sensor error dalam sesi fisik
   berbeda; tentukan target sensitivity/false-acceptance,
   coverage serta aturan abstain berdasarkan risiko dan
   besarnya set validasi sebelum final holdout.
6. **Kalibrasi:** latih calibrator tanpa mengintip blind
   holdout (mis. pipeline calibration set terpisah/group-aware),
   uji Brier score / reliabilitas / ECE per kelas dan
   *risk–coverage*. Persentase LCD baru boleh muncul bila
   kalibrasi/probabilitas sesuai data baru dan dapat ditolak
   saat out-of-distribution.
7. **Runtime parity:** satukan schema fitur host/model secara
   eksplisit; verifikasi nilai 5-siklus ADC yang identik
   menghasilkan fitur dan prediksi yang identik pada pipeline
   validasi serta runtime target. Pantau durasi, memori,
   checksums dan handling invalid data. Ini tahap perangkat
   nanti, **tanpa mengubah firmware RC2 sekarang**.
8. **QA independen + approval operator:** review reproducible
   hash snapshot/prediksi/label/final holdout; model baru
   tidak dipromosikan hanya karena Stage10 test script PASS.

## 7. Evidence dan reproduksibilitas

- Program: `scripts/stage10_model_readiness_audit.py`.
- Regression negative tests: `scripts/test_stage10_model_readiness.py`
  (mutasi label/batch, frame duplikat, probabilitas negatif,
  prediksi inkonsisten, perlindungan output dan raw).
- Hasil turunan: `results/stage10_readiness_20261014_v2/`:
  `summary.json`, `roast_confidence_diagnostics.csv`,
  `origin_coverage.csv`, `group_holdout_sensitivity.csv`.
- Tahap sebelumnya: Stage4/Stage5 regression dan Stage6
  fail-closed PASS, tetap ada **0 model promoted**.

**FINAL:** `NO_GO_NOT_READY_FOR_DEVICE` berlaku pada seluruh
klaim klasifikasi roasting, origin, dan roast probability.
Seluruh teks layar Nextion **tetap `N/A`** sampai persyaratan
yang dapat diaudit terpenuhi. G3 fisik sebelumnya **tetap PASS
untuk integritas akuisisi**, tidak perlu diulang pada tahap ini.
