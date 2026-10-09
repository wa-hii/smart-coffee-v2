# Tahap 2 — Audit provenance, distribusi, kualitas sinyal dan drift kandidat

**Tanggal:** 9 Oktober 2026

**Repo/branch:** Smart Coffee E-Nose v2 / `wahyu`
**Status:** audit read-only dan artefak QC **selesai untuk snapshot lokal**; validasi label/spesimen fisik **P0 TERHAMBAT**.

## 1. Ruang lingkup dan metodologi

Sumber: raw CSV final MQ3 B32+ di `data/raw/`, skema `scripts/acquisition_schema.py`, validator `scripts/validate_acquisition.py`, berita acara operator bench B37, dan manifest pengecualian `data/analysis/bench_only_exclusions.csv`.

Alat `scripts/stage2_dataset_audit.py` **tidak membuka COM5**, tidak memodifikasi CSV raw, dan tidak mengubah firmware/Nextion. Menghasilkan SHA256 per file, metadata, jumlah sensor/event/parsial, missing ADC/SHT, indikasi saturasi/0, interval sampling `millis()`, serta lima siklus data yang dipisahkan per fase. Empat batch B32–B35 dibandingkan tanpa menganggap file atau siklus sebagai spesimen kopi independen.

## 2. Inventaris dataset (snapshot 9 Oktober)

| Batch | Jumlah CSV final | Interpretasi |
|---|---:|---|
| B32 | 19 | Kandidat data kopi, label fisik belum diaudit |
| B33 | 20 | Kandidat data kopi, termasuk event historis metadata-only |
| B34 | 22 | Kandidat data kopi |
| B35 | 26 | Kandidat data kopi; sebagian kode berkas memiliki pengulangan |
| B37 | 2 | **Uji udara bersih** dari Nextion: dikecualikan training/evaluasi kopi |
| **Total** | **89** | **87 kandidat belum disetujui + 2 bench-only** |

**87/87** CSV B32–B35 dan **89/89** B32+ lulus validator **struktur canonical**. Ini **tidak** berarti 87 spesimen berbeda, kualitas sensor terkalibrasi, atau label kopi valid. Distribusi kandidat roast: light **31**, medium **28**, dark **28**. Ada **23 kombinasi kode sample_id**, tidak seluruhnya terwakili merata pada empat batch.

Manifest `data/analysis/stage2/file_manifest.csv` mencatat SHA256, schema, metadata, status label, serta field `physical_specimen_id`, `operator_session_id`, `collection_date_utc`, dan `firmware_hash` **kosong secara eksplisit**, karena belum ada bukti independen dari raw untuk mengisinya. Tanggal pada nama file/timestamp filesystem tidak menggantikan waktu akuisisi yang terkonfirmasi.

## 3. Kelengkapan kelas, asal dan independensi

- Dari **23 kode sampel × 4 batch = 92 sel**, terdapat **9 sel kosong** dan **4 sel memiliki lebih dari satu file**. Sel kosong terdapat pada kombinasi batch untuk `D-RAT`, `L-CAW`, `L-GAY`, `M-CAW`, dan `M-MUK`. Pengulangan dalam batch muncul pada `D-CAT`, `L-GRB`, `L-MING`, dan `M-MUK`.
- Tidak ditemukan satu `sample_id` yang memiliki beberapa string `origin` berbeda pada snapshot B32–B35. Ini hanya pemeriksaan **konsistensi teks**, bukan verifikasi bahwa asal, produsen, kebun, roasting dan varietas tidak tercampur secara semantik.
- Definisi `TEM/MUK/CAW` perlu dikonfirmasi dengan operator dan bukti kemasan/eksperimen. `CAW` tersimpan sebagai kode literal, bukan geografi yang sudah dikonfirmasi.
- Lima siklus pada satu file **berkorelasi**; pengulangan dua file di batch yang sama bukan bukti dua spesimen independen. Tanpa `physical_specimen_id`, sesi unik, tanggal, urutan pengukuran, dan catatan perlakuan, dataset **tidak boleh di-random-split berdasarkan siklus**.
- File `L-MING_B37.csv` / `M-MING_B37.csv` **bukan sampel kopi** walaupun label UI menunjukkan L/M-MING. Keduanya ditahan dari seluruh data latih/evaluasi roast/origin melalui manifest pengecualian per SHA256. Semua raw dipertahankan.

## 4. Kualitas akuisisi dan indikasi fisik (eksploratori)

