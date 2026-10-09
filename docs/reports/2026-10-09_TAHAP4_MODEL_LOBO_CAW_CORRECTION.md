# Tahap 4 — Koreksi CAW/B37 dan benchmark baseline/challenger

**Tanggal:** 9 Oktober 2026

**Proyek:** Smart Coffee E-Nose v2 / RoastSense, branch `wahyu`.
**Status:** Implementasi/QA benchmark **offline**. **Model ilmiah dan perangkat BELUM DISETUJUI**.

## 1. Koreksi fakta dari operator (penting)

Operator menegaskan bahwa **kode `CAW` dan seluruh batch 37 adalah udara bersih**.
Data `L-CAW_B33.csv`, `L-CAW_B34.csv`, `L-CAW_B35.csv`, dan
`M-CAW_B35.csv` sebenarnya **bukan kopi** walau kolom UI `roast_level`
menyatakan light/medium. Dua file B37 juga merupakan udara bersih.
**Enam file** kini dicatat dan dilindungi oleh
`data/analysis/bench_only_exclusions.csv`, nama dan SHA256.
Tidak ada modifikasi pada CSV asli. `CAW` bukan origin kopi.

Audit `data/analysis/stage2_v2/`: **89 file B32+ total**, terdiri dari
**83 kandidat kopi B32–B35** dan **6 file udara bersih** (4 CAW dan 2 B37).
Jumlah kandidat per batch B32=19, B33=19, B34=21, B35=24; distribusi label
UI dark=28, light=28, medium=27. Semua file masih lulus validator **struktur**
MQ3, tetapi label/sesi fisik **belum terverifikasi**. Berkas CAW
`L-CAW_B34.csv` yang sebelumnya HOLD karena `sample_idx` hilang kini
dikecualikan berdasarkan medium fisiknya; bukan dipulihkan sebagai kopi.

Fitur baru `data/processed/stage3_v2/`: **83 vektor valid**, dengan 62
fitur legacy, 82 fitur expanded dan tujuh kelompok ablation tetap.
Snapshot lama `stage2/` dan `stage3_v1/` **historis, tidak boleh lagi
dipakai untuk evaluasi kopi**.

## 2. Desain benchmark yang dijalankan

- **Target eksploratori:** klasifikasi roast `dark/light/medium` dari label
  UI, *bukan* prediksi asal kopi atau deteksi udara bersih.
- **Protokol:** 4 fold Leave-One-Batch-Out; B32, B33, B34, B35 masing-masing
  menjadi batch uji sekali; 1 file = 1 observasi, tidak membagi siklus.
- **Input:** hanya fitur `f_*`, tanpa `source_file`, `sample_id`,
  `origin`, `batch_id`, hash atau label dalam matriks `X`.
- **Tujuh grup fitur:** response10, response20, dynamic30,
  dynamic32_environment, raw_collect10, legacy62, expanded82.
- **Delapan baseline/challenger:** Dummy prior, regresi logistik L2,
  LDA shrinkage, SVM linear dan RBF, k-NN, Random Forest, ExtraTrees.
  Konfigurasi tetap tanpa grid-search. Scaler untuk model sensitif skala
  berada **di dalam pipeline per fold**.
- **224 evaluasi model pada fold** (7 grup × 8 model × 4 batch),
  **4.648 prediksi** yang dapat dilacak per file.

## 3. Hasil benchmark (bukan performa akhir)

| Konfigurasi, peringkat deskriptif | Fitur | Mean macro-F1 empat batch | Mean balanced accuracy |
|---|---:|---:|---:|
| Random Forest + expanded82 | 82 | **0,490** | **0,545** |
| Shrinkage LDA + response10 | 10 | **0,482** | **0,544** |
| SVM RBF + dynamic30 | 30 | 0,475 | 0,511 |
| SVM RBF + dynamic32_environment | 32 | 0,465 | 0,500 |
| Random Forest + dynamic32_environment | 32 | 0,456 | 0,508 |
| Dummy prior (kontrol dasar) | — | 0,163 | 0,333 |

**Sebaran batch untuk Random Forest expanded82:**

