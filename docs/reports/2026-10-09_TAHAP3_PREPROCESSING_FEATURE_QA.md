# Tahap 3 — Preprocessing dan ekstraksi fitur MQ3 yang dapat direproduksi

**Tanggal:** 9 Oktober 2026. **Repo:** Smart Coffee E-Nose v2, branch `wahyu`.

## 1. Tujuan dan keputusan teknis

Menyiapkan fitur yang **identik secara matematis pada CSV training dan data sensor dalam memori** (calon host Raspberry Pi), dengan input dataset dibekukan menurut SHA256 Tahap 2. Tidak ada perubahan raw, firmware, Nextion/TFT, COM5, atau artefak model. Seluruh keluaran **kandidat riset, tidak ada training atau inference produksi**.

Kode utama: `scripts/extract_b32_features.py::extract_sensor_features` (fungsi murni reusable), `scripts/stage3_feature_pipeline.py` (kontrak manifest dan penyimpanan), `scripts/test_stage3_feature_pipeline.py` (QA negatif dan reproduksi).

## 2. Temuan data yang baru

| Pemeriksaan | Hasil |
|---|---|
| Kandidat B32–B35 dalam manifest Tahap 2 | **87 file** |
| File lulus semua pemeriksaan fitur ketat | **86** |
| File ditahan | **1: `L-CAW_B34.csv`** |
| Masalah spesifik | Siklus 1 purging tidak memiliki `sample_idx=8` (tercatat 24 frame, rentang 1–25). CSV lolos validator umum Tahap 2, tetapi **tidak lolos kontinuitas strict Tahap 3**. |
| File benchmark B37 udara bersih | **2, keduanya dikecualikan** |
| Cohort fitur diterima per batch | **B32=19, B33=20, B34=21, B35=26** |
| Distribusi label UI belum terverifikasi | **light=30, medium=28, dark=28** |
| Fitur lama / eksploratori diperluas | **62 / 82** |
| Nonfinite pada fitur diterima | **0** |
| Kelompok kandidat ablation | **7**, telah ditentukan tanpa meninjau performa model |

**Catatan krusial:** artefak lama 86 baris dan artefak baru 86 baris **tidak memiliki unit akuisisi yang persis sama**. Cohort baru **menambahkan `L-MING_B32_20261009_172056.csv` dan menahan `L-CAW_B34.csv`**. Perbandingan terhadap 85 file dengan nama+SHA sama memperlihatkan parity 62 fitur legacy (selisih floating point maksimal sekitar `4,8e-12`). Tidak ada raw yang dikoreksi secara diam-diam.

## 3. Hasil preprocessing dan ablation design

- Menggunakan fungsi `extract_sensor_features` yang **tidak menerima kolom label** dan memeriksa lima siklus, urutan purge→collect, indeks per fase, timestamp meningkat, semua kanal ADC 10 sensor, dan kelengkapan SHT30. Event-only row historis dikeluarkan **hanya dalam memori**.
- Membandingkan **7 grup ukuran 10/20/30/32/10/62/82**, dari respons relatif saja sampai statistik temporal dan collecting mean mentah. Ini **desain ablation**, bukan pemeringkatan akurasi; belum dilakukan model fitting.
- `feature_quality.csv` merangkum rentang dan dispersi fitur di 86 file secara **deskriptif**, tidak boleh digunakan untuk memilih fitur berdasarkan seluruh data sebelum cross-validation. Pada snapshot ini **0 fitur memiliki SD global kurang dari 1e-9**, tetapi itu tidak membuktikan masing-masing fitur informatif.
- Normalisasi per siklus hanya menggunakan **baseline dari akuisisi yang sama**. Tidak ada `StandardScaler`, PCA, imputasi global, pembelajaran parameter, atau seleksi fitur pada seluruh dataset. Tahap 4 harus fit semua transformasi semacam itu **di dalam training fold**.
- Risiko ilmiah penting: 82 fitur untuk 86 file sangat rawan overfitting. Varian ringkas `response10` dan `dynamic30` menjadi pembanding a priori; fitur ADC mean mentah bisa sensitif terhadap baseline/gain, dan 5 titik purging terakhir perlu dibuktikan merepresentasikan baseline fisik yang stabil.

Kontrak lengkap, nama file, dan prosedur regenerasi ada pada `data/processed/STAGE3_FEATURE_CONTRACT.md`. Snapshot hash dan urutan fitur ada pada `data/processed/stage3_v1/snapshot.json`.

## 4. QA / gerbang kegagalan aman

Skenario otomatis `test_stage3_feature_pipeline.py` menguji: pembekuan hash raw dan manifest, pengecualian B37, input CSV vs frame sensor tanpa label, reproducibility byte-for-byte, output sudah ada (tidak overwrite), larangan menulis raw, sampel purging yang hilang, ADC NaN/out-of-range, SHT30 hilang, dan manifest bench dipalsukan sebagai kopi.

Tes kompatibilitas `test_feature_pipeline.py` pada formula 62 fitur existing tetap PASS; seluruh 87 kandidat diinspeksi dengan QA ketat sebelum 86 diterima.

**Hasil QA akhir yang benar-benar dijalankan — PASS:**

| Perintah/tes | Hasil |
|---|---|
| `pio run -e mega2560 -e nextion_test` | Dua environment SUCCESS |
| `verify_nextion_atmega_contract.py` | PASS 12 halaman/23 event, `Serial2` 9600 |
| `test_acquisition_suite.py` | PASS **89/89 CSV B32+** untuk validator canonical |
| `audit_b32_dataset.py` | PASS **87/87 CSV B32–B35** untuk struktur, termasuk satu file dengan gap sample_idx yang lolos kriteria lama |
| `test_feature_pipeline.py` | PASS kompatibilitas legacy 62 fitur |
| `test_stage3_feature_pipeline.py` | PASS fixture positif/negatif, snapshot, parity dan reproduksi byte-identik |
| `test_stage0_contract.py`, `test_stage1_firmware_contract.py` | PASS |
| `test_bench_stage1_passive_qa.py`, `test_stage2_dataset_audit.py`, `test_stage2_plot_provenance.py` | PASS |
| `python -m compileall -q scripts`, `git diff --check` | PASS (peringatan normalisasi LF→CRLF tidak fatal) |

**Perbedaan penting kriteria:** validator canonical mengizinkan satu frame purging hilang sejauh tidak melanggar batas minimal jumlah data/siklus. Tahap 3 menuntut `sample_idx` lengkap dan menahan `L-CAW_B34.csv`. Oleh sebab itu **89/89 PASS canonical tidak bertentangan dengan 1 HOLD Stage 3**. Operasi fisik, validasi label/spesimen dan training **tidak dijalankan**.

## 5. Kriteria penutupan

**PASS software Tahap 3:** ekstraksi deterministik 86/86 file lolos QC, satu ditahan secara eksplisit dan terlacak hash; output 62/82 fitur, urutan konsisten, tidak ada NaN/Inf, raw dan B37 terlindungi, serta parity CSV/in-memory diuji.

**TERBUKA / bukan klaim selesai riset AI:** validasi fisik origin/roast/independensi spesimen dari Tahap 2; kajian kesesuaian baseline 5 titik purging; benchmark grup fitur dengan split group tanpa kebocoran pada Tahap 4–5; data prospektif, model card, runtime Raspberry Pi dan inference E2E.