- Skema B32–B35 memiliki **10 kanal gas dengan MQ3** dan SHT30, 5 siklus nominal, masing-masing 25 s purging dan 5 s collecting. File lama B33–B35 dapat memuat metadata event-only; dipisahkan saat dihitung, **tidak dihapus dari raw**.
- Audit memeriksa missing/saturasi dan rentang sampel. Laporan fase `phase_metrics.csv` memiliki **4.450 pasangan file–siklus–kanal** (89×5×10), termasuk 100 baris dari dua run B37 untuk keperluan QC, bukan fitting AI.
- **Proxy perubahan selama purging:** `abs(median(purge pertama 5 sampel)-median(purge terakhir 5 sampel))/max(abs(median purge terakhir),1)`. Median kandidat untuk TGS822 sebesar **22,4%**, TGS2620 **7,4%**, MQ8 **7,2%**, TGS813 **6,7%**, TGS2602 **5,3%**, dan lebih rendah pada sebagian kanal lain. Ini menandakan perubahan sinyal dalam fase purge yang **perlu ditelusuri**, bukan langsung membuktikan carryover atau sensor rusak.
- **Proxy pergeseran baseline antar-batch:** dilakukan dengan mencocokkan sample_id yang ada di B32 dan B35, kemudian membandingkan median dari 5 titik akhir purging setiap siklus. Terdapat **180 pasangan sample_id–kanal = 18 kode × 10 sensor**. Median absolut pergeseran baseline B35 terhadap B32 misalnya **11,6% pada TGS2620**, **6,3% pada TGS2611**, **5,0% pada TGS813**, dan **0,7% pada MQ3**. Pengaruh massa/biji, temperatur, kelembapan, waktu/hari, urutan sesi, warm-up, serta kalibrasi **belum dapat dipisahkan**.
- Antrian review anomali `outlier_review.csv`: **33 flag file–kanal**, diperoleh dengan robust score dari median respons relatif antarpengukuran dengan sample_id sama (minimal empat file). **Jangan menghapus otomatis**; nilai fitur mendekati nol atau MAD kecil dapat memperbesar skor.

**Grafik dan batas fase:** event-only tidak boleh menjadi titik plot sensor. Analisis ini menggunakan `purging` dan `collecting` secara terpisah per siklus sehingga tidak menghubungkan nilai sensor melintasi metadata kosong. Generator grafik `scripts/plot_sensor_pattern.py` diperkuat agar mengecualikan file bench ber-hash dan menahan batch baru B36+ tanpa review, sehingga plot per-origin tidak menganggap udara bersih sebagai kopi.

## 5. Hasil QA/QC dan batas klaim

Jalankan dari root:

    python scripts/test_stage2_dataset_audit.py
    python scripts/test_stage2_plot_provenance.py
    python scripts/stage2_dataset_audit.py --output-dir data/analysis/stage2 --replace-derived
    python scripts/plot_sensor_pattern.py --dry-run --sample-only
    python scripts/test_acquisition_suite.py
    python scripts/test_feature_pipeline.py
    python -m compileall -q scripts

Tes negatif untuk audit mencakup CSV schema MQ9, ketidakcocokan SHA256 bench, penolakan output ke raw, benturan nama output, serta ketiadaan file bench lokal pada clone lain. Tes plot mengecek bahwa bench B37 tidak tampil sebagai kopi, batch belum direview tidak otomatis diplot, dan perubahan isi file bench memicu fail-closed.

**Pengujian aktual: PASS** untuk test_stage2_dataset_audit.py, test_stage2_plot_provenance.py, kontrak Tahap 0–1, pipeline fitur dan HMI (12 halaman/23 event). Build PlatformIO mega2560 dan nextion_test SUCCESS. Validator canonical B32+ 89/89 PASS; inventaris B32–B35 87/87 PASS. Generator grafik dry-run origin dan sample PASS tanpa menulis PNG; kedua file B37 bench dikecualikan dari input grafik.

**Bukti yang dapat diklaim:** integritas berkas, inventaris lengkap untuk snapshot, hash, cakupan kelas, proxy eksploratori dan pengecualian bench. **Bukan bukti:** kualitas identifikasi kopi, spesimen independen, generalisasi model, kalibrasi sensor, penyebab drift, dan kesiapan deployment.

## 6. Keputusan dan pekerjaan tertunda

**Tahap 2 software/audit: diselesaikan secara reproduksibel. Tahap 2 metodologi/validasi provenance: BELUM LULUS untuk promosi data training.**

1. Konfirmasi arti `TEM/MUK/CAW` serta label roast/origin dari dokumentasi fisik sampel; pisahkan kategori origin geografis, produsen, dan jenis proses pengolahan biji.
2. Untuk setiap pengambilan berikutnya, wajib metadata `session_id`, `physical_specimen_id`, waktu kalender (WIB/UTC), operator, urutan sesi, batch, massa/volume/suhu/humiditas, waktu warm-up, kalibrasi, dan versi firmware. Simpan sebagai manifest eksternal terlebih dahulu jika protokol CSV belum siap.
3. Tinjau 33 flag dan proxy baseline besar terhadap plot/riwayat pemanasan, tanpa langsung membuang file. Uji sampel fisik yang sama lintas hari untuk memisahkan repeatability dan drift.
4. Rancang split evaluasi dengan **batch terpisah minimal**; identitas spesimen harus mencegah irisan train/test. Verifikasi fold yang kekurangan kode kelas sebelum menjalankan Tahap 3–5.
5. Artefak fitur kandidat B32–B35 yang lama memuat **86 observasi** dan **belum diregenerasi otomatis** meskipun raw kini 87 file; Tahap 3 harus membuat output versi baru dengan manifest input yang dibekukan. Tidak ada training/inferensi yang dijalankan di Tahap 2.

**Keluaran:** `data/analysis/stage2/` dan skrip regresi, tanpa perubahan data mentah/EEPROM/firmware. Keterangan tindakan fisik Tahap 1 yang dikonfirmasi operator berada di laporan bench B37 dan SOP.
