# Riset dataset ilmiah E-Nose kopi dan persiapan Tahap 6

**Tanggal:** 10 Oktober 2026

**Proyek:** Smart Coffee E-Nose v2 (ATmega2560 + Nextion + Raspberry Pi 5)

**Status:** pencarian sumber ilmiah + unduhan dua dataset asli terverifikasi
+ benchmark terpisah **SELESAI OFFLINE**; penambahan langsung ke dataset
lokal, model final dan deployment **NO-GO**.

## 1. Tujuan, metode dan batas perbandingan

Tujuan mencari data **pengukuran sensor nyata dari karya ilmiah** untuk
mengatasi keterbatasan **83 akuisisi kopi kandidat** alat lokal, enam
rekaman udara bersih, dan risiko unknown yang ditemukan di Tahap 5.
Data yang hanya berupa gambar, hasil simulasi/dummy, atau kelas label
yang tak berkaitan **tidak dihitung sebagai tambahan train**.

Sensor lokal yang terverifikasi dari kontrak `scripts/acquisition_schema.py`:
`TGS822, MQ135, MQ3, TGS2611, TGS2620, TGS2600, TGS2602,
MQ8, TGS813, TGS816`, ditambah suhu dan kelembapan SHT30.
Protokol **5 siklus × (purging 25 s + collecting 5 s) pada ~1 Hz**;
angka yang direkam merupakan ADC digital, bukan resistansi
sensor yang sudah dikalibrasi. Label target calon adalah roasting
`light/medium/dark` dan origin kopi.

Kriteria penilaian data eksternal: (1) karya ilmiah bisa diverifikasi,
(2) data pengukuran asli bisa diakses, (3) sensor dan sinyal sesuai,
(4) target label sesuai, (5) provenance/format/split dapat direproduksi,
(6) lisensi dan izin redistribusi jelas. Jika salah satu komponen
berbeda, data tidak langsung digabung ke model lokal.

## 2. Hasil penelusuran publikasi dan akses data

| Sumber yang diverifikasi | Publikasi dan data | Kemiripan terhadap alat | Keputusan |
|---|---|---|---|
| **CoffeePow-4 / Aroma-7 (2025)** | Stefanone et al., *Results in Engineering*, DOI `10.1016/j.rineng.2025.106309`; Zenodo DOI `10.5281/zenodo.15425922`. Dua file CSV asli dapat diunduh, checksum diterbitkan | Sama-sama E-Nose dan mencakup kopi/udara bersih; **BME688 10 langkah pemanasan, bukan kanal MQ/TGS/ADC**; label produk/krim, **bukan roasting** | **UNDuh PASS, evaluasi benchmark terpisah, BUKAN transfer dataset** |
| **Colombian Coffee (2020 dataset; 2009 paper)** | Rodriguez Gamboa & Duran Acevedo, Mendeley `10.17632/7spd6fpvyk.1`, terkait *Sensors* 2010 `10.3390/s10010036`, 58 sampel HQ/AQ/LQ, 8 gas sensor, 1 Hz 300 s | **TGS813 sama**; kelas mutu kopi, bukan origin/roasting | Metadata terverifikasi, **HTTP 403** dari API Mendeley saat mencoba akses; **tidak diunduh atau dievaluasi** |
| **Coffee E-Nose 9 MOS (2023)** | Aghdamifar et al., *Sensors and Actuators B*, `10.1016/j.snb.2023.134229`, 9 kanal MOS, kelas varietas/kualitas | **6 sensor sama** (`MQ135/MQ8/TGS2620/TGS813/TGS822/MQ3`) tetapi MQ9/MQ4/MQ136 berbeda, juga fase 50/50/50 s | Referensi **hardware paling dekat**; artikel menyatakan **data on request**, unduhan asli publik tidak ditemukan |
| **Roasting E-Nose TGS (2024)** | *Sensing and Bio-Sensing Research*, DOI `10.1016/j.sbsr.2024.100632` | Target roasting dan beberapa TGS relevan | Artikel menyatakan **data on request**, bukan dataset training bebas |
| **Roast reflectance AS7265X (2025)** | Mendeley `10.17632/zpv2kjcyh7.1`, data 18-band multispektral Agtron | Bisa membantu standar label roasting, tetapi **bukan aroma/gas sensor** | Tidak dipakai melatih model E-Nose |

URL sumber primer dan atribusi:

