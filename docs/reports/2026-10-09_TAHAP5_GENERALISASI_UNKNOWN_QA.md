# Tahap 5 — Validasi lintas batch, ketahanan dan unknown

**Tanggal:** 9 Oktober 2026

**Repo:** Smart Coffee E-Nose v2, branch `wahyu`

**Keputusan:** **PASS engineering analisis offline**, **NO-GO validasi
prospektif / promosi model / deteksi unknown di perangkat**.

## 1. Cohort dan pengamanan data

- Input dibekukan dan diverifikasi SHA256 dari `stage2_v2` dan
  `stage3_v2`: **83 kandidat kopi** B32–B35.
- `CAW` dan **semua B37** adalah **udara bersih**, bukan kopi. Enam CSV
  ini tidak pernah dipakai melatih model roast, sesuai daftar pengecualian
  ber-hash; file asli tidak disentuh.
- Seluruh **21 kode sampel** muncul pada lebih dari satu batch;
  **empat sel kode–batch** mempunyai file berulang. Karena
  `physical_specimen_id`, asal produsen/sampel fisik, hari, urutan
  eksperimen, dan label roasting tidak diverifikasi, **LOBO tidak
  membuktikan independensi spesimen**.
- Data udara bersih berfitur valid **5/6**; `L-CAW_B34.csv`
  ditahan karena indeks purging 8 pada siklus 1 hilang.
- Setiap fold LOBO memiliki ketiga kelas `dark/light/medium`.
  Jumlah file per batch: B32=19, B33=19, B34=21, B35=24.

## 2. Protokol eksploratori

Dua pembanding yang dipilih setelah melihat Tahap 4: Random Forest dengan
82 fitur (`expanded82`) dan shrinkage LDA dengan 10 fitur
(`response10`). Penilaian LOBO menggunakan batch uji terpisah dan
fit preprocessing/model **hanya pada batch training**.
Keduanya memiliki `predict_proba`, tetapi angka probability adalah
**confidence yang belum dikalibrasi**.

Ambang abstain `0,0; 0,5; 0,6; 0,7; 0,8; 0,9` sudah
ditetapkan dalam skrip sebelum pengujian Tahap 5 dan **tidak dicari
yang terbaik** pada batch uji. Jika confidence di bawah ambang,
prediksi ditahan; angka coverage/risk yang dihitung hanya ilustrasi
konsekuensi ambang, **bukan threshold yang disetujui untuk perangkat**.

Validasi tambahan meliputi:

1. Confusion matrix/per-class F1 dan interval deskriptif dari seluruh
   **256 kemungkinan bootstrap 4 batch dengan replacement**. Empat
   cluster terlalu sedikit untuk klaim confidence interval yang kuat.
2. Probabilitas out-of-fold untuk 83 file per model; hasil label dan
   prediksi dicocokkan dengan output Tahap 4 yang sama.
3. Pemeriksaan clean-air surrogate: dua model dilatih pada **semua 83
   kopi kandidat**, lalu diujikan ke 5 udara bersih lolos QC. Sebagian
   CAW berasal dari batch yang sama dengan kopi, sehingga
   ini **bukan** tes independensi sesi/hari. Tidak ada *unknown-origin
   coffee* yang diuji.
4. Stress sintetis gain ADC seragam 0,90/0,95/1,05/1,10 di ruang
   fitur. Respons relatif dipertahankan di bawah asumsi
   `baseline ADC > 1`, sementara statistik ADC mentah
   serta slope/std diskalakan. Ini **bukan uji temperatur, aging
   sensor, carryover aroma, atau fisik aliran**.

## 3. Hasil lintas batch dan ketidakpastian

| Temuan | Random Forest 82 | LDA 10 |
|---|---:|---:|
| OOF benar pada 83 file | 45 | 45 |
| OOF salah pada 83 file | **38** | **38** |
| Rerata macro-F1 empat fold (Tahap 4) | 0,490 | 0,482 |
| Macro-F1 **pooled** dari seluruh 83 OOF | 0,512 | 0,539 |
| Bootstrap macro-F1 deskriptif p2,5–p97,5 (4 cluster) | 0,419–0,616 | 0,475–0,545 |

**Perbedaan rerata empat macro-F1 dan macro-F1 pooled**
adalah akibat definisi agregasi berbeda, bukan inkonsistensi prediksi.
Rentang bootstrap dengan hanya empat batch **tidak boleh** dianggap
jaminan generalisasi produk. Performa per kelas dan fold tersimpan pada
`results/stage5_validation_v1/class_metrics.csv`; kategori medium
paling lemah pada Random Forest.

## 4. Coverage versus risiko kesalahan

| Model dan ambang | Prediksi diterima | Prediksi salah yang tetap diterima | Risiko salah di antara diterima |
|---|---:|---:|---:|
| RF, tanpa abstain | 83/83 | 38 | 45,8% |
| RF, 0,6 | 36/83 | 15 | 41,7% |
| RF, 0,8 | 9/83 | 3 | **33,3%** |
| LDA, tanpa abstain | 83/83 | 38 | 45,8% |
| LDA, 0,6 | 48/83 | 22 | 45,8% |
| LDA, 0,8 | 20/83 | 6 | **30,0%** |

