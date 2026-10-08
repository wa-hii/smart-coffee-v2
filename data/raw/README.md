# Raw Acquisition Data

Folder ini menyimpan data mentah hasil akuisisi E-NOSE. Nilai raw CSV tidak
boleh diubah setelah pengambilan data.

## Kontrak akuisisi aktif mulai B32

Baseline yang saat ini dipakai untuk pengambilan data adalah B32:

- 5 run per file;
- purging 25 detik per run;
- collecting 5 detik per run;
- 10 kanal gas dengan adc_mq3, bukan adc_mq9;
- temperature dan humidity dari SHT30 wajib ikut tersimpan;
- file B32 aktif berada langsung di data/raw/*_B32.csv.

Validasi canonical:

    python scripts/validate_b32_acquisition.py

Validator tersebut hanya membaca file B32 dan tidak menjalankan training model.
Untuk seluruh B32–B35 gunakan:

    python scripts/test_acquisition_suite.py
    python scripts/audit_b32_dataset.py

Beberapa berkas B33–B35 yang direkam sebelum bugfix `54d3321` masih mengandung
baris event `PHASE_CHANGE` tanpa nilai sensor. Validator mengklasifikasikan
baris itu sebagai metadata-only; jangan hapus atau ubah CSV asli. Ekstraksi
dan plot perlu mengecualikannya hanya pada saat dibaca. Field suhu/kelembapan
dapat bernilai null jika SHT30 gagal; ini harus dicatat sebagai missing,
tidak diinterpolasi sembarangan.

Satu file berisi lima siklus, namun tidak identik dengan lima spesimen kopi
independen. `timestamp` firmware adalah uptime millisecond; untuk sampel baru
perlu identitas spesimen, session UID, waktu kalender, dan versi firmware.

## Data lama MQ9

Semua raw CSV yang header-nya masih menggunakan adc_mq9 dipertahankan tanpa
modifikasi di:

    data/raw/legacy_mq9/

Struktur subfolder lama dipertahankan di bawah folder tersebut. Data legacy
tidak dihapus dan tidak menjadi bagian dari QA akuisisi B32.

## Data MQ3 sebelum B32

Raw data lain yang sudah menggunakan MQ3 tetapi dibuat sebelum baseline B32
tetap dipertahankan pada lokasi historisnya. Data tersebut tidak otomatis
dianggap memenuhi kontrak akuisisi B32.

## Scope saat ini

Fokus project saat ini adalah pengambilan dan validasi raw data. Training model
AI dan deployment Raspberry Pi belum dijalankan dalam tahap ini.

## Autosave dari Nextion ke laptop

Untuk pengambilan data tanpa menjalankan 3_collect_data.py secara manual,
gunakan background listener:

    scripts/lcd_acquisition_service.py

Listener menunggu COM5 dan membuat CSV berdasarkan metadata yang dikirim
ATmega saat START ditekan dari halaman pTake. Metadata meliputi sample_id,
roast_level, origin_code, batch_id, dan filename.

- data sementara: data/raw/.incoming/
- data selesai: data/raw/*.csv
- run terputus: data/raw/incomplete/

Folder runtime tersebut tidak masuk Git.