- https://www.sciencedirect.com/science/article/pii/S2590123025023813
- https://zenodo.org/records/15425922
- https://github.com/mrc-rossoni/TransformerOdorClassification
- https://data.mendeley.com/datasets/7spd6fpvyk/1
- https://www.mdpi.com/1424-8220/10/1/36
- https://doi.org/10.1016/j.snb.2023.134229
- https://doi.org/10.1016/j.sbsr.2024.100632
- https://data.mendeley.com/datasets/zpv2kjcyh7/1

## 3. Unduhan asli dan integritas

Menggunakan `scripts/research_external_coffee_datasets.py` dari Zenodo
dan memeriksa MD5 resmi **sebelum menyimpan atau memproses**.

| Dataset | MD5 resmi (PASS) | SHA256 hasil unduhan | Ukuran |
|---|---|---|---:|
| CoffeePow-4.csv | `81d373ba934046490862e3964ca77392` | `34f5e8a4875375ff5f7d802f0e958b3cdcf1c273dbecae1051589f79bea99bd4` | 490.704 byte |
| Aroma-7.csv | `94562d5bb44d7ee7d28100dd00367975` | `4c1195ccdacd33e8f04593186786623a3a8fb6a5a78ad6b77224b1f4066d98aa` | 656.988 byte |

Cache lokal: `data/external/zenodo_15425922/`, **diabaikan Git**
dan tidak pernah dipindahkan ke `data/raw/`.

- CoffeePow-4 memiliki **35.830 baris = 3.583 rangkaian 10
  langkah**. Distribusi label indeks 0/1/2/3:
  **880/1.010/974/719**.
- Aroma-7 memiliki **47.504 baris**; **4.750 rangkaian lengkap**
  dan **4 pembacaan terakhir** tidak lengkap untuk rangkaian sepuluh.
  Tidak diinterpolasi dan tidak diubah dalam raw.
- Semua **3.583 rangkaian CoffeePow-4 ada identik pada awal Aroma-7**;
  Aroma-7 hanya menambah 1.167 rangkaian kelas 4–6.
  **Kedua dataset tidak independen** dan tidak boleh dihitung sebagai
  8.333 rangkaian unik.
- Skema sumber asli **dua kolom**
  `Resistance Gassensor,label`; yang diekstraksi hanya 10 langkah
  resistansi per rangkaian, bukan 8/10 sensor ADC yang sepadan
  dengan proyek lokal.
- Berkas tidak memuat ID spesimen fisik atau sesi akuisisi.
  Interpretasi indeks kelas 0=udara, 1–3=tiga produk kopi,
  4–6=krim dalam benchmark biner adalah **asumsi berdasar urutan
  README peneliti**, belum bukti label per spesimen pada file.

## 4. Benchmark terpisah pada dataset ilmiah asli

Metode: `scripts/evaluate_external_coffee_enose.py`.
10 langkah resistansi per rangkaian di-`log10`, model berupa
Dummy, Logistic Regression, LDA shrinkage, SVM RBF, Random Forest,
dan StandardScaler **dilatih dalam split training** (bukan global).
Parameter tetap dan seed tetap. Tidak ada dummy data digunakan
untuk hasil penelitian. Total **40 evaluasi** pada kombinasi
2 dataset × 2 tugas × 2 skema split × 5 algoritma.

Dua skema diagnostik:
1. `stratified_random`: 80/20 acak terstratifikasi; berisiko
   rangkaian berdekatan secara fisik masuk train dan test.
2. `within_class_tail`: 20% akhir **urutan tiap kelas** sebagai
   uji; memperketat kontinuitas lokal, tetapi **tidak
   membuktikan sesi/hari atau spesimen independen**.

**Skor contoh Random Forest:**

| Tugas | Macro-F1 random | Macro-F1 tail |
|---|---:|---:|
| CoffeePow-4 4 kelas | **0,906** | **0,501** |
| CoffeePow-4 udara vs tiga kopi (pemetaan indeks diasumsikan) | 0,929 | 0,866 |
| Aroma-7 7 kelas | **0,950** | **0,690** |

Model SVM pada biner Aroma-7 memperoleh **1,000 macro-F1**
di split tail internal ini; **bukan** hasil perangkat kita,
tidak ada pemisahan sesi fisik, dan tidak ada jaminan performa
untuk unknown coffee atau merek lain. Jangan memindahkan
threshold, bobot sensor atau probabilitas dari sana ke MQ/TGS.

Perbedaan skor acak vs tail, terutama klasifikasi empat/tujuh
kelas, menunjukkan kepekaan evaluasi terhadap metode split.
Kinerja peer-reviewed paper menggunakan model dan split
berbeda; **angka di atas adalah eksperimen kami sendiri,
bukan reproduksi skor publikasi penulis**.

