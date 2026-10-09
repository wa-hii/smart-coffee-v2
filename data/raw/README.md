# Data Mentah Akuisisi E-Nose

Folder ini menyimpan data mentah hasil akuisisi E-Nose. Nilai CSV mentah tidak
boleh diubah setelah pengambilan data.

## Peringatan provenance B37 — bench udara bersih (9 Oktober 2026)

**Konfirmasi lanjutan operator (9 Oktober): seluruh kode CAW juga berarti
UDARA BERSIH**, bukan origin kopi. Pada raw tercatat `L-CAW_B33.csv`,
`L-CAW_B34.csv`, `L-CAW_B35.csv`, dan `M-CAW_B35.csv`; seluruh
file tersebut dikecualikan bersama dua file B37, dengan SHA256 masing-masing
di `data/analysis/bench_only_exclusions.csv`. File tidak diubah. Daftar
ini mencakup pemakaian kode CAW pada B33–B35, sedangkan **semua batch B37**
harus dianggap udara bersih meskipun pilihan UI adalah origin kopi.

Berdasarkan konfirmasi operator bahwa selang berada pada **udara bersih** selama
uji Nextion batch B37, `L-MING_B37.csv` dan `M-MING_B37.csv` adalah **data
uji perangkat**, **bukan pengukuran kopi light/medium dari origin MING**.
Label kopi di CSV hanya merekam pilihan UI pada saat pengujian. **Jangan
gunakan dua file ini sebagai data training/evaluasi roast/origin.**

Jangan mengubah, memindahkan, atau merelabel CSV mentah. Catatan pengecualian
yang dapat diperiksa otomatis (nama file + SHA256) berada di
`data/analysis/bench_only_exclusions.csv`; detail QA ada dalam
`docs/reports/2026-10-09_TAHAP1_BENCH_B37_UDARA_BERSIH.md`.
Ekstraktor kandidat MQ3 yang ada saat ini memang membatasi input pada B32–B35.
Pipeline yang kelak membaca batch lain **wajib** menerapkan pengecualian ini.

## Audit provenance snapshot B32–B35 (9 Oktober 2026)

`scripts/stage2_dataset_audit.py` menghasilkan `data/analysis/stage2/file_manifest.csv`
ber-hash SHA256, matriks sample_id–batch, serta indikator kualitas dan perubahan
baseline tanpa menulis ulang raw. Pada mesin pengukuran saat audit terdapat 87
file B32–B35 dan dua file B37 bench. **87 file B32–B35 adalah kandidat
berlabel belum terverifikasi, bukan data training yang otomatis diizinkan.**
Perlu konfirmasi identitas spesimen kopi, semantik TEM/MUK/CAW, sesi/tanggal
akuisisi, dan riwayat pemanasan. Lihat `docs/reports/2026-10-09_TAHAP2_PROVENANCE_KUALITAS_DATASET.md`.

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
