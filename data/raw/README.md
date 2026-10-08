# Data Mentah Akuisisi E-Nose

Folder ini menyimpan data mentah hasil akuisisi E-Nose. Nilai CSV mentah tidak
boleh diubah setelah pengambilan data.

## Kontrak akuisisi aktif mulai B32

Acuan konfigurasi akuisisi yang digunakan saat ini dimulai dari B32:

- 5 siklus per file;
- purging 25 detik per siklus;
- collecting 5 detik per siklus;
- 10 kanal gas dengan adc_mq3, bukan adc_mq9;
- suhu dan kelembapan dari SHT30 disimpan apabila pembacaan valid;
- file B32 aktif berada langsung di data/raw/*_B32.csv.

Perintah validasi khusus B32:

    python scripts/validate_b32_acquisition.py

Validator tersebut hanya membaca file B32 dan tidak melatih model AI.
Untuk seluruh B32–B35 gunakan:

    python scripts/test_acquisition_suite.py
    python scripts/audit_b32_dataset.py

Beberapa berkas B33–B35 yang direkam sebelum perbaikan `54d3321` masih mengandung
baris event `PHASE_CHANGE` tanpa nilai sensor. Validator mengklasifikasikan
baris itu sebagai baris khusus metadata; jangan hapus atau ubah CSV asli. Ekstraksi
dan grafik perlu mengecualikannya hanya pada saat dibaca. Nilai suhu/kelembapan
dapat bernilai null jika SHT30 gagal; ini harus dicatat sebagai data hilang,
tidak diinterpolasi sembarangan.

Satu file berisi lima siklus, tetapi tidak identik dengan lima spesimen kopi
independen. `timestamp` firmware adalah waktu aktif MCU dalam milidetik; untuk sampel baru
perlu identitas spesimen, ID sesi unik, waktu kalender, dan versi firmware.

## Data lama MQ9

Semua CSV mentah dengan nama kolom adc_mq9 dipertahankan tanpa
modifikasi di:

    data/raw/legacy_mq9/

Struktur subfolder lama dipertahankan di bawah folder tersebut. Data historis
tidak dihapus dan tidak menjadi bagian dari QA akuisisi B32.

## Data MQ3 sebelum B32

Data mentah lain yang sudah menggunakan MQ3 tetapi dibuat sebelum acuan B32
tetap dipertahankan pada lokasi historisnya. Data tersebut tidak otomatis
dianggap memenuhi kontrak akuisisi B32.

## Ruang lingkup saat ini

Fokus yang sudah teruji adalah pengambilan dan validasi data mentah. Kandidat
ekstraksi fitur MQ3 sudah tersedia, tetapi pelatihan model AI pada B32–B35
dan penerapannya pada Raspberry Pi belum dijalankan.

## Penyimpanan otomatis dari Nextion ke laptop

Untuk pengambilan data tanpa menjalankan 3_collect_data.py secara manual,
gunakan layanan penerima yang berjalan di latar:

    scripts/lcd_acquisition_service.py

Layanan penerima menunggu COM5 dan membuat CSV berdasarkan metadata yang dikirim
ATmega saat START ditekan dari halaman pTake. Metadata meliputi sample_id,
roast_level, origin_code, batch_id, dan filename.

- data sementara: data/raw/.incoming/
- data selesai: data/raw/*.csv
- data pengambilan terputus: data/raw/incomplete/

Folder data sementara tersebut tidak dimasukkan ke Git.
