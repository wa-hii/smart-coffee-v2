# B6 — Salah klasifikasi LIGHT menjadi DARK pada uji fisik

Tanggal: 11 November 2026 (WIB). Branch: wahyu.
Status: **inferensi fisik menghasilkan kelas di Nextion, tetapi akurasi sampel pertama gagal**.

## Fakta yang dikonfirmasi

- Setelah firmware SVM30 berhasil dipasang, pengguna melaporkan kondisi pHome, pompa dan valve normal pada IDLE.
- Pengguna membuka pTestRun dan menyelesaikan proses AI Test; hasil akhir yang muncul adalah **DARK**, sedangkan sampel sebenarnya **LIGHT**.
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