**Kesimpulan:** kenaikan threshold mengurangi jumlah prediksi yang
diterima, tetapi tidak menjamin risiko kesalahan rendah. Contoh
RF ambang 0,8 menerima hanya sekitar 10,8% observasi
dan sepertiganya masih salah. Belum layak sebagai aturan `unknown`.

## 5. Temuan prioritas P0 — udara bersih diprediksi sebagai kopi

Lima file udara bersih yang lolos QC:
`L-CAW_B33.csv`, `L-CAW_B35.csv`,
`M-CAW_B35.csv`, `L-MING_B37.csv`, `M-MING_B37.csv`.

**Kedua model memprediksi light roast pada 5/5 file**.
Pada threshold confidence **0,6**, **0/5 ditolak** oleh
Random Forest maupun LDA.

Rentang confidence uji udara bersih:
- RF: sekitar **0,789–0,908**.
- LDA: sekitar **0,695–0,963**.

Dengan kata lain, nilai confidence tinggi **tidak dapat dijadikan bukti
bahwa medium adalah kopi**. Pengujian ini justru memperlihatkan
kegagalan deteksi udara bersih pada dua model *roast-only* yang tertutup.
Namun lima file udara bersih **tidak membuktikan** tingkat false-positive
untuk berbagai kondisi penggunaan. **Unknown coffee origin** belum
memiliki kelas/dataset uji yang sah.

**Keputusan:** jangan menampilkan hasil roast dari model roast-only
sebagai deteksi kopi tanpa pemeriksaan keberadaan kopi yang
tervalidasi. Jangan memilih threshold 0,6 atau 0,8 sebagai solusi cepat.
Alur aman AI_TEST sebelum ada model yang lulus harus memakai status
**N/A / BELUM TERSEDIA**, bukan memaksakan klasifikasi.

## 6. Stress pergeseran gain sintetis

| Model | Gain 0,90 | 0,95 | 1,05 | 1,10 |
|---|---:|---:|---:|---:|
| RF: jumlah prediksi berubah dari baseline (83 file) | 17 | 10 | 8 | 13 |
| LDA: jumlah prediksi berubah | 0 | 0 | 0 | 0 |

LDA hanya memakai respons relatif yang tetap pada transformasi
gain ADC seragam dalam asumsi simulasi. **Ini bukan bukti bahwa LDA
robust terhadap drift fisik, gangguan antarsensor, atau perubahan
kelembapan**. RF 82 fitur memuat statistik mentah yang lebih
sensitif dalam simulasi ini.

## 7. QA dan kebijakan penutupan

Kode `scripts/stage5_validation.py` menghasilkan output snapshot
`results/stage5_validation_v1/`, dan
`scripts/test_stage5_validation.py` melakukan:
cek prediksi sama dengan Tahap 4, kebocoran label/CAW/B37, satu
prediksi OOF per file/model, kecocokan kelas, matriks probabilitas,
threshold monoton, hasil metrik, perubahan gain, hash fail-closed,
dan larangan menimpa output/raw. Detail perintah QA dan hasil
dicatat setelah regresi akhir.

**Rekap pengujian aktual:**

| Pemeriksaan | Hasil |
|---|---|
| `python scripts/test_stage5_validation.py` | **PASS** — parity dengan prediksi Tahap 4, threshold, clean-air, hash, pengujian negatif |
| `python scripts/test_stage4_model_benchmark.py` | **PASS** |
| `python scripts/test_stage3_feature_pipeline.py` | **PASS** |
| `python scripts/test_stage2_dataset_audit.py` | **PASS** |
| `python scripts/test_stage2_plot_provenance.py` | **PASS** |
| `python scripts/test_bench_stage1_passive_qa.py` | **PASS** |
| `python scripts/test_acquisition_suite.py` | **89/89 PASS** validitas struktur seluruh CSV B32+ |
| `python scripts/test_stage0_contract.py` dan `test_stage1_firmware_contract.py` | **PASS** |
| Kontrak Nextion | **PASS**, 12 halaman/23 event |
| PlatformIO `mega2560` dan `nextion_test` | **2/2 SUCCESS** |
| `python -m compileall -q scripts` dan `git diff --check` | **PASS**, peringatan normalisasi line-ending tidak fatal |

Pengujian software PASS **tidak** mengesahkan prosedur pengoperasian
fisik atau keberhasilan model di Raspberry Pi.

**Belum selesai:** validasi prospektif fisik, label roast/origin yang
terverifikasi, unknown origin kopi, detektor kopi vs udara bersih,
kalibrasi confidence pada data terpisah, threshold frozen sebelum
uji final, transisi sebelum 5 siklus, repeatability spesimen,
drift antarhari, dan uji Raspberry Pi/Nextion langsung.

**Gerbang Tahap 5:** analisis software **PASS**, tetapi **NO-GO
untuk penutupan ilmiah dan deployment**. Tahap 6 pemilihan model
final tetap terhambat. Sebelum data prospektif dikumpulkan,
tetapkan SOP dan `physical_specimen_id`, kelas kopi dan kelas
nonkopi yang benar, kondisi instrumen, threshold serta batas
risiko yang diterima; pisahkan data pengembangan dari data uji
final yang tidak disentuh selama tuning.