Semua metrik/fold/class dan hash:
`results/external_coffee_enose_v1/`; tidak ada model final disimpan.

## 5. Temuan penelitian dan kelanjutan Tahap 6

**Tidak ditemukan data mentah publik yang sudah terbukti kompatibel
langsung dengan 10 sensor dan label tiga level roasting alat kita.**
Penelitian paling dekat di 2023 menawarkan **6/10 sensor sama tetapi
data perlu diminta kepada penulis**. Menggunakan kolom resistansi
BME688 sebagai `adc_tgs822` dan seterusnya adalah **manipulasi
tak sah**; tidak dilakukan.

Prioritas berikutnya untuk memperoleh validasi fisik:

1. Minta akses dataset mentah 2023 dan 2024 pada penulis. Jika
   diberikan, catat lisensi, versi/cek hash, sampel, satuan,
   protokol fase, label dan pemisahan spesimen; lakukan
   **benchmark eksternal terpisah lebih dulu**.
2. Kumpulkan batch lokal **baru** dan terkontrol, minimal
   medium udara bersih, aroma kopi berbagai roast, dan
   nonkopi/unknown berbeda. Simpan `physical_specimen_id`,
   `session_id`, urutan/tanggal, suhu/kelembapan, massa,
   batch, roast reference dan pemanasan sensor. Jumlah
   replika serta durasi ditetapkan **sebelum pengambilan**,
   bukan direkayasa dari data yang sudah ada.
3. Pisahkan set train/tuning/calibration dari **spesimen dan
   sesi prospektif yang dibutakan**, tidak menggunakan B32–B35
   berulang sebagai satu-satunya evaluasi akhir.
4. Rancang detektor *coffee presence* yang dilatih/diuji pada
   alat **lokal** terlebih dahulu, diikuti klasifikasi roast
   dan kebijakan unknown dengan risiko false confident yang
   disepakati. Jangan menggunakan confidence threshold
   heuristik dari hasil Tahap 5 untuk produksi.

**Tahap 6 persiapan (tanpa promosi model):** membuat
`scripts/stage6_release_gate.py` dan output
`results/stage6_release_gate_v1/decision.json` yang
memeriksa status Tahap 5, provenance dataset luar,
serta mengeluarkan **model_promotion_allowed=false** dan
**AI_TEST=N/A** sampai gerbang prospektif terpenuhi.
Tidak ada file `.joblib` final, flash/Nextion upload,
atau komunikasi perangkat pada pekerjaan ini.

## 6. Gerbang keputusan dan QA

**Riset sumber ilmiah, unduhan Zenodo, verifikasi hash dan
benchmark eksternal: PASS OFFLINE.** Kesesuaian untuk augmentasi
training lokal dan promosi model: **NO-GO**.

Uji regresi baru:

    python scripts/test_external_coffee_enose.py
    python scripts/test_stage6_release_gate.py

**Hasil QA lintas proyek yang telah dijalankan — PASS:**

| Pengujian | Hasil aktual |
|---|---|
| `test_external_coffee_enose.py` | **PASS**, validasi MD5 publisher atas data asli, schema, overlap, split, determinisme metrik, penolakan perubahan raw |
| `test_stage6_release_gate.py` | **PASS**, larangan promosi lokal atau menandai data luar sebagai training E-Nose |
| `test_stage5_validation.py`, `test_stage4_model_benchmark.py` | **PASS**, metode LOBO dan unknown lama tidak berubah |
| `test_stage3_feature_pipeline.py`, `test_stage2_dataset_audit.py`, `test_stage2_plot_provenance.py` | **PASS** |
| `test_bench_stage1_passive_qa.py`, `test_stage0_contract.py`, `test_stage1_firmware_contract.py` | **PASS** |
| `test_acquisition_suite.py` | **89/89 file CSV lokal lulus validator struktur** (tidak termasuk dua CSV Zenodo) |
| `verify_nextion_atmega_contract.py` | **PASS**, 12 halaman dan 23 event |
| `pio run -e mega2560 -e nextion_test` | **2/2 SUCCESS** |
| `python -m compileall -q scripts`, `git diff --check` | **PASS**; peringatan perubahan line-ending LF/CRLF tidak fatal |

Tidak ada tes integrasi hardware ataupun kalibrasi fisik pada tahap ini.
Kesimpulan ilmiah dan hasil pelatihan luar tidak dipromosikan
menjadi akurasi produk. **Dataset asli dari Zenodo bersumber pada
publikasi yang benar-benar ada; hasil benchmark adalah evaluasi
kami sendiri dan bukan duplikasi angka penulis publikasi.**
