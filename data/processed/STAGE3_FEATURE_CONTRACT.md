# Kontrak fitur Stage 3 — Snapshot v1 (9 Oktober 2026)

**ADDENDUM PENTING:** Snapshot `stage3_v1/` adalah **HISTORIS dan tidak
boleh dipakai untuk model kopi**, karena CAW kini terkonfirmasi sebagai
udara bersih. Gunakan `data/processed/stage3_v2/` (83 file kandidat kopi)
berdasarkan `data/analysis/stage2_v2/`. Formula 62/82 dan kelompok fitur
tetap; hanya cohort/provenance yang dikoreksi.

Status semua matriks: **KANDIDAT PENELITIAN — BELUM DISETUJUI UNTUK TRAINING FINAL / DEPLOYMENT**.

## Ekstraksi

- Sumber: `data/analysis/stage2/file_manifest.csv` sebagai **snapshot ber-hash**, input CSV final B32–B35 saja; raw wajib sesuai `source_sha256`.
- Semua file bench udara bersih B37 dikecualikan menggunakan `data/analysis/bench_only_exclusions.csv` (fail-closed bila nama/hash bertentangan).
- Unit observasi: **satu file lengkap berisi lima siklus**, bukan lima unit independen.
- Baris event-only `PHASE_CHANGE` lama dibuang **di memori**, tidak pernah dari CSV raw. Setiap siklus memiliki fase purge lalu collect; `sample_idx` masing-masing fase harus utuh 1..N, timestamp sensor meningkat.
- Fitur dihitung tanpa label, tanpa scaler, imputasi global, PCA atau fitting apa pun. `extract_sensor_features(sensor_df)` merupakan fungsi bersama ekstraksi file/host; hanya menerima data sensor plus suhu/kelembapan.
- Baseline tiap kanal/siklus = median **5 sampel purging terakhir**. Respons relatif = `(mean(collect) - baseline) / max(abs(baseline), 1)`; deviasi collecting = standar deviasi sampel (`ddof=1`), slope = linear fit terhadap detik dari `millis()` pada fase collecting.
- Kelima siklus digabung dengan rerata dan standar deviasi (`ddof=1`) masing-masing fitur. Suhu/kelembapan = rerata semua frame dalam satu sesi. Varian diperluas menambahkan `mean collecting` mentah per kanal (mean5 dan std5); fitur ini mungkin sensitif terhadap gain/drift dan **belum dibenarkan secara fisik**.
- File dengan ADC NaN/out-of-range, indeks hilang, fase salah, atau suhu/kelembapan hilang **ditahan**, tidak diinterpolasi.

## Artefak di `data/processed/stage3_v1/`

| File | Fungsi |
|---|---|
| `candidate_features82.csv` | **86 file yang lolos kontrak ketat**, delapan kolom metadata status/provenance dan 82 kolom `f_*`. Label pada metadata **belum diverifikasi**. |
| `candidate_legacy62.csv` | 86 file yang sama, 62 fitur formula lama. **Jangan disamakan** dengan artefak 86-file sebelum Tahap 3. |
| `feature_groups.json` | Nama/urutan tepat tujuh kelompok fitur untuk ablation study Tahap 4; semua dibuat **a priori** sebelum melatih model. |
| `feature_quality.csv` | Statistik nilai dan ragam fitur secara deskriptif **hanya untuk review**, bukan dasar memilih fitur secara global. |
| `feature_rejections.csv` | Daftar ber-hash file yang ditahan karena gagal kriteria QA baru, beserta alasan. |
| `snapshot.json` | Hash manifest dan daftar source filename/SHA256, urutan ADC dan seluruh fitur, kandidat diterima/ditahan. |
| `summary.json` | Jumlah kandidat, kelompok fitur, distribusi label yang belum diverifikasi, dan batas klaim. |

## Kelompok fitur untuk ablation (belum dievaluasi kinerja)

| Grup | Jumlah fitur | Isi |
|---|---:|---|
| `response10` | 10 | Rerata respons relatif lima siklus per sensor. |
| `response20` | 20 | Respons relatif mean5 dan std5 per sensor. |
| `dynamic30` | 30 | Respons relatif, collecting SD, dan collecting slope (masing-masing mean5). |
| `dynamic32_environment` | 32 | Dynamic30 + rerata suhu/kelembapan. |
| `raw_collect10` | 10 | Rerata ADC collecting mean5 per sensor. |
| `legacy62` | 62 | Tiga statistik respons (mean5 + std5 per sensor) + suhu/kelembapan. |
| `expanded82` | 82 | Legacy62 + 20 fitur collecting mean5/std5; **bukan otomatis terbaik**. |

### Keputusan file bermasalah

`L-CAW_B34.csv` lolos validator skema umum Tahap 2, tetapi **sampel purging ke-8 pada siklus 1 tidak terekam**. Tahap 3 menahannya (`HOLD_FOR_QA_NOT_FEATURE_READY`), tanpa mengubah CSV. Snapshot Tahap 2 tetap 87 kandidat, **hasil fitur lolos Tahap 3 = 86**.

Output `data/processed/b32_b35_features_candidate.csv` yang lama juga memuat 86 baris, tetapi cohort **BERBEDA**: memiliki `L-CAW_B34.csv` dan belum memiliki `L-MING_B32_20261009_172056.csv`. Dari **85 file dengan nama+SHA yang sama**, 62 fitur lama vs baru cocok pada toleransi floating point (maksimum selisih absolut sekitar `4,8e-12`). Jangan bandingkan dua file 86 baris hanya melalui nomor urut.

## Reproduksi

    python scripts/test_feature_pipeline.py
    python scripts/test_stage3_feature_pipeline.py
    python scripts/stage3_feature_pipeline.py --output-dir data/processed/stage3_v2

Gunakan **direktori output baru** untuk eksperimen berikutnya. `--replace-derived` hanya untuk regenerasi sadar atas artefak turunan v1; tidak mengubah raw. Pada clone tanpa file raw tambahan B32 yang masih lokal di PC, proses **sengaja menolak hash/file hilang**. Jangan diam-diam mengurangi cohort agar perbandingan tampak lulus.

### Masuk Tahap 4 (belum dijalankan)

Hanya kolom `f_*` dalam grup pilihan yang menjadi `X`, label belum terverifikasi digunakan hanya setelah perjanjian evaluasi eksploratori. `sample_id`, `batch_id`, `origin`, `roast_level`, hash, filename, dan uptime **jangan masuk X**. `StandardScaler`, seleksi fitur, PCA dan seluruh estimator harus `fit` **hanya pada training fold**. Gunakan split grup batch minimal; identitas spesimen fisik, hari/urutan sesi serta label TEM/MUK/CAW perlu dipastikan sebelum klaim generalisasi atau rilis.
