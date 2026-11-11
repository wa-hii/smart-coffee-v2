# B6 — Salah klasifikasi LIGHT menjadi DARK pada uji fisik

Tanggal: 11 November 2026 (WIB). Branch: wahyu.
Status: **inferensi fisik menghasilkan kelas di Nextion, tetapi akurasi sampel pertama gagal**.

## Fakta yang dikonfirmasi

- Setelah firmware SVM30 berhasil dipasang, pengguna melaporkan kondisi pHome, pompa dan valve normal pada IDLE.
- Pengguna membuka pTestRun dan menyelesaikan proses AI Test; hasil akhir yang muncul adalah **DARK**, sedangkan sampel sebenarnya **LIGHT**.
- **Identitas asal sampel telah dikonfirmasi pengguna: L-TOR (Light Toraja).**
- Asal kopi, jumlah dan temperatur sampel, usia pemanasan sensor, kurva ADC selama proses, 30 fitur hasil MCU, serta skor SVM fisik tidak tersedia. Firmware standalone memang tidak menyimpan 900 pembacaan ke CSV maupun telemetri fitur.
- Kelas yang muncul membuktikan fungsi inferensi lokal dapat menghasilkan output Nextion, **tidak membuktikan** ketepatan model maupun karakteristik ADC saat uji.

## Pemeriksaan kode dan model

- Firmware mengambil data SensorArray dengan empat kanal utama model: TGS822 (indeks 0), TGS2602 (6), TGS816 (9), MQ8 (7); urutan ini cocok dengan ekstraktor C++ dan referensi Python.
- Kontrak input adalah 30 siklus, 25 detik purging dan 5 detik collecting; 900 pembacaan 1 Hz. Inferensi hanya dipanggil setelah akumulator menyatakan data lengkap. Belum ada bukti bahwa seluruh fase valve secara fisik sama dengan indikator LCD.
- Model original SVM RBF 30 fitur menggunakan **nilai ADC absolut tanpa baseline correction per siklus**. Distribusi bisa bergeser akibat perubahan perangkat, pemanasan sensor, udara, asal/bentuk/massa sampel, aliran, dan kontaminasi aroma. Semua adalah kemungkinan, bukan diagnosis pasti.
- Pembacaan ADC pada firmware tidak disertai pemeriksaan gangguan per sampel seperti flatline atau saturasi, sementara adcAvailable hanya menandakan modul ADS tersedia berdasarkan deteksi awal.
- SVM akan selalu memilih salah satu dari DARK, LIGHT, MEDIUM saat inputnya dianggap valid; belum ada mekanisme calibrated out-of-distribution rejection.

## Bukti replay offline 199 rekaman

Analisis read-only dilakukan dengan scripts/diagnose_svm30_b6_replay.py dari golden reference privat. **Ini bukan pembacaan langsung dari alat**.

| Label sebenarnya | Prediksi DARK | LIGHT | MEDIUM | Total |
|---|---:|---:|---:|---:|
| DARK | 52 | 0 | 8 | 60 |
| LIGHT | 2 | 47 | 10 | 59 |
| MEDIUM | 18 | 5 | 57 | 80 |
| Total | 72 | 52 | 75 | 199 |

Total **156/199 (78,4%)** prediksi replay sesuai label. Sampel LIGHT yang salah menjadi DARK pada replay ialah L-CAT_B80.csv dan L-GAW_B71.csv. Pada corpus yang sama **199/199 prediksi native C++ identik dengan model Python**; porting SVM tidak menunjukkan masalah kesetaraan pada rekaman yang diuji. Angka 78,4% adalah kecocokan corpus replay campuran, **bukan evaluasi prospektif independen** atau akurasi fisik.

Kasus replay L-CAT_B80 memiliki beberapa fitur MQ8 dengan z-score sekitar -2,3 sampai -2,5; L-GAW_B71 menunjukkan metrik TGS2602 sekitar +1,6 sampai +1,9. **Tidak boleh menganggap kasus fisik pengguna memiliki nilai sensor serupa** tanpa pembacaan saat uji.

Jangan membalik label DARK menjadi LIGHT: dari 72 prediksi DARK replay, 52 di antaranya memang DARK dan 18 lainnya MEDIUM. Memodifikasi label hasil hanya menyembunyikan masalah.

Output analisis: private/svm30_b6_light_dark_replay_diagnosis.json (gitignored).

## Addendum — Perbandingan khusus origin TOR (L-TOR)

Pengguna mengklarifikasi bahwa sampel fisik yang menampilkan
DARK adalah **L-TOR**. Pada 199 rekaman golden replay,
terdapat **34 rekaman origin TOR**, dengan distribusi:

| Label TOR sebenarnya | Prediksi DARK | Prediksi LIGHT | Prediksi MEDIUM | Total |
|---|---:|---:|---:|---:|
| DARK | 8 | 0 | 2 | 10 |
| LIGHT | **0** | **13** | **1** | **14** |
| MEDIUM | 1 | 0 | 9 | 10 |
| **Total** | **9** | **13** | **12** | **34** |

