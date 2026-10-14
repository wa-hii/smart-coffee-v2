# Stage 11 — Dataset provenance, partisi independen dan protokol blind test

**Tanggal:** 14 Oktober 2026. **Status:** pipeline dan QA **PASS offline**;
**blind prospective final test = BLOCKED (belum ada data baru)**;
**promosi model = NO-GO**.

## I. Lingkup dan batas tindakan

Seluruh pekerjaan **hanya** kode evaluasi, metadata turunan, dan
perbandingan model development. Firmware ATmega RC2 tidak diubah,
tidak ada USB/COM5/SSH serial, pengoperasian Nextion, G3 ulang,
pompa, kalibrasi, atau deployment model. `data/raw/` dan
`platformio.ini` tidak disentuh. Seluruh source CSV dijaga SHA256;
artefak Stage4/5/10 sebelumnya tidak ditimpa.

## II. Koreksi kualitas dan provenance historis

Inventaris yang dihasilkan:
`results/stage11_provenance_20261014/historical_provenance.csv`

| Kategori | Unit CSV | Keputusan |
|---|---:|---|
| CSV B32–B35 valid pada snapshot Stage3 | **83** | `DEV_ONLY_LABELS_UNVERIFIED` |
| CAW/B37 udara bersih pada daftar pengecualian | **6** | `EXCLUDED_CLEAN_AIR` |
| Total inventaris SHA256 di snapshot Stage2 | **89** | Tidak ada mismatch sumber |
| Spesimen fisik yang identitasnya **terverifikasi** | **0** | Tidak bisa dipakai klaim independensi |
| Akuisisi prospektif blind baru | **0** | `BLIND_TEST_BLOCKED` |

**Audit ulang kualitas pada 14 Oktober malam** menghasilkan
`results/stage11_quality_review_20261014_rerun/`:
`quality_review_flags.csv` dan `quality_review_summary.json`.
Seluruh 89 sumber tetap cocok SHA256. Dari 83 berkas kopi,
**83** memiliki label roast/origin belum diaudit fisik,
**83** tidak mempunyai ID spesimen/sesi yang dapat diverifikasi,
**8 berkas** termasuk empat sel UI-code/batch berulang,
dan **14 berkas** ditandai untuk pemeriksaan interval sample
(diagnostik 900–1100 ms). Kategori bisa tumpang-tindih;
**tidak ada sampel otomatis dibuang**, tidak ada nilai sensor
atau label CSV diubah, dan seluruh 83 sumber tetap berstatus
*historical development only*.

Sebelas berkas CSV B23–B26 lainnya masih terlihat dalam `data/raw/`,
tetapi **di luar snapshot canonical B32+**. Mereka **tidak
otomatis** menjadi pengganti blind test atau dipindahkan/dihapus.

Peningkatan bukan dengan mengedit data untuk memperoleh skor lebih
tinggi. Pemeriksaan canonical meliputi 5 siklus, indeks sampel,
fase, 10 kanal ADC MQ3/TGS, metadata, suhu–kelembapan, sel hilang
dan source SHA256. Nilai ADC nol/saturasi, kualitas respons relatif,
pergeseran baseline, serta potensi carryover adalah indikator
**review**, bukan dasar menghapus contoh berdasarkan prediksi model.
Sampel bermasalah harus ditandai dengan alasan dan disetujui reviewer
independen sebelum masuk data baru. Tidak ada label/sesi/lot
yang diisi dengan menebak dari nama CSV.

## III. Pemisahan data yang benar-benar independen

`scripts/stage11_provenance_guard.py` menerapkan **fail-closed**.
Contoh template registri kosong:
`results/stage11_provenance_20261014/prospective_registry_TEMPLATE.csv`.

Setiap akuisisi BARU wajib dicatat oleh pengambil sampel dan reviewer
yang berbeda, dengan:

- `blind_id` **UUIDv4 acak** (misalnya dibuat memakai
  `python -c "import uuid; print(uuid.uuid4())"`), bukan nomor urut
  atau kode kopi; `source_file` dan `source_sha256` aktual;
  `split`: `development`, `calibration`, atau `blind_final`.