| Batch uji | File uji | Macro-F1 | Balanced accuracy |
|---|---:|---:|---:|
| B32 | 19 | 0,655 | 0,675 |
| B33 | 19 | 0,577 | 0,619 |
| B34 | 21 | **0,344** | **0,429** |
| B35 | 24 | **0,383** | **0,458** |

Peringkat tertinggi berbeda hanya ~**0,008 macro-F1** dari LDA 10 fitur.
Tanpa uji ketidakpastian atau set prospektif independen, hasil ini
**tidak cukup** untuk menyatakan fitur 82 dimensi unggul.
Penurunan di B34/B35 menunjukkan keterbatasan generalisasi antarbatch.
Metrik per kelas, confusion matrix dan seluruh prediksi tersimpan dalam
`results/stage4_lobo_v2/`.

## 4. QA, kebocoran, dan batas metode

Tes `scripts/test_stage4_model_benchmark.py` memeriksa bahwa:
(1) file CAW/B37 tidak masuk; (2) SHA256 manifest Tahap 2 dan pengecualian
cocok; (3) label/batch metadata sesuai Stage2 dan tidak masuk `X`;
(4) train/test batch tidak bertumpang tindih; (5) hasil prediksi dan metrik
dapat diulang; (6) output tidak menimpa hasil sebelumnya;
(7) manifest/hash yang berubah, kelas hilang, dan metadata label bocor
memicu penolakan.

**Klaim yang diperbolehkan:** benchmark per-fold yang reproduksibel pada
label UI kandidat, sebagai pemetaan opsi algoritma.

**Tidak boleh diklaim:** generalisasi spesimen fisik independen, klasifikasi
roast yang tervalidasi, kemampuan mendeteksi kopi tidak dikenal, kalibrasi
confidence, atau akurasi Raspberry Pi pada alat.
Pemeringkatan model dari fold yang sama menimbulkan *selection bias*,
sekalipun model per fold tidak dilatih pada batch ujinya. Validasi Tahap 5
memerlukan sumber label/spesimen dan batch baru prospektif yang tidak
dipakai memilih model.

## 5. Keputusan dan tindak lanjut

### Rekap pengujian akhir

| Pemeriksaan | Hasil |
|---|---|
| `python scripts/test_stage4_model_benchmark.py` | **PASS**: LOBO, determinisme hasil, hash/input, metadata dan kelas hilang, label leakage |
| `python scripts/test_stage3_feature_pipeline.py` | **PASS** |
| `python scripts/test_stage2_dataset_audit.py` | **PASS** |
| `python scripts/test_stage2_plot_provenance.py` | **PASS** |
| `python scripts/test_bench_stage1_passive_qa.py` | **PASS**, enam entry exclusion hash valid |
| `python scripts/test_acquisition_suite.py` | **89/89 PASS** validator struktur umum, termasuk CAW/B37 sebagai raw valid |
| `python scripts/test_feature_pipeline.py` dan `test_stage0_contract.py` / `test_stage1_firmware_contract.py` | **PASS** |
| Kontrak HMI Nextion | **PASS** (12 halaman, 23 event) |
| `pio run -e mega2560 -e nextion_test` | **2/2 SUCCESS** |
| `python -m compileall -q scripts` dan `git diff --check` | **PASS** |

Pemeriksaan file mentah/label tidak berarti sertifikasi fisik. Hasil
`results/stage4_lobo_v2/` hanya berupa data benchmark dan konfigurasi;
tidak ada model, kalibrasi, atau parameter yang dikirim ke Raspberry Pi.

**Tahap 4 engineering: selesai untuk benchmark awal, status eksploratori.**
**NO-GO promosi model** sampai identitas spesimen, kondisi pengambilan dan
label roasting dikonfirmasi, lalu uji prospektif, ketahanan drift, unknown
dan kalibrasi dilakukan.

Prioritas Tahap 5: periksa kekurangan kelas/origin per batch, repeatability
pada spesimen yang sama dan pada spesimen baru, evaluasi reject/unknown
dengan data udara bersih yang dikumpulkan secara terkontrol sebagai kelas
negatif terpisah (bukan kopi), dan tetapkan metrik penerimaan sebelum
menguji data prospektif. Jangan memilih hyperparameter atas B32–B35 yang
telah dilihat sebagai satu-satunya bukti final.