Jadi **13/14 (92,9%) rekaman L-TOR replay sesuai label
LIGHT**, dan satu-satunya yang tidak sesuai
adalah **L-TOR_B70.csv → MEDIUM**; **tidak ada
L-TOR → DARK** pada corpus replay ini. Empat kesalahan
TOR total terdiri atas dua DARK→MEDIUM, satu
MEDIUM→DARK, dan satu LIGHT→MEDIUM.

Ini adalah **pencocokan label pada replay yang tersedia**,
yang bisa mencakup sampel training dan bukan
validasi independen. Ukuran sampel L-TOR hanya
14 dan belum tersedia nilai ADC dari run fisik;
ketiadaan error LIGHT→DARK dalam 14 replay
**tidak membuktikan** bahwa model mustahil
mengeluarkan DARK untuk kopi Toraja baru.

**Implikasi:** Salah klasifikasi L-TOR fisik lebih jauh
dari pola contoh L-TOR yang telah diuji. Prioritaskan
perbandingan nilai ADC/final 30 fitur pada run fisik
terhadap distribusi L-TOR replay, termasuk respons
TGS822, TGS2602, TGS816, MQ8, identitas perangkat,
conditioning udara/sensor, serta waktu fase valve.
Belum ada dasar untuk menukar label, mengganti
parameter SVM, atau menyalahkan hardware tertentu.

## Pemeriksaan aman berikutnya

1. Catat identitas dan asal kopi yang baru diuji, roast sebenarnya, massa/posisi, kondisi suhu dan lama pemanasan sensor, serta apakah valve benar-benar berpindah selama fase purging/collecting.
2. Cek bahwa sensor ADS terdeteksi di status Nextion. Ini belum membuktikan sinyal ADC tidak menyimpang.
3. Jika hardware aman dan SOP konsisten, ulang satu kali pengukuran sampel LIGHT yang sama. Catat hasil dan keadaan fisik fase; jangan menjalankan serial monitor COM5 karena DTR dapat mereset ATmega.
4. Untuk diagnosis yang dapat membedakan kerusakan ADC vs pergeseran fitur vs kelemahan model, butuh firmware diagnostik opt-in yang dapat **melaporkan ringkasan ADC 4 sensor, vektor 30 fitur dan skor pasangan SVM**, tanpa perlu menyimpan CSV dan tanpa Raspberry Pi sebagai bagian dari inferensi. Menyiapkan firmware ini membutuhkan QA dan izin flashing baru; tidak diterapkan diam-diam.
5. Setelah bukti beberapa pengulangan LIGHT/MEDIUM/DARK terkumpul, lakukan evaluasi validasi model dan kemungkinan retraining/preprocessing/penolakan input out-of-distribution. Jangan mengubah mapping label atau model hanya berdasar satu observasi.

## Keputusan rilis

**B6 output fisik: PASS untuk satu kali alur klasifikasi MCU–Nextion.**
**B6 ketepatan: FAIL untuk sampel LIGHT yang dilaporkan.**
Tidak ada akses serial, reset, flashing, kalibrasi EEPROM, modifikasi TFT, atau perubahan firmware fisik pada sesi diagnosis ini. Akar masalah fisik **belum diketahui**.

## Addendum — Pengujian kedua L-TOR menghasilkan LIGHT (sesuai label)

Operator mengonfirmasi bahwa sampel dan kemasan uji fisik
berasal dari sumber **L-TOR yang sama** dengan dataset
sebelumnya. Pada **pengujian kedua** menggunakan L-TOR,
halaman hasil Nextion kali ini menampilkan **LIGHT**
(sesuai roast sebenarnya), sedangkan Coffee Origin
dan Roast Probability/Confidence masih **N/A**.

| Uji fisik | Roast sebenarnya | Prediksi MCU/Nextion | Penilaian |
|---|---|---|---|
| 1 | LIGHT (TOR) | DARK | Salah |
| 2 | LIGHT (TOR) | LIGHT | Benar |

Kedua sesi memperlihatkan bahwa jalur AI MCU–Nextion
dapat menghasilkan kelas, tetapi prediksinya **tidak
konsisten untuk sampel/kemasan yang sama**. Dua
pengamatan ini **tidak cukup** untuk menghitung akurasi
yang representatif, menentukan repeatability statistik,
atau memastikan penyebab perbedaan.

Pemeriksaan kode `src/main.cpp` fungsi
`updateNextionInferenceResult()` mengonfirmasi
bahwa firmware standalone **secara sengaja** mengisi
`tOrigin = N/A`, `tRConf = N/A`,
`tOConf = N/A`, serta mengatur bar
`jLight`, `jMedium`, `jDark` = 0.
Klasifikasi origin **belum dimodelkan** dan model
SVM roasting belum menghasilkan probabilitas
terkalibrasi. **N/A tidak menunjukkan kerusakan LCD
atau kegagalan AI Test**.

Prioritas berikutnya adalah mengamankan konsistensi
pengujian roasting melalui kontrol kondisi fisik
dan telemetri empat sensor utama. Pengembangan
origin classifier dan kalibrasi probabilitas
adalah pekerjaan lanjutan yang terpisah;
tidak boleh mengarang angka origin/probabilitas
atau menyamakan skor SVM dengan persentase.

**Belum ada akses COM5, pembacaan ulang hardware,
reflash, perubahan EEPROM, atau update HMI.**