- `physical_specimen_id`, `coffee_lot_id`, `roast_batch_id`,
  `operator_session_id`, `collection_date_utc` (timezone eksplisit),
  `operator_id` dan `firmware_build_id=g3-rc2-20261014`.
- `recording_condition`: `coffee`, `clean_air`, `other_voc`,
  atau `unknown_coffee`; `roast_evidence_id`, `origin_evidence_id`,
  `independent_reviewer`, `quality_review_id`.
- Label `roast_verified` dan `origin_verified` hanya boleh diisi
  untuk kopi pada development/calibration **setelah bukti
  spesimen fisik diperiksa reviewer**. Pada `blind_final` kolom
  ini wajib KOSONG; label final disimpan di *vault* custodian
  di luar checkout Git yang tidak diakses pembuat model.

Partisi ditolak jika ada file lama B32–B35/B37, SHA berubah,
format CSV tidak valid, metadata bukti kosong, tanggal sebelum
15 Oktober 2026 UTC, firmware lain tanpa kontrak yang ditinjau,
atau terdapat lot/spesimen/roast-batch/sesi/**hari UTC yang sama**
pada lebih dari satu partisi. Syarat hari yang disjoint bersifat
konservatif: mencegah sesi berbeda pada satu hari masuk train dan
test. Metadata `B32/B33` HMI **bukan** identifier lot fisik.

Pemeriksaan ini membuktikan konsistensi berkas dan klaim metadata;
**tidak otomatis membuktikan kebenaran fisik sertifikat**. Reviewer
harus memeriksa dokumen asal kopi, lot, roast (warna/Agtron atau
metode relevan yang ditetapkan sebelum collection), operator,
tanggal, suhu/RH, warm-up dan prosedur pembersihan chamber.

### Rancangan pembagian data

Gunakan **lot/spesimen baru yang tidak pernah masuk Stage2–10**.
Tetapkan kelompok sebelum data dibaca oleh pelatih model:

1. `development`: seluruh fitting model, praproses dan seleksi
   melalui grouped/nested CV antar-lot dan antar-sesi. Data historis
   B32–B35 boleh dipakai untuk eksplorasi terpisah, bukan sumber
   blind final dan tidak untuk mengklaim metrik final.
2. `calibration`: lot, sesi dan hari berbeda; fit calibrator,
   pilih threshold abstain, cek kondisi sensor; **tidak** digunakan
   untuk memilih ulang model setelah blind final dilihat.
3. `blind_final`: lot, spesimen, sesi dan hari lain;
   **dikumpulkan prospektif**, tidak disentuh untuk pemilihan
   model/fitur/threshold, hanya dievaluasi **sekali** oleh custodian
   setelah freeze prediksi/artefak. Siapkan udara bersih,
   noncoffee VOC, kopi origin dikenal dan belum dikenal.

**Perencanaan awal**, bukan klaim jumlah sampel telah tersedia:
untuk roast-only usulkan sekurangnya beberapa lusin spesimen
independen per kelas yang tersebar antar-lot/hari pada test final;
ukuran sampel pasti dan interval ketidakpastian ditentukan lewat
perhitungan kebutuhan sampel sebelum pengumpulan. Jika origin
sembilan kelas belum dapat dicakup dengan lot independen yang cukup,
**tunda origin deployment** daripada mengganti ID/label.

## IV. Hasil perbandingan ulang — development saja

`scripts/stage11_development_benchmark.py` menggunakan satu CSV
sebagai unit, empat held-out batch B32–B35, empat kandidat tetap,
fit scaler/model **di dalam training fold**. Tidak menyimpan model
produksi dan tidak memilih dari data blind yang belum ada.

| Model | Grup fitur | Benar/83 | Pooled macro-F1 | Mean fold macro-F1 | Recall medium |
|---|---|---:|---:|---:|---:|
| Dummy prior | response10 | 27 | 0,2373 | 0,1633 | 0,0000 |
| Logistic Regression L2 | response10 | 42 | 0,4954 | 0,4316 | 0,3333 |
| LDA shrinkage | response10 | 45 | 0,5389 | 0,4821 | 0,4444 |
| Random Forest | expanded82 | 45 | 0,5118 | 0,4898 | 0,2222 |

Perbandingan ini memperlihatkan LDA lebih seimbang pada sampel
`medium`, tetapi seluruh skor masih jauh dari kriteria usulan
dan label fisik belum diverifikasi. Perbedaan *pooled* dan
rerata fold harus dipertahankan; **tidak ada model yang
dipromosikan**. Nilai-nilai tersebut bukan uji buta.

Output hanya analisis:
`results/stage11_dev_benchmark_20261014/` (`summary.json`,
`development_fold_metrics.csv`, `development_oof_predictions.csv`).

## V. Pelaksanaan blind test kelak — terpisah dari peneliti model

1. **Custodian** memegang CSV asli, file registri dan bukti label.
   CSV asli memuat nama `D-/L-/M-` serta label UI sehingga **tidak
   boleh** dibagikan kepada pelatih model ketika blind test.
2. Custodian memvalidasi semua provenance dan mengeluarkan
  `blind_final_features.csv` yang HANYA memiliki `blind_id`
  opak dan **82 fitur `f_*`** melalui
   `scripts/stage11_prospective_features.py` (jika kelas dan split
   baru memenuhi kontrak). Latih dan kalibrasi model dari
   partisi *lain*, bukan fitur final. ID UUIDv4 diurutkan secara
   leksikografis saat ekspor, sehingga urutan pengambilan tidak
   ikut diteruskan sebagai petunjuk kelas.
3. Sebelum membuka label, peneliti menyerahkan model/config
   frozen, schema/feature order, prosedur rejection, hash model,
   roster model tetap, dan CSV prediksi untuk **seluruh** ID
   holdout. Custodian mengunci hash registry, prediksi, dan
   komitmen hash vault label beserta identitas reviewer dan
   waktu freeze; simpan receipt yang diawasi terpisah.
4. **Hanya custodian** melepaskan label setelah prediction freeze
   dan menjalankan `scripts/stage11_blind_scoring.py` satu kali.
   Script menolak perubahan SHA, daftar model berbeda,
   ID hilang/duplikat, probabilitas tidak valid, label final
   terlepas sebelum freeze, dan label vault di dalam repo.
5. Script scorer roast yang disiapkan melaporkan accuracy,
   macro-F1 dengan abstain sebagai salah, recall per kelas,
   *coverage*, tingkat penolakan unknown dan Brier multiclass
   deskriptif. Evaluasi tambahan per sesi/lot, confidence calibration
   yang sah, interval ketidakpastian, dan **model klasifikasi origin**
   masih perlu pipeline tersendiri sebelum ada klaim siap produksi.
   Bandingkan seluruhnya
   dengan ambang yang **ditetapkan sebelum unblinding**. Jika
   gagal, status `NO_GO` dan kumpulkan **holdout baru** setelah
   perubahan model—jangan pakai ulang blind set yang telah dibuka
   untuk mengklaim evaluasi final yang independen.

Script ini hanya memverifikasi receipt dan struktur;
**integritas blind secara manusiawi tidak bisa diverifikasi oleh
kode saja**. Custodian independen wajib mengelola akses serta
memberikan sign-off manual. Output scorer sengaja tetap
`model_promotion_allowed=false` meski metriknya bagus.

### Cara menjalankan gate jika data BARU sudah terkumpul

Semua perintah di bawah bersifat **untuk sesi mendatang**, tidak
dijalankan pada alat selama Stage11. Jalankan dari root repository.

```powershell
# Custodian: registri baru berisi bukti verified, bukan template kosong.
python scripts/stage11_provenance_guard.py check-prospective `
  --registry "D:\private-custodian\prospective_registry.csv" `
  --raw-dir "D:\private-custodian\raw"

# Custodian: keluaran development/calibration/blind yang terpisah.
python scripts/stage11_prospective_features.py `
  --registry "D:\private-custodian\prospective_registry.csv" `
  --raw-dir "D:\private-custodian\raw" `
  --output-dir "D:\private-custodian\stage11_views_v1"

# Langkah berikutnya bukan perintah otomatis: custodian hanya menyerahkan
# blind_final_features.csv ke pengembang, tanpa raw/registry/label vault.
# Developer mengunci dan menyerahkan prediksi untuk setiap blind_id.
# Custodian membekukan hash/receipt, lalu memberi cap release label.

# Custodian SAJA, sesudah prediksi terkunci:
python scripts/stage11_blind_scoring.py `
  --registry "D:\private-custodian\prospective_registry.csv" `
  --raw-dir "D:\private-custodian\raw" `
  --predictions "D:\private-custodian\predictions_frozen.csv" `
  --labels "D:\private-custodian\labels_sealed.csv" `
  --freeze "D:\private-custodian\freeze_receipt.json" `
  --output "D:\private-custodian\final_once_score.json"
```

`freeze_receipt.json` wajib mencakup:
`registry_sha256`, `predictions_sha256`,
`custodian_labels_sha256`, `independent_custodian_id`,
`analyst_id`, `model_artifact_sha256`, `feature_schema_sha256`,
`predeclared_acceptance_rules_sha256`, `predeclared_model_ids`,
`prediction_freeze_utc`, dan `label_release_utc`. Hash dan
timestamp yang diisikan sendiri **bukan tanda tangan digital**;
receipt harus disahkan melalui prosedur pihak independen.

`predictions_frozen.csv`: `blind_id,model_id,predicted_roast,abstained,prob_dark,prob_light,prob_medium`.
`labels_sealed.csv`: `blind_id,condition,true_roast,origin_verified,label_evidence_id,independent_reviewer`.
Nilai `abstained` wajib string `true/false` dan ketiga probabilitas
numerik harus berjumlah 1. Saat `condition != coffee`,
`true_roast` dan `origin_verified` dikosongkan. Kedua contoh
di sini hanya skema, bukan bukti ada data/prediksi nyata.

**SOP fisik untuk collection mendatang:** siapkan lot dan
spesimen yang berbeda nyata per partisi; tentukan urutan uji
yang diacak dan catat pembawa sampel serta evidence identitas.
Tetapkan metode roast reference sebelum merekam sinyal; catat
warm-up, status kalibrasi, suhu/RH, pergantian sampel, periode
pembersihan chamber dan blank kontrol sesuai SOP hardware.
Hindari penggabungan kurva berbeda spesimen dan uji ulang
spesimen yang sama di sisi split lain. Setiap CSV mewakili
**satu akuisisi lima siklus**, bukan lima unit independen.

## VI. QA dan keputusan

- Inventaris 89 CSV hash/kontrak: PASS.
- Laporan flag kualitas per sumber 89 CSV: PASS; 8 berkas
  UI-code/batch berulang dan 14 interval sampling perlu review;
  tidak ada perubahan label atau sampel terhapus.
- Benchmark dev 4×4 fold: PASS, development only.
- Uji negatif lot, sesi, hari, duplikasi, label leakage,
  provenance reviewer, hash tampering: PASS pada synthetic fixtures.
- Uji ekspor 82 fitur dari fixture prospektif baru:
  development/calibration/holdout PASS, blind tanpa label/metadata
  sensitif; fixture sintetis **tidak dihitung dataset nyata**.
- Uji blind scorer hash-frozen, model roster, release timing,
  label vault: PASS pada synthetic fixtures (gate asli belum dipakai).
- Tes `test_stage11_development_benchmark.py` memverifikasi tiap
  file tepat satu prediksi holdout per model, kelas dan batch
  sesuai frozen Stage3, 4 model × 4 fold, tanpa split campur:
  **PASS retrospektif**.
- Regresi Stage2–6, Stage10, seluruh Stage11 dan compileall:
  **PASS offline** (tanpa membuka port serial).
- **Actual prospective registry independent**: BLOCKED (0 data baru).
- **Actual sealed unseen blind comparison**: BLOCKED (belum ada
  blind predictions dan independent label vault).
- **Firmware RC2, G3, model deployment**: NOT TOUCHED.

**Gate final: NO-GO.** Perbaikan kualitas historis berarti
peningkatan audit, pemisahan, dan pemeliharaan data; **tidak
menambah bukti spesimen atau meningkatkan skor AI dengan
mengedit data**. Tahap berikutnya membutuhkan pengumpulan data
independen dengan custodian dan reviewer fisik di lokasi.
